"""埋め P13（docs/polyfills.md）。殻の workflow cancel <run>: Archon の cancel を打ち、その後に run の持ち主のプロセスの木に残った物を止める。

止めた Archon の cancel が止めるのは、切り離した持ち主（--detach）のプロセスグループだけ（packages/core/src/services/run-owner-stop.ts）。
AI のノードの provider（Claude）は、持ち主がノードごとに detached で起こす別のプロセス（packages/core/src/providers/process-provider.ts）で
自分のセッションに居るので、cancel の後も親が 1 になって残り、その下の claude と claude が起こしたプロセスも残る。子の run のノードも
同じ持ち主の中で走るので同じ。前で起こした run（--detach の無い workflow run）は、cancel が拒んで何も止めない。

- 選び: workflow get <run> --json の status が running で、親の run が無い（根の）run だけ。持ち主は metadata の execution_owner
  （host・pid・uid）で、この機械・この利用者の物に限る。その pid に、last_activity_at（born）より前に始まり、Archon の本体（命令の頭の
  最後の語）の workflow の命令を走らせるプロセスが居れば生きた持ち主。居なければ持ち主は先に消えている。どちらでもない物（別の命令・
  後から始まった番号の再利用）が居れば、何も止めない。
- 数え上げ: cancel を打つ前に、lib/tree_run.py の tree_members で木の仲間を数える。生きた持ち主は known に入れ、親子の鎖が切れる前に
  別のセッションの provider とその下を拾う。持ち主が先に消えた run は、持ち主の番号のグループとセッションに残った物を拾う
  （docs/polyfills.md の P1 の実測。番号の再利用は born で見る）。
- 止め: cancel の後に、数えた仲間のうち生きた物とその子孫を lib/tree_run.py の stop_group で止める。cancel が拒んだ前の run の持ち主も
  止める（Archon の拒みの文が勧める、前の命令を割り込みで止めるのと同じ SIGTERM。run は failed になり、resume で続けられる）。
- 出し: 止めた本数と、止めた後も残った物（pid とコマンドの名）を、それぞれ 1 行で標準エラーに出す。残りが在れば終了の値は 1、
  無ければ cancel の値。
抜け道: 数えた後・cancel の前に持ち主が新しく起こした子と、cancel の前に持ち主が消えて別のセッションに残った provider（番号の
つながりが無い）は拾わない。子の run だけを cancel した時は、持ち主が根の run の物で子の物だけを見分けられないので、何も止めない。
"""
import os
import socket
import subprocess
import sys
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from bin._lib import place

LIB = Path(__file__).resolve().parents[2] / "lib"
if str(LIB) not in sys.path:   # lib/ の部品は互いを名だけで import する
    sys.path.append(str(LIB))

import tree_run  # noqa: E402

childsweep = place.shared("childsweep")

NAME = "works-factory"
OWNER_KEY = "execution_owner"   # packages/workflows/src/schemas/workflow-run.ts の readExecutionOwner が読む鍵
RUNNING = "running"


class _Reaped:
    """stop_group に渡す長。持ち主はこの殻の子でないので、回収した長として渡す（グループを凍らせず、番号の再利用を born で見る）"""

    returncode = 0

    def __init__(self, pid: int):
        self.pid = pid

    def poll(self) -> int:
        return self.returncode


def cancel(head: list[str], argv: list[str], env: Mapping[str, str], cwd: str | None) -> int:
    """argv（workflow cancel <run> …）を Archon に渡し、run の木に残った物を止める。head は Archon を起こす命令の頭、cwd は --cwd の値"""
    run_id = argv[2] if len(argv) > 2 and not argv[2].startswith("-") else None
    tree = before_cancel(head, run_id, env, cwd) if run_id else None
    code = subprocess.run([*head, *argv], env=env).returncode
    if tree is None:
        return code
    owner, born, known = tree
    members, why = tree_run.tree_members(owner, known, born)
    if members is None:
        say(f"cancel の後に run {run_id} のプロセスを数えられない（{why}）")
        return 1
    alive = tree_run.living(members)
    if not alive:
        return code
    tree_run.stop_group(_Reaped(owner), born=born, known=known)
    members, why = tree_run.tree_members(owner, known, born)
    left = tree_run.living(members) if members is not None else alive
    stopped = len(alive.keys() - left.keys())
    if stopped:
        held = "。持ち主も止めたので run は failed になる（workflow resume で続けられる）" if owner in alive and owner not in left else ""
        say(f"Archon の cancel の後に残っていた run {run_id} のプロセス {stopped} 本を止めた{held}")
    if left:
        say(f"止めた後も残ったプロセス: {named(left)}")
        return 1
    return code


def before_cancel(head: list[str], run_id: str, env: Mapping[str, str], cwd: str | None) -> tuple[int, float, dict] | None:
    """cancel を打つ前の run の木 (持ち主の番号, born, known)。止める物が無い・決められない run は None"""
    got = subprocess.run([*head, "workflow", "get", run_id, "--json", *(["--cwd", cwd] if cwd else [])], env=env,
                         capture_output=True, text=True, encoding="utf-8")
    try:
        found = owner_of(childsweep.last_json(got.stdout))
    except ValueError:
        return None
    if found is None:
        return None
    owner, born = found
    rows, _ = tree_run.ps_all()
    if rows is None:
        return None
    known = {}
    if owner in rows:
        if rows[owner].started > born + tree_run.REUSE_SLACK or not runs_workflow(owner, head[-1]):
            return None
        known[owner] = rows[owner].started
    members, _ = tree_run.tree_members(owner, known, born)
    known.update({pid: m.started for pid, m in (members or {}).items()})
    return owner, born, known


def owner_of(run: object) -> tuple[int, float] | None:
    """workflow get --json の run の持ち主の番号と born（last_activity_at のエポック秒）。根の running の run で、この機械・この利用者が
    持つ物だけ"""
    if not isinstance(run, dict) or run.get("status") != RUNNING or run.get("parent_run_id"):
        return None
    owner = childsweep.run_metadata(run.get("metadata")).get(OWNER_KEY)
    if not isinstance(owner, dict) or owner.get("host") != socket.gethostname():
        return None
    pid = owner.get("pid")
    if not isinstance(pid, int) or pid <= 1 or owner.get("uid", os.getuid()) != os.getuid():
        return None
    try:
        return pid, datetime.fromisoformat(run["last_activity_at"]).timestamp()
    except (KeyError, TypeError, ValueError):
        return None


def runs_workflow(pid: int, entry: str) -> bool:
    """pid のプロセスが Archon の本体 entry の workflow の命令（run・resume・respond など）を走らせているか。serve などは持ち主でも止めない"""
    done = subprocess.run([tree_run.PS, "-o", "args=", "-p", str(pid)], stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    return f" {entry} workflow " in f" {done.stdout.strip()} "


def named(members: dict) -> str:
    """残った仲間を pid とコマンドの名（ps の comm。プロセスの記憶を読まない欄）で並べた字"""
    done = subprocess.run([tree_run.PS, "-o", "pid=,comm=", "-p", ",".join(map(str, members))], stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    names = dict(line.strip().partition(" ")[::2] for line in done.stdout.splitlines() if line.strip())
    return "、".join(f"pid {pid}（{names.get(str(pid), '').strip() or '名を読めない'}）" for pid in members)


def say(text: str) -> None:
    print(f"{NAME}: {text}", file=sys.stderr)

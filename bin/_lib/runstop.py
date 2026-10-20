"""埋め P13（docs/polyfills.md）。殻の workflow cancel <run>: Archon の cancel を打ち、その後に run のプロセスで残った物を止める。

止めた Archon の cancel が止めるのは、切り離した持ち主（--detach）のプロセスグループだけ（packages/core/src/services/run-owner-stop.ts）。
AI のノードの provider（Claude）は、持ち主がノードごとに detached で起こす別のプロセス（packages/core/src/providers/process-provider.ts）で
自分のセッションに居るので、cancel の後も親が 1 になって残り、その下の claude と claude が起こしたプロセスも残る。子の run のノードも
同じ持ち主の中で走るので同じ。前で起こした run（--detach の無い workflow run）は、cancel が拒んで何も止めない。前の命令を Ctrl-C で
止めた run（failed）も、AI のノードのプロセスが残る。

- 印は 2 つ。1 つは run と子の run（Archon の記録の parent_run_id で辿る）の完全な id（workflow runs が出す 8 字の短い id で打たれても、
  Archon の cancel と同じく workflow get で直す。読めなければ打たれた字のまま）で、AI のノードと bash のノードのプロセスは env の
  WORKFLOW_ID に自分の run の id を持つ（packages/workflows/src/exec-environment.ts）。子孫は env を継ぐ。もう 1 つは走っている根の run の
  生きた持ち主（metadata の execution_owner。この機械・この利用者の物で、last_activity_at より前に始まり、Archon の本体の workflow の
  命令を走らせるプロセス）で、持ち主とその子孫を親子の鎖で拾う。持ち主のグループとセッションでは拾わない（前の命令の持ち主は
  シェルのジョブの長で、`| tee` の相手が同じグループに居る）。拾うのは自分の利用者のプロセスだけで、殻と殻の祖先は拾わない。
- 数え上げ: cancel を打つ前に 2 つの印で数え、持ち主が消えて親子の鎖が切れた後も、数えた物の子孫を辿れるようにする。持ち主の木を
  数えない run（running でない・子の run・持ち主が別の機械か別の利用者か居ない・持ち主の番号に別の物が居る）は、その訳を 1 行で出し、
  WORKFLOW_ID だけで探す。env を読めない環境では、その訳と手で探す命令を 1 行で出す。
- 止め: cancel の後に数え直し、生きた持ち主が居れば先に持ち主だけへ SIGTERM を送って抜けるのを（KILL_GRACE 秒まで）待ち、残りの生きた物へ SIGTERM、KILL_GRACE 秒の内に消えなければ SIGKILL を 1 本ずつ送る（グループへは送らない）。
  cancel が拒んだ前の run の持ち主も止める（Archon の拒みの文が勧める、前の命令の割り込みと同じ SIGTERM。run は failed になる）。
- 出し: 止めた物と、止めた後も残った物（pid とコマンドの名）を、それぞれ 1 行で標準エラーに出す。残りが在れば終了の値は 1。
  殻が前の run の持ち主を止めたら、Archon が書き換えない子の run のうち running の物を workflow abandon で cancelled にする
  （片付けられなければ、残った子の run の id と片付けの命令を 1 行で出す）。残りが無ければ 0（Archon の拒みの文の割り込みは要らない）。ほかは cancel の値。
抜け道: env の WORKFLOW_ID を外した子孫は、数える前に親子の鎖が切れていると拾わない。
"""
import os
import re
import signal
import socket
import subprocess
import sys
import time
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
RUN_ENV = "WORKFLOW_ID"
RUN_IN_ENV = re.compile(rf"(?:^|\s){RUN_ENV}=(\S+)")
ENV_OPTION = "-E" if sys.platform == "darwin" else "e"   # ps が args の後ろに env を足す旗（macOS と procps）
VALUE_FLAGS = ("--cwd",)   # cancel が読む値つきの旗（packages/cli/src/cli.ts の cancel は positionals[2]・--json・--cwd だけを読む）
WAIT = 0.1


def cancel(head: list[str], argv: list[str], env: Mapping[str, str], cwd: str | None) -> int:
    """argv（workflow cancel <run> …）を Archon に渡し、run のプロセスで残った物を止める。head は Archon を起こす命令の頭、cwd は --cwd の値"""
    typed = run_id_of(argv)
    if typed is None:
        return subprocess.run([*head, *argv], env=env).returncode
    archon = Archon(head, env, cwd)
    run = archon.get(typed)
    run_id = run["id"] if isinstance(run, dict) else typed
    ids = archon.family(run_id)
    owner, known = archon.owner_tree(run_id, run)
    before, why = members(ids, known)
    if before is None:
        say(f"cancel の前に run {run_id} のプロセスを数えられない（{why}）")
    elif why:
        say(f"プロセスの env を読めず（{why}）、{RUN_ENV} で探していない。手で探すなら: "
            f"ps -A {ENV_OPTION} -ww -o pid=,args= | grep -F {RUN_ENV}={run_id}")
    known.update({pid: m.started for pid, m in (before or {}).items()})
    code = subprocess.run([*head, *argv], env=env).returncode
    alive, why = members(ids, known)
    if alive is None:
        say(f"cancel の後に run {run_id} のプロセスを数えられない（{why}）")
        return 1
    if not alive:
        return code
    names = commands(alive)
    left, why = stop(ids, known, owner)
    if left is None:
        say(f"止めた後の run {run_id} のプロセスを数えられない（{why}）")
        return 1
    stopped = [pid for pid in alive if pid not in left]
    held = code != 0 and owner in stopped   # Archon が拒んだ前の run の持ち主を殻が止めた
    if stopped:
        tail = ("。持ち主も止めたので run は failed になる。Archon の拒みの文の割り込みは要らない（続けるなら workflow resume、"
                "手放すなら workflow abandon）") if held else ""
        say(f"Archon の cancel の後に残っていた run {run_id} のプロセス {len(stopped)} 本を止めた: {listed(stopped, names)}{tail}")
    if held:
        archon.abandon_running(run_id, ids)
    if left:
        say(f"止めた後も残ったプロセス: {listed(left, {**names, **commands(left)})}")
        return 1
    return 0 if held else code


def run_id_of(argv: list[str]) -> str | None:
    """workflow cancel の後ろの最初の位置の語（旗とその値の後ろでも）"""
    words = iter(argv[2:])
    for word in words:
        if word in VALUE_FLAGS:
            next(words, None)
        elif not word.startswith("-"):
            return word
    return None


class Archon:
    """cancel を打つ前に run の記録を読む口"""

    def __init__(self, head: list[str], env: Mapping[str, str], cwd: str | None):
        self.head, self.env, self.cwd = head, env, cwd

    def read(self, *args: str) -> object:
        done = subprocess.run([*self.head, *args, "--json", *(["--cwd", self.cwd] if self.cwd else [])], env=self.env,
                              capture_output=True, text=True, encoding="utf-8")
        return childsweep.last_json(done.stdout)

    def get(self, typed: str) -> dict | str:
        """workflow get の run。typed は workflow runs が出す短い id でもよく、run の id は完全な物。読めなければ訳"""
        try:
            run = self.read("workflow", "get", typed)
        except ValueError as error:
            return f"run を読めない: {error}"
        return run if isinstance(run, dict) and isinstance(run.get("id"), str) else "run の形が読めない"

    def family(self, run_id: str) -> set[str]:
        """run と、Archon の記録で辿れる子の run（孫も）の id。一覧を読めなければ訳を出して run だけ"""
        try:
            listing = self.read("workflow", "runs", "--all", "--limit", str(childsweep.LIST_LIMIT))
            runs = listing.get("runs") if isinstance(listing, dict) else None
            if not isinstance(runs, list):
                raise ValueError("runs の一覧が無い")
        except ValueError as error:
            say(f"run {run_id} の子の run を引けない（{error}）。子の run の {RUN_ENV} では探さない")
            return {run_id}
        ids, todo = {run_id}, [run_id]
        while todo:
            parent = todo.pop()
            for run in runs:
                if isinstance(run, dict) and run.get(childsweep.PARENT_KEY) == parent and run.get("id") not in ids:
                    ids.add(run["id"])
                    todo.append(run["id"])
        return ids

    def abandon_running(self, run_id: str, ids: set[str]) -> None:
        """持ち主を止めた後も running で残る子の run（Archon は持ち主の止まった run の子の run を書き換えない）を workflow abandon で
        cancelled にする。片付けられなければ、残った子の run の id と片付けの命令を 1 行で出す"""
        left = []
        for kid in sorted(ids - {run_id}):
            run = self.get(kid)
            if isinstance(run, dict) and run.get("status") == RUNNING:
                done = subprocess.run([*self.head, "workflow", "abandon", kid, *(["--cwd", self.cwd] if self.cwd else [])],
                                      env=self.env, capture_output=True, text=True, encoding="utf-8")
                if done.returncode != 0:
                    left.append(kid)
        if left:
            say(f"run {run_id} の子の run が running のまま残った: {'、'.join(left)}。片付けるなら: "
                + "; ".join(f"{' '.join(self.head)} workflow abandon {kid}" + (f" --cwd {self.cwd}" if self.cwd else "") for kid in left))

    def owner_tree(self, run_id: str, run: dict | str) -> tuple[int | None, dict[int, float]]:
        """run（get の物）の生きた持ち主の番号と known（{持ち主の番号: 開始時刻}）。持ち主の木を数えない run は訳を出して (None, {})"""
        found = run if isinstance(run, str) else owner_of(run)
        if isinstance(found, tuple):
            found = live_owner(*found, self.head[-1])
        if isinstance(found, str):
            say(f"run {run_id} の持ち主のプロセスの木は数えない（{found}）。{RUN_ENV} で探す")
            return None, {}
        pid, started = found
        return pid, {pid: started}


def owner_of(run: dict) -> tuple[int, float] | str:
    """workflow get --json の run の持ち主の番号と born（last_activity_at のエポック秒）。根の running の run で、この機械・この利用者が
    持つ物だけ。ほかは数えない訳"""
    if run.get("status") != RUNNING:
        return f"run は {RUNNING} でない（{run.get('status')}）"
    if run.get("parent_run_id"):
        return f"子の run で、持ち主は根の run {run['parent_run_id']} の物"
    owner = childsweep.run_metadata(run.get("metadata")).get(OWNER_KEY)
    if not isinstance(owner, dict):
        return f"run の記録に持ち主（{OWNER_KEY}）が無い"
    if owner.get("host") != socket.gethostname():
        return f"持ち主は別の機械 {owner.get('host')} に居る"
    pid = owner.get("pid")
    if not isinstance(pid, int) or pid <= 1:
        return f"持ち主の番号が読めない（{pid!r}）"
    if owner.get("uid", os.getuid()) != os.getuid():
        return f"持ち主は別の利用者（uid {owner.get('uid')}）"
    try:
        return pid, datetime.fromisoformat(run["last_activity_at"]).timestamp()
    except (KeyError, TypeError, ValueError):
        return "run の last_activity_at が読めない"


def live_owner(pid: int, born: float, entry: str) -> tuple[int, float] | str:
    """pid が last_activity_at（born）より前に始まり、Archon の本体 entry の workflow の命令を走らせていれば (pid, 開始時刻)。
    ほかは数えない訳"""
    rows, why = tree_run.ps_all()
    if rows is None:
        return why
    if pid not in rows:
        return f"持ち主 pid {pid} はもう居ない"
    if rows[pid].started > born + tree_run.REUSE_SLACK:
        return f"持ち主の番号 pid {pid} に、run の最後の動きより後に始まった別のプロセスが居る"
    if not runs_workflow(pid, entry):
        return f"持ち主の番号 pid {pid} に、今の Archon の源 {entry} の workflow の命令でない物が居る"
    return pid, rows[pid].started


def runs_workflow(pid: int, entry: str) -> bool:
    """pid のプロセスが Archon の本体 entry の workflow の命令（run・resume・respond など）を走らせているか。serve などは持ち主でも止めない"""
    done = subprocess.run([tree_run.PS, "-o", "args=", "-p", str(pid)], stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    return f" {entry} workflow " in f" {done.stdout.strip()} "


def members(ids: set[str], known: dict[int, float]) -> tuple[dict | None, str | None]:
    """run のプロセス {pid: _Proc}（ゾンビを除く）と、env を読めなかった訳。印は env の WORKFLOW_ID が ids の物と、known（前に数えた
    {pid: 開始時刻}。今の表に同じ開始時刻で居る物）で、その子孫も拾う。表を読めなければ (None, 訳)"""
    rows, why = tree_run.ps_all()
    if rows is None:
        return None, why
    envs, blind = run_ids_in_env()
    found = {pid for pid, t in known.items() if pid in rows and abs(rows[pid].started - t) <= tree_run.REUSE_SLACK}
    found |= {pid for pid, run_ids in (envs or {}).items() if pid in rows and run_ids & ids}
    children: dict[int, list[int]] = {}
    for pid, row in rows.items():
        children.setdefault(row.ppid, []).append(pid)
    todo = list(found)
    while todo:
        for kid in children.get(todo.pop(), ()):
            if kid not in found:
                found.add(kid)
                todo.append(kid)
    mine, cur = set(), os.getpid()
    while cur in rows and cur not in mine:
        mine.add(cur)
        cur = rows[cur].ppid
    uid = os.getuid()
    return {pid: rows[pid] for pid in found - mine if rows[pid].uid == uid and not rows[pid].stat.startswith("Z")}, blind


def run_ids_in_env() -> tuple[dict[int, set[str]] | None, str | None]:
    """プロセスごとの env の WORKFLOW_ID の値 {pid: {値}}。env は ps の args の後ろに足される字で、env の無い ps の args を頭から外して
    読む（args の中の同じ字は印にしない）。読めなければ (None, 訳)"""
    plain, full = ps_args(), ps_args(ENV_OPTION)
    if plain is None or full is None:
        return None, f"ps -A {ENV_OPTION} が表を返さない"
    if "=" not in env_part(plain.get(os.getpid()), full.get(os.getpid(), "")):
        return None, f"ps -A {ENV_OPTION} が自分のプロセスの env も見せない"
    return {pid: set(RUN_IN_ENV.findall(env_part(plain.get(pid), line))) for pid, line in full.items()}, None


def ps_args(*options: str) -> dict[int, str] | None:
    try:
        done = subprocess.run([tree_run.PS, "-A", *options, "-ww", "-o", "pid=,args="], stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError:
        return None
    if done.returncode != 0:
        return None
    rows = {}
    for line in done.stdout.splitlines():
        pid, _, args = line.strip().partition(" ")
        if pid.isdigit():
            rows[int(pid)] = args
    return rows


def env_part(args: str | None, line: str) -> str:
    return line[len(args):] if args is not None and line.startswith(args) else line


def stop(ids: set[str], known: dict[int, float], owner: int | None = None) -> tuple[dict | None, str | None]:
    """run のプロセスへ SIGTERM、KILL_GRACE 秒の内に消えなければ SIGKILL を送り、止めた後も残った物を返す。表を読めなければ (None, 訳)。
    回ごとに数え直し（数えた物は known に足す）、その回に生きていた物へ 1 本ずつ送る。owner（生きた持ち主の番号）が居れば、先に
    持ち主だけへ SIGTERM を送り、抜けるのを（KILL_GRACE 秒まで）待ってから残りを送る。持ち主の後始末（子の run の状態の書き込み）を
    残りの SIGKILL が切らないため"""
    alive, _ = members(ids, known)
    if owner in (alive or {}):
        known.update({owner: alive[owner].started})
        try:
            os.kill(owner, signal.SIGTERM)
        except OSError:
            pass
        end = time.monotonic() + tree_run.KILL_GRACE
        while time.monotonic() < end and owner in (members(ids, known)[0] or {}):
            time.sleep(WAIT)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        alive, why = members(ids, known)
        if not alive:
            return alive, why
        known.update({pid: m.started for pid, m in alive.items()})
        for pid in alive:
            try:
                os.kill(pid, sig)
            except OSError:
                pass   # 間に消えた・送れない（送れない相手は数え直しで残りとして名指しする）
        end = time.monotonic() + tree_run.KILL_GRACE
        while time.monotonic() < end and (members(ids, known)[0] or {}):
            time.sleep(WAIT)
    return members(ids, known)


def commands(members: dict) -> dict[int, str]:
    """pid ごとのコマンドの名（ps の comm。プロセスの記憶を読まない欄）"""
    done = subprocess.run([tree_run.PS, "-o", "pid=,comm=", "-p", ",".join(map(str, members))], stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    pairs = (line.strip().partition(" ")[::2] for line in done.stdout.splitlines() if line.strip())
    return {int(pid): name.strip() for pid, name in pairs if pid.isdigit() and name.strip()}


def listed(pids, names: dict[int, str]) -> str:
    return "、".join(f"pid {pid}（{names.get(pid, '名を読めない')}）" for pid in pids)


def say(text: str) -> None:
    print(f"{NAME}: {text}", file=sys.stderr)

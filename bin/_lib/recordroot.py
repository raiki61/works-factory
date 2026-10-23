"""殻の workflow run が終わった(承認ノードで止まった)後に、その run の記録の置き場を 1 行で告げる(issue #810 の 2)。

部品の返す値(最後の段の JSON)はファイルの指し(`{"type":"archon_artifact","run_id":…,"path":"review.json"}`)で、そのファイルの
フォルダは run の出力に出ない。置き場は Archon の記録(`workflow get <run> --json` の `terminal_record.artifacts.root`)から読む。承認で止まった
run は終わりの記録が無いので、run の行の `output_root` から Archon と同じ形で組む(root_of)。

run の見つけ方: 殻は run を子のプロセスで起こすので、その番号を知っている。Archon が run の記録に付ける持ち主(`metadata.execution_owner`。
host と pid)が子の番号と同じ run を、`workflow runs --json` から選ぶ。同じ対象に同じグラフを同時に起こしても取り違えない。
見つからない・読めない時は、黙らずにそう言う(run は終わっているので、止めない)。
"""
import os
import signal
import socket
import subprocess
import sys
from collections.abc import Callable, Mapping

from bin._lib import place

childsweep = place.shared("childsweep")

LABEL = "記録の置き場"


def owned_run(listing: object, pid: int, host: str) -> str | None:
    """`workflow runs --json` の物から、持ち主が（host, pid）の run の id。無ければ None"""
    runs = listing.get("runs") if isinstance(listing, dict) else None
    for run in runs if isinstance(runs, list) else []:
        owner = childsweep.run_metadata(run.get("metadata")).get("execution_owner") if isinstance(run, dict) else None
        if isinstance(owner, dict) and owner.get("pid") == pid and owner.get("host") == host and isinstance(run.get("id"), str):
            return run["id"]
    return None


def root_of(record: object) -> str | None:
    """`workflow get <run> --json` の物の、run の記録の置き場。終わった run は terminal_record.artifacts.root。承認で止まった run は
    終わりの記録が無いので、run の行の output_root（プロジェクトの置き場）の下の artifacts/runs/<run の id>（Archon の
    getRunArtifactsDirForRoot が組む形。packages/paths/src/archon-paths.ts）"""
    if not isinstance(record, dict):
        return None
    root = (((record.get("terminal_record") or {}).get("artifacts")) or {}).get("root")
    if isinstance(root, str) and root:
        return root
    base, run = record.get("output_root"), record.get("id")
    return os.path.join(base, "artifacts", "runs", run) if isinstance(base, str) and base and isinstance(run, str) and run else None


def line(read: Callable[..., object], pid: int, host: str | None = None) -> str:
    """告げる 1 行。read(*archon の引数) は Archon の JSON を返す(読めなければ ValueError)"""
    try:
        run = owned_run(read("workflow", "runs", "--json", "--limit", "100"), pid, host or socket.gethostname())
        if run is None:
            return f"{LABEL}を特定できない（持ち主が殻の起こした Archon の run が記録に無い）。`workflow runs` で run を探し、`workflow get <run> --json` の terminal_record.artifacts.root を読む"
        root = root_of(read("workflow", "get", run, "--json"))
    except ValueError as error:
        return f"{LABEL}を読めない（{error}）"
    if root is None:
        return f"{LABEL}を run {run} の記録から読めない。`workflow get {run} --json` を読む"
    return f"{LABEL}: {root}"


def run_and_say(command: list[str], env: Mapping[str, str], head: list[str], cwd: str, name: str) -> int:
    """command(workflow run)を子のプロセスで走らせ、終わったら(承認ノードで止まった時も)記録の置き場を標準エラーに 1 行出して、
    子の終了の値を返す。head は Archon を起こす命令の頭、cwd は対象。端末の割り込み(SIGINT)は同じグループの子にも届くので
    殻は受け流し、SIGTERM・SIGHUP は子に渡す(exec で入れ替わっていた時と同じに、止める信号が run に届く)"""
    child = subprocess.Popen(command, env=dict(env))
    previous = {sig: signal.signal(sig, lambda number, _frame: child.send_signal(number))
                for sig in (signal.SIGTERM, signal.SIGHUP)}
    previous[signal.SIGINT] = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        code = child.wait()
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    say(head, env, cwd, child.pid, name)
    return 128 - code if code < 0 else code


def say(head: list[str], env: Mapping[str, str], cwd: str | None, pid: int, name: str) -> None:
    """標準エラーに 1 行出す。head は Archon を起こす命令の頭、cwd は --cwd の値"""
    def read(*args: str) -> object:
        done = subprocess.run([*head, *args, *(["--cwd", cwd] if cwd else [])], env=env, capture_output=True, text=True,
                              encoding="utf-8")
        return childsweep.last_json(done.stdout)

    print(f"{name}: {line(read, pid)}", file=sys.stderr)

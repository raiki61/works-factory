"""封じた差分を対象に当てる口 bin/apply の中身: bin/apply <run-id> [--cwd <対象>] [--allow-delete] [--allow-stopped]。

約束は docs/plans/2026-10-13-stage1-walking-skeleton.md の「bin/apply（土台の計画 Task 7）」の 1〜9。run は殻 bin/works-factory の
workflow get で読み（家・隔離・Archon の起こし方は殻の物）、線の返す節 result の値（terminal_record.returns.value）から当てる差分を選ぶ。
hash の正本は Archon の DB の run の記録で、置き場のファイルではない。今の works の確かめ（works/dev/use.sh の apply_checked:
消す行の許し・止まった run の許し・git apply --check）に、封じた hash と指し札の照らし・読み戻しを足す。commit はしない。
封じた hash で確かめられない差分（線の返りが読めない run・封じる前に止まった run）は当てず、拒む 1 行に素の git apply で当てる道を書く
（docs/plans/2026-10-13-line-wiring.md の M45・M46 の決め。新しい旗は足さない）。
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from bin._lib import launcher

LIB = Path(__file__).resolve().parents[2] / "lib"
if str(LIB) not in sys.path:   # lib/ の部品は互いを名だけで import する（merge の script と同じく lib/ を sys.path に置く）
    sys.path.append(str(LIB))

import seal  # noqa: E402  差分の封印と R2 の語の持ち主（merge の apply と同じ決まりを 2 か所に持たない）

NAME = "apply"
SHELL = Path(__file__).resolve().parents[1] / "works-factory"
UNREADABLE = 2
REFUSED = 1
POINTER_TYPE = "archon_artifact"   # merge の返りの diff の型（試験が workflows/merge の output_format と縛る）
APPLY_DIFF, SEALED_DIFF = "merge/apply.diff", "merge/sealed.diff"   # merge が置き場に置く差分（同じく output_format の enum と縛る）

Get = Callable[[str, Path], subprocess.CompletedProcess[str]]


class Refuse(Exception):
    """対象を変えずに止まる（終了の値つき）"""

    def __init__(self, message: str, code: int = REFUSED):
        super().__init__(message)
        self.code = code


def ask_launcher(run_id: str, target: Path) -> subprocess.CompletedProcess[str]:
    """殻を子のプロセスで起こして run を読む。殻の文（標準エラー）はそのまま利用者へ流す"""
    return subprocess.run([sys.executable, str(SHELL), "workflow", "get", run_id, "--json", "--cwd", str(target)],
                          stdout=subprocess.PIPE, text=True, encoding="utf-8")


def main(argv: list[str], here: Path | None = None, get: Get = ask_launcher) -> int:
    parser = argparse.ArgumentParser(prog=NAME, description="封じた差分を対象の作業ツリーに当てる（commit しない）")
    parser.add_argument("run_id")
    parser.add_argument("--cwd", help="対象（無ければ打った場所）")
    parser.add_argument("--allow-delete", action="store_true", help="対象のファイルを消す差分も当てる")
    parser.add_argument("--allow-stopped", action="store_true", help="最後の関所で止めた run の封じた差分を当てる")
    args = parser.parse_args(argv)
    here = here or Path.cwd()
    try:
        target = launcher.target_root(Path(args.cwd or here), here)
        run = read_run(get(args.run_id, target), args.run_id, target)
        diff, sealed_hash, stopped = choose(run, target, args.allow_stopped)
        try:
            data = diff.read_bytes()
        except OSError as e:
            raise Refuse(f"差分のファイルを読めない（{e.strerror}: {diff}）") from None
        if seal.digest(data) != sealed_hash:
            raise Refuse(f"封じた hash と合わない（記録 {sealed_hash}・置き場のファイル {seal.digest(data)}: {diff}）。当てない")
        files = put(target, data, args.allow_delete)
    except (launcher.Stop, Refuse) as stop:
        print(f"{NAME}: {one_line(str(stop))}", file=sys.stderr)
        return stop.code
    if stopped:
        print(f"{NAME}: {one_line(stopped)}で止まった run。--allow-stopped が在るので当てた", file=sys.stderr)
    print(f"run {run['terminal_record']['run_id']} の封じた差分を {target} に当てた: {' '.join(files)}")
    print("commit はしていない。試験を回してから commit する")
    return 0


def read_run(done: subprocess.CompletedProcess[str], run_id: str, target: Path) -> dict:
    """workflow get --json の答え（run の記録の欄と、終わった run の terminal_record）。読めなければ終了の値 2"""
    if done.returncode != 0:
        raise Refuse(f"run {run_id} を読めない（workflow get が終了の値 {done.returncode}）", UNREADABLE)
    try:
        run = json.loads(done.stdout)
        record = run.get("terminal_record")
    except (json.JSONDecodeError, AttributeError):
        raise Refuse(f"run {run_id} を読めない（workflow get の答えが JSON の object でない）", UNREADABLE) from None
    if record is None:
        raise Refuse(f"run {run_id} は終わっていない（terminal_record が null）。終わってから当てる", UNREADABLE)
    returns = record.get("returns") or {}
    if returns.get("availability") != "available":
        raise Refuse(f"run {run_id} の線の返りが読めない（returns.availability が {returns.get('availability')}）"
                     f"{unchecked(record, target)}", UNREADABLE)
    if not isinstance(returns.get("value"), dict):
        raise Refuse(f"run {run_id} の線の返り（returns.value）が object でない{unchecked(record, target)}", UNREADABLE)
    return run


def unchecked(record: dict, target: Path) -> str:
    """線の返りが読めない run の、置き場に在る差分を確かめずに当てる道（置き場に差分が無ければ空）"""
    root = (record.get("artifacts") or {}).get("root")
    if not isinstance(root, str) or not root:
        return ""
    for rel in (APPLY_DIFF, SEALED_DIFF):
        path = Path(root, rel)
        if path.is_file():
            return f"。置き場の差分 {path} を確かめずに当てるなら {shlex.join(['git', '-C', str(target), 'apply', str(path)])}"
    return ""


def choose(run: dict, target: Path, allow_stopped: bool) -> tuple[Path, str, str]:
    """当てる差分のファイルと、記録の封じた hash と、止まった run を許しで当てるならその訳（ほかは空）"""
    record = run["terminal_record"]
    value = record["returns"]["value"]
    placed, sealed = value.get("apply"), value.get("sealed")
    if isinstance(placed, dict) and placed.get("ok") is True:
        if not isinstance(sealed, dict) or placed.get("hash") != sealed.get("hash"):
            raise Refuse(f"置いた差分の hash が封じた hash と合わない（apply {placed.get('hash')}・"
                         f"sealed {sealed.get('hash') if isinstance(sealed, dict) else None}）。当てない")
        return pointed(record, placed.get("diff")), placed["hash"], ""
    why = stopped_why(value)
    nothing = f"置いた差分が無い（{why}）"
    if not (isinstance(sealed, dict) and sealed.get("ok") is True):
        by_hand = "" if value.get("r2_status") == seal.REDESIGN else from_worktree(run, target)
        raise Refuse(f"{nothing}。封じていない差分は当てない{by_hand}")
    if not allow_stopped:
        raise Refuse(f"{nothing}。最後の関所で止めた run の封じた差分を当てるなら --allow-stopped を付けて打ち直す")
    if value.get("r2_status") == seal.REDESIGN:
        raise Refuse(f"R2 が {seal.REDESIGN} を言った run の差分は、--allow-stopped でも当てない")
    return pointed(record, sealed.get("diff")), sealed["hash"], why


def stopped_why(value: dict) -> str:
    """結末の語と、止めた所と、最後の関所で人が書いた一言"""
    parts = [f"結末 {value.get('outcome')}"]
    if value.get("stop_reason"):
        parts.append(f"止めた所 {value['stop_reason']}")
    said = value.get("final_answer")
    if isinstance(said, dict) and isinstance(said.get("text"), str) and said["text"].strip():
        parts.append(f"人の一言「{said['text']}」")
    return "・".join(parts)


def from_worktree(run: dict, target: Path) -> str:
    """封じる前に止まった run の作業ツリーの差分を確かめずに当てる道（作業ツリーか始めの commit が記録に無ければ空）。
    始めの commit は、線の始めの記録の base_rev（始めの節が読む HEAD）と同じ、Archon が最初の節の前に見た checkout"""
    path, start = run.get("working_path"), run.get("checkout_baseline") or {}
    base = start.get("commit") if start.get("kind") == "git" else None
    if not (isinstance(path, str) and path and isinstance(base, str) and base):
        return ""
    return (f"。run の作業ツリーの差分を確かめずに当てるなら {shlex.join(['git', '-C', path, 'diff', base])} | "
            f"{shlex.join(['git', '-C', str(target), 'apply'])}")


def pointed(record: dict, ptr) -> Path:
    """指し札の先の実のパス。指し札がこの run の物で、置き場の根の実のパスの下の在る普通のファイルでなければ止まる"""
    if not isinstance(ptr, dict) or ptr.get("type") != POINTER_TYPE or not isinstance(ptr.get("path"), str):
        raise Refuse(f"差分の指し札が読めない: {json.dumps(ptr, ensure_ascii=False)}")
    if ptr.get("run_id") != record["run_id"]:
        raise Refuse(f"差分の指し札が別の run {ptr.get('run_id')} を指す（記録の run は {record['run_id']}）")
    root = (record.get("artifacts") or {}).get("root")
    if not isinstance(root, str) or not root:
        raise Refuse("run の置き場の根（artifacts.root）が記録に無い")
    if os.path.isabs(ptr["path"]):
        raise Refuse(f"差分の指し札のパスが相対でない: {ptr['path']}")
    real_root = os.path.realpath(root)
    real = os.path.realpath(os.path.join(root, ptr["path"]))
    if os.path.commonpath([real_root, real]) != real_root:
        raise Refuse(f"差分の指し札が run の置き場の外を指す: {ptr['path']}（{real}）")
    if not os.path.isfile(real):
        raise Refuse(f"差分の指し札の先に普通のファイルが無い: {real}")
    return Path(real)


def put(target: Path, data: bytes, allow_delete: bool) -> list[str]:
    """照らしたバイトの差分を、消す行・当たるかを確かめてから当て、読み戻す。当てたファイルの一覧"""
    try:
        files = list(seal.diff_files(target, data))
    except ValueError as e:
        raise Refuse(f"差分を読めない（{e}）") from None
    summary = git_apply(target, data, "--summary", "-z")
    if summary.returncode != 0:
        raise Refuse(f"差分を読めない（git apply --summary）: {summary.stderr}")
    gone = [line.split(maxsplit=3)[3] for line in summary.stdout.split("\n") if line.startswith(" delete mode ")]
    if gone and not allow_delete:
        raise Refuse(f"差分が対象のファイルを消す（{' '.join(gone)}）。消してよければ --allow-delete を付けて打ち直す")
    check = git_apply(target, data, "--check")
    if check.returncode != 0:
        raise Refuse(f"差分が対象に当たらない（対象の手元の変更とぶつかっていないかを見る）: {check.stderr}")
    done = git_apply(target, data)
    if done.returncode != 0:
        raise Refuse(f"git apply が落ちた: {done.stderr}")
    back = git_apply(target, data, "-R", "--check")
    if back.returncode != 0:
        raise Refuse(f"当てたが読み戻せない（git apply -R --check）: {back.stderr}")
    return files


def one_line(text: str) -> str:
    """拒む文は 1 行（git の標準エラーや人の一言の改行を畳む）"""
    return " ".join(text.split())


def git_apply(target: Path, data: bytes, *flags: str) -> subprocess.CompletedProcess[str]:
    """git apply に差分のバイトを標準入力で渡す（hash を照らした物そのものを当てる）。
    --whitespace=nowarn は、利用者の apply.whitespace の設定で落ちたり封じた物と違う行を当てたりしないため（seal.diff_files と同じ）"""
    done = subprocess.run(["git", "-C", str(target), "apply", "--whitespace=nowarn", *flags, "-"], input=data,
                          capture_output=True)
    return subprocess.CompletedProcess(done.args, done.returncode, done.stdout.decode("utf-8", "replace"),
                                       done.stderr.decode("utf-8", "replace").strip())

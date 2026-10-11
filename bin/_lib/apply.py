"""封じた差分を対象に当てる口 bin/apply の中身: bin/apply <run-id> [--cwd <対象>] [--allow-delete] [--allow-stopped]。

約束は docs/plans/2026-10-13-stage1-walking-skeleton.md の「bin/apply（土台の計画 Task 7）」の 1〜9。run は殻 bin/works-factory の
workflow get で読み（家・隔離・Archon の起こし方は殻の物）、線の返す節 result の値（terminal_record.returns.value）から当てる差分を選ぶ。
hash の正本は Archon の DB の run の記録で、置き場のファイルではない。今の works の確かめ（works/dev/use.sh の apply_checked:
消す行の許し・止まった run の許し・git apply --check）に、封じた hash と指し札の照らし・読み戻しを足す。commit はしない。
"""
import argparse
import json
import os
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
        record = read_run(get(args.run_id, target), args.run_id)
        diff, sealed_hash = choose(record, args.allow_stopped)
        data = diff.read_bytes()
        if seal.digest(data) != sealed_hash:
            raise Refuse(f"封じた hash と合わない（記録 {sealed_hash}・置き場のファイル {seal.digest(data)}: {diff}）。当てない")
        files = put(target, data, args.allow_delete)
    except (launcher.Stop, Refuse) as stop:
        print(f"{NAME}: {stop}", file=sys.stderr)
        return stop.code
    print(f"run {record['run_id']} の封じた差分を {target} に当てた: {' '.join(files)}")
    print("commit はしていない。試験を回してから commit する")
    return 0


def read_run(done: subprocess.CompletedProcess[str], run_id: str) -> dict:
    """workflow get --json の答えから、終わった run の記録（terminal_record）を取る。読めなければ終了の値 2"""
    if done.returncode != 0:
        raise Refuse(f"run {run_id} を読めない（workflow get が終了の値 {done.returncode}）", UNREADABLE)
    try:
        record = json.loads(done.stdout).get("terminal_record")
    except (json.JSONDecodeError, AttributeError):
        raise Refuse(f"run {run_id} を読めない（workflow get の答えが JSON の object でない）", UNREADABLE) from None
    if record is None:
        raise Refuse(f"run {run_id} は終わっていない（terminal_record が null）。終わってから当てる", UNREADABLE)
    returns = record.get("returns") or {}
    if returns.get("availability") != "available":
        raise Refuse(f"run {run_id} の線の返りが読めない（returns.availability が {returns.get('availability')}）",
                     UNREADABLE)
    if not isinstance(returns.get("value"), dict):
        raise Refuse(f"run {run_id} の線の返り（returns.value）が object でない", UNREADABLE)
    return record


def choose(record: dict, allow_stopped: bool) -> tuple[Path, str]:
    """当てる差分のファイルと、記録の封じた hash"""
    value = record["returns"]["value"]
    placed, sealed = value.get("apply"), value.get("sealed")
    if isinstance(placed, dict) and placed.get("ok") is True:
        if not isinstance(sealed, dict) or placed.get("hash") != sealed.get("hash"):
            raise Refuse(f"置いた差分の hash が封じた hash と合わない（apply {placed.get('hash')}・"
                         f"sealed {sealed.get('hash') if isinstance(sealed, dict) else None}）。当てない")
        return pointed(record, placed.get("diff")), placed["hash"]
    nothing = f"置いた差分が無い（結末 {value.get('outcome')}）"
    if not (isinstance(sealed, dict) and sealed.get("ok") is True):
        raise Refuse(f"{nothing}。封じていない差分は当てない")
    if not allow_stopped:
        raise Refuse(f"{nothing}。最後の関所で止めた run の封じた差分を当てるなら --allow-stopped を付けて打ち直す")
    if value.get("r2_status") == seal.REDESIGN:
        raise Refuse(f"R2 が {seal.REDESIGN} を言った run の差分は、--allow-stopped でも当てない")
    return pointed(record, sealed.get("diff")), sealed["hash"]


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


def git_apply(target: Path, data: bytes, *flags: str) -> subprocess.CompletedProcess[str]:
    """git apply に差分のバイトを標準入力で渡す（hash を照らした物そのものを当てる）。
    --whitespace=nowarn は、利用者の apply.whitespace の設定で落ちたり封じた物と違う行を当てたりしないため（seal.diff_files と同じ）"""
    done = subprocess.run(["git", "-C", str(target), "apply", "--whitespace=nowarn", *flags, "-"], input=data,
                          capture_output=True)
    return subprocess.CompletedProcess(done.args, done.returncode, done.stdout.decode("utf-8", "replace"),
                                       done.stderr.decode("utf-8", "replace").strip())

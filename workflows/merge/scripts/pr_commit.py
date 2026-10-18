# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""出口の語 pr の commit の節 pr-commit。照らした差分を run の作業ツリーの枝へ 1 つの commit に積み、PR を作る子の run に渡す枝を返す。

積む前に止める（go: false と訳。何も積まない）: 本体の作業ツリーか切り離された HEAD（lib/runbranch.py）・run の枝の名が対象の既定の
枝（origin の HEAD が指す枝）と同じ・既定の枝を読めない・origin の URL から PR を出す repo を決められない・今の差分の hash が封じた
hash と違う。commit は対象の commit の hooks を飛ばさずに走らせ（hooks は対象のコマンドなので、対象のコマンドの環境——
tree_run.outside_env: 利用者の HOME・XDG に戻し、uv が足した物を外し、読むだけの gh を PATH の頭に置く——と、印の置き場（入力
user_env_dir）で git commit を起こす。git commit 自身も利用者の HOME・XDG で走るので、利用者の大域の git の設定（core.hooksPath など）で、
走る hooks が利用者自身の commit と同じに決まる。同じ口の git add・git diff は渡された環境のままで、利用者の環境で起こすのは git commit
だけ）、hooks が落ちれば go: false と hooks の言葉（積まない）。印は起こす直前に置き
（tree_run.split_mark・place_mark）、置けなければ積まずに止める。積まなかった回（hooks も走っていない）は新しく置いた印を消す。
GitFailed は runbranch の口からは hooks が走ったかを見分けられないので、印を残す側に倒す（git add で落ちた稀な回は報告が言い過ぎうる）。
RECORD の形が違う・RECORD が在るのに印の置き場が空なら、積まずに go: false。push の hooks（pre-push）は pr-open の archon-pr が
工場の環境で走らせ、この節の外にある。積んだ後に、差分の根から積んだ commit まで
の差分の hash を封じた hash と照らし、違えば go: false（積んだ commit は run の枝に残るが、push はされない）。作業ツリーに変更が
無く、封じた差分が既に枝の commit に在る時は積まずに進む。push・PR の作成はこの節でしない。
commit の文が PR を作る子の run への渡し物（子の run には枝しか入力で渡せないので）: 題は run の id、本文は照らしの要約・封じた hash・
run の id・報告の在りか（報告は merge の後に書かれるので、run の id から組める在りかだけ）・向け先の既定の枝・依頼が名指した issue
（閉じない参照）。
出力の branch・base・repo（origin の {host, path}）は、PR を作る子の run の入力と読み戻しの照らしに使う。
落ちない: どの誤りも go: false と訳を返す。

入力: mode（照らしの形。apply か check）・base_rev（差分の根の版）・sealed_hash（封じた差分の sha256）・request（依頼のファイルのパス。
相対なら対象の根から。空は無し）・user_env_dir（利用者の HOME・XDG に戻した印を置く置き場の絶対パス。空は置き場が無い）
"""
import json
import os
import sys
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    unread = None
except Exception as error:   # 返す節が結ぶので落ちない（上の docstring）
    boundary, unread = None, error

if boundary is not None:
    with boundary.guarded_imports():
        import entryshape
        import forge
        import green_cert
        import runbranch
        import seal
        import tree_run

REMOTE = "origin"
CHECKED = {
    "apply": "最後の承認ノードの後に、封じた差分の hash・修正の後のテストの緑の認証・独立の確かめ・守りのパスの当たりを照らして通った",
    "check": "封じた差分の hash を今の差分と照らして通った（テストと確かめは差分を作った所で済んだ）",
}


def stopped(reason: str) -> dict:
    return {"go": False, "head": "", "branch": "", "base": "", "repo": None, "reason": reason}


def message(mode: str, run_id: str, sealed: str, name: str, base: str, issues: list) -> str:
    lines = [f"works-factory の run {run_id} が照らした差分", "",
             f"照らし（merge の {mode}）: {CHECKED[mode]}",
             f"封じた差分の sha256: {sealed}",
             f"run: {run_id}",
             f"報告: run {run_id} の報告（merge の後に書かれる。workflow get {run_id} の出力の report が指す）",
             f"向け先: 対象の既定の枝 {base}（この枝 {name} から）"]
    lines += [f"Refs #{n}" for n in issues]
    return "\n".join(lines) + "\n"


def origin_repo(repo: Path):
    try:
        got = forge.repo_of(runbranch.git(repo, "config", "--get", f"remote.{REMOTE}.url"))
    except runbranch.GitFailed:
        return None
    return None if got is None else {"host": got["host"], "path": f"{got['owner']}/{got['name']}"}


def commit() -> dict:
    repo = Path.cwd()
    run_id = os.environ["WORKFLOW_ID"]
    mode = boundary.text(os.environ.get("INPUTS_MODE"))
    base_rev = boundary.text(os.environ.get("INPUTS_BASE_REV"))
    sealed = boundary.text(os.environ.get("INPUTS_SEALED_HASH"))
    if mode not in CHECKED:
        return stopped(f"照らしの形 {mode!r} は {' か '.join(CHECKED)} でない（照らした差分しか積まない）")
    if not base_rev:
        return stopped("差分の根 base_rev が無い")
    reason = runbranch.refusal(repo)
    if reason:
        return stopped(reason)
    name = runbranch.branch(repo)
    try:
        base = runbranch.default_branch(repo, REMOTE)
    except runbranch.GitFailed as error:
        return stopped(f"対象の既定の枝を読めない（既定の枝へ push しないことを確かめられない）: {error}")
    if name == base:
        return stopped(f"run の枝 {name} が対象の既定の枝と同じ名（既定の枝へは push しない）")
    target = origin_repo(repo)
    if target is None:
        return stopped(f"{REMOTE} の URL から PR を出す repo（host と owner/name）を決められない")
    why = seal.hash_refusal(sealed, seal.digest(green_cert.diff_bytes(repo, base_rev, skip=boundary.SKIP)))
    if why:
        return stopped(f"{why}（commit しない）")
    _, issues = entryshape.named({"request": boundary.text(os.environ.get("INPUTS_REQUEST"))}, repo)
    boundary.drop_runner_env(os.environ.get("INPUTS_USER_ENV_DIR", ""))   # 入力を読み終えた。hooks に Archon の変数を継がせない
    env, mark = tree_run.split_mark(tree_run.outside_env(os.environ))
    try:
        placed = mark is not None and tree_run.place_mark(mark)
    except OSError as error:
        return stopped(f"{error}（積まない・push しない）")
    try:
        changed, head = runbranch.commit(repo, message(mode, run_id, sealed, name, base, issues), boundary.RUNTIME_COPY,
                                         hook_env=env)
    except runbranch.GitFailed as error:   # hooks が走ったかを口から見分けられないので、印は残す側に倒す
        return stopped(f"commit が通らなかった（対象の commit の hooks が落ちたか）: {error}（積まない・push しない）")
    if placed and not changed:   # 積まず、hooks も走っていない。新しく置いた印は報告が言い過ぎるので消す
        Path(mark).unlink(missing_ok=True)
    why = seal.hash_refusal(sealed, seal.digest(green_cert.diff_between(repo, base_rev, head, skip=boundary.SKIP)))
    if why:
        return stopped(f"積んだ commit {head} の差分が封じた差分と違う: {why}（push しない）")
    return {"go": True, "head": head, "branch": name, "base": base, "repo": target, "reason": ""}


def main() -> None:
    if boundary is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(stopped(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        boundary.run(commit, stopped)


if __name__ == "__main__":
    main()

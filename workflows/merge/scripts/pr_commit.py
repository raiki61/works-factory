# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""出口の語 pr の commit の節 pr-commit。照らした差分を run の作業ツリーの枝へ 1 つの commit に積み、PR を作る子の run に渡す文を組む。

積む前に止める（go: false と訳。何も積まない）: 本体の作業ツリーか切り離された HEAD（lib/runbranch.py）・run の枝の名が対象の既定の
枝（origin の HEAD が指す枝）と同じ・既定の枝を読めない・今の差分の hash が封じた hash と違う。積んだ後に、差分の根から積んだ commit
までの差分の hash を封じた hash と照らし、違えば go: false（積んだ commit は run の枝に残るが、push はされない）。作業ツリーに変更が
無く、封じた差分が既に枝の commit に在る時は積まずに進む。push・PR の作成はこの節でしない。
返りの context は PR を作る子の run の依頼の文（run の id・封じた hash・積んだ commit・既定の枝・依頼が名指した issue）。
落ちない: どの誤りも go: false と訳を返す。

入力: base_rev（差分の根の版）・sealed_hash（封じた差分の sha256）・request（依頼のファイルのパス。相対なら対象の根から。空は無し）
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
        import green_cert
        import runbranch
        import seal

REMOTE = "origin"


def stopped(reason: str) -> dict:
    return {"go": False, "head": "", "branch": "", "base": "", "context": "", "reason": reason}


def message(run_id: str, sealed: str) -> str:
    return f"works-factory の run {run_id} の差分\n\n封じた差分の sha256: {sealed}\nrun: {run_id}\n"


def context(run_id: str, sealed: str, name: str, head: str, base: str, issues: list) -> str:
    lines = [f"works-factory の run {run_id} が確かめて封じた差分を、この枝 {name} の commit {head} に積んだ（封じた差分の sha256: {sealed}）。",
             f"対象の既定の枝は {base}。"]
    if issues:
        lines.append("依頼が名指した issue: " + "・".join(f"#{n}" for n in issues) + "（閉じない参照で名指す）")
    return "\n".join(lines)


def commit() -> dict:
    repo = Path.cwd()
    run_id = os.environ["WORKFLOW_ID"]
    base_rev = boundary.text(os.environ.get("INPUTS_BASE_REV"))
    sealed = boundary.text(os.environ.get("INPUTS_SEALED_HASH"))
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
    why = seal.hash_refusal(sealed, seal.digest(green_cert.diff_bytes(repo, base_rev, skip=boundary.SKIP)))
    if why:
        return stopped(f"{why}（commit しない）")
    _, head = runbranch.commit(repo, message(run_id, sealed), boundary.RUNTIME_COPY)
    why = seal.hash_refusal(sealed, seal.digest(green_cert.diff_between(repo, base_rev, head, skip=boundary.SKIP)))
    if why:
        return stopped(f"積んだ commit {head} の差分が封じた差分と違う: {why}（push しない）")
    _, issues = entryshape.named({"request": boundary.text(os.environ.get("INPUTS_REQUEST"))}, repo)
    return {"go": True, "head": head, "branch": name, "base": base, "context": context(run_id, sealed, name, head, base, issues),
            "reason": ""}


def main() -> None:
    if boundary is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(stopped(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        boundary.run(commit, stopped)


if __name__ == "__main__":
    main()

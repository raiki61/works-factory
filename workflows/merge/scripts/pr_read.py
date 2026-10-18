# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""出口の語 pr の読み戻しの節 pr-read。PR を作る子の run が返した PR の記録を、積んだ commit とその枝・向け先と照らす。

作ったと言うのは、記録の PR が開いていて、repo と head の repo が origin の repo（commit の節が URL から決めた {host, path}。大文字と
小文字は区別しない）、head の枝が積んだ枝、base の枝が既定の枝、head の版が積んだ commit と同じ時だけ。どれかが違えば ok: false と訳
（push と PR の作成は済んでいるかもしれない）。子の run が落ちた時はこの節は飛ばされ、後ろの節が飛ばされたことを訳にする。
落ちない: どの誤りも ok: false と訳を返す。

入力: got（PR の記録 {number, url, state, repo, head_repo, head, base, head_revision, is_draft, …}）・head（積んだ commit）・
branch（積んだ枝）・base_branch（既定の枝）・repo（origin の {host, path}）
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

NAMES = ("number", "url", "state", "repo", "head_repo", "head", "base", "head_revision", "is_draft")
OPEN = "open"


def not_read(reason: str) -> dict:
    return {"ok": False, "number": None, "url": "", "is_draft": None, "reason": reason}


def same_repo(got, want) -> bool:
    return (isinstance(got, dict) and isinstance(want, dict)
            and all(isinstance(got.get(k), str) and isinstance(want.get(k), str) and got[k].lower() == want[k].lower()
                    for k in ("host", "path")))


def mismatch(got, want: dict) -> str:
    """記録 got が積んだ物 want と違う所の 1 行（同じなら空）"""
    if got.get("state") != OPEN:
        return f"が開いていない（{got.get('state')!r}）"
    for name in ("repo", "head_repo"):
        if not same_repo(got.get(name), want["repo"]):
            return f"の {name} {got.get(name)!r} が origin の repo {want['repo']!r} と違う"
    for name, kept, what in (("head", want["branch"], "積んだ枝"), ("base", want["base"], "既定の枝"),
                             ("head_revision", want["head"], "積んだ commit")):
        if got.get(name) != kept:
            return f"の {name} {got.get(name)!r} が{what} {kept} と違う"
    return ""


def read() -> dict:
    got = boundary.picked(os.environ.get("INPUTS_GOT"), NAMES)
    want = {"head": boundary.text(os.environ.get("INPUTS_HEAD")), "branch": boundary.text(os.environ.get("INPUTS_BRANCH")),
            "base": boundary.text(os.environ.get("INPUTS_BASE_BRANCH")), "repo": boundary.value(os.environ.get("INPUTS_REPO"))}
    if got is None:
        return not_read("PR の記録が無い")
    url, number = got.get("url"), got.get("number")
    if not isinstance(url, str) or not url or not isinstance(number, int):
        return not_read(f"PR の記録に番号か在りかが無い（number {number!r}・url {url!r}）")
    why = mismatch(got, want)
    if why:
        return {**not_read(f"PR {url} {why}"), "number": number, "url": url}
    return {"ok": True, "number": number, "url": url, "is_draft": got.get("is_draft") is True, "reason": ""}


def main() -> None:
    if boundary is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(not_read(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        boundary.run(read, not_read)


if __name__ == "__main__":
    main()

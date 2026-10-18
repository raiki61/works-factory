# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""出口の語 pr の読み戻しの節 pr-read。PR を作る子の run が返した PR の記録を、積んだ commit と照らす。

作ったと言うのは、記録の PR が開いていて、その head の版が積んだ commit と同じ時だけ。違えば ok: false と訳。子の run が落ちた時は
この節は飛ばされ、後ろの節が飛ばされたことを訳にする。
落ちない: どの誤りも ok: false と訳を返す。

入力: got（PR の記録 {number, url, state, head_revision, is_draft, …}）・head（積んだ commit）
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

NAMES = ("number", "url", "state", "head_revision", "is_draft")
OPEN = "open"


def unread(reason: str) -> dict:
    return {"ok": False, "number": None, "url": "", "is_draft": None, "reason": reason}


def read() -> dict:
    got = boundary.picked(os.environ.get("INPUTS_GOT"), NAMES)
    head = boundary.text(os.environ.get("INPUTS_HEAD"))
    if got is None:
        return unread("PR の記録が無い")
    url, number = got.get("url"), got.get("number")
    if not isinstance(url, str) or not url or not isinstance(number, int):
        return unread(f"PR の記録に番号か在りかが無い（number {number!r}・url {url!r}）")
    if got.get("state") != OPEN:
        return {**unread(f"PR {url} が開いていない（{got.get('state')!r}）"), "number": number, "url": url}
    if got.get("head_revision") != head:
        return {**unread(f"PR {url} の head {got.get('head_revision')!r} が積んだ commit {head} と違う"), "number": number, "url": url}
    return {"ok": True, "number": number, "url": url, "is_draft": got.get("is_draft") is True, "reason": ""}


def main() -> None:
    if boundary is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(unread(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        boundary.run(read, unread)


if __name__ == "__main__":
    main()

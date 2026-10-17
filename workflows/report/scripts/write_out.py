# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""書き手のループ（1 つの項目の fan_out）の出力の配列を、書き手の答えのポインタ ai と、AI の本文が無い訳 fell にする。ループが落ちた項目は
落ちた誤りの文を、ループが答えのファイルを残さなかった時はその旨を fell に置く。落ちない（落ちると run が落ちる）: 読めない出力も、
境の口を読めない時も、fell に訳を置いて返す。"""
import json
import os
import sys
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    unread = None
except Exception as error:  # noqa: BLE001 — 落ちない（下の unreadable で返す）
    boundary, unread = None, error

NAMES = ("ok", "ai")
NO_ANSWER = "書き手のループが答えのファイルを残さなかった"


def unreadable(what: str, error: BaseException) -> dict:
    return {"ai": None, "fell": f"{what}（{type(error).__name__}: {' '.join(str(error).split())}）"}


def read() -> dict:
    items = boundary.fanned(os.environ.get("INPUTS_GOT"), NAMES)
    if len(items) != 1:
        raise ValueError(f"書き手のループの項目が 1 つでない（{len(items)} 個）")
    got = items[0]
    if isinstance(got, boundary.Fell):
        return {"ai": None, "fell": str(got)}
    return {"ai": got["ai"], "fell": ""} if got["ok"] is True else {"ai": None, "fell": NO_ANSWER}


if __name__ == "__main__" and boundary is None:   # 境の口を読めない時
    print(json.dumps(unreadable("書き手のループの出力を読む境の口を読めない", unread), ensure_ascii=False, allow_nan=False), flush=True)
elif __name__ == "__main__":
    try:
        out = read()
    except Exception as error:  # noqa: BLE001 — 落ちない（上の訳）
        out = unreadable("書き手のループの出力を読めない", error)
    boundary.returns(out)

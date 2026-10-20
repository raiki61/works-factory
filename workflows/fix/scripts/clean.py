# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node clean（全体の形）: 控えに無かった git が無視するファイルだけを消す（leftovers.remove_new_ignored。.archon/ と前から
在ったフォルダは残す）。当たったままの組が在れば何も消さない。今のまま。返り {ok, count}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


import leftovers  # noqa: E402
import oneline  # noqa: E402

from src import board  # noqa: E402

SKIP = (ports.RUNTIME_COPY_PREFIX,)


def main() -> dict:
    place = ports.place()
    if board.held(place):
        return {"ok": True, "count": 0}
    out = leftovers.remove_new_ignored(place, Path.cwd(), skip=SKIP)
    return {"ok": True, "count": out["count"]}


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:
        print(f"clean: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(result)

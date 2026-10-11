# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""レンズの集め（節 lens-collect）: レンズの返り（with: reply。起こさなかった・飛ばされた時は null）で置き場の lens.json の行を
埋め（lenses.collect。返りが無ければ failed と理由、在れば ran と出どころつきの findings）、1 回目の審査役の材料の lens の欄に
足す（fixboard.brief_lens）。支度が落ちて控えが無ければ、その理由の行（not_routed）を残してから集める。
返り {state（レンズの行の state）, count（集めた指摘の数）}。回す側の誤り（審査役の材料が無い）は標準エラーに 1 行で非 0。
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import fixio  # noqa: E402
import fixboard  # noqa: E402
import lens  # noqa: E402
import lenses  # noqa: E402

LENS = "silent-failure-hunter"
NO_ROUTE = "レンズの支度（lens-prep）が振り分けの控えを書いていない（支度が落ちたか走らなかった）"


def main() -> None:
    place = fixio.place()
    if lens.read(place) is None:
        lens.write_routes(place, [{"lens": r["lens"], "agent": r["agent"], "go": False, "reason": NO_ROUTE}
                                  for r in lenses.LENSES])
    got = lenses.collect(place, {LENS: os.environ["INPUTS_REPLY"]})
    if not got["ok"]:
        raise ValueError(got["reason"])
    fixboard.brief_lens(place)
    row = next((r for r in lens.read(place) or [] if r["lens"] == LENS), {})
    boundary.returns({"state": str(row.get("state") or "failed"), "count": len(row.get("findings") or [])})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(f"lens-collect: {type(e).__name__}: {' '.join(str(e).split())}")

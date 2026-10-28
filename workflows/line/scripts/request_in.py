# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""依頼の出どころを 1 つに選ぶ node request-in（docs/design/line.md の 3.3 節。決めは src.descend.request_in）。

テーマの run は theme-descend が書いた依頼（承認された設計の変える所の行）、ほかの run は start の配る値の依頼を返す。判定から後ろの node は
依頼（request・request_file・request_answers・entry・request_origin・request_scope・prior_rows）をここの返りからだけ読む。テーマの run で
降りなかった時は go を偽にして止めの語を運ぶ（後ろは when: で飛ぶ）。

入力（with:）: ports（start の配る値）・theme（{from: $theme-descend.output, if_skipped: null}）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute() -> dict:
    from src import descend
    raw_ports, raw_theme = os.environ.get("INPUTS_PORTS"), os.environ.get("INPUTS_THEME")
    given = ports.parsed(raw_ports)
    if not isinstance(given, dict):
        raise ValueError("配る値（ports）が読めない。with: の鍵の結びを確かめる")
    return descend.request_in(given, ports.parsed(raw_theme))


def fallback(reason: str) -> dict:
    from src import deal, descend, guard
    empty = deal.empty()
    return {"go": False, "stop_reason": guard.LINE_SCRIPT, "reason": reason, **{n: empty[n] for n in descend.REQUEST_FIELDS}, "notes": []}


ports.run(compute, fallback)

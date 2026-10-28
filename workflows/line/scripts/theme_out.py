# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""設計の往復（loop_group の theme-rounds）の本体の node theme-out（docs/design/line.md の 3.3 節。決めは src.themetalk.record）。

書き手の block の返りと事前審査（形 theme）の返りを往復の記録 theme-converge.json に足し、止め時（src.rounds.decide）と、次の周の書き手に
渡す前の周の設計の案を返す。計画の往復の plan-out と同じ役。例外の時は設計の案ができなかった形（ok: false・done: true）と works:line-script。

入力（with:）: design（$theme.output）・review（{from: $theme-review.output, if_skipped: null}）・prior（この周の往復の記録の pointer）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

DESIGN = ("ok", "status", "design", "design_md", "reason", "report")
REVIEW = ("ok", "status", "holes", "reason")


def compute() -> dict:
    from src import themetalk
    raw_design, raw_review, raw_prior = os.environ.get("INPUTS_DESIGN"), os.environ.get("INPUTS_REVIEW"), os.environ.get("INPUTS_PRIOR")
    design = ports.picked(raw_design, DESIGN)
    if design is None:
        raise ValueError("書き手の block の出力（design）が読めない。with: の鍵の結びを確かめる")
    review = ports.picked(raw_review, REVIEW)
    return themetalk.record(dict(design), dict(review) if review is not None else None, raw_prior, place=ports.place())


def fallback(reason: str) -> dict:
    from src import themetalk
    return {**themetalk.failed(), "reason": reason}


ports.run(compute, fallback)

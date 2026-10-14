# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""計画の往復の 1 周で、事前審査の輪を run の頭の深さで飛ばすかを決める節 plan-review-due（lib/headdepth.due。docs/design.md の
「深さで飛ばすノードの表」）。飛ばすのは頭の深さが軽量・計画ができた・計画の単位ごとの深さが全部軽量の時だけ。頭が軽量でも単位に
標準が在れば飛ばさず、上げた訳を raised に並べる（飛ばす予定だった事前審査はそのまま走る）。skipped は飛ばしたノードの run の記録の
id（表の行と同じ字。tests/layers/test_depth_skip.py が突き合わせる）。
例外の時は飛ばさない形と止めの理由 works:line-script を返す。

入力（with:）: head_depth（判定の depth）・ready（plan の ready）・plan_depth（plan の depth。単位ごとの深さの並び）
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import headdepth

ROW = "plan-review-run__review-loop"


def plan_review_due(head_depth, ready, plan_depth) -> dict:
    got = headdepth.due(head_depth, ready, plan_depth)
    return {**got, "skipped": [ROW] if got["skip"] else [], "stop_reason": ""}


def from_env() -> tuple:
    return (boundary.text(os.environ.get("INPUTS_HEAD_DEPTH")), boundary.value(os.environ.get("INPUTS_READY")),
            boundary.items(os.environ.get("INPUTS_PLAN_DEPTH")))


def fallback(reason: str) -> dict:
    return {"skip": False, "why": "", "raised": [], "skipped": [], "stop_reason": boundary.LINE_SCRIPT}


if __name__ == "__main__":
    boundary.run(lambda: plan_review_due(*from_env()), fallback)

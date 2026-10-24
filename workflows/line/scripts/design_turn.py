# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""計画の往復（loop_group の plan-rounds）の本体の頭の node design-turn（docs/design/line.md の 3.1 節。決めは src.talk.turn）。

前の周の設計の相談の承認ノード gate-design の答え（$LOOP_PREV。1 周目と関所が飛んだ周は空）を読み、この周に plan と事前審査を回すかと、
この周の plan・事前審査・plan-out に渡す前の周の値（prior の 2 本・依頼の答え・記録された方針の行）を返す。通常の run は答えが無いので
前の周の値をそのまま運ぶ（今の $LOOP_PREV.plan-out.output.plan_prior・record と、配る値の request_answers・owed の recorded と同じ値）。
修正要望の周は、人の一言を往復の記録に差し込んだ写しと、一言を足した依頼の答え・記録された方針の行を返す。答えを run の置き場の
gates/gate-design.json に並べて書く（人が読む控え）。

入力（with:）: answer（$LOOP_PREV.gate-design.output）・previous（$LOOP_PREV.design-talk.output）・last（$LOOP_PREV.design-turn.output）・
ports（start の配る値）・recorded（owed の recorded）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute() -> dict:
    raw = {name: os.environ.get(f"INPUTS_{name.upper()}") for name in ("answer", "previous", "last", "ports", "recorded")}
    from src import talk

    given = ports.parsed(raw["ports"])
    if not isinstance(given, dict):
        raise ValueError("配る値（ports）が読めない。with: の鍵の結びを確かめる")
    return talk.turn(answer_raw=raw["answer"], previous_raw=raw["previous"], last_raw=raw["last"], given=given,
                     recorded=ports.parsed(raw["recorded"]), place=ports.place())


def fallback(reason: str) -> dict:
    """読めない時は計画を回さずに止める形（design-talk が往復を止める。設計し直しを黙って飛ばさない）"""
    from src import guard
    return {"plan": False, "answer": None, "plan_prior": "", "record": "", "answers": [], "recorded": [], "asks": [], "talks": [], "notes": [], "timeline": [],
            "stop_reason": guard.LINE_SCRIPT, "reason": reason}


ports.run(compute, fallback)

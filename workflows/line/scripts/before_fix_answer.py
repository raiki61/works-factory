# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正前の関所の答えを受ける返しの節 answer-before-fix（埋め P2）。

関所の答えの読みと返り {go, answer, stop_reason} は gate_answer と同じ。加えて答えに関所で見せた問いの行 asked を足す。fix の置き場の
読み（lib/fixboard.py の gate_items）は asked の行が問いの頭で始まる時だけ、その問いを人が答えたと読み、問いの単位を直す義務に戻す。

入力（with:）: gate_answer の入力と asked（関所で見せた問いの行。$plan-rounds.output.questions）
"""
import os
from pathlib import Path

import gate_answer
import linekit


def from_env() -> dict:
    """gate_answer.answer の引数のうち with: の欄（全部を読む）"""
    return {"gate_raw": os.environ.get("INPUTS_GATE"), "go_raw": os.environ.get("INPUTS_GO"),
            "stop_raw": os.environ.get("INPUTS_STOP_REASON"), "place": os.environ.get("INPUTS_PLACE"),
            "asked_raw": os.environ.get("INPUTS_ASKED")}


def fallback(reason: str) -> dict:
    return gate_answer.fallback(reason)


if __name__ == "__main__":
    linekit.run(lambda: gate_answer.answer(**from_env(), artifacts=Path(os.environ["ARTIFACTS_DIR"])), fallback)

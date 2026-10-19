# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""独立設計の入口: port を読み、この block のファイルを名で消して intake.json を書き、役を起こすかを決める。目的が使えない
（出典が目的不明・裏取りを通った狭めている）時は役を起こさず unusable。読めない port は failed と訳。落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.intake(
        ports.place(), purpose=os.environ.get("INPUTS_PURPOSE"), purpose_source=os.environ.get("INPUTS_PURPOSE_SOURCE"),
        purpose_review=os.environ.get("INPUTS_PURPOSE_REVIEW"), constraints=os.environ.get("INPUTS_CONSTRAINTS"),
        answers=os.environ.get("INPUTS_ANSWERS"), request=os.environ.get("INPUTS_REQUEST"), policy_file=os.environ.get("INPUTS_POLICY"),
        base=os.environ.get("INPUTS_BASE"), head=os.environ.get("INPUTS_HEAD"), lang=os.environ.get("INPUTS_LANG"))


ports.run(compute, lambda why: {"due": False, "status": "failed", "reason": f"独立設計の支度が落ちた（{why}）"})

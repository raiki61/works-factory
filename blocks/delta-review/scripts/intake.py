# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""差分の審査の入口: port を読み、この block のファイルを消し、材料を写し、審査が要るかを決め、要れば 1 回目の差分と材料と作業ツリーの写しを置く。port が読めなくても落ちず、due: false と理由を返す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402


def compute():
    return steps.intake(ports.place(), Path.cwd(), base=os.environ.get("INPUTS_BASE"), plan=os.environ.get("INPUTS_PLAN"),
                        lens_rows=os.environ.get("INPUTS_LENS_ROWS"), fix_reply=os.environ.get("INPUTS_FIX_REPLY"),
                        permits=os.environ.get("INPUTS_PERMITS"), plan_review=os.environ.get("INPUTS_PLAN_REVIEW"),
                        policy=os.environ.get("INPUTS_POLICY"), request=os.environ.get("INPUTS_REQUEST"), lang=os.environ.get("INPUTS_LANG"))


ports.run(compute, lambda why: {"due": False, "reason": f"入口が落ちた（{why}）"})

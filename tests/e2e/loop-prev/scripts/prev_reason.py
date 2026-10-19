# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""前の周の受け付けの理由（1 周目は空の字。節の with: の reason）を、そのまま今の周の返りにする（judge の reject と同じ形。PR #100）。
輪の中の役の節は自分の with: を結べないので、役はこの節の返りを読む"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import ports  # noqa: E402  （pack の .shared/ports.py）

ports.returns({"reason": os.environ["INPUTS_REASON"]})

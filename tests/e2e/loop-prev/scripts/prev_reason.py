# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""前の周の受け付けの理由（1 周目は空の字）を、そのまま今の周の返りにする（judge の reject と同じ形。PR #100）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

boundary.returns({"reason": os.environ["INPUTS_REASON"]})

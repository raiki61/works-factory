# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""役の聞き返しが空なら REASON で拒み、REASON が届いていれば通す。ほかの字なら届いた字を名指して拒む"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import ports  # noqa: E402  （pack の .shared/ports.py）

REASON = "loop-prev-round-1-rejected"

heard = os.environ["INPUTS_HEARD"].strip()
if heard == REASON:
    ports.returns({"done": True, "reason": ""})
elif heard:
    ports.returns({"done": False, "reason": f"知らない聞き返し: {heard}"})
else:
    ports.returns({"done": False, "reason": REASON})

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""役 echo の AI の無い代わり: 輪の頭の理由をそのまま聞き返す（tests/e2e/test_loop_prev_real.py の LoopPrevScriptedCase が差し替える）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import ports  # noqa: E402  （pack の .shared/ports.py）

ports.returns({"heard": os.environ["INPUTS_HEARD"]})

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""R4 の返答を受け付ける（lib/eyeverdict.r4_accept）。拒否は数え、3 回目で done。返りの reply は輪の外の r4-scope-verdict が書く"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import eyeverdict  # noqa: E402

passed = eyeverdict._human_passed(boundary.parsed(os.environ["INPUTS_PLAN_QUESTIONS"]), boundary.parsed(os.environ["INPUTS_ANSWERS"]))
boundary.returns(eyeverdict.r4_accept(Path(os.environ["ARTIFACTS_DIR"]) / "eyes", os.environ["INPUTS_REPLY"], passed))

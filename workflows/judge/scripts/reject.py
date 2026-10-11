# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""前の周の受け付けが拒んだ理由（with: の reason。1 周目は空の字）を、そのまま今の周の返りにする。
輪の中の役の節は、自分の with: で結んだ名を $INPUTS で読めない: 線が include した時に、止めた Archon が「入力が無い」と止める
（packages/workflows/src/include-expander.ts:566・627。輪の中の節の with: を楯にしない）。だから前の周の値は、今の周のこの節の返りを
役の指示書が $<この節>.output.reason で読む形で渡す（ASF の W/deliver/archon-deliver.yaml の ci-evidence と同じ形）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

boundary.returns({"reason": os.environ["INPUTS_REASON"]})

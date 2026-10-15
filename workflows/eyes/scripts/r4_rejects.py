# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""R4 の受け付けの輪の頭の節。返りの reason は、受け付けがこれまでに拒んだ理由の全部（eyeverdict.r4_rejects。1 周目は空の字）。
R4 は 1 回目は新しい会話で起き、拒まれた後の出し直しは同じ会話の続き（全部を渡すのは、resume で輪が 1 周目から回り直す時も
前の拒否を落とさないため）。指示書が $<この節>.output.reason で読む"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import eyeverdict  # noqa: E402

boundary.returns({"reason": eyeverdict.r4_rejects(Path(os.environ["ARTIFACTS_DIR"]) / "eyes")})

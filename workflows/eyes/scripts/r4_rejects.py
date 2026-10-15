# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""R4 の受け付けの輪の頭の節。返りの reason は、受け付けがこれまでに拒んだ理由の全部（eyeverdict.r4_rejects。1 周目は空の字）。
R4 は 1 回目は新しい会話で起き、拒まれた後の出し直しは同じ会話の続き（全部を渡すのは、resume で輪が 1 周目から回り直す時も
前の拒否を落とさないため）。指示書が $<この節>.output.reason で読む。
この輪の実行の中で前の周が拒まれ（with: の prev が前の周の受け付けの ok の false。拒否の文でなく真偽を結ぶのは、Archon が
with: に貼った値の中の節の参照の字をもう 1 度置き換えるため。元の裁定 R44）、受け付けが合わせた答えの控えが在れば、出し直しの役
（1 回目の役の会話の続き）の短い指示書を書き（rolekit.resubmit_brief）、resubmit: true とそのパス brief も返す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import eyeverdict  # noqa: E402
import rolekit  # noqa: E402

eyes = Path(os.environ["ARTIFACTS_DIR"]) / "eyes"
brief = rolekit.resubmit_brief(eyes, eyeverdict.R4_NODE, boundary.value(os.environ.get("INPUTS_PREV")))
boundary.returns({"reason": eyeverdict.r4_rejects(eyes), "resubmit": bool(brief), "brief": brief})

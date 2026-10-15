# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""拒否の控えの全部を役に渡す輪の頭の節。返りの reason は、with: の board（置き場からの相対のフォルダ）と
accept（受け付けの拒否の控えの名）が指す控え rejects-<accept>.json の拒否の全部（rolekit.rejects_text。1 周目は空の字）。
役が周ごとに新しい会話で起きた頃に、最後の 1 件だけでは 3 回目の役が 1 回目の誤りを繰り返したので作った（#345）。会話を続ける
輪（#571）でも渡してよい。ほかの輪は reject.py で前の周の理由だけを渡す。
reject.py と分けるのは、止めた Archon の validate が script の字の読む入力を、その script を使う節の全部に結ばせるため。
返りの形と言語の 1 行 lang_line は reject.py と同じ（役の指示書が $<この節>.output.reason・lang_line で読む）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import rolekit  # noqa: E402

board = boundary.resolve(boundary.pointer(os.environ["INPUTS_BOARD"]))
boundary.returns({"reason": rolekit.rejects_text(rolekit.rejected(board, os.environ["INPUTS_ACCEPT"])),
                  "lang_line": rolekit.pointed_lang_line(os.environ.get("INPUTS_START"), boundary.pointed)})

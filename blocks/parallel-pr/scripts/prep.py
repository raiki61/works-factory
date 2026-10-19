# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""並行 PR の役の指示を prompts/pr-check.md から組む（前の回までの却下は place の控えから全部）。組めなければ node が落ち、
出口が「役の返答を受けた記録が無い」で返す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
import prompt  # noqa: E402
import rolekit  # noqa: E402  （lib/。ports を読むと lib/ が sys.path に入る）
from src import files  # noqa: E402

place = ports.place()
rejected = rolekit.rejected(place, files.ROLE)
values = {"brief_file": str(place / files.BRIEF), "limit": files.PR_LIMIT, "lang_line": rolekit.lang_line({"lang": ports.text(os.environ.get("INPUTS_LANG"))}),
          "rejection": rolekit.rejects_text(rejected)}
ports.returns(prompt.emit(files.ROLE, values, {}, prompt.round_of(files.ROLE)))

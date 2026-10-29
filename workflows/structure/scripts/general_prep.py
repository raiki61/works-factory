# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""一般の構造を描く目の指示と system prompt を prompts/general-structure.md と prompts/general-structure.system.md から組む（見せる
のは構造を描く役が書いた種類の 1 文だけ。前の回までの却下は place の控えから全部）。組めなければ node が落ちる。
返り {prompt, system, attempt}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import sketch  # noqa: E402

ports.returns(sketch.general_prompt(ports.place(), os.environ.get("INPUTS_LANG")))

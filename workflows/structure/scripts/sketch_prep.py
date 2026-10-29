# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""構造を描く役の指示を prompts/system-sketch.md から組む（見せるのは構造の目が見る単位の id・paths・summary。前の回までの却下は
place の控えから全部）。組めなければ node が落ちる。返り {prompt, attempt}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import sketch  # noqa: E402

ports.returns(sketch.sketch_prompt(ports.place(), os.environ.get("INPUTS_LANG")))

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""構造の目の指示を prompts/structure-eye.md から組む（前の回までの却下は place の控えから全部）。組めなければ node が落ち、
出口が理由を残す。返り {prompt, attempt}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import eye  # noqa: E402

ports.returns(eye.prepare(ports.place(), os.environ.get("INPUTS_LANG")))

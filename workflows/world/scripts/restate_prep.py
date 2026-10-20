# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""言い直す役の指示を prompts/world-classes.md から組む（前の回までの却下は place の控えから全部）。組めなければ node が落ち、出口が理由を残す"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402

ports.returns(steps.classes_prompt(ports.place()))

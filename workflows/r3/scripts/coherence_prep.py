# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""R3 の整合の役の指示を prompts/r3-coherence.md から組む。組めなければ node が落ち、出口がそれを判定の行にする"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402

ports.returns(steps.coherence_prompt(ports.place(), Path.cwd()))

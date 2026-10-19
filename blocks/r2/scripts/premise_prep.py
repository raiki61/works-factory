# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""R2 の前提の検算の役の指示を prompts/premise-check.md から組む"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402

ports.returns(steps.premise_prompt(ports.place(), Path.cwd()))

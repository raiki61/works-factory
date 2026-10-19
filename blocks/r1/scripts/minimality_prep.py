# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""R1 の冗長と最小性の役の指示を prompts/r1-minimality.md から組む（前段の返答のファイルが在るかで段落を選ぶ）"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402

ports.returns(steps.minimality_prompt(ports.place(), Path.cwd()))

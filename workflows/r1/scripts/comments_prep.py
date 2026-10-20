# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""R1 の前段（コメントの削除候補）の役の指示を prompts/r1-comments.md から組む。組めなければ node が落ち、2 段目はそのまま回る"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402

ports.returns(steps.comments_prompt(ports.place(), Path.cwd()))

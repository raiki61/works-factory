# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""web が off の run の、道具を持たない web の役の指示を prompts/world-judge-offline.md（web の役と同じ md）から組む。組めなければ node が落ち、出口が理由を残す"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402

ports.returns(steps.judge_prompt(ports.place(), steps.OFFLINE_NODE))

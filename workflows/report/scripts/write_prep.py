# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""書き手の指示を prompts/write.md から組む（前の回までの拒否は place の控えから全部）。先に機械の報告の冒頭から、resume の前に出口が置いた
「本文は無い」の行を外す。組めなければ node が落ち、出口が理由を残す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402

ports.returns(steps.write_prompt(ports.place(), run_id=os.environ.get("WORKFLOW_ID", "")))

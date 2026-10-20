# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""n 回目（INPUTS_N は 1 か 2）の審査役の指示を prompts/review-<n>.md から組む。組めなければ errors.json に node と訳を積んでから落ちる"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402

ports.returns(steps.review_prompt(ports.place(), steps.round_input(os.environ.get("INPUTS_N"))))

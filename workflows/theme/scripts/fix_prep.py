# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""拒まれた後の出し直しの役の指示を prompts/theme-writer-fix.md から組む（最後の拒否の理由と、合わせた前の答えの控えのパス）。組めなければ
node が落ち、出口が訳を残す"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

from src import steps  # noqa: E402

try:
    ports.returns(steps.fix_prep(ports.place()))
except Exception as error:
    steps.record_crash(ports.place(), "theme-fix-prep", f"{type(error).__name__}: {error}")
    raise

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""書き手の指示を prompts/theme-writer.md から組む。前の回の受け付けが拒み、合わせた答えの控えが在れば resubmit: true を返し（出し直しの役の
指示は fix_prep が組む）、指示は組まない。前の回までの却下は周のフォルダの控えから全部読む。組めなければ node が落ち、出口が訳を残す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

from src import steps  # noqa: E402

try:
    ports.returns(steps.prep(ports.place(), steps.value(os.environ.get("INPUTS_PREV"))))
except Exception as error:
    steps.record_crash(ports.place(), "write-prep", f"{type(error).__name__}: {error}")
    raise

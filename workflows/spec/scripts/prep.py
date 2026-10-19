# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""役（書く・審査・直す）の 1 回目の指示を prompts/spec-<役>.md から組む。前の周の受け付けが拒み、出し直しの控えが在れば
resubmit: true を返し（出し直しの役の指示は fix_prep が組む）、指示は組まない。組めなければ node が落ち、出口が理由を残す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

from src import files, steps  # noqa: E402

role = ports.choice(os.environ.get("INPUTS_ROLE"), tuple(files.ROLES))
ports.returns(steps.prep(ports.place(), role, files.value(os.environ.get("INPUTS_PREV"))))

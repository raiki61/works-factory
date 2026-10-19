# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""拒まれた後の出し直しの役の指示を prompts/spec-<役>-fix.md から組む（最後の拒否の理由と、合わせた前の答えの控えのパス）。
組めなければ node が落ち、受け付けが拒否にする"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

from src import files, steps  # noqa: E402

role = ports.choice(os.environ.get("INPUTS_ROLE"), tuple(files.ROLES))
ports.returns(steps.fix_prompt(ports.place(), role))

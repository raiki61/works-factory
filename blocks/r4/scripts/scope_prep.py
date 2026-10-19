# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""R4 の範囲の役の輪の頭: 前の周が拒まれ、合わせた答えの控えが在れば出し直しの周（resubmit: true。出し直しの役の指示は scope_fix_prep が組む）、
そうでなければ 1 回目の役の指示を prompts/r4-scope.md から組む。返り {prompt, resubmit, attempt}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402

ports.returns(steps.scope_prep(ports.place(), Path.cwd(), os.environ.get("INPUTS_PREV")))

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""再審の役の 1 回目の指示を prompts/rejudge.md から組む（前の回までの却下は place の控えから全部）。前の周の受け付けが拒み、合わせた
答えの控えが在れば resubmit: true を返し（出し直しの役の指示は rejudge_fix_prep が組む）、指示は組まない。組めなければ
prompt-error.json に訳を書いて node が落ち、出口が理由を残す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import inputs, rejudge  # noqa: E402

ports.returns(inputs.prep(ports.place(), inputs.rejudge_prompt, rejudge.value(os.environ.get("INPUTS_PREV"))))

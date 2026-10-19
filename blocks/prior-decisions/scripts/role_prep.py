# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""突合の役の指示を prompts/prior-decisions.md から組む（前の回までの却下は place の控えから全部）。組めなければ node が落ち、
出口が「役の返答を受けた記録が無い」で返す"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
import materialkit  # noqa: E402  （lib/。ports を読むと lib/ が sys.path に入る）
from src import viewpoint  # noqa: E402
import prompt  # noqa: E402

values, when, n = materialkit.prompt_inputs(viewpoint, ports.place(), prompt.lang)
ports.returns(prompt.emit(viewpoint.NAME, values, when, n))

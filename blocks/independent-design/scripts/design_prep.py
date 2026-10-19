# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""独立設計の役の指示と system prompt を prompts/design.md と prompts/design.system.md から組む（前の回までの却下は place の控えから
全部）。役を起こす前の作業ツリーの姿と貼った前提の控えも置く。組めなければ node が落ち、出口が理由を残す"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402

try:
    ports.returns(steps.design_prompt(ports.place(), Path.cwd()))
except Exception as error:
    steps.record_crash(ports.place(), "design_prep", f"{type(error).__name__}: {error}")
    raise

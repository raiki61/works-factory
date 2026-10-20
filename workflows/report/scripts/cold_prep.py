# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""初見の読み手の指示を prompts/cold.md から組む。貼る本文は人に向けた報告の頭と同じ物（機械の報告の冒頭・書き手の返答の頭・その頭に現れる語の
定義を、語の表で言い換えた物）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402

ports.returns(steps.cold_prompt(ports.place(), os.environ.get("INPUTS_WRITER", "")))

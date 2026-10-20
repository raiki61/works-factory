# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""役の返答をそのまま place の <name>.json に書く（後ろの役と出口がファイルで読む）。name が src/files.py の REPLIES の外なら落ちる"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402

ports.returns(steps.save(ports.place(), ports.text(os.environ.get("INPUTS_NAME")), os.environ.get("INPUTS_REPLY")))

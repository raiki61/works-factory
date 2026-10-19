# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""レンズの指示を prompts/<レンズ>.md から組む。組めなければ errors.json に積んでから落ち（レンズの node は起きず、出口がその行を failed にする）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

from src import steps  # noqa: E402

name = os.environ.get("INPUTS_LENS", "")
try:
    out = steps.lens_prompt(ports.place(), name)
except Exception as e:  # noqa: BLE001
    steps.add_error(ports.place(), name, f"{type(e).__name__}: {e}")
    sys.exit(f"lens-prep {name}: {type(e).__name__}: {e}")
ports.returns(out)

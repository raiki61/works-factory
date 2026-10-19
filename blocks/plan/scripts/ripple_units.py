# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""案の前の波及の一覧（単位の key の名の呼び出し元と試験）を r<k>/ripple-units.json に書く。形 replan では走らない。返り {ok}"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

from src import steps  # noqa: E402

ports.returns(steps.ripple_units(ports.place(), Path.cwd()))

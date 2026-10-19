# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node suite-place: 実行器を書く役の返り（{made, body, why}）の本文を place の suite/ に実行の印つきで書き、照らす印を実行器の控えに置く
（suitewrite.place）。{made, why}。落ちない: 読めない入力は made: false と訳の返りにする（控えの悲観の印は suite-prep が置いたまま）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute() -> dict:
    import suitewrite
    from src import files, suite
    place = ports.place()
    return suitewrite.place(suite.path(place), files.suite_folder(place), ports.parsed(os.environ.get("INPUTS_REPLY")))


ports.run(compute, lambda why: {"made": False, "why": why})

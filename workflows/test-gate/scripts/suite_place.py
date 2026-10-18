# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 suite-place: 実行器を書く役の返り（{made, body, why}）の本文を test-gate/suite/ に実行の印つきで書き、照らす印を記録に置く
（suitewrite.place）。{made, why}。落ちない: 読めない入力は made: false と訳の返りにする（記録の悲観の印は suite-prep が置いたまま）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import suitewrite


def place() -> dict:
    start = boundary.needed(os.environ.get("INPUTS_START", ""), "start")
    folder = Path(os.environ["ARTIFACTS_DIR"]) / "test-gate" / "suite"
    return suitewrite.place(start, folder, boundary.parsed(os.environ.get("INPUTS_REPLY", "")))


if __name__ == "__main__":
    boundary.run(place, lambda reason: {"made": False, "why": reason})

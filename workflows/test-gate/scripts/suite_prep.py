# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 suite-prep: TDD の実行器を用意する輪の 1 周の頭。取り置き（境の口の suite_keep）に同じ test_cmd の実行器が在れば
test-gate/suite/ に写して書き手を起こさず、無いか前の周で取り置きが照らしを通らなかったなら、書き手の役の材料の文を置いて記録に
悲観の印を置く（suitewrite.prepare）。{write, brief_file}。
落ちない: 読めない入力は write: false の返りにする（記録に印が無ければ報告は何も言わない）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import suitewrite


def prepare() -> dict:
    start = boundary.needed(os.environ.get("INPUTS_START", ""), "start")
    folder = Path(os.environ["ARTIFACTS_DIR"]) / "test-gate" / "suite"
    return suitewrite.prepare(start, folder, boundary.suite_keep(), Path.cwd())


if __name__ == "__main__":
    boundary.run(prepare, lambda reason: {"write": False, "brief_file": ""})

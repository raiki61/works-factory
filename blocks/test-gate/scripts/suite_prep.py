# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node suite-prep: TDD の実行器を用意する輪の 1 周の頭。取り置き（ports.suite_keep）に同じ test_cmd の実行器が在れば place の suite/ に写して
書き手を起こさず、無いか前の周で取り置きが照らしを通らなかったなら、書き手の材料の文を置いて実行器の控えに悲観の印を置き
（suitewrite.prepare）、書き手の役の指示を組んで返す。{write, prompt}。
落ちない: 読めない入力は write: false の返りにする（控えに印が無ければ報告は何も言わない）"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute() -> dict:
    import suitewrite
    from src import files, prompts, suite
    place = ports.place()
    got = suitewrite.prepare(suite.path(place), files.suite_folder(place), ports.suite_keep(), Path.cwd())
    if not got["write"]:
        return {"write": False, "prompt": ""}
    return {"write": True, "prompt": prompts.suite_write(got["brief_file"])["prompt"]}


ports.run(compute, lambda why: {"write": False, "prompt": ""})

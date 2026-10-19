"""TDD の実行器の控え suite-state.json の読み書きと、出力の欄 suite・suite_note の組み方。

lib/suitewrite.py は始めの記録のファイルを start_file として渡されて読み書きする（欄は test_cmd・tdd_suite・suite_written の 3 つだけ）。
block は始めの記録を持たないので、place の suite-state.json を代わりに渡す（docs/design/test-gate.md の 11 節の 2）。
照らしが通ると tdd_suite に実行器の絶対パスが入る。
"""
from __future__ import annotations

import pathlib

import startrec     # lib/。形を問わない JSON の読み書き
import suitewrite   # lib/

from src import files


def path(place) -> pathlib.Path:
    return pathlib.Path(place) / files.SUITE_STATE


def write(place, test_cmd: str, tdd_suite: str) -> None:
    startrec.save(path(place), {"test_cmd": test_cmd, "tdd_suite": tdd_suite})


def load(place) -> dict:
    return startrec.load(path(place))


def outputs(place, mode: str, tdd_suite: str) -> dict:
    """出力の欄 {suite, suite_note}。suite はこの後の段が使う実行器のパス。base: port の tdd_suite が在ればそれ、無ければ照らしを
    通った実行器（place の suite/runner の絶対パス）、作れなければ ""。final: port の tdd_suite のまま。suite_note は実行器を取り置きから
    使った・書いた・作れなかったの 1 行（suitewrite.head_note。用意しなかった run は ""）"""
    state = load(place)
    suite = (state.get("tdd_suite") or "") if mode == "base" else tdd_suite
    return {"suite": suite, "suite_note": suitewrite.head_note(state)}

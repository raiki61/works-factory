# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node tdd-go（組の形）: TDD の輪と修正役の輪を回すかを、輪の頭の返り（tdd-start.json。group-start が書き、起動スクリプトを書き直した
組は suite-fix-try が書き直す）から決める（src/suitefix.gate）。{tdd, stop}。stop は起動スクリプトが書き直しても壊れたままの組で、
修正役の輪も回さない（確かめていない直しを書き進めない。docs/design/fix.md の 19 節）。落ちない: 読めなければ tdd: false・stop: false"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute() -> dict:
    from src import suitefix
    return suitefix.gate(ports.place())


ports.run(compute, lambda why: {"tdd": False, "stop": False})

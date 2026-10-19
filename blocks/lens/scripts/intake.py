# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""レンズの入口: port を読み、この block のファイルを消し、修正の前の版 base から今の作業ツリーまでの差分を切って、レンズごとに起こすかを
決める（lens.json に振り分けの行、intake.json に定義の本文）。壊れても落ちず、全部の <key>_go を偽にして返す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.intake(ports.place(), Path.cwd(), base=os.environ.get("INPUTS_BASE"), lenses_raw=os.environ.get("INPUTS_LENSES"),
                        lang=os.environ.get("INPUTS_LANG"))


ports.run(compute, lambda why: {"due": False, "reason": f"レンズの入口が落ちた（{why}）", "silent_failure_hunter_go": False})

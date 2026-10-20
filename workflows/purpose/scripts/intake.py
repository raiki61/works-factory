# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""目的の固定の入口: port を読み、place に固めた目的が在れば役を起こさない。無ければこの block のファイルを消して intake.json と
作業ツリーの写し tree.json を書く。port が読めなくても落ちず、due: false と理由を返す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.intake(ports.place(), request=os.environ.get("INPUTS_REQUEST"), pr_text=os.environ.get("INPUTS_PR_TEXT"),
                        constraints=os.environ.get("INPUTS_CONSTRAINTS"), lang=os.environ.get("INPUTS_LANG"))


ports.run(compute, lambda why: {"due": False, "reason": f"目的の役の支度が落ちた（{why}）"})

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""案内の道の目の入口: port を読み、place のこの block のファイルを消して intake.json を書く。port が読めなくても落ちず、due: false と理由を返す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.intake(ports.place(), requests=os.environ.get("INPUTS_REQUESTS"), entry=os.environ.get("INPUTS_ENTRY"),
                        lang=os.environ.get("INPUTS_LANG"))


ports.run(compute, lambda why: {"due": False, "requests": 0, "reason": f"入口が落ちた（{why}）"})

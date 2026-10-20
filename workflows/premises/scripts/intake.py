# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""前提の実測の入口: port を読み、この block のファイルを消して intake.json と作業ツリーの写し tree.json を書く。port が読めなくても落ちず、due: false と理由を返す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.intake(ports.place(), request=os.environ.get("INPUTS_REQUEST"), carried=os.environ.get("INPUTS_CARRIED"),
                        lang=os.environ.get("INPUTS_LANG"))


def fallback(why: str) -> dict:
    return {"due": False, "reason": f"前提の実測の支度が落ちた（{why}）"}


ports.run(compute, fallback)

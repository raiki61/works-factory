# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""取る問題の類を上限まで決めて plan.json に書く。返り {due, reason}（due は web の役を起こすか）。落ちない"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.pick(ports.place())


ports.run(compute, lambda why: {"due": False, "reason": f"類を決める node が落ちた（{why}）"})

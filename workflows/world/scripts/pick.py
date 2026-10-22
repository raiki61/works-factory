# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""言い直しの行に出た問題の類を全部 plan.json に書く。返り {due, web, reason}（due は web の役を起こすか）。落ちない"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.pick(ports.place())


ports.run(compute, lambda why: {"due": False, "web": False, "reason": f"類を決める node が落ちた（{why}）"})

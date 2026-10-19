# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""読み手が置いた所を、頼みの閉じるべき所と比べる。返り {due, misses, reason}。落ちない"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.compare(ports.place())


ports.run(compute, lambda why: {"due": False, "misses": 0, "reason": f"比べる node が落ちた（{why}）"})

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""差分の審査の出口: 往復の控えを読んで holes.json・delta.diff を書き、block の返りを返す。どの段が落ちても落ちない"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import summary  # noqa: E402


def compute():
    return summary.finish(ports.place(), Path.cwd())


def fallback(why: str) -> dict:
    reason = f"出口が落ちた（{why}）"
    return {"ok": False, "status": "failed", "reason": reason, "rounds": 0, "pass": False, "holes": None, "diff": None, "carry": [],
            "report": [f"- 差分の審査の段が落ちた: {reason}"]}


ports.run(compute, fallback)

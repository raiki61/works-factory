# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""前提の実測の出口: 受けた制約の pointer と数と報告の行を返す。どの段が落ちても落ちない"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.finish(ports.place())


def fallback(why: str) -> dict:
    return {"ok": False, "status": "failed", "reason": why, "constraints": None, "measured": 0, "hypotheses": 0,
            "report": [f"前提の制約: {why}"]}


ports.run(compute, fallback)

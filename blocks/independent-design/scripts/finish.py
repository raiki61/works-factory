# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""独立設計の出口: 受け取った設計と貼った前提の控えの pointer、設計の無い訳、下げている所、報告の行を返す。どの段が落ちても落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.finish(ports.place())


def fallback(why: str) -> dict:
    reason = f"出口が落ちた（{why}）"
    return {"ok": False, "status": "failed", "stands": None, "design": None, "premises": None, "reason": reason,
            "downgrades": [], "report": [f"独立設計: {reason}"]}


ports.run(compute, fallback)

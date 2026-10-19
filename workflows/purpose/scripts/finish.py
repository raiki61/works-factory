# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""目的の固定の出口: 固めた目的の pointer と、目的の文・出典の語・解き方の並びを返す。どの段が落ちても落ちない"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.finish(ports.place())


def fallback(why: str) -> dict:
    return {"ok": False, "status": "failed", "reason": why, "purpose": None, "purpose_text": "", "source": "", "means": [],
            "report": [f"目的の文: {why}"]}


ports.run(compute, fallback)

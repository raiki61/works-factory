# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""案内の道の目の出口: 頼みごとの道を paths.json に書き、block の返りを返す。どの段が落ちても落ちない"""
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
    return {"ok": False, "status": "failed", "reason": reason, "paths": None, "fixes": [], "hits": 0, "misses": 0,
            "report": [f"- 案内の道の目が最後まで回らなかった: {reason}"]}


ports.run(compute, fallback)

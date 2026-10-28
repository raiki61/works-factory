# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""設計の案の書き手の出口: 受けた設計の案と md の pointer、status、訳、報告の行を返す。どの段が落ちても落ちない"""
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
    return {"ok": False, "status": "failed", "design": None, "design_md": None, "reason": reason, "report": [f"設計の案: {reason}"]}


ports.run(compute, fallback)

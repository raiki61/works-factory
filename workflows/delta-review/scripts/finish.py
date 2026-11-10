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


def compute():
    from src import summary   # lib を読む src は守った中で読む（lib を読めない時も fallback で返す。落とし穴 K1）
    return summary.finish(ports.place(), Path.cwd())


def fallback(why: str) -> dict:
    reason = f"出口が落ちた（{why}）"
    return {"ok": False, "status": "failed", "reason": reason, "rounds": 0, "pass": False, "holes": None, "diff": None, "carry": [],
            "report": [f"- 差分の審査の段が落ちた: {reason}"]}


ports.run(compute, fallback)

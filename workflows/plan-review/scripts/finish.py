# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""事前審査の出口: 受けた審査の返答と往復の記録に足す行の材料の pointer、block の穴の key、人に回しうる行と外れと案の直しの事実、
報告の行を返す。どの段が落ちても落ちない"""
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
    return {"ok": False, "status": "failed", "form": "", "round": 0, "reason": reason, "holes": None, "blocks": [], "pass": None,
            "asks": [], "deviations": [], "replan": [], "gave_up": None, "reads": None, "report": [f"事前審査: {reason}"]}


ports.run(compute, fallback)

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""R2 の出口: place の intake.json と役の返答のファイルから判定の行と報告の行を組む（落ちた node へは with: を結ばない）。落ちない:
中の誤りも、JSON に書けない出力（NaN・Infinity）も、出口が落ちた形の出力にする"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    out = steps.finish(ports.place())
    try:
        json.dumps(out, allow_nan=False)
    except ValueError as e:
        raise ValueError(f"出力が JSON に書けない: {e}") from None
    return out


def fallback(why: str) -> dict:
    row = {"status": "unverifiable", "reason": f"出口が落ちた: {why}"}
    return {"ok": False, "status": "failed", "reason": row["reason"], "verdict": row, "questions": [],
            "premise_check": None, "notes": [], "report": [f"R2: {row['status']}（{row['reason']}）"]}


ports.run(compute, fallback)

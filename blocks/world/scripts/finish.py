# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""世界の解の出口: 行を行のファイル（lib/worldmark の WORLD_FILE）に、段の控えを state.json に書き、block の返りを返す。どの段が落ちても落ちない（落とし穴 K1・K13）"""
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
    return {"ok": False, "status": "failed", "reason": reason, "rows": None, "classes": 0, "dropped": 0,
            "report": [f"- 世界の解の段が落ちた（行なしで進んだ）: {reason}"]}


ports.run(compute, fallback)

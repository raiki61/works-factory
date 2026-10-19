# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""仕様の出口: write は止めの控えと固めた仕様から status・stop_reason・pointer・報告の行を、check は照らしの返りから問いを返す。
どの段が落ちても落ちない（落とし穴 K1・K13）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.finish(ports.place(), ports.parsed(os.environ.get("INPUTS_CHECKED")))


def fallback(why: str) -> dict:
    reason = f"出口が落ちた（{why}）"
    return {"ok": False, "status": "failed", "stop_reason": "works:spec", "reason": reason, "spec": None, "added_rows": None,
            "added_origin": "", "questions": [], "unchecked": False, "report": [f"仕様: 固まらなかった（{reason}）"]}


ports.run(compute, fallback)

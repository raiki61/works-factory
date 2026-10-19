# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""レンズの出口: 受け取った返答で lens.json の行を埋め、数えと報告の行を返す。どの段が落ちても落ちない（標準ライブラリだけの逃げ道を持つ）"""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.finish(ports.place())


def fallback(why: str) -> dict:
    return {"ok": False, "status": "failed", "reason": why, "rows": None, "ran": 0, "failed": 0, "not_routed": 0, "carry": [],
            "report": [f"レンズ: 落ちた（{why}）"], "optional": [{"node": "silent-failure-hunter", "bare": False},
                                                              {"node": "silent-failure-hunter-take", "bare": False}]}


ports.run(compute, fallback)

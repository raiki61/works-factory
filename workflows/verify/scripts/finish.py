# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""判定の裏取りの出口: 答えのファイルを確かめて申し送りを書き、作業ツリーを比べ、返りを返す。どの段が落ちても落ちない"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.finish(ports.place())


def fallback(why: str) -> dict:
    return {"ok": False, "status": "failed", "stop_reason": "", "reason": f"判定の裏取りのまとめの中で例外（{why}）", "verify": None,
            "report": [f"判定の単位の裏取り: まとめが落ちた（{why}）"]}


ports.run(compute, fallback)

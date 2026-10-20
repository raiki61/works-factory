# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正案の出口: 受けた案の有無・status・pointer の先（在って空でない plan-fields.json・ripple.json）・形 replan で諦めた項目ごとの行・報告の行を返す。
どの段が落ちても落ちない（標準ライブラリだけで finish-error.txt に訳を書き、status failed の約束の形を返す）"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.finish(ports.place())


def fallback(why: str) -> dict:
    from src import files
    return files.crash_finish(ports.place(), f"出口の中で誤りが起きた: {why}")


ports.run(compute, fallback)

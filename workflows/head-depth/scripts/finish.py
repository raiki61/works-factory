# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""run の頭の深さの出口: 控え depth-head.json を読み、段・根拠・行・控えの pointer・報告の行を返す。どの段が落ちても落ちない"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.finish(ports.place())


def fallback(why: str) -> dict:
    from src import steps
    return steps.fallback(ports.place(), why)


ports.run(compute, fallback)

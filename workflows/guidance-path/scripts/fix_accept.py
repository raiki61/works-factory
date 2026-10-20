# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""案内を見直す役の返答を受け付ける: 外れた頼みの全部に直しが 1 つ以上・種類が決まった語。3 回目の却下で done。落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.fix_accept(ports.place(), os.environ.get("INPUTS_REPLY", ""))


ports.run(compute, lambda why: {"ok": False, "done": True, "reason": f"受け付けが落ちた（{why}）"})

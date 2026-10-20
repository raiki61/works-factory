# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""web の役の返答を受け付ける: 抜き書きを同じ URL から取り直した本文で照らし、字のまま無い抜き書きを指す根拠を外す。3 回目の却下で done。
諦めても落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.accept(ports.place(), steps.JUDGE_ROLE, os.environ.get("INPUTS_REPLY", ""))


ports.run(compute, lambda why: {"ok": False, "done": True, "reason": f"受け付けが落ちた（{why}）"})

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""実測役の返答を受け付ける: 依頼の実測を測り直した・作業ツリーを変えていない・実測の行が出力を持つ。通れば premises.json を書く。3 回目の却下で done。諦めても落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.take(ports.place(), os.environ.get("INPUTS_REPLY", ""), Path.cwd())


def fallback(why: str) -> dict:
    return {"ok": False, "done": True, "reason": f"受け付けが落ちた（{why}）"}


ports.run(compute, fallback)

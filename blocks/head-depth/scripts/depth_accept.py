# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""run の頭の深さの役の返答を受け付ける: 引用が依頼とリポジトリに字のまま在るかを照らし、通れば一番重い種類の段と群の選びを控え
depth-head.json に書く。拒めば標準と訳で書き直す。3 回目の却下で done（run は止めない）。落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.take(ports.place(), os.environ.get("INPUTS_REPLY", ""), Path.cwd())


ports.run(compute, lambda why: {"ok": False, "done": True, "reason": f"受け付けが落ちた（{why}）"})

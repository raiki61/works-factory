# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""読み手の返答を受け付ける: 開いたファイルが作業ツリーに在る・置く所と手本のパスが根からの相対。頼みごとに 3 回目の却下で諦めて次へ。落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.walk_accept(ports.place(), os.environ.get("INPUTS_REPLY", ""))


ports.run(compute, lambda why: {"ok": False, "done": True, "reason": f"受け付けが落ちた（{why}）"})

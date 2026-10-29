# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""一般の構造を描く目を起こすかを決める: 構造を描く役の行が受け付けられていれば起こす。落ちない。返り {general, reason}"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import sketch
    return sketch.sketched(ports.place())


ports.run(compute, lambda why: {"general": False, "reason": f"構造を描く役の行を読めない（{why}）"})

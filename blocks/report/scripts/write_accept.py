# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""書き手の返答と初見の読み手の判定を受け付ける（ループの until が done を読む）。受け取った物は place に書く。諦めても落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import writer
    return writer.accept(os.environ.get("INPUTS_REPLY", ""), os.environ.get("INPUTS_COLD", ""), place=ports.place())


ports.run(compute, lambda why: {"done": True, "ok": False, "reason": f"受け付けが落ちた（{why}）", "kind": "answer", "prev_file": ""})

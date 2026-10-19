# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""書き手の返答と初見の読み手の判定を受け付ける（ループの until が done を読む）。受け取った物は place に書く。諦めても落ちないが、思わぬ誤りは落とす"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import writer
    return writer.accept(os.environ.get("INPUTS_REPLY", ""), os.environ.get("INPUTS_COLD", ""), place=ports.place())


ports.returns(compute())   # 思わぬ誤りは捕まえない: node を落として run を failed にし、finish が書き手のノードの落ちを機械の報告の頭に置く（resume できる）

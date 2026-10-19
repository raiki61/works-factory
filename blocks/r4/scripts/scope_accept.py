# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""R4 の範囲の役の返答の受け付け: 出し直しは前の答えの控えと欄ごとに合わせてから、方針とのぶつかりの名指しと（まとめた形では）欄 r3 を照らす。
拒否は控えに積み、3 回目の拒否で輪を抜ける。落ちない（中の誤りは諦めた拒否にする）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402


def compute():
    return steps.accept(ports.place(), steps.value(os.environ.get("INPUTS_REPLY")), steps.value(os.environ.get("INPUTS_FIX_REPLY")))


ports.run(compute, lambda why: {"ok": False, "done": True, "give_up": True, "reason": f"受け付けが落ちた: {why}"})

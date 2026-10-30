# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""n 回目（INPUTS_N は 1 か 2）の手直しの役の返答を受け付ける: 義務への答えの過不足・段の頭の木からの変更の申告・承認済みの修正案の範囲・書き込みの記録と申告。3 回目の拒否で done（作業ツリーの手直しは戻さない）。諦めても落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import files, steps, touchup  # noqa: E402


n = steps.round_input(os.environ.get("INPUTS_N"))   # 配線の誤り（n が 1 か 2 でない）は落ちて名指す


def compute():
    place = ports.place()
    return touchup.accept_reply(place, n, os.environ.get("INPUTS_REPLY", ""), Path.cwd(), steps.read_intake(place)["base"],
                                steps.sealed(os.environ.get("INPUTS_SEAL")))


def fallback(why: str) -> dict:
    files.broke(ports.place(), files.REFIX[n] + "-accept", f"受け付けが落ちた（{why}）")
    return {"ok": False, "done": True, "reason": f"受け付けが落ちた（{why}）"}


ports.run(compute, fallback)

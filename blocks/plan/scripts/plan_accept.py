# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正案の役の返答の受け付け。拒まれた後の出し直しの役の返答 fix_reply（拒まれた所だけ）は、前の回の答えの控えと合わせてから照らす。拒否は
rolekit.accept_round が控え rejects-plan.json に積み、受け付けの網（NET_AFTER）の回の拒否で done・give_up（輪を max_iterations で落とさずに抜ける）。
受けた案の控えを置けない時は拒否に数えずに done・give_up。拒否の控えが読めない・書けない時は、落ちずに done・give_up の拒否。落ちない。
返り {ok, done, give_up, reason, attempt}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps, take
    return take.accept(ports.place(), Path.cwd(), steps.value(os.environ.get("INPUTS_REPLY")), steps.value(os.environ.get("INPUTS_FIX_REPLY")))


ports.run(compute, lambda why: {"ok": False, "done": True, "give_up": True, "reason": f"受け付けが落ちた（{why}）", "attempt": 0})

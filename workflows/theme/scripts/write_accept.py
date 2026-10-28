# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""書き手の返答の受け付け。出し直しの役の返答 fix_reply（拒まれた欄だけ）は、前の回の答えの控えと合わせてから照らす。拒否は控え
rejects-theme.json に積み、3 回目の拒否で done・give_up。落ちない。返答 {ok, done, give_up, reason}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.accept(ports.place(), Path.cwd(), steps.value(os.environ.get("INPUTS_REPLY")), steps.value(os.environ.get("INPUTS_FIX_REPLY")))


def fallback(why: str) -> dict:
    try:
        from src import steps
        steps.record_crash(ports.place(), "write-accept", why)
    except Exception:  # noqa: BLE001 — 控えを残せなくても返答は返す
        pass
    return {"ok": False, "done": True, "give_up": True, "reason": f"受け付けが落ちた（{why}）"}


ports.run(compute, fallback)

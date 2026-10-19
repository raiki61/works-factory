# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""再審の役の返答を受け付ける: 作業ツリー・class_query の例・確かめた事実の長さ。拒まれた後の出し直しの役の返答 fix_reply（直す欄だけ）は、
前の答えの控えと欄ごとに合わせてから照らす。通れば judgment.json と単位の前後の差を書く。輪を抜ける時は出口 rejudge-exit.json を書く。
3 回目の却下で done。諦めても落ちない（落ちた訳は prompt-error.json に残す）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import inputs
    return inputs.accept_rejudge(ports.place(), os.environ.get("INPUTS_REPLY"), os.environ.get("INPUTS_FIX_REPLY"), Path.cwd())


def fallback(why: str) -> dict:
    reason = f"受け付けが落ちた（{why}）"
    try:
        from src import inputs
        inputs.fell(ports.place(), "rejudge-accept", reason)
    except Exception:  # noqa: BLE001 — 落ちない node の口。控えが書けなくても返りは返す
        pass
    return {"ok": False, "done": True, "reason": reason}


ports.run(compute, fallback)

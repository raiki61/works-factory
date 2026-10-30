# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""事前審査の返答を受け付ける（docs/design/plan-review.md の 9.1）。4 つの組の返答（review・review-fix・review-tree・review-tree-fix。
起きなかった node は null）のうち起きた組を src/take.py の take に渡す。通れば review.json（と形 plan なら pass.json）を書く。
拒否の回数では諦めず、受け付けの網 rolekit.NET_AFTER 回目で done・give_up。中の誤りは crash.json に訳を書き、done・give_up で返す（落ちない）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    import accept  # lib/
    from src import steps, take
    return take.take(ports.place(), steps.reply_value(os.environ.get("INPUTS_REPLY", "")), Path.cwd(),
                     keys=accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", "")),
                     fix_reply=steps.reply_value(os.environ.get("INPUTS_FIX_REPLY", "")),
                     tree_reply=steps.reply_value(os.environ.get("INPUTS_TREE_REPLY", "")),
                     tree_fix_reply=steps.reply_value(os.environ.get("INPUTS_TREE_FIX_REPLY", "")))


def fallback(why: str) -> dict:
    try:
        from src import steps
        steps.record_crash(ports.place(), "review-accept", why)
    except Exception:  # noqa: BLE001 — 控えを残せなくても返りは返す
        pass
    return {"ok": False, "done": True, "give_up": True, "reason": f"受け付けが落ちた（{why}）"}


ports.run(compute, fallback)

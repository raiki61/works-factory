# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""設計の案の審査の返答を受け付ける（docs/design/plan-review.md の 19 節）。1 回目の役（review-theme）と出し直しの役
（review-theme-fix。起きなかった node は null）の返答を src/themeform.py の take に渡す。通れば review.json を書く。拒否の回数では
諦めず、受け付けの網 rolekit.NET_AFTER 回目で done・give_up。中の誤りは crash.json に訳を書き、done・give_up で返す（落ちない）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    import accept  # lib/
    from src import steps, themeform
    return themeform.take(ports.place(), steps.reply_value(os.environ.get("INPUTS_REPLY", "")), Path.cwd(),
                          keys=accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", "")),
                          fix_reply=steps.reply_value(os.environ.get("INPUTS_FIX_REPLY", "")))


def fallback(why: str) -> dict:
    try:
        from src import steps
        steps.record_crash(ports.place(), "theme-accept", why)
    except Exception:  # noqa: BLE001 — 控えを残せなくても返りは返す
        pass
    return {"ok": False, "done": True, "give_up": True, "reason": f"受け付けが落ちた（{why}）"}


ports.run(compute, fallback)

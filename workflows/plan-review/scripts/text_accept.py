# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""方針の文の審査の返答を受け付ける（docs/design/plan-review.md の 9.4）: 作業ツリーが役の前と同じ・穴の行ごとの照らし・返答の全体。
通れば review.json を書く。rolekit.GIVE_UP_AFTER 回目の却下で done・give_up（落ちない）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    import accept  # lib/
    from src import textform
    return textform.take(ports.place(), os.environ.get("INPUTS_REPLY", ""), Path.cwd(),
                         keys=accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", "")))


def fallback(why: str) -> dict:
    try:
        from src import steps
        steps.record_crash(ports.place(), "text-accept", why)
    except Exception:  # noqa: BLE001 — 控えを残せなくても返りは返す
        pass
    return {"ok": False, "done": True, "give_up": True, "reason": f"受け付けが落ちた（{why}）"}


ports.run(compute, fallback)

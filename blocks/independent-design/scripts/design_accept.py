# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""独立設計の役の返答を受け付ける: 作業ツリーが役の前と同じ・問いが立たない根拠の名指しが固めた版に在る・立つ設計は要素を持つ。
通れば design.json を書く。3 回目の却下で done・give_up（諦めても止めない）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    import accept  # lib/
    from src import steps
    return steps.check_design(ports.place(), os.environ.get("INPUTS_REPLY", ""), Path.cwd(),
                              keys=accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", "")))


def fallback(why: str) -> dict:
    try:
        from src import steps
        steps.record_crash(ports.place(), "design_accept", why)
    except Exception:  # noqa: BLE001 — 控えを残せなくても返りは返す
        pass
    return {"ok": False, "done": True, "give_up": True, "reason": f"受け付けが落ちた（{why}）"}


ports.run(compute, fallback)

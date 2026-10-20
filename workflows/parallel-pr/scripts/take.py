# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""並行 PR の役の返答を受け付ける: 投稿していない・作業ツリーを変えていない・素材の欄が決まりに合う・外す hunk が合う。
3 回目の却下で done。諦めても落ちない（出口が status: failed にする）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import take
    got = take.accept(ports.place(), Path.cwd(), os.environ.get("INPUTS_REPLY", ""))
    return {"ok": bool(got["ok"]), "done": bool(got["done"]), "reason": str(got["reason"])}


ports.run(compute, lambda why: {"ok": False, "done": True, "reason": f"受け付けが落ちた（{why}）"})

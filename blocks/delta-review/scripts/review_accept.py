# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""n 回目（INPUTS_N は 1 か 2）の審査役の返答を受け付ける: 穴と検算の照らし・1 回目だけ 2 判定の照らし・機械の穴の追加・作業ツリーの写しとの比べ。3 回目の拒否で done。諦めても落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import files, review, steps  # noqa: E402


n = steps.round_input(os.environ.get("INPUTS_N"))   # 配線の誤り（n が 1 か 2 でない）は落ちて名指す


def compute():
    return review.accept_reply(ports.place(), n, os.environ.get("INPUTS_REPLY", ""), Path.cwd(), steps.sealed(os.environ.get("INPUTS_SEAL")))


def fallback(why: str) -> dict:
    steps.broke(ports.place(), files.REVIEW[n] + "-accept", f"受け付けが落ちた（{why}）")
    return {"ok": False, "done": True, "reason": f"受け付けが落ちた（{why}）"}


ports.run(compute, fallback)

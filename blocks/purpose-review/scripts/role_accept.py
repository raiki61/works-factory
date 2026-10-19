# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""目的の監査の役の返答を受け付ける: 作業ツリーを変えていない・根拠の字を固めた版で数え直して申告と合う。3 回目の却下で done。
諦めても落ちない（出口が status: gave_up にする）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
import materialkit  # noqa: E402  （lib/。ports を読むと lib/ が sys.path に入る）
from src import viewpoint  # noqa: E402

got = materialkit.accept(viewpoint, ports.place(), Path.cwd(), os.environ.get("INPUTS_REPLY", ""))
ports.returns({"ok": got["ok"], "done": got["done"], "reason": got["reason"]})

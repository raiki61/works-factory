# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""整合性と迂回の役の返答を受け付ける: 作業ツリーを変えていない・所見の場所がファイルに在る・素材の欄が決まりに合う。3 回目の却下で done。
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

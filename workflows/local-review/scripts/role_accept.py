# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""局所レビューの役の返答を受け付ける: 作業ツリーを変えていない・必須のレンズを起こした・宣言の 1 本に行が 1 本・所見の場所がファイルに在る・
素材の欄が決まりに合う。3 回目の却下（プラグインの欠けは 1 回目）で done。諦めても落ちない（出口が status: gave_up にする）。
lens_gap が CLAUDE_CONFIG_DIR を読むので、Archon が node に渡した環境をそのまま使う"""
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

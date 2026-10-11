"""形の振り分け: 入力 mode が group なら組の子の run、空ならブロックの形。include の中の when: は $INPUTS を左に置けないので、
ここが読んで返す。知らない語は止める（黙ってブロックの形にしない）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

MODES = {"": False, "group": True}

mode = os.environ.get("INPUTS_MODE", "")
if mode not in MODES:
    sys.exit(f"入力 mode は空か group: {mode!r}")
boundary.returns({"group": MODES[mode]})

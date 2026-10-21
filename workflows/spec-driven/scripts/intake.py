# /// script
# requires-python = ">=3.12"
# dependencies = ["PyYAML==6.0.3"]
# ///
"""形 entry の入口（docs/design/spec-driven.md の 6.2 の足す node の 1・6.7）: 仕様駆動の道の表（YAML）を読む、この block でただ 1 本の
script。表を確かめ、判定の役と計画の部品に渡す値を組んで place に置く（src/entry.py）。落ちない: 誤りは止めの返りにする"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import entry, files
    return {"done": entry.entry(ports.place(), Path.cwd(), os.environ.get("INPUTS_TABLE"), os.environ.get(files.REVIEWS_ENV, ""))["ok"],
            "reason": ""}


ports.run(compute, lambda why: {"done": False, "reason": f"入口が落ちた（{why}）"})

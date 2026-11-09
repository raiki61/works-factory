# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""診断の出口: 判定か再審の結果を返す。どの段が落ちても落ちない（落ちた訳は reason に）。judgment の pointer は、出口が落ちて形の照らし（lib）も
読めない時のほかはいつも在る"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import exit as finish
    return finish.finish(ports.place(), Path.cwd(), os.environ.get("INPUTS_OBJECTION", ""))


def fallback(why: str) -> dict:
    from src import fallback as fell   # 標準ライブラリだけ（lib を読めない時も返す。落とし穴 K1）
    return fell.fallen(ports.place(), why, os.environ.get("INPUTS_OBJECTION", ""))


ports.run(compute, fallback)

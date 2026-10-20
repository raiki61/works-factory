# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""診断の出口: 判定か再審の結果を返す。どの段が落ちても落ちない（落ちた訳は reason に）。judgment の pointer はいつも在る"""
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
    from src import exit as finish
    return finish.fallback(ports.place(), why, os.environ.get("INPUTS_OBJECTION", ""))


ports.run(compute, fallback)

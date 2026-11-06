# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""一言の向きの判定の出口: 受け皿が place に写した役の返答（reply.json）を読み、{ok, status, reason, direction, aligned, why, report} を返す。
aligned が真になるのは向きが aligned の時と、役を起こさなかった（skipped）時だけ。支度が落ちた・入力が読めない・返答が無いか読めない時は
status failed で aligned 偽。どの段が落ちても落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import direction
    saved = ports.place() / direction.REPLY
    raw = saved.read_text(encoding="utf-8") if saved.is_file() else ""
    return direction.outcome(ports.parsed(os.environ.get("INPUTS_PREP")), raw)


def fallback(why: str) -> dict:
    from src import direction
    return direction.failed(f"出口が落ちた（{why}）")


ports.run(compute, fallback)

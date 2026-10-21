# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""出口: 形 entry か check の控えを読み、block の返りにする（形の欄の無い方は空の値）。控えが無ければ、落ちた訳を止めにして返す"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

EMPTY = {"ok": False, "stop_reason": "", "reason": "", "request": None, "origin": "", "purpose": None, "spec": None, "spec_files": [],
         "tdd": False, "out_of_scope": [], "mismatches": [], "report": []}


def fallen(why: str) -> dict:
    stop = "works:spec-entry"   # src/files.STOP_ENTRY と同じ字（src を読めない時の道）
    return {**EMPTY, "stop_reason": stop, "reason": why, "report": [f"- 止めた（{stop}）: 仕様駆動の道の block が落ちた: {why}"]}


def compute():
    from src import files
    place = ports.place()
    picked = ports.parsed(os.environ.get("INPUTS_PICK")) or {}
    name = files.ENTRY if picked.get("entry") else files.CHECK if picked.get("check") else None
    if name is None:
        return {**fallen(str(picked.get("reason") or "形を選べなかった")),
                "stop_reason": files.STOP_ENTRY if ports.text(os.environ.get("INPUTS_MODE")).strip() != "check" else files.STOP_MISMATCH}
    try:
        got = json.loads((place / name).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        stop = files.STOP_ENTRY if name == files.ENTRY else files.STOP_MISMATCH
        ran = ports.parsed(os.environ.get("INPUTS_ENTRY_RUN" if name == files.ENTRY else "INPUTS_CHECK_RUN")) or {}
        why = str(ran.get("reason") or "") or f"形の控え {name} を読めない（{type(error).__name__}）"
        return {**fallen(why), "stop_reason": stop}
    return {**EMPTY, **got}


ports.run(compute, fallen)

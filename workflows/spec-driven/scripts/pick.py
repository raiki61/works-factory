# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""形を選ぶ: 入力 mode（entry か check）を読み、回す node を決める。読めなくても落ちず、どちらも回さずに訳を返す（finish が止めにする）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

MODES = ("entry", "check")


def compute():
    from src import files
    place = ports.place()
    for name in files.OWN_FILES:
        (place / name).unlink(missing_ok=True)
    mode = ports.choice(os.environ.get("INPUTS_MODE"), MODES)
    return {"entry": mode == "entry", "check": mode == "check", "reason": ""}


ports.run(compute, lambda why: {"entry": False, "check": False, "reason": f"入力 mode を読めない（{why}）"})

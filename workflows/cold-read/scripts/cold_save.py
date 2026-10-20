# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""初見の読み手の返答の受け皿: 役の返答を place の reply.json に写す（出口は役の node を結ばず、このファイルで読む。役が落ちた・
飛ばされた時はこの node も飛び、ファイルは無い）。JSON に読めない返答は字のまま写し、出口が読めない返答と名指す。返り {saved}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    import jsonfile  # lib/
    from src import files
    raw = ports.text(os.environ.get("INPUTS_REPLY"))
    if not raw.strip() or raw.strip() == "null":
        return {"saved": False}
    path = ports.place() / files.REPLY_FILE
    try:
        jsonfile.write(path, ports.parsed(raw))
    except ValueError:   # 読めない返答は字のまま写す。出口の読みが名指して failed にする
        path.write_text(raw, encoding="utf-8")
    return {"saved": True}


def fallback(why: str) -> dict:
    return {"saved": False}


ports.run(compute, fallback)

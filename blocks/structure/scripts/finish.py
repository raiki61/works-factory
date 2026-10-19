# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""構造の目の出口: 控え structure-state.json を書いて指し、判定の行の数と報告の行を返す。落ちない: 境の口と lib の import から先の
誤りは全部捕まえ、標準ライブラリだけで status: failed の控えと 0 バイトの design.jsonl を書いて返す"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import state
    return state.finish(ports.place())


def fallback(why: str) -> dict:
    from src import files
    try:
        place = ports.place()
        design = place / files.DESIGN_FILE
        if not design.is_file():
            design.write_bytes(b"")
        doc = {"status": "failed", "reason": f"出口の中で誤りが起きた: {why}", "design_file": str(design), "skipped": []}
        (place / files.STATE_FILE).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        pointer = ports.pointer(place / files.STATE_FILE)
    except Exception as error:  # noqa: BLE001 — 出口は落ちない
        pointer, why = None, f"{why} / 控えを書けない: {error}"
    return {"ok": False, "status": "failed", "reason": f"出口の中で誤りが起きた: {why}", "structure": pointer, "dirty": 0, "escalate": 0,
            "optional": files.OPTIONAL, "report": [f"構造の目: 出口の中で誤りが起きた（{why}）"]}


ports.run(compute, fallback)

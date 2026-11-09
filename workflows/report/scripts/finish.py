# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""報告の出口。書き手のループが落ちた訳を機械の報告の冒頭に置き（resume で書き直した run では外す）、人に向けた報告と詳細のファイルを書いて
出力を返す。落ちない: 思わぬ誤りは捕まえて record_invalid と訳を返し、facts の機械の報告が在ればそれを指す。ライブラリを読めない時は
訳だけのファイルを書いて指す（題の行は src/title.py から facts.json の依頼の字で描く。それも読めない時だけ題の行を付けない）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.finish(ports.place(), run_id=os.environ.get("WORKFLOW_ID", ""))


def fallback(why: str) -> dict:
    try:
        from src import steps
        return steps.finish_fallback(ports.place(), why, os.environ.get("WORKFLOW_ID", ""))
    except Exception:  # noqa: BLE001 — ライブラリを読めない時は標準ライブラリだけで訳だけのファイルを書いて指す
        path = ports.place() / "report-finish-unwritten.md"
        try:
            from src import title   # 題の型の字は標準ライブラリと ports だけの 1 か所。依頼の字は facts の facts.json から読む
            first = title.render(os.environ.get("WORKFLOW_ID") or "—", title.requests_in(str(ports.place() / "facts.json")))
            body = f"{first}\n\n報告を組めなかった: {why}\n"
        except Exception:  # noqa: BLE001 — 題の部品そのものを読めない時だけ、題の行を付けずに訳を書く
            body = f"報告を組めなかった: {why}\n"
        path.write_text(body, encoding="utf-8")
        ptr = ports.pointer(path, "file")
        return {"outcome": "record_invalid", "ok": False, "stop_reason": f"report:{why}", "machine": ptr, "human": None, "detail": None, "next_request": None, "prior_failures": None, "report": [f"機械の報告: {ptr['path']}"]}


ports.run(compute, fallback)

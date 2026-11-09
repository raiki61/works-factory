# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""報告の最初の node: port（sections・facts・lang）と run の記録を読み、結末を決め、機械の報告・次の run の依頼の下書き・前の失敗を place に書く。
facts.json に書き手の段の値を置く。0 以外で終わらない（落ちると出口が結果を受けられない）: 思わぬ誤りは捕まえ、訳を載せた機械の報告を指す
record_invalid で返す。ライブラリを読めない時も、標準ライブラリだけで訳だけのファイルを書いて返す
（題の行は src/title.py から描く。それも読めない時だけ題の行を付けない）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import files, steps
    return steps.facts(ports.place(), sections=os.environ.get("INPUTS_SECTIONS"), facts=os.environ.get("INPUTS_FACTS"),
                       lang=os.environ.get("INPUTS_LANG"), run_id=os.environ.get("WORKFLOW_ID", ""),
                       workflow_file=Path(__file__).resolve().parents[1] / files.WORKFLOW_FILE, repo=Path.cwd())


def fallback(why: str) -> dict:
    try:
        from src import steps
        return steps.facts_fallback(ports.place(), why, os.environ.get("WORKFLOW_ID", ""), os.environ.get("INPUTS_FACTS"))
    except Exception:  # noqa: BLE001 — ライブラリを読めない時は標準ライブラリだけで訳だけのファイルを書いて指す
        path = ports.place() / "report-facts-unwritten.md"
        try:
            from src import title   # 題の型の字は標準ライブラリと ports だけの 1 か所
            first = title.render(os.environ.get("WORKFLOW_ID") or "—", title.requests_in(os.environ.get("INPUTS_FACTS")))
            body = f"{first}\n\n報告を組めなかった: {why}\n"
        except Exception:  # noqa: BLE001 — 題の部品そのものを読めない時だけ、題の行を付けずに訳を書く
            body = f"報告を組めなかった: {why}\n"
        path.write_text(body, encoding="utf-8")
        ptr = ports.pointer(path, "file")
        return {"outcome": "record_invalid", "ok": False, "stop_reason": f"report:{why}", "machine": ptr, "next_request": None, "prior_failures": None, "ai_go": False, "stamp": ""}


ports.run(compute, fallback)

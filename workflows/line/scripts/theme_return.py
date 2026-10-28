# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""計画の段から設計へ戻す node theme-return（docs/design/line.md の 3.3 節。決めは src.descend.back）。

テーマの run の計画の承認ノード gate-design で redesign と答えた時だけ、続きの run のテーマの md（前のテーマ・承認した設計・見つかった欠け・
持ち主の一言）・依頼のファイル（それまでの答え）・起動の 1 行を run の置き場の theme/next/ に書く。ほかの時は何も書かずに back: false。
run を閉じるのは修正前の承認ノード（agreed の語が通す語でないので human:gate-design で止める）。

入力（with:）: rounds（plan-rounds-out の got）・ports（start の配る値）・record（始めの記録の pointer）・descended（theme-descend の返り）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute() -> dict:
    from src import descend, startrec
    given = ports.parsed(os.environ.get("INPUTS_PORTS"))
    record_path = ports.file(os.environ.get("INPUTS_RECORD"), "json(start-record.schema.json)")
    record = startrec.load(record_path) if record_path else {}
    return descend.back(ports.parsed(os.environ.get("INPUTS_ROUNDS")), given=given if isinstance(given, dict) else {},
                        record=record if isinstance(record, dict) else {}, descended=ports.parsed(os.environ.get("INPUTS_DESCENDED")),
                        place=ports.place())


def fallback(reason: str) -> dict:
    return {"back": False, "next": "", "command": "", "reason": reason, "report": [f"設計の段: 続きの run の材料を書けなかった（{reason}）"]}


ports.run(compute, fallback)

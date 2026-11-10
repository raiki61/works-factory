"""run の頭の深さの出口が落ちた時の返り（docs/design/head-depth.md の 1.5 の「出口は落ちない」）。標準ライブラリと境の口 ports と
src/report.py（標準ライブラリだけ）だけを読む（出口の script が lib を読めない時にも同じ形を返す。落とし穴 K1）。

- fallen(place, why) -> 控えを標準と訳で書き直し、status: failed で返す。形の照らし（lib）を読めない時だけ record は null
  （照らせない控えは指さない。pointer の札は手で組まない）
- 段の語 STANDARD と控えの名 RECORD_FILE は src/steps.py と 1 か所（steps が読み込みの時に lib/headdepth.py の語と同じ字かを照らす）
"""
from __future__ import annotations

import json
import pathlib

import ports

from src import report

RECORD_FILE = "depth-head.json"
STANDARD = "標準"


def fallen(place, why: str) -> dict:
    doc = {"depth": STANDARD, "why": why, "items": [], "facts": {}, "groups": []}   # lib/headdepth.py の record(STANDARD, why) と同じ形
    path = pathlib.Path(place) / RECORD_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        record = ports.pointer(path, "json(shared:depth-record.schema.json)")
    except ImportError:   # 形の照らし（lib）を読めない
        record = None
    return {"ok": False, "status": "failed", "reason": why, "tier": STANDARD, "why": why, "rows": [], "record": record,
            "report": [report.report_line(STANDARD, why)]}

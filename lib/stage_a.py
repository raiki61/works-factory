# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""段 A の実測（設計書 structure-block-design の 2 節・8 節）の部品。structure.json と design.jsonl を書くのも、構造の目を起こすかを
決めるのもブロックの script で、ここは単位の読みと 1 単位の実測だけを出す。

- read_units(path): 入力の契約の単位のファイル（JSON の配列で、各行は {id, paths, summary}）を読み、形を確かめて返す。読めない・
  形が違うなら ValueError
- measure_unit(unit, root): 単位の paths を同じフォルダの measure.py に子のプロセスで渡し（コマンド 1 つの口。import しない）、
  {id, summary, paths, status, reason, measure} を返す。status は measured か failed（failed なら reason に measure.py の
  標準エラーの末尾 REASON_TAIL 字。実測が落ちても例外にしない）
"""
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように。必ず import より前

MEASURE = Path(__file__).resolve().parent / "measure.py"
REASON_TAIL = 2000


def read_units(path: str) -> list:
    """単位のファイルを読み、形を確かめて返す。読めない・形が違うなら ValueError"""
    if not path:
        raise ValueError("単位のファイルのパスが空")
    try:
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"単位のファイルが読めない: {e}") from None
    if not isinstance(rows, list):
        raise ValueError("単位のファイルが JSON の配列でない")
    for i, r in enumerate(rows):
        ok = (isinstance(r, dict) and isinstance(r.get("id"), str) and r["id"]
              and isinstance(r.get("paths"), list) and r["paths"] and all(isinstance(p, str) and p for p in r["paths"])
              and isinstance(r.get("summary", ""), str))
        if not ok:
            raise ValueError(f"単位 {i} の形が違う（id は空でない文字列・paths は空でない文字列の空でない配列・summary は文字列）")
    return rows


def measure_unit(unit: dict, root: Path) -> dict:
    row = {"id": unit["id"], "summary": unit.get("summary", ""), "paths": unit["paths"]}
    p = subprocess.run([sys.executable, str(MEASURE), "--paths", *unit["paths"], "--repo", str(root)], cwd=str(root),
                       capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
    if p.returncode == 0:
        try:
            return {**row, "status": "measured", "reason": "", "measure": json.loads(p.stdout)}
        except json.JSONDecodeError as e:
            return {**row, "status": "failed", "reason": f"measure.py の出力が JSON でない: {e}", "measure": None}
    why = (p.stderr.strip() or f"measure.py が終了コード {p.returncode}")[-REASON_TAIL:]
    return {**row, "status": "failed", "reason": why, "measure": None}

# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""段 A の実測（設計書 structure-block-design の 2 節・8 節）。入力の契約の単位のファイル（INPUTS_UNITS。JSON の配列で、各行は
{id, paths, summary}）を読み、単位ごとに paths を同じフォルダの measure.py に子のプロセスで渡し（コマンド 1 つの口。import しない）、
結果を run の置き場の structure/structure.json に書く。設計の行のファイル design.jsonl は 0 バイトで置き直す（JSON Lines は空行を
許さないので改行も書かない。行を書くのは構造の目の受け付け）。前の周の構造の目の控え eye.json は消す。

structure.json: {status: ok|failed, reason, root, policy_path, rules, units: [{id, summary, paths, status, reason, measure, concepts}],
timing: {started_at, finished_at, 秒（lib/eye の WALL）}}。単位の status は measured か failed（failed なら reason に measure.py の標準エラーの末尾）。
rules（方針の文書の中身と根の地図の文書）と単位の concepts（単位のパスに当たる考えの地図の行と知る場所の数）は lib/context が
対象の根から機械で探した物（構造の目に見せる。地図・柵の表の無い対象では空。作らない）。

- 対象の根（INPUTS_ROOT）は空なら cwd。相対なら cwd から解く。方針の文書（INPUTS_POLICY_PATH）は任意で、中身を rules に置く
- 単位のファイルが読めない・形が違う・measure.py が落ちた時も、structure.json の status: failed と reason に残して 0 で終える
  （実測が落ちても線を止めない。GitHub Actions の continue-on-error と同じ分け方で、節の結末は成功のまま）
- 直しの前の版（INPUTS_BASE_REV）が在る周は直しの後の段: 単位を読まず測らず、units の空の structure.json を AFTER_DIR の下に書いて
  after: true を返す（1 度目の段の design.jsonl と目の控えを消さない）
  （段 B の stage_b がその差分を測る。計画 2026-10-09-clean-whole の Task 2.5）
- {"structure_file", "design_file", "eye", "after"} を 1 行出して 0（eye は構造の目を起こす周か。lib/eye.due）。run の置き場の環境変数が欠けた（空も欠け）時だけ、標準エラーに名前を出して 2
"""
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように。必ず import より前

UNITS_ENV = "INPUTS_UNITS"
MEASURE = Path(__file__).resolve().parent / "measure.py"
REASON_TAIL = 2000


def read_units(path: str) -> list:
    """単位のファイルを読み、形を確かめて返す。読めない・形が違うなら ValueError"""
    if not path:
        raise ValueError(f"{UNITS_ENV} が空")
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

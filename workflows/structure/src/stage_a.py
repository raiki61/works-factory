"""段 A の実測の部品（docs/design/structure.md の 1.5。lib/stage_a.py の read_units・measure_unit と、lib/context.py の find・concepts・
_sections・_rel・HEADING の写し）。

- read_units(path): 単位のファイル（JSON の配列で、各行は {id, paths, summary}）を読み、形を確かめて返す。読めない・形が違うなら ValueError
- measure_unit(unit, root): 単位の paths を lib/measure.py にコマンドとして渡し（import しない）、
  {id, summary, paths, status, reason, measure} を返す。status は measured か failed（実測が落ちても例外にしない）
- find(root): 対象の柵の表と地図を探す（投げない）
- concepts(root, paths, found): 単位のパスに当たる考えの地図の行と、単位のファイルの知る場所の数
"""
from __future__ import annotations

import fnmatch
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

import conceptfence   # lib/
import concepthome    # lib/

from src.intent import TEXT_CAP   # 地図の 1 行の字の上限（目の指示を小さく保つ。切ったら印を付ける）

MEASURE = pathlib.Path(importlib.util.find_spec("measure").origin)   # lib/measure.py をコマンドとして起こす
REASON_TAIL = 2000
HEADING = re.compile(r"^### `([^`]+)`")


def _cut(text: str) -> str:
    return text if len(text) <= TEXT_CAP else text[:TEXT_CAP] + f"\n…（{len(text) - TEXT_CAP} 字を切った）"


def read_units(path) -> list:
    """単位のファイルを読み、形を確かめて返す。読めない・形が違うなら ValueError"""
    if not path:
        raise ValueError("単位のファイルのパスが空")
    try:
        rows = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
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


def measure_unit(unit: dict, root) -> dict:
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


def _sections(md: str) -> dict:
    """地図の {id: 見出しから次の見出し（### か ## か ---）の前までの文}"""
    out, cur, buf = {}, None, []
    for line in md.splitlines():
        m = HEADING.match(line)
        if m or line.startswith("## ") or line.strip() == "---":
            if cur is not None:
                out[cur] = "\n".join(buf).rstrip()
            cur, buf = (m.group(1), [line]) if m else (None, [])
            continue
        if cur is not None:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf).rstrip()
    return out


def find(root) -> dict:
    """{tables: [(持ち主のフォルダ, 表)], maps: [(持ち主のフォルダ, 地図のパス, {id: 行})], reason}"""
    root = pathlib.Path(root)
    tables, bad = conceptfence.tables(root)
    names, why = concepthome.tracked_names(root)
    maps = []
    for name in concepthome.pick_maps(names)[0]:
        try:
            maps.append((concepthome.base_of(name), name, _sections((root / name).read_text(encoding="utf-8"))))
        except (OSError, UnicodeDecodeError) as e:
            bad.append(f"{name}: {e}")
    if why and not any(b.startswith("木を読めなかった") for b in bad):
        bad.append(f"木を読めなかった: {why}")
    return {"tables": tables, "maps": maps, "reason": " / ".join(bad)}


def _rel(path: str, base: str):
    if not base:
        return path
    return path[len(base) + 1:] if path.startswith(base + "/") else None


def concepts(root, paths, found: dict) -> dict:
    rows, places = [], []
    hit = {}   # (持ち主のフォルダ, 考えの id) → 当たった訳
    for base, table in found.get("tables") or []:
        rel = [r for r in (_rel(p, base) for p in paths) if r is not None]
        for k, v in (table.get("concepts") or {}).items():
            for f in v.get("fences") or []:
                if any(fnmatch.fnmatch(r, g) for r in rel for g in f.get("allowed") or []):
                    hit.setdefault((base, k), True)
        try:
            got = conceptfence.places(root, base, table, paths)
        except Exception:   # noqa: BLE001 — 柵の語の形が壊れた表でも、地図の行と実測で判じる
            got = []
        places += got
        for g in got:
            hit.setdefault((base, g["concept"]), True)
    for base, name, sections in found.get("maps") or []:
        rel = [r for r in (_rel(p, base) for p in paths) if r is not None]
        for k, text in sections.items():
            if (base, k) in hit or any(r in text for r in rel):
                rows.append({"id": k, "map": name, "text": _cut(text)})
    return {"rows": rows, "places": places}

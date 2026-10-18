"""構造のブロック（workflows/structure/）の置き場の名（出力の欄が指すファイルの名は住処 structbeside）と、段 A の実測と構造の目の控えの書き手。
元の works では別のブロック blk-structure だった物（元の関数は名前のまま、docstring に元の <パス>:<行> を書く）。

置き場は run の置き場の DIR（structure/）。中身:
- UNITS_FILE（paths の在る単位の目録）・SKIPPED_FILE（paths の空な単位の id）・STRUCTURE_FILE（段 A の実測）
- 設計の行のファイル（DESIGN_FILE。段 A が 0 バイトで置き、構造の目の受け付けが行を書く）・目の控えと拒否の控え（eye）
- STATE_FILE（構造の目の控え。structmark の形。返す節の出力の欄 structure の指し札の先）
ほかのブロックとメイングラフは出力の欄 PORTS で受け、隣のファイルを名で開かない: 設計の行は控えの design_file、測らなかった単位は
控えの skipped から、structmark の読み口で読む（docs/design.md の「structure の出力」）。

- measure(out_dir, units, root, policy_path): 段 A の実測（元 works/blk-structure/scripts/stage_a.py の main）
- write_state(out_dir): 構造の目の控え（元 blk-structure/scripts/collect.py）
- keep_state(art): 置き場に控えを書く（write_state）。書けなければ SPARE_DIR に訳つきの failed の控えを置く
"""
from __future__ import annotations

import pathlib
import sys
import time
from datetime import datetime, timezone

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

import context  # noqa: E402
import eye  # noqa: E402
import jsonfile  # noqa: E402
import rolekit  # noqa: E402
import stage_a  # noqa: E402
import structbeside  # noqa: E402
import structmark  # noqa: E402

DIR = "structure"                       # run の置き場の中の、このブロックの置き場
# 出力の欄が指すファイルの名は住処 structbeside の物を引く
STATE_FILE = structbeside.STATE_FILE
DESIGN_FILE = structbeside.DESIGN_FILE
STRUCTURE_FILE = "structure.json"
UNITS_FILE = "units.json"
SKIPPED_FILE = "skipped-units.json"
SPARE_DIR = "structure-spare"           # 置き場に控えを書けない run の控えの置き場（run の置き場の直下）
UNWRITABLE_STATE = "構造の控えを書けない"
# 返す節の出力の欄 → 置き場の控え。ほかのブロックとメイングラフはこの欄で受け、名で開かない
PORTS = {"structure": STATE_FILE}


def _measured_units(units) -> tuple:
    """(測る単位の目録, paths が空で測らない単位の id)。目録が配列でなければそのまま返し、段 A の読みが形の誤りを言う"""
    if not isinstance(units, list):
        return units, []
    rows = [u for u in units if not (isinstance(u, dict) and isinstance(u.get("paths"), list) and not u["paths"])]
    return rows, [u.get("id") for u in units if isinstance(u, dict) and u not in rows]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def measure(out_dir, units, root, policy_path: str, unread=()) -> dict:
    """段 A の実測（元 works/blk-structure/scripts/stage_a.py の main）。paths の在る単位を UNITS_FILE に、paths の空な単位の id を
    SKIPPED_FILE に書き、単位ごとに stage_a.measure_unit で測って STRUCTURE_FILE を書き、設計の行のファイルを 0 バイトで置き直し、
    目の控えを消す。落ちても STRUCTURE_FILE の status: failed と reason に残す。unread（読めなかった入力の「<名>: <訳>」の行）は
    STRUCTURE_FILE の欄 unread に残す（方針の文書を黙って「無い」と読まない）。
    返り {structure_file, design_file, eye（構造の目を起こすか。eye.due）}"""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    structure, design = out_dir / STRUCTURE_FILE, out_dir / DESIGN_FILE
    rows, skipped = _measured_units(units)
    jsonfile.write(out_dir / UNITS_FILE, rows)
    jsonfile.write(out_dir / SKIPPED_FILE, skipped)
    t0, started = time.monotonic(), _now()
    design.write_bytes(b"")
    eye.reset(out_dir)
    root = pathlib.Path(root).resolve()
    doc = {"status": "ok", "reason": "", "root": str(root), "policy_path": policy_path, "units": []}
    try:
        got = stage_a.read_units(str(out_dir / UNITS_FILE))
    except ValueError as e:
        doc.update(status="failed", reason=str(e))
    else:
        found = context.find(root)
        doc["units"] = [{**stage_a.measure_unit(u, root), "concepts": context.concepts(root, u["paths"], found)} for u in got]
        if found["reason"]:
            doc["concepts_reason"] = found["reason"]
        failed = [u["id"] for u in doc["units"] if u["status"] == "failed"]
        if failed:
            doc.update(status="failed", reason=f"実測が落ちた単位: {', '.join(failed)}")
    doc["rules"] = context.rules(root, policy_path)
    if unread:
        doc["unread"] = list(unread)
    eye.stamp(doc, t0, started_at=started, finished_at=_now())
    jsonfile.write(structure, doc)
    return {"structure_file": str(structure), "design_file": str(design), "eye": eye.due(doc)}


def _outcome(doc: dict, kept: dict, rejects: list) -> tuple:
    """(status, reason)（元 works/blk-structure/scripts/collect.py の outcome。輪の出口の代わりに目の控えと拒否の控え rejects
    （rolekit.rejected）を読む）"""
    if doc.get("status") != "ok":
        return "failed", f"実測が落ちた: {doc.get('reason') or '理由の記録が無い'}"
    if not eye.due(doc):
        return "ok", ""
    if kept.get("status") == "ok":
        return "ok", ""
    if kept.get("status") == "gave_up":
        return "failed", f"構造の目の返答が {len(rejects) or '?'} 回とも受け付けで拒まれた: {rejects[-1] if rejects else ''}"
    return "failed", "構造の目の会話が落ちたか走らなかった（目の受け付けの控えが無いか途中のまま）"


def write_state(out_dir) -> pathlib.Path:
    """構造の目の控え STATE_FILE（structmark の形。skipped は SKIPPED_FILE の id）を書いて返す。STRUCTURE_FILE が読めなければ
    failed（実測が落ちたか走らなかった）。設計の行のファイルが無ければ 0 バイトで置く（控えの design_file はいつも在るファイルを指す）"""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    design = out_dir / DESIGN_FILE
    if not design.is_file():
        design.write_bytes(b"")
    doc = jsonfile.read_or(out_dir / STRUCTURE_FILE)
    kept = eye.state(out_dir)
    if isinstance(doc, dict):
        status, reason = _outcome(doc, kept, rolekit.rejected(out_dir, eye.NAME))
    else:
        status, reason = "failed", f"段 A の {STRUCTURE_FILE} が読めない"
    skipped = jsonfile.read_or(out_dir / SKIPPED_FILE, [])
    return structmark.write(out_dir / STATE_FILE, status=status, reason=reason, design_file=str(design), timed=(doc, kept),
                            skipped=skipped if isinstance(skipped, list) else [])


def keep_state(art) -> pathlib.Path:
    """run の置き場 art の DIR に構造の目の控えを書く（write_state）。書けなければ節を落とさず、SPARE_DIR に UNWRITABLE_STATE の訳で
    failed の控えを置いて返す（計画は構造の目の行なしで進む。元 works/darkfactory/lib/line_edge.py の structure_edge）"""
    art = pathlib.Path(art)
    try:
        return write_state(art / DIR)
    except OSError as e:
        spare = art / SPARE_DIR
        spare.mkdir(parents=True, exist_ok=True)
        design = spare / DESIGN_FILE
        design.write_bytes(b"")
        return structmark.write(spare / STATE_FILE, status="failed", reason=f"{UNWRITABLE_STATE}（{DIR}/{STATE_FILE}）: {e}",
                                design_file=str(design))

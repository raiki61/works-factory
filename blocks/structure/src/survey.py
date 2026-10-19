"""measure の node の中身（docs/design/structure.md の 3 節。lib/structfile.py の measure と lib/eye.py の view・due の写し）。

port を読み、place のこの block のファイルを消して（名を持つ物だけ）、段 A の実測を書き、構造の目に見せる JSON（view.json）を組む。
中の誤りは structure.json の status: failed と reason に残し、落ちない。
"""
from __future__ import annotations

import pathlib
import time
from datetime import datetime, timezone

import ports

import context     # lib/。方針の文書と根の地図の文書（rules）
import eye as libeye   # lib/。時間の欄（stamp）
import jsonfile    # lib/
import listcut     # lib/。目に見せる duplicates の件数

from src import files, stage_a


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def measured(doc: dict) -> list:
    return [u for u in doc.get("units") or [] if isinstance(u, dict) and u.get("status") == "measured"]


def due(doc: dict) -> bool:
    """構造の目を起こす周か: 実測が ok で、測れた単位が 1 つ以上"""
    return doc.get("status") == "ok" and bool(measured(doc))


def _cut(v):
    """duplicates の配列を先頭 listcut.SHOWN 件に切り、全件の数を隣の duplicates_total に置く（入れ子のどこでも）。
    大きい追跡ファイルを名指す単位で塊の一致が数百件になり、指示が実行基盤の標準出力の上限を越えて線が落ちた（run 131）"""
    if isinstance(v, list):
        return [_cut(x) for x in v]
    if not isinstance(v, dict):
        return v
    out = {k: _cut(x) for k, x in v.items()}
    dups = v.get("duplicates")
    if isinstance(dups, list) and len(dups) > listcut.SHOWN:
        out["duplicates"] = [_cut(x) for x in dups[:listcut.SHOWN]]
        out["duplicates_total"] = len(dups)
    return out


def view(doc: dict) -> dict:
    """目に見せる JSON。根拠の JSON Pointer はこれの中を指すので、受け付けも同じ物で引く。concepts と rules は段 A が置いた時だけ載る"""
    units = []
    for u in measured(doc):
        row = {"id": u["id"], "summary": u.get("summary", ""), "measure": _cut(u.get("measure"))}
        if u.get("concepts"):
            row["concepts"] = u["concepts"]
        units.append(row)
    out = {"units": units, "timing": doc.get("timing")}
    if doc.get("rules"):
        out["rules"] = doc["rules"]
    return out


def _measured_units(units) -> tuple:
    """(測る単位の目録, paths が空で測らない単位の id)。目録が配列でなければそのまま返し、段 A の読みが形の誤りを言う"""
    if not isinstance(units, list):
        return units, []
    rows = [u for u in units if not (isinstance(u, dict) and isinstance(u.get("paths"), list) and not u["paths"])]
    return rows, [u.get("id") for u in units if isinstance(u, dict) and u not in rows]


def _clear(out: pathlib.Path) -> None:
    """この block が名を持つファイルだけを消す（広い形で消さない）"""
    for name in files.OWN_FILES:
        (out / name).unlink(missing_ok=True)
    for pattern in files.OWN_PROMPTS:
        for path in out.glob(pattern):
            path.unlink()


def before(out, units, root, policy_path: str, unread=()) -> dict:
    """段 A の実測。paths の在る単位を units.json に、paths の空な単位の id を skipped-units.json に書き、単位ごとに測って
    structure.json と view.json を書き、設計の行のファイルを 0 バイトで置く。返り {eye, reason}"""
    out = pathlib.Path(out)
    structure = out / files.STRUCTURE_FILE
    rows, skipped = _measured_units(units)
    jsonfile.write(out / files.UNITS_FILE, rows)
    jsonfile.write(out / files.SKIPPED_FILE, skipped)
    t0, started = time.monotonic(), _now()
    (out / files.DESIGN_FILE).write_bytes(b"")
    root = pathlib.Path(root).resolve()
    doc = {"status": "ok", "reason": "", "root": str(root), "policy_path": policy_path, "units": []}
    try:
        got = stage_a.read_units(str(out / files.UNITS_FILE))
    except ValueError as e:
        doc.update(status="failed", reason=str(e))
    else:
        found = stage_a.find(root)
        doc["units"] = [{**stage_a.measure_unit(u, root), "concepts": stage_a.concepts(root, u["paths"], found)} for u in got]
        if found["reason"]:
            doc["concepts_reason"] = found["reason"]
        failed = [u["id"] for u in doc["units"] if u["status"] == "failed"]
        if failed:
            doc.update(status="failed", reason=f"実測が落ちた単位: {', '.join(failed)}")
    doc["rules"] = context.rules(root, policy_path)
    if unread:
        doc["unread"] = list(unread)
    libeye.stamp(doc, t0, started_at=started, finished_at=_now())
    jsonfile.write(structure, doc)
    eye = due(doc)
    if eye:
        jsonfile.write(out / files.VIEW_FILE, view(doc))
    reason = "" if eye else (f"実測が落ちた: {doc['reason']}" if doc["status"] != "ok" else "測れた単位が無い")
    return {"eye": eye, "reason": reason}


def run(place, *, units, policy) -> dict:
    """measure の node。port を読み、place のこの block のファイルを消して測る。返り {eye, reason}"""
    out = pathlib.Path(place)
    _clear(out)
    unread = []
    try:
        path = ports.file(policy)
        policy_path = str(path) if path else ""
    except ValueError as e:
        policy_path, unread = "", [f"policy: {e}"]
    try:
        rows = ports.json(units, "units.schema.json")
    except ValueError as e:
        rows = None
        unread.append(f"units: {e}")
    if rows is None:
        jsonfile.write(out / files.UNITS_FILE, [])
        jsonfile.write(out / files.SKIPPED_FILE, [])
        (out / files.DESIGN_FILE).write_bytes(b"")
        jsonfile.write(out / files.STRUCTURE_FILE, {"status": "failed", "reason": unread[-1], "units": [], "unread": unread})
        return {"eye": False, "reason": unread[-1]}
    return before(out, rows, pathlib.Path.cwd(), policy_path, unread)

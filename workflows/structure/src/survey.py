"""measure の node の中身（docs/design/structure.md の 3 節。lib/structfile.py の measure と lib/eye.py の view・due の写しを mode で 2 つに分けた物）。

port を読み、place のこの block のファイルを消して（名を持つ物だけ）、書いた意図を探し、before なら段 A の実測、after なら段 B の実測を書いて、
構造の目に見せる JSON（view.json）を組む。中の誤りは structure.json（before）か structure-after.json（after）の status: failed と reason に
残し、落ちない。
"""
from __future__ import annotations

import json
import pathlib
import time
from datetime import datetime, timezone

import ports

import eye as libeye   # lib/。時間の欄（stamp）
import jsonfile    # lib/
import listcut     # lib/。目に見せる duplicates の件数
import planmarks   # lib/。修正案の外れの訳
import structmark  # lib/。直した後の控え

from src import files, intent, stage_a, stage_b


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
    """目に見せる JSON（before）。根拠の JSON Pointer はこれの中を指すので、受け付けも同じ物で引く。concepts は段 A が置いた時だけ載る"""
    units = []
    for u in measured(doc):
        row = {"id": u["id"], "summary": u.get("summary", ""), "measure": _cut(u.get("measure"))}
        if u.get("concepts"):
            row["concepts"] = u["concepts"]
        units.append(row)
    return {"units": units, "timing": doc.get("timing")}


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


def _intent(out: pathlib.Path, root, rev: str, paths, given, policy) -> None:
    jsonfile.write(out / files.INTENT_FILE, intent.find(root, rev, paths, given, policy))


def before(out, units, root, given, policy) -> dict:
    """直す前の実測。paths の在る単位を units.json に、paths の空な単位の id を skipped-units.json に書き、書いた意図を HEAD の版から探して
    intent.json に書き、単位ごとに測って structure.json と view.json を書き、設計の行のファイルを 0 バイトで置く。返り {eye, reason}"""
    out = pathlib.Path(out)
    rows, skipped = _measured_units(units)
    jsonfile.write(out / files.UNITS_FILE, rows)
    jsonfile.write(out / files.SKIPPED_FILE, skipped)
    t0, started = time.monotonic(), _now()
    (out / files.DESIGN_FILE).write_bytes(b"")
    root = pathlib.Path(root).resolve()
    doc = {"status": "ok", "reason": "", "root": str(root), "units": []}
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
        try:
            head = intent._git(root, "rev-parse", "HEAD").strip()   # 見出しに出す版を commit に決める（字の HEAD のままにしない）
            _intent(out, root, head, [p for u in got for p in u["paths"]], given, policy)
        except RuntimeError as e:
            doc.update(status="failed", reason=f"書いた意図を探せない: {e}")
    libeye.stamp(doc, t0, started_at=started, finished_at=_now())
    jsonfile.write(out / files.STRUCTURE_FILE, doc)
    eye = due(doc)
    if eye:
        jsonfile.write(out / files.VIEW_FILE, view(doc))
    reason = "" if eye else (f"実測が落ちた: {doc['reason']}" if doc["status"] != "ok" else "測れた単位が無い")
    return {"eye": eye, "reason": reason}


def after_view(units: list, after: dict, deviations: list) -> dict:
    """目に見せる JSON（after）: {units: [{id, summary, paths}], after: {...}, timing}"""
    shown = {k: after.get(k) for k in ("base_rev", "changed", "tables", "tables_changed", "dup_blocks_added")}
    for name in ("fence_up", "new_names"):
        items = after.get(name) or []
        shown[name] = items[:listcut.SHOWN]   # 超える分は全件の数を隣の <名>_total に置く
        if len(items) > listcut.SHOWN:
            shown[f"{name}_total"] = len(items)
    shown["deviations"] = deviations
    return {"units": [{"id": u["id"], "summary": u.get("summary", ""), "paths": u["paths"]} for u in units], "after": shown,
            "timing": after.get("timing")}


def after(out, units, root, base: str, plan, given, policy) -> dict:
    """直した後の実測。base から今の作業ツリーまでの差分を段 B で測って structure-after.json に、差分の全体を after.diff に、書いた意図を
    base の版から探して intent.json に、目に見せる JSON を view.json に書く。返り {eye, reason}"""
    out = pathlib.Path(out)
    root = pathlib.Path(root).resolve()
    rows, skipped = _measured_units(units)
    jsonfile.write(out / files.SKIPPED_FILE, skipped)
    (out / files.DESIGN_FILE).write_bytes(b"")
    problems, devs, got, shown_units = [], [], {}, []
    t0 = time.monotonic()
    try:
        got = stage_b.run(root, base, skip_prefix=ports.RUNTIME_COPY_PREFIX)
        libeye.stamp(got, t0)
        if got["status"] != "ok":
            problems.append(got["reason"])
    except Exception as e:  # noqa: BLE001 — 測れない訳は理由に残して進む
        problems.append(f"直した後の実測が落ちた: {type(e).__name__}: {e}")
    try:
        if plan is not None:
            devs = planmarks.deviations((json.loads(plan.read_text(encoding="utf-8")) or {}).get("fields"))
    except Exception as e:  # noqa: BLE001
        problems.append(f"修正案の外れの訳が読めない: {type(e).__name__}: {e}")
    changed = got.get("changed") or []
    if not problems and changed:
        try:
            (out / files.DIFF_FILE).write_bytes(stage_b.patch_of(root, base, changed))
            owned = [u for u in rows if isinstance(u, dict) and u.get("paths")]
            shown_units = owned or [{"id": "diff", "summary": "", "paths": changed}]
            jsonfile.write(out / files.UNITS_FILE, shown_units)
            _intent(out, root, base, [p for u in shown_units for p in u["paths"]] + changed, given, policy)
        except (RuntimeError, OSError) as e:
            problems.append(f"差分か書いた意図を読めない: {e}")
    status, reason = ("failed", " / ".join(problems)) if problems else ("ok", "")
    structmark.write_after(out, status=status, reason=reason, after=got, deviations=devs)
    eye = status == "ok" and bool(changed)
    if eye:
        jsonfile.write(out / files.VIEW_FILE, after_view(shown_units, got, devs))
    return {"eye": eye, "reason": "" if eye else (f"直した後の実測が落ちた: {reason}" if reason else "差分が無い")}


def _port(name: str, read):
    try:
        return read()
    except ValueError as e:
        raise ValueError(f"入力 {name}: {e}") from None


def run(place, *, mode, units, intent_paths, policy, base, plan) -> dict:
    """measure の node。port を読み、place のこの block のファイルを消して測る。返り {eye, reason}。読めない入力は黙って空にせず、
    控え（before は structure.json、after は structure-after.json）に status: failed と理由を残して目を起こさない"""
    out = pathlib.Path(place)
    _clear(out)
    kind = "before"
    try:
        kind = _port("mode", lambda: ports.choice(mode or "before", files.MODES))
        given = _port("intent", lambda: ports.json(intent_paths or "[]", "shared:intent.schema.json"))
        policy_file = _port("policy", lambda: ports.file(policy, "file"))
        rows = _port("units", lambda: ports.json(units or "[]", "shared:units.schema.json"))
        plan_file = _port("plan", lambda: ports.file(plan, "json(shared:plan-fields.schema.json)")) if kind == "after" else None
    except ValueError as e:
        why = str(e)
        jsonfile.write(out / files.SKIPPED_FILE, [])
        (out / files.DESIGN_FILE).write_bytes(b"")
        if kind == "after":
            structmark.write_after(out, status="failed", reason=why, after={}, deviations=[])
        else:
            jsonfile.write(out / files.STRUCTURE_FILE, {"status": "failed", "reason": why, "units": []})
        return {"eye": False, "reason": why}
    if kind == "after":
        return after(out, rows, pathlib.Path.cwd(), ports.text(base).strip(), plan_file, given, policy_file)
    return before(out, rows, pathlib.Path.cwd(), given, policy_file)

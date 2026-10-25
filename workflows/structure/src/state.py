"""finish の node の中身: 構造の目の控え structure-state.json（docs/design/structure.md の 1.2・3 節。lib/structfile.py の _outcome・
write_state の写し）。控えの形と読み口は lib/structmark.py（KEEP）。
"""
from __future__ import annotations

import pathlib

import ports

import jsonfile   # lib/
import rolekit    # lib/
import structmark   # lib/

from src import eye, files, survey


def _outcome(doc: dict, kept: dict, rejects: list, after: bool = False) -> tuple:
    """(status, reason)。目の控えと拒否の控え rejects（rolekit.rejected）から決める。doc は before なら structure.json、after なら
    structure-after.json"""
    if doc.get("status") != "ok":
        return "failed", f"{'直した後の' if after else ''}実測が落ちた: {doc.get('reason') or '理由の記録が無い'}"
    if not (bool((doc.get("after") or {}).get("changed")) if after else survey.due(doc)):
        return "ok", ""
    if kept.get("status") == "ok":
        return "ok", ""
    if kept.get("status") == eye.UNREADABLE:
        return "failed", f"設計の行が読めない: {kept.get('reason') or '理由の記録が無い'}"
    if kept.get("status") == "gave_up":
        return "failed", f"構造の目の返答が {len(rejects) or '?'} 回とも受け付けで拒まれた: {rejects[-1] if rejects else ''}"
    return "failed", "構造の目の会話が落ちたか走らなかった（目の受け付けの控えが無いか途中のまま）"


def write_state(out, mode: str = "before") -> pathlib.Path:
    """構造の目の控え STATE_FILE（skipped は SKIPPED_FILE の id）を書いて返す。structure.json が読めなければ failed。設計の行のファイルが
    無ければ 0 バイトで置く（控えの design_file はいつも在るファイルを指す）。書けなければ OSError"""
    out = pathlib.Path(out)
    design = out / files.DESIGN_FILE
    if not design.is_file():
        design.write_bytes(b"")
    after = mode == "after"
    doc = structmark.read_after(out) if after else jsonfile.read_or(out / files.STRUCTURE_FILE)
    kept = eye.state(out)
    if isinstance(doc, dict):
        status, reason = _outcome(doc, kept, rolekit.rejected(out, files.NAME), after)
    else:
        status, reason = "failed", f"{'段 B の ' + files.AFTER_FILE if after else '段 A の ' + files.STRUCTURE_FILE} が読めない"
    skipped = jsonfile.read_or(out / files.SKIPPED_FILE, [])
    return structmark.write(out / files.STATE_FILE, status=status, reason=reason, design_file=str(design), timed=({} if after else doc, kept),
                            skipped=skipped if isinstance(skipped, list) else [])


UNWRITABLE_STATE = "構造の目の控えを書けない"


def returned(status: str, reason: str, structure, after, dirty: int, escalate: int, report: list) -> dict:
    return {"ok": status == "ok", "status": status, "reason": reason, "structure": structure, "after": after, "dirty": dirty,
            "escalate": escalate, "optional": files.OPTIONAL, "report": report}


def finish(out, mode: str = "before") -> dict:
    """block の返り {ok, status, reason, structure, after, dirty, escalate, optional, report}。控えを書けなければ structure: null と failed
    （place の外には書かない）"""
    out = pathlib.Path(out)
    try:
        path = write_state(out, mode)
    except OSError as e:
        reason = f"{UNWRITABLE_STATE}（{files.STATE_FILE}）: {' '.join(str(e).split())}"
        return returned("failed", reason, None, None, 0, 0, [reason])
    st = structmark.read(path) or {}
    try:
        rows = structmark.rows(st.get("design_file") or "")
    except ValueError:
        rows = []
    dirty = [r for r in rows if r.get("verdict") == structmark.DIRTY]
    up = [r for r in dirty if r.get("route") == structmark.ROUTE_UP]
    after = mode == "after" and structmark.read_after(out) is not None
    return returned(st.get("status") or "failed", st.get("reason") or "", ports.pointer(path, "json(shared:structure-state.schema.json)"),
                    ports.pointer(out / files.AFTER_FILE, "json(shared:structure-after.schema.json)") if after else None, len(dirty), len(up),
                    structmark.report_lines(path, out if mode == "after" else None))

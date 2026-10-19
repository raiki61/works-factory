"""返す node finish（docs/design/fix.md の 1.2 の出力・7 節の finish.py。今の collect.py の block・fields・group の後継）と、
今の lib/fixbeside.py のうち fix の物（閉鎖の表 CLOSURE_FILE・claimed_of・closure_rows と、受け付けの行の選び _accepted_tests）。

前の node の返りを with: で束ねず、各 node が place に書いたファイルを読んで出力の欄を組む。差分の審査とレンズの欄は無い
（delta-review と lens の block の出力）。中の誤りは script が捕まえて fallback で返す（落ちない）。
"""
from __future__ import annotations

import functools
import json
import os
import pathlib

import ports

from src import files

CLOSURE_FILE = files.CLOSURE_FILE
CHANGED_MARKS = ("mechanism_changed", "premise_drift", "gates_changed", "seams_changed", "security_surface_changed",
                 "path_changed")
DRIFT_NOTE = "premise_drift_note"
JOIN_MISSING = "join が結果を残さなかった（落ちたか走らなかった）"


# ---------------------------------------------------------------- 今の fixbeside の fix の物
def claimed_of(reply) -> list:
    """修正役が changes に載せた単位の key（申告。閉じたかは閉鎖の表が決める）"""
    return [str(c["unit_key"]) for c in (reply.get("changes") if isinstance(reply, dict) else None) or []
            if isinstance(c, dict) and isinstance(c.get("unit_key"), str)]


def closure_rows(place) -> list | None:
    """置き場の閉鎖の表（querytest.CLOSURE_FILE）の行。表が無ければ []、在るのに読めない・形が違えば None（書き手が訳にする）"""
    import querytest
    path = pathlib.Path(place) / querytest.CLOSURE_FILE
    if not path.is_file():
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    rows = doc.get("rows") if isinstance(doc, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else None


def write_closure(place, results, ruled_reply=None) -> None:
    """place に CLOSURE_FILE を書く（今の fixbeside.write の閉鎖の表の部分）。results は戻せた組の子の結果（欄 closure・claimed。
    closure が None の子は表を読めなかった）、ruled_reply は裁定の後の修正役の返答。組めなければ {"error": 訳}"""
    import oneline
    from src import board
    place = pathlib.Path(place)
    results = [r for r in results or [] if isinstance(r, dict)]
    try:
        own = closure_rows(place)
        broken = [str(res.get("group_id")) for res in results if "closure" in res and res["closure"] is None]
        if own is None or broken:
            raise ValueError("閉鎖の表を読めない（" + "・".join([*(f"組 {g}" for g in broken), *(["この置き場"] if own is None else [])])
                             + "）")
        rows = {}
        for r in [*(x for res in results for x in res.get("closure") or []), *own]:
            if isinstance(r, dict):
                rows[r.get("unit_key")] = r   # 裁定の後の段の表がその単位の 1 回目の表を上書きする
        claimed = [*(k for res in results for k in res.get("claimed") or []), *claimed_of(ruled_reply)]
        doc = {"rows": list(rows.values()), "claimed": list(dict.fromkeys(claimed))}
    except Exception as e:   # 隣のファイルは材料。組めない訳を置き、出力の node は落とさない
        doc = {"error": f"{type(e).__name__}: {oneline.one_line(e)}"}
    board.write_json(place / CLOSURE_FILE, doc)


def _accepted_tests(trace: list) -> list:
    """1 つの修正の段の受け付けの選んだ試験の行（TESTS_OP）のうち、組と受け付けの段（pass）ごとの最後の回の物"""
    import impact
    TESTS_OP = impact.ACCEPT_TRACE_OP   # noqa: N806  今の fixbeside.TESTS_OP
    last: dict = {}
    for row in trace:
        if row.get("op") == TESTS_OP:
            key = (row.get("group_id"), row.get("pass"))
            if key not in last or (row.get("attempt") or 0) >= (last[key].get("attempt") or 0):
                last[key] = row
    return list(last.values())


# ---------------------------------------------------------------- 出力の組み立て
def _ptr(path) -> dict | None:
    path = pathlib.Path(path)
    return ports.pointer(path) if path.is_file() else None


def _diff(place, repo) -> dict:
    """累積差分（修正前の版から。未追跡を含み .archon/ の下は除く）の pointer。空なら理由のファイルの pointer"""
    from src import board
    path, _, _ = board.diff_file(repo, lambda: board.base_rev_of(place), place, files.DIFF_FILE, files.DIFF_NONE_FILE,
                                 (ports.RUNTIME_COPY_PREFIX,))
    return ports.pointer(path)


def _frozen(place) -> pathlib.Path | None:
    """輪ごとの凍ったテストのファイルの hash {loops: [{state, frozen, frozen_tree}]}（輪が無ければ書かない）"""
    from src import board, tdd
    loops = []
    for state in tdd.states(place):
        doc = board.read_json(state, {}) or {}
        loops.append({"state": str(state), "frozen": doc.get("frozen") or {}, "frozen_tree": doc.get("frozen_tree") or ""})
    if not loops:
        return None
    return board.write_json(pathlib.Path(place) / files.FROZEN_FILE, {"loops": loops})


def _scope(place) -> pathlib.Path | None:
    """{plan_items, ruled_paths, agreed}（lib の fixboard.scope_brief。修正案の無い run は書かない）"""
    from src import board
    place = pathlib.Path(place)
    if not (place / files.PLAN_REPLY_FILE).is_file():
        return None
    return board.write_json(place / files.SCOPE_FILE, board.scope_brief(place, functools.partial(board.place_items, place)))


def _tdd_refused(place) -> dict:
    """TDD の輪の状態の calls から修正役が拒まれた単位と、在るのに読めない状態の訳（今の fixbeside.tdd_refused）"""
    from src import tdd
    refused, unread = [], []
    for state in tdd.states(place):
        try:
            doc = json.loads(state.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            unread.append(f"修正の控え {state} が読めない（{type(e).__name__}）")
            continue
        if not isinstance(doc, dict) or "error" in doc:
            unread.append(f"修正の控え {state} の形が違う")
            continue
        refused += tdd.refused_units(doc.get("calls"))
    return {"refused": refused, "unread": unread}


def _removed(place):
    import leftovers
    try:
        return [ports.pointer(p) for p in leftovers.found(place)]
    except leftovers.Unreadable:
        return None


def _item_claims(place, results, ruled, repo) -> dict:
    """項目ごとの commit の記録（itemcommits.record。今の collect.item_claims）"""
    import itemcommits
    from src import board
    unread, replies = [], [ruled]
    try:
        items = board.place_items(place)
    except ValueError as e:
        items, unread = None, [f"承認済みの修正案の項目を読めない（{' '.join(str(e).split())}）"]
    for r in results:
        named = r.get("reply_file")
        try:
            reply = board.read_json(named) if named else None
        except ValueError:
            reply = None
        if named and reply is None:
            unread.append(f"組 {r.get('group_id')} の修正役の返答 {named} を読めない")
        replies.append(reply)
    tdd = [{"unit_key": u.get("unit_key"), "test_files": board.unit_test_files(u)} for r in results for u in board.child_tdd_units(r)]
    return itemcommits.record(items, replies, tdd, repo, unread)


def _common(place, repo, rows_groups, groups, extras, results, *, ok, reason, final, stop="", declared=(), claims=None,
            tdd_rows=(), checked=None, carry=None, reply=None, ruled_reply=None, start_tree="") -> dict:
    import conflict
    from src import board, report
    place = pathlib.Path(place)
    rows = conflict.items(place)
    groups_rows, units_rows = rows_groups
    board.write_json(place / files.ALLOWED_TESTS_FILE, board.allowed_test_rows(place, extras))
    board.write_json(place / files.ACCEPT_TRACE_FILE, board.accept_trace_rows(place, results))
    tdd_rows = list(tdd_rows)
    unit_file = board.write_json(place / files.TDD_UNIT_FILE, tdd_rows)
    objection = [board.objection(extras), *conflict.rejudge_texts(conflict.this_pass(place))]
    frozen = _frozen(place)
    return {"ok": ok, "reason": reason, "units": units_rows, "groups": groups_rows,
            "conflicts": _ptr(place / conflict.FILE) if rows else None,
            "carry": carry,
            "replan_items": board.replan_items(conflict.this_pass(place), groups),
            "objection": "\n".join(dict.fromkeys(x for x in objection if x)), "diff": _diff(place, repo),
            "start_tree": start_tree, "reply": reply, "ruled_reply": ruled_reply, "scope": _ptr(_scope(place) or place / files.SCOPE_FILE),
            "checked": checked or {"ok": True, "reason": ""},
            "allowed_test_changes": board.allowed_tests(place, extras),
            "changed": board.changed_marks(extras), "x_scalars": board.x_scalars(extras),
            "handoffs": final[0], "mismatched": final[1], "plan_declared": list(declared), "stop_reason": stop,
            "item_claims": claims,
            "allowed_tests": _ptr(place / files.ALLOWED_TESTS_FILE), "accept_trace": _ptr(place / files.ACCEPT_TRACE_FILE),
            "closure": _ptr(place / CLOSURE_FILE), "tdd_unit": ports.pointer(unit_file), "tdd": tdd_rows,
            "frozen": ports.pointer(frozen) if frozen else None, "removed": _removed(place), "tdd_refused": _tdd_refused(place),
            "freeze_off": report.freeze_off(tdd_rows), "report": report.lines(place, tdd_rows, units_rows, repo)}


def whole(place, repo) -> dict:
    """全体の形の出力（今の collect.block から差分の審査の欄を外した物）"""
    import conflict
    import stopby
    from src import board, carry
    place = pathlib.Path(place)
    if conflict.second_pass(place):
        import replan
        replan.close(place, replan.CLOSE_WHY)
    plan = board.read_json(place / board.GROUPS_FILE)
    if not isinstance(plan, dict) or not isinstance(plan.get("groups"), list):
        raise ValueError(f"置き場に groups.json が無い（prep が走らなかった。{place}）")
    joined = board.read_json(place / board.JOIN_FILE)
    if isinstance(joined, dict):
        rows_groups = (joined["groups"], joined["units"])
    else:
        rows_groups = board.join_rows(plan["groups"], {g["group_id"]: (None, False, JOIN_MISSING) for g in plan["groups"]})
    rows_groups = (rows_groups[0], board.with_ruled(rows_groups[1], board.read_json(place / board.FIX_UNITS_FILE)))
    back = [g["group_id"] for g in rows_groups[0] if g["returned"]]
    results = [board.read_json(pathlib.Path(plan["out_dir"]) / gid / board.RESULT_FILE) for gid in back]
    results = [r for r in results if isinstance(r, dict)]
    ruled = board.read_json(place / board.RULED_REPLY_FILE)
    extras = results + ([ruled] if ruled is not None else [])
    checked = board.read_json(place / board.ASSERT_FILE) or {}
    checked = {"ok": checked.get("ok") is True, "reason": str(checked.get("reason") or ("" if checked else "assert-changed が走らなかった"))}
    stop = stopby.UNRESTORED if board.held(place) else ""
    ok = isinstance(joined, dict) and checked["ok"] and not stop
    reason = "" if ok else (JOIN_MISSING if not isinstance(joined, dict) else stop or checked["reason"])
    reply = board.group_fix_reply(place)
    write_closure(place, results, ruled)
    final = (board.final_lines(results, "handoffs", board.handoff_lines([ruled])),
             board.final_lines(results, "mismatched", board.mismatched_lines(place)))
    tdd_rows = board.tdd_units(plan["groups"], {g["group_id"]: board.usable_result(pathlib.Path(plan["out_dir"]) / g["group_id"])
                                                for g in plan["groups"]})
    carried = carry.write(place)
    return _common(place, repo, rows_groups, plan["groups"], extras, results, ok=ok, reason=reason, final=final, stop=stop,
                   declared=board.declared_lines(place), claims=_item_claims(place, results, ruled, repo), tdd_rows=tdd_rows,
                   checked=checked, carry=ports.pointer(carried) if carried else None,
                   reply=ports.pointer(reply) if reply else None, ruled_reply=_ptr(place / board.RULED_REPLY_FILE),
                   start_tree=board.start_tree(place))


def group(place, repo, doc: dict) -> dict:
    """組の形の出力: 自分の組の結果の行だけ（今の collect.group）"""
    from src import board
    place = pathlib.Path(place)
    g = doc["group"]
    gid = g["group_id"]
    gdir = board.group_dir(place, doc.get("out_dir") or "", gid)
    result = board.usable_result(gdir)
    rows_groups = board.join_rows([g], {gid: (result, result is not None, "" if result else board.NO_RESULT)})
    extras = [result] if result else []
    write_closure(place, extras)
    final = (board.final_lines(extras, "handoffs"), board.final_lines(extras, "mismatched"))
    tdd_rows = board.tdd_units([g], {gid: result})
    reply = place / board.FIX_REPLY_FILE
    return _common(place, repo, rows_groups, [g], extras, [], ok=result is not None,
                   reason="" if result is not None else board.NO_RESULT, final=final, tdd_rows=tdd_rows,
                   reply=_ptr(reply), start_tree=board.start_tree(place))


def collect(place, repo) -> dict:
    from src import intake
    doc = intake.load(place)
    if doc.get("mode") == "whole":
        return whole(place, repo)
    return group(place, repo, doc)


def fallback(place, why: str) -> dict:
    """誤りの時の約束の形の返り（ok: false と理由。ほかは空の値。当たったままの組は stopby.UNRESTORED で返す）。lib が読めない時も
    標準ライブラリだけで返す"""
    groups_rows, units_rows, stop = [], [], ""
    place = pathlib.Path(place)
    try:
        import stopby
        from src import board
        stuck = board.unrestored_of(place)
        stop = stopby.UNRESTORED if stuck else ""
        plan = board.read_json(place / board.GROUPS_FILE)
        gs = plan["groups"] if isinstance(plan, dict) and isinstance(plan.get("groups"), list) else []
        if not gs:
            got = json.loads((place / files.INTAKE).read_text(encoding="utf-8")).get("group")
            gs = [got] if isinstance(got, dict) else []
        for g in gs:
            groups_rows.append({"group_id": str(g["group_id"]), "unit_ids": [str(k) for k in g["unit_ids"]],
                                "returned": False, "reason": why,
                                **({"unrestored": stuck[str(g["group_id"])]} if str(g["group_id"]) in stuck else {})})
            units_rows += [{"unit_id": str(k), "group_id": str(g["group_id"]), "status": "not_done", "reason": why}
                           for k in g["unit_ids"]]
    except Exception:
        groups_rows, units_rows = [], []
    if not groups_rows:
        groups_rows = [{"group_id": "", "unit_ids": [], "returned": False, "reason": why}]
    try:
        place.mkdir(parents=True, exist_ok=True)
        (place / files.COLLECT_ERROR).write_text(why + "\n", encoding="utf-8")
        (place / files.ALLOWED_TESTS_FILE).write_text("[]\n", encoding="utf-8")
        if not (place / files.ACCEPT_TRACE_FILE).exists():
            (place / files.ACCEPT_TRACE_FILE).write_text("[]\n", encoding="utf-8")
        diff = ports.pointer(place / files.COLLECT_ERROR)
    except Exception:
        diff = {"type": ports.POINTER_TYPE, "run_id": os.environ.get("WORKFLOW_ID", ""), "path": files.COLLECT_ERROR}

    def ptr(name):
        try:
            return ports.pointer(place / name) if (place / name).is_file() else None
        except Exception:
            return None
    return {"ok": False, "reason": why, "units": units_rows, "groups": groups_rows, "conflicts": None, "carry": None,
            "replan_items": [], "objection": "", "diff": diff, "start_tree": "", "reply": None, "ruled_reply": None, "scope": None,
            "checked": {"ok": False, "reason": why}, "allowed_test_changes": [],
            "changed": {**{k: False for k in CHANGED_MARKS}, DRIFT_NOTE: ""}, "x_scalars": {},
            "handoffs": [], "mismatched": [], "plan_declared": [], "stop_reason": stop, "item_claims": None,
            "allowed_tests": ptr(files.ALLOWED_TESTS_FILE), "accept_trace": ptr(files.ACCEPT_TRACE_FILE), "closure": None,
            "tdd_unit": None, "tdd": [], "frozen": None, "removed": None, "tdd_refused": {"refused": [], "unread": [why]},
            "freeze_off": [], "report": [f"修正の出力を組めない: {why}"]}


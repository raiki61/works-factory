# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返す節 fix（script collect。両方の形）: 前の節の返りを with: で束ねず、各節が置き場に書いたファイルを読んで返りの約束の欄を組む。

形 ""（ブロック）: 組と単位の結末は join.json、申し出と裁定は conflicts.json（指し札。無ければ null。2 回目の修正の段は 1 回目の段の
行を写して持つ）、replan_items はこの段の裁定 fix_plan_item の項目（conflict.this_pass）、objection・changed（6 つの印と前提のずれの
申告の文 premise_drift_note）・x_scalars（修正役が足した規模の数値。組ごとの値を名ごとに足す）・allowed_test_changes は戻せた組の
子の結果（result.json）と裁定の後の修正役の返答（fix-ruled-reply.json）と裁定の許し（objection には、この段の裁定 rejudge の文も
足す。conflict.rejudge_texts。組どうしの合わせの申し出を判定のやり直しへ回す異議）、delta_review は delta/review-<n>.json（{pass}）の数と最後の pass（delta/skipped.json が
在れば {rounds: 0, pass: true}）。done は assert-changed.json の ok かつ（審査を省いた か 審査が通った）かつ戻せず当たったままの組
（join.json の欄 unrestored）が無い。そういう組が在れば stop_reason は stopby.UNRESTORED（人待ちの語。作業ツリーが信用できないので
線は先へ進めない）、ほかは ""（形 group も）。
2 回目の修正の段（conflict.second_pass）は、段を抜ける前に案の直しを待つ行（この段で新しく fix_plan_item と裁いた行）を諦めた行にする
（replan.close と CLOSE_WHY。案の段に戻るのは 1 run に 1 回。元 works/darkfactory/lib/line_edge.py:1159 の replan.settle）。
形 group（組の子）: 自分の組の結果（out_dir/<group_id>/result.json。out_dir が空なら自分の置き場の groups/ の下）の行だけを同じ形で返す。
レンズの集め役の事実は diff の隣の lenses.json（{collector: {ok, reason}}。集め役が書かずに落ちた・走らなかった時は ok: false）。
累積差分（修正前の版 fixboard.base_rev_of から。未追跡を含み .archon/ の下は除く）は置き場の fix.diff に書いて指し札にする（空なら理由のファイルを指す）。
diff の隣（置き場）に許したテストの変更の訳 allowed-tests.json = [{path, permit, source}]（fixboard.allowed_test_rows）と、
受け付けの行 accept-trace.json（戻せた組の子の結果の行と親の置き場の行。fixboard.accept_trace_rows）と、閉鎖の数え直しと差分の審査の
穴の名札と手直しの結果（lib/fixbeside.py の closure.json・delta-holes.json。戻せた組の子の結果が運んだ分と、裁定の後の修正の段の分を
合わせる）を置く。
最後の関所を開ける理由の 2 欄（元 works/darkfactory/lib/line_edge.py:800 _final_needs）: handoffs は修正役が人に回した物
（子の結果の handoffs と裁定の後の返答の changes[].breaks.accepted。fixboard.handoff_lines）、mismatched は直したという申告と
機械の数え直しが合わない単位（子の結果の mismatched と親の置き場の閉鎖の表。fixboard.mismatched_lines）。形 group は自分の結果の行だけ。
plan_declared は修正役が直さずに残すと答えた事前審査の block の行（fixboard.declared_lines。独立の目へ申し送る）。形 group は [] で、
組の子の答えは親の置き場の fix-reply.json に集まってから数える。
この節は落ちない: 中の誤りは全部捕まえ、done: false・理由（units と groups の reason）・ほかは空の値で返し、終了の値は 0
（diff は理由のファイル fix-collect-error.txt を指し、その隣の allowed-tests.json は空の []、accept-trace.json は無ければ []。
closure.json・delta-holes.json は置かず、読み手が「無い」と名指す）。
返りの全部（fallback も）に欄 optional を載せる: 入力（with:）optional の、このブロックが落ちても線が先へ進めてよい節の宣言
（[{node, bare}] の JSON の字）を境の口 boundary.items で読んだ並び。境の口を読めない時だけ []。
"""
import functools
import json
import os
import sys
from pathlib import Path

NO_REVIEW = {"rounds": 0, "pass": False}
CHANGED_MARKS = ("mechanism_changed", "premise_drift", "gates_changed", "seams_changed", "security_surface_changed",
                 "path_changed")
DRIFT_NOTE = "premise_drift_note"   # fixboard.DRIFT_NOTE の写し（lib を読めない時の返りの形）
ERROR_FILE = "fix-collect-error.txt"
LENSES_FILE = "lenses.json"   # fixboard.LENSES_FILE と同じ名（lib が読めない道でも書く）
NO_COLLECTOR = "レンズの集め役が終わらなかった: 集め役の出口が無い（集め役が落ちたか走らなかった）"   # fixboard.LENS_NOT_DONE の形
GROUP_LENSES = "組の子の run はレンズを起こさない（差分の審査は親の run が回す）"
ALLOWED_TESTS = "allowed-tests.json"   # fixboard.ALLOWED_TESTS_FILE と同じ名（lib を読めない時も diff の隣に [] を置く）
ACCEPT_TRACE = "accept-trace.json"     # fixboard.ACCEPT_TRACE_FILE と同じ名（lib を読めない時も diff の隣に無ければ [] を置く）
boundary = fixbeside = None   # 境の口と隣の約束のファイルの口。読めない時は fallback が stdlib だけで返す


def rel(place: Path, name: str) -> str:
    return (place / name).relative_to(Path(os.environ["ARTIFACTS_DIR"])).as_posix()


def diff_pointer(fixboard, place: Path) -> dict:
    """累積差分のファイルの指し札。書けない・空なら理由を書いたファイルの指し札"""
    path, _, _ = fixboard.diff_file(boundary.work_tree(), lambda: fixboard.base_rev_of(place), place, "fix.diff",
                                 "fix-diff-none.txt", boundary.SKIP)
    return boundary.pointer(rel(place, path.name))


def fields(fixboard, conflict, place: Path, rows_groups, groups, extras, review, done, final, results, stop="", declared=()) -> dict:
    """返りの欄（組と単位の行は rows_groups = (組の行, 単位の行)。groups は組の分け、extras は子の結果と修正役の返答、final は
    最後の関所を開ける理由の行 (handoffs, mismatched)、results は受け付けの行を親の置き場に集める組の子の結果、stop は止めの語、
    declared は修正役が直さずに残すと答えた事前審査の block の行）"""
    rows = conflict.items(place)
    groups_rows, units_rows = rows_groups
    fixboard.write_json(place / fixboard.ALLOWED_TESTS_FILE, fixboard.allowed_test_rows(place, extras))
    fixboard.write_json(place / fixboard.ACCEPT_TRACE_FILE, fixboard.accept_trace_rows(place, results))
    objection = [fixboard.objection(extras), *conflict.rejudge_texts(conflict.this_pass(place))]
    return {"done": done, "units": units_rows, "groups": groups_rows,
            "conflicts": boundary.pointer(rel(place, conflict.FILE)) if rows else None,
            "replan_items": fixboard.replan_items(conflict.this_pass(place), groups),
            "objection": "\n".join(dict.fromkeys(x for x in objection if x)), "diff": diff_pointer(fixboard, place),
            "allowed_test_changes": fixboard.allowed_tests(place, extras),
            "changed": fixboard.changed_marks(extras), "x_scalars": fixboard.x_scalars(extras), "delta_review": review,
            "handoffs": final[0], "mismatched": final[1], "plan_declared": list(declared), "stop_reason": stop}


def block(fixboard, conflict) -> dict:
    import stopby
    place = boundary.place("fix")
    if conflict.second_pass(place):
        import replan
        replan.close(place, replan.CLOSE_WHY)
    plan = fixboard.read_json(place / fixboard.GROUPS_FILE)
    if not isinstance(plan, dict) or not isinstance(plan.get("groups"), list):
        raise ValueError(f"置き場に groups.json が無い（prep が走らなかった。{place}）")
    joined = fixboard.read_json(place / fixboard.JOIN_FILE)
    if isinstance(joined, dict):
        rows_groups = (joined["groups"], joined["units"])
    else:
        rows_groups = fixboard.join_rows(plan["groups"], {g["group_id"]: (None, False, "join が結果を残さなかった（落ちたか走らなかった）")
                                                          for g in plan["groups"]})
    rows_groups = (rows_groups[0], fixboard.with_ruled(rows_groups[1], fixboard.read_json(place / fixboard.FIX_UNITS_FILE)))
    back = [g["group_id"] for g in rows_groups[0] if g["returned"]]
    results = [fixboard.read_json(Path(plan["out_dir"]) / gid / fixboard.RESULT_FILE) for gid in back]
    results = [r for r in results if isinstance(r, dict)]
    ruled = fixboard.read_json(place / fixboard.RULED_REPLY_FILE)
    extras = results + ([ruled] if ruled is not None else [])
    review, _ = fixboard.delta_review(place)
    checked = fixboard.read_json(place / fixboard.ASSERT_FILE) or {}
    stop = stopby.UNRESTORED if fixboard.held(place) else ""
    done = isinstance(joined, dict) and checked.get("ok") is True and review["pass"] and not stop
    reply = place / fixboard.FIX_REPLY_FILE
    fixbeside.write(place, results, ruled,
                    items=functools.partial(fixboard.place_items, place), plan_review=fixboard.plan_review_file(place),
                    fix_reply=reply if reply.is_file() else None)
    final = (fixboard.final_lines(results, "handoffs", fixboard.handoff_lines([ruled])),
             fixboard.final_lines(results, "mismatched", fixboard.mismatched_lines(place)))
    return fields(fixboard, conflict, place, rows_groups, plan["groups"], extras, review, done, final, results, stop,
                  fixboard.declared_lines(place))


def group(fixboard, conflict) -> dict:
    place = boundary.place("fix")
    g = boundary.parsed(os.environ["INPUTS_GROUP"])
    gid = g["group_id"]
    gdir = fixboard.group_dir(place, os.environ.get("INPUTS_OUT_DIR", ""), gid)
    result = fixboard.usable_result(gdir)
    rows_groups = fixboard.join_rows([g], {gid: (result, result is not None, "" if result else fixboard.NO_RESULT)})
    extras = [result] if result else []
    fixbeside.write(place, extras)
    final = (fixboard.final_lines(extras, "handoffs"), fixboard.final_lines(extras, "mismatched"))
    return fields(fixboard, conflict, place, rows_groups, [g], extras, dict(NO_REVIEW), result is not None, final, [])


def place_rel() -> str:
    """置き場の成果物の置き場からの相対パス（boundary.place("fix") と同じ fix/<include の名>。境の口を読めない時は fix/fix）"""
    try:
        name = boundary.include_name("fix")
    except Exception:
        name = "fix"
    return f"fix/{name}"


def error_pointer(why: str) -> dict:
    """理由を置き場の fix-collect-error.txt に書いた指し札（stdlib だけ。境の口を読めない時も置く）"""
    rel_path = f"{place_rel()}/{ERROR_FILE}"
    try:
        target = Path(os.environ["ARTIFACTS_DIR"]) / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(why + "\n", encoding="utf-8")
        (target.parent / ALLOWED_TESTS).write_text("[]\n", encoding="utf-8")
        if not (target.parent / ACCEPT_TRACE).exists():
            (target.parent / ACCEPT_TRACE).write_text("[]\n", encoding="utf-8")
    except Exception:
        pass
    return {"type": "archon_artifact", "run_id": os.environ.get("WORKFLOW_ID", ""), "path": rel_path}


def lenses_file() -> None:
    """diff の隣の lenses.json（レンズの集め役の事実 {collector: {ok, reason}}。fixboard.LENSES_FILE と同じ名）を必ず置く: 集め役
    （lens-collect）か delta-cut が書いた行が読めればそのまま、無い・形が違えば ok: false と理由（集め役が何も書けずに落ちたか
    走らなかった）、組の子は ok: true（レンズを起こさない）。stdlib だけ（lib と境の口が読めない道でも書く）。書けなければ標準
    エラーに名指す（落ちない）"""
    path = Path(os.environ.get("ARTIFACTS_DIR", ".")) / place_rel() / LENSES_FILE
    if os.environ.get("INPUTS_MODE", "") == "group":
        doc = {"collector": {"ok": True, "reason": GROUP_LENSES}}
    else:
        try:
            got = json.loads(path.read_text(encoding="utf-8"))["collector"]
            if isinstance(got.get("ok"), bool) and isinstance(got.get("reason"), str):
                return
        except Exception:
            pass
        doc = {"collector": {"ok": False, "reason": NO_COLLECTOR}}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as e:
        print(f"collect: {LENSES_FILE} を書けない（{path}: {type(e).__name__}: {' '.join(str(e).split())}）", file=sys.stderr)


def fallback(why: str) -> dict:
    """誤りの時の約束の形の返り（done: false と理由。ほかは空の値。join.json の当たったままの組は、行に当たったままのパスを
    残して止めの語 stopby.UNRESTORED で返す）"""
    groups_rows, units_rows, stop = [], [], ""
    try:
        import fixboard
        import stopby
        stuck = fixboard.unrestored_of(boundary.place("fix"))
        stop = stopby.UNRESTORED if stuck else ""
        plan = fixboard.read_json(boundary.place("fix") / fixboard.GROUPS_FILE)
        gs = plan["groups"] if isinstance(plan, dict) and isinstance(plan.get("groups"), list) else []
        if not gs and (g := boundary.parsed(os.environ.get("INPUTS_GROUP"))) is not None:
            gs = [g]
        for g in gs:
            groups_rows.append({"group_id": str(g["group_id"]), "unit_ids": [str(k) for k in g["unit_ids"]],
                                "returned": False, "reason": why,
                                **({"unrestored": stuck[str(g["group_id"])]} if str(g["group_id"]) in stuck else {})})
            units_rows += [{"unit_id": str(k), "group_id": str(g["group_id"]), "status": fixboard.NOT_DONE, "reason": why}
                           for k in g["unit_ids"]]
    except Exception:
        groups_rows, units_rows = [], []
    if not groups_rows:
        groups_rows = [{"group_id": "", "unit_ids": [], "returned": False, "reason": why}]
    return {"done": False, "units": units_rows, "groups": groups_rows, "conflicts": None, "replan_items": [],
            "objection": "", "diff": error_pointer(why), "allowed_test_changes": [],
            "changed": {**{k: False for k in CHANGED_MARKS}, DRIFT_NOTE: ""}, "x_scalars": {}, "delta_review": dict(NO_REVIEW),
            "handoffs": [], "mismatched": [], "plan_declared": [], "stop_reason": stop}


def main() -> dict:
    global boundary, fixbeside
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    sys.path.append(str(boundary.lib_root()))

    import conflict
    import fixbeside
    import fixboard
    mode = os.environ.get("INPUTS_MODE", "")
    if mode not in fixboard.MODES:
        raise ValueError(f"入力 mode は空か group: {mode!r}")
    return group(fixboard, conflict) if mode == "group" else block(fixboard, conflict)


if __name__ == "__main__":
    try:
        out = main()
    except BaseException as e:   # 返す節は落ちない（線が先へ進めなくなる）。境の口と lib を読む所の誤りも捕まえる
        why = f"fix の出力を組めない（{type(e).__name__}: {' '.join(str(e).split())[:500]}）"
        print(f"collect: {why}", file=sys.stderr)
        out = fallback(why)
    lenses_file()
    noted = boundary.items(os.environ.get("INPUTS_OPTIONAL")) if boundary is not None else []
    try:
        print(json.dumps({**out, "optional": noted}, ensure_ascii=False, allow_nan=False), flush=True)
    except ValueError as e:
        print(json.dumps({**fallback(f"fix の出力を書けない（{type(e).__name__}: {e}）"), "optional": noted},
                         ensure_ascii=False, allow_nan=False), flush=True)
    sys.exit(0)

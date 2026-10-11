# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返す節 fix（script collect。両方の形）: 前の節の返りを with: で束ねず、各節が置き場に書いたファイルを読んで返りの約束の欄を組む。

形 ""（ブロック）: 組と単位の結末は join.json、申し出と裁定は conflicts.json（指し札。無ければ null）、replan_items は裁定
fix_plan_item の項目、objection・changed・allowed_test_changes は戻せた組の子の結果（result.json）と裁定の後の修正役の返答
（fix-ruled-reply.json）と裁定の許し、delta_review は delta/review-<n>.json（{pass}）の数と最後の pass（delta/skipped.json が
在れば {rounds: 0, pass: true}）。done は assert-changed.json の ok かつ（審査を省いた か 審査が通った）。
形 group（組の子）: 自分の組の結果（out_dir/<group_id>/result.json。out_dir が空なら自分の置き場の groups/ の下）の行だけを同じ形で返す。
累積差分（版 HEAD から。未追跡を含み .archon/ の下は除く）は置き場の fix.diff に書いて指し札にする（空なら理由のファイルを指す）。
この節は落ちない: 中の誤りは全部捕まえ、done: false・理由（units と groups の reason）・ほかは空の値で返し、終了の値は 0。
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import fixio  # noqa: E402

NO_REVIEW = {"rounds": 0, "pass": False}


def rel(place: Path, name: str) -> str:
    return (place / name).relative_to(Path(os.environ["ARTIFACTS_DIR"])).as_posix()


def diff_pointer(fixboard, place: Path, why: str = "") -> dict:
    """累積差分のファイルの指し札。書けない・空なら理由を書いたファイルの指し札"""
    if not why:
        try:
            text = fixboard.run_diff(fixio.repo(), "HEAD", fixio.SKIP)
        except Exception as e:
            text, why = "", f"累積差分が取れない（{type(e).__name__}: {' '.join(str(e).split())}）"
        if text.strip():
            (place / "fix.diff").write_text(text, encoding="utf-8", errors="surrogateescape")
            return boundary.pointer(rel(place, "fix.diff"))
        why = why or "累積差分は空（run の始めの版から作業ツリーは変わっていない）"
    (place / "fix-diff-none.txt").write_text(why + "\n", encoding="utf-8")
    return boundary.pointer(rel(place, "fix-diff-none.txt"))


def fields(fixboard, conflict, place: Path, rows_groups, groups, extras, review, done) -> dict:
    """返りの欄（組と単位の行は rows_groups = (組の行, 単位の行)。groups は組の分け、extras は子の結果と修正役の返答）"""
    rows = conflict.items(place)
    groups_rows, units_rows = rows_groups
    return {"done": done, "units": units_rows, "groups": groups_rows,
            "conflicts": boundary.pointer(rel(place, conflict.FILE)) if rows else None,
            "replan_items": fixboard.replan_items(rows, groups),
            "objection": fixboard.objection(extras), "diff": diff_pointer(fixboard, place),
            "allowed_test_changes": fixboard.allowed_tests(place, extras),
            "changed": fixboard.changed_marks(extras), "delta_review": review}


def block(fixboard, conflict) -> dict:
    place = fixio.place()
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
    extras = [r for r in results if isinstance(r, dict)] + [fixboard.read_json(place / fixboard.RULED_REPLY_FILE)]
    review, _ = fixboard.delta_review(place)
    checked = fixboard.read_json(place / fixboard.ASSERT_FILE) or {}
    done = isinstance(joined, dict) and checked.get("ok") is True and review["pass"]
    return fields(fixboard, conflict, place, rows_groups, plan["groups"], [r for r in extras if r is not None], review, done)


def group(fixboard, conflict) -> dict:
    place = fixio.place()
    g = json.loads(os.environ["INPUTS_GROUP"])
    gid = g["group_id"]
    gdir = fixboard.group_dir(place, os.environ.get("INPUTS_OUT_DIR", ""), gid)
    result = fixboard.read_json(gdir / fixboard.RESULT_FILE)
    if not isinstance(result, dict):
        result = None
    rows_groups = fixboard.join_rows([g], {gid: (result, result is not None, "" if result else fixboard.NO_RESULT)})
    extras = [result] if result else []
    return fields(fixboard, conflict, place, rows_groups, [g], extras, dict(NO_REVIEW), result is not None)


def fallback(why: str) -> dict:
    """誤りの時の約束の形の返り（done: false と理由。ほかは空の値）"""
    groups_rows, units_rows = [], []
    try:
        import fixboard
        place = fixio.place()
        plan = fixboard.read_json(place / fixboard.GROUPS_FILE)
        gs = plan["groups"] if isinstance(plan, dict) and isinstance(plan.get("groups"), list) else []
        if not gs and os.environ.get("INPUTS_GROUP", "").strip():
            gs = [json.loads(os.environ["INPUTS_GROUP"])]
        for g in gs:
            groups_rows.append({"group_id": str(g["group_id"]), "unit_ids": [str(k) for k in g["unit_ids"]],
                                "returned": False, "reason": why})
            units_rows += [{"unit_id": str(k), "group_id": str(g["group_id"]), "status": "not_done", "reason": why}
                           for k in g["unit_ids"]]
    except Exception:
        groups_rows, units_rows = [], []
    if not groups_rows:
        groups_rows = [{"group_id": "", "unit_ids": [], "returned": False, "reason": why}]
    try:
        place = fixio.place()
        (place / "fix-collect-error.txt").write_text(why + "\n", encoding="utf-8")
        diff = boundary.pointer(rel(place, "fix-collect-error.txt"))
    except Exception:
        diff = {"type": boundary.POINTER_TYPE, "run_id": os.environ.get("WORKFLOW_ID", ""),
                "path": "fix/fix/fix-collect-error.txt"}
    return {"done": False, "units": units_rows, "groups": groups_rows, "conflicts": None, "replan_items": [],
            "objection": "", "diff": diff, "allowed_test_changes": [],
            "changed": {k: False for k in ("mechanism_changed", "premise_drift", "gates_changed", "seams_changed",
                                           "security_surface_changed", "path_changed")},
            "delta_review": dict(NO_REVIEW)}


def main() -> dict:
    import conflict
    import fixboard
    mode = os.environ.get("INPUTS_MODE", "")
    if mode not in fixio.MODES:
        raise ValueError(f"入力 mode は空か group: {mode!r}")
    return group(fixboard, conflict) if mode == "group" else block(fixboard, conflict)


if __name__ == "__main__":
    try:
        out = main()
    except BaseException as e:   # 返す節は落ちない（線が先へ進めなくなる）
        why = f"fix の返りを組めない（{type(e).__name__}: {' '.join(str(e).split())[:500]}）"
        print(f"collect: {why}", file=sys.stderr)
        out = fallback(why)
    try:
        boundary.returns(out)
    except Exception as e:
        boundary.returns(fallback(f"fix の返りを書けない（{type(e).__name__}: {e}）"))
    sys.exit(0)

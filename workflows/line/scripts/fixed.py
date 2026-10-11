"""1 回目の修正（fix）と 2 度目の修正（refix）の返りを合わせて後の段へ渡す返しの節 fixed（埋め P2）。

done・diff・changed・delta_review は refix が走ればその物（diff はどちらも run の始めからの累積）。units は unit_id ごとに後の物、
groups・allowed_test_changes は和。申し出 conflicts は走った方の指し札を全部並べた配列にし、1 回目の申し出と許したテストの変更が
最後の関所と報告から消えないようにする。replan_items・objection は 1 回目の物（差し込みを決めたのは 1 回目）。

入力（with:）: fix_<欄>（fix の返り）・refix_<欄>（refix の返り。`{from, if_skipped: null}`）
"""
import json
import os

import linekit

FIELDS = ("done", "units", "groups", "conflicts", "replan_items", "objection", "diff", "allowed_test_changes", "changed",
          "delta_review")


def union(*lists) -> list:
    seen, out = set(), []
    for row in (x for rows in lists for x in rows or []):
        key = json.dumps(row, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


def fixed(fix: dict, refix: dict | None) -> dict:
    last = refix if refix is not None else fix
    units = {}
    for unit in [*(fix.get("units") or []), *((refix or {}).get("units") or [])]:
        if isinstance(unit, dict):
            units[unit.get("unit_id")] = unit
    return {
        "done": last.get("done") is True,
        "units": list(units.values()),
        "groups": union(fix.get("groups"), (refix or {}).get("groups")),
        "conflicts": [c for c in (fix.get("conflicts"), (refix or {}).get("conflicts")) if c],
        "replan_items": fix.get("replan_items") or [],
        "objection": fix.get("objection") or "",
        "diff": last.get("diff"),
        "allowed_test_changes": union(fix.get("allowed_test_changes"), (refix or {}).get("allowed_test_changes")),
        "changed": last.get("changed"),
        "delta_review": last.get("delta_review"),
        "refixed": refix is not None,
    }


def from_env() -> tuple:
    fix = {
        "done": linekit.value(os.environ.get("INPUTS_FIX_DONE")),
        "units": linekit.value(os.environ.get("INPUTS_FIX_UNITS")),
        "groups": linekit.value(os.environ.get("INPUTS_FIX_GROUPS")),
        "conflicts": linekit.value(os.environ.get("INPUTS_FIX_CONFLICTS")),
        "replan_items": linekit.value(os.environ.get("INPUTS_FIX_REPLAN_ITEMS")),
        "objection": linekit.text(os.environ.get("INPUTS_FIX_OBJECTION")),
        "diff": linekit.value(os.environ.get("INPUTS_FIX_DIFF")),
        "allowed_test_changes": linekit.value(os.environ.get("INPUTS_FIX_ALLOWED_TEST_CHANGES")),
        "changed": linekit.value(os.environ.get("INPUTS_FIX_CHANGED")),
        "delta_review": linekit.value(os.environ.get("INPUTS_FIX_DELTA_REVIEW")),
    }
    refix = {
        "done": linekit.value(os.environ.get("INPUTS_REFIX_DONE")),
        "units": linekit.value(os.environ.get("INPUTS_REFIX_UNITS")),
        "groups": linekit.value(os.environ.get("INPUTS_REFIX_GROUPS")),
        "conflicts": linekit.value(os.environ.get("INPUTS_REFIX_CONFLICTS")),
        "replan_items": linekit.value(os.environ.get("INPUTS_REFIX_REPLAN_ITEMS")),
        "objection": linekit.text(os.environ.get("INPUTS_REFIX_OBJECTION")),
        "diff": linekit.value(os.environ.get("INPUTS_REFIX_DIFF")),
        "allowed_test_changes": linekit.value(os.environ.get("INPUTS_REFIX_ALLOWED_TEST_CHANGES")),
        "changed": linekit.value(os.environ.get("INPUTS_REFIX_CHANGED")),
        "delta_review": linekit.value(os.environ.get("INPUTS_REFIX_DELTA_REVIEW")),
    }
    return fix, (None if refix["done"] is None else refix)


def fallback(reason: str) -> dict:
    return {**{key: None for key in FIELDS}, "done": False, "units": [], "groups": [], "conflicts": [], "replan_items": [],
            "objection": "", "allowed_test_changes": [], "refixed": False}


if __name__ == "__main__":
    linekit.run(lambda: fixed(*from_env()), fallback)

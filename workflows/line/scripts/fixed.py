"""1 回目の修正（fix）と 2 度目の修正（refix）の返りを合わせて後の段へ渡す返しの節 fixed（埋め P2）。

done・diff・changed・delta_review は refix が走ればその物（diff はどちらも run の始めからの累積）。units は unit_id ごとに後の物、
groups・allowed_test_changes は和。申し出 conflicts は走った方の指し札を全部並べた配列にし、1 回目の申し出と許したテストの変更が
最後の関所と報告から消えないようにする。replan_items・objection は 1 回目の物（差し込みを決めたのは 1 回目）。
done は、案の直しが要ったのに 2 度目の修正が走らなかった時（案の直しの関所の stop・無人の止め・案ができなかった・refix の中が
落ちた）と、前の線の script（after-fix・judged）が止めた時は偽。1 回目の修正の差分を試験の関門から先へ進めない。

入力（with:）: fix_<欄>（fix の返り）・refix_<欄>（refix の返り。`{from, if_skipped: null}`）・replan（after-fix の返り）・
stop_after_fix・stop_judged（after-fix・judged の止めの理由）
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


def fixed(fix: dict, refix: dict | None, *, replan: bool, stops: tuple) -> dict:
    last = refix if refix is not None else fix
    held = (replan and refix is None) or any(stops)
    units = {}
    for unit in [*(fix.get("units") or []), *((refix or {}).get("units") or [])]:
        if isinstance(unit, dict):
            units[unit.get("unit_id")] = unit
    return {
        "done": last.get("done") is True and not held,
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
        "stop_reason": "",
    }


def of_env(prefix: str) -> dict:
    return {key: linekit.field(key, os.environ.get(f"INPUTS_{prefix}_{key.upper()}")) for key in FIELDS}


def from_env() -> dict:
    refix = of_env("REFIX")
    return {"fix": of_env("FIX"), "refix": None if refix["done"] is None else refix,
            "replan": linekit.flag(os.environ.get("INPUTS_REPLAN")),
            "stops": (linekit.text(os.environ.get("INPUTS_STOP_AFTER_FIX")), linekit.text(os.environ.get("INPUTS_STOP_JUDGED")))}


def fallback(reason: str) -> dict:
    return {**{key: None for key in FIELDS}, "done": False, "units": [], "groups": [], "conflicts": [], "replan_items": [],
            "objection": "", "allowed_test_changes": [], "refixed": False, "stop_reason": linekit.LINE_SCRIPT}


if __name__ == "__main__":
    linekit.run(lambda: fixed(**from_env()), fallback)

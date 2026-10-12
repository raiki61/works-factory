# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""1 回目の修正（fix）と 2 度目の修正（refix-run）の返りを合わせて後の段へ渡す節 fixed。

done・diff・changed・delta_review は refix-run が走ればその物（diff はどちらも run の始めからの累積）。units は unit_id ごとに後の物、
groups・allowed_test_changes は和、x_scalars（修正役が足した規模の数値）は名ごとに 2 度目の値を優先して合わせる。申し出 conflicts は
指し札の配列: refix-run が返した控えは 1 回目の段の行を写して持つ（fix の入力 prior_conflicts。元は 1 つの盤面）ので、在ればそれ 1 つ、
無ければ 1 回目の物（1 回目の申し出が最後の関所と報告から消えず、同じ行を 2 度数えない）。diffs は段ごとの diff の指し札の並び
（1 回目・2 度目の順。どちらの隣にも段の約束のファイル lib/fixbeside.py が在り、最後の関所と報告が両方を読む）。replan_items は 1 回目の物（差し込みを
決めたのは 1 回目）。objection は 1 回目と 2 度目の修正役の異議をつないだ文で、rejudge は異議が在り held でない時に真（再審は 2 度目の
修正の後に 1 度だけ両方の異議を受ける。元 works/darkfactory/darkfactory.yaml:827 の h-rejudge は refit の後）。
done は、案の直しが要ったのに 2 度目の修正が走らなかった時（案の直しの関所の stop・無人の止め・案ができなかった・refix-run の中が
落ちた）と、前の線の script（after-fix）が止めた時は偽（held）。再審の止め（judged）は試験の関門の when が読む。go は試験の関門（final）へ進めるか: held でなく、done か、
差分の審査が回って通らなかった（delta_review の rounds が 1 以上で pass が偽。審査は変更の確かめが通った run でだけ回る）時。
今の works の最後のテスト p4.ci は手直しの段が済むのを待つだけで、審査が通ったかを待たない（done が偽の残りは報告が数える）。
held の時は 1 回目の修正の差分を試験の関門から先へ進めない。
plan・ripple は独立の目が照らす修正案と波及: 2 度目の修正が走った run は案の直し（replan）の物、ほかは計画の往復の物
（元 works/darkfactory/lib/line_edge.py 1058-1064 行。案の直しの後は承認済みの案を差し替えた）。

入力（with:）: fix_<欄>（fix の返り）・refix_<欄>（refix-run の返り。`{from, if_skipped: null}`）・replan（after-fix の返り）・
stop_after_fix（after-fix の止めの理由）・plan・ripple（計画の往復の返り）・replanned（案の直しの返りの受け皿
replan-out の got。`{from, if_skipped: null}`。案の直しの返す節が落ちても fixed が落ちないように、replan を直に読まない）
"""
import json
import os

import linekit

FIELDS = ("done", "units", "groups", "conflicts", "replan_items", "objection", "diff", "allowed_test_changes", "changed",
          "x_scalars", "delta_review")
PLANS = ("plan", "ripple")


def union(*lists) -> list:
    seen, out = set(), []
    for row in (x for rows in lists for x in rows or []):
        key = json.dumps(row, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


def review_failed(returned: dict) -> bool:
    review = returned.get("delta_review")
    return isinstance(review, dict) and (review.get("rounds") or 0) >= 1 and review.get("pass") is False


def fixed(fix: dict, refix: dict | None, *, replan: bool, stops: tuple, plans: dict | None = None) -> dict:
    last = refix if refix is not None else fix
    plans = plans or {}
    again = plans.get("replanned") if refix is not None and isinstance(plans.get("replanned"), dict) else None
    held = (replan and refix is None) or any(stops)
    done = last.get("done") is True and not held
    units = {}
    for unit in [*(fix.get("units") or []), *((refix or {}).get("units") or [])]:
        if isinstance(unit, dict):
            units[unit.get("unit_id")] = unit
    said = [str(r.get("objection") or "").strip() for r in (fix, refix or {})]
    objection = "\n".join(dict.fromkeys(o for o in said if o))
    scalars = {**(fix.get("x_scalars") if isinstance(fix.get("x_scalars"), dict) else {}),
               **((refix or {}).get("x_scalars") if isinstance((refix or {}).get("x_scalars"), dict) else {})}
    return {
        "done": done,
        "go": done or (not held and review_failed(last)),
        "units": list(units.values()),
        "groups": union(fix.get("groups"), (refix or {}).get("groups")),
        "conflicts": [c for c in ((refix or {}).get("conflicts") or fix.get("conflicts"),) if c],
        "replan_items": fix.get("replan_items") or [],
        "objection": objection,
        "rejudge": bool(objection) and not held,
        "diff": last.get("diff"),
        "diffs": [d for d in (fix.get("diff"), (refix or {}).get("diff")) if d],
        "allowed_test_changes": union(fix.get("allowed_test_changes"), (refix or {}).get("allowed_test_changes")),
        "changed": last.get("changed"),
        "x_scalars": scalars,
        "delta_review": last.get("delta_review"),
        "refixed": refix is not None,
        **{key: (again or plans).get(key) for key in PLANS},
        "stop_reason": "",
    }


def of_env(prefix: str) -> dict:
    return {key: linekit.field(key, os.environ.get(f"INPUTS_{prefix}_{key.upper()}")) for key in FIELDS}


def from_env() -> dict:
    refix = of_env("REFIX")
    return {"fix": of_env("FIX"), "refix": None if refix["done"] is None else refix,
            "replan": linekit.flag(os.environ.get("INPUTS_REPLAN")),
            "plans": {key: linekit.value(os.environ.get(f"INPUTS_{key.upper()}")) for key in (*PLANS, "replanned")},
            "stops": (linekit.text(os.environ.get("INPUTS_STOP_AFTER_FIX")),)}


def fallback(reason: str) -> dict:
    return {**{key: None for key in FIELDS}, "done": False, "go": False, "units": [], "groups": [], "conflicts": [], "diffs": [], "replan_items": [],
            "objection": "", "rejudge": False, "allowed_test_changes": [], "x_scalars": {}, "refixed": False, "plan": None, "ripple": None,
            "stop_reason": linekit.LINE_SCRIPT}


if __name__ == "__main__":
    linekit.run(lambda: fixed(**from_env()), fallback)

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""1 回目の修正（fix）と 2 度目の修正（refix-run）の返りを合わせて後の段へ渡す節 fixed。

done・diff・changed・delta_review は refix-run が走ればその物（diff はどちらも run の始めからの累積）。units は unit_id ごとに後の物、
groups・allowed_test_changes と、最後の承認ノードを開ける理由の行 handoffs（修正役が人に回した物）・mismatched（申告と
数え直しが合わない単位）は和、x_scalars（修正役が足した規模の数値）は名ごとに 2 度目の値を優先して合わせる。申し出 conflicts は
指し札の配列: refix-run が返した控えは 1 回目の段の行を写して持つ（fix の入力 prior_conflicts。元は 1 つの盤面）ので、在ればそれ 1 つ、
無ければ 1 回目の物（1 回目の申し出が最後の関所と報告から消えず、同じ行を 2 度数えない）。diffs は段ごとの diff の指し札の並び
（1 回目・2 度目の順。どちらの隣にも段の約束のファイル lib/fixbeside.py と許したテストの変更の訳 allowed-tests.json が在り、
最後の承認ノードと報告が両方を読む）。replan_items は 1 回目の物（差し込みを
決めたのは 1 回目）。objection は 1 回目と 2 度目の修正役の異議をつないだ文で、rejudge は異議が在り held でない時に真（再審は 2 度目の
修正の後に 1 度だけ両方の異議を受ける。元 works/darkfactory/darkfactory.yaml:827 の h-rejudge は refit の後）。
done は、案の直しが要ったのに 2 度目の修正が走らなかった時（案の直しの関所の stop・無人の止め・案ができなかった・refix-run の中が
落ちた）と、前の線の script（after-fix）が止めた時と、fix か refix-run が止めの語を返した時（戻せず当たったままの組。
stopby.UNRESTORED）は偽（held）。stop_reason は fix か refix-run が返した止めの語（報告の結末が読む。after-fix の止めは collect が別に受ける）。再審の止め（judged）は試験の関門の when が読む。go は試験の関門（final）へ進めるか: held でなく、done か、
差分の審査が回って通らなかった（delta_review の rounds が 1 以上で pass が偽。審査は変更の確かめが通った run でだけ回る）時。
今の works の最後のテスト p4.ci は手直しの段が済むのを待つだけで、審査が通ったかを待たない（done が偽の残りは報告が数える）。
held の時は 1 回目の修正の差分を試験の関門から先へ進めない。
plan・ripple は独立の目が照らす修正案と波及: 2 度目の修正が走った run は案の直し（replan）の物、ほかは計画の往復の物
（元 works/darkfactory/lib/line_edge.py 1058-1064 行。案の直しの後は承認済みの案を差し替えた）。

design・plan_questions・answer は独立の目へ渡す計画の往復の設計と修正前の関所の問いと答え（そのまま渡す）。直す物が無い周（fix が
走らず design-only が走った。fix の欄が null）は no_fix の形（no_fix）を返す（L-W07）。review_skipped は計画の往復が事前審査を run の
頭の深さで飛ばしたか（fix-in が運ぶ計画の往復の depth_skip。固定材料の run は写した run の値。真の時だけ真）で、独立の目が R1〜R4 を
省かない印。

入力（with:）: fix_<欄>（fix の返り。止めの語 stop_reason も）・refix_<欄>（refix-run の返り）・replan（after-fix の返り）・stop_after_fix（after-fix の止めの理由）・
plan・ripple・design・plan_questions（計画の往復の返り）・answer（修正前の関所の答え）・no_fix_design（design-only の design）・replanned
（案の直しの返りの受け皿 replan-out の got。案の直しの返す節が落ちても fixed が落ちないように、replan を直に読まない）・
review_skipped（fix-in の depth_skip）。直す物が
無い周に飛ぶ節を結ぶので、どれも `{from, if_skipped: null}`
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

FIELDS = ("done", "units", "groups", "conflicts", "replan_items", "objection", "diff", "allowed_test_changes", "changed",
          "x_scalars", "delta_review", "handoffs", "mismatched", "stop_reason")
PLANS = ("plan", "ripple")
PASSED = ("design", "plan_questions", "answer")   # 独立の目へ渡す計画の往復の設計・修正前の関所の問いと答え（飛ばされた周は null）


def no_fix(plans: dict) -> dict:
    """直す物が無い周（fix が走らず、独立設計だけを作る差し込み design-only が走った。元 works/darkfactory/lib/line_edge.py:1107-1119
    の plan_edge）の形: 直す物も差分も申し出も無く、最後のテストと独立の目へ進める（go）。独立の目の設計は design-only の物、
    修正前の関所は開いていない（問い []・答え null）。差分が無いので封じず当てない（線の merge-seal・merge-apply の when が no_fix を読む）"""
    return {"done": True, "go": True, "units": [], "groups": [], "conflicts": [], "replan_items": [], "objection": "", "diff": None,
            "diffs": [], "allowed_test_changes": [], "handoffs": [], "mismatched": [], "changed": {}, "x_scalars": {}, "delta_review": None, "refixed": False,
            "rejudge": False, "plan": None, "ripple": None, "design": plans.get("no_fix_design"), "plan_questions": [],
            "answer": None, "no_fix": True, "stop_reason": ""}


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


def fixed(fix: dict, refix: dict | None, *, replan: bool, stops: tuple, plans: dict | None = None,
          review_skipped: bool = False) -> dict:
    plans = plans or {}
    if fix.get("done") is None and refix is None:
        return {**no_fix(plans), "review_skipped": review_skipped}
    last = refix if refix is not None else fix
    again = plans.get("replanned") if refix is not None and isinstance(plans.get("replanned"), dict) else None
    own = next((s for s in (fix.get("stop_reason"), (refix or {}).get("stop_reason")) if isinstance(s, str) and s), "")
    held = (replan and refix is None) or any(stops) or bool(own)
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
        "handoffs": union(fix.get("handoffs"), (refix or {}).get("handoffs")),
        "mismatched": union(fix.get("mismatched"), (refix or {}).get("mismatched")),
        "changed": last.get("changed"),
        "x_scalars": scalars,
        "delta_review": last.get("delta_review"),
        "refixed": refix is not None,
        **{key: (again or plans).get(key) for key in PLANS},
        "design": plans.get("design"),
        "plan_questions": plans.get("plan_questions") or [],
        "answer": plans.get("answer"),
        "no_fix": False,
        "review_skipped": review_skipped,
        "stop_reason": own,
    }


def of_env(prefix: str) -> dict:
    return {key: boundary.field(key, os.environ.get(f"INPUTS_{prefix}_{key.upper()}")) for key in FIELDS}


def from_env() -> dict:
    refix = of_env("REFIX")
    return {"fix": of_env("FIX"), "refix": None if refix["done"] is None else refix,
            "replan": boundary.flag(os.environ.get("INPUTS_REPLAN")),
            "plans": {key: boundary.value(os.environ.get(f"INPUTS_{key.upper()}"))
                      for key in (*PLANS, "replanned", *PASSED, "no_fix_design")},
            "stops": (boundary.text(os.environ.get("INPUTS_STOP_AFTER_FIX")),),
            "review_skipped": boundary.flag(os.environ.get("INPUTS_REVIEW_SKIPPED"))}


def fallback(reason: str) -> dict:
    return {**{key: None for key in FIELDS}, "done": False, "go": False, "units": [], "groups": [], "conflicts": [], "diffs": [], "replan_items": [],
            "handoffs": [], "mismatched": [],
            "objection": "", "rejudge": False, "allowed_test_changes": [], "x_scalars": {}, "refixed": False, "plan": None, "ripple": None,
            "design": None, "plan_questions": [], "answer": None, "no_fix": False, "review_skipped": False,
            "stop_reason": boundary.LINE_SCRIPT}


if __name__ == "__main__":
    boundary.run(lambda: fixed(**from_env()), fallback)

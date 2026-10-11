"""案の直しの関所を開くかと、見せる文を決める節 ask-replan（docs/design.md の「線」の「順と関所」の 7）。

直した項目ごとに、承認済みの項目（計画の往復の plan）と直した項目（replan の plan）の約束の欄を比べる（lib/planmarks.py の
contract_diff）。約束の欄が変わった項目と、事前審査（replan-review）が人に聞くと言った時は聞く。無人の run では、範囲を広げるだけの
直し（planmarks.widened）は聞かずに通し、通したことを返す（widened。報告に届く）。読めない計画は聞く側に倒す。
無人の run で聞くはずの時は開かずに止める（needs-human）。

入力（with:）: old_plan・new_plan（指し札）・items（直す計画の項目の id。1 から数える番号）・ask_human・questions・unattended
"""
import json
import os

import linekit
from linekit import boundary

import answer
import gatemarks
import planmarks

HEAD = "案の直しの関所"
RECORD = "run の置き場の gates/gate-replan.json"


def plan_items(ptr) -> list | None:
    """修正案の指し札の先（plan-fields.json の {fields: [...]}）の項目の欄。読めなければ None"""
    try:
        doc = json.loads(boundary.resolve(ptr).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None
    fields = doc.get("fields") if isinstance(doc, dict) else None
    return fields if isinstance(fields, list) else None


def item(fields, ident: str):
    if fields is None or not str(ident).isdigit() or not 1 <= int(ident) <= len(fields):
        return None
    got = fields[int(ident) - 1]
    return got if isinstance(got, dict) else None


def ask(old_ptr, new_ptr, ids: list, *, ask_human: bool, questions: list, unattended: bool, run_id: str) -> dict:
    old_fields, new_fields = plan_items(old_ptr), plan_items(new_ptr)
    rows, widened = [], []
    for ident in ids:
        old, new = item(old_fields, ident), item(new_fields, ident)
        if old is None or new is None:
            rows.append(f"項目 {ident}: 承認済みの項目か直した項目を読めない（聞く側に倒す）")
            continue
        changed = planmarks.contract_diff(old, new)
        wide = planmarks.widened(old, new) if unattended and changed and not ask_human else None
        if wide:
            widened.append(f"項目 {ident}: 範囲を広げるだけの直しを聞かずに通した（{json.dumps(wide, ensure_ascii=False)}）")
        elif changed:
            rows.append(f"項目 {ident}: 約束の欄が変わった（{'・'.join(changed)}）")
    if ask_human:
        rows += [f"事前審査の問い: {q}" for q in questions] or ["事前審査が人に聞くと言った"]
    if not rows:
        return {"open": False, "go": True, "stop_reason": "", "text": "", "widened": widened}
    if unattended:
        return {"open": False, "go": False, "stop_reason": linekit.NEEDS_HUMAN, "text": "", "widened": widened}
    lines = gatemarks.head3(f"{HEAD}が開いた。修正の段が誤りとした計画の項目を直した案に、人が決める物が {len(rows)} 件ある",
                            "直した案で 2 度目の修正へ進めるか、止めるか（打つ行は末尾の答え方）", gatemarks.push_of(rows))
    lines += ["", f"項目（{len(rows)} 件）:", *[f"- {row}" for row in rows], *[f"- {w}" for w in widened], "",
              "答え方:",
              f"- 修正に戻る: {answer.line(run_id, 'continue', '<一言>')}（一言は {RECORD} に残り、報告に届く。2 度目の修正には修正前の関所の答えが届く）",
              f"- 止める: {answer.line(run_id, 'stop', '<理由>')}（報告は出る）"]
    return {"open": True, "go": True, "stop_reason": "", "text": "\n".join(lines) + "\n", "widened": widened}


def fallback(reason: str) -> dict:
    return {"open": False, "go": False, "stop_reason": linekit.LINE_SCRIPT, "text": "", "widened": []}


if __name__ == "__main__":
    linekit.run(lambda: ask(linekit.value(os.environ.get("INPUTS_OLD_PLAN")), linekit.value(os.environ.get("INPUTS_NEW_PLAN")),
                            [str(x) for x in linekit.items(os.environ.get("INPUTS_ITEMS"))],
                            ask_human=linekit.flag(os.environ.get("INPUTS_ASK_HUMAN")),
                            questions=linekit.items(os.environ.get("INPUTS_QUESTIONS")),
                            unattended=linekit.flag(os.environ.get("INPUTS_UNATTENDED")), run_id=os.environ["WORKFLOW_ID"]),
                fallback)

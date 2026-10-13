# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""案の直しの関所を開くかと、見せる文を決める節 ask-replan（docs/design.md の「メイングラフ」の「順と承認ノード」の 7）。

直した項目ごとに、承認済みの項目（計画の往復の plan）と直した項目（replan の plan）の約束の欄を比べる（lib/planmarks.py の
contract_diff）。約束の欄が変わった項目と、事前審査（replan-review）が人に聞くと言った時は聞く。無人の run では、範囲を広げるだけの
直し（planmarks.widened）は聞かずに通し、通したことを元 replan._widen_text の字（lib/replan.widen_text。足した glob・外した glob）で
返す（widened。元の trace の行 replan.WIDEN_OP の代わりにこの節の返りが run の記録に 1 度だけ残り、線の collect が report へ渡す）。読めない計画は聞く側に倒す。無人の run で聞くはずの時は開かずに止める（needs-human）。
関所の文は聞く項目ごとの節（元 replan._gate_section）: 約束の欄の変化・人に聞く穴（事前審査の問い）・その項目を誤りとした申し出の文と
裁定の文（fix の conflicts.json の、裁定 fix_plan_item が項目の番号を名指す行。字のまま）・前の項目と直した項目の JSON。
asked は関所に見せた項目の行（「項目 <id>: …」と事前審査の問いの行。answer-replan が答えの asked にする）。

入力（with:）: old_plan・new_plan（指し札）・items（直す計画の項目の id。1 から数える番号）・ask_human・questions（事前審査の関所の
項目 {kind, text}）・conflicts（1 回目の修正の申し出と裁定の指し札。無ければ null）・unattended
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import answer
    import conflict
    import gatemarks
    import oneline
    import planmarks
    import replan
    import stopby

HEAD = "案の直しの承認ノード"
RECORD = "run の置き場の gates/gate-replan.json"
ITEM_HEAD = "## 人に聞く直した項目 {n}（単位 {units}）"   # 元 replan.GATE_ITEM_HEAD
NEW_HEAD = "### 直した項目（修正案の役が返した形。機械が貼った）"   # 元 replan.NEW_HEAD


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


def ruled_rows(ptr) -> tuple:
    """(1 回目の修正の申し出の行, 読めなかった訳)。指し札が無ければ ([], "")"""
    if ptr is None:
        return [], ""
    try:
        return conflict.items(boundary.resolve(ptr).parent), ""
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        return [], f"申し出と裁定の控えを読めない（{type(error).__name__}: {oneline.one_line(error)}）"


def item_rows(rows: list, ident: str, old, new) -> list:
    """項目 ident を誤りとした申し出の行（conflict.replan_rows。裁定 fix_plan_item が項目の番号を名指すか、申し出の単位が項目の単位）"""
    keys = (new or old or {}).get("unit_keys") or []
    return conflict.replan_rows(rows, int(ident), keys) if str(ident).isdigit() else []


def section(ident: str, old, new, changed: list, rows: list) -> list:
    """聞く項目の節（元 replan._gate_section）: 約束の欄の変化・申し出の文・裁定の文（字のまま）・前と後の項目の JSON"""
    units = "、".join(str(k) for k in (new or old or {}).get("unit_keys") or []) or "（無い）"
    lines = [ITEM_HEAD.format(n=ident, units=units), "", f"- 約束の欄の変化: {'・'.join(changed) or '（無し）'}"]
    for r in rows:
        lines += [f"- 申し出の文（{r.get('id')}・単位 {r.get('unit_key')}）: {r.get(conflict.WHY_FIELD)}",
                  f"- 裁定の文（{r.get('id')}）: {(r.get('ruling') or {}).get('text')}"]
    if not rows:
        lines.append("- 申し出の文と裁定の文: この項目を名指す裁定の行が控えに無い")
    for head, doc in ((replan.OLD_HEAD, old), (NEW_HEAD, new)):
        lines += ["", head, "", "```json", json.dumps(doc, ensure_ascii=False, indent=1) if doc is not None else "（読めない）", "```"]
    return lines + [""]


def ask(old_ptr, new_ptr, ids: list, *, ask_human: bool, questions: list, unattended: bool, run_id: str, conflicts=None) -> dict:
    old_fields, new_fields = plan_items(old_ptr), plan_items(new_ptr)
    ruled, unread = ruled_rows(conflicts)
    rows, widened, sections = [], [], []
    for ident in ids:
        old, new = item(old_fields, ident), item(new_fields, ident)
        if old is None or new is None:
            rows.append(f"項目 {ident}: 承認済みの項目か直した項目を読めない（聞く側に倒す）")
            sections += section(ident, old, new, [], item_rows(ruled, ident, old, new))
            continue
        changed = planmarks.contract_diff(old, new)
        wide = planmarks.widened(old, new) if unattended and changed and not ask_human else None
        if wide:
            widened.append(f"項目 {ident}: {replan.widen_text(wide)}")
        elif changed:
            rows.append(f"項目 {ident}: 約束の欄が変わった（{'・'.join(changed)}）")
            sections += section(ident, old, new, changed, item_rows(ruled, ident, old, new))
    if ask_human:
        rows += [f"事前審査の問い: {q}" for q in gatemarks.row_texts(questions)] or ["事前審査が人に聞くと言った"]
    if not rows:
        return {"open": False, "go": True, "stop_reason": "", "text": "", "widened": widened, "asked": []}
    if unattended:
        return {"open": False, "go": False, "stop_reason": stopby.NEEDS_HUMAN, "text": "", "widened": widened, "asked": []}
    lines = gatemarks.head3(f"{HEAD}が開いた。修正の段が誤りとした計画の項目を直した案に、人が決める物が {len(rows)} 件ある",
                            "直した案で 2 度目の修正へ進めるか、止めるか（打つ行は末尾の答え方）", gatemarks.push_of(rows))
    lines += ["", f"項目（{len(rows)} 件）:", *[f"- {row}" for row in rows], *[f"- {w}" for w in widened],
              *([f"- {unread}"] if unread else []), "", *sections,
              "答え方:",
              f"- 修正に戻る: {answer.line(run_id, 'continue', '<一言>')}（一言は {RECORD} に残り、修正前の承認ノードの答えの条件と共に 2 度目の修正に届く）",
              f"- 止める: {answer.line(run_id, 'stop', '<理由>')}（報告は出る）"]
    return {"open": True, "go": True, "stop_reason": "", "text": "\n".join(lines) + "\n", "widened": widened, "asked": rows}


def fallback(reason: str) -> dict:
    return {"open": False, "go": False, "stop_reason": boundary.LINE_SCRIPT, "text": "", "widened": [], "asked": []}


if __name__ == "__main__":
    boundary.run(lambda: ask(boundary.value(os.environ.get("INPUTS_OLD_PLAN")), boundary.value(os.environ.get("INPUTS_NEW_PLAN")),
                            [str(x) for x in boundary.items(os.environ.get("INPUTS_ITEMS"))],
                            ask_human=boundary.flag(os.environ.get("INPUTS_ASK_HUMAN")),
                            questions=boundary.items(os.environ.get("INPUTS_QUESTIONS")),
                            unattended=boundary.flag(os.environ.get("INPUTS_UNATTENDED")), run_id=os.environ["WORKFLOW_ID"],
                            conflicts=boundary.value(os.environ.get("INPUTS_CONFLICTS"))),
                fallback)

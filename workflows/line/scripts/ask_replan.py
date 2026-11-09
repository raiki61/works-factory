# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""案の直しの承認ノードを開くかと、見せる文を決める node ask-replan（docs/design/line.md の 2 節の 3・4.2・6 節。今の
workflows/line/scripts/ask_replan.py の決まりのまま）。

直した項目ごとの事実は案の直しの事前審査の出力 replan の行 {item, units, contract_changed, human, widened}（plan-review の設計書の
10.3）。聞くかは line が決める（src.gates.replan_asks: (contract_changed かつ 無人の run で widened でない) か human が在る。読めない
行は聞く側に倒す）。直した項目の頼みの解き方と判定の処方の外れ（事前審査の deviations の source means・prescription）は、事前審査の役の推しを行の欄 recommend に
持たせて聞く（depart_rows）。修正前の承認ノードの答えで通した穴の行（事前審査の穴 [kind] key の頭で始まる asked の行）は聞き直さない
（L-D26・S22）。無人の run で範囲を広げるだけの直しは聞かずに通し、足した・外した glob を widened で返す（L-G45）。無人の run で聞く
はずの時は gates.passage（約束の欄が変わった項目の行は欄 recommend を持たないので止まる。L-D30）。
案の直しが計画を作れなかった（replan の ok が偽）時は開かず進めない（fixed が held にする）。事前審査が諦めた・落ちた時は、その訳を
聞く行にする（案を審査できていない）。その時の外れは、直した項目の計画の {means, deviation}・{prescription, deviation} を推しなしで並べる
（修正前の承認ノードと同じ。無人の run なら止まる。判定の処方の文は入力 judgment の判定から引き、読めなければ読めていないと名乗る）。
文は聞く項目ごとの節（約束の欄の変化・人に聞く穴・その項目を誤りとした申し出の文と裁定の文〔fix の conflicts。字のまま〕・前と後の
項目の JSON）。asked は承認ノードに見せた項目の本文の字の並び（「項目 <id>: …」と事前審査の問いの行。推しは文に書かない。answer-replan が答えの asked にする）。

入力（with:）: replan（replan-out の got）・review（replan-review-out の got か null）・old_plan（承認済みの案の欄の pointer）・
items（直す計画の項目の番号）・conflicts（1 回目の修正の申し出と裁定の pointer か null）・before_fix（修正前の承認ノードの答え）・
record（始めの記録の pointer。方針の文書が固めた版から変わっていれば、その行を聞く項目に足す）・ports（start の配る値）・
means（依頼が示した解き方の文の並びか null。外れの行の M<n> に文を添える）・
judgment（判定の pointer か null。事前審査が落ちた時に、外れの行へ判定の処方の文を添える）
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

REPLAN = ("ok", "status", "reason", "plan", "fix_plan", "ripple", "round")
REVIEW = ("ok", "status", "reason", "replan", "round", "holes", "blocks", "deviations")
HEAD = "案の直しの承認ノード"
RECORD = "run の置き場の gates/gate-replan.json"
ITEM_HEAD = "## 人に聞く直した項目 {n}（単位 {units}）"   # 元 replan.GATE_ITEM_HEAD
OLD_HEAD = "### 前の項目（承認済み。機械が貼った）"   # 元 replan.OLD_HEAD
NEW_HEAD = "### 直した項目（修正案の役が返した形。機械が貼った）"   # 元 replan.NEW_HEAD
REVIEW_FELL = "案の直しの事前審査が案を審査できていない（{why}）"
PREVIOUS = "gates/gate-replan.json"   # 同じ承認ノードの前の答え（answer.taken が書く。resume で回し直した時に聞き直さない）


def plan_items(path: str) -> list | None:
    """修正案の欄のファイル（plan-fields.json の {fields: [...]}）の項目の欄。読めなければ None"""
    from src import gates
    doc = gates.read_json(path)
    fields = doc.get("fields") if isinstance(doc, dict) else None
    return fields if isinstance(fields, list) else None


def item(fields, ident) -> dict | None:
    ident = str(ident)
    if fields is None or not ident.isdigit() or not 1 <= int(ident) <= len(fields):
        return None
    got = fields[int(ident) - 1]
    return got if isinstance(got, dict) else None


def ruled_rows(path: str) -> tuple:
    """(1 回目の修正の申し出の行, 読めなかった訳)。pointer が無ければ ([], "")"""
    import conflict
    import oneline
    if not path:
        return [], ""
    try:
        return conflict.items(Path(path).parent), ""
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        return [], f"申し出と裁定の控えを読めない（{type(error).__name__}: {oneline.one_line(error)}）"


def section(ident, old, new, changed: list, rows: list) -> list:
    """聞く項目の節（元 replan._gate_section）: 約束の欄の変化・申し出の文・裁定の文（字のまま）・前と後の項目の JSON"""
    import conflict
    keys = (new or old or {}).get("unit_keys") or []
    hits = conflict.replan_rows(rows, int(ident), keys) if str(ident).isdigit() else []
    units = "、".join(str(k) for k in keys) or "（無い）"
    lines = [ITEM_HEAD.format(n=ident, units=units), "", f"- 約束の欄の変化: {'・'.join(changed) or '（無し）'}"]
    for r in hits:
        lines += [f"- 申し出の文（{r.get('id')}・単位 {r.get('unit_key')}）: {r.get(conflict.WHY_FIELD)}",
                  f"- 裁定の文（{r.get('id')}）: {(r.get('ruling') or {}).get('text')}"]
    if not hits:
        lines.append("- 申し出の文と裁定の文: この項目を名指す裁定の行が控えに無い")
    for head, doc in ((OLD_HEAD, old), (NEW_HEAD, new)):
        lines += ["", head, "", "```json", json.dumps(doc, ensure_ascii=False, indent=1) if doc is not None else "（読めない）", "```"]
    return lines + [""]


def passed_before(before_fix, face: dict) -> bool:
    """修正前の承認ノードの答えが、この穴の行（事前審査の穴 [kind] key の頭）を通した（continue）か（L-D26）"""
    import answer
    if not isinstance(before_fix, dict) or before_fix.get("decision") not in answer.GO_WORDS:
        return False
    head = f"事前審査の穴 [{face.get('kind')}] {face.get('key')}: "
    return any(isinstance(a, str) and a.startswith(head) for a in before_fix.get("asked") or [])


def depart_rows(deviations, ids: list, before_fix) -> list:
    """案の直しの事前審査の外れの行のうち、直した項目（ids）の頼みの解き方と判定の処方の行の項目の行（本文は gatemarks.depart_item の文、欄 recommend は
    事前審査の役が書いて gatemarks.recommend_of が検めた推し。計画 means-answers の 3.3 の 5）。修正前の承認ノードが continue で通した行は、推しが
    書き直されていても聞き直さない: 頼みの解き方は聞いた文の頭の鍵 (項目, M<n>, 向き)（gatemarks.means_key）、判定の処方は本文の全文一致で比べる
    （同じ項目・同じ単位・同じ外れの訳なら同じ行。外れの訳を変えた行は聞く）。直さない項目の行は修正前の承認ノードで答え済みなので
    足さない。事前審査が諦めた・落ちた時は、deviations に直した案の計画の外れの行（gatemarks.means_rows・prescription_depart_rows。
    推しなし）を渡す"""
    import answer
    import gatemarks
    import plainask
    revised = {int(i) for i in ids if str(i).isdigit()}
    asked = []
    if isinstance(before_fix, dict) and before_fix.get("decision") in answer.GO_WORDS:
        asked = [t for a in before_fix.get("asked") or [] if (t := plainask.item_text(a))]
    passed_means = {k for a in asked if (k := gatemarks.means_key(a)) is not None}
    passed_text = set(asked)
    out = []
    for d in deviations if isinstance(deviations, list) else []:
        if not (isinstance(d, dict) and d.get("source") in (gatemarks.MEANS_KIND, gatemarks.PRESCRIPTION_KIND) and d.get("item") in revised):
            continue
        text = gatemarks.depart_item(d)
        if d["source"] == gatemarks.MEANS_KIND:
            again = gatemarks.means_key(text) in passed_means
        else:
            again = text in passed_text
        mark = d.get("mark") if isinstance(d.get("mark"), dict) else {}
        row = plainask.item_row(text, None, gatemarks.recommend_of(mark))
        if not again and row not in out:
            out.append(row)
    return out


def policy_row(record: dict, folder: Path, answered: list) -> str:
    """方針の文書が始めの記録の固めた版から変わっていれば、その行（src.gates.change_row）。今の案の直しの承認ノードも、事前審査の
    _asked が方針の変化の行を足して開いた（元の boardview の collect）。人が前に continue で通した同じ文の行は聞き直さない
    （修正前の承認ノードの答えか、この承認ノードの前の答え。ほかの行と同じ決まり）。修正前に通して固め直した run は、始めの記録の
    方針が今の版なので行が出ない"""
    from src import gates
    change = gates.policy_change(record, Path.cwd(), folder)
    row = gates.change_row(change) if change else ""
    return "" if not row or gates._continued(answered, row) else row


def ask(replan_got, review_got, old_plan: str, ids: list, conflicts: str, before_fix, *, unattended: bool, run_id: str,
        policy: str = "", missing=(), means=(), judgment=None) -> dict:
    import answer
    import gatemarks
    import plainask
    import planmarks
    import replan
    import worldmark
    from src import gates

    closed = {"open": False, "go": False, "stop_reason": "", "text": "", "widened": [], "asked": [], "pushed": None}
    if replan_got is None or replan_got["ok"] is not True:
        return closed
    missing = list(missing)   # 指す先が無い・読めない控え（聞く行にする。形の違う pointer は落ちる）
    old_fields = plan_items(old_plan)
    new_fields = plan_items(gates.located(replan_got["plan"], "案の直しの修正案の欄", missing, lambda raw: ports.file(raw, "json(shared:plan-fields.schema.json)")))
    ruled, unread = ruled_rows(conflicts)
    rows, widened, sections = [], [], []
    if review_got is None or review_got["status"] != "ok":
        why = "出力が無い" if review_got is None else (review_got["reason"] or review_got["status"])
        rows.append(plainask.item_row(REVIEW_FELL.format(why=why)))
        facts = [{"item": i} for i in ids]
        judged = gates.read_located(judgment, "判定", missing, lambda raw: ports.file(raw, "json(shared:judgment.schema.json)"))
        rows += depart_rows([*gatemarks.means_rows(new_fields, worldmark.means_hints(means)),
                             *gatemarks.prescription_depart_rows(new_fields, planmarks.judged_prescriptions(judged))], ids, before_fix)
    else:
        facts = [r for r in review_got["replan"] or []]
        rows += depart_rows(review_got["deviations"] or [], ids, before_fix)
    for r in gates.replan_asks(facts, unattended_run=unattended) if facts else []:
        ident = r.get("item") if isinstance(r, dict) else None
        old, new = item(old_fields, ident), item(new_fields, ident)
        if not isinstance(r, dict) or old is None or new is None or "contract_changed" not in r:
            rows.append(plainask.item_row(f"項目 {ident}: 承認済みの項目か直した項目を読めない（聞く側に倒す）"))
            sections += section(ident, old, new, [], ruled)
            continue
        changed = list(r.get("contract_changed") or [])
        human = [f for f in r.get("human") or [] if isinstance(f, dict) and not passed_before(before_fix, f)]
        if changed:
            rows.append(plainask.item_row(f"項目 {ident}: 約束の欄が変わった（{'・'.join(changed)}）"))
        rows += [plainask.item_row(f"事前審査の問い: 事前審査の穴 [{f.get('kind')}] {f.get('key')}: {f.get('why')}") for f in human]
        if changed or human:
            sections += section(ident, old, new, changed, ruled)
    for r in facts:
        if unattended and isinstance(r, dict) and r.get("widened") and not r.get("human"):
            widened.append(f"項目 {r.get('item')}: {replan.widen_text(r['widened'])}")
    rows += [plainask.item_row(f"{row}{gates.UNREAD_TAIL}") for row in dict.fromkeys(missing)]
    if policy:
        rows.append(plainask.item_row(policy))
    if not rows:
        return {**closed, "go": True, "widened": widened}
    if unattended:
        got = gates.passage(rows)
        return {**closed, "go": got.go, "stop_reason": got.stop_reason, "widened": widened, "asked": got.asked, "pushed": got.pushed}
    lines = gatemarks.head3(f"{HEAD}が開いた。修正の段が誤りとした計画の項目を直した案に、人が決める物が {len(rows)} 件ある",
                            "直した案で 2 度目の修正へ進めるか、止めるか（打つ行は末尾の答え方）", gatemarks.push_of(rows))
    lines += ["", f"項目（{len(rows)} 件）:", *gatemarks.item_lines(rows), *[f"- {w}" for w in widened],
              *([f"- {unread}"] if unread else []), "", *sections,
              "答え方:",
              f"- 修正に戻る: {answer.line(run_id, 'continue', '<一言>')}（一言は {RECORD} に残り、修正前の承認ノードの答えの条件と共に 2 度目の修正に届く）",
              f"- 止める: {answer.line(run_id, 'stop', '<理由>')}（報告は出る）"]
    return {"open": True, "go": True, "stop_reason": "", "text": "\n".join(lines) + "\n", "widened": widened,
            "asked": [plainask.item_text(row) for row in rows], "pushed": None}


def compute() -> dict:
    raw = {"old_plan": os.environ.get("INPUTS_OLD_PLAN"), "items": os.environ.get("INPUTS_ITEMS"),
           "conflicts": os.environ.get("INPUTS_CONFLICTS"), "before_fix": os.environ.get("INPUTS_BEFORE_FIX"),
           "record": os.environ.get("INPUTS_RECORD"), "ports": os.environ.get("INPUTS_PORTS"), "means": os.environ.get("INPUTS_MEANS"),
           "judgment": os.environ.get("INPUTS_JUDGMENT")}
    from src import gates, startrec

    given = ports.parsed(raw["ports"]) or {}
    ids = ports.parsed(raw["items"]) or []
    record_path = ports.file(raw["record"], "json(start-record.schema.json)")
    before_fix = ports.parsed(raw["before_fix"])
    means = ports.parsed(raw["means"])
    previous = gates.read_json(ports.place() / PREVIOUS)
    answered = [a for a in (before_fix, previous) if isinstance(a, dict)]
    row = policy_row(startrec.load(record_path) if record_path else {}, ports.place(), answered)
    missing: list = []
    old_plan = gates.located(raw["old_plan"], "承認済みの修正案の欄", missing, lambda raw: ports.file(raw, "json(shared:plan-fields.schema.json)"))
    conflicts = gates.located(raw["conflicts"], "修正の申し出と裁定の控え", missing, lambda raw: ports.file(raw, "json(lib:conflicts.schema.json)"))
    return ask(ports.picked(os.environ.get("INPUTS_REPLAN"), REPLAN),
               # deviations は頼みの解き方の行を持たない前の版の返りと stub では無く、空と読む
               ports.picked(os.environ.get("INPUTS_REVIEW"), REVIEW, optional=("deviations",)), old_plan,
               [str(x) for x in ids] if isinstance(ids, list) else [], conflicts, before_fix,
               unattended=bool(given.get("unattended")), run_id=os.environ["WORKFLOW_ID"], policy=row, missing=missing,
               means=means if isinstance(means, list) else [], judgment=raw["judgment"])


def fallback(reason: str) -> dict:
    from src import guard

    return {"open": False, "go": False, "stop_reason": guard.LINE_SCRIPT, "text": "", "widened": [], "asked": [], "pushed": None}


ports.run(compute, fallback)

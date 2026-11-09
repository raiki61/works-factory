"""report の block へ渡す facts を組む（docs/design/line.md の 7.2。欄と意味は docs/design/report.md の 1.2 の表）。

元は組み込みで消えた outcome（結末の読み分けの部分）と runreport（line だけが使う部分）の同じ名の関数（integration.md の
4.5-4 (f)）。元は block の返り（returns: 段の役の名 → 返り）を読んだので、ここでも受け皿の got を元の役の名の returns に詰め直して
（returns_of）、同じ名の関数で読む。pointer は stages.resolve で place の中のパスに戻す。結末の 10 語と決める順は report の
block の src/outcome.py が持ち、ここは止め・人待ち・残り・証の事実に仕分けるだけ。lib は KEEP の物だけを読む（関数の中で import する。stopby・gatemarks・fixboard だけは表 HEAD_NOTICE・ASK_SOURCES の鍵に使うので頭で読む）。

- returns_of(values, record) -> returns: collect が受けた値（受け皿の got・line の script の出力）を元の役の名の dict に
- build(values, record, record_why) -> facts（facts.schema.json の欄の全部）
- 部分ごとに組めなかった時は、結末に効く部分（止め・人待ち・残り・証）なら problems（結末を名乗らせない）、見せるだけの部分なら notes に
  訳を足して先へ進む（黙って空にしない）
"""
from __future__ import annotations

import json
import pathlib
import typing

import fixboard
import gatemarks
import stopby
from src import stages as stageslib

GATES = (("gate-start", "answer_start"), ("gate-before-fix", "answer_before_fix"), ("gate-replan", "answer_replan"),
         ("gate-final", "answer_final"))
# line の script の止めの語を読む node（collect の入力の名 → node の id）
LINE_STOPS = (("start", "start"), ("answer-start", "answer_start"), ("tiers", "tiers"), ("owed", "owed"), ("structure-in", "structure_in"),
              ("design-in", "design_in"), ("ask-before-fix", "ask_before_fix"), ("answer-before-fix", "answer_before_fix"),
              ("fix-in", "fix_in"), ("after-fix", "after_fix"), ("raise", "raise"), ("lens-in", "lens_in"), ("ask-replan", "ask_replan"),
              ("answer-replan", "answer_replan"), ("lens-2-in", "lens_2_in"), ("fixed", "fixed"), ("judged", "judged"),
              ("ask-final", "ask_final"), ("answer-final", "answer_final"), ("spec-rounds", "spec_rounds"),
              ("theme-descend", "theme_descend"), ("request-in", "request_in"))
# block の返りの止めの語（node の id → collect の入力の名）。修正後の並行 PR の確かめ直しは run を止めない（docs/design/line.md の 8.1）
BLOCK_STOPS = (("judge", "judge"), ("spec-check-run", "spec_check"), ("spec-entry", "spec_entry"), ("spec-check", "spec_driven_check"))
GIVE_UP = "give-up"
NOT_OK = "not-ok"
CHAIN_CUT = "chain-cut"
MATERIAL_WHERE = "素材"
AFTER_WHERE = "直した後の構造の実測"   # 残りの行の where: 直した後の実測を読めない
NOT_CLOSED = "直したと申告したが、機械が判定の問いで数え直すと閉じていない"
MISSING_EYE = "の結果が無い——再実行の要あり（深さは標準で、省いていない）"
EYE_NAMES = ("r1", "r2", "r3", "r4")
GAVE_UP_WHERE = "修正の受け付けを通らなかった単位"
PLAN_GAVE_UP_WHERE = "受け付け 計画"
STOPPED_WHERE = "止めた段"
GROUP_WHERE = "組"
PROTECTED_HITS_HEAD = "守ると決めたファイルに当たった差分"   # 報告の頭に種の名として出る言い方なので、工場の中だけの語（語の表 glossary.json の語）を使わない
BACKED_OUT_HEAD = "当ててから確かめ直しが赤か落ちて戻した修正のまとまり"
REPAIRED_HEAD = "合わせ役が直して当てた組"
UNRESTORED_GROUP_HEAD = "戻せずに作業フォルダへ当たったままの修正のまとまり（人が確かめる）"
UNCOMPARED_HEAD = "当てた後の確かめ直しで直す前の版と比べられなかった赤（組は戻さずに当てた。直しが壊したかを人が確かめる）"
PR_COMMITS = "PR の commit: "
POLICY_CHANGED_HEAD = "方針の文書が始めに固定した版から変わったまま終わった"
UNNAMED_NODE = "名の訳が無いノード"
UNKNOWN_STOP = "語の意味の記録が無い"
NO_STOP_REASON = "訳の記録が無い"
# 止めの語 → 報告の頭の知らせの種（head.Notice の値）。語が在る止めは、訳が空でも黙らない。種の文（何が起きて何をするか）は報告の頭の表 head.NOTICES が持ち、
# ここは種と差し込み口の値と、返りの訳（本文 text。報告の節「2. 止めたか」に載る）だけを付ける
HEAD_NOTICE = {stopby.START_REFUSED: "start_refused", stopby.ANSWER_REDIRECTED: "answer_redirected"}
NO_QUOTE = "一言なし"
NO_CMD = "（無し）"
NO_LOG = "（記録なし）"
UNPASSED_WHERE = "指摘の全文は報告の「2. 止めたか」の節"
EYE_ASK_HEAD = "依頼の範囲を超えていないかを見る目の問い"   # gatemarks.EYES["R4"] の問い。頭の行に目の印 R4 を出さない
MEANS_ASK_HEAD = "頼みの解き方どおりで、別に作った設計と食い違う所"   # R2 の頼みどおりの違いの問い（計画 means-answers の 6.3 の 3。行の頭の R2: で目が分かる）。頭に出る種の名なので語の表の語を使わない
CONFLICT_ASK_HEAD = "修正の役が人に回した食い違いの知らせ"   # 修正の役が人に回した食い違いの申し出の種の名。頭に出る言い方なので語の表の語を使わない
MEANS_WAIT = "r2-means-ask"   # その問いが答えを得ていない人待ちの語


class _Marker:
    """題の出どころの印（表 ASK_SOURCES の値。字の値は種ごとの決まった字の題）"""

    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return self.name


ROW_TITLE = _Marker("ROW_TITLE")   # 本文を書いた所が行の title の欄に題を書いた（読み口 plainask.item_title が 1 行に畳む）
KIND_NAME = _Marker("KIND_NAME")   # 題を持たず、報告の頭は種の名に戻す（題の欄を書く役が無い種。古い記録で題の欄が無い行の戻しは report の ask_rows の 1 か所）
HELD_KIND = "保留にしたままの問い"
PLAN_KIND = "修正前の問い"
UNRETURNED_KIND = "直しの対象に戻せなかった項目"
ESCALATED_KIND = "前提の検算が人に上げた物"
SPEC_HEADS = {unchecked: gatemarks.spec_words(unchecked).head for unchecked in (False, True)}   # 仕様を確かめる役の問いの見出し（照らせなかったか → 見出し。選びは spec_words の 1 か所）
# 人が決める物の種 → 題の出どころ。種の順と題の出どころはここ 1 か所（decisions は ask_groups が集めた {種: 行} をこの鍵の順に並べるだけで、
# 表に無い種は並べられない）。値: ROW_TITLE（行の title の欄）・KIND_NAME（題を持たず種の名に戻す）・字（機械が本文を組む種の決まった題。
# 行ごとの値を差し込まない〔単位の id は工場の中の値で、頭の読み手の世界の値でない〕ので、同じ種の行は報告の頭で 1 行にまとまる）。仕様を確かめる役の問いの見出しは入力で
# 2 つに分かれる（照らせた時・照らせなかった時。gatemarks.spec_words）ので、2 つとも種の名に戻す印で置く。字の題は報告の頭に出るので語の表の語を使わない
ASK_SOURCES = {
    UNRESTORED_GROUP_HEAD: "戻せずに当たったままの修正を、人が確かめる",
    BACKED_OUT_HEAD: "確かめ直しが通らず戻した修正を、どうするか決める",
    **dict.fromkeys(SPEC_HEADS.values(), KIND_NAME),
    PLAN_KIND: ROW_TITLE,
    EYE_ASK_HEAD: ROW_TITLE,
    MEANS_ASK_HEAD: ROW_TITLE,
    HELD_KIND: ROW_TITLE,
    CONFLICT_ASK_HEAD: "修正の役が人に回した食い違いに答える",
    fixboard.HANDOFF_HEAD: ROW_TITLE,
    PROTECTED_HITS_HEAD: "守ると決めたファイルに当たった差分を確かめる",
    UNRETURNED_KIND: "直しの対象に戻せなかった修正の訳を確かめる",
    UNCOMPARED_HEAD: "直す前の版と比べられなかった赤を、人が確かめる",
    ESCALATED_KIND: "前提の検算が人に上げた判定を決める",
}
OWN_LINES = (UNRESTORED_GROUP_HEAD, BACKED_OUT_HEAD)   # 種の行を decisions の before に別に並べる種（種の見出しと件数の行を足さない）
NO_EYES = "独立の目のサブグラフの出力が無い（飛ばされた・落ちた）"
DATA_PLACES = "固定のデータの在り処: run の頭の深さの控え {head}"
NO_HEAD_AT = "（控えが無い）"
STOP_OUTCOMES = ("stopped_by_request", "stopped_by_human", "stopped_by_line", "needs_human")
# 段の表（docs/design/line.md の 7.2 の cut。今の collect.STAGES を新しい node の名に直した物）。返りの続き: 前の段 before の欄 flag
# （None は返りが在るだけ）が真なのに後の段 after の返りが無ければ text の切れ目。held: before の返りのその欄が偽なら数えない、needs: その
# 役の返りが無い周は数えない
STAGES = (
    {"before": "judge", "flag": "ready", "after": "plan", "text": "判定が直す単位を出したのに計画の出力が無い"},
    {"before": "plan", "flag": "ok", "after": "fix", "text": "計画が修正案を出したのに修正の出力が無い"},
    {"before": "fix", "flag": None, "after": "final-tests", "text": "修正の段が走ったのに最後のテストの出力が無い", "held": "go"},
    {"before": "final-tests", "flag": "ok", "after": "sealed-diff", "text": "最後のテストが通ったのに差分を封じた出力が無い",
     "needs": "fix"},
)
NODE_OF = {"judge": "judge", "plan": "plan-rounds", "fix": "fix", "final-tests": "test-gate-final", "sealed-diff": "merge-seal",
           "applied-diff": "merge-apply", "plan-review": "plan-rounds", "rejudge": "rejudge-run"}


def as_dict(v) -> dict:
    return v if isinstance(v, dict) else {}


def _list(v) -> list:
    return v if isinstance(v, list) else []


def read_ptr(ptr, field: str):
    """(中身, 読めなかった訳)。field は pointer を返した作り手の欄の名（stages.resolve がその宣言の form で照らす）。pointer が無ければ (None, "")"""
    import oneline
    if ptr is None or ptr == "":
        return None, ""
    try:
        return json.loads(stageslib.resolve(ptr, field).read_text(encoding="utf-8")), ""
    except (OSError, *stageslib.READ_ERRORS) as e:
        return None, f"{ptr.get('path') if isinstance(ptr, dict) else ptr} が読めない: {oneline.one_line(e)}"


# ---------------------------------------------------------------- 受け皿の got を元の役の名の returns に
def returns_of(values: dict, record: dict | None) -> dict:
    """元の役の名の returns: judge（fix-in が運んだ固定材料の値で埋める）・rejudge・plan（計画の往復の記録 plan-out）・plan-review
    （最後の往復の事前審査の値。plan-out の stalled・asks を持つ）・replan・replan-review-result・fix（fixed の合わせ）・before-tests・
    final-tests・eyes・sealed-diff・applied-diff・structure・start（始めの記録）・theme_descend（テーマの run の降りる道）・request_in
    （依頼の出どころ。台帳の依頼の答えの源）"""
    received = as_dict(as_dict(values.get("fix_in")).get("received"))
    judge = values.get("judge") if isinstance(values.get("judge"), dict) else received.get("judge")
    rounds = values.get("rounds") if isinstance(values.get("rounds"), dict) else received.get("rounds")
    fixed = values.get("fixed") if isinstance(values.get("fixed"), dict) else None
    return {
        "start": record or {},
        "before-tests": values.get("test_gate_base") if isinstance(values.get("test_gate_base"), dict) else received.get("test_gate_base"),
        "judge": judge if isinstance(judge, dict) else None,
        "rejudge": values.get("rejudge") if isinstance(values.get("rejudge"), dict) else None,
        "plan": rounds if isinstance(rounds, dict) else None,
        "plan-review": rounds if isinstance(rounds, dict) else None,
        "replan": values.get("replan") if isinstance(values.get("replan"), dict) else None,
        "replan-review-result": values.get("replan_review") if isinstance(values.get("replan_review"), dict) else None,
        "fix": fixed if fixed is not None and (fixed.get("stages") or fixed.get("no_fix")) else None,
        "final-tests": values.get("test_gate_final") if isinstance(values.get("test_gate_final"), dict) else None,
        "eyes": values.get("eyes") if isinstance(values.get("eyes"), dict) else None,
        "sealed-diff": values.get("merge_seal") if isinstance(values.get("merge_seal"), dict) else None,
        "applied-diff": values.get("merge_apply") if isinstance(values.get("merge_apply"), dict) else None,
        "structure": values.get("structure") if isinstance(values.get("structure"), dict) else received.get("structure"),
        "theme_descend": values.get("theme_descend") if isinstance(values.get("theme_descend"), dict) else None,
        "request_in": values.get("request_in") if isinstance(values.get("request_in"), dict) else None,
    }


def latest(returns: dict, rid: str) -> dict | None:
    """段の返り（後の段の返りが在ればそちら。元 outcome.latest）"""
    later = {"judge": "rejudge", "plan-review": "replan-review-result"}.get(rid, "")
    got = returns.get(later)
    got = got if isinstance(got, dict) else returns.get(rid)
    return got if isinstance(got, dict) else None


def _units(returns: dict) -> list:
    return _list(as_dict(latest(returns, "judge")).get("units"))


def fix_stages(returns: dict) -> list:
    """修正の段ごとの控えの段（stages.stage。fixed の stages の fix の got から）"""
    out = []
    rows = _list(as_dict(returns.get("fix")).get("stages"))
    for s, name in zip(rows, stageslib.names(rows)):
        got = as_dict(s).get("fix")
        if isinstance(got, dict):
            try:
                out.append(stageslib.stage(got, name))
            except KeyError:
                out.append(None)
    return out


def beside(returns: dict) -> dict:
    """修正の段の控えの見え方（stages.read）"""
    return stageslib.read(fix_stages(returns), stageslib.resolve)


# ---------------------------------------------------------------- 申し出と素材（元 outcome）
def conflict_rows(returns: dict) -> tuple[list, list]:
    """fix の conflicts の先の行を全部の段で合わせた物と、読めなかった訳の行"""
    import conflict
    import oneline
    rows, notes = [], []
    for ptr in _list(as_dict(returns.get("fix")).get("conflicts")):
        doc, why = read_ptr(ptr, "conflicts")
        items = doc.get(conflict.ITEMS) if isinstance(doc, dict) else None
        if why or not isinstance(items, list):
            notes.append(f"申し出と裁定のファイルが読めない: {oneline.one_line(why or f'欄 {conflict.ITEMS} の配列が無い')}")
            continue
        rows += [i for i in items if isinstance(i, dict)]
    return rows, notes


def waiting_conflicts(returns: dict) -> list:
    import conflict
    return conflict.waiting_rows(conflict_rows(returns)[0])


def asked_conflicts(returns: dict, closed: bool = True) -> list:
    """人に諮る申し出の行。closed（途中で落ちていない run）なら、案の直しを待つ行も諦めた行として足す（訳は replan.CLOSE_WHY）"""
    import conflict
    import replan
    asked = conflict.asked_rows(conflict_rows(returns)[0])
    return asked + [{**i, conflict.REPLAN_WHY: replan.CLOSE_WHY} for i in waiting_conflicts(returns)] if closed else asked


def asked_units(returns: dict, closed: bool = True, rows: list | None = None) -> list:
    import conflict
    rows = asked_conflicts(returns, closed) if rows is None else rows
    own, out = {}, {}
    for r in rows:
        own.setdefault(r.get("unit_key"), r)
    for r in rows:
        for k in conflict.ruled_units(r):
            if isinstance(k, str) and k:
                out.setdefault(k, own.get(k, r))
    return list(out.items())


def materials(returns: dict) -> tuple[dict, str]:
    """判定（再審が在ればその）の返りの欄 materials の先の素材の状態と、読めなかった訳"""
    doc, why = read_ptr(as_dict(latest(returns, "judge")).get("materials"), "materials")
    if why:
        return {}, f"素材の状態が読めない（測れていない素材は無いと数えた）: {why}"
    if doc is not None and not isinstance(doc, dict):
        return {}, "素材の状態がオブジェクトでない（測れていない素材は無いと数えた）"
    return doc or {}, ""


def judgment_doc(returns: dict) -> dict:
    doc, _ = read_ptr(as_dict(latest(returns, "judge")).get("judgment"), "judgment")
    return as_dict(doc)


def ledger(returns: dict, gates: dict, unattended: bool):
    """問いの台帳の見え方（元 runreport.ledger。gatemarks.ledger。依頼の答えは request-in の返り。_request_answers）"""
    import gatemarks
    ties_doc, _ = read_ptr(as_dict(returns.get("judge")).get("answer_ties"), "answer_ties")
    ties = gatemarks.ties_of(ties_doc) if ties_doc is not None else []
    mats, _ = materials(returns)
    return gatemarks.ledger(judgment_doc(returns), answers=_request_answers(returns), gate=gates.get("gate-before-fix"), ties=ties,
                            materials=mats, takes_push=unattended)


def ties_note(returns: dict) -> str:
    """問いの台帳の答えの結びを読めない訳（ledger は結びが無いとして組むので、無いと黙って数えずに notes で名指す。E23）。読めれば空"""
    _, why = read_ptr(as_dict(returns.get("judge")).get("answer_ties"), "answer_ties")
    return f"答えの結びを読めない（保留の問いと答えを結ばずに数えた）: {why}" if why else ""


def _request_answers(returns: dict) -> list:
    """依頼の答え（request-in の返りの request_answers。テーマの run は降りた依頼の答えで、判定が問いを結んだ答えと同じ源）"""
    return [a for a in _list(as_dict(returns.get("request_in")).get("request_answers")) if isinstance(a, dict)]


def _material_row(name: str, status: str, why=None) -> dict:
    import oneline
    said = f": {oneline.one_line(why)}" if why else ""
    return {"where": f"{MATERIAL_WHERE} {name}",
            "text": f"素材 '{name}' が {status}{said}（run の中で測れていない確かめ。人が手元で確かめる）"}


def _eye_rows(returns: dict, eyes_due: bool | None) -> list:
    """独立の目の残り: 通さなかった目と、目を回したのに返りの無い目（eyes_due が真。回さない run は数えない）"""
    import oneline
    import report
    import seal
    eyes = returns.get("eyes")
    if not isinstance(eyes, dict):
        return []
    rows = []
    for name in EYE_NAMES:
        e = eyes.get(name)
        label = name.upper()
        if isinstance(e, dict) and e.get("status") != seal.PASSED:
            rows.append({"where": f"{report.EYES_WHERE} {label}",
                         "text": f"{label} が {e.get('status')}: {oneline.one_line(e.get('reason') or '理由なし')}"})
        elif e is None and eyes_due is True:
            rows.append({"where": f"{report.EYES_WHERE} {label}", "text": f"{label} {MISSING_EYE}"})
    if eyes.get("ok") is False and not rows:
        rows.append({"where": report.EYES_WHERE,
                     "text": "独立の目のまとめが ok でない: 目ごとの出力（r1〜r4）に通さなかった目が無い"})
    return rows


def _after_rows(returns: dict) -> list:
    """直した後の構造の実測が見た、住処の外の知る場所の増え（structmark.after_rows。指し札の先のフォルダを読む）。指し札か控えを
    読めない時は、増えが無いと数えずに読めない訳の 1 行（E23）"""
    import structmark
    ptr = as_dict(returns.get("eyes")).get("after")
    if not ptr:
        return []
    try:
        folder = stageslib.resolve(ptr, "after").parent
    except stageslib.READ_ERRORS as error:
        return [{"where": AFTER_WHERE, "text": f"直した後の実測のポインタを読めない（柵の増えを数えていない。{type(error).__name__}: {error}）"}]
    if structmark.read_after(folder) is None:
        return [{"where": AFTER_WHERE, "text": f"直した後の実測の控え {structmark.AFTER_FILE} を読めない（柵の増えを数えていない）"}]
    return structmark.after_rows(folder)


def residue(returns: dict, facts: dict) -> list:
    """fixed を名乗らせない残りの行 [{where, text, unmeasured}]（元 outcome.residue。受け止めた落ちは report が足す）"""
    import fixboard
    import gatemarks
    import oneline
    rows = []
    final = returns.get("final-tests")
    if isinstance(final, dict) and (final.get("ok") is not True or final.get("green") is not True):
        rows.append({"where": "最後のテスト", "text": f"最後のテストが緑でない・認証できない（ok {final.get('ok')}・green {final.get('green')}・"
                                                 f"赤の原因 {final.get('red_cause') or '—'}）"})
    rows += _eye_rows(returns, facts.get("eyes_due"))
    fix = returns.get("fix")
    if isinstance(fix, dict) and not fix.get("no_fix"):
        units = [u for u in _list(fix.get("units")) if isinstance(u, dict)]
        for u in units:
            if u.get("status") in fixboard.UNIT_LEFT:
                rows.append({"where": f"修正 {u.get('unit_id')}",
                             "text": f"単位 {u.get('unit_id')} が {u['status']}: {oneline.one_line(u.get('reason') or '理由なし')}"})
        left = {u.get("unit_id") for u in units if u.get("status") in fixboard.UNIT_LEFT}
        got = facts.get("beside") or beside(returns)
        for k in stageslib.not_closed(got):
            if k not in left:
                rows.append({"where": f"修正 {k}", "text": f"単位 {k} が閉鎖の表で閉じていない（{NOT_CLOSED}）"})
        rows += [{"where": "修正", "text": line} for line in got["closure_unread"]]
        if fix.get("done") is False:
            rows.append({"where": "修正", "text": "修正の段が直し終えていない（done が false）"})
        rows += [r for r in _list(fix.get("left")) if isinstance(r, dict)]
    rows += _after_rows(returns)
    mats, _ = materials(returns)
    checked = facts.get("measured") or set()
    rows += [_material_row(n, s, as_dict(mats.get(n)).get("reason")) for n, s in gatemarks.unmeasured_of(mats).items() if n not in checked]
    return [{"where": str(r.get("where")), "text": str(r.get("text")), "unmeasured": str(r.get("where") or "").startswith(f"{MATERIAL_WHERE} ")}
            for r in rows]


# ---------------------------------------------------------------- 止め・人待ち・切れ目・証
def gates_of(values: dict) -> dict:
    """承認ノードの答え {承認ノード: {decision, text, …} | None}"""
    out = {at: as_dict(values.get(name)).get("answer") if isinstance(as_dict(values.get(name)).get("answer"), dict) else None
           for at, name in GATES}
    import answer
    theme = as_dict(values.get("theme_descend")).get("answer")   # テーマの run の設計の段の承認ノードの答え（無人の run の推しも。3.3 節）
    if isinstance(theme, dict):
        out = {"gate-theme": theme, **out}
    talked = as_dict(values.get("ask_before_fix")).get("agreed")   # 対話モードの run の設計の相談の最後の答え（docs/design/line.md の 3.1 節）
    # 通す語の合意は answer-before-fix が修正前の答えとして書くので、そこに答えが在れば 2 度数えない（止めた答えと、修正前に答えが無い合意だけ出す）
    if isinstance(talked, dict) and (talked.get("decision") not in answer.GO_WORDS or out.get("gate-before-fix") is None):
        out = {"gate-design": talked, **out}
    return out


def gate_rows(gates: dict) -> list:
    return [{"at": at, "decision": g.get("decision") if isinstance(g, dict) else None,
             "text": str(g.get("text") or "") if isinstance(g, dict) else ""} for at, g in gates.items()]


def stop_returns(values: dict) -> list:
    """止めた段の返り [(node, 止めの語, 訳)]（LINE_STOPS・BLOCK_STOPS の表の順）: 返りの stop_reason が空でない字の段だけ。訳は返りの reason
    （空でない字ならその字、ほかは空）。node から返りを引く読みはここだけ"""
    out = []
    for node, name in (*LINE_STOPS, *BLOCK_STOPS):
        got = as_dict(values.get(name))
        word = got.get("stop_reason")
        if isinstance(word, str) and word:
            why = got.get("reason")
            out.append((node, word, why if isinstance(why, str) and why.strip() else ""))
    return out


def stop_rows(values: dict, returns: dict) -> list:
    """止めの語 [{at, word}]: line の script の止めの語と、block の返りの stop_reason（judge・修正の各段・spec check の人待ちの語）。修正の段の at は
    段の種類で引く node の名（stages.nodes。fix・refix-run・返した段の back-<k>-fix）"""
    out = [{"at": node, "word": word} for node, word, _ in stop_returns(values)]
    stages = [as_dict(s) for s in _list(as_dict(returns.get("fix")).get("stages"))]
    for at, s in zip(stageslib.nodes(stages), stages):
        word = as_dict(s.get("fix")).get("stop_reason")
        if isinstance(word, str) and word:
            out.append({"at": at, "word": word})
    spec = as_dict(values.get("spec_check"))
    if spec and [q for q in _list(spec.get("questions")) if isinstance(q, str) and q.strip()]:
        out.append({"at": "spec-check-run", "word": stopby.SPEC_CHANGED})
    seen, kept = set(), []
    for row in out:
        key = (row["at"], row["word"])
        if key not in seen:
            seen.add(key)
            kept.append(row)
    return kept


def plan_nothing_owed(returns: dict) -> bool:
    return as_dict(returns.get("plan")).get("status") == "nothing_owed"


def plan_gave_up(returns: dict) -> bool:
    """計画が直す単位を受けたのに修正案を出せなかった（直す義務 0 件の周は諦めでない）"""
    plan = returns.get("plan")
    return isinstance(plan, dict) and plan.get("ok") is not True and plan.get("status") in ("gave_up", "failed", "held") \
        and bool(_units(returns)) and not plan_nothing_owed(returns)


def review_fell(returns: dict) -> bool:
    """計画は通ったのに事前審査が諦めた・落ちた周（plan-out の review_status）"""
    plan = as_dict(returns.get("plan"))
    return plan.get("status") == "ok" and plan.get("review_status") in ("gave_up", "failed")


def halt_rows(returns: dict) -> list:
    """line が返りの欄から読んだ止め: 往復が進まない（修正へ進まなかった run）・計画の諦め・封じと置きの ok でない"""
    out = []
    plan = as_dict(returns.get("plan"))
    if (plan.get("stalled") is True or review_fell(returns)) and returns.get("fix") is None:
        # 事前審査が諦めた・落ちた周も往復が進まない止め（今の事前審査は諦めた周を stalled で返した。元の boardview の verdict）
        out.append({"at": "plan-review", "word": stopby.PLAN_CONVERGE})
    if plan_gave_up(returns):
        sr = plan.get("stop_reason")
        out.append({"at": "plan", "word": sr if isinstance(sr, str) and sr else GIVE_UP})
    for rid in ("sealed-diff", "applied-diff"):
        if isinstance(returns.get(rid), dict) and returns[rid].get("ok") is False:
            out.append({"at": NODE_OF[rid], "word": NOT_OK})
    return out


def _question_rows(items, *, push: bool = False) -> list:
    """独立の目の問いの要素（字でも {text, title} の行でも。plainask の読み口）を {text, title} の行にする。本文が空の物は落とす。
    題は読み口が 1 行に畳み、無ければ None。push が真（R2 の問い）なら行の欄 recommend も持ち回る（R4 の問いは欄を持たない）"""
    import plainask
    return [{"text": plainask.item_text(q), "title": plainask.item_title(q),
             **({"recommend": plainask.item_recommend(q)} if push and plainask.item_recommend(q) is not None else {})}
            for q in _list(items) if plainask.item_text(q).strip()]


def eye_questions(returns: dict) -> list:
    """R4 の問い [{text, title}]（要素が字でも行でも読む。本文が空の物は落とす）"""
    return _question_rows(as_dict(returns.get("eyes")).get("questions"))


def means_questions(returns: dict, gates: dict) -> list:
    """R2 の頼みどおりの違いの問いのうち、答えを得ていない物 [{text, title}]（計画 means-answers の 6.3 の 3）。最後の承認ノードの continue / stop が
    そのまま答えなので、答えた run は空。R2 が redesign-needed の run は差分が当たらない（決め small-core）ので答えに数えず全部"""
    import answer
    import seal
    eyes = as_dict(returns.get("eyes"))
    qs = _question_rows(eyes.get("means_questions"), push=True)
    decided = as_dict(gates.get("gate-final")).get("decision") in (*answer.GO_WORDS, *answer.STOP_WORDS)
    return [] if decided and as_dict(eyes.get("r2")).get("status") != seal.REDESIGN else qs


def wait_rows(values: dict, returns: dict) -> dict:
    """人待ち {conflicts, conflicts_if_closed, others}"""
    asked = asked_conflicts(returns, closed=False)
    waiting = waiting_conflicts(returns)
    others = []
    if as_dict(as_dict(returns.get("eyes")).get("premise_check")).get("verdict") == "escalate":
        others.append({"at": "eyes", "word": "premise-escalate"})
    if eye_questions(returns):
        others.append({"at": "eyes", "word": "r4-ask"})
    if means_questions(returns, gates_of(values)):
        others.append({"at": "eyes", "word": MEANS_WAIT})
    # 修正前に人に聞く物（載せなかった台帳の問いか、承認ノードに載せた行）が残ったまま、答えも修正も無い run（今の outcome._waits の
    # 事前審査の ask_human。ask_human は関所の項目と諦めた往復の行を持った）
    before = as_dict(values.get("ask_before_fix"))
    pending = _list(before.get("deferred")) or _list(before.get("asked"))
    if pending and returns.get("fix") is None and as_dict(values.get("answer_before_fix")).get("answer") is None:
        others.append({"at": "plan-review", "word": "ask-human"})
    return {"conflicts": [{"at": "fix", "word": stopby.CONFLICT}] if asked else [],
            "conflicts_if_closed": [{"at": "fix", "word": stopby.CONFLICT}] if waiting else [], "others": others}


def _chain_cuts(returns: dict) -> list:
    """返りの続きが切れている所 [(後の段の役の名, 文)]"""
    out = []
    for row in STAGES:
        before, flag, after = row["before"], row["flag"], row["after"]
        if row.get("needs") and returns.get(row["needs"]) is None:
            continue
        got = latest(returns, before)
        if row.get("held") and as_dict(got).get(row["held"]) is False:
            continue
        if got and (flag is None or got.get(flag) is True) and latest(returns, after) is None:
            if after == "sealed-diff" and as_dict(returns.get("fix")).get("no_fix"):
                continue   # 直す物が無い周は封じない（merge-seal の when:）
            out.append((after, row["text"]))
    return out


def cut_row(returns: dict) -> dict | None:
    """段の表の続きの切れ目（最初の段の返りが無い run はそこで切れている）"""
    first = STAGES[0]["before"]
    spec_run = bool(as_dict(returns.get("start")).get("spec_table"))   # 仕様駆動の run は判定の graph を回さない（止めは spec の node が名乗る）
    if returns.get("start") and as_dict(returns.get("start")).get("input") is not None and latest(returns, first) is None \
            and returns.get("fix") is None and returns.get("before-tests") is not None and not spec_run:
        return {"at": NODE_OF[first], "word": CHAIN_CUT}
    cuts = _chain_cuts(returns)
    return {"at": NODE_OF.get(cuts[0][0], cuts[0][0]), "word": CHAIN_CUT} if cuts else None


def chain_notes(returns: dict) -> list:
    return [text for _, text in _chain_cuts(returns)]


def no_fix(returns: dict) -> bool:
    """直す物が無い周: fixed が直す物の無い形か、判定が ready でなく止めの語も無いか、直す単位が 0か、テーマの run で承認された設計に変える所が
    無い（設計だけの結末）"""
    if as_dict(returns.get("fix")).get("no_fix") is True or as_dict(returns.get("theme_descend")).get("no_change") is True:
        return True
    j = latest(returns, "judge")
    return bool(j) and ((j.get("ready") is False and not j.get("stop_reason")) or not _units(returns))


def proved(returns: dict) -> bool:
    """最後のテストの ok と green が真で、差分を封じた（封じた差分の返りの ok が真）"""
    final, seal = as_dict(returns.get("final-tests")), as_dict(returns.get("sealed-diff"))
    return final.get("ok") is True and final.get("green") is True and seal.get("ok") is True


# ---------------------------------------------------------------- 冒頭の句（元 runreport）
def _parked(returns: dict) -> list:
    return [g for g in _list(as_dict(returns.get("fix")).get("groups")) if isinstance(g, dict) and g.get("returned") is False]


def _repaired(returns: dict) -> list:
    return [g for g in _list(as_dict(returns.get("fix")).get("groups"))
            if isinstance(g, dict) and g.get("returned") is True and as_dict(g.get("clash")).get("outcome") == "repaired"]


def _backed_out(returns: dict) -> list:
    return [g for g in _parked(returns) if _list(g.get("backed_out"))]


def _unrestored(returns: dict) -> list:
    return [g for g in _parked(returns) if _list(g.get("unrestored"))]


def split_line(returns: dict) -> str:
    """冒頭の 1 行目に添える、修正の段が受けた単位と止めて持ち越した単位の 1 文（元 runreport.split_line）"""
    groups = [g for g in _list(as_dict(returns.get("fix")).get("groups")) if isinstance(g, dict)]
    parked = _parked(returns)
    repaired = f"{REPAIRED_HEAD}: 組 {'・'.join(str(g.get('group_id')) for g in got)}" if (got := _repaired(returns)) else ""
    if not parked:
        return repaired
    kept = [str(u) for g in groups if g.get("returned") is True for u in _list(g.get("unit_ids"))]
    held = [str(u) for g in parked for u in _list(g.get("unit_ids"))]
    marked = [(head, gs) for head, gs in ((BACKED_OUT_HEAD, _backed_out(returns)), (UNRESTORED_GROUP_HEAD, _unrestored(returns))) if gs]
    return (f"修正の段は {len(kept)} 単位（{'・'.join(kept) or 'なし'}）を受け、{len(held)} 単位"
            f"（{'・'.join(held)}）を止めて持ち越した（組 {'・'.join(str(g.get('group_id')) for g in parked)}。次の run の依頼に載る）"
            + "".join(f"。{head}: 組 {'・'.join(str(g.get('group_id')) for g in gs)}" for head, gs in marked)
            + (f"。{repaired}" if repaired else ""))


def uncompared_rows(returns: dict) -> list:
    """当てたままの組の行の uncompared（確かめ直しで直す前の版と比べられなかったので組を戻す理由にしなかった赤の鍵。fix の #846）を
    1 件 1 行「<鍵>（組 <group_id>・単位 <unit_ids>）」に（人が決めること）"""
    return [f"{k}（組 {g.get('group_id')}・単位 {'・'.join(str(u) for u in _list(g.get('unit_ids'))) or 'なし'}）"
            for g in _list(as_dict(returns.get("fix")).get("groups")) if isinstance(g, dict) and g.get("returned") is True
            for k in _list(g.get("uncompared")) if isinstance(k, str)]


def unrestored_lines(returns: dict) -> list:
    import oneline
    out = []
    for g in _unrestored(returns):
        units = "・".join(str(u) for u in _list(g.get("unit_ids"))) or "なし"
        out += [f"{UNRESTORED_GROUP_HEAD}: 組 {g.get('group_id')}（単位 {units}）。当たったままのパス {'・'.join(map(str, _list(g.get('unrestored'))))}",
                f"  - 訳: {oneline.one_line(g.get('reason') or '訳の記録が無い')}"]
    return out


def backed_out_lines(returns: dict) -> list:
    import oneline
    kept = [g for g in _list(as_dict(returns.get("fix")).get("groups")) if isinstance(g, dict) and g.get("returned") is True]
    out = []
    for g in _backed_out(returns):
        units = "・".join(str(u) for u in _list(g.get("unit_ids"))) or "なし"
        mark = as_dict(g.get("clash"))
        said = (f"合わせ役が直せず、組どうしの合わせの申し出 {'・'.join(map(str, _list(mark.get('requests'))))} にした（控えの差分 {mark.get('patch')}）"
                if mark.get("outcome") == "parked" else "合わせ役が直していない")
        out += [f"{BACKED_OUT_HEAD}: 組 {g.get('group_id')}（単位 {units}）。戻したパス {'・'.join(map(str, _list(g.get('backed_out'))))}",
                f"  - 赤: {oneline.one_line(g.get('reason') or '訳の記録が無い')}",
                f"  - 合わせの結果: {said}。ほかの組は {len(kept)} 組を当てたまま、外した単位 {units} は次の run の依頼に回した"]
    return out


def _pushed(gates: dict) -> list:
    import answer
    return [(at, rec) for at, g in gates.items() for rec in (as_dict(g).get(answer.PUSHED) or []) if isinstance(rec, dict)]


def pushed_lines(gates: dict, taken=()) -> list:
    """「人が決めること」の頭に、無人の run が採った推しを 1 件 1 行（元 runreport._pushed_lines）"""
    import gatemarks
    import oneline
    return [*(f"無人の run で推しを採って通した（承認ノード {named(at)}）: {oneline.one_line(r.get('item') or '')}——"
              f"{gatemarks.RECOMMEND_WORDS.get(r.get('answer'), '')}（{r.get('answer')}）: {r.get('note')}（推す理由: {r.get('why')}）。"
              "違えば次の run の依頼で直す" for at, r in _pushed(gates)),
            *(f"無人の run で推しを採って答えた（{gatemarks.ASK_HEAD} {q.get('key')}）: 推し: {oneline.one_line(push)}——出どころ・depends の"
              f"単位 {'・'.join(keep) or '（今の周の単位に無い）'} を直す義務に戻した。違えば次の run の依頼の answers で直す"
              for q, push, keep in taken)]


def pushed_said(gates: dict, taken=()) -> str:
    got = _pushed(gates)
    where = "中身は「1. 人が決めること」のセクション"
    said = [f"無人の run で推しを採って通した承認ノード: {'・'.join(dict.fromkeys(plain(at) for at, _ in got))}（推し {len(got)} 件。{where}）"] if got else []
    if taken:
        said.append(f"無人の run で推しを採って答えた台帳の問い: {'・'.join(str(q.get('key')) for q, _, _ in taken)}（推し {len(taken)} 件。{where}）")
    return "。".join(said)


def script_fall_notes(values: dict) -> list:
    """line の script が落ちて（止めの語 works:line-script）返した訳の行。今は fix-in が reason を運ぶ（壊れた始めの記録 start.json の名など）。
    止めの語の行は語の意味しか言わないので、訳は problems に名指しで出す"""
    import oneline
    return [f"{node} の script が落ちた（{oneline.one_line(why)}）" for node, word, why in stop_returns(values)
            if word == stopby.LINE_SCRIPT and why]


def node_names() -> dict:
    """node の id → 人が読む言葉の表（nodenames.json。報告の最初の 3 行に出る名に、初見の読み手向けの訳を付ける）"""
    return json.loads((pathlib.Path(__file__).parent / "nodenames.json").read_text(encoding="utf-8"))


def named(at: str) -> str:
    """node の id に人が読む言葉を前に付ける（「訳（id）」。表に無い id はそのまま）。頭の外の節の行に使う（頭には plain を使う）"""
    plain = node_names().get(at)
    return f"{plain}（{at}）" if plain else at


def plain(at: str) -> str:
    """node の id の人が読む言葉（id は付けない）。報告の頭の行に使う。表に無い id も字で出さない（試験が全部の id に行が在ることを縛る）"""
    return node_names().get(at) or UNNAMED_NODE


def stop_meaning(word) -> str:
    """止めの語（works: の頭は付いていても無くてもよい）の人が読む意味。表に無い語は UNKNOWN_STOP。語から意味を引く読みはここだけ"""
    return stopby.REASONS.get(str(word).removeprefix(stopby.HEAD), UNKNOWN_STOP)


def stop_words(stops: list) -> list:
    """止めの語ごとの 1 行（頭の行）: 人が読む言葉の node の名を並べ、語の意味を言う。node の id と止めの語の字は出さない（頭の外の
    stop_words_full の行に残る）"""
    by_word = {}
    for s in stops:
        by_word.setdefault(str(s["word"]), []).append(plain(s["at"]))
    return [f"{'・'.join(dict.fromkeys(ats))}が止めた: {stop_meaning(word)}"
            for word, ats in by_word.items()]


def stop_words_full(stops: list) -> list:
    """止めの語の行の全部（頭の外の節の行）: 「訳（node の id） が 止めの語（意味）」"""
    return [f"{named(s['at'])} が {s['word']}（{stop_meaning(s['word'])}）" for s in stops]


def _unpassed(returns: dict) -> list:
    import seal
    eyes = as_dict(returns.get("eyes"))
    return [(name.upper(), e) for name in EYE_NAMES if isinstance(e := eyes.get(name), dict) and e.get("status") != seal.PASSED]


def unpassed_full(returns: dict) -> list:
    """通さなかった目の行の全部（頭の外の節の行）: 目の印・状態の語・理由の全文"""
    import gatemarks
    import oneline
    return [f"独立の目が通さなかった理由の全文: {gatemarks.eye_named(label, e.get('status'))}——{oneline.one_line(e.get('reason') or '理由なし')}"
            for label, e in _unpassed(returns)]


def plain_reasons(reasons: list) -> list:
    """最後の承認ノードを開ける理由の文の、目の印（R1 など）を何を見る目かの言葉に（頭の行に出す形）"""
    import gatemarks
    import re
    return [re.sub(r"\b(R[1-4])\b", lambda m: gatemarks.EYES[m.group(1)], str(x)) for x in reasons]


def stopped_why(returns: dict, stops: list, final_reasons: list) -> list:
    """止まった run の冒頭 1 行目に足す訳: 止めの語・最後の承認ノードを開ける理由・通さなかった目。名前は人の言葉で言い、目の指摘の長い文は
    1 行の要約（何を見る目がどの状態か）にして、全文は頭の外の節に置く（unpassed_full）"""
    import gatemarks
    unpassed = [f"{gatemarks.EYES.get(label, '独立の目')}が通さなかった（{gatemarks.REVIEW_WORDS.get(str(e.get('status')), '状態の語を読めない')}）"
                for label, e in _unpassed(returns)]
    reasons = plain_reasons(final_reasons)
    return [*stop_words(stops), *(["開けた理由: " + "・".join(reasons)] if reasons else []),
            *unpassed, *([UNPASSED_WHERE] if unpassed else [])]


def head_notice(kind: str, text: str = "", **slots) -> dict:
    """報告の頭の知らせの 1 行 {kind, slots, text}。kind は頭の表 head.Notice の値、slots は種の差し込み口の値（読み手の世界の値だけ）、text は
    返りの訳を 1 行に畳んだ字で、頭には出ず報告の節「2. 止めたか」に載る（種の意味の句は持たない。それは表の文）"""
    import oneline
    return {"kind": kind, "slots": slots, "text": oneline.one_line(text)}


def first_word(cmd) -> str:
    """試験のコマンドの最初の語（読みは lib の住処 tree_run.first_word。前置きの NAME=値 は出さない。値に秘密が混じりうる）。
    字面から引けなければ NO_CMD"""
    import tree_run
    got = tree_run.first_word(str(cmd or ""))
    return got[0] if got else NO_CMD


def ran_notes(returns: dict) -> list:
    """最後のテストが走っていない・走ったと確かめられていない時の知らせ（本文は green_cert.ran_note）"""
    import green_cert
    fin = as_dict(returns.get("final-tests"))
    note = (green_cert.ran_note(green=fin.get("green") is True, red_cause=fin.get("red_cause") or "", by=fin.get("by") or "",
                                steps=fin.get("ran_steps")) if fin else "")
    return [head_notice("tests_not_run", note)] if note else []


def spoken_stops(values: dict, returns: dict, record: dict | None = None) -> list:
    """頭に知らせを出す止め [head_notice の行]: 表 HEAD_NOTICE に在る止めの語（入口が入力を断った止めと、修正前の承認の一言の向きで止めた止め。
    訳が空でも黙らず、訳の記録が無いと言う）と、止めの語を持たずに ok を偽で返す直す前の試験の関門（試験のコマンドの最初の語を起こせない run など）だけ。
    ほかの止めの訳は頭に出さない（止めた所と語の意味は stop_words の行が言い、line の script の落ちの訳は problems に、block の止めの訳はその block の報告の行に、テーマの設計の段の訳は
    報告の設計の段の行に在る）。本文 text は返りの reason を 1 行に畳むだけで言い換えない"""
    import oneline
    out = []
    for _, word, why in stop_returns(values):
        if word in HEAD_NOTICE:
            slots = ({"quote": oneline.one_line(as_dict(as_dict(values.get("answer_before_fix")).get("answer")).get("text") or "") or NO_QUOTE}
                     if HEAD_NOTICE[word] == "answer_redirected" else {})
            out.append(head_notice(HEAD_NOTICE[word], why or NO_STOP_REASON, **slots))
            break
    base = as_dict(returns.get("before-tests"))
    if base.get("ok") is False and base.get("reason"):
        out.append(head_notice("base_gate_stopped", base["reason"], cmd=first_word(as_dict(record).get("test_cmd"))))
    return out


def suite_broken_notes(values: dict) -> list:
    """修正の段が、工場の書いた試験の起動スクリプトが書き直しても壊れたままで止めた組と、試験の実行器が無い・走らないで止めた組の
    知らせ（訳とログのパス。#836・docs/design/fix.md の 19 節・docs/plans/2026-10-24-fix-weapons.md の 3.9 の止め方の 6）。fixed の
    tdd（段ごとの組ごとの TDD の記録）の suite_broken・no_suite の行から。差し込み口は組の id とログのパス、本文は訳。無ければ空"""
    def rows(v):
        if isinstance(v, list):
            for x in v:
                yield from rows(x)
        elif isinstance(v, dict):
            yield v
    out = []
    for r in rows(as_dict(values.get("fixed")).get("tdd")):
        group = str(r.get("group_id") or "—")
        if r.get("suite_broken") is True:
            note = head_notice("suite_broken", r.get("reason") or "", group=group, runner_log=str(r.get("runner_log") or NO_LOG),
                               cmd_log=str(r.get("cmd_log") or NO_LOG))
        elif r.get("no_suite") is True:
            note = head_notice("no_suite", r.get("reason") or "", group=group)
        else:
            continue
        if note not in out:
            out.append(note)
    return out


def gate_line(g) -> str:
    import answer
    import oneline
    if not isinstance(g, dict):
        return "開かなかった"
    said = oneline.one_line(g.get("text") or "")
    return f"{g.get('decision')}（推しで通した: {said}）" if answer.by_push(g) else f"{g.get('decision')}（{said}）"


def eye_word(eyes: dict, name: str, eyes_due) -> str:
    e = eyes.get(name)
    if isinstance(e, dict):
        return str(e.get("status"))
    return "省いた" if eyes_due is False else "結果が無い"


# ---------------------------------------------------------------- 次の run に渡す物
def _outside(returns: dict) -> tuple[list, list, str]:
    """判定が目的の外とした所見の (次の依頼の行, 報告の行, 件数の 1 行)。控えは outpurpose の名のファイル"""
    import outpurpose
    ptr = as_dict(returns.get("judge")).get("out_of_purpose")
    if not ptr:
        return [], [], ""
    try:
        path = stageslib.resolve(ptr, "out_of_purpose")
    except stageslib.READ_ERRORS as e:
        return [], [f"目的の外の所見の控えを開けない（{e}）"], ""
    if path.name != outpurpose.FILE:
        return [], [f"目的の外の所見のファイル {path} の名が {outpurpose.FILE} でない（読まなかった）"], ""
    return (outpurpose.next_items(path.parent), outpurpose.report_lines(path.parent),
            outpurpose.count_line(path.parent, "", "判定が目的の外とした所見"))


def next_request(returns: dict, left: list, closed: bool, got: dict, carried_rows: list) -> list:
    """次の依頼の findings（元 runreport.next_request）: 残りの行（R2 の作り直しの行は前の失敗にだけ）・目的の外の所見・親の木へ戻せ
    なかった組・再審の行（judged の carry）・差分の審査とレンズが残した穴（fixed の carry）・人に回した申し出の単位"""
    import oneline
    import report
    asked = _asked_rows(returns, closed)
    owned = {f"修正 {r['where']}" for r in asked}
    items = [{"where": r["where"], "text": r["text"]} for r in left if not report._r2_redesign(r) and r["where"] not in owned]
    items += _outside(returns)[0]
    items += [{"where": f"{GROUP_WHERE} {g.get('group_id')}",
               "text": f"組 {g.get('group_id')}（単位 {'・'.join(str(u) for u in _list(g.get('unit_ids')))}）を親の木へ戻せなかった——"
                       f"直しを持ち越した: {oneline.one_line(g.get('reason') or '理由の記録が無い')}"} for g in _parked(returns)]
    items += stageslib.next_items(got, carried_rows)
    items += asked
    seen, out = set(), []
    for it in items:
        k = (it["where"], it["text"])
        if k not in seen:
            seen.add(k)
            out.append(it)
    return out


def _asked_rows(returns: dict, closed: bool) -> list:
    """人に回した申し出を外した単位ごとの次の依頼の行と、途中で落ちた run の案の直しを待つ行"""
    import conflict
    import replan
    out = []
    if not closed:
        for k, r in asked_units(returns, rows=waiting_conflicts(returns)):
            out.append({"where": k, "text": f"{k}（{replan.PENDING_WHY}。裁定の文: {as_dict(r.get(conflict.RULING)).get('text') or ''}。"
                                            f"名指し {', '.join(str(x) for x in _list(r.get('between')))}。{conflict.HELD_WORK_KEPT}）"})
    asked = asked_conflicts(returns, closed)
    for k, r in asked_units(returns, closed, rows=asked):
        ruling = as_dict(r.get(conflict.RULING))
        why = r.get(conflict.REPLAN_WHY)
        out.append({"where": k,
                    "text": f"{k}（{conflict.HEAD}を人に回した——{conflict.place_words(conflict.unit_rows(asked, k))}。"
                            f"裁定の文: {ruling.get('text') or ''}。名指し {', '.join(str(x) for x in _list(r.get('between')))}"
                            + (f"。案の直し: {why}" if why else "") + "）"})
    return out


def prior_failures(returns: dict, left: list, stops: list) -> list:
    """前の失敗 [{where, text}]（元 runreport.prior_failures）"""
    import carry
    import fixboard
    import oneline
    import report
    rows = [{"where": f"{GAVE_UP_WHERE} {u.get('unit_id')}", "text": oneline.one_line(u.get("reason") or "理由の記録が無い")}
            for u in _list(as_dict(returns.get("fix")).get("units")) if isinstance(u, dict) and u.get("status") == fixboard.GIVEN_UP]
    gave_up = plan_gave_up(returns)
    items = [{"where": f"案の直しを終えられなかった項目 {r.get('item')}", "text": oneline.one_line(f"{r.get('why')}。裁定の文: {r.get('ruling')}")}
             for rid in ("replan", "replan-review-result") for r in _list(as_dict(returns.get(rid)).get("gave_up")) if isinstance(r, dict)]
    rows += items
    if gave_up and not items:
        sr = as_dict(returns.get("plan")).get("stop_reason")
        rows.append({"where": PLAN_GAVE_UP_WHERE,
                     "text": "計画が直す単位を受けたのに修正案を出せなかった（受け付けが網の回まで拒み続けたか、行き止まりの単位が在る）"
                             + (f": {sr}" if isinstance(sr, str) and sr else "")})
    rows += [{"where": f"{STOPPED_WHERE} {s['at']}",
              "text": f"{s['word']}（{stop_meaning(s['word'])}）"}
             for s in stops if stopby.is_line(s["word"]) and s["word"] not in stopby.WAITING and not (gave_up and s["at"] in ("plan", "replan"))]
    r2 = [r for r in left if report._r2_redesign(r)]
    if r2:
        rows.append({"where": carry.REDESIGN_WHERE, "text": oneline.one_line(r2[0]["text"])})
    return rows


def constraints_of(returns: dict, run_id: str) -> list:
    """前提の検算が偽と示した仮定の実測を次の run の制約に（E37。eyes の premise_check の facts）"""
    import carry
    facts = as_dict(as_dict(returns.get("eyes")).get("premise_check")).get("facts")
    return carry.carried_constraints(facts if isinstance(facts, list) else [], run_id)


# ---------------------------------------------------------------- 人が決めることの節の後ろの行（元 runreport の _decisions の後ろ）
# 写さない行（同じ行を block の report が返す。報告から行は落ちない）: verify_lines（verify の block の report。judge の graph の節
# 「判定の単位の裏取り」）・premise_lines（premises の block の report。節「前提の実測」）・_design_lines（independent-design の block の
# report。節「独立設計」）・_pr_draft_lines（parallel-pr の block の report。節「並行 PR」）・_converge_lines（line の rounds.lines。節「計画の往復」）
DEFERRED_HEAD = "無人の run で修正前の承認ノードに載せずに報告へ回した問い（承認ノードを開かずに修正へ進めた）"
FINAL_REASONS_HEAD = {True: "最後の承認ノードを開ける理由（無人の run では開かずに止めた理由）", False: "最後の承認ノードを開けた理由"}  # 無人の run か → 見出し
EYE_PASSES_HEAD = ("修正前の承認ノードで通した行（人が通したか、無人の run が推しで通したので、独立の目 R4 の問いから外して聞き直さ"
                   "なかった行。どちらかは行ごとに書く）")


def _counted(head: str, rows: list) -> list:
    """見出しの件数の行と 1 件 1 行（rows が空なら何も出さない）"""
    import oneline
    return [f"{head}: {len(rows)} 件", *[f"  - {oneline.one_line(x)}" for x in rows]] if rows else []


def conflict_line(returns: dict) -> str:
    """申し出の件数と裁定・種類の内訳（元 runreport._conflict_line）"""
    import conflict
    rows, _ = conflict_rows(returns)
    c, k = conflict.counts_of(rows), conflict.kind_counts_of(rows)
    plan_n = f"・案の項目を直す（{conflict.REPLAN}）{c[conflict.REPLAN]}" if conflict.REPLAN in c else ""
    swap = f"・問いを置き換える（{conflict.REPLACE}）{c[conflict.REPLACE]}" if conflict.REPLACE in c else ""
    swap += f"・判定をやり直す（{conflict.REJUDGE}）{c[conflict.REJUDGE]}" if conflict.REJUDGE in c else ""
    kinds = [f"{x} {k[x]}" for x in conflict.DIV_KINDS] + ([f"種類なし {k[conflict.UNSET]}"] if conflict.UNSET in k else [])
    return (f"{conflict.HEAD}: {c['parked']} 件（裁定の内訳。括弧は記録の名: テストの直しを許す（fix_test_scope）"
            f"{c['fix_test_scope']}・コードをこう直す（fix_code_as）{c['fix_code_as']}・人に回す（ask_human）{c[conflict.ASK]}"
            f"{swap}{plan_n}・裁定なし {c['unruled']}）。種類の内訳: " + "・".join(kinds))


def unproven_lines(returns: dict) -> list:
    """例で証明できない判定の問いの行（今の判定の judgment から。行は src/final.py の unproven_lines。最後の承認ノードと同じ口）"""
    import querytest
    from src import final
    return _counted(querytest.UNPROVEN_HEAD, final.unproven_lines(as_dict(latest(returns, "judge")).get("judgment")))


def pr_lines(returns: dict) -> list:
    """並行 PR と重なるので外した範囲（判定の出力の欄 excluded の先。元 runreport.pr_lines。parallel-pr の block の report は外した範囲を
    並べないので line が組む）"""
    doc, why = read_ptr(as_dict(returns.get("judge")).get("excluded"), "excluded")
    if why:
        return [f"並行 PR と重なるので外した範囲: {why}"]
    rows = doc.get("excluded") if isinstance(doc, dict) else doc
    return [f"並行 PR #{x.get('pr')} と重なるので外した範囲: {x.get('file')}:{x.get('start')}-{x.get('end')}（{x.get('why') or ''}）"
            for x in _list(rows) if isinstance(x, dict)]


def inner_word_lines(diff_ptr, known) -> list:
    """直しの差分が足した行のうち works の内側の語を含む行（元 runreport.inner_word_lines。対象が直す前の版で既に使う語 known(語) は
    数えない）。差分が無い・当たりが無ければ空。差分が読めなければその行"""
    import report
    if not diff_ptr:
        return []
    try:
        text = stageslib.resolve(diff_ptr, "diff").read_text(encoding="utf-8", errors="replace")
    except (OSError, *stageslib.READ_ERRORS) as e:
        return [f"差分が読めない（{type(e).__name__}）——内側の語を確かめていない"]
    rows = [f"{h['path']}:{h['line']}（{'・'.join(h['words'])}）: {h['text']}" for h in report.inner_word_hits(text, known)]
    return [f"{report.INNER_WORDS_HEAD}: {len(rows)} 件", *[f"  - {r}" for r in rows]] if rows else []


def gate_passes(values: dict, returns: dict) -> list:
    """修正前の承認ノードが聞かずに通した行（ask-before-fix の passes。line が組む。元 runreport._gate_passes）と、人が通したので独立の
    目 R4 の問いから外した行（eyes の passes）"""
    import gatemarks
    out = []
    ask = values.get("ask_before_fix")
    if isinstance(ask, dict):
        rows = _list(ask.get("passes"))
        out.append(f"修正前の承認ノードが聞かずに通した行（gate-before-fix）: {len(rows)} 件")
        out += [f"  - {x}" for x in gatemarks.pass_lines(rows)]
    eyes = returns.get("eyes")
    if isinstance(eyes, dict) and _list(eyes.get("passes")):
        rows = _list(eyes.get("passes"))
        out += [f"{EYE_PASSES_HEAD}: {len(rows)} 件", *[f"  - {x}" for x in gatemarks.pass_lines(rows)]]
    return out


def amend_lines(values: dict, returns: dict, gates: dict, closed: bool) -> list:
    """同じ run の中で直した修正案の項目ごとの 1 行（元 runreport._amend_lines。lib/replan.amend_lines）"""
    import conflict
    import replan
    fix = as_dict(returns.get("fix"))
    items = [str(i) for i in _list(fix.get("replan_items"))]
    whys = {}
    for r in conflict_rows(returns)[0]:
        why = r.get(conflict.REPLAN_WHY)
        for n in map(str, conflict.ruled_items(r)):
            if isinstance(why, str) and why:
                whys.setdefault(n, why)
    rows = replan.amend_lines(items, refixed=fix.get("refixed") is True, answer=gates.get("gate-replan"),
                              widened=_list(as_dict(values.get("ask_replan")).get("widened")), whys=whys, pending=not closed,
                              gate="gate-replan")
    return _counted(replan.AMEND_HEAD, rows)


def more_lines(values: dict, returns: dict, gates: dict, *, closed: bool, unattended: bool, cwd=None) -> list:
    """人が決めることの節の後ろの行: 申し出の内訳・例で証明できない問い・外した範囲・内側の語・聞かずに通した行・直した案の項目・
    載せなかった問いと最後の承認ノードを開ける理由"""
    import report
    rev = str(as_dict(as_dict(values.get("start")).get("ports")).get("base_rev") or "")
    out = [conflict_line(returns), *unproven_lines(returns), *pr_lines(returns)]
    out += inner_word_lines(as_dict(returns.get("fix")).get("diff"), lambda w: report.target_uses(cwd, rev, w) if cwd else False)
    out += gate_passes(values, returns)
    out += amend_lines(values, returns, gates, closed)
    out += _counted(DEFERRED_HEAD, [_deferred_said(q) for q in _list(as_dict(values.get("ask_before_fix")).get("deferred"))])
    out += _counted(FINAL_REASONS_HEAD[unattended], [str(r) for r in _list(as_dict(values.get("ask_final")).get("reasons"))])
    return out


def _deferred_said(q) -> str:
    """載せなかった問いの要素（字か {text, title} の行）の報告の行（行は本文。題は報告の頭に出る）。読めない形は JSON の字のまま"""
    import plainask
    return plainask.item_text(q) or (q if isinstance(q, str) else json.dumps(q, ensure_ascii=False))


# ---------------------------------------------------------------- 人が決めること
class AskRow(typing.NamedTuple):
    """人が決める物の 1 行: text は 1 行に畳んだ本文、title は本文を書いた所の題（読み口が畳んだ字。無ければ None）、push は問いの種の行
    （推しの句を足す）、recommend は行の欄の推し（gatemarks.recommend_of が検めた値。無ければ None）、reason_push は台帳の問いの理由の推し
    （本文が理由を載せているので句は足さず、推しが在ることだけを言う表示の欄。無ければ None）"""
    text: str
    title: str | None = None
    push: bool = False
    recommend: dict | None = None
    reason_push: str | None = None


def _rows(items, *, push: bool = False, titles=None, recommends=None, reason_pushes=None) -> list:
    """items の各要素を AskRow に（本文は _item_said を 1 行に畳む）。titles・recommends・reason_pushes は要素の並びと同じ長さの題・検めた推し・
    台帳の問いの理由の推しの並び"""
    import oneline
    return [AskRow(oneline.one_line(_item_said(x)), (titles[i] if titles else None), push, (recommends[i] if recommends else None),
                   (reason_pushes[i] if reason_pushes else None)) for i, x in enumerate(items)]


def _vetted(x) -> dict | None:
    """行の欄 recommend を gatemarks.recommend_of で検めた値（字の要素・欄の無い行・崩れた欄は None）"""
    return gatemarks.recommend_of(x) if isinstance(x, dict) else None


def ask_groups(values: dict, returns: dict, gates: dict, *, book, hits: list, unreturned: list, closed: bool) -> dict:
    """人が決める物の種ごとの行 {種: [AskRow]}（空の種も鍵に持つ。種を表 ASK_SOURCES の順に並べるのは decisions）。book（問いの台帳の見え方 ledger）・
    hits（守ると決めたファイルに当たった差分）・unreturned（直しの対象に戻せなかった単位）は decisions が 1 度だけ求めた物を受ける。仕様を確かめる役の問いの
    種の見出しは入力で 2 つの一方になる（gatemarks.spec_words）。題はここで集める行ごとの出どころから付ける: 判定の役の問い（保留にしたままの問い）は
    台帳の問いの title、載せなかった修正前の問いと独立の目の問いは行の title、修正の役の申し送りは fix の出力の handoff_titles（ここで 1 度だけ
    行にする）。どれも plainask.item_title が 1 行に畳む。保留の行の後ろの unreturned_lines の行は問いを持たないので題なし"""
    import oneline
    import plainask
    deferred = _list(as_dict(values.get("ask_before_fix")).get("deferred"))
    plan_raw = [plainask.item_text(q) for q in deferred]   # 保留の行と重なる問いを引く鍵（畳む前の字）
    spec = as_dict(values.get("spec_check"))
    spec_qs = [q for q in _list(spec.get("questions")) if isinstance(q, str) and q.strip()]
    spec_head = SPEC_HEADS[bool(spec_qs) and spec.get("unchecked") is not False]
    held_qs = gatemarks.held_questions(book)
    lines_ = gatemarks.held_lines(book)
    held = [*zip(held_qs, lines_), *((None, line) for line in lines_[len(held_qs):])]
    held = [(q, line) for q, line in held if q is None or not any(x.startswith(gatemarks._prefix(q)) for x in plan_raw)]
    fix = as_dict(returns.get("fix"))
    handoffs = [x for x in _list(fix.get("handoffs")) if isinstance(x, str)]
    handoff_titles = as_dict(fix.get("handoff_titles"))
    premise = as_dict(as_dict(returns.get("eyes")).get("premise_check"))
    eyes_ = eye_questions(returns)
    means = means_questions(returns, gates)

    def unrest(head: str, rows: list) -> list:
        return [AskRow(x.removeprefix(f"{head}: ")) for x in rows if x.startswith(f"{head}: ")]

    return {
        UNRESTORED_GROUP_HEAD: unrest(UNRESTORED_GROUP_HEAD, unrestored_lines(returns)),
        BACKED_OUT_HEAD: unrest(BACKED_OUT_HEAD, backed_out_lines(returns)),
        spec_head: _rows(spec_qs, push=True),
        PLAN_KIND: _rows([plainask.item_text(q) for q in deferred], push=True, titles=[plainask.item_title(q) for q in deferred],
                         recommends=[_vetted(q) for q in deferred], reason_pushes=[plainask.item_reason_push(q) for q in deferred]),
        EYE_ASK_HEAD: _rows([q["text"] for q in eyes_], push=True, titles=[q["title"] for q in eyes_]),
        MEANS_ASK_HEAD: _rows([q["text"] for q in means], push=True, titles=[q["title"] for q in means],
                              recommends=[_vetted(q) for q in means]),
        HELD_KIND: _rows([line for _, line in held], push=True, titles=[plainask.item_title(q) if q else None for q, _ in held],
                         reason_pushes=[(gatemarks.reason_push(q) or None) if q else None for q, _ in held]),
        CONFLICT_ASK_HEAD: _rows(asked_conflicts(returns, closed)),
        fixboard.HANDOFF_HEAD: _rows(handoffs, titles=[plainask.item_title({"title": handoff_titles.get(x)}) for x in handoffs]),
        PROTECTED_HITS_HEAD: _rows(hits[:5]),
        UNRETURNED_KIND: _rows(unreturned),
        UNCOMPARED_HEAD: _rows(uncompared_rows(returns)),
        ESCALATED_KIND: _rows([premise] if premise.get("verdict") == "escalate" else []),
    }


def _push_clause(row: AskRow, *, said: bool = False) -> str:
    """行の本文の後ろに足す推しの句。欄 recommend が在れば検めた推し。欄が無い問いの種の行は「判定の役が書いていない」（行の本文か台帳の問いの理由が
    推しを載せている行〔reason_push〕と、本文が既にその句を言っている行には足さない）。said が真（報告の頭の行）は、推しの在る行にだけ足す"""
    if row.recommend is not None:
        return f"——{gatemarks.PUSH}{gatemarks._words(row.recommend)}"
    if said or not row.push or row.reason_push or gatemarks.PUSH + gatemarks.NO_PUSH in row.text:
        return ""
    return f"——{gatemarks.PUSH}{gatemarks.NO_PUSH}"


def ask_title(kind: str, row: AskRow) -> str | None:
    """行の題。出どころは表 ASK_SOURCES: 行の title の欄・決まった字（行ごとの値を差し込まない）・題なし（種の名に戻す）。空白だけの題は題なし"""
    source = ASK_SOURCES[kind]
    title = row.title if source is ROW_TITLE else None if source is KIND_NAME else source
    return title if isinstance(title, str) and title.strip() else None


def decisions(values: dict, returns: dict, gates: dict, *, unattended: bool, left: list, closed: bool, got: dict,
              taken: list, cwd=None) -> tuple[dict, list, dict, list]:
    """(decisions {before, after, outside}, asks [{kind, text, title?}], tallied, counted_left)。種の順と題の出どころは表 ASK_SOURCES、種ごとの行は
    ask_groups が集める。結末で決まる塊（人が確かめる物・直しきれずに
    残った物・記録が通らないこと）は report が足す（report の設計書の 1.2 の asks）"""
    b = ledger(returns, gates, unattended)
    fix = as_dict(returns.get("fix"))
    unreturned = [u for u in _list(fix.get("units")) if isinstance(u, dict) and u.get("status") == fixboard.NOT_DONE]
    seal = as_dict(returns.get("sealed-diff"))
    hits = [str(h) for h in _list(seal.get("protected_hits"))]
    hit_count = seal.get("protected_count") if isinstance(seal.get("protected_count"), int) else len(hits)
    tallied = {PROTECTED_HITS_HEAD: hit_count} if hit_count else {}
    groups = ask_groups(values, returns, gates, book=b, hits=hits, unreturned=unreturned, closed=closed)
    before = [*pushed_lines(gates, taken), *unrestored_lines(returns), *backed_out_lines(returns)]
    asks, emitted = [], set()
    for kind in ASK_SOURCES:   # 種の順と題の出どころは表の 1 か所。表に無い種は並べられない
        rows = groups.get(kind) or []
        if not rows:
            continue
        emitted.add(kind)
        if kind not in OWN_LINES:
            before.append(f"{kind}: {tallied.get(kind, len(rows))} 件")
            before += [f"  - {row.text}{_push_clause(row, said=True)}" for row in rows]
        for row in rows:
            title = ask_title(kind, row)
            asks.append({"kind": kind, "text": row.text + _push_clause(row), **({"title": title} if title else {})})
    if HELD_KIND in emitted:
        before.append(f"  {gatemarks.ANSWER_HOW}")
    after = []
    done = gatemarks.answered_ledger_lines(b)
    if done:
        after.append(f"{gatemarks.ANSWERED_HEAD}（{len(done)} 件。保留と人が決めることの件数には数えない）:")
        after += [f"  - {x}" for x in done]
    after += gatemarks.unmatched_answer_lines(b)
    after += gatemarks.unread_hold_lines(b)
    after += gatemarks.answer_tie_lines(b)
    after += _list(as_dict(values.get("judged")).get("lines"))
    after.append(f"残り: {len(left)} 件（最後のテストが緑でない・独立の目が通さなかった目と結果が無い目・修正の段の残り・直しの後の実測が"
                 "見た住処の外の知る場所の増え・測れていない素材）")
    after += stageslib.always_rows(got)
    after += [*stageslib.tests_left_lines(got), *stageslib.gates_lines(got), *stageslib.plan_ask_lines(got)]
    after += [f"修正の控え: {x}" for x in got["unread"]]
    after += more_lines(values, returns, gates, closed=closed, unattended=unattended, cwd=cwd)
    _, _, outside_count = _outside(returns)
    counted_left = [f"修正 {u.get('unit_id')}" for u in unreturned]
    return {"before": before, "after": after, "outside": [outside_count] if outside_count else []}, asks, tallied, counted_left


def _item_said(x) -> str:
    import conflict
    if isinstance(x, str):
        return x
    if "where" in x:
        return f"{x.get('where')}: {x.get('text')}"
    if "unit_id" in x:
        return f"単位 {x.get('unit_id')}: {x.get('reason') or '訳の記録が無い'}"
    if "verdict" in x:
        return f"検算の判定 {x.get('verdict')}: {x.get('reason') or '訳の記録が無い'}"
    if "unit_key" in x:
        return f"単位 {x.get('unit_key')}: {as_dict(x.get(conflict.RULING)).get('text') or x.get(conflict.WHY_FIELD) or '訳の記録が無い'}"
    return json.dumps(x, ensure_ascii=False)


REDIRECT_SOURCE = "修正前の承認の一言が計画と違う向きで止めた行（一言を見直して答え直す）"
REDIRECT_NOTE = "承認ノードの一言が計画と違う向きを選んだか、向きが読めないか、判定が落ちたので修正へ進まず止めた。止めた訳: {reason}。この項目への答えを、一言の向きを見直して text に書く"


def redirect_drafts(values: dict) -> list:
    """修正前の答えの一言の向きで止めた run（止めの語 stopby.ANSWER_REDIRECTED）が、承認ノードで見せた項目に答え直す下書き。項目ごとに 1 行:
    question は項目の文の全文、text は空（機械は人の一言から答えを作らない）、note に返りの reason（止めた訳。人の一言を含む）。止めていない run は空"""
    import oneline
    got = as_dict(values.get("answer_before_fix"))
    if got.get("stop_reason") != stopby.ANSWER_REDIRECTED:
        return []
    said = as_dict(got.get("answer"))
    note = REDIRECT_NOTE.format(reason=oneline.one_line(got.get("reason") or NO_STOP_REASON))
    import gatemarks
    return [gatemarks._draft(q, "", REDIRECT_SOURCE, note) for q in _list(said.get("asked")) if isinstance(q, str) and q.strip()]


def answer_drafts(values: dict, returns: dict, gates: dict, unattended: bool) -> list:
    """人の判断を待つ項目への答えの下書き（元 runreport.answer_drafts の、承認し直すかの問い・載せなかった修正前の問いと R4 の問い・
    保留の台帳の問い・問いの立っていない測れていない素材の行。修正前の答えの一言の向きで止めた run の見せた項目への答え直しの行は redirect_drafts）"""
    import answer
    import plainask
    spec = as_dict(values.get("spec_check"))
    spec_qs = [q for q in _list(spec.get("questions")) if isinstance(q, str) and q.strip()]
    words = gatemarks.spec_words(bool(spec_qs) and spec.get("unchecked") is not False)
    out = [gatemarks._draft(q, "", words.source, words.note) for q in spec_qs]
    out += redirect_drafts(values)
    b = ledger(returns, gates, unattended)
    held = gatemarks.held_questions(b)
    asked = [plainask.item_row(q["text"]) for q in eye_questions(returns)]   # R4 の問いは欄 recommend を持たない
    if unattended and as_dict(gates.get("gate-before-fix")).get("decision") not in answer.GO_WORDS:
        # 載せなかった修正前の項目のうち台帳の問い（gatemarks.ask_text の文）は、下の保留の台帳の問いとして key で 1 行にする
        ledger_texts = {gatemarks.ask_text(q) for q in held}
        deferred = [q for q in _list(as_dict(values.get("ask_before_fix")).get("deferred")) if plainask.item_text(q) not in ledger_texts]
        asked = [plainask.item_row(plainask.item_text(q), None, _vetted(q)) for q in deferred] + asked
    asked += [plainask.item_row(q["text"], None, _vetted(q)) for q in means_questions(returns, gates)]
    # asked は行の並び: 下書きの答えは行の欄 recommend だけから決める（final.unattended_pass と gates.before_fix の抜け方 gates.passage が同じ欄を
    # 同じ gatemarks.recommend_of で読むので、抜け方と下書きは食い違わない）。欄の無い行（R4 の問い・設計の行・R2 の照らせない行）は text が空
    out += [gatemarks.item_draft(plainask.item_text(q), gatemarks.GATE_NODE, recommend=q.get("recommend")) for q in asked
            if plainask.item_text(q).strip()]
    for q in held:
        key = gatemarks.answer_key(b, q)
        push = gatemarks.reason_push(q)
        if push:
            out.append(gatemarks._draft(key, push, f"{gatemarks.ASK_HEAD} {key} の理由の推し（判定の役）"))
        else:
            opts = "・".join(str(o) for o in q.get("options") or []) or "（無し）"
            out.append(gatemarks._draft(key, "", f"{gatemarks.ASK_HEAD} {key} の選択肢", f"推しを判定の役が書いていない。選択肢から人が答えを text に書く: {opts}"))
    mats, _ = materials(returns)
    missing = gatemarks.unmeasured_of(mats)
    asked_from = {gatemarks.origin(q, missing) for q in judgment_doc(returns).get("questions") or [] if isinstance(q, dict)
                  and q.get("status") in gatemarks.ASKING}
    out += [gatemarks._material_draft(n, st, as_dict(mats.get(n)).get("reason")) for n, st in missing.items()
            if n not in asked_from and gatemarks.material_answer(b, n) is None]
    seen, kept = set(), []
    for d in out:
        if d["question"] not in seen:
            seen.add(d["question"])
            kept.append(d)
    return kept


# ---------------------------------------------------------------- 封じと置き
def apply_of(returns: dict, gates: dict) -> dict:
    """{sealed, placed, redesign, said, pr, commits}（元 runreport._seal_state・_apply_lines の said・_pr_commit_lines）"""
    import answer
    import oneline
    import seal as seallib
    sealed = as_dict(returns.get("sealed-diff"))
    applied = as_dict(returns.get("applied-diff"))
    handed = as_dict(applied.get("deliver"))
    said = next((g.get("text") for g in (gates.get(k) for k in ("gate-final", "gate-start", "gate-before-fix", "gate-replan"))
                 if isinstance(g, dict) and g.get("text") and not answer.by_push(g)), "")
    commits = [c for c in _list(handed.get("commits")) if isinstance(c, dict)]
    lines = ([f"{PR_COMMITS}修正案の項目ごとに {len(commits)} 本（依存の順。各 commit の時点で試験が通るかは確かめていない。確かめたのは"
              "積み終えた木の差分の hash）",
              *(f"項目 {c.get('item')}: {str(c.get('head'))[:12]}（{oneline.one_line(c.get('subject') or '')}）" for c in commits)]
             if commits else
             [f"{PR_COMMITS}項目ごとに分けなかった（{oneline.one_line(handed.get('split'))}）"]
             if isinstance(handed.get("split"), str) and handed.get("split") else [])
    pr = None
    if handed.get("act") in ("pr", "stopped", "unconfirmed"):
        got = as_dict(handed.get("pr"))
        pr = {"act": handed.get("act"), "url": got.get("url"), "number": got.get("number"), "is_draft": got.get("is_draft") is True,
              "reason": handed.get("reason") or ""}
    redesign = seallib.REDESIGN if as_dict(as_dict(returns.get("eyes")).get("r2")).get("status") == seallib.REDESIGN else ""
    return {"sealed": sealed.get("ok") is True and bool(sealed.get("diff")), "placed": applied.get("ok") is True,
            "redesign": redesign, "said": said or "", "pr": pr, "commits": lines}


def stop_lines(returns: dict, gates: dict, stops: list) -> dict:
    """節「2. 止めたか」の line の行: line の止めの語・承認ノードの行・封じと置きの ok でない行（before）と、続きの切れ目（after）"""
    import oneline
    before = [f"メイングラフのノードの止め: {x}" for x in stop_words_full(stops)]
    before += [f"承認ノード {named(at)}: {gate_line(g)}" for at, g in gates.items()]
    before += unpassed_full(returns)
    for rid in ("sealed-diff", "applied-diff"):
        m = returns.get(rid)
        if isinstance(m, dict) and m.get("ok") is not True:
            before.append(f"{NODE_OF[rid]} が ok でない: {oneline.one_line(m.get('reason') or '訳の記録が無い')}")
    return {"before": before, "after": [f"出力の続きが切れている: {x}" for x in chain_notes(returns)]}


def outcome_parts(returns: dict, gates: dict, eyes_due, head_at: str) -> dict:
    eyes = returns.get("eyes")
    seen = NO_EYES if not isinstance(eyes, dict) else "・".join(f"{n.upper()}: {eye_word(eyes, n, eyes_due)}" for n in EYE_NAMES)
    return {"gate": f"最後の承認ノード gate-final: {gate_line(gates.get('gate-final'))}", "eyes": f"独立の目: {seen}",
            "data": DATA_PLACES.format(head=head_at or NO_HEAD_AT)}


# ---------------------------------------------------------------- 方針の文書の変化（integration.md 4.5-12）
def policy_lines(record: dict, cwd, folder) -> list:
    """方針の文書が始めに固定した版から変わったまま終わった run の 1 行（integration.md 4.5-12。報告の節 1 の方針の行）。比べと行の字は
    修正前の承認ノードと同じ口（src/gates.py の policy_change・change_row。元 boardview の同じ名）"""
    import oneline
    from src import gates
    try:
        ch = gates.policy_change(record, cwd, folder)
    except (OSError, ValueError) as e:
        return [f"{POLICY_CHANGED_HEAD}か: 確かめられない（{oneline.one_line(e)}）"]
    return [f"{POLICY_CHANGED_HEAD}: {gates.change_row(ch)}"] if ch else []


# ---------------------------------------------------------------- 4.5-14: 軽量の単位で test_cmd を省いた数
def cmd_skipped(tdd_stages: list) -> int:
    """fixed の tdd（段ごとの fix の tdd の配列）の単位のうち、test_cmd が軽量の語（lib/report.py の CMD_LIGHT）の物の数"""
    import report
    light = report.CMD_LIGHT
    keys = set()
    for stage in tdd_stages or []:
        for group in stage if isinstance(stage, list) else []:
            for u in _list(as_dict(group).get("units")):
                if isinstance(u, dict) and u.get("test_cmd") == light:
                    keys.add(u.get("unit_key"))
    return len(keys)


# ---------------------------------------------------------------- 組む
def optional_of(values: dict) -> list:
    """落ちても受け止める段の宣言: line 自身の宣言（collect の入力 optional）と、受け皿が運んだ judge の graph の宣言（頭 judge__）"""
    own = [h for h in _list(values.get("optional")) if isinstance(h, str) and h]
    for row in _list(as_dict(values.get("judge")).get("optional")):
        if isinstance(row, dict) and isinstance(row.get("node"), str) and row["node"]:
            own.append(row["node"] if row.get("bare") is True else f"judge__{row['node']}")
    return list(dict.fromkeys(own))


RETURNED = (("test-gate-base", "test_gate_base"), ("judge", "judge"), ("structure", "structure"),
            ("independent-design", "independent_design"), ("plan-rounds", "rounds"), ("fix", "fix"), ("lens", "lens"),
            ("delta-review", "delta"), ("replan", "replan"), ("replan-review", "replan_review"), ("refix-run", "refix"),
            ("lens-2", "lens_2"), ("delta-review-2", "delta_2"), ("parallel-pr-after", "parallel_after"), ("rejudge-run", "rejudge"),
            ("spec-check-run", "spec_check"), ("test-gate-final", "test_gate_final"), ("eyes", "eyes"), ("merge-seal", "merge_seal"),
            ("merge-apply", "merge_apply"))


def build(values: dict, record: dict | None, record_why: str = "", cwd=None) -> dict:
    """facts（docs/design/report.md の 1.2 の欄の全部）"""
    import oneline
    record = record or {}
    returns = returns_of(values, record)
    start = as_dict(values.get("start"))
    ports_ = as_dict(start.get("ports"))
    unattended = start.get("unattended") is True
    gates = gates_of(values)
    problems, notes = [], []
    if record_why:
        problems.append(record_why)

    def part(name, fn, default, *, outcome=True):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — 1 つの部分が組めなくても facts を書く（訳を名指す）
            (problems if outcome else notes).append(f"{name}を組めない（{type(e).__name__}: {oneline.one_line(e)}）")
            return default

    got = part("修正の段の控え", lambda: beside(returns), stageslib.read([], stageslib.resolve), outcome=False)
    problems += part("申し出と裁定", lambda: conflict_rows(returns)[1], [])
    problems += part("script の落ちた訳", lambda: script_fall_notes(values), [])
    fixed = as_dict(values.get("fixed"))
    measured = part("依頼の答えが当たった素材", lambda: _measured(returns, gates, unattended), set(), outcome=False)
    facts_ctx = {"eyes_due": fixed.get("eyes_due") if fixed else None, "beside": got, "measured": measured}
    left = part("残りの行", lambda: residue(returns, facts_ctx), [])
    stops = part("止めの語", lambda: stop_rows(values, returns), [])
    halts = part("line の止め", lambda: halt_rows(returns), [])
    waits = part("人待ち", lambda: wait_rows(values, returns), {"conflicts": [], "conflicts_if_closed": [], "others": []})
    cut = part("段の表の切れ目", lambda: cut_row(returns), None)
    closed = cut is None
    taken = part("無人の run が採った推し", lambda: _taken(returns, gates, unattended), [], outcome=False)
    dec, asks, tallied, counted_left = part(
        "人が決めること", lambda: decisions(values, returns, gates, unattended=unattended, left=left, closed=closed, got=got,
                                       taken=taken, cwd=cwd),
        ({"before": [], "after": [], "outside": []}, [], {}, []), outcome=False)
    carried_rows = [*_list(fixed.get("carry")), *_list(as_dict(values.get("judged")).get("carry"))]
    findings = part("次の依頼", lambda: next_request(returns, left, closed, got, carried_rows), [])
    prior = part("前の失敗", lambda: prior_failures(returns, left, stops), [])
    drafts = part("答えの下書き", lambda: answer_drafts(values, returns, gates, unattended), [], outcome=False)
    constraints = part("次の run の制約", lambda: constraints_of(returns, str(ports_.get("run_id") or "")), [], outcome=False)
    _, material_note = part("素材の状態", lambda: materials(returns), ({}, ""), outcome=False)
    notes += [material_note] if material_note else []
    ties_why = part("答えの結び", lambda: ties_note(returns), "", outcome=False)
    notes += [ties_why] if ties_why else []
    notes += [f"修正の控え: {x}" for x in got["unread"]]
    before = [x for x in (part("修正の段の分け", lambda: split_line(returns), "", outcome=False),
                          part("推しの句", lambda: pushed_said(gates, taken), "", outcome=False)) if x]
    after = [*part("止めた段の訳の句", lambda: spoken_stops(values, returns, record), [], outcome=False),
             *part("起動スクリプトの壊れの句", lambda: suite_broken_notes(values), [], outcome=False),
             *part("最後のテストの句", lambda: ran_notes(returns), [], outcome=False),
             *part("TDD の実行器の句", lambda: _suite_note(record), [], outcome=False),
             *part("利用者の環境の句", lambda: _user_env_note(ports_), [], outcome=False)]
    requests = part("依頼の字", lambda: request_texts(ports_, record), [], outcome=False)
    notices = [head_notice("test_cmd_note", line) for line in str(values.get("notices") or "").splitlines() if line.strip()]
    head_at = _head_at(returns)
    return {
        "start_ok": bool(record) and not record_why,
        "problems": [str(p) for p in problems],
        "notes": [str(n) for n in notes],
        "gates": gate_rows(gates),
        "stops": stops,
        "halts": halts,
        "waits": waits,
        "cut": cut,
        "optional": optional_of(values),
        "returned": [rid for rid, name in RETURNED if isinstance(values.get(name), dict)],
        "no_fix": part("直す物が無い周", lambda: no_fix(returns), False),
        "left": left,
        "proved": proved(returns),
        "head": {"before": before, "stopped": part("止まった訳", lambda: stopped_why(returns, stops, _list(as_dict(values.get("ask_final")).get("reasons"))),
                                                   [], outcome=False),
                 "after": after, "notices": notices},
        "asks": asks,
        "tallied": tallied,
        "counted_left": counted_left,
        "decisions": dec,
        "apply": part("封じと置き", lambda: apply_of(returns, gates),
                      {"sealed": False, "placed": False, "redesign": "", "said": "", "pr": None, "commits": []}),
        "carry": {"findings": findings, "prior": prior, "drafts": drafts, "constraints": constraints},
        "stop_lines": part("止めたかの行", lambda: stop_lines(returns, gates, stops), {"before": [], "after": []}, outcome=False),
        "outcome_parts": part("模型の結末の句", lambda: outcome_parts(returns, gates, fixed.get("eyes_due") if fixed else None, head_at),
                              {"gate": "", "eyes": "", "data": ""}, outcome=False),
        "round": as_dict(returns.get("plan")).get("round") if isinstance(as_dict(returns.get("plan")).get("round"), int) else None,
        "line_rev": part("メイングラフの版", lambda: _line_rev(record), "", outcome=False),
        "request_texts": requests,
    }


def _measured(returns, gates, unattended) -> set:
    import gatemarks
    return gatemarks.measured_materials(ledger(returns, gates, unattended)) if _request_answers(returns) else set()


def _taken(returns, gates, unattended) -> list:
    import gatemarks
    return gatemarks.taken_pushes(ledger(returns, gates, unattended))


def _suite_note(record: dict) -> list:
    """TDD の実行器の用意の知らせ。状態の分け方は suitewrite.note_state の 1 か所が持ち、種はその状態から選ぶだけ。本文は括弧の中身 note_detail"""
    import suitewrite
    kinds = {suitewrite.USED: "suite_used", suitewrite.WROTE: "suite_wrote", suitewrite.NOT_MADE: "suite_not_made"}
    state = suitewrite.note_state(record)
    return [head_notice(kinds[state], suitewrite.note_detail(record))] if state else []


def request_texts(ports_: dict, record: dict | None) -> list:
    """報告の題に添える依頼の字: 始めの節が持つ人の依頼のファイルの写し（ports.request）の行の text を、依頼のファイルの順のまま。行が 0 で、
    始めの記録の入口の入力の形に PR の題が在れば、その題 1 つ。写しの pointer が無い run（始めの節の前で止まった run）は空。テーマの run が降りた依頼
    （request-in の返り）は設計の段が書いた字を持つので読まない。形に合わない写し・下書きの行は ValueError"""
    import requestrows

    from src import startrec

    pointer = ports_.get("request")
    if not pointer:
        return []
    rows = requestrows.findings(json.dumps(pointer))
    if rows:
        return [str(row["text"]) for row in rows]
    title = as_dict(as_dict(startrec.shape(record or {})).get("pr")).get("title")
    return [title] if isinstance(title, str) and title else []


def _user_env_note(ports_: dict) -> list:
    """利用者の HOME・XDG に戻して起こした run なら知らせ（文は userenv.NOTE を引く表の行。印の置き場 user_env_dir に印が在るか）。本文は空"""
    import userenv
    folder = str(ports_.get("user_env_dir") or "")
    return [head_notice("user_env")] if folder and userenv.ran(pathlib.Path(folder)) else []


def _head_at(returns: dict) -> str:
    ptr = as_dict(returns.get("judge")).get("tier_record")
    try:
        return str(stageslib.resolve(ptr, "tier_record")) if ptr else ""
    except stageslib.READ_ERRORS:
        return ""


def _line_rev(record: dict) -> str:
    from src import versions
    return versions.line_rev(as_dict(record).get("versions")) or ""

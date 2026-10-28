# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正の後の上げ直し（node raise。docs/design/line.md の 5.3。今の line の redepth と fix の中の fixboard.redepth を 1 つにした物）。

run に 1 回、1 回目の修正の段（fix・after-fix）の後、1 回目の lens・delta-review の前。fix-in が決めた単位の深さを、修正の後の信号で
標準へ上げる（src.tiers.raise_doc。下げない）。信号は、単位ごとに: 1 回目の fix が止めた単位（units の status が fixed でない）。
run 全体に: 申し出が在る（fix の conflicts の行）・答えていない問い（問いの台帳の問いごと。gatemarks.pending。台帳が読めなければ
上げる側に倒す）・案の直しが走る（after-fix の replan）・修正役の異議が在る（fix の objection）と、修正の差分が頭の深さの引用の外に
出た・TDD の輪で修正役が拒まれた・範囲の相談をした・直さずに残すと答えた事前審査の block（tiers.signals。引用は判定のまとめの
tier_record）。返り: units（上げた後の行）・checks（差分の審査・レンズ・目を回すか: 省く理由の文が空）・skip_why（回さない時の訳）・
eyes_due（checks か、前の run の前提の検算が運んだ実測が在る run〔ports.carried_measured〕）・raised・counted（run の広さの数え。
記録だけ）・lines（報告の冒頭 2 の深さの行。軽量で test_cmd を省いた数は facts が fixed.tdd から数えて tiers.lines で組み直す）・
stop_reason。例外の時は works:line-script を返し、fixed が held にして試験の関門から先は飛ぶ（深さの分からない差分を目に通さない）。

入力（with:）: fix（$fix.output）・replan（after-fix の replan）・units_tier・switches（fix-in の返り）・judgment・tier_record・answer
（fix-in が運んだ判定の pointer・頭の深さの控え・修正前の答え）・record（始めの記録の pointer）・ports・request（request-in の返り。
依頼の答えはここから読む）。在れば plan・answer_ties・
materials（fix-in が運んだ承認済みの案の欄・結び・素材の状態の pointer）も読む
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

FIX = ("units", "conflicts", "objection", "diff", "plan_declared", "tdd_refused", "accept_trace")
READ_ERRORS = (OSError, ValueError, TypeError, AttributeError, KeyError)


def _path(raw, field: str):
    """作り手の返りの欄 field の pointer かパスの字・値の先のパス（null・空は None。その欄の宣言の form で照らす。src.stages.resolve）"""
    from src import stages
    if raw is None or raw == "" or raw == "null":
        return None
    return stages.resolve(raw, field)


def _doc(raw, field: str):
    path = _path(raw, field)
    return None if path is None else json.loads(path.read_text(encoding="utf-8"))


def pending_signals(judgment, ports_values: dict, answer, ties, materials) -> list:
    """答えていない問いの信号（問いの台帳の問いごと。依頼の answers と修正前の承認ノードの答えが答えた問いと、無人の run が採った判定の
    推しは数えない）。判定が無ければ空、台帳が読めなければ読めない訳の 1 行（上げる側に倒す）"""
    import gatemarks
    if judgment is None:
        return []
    try:
        doc = _doc(judgment, "judgment")
        ledger = gatemarks.ledger_files(doc if isinstance(doc, dict) else {}, ties_file=_path(ties, "answer_ties"),
                                        materials_file=_path(materials, "materials"),
                                        answers=[a for a in ports_values.get("request_answers") or [] if isinstance(a, dict)],
                                        gate=answer, takes_push=ports_values.get("takes_push") is True)
        return [f"答えていない問い {q.get('key')}" for q in gatemarks.pending(ledger)]
    except READ_ERRORS as error:
        return [f"問いの台帳が読めない（{type(error).__name__}）"]


def _conflict_rows(raw) -> list:
    """fix の conflicts の先の行（{items: [...]} か行の配列。無ければ []。読めなければ 1 行の印で上げる側に倒す）"""
    if raw is None:
        return []
    try:
        doc = _doc(raw, "conflicts")
    except READ_ERRORS as error:
        return [{"unread": f"{type(error).__name__}"}]
    rows = doc.get("items") if isinstance(doc, dict) else doc
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _plan_items(plan) -> list:
    try:
        doc = _doc(plan, "plan")
    except READ_ERRORS:
        return []
    items = doc.get("fields") if isinstance(doc, dict) else None
    return items if isinstance(items, list) else []


def touched_files(diff) -> tuple:
    """(修正の差分の触るファイル, 数えの起点の 1 行)。読めなければ空で、起点は計画の allowed_paths とその訳"""
    import changemap
    from src import tiers
    try:
        text = _path(diff, "diff").read_text(encoding="utf-8", errors="replace")
        return list(changemap.split_diff(text)[0]), f"修正の差分 {diff['path']}"
    except READ_ERRORS as error:
        return [], f"{tiers.PLAN_ORIGIN}（修正の差分を読めない: {type(error).__name__}）"


def raise_depth(fix, *, replan: bool, units_tier, switches: dict, judgment, tier_record, answer, dealt: dict, plan=None, ties=None,
                materials=None) -> dict:
    from src import tiers
    head = (switches or {}).get("tier") or tiers.STANDARD
    doc = tiers.docs_of(units_tier, forced=dealt.get("forced") or "")
    keys = list(doc["units"])
    stopped = {u["unit_id"]: f"修正の段が止めた単位（{u.get('status')}）" for u in fix["units"] or []
               if isinstance(u, dict) and u.get("unit_id") and u.get("status") != "fixed"}
    run = []
    conflicts = _conflict_rows(fix["conflicts"])
    if conflicts:
        run.append(f"申し出が在る（{len(conflicts)} 件）")
    run += pending_signals(judgment, dealt, answer, ties, materials)
    if replan:
        run.append("案の直しが走る")
    if str(fix["objection"] or "").strip():
        run.append("修正役の異議が在る")
    touched, origin = touched_files(fix["diff"])
    try:
        head_record = _path(tier_record, "tier_record")
    except READ_ERRORS:
        head_record = None
    late = tiers.late_records(dict(fix), _path)
    signals, counted = tiers.signals(_plan_items(plan), keys, touched, origin=origin, head_record=head_record, late=late,
                                     declared=fix["plan_declared"] or [])
    run += signals
    raised = tiers.raise_doc(doc, units=stopped, run=run)
    raised["counted"] = counted
    skip = tiers.skip_reason(raised, head)
    checks = not skip
    return {"units": tiers.rows_of(raised), "checks": checks, "skip_why": skip,
            "eyes_due": checks or dealt.get("carried_measured") is True, "raised": raised["raised"], "counted": counted,
            "lines": tiers.lines(raised, head, cmd_skipped=0), "stop_reason": ""}


def compute() -> dict:
    raw_fix, raw_replan = os.environ.get("INPUTS_FIX"), os.environ.get("INPUTS_REPLAN")
    raw_units, raw_switches = os.environ.get("INPUTS_UNITS_TIER"), os.environ.get("INPUTS_SWITCHES")
    raw_judgment, raw_record = os.environ.get("INPUTS_JUDGMENT"), os.environ.get("INPUTS_TIER_RECORD")
    raw_answer, raw_start, raw_ports = os.environ.get("INPUTS_ANSWER"), os.environ.get("INPUTS_RECORD"), os.environ.get("INPUTS_PORTS")
    raw_plan, raw_ties = os.environ.get("INPUTS_PLAN"), os.environ.get("INPUTS_ANSWER_TIES")
    raw_materials, raw_request = os.environ.get("INPUTS_MATERIALS"), os.environ.get("INPUTS_REQUEST")
    del raw_start   # 始めの記録は読まない（答えと無人の印は配る値から）
    from src import descend
    fix = ports.picked(raw_fix, FIX)
    if fix is None:
        raise ValueError("fix の出力（fix）が読めない。with: の鍵の結びを確かめる")
    return raise_depth(fix, replan=ports.parsed(raw_replan) is True, units_tier=ports.parsed(raw_units) or [],
                       switches=ports.parsed(raw_switches) or {}, judgment=ports.parsed(raw_judgment),
                       tier_record=ports.parsed(raw_record), answer=ports.parsed(raw_answer),
                       dealt=descend.dealt(ports.parsed(raw_ports), raw_request),
                       plan=ports.parsed(raw_plan), ties=ports.parsed(raw_ties), materials=ports.parsed(raw_materials))


def fallback(reason: str) -> dict:
    from src import guard
    return {"units": [], "checks": True, "skip_why": "", "eyes_due": True, "raised": [f"深さを上げ直せなかった（{reason}）"],
            "counted": "", "lines": [], "stop_reason": guard.LINE_SCRIPT}


ports.run(compute, fallback)

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""独立の目のまとめ（eyes の graph）へ渡す値を組む node eyes-in（docs/design/line.md の 4.5 の eyes の行・5.4）。

- merge: 段が目をまとめる（fix-in の switches の merge）で、目を回す（fixed の eyes_due）時だけ真。目を省かずに回す軽量の run だけ
  R3 を R4 の会話に入れる（今の depth.merges。持ち主の決め eyes-by-reason）
- policy: 修正前の承認ノードが固め直した写し（fix-in が運ぶ）か、start が固めた写し
- review: 修正が使った案を審査した最後の往復の結論 {round, verdict, blocks, why}（src.gates.review_verdict）。案の直しが走れば案の直しの
  事前審査の結論。往復の記録の最後の往復が修正の使った案の周と組まなければ unread（今の boardview.read_open_of の照らし）。直す物が
  無い周は design
- pushes: 無人の run が判定の保留の問いに採った推し（gatemarks.taken_pushes を、最後の承認ノードと同じ判定・結び・修正前の答えで読む）。
  読めなければ空と、notes に訳
- answers: {start, before_fix}（承認ノードの答え）。asked: 修正前の承認ノードで聞いた項目 [{kind, text}]（今の plan_questions）

入力（with:）: fix_in（fix-in の返り）・fixed（fixed の返り）・start_answer（起動の承認ノードの答えか null）・replan_review（案の直しの
事前審査の受け皿の got か null）・judged（judged の返り）・record（始めの記録の pointer）・ports（start の配る値）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

FIX_IN = ("policy", "answer", "record", "round", "switches", "no_fix")
FIXED = ("eyes_due", "no_fix", "refixed")
JUDGED = ("judgment", "answer_ties", "materials")
REVIEW = ("ok", "status", "reason", "round", "blocks")
NO_FIX_REVIEW = {"verdict": "design", "blocks": [], "why": "直す物が無い周で、案を審査していない"}


def kind_of(text: str) -> str:
    """修正前の承認ノードに載せた項目の文の種類（行の頭から。今の事前審査の questions の kind）"""
    import gatemarks
    if gatemarks.NARROW_HEAD.match(text):
        return "regression"
    face = gatemarks.FACE_HEAD.match(text)
    if face:
        return face.group(1)
    for head, kind in ((gatemarks.DESIGN_HEAD, gatemarks.DESIGN_KIND), (gatemarks.ASK_HEAD, gatemarks.ASK_KINDS[0]),
                       (gatemarks.DESIGN_ONLY_ITEM, gatemarks.DESIGN_ONLY_KIND), (gatemarks.STUCK_ITEM, gatemarks.DESIGN_ONLY_KIND)):
        if text.startswith(head):
            return kind
    return ""


def pushes(judged, record: dict, before_fix, *, unattended: bool) -> tuple:
    """(無人の run が判定の保留の問いに採った推しの文, 添える行)。読めなければ推しを無しにして訳"""
    import gatemarks
    from src import gates
    if judged is None or judged["judgment"] is None:
        return [], []
    try:
        doc = gates.read_json(gates.path_of(judged["judgment"])) or {}
        b = gatemarks.ledger_files(doc, ties_file=gates.path_of(judged["answer_ties"]) or None,
                                   materials_file=gates.path_of(judged["materials"]) or None, answers=gates.request_answers(record),
                                   gate=before_fix, takes_push=unattended)
        return [f"問い {q.get('key')}: {push}" for q, push, _ in gatemarks.taken_pushes(b)], []
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        return [], [f"判定の問いの控えか始めの記録を読めない（無人の run が保留の問いに採った推しを並べていない。{type(error).__name__}: {error}）"]


def compute() -> dict:
    raw = {"fix_in": os.environ.get("INPUTS_FIX_IN"), "fixed": os.environ.get("INPUTS_FIXED"),
           "start_answer": os.environ.get("INPUTS_START_ANSWER"), "replan_review": os.environ.get("INPUTS_REPLAN_REVIEW"),
           "judged": os.environ.get("INPUTS_JUDGED"), "record": os.environ.get("INPUTS_RECORD"), "ports": os.environ.get("INPUTS_PORTS")}
    from src import gates, startrec

    given = ports.parsed(raw["ports"]) or {}
    fix_in = ports.picked(raw["fix_in"], FIX_IN)
    fixed = ports.picked(raw["fixed"], FIXED)
    judged = ports.picked(raw["judged"], JUDGED)
    replan_review = ports.picked(raw["replan_review"], REVIEW)
    start_answer = ports.parsed(raw["start_answer"])
    record_path = ports.file(raw["record"])
    record = startrec.load(record_path) if record_path else {}
    before_fix = fix_in["answer"] if fix_in is not None else None
    switches = (fix_in or {}).get("switches") if isinstance((fix_in or {}).get("switches"), dict) else {}
    due = bool((fixed or {}).get("eyes_due"))
    if fixed is not None and fixed["no_fix"]:
        review = dict(NO_FIX_REVIEW)
    else:
        doc = gates.read_json(gates.path_of(fix_in["record"])) if fix_in is not None else None
        review = gates.review_verdict(doc, round_=(fix_in or {}).get("round"),
                                      replan_review=dict(replan_review) if replan_review is not None else None)
    taken, notes = pushes(judged, record, before_fix, unattended=bool(given.get("unattended")))
    asked = (before_fix or {}).get("asked") if isinstance(before_fix, dict) else None
    return {"merge": bool(switches.get("merge")) and due,
            "policy": str((fix_in or {}).get("policy") or given.get("policy") or ""),
            "review": review, "pushes": taken,
            "answers": {"start": start_answer if isinstance(start_answer, dict) else None,
                        "before_fix": before_fix if isinstance(before_fix, dict) else None},
            "asked": [{"kind": kind_of(t), "text": t} for t in asked or [] if isinstance(t, str)], "notes": notes}


def fallback(reason: str) -> dict:
    return {"merge": False, "policy": "", "review": {"verdict": "unread", "blocks": [], "why": reason}, "pushes": [],
            "answers": {}, "asked": [], "notes": [f"独立の目へ渡す値を組めなかった（{reason}）"]}


ports.run(compute, fallback)

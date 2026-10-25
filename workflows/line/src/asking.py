"""修正前の承認ノードの材料の読み（docs/design/line.md の 2 節の 2）。修正前の承認ノード ask-before-fix と、対話モードの run の計画の
往復の末尾の設計の相談 design-talk（src/talk.py）が、同じ材料から同じ行を組むための 1 か所。行の決めは src.gates.before_fix。

- materials(rounds, *, structure_raw, judge_raw, record_raw, unattended, place) -> dict: before_fix に渡す材料（ledger・design_rows_・
  policy_row・stuck_reason・record_doc・answered・unread）。読めない控えは unread に名指す（開ける理由）。rounds の agreed（設計の相談で
  合意した答え）は台帳の問いへの関所の答えとして読む（合意した問いを修正前に聞き直さない）
- record_doc(ptr, unread) -> dict | None: 往復の記録の 1 つの読み口（src.rounds.read）。読めない記録は unread に名指して None
- PREVIOUS: 同じ承認ノードの前の答え（answer.taken が書く。resume で回し直した時に聞き直さない）
"""
from __future__ import annotations

from pathlib import Path

import answer
import gatemarks
import ports

PREVIOUS = "gates/gate-before-fix.json"


def record_doc(ptr, unread: list):
    """往復の記録の pointer ptr の中身（src.rounds.read の 1 つの読み口）。無い・読めない・形の違う記録は unread に訳を足して None
    （読めない控えは聞く側に倒す。E23）"""
    from src import gates, rounds
    path = gates.located(ptr, "往復の記録", unread, lambda raw: ports.file(raw, "json(shared:plan-converge.schema.json)"))
    if not path:
        return None
    try:
        return rounds.read(path)
    except ValueError as error:
        unread.append(f"往復の記録 {path} が読めない（{error}）")
        return None


def materials(rounds: dict | None, *, structure_raw, judge_raw, record_raw, unattended: bool, place: Path) -> dict:
    from src import files, gates, rounds as rounds_mod, startrec

    judge = ports.picked(judge_raw, ("judgment", "answer_ties", "materials"), optional=())
    record_path = ports.file(record_raw, "json(start-record.schema.json)")
    record = startrec.load(record_path) if record_path else {}
    unread: list = []   # 指す先が無い・読めない控え（開ける理由にする。形の違う pointer は落ちる）
    rec_doc = record_doc((rounds or {}).get("record"), unread) if rounds else None
    stuck = (rounds_mod.stuck_reason(rec_doc, str(place / files.PLAN_CONVERGE_DIR))
             if rounds and rounds.get("stalled") and isinstance(rec_doc, dict) else "")
    agreed = (rounds or {}).get("agreed")   # 設計の相談で合意した答え（台帳の問いの答え・保留も一言に在る。ask-before-fix の rounds だけが持つ）
    agreed = agreed if isinstance(agreed, dict) and agreed.get("decision") in answer.GO_WORDS else None
    ledger = None
    if judge is not None and judge["judgment"] is not None:
        doc = gates.read_located(judge["judgment"], "判定", unread, lambda raw: ports.file(raw, "json(shared:judgment.schema.json)"))
        ties = gates.located(judge["answer_ties"], "答えの結び", unread, lambda raw: ports.file(raw, "json(shared:answer-ties.schema.json)"))
        found = gates.located(judge["materials"], "素材の状態", unread, lambda raw: ports.file(raw, "json(shared:materials-state.schema.json)"))
        if isinstance(doc, dict):
            ledger = gatemarks.ledger_files(doc, ties_file=ties or None, materials_file=found or None,
                                            answers=gates.request_answers(record), gate=agreed, takes_push=unattended)
    change = gates.policy_change(record, Path.cwd(), place)
    previous = gates.read_json(place / PREVIOUS)
    structure = gates.located(structure_raw, "構造の目の控え", unread,   # 形の違う pointer はここで ValueError（落ちる道）
                              lambda raw: ports.file(raw, "json(shared:structure-state.schema.json)"))
    try:
        design_rows = gates.design_rows(structure)
    except ValueError as error:   # 控えが在るのに壊れている: 読めなかった控えとして承認ノードを開き、控えの名を見せる
        design_rows = []
        unread.append(str(error))
    return {"ledger": ledger, "design_rows_": design_rows, "policy_row": gates.change_row(change) if change else "",
            "stuck_reason": stuck, "record_doc": rec_doc, "answered": [previous] if isinstance(previous, dict) else [], "unread": unread}

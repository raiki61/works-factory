# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正前の承認ノードを開くかと、見せる文を決める node ask-before-fix（docs/design/line.md の 2 節の 2・6 節。今の
workflows/line/scripts/ask_before_fix.py の決まりのまま、軸・項目・聞かずに通した行を line が組む形にした物）。決めは src.gates.before_fix。

- 計画ができていない（往復が修正へ進む抜け方でなく、止まってもいない）・直す義務 0 件の周: 開かず、修正へも進まない
- 必ず開く: 往復が止まった（stalled）・設計だけの run。どちらも「設計だけ」の種類の行を 1 行（同じ種類の行が既に在れば足さない）
- 開く: 事前審査の人に回しうる行（asks の decided が偽か why の在る行）・世界の解の外れ（deviations の world の why の在る行）・
  構造の目の人に上げる行・問いの台帳の問い（gatemarks.ledger_at の読み）・方針の文書の変化。軸の行は項目が無い時だけ足す
- 無人の run: 台帳の問いは載せず deferred に返す。ほかの項目は gates.passage（全部が通す推しの尾を持つ時だけ推しで進み、ほかは
  works:needs-human で止める）
返り: open・go・stop_reason・text・deferred・asked（載せた項目の文）・pushed（推しで進んだ答え）・passes（聞かずに通した行）・
policy_changed（方針の文書の変化の行を載せたか。answer-before-fix が固め直す）。

入力（with:）: rounds（plan-rounds-out の got）・structure（structure-in の structure。構造の目の控えの pointer か null）・judge
（judge-out の got）・record（始めの記録の pointer）・ports（start の配る値）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

ROUNDS = ("done", "ok", "status", "round", "plan_prior", "record", "plan", "fix_plan", "reply", "handoffs", "ripple", "owed", "gave_up",
          "stalled", "capped", "review", "asks", "deviations", "review_status", "review_reason", "stop_reason")
JUDGE = ("judgment", "answer_ties", "materials")
RECORD = "run の置き場の gates/gate-before-fix.json"
QUESTION = "事前審査の 4 つの軸と人への問い。通すなら通す範囲と条件を一言に"
PREVIOUS = "gates/gate-before-fix.json"   # 同じ承認ノードの前の答え（answer.taken が書く。resume で回し直した時に聞き直さない）


def compute() -> dict:
    raw = {"rounds": os.environ.get("INPUTS_ROUNDS"), "structure": os.environ.get("INPUTS_STRUCTURE"),
           "judge": os.environ.get("INPUTS_JUDGE"), "record": os.environ.get("INPUTS_RECORD"), "ports": os.environ.get("INPUTS_PORTS")}
    import gatemarks
    from src import files, gates, rounds as rounds_mod, startrec

    given = ports.parsed(raw["ports"]) or {}
    unattended, design = bool(given.get("unattended")), bool(given.get("design_only"))
    rounds = ports.picked(raw["rounds"], ROUNDS)
    judge = ports.picked(raw["judge"], JUDGE, optional=())
    record_path = ports.file(raw["record"])
    record = startrec.load(record_path) if record_path else {}
    place = ports.place()
    unread: list = []   # 指す先が無い・読めない控え（開ける理由にする。形の違う pointer は落ちる）
    rec_doc = gates.read_located((rounds or {}).get("record"), "往復の記録", unread) if rounds else None
    stuck = rounds_mod.stuck_reason(rec_doc, str(place / files.PLAN_CONVERGE_DIR)) if rounds and rounds.get("stalled") and isinstance(rec_doc, dict) else ""
    ledger = None
    if judge is not None and judge["judgment"] is not None:
        doc = gates.read_located(judge["judgment"], "判定", unread)
        ties = gates.located(judge["answer_ties"], "答えの結び", unread)
        materials = gates.located(judge["materials"], "素材の状態", unread)
        if isinstance(doc, dict):
            ledger = gatemarks.ledger_files(doc, ties_file=ties or None, materials_file=materials or None,
                                            answers=gates.request_answers(record), gate=None, takes_push=unattended)
    change = gates.policy_change(record, Path.cwd(), place)
    previous = gates.read_json(place / PREVIOUS)
    got = gates.before_fix(dict(rounds) if rounds is not None else None, unattended_run=unattended, design=design, ledger=ledger,
                           design_rows_=gates.design_rows(gates.located(raw["structure"], "構造の目の控え", unread)),
                           policy_row=gates.change_row(change) if change else "", stuck_reason=stuck, record_doc=rec_doc,
                           answered=[previous] if isinstance(previous, dict) else [], unread=unread)
    text = ""
    if got["open"]:
        asking = {"node": gatemarks.GATE_NODE, "question": QUESTION, "items": [t for _, t in got["items"]],
                  "kinds": list(dict.fromkeys(k for k, _ in got["items"] if k)) or [gates.AXIS_KIND]}
        text = gatemarks.gate_text(asking, run_id=os.environ["WORKFLOW_ID"], node=gatemarks.GATE_NODE, record_name=RECORD)
    return {"open": got["open"], "go": got["go"], "stop_reason": got["stop_reason"], "text": text, "deferred": got["deferred"],
            "asked": got["asked"], "pushed": got["pushed"], "passes": got["passes"], "policy_changed": got["policy_changed"]}


def fallback(reason: str) -> dict:
    from src import guard

    return {"open": False, "go": False, "stop_reason": guard.LINE_SCRIPT, "text": "", "deferred": [], "asked": [], "pushed": None,
            "passes": [], "policy_changed": False}


ports.run(compute, fallback)

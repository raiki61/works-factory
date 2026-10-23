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
  works:needs-human で止める。止めた時は止めた項目も deferred に返し、報告と次の依頼の下書きに届ける）
- 対話モードの run（設計だけの run で無人でない）: 往復の返りの agreed（設計の相談の承認ノードの最後の答え）を before_fix に渡す。止める語なら
  開かずに止め、通す語ならそこで見せた行を聞き直さず、設計だけの行も足さない（合意した承認を聞き直さない）
返り: open・go・stop_reason・text・deferred・asked（載せた項目の文）・pushed（推しで進んだ答え）・passes（聞かずに通した行）・
policy_changed（方針の文書の変化の行を載せたか。answer-before-fix が固め直す）・agreed（設計の相談の最後の答え。answer-before-fix が通す語の
合意を修正前の答えとして書き、報告は止めた答えの一言も出す。対話モードでない run は null）。材料の読みは src.asking.materials（設計の相談と同じ 1 か所）。

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
TALKED = ("agreed",)   # 対話モードの run の計画の往復の返りだけが持つ欄（設計の相談の承認ノードの最後の答え。仕様駆動の run の往復の部は持たない）
RECORD = "run の置き場の gates/gate-before-fix.json"
QUESTION = "事前審査の 4 つの軸と人への問い。通すなら通す範囲と条件を一言に"


def compute() -> dict:
    raw = {"rounds": os.environ.get("INPUTS_ROUNDS"), "structure": os.environ.get("INPUTS_STRUCTURE"),
           "judge": os.environ.get("INPUTS_JUDGE"), "record": os.environ.get("INPUTS_RECORD"), "ports": os.environ.get("INPUTS_PORTS")}
    import gatemarks
    from src import gates
    from src.asking import materials

    given = ports.parsed(raw["ports"]) or {}
    unattended, design = bool(given.get("unattended")), bool(given.get("design_talk"))
    rounds = ports.picked(raw["rounds"], ROUNDS + TALKED, optional=TALKED)
    agreed = rounds["agreed"] if rounds is not None and isinstance(rounds["agreed"], dict) else None
    kw = materials(dict(rounds) if rounds is not None else None, structure_raw=raw["structure"], judge_raw=raw["judge"],
                   record_raw=raw["record"], unattended=unattended, place=ports.place())
    got = gates.before_fix(dict(rounds) if rounds is not None else None, unattended_run=unattended, design=design, agreed=agreed, **kw)
    text = ""
    if got["open"]:
        asking = {"node": gatemarks.GATE_NODE, "question": QUESTION, "items": [t for _, t in got["items"]],
                   "kinds": list(dict.fromkeys(k for k, _ in got["items"] if k)) or [gates.AXIS_KIND]}
        text = gatemarks.gate_text(asking, run_id=os.environ["WORKFLOW_ID"], node=gatemarks.GATE_NODE, record_name=RECORD)
    return {"open": got["open"], "go": got["go"], "stop_reason": got["stop_reason"], "reason": "", "text": text, "deferred": got["deferred"],
            "asked": got["asked"], "pushed": got["pushed"], "passes": got["passes"], "policy_changed": got["policy_changed"],
            "agreed": agreed}


def fallback(reason: str) -> dict:
    from src import guard

    return {"open": False, "go": False, "stop_reason": guard.LINE_SCRIPT, "reason": reason, "text": "", "deferred": [], "asked": [], "pushed": None,
            "passes": [], "policy_changed": False, "agreed": None}


ports.run(compute, fallback)

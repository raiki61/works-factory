# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正前の関所を開くかと、見せる文を決める節 ask-before-fix（docs/design.md の「メイングラフ」の「順と承認ノード」の 6）。

入力（with:）は計画の往復の返り（plan-rounds の ready・pass・stalled・ask_human・gate_axes・questions）と、始めの節の
unattended・design_only。questions の行は関所の項目の種類と文 {kind, text}（plan-review の返り。lib/gatemarks.py の question_row）。
- 計画ができていない（ready が false）: 関所を開かず、修正へも進まない（go: false。結末は report が計画と判定の返りから決める）。
  直す義務 0 件の周（plan-out の nothing_owed）は design-only を通って最後のテストと独立の目へ進む
- 必ず開く: 事前審査の壁打ちが止まった（stalled。往復の安全の上限の周で止めた時も stalled で、理由は questions に載る）・
  設計だけの run（design_only）。事前審査が設計だけの
  行（種類 design_only。止まった理由を尾に持つ gatemarks.design_item）を返していれば、その 1 行だけにして足し直さない（元
  gatemarks.design_item の 1 行。L-D19・P249）
- 開く: 4 つの軸のどれかが ok でない・事前審査が人に聞くと言った（ask_human）・関所の項目が在る。軸の訳は事前審査の項目の尾に在る
  （元 gatemarks._item の「人に聞く訳」）ので、軸の行は項目が 1 つも無い時だけ足す
- 無人の run: 判定の推しが選択肢を名指し出どころ・depends が開いた単位の fork・held は台帳の読み（gatemarks.answered の run_push）が無人の run の答えとして採り、出どころを
  直す義務に戻すので、ここに来る台帳の問い（種類 fork・escalate。gatemarks.ASK_KINDS）は採れる推しの無い物と escalate だけで、それは関所に
  載せず deferred で返す（問いの出どころは直す義務から外れたまま修正へ進む。元 works/.shared/core/gatemarks.py:637-638）。ほかの種類（狭め・事前審査の穴・方針の文書の変化・事前審査の
  諦め・設計の問い・世界の解の外れ・設計だけ）が在れば、その項目の全部が通す推しの尾を持つ時だけ推しで進み（返り pushed。
  gatemarks.pushed_answer。持ち主 2026-10-15「人がいないときは推しの答え。」）、ほかは開かずに止める（needs-human。今の works で
  無人の殻が関所に stop を返したのと同じ結末）。事前審査の壁打ちが止まった行（種類 design_only の止まりの行）も、
  事前審査の役の推しの尾（付く条件は gatemarks.stuck_push）を持てば同じく推しで進む。ここは pushed_answer に渡すだけで変えない
返り asked は関所に載せた項目の文の並び（開かない時は []。推しで進んだ時は推しで通した項目）。answer-before-fix がそれを答えの asked
にし、fix・plan-review・eyes が通した行として読む。pushed は推しで進んだ時の答え（answer-before-fix が答えとして記録する）で、ほかは null。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import gatemarks
    import stopby

AXES = {"obvious": "自明", "world": "世界の解", "clean": "汚くない", "not_overkill": "やりすぎでない"}
AXIS_KIND = "plan_review"
QUESTION = "事前審査の 4 つの軸と人への問い。通すなら通す範囲と条件を一言に"
RECORD = "run の置き場の gates/gate-before-fix.json"


def ask(plan: dict, *, unattended: bool, design_only: bool, run_id: str) -> dict:
    if not plan.get("ready"):
        return {"open": False, "go": False, "stop_reason": "", "text": "", "deferred": [], "asked": [], "pushed": None}
    rows, deferred = [], []
    questions = [(str(q.get("kind") or ""), str(q.get("text") or "")) if isinstance(q, dict) else ("", str(q))
                 for q in plan.get("questions") or []]
    if not questions:   # 事前審査の項目は揃わない訳を行の尾に持つ。項目の無い時だけ軸の訳を行にする（P249）
        for key, word in AXES.items():
            axis = (plan.get("gate_axes") or {}).get(key)
            if isinstance(axis, dict) and axis.get("ok") is False:
                rows.append((AXIS_KIND, f"{word}（{key}）の軸が通らない: {axis.get('note') or '（訳が無い）'}"))
    for kind, text in questions:
        if unattended and kind in gatemarks.ASK_KINDS:
            deferred.append(text)
        else:
            rows.append((kind, text))
    # 事前審査が設計だけの行・止まりの行（止まった理由つき。gatemarks.design_item）を返していれば足し直さない（L-D19・P249）
    if not any(kind == gatemarks.DESIGN_ONLY_KIND for kind, _ in questions):
        if plan.get("stalled"):
            rows.append((gatemarks.DESIGN_ONLY_KIND, gatemarks.STUCK_ITEM))
        if design_only:
            rows.append((gatemarks.DESIGN_ONLY_KIND, gatemarks.DESIGN_ONLY_ITEM))
    opens = bool(rows) or (bool(plan.get("ask_human")) and not unattended)
    if not opens:
        return {"open": False, "go": True, "stop_reason": "", "text": "", "deferred": deferred, "asked": [], "pushed": None}
    if unattended:
        asked = [item for _, item in rows]
        pushed = gatemarks.pushed_answer(asked)
        if pushed is None:
            return {"open": False, "go": False, "stop_reason": stopby.NEEDS_HUMAN, "text": "", "deferred": deferred, "asked": [],
                    "pushed": None}
        return {"open": False, "go": True, "stop_reason": "", "text": "", "deferred": deferred, "asked": asked, "pushed": pushed}
    asking = {"node": gatemarks.GATE_NODE, "kinds": list(dict.fromkeys(kind for kind, _ in rows if kind)) or [AXIS_KIND],
              "question": QUESTION, "items": [item for _, item in rows]}
    return {"open": True, "go": True, "stop_reason": "", "text": gate_text(asking, run_id=run_id), "deferred": deferred,
            "asked": [item for _, item in rows], "pushed": None}


def gate_text(asking: dict, *, run_id: str) -> str:
    """問い {node, kinds, question, items} を修正前の関所の文にする（冒頭 3 行と答え方の行つき。組み立ては gatemarks.gate_text）"""
    return gatemarks.gate_text(asking, run_id=run_id, node=gatemarks.GATE_NODE, record_name=RECORD)


def plan_of_env() -> dict:
    return {
        "ready": boundary.flag(os.environ.get("INPUTS_READY")),
        "pass": boundary.flag(os.environ.get("INPUTS_PASS")),
        "stalled": boundary.flag(os.environ.get("INPUTS_STALLED")),
        "ask_human": boundary.flag(os.environ.get("INPUTS_ASK_HUMAN")),
        "gate_axes": boundary.value(os.environ.get("INPUTS_GATE_AXES")),
        "questions": boundary.items(os.environ.get("INPUTS_QUESTIONS")),
    }


def fallback(reason: str) -> dict:
    return {"open": False, "go": False, "stop_reason": boundary.LINE_SCRIPT, "text": "", "deferred": [], "asked": [], "pushed": None}


if __name__ == "__main__":
    boundary.run(lambda: ask(plan_of_env(), unattended=boundary.flag(os.environ.get("INPUTS_UNATTENDED")),
                            design_only=boundary.flag(os.environ.get("INPUTS_DESIGN_ONLY")),
                            run_id=os.environ["WORKFLOW_ID"]),
                fallback)

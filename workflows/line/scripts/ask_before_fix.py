# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正前の関所を開くかと、見せる文を決める節 ask-before-fix（docs/design.md の「線」の「順と関所」の 6）。

入力（with:）は計画の往復の返り（plan-rounds の ready・pass・stalled・round・ask_human・gate_axes・questions）と、始めの節の
unattended・design_only。questions の行は関所の項目の種類と文 {kind, text}（plan-review の返り。lib/gatemarks.py の question_row）。
- 計画ができていない（ready が false）: 関所を開かず、修正へも進まない（go: false。結末は report が計画と判定の返りから決める）
- 必ず開く: 事前審査の壁打ちが止まった（stalled）・往復が 3 周で決着しなかった・設計だけの run（design_only）。事前審査が設計だけの
  行（種類 design_only。止まった理由を尾に持つ gatemarks.design_item）を返していれば、その 1 行だけにして足し直さない（元
  gatemarks.design_item の 1 行。L-D19・P249）
- 開く: 4 つの軸のどれかが ok でない・事前審査が人に聞くと言った（ask_human）・関所の項目が在る。軸の訳は事前審査の項目の尾に在る
  （元 gatemarks._item の「人に聞く訳」）ので、軸の行は項目が 1 つも無い時だけ足す
- 無人の run: 台帳の問い（種類 fork・escalate。gatemarks.ASK_KINDS）だけは関所に載せず deferred で返し（問いの出どころは直す義務から
  外れたまま修正へ進む。元 works/.shared/core/gatemarks.py:637-638）、ほかの種類（狭め・事前審査の穴・方針の文書の変化・事前審査の
  諦め・設計の問い・世界の解の外れ・設計だけ）が在れば開かずに止める（needs-human。今の works で無人の殻が関所に stop を返したのと
  同じ結末）
返り asked は関所に載せた項目の文の並び（開かない時は []）。answer-before-fix がそれを答えの asked にし、fix・plan-review・eyes が人の
通した行として読む。
"""
import os

import linekit
from plan_out import ROUND_LIMIT

with linekit.guarded_imports():
    import gatemarks

AXES = {"obvious": "自明", "world": "世界の解", "clean": "汚くない", "not_overkill": "やりすぎでない"}
AXIS_KIND = "plan_review"
UNSETTLED_ITEM = "事前審査が 3 往復で決着しなかった案: 修正に進まない（continue で修正へ進む・stop で報告へ）"
QUESTION = "事前審査の 4 つの軸と人への問い。通すなら通す範囲と条件を一言に"
RECORD = "run の置き場の gates/gate-before-fix.json"


def ask(plan: dict, *, unattended: bool, design_only: bool, run_id: str) -> dict:
    if not plan.get("ready"):
        return {"open": False, "go": False, "stop_reason": "", "text": "", "deferred": [], "asked": []}
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
        elif (plan.get("round") or 0) >= ROUND_LIMIT and not plan.get("pass"):
            rows.append((gatemarks.DESIGN_ONLY_KIND, UNSETTLED_ITEM))
        if design_only:
            rows.append((gatemarks.DESIGN_ONLY_KIND, gatemarks.DESIGN_ONLY_ITEM))
    opens = bool(rows) or (bool(plan.get("ask_human")) and not unattended)
    if not opens:
        return {"open": False, "go": True, "stop_reason": "", "text": "", "deferred": deferred, "asked": []}
    if unattended:
        return {"open": False, "go": False, "stop_reason": linekit.NEEDS_HUMAN, "text": "", "deferred": deferred, "asked": []}
    asking = {"node": gatemarks.GATE_NODE, "kinds": list(dict.fromkeys(kind for kind, _ in rows if kind)) or [AXIS_KIND],
              "question": QUESTION, "items": [item for _, item in rows]}
    return {"open": True, "go": True, "stop_reason": "", "text": gate_text(asking, run_id=run_id), "deferred": deferred,
            "asked": [item for _, item in rows]}


def gate_text(asking: dict, *, run_id: str) -> str:
    """問い {node, kinds, question, items} を修正前の関所の文にする（冒頭 3 行と答え方の行つき。組み立ては gatemarks.gate_text）"""
    return gatemarks.gate_text(asking, run_id=run_id, node=gatemarks.GATE_NODE, record_name=RECORD)


def plan_of_env() -> dict:
    return {
        "ready": linekit.flag(os.environ.get("INPUTS_READY")),
        "pass": linekit.flag(os.environ.get("INPUTS_PASS")),
        "stalled": linekit.flag(os.environ.get("INPUTS_STALLED")),
        "round": linekit.value(os.environ.get("INPUTS_ROUND")),
        "ask_human": linekit.flag(os.environ.get("INPUTS_ASK_HUMAN")),
        "gate_axes": linekit.value(os.environ.get("INPUTS_GATE_AXES")),
        "questions": linekit.items(os.environ.get("INPUTS_QUESTIONS")),
    }


def fallback(reason: str) -> dict:
    return {"open": False, "go": False, "stop_reason": linekit.LINE_SCRIPT, "text": "", "deferred": [], "asked": []}


if __name__ == "__main__":
    linekit.run(lambda: ask(plan_of_env(), unattended=linekit.flag(os.environ.get("INPUTS_UNATTENDED")),
                            design_only=linekit.flag(os.environ.get("INPUTS_DESIGN_ONLY")),
                            run_id=os.environ["WORKFLOW_ID"]),
                fallback)

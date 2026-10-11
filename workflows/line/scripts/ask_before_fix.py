"""修正前の関所を開くかと、見せる文を決める節 ask-before-fix（docs/design.md の「線」の「順と関所」の 6）。

入力（with:）は計画の往復の返り（plan-rounds の ready・pass・stalled・round・ask_human・gate_axes・questions）と、始めの節の
unattended・design_only。
- 計画ができていない（ready が false）: 関所を開かず、修正へも進まない（go: false。結末は report が計画と判定の返りから決める）
- 必ず開く: 事前審査の壁打ちが止まった（stalled）・往復が 3 周で決着しなかった・設計だけの run（design_only）
- 開く: 4 つの軸のどれかが ok でない・事前審査が人に聞くと言った（ask_human）・人への問いが在る
- 無人の run: 人への問い（台帳の問い）は関所に載せず、報告へ回す（deferred）。それでも開くはずの時は開かずに止める
  （needs-human。今の works で無人の殻が関所に stop を返したのと同じ結末）
"""
import os

import linekit

import gatemarks

ROUND_LIMIT = 3
AXES = {"obvious": "自明", "world": "世界の解", "clean": "汚くない", "not_overkill": "やりすぎでない"}
AXIS_KIND = "plan_review"
UNSETTLED_ITEM = "事前審査が 3 往復で決着しなかった案: 修正に進まない（continue で修正へ進む・stop で報告へ）"
QUESTION = "事前審査の 4 つの軸と人への問い。通すなら通す範囲と条件を一言に"
RECORD = "run の置き場の gates/gate-before-fix.json"


def ask(plan: dict, *, unattended: bool, design_only: bool, run_id: str) -> dict:
    if not plan.get("ready"):
        return {"open": False, "go": False, "stop_reason": "", "text": "", "deferred": []}
    rows = []
    for key, word in AXES.items():
        axis = (plan.get("gate_axes") or {}).get(key)
        if isinstance(axis, dict) and axis.get("ok") is False:
            rows.append((AXIS_KIND, f"{word}（{key}）の軸が通らない: {axis.get('note') or '（訳が無い）'}"))
    questions = [str(q) for q in plan.get("questions") or []]
    deferred = questions if unattended else []
    rows += [] if unattended else [(gatemarks.ASK_KINDS[0], q) for q in questions]
    if plan.get("stalled"):
        rows.append((gatemarks.DESIGN_ONLY_KIND, gatemarks.STUCK_ITEM))
    elif (plan.get("round") or 0) >= ROUND_LIMIT and not plan.get("pass"):
        rows.append((gatemarks.DESIGN_ONLY_KIND, UNSETTLED_ITEM))
    if design_only:
        rows.append((gatemarks.DESIGN_ONLY_KIND, gatemarks.DESIGN_ONLY_ITEM))
    opens = bool(rows) or (bool(plan.get("ask_human")) and not unattended)
    if not opens:
        return {"open": False, "go": True, "stop_reason": "", "text": "", "deferred": deferred}
    if unattended:
        return {"open": False, "go": False, "stop_reason": linekit.NEEDS_HUMAN, "text": "", "deferred": deferred}
    asking = {"node": gatemarks.GATE_NODE, "kinds": list(dict.fromkeys(kind for kind, _ in rows)) or [AXIS_KIND],
              "question": QUESTION, "items": [item for _, item in rows]}
    text = gatemarks.gate_text(asking, run_id=run_id, node=gatemarks.GATE_NODE, record_name=RECORD)
    return {"open": True, "go": True, "stop_reason": "", "text": text, "deferred": deferred}


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
    return {"open": False, "go": False, "stop_reason": linekit.LINE_SCRIPT, "text": "", "deferred": []}


if __name__ == "__main__":
    linekit.run(lambda: ask(plan_of_env(), unattended=linekit.flag(os.environ.get("INPUTS_UNATTENDED")),
                            design_only=linekit.flag(os.environ.get("INPUTS_DESIGN_ONLY")),
                            run_id=os.environ["WORKFLOW_ID"]),
                fallback)

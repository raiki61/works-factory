# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正前の関所を開くかと、見せる文を決める節 ask-before-fix（docs/design.md の「線」の「順と関所」の 6）。

入力（with:）は計画の往復の返り（plan-rounds の ready・pass・stalled・ask_human・gate_axes・questions）と、始めの節の
unattended・design_only。
- 計画ができていない（ready が false）: 関所を開かず、修正へも進まない（go: false。結末は report が計画と判定の返りから決める）
- 必ず開く: 事前審査の壁打ちが止まった（stalled。往復の安全の上限の周で止めた時も stalled で、理由は questions に載る）・
  設計だけの run（design_only）
- 開く: 4 つの軸のどれかが ok でない・事前審査が人に聞くと言った（ask_human）・人への問いが在る
- 無人の run: 人への問い（台帳の問い）は関所に載せず、deferred で返す（report に受ける入力が無く、まだ報告には届かない。
  docs/design.md の「report の返り」）。それでも開くはずの時は開かずに止める
  （needs-human。今の works で無人の殻が関所に stop を返したのと同じ結末）
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
    if design_only:
        rows.append((gatemarks.DESIGN_ONLY_KIND, gatemarks.DESIGN_ONLY_ITEM))
    opens = bool(rows) or (bool(plan.get("ask_human")) and not unattended)
    if not opens:
        return {"open": False, "go": True, "stop_reason": "", "text": "", "deferred": deferred}
    if unattended:
        return {"open": False, "go": False, "stop_reason": stopby.NEEDS_HUMAN, "text": "", "deferred": deferred}
    asking = {"node": gatemarks.GATE_NODE, "kinds": list(dict.fromkeys(kind for kind, _ in rows)) or [AXIS_KIND],
              "question": QUESTION, "items": [item for _, item in rows]}
    return {"open": True, "go": True, "stop_reason": "", "text": gate_text(asking, run_id=run_id), "deferred": deferred}


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
    return {"open": False, "go": False, "stop_reason": boundary.LINE_SCRIPT, "text": "", "deferred": []}


if __name__ == "__main__":
    boundary.run(lambda: ask(plan_of_env(), unattended=boundary.flag(os.environ.get("INPUTS_UNATTENDED")),
                            design_only=boundary.flag(os.environ.get("INPUTS_DESIGN_ONLY")),
                            run_id=os.environ["WORKFLOW_ID"]),
                fallback)

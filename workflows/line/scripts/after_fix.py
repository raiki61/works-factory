# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正の後に、案の直しを差し込むかを決める node after-fix（docs/design/line.md の 4.2）。

when: は配列が空かを比べられないので、ここで数える。fix の replan_items（裁定が誤りとした計画の項目）が空でなければ案の直し（1 run に
1 度。line に差し込みは 1 つしか無い）。真の時は、案の直しの plan の port prior に渡す承認済みの案の周（最後の周の reply・fields〔欄 plan〕・
fix_plan・ripple と、全部の周の handoff。review と record は null。plan の設計書の 1.6 の plan-prior.schema.json の形）を place の
src.files.REPLAN_PRIOR に書いて pointer を返す。例外の時は止めの語 works:line-script を返し、fixed が held にして試験の関門から先へ進めない。

入力（with:）: replan_items（fix の出力）・rounds（計画の往復の記録の pointer。読まない。往復の外の周であることの控え）・plan・fix_plan・
ripple・reply（承認済みの案の最後の周の出力の pointer か null）・handoffs（全部の周の handoff の pointer の並び）・round（周の番号）
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def prior_doc(env) -> dict:
    """案の直しの plan の prior（plan-prior.schema.json の欄 round・reply・fields・fix_plan・ripple・review・record・handoffs）"""
    rnd = ports.parsed(env.get("INPUTS_ROUND"))
    return {"round": rnd if isinstance(rnd, int) and rnd >= 1 else 1, "reply": ports.parsed(env.get("INPUTS_REPLY")),
            "fields": ports.parsed(env.get("INPUTS_PLAN")), "fix_plan": ports.parsed(env.get("INPUTS_FIX_PLAN")),
            "ripple": ports.parsed(env.get("INPUTS_RIPPLE")), "review": None, "record": None,
            "handoffs": [h for h in ports.parsed(env.get("INPUTS_HANDOFFS")) or [] if isinstance(h, dict)]}


def compute():
    from src import files
    env = {"INPUTS_REPLAN_ITEMS": os.environ.get("INPUTS_REPLAN_ITEMS"), "INPUTS_ROUND": os.environ.get("INPUTS_ROUND"),
           "INPUTS_REPLY": os.environ.get("INPUTS_REPLY"), "INPUTS_PLAN": os.environ.get("INPUTS_PLAN"),
           "INPUTS_FIX_PLAN": os.environ.get("INPUTS_FIX_PLAN"), "INPUTS_RIPPLE": os.environ.get("INPUTS_RIPPLE"),
           "INPUTS_HANDOFFS": os.environ.get("INPUTS_HANDOFFS"), "INPUTS_ROUNDS": os.environ.get("INPUTS_ROUNDS")}
    items = ports.parsed(env["INPUTS_REPLAN_ITEMS"]) or []
    if not isinstance(items, list):
        raise ValueError(f"replan_items が配列でない（{type(items).__name__}）")
    if not items:
        return {"replan": False, "prior": None, "stop_reason": ""}
    path = ports.place() / files.REPLAN_PRIOR
    path.write_text(json.dumps(prior_doc(env), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"replan": True, "prior": ports.pointer(path), "stop_reason": ""}


def fallback(reason: str) -> dict:
    from src import guard
    return {"replan": False, "prior": None, "stop_reason": guard.LINE_SCRIPT}


ports.run(compute, fallback)

"""仕様駆動の run の判定と計画の往復の組み直し（node spec-rounds。docs/design/spec-driven.md の 6.2 の足す node の 8・6.8 の 1 と 2）。

判定の役（spec-diagnose）と計画の部品（spec-plan）を 1 回ずつ通した返りを、今の judge-out と plan-rounds-out の受け皿の got と同じ形
（fix-in と ask_before_fix が読む欄の全部）に組み直す。修正前の承認ノードの前の段と fix-in が同じ値を読む。

- judge_part(diagnose, purpose_text, forced) -> 判定の部: 判定の役の返りと、今の本線でその欄を作る段が回らなかった run と同じ値
- rounds_part(plan, asks) -> 往復の部: 計画の部品の返りと、往復を 1 回で終えた値（record・review は無い。review_status は ok）
- narrow_rows(fix_plan, repo, files) -> asks の行: lib/gatemarks.narrow_asks に、仕様駆動の run の軸の材料（出どころの照らしの根は
  表と設計書、世界の解の行・構造の目の行は無い）を渡す
- collect_values(values) -> collect の読む値: 仕様駆動の run の値（spec-rounds の判定の部と往復の部・spec- の付いた承認ノードの返り）を
  今の欄の名（judge・rounds・ask_before_fix・answer_before_fix）に重ねる。依頼の文の run は values のまま
"""
from __future__ import annotations

import pathlib

import cite        # lib/。決め手の出どころが現物に在るか
import converge    # lib/。planned_units
import gatemarks   # lib/。narrow_asks・AxisFacts
import headdepth   # lib/。段の語

# fix_in.NAMES["judge"] のうち、仕様駆動の run の中で回らない段が作る欄（今の本線でもその段が回らない run は null）
NOT_RUN = ("constraints", "world", "spec", "excluded", "decisions", "tier_record", "verify")
DIAGNOSE = ("units", "questions", "judgment", "answer_ties", "out_of_purpose", "materials", "brief", "inputs")


def judge_part(diagnose: dict, purpose, purpose_text: str, forced: str) -> dict:
    """判定の部。ok は真・stop_reason は空（spec-rounds は形 check を通った run だけで回る）。tier は thickness の名指しか標準"""
    out = {name: diagnose.get(name) for name in DIAGNOSE}
    out.update({"ok": True, "stop_reason": "", "ready": diagnose.get("ready") is True, "units": diagnose.get("units") or [],
                "questions": diagnose.get("questions") or [], "purpose": purpose, "purpose_text": purpose_text, "means": [],
                "tier": forced or headdepth.STANDARD})
    out.update(dict.fromkeys(NOT_RUN))
    return out


def rounds_part(plan: dict, asks: list) -> dict:
    """往復の部（ask_before_fix.ROUNDS の 21 と fix_in.NAMES["rounds"]）"""
    return {"done": True, "ok": True, "status": plan.get("status"), "round": 1, "plan_prior": None, "record": None,
            "plan": plan.get("plan"), "fix_plan": plan.get("fix_plan"), "reply": plan.get("reply"), "handoffs": [],
            "ripple": plan.get("ripple"), "owed": list(plan.get("owed") or []), "gave_up": None, "stalled": False, "capped": False,
            "review": None, "asks": asks, "deviations": [], "review_status": "ok", "review_reason": "", "stop_reason": ""}


def narrow_rows(fix_plan, repo, files) -> list:
    """計画の行の narrows を承認ノードに回しうる行にする。決め手の出どころは、依頼の引用の元を表と設計書の本文にして照らす"""
    repo = pathlib.Path(repo)
    roots = [str((repo / f).resolve()) for f in files]
    quoted = "\n".join((repo / f).read_text(encoding="utf-8", errors="replace") for f in files if (repo / f).is_file())
    rows = (fix_plan or {}).get("plan") if isinstance(fix_plan, dict) else None
    facts = gatemarks.AxisFacts(cite_ok=lambda text: cite.sources_problem(text, str(repo), roots, quoted), world_rows=False,
                                ups=frozenset(), dirty=frozenset(), answered=None, planned=frozenset(converge.planned_units(rows)))
    return gatemarks.narrow_asks(rows, None, facts)


NOT_RUN_WHY = "仕様駆動の run では回さない（会話の中で回したか、判定の役だけを工場の中で回した）"
DIAGNOSE_TITLE = "根本の診断"   # 判定のまとめの節の見出し（src/sections.py の JUDGE_DIAGNOSE と同じ字）


def collect_values(values: dict) -> dict:
    """collect の読む値に、仕様駆動の run の値を今の欄の名で重ねる（判定の graph・計画の往復・今の修正前の承認ノードは仕様駆動の run では
    回らないので、その欄は空）。判定の部には、判定のまとめが持つ報告の欄（sections ほか）を、回さなかった段の値で足す"""
    out = dict(values)
    spec = values.get("spec_rounds") if isinstance(values.get("spec_rounds"), dict) else {}
    if out.get("rounds") is None and isinstance(spec.get("rounds"), dict):
        out["rounds"] = spec["rounds"]
    if out.get("judge") is None and isinstance(spec.get("judge"), dict):
        diagnose = values.get("spec_diagnose") if isinstance(values.get("spec_diagnose"), dict) else {}
        out["judge"] = {**spec["judge"], "reason": "", "purpose_source": "", "purpose_review": None,
                        "world_state": {"status": "skipped", "reason": NOT_RUN_WHY}, "spec_rows": None, "spec_origin": "",
                        "pr_drafts": None, "downgrades": list(diagnose.get("downgrades") or []), "tier_why": NOT_RUN_WHY, "row_asks": [],
                        "verify_why": NOT_RUN_WHY, "report": [], "optional": [],
                        "sections": [{"title": DIAGNOSE_TITLE, "lines": [str(x) for x in diagnose.get("report") or []]}]}
    for name in ("ask_before_fix", "answer_before_fix"):
        if out.get(name) is None and values.get(f"spec_{name}") is not None:
            out[name] = values[f"spec_{name}"]
    return out

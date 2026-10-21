# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""仕様駆動の run の判定と計画の往復を、今の受け皿の形に組み直す node spec-rounds（docs/design/spec-driven.md の 6.2 の足す node の 8。
決まりは src/specrounds.py）。返り {judge, rounds, stop_reason, reason}。例外の時は止めの語 works:line-script で、後ろは when: で飛ぶ。

入力（with:）: diagnose（spec-diagnose-out の got）・plan（spec-plan-out の got）・entry（spec-entry-out の got）・ports（start の配る値）
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

DIAGNOSE = ("ok", "ready", "judgment", "units", "questions", "inputs", "brief", "materials", "out_of_purpose", "answer_ties")
PLAN = ("status", "plan", "fix_plan", "reply", "ripple", "owed")
ENTRY = ("purpose", "spec_files")


def _doc(ptr):
    """pointer の先の JSON（null は None）"""
    return None if ptr is None else json.loads(ports.file(json.dumps(ptr)).read_text(encoding="utf-8"))


def compute():
    from src import specrounds
    raw = {"diagnose": os.environ.get("INPUTS_DIAGNOSE"), "plan": os.environ.get("INPUTS_PLAN"),
           "entry": os.environ.get("INPUTS_ENTRY"), "ports": os.environ.get("INPUTS_PORTS")}
    diagnose = dict(ports.picked(raw["diagnose"], DIAGNOSE) or {})
    plan = dict(ports.picked(raw["plan"], PLAN) or {})
    entry = dict(ports.picked(raw["entry"], ENTRY) or {})
    if not (diagnose and plan and entry):
        raise ValueError("判定の役・計画の部品・入口の返す値のどれかが無い（spec-rounds は 3 つが揃った run だけで回る）")
    given = ports.parsed(raw["ports"]) or {}
    purpose = _doc(entry["purpose"]) or {}
    asks = specrounds.narrow_rows(_doc(plan["fix_plan"]), Path.cwd(), entry["spec_files"] or [])
    return {"judge": specrounds.judge_part(diagnose, entry["purpose"], str(purpose.get("purpose_text") or ""), str(given.get("forced") or "")),
            "rounds": specrounds.rounds_part(plan, asks), "stop_reason": "", "reason": ""}


def fallback(reason: str) -> dict:
    from src import guard
    return {"judge": None, "rounds": None, "stop_reason": guard.LINE_SCRIPT, "reason": reason}


ports.run(compute, fallback)

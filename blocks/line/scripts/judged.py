# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""判定（再審が走れば再審）を後ろへ渡す node judged（docs/design/line.md の 4.4。決まりは src/stages.py の judged）。

再審（diagnose を直に include した rejudge-run）の返す node が落ちても落ちないように、受け皿 rejudge-run-out の got を読む。走るはず
（fixed の rejudge が真）なのに got が null なら、再審が返らなかったと止めの語 works:rejudge で止める。前後の比べ（後に開いた単位・
block から下げた単位・異議が名指さずに変わった単位）は再審の出口を読み、読めなければ訳を unread。例外の時は works:line-script。

入力（with:）: fix_in（fix-in の出力まるごと。1 回目の判定の値）・rejudge_due（fixed の rejudge）・objection（fixed の objection）・
rejudge（受け皿 rejudge-run-out の got か null）・fixed_units（fixed の units。再審が開いた単位のうち、修正の段が受けた単位を
「この run では直していない」から除く）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

FIX_IN = ("judgment", "units", "answer_ties", "materials", "out_of_purpose")
REJUDGE = ("ok", "status", "mode", "stop_reason", "reason", "ready", "judgment", "units", "questions", "inputs", "brief", "materials",
           "out_of_purpose", "answer_ties", "rejudge_verdict", "rejudge_exit", "rejudge_diff", "downgrades", "report")


def compute():
    raw = {"fix_in": os.environ.get("INPUTS_FIX_IN"), "due": os.environ.get("INPUTS_REJUDGE_DUE"),
           "objection": os.environ.get("INPUTS_OBJECTION"), "rejudge": os.environ.get("INPUTS_REJUDGE"),
           "fixed_units": os.environ.get("INPUTS_FIXED_UNITS")}
    from src import stages
    fix_in = ports.picked(raw["fix_in"], FIX_IN)
    rejudge = ports.picked(raw["rejudge"], REJUDGE)
    return stages.judged(dict(fix_in or {}), None if rejudge is None else dict(rejudge), due=ports.flag(raw["due"]),
                         objection=ports.text(raw["objection"]), fixed_units=fixed_units(raw["fixed_units"]))


def fixed_units(raw) -> list:
    """修正の段が受けた単位の行（fixed の units。配列でなければ ValueError）"""
    got = ports.parsed(raw)
    if got is None:
        return []
    if not isinstance(got, list):
        raise ValueError(f"fixed_units が配列でない（{type(got).__name__}）")
    return [u for u in got if isinstance(u, dict)]


def fallback(reason: str) -> dict:
    from src import guard
    return {"units": [], "judgment": None, "answer_ties": None, "materials": None, "out_of_purpose": None, "rejudged": False,
            "rejudge_verdict": None, "rejudge_exit": None, "rejudge_diff": None, "new_open_units": [], "lowered": [],
            "unnamed_changed": [], "unread": "", "lines": [], "carry": [], "stop_reason": guard.LINE_SCRIPT}


ports.run(compute, fallback)

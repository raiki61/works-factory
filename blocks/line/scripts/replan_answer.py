# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""案の直しの承認ノードの答えを受ける返し answer-replan（埋め P2。docs/design/line.md の 2 節の 3・5.2。今の
workflows/line/scripts/replan_answer.py の決まりのまま）。

答えの読みと返り {go, answer, stop_reason} は gate_answer と同じ（lib/answer.py の taken。asked は ask-replan が見せた項目の行、無人の
run が推しで進んだ時は pushed を答えとして記録する）。加えて 2 度目の修正に渡す物:
- fix_answers: 修正前の承認ノードの条件が先・案の直しの一言が後の文（元 works の replan._notes の頭の 2 つ）と、修正前の承認ノードで
  見せた問いの行 asked（人が通した問いの単位を 2 度目の修正も直す）。どちらかが推しで通した答えなら answer.PUSHED を合わせて持つ
- fix_notes: 採った項目ごとの、案の直しの事前審査の穴のうち人に聞く種類（gates.HUMAN_FACE_KINDS）でない物（replan.fix_notes）。
  事前審査が飛んだ・読めない時は訳の 1 行。止める答えの時は ""
- fix_ripple: 案の直しが作り直した波及の一覧の pointer。作り直せなかった時だけ 1 回目の物（replan.remade_ripple）。止める答えは null
- plan_review: 2 度目の修正と 2 度目の差分の審査に渡す事前審査の返答（案の直しの事前審査の holes）。飛んだ時は null
- units_tier: 直した案の単位を、案の直しが走ったので全部標準と読み、1 回目の行を単位ごとに置き換えた並び（今の redepth.merged）
- skip_rerun: いつも []（全部が標準なので省く単位は無い）

入力（with:）: gate・go・stop_reason・place・asked・pushed（承認ノードと ask-replan の返り）・before_fix（修正前の承認ノードの答え）・
replan（replan-out の got）・review（replan-review-out の got か null）・items（直した項目の番号）・first_ripple（計画の往復の波及の一覧）・
units_tier（fix-in の単位の深さ）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

REPLAN = ("ok", "plan", "fix_plan", "ripple", "owed")
REVIEW = ("ok", "status", "holes")
# 元 replan.FIX_NOTES_HEAD・NOTE_HEAD。答えた者を名乗らない（推しで通した答えの印は、読み手が answer.said で一言の前に 1 度だけ置く）
FIX_NOTES_HEAD = "## 修正前の承認ノード（gate-before-fix）で答えた条件（1 回目の修正の段と同じく、この段にも効く）"
NOTE_HEAD = "## 承認ノード gate-replan の一言"
REPLANNED = "案の直しが走った"


def fix_answers(before_fix, replan_answer) -> dict | None:
    """2 度目の修正の answers {decision, text, asked}。decision は後の承認ノードの答えの語で、text は条件と一言のうち在る物、asked は
    修正前の承認ノードの答えの物。どちらかが推しで通した答えなら、採った推しを合わせた欄 answer.PUSHED も持つ。どちらの承認ノードも
    開かなかった run は null"""
    import answer
    import oneline
    answered = [a for a in (before_fix, replan_answer) if isinstance(a, dict)]
    if not answered:
        return None
    prior = str(before_fix.get("text") or "").strip() if isinstance(before_fix, dict) else ""
    note = oneline.one_line(replan_answer.get("text") or "") if isinstance(replan_answer, dict) else ""
    parts = [f"{FIX_NOTES_HEAD}\n\n{prior}\n"] if prior else []
    if note:
        parts.append(f"{NOTE_HEAD}\n\n{note}\n")
    asked = before_fix.get("asked") if isinstance(before_fix, dict) else None
    got = {"decision": answered[-1]["decision"], "text": "\n".join(parts), "asked": asked if isinstance(asked, list) else []}
    if any(answer.by_push(a) for a in answered):
        got[answer.PUSHED] = [r for a in answered for r in a.get(answer.PUSHED) or []]
    return got


def fix_notes(review, fix_plan, items: list) -> str:
    """2 度目の修正に渡す機械の申し送り（replan.fix_notes）。事前審査の返りが無い・指す先が無い・読めない時は訳の 1 行（2 度目の修正の
    notes に載る）。pointer の形の違い（型・ほかの run・run directory の外）は約束の誤りなので落ちる（src.gates.located）"""
    import oneline
    import replan
    from src import gates
    if review is None or review["holes"] is None:
        return replan.NO_REVIEW_WHY.format(why="案の直しの事前審査が飛ばされた（出力が無い）")
    unread: list = []
    doc = gates.read_located(review["holes"], "案の直しの事前審査の返答", unread)
    plan = gates.read_located(fix_plan, "案の直しの修正案", unread)
    if unread or not isinstance(doc, dict):
        why = "・".join(unread) or "案の直しの事前審査の返答が JSON の object でない"
        return replan.NO_REVIEW_WHY.format(why=oneline.one_line(why))
    try:
        return replan.fix_notes(doc, plan, items, gates.HUMAN_FACE_KINDS)
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        return replan.NO_REVIEW_WHY.format(why=oneline.one_line(f"{type(error).__name__}: {error}"))


def fix_ripple(again, first):
    """2 度目の修正に渡す波及の一覧の pointer（replan.remade_ripple。作り直せなかった時だけ 1 回目の物）"""
    import replan
    from src import gates
    doc = gates.read_located(again, "作り直した波及の一覧", []) if again is not None else None
    return again if replan.remade_ripple(doc) else first


def units_tier(first: list, owed: list) -> list:
    """1 回目の単位の深さの行を、直した案の単位（全部標準）で単位ごとに置き換えた並び（直した案だけに在る単位は後ろに足す）"""
    from src import tiers
    rows = {r["unit_id"]: r for r in first or [] if isinstance(r, dict) and r.get("unit_id")}
    for key in owed or []:
        if isinstance(key, str) and key:
            rows[key] = {"unit_id": key, "depth": tiers.STANDARD, "why": REPLANNED}
    return list(rows.values())


def compute() -> dict:
    raw = {"gate": os.environ.get("INPUTS_GATE"), "go": os.environ.get("INPUTS_GO"), "stop_reason": os.environ.get("INPUTS_STOP_REASON"),
           "place": os.environ.get("INPUTS_PLACE"), "before_fix": os.environ.get("INPUTS_BEFORE_FIX"),
           "asked": os.environ.get("INPUTS_ASKED"), "pushed": os.environ.get("INPUTS_PUSHED"), "replan": os.environ.get("INPUTS_REPLAN"),
           "review": os.environ.get("INPUTS_REVIEW"), "items": os.environ.get("INPUTS_ITEMS"),
           "first_ripple": os.environ.get("INPUTS_FIRST_RIPPLE"), "units_tier": os.environ.get("INPUTS_UNITS_TIER")}
    import answer
    from src import gates

    asked = ports.parsed(raw["asked"]) or []
    replan = ports.picked(raw["replan"], REPLAN)
    review = ports.picked(raw["review"], REVIEW)
    items = ports.parsed(raw["items"]) or []
    first_tier = ports.parsed(raw["units_tier"]) or []
    got = answer.taken(ports.parsed(raw["gate"]), go=ports.flag(raw["go"]), stop_reason=ports.text(raw["stop_reason"]),
                       place=ports.text(raw["place"]), folder=ports.place(), asked=asked if isinstance(asked, list) else [],
                       pushed=ports.parsed(raw["pushed"]))
    go = got["go"]
    return {**got, "fix_answers": fix_answers(ports.parsed(raw["before_fix"]), got["answer"]),
            "fix_notes": fix_notes(review, (replan or {}).get("fix_plan"), items) if go else "",
            "fix_ripple": fix_ripple((replan or {}).get("ripple"), ports.parsed(raw["first_ripple"])) if go else None,
            "plan_review": (review or {}).get("holes") if go and review is not None else None,
            "units_tier": units_tier(first_tier, (replan or {}).get("owed") or []), "skip_rerun": []}


def fallback(reason: str) -> dict:
    from src import guard

    return {"go": False, "answer": None, "stop_reason": guard.LINE_SCRIPT, "fix_answers": None, "fix_notes": "", "fix_ripple": None,
            "plan_review": None, "units_tier": [], "skip_rerun": []}


ports.run(compute, fallback)

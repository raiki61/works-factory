# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""案の直しの関所の答えを受ける返しの節 answer-replan（埋め P2）。

関所の答えの読みと返り {go, answer, stop_reason} は gate_answer と同じ。加えて、2 度目の修正に渡す answers（fix_answers）を返す:
修正前の関所の答えの条件と案の直しの関所の一言を見出しの下に並べた文（元 works/.shared/core/replan.py の _notes。人が修正前の
関所で答えた条件は 2 度目の修正にも効く）と、修正前の関所で見せた問いの行 asked（人が通した問いの単位を 2 度目の修正も直す）。

答え {decision, text, asked} の asked は案の直しの関所に見せた項目の行（ask-replan の asked。「項目 <id>: …」の行で、報告と最後の関所が
項目ごとに人が承認したかを読む。lib/replan.amend_lines）。

fix_notes は 2 度目の修正に渡す機械の申し送り（元 replan._notes の 3 つ目の節。fix の入力 notes）: 採った項目（2 度目の修正が走る
時は直した項目の全部。関所の答えは 1 つの語で聞いた項目の全部に効く）ごとに、案の直しの事前審査の返り review の穴のうち人に聞く種類
（lib/boardview.py の HUMAN_FACE_KINDS）でない物を lib/replan.fix_notes の見出しの下に並べる。人の答え fix_answers には混ぜない。
事前審査が飛ばされた・読めない時は訳を 1 行（replan.NO_REVIEW_WHY）。止める答えの時は ""。
fix_ripple は 2 度目の修正に渡す波及の一覧の指し札: 案の直しが作り直した一覧（ripple）、作り直せなかった（読めない・作れなかった訳
error を持つ）時だけ 1 回目の案の一覧（first_ripple）。元 works/darkfactory/lib/line_edge.py:169 の refit_ripple_file。止める答えの時は null。

入力（with:）: gate_answer の入力と before_fix（修正前の関所の答え）・asked（関所に見せた項目の行）・review（replan-review の review。
`{from, if_skipped: null}`）・plan（案の直しの修正案の指し札。項目の単位を隣の修正案の役の返答から引く）・items（直した項目の id）・
ripple（案の直しの波及の一覧の指し札）・first_ripple（計画の往復の波及の一覧の指し札）
"""
import json
import os
from pathlib import Path

import gate_answer
import linekit
from linekit import boundary

with linekit.guarded_imports():
    import boardview
    import planfile
    import replan

FIX_NOTES_HEAD = "## 修正前の関所（gate-before-fix）で人が答えた条件（1 回目の修正の段と同じく、この段にも効く）"   # 元 replan.FIX_NOTES_HEAD
NOTE_HEAD = "## 人の一言（関所 gate-replan）"   # 元 replan.NOTE_HEAD


def fix_answers(before_fix, replan) -> dict | None:
    """2 度目の修正の answers {decision, text, asked}。decision は後の関所の答えの語で、text は条件と一言のうち在る物（元 replan._notes の
    頭の 2 つ）、asked は修正前の関所の答えの物。どちらの関所も開かなかった run は null"""
    answered = [a for a in (before_fix, replan) if isinstance(a, dict)]
    if not answered:
        return None
    prior = str(before_fix.get("text") or "").strip() if isinstance(before_fix, dict) else ""
    note = " ".join(str(replan.get("text") or "").split()) if isinstance(replan, dict) else ""
    parts = [f"{FIX_NOTES_HEAD}\n\n{prior}\n"] if prior else []
    if note:
        parts.append(f"{NOTE_HEAD}\n\n{note}\n")
    asked = before_fix.get("asked") if isinstance(before_fix, dict) else None
    return {"decision": answered[-1]["decision"], "text": "\n".join(parts), "asked": asked if isinstance(asked, list) else []}


def fix_notes(review_raw, plan_raw, items_raw) -> str:
    """2 度目の修正に渡す機械の申し送り（replan.fix_notes）。事前審査の返りが無い・読めない時は訳の 1 行"""
    review = linekit.value(review_raw)
    try:
        if review is None:
            raise ValueError("案の直しの事前審査が飛ばされた（返りが無い）")
        doc = json.loads(boundary.resolve(review).read_text(encoding="utf-8"))
        ptr = linekit.value(plan_raw)
        reply = boundary.resolve(ptr).parent / planfile.FIX_PLAN_FILE if ptr is not None else None
        plan = json.loads(reply.read_text(encoding="utf-8")) if reply is not None and reply.is_file() else None
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        return replan.NO_REVIEW_WHY.format(why=" ".join(f"{type(error).__name__}: {error}".split()))
    return replan.fix_notes(doc if isinstance(doc, dict) else {}, plan, linekit.items(items_raw), boardview.HUMAN_FACE_KINDS)


def fix_ripple(ripple_raw, first_raw):
    """2 度目の修正に渡す波及の一覧の指し札（replan.remade_ripple。作り直せなかった時だけ 1 回目の物）"""
    again = linekit.value(ripple_raw)
    try:
        doc = json.loads(boundary.resolve(again).read_text(encoding="utf-8")) if again is not None else None
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        doc = None
    return again if replan.remade_ripple(doc) else linekit.value(first_raw)


def answer(gate_raw, go_raw, stop_raw, before_fix_raw, place: str, artifacts: Path, asked_raw=None, review_raw=None, plan_raw=None,
           items_raw=None, ripple_raw=None, first_ripple_raw=None) -> dict:
    got = gate_answer.answer(gate_raw, go_raw, stop_raw, place, artifacts, asked_raw)
    return {**got, "fix_answers": fix_answers(linekit.value(before_fix_raw), got["answer"]),
            "fix_notes": fix_notes(review_raw, plan_raw, items_raw) if got["go"] else "",
            "fix_ripple": fix_ripple(ripple_raw, first_ripple_raw) if got["go"] else None}


def fallback(reason: str) -> dict:
    return {**gate_answer.fallback(reason), "fix_answers": None, "fix_notes": "", "fix_ripple": None}


if __name__ == "__main__":
    linekit.run(lambda: answer(os.environ.get("INPUTS_GATE"), os.environ.get("INPUTS_GO"), os.environ.get("INPUTS_STOP_REASON"),
                               os.environ.get("INPUTS_BEFORE_FIX"), os.environ["INPUTS_PLACE"], Path(os.environ["ARTIFACTS_DIR"]),
                               os.environ.get("INPUTS_ASKED"), os.environ.get("INPUTS_REVIEW"), os.environ.get("INPUTS_PLAN"),
                               os.environ.get("INPUTS_ITEMS"), os.environ.get("INPUTS_RIPPLE"), os.environ.get("INPUTS_FIRST_RIPPLE")),
                fallback)

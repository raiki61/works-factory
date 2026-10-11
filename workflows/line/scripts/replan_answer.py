# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""案の直しの関所の答えを受ける返しの節 answer-replan（埋め P2）。

関所の答えの読みと返り {go, answer, stop_reason} は gate_answer と同じ。加えて、2 度目の修正に渡す answers（fix_answers）を返す:
修正前の関所の答えの条件と案の直しの関所の一言を見出しの下に並べた文（元 works/.shared/core/replan.py の _notes。人が修正前の
関所で答えた条件は 2 度目の修正にも効く）。

入力（with:）: gate_answer の入力と before_fix（修正前の関所の答え）
"""
import os
from pathlib import Path

import gate_answer
import linekit

FIX_NOTES_HEAD = "## 修正前の関所（gate-before-fix）で人が答えた条件（1 回目の修正の段と同じく、この段にも効く）"   # 元 replan.FIX_NOTES_HEAD
NOTE_HEAD = "## 人の一言（関所 gate-replan）"   # 元 replan.NOTE_HEAD


def fix_answers(before_fix, replan) -> dict | None:
    """2 度目の修正の answers {decision, text}。decision は後の関所の答えの語で、text は条件と一言のうち在る物（元 replan._notes の頭の
    2 つ）。どちらの関所も開かなかった run は null"""
    answered = [a for a in (before_fix, replan) if isinstance(a, dict)]
    if not answered:
        return None
    prior = str(before_fix.get("text") or "").strip() if isinstance(before_fix, dict) else ""
    note = " ".join(str(replan.get("text") or "").split()) if isinstance(replan, dict) else ""
    parts = [f"{FIX_NOTES_HEAD}\n\n{prior}\n"] if prior else []
    if note:
        parts.append(f"{NOTE_HEAD}\n\n{note}\n")
    return {"decision": answered[-1]["decision"], "text": "\n".join(parts)}


def answer(gate_raw, go_raw, stop_raw, before_fix_raw, place: str, artifacts: Path) -> dict:
    got = gate_answer.answer(gate_raw, go_raw, stop_raw, place, artifacts)
    return {**got, "fix_answers": fix_answers(linekit.value(before_fix_raw), got["answer"])}


def fallback(reason: str) -> dict:
    return {**gate_answer.fallback(reason), "fix_answers": None}


if __name__ == "__main__":
    linekit.run(lambda: answer(os.environ.get("INPUTS_GATE"), os.environ.get("INPUTS_GO"), os.environ.get("INPUTS_STOP_REASON"),
                               os.environ.get("INPUTS_BEFORE_FIX"), os.environ["INPUTS_PLACE"], Path(os.environ["ARTIFACTS_DIR"])),
                fallback)

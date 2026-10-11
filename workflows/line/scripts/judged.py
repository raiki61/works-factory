# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""判定の単位と判定を後の段へ渡す節 judged。

再審（rejudge）が走ればその返りから、走らなければ判定（judge）の返りから返す。後の段は単位と判定をここから読む。
再審が走った時は、判定と再審の 2 つの judgment の指し札の先（judgment.json の units）を key で比べて返す（report に受ける入力が無く、まだ報告には届かない）
（今の works の works/.shared/core/rejudge.py の collect 552-563 行と diff_units 474-509 行）:
- new_open_units: 再審の後に開いた単位（再審の前は無いか開いていなかった）
- lowered: 再審の前は block で、後は block でない単位
- unnamed_changed: 欄が変わったか増えた・消えたのに、異議の文が名指していない単位（変化は争点外として強調する側に倒す）
judgment の先を読めない時は 3 つを空にし、読めなかった訳を unread に返す（黙って空にしない）。例外の時は止めの理由
works:line-script を返し、fixed がそれを読んで後ろへ進めない。

入力（with:）: judge_<欄>（judge の返り）・rejudge_<欄>（rejudge の返り。`{from, if_skipped: null}`）・objection（fix の異議）
"""
import json
import os
import re

import linekit
from linekit import boundary

FIELDS = ("units", "judgment", "purpose", "world", "rejudge_verdict")
UNIT_FIELDS = ("label", "disposition", "reason", "reopen_evidence")   # 再審が単位を置き換える時に残す欄（元 review-loop.json の p2.rejudge の pick）
BLOCK = "block"
# 異議の文が修正役に貼った単位の番号を名指す形（元 rejudge.py 77 行）
NUMBERS = (re.compile(r"(?<![A-Za-z])no\.?\s*(\d+)", re.IGNORECASE), re.compile(r"[#＃]\s*(\d+)"), re.compile(r"(\d+)\s*番"))


def is_open(unit: dict) -> bool:
    """今の周に直す単位（元 works/.shared/core/scripts/review-record.py 624 行）"""
    return unit.get("label") == BLOCK or (unit.get("label") == "suggest" and unit.get("disposition") == "do-now")


def named_numbers(text: str) -> set:
    return {int(m.group(1)) for rx in NUMBERS for m in rx.finditer(text or "")}


def unit_changes(before: list, after: list, objection: str) -> dict:
    """再審の前後の単位を key で比べる。修正役に貼った番号は前の単位の並び（元 rejudge.numbered_keys の控えが無い時と同じ）"""
    was = {u.get("key"): u for u in before}
    now = {u.get("key"): u for u in after}
    numbered = [u.get("key") for u in before]
    by_number = {numbered[n - 1] for n in named_numbers(objection) if 1 <= n <= len(numbered)}

    def named(key) -> bool:
        return bool(objection) and (str(key) in objection or key in by_number)

    def moved(key) -> bool:
        return key not in was or key not in now or any(was[key].get(f) != now[key].get(f) for f in UNIT_FIELDS)

    return {
        "new_open_units": [u.get("key") for u in after if is_open(u) and not (u.get("key") in was and is_open(was[u.get("key")]))],
        "lowered": [u.get("key") for u in after if (was.get(u.get("key")) or {}).get("label") == BLOCK and u.get("label") != BLOCK],
        "unnamed_changed": [key for key in [*was, *(k for k in now if k not in was)] if moved(key) and not named(key)],
    }


def judged_units(ptr) -> list:
    doc = json.loads(boundary.resolve(ptr).read_text(encoding="utf-8"))
    return [u for u in doc.get("units") or [] if isinstance(u, dict)]


def compared(judge: dict, rejudge: dict | None, objection: str) -> dict:
    empty = {"new_open_units": [], "lowered": [], "unnamed_changed": [], "unread": ""}
    if rejudge is None:
        return empty
    try:
        before, after = judged_units(judge.get("judgment")), judged_units(rejudge.get("judgment"))
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        return {**empty, "unread": f"再審の前後の判定を比べられない（{type(error).__name__}: {error}）"}
    return {**unit_changes(before, after, objection), "unread": ""}


def judged(judge: dict, rejudge: dict | None, objection: str) -> dict:
    took = rejudge if rejudge is not None else judge
    return {**{key: took.get(key) for key in FIELDS}, "rejudged": rejudge is not None, **compared(judge, rejudge, objection),
            "stop_reason": ""}


def of_env(prefix: str) -> dict:
    return {key: linekit.field(key, os.environ.get(f"INPUTS_{prefix}_{key.upper()}")) for key in FIELDS}


def from_env() -> tuple:
    rejudge = of_env("REJUDGE")
    return of_env("JUDGE"), (None if rejudge["units"] is None else rejudge), linekit.text(os.environ.get("INPUTS_OBJECTION"))


def fallback(reason: str) -> dict:
    return {**{key: None for key in FIELDS}, "rejudged": False, "new_open_units": [], "lowered": [], "unnamed_changed": [],
            "unread": "", "stop_reason": linekit.LINE_SCRIPT}


if __name__ == "__main__":
    linekit.run(lambda: judged(*from_env()), fallback)

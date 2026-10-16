# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""判定の単位と判定を後の段へ渡す節 judged。

再審（rejudge-run）が走ればその返りから、走らなければ判定（judge）の返りから返す。後の段は単位と判定をここから読む。
再審が走った時は、判定のブロックが再審の judgment の隣に書いた再審の出口 rejudge-exit.json（lib/report.REJUDGE_EXIT。書き手は
lib/judge_accept.rejudge_collect。元 works/.shared/core/rejudge.py の collect 552-563 行と diff_units 474-509 行）の比べを返す
（自分では数えない。報告も同じファイルを読む）:
- new_open_units: 再審の後に開いた単位（再審の前は無いか開いていなかった）
- lowered: 再審の前は block で、後は block でない単位
- unnamed_changed: 欄が変わったか増えた・消えたのに、異議の文が名指していない単位（変化は争点外として強調する側に倒す）
出口を読めない時は 3 つを空にし、読めなかった訳を unread に返す（黙って空にしない）。例外の時は止めの理由
works:line-script を返し、fixed がそれを読んで後ろへ進めない。
再審が止まった（3 回とも拒まれた・支度ができない。judge のブロックが止めの理由 works:rejudge ほかを返した）時は、その止めの理由を
stop_reason で返し、fixed が試験の関門・独立の目・merge へ進めない（元 works/.shared/core/rejudge.py 546-558 行の b.stop）。

入力（with:）: judge_<欄>（judge の返り。fix-in の欄つきの参照）・rejudge（rejudge-run の返りまるごと。`{from, if_skipped: null}`。
読む欄の名は REJUDGE で、止めの理由 stop_reason も同じ返りから読む）・objection（fix の異議）
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import report

FIELDS = ("units", "judgment", "purpose", "world", "rejudge_verdict")
REJUDGE = (*FIELDS, "stop_reason")   # rejudge-run の返りから読む欄（口 boundary.picked に渡す）。止めの理由 stop_reason も同じ返りから読む
COMPARED = ("new_open_units", "lowered", "unnamed_changed")


def compared(rejudge: dict | None) -> dict:
    """再審の出口の比べ（再審が無ければ空）。出口を読めなければ空と訳"""
    empty = {**{key: [] for key in COMPARED}, "unread": ""}
    if rejudge is None:
        return empty
    try:
        folder = boundary.resolve(rejudge.get("judgment")).parent
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        return {**empty, "unread": f"再審の前後を比べられない（再審の判定のポインタを開けない。{type(error).__name__}: {error}）"}
    doc, why = report.rejudge_exit(folder)
    if doc is None:
        return {**empty, "unread": f"再審の前後を比べられない（{why}）"}
    return {**{key: [k for k in doc.get(key) or [] if isinstance(k, str)] for key in COMPARED}, "unread": ""}


def judged(judge: dict, rejudge: dict | None, objection: str, rejudge_stop: str = "") -> dict:
    took = rejudge if rejudge is not None else judge
    return {**{key: took.get(key) for key in FIELDS}, "rejudged": rejudge is not None, **compared(rejudge),
            "stop_reason": rejudge_stop if rejudge is not None else ""}


def judge_from_env(prefix: str) -> dict:
    """judge_ の頭の入力（fix-in の欄つきの参照）。値は enum の字か null なので、5 欄とも boundary.value で読む"""
    return {key: boundary.value(os.environ.get(f"INPUTS_{prefix}_{key.upper()}")) for key in FIELDS}


def from_env() -> tuple:
    rejudge = boundary.picked(os.environ.get("INPUTS_REJUDGE"), REJUDGE)   # 走らなかった（飛んだ節）なら None
    stop = rejudge["stop_reason"] if rejudge is not None else ""
    return (judge_from_env("JUDGE"), rejudge, boundary.text(os.environ.get("INPUTS_OBJECTION")), boundary.as_text(stop))


def fallback(reason: str) -> dict:
    return {**{key: None for key in FIELDS}, "rejudged": False, "new_open_units": [], "lowered": [], "unnamed_changed": [],
            "unread": "", "stop_reason": boundary.LINE_SCRIPT}


if __name__ == "__main__":
    boundary.run(lambda: judged(*from_env()), fallback)

"""借りた superpowers の部品を役の指示に載せる値（docs/design/delta-review.md の 1.5。写す元は lib/seat.py の section・words_table）。

座の文の決まった字（見出し・「この指示が勝つ」・表の頭・注・読み替えの頭の 1 文）は md に在る。ここは借りた写し（lib/borrow/）の字を値で返す:
審査役は型 task-review（superpowers の task-reviewer の写し）の本文と判定の語の表の行、手直しの役はスキル receiving-code-review の名と効く所・
効かない所。どちらも読み替えの本文（lib/borrow/unattended.md の役の種類の節と共通の文）とその在りかを返す。写しが固定と違えば ValueError。
"""
import ports  # noqa: F401  （lib/ を sys.path に足す）

import seat  # lib/
import spseam  # lib/

REVIEW_SEAT = "task-review"
REFIX_SEAT = "receiving-review"


def _bullets(rows) -> str:
    return "\n".join(f"- {r}" for r in rows)


def _overlay(kind: str) -> dict:
    return {"overlay_path": str(spseam.BORROW_DIR / spseam.OVERLAY_FILE), "overlay": seat.overlay_body(seat.OVERLAY_KINDS[kind]).rstrip("\n")}


def words_rows() -> str:
    """審査役の型の語・works の語・欄の値の表の行（`| <型の語> | <works の語> | `<欄>.verdict`: `<値>` |`）。works の語が seat.VERDICT_WORDS に無ければ ValueError"""
    words = spseam.load_seams()[REVIEW_SEAT].get("words") or {}
    lack = sorted(w for w in words.values() if w not in seat.VERDICT_WORDS)
    if lack:
        raise ValueError(f"セクション {REVIEW_SEAT} の語 {lack} が判定の欄の語の対応（seat.VERDICT_WORDS）に無い")
    return "\n".join(f"| {said} | {w} | `{seat.VERDICT_WORDS[w][0]}.verdict`: `{seat.VERDICT_WORDS[w][1]}` |" for said, w in words.items())


def review_values(*, brief_file: str, policy_file: str, report_file: str, base: str, head: str, diff_file: str) -> dict:
    """審査役の座の値 {seat_file, seat_template, seat_words, overlay_path, overlay}。型の穴は呼び手が渡す値で全部埋める（無い物は seat.NONE）"""
    seat.pinned()
    sec = spseam.load_seams()[REVIEW_SEAT]
    template = seat.fill(REVIEW_SEAT, {
        "[BRIEF_FILE]": brief_file, "[GLOBAL_CONSTRAINTS]": policy_file or seat.NONE, "[REPORT_FILE]": report_file or seat.NONE,
        "[BASE_SHA]": base or seat.NONE, "[HEAD_SHA]": head or seat.NONE, "[DIFF_FILE]": diff_file})
    return {"seat_file": sec["files"][0], "seat_template": template.rstrip("\n"), "seat_words": words_rows(), **_overlay("review")}


def refix_values() -> dict:
    """手直しの役の座の値 {seat_skill, seat_applies, seat_not_applies, overlay_path, overlay}"""
    seat.pinned()
    sec = spseam.load_seams()[REFIX_SEAT]
    return {"seat_skill": seat.skill_of(sec), "seat_applies": _bullets(sec.get("applies") or []),
            "seat_not_applies": _bullets(sec.get("not_applies") or []), **_overlay("refix")}

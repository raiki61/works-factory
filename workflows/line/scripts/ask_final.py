"""最後の関所を開くかと、見せる文を決める節 ask-final（docs/design.md の「線」の「順と関所」の 11）。

開ける理由（final_needs。今の works の works/darkfactory/lib/line_edge.py の _final_needs の理由のうち、線が返りから読める物）を
test-gate（final）・fixed・eyes・merge（seal）・judged の返りから並べ、開き方（final_gate）で開くかを決める（lib/gatepolicy.py の
opens）。守りのパスの当たり（確かめられなかった時も）と食い違いの申し出は、開き方に依らず開く（通すのは人の答えだけ。1 回目の修正の
申し出も fixed が運ぶ）。無人の run で開くはずの時は開かずに止め（needs-human）、merge（apply）を飛ばす。
判定の役が人に聞くと保留にしたままの問い（判定の指し札の先の questions のうち、修正前の関所で答えていない物）は冒頭と本文に見せるが、
開ける理由には数えない（元の _final_head・_final_text と同じ）。

文は冒頭 3 行（final_head。lib/gatemarks.py の head3）で始め、守りのパス・申し出・許したテストの変更・独立の目の行・保留の問い・
封じた差分を並べる。
"""
import json
import os

import linekit
from linekit import boundary

with linekit.guarded_imports():
    import answer
    import gatemarks
    import gatepolicy
    import seal
    import structmark

EYES = ("r1", "r2", "r3", "r4")
PASS = "pass"
ESCALATE = "escalate"
PROTECTED_HEAD = "守りのパスを触った"
PROTECTED_UNKNOWN = "守りのパスを確かめられなかった"   # 元 line_edge.py 111 行。merge が確かめられなかった行（lib/seal.py の UNKNOWN_HEAD）の見出し
ASKING = ("held", "escalate")   # 人に聞く状態の問い（元 works/.shared/core/scripts/review-record.py 343 行）
RECORD = "run の置き場の gates/gate-final.json"


def tests_word(ok: bool, green: bool, red_cause: str) -> str:
    if ok and green:
        return "緑"
    if not ok:
        return "認証できなかった" + (f"（{red_cause}）" if red_cause else "")
    return "赤" + (f"（{red_cause}）" if red_cause else "")


def final_needs(got: dict) -> list:
    """最後の関所を開ける理由（1 件 1 句）。開ける理由の要る開き方で開くかは、この列が空でないかだけで決める"""
    why = []
    unknown, hits = protected(got)
    if unknown:
        why.append(f"{PROTECTED_UNKNOWN}（人の確かめが要る）")
    if hits:
        why.append(f"{PROTECTED_HEAD}（{len(hits)} 件。人の確かめが要る）")
    word = tests_word(got["tests_ok"], got["green"], got["red_cause"])
    if word != "緑":
        why.append(f"最後のテストが{word}")
    if got["conflicts"]:
        why.append(f"食い違いの申し出を人に回した（{len(got['conflicts'])} 件）")
    blocked = [name.upper() for name in EYES if isinstance(got["eyes"].get(name), dict) and got["eyes"][name].get("status") != PASS]
    if blocked:
        why.append(f"独立の目が阻害を返した（{'・'.join(blocked)}）")
    premise = got["eyes"].get("premise_check")
    if isinstance(premise, dict) and premise.get("verdict") == ESCALATE:
        why.append("前提の検算が人に上げた")
    if got["fenced"]:
        why.append(f"考えの住処の柵の数が増えた（{len(got['fenced'])} 件。住処へ寄せるか、増やすなら地図と柵の表を直す）")
    if got["questions"]:
        why.append(f"人に聞いている問いが在る（{len(got['questions'])} 件）")
    if got["objection"] and got["rejudge_verdict"] != "採る":
        why.append("止めずに残った異議が在る")
    if not got["sealed"]:
        why.append(f"差分を封じられなかった（{got['seal_reason'] or '訳が無い'}）")
    return why


def protected(got: dict) -> tuple:
    """守りのパスの行を (確かめられなかった行, 当たった行) に分ける"""
    rows = got["protected_hits"]
    unknown = [row for row in rows if str(row).startswith(seal.UNKNOWN_HEAD)]
    return unknown, [row for row in rows if row not in unknown]


def final_head(got: dict, why: list) -> list:
    guarded = bool(got["protected_hits"])
    held = got["held"]
    happened = (f"最後のテストと独立の目が済み、報告の前で止まった。テストは{tests_word(got['tests_ok'], got['green'], got['red_cause'])}。"
                + ("開けた理由: " + "・".join(why) if why else
                   f"関所はいつも開く設定（{gatepolicy.head_words({gatepolicy.FINAL_KEY: gatepolicy.ALWAYS})}）で、ほかに開けた理由は無い")
                + (f"。判定の役が人に聞くと保留にしたままの問いも在る（{len(held)} 件。関所を開ける理由には数えない）" if held else ""))
    decide = ("報告へ進めて run を終えるか、止めるか（打つ行は末尾の答え方）"
              + ("。守りのパスの変更は下の最初の節を確かめてから通す" if guarded else ""))
    return gatemarks.head3(happened, decide, gatemarks.pushes([*held, *got["questions"]]))


def final_text(got: dict, why: list, run_id: str) -> str:
    lines = [*final_head(got, why), ""]
    if got["protected_hits"]:
        lines += [f"## {PROTECTED_HEAD}（{len(got['protected_hits'])} 件。通すのは人の答えだけ）", *[f"- {p}" for p in got["protected_hits"]], ""]
    if got["conflicts"]:
        lines += [f"## 食い違いの申し出（{len(got['conflicts'])} 件。修正の段が人に回した。通すのは人の答えだけ）",
                  *[f"- {c.get('path') if isinstance(c, dict) else c}" for c in got["conflicts"]], ""]
    if got["allowed_test_changes"]:
        lines += [f"## 許したテストの変更（{len(got['allowed_test_changes'])} 件）", *[f"- {p}" for p in got["allowed_test_changes"]], ""]
    eyes = [f"- {name.upper()}: {got['eyes'][name].get('status')}（{got['eyes'][name].get('reason') or ''}）"
            for name in EYES if isinstance(got["eyes"].get(name), dict)]
    if eyes or got["questions"]:
        lines += ["## 独立の目", *eyes, *[f"- 問い: {q}" for q in got["questions"]], ""]
    if got["fenced"]:
        lines += [f"## 考えの住処の柵の数が増えた（{len(got['fenced'])} 件）", *[f"- {row['text']}" for row in got["fenced"]], ""]
    if got["held"]:
        lines += [f"## 判定の役が人に聞くと保留にしたままの問い（{len(got['held'])} 件。この関所の答えは問いに答えない。問いは報告の冒頭に並ぶ）",
                  *[f"- {q}" for q in got["held"]], gatemarks.ANSWER_HOW, ""]
    if got["unread"]:
        lines += [f"- {got['unread']}", ""]
    lines += [f"封じた差分の hash: {got['hash'] or '（無い）'}", "", "答え方:",
              f"- 報告へ進める: {answer.line(run_id, 'continue', '<一言>')}（一言は {RECORD} に残る）",
              f"- 止める: {answer.line(run_id, 'stop', '<理由>')}（報告は出る）"]
    return "\n".join(lines) + "\n"


def ask(got: dict, *, mode: str, unattended: bool, run_id: str) -> dict:
    why = final_needs(got)
    must = bool(got["protected_hits"]) or bool(got["conflicts"])
    opens = must or gatepolicy.opens(mode or gatepolicy.ALWAYS, reasons=why, guarded=bool(got["protected_hits"]))
    if not opens:
        return {"open": False, "go": True, "stop_reason": "", "text": "", "reasons": why}
    if unattended:
        return {"open": False, "go": False, "stop_reason": linekit.NEEDS_HUMAN, "text": "", "reasons": why}
    return {"open": True, "go": True, "stop_reason": "", "text": final_text(got, why, run_id), "reasons": why}


def held_questions(judgment, answered: bool) -> tuple:
    """(判定の役が人に聞くと保留にしたままの問いの行, 読めなかった訳)。問いは判定の指し札の先（judgment.json）の questions のうち、
    人に聞く状態の fork と escalate の問い（元 gatemarks.asks）。修正前の関所で答えた run は保留が無い。判定が無い（null）・
    読めない時は問いの行は空で、読めなければ訳を返す（黙って空にしない）"""
    if answered or judgment is None:
        return [], ""
    try:
        doc = json.loads(boundary.resolve(judgment).read_text(encoding="utf-8"))
        questions = [q for q in doc.get("questions") or [] if isinstance(q, dict)]
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        return [], f"判定の問いの控えを読めない（保留の問いを数えていない。{type(error).__name__}: {error}）"
    asks = [q for q in questions if (q.get("kind") == "fork" and q.get("status") in ASKING) or q.get("status") == ESCALATE]
    return [gatemarks.ask_text(q) for q in asks], ""


def fenced_rows(structure_after) -> list:
    """直した後の実測（eyes の structure_after の指し札の先の structure-after.json）で、考えの住処の外の知る場所が増えた所の行。
    実測が無い（null）・この run の物でない時は空（元 structmark.after_rows も控えが無い run は空）"""
    if structure_after is None:
        return []
    try:
        folder = boundary.resolve(structure_after).parent
    except (ValueError, TypeError, AttributeError, KeyError):
        return []
    return structmark.after_rows(folder)


def got_of_env() -> dict:
    held, unread = held_questions(linekit.value(os.environ.get("INPUTS_JUDGMENT")),
                                  linekit.value(os.environ.get("INPUTS_BEFORE_FIX_ANSWER")) is not None)
    return {
        "tests_ok": linekit.flag(os.environ.get("INPUTS_TESTS_OK")),
        "green": linekit.flag(os.environ.get("INPUTS_GREEN")),
        "red_cause": linekit.text(os.environ.get("INPUTS_RED_CAUSE")),
        "protected_hits": linekit.items(os.environ.get("INPUTS_PROTECTED_HITS")),
        "conflicts": linekit.items(os.environ.get("INPUTS_CONFLICTS")),
        "allowed_test_changes": linekit.items(os.environ.get("INPUTS_ALLOWED_TEST_CHANGES")),
        "eyes": {
            "r1": linekit.value(os.environ.get("INPUTS_R1")),
            "r2": linekit.value(os.environ.get("INPUTS_R2")),
            "r3": linekit.value(os.environ.get("INPUTS_R3")),
            "r4": linekit.value(os.environ.get("INPUTS_R4")),
            "premise_check": linekit.value(os.environ.get("INPUTS_PREMISE_CHECK")),
        },
        "questions": linekit.items(os.environ.get("INPUTS_QUESTIONS")),
        "objection": linekit.text(os.environ.get("INPUTS_OBJECTION")),
        "rejudge_verdict": linekit.text(os.environ.get("INPUTS_REJUDGE_VERDICT")),
        "sealed": linekit.flag(os.environ.get("INPUTS_SEALED")),
        "seal_reason": linekit.text(os.environ.get("INPUTS_SEAL_REASON")),
        "hash": linekit.text(os.environ.get("INPUTS_HASH")),
        "fenced": fenced_rows(linekit.value(os.environ.get("INPUTS_STRUCTURE_AFTER"))),
        "held": held,
        "unread": unread,
    }


def fallback(reason: str) -> dict:
    return {"open": False, "go": False, "stop_reason": linekit.LINE_SCRIPT, "text": "", "reasons": [reason]}


if __name__ == "__main__":
    linekit.run(lambda: ask(got_of_env(), mode=linekit.text(os.environ.get("INPUTS_FINAL_GATE")),
                            unattended=linekit.flag(os.environ.get("INPUTS_UNATTENDED")), run_id=os.environ["WORKFLOW_ID"]),
                fallback)

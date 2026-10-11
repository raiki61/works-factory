# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""最後の関所を開くかと、見せる文を決める節 ask-final（docs/design.md の「線」の「順と関所」の 11）。

開ける理由（final_needs。今の works の works/darkfactory/lib/line_edge.py の _final_needs の理由のうち、線が返りから読める物）を
test-gate（final）・fixed・eyes・merge（seal）・judged の返りから並べ、開き方（final_gate）で開くかを決める（lib/gatepolicy.py の
opens）。守りのパスの当たり（確かめられなかった時も）と食い違いの申し出は、開き方に依らず開く（通すのは人の答えだけ。1 回目の修正の
申し出も fixed が運ぶ）。無人の run で開くはずの時は開かずに止め（needs-human）、merge（apply）を飛ばす。
判定の役が人に聞くと保留にしたままの問い（held_questions。元 gatemarks.held_lines）は冒頭と本文に見せるが、開ける理由には数えない
（元の _final_head・_final_text と同じ）。保留の問いと柵の増えの控えを読めなければ、読めなかった訳を本文に並べる。

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
    if (got["objection"] and got["rejudge_verdict"] != "採る") or got["refix_objection"]:
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
        lines += [*[f"- {why}" for why in got["unread"]], ""]
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


def held_questions(judgment, start, before_fix, before_fix_asked: list) -> tuple:
    """(判定の役が人に聞くと保留にしたままの問いの行, 読めなかった訳)。元 gatemarks.held_lines を、盤面の代わりに判定の指し札の先
    （judgment.json の questions・units）・始めの記録の answers（依頼の答え）・修正前の関所の答えと関所に載せた項目で当てる。
    依頼の答えは問いの key か出どころ（origin）の字の一致で結ぶ（判定の結び answer_ties と、測れていない素材の名から出どころを
    読む道は判定のブロックの中に在り、線は読まない）。判定が無い（null）時は空、読めなければ訳を返す（黙って空にしない）"""
    if judgment is None:
        return [], ""
    try:
        doc = json.loads(boundary.resolve(judgment).read_text(encoding="utf-8"))
        questions = [q for q in doc.get("questions") or [] if isinstance(q, dict)]
        units = {u.get("key") for u in doc.get("units") or [] if isinstance(u, dict)}
        rows = json.loads(boundary.resolve(start).read_text(encoding="utf-8")).get("answers") if start is not None else []
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        return [], f"判定の問いの控えか始めの記録を読めない（保留の問いを数えていない。{type(error).__name__}: {error}）"
    answers = [a for a in rows if isinstance(a, dict)] if isinstance(rows, list) else []
    passed = isinstance(before_fix, dict) and before_fix.get("decision") in linekit.GO_WORDS
    note = str(before_fix.get("text") or "") if passed else ""
    holds = gatemarks.hold_keys(note, {str(q.get("key")) for q in questions if q.get("key")})

    def binds(a) -> list:
        name = a.get("question")
        by_key = [q for q in questions if isinstance(q.get("key"), str) and q.get("key") and q.get("key") == name]
        return by_key or [q for q in questions if name and q.get("origin") == name]

    def by_request(q) -> bool:
        return any((hit := binds(a)) and len(hit) == 1 and hit[0] is q for a in answers)

    def answered(q) -> bool:
        asked = any(isinstance(a, str) and a.startswith(gatemarks._prefix(q)) for a in before_fix_asked)
        return by_request(q) or (passed and asked and str(q.get("key") or "") not in holds)

    asking = [q for q in questions if q.get("status") in ASKING]
    asks = [q for q in asking if q.get("kind") == "fork" or q.get("status") == ESCALATE]
    pending = [q for q in asks if not answered(q)]
    done = [q for q in asks if answered(q)]
    back = {k for q in done for k in gatemarks._skips(q) if k in units}
    kept = {k for q in pending for k in gatemarks._skips(q) if k not in back}
    lines = [gatemarks._ledger_line(q, skip=[k for k in gatemarks._skips(q) if k in kept] if q in pending else [])
             + f"／{gatemarks.ANSWER_KEY_HEAD}: {json.dumps(str(q.get('key') or ''), ensure_ascii=False)}"
             for q in asking if q in pending or (q not in asks and not by_request(q))]
    return lines + [f"関所で答えたが直す単位に入れられなかった: {q.get('key')}・{k}（理由: 今の周の判定に無い）"
                    for q in done for k in gatemarks._skips(q) if k not in units], ""


def fenced_rows(structure_after) -> tuple:
    """(直した後の実測（eyes の structure_after の指し札の先の structure-after.json）で考えの住処の外の知る場所が増えた所の行,
    読めなかった訳)。実測が無い（null）時は空（元 structmark.after_rows も控えが無い run は空）。指し札が読めない・先の控えが
    読めなければ訳を返す（黙って空にしない）"""
    if structure_after is None:
        return [], ""
    try:
        folder = boundary.resolve(structure_after).parent
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        return [], f"直した後の実測の指し札を読めない（柵の増えを数えていない。{type(error).__name__}: {error}）"
    if structmark.read_after(folder) is None:
        return [], f"直した後の実測の控え {structmark.AFTER_FILE} を読めない（柵の増えを数えていない）"
    return structmark.after_rows(folder), ""


def got_of_env() -> dict:
    held, held_unread = held_questions(linekit.value(os.environ.get("INPUTS_JUDGMENT")),
                                       linekit.value(os.environ.get("INPUTS_START")),
                                       linekit.value(os.environ.get("INPUTS_BEFORE_FIX_ANSWER")),
                                       [str(q) for q in linekit.items(os.environ.get("INPUTS_BEFORE_FIX_ASKED"))])
    fenced, fenced_unread = fenced_rows(linekit.value(os.environ.get("INPUTS_STRUCTURE_AFTER")))
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
        "refix_objection": linekit.text(os.environ.get("INPUTS_REFIX_OBJECTION")),
        "rejudge_verdict": linekit.text(os.environ.get("INPUTS_REJUDGE_VERDICT")),
        "sealed": linekit.flag(os.environ.get("INPUTS_SEALED")),
        "seal_reason": linekit.text(os.environ.get("INPUTS_SEAL_REASON")),
        "hash": linekit.text(os.environ.get("INPUTS_HASH")),
        "fenced": fenced,
        "held": held,
        "unread": [why for why in (held_unread, fenced_unread) if why],
    }


def from_env() -> dict:
    """ask の引数（with: の欄の全部を読む）"""
    return {"got": got_of_env(), "mode": linekit.text(os.environ.get("INPUTS_FINAL_GATE")),
            "unattended": linekit.flag(os.environ.get("INPUTS_UNATTENDED")), "run_id": os.environ["WORKFLOW_ID"]}


def fallback(reason: str) -> dict:
    return {"open": False, "go": False, "stop_reason": linekit.LINE_SCRIPT, "text": "", "reasons": [reason]}


if __name__ == "__main__":
    linekit.run(lambda: ask(**from_env()), fallback)

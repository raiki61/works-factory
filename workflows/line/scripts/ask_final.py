# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""最後の関所を開くかと、見せる文を決める節 ask-final（docs/design.md の「線」の「順と関所」の 11）。

開ける理由（needs。今の works の works/darkfactory/lib/line_edge.py の _final_needs の理由のうち、線が返りから読める物）を
test-gate（final）・fixed・eyes・merge（seal）・judged の返りから 1 つの列に並べ、開くかと冒頭の 1 行目をこの列だけから作る
（元 _final_needs。開き方 final_gate で開くかは lib/gatepolicy.py の opens）。列の行のうち、守りのパスの当たり（確かめられなかった
時も）・書き換えを許したテストに触った・人に回した食い違いの申し出・申し出の控えを読めない、は開き方に依らず開く（must。通すのは
人の答えだけ。元 _guard と line_edge.py:1184-1197）。無人の run で開くはずの時は開かずに止め（needs-human）、merge（apply）を飛ばす。
申し出は fix・refix-run の conflicts.json（fixed の conflicts の指し札の並び）を lib/conflict.py の asked で数え、文は human_lines の
行のまま（ask_human と案の直しを諦めた fix_plan_item だけ。直す裁定だけなら開けない）。控えを読めなければ黙って 0 にせず、開ける理由と
文に訳を出す。判定の役が人に聞くと保留にしたままの問い（held）は冒頭と本文に見せるが、開ける理由には数えない（元 _final_head）。
元の理由のうち「修正役が人に回した物が在る」（report.handoff_lines）と「直したという申告と機械の数え直しが合わない単位が在る」
（querytest.closure_lines の mismatched_only）は、fix の返りの約束に控えが無く読めないので持たない（S03・S28。今の works からの狭め）。

文は冒頭 3 行（final_head。lib/gatemarks.py の head3）で始め、元 line_edge.final_edge・_final_text の節の並びに戻す: 守りのパス
（差分の見方と一覧）・食い違いの申し出・例で試していない単位・同じ run で直した案の項目 → 最後のテストの一式と修正前のテスト
（証拠 evidence.md の字のまま）・ログ・作業ツリー・差分の審査・異議と再審・直した後の実測・修正前の関所で通した行と往復・許した
テストの変更・取り込むと消えるファイル・独立の目・残り・人に聞いている問い（記録のまま引く）・保留の問いと答えた問いと当たらなかった
依頼の答えと読めなかった保留。開いた文は run の置き場の FINAL_GATE_FILE にも残す（元 line_edge.py:887 の final-gate.md）。
"""
import json
import os
from pathlib import Path

import linekit
from linekit import boundary

with linekit.guarded_imports():
    import answer
    import conflict
    import declared_checks
    import gatemarks
    import gatepolicy
    import protect
    import querytest
    import replan
    import runreport
    import seal
    import structmark

EYES = ("r1", "r2", "r3", "r4")
PASS = "pass"
ESCALATE = "escalate"
PROTECTED_HEAD = "守りのパスを触った"
PROTECTED_UNKNOWN = "守りのパスを確かめられなかった"   # 元 line_edge.py 111 行。merge が確かめられなかった行（lib/seal.py の UNKNOWN_HEAD）の見出し
ALLOWED_TESTS_HEAD = "書き換えを許したテストを触った"   # 元は conflict.ruled_test_doc を 2 つ目の一覧として守りのパスに通した（line_edge.py:640-651）
CONFLICT_UNREAD = "食い違いの申し出の控えを読めない"
RECORD = "run の置き場の gates/gate-final.json"
FINAL_GATE_FILE = "gates/final-gate.md"   # 開いた関所の文の控え（元 line_edge.FINAL_GATE_FILE）
NO_DELTA_HOLES = "穴の数と枝の名札・手直しの結果: 取れない（修正の返りの約束に差分の審査の穴の控えが無い。S29）"
NOT_COUNTED = ("clean が消したファイル・レンズ・仕組みの異常: 取れない（修正の返りの約束にその控えが無い。S28）")
EYE_QUESTION_NODE = "r4.human_gate"


def tests_word(ok: bool, green: bool, red_cause: str) -> str:
    if ok and green:
        return "緑"
    if not ok:
        return "認証できなかった" + (f"（{red_cause}）" if red_cause else "")
    return "赤" + (f"（{red_cause}）" if red_cause else "")


def protected(got: dict) -> tuple:
    """守りのパスの行を (確かめられなかった行, 当たった行) に分ける"""
    rows = got["protected_hits"]
    unknown = [row for row in rows if str(row).startswith(seal.UNKNOWN_HEAD)]
    return unknown, [row for row in rows if row not in unknown]


def blocked_eyes(got: dict) -> list:
    return [name.upper() for name in EYES if isinstance(got["eyes"].get(name), dict) and got["eyes"][name].get("status") != PASS]


def needs(got: dict) -> list:
    """最後の関所を開ける理由の列 [(1 句, 開き方に依らず開くか)]。開くか（ask）と 1 行目（final_head）はこの列だけから作る"""
    why = []
    unknown, hits = protected(got)
    if unknown:
        why.append((f"{PROTECTED_UNKNOWN}（人の確かめが要る）", True))
    if hits:
        why.append((f"{PROTECTED_HEAD}（{len(hits)} 件。人の確かめが要る）", True))
    if got["allowed_test_changes"]:
        why.append((f"{ALLOWED_TESTS_HEAD}（{len(got['allowed_test_changes'])} 件。人の確かめが要る）", True))
    word = tests_word(got["tests_ok"], got["green"], got["red_cause"])
    if word != "緑":
        why.append((f"最後のテストが{word}", False))
    if got["conflicts_unread"]:
        why.append((f"{CONFLICT_UNREAD}（{len(got['conflicts_unread'])} 件。人に回した申し出を数えられない）", True))
    if got["asked"]:
        why.append((f"{conflict.HEAD}を人に回した（{len(got['asked'])} 件）", True))
    blocked = blocked_eyes(got)
    if blocked:
        why.append((f"独立の目が阻害を返した（{'・'.join(blocked)}）", False))
    premise = got["eyes"].get("premise_check")
    if isinstance(premise, dict) and premise.get("verdict") == ESCALATE:
        why.append(("前提の検算が人に上げた", False))
    if got["fenced"]:
        why.append((f"考えの住処の柵の数が増えた（{len(got['fenced'])} 件。住処へ寄せるか、増やすなら地図と柵の表を直す）", False))
    if got["questions"]:
        why.append((f"人に聞いている問いが在る（{len(got['questions'])} 件）", False))
    if left_objection(got):
        why.append(("止めずに残った異議が在る", False))
    if not got["sealed"]:
        why.append((f"差分を封じられなかった（{got['seal_reason'] or '訳が無い'}）", False))
    return why


def final_needs(got: dict) -> list:
    """最後の関所を開ける理由（1 件 1 句）。開ける理由の要る開き方で開くかは、この列が空でないかだけで決める"""
    return [phrase for phrase, _ in needs(got)]


def left_objection(got: dict) -> str:
    """止めずに残った異議（再審が採らなかった修正役の異議。線の fixed の objection は 1 回目と 2 度目の修正の異議をつないだ文で、
    再審は 2 度目の修正の後に両方を受ける）。無ければ空"""
    return got["objection"] if got["objection"] and got["rejudge_verdict"] != "採る" else ""


def final_head(got: dict, why: list) -> list:
    guarded = bool(got["protected_hits"]) or bool(got["allowed_test_changes"])
    held = got["held"]
    happened = (f"最後のテストと独立の目が済み、報告の前で止まった。テストは{tests_word(got['tests_ok'], got['green'], got['red_cause'])}。"
                + ("開けた理由: " + "・".join(why) if why else
                   f"関所はいつも開く設定（{gatepolicy.head_words({gatepolicy.FINAL_KEY: gatepolicy.ALWAYS})}）で、ほかに開けた理由は無い")
                + (f"。判定の役が人に聞くと保留にしたままの問いも在る（{len(held)} 件。関所を開ける理由には数えない）" if held else "")
                + (f"。{got['split']}" if got["split"] else ""))
    decide = ("報告へ進めて run を終えるか、止めるか（打つ行は末尾の答え方）"
              + ("。守りのパスと許したテストの変更は下の最初の節を確かめてから通す" if guarded else ""))
    return gatemarks.head3(happened, decide, gatemarks.pushes([*held, *got["questions"]]))


def protected_section(got: dict) -> list:
    """冒頭 3 行の直後の節（元 line_edge._protected_text）: 確かめられなかった訳と一覧、か、当たった行・差分の見方・一覧"""
    unknown, hits = protected(got)
    lines = []
    if unknown:
        lines += [f"## {PROTECTED_UNKNOWN}（差分が一覧に触れていないとは言えない）", "",
                  *[f"- 理由: {str(row).removeprefix(seal.UNKNOWN_HEAD)}" for row in unknown], f"- 一覧: {protect.MANIFEST}", ""]
    if hits:
        lines += [f"## {PROTECTED_HEAD}（{len(hits)} 件。works 自身の試験・柵・受け付けの口。通すのは人の答えだけ）", "",
                  *[f"- {p}" for p in hits],
                  f"- 差分: git -C {got['worktree']} diff {got['base_rev'][:12] or '<起点の版が記録に無い>'} -- <パス>（未追跡は新しいファイル）",
                  f"- 一覧: {protect.MANIFEST}", ""]
    if got["allowed_test_changes"]:
        lines += [f"## {ALLOWED_TESTS_HEAD}（{len(got['allowed_test_changes'])} 件。承認済みの案と裁定が書き換えを許したテスト。"
                  "通すのは人の答えだけ）", "", *[f"- {p}" for p in got["allowed_test_changes"]], ""]
    return lines


def conflict_section(got: dict) -> list:
    """食い違いの申し出の節（元 line_edge._conflict_text。conflict.human_lines の行のまま）と、控えを読めなかった訳"""
    lines = []
    if got["asked"]:
        lines += [f"## {conflict.HEAD}（{len(got['asked'])} 件。裁定役か機械が人に回した。単位は直さずに残した。通すのは人の答えだけ）", "",
                  *[f"- {row}" for row in got["asked"]], ""]
    if got["conflicts_unread"]:
        lines += [f"## {CONFLICT_UNREAD}（{len(got['conflicts_unread'])} 件。人に回した行かを数えられない。通すのは人の答えだけ）", "",
                  *[f"- {row}" for row in got["conflicts_unread"]], ""]
    return lines


def rows_section(head: str, rows: list) -> list:
    return [f"## {head}（{len(rows)} 件）", "", *[f"- {row}" for row in rows], ""] if rows else []


def tests_lines(got: dict) -> list:
    """最後のテストの一式と修正前のテスト（証拠の字のまま。元 _final_text の entry.suites_line・baseline_line）・自己申告の緑の次の手・
    ログ・走れなかった理由・作業ツリー"""
    ev = got["evidence"]
    lines = [f"- テストの一式: {ev['suites'] or '証拠に走らせ方の行が無い'}",
             f"- {runreport.BASELINE_ROW[0]}: {ev['baseline'] or '証拠に修正前のテストの行が無い'}"]
    if ev["suites"].startswith(declared_checks.ROLE_NEEDED):
        lines.append(f"- {declared_checks.SELF_REPORTED_NOTE}。確かめてから通すか（continue の一言に何を走らせて何色だったか）、止めるか（stop）")
    lines.append(f"- ログ: {ev['log'] or '（無い）'}")
    if ev["why"]:
        lines.append(f"- 走れなかった・認証しなかった理由: {ev['why']}")
    if ev["unread"]:
        lines.append(f"- {ev['unread']}")
    lines.append(f"- run の作業ツリー: {got['worktree']}")
    return lines


def delta_lines(got: dict) -> list:
    """差分の審査の回数と、穴と目の行の枝の名札（元 report.branch_rows。修正の返りに控えが無い間は取れないと書く）"""
    review = got["delta_review"] if isinstance(got["delta_review"], dict) else {}
    rounds = review.get("rounds")
    head = (f"- 差分の審査: {rounds} 回（最後の審査は{'通った' if review.get('pass') else '通らなかった'}）" if rounds
            else "- 差分の審査: 回っていない（審査を省いたか、変更の確かめが通らなかった）")
    return [head, *[x if x[:1].isspace() else f"- {x}" for x in got["branch_rows"]], *([] if got["branch_rows"] else [f"  - {NO_DELTA_HOLES}"])]


def eye_lines(got: dict) -> list:
    """独立の目の判定（元 line_edge._eyes。主語は平易な名、目の名と状態の語は括弧に回す: gatemarks.eye_named）と残りの数え"""
    lines = [f"- 独立の目の判定（阻害: {'・'.join(blocked_eyes(got)) or '無い'}）:"]
    missing = []
    for name in EYES:
        row = got["eyes"].get(name)
        if not isinstance(row, dict):
            missing.append(name.upper())
            lines.append(f"  - {gatemarks.EYES[name.upper()]}（{name.upper()}）: 結果が無い（深さで省いたか、目のブロックが返さなかった）")
            continue
        reason = " ".join(str(row.get("reason") or "").split())
        lines.append(f"  - {gatemarks.eye_named(name.upper(), row.get('status'))}" + (f"——理由: {reason}" if reason else ""))
    premise = got["eyes"].get("premise_check")
    if isinstance(premise, dict):
        lines.append(f"  - 前提の検算: {premise.get('verdict') or '語が無い'}（{' '.join(str(premise.get('reason') or '').split())}）")
    blocked = blocked_eyes(got)
    lines.append(f"- 残り（最後の関所で数えられる分）: 独立の目の阻害 {len(blocked)} 件（{'・'.join(blocked) or '無し'}）・"
                 f"結果が無い目 {len(missing)} 件（{'・'.join(missing) or '無し'}）・最後のテストが緑でない "
                 f"{0 if tests_word(got['tests_ok'], got['green'], got['red_cause']) == '緑' else 1} 件・柵の増え {len(got['fenced'])} 件")
    lines.append(f"- {NOT_COUNTED}")
    return lines


def question_lines(got: dict) -> list:
    """人に聞いている問い（記録のまま引く。元 _final_text の pending_human）・保留の問いと答え方・答えた問い・当たらなかった依頼の
    答え・読めなかった保留。どれも無い時だけ「盤面の問い: 無い」"""
    lines = []
    if got["questions"]:
        lines.append(f"- {gatemarks.named(EYE_QUESTION_NODE)}が人に聞いている問い（記録のまま引く。{len(got['questions'])} 件）:")
        for q in got["questions"]:
            lines += [f"  {x}" for x in gatemarks.quote(q)]
        lines.append("  - この関所の答えはこの問いに答えない。問いは報告の冒頭と次の run の依頼の下書きへ渡る")
    if got["held"]:
        lines.append(f"- 判定の役が人に聞くと保留にしたままの問い（問いの台帳・{len(got['held'])} 件。この関所の答えは問いに答えない。"
                     "問いは報告の冒頭に並ぶ）:")
        lines += [f"  - {q}" for q in got["held"]]
        lines.append(f"  {gatemarks.ANSWER_HOW}")
    if got["answered"]:
        lines.append(f"- {gatemarks.ANSWERED_HEAD}（問いの台帳・{len(got['answered'])} 件。保留の件数には数えない）:")
        lines += [f"  - {x}" for x in got["answered"]]
    lines += [f"- {x}" for x in got["unmatched"]]
    lines += [f"- {x}" for x in got["unread_holds"]]
    if not (got["questions"] or got["held"] or got["answered"] or got["unmatched"]):
        lines.append("- 盤面の問い: 無い")
    return lines


def final_text(got: dict, why: list, run_id: str) -> str:
    lines = [*final_head(got, why), ""]
    lines += protected_section(got)
    lines += conflict_section(got)
    lines += rows_section(querytest.UNPROVEN_HEAD, got["unproven"])
    lines += rows_section(replan.AMEND_HEAD, got["amend"])
    lines += [f"最後の人の関所（最後のテストと独立の目の後・報告の前）: テストは{tests_word(got['tests_ok'], got['green'], got['red_cause'])}", ""]
    lines += tests_lines(got)
    lines += delta_lines(got)
    lines.append(f"- 止めずに残った異議: {left_objection(got) or '無い'}")
    lines += ["- 再審で決着した結果:", *[f"  {x}" if x.startswith("  ") else f"  - {x}" for x in got["rejudge"]]] if got["rejudge"] \
        else ["- 再審: 無い"]
    lines += [x if x[:1].isspace() else f"- {x}" for x in got["after"]]
    if got["passes"]:
        lines.append(f"- 直す前の関所で通した項目（決め手が在るので聞かずに通した行と、人が通したので後の関所で聞き直さなかった行。"
                     f"{len(got['passes'])} 件）:")
        lines += [f"  - {x}" for x in got["passes"]]
    lines += [x if x[:1].isspace() else f"- {x}" for x in got["converge"]]
    lines += [f"- {seal.DELETED_HEAD}: {p}" for p in got["deleted"]]
    lines += eye_lines(got)
    lines += question_lines(got)
    lines += [f"- {why_}" for why_ in got["unread"]]
    lines += [f"- 封じた差分の hash: {got['hash'] or '（無い）'}", f"- この文の控え: run の置き場の {FINAL_GATE_FILE}", "",
              "答え方（人が決める関所。依頼者に聞いて、その言葉で答える）:",
              f"- 報告へ進める: {answer.line(run_id, 'continue', '<一言>')}（一言は {RECORD} に残る）",
              f"- 止める: {answer.line(run_id, 'stop', '<理由>')}（報告は出る）"]
    return "\n".join(lines) + "\n"



def ask(got: dict, *, mode: str, unattended: bool, run_id: str) -> dict:
    rows = needs(got)
    why = [phrase for phrase, _ in rows]
    must = any(m for _, m in rows)
    opens = must or gatepolicy.opens(mode or gatepolicy.ALWAYS, reasons=why, guarded=bool(got["protected_hits"]))
    if not opens:
        return {"open": False, "go": True, "stop_reason": "", "text": "", "reasons": why}
    if unattended:
        return {"open": False, "go": False, "stop_reason": linekit.NEEDS_HUMAN, "text": "", "reasons": why}
    return {"open": True, "go": True, "stop_reason": "", "text": final_text(got, why, run_id), "reasons": why}


def keep(out: dict, artifacts: Path) -> dict:
    """開いた関所の文を run の置き場の FINAL_GATE_FILE に残す（書けなければ文の末尾に訳を足す）"""
    if out["open"]:
        try:
            path = artifacts / FINAL_GATE_FILE
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(out["text"], encoding="utf-8")
        except OSError as error:
            out = {**out, "text": out["text"] + f"\n（この文の控えを書けない: {error}）\n"}
    return out


def asked_conflicts(pointers) -> tuple:
    """(人に回した申し出の行, 控えを読めなかった訳)。fixed の conflicts（fix と refix-run の conflicts.json の指し札の並び）の先の
    フォルダごとに lib/conflict.py の human_lines（asked の行の文）を足す。読めない控えは訳にして数えない（黙って 0 にしない）"""
    rows, unread = [], []
    for ptr in pointers or []:
        try:
            folder = boundary.resolve(ptr).parent
            if not (folder / conflict.FILE).is_file():
                raise ValueError(f"{conflict.FILE} が無い")
            rows += conflict.human_lines(folder)
        except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
            where = ptr.get("path") if isinstance(ptr, dict) else ptr
            unread.append(f"{where}: {type(error).__name__}: {' '.join(str(error).split())}")
    return rows, unread


def ledger(judgment, start, before_fix, ties_judgment=None) -> tuple:
    """(問いの台帳の見え方（gatemarks.ledger_beside）か None, 添える行)。判定の指し札の先（judgment.json の questions・units と隣の
    materials.json）・始めの記録の answers（依頼の答え）・修正前の関所の答え {decision, text, asked}・判定の結び（answer-ties.json。
    再審の判定の隣には無いので、1 回目の判定の指し札 ties_judgment の隣から読む）。結びの宛て先の key が今の問いにも単位にも無ければ
    字の一致に落とし、そのことを添える行に 1 行出す（gatemarks.lost_ties）。判定が無い（null）時は None、読めなければ添える行に訳"""
    if judgment is None:
        return None, []
    try:
        path = boundary.resolve(judgment)
        doc = json.loads(path.read_text(encoding="utf-8"))
        rows = json.loads(boundary.resolve(start).read_text(encoding="utf-8")).get("answers") if start is not None else []
        ties_dir = boundary.resolve(ties_judgment).parent if ties_judgment is not None else path.parent
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        return None, [f"判定の問いの控えか始めの記録を読めない（保留の問いを数えていない。{type(error).__name__}: {error}）"]
    b = gatemarks.ledger_beside(path.parent, doc if isinstance(doc, dict) else {}, answers=rows if isinstance(rows, list) else [],
                                gate=before_fix, ties_dir=ties_dir)
    units = [u.get("key") for u in b.record["units"]]
    return b, gatemarks.lost_ties(b.ties, b.record["questions"], units)


def held_questions(judgment, start, before_fix, ties_judgment=None) -> tuple:
    """(判定の役が人に聞くと保留にしたままの問いの行（元 gatemarks.held_lines）, 添える行)。台帳は ledger の見え方"""
    b, notes = ledger(judgment, start, before_fix, ties_judgment)
    return (gatemarks.held_lines(b) if b is not None else []), notes


def ledger_rows(b) -> dict:
    """台帳の見え方 b から最後の関所に並べる行: 保留の問い・答えた問い（ANSWERED_HEAD）・当たらなかった依頼の答え・読めなかった保留"""
    if b is None:
        return {"held": [], "answered": [], "unmatched": [], "unread_holds": []}
    return {"held": gatemarks.held_lines(b), "answered": gatemarks.answered_lines(b),
            "unmatched": gatemarks.unmatched_answer_lines(b), "unread_holds": gatemarks.unread_hold_lines(b)}


def after_rows(structure_after) -> tuple:
    """(柵の増えの行, 直した後の実測の行（元 structmark.after_lines: 数・柵の増え・新しい名・修正案の外れの訳）, 読めなかった訳)。
    実測が無い（null）時は空（元 structmark.after_rows も控えが無い run は空）。指し札が読めない・先の控えが読めなければ訳を返す"""
    if structure_after is None:
        return [], [], ""
    try:
        folder = boundary.resolve(structure_after).parent
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        return [], [], f"直した後の実測の指し札を読めない（柵の増えを数えていない。{type(error).__name__}: {error}）"
    if structmark.read_after(folder) is None:
        return [], [], f"直した後の実測の控え {structmark.AFTER_FILE} を読めない（柵の増えを数えていない）"
    return structmark.after_rows(folder), structmark.after_lines(folder), ""


def fenced_rows(structure_after) -> tuple:
    """(柵の増えの行, 読めなかった訳)"""
    fenced, _, unread = after_rows(structure_after)
    return fenced, unread


def evidence_rows(ptr) -> dict:
    """最後のテストの証拠（test-gate の evidence.md）から、走らせ方・修正前のテスト・ログ・認証しなかった訳の行（字のまま）"""
    got = {"suites": "", "baseline": "", "log": "", "why": "", "unread": ""}
    if ptr is None:
        got["unread"] = "最後のテストの証拠が無い（試験の関門が返さなかった）"
        return got
    try:
        rows = boundary.resolve(ptr).read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError, TypeError, AttributeError, KeyError, UnicodeDecodeError) as error:
        got["unread"] = f"最後のテストの証拠を読めない（{type(error).__name__}: {' '.join(str(error).split())}）"
        return got

    def row(prefix: str) -> str:
        return next((r.removeprefix(prefix) for r in rows if r.startswith(prefix)), "")
    (_, run_prefix), (_, log_prefix) = runreport.EVIDENCE_ROWS
    got.update(suites=row(run_prefix), log=row(log_prefix), baseline=row(runreport.BASELINE_ROW[1]))
    ok = row(runreport.OK_ROW)
    if ok.startswith("false（") and ok.endswith("）"):
        got["why"] = ok[len("false（"):-1]
    return got


def review_rows(reviews) -> tuple:
    """(修正前の関所で通した行, 壁打ちの往復の行, 読めなかった訳)。事前審査の返り review（計画の往復と案の直しの事前審査）の隣の
    gatemarks.PASSES_FILE と GATE_RECORD_FILE の converge から"""
    passes, rounds, unread = [], [], []
    for ptr in reviews:
        if ptr is None:
            continue
        try:
            folder = boundary.resolve(ptr).parent
            passes += gatemarks.pass_lines(json.loads((folder / gatemarks.PASSES_FILE).read_text(encoding="utf-8")))
            rounds += gatemarks.converge_of(folder)
        except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
            unread.append(f"事前審査の隣の控え（通した行・往復）を読めない（{type(error).__name__}: {' '.join(str(error).split())}）")
    return passes, rounds, unread


def path_of(ptr) -> str:
    """指し札の先のパスの字（無い・読めない指し札は空）"""
    try:
        return str(boundary.resolve(ptr)) if ptr is not None else ""
    except (ValueError, TypeError, AttributeError, KeyError):
        return ""


def judged_returns(raw: dict) -> dict:
    """runreport の段の返りの形（指し札はパスの字）: 判定・再審・修正の欄のうち、再審の結果と例で試していない単位と持ち越した単位を
    組むのに要る物"""
    rejudge = ({"units": raw["units"], "judgment": path_of(raw["judgment"]), "rejudge_verdict": raw["rejudge_verdict"]}
               if raw["rejudged"] else None)
    return {"judge": {"units": raw["first_units"], "judgment": path_of(raw["ties_judgment"])}, "rejudge": rejudge,
            "fix": {"objection": raw["objection"], "units": raw["fix_units"],
                    "groups": raw["groups"]}}


def rejudge_rows(returns: dict) -> list:
    """決着した再審の結果（runreport.rejudge_lines。残った異議の行は「止めずに残った異議」の 1 行が持つので外す）"""
    return [x for x in runreport.rejudge_lines(returns) if not x.startswith("再審されずに残った異議")]


def deleted_files(diff) -> tuple:
    """(封じた差分が消すファイル, 読めなかった訳)"""
    if diff is None:
        return [], ""
    try:
        return seal.deleted_paths(boundary.resolve(diff).read_text(encoding="utf-8", errors="replace")), ""
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        return [], f"封じた差分を読めない（取り込むと消えるファイルを数えていない。{type(error).__name__}: {error}）"


def start_doc(start) -> dict:
    try:
        doc = json.loads(boundary.resolve(start).read_text(encoding="utf-8")) if start is not None else {}
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        return {}
    return doc if isinstance(doc, dict) else {}


def env(name: str):
    return linekit.value(os.environ.get(f"INPUTS_{name}"))


def got_of_env() -> dict:
    start = env("START")
    b, ledger_notes = ledger(env("JUDGMENT"), start, env("BEFORE_FIX_ANSWER"), env("TIES_JUDGMENT"))
    fenced, after, after_unread = after_rows(env("STRUCTURE_AFTER"))
    asked, conflicts_unread = asked_conflicts(linekit.items(os.environ.get("INPUTS_CONFLICTS")))
    passes, rounds, review_unread = review_rows((env("PLAN_REVIEW"), env("REPLAN_REVIEW")))
    deleted, deleted_unread = deleted_files(env("SEALED_DIFF"))
    raw = {"units": linekit.items(os.environ.get("INPUTS_UNITS")), "first_units": linekit.items(os.environ.get("INPUTS_FIRST_UNITS")),
           "judgment": env("JUDGMENT"), "ties_judgment": env("TIES_JUDGMENT"), "rejudged": linekit.flag(os.environ.get("INPUTS_REJUDGED")),
           "rejudge_verdict": linekit.text(os.environ.get("INPUTS_REJUDGE_VERDICT")),
           "objection": linekit.text(os.environ.get("INPUTS_OBJECTION")),
           "fix_units": linekit.items(os.environ.get("INPUTS_FIX_UNITS")), "groups": linekit.items(os.environ.get("INPUTS_GROUPS"))}
    returns = judged_returns(raw)
    return {
        "tests_ok": linekit.flag(os.environ.get("INPUTS_TESTS_OK")),
        "green": linekit.flag(os.environ.get("INPUTS_GREEN")),
        "red_cause": linekit.text(os.environ.get("INPUTS_RED_CAUSE")),
        "evidence": evidence_rows(env("EVIDENCE")),
        "worktree": str(Path.cwd().resolve()),
        "base_rev": str(start_doc(start).get("base_rev") or ""),
        "protected_hits": linekit.items(os.environ.get("INPUTS_PROTECTED_HITS")),
        "asked": asked,
        "conflicts_unread": conflicts_unread,
        "allowed_test_changes": linekit.items(os.environ.get("INPUTS_ALLOWED_TEST_CHANGES")),
        "eyes": {
            "r1": env("R1"), "r2": env("R2"), "r3": env("R3"), "r4": env("R4"),
            "premise_check": env("PREMISE_CHECK"),
        },
        "questions": [q for q in linekit.items(os.environ.get("INPUTS_QUESTIONS")) if isinstance(q, str)],
        "objection": raw["objection"],
        "rejudge_verdict": raw["rejudge_verdict"],
        "rejudge": rejudge_rows(returns),
        "split": runreport.split_line(returns),
        "unproven": [x.removeprefix("  - ") for x in runreport.unproven_lines(returns)[1:]],
        "amend": replan.amend_lines(linekit.items(os.environ.get("INPUTS_REPLAN_ITEMS")),
                                    refixed=linekit.flag(os.environ.get("INPUTS_REFIXED")), answer=env("REPLAN_ANSWER"),
                                    widened=linekit.items(os.environ.get("INPUTS_WIDENED"))),
        "delta_review": env("DELTA_REVIEW"),
        "branch_rows": [],
        "sealed": linekit.flag(os.environ.get("INPUTS_SEALED")),
        "seal_reason": linekit.text(os.environ.get("INPUTS_SEAL_REASON")),
        "hash": linekit.text(os.environ.get("INPUTS_HASH")),
        "deleted": deleted,
        "fenced": fenced,
        "after": after,
        "passes": passes,
        "converge": rounds,
        **ledger_rows(b),
        "unread": [*ledger_notes, *([after_unread] if after_unread else []), *review_unread,
                   *([deleted_unread] if deleted_unread else [])],
    }


def from_env() -> dict:
    """ask の引数（with: の欄の全部を読む）"""
    return {"got": got_of_env(), "mode": linekit.text(os.environ.get("INPUTS_FINAL_GATE")),
            "unattended": linekit.flag(os.environ.get("INPUTS_UNATTENDED")), "run_id": os.environ["WORKFLOW_ID"]}


def fallback(reason: str) -> dict:
    return {"open": False, "go": False, "stop_reason": linekit.LINE_SCRIPT, "text": "", "reasons": [reason]}


if __name__ == "__main__":
    linekit.run(lambda: keep(ask(**from_env()), Path(os.environ["ARTIFACTS_DIR"])), fallback)

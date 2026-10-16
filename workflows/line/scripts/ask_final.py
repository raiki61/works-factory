# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""最後の関所を開くかと、見せる文を決めるノード ask-final（docs/design.md の「メイングラフ」の「順と承認ノード」の 11）。

開ける理由（needs。今の works の works/darkfactory/lib/line_edge.py の _final_needs の理由のうち、線が返りから読める物）を
test-gate（final）・fixed・eyes・merge（seal）・judged の返りから 1 つの列に並べ、開くかと冒頭の 1 行目をこの列だけから作る
（元 _final_needs。開き方 final_gate で開くかは lib/gatepolicy.py の opens）。列の行のうち、守りのパスの当たり（確かめられなかった
時も）・書き換えを許したテストに触った・人に回した食い違いの申し出・申し出の控えを読めない・修正の段の隣の控えを読めない・承認の後に
受け入れ条件のテストが変わった（spec-check の questions。この関所の答えはその問いに答えない。照らせなかった時（unchecked）は
「照らせなかった」と言い、答えると差分が当たることを 1 行で言う）、は開き方に依らず開く（must。通すのは人の答えだけ。元 _guard と
line_edge.py:1184-1197）。無人の run で開くはずの時は開かずに止め（needs-human）、merge（apply）を飛ばす。
申し出は fix・refix-run の conflicts.json（fixed の conflicts の指し札の並び）を lib/conflict.py の asked で数え、文は human_lines の
行のまま（ask_human と案の直しを諦めた fix_plan_item だけ。直す裁定だけなら開けない）。控えを読めなければ黙って 0 にせず、開ける理由と
文に訳を出す。判定の役が人に聞くと保留にしたままの問い（held）は冒頭と本文に見せるが、開ける理由には数えない（元 _final_head）。
「修正役が人に回した物が在る」（元 report.handoff_lines）と「直したという申告と機械の数え直しが合わない単位が在る」（元
querytest.closure_lines の mismatched_only）は、fix の出力の handoffs・mismatched（fixed が 1 回目と 2 度目の修正の分を合わせた物）を読む。
許したテストの変更は、修正の段ごとの diff（fixed の diffs）の隣の allowed-tests.json（[{path, permit, source}]）を読んで、許しの id と
出どころつきで並べる。ほかの段の控え（閉鎖の表・穴の名札と手直し・受け付けの trace・レンズ）は同じ diff の隣から lib/fixbeside.py で読む。

文は冒頭 3 行（final_head。lib/gatemarks.py の head3）で始め、元 line_edge.final_edge・_final_text の節の並びに戻す: 守りのパス
（差分の見方と一覧）・食い違いの申し出・修正役が人に回した物・減っていない単位・例で試していない単位・閉鎖の数え直し・同じ run で
直した案の項目 → 最後のテストの一式と修正前のテスト（test-gate の返りの欄のまま）・回さなかった試験と赤緑を確かめずに受けた回・
ログ・作業ツリー・差分の審査と穴の枝の名札と手直しの結果・異議と再審・構造のブロックが落ちた周・直した後の実測・修正前の関所で
通した行と往復・許したテストの変更・取り込むと消えるファイル・独立の目・clean とレンズと仕組みの異常・残り・承認し直すかの問い・
人に聞いている問い（記録のまま引く）・保留の問いと答えた問いと当たらなかった依頼の答えと読めなかった保留。開いた文は run の置き場の FINAL_GATE_FILE にも残す（元 line_edge.py:887 の final-gate.md）。
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import answer
    import conflict
    import declared_checks
    import eyeverdict
    import fixbeside
    import fixboard
    import gatemarks
    import gatepolicy
    import green_cert
    import judge_accept
    import oneline
    import protect
    import querytest
    import replan
    import runreport
    import seal
    import startrec
    import stopby
    import structmark

PROTECTED_HEAD = "守りのパスを触った"
PROTECTED_UNKNOWN = "守りのパスを確かめられなかった"   # 元 line_edge.py 111 行。merge が確かめられなかった行（lib/seal.py の UNKNOWN_HEAD）の見出し
ALLOWED_TESTS_HEAD = "書き換えを許したテストを触った"   # 元は conflict.ruled_test_doc を 2 つ目の一覧として守りのパスに通した（line_edge.py:640-651）
CONFLICT_UNREAD = "食い違いの申し出の控えを読めない"
BESIDE_UNREAD = "修正の段の控えを読めない"
RECORD = "run の置き場の gates/gate-final.json"
FINAL_GATE_FILE = "gates/final-gate.md"   # 開いた関所の文の控え（元 line_edge.FINAL_GATE_FILE）
HANDOFF_REASON = "修正役が人に回した物が在る"
MISMATCH_REASON = "直したという申告と機械の数え直しが合わない単位が在る"
NO_AFTER = "直した後の構造の実測: 無い（独立の目の structure_after が null——実測のノードが落ちたか走らなかった。メイングラフは止めずに進めた）"
# 読む欄の名（with: の tests・eyes・seal は返りまるごとで届き、口 boundary.picked にこの名の並びを渡す。名は返す節の output_format の欄）
TESTS = ("ok", "green", "red_cause", "ran_steps", "by", "suites_line", "log", "baseline_line", "reason")
EYES = ("r1", "r2", "r3", "r4", "premise_check", "questions", "notes", "structure_after")
SEAL = ("ok", "reason", "hash", "protected_hits", "diff")
# 封じの節が飛んだ（差分が無い周）時の既定。差分が無いので封じず、守りのパスの当たりも無い
SEAL_SKIPPED = {"ok": True, "reason": "", "hash": "", "protected_hits": [], "diff": None}


def tests_word(got: dict) -> str:
    ok, green, red_cause = got["tests_ok"], got["green"], got["red_cause"]
    if ok and green:
        return "緑"
    cause = f"（{red_cause}）" if red_cause else ""
    note = green_cert.ran_note(green=green, red_cause=red_cause, by=got["tests"]["by"], steps=got["ran_steps"])
    return ("赤" if ok else "認証できなかった") + cause + (f"——{note}" if note else "")


def protected(got: dict) -> tuple:
    """守りのパスの行を (確かめられなかった行, 当たった行) に分ける"""
    rows = got["protected_hits"]
    unknown = [row for row in rows if str(row).startswith(seal.UNKNOWN_HEAD)]
    return unknown, [row for row in rows if row not in unknown]


def blocked_eyes(got: dict) -> list:
    return [name.upper() for name in eyeverdict.EYES if isinstance(got["eyes"].get(name), dict) and got["eyes"][name].get("status") != seal.PASSED]


def needs(got: dict) -> list:
    """最後の関所を開ける理由の列 [(1 句, 開き方に依らず開くか)]。開くか（ask）と 1 行目（final_head）はこの列だけから作る"""
    why = []
    if got["spec_changed"]:
        said = gatemarks.spec_words(got["spec_unchecked"]).said
        why.append((f"{said}（{len(got['spec_changed'])} 件。承認し直すかは次の run で答える）", True))
    unknown, hits = protected(got)
    if unknown:
        why.append((f"{PROTECTED_UNKNOWN}（人の確かめが要る）", True))
    if hits:
        why.append((f"{PROTECTED_HEAD}（{len(hits)} 件。人の確かめが要る）", True))
    if got["allowed_tests"]:
        why.append((f"{ALLOWED_TESTS_HEAD}（{len(got['allowed_tests'])} 件。人の確かめが要る）", True))
    word = tests_word(got)
    if word != "緑":
        why.append((f"最後のテストが{word}", False))
    if got["conflicts_unread"]:
        why.append((f"{CONFLICT_UNREAD}（{len(got['conflicts_unread'])} 件。人に回した申し出を数えられない）", True))
    if got["asked"]:
        why.append((f"{conflict.HEAD}を人に回した（{len(got['asked'])} 件）", True))
    if got["beside_unread"]:
        why.append((f"{BESIDE_UNREAD}（{len(got['beside_unread'])} 件。人に回した物・数え直しの食い違いを数えられない）", True))
    if got["handoffs"]:
        why.append((f"{HANDOFF_REASON}（{len(got['handoffs'])} 件）", False))
    blocked = blocked_eyes(got)
    if blocked:
        why.append((f"独立の目が阻害を返した（{'・'.join(blocked)}）", False))
    premise = got["eyes"].get("premise_check")
    if isinstance(premise, dict) and premise.get("verdict") == eyeverdict.VERDICTS[1]:
        why.append(("前提の検算が人に上げた", False))
    if got["mismatched"]:
        why.append((f"{MISMATCH_REASON}（{len(got['mismatched'])} 件）", False))
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
    return got["objection"] if got["objection"] and got["rejudge_verdict"] != judge_accept.ADOPTED else ""


def final_head(got: dict, why: list) -> list:
    guarded = bool(got["protected_hits"]) or bool(got["allowed_tests"])
    held = got["held"]
    happened = (f"最後のテストと独立の目が済み、報告の前で止まった。テストは{tests_word(got)}。"
                + ("開けた理由: " + "・".join(why) if why else
                   f"承認ノードはいつも開く設定（{gatepolicy.head_words({gatepolicy.FINAL_KEY: gatepolicy.ALWAYS})}）で、ほかに開けた理由は無い")
                + (f"。判定の役が人に聞くと保留にしたままの問いも在る（{len(held)} 件。承認ノードを開ける理由には数えない）" if held else "")
                + (f"。{got['split']}" if got["split"] else ""))
    decide = ("報告へ進めて run を終えるか、止めるか（打つ行は末尾の答え方）"
              + ("。守りのパスと許したテストの変更は下の最初のセクションを確かめてから通す" if guarded else ""))
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
    if got["allowed_tests"]:
        lines += [f"## {ALLOWED_TESTS_HEAD}（{len(got['allowed_tests'])} 件。承認済みの案と範囲の相談と裁定が書き換えを許したテスト。"
                  "通すのは人の答えだけ）", "",
                  *[f"- {row.get('path')}（許し {row.get('permit')}・{row.get('source')}）" for row in got["allowed_tests"]], ""]
    return lines


def conflict_section(got: dict) -> list:
    """食い違いの申し出の節（元 line_edge._conflict_text。conflict.human_lines の行のまま）と、控えを読めなかった訳"""
    lines = []
    if got["asked"]:
        lines += [f"## {conflict.HEAD}（{len(got['asked'])} 件。裁定役か機械が人に回した。直しの在りかは行ごとの末尾の括弧。通すのは人の答えだけ）", "",
                  *[f"- {row}" for row in got["asked"]], ""]
    if got["conflicts_unread"]:
        lines += [f"## {CONFLICT_UNREAD}（{len(got['conflicts_unread'])} 件。人に回した行かを数えられない。通すのは人の答えだけ）", "",
                  *[f"- {row}" for row in got["conflicts_unread"]], ""]
    if got["beside_unread"]:
        lines += [f"## {BESIDE_UNREAD}（{len(got['beside_unread'])} 件。人に回した物と数え直しの食い違いを数えられない。通すのは人の答えだけ）",
                  "", *[f"- {row}" for row in got["beside_unread"]], ""]
    return lines


def rows_section(head: str, rows: list, tail: str = "") -> list:
    return [f"## {head}（{len(rows)} 件{tail}）", "", *[f"- {row}" for row in rows], ""] if rows else []


def tests_lines(got: dict) -> list:
    """最後のテストの一式と修正前のテスト（test-gate の返りの欄のまま。元 _final_text の entry.suites_line・baseline_line）・自己申告の
    緑の次の手・ログ・走れなかった理由・作業ツリー"""
    ev = got["tests"]
    lines = [f"- テストの一式: {ev['suites']}", f"- {ev['baseline']}"]
    if ev["by"] == declared_checks.ROLE_NEEDED:
        lines.append(f"- {declared_checks.SELF_REPORTED_NOTE}。確かめてから通すか（continue の一言に何を走らせて何色だったか）、止めるか（stop）")
    lines += [x if x[:1].isspace() else f"- {x}" for x in [*got["tests_left"], *got["gates"]]]
    lines.append(f"- ログ: {ev['log']}")
    if ev["reason"]:
        lines.append(f"- 走れなかった・認証しなかった理由: {ev['reason']}")
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
    return [head, *[x if x[:1].isspace() else f"- {x}" for x in got["branch_rows"]]]


def eye_lines(got: dict) -> list:
    """独立の目の判定（元 line_edge._eyes。主語は平易な名、目の名と状態の語は括弧に回す: gatemarks.eye_named）と残りの数え"""
    lines = [f"- 独立の目の判定（阻害: {'・'.join(blocked_eyes(got)) or '無い'}）:"]
    missing = []
    for name in eyeverdict.EYES:
        row = got["eyes"].get(name)
        if not isinstance(row, dict):
            missing.append(name.upper())
            lines.append(f"  - {gatemarks.EYES[name.upper()]}（{name.upper()}）: 結果が無い（深さで省いたか、目のサブグラフが返さなかった）")
            continue
        reason = oneline.one_line(row.get("reason") or "")
        lines.append(f"  - {gatemarks.eye_named(name.upper(), row.get('status'))}" + (f"——理由: {reason}" if reason else ""))
        if name == "r2":
            lines += [f"    - {x}" for x in got["r2_inputs"]]
    premise = got["eyes"].get("premise_check")
    if isinstance(premise, dict):
        lines.append(f"  - 前提の検算: {premise.get('verdict') or '語が無い'}（{oneline.one_line(premise.get('reason') or '')}）")
        lines += [f"    - {x}" for x in got["premise_facts"]]
    blocked = blocked_eyes(got)
    lines.append(f"- 残り（最後の承認ノードで数えられる分）: 独立の目の阻害 {len(blocked)} 件（{'・'.join(blocked) or '無し'}）・"
                 f"結果が無い目 {len(missing)} 件（{'・'.join(missing) or '無し'}）・最後のテストが緑でない "
                 f"{0 if tests_word(got) == '緑' else 1} 件・柵の増え {len(got['fenced'])} 件")
    lines += [x if x[:1].isspace() else f"- {x}" for x in got["always"]]
    return lines


SPEC_APPLIES = ("  - 承認して報告へ進める（continue）と、差分は承認し直しを待たずに当たる（merge が run の置き場に置き、bin/apply が"
                "対象に当てる）。承認し直してから当てるなら stop で止める")


def question_lines(got: dict) -> list:
    """承認し直すかの問い（spec-check の questions）・人に聞いている問い（記録のまま引く。元 _final_text の pending_human）・保留の問いと答え方・答えた問い・当たらなかった依頼の
    答え・読めなかった保留。どれも無い時だけ「盤面の問い: 無い」"""
    lines = []
    if got["spec_changed"]:
        head = gatemarks.spec_words(got["spec_unchecked"]).head
        lines.append(f"- {head}: {len(got['spec_changed'])} 件")
        lines += [f"  - {q}" for q in got["spec_changed"]]
        lines.append("  - この承認ノードの答えはこの問いに答えない（continue でも仕様は承認し直さない）。問いは報告の冒頭と次の run の依頼の下書きへ渡る")
        lines.append(SPEC_APPLIES)
    if got["questions"]:
        lines.append(f"- {gatemarks.named(gatemarks.R4_GATE_NODE)}が人に聞いている問い（記録のまま引く。{len(got['questions'])} 件）:")
        for q in got["questions"]:
            lines += [f"  {x}" for x in gatemarks.quote(q)]
        lines.append("  - この承認ノードの答えはこの問いに答えない。問いは報告の冒頭と次の run の依頼の下書きへ渡る")
    if got["held"]:
        lines.append(f"- 判定の役が人に聞くと保留にしたままの問い（問いの台帳・{len(got['held'])} 件。この承認ノードの答えは問いに答えない。"
                     "問いは報告の冒頭に並ぶ）:")
        lines += [f"  - {q}" for q in got["held"]]
        lines.append(f"  {gatemarks.ANSWER_HOW}")
    if got["answered"]:
        lines.append(f"- {gatemarks.ANSWERED_HEAD}（問いの台帳・{len(got['answered'])} 件。保留の件数には数えない）:")
        lines += [f"  - {x}" for x in got["answered"]]
    lines += [f"- {x}" for x in got["unmatched"]]
    lines += [f"- {x}" for x in got["unread_holds"]]
    if not (got["spec_changed"] or got["questions"] or got["held"] or got["answered"] or got["unmatched"]):
        lines.append("- 共有ボードの問い: 無い")
    return lines


def final_text(got: dict, why: list, run_id: str) -> str:
    lines = [*final_head(got, why), ""]
    lines += protected_section(got)
    lines += conflict_section(got)
    lines += rows_section(fixboard.HANDOFF_HEAD, got["handoffs"], "。通すのは人の continue だけ")
    lines += rows_section(querytest.STUCK_HEAD, got["stuck"])
    lines += rows_section(querytest.UNPROVEN_HEAD, got["unproven"])
    lines += rows_section(querytest.CLOSURE_HEAD, got["closure"])
    lines += rows_section(replan.AMEND_HEAD, got["amend"])
    lines += [f"最後の承認ノード（最後のテストと独立の目の後・報告の前）: テストは{tests_word(got)}", ""]
    lines += tests_lines(got)
    lines += delta_lines(got)
    lines.append(f"- 止めずに残った異議: {left_objection(got) or '無い'}")
    lines += ["- 再審で決着した結果:", *[f"  {x}" if x.startswith("  ") else f"  - {x}" for x in got["rejudge"]]] if got["rejudge"] \
        else ["- 再審: 無い"]
    lines += [f"- 構造のサブグラフ: {got['structure_missing']}"] if got["structure_missing"] else []
    lines += [x if x[:1].isspace() else f"- {x}" for x in got["after"]]
    if got["passes"]:
        lines.append(f"- 直す前の承認ノードで通した項目（決め手が在るので聞かずに通した行と、人が通したので後の承認ノードで聞き直さなかった行。"
                     f"{len(got['passes'])} 件）:")
        lines += [f"  - {x}" for x in got["passes"]]
    lines += [x if x[:1].isspace() else f"- {x}" for x in got["converge"]]
    lines += [f"- {seal.DELETED_HEAD}: {p}" for p in got["deleted"]]
    lines += eye_lines(got)
    lines += question_lines(got)
    lines += [f"- {why_}" for why_ in got["unread"]]
    lines += [f"- 封じた差分の hash: {got['hash'] or '（無い）'}", f"- この文の控え: run の置き場の {FINAL_GATE_FILE}", "",
              "答え方（人が決める承認ノード。依頼者に聞いて、その言葉で答える）:",
              f"- 報告へ進める: {answer.line(run_id, 'continue', '<一言>')}（一言は {RECORD} に残る）",
              f"- 止める: {answer.line(run_id, 'stop', '<理由>')}（報告は出る）"]
    return "\n".join(lines) + "\n"



def ask(got: dict, *, mode: str, unattended: bool, run_id: str) -> dict:
    why, must = final_needs(got), any(m for _, m in needs(got))
    opens = must or gatepolicy.opens(mode or gatepolicy.ALWAYS, reasons=why, guarded=bool(got["protected_hits"]))
    if not opens:
        return {"open": False, "go": True, "stop_reason": "", "text": "", "reasons": why}
    if unattended:
        return {"open": False, "go": False, "stop_reason": stopby.NEEDS_HUMAN, "text": "", "reasons": why}
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
            unread.append(f"{where}: {type(error).__name__}: {oneline.one_line(error)}")
    return rows, unread


def ledger(judgment, start, before_fix, ties_judgment=None) -> tuple:
    """(問いの台帳の見え方（gatemarks.ledger_beside）か None, 添える行)。判定の指し札の先（judgment.json の questions・units と隣の
    materials.json）・始めの記録 start（start_doc で読んだ dict）の answers（依頼の答え）・修正前の関所の答え {decision, text, asked}・判定の結び（answer-ties.json。
    再審の判定の隣には無いので、1 回目の判定の指し札 ties_judgment の隣から読む）。結びの宛て先の key が今の問いにも単位にも無ければ
    字の一致に落とし、そのことを添える行に 1 行出す（gatemarks.lost_ties）。判定が無い（null）時は None、読めなければ添える行に訳"""
    if judgment is None:
        return None, []
    try:
        b = gatemarks.ledger_at(boundary.resolve(judgment), start, before_fix,
                                boundary.resolve(ties_judgment) if ties_judgment is not None else None)
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        return None, [f"判定の問いの控えか始めの記録を読めない（保留の問いを数えていない。{type(error).__name__}: {error}）"]
    units = [u.get("key") for u in b.record["units"]]
    return b, gatemarks.lost_ties(b.ties, b.record["questions"], units)


def ledger_rows(b) -> dict:
    """台帳の見え方 b から最後の関所に並べる行: 保留の問い・答えた問い（ANSWERED_HEAD）・当たらなかった依頼の答え・読めなかった保留"""
    if b is None:
        return {"held": [], "answered": [], "unmatched": [], "unread_holds": []}
    return {"held": gatemarks.held_lines(b), "answered": gatemarks.answered_lines(b),
            "unmatched": gatemarks.unmatched_answer_lines(b), "unread_holds": gatemarks.unread_hold_lines(b)}


def after_rows(structure_after) -> tuple:
    """(柵の増えの行, 直した後の実測の行（元 structmark.after_lines: 数・柵の増え・新しい名・修正案の外れの訳。実測の一部が落ちた
    status: failed はその訳つき）, 読めなかった訳)。実測が無い（null。実測の節が落ちた）時は、そう言う 1 行（NO_AFTER。元
    line_edge.after_edge は出口の無い実測を failed と理由で残した）。指し札が読めない・先の控えが読めなければ訳を返す"""
    if structure_after is None:
        return [], [NO_AFTER], ""
    try:
        folder = boundary.resolve(structure_after).parent
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        return [], [], f"直した後の実測のポインタを読めない（柵の増えを数えていない。{type(error).__name__}: {error}）"
    if structmark.read_after(folder) is None:
        return [], [], f"直した後の実測の控え {structmark.AFTER_FILE} を読めない（柵の増えを数えていない）"
    return structmark.after_rows(folder), structmark.after_lines(folder), ""


def structure_missing(structure) -> str:
    """計画の構造の目が落ちた周の 1 文（計画の返り structure の先の structure-state.json。structmark.note。元 line_edge._final_text の
    「構造のブロック: …」）。落ちていない・控えが無ければ空。指し札が読めなければその訳"""
    if structure is None:
        return ""
    try:
        folder = boundary.resolve(structure).parent
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        return f"構造の目の控えのポインタを読めない（{type(error).__name__}: {error}）"
    return structmark.note(structmark.read(folder))


def fix_beside(pointers) -> dict:
    """修正の段ごとの diff の隣の控え（fixed の diffs の先のフォルダ。lib/fixbeside.py と許したテストの変更の訳）から関所に並べる行:
    減っていない単位・閉鎖の数え直し・回さなかった試験・赤緑を確かめずに受けた回・差分の審査の穴の名札と手直しの結果・clean と
    レンズと仕組みの異常・許したテストの変更、と読めなかった訳（beside_unread。開ける理由になる）"""
    folders, unread = [], []
    for ptr in pointers or []:
        try:
            folders.append(boundary.resolve(ptr).parent)
        except (ValueError, TypeError, AttributeError, KeyError) as error:
            unread.append(f"修正の差分のポインタを読めない（隣の控えを読んでいない。{type(error).__name__}: {error}）")
    got = fixbeside.read(folders)
    allowed, allowed_unread = allowed_tests(folders)
    return {"stuck": fixbeside.closure_lines(got, stuck_only=True), "closure": fixbeside.closure_lines(got),
            "tests_left": fixbeside.tests_left_lines(got), "gates": fixbeside.gates_lines(got),
            "branch_rows": fixbeside.branch_rows(got), "always": fixbeside.always_rows(got), "allowed_tests": allowed,
            "beside_unread": [*unread, *got["unread"], *allowed_unread]}


def allowed_tests(folders) -> tuple:
    """(許したテストの変更の訳の行 {path, permit, source}, 読めなかった訳)。fix の collect が差分の隣に置く
    fixboard.ALLOWED_TESTS_FILE を段の順に読む。collect は落ちた道でも [] を置くので、無い・読めない・行の配列でないファイルは訳を
    返す（黙って空にしない）"""
    rows, unread = [], []
    for folder in folders:
        try:
            doc = json.loads((folder / fixboard.ALLOWED_TESTS_FILE).read_text(encoding="utf-8"))
            if not isinstance(doc, list) or not all(isinstance(row, dict) for row in doc):
                raise ValueError("行の配列でない")
        except (OSError, ValueError) as error:
            unread.append(f"許したテストの変更の訳 {folder / fixboard.ALLOWED_TESTS_FILE} を読めない（{type(error).__name__}: {error}）")
            continue
        rows += [row for row in doc if row not in rows]
    return rows, unread


def eye_notes(notes) -> dict:
    """独立の目の返り notes（premise-inputs.json の指し札）の隣の材料: R2 の行の下の前提の入力と『渡されていない』の照らし
    （eyeverdict.r2_input_lines。元 line_edge._r2_inputs）・人が通したので R4 で聞き直さなかった行（r4-gate-passes.json。元
    _final_text の gatemarks.lines）・前提の検算で偽と分かった仮定の問いと次の run の制約に足す実測（premise-check.json）。null は
    目のブロックが材料を書けなかった道（訳の 1 行）"""
    if notes is None:
        return {"r2_inputs": ["独立の設計と比べる目に渡した入力の控えが無い（独立の目の出力 notes が null）"], "eye_passes": [],
                "premise_facts": [], "notes_unread": []}
    try:
        folder = boundary.resolve(notes).parent
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        return {"r2_inputs": [], "eye_passes": [], "premise_facts": [],
                "notes_unread": [f"独立の目の材料のポインタを読めない（R2 の前提・人が通した行を並べていない。{type(error).__name__}: {error}）"]}
    rows = eyeverdict.gate_pass_rows(folder)
    return {"r2_inputs": eyeverdict.r2_input_lines(folder), "eye_passes": gatemarks.pass_lines(rows or []),
            "premise_facts": eyeverdict.premise_fact_lines(folder),
            "notes_unread": [] if rows is not None else [f"独立の目の {eyeverdict.GATE_PASSES} を読めない（人が通した行を並べていない）"]}


def review_rows(reviews) -> tuple:
    """(修正前の関所で通した行, 壁打ちの往復の行, 読めなかった訳)。事前審査の返り review（計画の往復と案の直しの事前審査）の隣の
    gatemarks.PASSES_FILE と PLAN_GATE_FILE の converge から"""
    passes, rounds, unread = [], [], []
    for ptr in reviews:
        if ptr is None:
            continue
        try:
            folder = boundary.resolve(ptr).parent
            passes += gatemarks.passes_of(folder)
            rounds += gatemarks.converge_of(folder)
        except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
            unread.append(f"事前審査の隣の控え（通した行・往復）を読めない（{type(error).__name__}: {oneline.one_line(error)}）")
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
    return [x for x in runreport.rejudge_lines(returns, runreport.rejudge_exit(returns)) if not x.startswith("再審されずに残った異議")]


def deleted_files(diff) -> tuple:
    """(封じた差分が消すファイル, 読めなかった訳)"""
    if diff is None:
        return [], ""
    try:
        return seal.deleted_paths(boundary.resolve(diff).read_text(encoding="utf-8", errors="replace")), ""
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        return [], f"封じた差分を読めない（取り込むと消えるファイルを数えていない。{type(error).__name__}: {error}）"


def start_doc(ptr) -> tuple:
    """(始めの記録の dict か None, 読めなかった訳)。指し札が無ければ (None, "")"""
    if ptr is None:
        return None, ""
    try:
        return startrec.load(boundary.resolve(ptr)), ""
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        return None, f"始めの記録を読めない（保留の問いと起点の版を読んでいない。{type(error).__name__}: {error}）"


def env(name: str):
    return boundary.value(os.environ.get(f"INPUTS_{name}"))


def final_tests(tests) -> dict:
    """最後のテストの返り tests（試験の関門の返りまるごと）の by・suites_line・log・baseline_line・reason を declared_checks.gate_values で
    見せる値にし、関門が返さなかった（tests が None＝飛ばされた節）時だけ unread にその旨（by の空の字は返った形のまま）"""
    return {**declared_checks.gate_values(tests), "unread": "" if tests is not None else "最後のテストの証拠が無い（試験の関門が返さなかった）"}


def got_of_env() -> dict:
    tests = boundary.picked(os.environ.get("INPUTS_TESTS"), TESTS)
    eyes = boundary.picked(os.environ.get("INPUTS_EYES"), EYES)
    seal = boundary.picked(os.environ.get("INPUTS_SEAL"), SEAL)
    gate = dict.fromkeys(TESTS) if tests is None else tests
    eye = dict.fromkeys(EYES) if eyes is None else eyes
    closing = SEAL_SKIPPED if seal is None else seal
    start, start_unread = start_doc(env("START"))
    b, ledger_notes = ledger(env("JUDGMENT"), start, env("BEFORE_FIX_ANSWER"), env("TIES_JUDGMENT"))
    fenced, after, after_unread = after_rows(eye["structure_after"])
    asked, conflicts_unread = asked_conflicts(boundary.items(os.environ.get("INPUTS_CONFLICTS")))
    passes, rounds, review_unread = review_rows((env("PLAN_REVIEW"), env("REPLAN_REVIEW")))
    deleted, deleted_unread = deleted_files(closing["diff"])
    beside = fix_beside(boundary.items(os.environ.get("INPUTS_FIX_DIFFS")))
    noted = eye_notes(eye["notes"])
    raw = {"units": boundary.items(os.environ.get("INPUTS_UNITS")), "first_units": boundary.items(os.environ.get("INPUTS_FIRST_UNITS")),
           "judgment": env("JUDGMENT"), "ties_judgment": env("TIES_JUDGMENT"), "rejudged": boundary.flag(os.environ.get("INPUTS_REJUDGED")),
           "rejudge_verdict": boundary.text(os.environ.get("INPUTS_REJUDGE_VERDICT")),
           "objection": boundary.text(os.environ.get("INPUTS_OBJECTION")),
           "fix_units": boundary.items(os.environ.get("INPUTS_FIX_UNITS")), "groups": boundary.items(os.environ.get("INPUTS_GROUPS"))}
    returns = judged_returns(raw)
    return {
        "tests_ok": boundary.as_flag(gate["ok"]),
        "green": boundary.as_flag(gate["green"]),
        "red_cause": boundary.as_text(gate["red_cause"]),
        "ran_steps": gate["ran_steps"],
        "tests": final_tests(tests),
        "worktree": str(Path.cwd().resolve()),
        "base_rev": str((start or {}).get("base_rev") or ""),
        "protected_hits": boundary.as_items(closing["protected_hits"]),
        "asked": asked,
        "conflicts_unread": conflicts_unread,
        "handoffs": [x for x in boundary.items(os.environ.get("INPUTS_HANDOFFS")) if isinstance(x, str)],
        "mismatched": [x for x in boundary.items(os.environ.get("INPUTS_MISMATCHED")) if isinstance(x, str)],
        "eyes": {name: eye[name] for name in ("r1", "r2", "r3", "r4", "premise_check")},
        "questions": [q for q in boundary.as_items(eye["questions"]) if isinstance(q, str)],
        "spec_changed": [q for q in boundary.items(os.environ.get("INPUTS_SPEC_CHANGED")) if isinstance(q, str)],
        "spec_unchecked": boundary.flag(os.environ.get("INPUTS_SPEC_UNCHECKED")),
        "objection": raw["objection"],
        "rejudge_verdict": raw["rejudge_verdict"],
        "rejudge": rejudge_rows(returns),
        "split": runreport.split_line(returns),
        "unproven": [x.removeprefix("  - ") for x in runreport.unproven_lines(returns)[1:]],
        "amend": replan.amend_lines(boundary.items(os.environ.get("INPUTS_REPLAN_ITEMS")),
                                    refixed=boundary.flag(os.environ.get("INPUTS_REFIXED")), answer=env("REPLAN_ANSWER"),
                                    widened=boundary.items(os.environ.get("INPUTS_WIDENED"))),
        "delta_review": env("DELTA_REVIEW"),
        **beside,
        "structure_missing": structure_missing(env("STRUCTURE")),
        "sealed": boundary.as_flag(closing["ok"]),
        "seal_reason": boundary.as_text(closing["reason"]),
        "hash": boundary.as_text(closing["hash"]),
        "deleted": deleted,
        "fenced": fenced,
        "after": after,
        "passes": [*passes, *noted["eye_passes"]],
        "r2_inputs": noted["r2_inputs"],
        "premise_facts": noted["premise_facts"],
        "converge": rounds,
        **ledger_rows(b),
        "unread": [*([start_unread] if start_unread else []), *ledger_notes, *([after_unread] if after_unread else []),
                   *review_unread, *([deleted_unread] if deleted_unread else []), *noted["notes_unread"]],
    }


def from_env() -> dict:
    """ask の引数（with: の欄の全部を読む）"""
    return {"got": got_of_env(), "mode": boundary.text(os.environ.get("INPUTS_FINAL_GATE")),
            "unattended": boundary.flag(os.environ.get("INPUTS_UNATTENDED")), "run_id": os.environ["WORKFLOW_ID"]}


def fallback(reason: str) -> dict:
    return {"open": False, "go": False, "stop_reason": boundary.LINE_SCRIPT, "text": "", "reasons": [reason]}


if __name__ == "__main__":
    boundary.run(lambda: keep(ask(**from_env()), Path(os.environ["ARTIFACTS_DIR"])), fallback)

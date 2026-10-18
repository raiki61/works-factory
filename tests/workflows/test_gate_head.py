"""人が読む関所の文の冒頭 3 行（lib/gatemarks.py の head3・gate_text・pushes）を、線の script で照らす。
元は今の works の works/tests/test_gate_head.py の AskGateCase と FinalHeadCase（関所の文を線が持つので、線の script の試験に置く）。

- 修正前の関所（ask_before_fix.gate_text）は 1〜3 行目が 起きたこと・決めてほしいこと・推し
- 最後の関所の冒頭（ask_final.final_head）は開けた理由（ask_final.final_needs）を 1 行目に並べ、守りのパスはそこで名指す
- 推しは判定の役が問いの理由に書いた物だけ（機械は作らない）。3 行を足しても中身は 1 つも落ちない
- 最後の関所の文の本文は元 line_edge.final_edge・_final_text の節の並び（FinalSectionsCase。部分 B2）
- 元 works/tests/test_plan_gate.py の 3 本を元の名で写した（LedgerAsksCase。S27）
盤面に届く物（仕様の関所）を読む元の試験は持ってこない。保留にしたままの問いは判定の指し札の先から読む（ask_final.ledger。
tests/workflows/test_line.py の AskFinalReadsCase）。
"""
import json
import os
import pathlib
import re
import tempfile
import unittest
from unittest import mock

from lib.tests import test_plan_gate as plan_gate
from lib.tests.test_outcome import fixed_run
from tests.bin.linescripts import load

ask_before_fix = load("ask_before_fix")
ask_final = load("ask_final")

import answer  # noqa: E402  （線の script が lib/ を sys.path に足した後に読む）
import conflict  # noqa: E402
import declared_checks  # noqa: E402
import eyeverdict  # noqa: E402
import gatemarks  # noqa: E402
import green_cert  # noqa: E402
import protect  # noqa: E402
import querytest  # noqa: E402
import replan  # noqa: E402
import runreport  # noqa: E402
import seal  # noqa: E402

HEADS = [gatemarks.HAPPENED, gatemarks.DECIDE, gatemarks.PUSH]
NARROW_ITEM = "修正案 1 が狭める能力: 空の列の mean——0 割りの例外のまま"

# 元 works/tests/test_plan_gate.py 324-327 行
FORK_UNIT = "stats.py mean: 空の列の扱いが決まらない"
OTHER_UNIT = "stats.py clamp: 上限を超えた値に lo を返す"
UNITS = [{"key": FORK_UNIT, "label": "block"}, {"key": OTHER_UNIT, "label": "block"}]
FORK = {"key": "q-empty-mean", "kind": "fork", "status": "held", "origin": FORK_UNIT, "options": ["例外", "0 を返す"],
        "reason": "空の列の意味が 2 つに割れる。推し: 例外——呼び手が既に例外を捕まえている"}

# 元 works/tests/test_plan_gate.py 716-750 行
RECORD_NAME = re.compile(r"(?<![A-Za-z0-9_.])(?:(?:p\d|spec|report)\.[a-z0-9_]+|process\.[a-z_.]+[a-z]|fix_test_scope|fix_code_as|ask_human)")
EYE_OR_STATE = re.compile(r"(?<![A-Za-z0-9_-])(?:R[1-4]|" + "|".join(map(re.escape, seal.STATUSES))
                          + r"|premise-invalid|carried_over|not_applicable|not_run)(?![A-Za-z0-9_-])")


def _spans(line: str) -> list:
    """行の外側の括弧（（）と ()）の (始め, 終わり)"""
    out, depth, start = [], 0, 0
    for i, ch in enumerate(line):
        if ch in "（(":
            if depth == 0:
                start = i
            depth += 1
        elif ch in "）)" and depth:
            depth -= 1
            if depth == 0:
                out.append((start, i))
    return out


def internal_subjects(text: str) -> list:
    """人が読む文の行のうち、盤面の内部の名が主語になっている行。記録の名（節の名・記録の欄・裁定の語）は括弧の中の『記録の名』の
    後ろにだけ、目の名と状態の語は括弧の中にだけ置いてよい（平易な名が主語で、内部の名は括弧に回す）"""
    bad = []
    for line in text.splitlines():
        spans = _spans(line)
        inside = lambda m: next(((s, e) for s, e in spans if s < m.start() < e), None)  # noqa: E731
        for m in EYE_OR_STATE.finditer(line):
            if inside(m) is None:
                bad.append(line)
        for m in RECORD_NAME.finditer(line):
            span = inside(m)
            if span is None or "記録の名" not in line[span[0]:m.start()]:
                bad.append(line)
    return list(dict.fromkeys(bad))


def heads(text: str) -> list:
    return [next((h for h in HEADS if x.startswith(h)), x) for x in text.splitlines()[:3]]


class AskGateCase(unittest.TestCase):
    def asking(self, items, kinds=("regression",)):
        return {"node": "p2.human_gate", "kinds": list(kinds), "question": "狭まる能力を代償に採るか", "items": list(items)}

    def test_plan_gate_starts_with_three_lines(self):
        text = ask_before_fix.gate_text(self.asking([NARROW_ITEM]), run_id="run-1")
        self.assertEqual(heads(text), HEADS)
        first = text.splitlines()[0]
        self.assertIn("直す前の承認ノード", first)
        self.assertIn("1 件", first)
        self.assertEqual(internal_subjects("\n".join(text.splitlines()[:3])), [])

    def test_nothing_is_dropped_behind_the_head(self):
        """3 行の後ろに問いの文・項目・両方の答えの行が残る（依頼 4: 情報を 1 つも減らさない）"""
        text = ask_before_fix.gate_text(self.asking([NARROW_ITEM]), run_id="run-1")
        rest = "\n".join(text.splitlines()[3:])
        for want in ("> 狭まる能力を代償に採るか", f"- {NARROW_ITEM}", answer.line("run-1", "continue", "<通す範囲と条件>"),
                     answer.line("run-1", "stop", "<理由>"), f"記録の名 {ask_before_fix.RECORD}"):
            self.assertIn(want, rest)

    def test_push_comes_only_from_the_record(self):
        """推しは項目（判定の問いの理由）に書かれた物だけ。無ければ NO_PUSH、推しの無い項目が混じればそう断る"""
        none = ask_before_fix.gate_text(self.asking([NARROW_ITEM]), run_id="run-1").splitlines()[2]
        self.assertEqual(none, gatemarks.PUSH + gatemarks.NO_PUSH)
        ask = gatemarks.ask_text(FORK)
        only = ask_before_fix.gate_text(self.asking([ask], kinds=("fork",)), run_id="run-1").splitlines()[2]
        self.assertEqual(only, gatemarks.PUSH + "例外——呼び手が既に例外を捕まえている")
        mixed = ask_before_fix.gate_text(self.asking([ask, NARROW_ITEM], kinds=("fork", "regression")), run_id="run-1").splitlines()[2]
        self.assertTrue(mixed.startswith(only), mixed)
        self.assertIn(gatemarks.NO_PUSH, mixed)
        unsaid = gatemarks.ask_text({**FORK, "reason": "空の列の意味が 2 つに割れる"})
        self.assertEqual(gatemarks.pushes([unsaid]), gatemarks.NO_PUSH, "ask_text の断りの句を推しと読まない")


def final_got(**kw) -> dict:
    """最後の関所の材料（ask_final.got_of_env の形）。既定は緑で、目は全部通り、申し出も守りのパスの当たりも無い"""
    eye = {"status": "pass", "reason": ""}
    got = {"tests_ok": True, "green": True, "red_cause": "", "ran_steps": None, "tests": {**declared_checks.gate_values({"by": declared_checks.ENGINE}), "unread": ""},
           "worktree": "/tmp/tree", "base_rev": "0123456789abcdef", "protected_hits": [], "asked": [], "conflicts_unread": [],
           "allowed_tests": [], "beside_unread": [], "eyes": {"r1": eye, "r2": eye, "r3": eye, "r4": eye, "premise_check": None}, "questions": [], "spec_changed": [], "spec_unchecked": False,
           "objection": "", "rejudge_verdict": "", "rejudge": [], "split": "", "unproven": [], "amend": [],
           "delta_review": None, "branch_rows": [], "handoffs": [], "mismatched": [], "stuck": [], "closure": [], "tests_left": [],
           "gates": [], "always": [], "structure_missing": "", "r2_inputs": [], "premise_facts": [], "sealed": True, "seal_reason": "", "hash": "a" * 64, "deleted": [], "sealed_diff": "", "fenced": [],
           "after": [], "passes": [], "converge": [], "held": [], "answered": [], "unmatched": [], "unread_holds": [], "unread": []}
    got.update(kw)
    return got


class FinalHeadCase(unittest.TestCase):
    def head(self, got):
        return ask_final.final_head(got, ask_final.final_needs(got))

    def test_three_lines_and_reasons(self):
        blocked = {"status": "redesign-needed", "reason": ""}
        got = self.head(final_got(green=False, red_cause="introduced", asked=["u1: 裁定の文（名指し a.py:1, t.py:2・種類 not_red・正しいと見た側 unknown・c1）"],
                                  eyes={**final_got()["eyes"], "r3": blocked}))
        self.assertEqual(heads("\n".join(got)), HEADS)
        for want in ("テストは赤", "食い違いの申し出を人に回した（1 件）", "独立の目が通さなかった（R3: 作り直しが要る）"):
            self.assertIn(want, got[0])
        self.assertEqual(got[2], gatemarks.PUSH + gatemarks.NO_PUSH)
        self.assertEqual(internal_subjects("\n".join(got)), [])

    def test_tests_that_did_not_run_are_named_in_the_first_line(self):
        """#492: 最後のテストが走っていない（incomplete）・走ったと確かめられていない（原因の無い赤）は 1 行目に句で出る"""
        for cause, want in (("incomplete", green_cert.NOT_RAN), ("", green_cert.UNVERIFIED_RUN)):
            with self.subTest(cause=cause):
                first = self.head(final_got(tests_ok=False, green=False, red_cause=cause))[0]
                self.assertIn(want, first)
                self.assertIn(green_cert.RAN_GUIDE, first)
        green = self.head(final_got())[0]
        for note in green_cert.RAN_NOTES:
            self.assertNotIn(note, green)

    def test_partly_started_steps_are_named_in_the_first_line(self):
        """#514: 宣言の段の一部だけ起こせた最後のテストは、1 行目が起こした段と起こせなかった段を名指し、「走っていない」と言わない"""
        first = self.head(final_got(tests_ok=False, green=False, red_cause="incomplete",
                                    ran_steps={"ran": ["unit"], "unran": ["lint"]}))[0]
        self.assertIn(green_cert.PARTLY_RAN, first)
        self.assertIn("unit", first)
        self.assertIn("lint", first)
        self.assertNotIn(green_cert.NOT_RAN, first)

    def test_gate_script_failure_is_not_named_not_ran(self):
        """#492 R1: 返す節の中の誤り（by が空・incomplete）は「走っていない」と言わず、工場の不具合の句を出す"""
        broke = {**declared_checks.gate_values({}), "unread": ""}
        first = self.head(final_got(tests_ok=False, green=False, red_cause="incomplete", tests=broke))[0]
        self.assertIn(green_cert.GATE_BROKE, first)
        self.assertNotIn(green_cert.NOT_RAN, first)

    def test_protected_named_in_the_first_line(self):
        got = self.head(final_got(protected_hits=["tests/test_stats.py"]))
        self.assertIn(ask_final.PROTECTED_HEAD, got[0])
        self.assertIn("人の確かめが要る", got[0])
        self.assertIn("守りのパス", got[1])
        unknown = self.head(final_got(protected_hits=[seal.unknown_row("一覧が読めない")]))
        self.assertIn(ask_final.PROTECTED_UNKNOWN, unknown[0])
        self.assertNotIn(ask_final.PROTECTED_HEAD, unknown[0])
        self.assertNotIn("守りのパス", "".join(self.head(final_got())[:2]))

    def test_final_edge_puts_the_head_before_the_sections(self):
        """最後の関所の文: 冒頭 3 行 → 空行 → 守りのパスの節（最初の見出し）→ 残りの節"""
        text = ask_final.final_text(final_got(protected_hits=["tests/test_stats.py"]), ["理由"], "run-1")
        lines = text.splitlines()
        self.assertEqual(heads(text), HEADS)
        self.assertEqual(lines[3], "")
        self.assertTrue(lines[4].startswith("## " + ask_final.PROTECTED_HEAD), lines[4])

    def test_protected_section_keeps_rule_and_count(self):
        """merge が protect.lines で作った行は、冒頭 3 行の直後の最初の節に字のまま載る（規則と行数を落とさない）"""
        rows = protect.lines([{"path": "lib/seal.py", "id": "seal", "glob": "lib/seal.py", "why": "封印", "added": 2, "deleted": 1},
                              {"path": "lib/x.bin", "id": "lib", "glob": "lib/**", "why": "芯", "added": None, "deleted": None}])
        lines = ask_final.final_text(final_got(protected_hits=rows), ["理由"], "run-1").splitlines()
        self.assertTrue(lines[4].startswith("## " + ask_final.PROTECTED_HEAD), lines[4])
        self.assertEqual(lines[5:8], ["", *[f"- {row}" for row in rows]])   # 見出しの下は元 line_edge._protected_text と同じく空行
        self.assertIn("（+2 −1）: 規則 seal（lib/seal.py）", lines[6])

    def test_final_text_names_the_sealed_hash(self):
        self.assertIn(f"封じた差分の hash: {'a' * 64}", ask_final.final_text(final_got(), ["理由"], "run-1"))
        self.assertIn("封じた差分の hash: （無い）", ask_final.final_text(final_got(hash=""), ["理由"], "run-1"))

    def test_when_needed_opens_on_the_same_reasons_as_the_first_line(self):
        """when_needed で開くかと 1 行目の開けた理由は同じ 1 つの列（final_needs）: 列が空なら開かず、在れば全部が 1 行目に載る"""
        self.assertFalse(ask_final.ask(final_got(), mode="when_needed", unattended=False, run_id="run-1")["open"])
        got = ask_final.ask(final_got(green=False, questions=["q"]), mode="when_needed", unattended=False, run_id="run-1")
        self.assertTrue(got["open"])
        self.assertIn("開けた理由: " + "・".join(got["reasons"]), got["text"].splitlines()[0])

    def test_unknown_eye_status_opens_when_needed(self):
        """表に無い status を返した目（R3）は『独立の目が通さなかった』を開ける理由に入れる（when_needed で関所が開く）。表に無い語は字のまま"""
        odd = {"status": "not-in-the-status-table", "reason": "表に無い"}
        got = final_got(eyes={**final_got()["eyes"], "r3": odd})
        self.assertEqual(ask_final.final_needs(got), ["独立の目が通さなかった（R3: not-in-the-status-table）"])

    def test_fix_needed_eye_opens_without_calling_it_blocking(self):
        """R1 だけが fix-needed の時、開ける理由は『独立の目が通さなかった（R1: 直しが要る）』の 1 句で『阻害』と呼ばず、when_needed で関所は
        開く。冒頭と目の行の主語は平易なまま（目の名と状態の語は括弧の中だけ。R1 の理由の頭の UNNAMED_REDESIGN も同じ）"""
        fix = {"status": seal.FIX_NEEDED, "reason": eyeverdict.UNNAMED_REDESIGN + "名前の付け方が揃っていない"}
        got = final_got(eyes={**final_got()["eyes"], "r1": fix})
        self.assertEqual(ask_final.final_needs(got), ["独立の目が通さなかった（R1: 直しが要る）"])
        opened = ask_final.ask(got, mode="when_needed", unattended=False, run_id="run-1")
        self.assertTrue(opened["open"])
        self.assertEqual(opened["reasons"], ["独立の目が通さなかった（R1: 直しが要る）"])
        shown = "\n".join([*self.head(got), *ask_final.eye_lines(got)])
        self.assertNotIn("阻害", opened["text"])
        self.assertEqual(internal_subjects(shown), [])
        self.assertIn("独立の目の判定（通さなかった目: R1: 直しが要る）", shown)
        self.assertIn("独立の目が通さなかった目 1 件（R1: 直しが要る）", shown)

    def test_held_questions_shown_but_not_a_reason(self):
        """保留にしたままの問いは 1 行目に出るが、開けた理由には数えない（when_needed で関所を開けない）"""
        got = final_got(held=[gatemarks.ask_text(FORK)])
        self.assertEqual(ask_final.final_needs(got), [])
        first = self.head(got)[0]
        self.assertIn("保留にしたままの問いも在る（1 件。承認ノードを開ける理由には数えない）", first)
        self.assertNotIn("開けた理由: ", first)
        self.assertFalse(ask_final.ask(got, mode="when_needed", unattended=False, run_id="run-1")["open"])

    def test_push_from_held_questions(self):
        got = self.head(final_got(held=[gatemarks.ask_text(FORK)]))
        self.assertEqual(got[2], gatemarks.PUSH + "例外——呼び手が既に例外を捕まえている")
        got = self.head(final_got(questions=[gatemarks.ask_text(FORK)]))
        self.assertEqual(got[2], gatemarks.PUSH + "例外——呼び手が既に例外を捕まえている")

    def test_fence_rise_is_a_reason(self):
        row = {"where": "a.py", "text": "考えの住処: 止め（語）を知る場所が a.py で増えた"}
        self.assertEqual(ask_final.final_needs(final_got(fenced=[row])),
                         ["考えの住処の柵の数が増えた（1 件。住処へ寄せるか、増やすなら地図と柵の表を直す）"])


def every_section() -> dict:
    """最後の関所の文の節が全部在る材料（L-G51・L-W28〜L-W37 の節ごとに 1 行ずつ）"""
    tests = declared_checks.gate_values({"by": "engine", "suites_line": "走らせた: suite（exit 0）／走らせなかった: 無い",
                                   "log": "test-gate/final/logs/checks.log", "reason": "",
                                   "baseline_line": "修正前のテスト: 緑（元の結末（入力 baseline）の status clean）——最後のテストの赤は修正の後に出た赤でありうる"})
    return final_got(
        tests={**tests, "unread": ""}, protected_hits=["tests/test_stats.py（+1 −0）: 規則 tests（tests/**）——試験"],
        asked=["u1: 人が決める（名指し a.py:1, t.py:2・種類 not_red・正しいと見た側 unknown・c1）"],
        allowed_tests=[{"path": "tests/test_mean.py", "permit": "plan-1", "source": "plan"}], unproven=["u1: 例が無い"], amend=["案の項目 1: 直した——人が承認した"],
        delta_review={"rounds": 2, "pass": True}, branch_rows=["差分の審査の穴の枝: 見本の 1 行", "  - k: 項目 1"],
        objection="異議の文", rejudge=["再審の結果: 退ける（異議: 異議の文）"],
        after=["直した後の実測: 表 1", "  - 新しい名 mean_or_zero（現れる所 2 か所）"],
        passes=["直す前の関所（記録の名 p2.human_gate）（周 1）で決め手が在るので聞かずに通した: 行（決め手: docs/adr.md:3）"],
        converge=["事前審査の壁打ち: 1 往復で clean"], deleted=["old.py"], questions=["R4 が聞く問い"],
        held=[gatemarks.ask_text(FORK)], answered=["答えた行"], unmatched=["依頼の答えに当たる問いが台帳に無い: x"],
        unread_holds=["読めなかった保留: 「q-typo」"], unread=["読めない訳"])


class FinalSectionsCase(unittest.TestCase):
    """最後の関所の文の本文を元 line_edge.final_edge・_final_text の節の並びに戻した（L-G51・L-W28〜L-W37・T35・T41・M29・M38）"""

    def text(self, got):
        return ask_final.final_text(got, ask_final.final_needs(got), "run-1")

    def test_final_text_keeps_every_section(self):
        """L-G51: 節が元の並びで全部在る（冒頭 3 行 → 守りのパス → 許したテスト → 申し出 → 例で試していない単位 → 直した案の項目 →
        テスト・ログ・作業ツリー → 差分の審査 → 異議・再審 → 実測 → 通した行・往復 → 消えるファイル → 目 → 問い → 控え → 答え方）"""
        text = self.text(every_section())
        order = ["## " + ask_final.PROTECTED_HEAD, "## " + ask_final.ALLOWED_TESTS_HEAD, "## " + conflict.HEAD,
                 "## " + querytest.UNPROVEN_HEAD, "## " + replan.AMEND_HEAD, "最後の承認ノード（", "- テストの一式: ",
                 "- 修正前のテスト: ", "- ログ: ", "- run の作業ツリー: ", "- 差分の審査: 2 回", "差分の審査の穴の枝: 見本の 1 行",
                 "- 止めずに残った異議: 異議の文", "- 再審で決着した結果:", "直した後の実測: 表 1", "- 直す前の承認ノードで通した項目",
                 "事前審査の壁打ち: 1 往復", f"- {seal.DELETED_HEAD}: old.py", "- 独立の目の判定", "- 残り（最後の承認ノードで数えられる分）",
                 "が人に聞いている問い（記録のまま引く", "- 判定の役が人に聞くと保留にしたままの問い", gatemarks.ANSWERED_HEAD,
                 "依頼の答えに当たる問いが台帳に無い", "読めなかった保留", "- 読めない訳", "- 封じた差分の hash", "- この文の控え: ",
                 "答え方（"]
        at = [text.find(x) for x in order]
        self.assertNotIn(-1, at, [x for x, i in zip(order, at) if i < 0])
        self.assertEqual(at, sorted(at), text)

    def test_final_text_subjects_are_plain(self):
        """L-G25: 文の全体で、主語は平易な名で、盤面の節・目・状態の語は括弧に回す（元 gatemarks.named・eye_named）"""
        blocked = {"status": "redesign-needed", "reason": "独立設計と食い違う"}
        got = every_section()
        got["eyes"] = {**got["eyes"], "r2": blocked, "r4": None}
        got["questions"] = []
        self.assertEqual(internal_subjects(self.text(got)), [])

    def test_plain_subject_guard_sees_every_eye_word(self):
        """目の状態の語（seal.STATUSES の全部。直しが要る seal.FIX_NEEDED を含む）は、素の語で主語に置くと両方の柵が拾い、括弧の中なら拾わない"""
        self.assertIn(seal.FIX_NEEDED, seal.STATUSES)
        for guard in (internal_subjects, plan_gate.internal_subjects):
            for word in seal.STATUSES:
                with self.subTest(guard=guard.__module__, word=word):
                    self.assertTrue(guard(f"目が {word} を返した"))
                    self.assertEqual(guard(f"目が返した（{word}）"), [])

    def test_final_text_carries_suites_and_baseline_lines(self):
        """T35: 最後のテストの一式の行と修正前のテストの行を、test-gate の返りの欄のまま出す"""
        text = self.text(every_section())
        self.assertIn("- テストの一式: engine・走らせた: suite（exit 0）／走らせなかった: 無い", text)
        self.assertIn("- 修正前のテスト: 緑（元の結末（入力 baseline）の status clean）——最後のテストの赤は修正の後に出た赤でありうる", text)
        self.assertIn("- ログ: test-gate/final/logs/checks.log", text)

    def test_self_reported_green_names_how_to_declare(self):
        """T41: 任せ先の自己申告の緑は、engine が走らせた結果でないことと、宣言 .review-checks.json に書く次の手と、確かめて続けるか
        止めるかを添える"""
        got = every_section()
        got["tests"] = {**got["tests"], "by": declared_checks.ROLE_NEEDED,
                        "suites": "role_needed・走らせた: 任せ先の CI の役 blk-ci が選んだ一式（素材の status clean）",
                        "reason": "任せ先の自己申告の緑（機械が走らせていない）"}
        text = self.text({**got, "tests_ok": False})
        line = next(x for x in text.splitlines() if declared_checks.DECL_NAME in x)
        for want in ("engine が走らせた結果ではない", "次の run から engine が走らせる", "continue", "stop"):
            self.assertIn(want, line)
        self.assertIn("- 走れなかった・認証しなかった理由: 任せ先の自己申告の緑", text)
        self.assertNotIn(declared_checks.DECL_NAME, self.text(every_section()))

    def test_protected_section_says_how_to_see_the_diff(self):
        """M29: 当たりの在る節に差分の見方（git -C <作業ツリー> diff <起点> -- <パス>）と一覧の置き場。確かめられない時は理由と一覧"""
        text = self.text(every_section())
        self.assertIn("- 差分: git -C /tmp/tree diff 0123456789ab -- <パス>（未追跡は新しいファイル）", text)
        self.assertIn(f"- 一覧: {protect.MANIFEST}", text)
        unknown = self.text(final_got(protected_hits=[seal.unknown_row("一覧が読めない")]))
        self.assertIn(f"## {ask_final.PROTECTED_UNKNOWN}", unknown)
        self.assertIn("- 理由: 一覧が読めない", unknown)
        self.assertIn(f"- 一覧: {protect.MANIFEST}", unknown)
        self.assertNotIn("git -C", unknown)

    def test_gate_passes_are_listed(self):
        """L-G19: 修正前の関所が聞かずに通した行（と R4 で聞き直さなかった行）を最後の関所の文に 1 件 1 行で載せる"""
        text = self.text(every_section())
        self.assertIn("  - 直す前の関所（記録の名 p2.human_gate）（周 1）で決め手が在るので聞かずに通した: 行", text)
        self.assertNotIn("直す前の承認ノードで通した項目", self.text(final_got()))

    def test_answered_and_unmatched_are_listed(self):
        """L-G37: 答えた問い（ANSWERED_HEAD）とどの問いにも当たらなかった依頼の答えを並べ、「盤面の問い: 無い」と書かない"""
        text = self.text(final_got(answered=["答えた行"], unmatched=["依頼の答えに当たる問いが台帳に無い: x"]))
        self.assertIn(f"- {gatemarks.ANSWERED_HEAD}（問いの台帳・1 件。保留の件数には数えない）:", text)
        self.assertIn("  - 答えた行", text)
        self.assertIn("- 依頼の答えに当たる問いが台帳に無い: x", text)
        self.assertNotIn("共有ボードの問い: 無い", text)
        self.assertIn("共有ボードの問い: 無い", self.text(final_got()))

    def test_conflict_section_comes_first_without_protected(self):
        """L-G49: 守りのパスが無ければ、申し出の節が冒頭 3 行の直後の最初の節（1 行目でも名指す）"""
        got = final_got(asked=["u1: 人が決める"])
        lines = self.text(got).splitlines()
        self.assertTrue(lines[4].startswith("## " + conflict.HEAD), lines[4])
        self.assertIn(f"{conflict.HEAD}を人に回した（1 件）", lines[0])

    def test_conflict_section_head_leaves_where_the_fix_is_to_each_row(self):
        """節の見出しは単位を直さずに残したと言い切らない。query_hits_fixed の直しは差分に在り、直したかは行ごとに
        conflict.human_lines が種類から書く（#355。c38831c2 の関所が差分に在る直しを直さずに残したと書いた）"""
        got = final_got(asked=[f"u1: 置き換える問いを書けない（名指し a.py:1・種類 query_hits_fixed・c1・{conflict.FIX_IN_DIFF}）"])
        head = next(x for x in self.text(got).splitlines() if x.startswith("## " + conflict.HEAD))
        self.assertNotIn(conflict.UNFIXED_LEFT, head)


class LedgerAsksCase(unittest.TestCase):
    """元 works/tests/test_plan_gate.py の LedgerAsksCase・EscalateAsksCase の 3 本を元の名で写した（S27）。元は盤面の記録から
    line_edge._final_text と report.head_decisions を組んだ。ここは判定の judgment.json と始めの記録と修正前の関所の答えを置き、
    最後の関所の文は ask_final（ledger・ledger_rows・final_text）、報告の冒頭は runreport._decisions（「1. 人が決めること」の行）で組む"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.artifacts = pathlib.Path(tmp.name)
        env = mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(self.artifacts), "WORKFLOW_ID": "run-1"})
        env.start()
        self.addCleanup(env.stop)

    def place(self, rel, doc):
        path = self.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return {"type": "archon_artifact", "run_id": "run-1", "path": rel}

    def gate(self, questions=(), units=UNITS, answer=None):
        """(最後の関所の文, 報告の冒頭の行)。answer は修正前の関所の答え {decision, text, asked}"""
        judgment = self.place("judge/judgment.json", {"questions": list(questions), "units": list(units)})
        start = self.place("start.json", {"answers": []})
        b, notes = ask_final.ledger(judgment, ask_final.start_doc(start)[0], answer)
        self.assertEqual(notes, [])
        got = final_got(**ask_final.ledger_rows(b))
        final = ask_final.final_text(got, ask_final.final_needs(got), "run-1")
        returns = fixed_run(judge={**fixed_run()["judge"], "judgment": str(self.artifacts / "judge/judgment.json"),
                                   "units": [{"id": u["key"], "label": u["label"]} for u in units]})
        head, _ = runreport._decisions(returns, {"before-fix-answer": answer} if answer else {}, {"answers": []}, "fixed", [], closed=True,
                                       beside=runreport.fix_beside(returns), exit_=runreport.rejudge_exit(returns))
        return final, "\n".join(head)

    def test_branch_rows_in_final_text_and_head(self):
        """差分の審査の穴と目の行の枝の名札（元 report.branch_rows。線の木の段 4a）は最後の関所の文に出る。写した字の差: 元は
        report.branch_rows を差し替えて最後の関所の文と報告の冒頭の両方を照らした。修正の返りに穴の名札の控えが無い（S29。部分 D2）
        ので、最後の関所の文の材料 branch_rows に行を置いて照らし、報告の冒頭の側は照らさない"""
        rows = ["差分の審査の穴の枝: 見本の 1 行", "  - k: 項目 1"]
        got = final_got(branch_rows=rows, delta_review={"rounds": 1, "pass": True})
        text = ask_final.final_text(got, [], "run-1")
        self.assertIn("差分の審査の穴の枝: 見本の 1 行", text)
        self.assertIn("  - k: 項目 1", text)

    def test_held_questions_are_listed_not_none(self):
        """最後の関所の文と報告の冒頭: 台帳の保留（fork でない awaiting も）を並べ、『盤面の問い: 無い』と書かない"""
        awaiting = {"key": "q-awaiting-pr", "kind": "awaiting", "status": "held", "origin": "parallel_pr", "reason": "人が確かめる"}
        for name, text in zip(("最後の関所", "報告の冒頭"), self.gate(questions=[FORK, awaiting])):
            with self.subTest(name):
                self.assertNotIn("共有ボードの問い: 無い", text)
                self.assertIn(FORK["key"], text)
                self.assertIn(awaiting["key"], text)
        final, head = self.gate()
        self.assertIn("共有ボードの問い: 無い", final)
        self.assertNotIn(gatemarks.ASK_HEAD, head)

    def test_answered_question_is_not_counted_as_held(self):
        """関所で continue を受けた問いは、報告の冒頭と最後の関所の文の「保留にしたままの問い」の件数に数えない（行は答えた問いとして
        並べたまま）。関所に載らない台帳の問いは今どおり数える。写した字の差: 元の報告の冒頭 report.head3 の「保留にしたままの問い
        1 件」は、runreport._decisions の「保留にしたままの問い: 1 件」"""
        awaiting = {"key": "q-awaiting-pr", "kind": "awaiting", "status": "held", "origin": "parallel_pr", "reason": "人が確かめる"}
        passed = {"decision": "continue", "text": "例外で", "asked": [gatemarks.ask_text(FORK)]}
        final, head = self.gate(questions=[FORK], answer=passed)
        self.assertNotIn("保留にしたままの問い", head)
        self.assertNotIn("保留にしたままの問い", final)
        self.assertIn(gatemarks.GATE_CONTINUED.lstrip("・"), final)
        final, head = self.gate(questions=[FORK, awaiting], answer=passed)
        self.assertIn("保留にしたままの問い: 1 件", head)
        self.assertIn("保留にしたままの問い（問いの台帳・1 件", final)


if __name__ == "__main__":
    unittest.main()

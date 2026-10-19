"""line の筋書き（blocks/line/fixtures/）のうち、承認ノード・計画の往復・案の直し・再審・無人の run・修正の後の並行 PR・守りのパスの 21 本を dry-run の trace で照らす
（docs/design/line.md の 11 節。元は tests/e2e/test_line_scenarios.py の LineReturnsTest・UnattendedGateTest・HeldPushTest・
ProtectedNotAppliedTest・RefixHandoffTest）。

筋書きの宣言（`reached`）は節が走らなかったことを照らせない（止めた Archon の packages/workflows/src/fixture-runner.ts の
fixtureDeclarationSchema）ので、走らなかったことと節の出力は、筋書きの stub と入力をそのまま `workflow run --dry-run --exec-code` に
渡した trace で照らす。dry-run は置き場にファイルを書けず、include の入力を名前の script に渡さない（docs/design/README.md の 13 章）ので、
ファイルを置いて走らせ直す照らしと報告の文の照らしは、line の script の試験（test_gates.py・test_collect.py）に在る。
Archon の源か bun が無ければ tests/archon.py の見送り。
"""
import json
import re
import unittest

import yaml

from tests.blocks import kit

NAMES = (
    "eyes-failed", "final-stop", "final-when-needed-green", "policy-continue", "policy-stop", "refix-handoff", "rejudge",
    "rejudge-stop", "replan", "replan-answers", "replan-stop", "unattended-held-no-push", "unattended-held-push",
    "unattended-needs-human", "unattended-policy-change", "unattended-push", "unattended-push-stop", "unattended-questions",
    "parallel-pr-after-found", "seal-protected", "seal-protected-unattended",
)


def included(block: str = "line") -> list[str]:
    """block が include する block の名（入れ子の中も）。木に一緒に置く"""
    return sorted(_closure(block) - {block})


def _closure(block: str) -> set[str]:
    seen, todo = set(), [block]
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        text = (kit.BLOCKS / name / f"works-factory-{name}.yaml").read_text(encoding="utf-8")
        todo += re.findall(r"^\s*include: works-factory-([\w-]+)\s*$", text, re.M)
    return seen


def ran(trace: dict, node: str) -> bool:
    return node in trace and trace[node]["state"] in ("completed", "stubbed")


def out(trace: dict, node: str):
    return json.loads(trace[node]["output"])


def traces(names) -> dict:
    return kit.dry_run_traces("line", names, included())


class DeclaredCase(unittest.TestCase):
    """18 本が揃い、宣言した `reached` の節が全部走る"""

    @classmethod
    def setUpClass(cls):
        cls.traces = traces(NAMES)

    def test_every_scenario_file_exists(self):
        for name in NAMES:
            with self.subTest(name=name):
                self.assertTrue((kit.BLOCKS / "line" / "fixtures" / f"{name}.stubs.yaml").is_file())

    def test_declared_nodes_ran(self):
        for name in NAMES:
            reached = kit.fixture("line", name)["fixture"]["reached"]
            with self.subTest(name=name):
                self.assertEqual([n for n in reached if not ran(self.traces[name], n)], [])


class GateCase(unittest.TestCase):
    """承認ノードの開き方と答えの受け方（policy-*・final-*・replan-*）"""

    @classmethod
    def setUpClass(cls):
        cls.t = traces(("policy-continue", "policy-stop", "final-stop", "final-when-needed-green", "replan-stop", "replan-answers"))

    def test_policy_continue_opens_before_fix_and_goes_on_to_fix(self):
        trace = self.t["policy-continue"]
        self.assertTrue(ran(trace, "gate-before-fix"))
        self.assertIs(out(trace, "ask-before-fix")["open"], True)
        self.assertTrue(ran(trace, "fix__finish"))

    def test_policy_stop_never_reaches_fix_or_the_seal(self):
        trace = self.t["policy-stop"]
        self.assertTrue(ran(trace, "gate-before-fix"))
        self.assertEqual(out(trace, "answer-before-fix")["go"], False)
        for node in ("fix__finish", "test-gate-final__result", "eyes__verdict", "merge-seal__merge", "merge-apply__merge"):
            self.assertFalse(ran(trace, node), node)
        self.assertTrue(ran(trace, "report__finish"))

    def test_final_stop_keeps_the_seal_without_applying(self):
        trace = self.t["final-stop"]
        self.assertEqual(out(trace, "answer-final")["go"], False)
        for node in ("merge-apply__place", "merge-apply__merge"):
            self.assertFalse(ran(trace, node), node)
        got = out(trace, "result")
        self.assertIsNone(got["apply"], got)
        self.assertIs(got["sealed"]["ok"], True)
        self.assertEqual(got["final_answer"]["decision"], "stop")

    def test_when_needed_run_reaches_the_apply(self):
        """開き方 when_needed でも、dry-run は修正の段の控えを置けず、読めない控えは開ける理由なので承認ノードは開く。通せば差分を当てる"""
        trace = self.t["final-when-needed-green"]
        got = out(trace, "ask-final")
        self.assertIn("修正の段の控えを読めない", got["text"].splitlines()[0])
        self.assertEqual(out(trace, "answer-final")["go"], True)
        self.assertTrue(ran(trace, "merge-apply__merge"))

    def test_replan_stop_never_runs_the_second_fix(self):
        trace = self.t["replan-stop"]
        self.assertEqual(out(trace, "answer-replan")["go"], False)
        for node in ("refix-run__finish", "lens-2__finish", "test-gate-final__result", "eyes__verdict", "merge-seal__merge", "merge-apply__merge"):
            self.assertFalse(ran(trace, node), node)
        self.assertTrue(ran(trace, "raise"))
        self.assertTrue(ran(trace, "report__finish"))

    def test_replan_answers_carry_the_before_fix_condition_to_the_second_fix(self):
        """answer-replan の script が修正前の条件（answer-before-fix の stub）を本当に組み、2 度目の修正の answers に先に置く"""
        trace = self.t["replan-answers"]
        self.assertTrue(ran(trace, "gate-before-fix"))
        self.assertTrue(ran(trace, "gate-replan"))
        self.assertIn("範囲は stats.py だけ", json.dumps(out(trace, "answer-replan"), ensure_ascii=False))
        self.assertTrue(ran(trace, "refix-run__finish"))


class ReplanCase(unittest.TestCase):
    """案の直しと 2 度目の修正の段は 1 度だけ。段ごとの差分の審査（lens・delta-review）も 2 度目の段で 1 度ずつ"""

    @classmethod
    def setUpClass(cls):
        cls.t = traces(("replan", "refix-handoff"))

    def test_replan_runs_each_once_stage_once(self):
        trace = self.t["replan"]
        for node in ("replan__finish", "replan-review__finish", "ask-replan", "gate-replan", "answer-replan", "refix-run__finish",
                     "lens-2__finish", "delta-review-2__finish"):
            self.assertTrue(ran(trace, node), node)

    def test_refix_handoff_opens_the_final_gate_with_both_stage_rows(self):
        trace = self.t["refix-handoff"]
        got = out(trace, "ask-final")
        self.assertTrue(got["open"], got)
        self.assertEqual(len(out(trace, "fixed")["stages"]), 2, "1 回目と 2 度目の修正の段")
        self.assertIn("修正役が人に回した物が在る（2 件）", got["text"].splitlines()[0])
        self.assertIn("- u1: 壊すと分かって通した——段 1 で既定が変わる\n- u1: 壊すと分かって通した——段 2 で既定が変わる", got["text"])


class ParallelAfterCase(unittest.TestCase):
    """line.md の 8 節の 1: 修正の後の並行 PR の確かめ直しが found を返したら、最後の承認ノードの開ける理由に入り、冒頭の 1 行目に出る。
run は止まらず、答えの approve で差分を当てる"""

    @classmethod
    def setUpClass(cls):
        cls.trace = traces(("parallel-pr-after-found",))["parallel-pr-after-found"]

    def test_found_opens_the_final_gate_without_being_a_must(self):
        self.assertTrue(ran(self.trace, "parallel-pr-after__finish"))
        got = out(self.trace, "ask-final")
        self.assertTrue(got["open"], got)
        self.assertIn("直したファイルが開いている PR と重なる（1 件）", got["text"].splitlines()[0])
        self.assertTrue(ran(self.trace, "gate-final"))
        self.assertTrue(ran(self.trace, "merge-apply__merge"))


class SealProtectedCase(unittest.TestCase):
    """keep-essence 10: 封じる段が守りのパスの当たりを返したら、最後の承認ノードは開き方に依らず開き、無人の run は開かずに止まる"""

    @classmethod
    def setUpClass(cls):
        cls.t = traces(("seal-protected", "seal-protected-unattended"))

    def test_hit_opens_the_final_gate_even_when_needed_only(self):
        trace = self.t["seal-protected"]
        got = out(trace, "ask-final")
        self.assertTrue(got["open"], got)
        self.assertIn("守りのパス", got["text"].splitlines()[0])
        self.assertIn("tests/test_stats.py", got["text"])
        self.assertTrue(ran(trace, "gate-final"))

    def test_hit_stops_an_unattended_run_without_applying(self):
        trace = self.t["seal-protected-unattended"]
        got = out(trace, "ask-final")
        self.assertEqual((got["open"], got["go"], got["stop_reason"]), (False, False, "works:needs-human"), got)
        self.assertFalse(ran(trace, "gate-final"))
        self.assertFalse(ran(trace, "merge-apply__merge"))
        self.assertIsNone(out(trace, "result")["apply"])


class RejudgeCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = traces(("rejudge", "rejudge-stop"))

    def test_rejudge_reaches_judged_and_the_eyes(self):
        trace = self.t["rejudge"]
        self.assertTrue(ran(trace, "rejudge-run__finish"))
        self.assertIs(out(trace, "judged")["rejudged"], True)
        self.assertTrue(ran(trace, "eyes__verdict"))

    def test_rejudge_stop_never_seals(self):
        """L-D48: 再審が止まった run は試験の関門から先へ進まず、封じも当てもしない"""
        trace = self.t["rejudge-stop"]
        self.assertEqual(out(trace, "judged")["stop_reason"], "works:rejudge")
        for node in ("test-gate-final__result", "eyes__verdict", "merge-seal__merge", "merge-apply__merge"):
            self.assertFalse(ran(trace, node), node)
        got = out(trace, "result")
        self.assertEqual((got["apply"], got["sealed"], got["r2_status"], got["final_answer"]), (None, None, None, None), got)


class UnattendedCase(unittest.TestCase):
    """無人の run の修正前の承認ノード（L-G38・L-G40・#552・#593）: 台帳の問いだけなら開かず修正へ進み、方針の文書の変化が在れば修正へ
    進まずに止まる。推しが通すなら推しを採って進み、止めるなら止まる"""

    @classmethod
    def setUpClass(cls):
        cls.t = traces(("unattended-questions", "unattended-policy-change", "unattended-push", "unattended-push-stop",
                        "unattended-needs-human", "unattended-held-push", "unattended-held-no-push", "eyes-failed"))

    def test_questions_only_go_to_fix_without_the_gate(self):
        trace = self.t["unattended-questions"]
        asked = out(trace, "ask-before-fix")
        self.assertEqual((asked["open"], asked["go"], asked["stop_reason"], len(asked["deferred"])), (False, True, "", 1), asked)
        self.assertFalse(ran(trace, "gate-before-fix"))
        self.assertTrue(ran(trace, "fix__finish"))

    def test_policy_change_stops_before_fix(self):
        trace = self.t["unattended-policy-change"]
        asked = out(trace, "ask-before-fix")
        self.assertEqual((asked["open"], asked["go"], asked["stop_reason"]), (False, False, "works:needs-human"), asked)
        self.assertFalse(ran(trace, "gate-before-fix"))
        self.assertFalse(ran(trace, "fix__finish"))
        self.assertTrue(ran(trace, "report__finish"))

    def test_continue_push_goes_to_fix(self):
        """#552: 項目の全部が通す推しを持つ無人の run は、承認ノードを開かずに推しを採って修正へ進み、答えが欄 pushed を持つ"""
        trace = self.t["unattended-push"]
        asked = out(trace, "ask-before-fix")
        self.assertEqual((asked["open"], asked["go"], asked["stop_reason"]), (False, True, ""), asked)
        self.assertEqual(asked["pushed"]["decision"], "continue", asked)
        self.assertFalse(ran(trace, "gate-before-fix"))
        self.assertTrue(ran(trace, "fix__finish"))
        self.assertEqual(out(trace, "answer-before-fix")["answer"]["pushed"], asked["pushed"]["pushed"])

    def test_stop_push_stops_before_fix(self):
        """#552: 推しが止める無人の run は、推しで進まずに今どおり止まって報告へ進む"""
        trace = self.t["unattended-push-stop"]
        asked = out(trace, "ask-before-fix")
        self.assertEqual((asked["open"], asked["go"], asked["stop_reason"], asked["pushed"]), (False, False, "works:needs-human", None), asked)
        self.assertFalse(ran(trace, "fix__finish"))
        self.assertTrue(ran(trace, "report__finish"))

    def test_final_gate_of_an_unattended_run_stops_instead_of_opening(self):
        """L-G39・L-W25: 開くはずの時は開かずに works:needs-human で止め、merge の apply を飛ばす"""
        for name in ("unattended-needs-human", "unattended-held-push", "unattended-questions"):
            with self.subTest(name=name):
                trace = self.t[name]
                got = out(trace, "ask-final")
                self.assertEqual((got["open"], got["go"], got["stop_reason"]), (False, False, "works:needs-human"), got)
                self.assertFalse(ran(trace, "gate-final"))
                self.assertFalse(ran(trace, "merge-apply__merge"))
                self.assertTrue(ran(trace, "report__finish"))

    def test_held_question_with_a_push_goes_to_fix(self):
        """#593: 推しつきの保留の問いは答えに採られ、plan は u1 を直す義務に数えるので、修正前の承認ノードを開かずに修正へ進む"""
        trace = self.t["unattended-held-push"]
        self.assertFalse(ran(trace, "gate-before-fix"))
        self.assertTrue(ran(trace, "fix__finish"))
        self.assertFalse(out(trace, "fix-in")["no_fix"])

    def test_held_question_without_a_push_closes_the_round_without_fixing(self):
        """#593: 推しの無い保留の問いは答えに採らず、plan の直す義務は 0 件。修正は飛び、直す物が無い周として独立設計・最後のテスト・
        独立の目で周を締める（封じも当てもしない）"""
        trace = self.t["unattended-held-no-push"]
        self.assertEqual(out(trace, "plan__finish")["status"], "nothing_owed")
        self.assertTrue(out(trace, "fix-in")["no_fix"])
        self.assertFalse(ran(trace, "fix__finish"))
        for node in ("independent-design__finish", "test-gate-final__result", "eyes__verdict"):
            self.assertTrue(ran(trace, node), node)
        for node in ("merge-seal__merge", "merge-apply__merge"):
            self.assertFalse(ran(trace, node), node)

    def test_eyes_failure_never_applies(self):
        """L-G50: 独立の目の graph が落ちた run は、封じる段から先が飛んだまま差分を当てない。報告と線の返りは出る"""
        trace = self.t["eyes-failed"]
        self.assertEqual(trace["eyes__verdict"]["state"], "failed")
        for node in ("merge-seal__merge", "ask-final", "gate-final", "answer-final", "merge-apply__merge"):
            self.assertFalse(ran(trace, node), node)
        self.assertTrue(ran(trace, "report__finish"))
        self.assertIsNone(out(trace, "result")["apply"])


if __name__ == "__main__":
    unittest.main()

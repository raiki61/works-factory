"""line の筋書き（workflows/line/fixtures/）のうち、承認ノード・案の直し・無人の run・守りのパスの結末を dry-run の trace で照らす
（docs/design/line.md の 11 節。元は test_line_scenarios.py の UnattendedGateTest・ProtectedNotAppliedTest・RefixHandoffTest）。
結末ごとに 1 本を残し、開くか・進むかの決めの組み合わせは line の script の単体の試験（test_gates.py・test_judged.py）が見る。

筋書きが通るか（宣言の `reached` など）は層の試験 tests/layers/test_block_shape.py の ArchonCase が workflow test で照らす。宣言は節が走らなかったことを照らせない（止めた Archon の packages/workflows/src/fixture-runner.ts の
fixtureDeclarationSchema）ので、走らなかったことと節の出力は、筋書きの stub と入力をそのまま `workflow run --dry-run --exec-code` に
渡した trace で照らす。dry-run は置き場にファイルを書けず、include の入力を名前の script に渡さない（docs/design/README.md の 13 章）ので、
ファイルを置いて走らせ直す照らしと報告の文の照らしは、line の script の試験（test_gates.py・test_collect.py）に在る。
Archon の源か bun が無ければ tests/archon.py の見送り。
"""
import unittest

from tests.blocks.line.test_scenarios import line_traces, out, ran

class GateCase(unittest.TestCase):
    """承認ノードの止めの答え（policy-stop・final-stop）。通す答えで修正へ進み差分を当てる結末は筋書き standard（test_scenarios.py の
    LineReturnsTest）が見る"""

    @classmethod
    def setUpClass(cls):
        cls.t = line_traces(("policy-stop", "final-stop"))

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



class ReplanCase(unittest.TestCase):
    """案の直し（refix-handoff）: 2 つの修正の段で人へ回した物が、どちらも最後の承認ノードに出る"""

    @classmethod
    def setUpClass(cls):
        cls.t = line_traces(("refix-handoff",))

    def test_refix_handoff_opens_the_final_gate_with_both_stage_rows(self):
        trace = self.t["refix-handoff"]
        got = out(trace, "ask-final")
        self.assertTrue(got["open"], got)
        self.assertEqual(len(out(trace, "fixed")["stages"]), 2, "1 回目と 2 度目の修正の段")
        self.assertIn("直しの途中で AI が自分で決めずに人に回した物が在る（2 件）", got["text"].splitlines()[0])
        self.assertIn("- u1: 壊すと分かって通した——段 1 で既定が変わる\n- u1: 壊すと分かって通した——段 2 で既定が変わる", got["text"])

    def test_refix_handoff_titles_of_both_stages_reach_the_merged_fix(self):
        """facts は artifact の指す先で dry-run の後に読めないので、2 つの段の題が合わせた修正の返りに届くことまでを見る"""
        titles = out(self.t["refix-handoff"], "fixed")["handoff_titles"]
        self.assertEqual(sorted(titles.values()), ["1 回目の直しで既定の値が変わってよいか", "2 度目の直しで既定の値が変わってよいか"])


class SealProtectedCase(unittest.TestCase):
    """keep-essence 10: 封じる段が守りのパスの当たりを返したら、最後の承認ノードは開き方に依らず開き、無人の run は開かずに止まる"""

    @classmethod
    def setUpClass(cls):
        cls.t = line_traces(("seal-protected", "seal-protected-unattended"))

    def test_hit_opens_the_final_gate_even_when_needed_only(self):
        trace = self.t["seal-protected"]
        got = out(trace, "ask-final")
        self.assertTrue(got["open"], got)
        self.assertIn("守りのパス", got["text"].splitlines()[0])
        self.assertIn("test/test_stats.py", got["text"])
        self.assertTrue(ran(trace, "gate-final"))

    def test_hit_stops_an_unattended_run_without_applying(self):
        trace = self.t["seal-protected-unattended"]
        got = out(trace, "ask-final")
        self.assertEqual((got["open"], got["go"], got["stop_reason"]), (False, False, "works:needs-human"), got)
        self.assertFalse(ran(trace, "gate-final"))
        self.assertFalse(ran(trace, "merge-apply__merge"))
        self.assertIsNone(out(trace, "result")["apply"])


class UnattendedCase(unittest.TestCase):
    """無人の run（L-G39・#552）: 修正前の承認ノードは推しが通すなら推しを採って進み、止めるなら止まる。最後の承認ノードは開かずに止める。
    独立の目が落ちた run は当てない。台帳の問い・方針の変化・保留の問いで開くか進むかの決めは tests/blocks/line/test_gates.py の
    AskBeforeFixCase・LedgerAsksCase が見る"""

    @classmethod
    def setUpClass(cls):
        cls.t = line_traces(("unattended-push", "unattended-push-stop", "unattended-needs-human", "eyes-failed"))

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
        trace = self.t["unattended-needs-human"]
        got = out(trace, "ask-final")
        self.assertEqual((got["open"], got["go"], got["stop_reason"]), (False, False, "works:needs-human"), got)
        self.assertFalse(ran(trace, "gate-final"))
        self.assertFalse(ran(trace, "merge-apply__merge"))
        self.assertTrue(ran(trace, "report__finish"))

    def test_eyes_failure_never_applies(self):
        """L-G50: 独立の目の graph が落ちた run は、封じる段から先が飛んだまま差分を当てない。報告と線の返りは出る"""
        trace = self.t["eyes-failed"]
        self.assertEqual(trace["eyes__verdict"]["state"], "failed")
        for node in ("merge-seal__merge", "ask-final", "gate-final", "answer-final", "merge-apply__merge"):
            self.assertFalse(ran(trace, node), node)
        self.assertTrue(ran(trace, "report__finish"))
        self.assertIsNone(out(trace, "result")["apply"])


class NoApplyCase(unittest.TestCase):
    """止まった・落ちた・直す物が無い run（policy-stop・final-stop・eyes-failed・seal-protected-unattended・unattended-push-stop・unattended-needs-human）は差分を当てない。修正の前で止まる run は封じもしない。
    when: の句の取り違え（止まった run で後ろの書き込みの段が走る）を、当てない結末の筋書きの全部で照らす（消した YAML の形の試験
    WhenCase・FlowCase の代わり。持ち主の決め mechanism-over-tests）"""

    NEVER_APPLY = ("policy-stop", "final-stop", "eyes-failed", "seal-protected-unattended", "unattended-push-stop", "unattended-needs-human")
    NEVER_SEAL = ("policy-stop", "eyes-failed", "unattended-push-stop")

    def test_no_write_after_a_stop(self):
        traces = line_traces(self.NEVER_APPLY)
        for name in self.NEVER_APPLY:
            with self.subTest(scenario=name):
                trace = traces[name]
                for node in ("merge-apply__place", "merge-apply__merge", "merge-apply__pr-commit", "merge-apply__pr-open"):
                    self.assertFalse(ran(trace, node), node)
                self.assertIsNone(out(trace, "result")["apply"])
                if name in self.NEVER_SEAL:
                    self.assertFalse(ran(trace, "merge-seal__merge"))
                    self.assertIsNone(out(trace, "result")["sealed"])


if __name__ == "__main__":
    unittest.main()

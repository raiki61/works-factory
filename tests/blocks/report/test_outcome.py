"""結末の決め（blocks/report/src/outcome.py。docs/design/report.md の 1.7 の 11 の順）を、facts と run の組で 1 つずつ照らす。
写す元は lib/tests/test_outcome.py の TableCase・LineStopCase・OrderCase。返りの欄を組む見本は facts の欄の見本に替えた。"""
import unittest

from tests.blocks.report import base

M = base.src()
REQUEST_GATE = {"at": "final-answer", "decision": "stop", "text": "request: 止め札"}
HUMAN_GATE = {"at": "start-answer", "decision": "reject", "text": "やめる"}
RUN = {"ok": True, "failed": [], "absorbed": []}


def decide(run=RUN, **facts):
    return M.outcome.decide(M.facts_in.read({**base.READY, **facts}), run)


class TableCase(unittest.TestCase):
    def test_nothing_given_is_record_invalid(self):
        self.assertEqual(M.outcome.decide(M.facts_in.read({}), RUN), ("record_invalid", "start:record-invalid"))

    def test_problems_are_record_invalid(self):
        self.assertEqual(decide(problems=["入力 sections: 空"]), ("record_invalid", "report:record-invalid"))

    def test_proved_and_nothing_left_is_fixed(self):
        self.assertEqual(decide(), ("fixed", ""))

    def test_not_proved_is_round_limit(self):
        self.assertEqual(decide(proved=False), ("round_limit", ""))

    def test_left_rows_are_round_limit(self):
        self.assertEqual(decide(left=[{"where": "最後のテスト", "text": "緑でない"}]), ("round_limit", ""))

    def test_unmeasured_rows_only_with_proof_need_a_check(self):
        rows = [{"where": "素材 a", "text": "測れていない", "unmeasured": True}]
        self.assertEqual(decide(left=rows), ("fixed_needs_check", ""))
        self.assertEqual(decide(left=[*rows, {"where": "修正 u1", "text": "残り"}]), ("round_limit", ""))
        self.assertEqual(decide(left=rows, proved=False), ("round_limit", ""))

    def test_no_fix_is_no_fix_needed_unless_something_is_left(self):
        self.assertEqual(decide(no_fix=True, proved=False), ("no_fix_needed", ""))
        self.assertEqual(decide(no_fix=True, left=[{"where": "w", "text": "t"}]), ("round_limit", ""))

    def test_absorbed_fall_is_left_unless_its_include_returned(self):
        run = {"ok": True, "failed": [], "absorbed": [{"node": "eyes__r1", "error": "boom"}]}
        self.assertEqual(decide(run), ("round_limit", ""))
        self.assertEqual(decide(run, returned=["eyes"]), ("fixed", ""))
        rows = M.outcome.left_all(M.facts_in.read(base.READY), run)
        self.assertEqual(rows[0]["where"], "受け止めた落ち eyes__r1")
        self.assertIn("eyes__r1 が落ちた（誤り: boom）", rows[0]["text"])

    def test_cut_is_interrupted(self):
        self.assertEqual(decide(cut={"at": "plan", "word": "chain-cut"}), ("interrupted", "plan:chain-cut"))
        run = {"ok": True, "failed": ["fix__tdd"], "absorbed": []}
        self.assertEqual(decide(run, cut={"at": "plan", "word": "chain-cut"}), ("interrupted", "fix__tdd:node-error"), "落ちたノードが先")


class StopCase(unittest.TestCase):
    def test_gate_stop_is_human_or_request(self):
        self.assertEqual(decide(gates=[REQUEST_GATE]), ("stopped_by_request", "final-answer:stop"))
        self.assertEqual(decide(gates=[HUMAN_GATE]), ("stopped_by_human", "start-answer:reject"))
        self.assertEqual(decide(gates=[{"at": "start-answer", "decision": "continue", "text": "進める"}, {"at": "x", "decision": None, "text": ""}]),
                         ("fixed", ""))

    def test_stop_words_by_head(self):
        self.assertEqual(decide(stops=[{"at": "judge", "word": "request:止め"}]), ("stopped_by_request", "judge:request:止め"))
        self.assertEqual(decide(stops=[{"at": "judge", "word": "human:止め"}]), ("stopped_by_human", "judge:human:止め"))

    def test_line_word_is_stopped_by_line_but_waiting_words_are_not(self):
        self.assertEqual(decide(stops=[{"at": "plan", "word": "works:adapter"}]), ("stopped_by_line", "plan:works:adapter"))
        self.assertEqual(decide(stops=[{"at": "fix", "word": "works:conflict"}]), ("needs_human", "fix:works:conflict"))
        self.assertEqual(decide(halts=[{"at": "plan-review", "word": "works:plan-converge"}]), ("stopped_by_line", "plan-review:works:plan-converge"))

    def test_waits_in_order(self):
        waits = {"conflicts": [{"at": "fix", "word": "works:conflict"}], "conflicts_if_closed": [{"at": "fix", "word": "works:replan"}],
                 "others": [{"at": "eyes", "word": "r4-ask"}]}
        self.assertEqual(decide(waits=waits), ("needs_human", "fix:works:conflict"))
        self.assertEqual(decide(waits={**waits, "conflicts": []}), ("needs_human", "fix:works:replan"))
        self.assertEqual(decide(waits={**waits, "conflicts": []}, cut={"at": "plan", "word": "chain-cut"}), ("needs_human", "eyes:r4-ask"),
                         "途中で終わった run は案の直しを待つ行を人待ちに数えない")
        self.assertEqual(decide(waits={**waits, "conflicts": [], "others": []}, cut={"at": "plan", "word": "chain-cut"}),
                         ("interrupted", "plan:chain-cut"))


class OrderCase(unittest.TestCase):
    def test_human_stop_beats_line_stop_beats_wait_beats_invalid_beats_cut(self):
        line = [{"at": "plan", "word": "works:adapter"}]
        wait = {"conflicts": [{"at": "fix", "word": "works:conflict"}]}
        cut = {"at": "plan", "word": "chain-cut"}
        self.assertEqual(decide(gates=[HUMAN_GATE], stops=line, waits=wait, cut=cut)[0], "stopped_by_human")
        self.assertEqual(decide(stops=line, waits=wait, cut=cut)[0], "stopped_by_line")
        self.assertEqual(decide(waits=wait, cut=cut)[0], "needs_human")
        self.assertEqual(decide(start_ok=False, cut=cut)[0], "record_invalid")
        self.assertEqual(decide(cut=cut)[0], "interrupted")


class AsksCase(unittest.TestCase):
    ROWS = [{"where": "素材 a", "text": "測れていない", "unmeasured": True}, {"where": "修正 u1", "text": "残り\nあり"}]

    def asks(self, outcome, **facts):
        got = M.facts_in.read({**base.READY, **facts})
        return M.outcome.outcome_asks(outcome, got, M.outcome.left_all(got, RUN))

    def test_each_outcome_names_its_own_kind(self):
        self.assertEqual(self.asks("fixed_needs_check", left=self.ROWS[:1]), [("人が確かめる物", "素材 a: 測れていない")])
        self.assertEqual(self.asks("round_limit", left=self.ROWS), [("直しきれずに残った物", "素材 a: 測れていない"),
                                                                 ("直しきれずに残った物", "修正 u1: 残り あり")])
        self.assertEqual(self.asks("record_invalid"), [("記録が通らないこと", "record_invalid")])
        self.assertEqual(self.asks("fixed"), [])

    def test_counted_units_are_not_repeated_in_round_limit(self):
        self.assertEqual(self.asks("round_limit", left=self.ROWS, counted_left=["修正 u1"]), [("直しきれずに残った物", "素材 a: 測れていない")])


class FactsInCase(unittest.TestCase):
    def test_defaults_fill_and_nested_defaults_merge(self):
        got = M.facts_in.read({"head": {"before": ["a"]}, "apply": {"sealed": True}})
        self.assertEqual(got["head"], {"before": ["a"], "stopped": [], "after": [], "notices": []})
        self.assertEqual((got["apply"]["sealed"], got["apply"]["commits"], got["start_ok"], got["cut"]), (True, [], False, None))

    def test_wrong_shapes_name_the_field(self):
        for bad in ({"gates": "x"}, {"tallied": {"a": "x"}}, {"nope": 1}, {"left": [{"where": "w"}]}, {"start_ok": "yes"}):
            with self.subTest(bad), self.assertRaises(ValueError):
                M.facts_in.read(bad)
        with self.assertRaises(ValueError) as caught:
            M.facts_in.read({"gates": "x"})
        self.assertIn("gates", str(caught.exception))

    def test_defaults_are_not_shared_between_calls(self):
        M.facts_in.read({})["notes"].append("x")
        self.assertEqual(M.facts_in.read({})["notes"], [])


if __name__ == "__main__":
    unittest.main()

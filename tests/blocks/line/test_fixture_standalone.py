"""line の standalone の筋書きを dry-run で回し、道の node の状態と result の返りを見る（docs/design/line.md の 11 節）。

include した block が blocks/ に要る（組み込みの前は別の枝に在る block が無いので赤。Archon の源か bun が無ければ見送り）。
36 本の今の筋書きの書き直しは別の試験（test_scenarios.py・test_scenarios_gates.py）が持つ。
"""
import json
import unittest

from tests.blocks import kit

BLOCK = "line"
INCLUDED = ("test-gate", "judge", "head-depth", "spec", "parallel-pr", "premises", "purpose", "world", "prior-decisions",
            "purpose-review", "local-review", "consistency-bypass", "hygiene", "external-standards", "procedure-trace",
            "test-double-fidelity", "main-path-observation", "provenance", "diagnose", "verify", "structure", "independent-design", "plan",
            "plan-review", "fix", "lens", "delta-review", "eyes", "r1", "r2", "r3", "r4", "merge", "report")


class StandaloneCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trace = kit.dry_run_traces(BLOCK, ("standalone",), INCLUDED)["standalone"]

    def state(self, node):
        return self.trace.get(node, {}).get("state", "absent")

    def test_the_no_fix_round_reaches_the_report(self):
        """判定が直す単位を出さない周: 修正の段は fix を起こさずに直す物の無い形を返し、最後のテストと独立の目と最後の承認ノードを通って
        報告と result まで届く。封じと置きは直す物が無いので飛ぶ"""
        for node in ("start", "answer-start", "tiers", "design-in", "fix-in", "fixed", "judged", "eyes-in", "ask-final", "answer-final",
                     "collect", "report__finish", "sweep-children", "result"):
            self.assertEqual(self.state(node), "completed", node)
        for node in ("fix__intake", "plan-rounds", "merge-seal__place", "merge-apply__place", "rejudge-run__intake"):
            self.assertIn(self.state(node), ("skipped", "absent"), node)
        fixed = json.loads(self.trace["fixed"]["output"])
        self.assertEqual((fixed["no_fix"], fixed["go"], fixed["eyes_due"]), (True, True, True))

    def test_result_carries_the_report(self):
        out = json.loads(self.trace["result"]["output"])
        self.assertIs(out["fixed"], False)
        self.assertIsNotNone(out["report"])
        self.assertIsNone(out["apply"])


if __name__ == "__main__":
    unittest.main()

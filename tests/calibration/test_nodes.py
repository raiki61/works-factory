"""ノードごとの表 tests/calibration/nodes.py の試験。fixtures/ の切った試み（test_reviewbench.py の docstring）から変換の控えを作り、
表を組む。fixtures/works-factory の出来事は、時刻の取れないノードの形として judge__intake の timing を外し、子の run の出来事の形として
親の fix__tdd-unit の値を子の tdd-unit に置いた（#214 の run は子の出来事を写していなかった）。判定役の結果は控えの指摘から組む stub。
"""
import json
import unittest

from tests.bin import hermetic
from tests.calibration import nodes, reviewbench
from tests.calibration import run as runner
from tests.calibration.test_reviewbench import ENDED, TASK, attempt_from

KEY = reviewbench.key(TASK)


class NodesCase(unittest.TestCase):
    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.out = self.tmp / "out"
        attempt, head = attempt_from(self.tmp, "works-factory")
        doc, record = reviewbench.convert(runner.WorksFactory, TASK, attempt, "run-1", TASK["base"], head, ENDED)
        reviewbench.write(self.out, "works-factory", KEY, doc, record)
        self.findings = doc["findings"]

    def judged(self):
        details = self.out / "works-factory" / "scoring" / "results.details.json"
        details.parent.mkdir(parents=True)
        details.write_text(json.dumps([{"pr_key": KEY, "candidate_findings": [
            {**self.findings[0], "status": "matched_tp"}, {**self.findings[1], "status": "novel_fp"}]}]), encoding="utf-8")

    def rows(self, got) -> dict:
        return {r["node"]: r for r in got["nodes"]}

    def test_table_from_cut_attempt(self):
        self.judged()
        got = nodes.table(self.out, runner.WorksFactory())
        self.assertEqual((got["producer"], got["tasks"], got["judged"]), ("works-factory", 1, True))
        self.assertIn("おかげ", got["note"])
        rows = self.rows(got)
        diagnose = rows["judge__diagnose-loop.diagnose"]
        self.assertEqual((diagnose["seconds"], diagnose["usd"], diagnose["findings"]), (86.143, 0.584333, 1))
        self.assertEqual(diagnose["verdicts"], {"hit": 1, "real": 0, "wrong": 0, "unjudged": 0})
        self.assertEqual(diagnose["in_final_diff"], {"yes": 1, "no": 0, "unknown": 0})
        self.assertEqual((diagnose["subgraph"], diagnose["tasks"], diagnose["invocations"]), ("judge", 1, 1))
        self.assertEqual(rows["eyes__r4-scope"]["verdicts"]["wrong"], 1)
        start = rows["start"]
        self.assertEqual((start["usd"], start["usd_why"], start["subgraph"]), (None, "not_applicable", "line"))
        self.assertEqual(start["seconds"], 0.524)
        intake = rows["judge__intake"]
        self.assertEqual((intake["seconds"], intake["seconds_why"]), (None, "timing が無い"))
        self.assertEqual(rows["fix/tdd-unit"]["subgraph"], "fix")
        judge = {r["subgraph"]: r for r in got["subgraphs"]}["judge"]
        self.assertEqual((judge["invocations"], judge["findings"], judge["usd"]), (2, 1, 0.584333))
        self.assertEqual(judge["usd_why"], "一部の起動の費用が無い: not_applicable")
        md = nodes.markdown(got)
        self.assertIn("| ノード | サブグラフ | 課題 | 起動 | 秒 | USD | 所見 | 番地を解いた | 差分に入った | 当たり | 本物 | 誤り |", md)
        self.assertIn("- judge__intake: 秒 timing が無い", md)
        self.assertIn("- start: 費用 not_applicable", md)

    def test_resolved_references_are_counted(self):
        path = self.out / "works-factory" / "convert" / f"{KEY}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(sum(f["ref_as_written"] is not None for f in record["findings"]), 0)
        record["findings"][0]["ref_as_written"] = "stats.py:9-9"
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        got = nodes.table(self.out, runner.WorksFactory())
        rows = self.rows(got)
        self.assertEqual((rows["judge__diagnose-loop.diagnose"]["resolved"], rows["eyes__r4-scope"]["resolved"]), (1, 0))
        self.assertEqual({r["subgraph"]: r["resolved"] for r in got["subgraphs"]}["judge"], 1)
        self.assertIn("| judge__diagnose-loop.diagnose | judge | 1 | 1 | 86.143 | 0.584333 | 1 | 1 |", nodes.markdown(got))

    def test_without_details_everything_is_unjudged(self):
        got = nodes.table(self.out, runner.WorksFactory())
        self.assertFalse(got["judged"])
        self.assertEqual(sum(r["verdicts"]["unjudged"] for r in got["nodes"]), 2)
        self.assertEqual(sum(r["verdicts"]["hit"] + r["verdicts"]["real"] + r["verdicts"]["wrong"] for r in got["nodes"]), 0)

    def test_plain_claude_is_one_row_per_task(self):
        record = {"key": KEY, "attempt": str(self.tmp / "nowhere"), "seconds": 60.0, "usd": None,
                  "findings": [{"file": "a.py", "start_line": 1, "end_line": 1, "message": "m", "node": "claude",
                                "in_final_diff": None}]}
        reviewbench.write(self.out, "claude", KEY, {}, record)
        got = nodes.table(self.out, runner.PlainClaude())
        [row] = got["nodes"]
        self.assertEqual((row["node"], row["seconds"], row["usd"], row["findings"]), ("claude", 60.0, None, 1))
        self.assertEqual(row["usd_why"], "控えの seconds・usd が無い")
        self.assertEqual(row["in_final_diff"]["unknown"], 1)


if __name__ == "__main__":
    unittest.main()

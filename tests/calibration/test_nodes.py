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

    def judged(self, second="novel_fp"):
        details = self.out / "works-factory" / "scoring" / "results.details.json"
        details.parent.mkdir(parents=True, exist_ok=True)
        details.write_text(json.dumps([{"pr_key": KEY, "candidate_findings": [
            {**self.findings[0], "status": "matched_tp"}, {**self.findings[1], "status": second}]}]), encoding="utf-8")

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

    def test_tokens_per_node_and_subgraph(self):
        """fixtures の出来事の spend.tokens は Archon の本物の形: provider の値（diagnose）、cachePartial の値（r4-scope）、
        unavailable（start）、欄の無い形（intake）"""
        columns = ("input", "cacheRead", "cacheWrite", "uncached", "output")
        got = nodes.table(self.out, runner.WorksFactory())
        rows = self.rows(got)
        diagnose = rows["judge__diagnose-loop.diagnose"]
        self.assertEqual([diagnose[k] for k in columns], [1000, 700, 100, 200, 200], "input は cacheRead・cacheWrite を含むので足し直さない")
        self.assertIsNone(diagnose["tokens_why"])
        scope = rows["eyes__r4-scope"]
        self.assertEqual([scope[k] for k in columns], [400, 300, 50, None, 40], "cachePartial の値はキャッシュ外を出さない")
        self.assertEqual(scope["cacheUnknown"], 1)
        self.assertIn("キャッシュの内訳が不明な起動 1 件", scope["tokens_why"])
        start = rows["start"]
        self.assertEqual(([start[k] for k in columns], start["tokens_why"]), ([None] * 5, "not_applicable"))
        self.assertEqual(rows["judge__intake"]["tokens_why"], "spend.tokens が無い")
        judge = {r["subgraph"]: r for r in got["subgraphs"]}["judge"]
        self.assertEqual([judge[k] for k in columns], [1000, 700, 100, 200, 200])
        self.assertEqual(judge["tokens_why"], "一部の起動のトークンが無い: spend.tokens が無い")
        md = nodes.markdown(got)
        self.assertIn("| 誤り | 入力 | キャッシュの読み | キャッシュの書き | キャッシュ外 | 出力 |", md)
        self.assertIn("| judge__diagnose-loop.diagnose | judge | 1 | 1 | 86.143 | 0.584333 | 1 | 0 | 1 | 0 | 0 | 0 | 1000 | 700 | 100 | 200 | 200 |", md)
        self.assertIn("- start: トークン not_applicable", md)
        self.assertIn("- eyes__r4-scope: トークン キャッシュの内訳が不明な起動 1 件", md)
        with self.subTest("cacheRead の欠けた起動も内訳が不明な起動に数える"):
            row = nodes.Row("n", "s")
            row.ran("t", 1.0, None, None, "x", {"input": 100, "output": 10, "cacheWrite": 20}, None)
            row.ran("t", 1.0, None, None, "x", {"input": 50, "output": 5, "cacheRead": 10, "cacheWrite": 0}, None)
            view = row.view()
            self.assertEqual([view[k] for k in columns], [150, 10, 20, None, 15])
            self.assertEqual(view["cacheUnknown"], 1)
        with self.subTest("控えだけの作り手は tokens の訳を残す"):
            record = {"key": KEY, "attempt": str(self.tmp / "nowhere"), "seconds": 60.0, "usd": None, "findings": []}
            reviewbench.write(self.out, "claude", KEY, {}, record)
            [only] = nodes.table(self.out, runner.PlainClaude())["nodes"]
            self.assertEqual((only["input"], only["tokens_why"]), (None, "控えの tokens が無い"))

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

    def test_unknown_verdict_word_stops_with_its_name(self):
        for word in ("matched_tp_v2", None):
            with self.subTest(word=word):
                self.judged(second=word)
                with self.assertRaises(reviewbench.BenchError) as caught:
                    nodes.table(self.out, runner.WorksFactory())
                self.assertIn(repr(word), str(caught.exception))
                self.assertIn(KEY, str(caught.exception))

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

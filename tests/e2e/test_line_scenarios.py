"""線 works-factory-line の筋書き（workflows/line/fixtures/*.stubs.yaml）を、止めた Archon の `workflow test` で回す。

木は tests/archon.py の使い捨ての木に、線と .shared/ と、線が差し込む本物のブロックを置いた物。筋書きは本物のブロックの節の id
（例 test-gate-base__run）に stub を置き、本物の返す節の output_format に合う値で差す。
筋書きは exec-code: true で、stub の無い線の script は本当に走る。dry-run は include の入力をブロックの名前の script に渡さない
（止めた Archon の dry-run.ts）ので、通るブロックの script の節は全部 stub にする。fix は組の子の形（route の group: true）を
通して、届く fan_out: を避ける（dry-run は workflow: の fan_out: を模擬できない）。輪の中の節の id は差し込まれても頭が付かないので、
fix-loop の中の stub（fix-prep・fix-accept）は fix と refix-run の両方に効く。Archon の源か bun が無ければ名前つきで見送る。
"""
import json
import pathlib
import unittest

from tests import archon
from tests.layers import scan

LINE = archon.WORKFLOWS / "line"
SCENARIOS = (
    "standard", "start-refused", "no-fix", "policy-continue", "policy-stop", "plan-stalled", "plan-unsettled", "replan",
    "rejudge", "light", "final-stop", "final-when-needed-green", "conflict-ask", "unattended-needs-human", "block-failed",
    "replan-stop", "plan-failed", "block-returns-failed", "replan-answers",
)


def blocks() -> list[str]:
    """線が差し込むブロックのフォルダの名"""
    return sorted({name.removeprefix(scan.OURS_PREFIX) for name in scan.includes(archon.ROOT, scan.LINE_YAML)})


def run_line() -> dict:
    """筋書きの名 → workflow test の 1 件の結果"""
    with archon.tree(["line", *blocks()]) as tree:
        done = archon.archon(tree, "workflow", "test", archon.PACK["ours"]["line"], "--cwd", str(tree), "--json")
        return scenarios(done)


def scenarios(done) -> dict:
    try:
        report = json.loads(done.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(f"workflow test の返りが読めない（{error}）: {done.stdout}{done.stderr}") from None
    if "results" not in report:
        raise AssertionError(f"workflow test が筋書きを回せない: {json.dumps(report, ensure_ascii=False)}")
    return {pathlib.PurePosixPath(r["fixture"]).name.removesuffix(".stubs.yaml"): r for r in report["results"]}


class LineScenariosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not LINE.is_dir():
            raise AssertionError(f"線の置き場 {LINE} が無い")
        cls.results = run_line()

    def test_every_block_is_real(self):
        """線が差し込むブロックは全部 workflows/ に在り、筋書きは本物と組む"""
        for name in blocks():
            with self.subTest(block=name):
                self.assertTrue((archon.WORKFLOWS / name).is_dir())

    def test_every_scenario_is_declared(self):
        self.assertEqual(sorted(self.results), sorted(SCENARIOS))

    def test_every_scenario_passes(self):
        for name in SCENARIOS:
            with self.subTest(scenario=name):
                got = self.results.get(name)
                self.assertIsNotNone(got, f"筋書き {name} が無い")
                self.assertTrue(got["pass"], json.dumps(got, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()

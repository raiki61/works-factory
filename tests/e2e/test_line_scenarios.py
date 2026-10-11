"""線 works-factory-line の筋書き（workflows/line/fixtures/*.stubs.yaml）を、止めた Archon の `workflow test` で回す。

木は tests/archon.py の使い捨ての木に、線と .shared/ と、代わりのブロック（workflows/line/fixtures/stub-blocks/<ブロック>/）を
本物のブロックの置き場（<ブロック>/）に写した物。本物のブロックは置かないので、main に在っても混ざらない。
筋書きは exec-code: true で、stub の無い線の script は本当に走る。同じ木で `archon validate` も回し、線が誤りも警告も出さないことを
照らす（本物のブロックが揃うまで、tests/layers/test_archon_validate.py は線を見送るため）。Archon の源か bun が無ければ名前つきで見送る。
"""
import json
import pathlib
import shutil
import tempfile
import unittest

from tests import archon
from tests.layers.test_archon_validate import validate

LINE = archon.WORKFLOWS / "line"
STUB_BLOCKS = LINE / "fixtures" / "stub-blocks"
SCENARIOS = (
    "standard", "start-refused", "no-fix", "policy-continue", "policy-stop", "plan-stalled", "plan-unsettled", "replan",
    "rejudge", "light", "final-stop", "final-when-needed-green", "conflict-ask", "unattended-needs-human", "block-failed",
    "replan-stop", "plan-failed",
)


def run_line() -> tuple[dict, dict]:
    """(筋書きの名 → workflow test の 1 件の結果, 工程の名 → validate の誤りと警告の行)"""
    with tempfile.TemporaryDirectory() as tmp:
        workflows = pathlib.Path(tmp) / "workflows"
        shutil.copytree(LINE, workflows / "line", ignore=shutil.ignore_patterns("__pycache__"))
        blocks = sorted(p.name for p in STUB_BLOCKS.iterdir() if p.is_dir())
        for name in blocks:
            shutil.copytree(STUB_BLOCKS / name, workflows / name)
        with archon.tree(["line", *blocks], workflows) as tree:
            done = archon.archon(tree, "workflow", "test", archon.PACK["ours"]["line"], "--cwd", str(tree), "--json")
            return scenarios(done), validate(tree)


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
        cls.results, cls.validated = run_line()

    def test_line_validates_without_errors_or_warnings(self):
        line = archon.PACK["ours"]["line"]
        self.assertEqual(self.validated.get(line), [], self.validated)

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

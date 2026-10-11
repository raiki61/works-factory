"""線 works-factory-line の筋書き（workflows/line/fixtures/*.stubs.yaml）を、止めた Archon の `workflow test` で回す。

木は tests/archon.py の使い捨ての木に、線と .shared/ と、線が差し込むブロックを置いた物。workflows/ に在るブロックは本物を、
まだ無いブロックだけ代わり（workflows/line/fixtures/stub-blocks/<ブロック>/）を置く。だから筋書きは本物のブロックの節の id
（例 test-gate-base__run）に stub を置き、本物の返す節の output_format に合う値で差す。
筋書きは exec-code: true で、stub の無い線の script は本当に走る。同じ木で `archon validate` も回し、線が誤りも警告も出さないことを
照らす（全部のブロックが揃うまで、tests/layers/test_archon_validate.py は線を見送るため）。Archon の源か bun が無ければ名前つきで見送る。
"""
import json
import pathlib
import shutil
import tempfile
import unittest

from tests import archon
from tests.layers import scan
from tests.layers.test_archon_validate import validate

LINE = archon.WORKFLOWS / "line"
STUB_BLOCKS = LINE / "fixtures" / "stub-blocks"
SCENARIOS = (
    "standard", "start-refused", "no-fix", "policy-continue", "policy-stop", "plan-stalled", "plan-unsettled", "replan",
    "rejudge", "light", "final-stop", "final-when-needed-green", "conflict-ask", "unattended-needs-human", "block-failed",
    "replan-stop", "plan-failed", "block-returns-failed", "replan-answers",
)


def blocks() -> list[str]:
    """線が差し込むブロックのフォルダの名"""
    return sorted({name.removeprefix(scan.OURS_PREFIX) for name in scan.includes(archon.ROOT, scan.LINE_YAML)})


def run_line() -> tuple[dict, dict]:
    """(筋書きの名 → workflow test の 1 件の結果, 工程の名 → validate の誤りと警告の行)"""
    with tempfile.TemporaryDirectory() as tmp:
        workflows = pathlib.Path(tmp) / "workflows"
        no_cache = shutil.ignore_patterns("__pycache__")
        shutil.copytree(LINE, workflows / "line", ignore=no_cache)
        for name in blocks():
            real = archon.WORKFLOWS / name
            shutil.copytree(real if real.is_dir() else STUB_BLOCKS / name, workflows / name, ignore=no_cache)
        with archon.tree(["line", *blocks()], workflows) as tree:
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

    def test_every_block_is_real_or_has_a_stand_in(self):
        """在るブロックの代わりは置かない（本物と照らさない代わりが残らない）。無いブロックには代わりが在る"""
        for name in blocks():
            with self.subTest(block=name):
                self.assertNotEqual((archon.WORKFLOWS / name).is_dir(), (STUB_BLOCKS / name).is_dir())

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

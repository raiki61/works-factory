"""`workflows/` の YAML で、期限を持つ節の `timeout`・`idle_timeout` が全部 `1728000000`（workflows/AGENTS.md の E12 の機械の行）。"""
import pathlib
import tempfile
import unittest

from tests.layers import scan

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"


class NoTimeoutsTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E12", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E12", SEEDS / "e12")
        self.assertGreaterEqual(len(got), 1)
        self.assertTrue(any("workflows/judge/works-factory-judge.yaml" in line for line in got), got)

    def test_missing_timeout_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            block = pathlib.Path(tmp) / "workflows" / "judge"
            block.mkdir(parents=True)
            (block / "works-factory-judge.yaml").write_text(
                "name: works-factory-judge\nnodes:\n  - id: run\n    script: stub\n", encoding="utf-8"
            )
            got = scan.problems("E12", pathlib.Path(tmp))
        self.assertTrue(any("workflows/judge/works-factory-judge.yaml" in line for line in got), got)


if __name__ == "__main__":
    unittest.main()

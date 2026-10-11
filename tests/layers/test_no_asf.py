"""`workflows/` の YAML の `include:`・`workflow:` の値が `works-factory-` で始まる（根の AGENTS.md の E8 の機械の行）。"""
import pathlib
import unittest

from tests.layers import scan

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"


class NoAsfTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E8", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E8", SEEDS / "e8")
        self.assertGreaterEqual(len(got), 1)
        self.assertTrue(any("workflows/judge/works-factory-judge.yaml" in line for line in got), got)


if __name__ == "__main__":
    unittest.main()

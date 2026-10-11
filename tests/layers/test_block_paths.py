"""ブロックの script の字に、ほかのブロックの名と、`lib/`・`workflows/.shared/` の外への相対パスが無い（workflows/AGENTS.md の E4 の機械の行）。"""
import pathlib
import unittest

from tests.layers import scan

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"


class BlockPathsTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E4", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E4", SEEDS / "e4")
        self.assertGreaterEqual(len(got), 1)
        self.assertTrue(any("workflows/judge/scripts/a.py" in line for line in got), got)


if __name__ == "__main__":
    unittest.main()

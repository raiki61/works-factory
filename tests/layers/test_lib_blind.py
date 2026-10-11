"""`lib/` に Archon の名の字の形が無く、`workflows`・`bin` の中の物を import しない（lib/AGENTS.md の E3 の機械の行）。"""
import pathlib
import unittest

from tests.layers import scan

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"


class LibBlindTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E3", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E3", SEEDS / "e3")
        self.assertGreaterEqual(len(got), 1)
        self.assertTrue(any("lib/x.py" in line for line in got), got)


if __name__ == "__main__":
    unittest.main()

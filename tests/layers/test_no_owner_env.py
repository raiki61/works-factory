"""`bin/`・`workflows/`・`lib/` に、持ち主の環境の字（`raiki61`・`claude-code-oauth-`・`/Users/`）が無い（根の AGENTS.md の E14 の機械の行）。"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"


class NoOwnerEnvTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E14", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E14", SEEDS / "e14")
        self.assertGreaterEqual(len(got), 1)
        self.assertTrue(any("bin/x" in line for line in got), got)


    def test_unreadable_file_is_red(self):
        with tree({"bin/y": b"\x81 /Users/example/\n"}) as root:
            got = scan.problems("E14", root)
        self.assertTrue(any("bin/y" in line for line in got), got)


if __name__ == "__main__":
    unittest.main()

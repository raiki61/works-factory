"""`lib/` に Archon の名の字の形が無く、`workflows`・`bin` の中の物を import しない（lib/AGENTS.md の E3 の機械の行）。"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"


class LibBlindTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E3", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E3", SEEDS / "e3")
        self.assertGreaterEqual(len(got), 1)
        self.assertTrue(any("lib/x.py" in line for line in got), got)


    def test_import_of_blocks_is_red(self):
        with tree({"lib/y.py": "from workflows.judge import thing\n"}) as root:
            got = scan.problems("E3", root)
        self.assertTrue(any("lib/y.py:1" in line and "import" in line for line in got), got)

    def test_unreadable_file_is_red(self):
        with tree({"lib/z.py": b"\xff TYPED_ARTIFACTS_FILE\n"}) as root:
            got = scan.problems("E3", root)
        self.assertTrue(any("lib/z.py" in line for line in got), got)


if __name__ == "__main__":
    unittest.main()

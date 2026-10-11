"""役の指示書（`workflows/*/commands/`）と `lib/` に、言語と実行器の名の語の表に当たる字が無い（根の AGENTS.md の E13 の機械の行）。"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"


class LangNeutralTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E13", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E13", SEEDS / "e13")
        self.assertGreaterEqual(len(got), 1)
        self.assertTrue(any("workflows/judge/commands/a.md" in line for line in got), got)


    def test_lib_is_in_scope(self):
        with tree({"lib/run.py": 'CMD = "pytest"\n'}) as root:
            got = scan.problems("E13", root)
        self.assertTrue(any("lib/run.py:1" in line for line in got), got)

    def test_name_with_version_is_red(self):
        with tree({"workflows/judge/commands/a.md": "run `python3 lib/check.py`\n"}) as root:
            got = scan.problems("E13", root)
        self.assertTrue(any("a.md:1" in line and "python" in line for line in got), got)

    def test_unreadable_file_is_red(self):
        with tree({"workflows/judge/commands/b.md": b"\xe9 pytest\n"}) as root:
            got = scan.problems("E13", root)
        self.assertTrue(any("commands/b.md" in line for line in got), got)


if __name__ == "__main__":
    unittest.main()

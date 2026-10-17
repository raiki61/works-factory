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

    def test_import_of_bin_is_red(self):
        for text in ("from bin._lib import place\n", "import bin._lib.place\n"):
            with self.subTest(text=text), tree({"lib/y.py": text}) as root:
                got = scan.problems("E3", root)
                self.assertTrue(any("lib/y.py:1" in line and "bin の中の物を import する" in line for line in got), got)

    def test_unreadable_file_is_red(self):
        with tree({"lib/z.py": b"\xff TYPED_ARTIFACTS_FILE\n"}) as root:
            got = scan.problems("E3", root)
        self.assertTrue(any("lib/z.py" in line for line in got), got)


    def test_runtime_names_are_red(self):
        """実行基盤の入力・run の id・前の周・輪・節の出力の字（K7）。UNREAD_INPUTS_HEAD のような名の一部は数えない"""
        for text, word in (('X = "INPUTS_UNITS"\n', "INPUTS_UNITS"), ('X = "WORKFLOW_ID"\n', "WORKFLOW_ID"),
                           ("# $LOOP_PREV で貼る\n", "$LOOP_PREV"), ("# 線の loop_group の 3 回\n", "loop_group"),
                           ("# $material-route.output.<欄> で読む\n", "$material-route.output")):
            with self.subTest(word=word), tree({"lib/y.py": text}) as root:
                got = scan.problems("E3", root)
                self.assertEqual(len(got), 1, got)
                self.assertTrue(got[0].endswith(f" {word}"), got)
        with tree({"lib/y.py": 'UNREAD_INPUTS_HEAD = "x"\n'}) as root:
            self.assertEqual(scan.problems("E3", root), [])

    def test_named_word_allowance_hides_only_that_word(self):
        """ALLOWED の `<パス>#<字>` の行は、そのファイルのその字だけを外す（同じファイルのほかの字は赤のまま）"""
        with tree({"lib/tests/test_blk_fix.py": 'A = "$LOOP_PREV"\nB = "INPUTS_OTHER"\n'}) as root:
            got = scan.problems("E3", root)
        self.assertEqual(len(got), 1, got)
        self.assertIn("INPUTS_OTHER", got[0])


if __name__ == "__main__":
    unittest.main()

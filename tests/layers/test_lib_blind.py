"""`lib/` に Archon の名の字の形が無く、`workflows`・`bin` の中の物を import しない（`lib/AGENTS.md` の E3 と根の `AGENTS.md` の E22 の機械の行）。

- Archon の名: `archon`・`$ARTIFACTS_DIR`・`$TYPED_ARTIFACTS_FILE`・`ARCHON_` で始まる環境変数・`INPUTS_<名>`・`WORKFLOW_ID`・`$LOOP_PREV`・`loop_group`・`$<ノード>.output`・`output_type` の語（照らしは `scan.ARCHON_WORDS` の字の形だけで、ノードの id は照らさない）。
- import の向き: 層の地図 `docs/layers.json` で lib が頼ってよい層（`may_use`）の外の層の頭のフォルダ（`workflows`・`bin`）を import しない（`scan.LAYER_IMPORT`）。
- 照らしから外すのは `tests/layers/scan.py` の `ALLOWED["E3"]` の行だけ: この決まりの文の `lib/AGENTS.md` と、役が読む借りたスキルの読み替え `lib/borrow/unattended.md` が役に説く Archon の字（`<パス>#<字>` の行）と、`lib/borrow/COPIED_FROM` の、消した文の原文の記録に残る Archon の字（`lib/borrow/COPIED_FROM#loop_group`）と、Archon の run の記録を読む口 `lib/runlog.py` とその試験 `lib/tests/test_runlog.py`（report と chain の 2 つが使うので lib に上げた。`docs/design/integration.md` の 4.5-2）。
"""
import pathlib
import unittest
from unittest import mock

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
        with tree({"lib/x.py": 'A = "$LOOP_PREV"\nB = "INPUTS_OTHER"\n'}) as root, \
                mock.patch.dict(scan.ALLOWED, {"E3": ("lib/x.py#$LOOP_PREV",)}):
            got = scan.problems("E3", root)
        self.assertEqual(len(got), 1, got)
        self.assertIn("INPUTS_OTHER", got[0])


if __name__ == "__main__":
    unittest.main()

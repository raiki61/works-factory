"""線 A の入口の入力（.shared/core/entry.py の check_inputs・build_input と board.diff_of）の検査。

どの入口（依頼のファイル・base の版・PR）も 1 つの入力の形（差分の根・差分・依頼の行・PR の添え物）に揃える。差分の根は
base と HEAD の merge-base（GitHub の PR の three-dot と同じ）、名指しが無ければ HEAD。差分が空で依頼の行も空なら拒む
（盤面を作る前）。種の git は gitkit の型の写し。
"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import entryshape  # noqa: E402  （入口の変換）
from tests.bin.gitkit import committed_copy, git  # noqa: E402

SEED = LIB.parent / "tests" / "e2e" / "target-seed"


class ChangeInputsCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self._tmp.name) / "repo"
        self.fork = committed_copy(self.repo, SEED)
        git(self.repo, "branch", "base")
        with (self.repo / "stats.py").open("a", encoding="utf-8") as f:
            f.write("\n# 変更\n")
        git(self.repo, "commit", "-q", "-am", "change")

    def tearDown(self):
        self._tmp.cleanup()

    def test_diff_of_clean_head_is_empty(self):
        """綺麗な作業ツリーを HEAD から測る → 空・0 ファイル"""
        got = entryshape.diff_of(self.repo, git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual((got["empty"], got["files"]), (True, 0))
        self.assertIsInstance(got["stat"], str)

    def test_diff_of_counts_untracked(self):
        """未追跡の新規ファイル 1 本は数える。.gitignore に当たる物は数えない（写しの核の _worktree_tree と同じ測り方）"""
        head = git(self.repo, "rev-parse", "HEAD")
        (self.repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        git(self.repo, "add", ".gitignore")
        git(self.repo, "commit", "-q", "-m", "ignore")
        head = git(self.repo, "rev-parse", "HEAD")
        (self.repo / "ignored.txt").write_text("x\n", encoding="utf-8")
        self.assertTrue(entryshape.diff_of(self.repo, head)["empty"])
        (self.repo / "new.py").write_text("x = 1\n", encoding="utf-8")
        got = entryshape.diff_of(self.repo, head)
        self.assertEqual((got["empty"], got["files"]), (False, 1))
        self.assertIn("1 file", got["stat"])

    def test_diff_of_refuses_unknown_rev(self):
        """引けない版 → Reject（黙って空と言わない）"""
        with self.assertRaises(entryshape.Reject):
            entryshape.diff_of(self.repo, "1" * 40)



class NamedCase(unittest.TestCase):
    def test_request_names_pr_and_issue(self):
        """L-E18: 依頼の欄 pr・issue で名指した番号も run の中で読む（入力 pr と合わせ、重ねない。元 entryshape.py 156-169 行 named）"""
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp)
            (repo / "req.json").write_text(json.dumps({"findings": [{"where": "a", "text": "b"}], "pr": [3, 7], "issue": [9]}),
                                           encoding="utf-8")
            self.assertEqual(entryshape.named({"request": "req.json", "pr": "7"}, repo), ([3, 7], [9]))
            self.assertEqual(entryshape.named({"request": "", "pr": "7"}, repo), ([7], []))
            self.assertEqual(entryshape.named({"request": "no-such.json", "pr": ""}, repo), ([], []))


if __name__ == "__main__":
    unittest.main()

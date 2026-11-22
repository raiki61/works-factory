"""`bin/`・`workflows/`・`lib/` と見る道具のフォルダに、持ち主の環境の字（`raiki61`・`claude-code-oauth-`・`/Users/`）が無い（根の `AGENTS.md` の E14 の機械の行。持ち主の決め `others-may-use`）。

- 持ち主の環境（Claude のアカウントの名・keychain の項目の名・GitHub のアカウントの名・置き場のパス）は、選べる道として置き、値は利用者の設定か起動の引数で渡す。
- 何かを削る直しが普通の利用者の環境で要らないかは人が見る。
"""
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

    def test_git_ignored_files_are_not_read(self):
        """git が無視するファイルは読まない（UTF-8 で読めなくても数えない）。無視されない未追跡の物は今までどおり照らす"""
        files = {".gitignore": "*.cache\n", "bin/y.cache": b"\x81 /Users/example/\n", "bin/z": "/Users/example/\n"}
        with tree(files, git_init=True) as root:
            got = scan.problems("E14", root)
        self.assertEqual([line.partition(":")[0] for line in got], ["bin/z"], got)

    def test_tree_inside_an_outer_git_worktree_that_ignores_it_is_still_read(self):
        """試験の木が外の git の作業木の中に作られ、外の無視の表が木を隠しても、柵は木を読む（何も読まずに通らない）"""
        with tree({".gitignore": "inner/\n"}, git_init=True) as outer:
            inner = outer / "inner"
            (inner / "bin").mkdir(parents=True)
            (inner / "bin" / "z").write_text("/Users/example/\n", encoding="utf-8")
            got = scan.problems("E14", inner)
        self.assertEqual([line.partition(":")[0] for line in got], ["bin/z"], got)


if __name__ == "__main__":
    unittest.main()

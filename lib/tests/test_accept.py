"""受け付けの口（.shared/core/accept.py）の検査。

良い返答の見本が通り、悪い見本（拒む理由が 1 つだけになるように作った物）が ok: False で拒まれるかを、
dev/target-seed/ を一時ディレクトリの git に写した使い捨ての対象リポジトリで見る。見本は tests/replies/ に在る。
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
SEED = LIB.parent / "tests" / "e2e" / "target-seed"
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from accept import _ignored_entries, snapshot_tree, tree_change, tree_state  # noqa: E402
from tests.bin.gitkit import committed_copy, git  # noqa: E402

class AcceptCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(self._tmp.name)
        self.repo = tmp / "repo"
        self.base = committed_copy(self.repo, SEED)   # 種を写して commit した git（型の写し。gitkit）

    def tearDown(self):
        self._tmp.cleanup()


class TestSnapshot(AcceptCase):
    def test_snapshot_sees_ignored_content(self):
        (self.repo / "__pycache__").mkdir()
        pyc = self.repo / "__pycache__" / "stats.cpython-314.pyc"
        pyc.write_bytes(b"a")
        before = snapshot_tree(self.repo)
        self.assertEqual(before["ignored"], ["__pycache__/"])
        self.assertEqual(before["porcelain"], "", "porcelain は無視されるファイルを映さない（だから ignored が要る）")
        pyc.write_bytes(b"b")
        self.assertNotEqual(before["diff_sha256"], snapshot_tree(self.repo)["diff_sha256"])

    def test_snapshot_skips_cli_write_ledger(self):
        # Claude Code 2.1.283 が役の cwd に作る空のフォルダ .claude/.cc-writes/（台帳 R62・自分食い 23 件目で読むだけの役が 3 回拒まれた）
        (self.repo / ".gitignore").write_text(".claude/\n")
        git(self.repo, "add", ".gitignore")
        git(self.repo, "commit", "-qm", "ignore")
        before = snapshot_tree(self.repo)
        (self.repo / ".claude" / ".cc-writes").mkdir(parents=True)
        (self.repo / ".claude" / ".cc-writes" / "w").write_bytes(b"x")
        self.assertEqual(snapshot_tree(self.repo), before)
        (self.repo / ".claude" / "other").write_bytes(b"x")    # 同じ .claude/ の下でも、ほかの物は見る
        self.assertNotEqual(snapshot_tree(self.repo), before)

    def test_snapshot_skips_nested_cli_write_ledger(self):
        # run 30: 役の Bash が cd した先（works/docs/specs）にも Claude Code が空の .claude/.cc-writes/ を作り、git の全体の除外
        # （.claude/.cc-writes/）で `!! works/docs/specs/.claude/.cc-writes/` に出た。深さを問わず数えない
        (self.repo / "docs" / "specs").mkdir(parents=True)
        (self.repo / "docs" / "specs" / "a.md").write_text("a\n")
        (self.repo / ".gitignore").write_text(".claude/.cc-writes/\n")
        git(self.repo, "add", ".gitignore", "docs")
        git(self.repo, "commit", "-qm", "ignore")
        before = snapshot_tree(self.repo)
        (self.repo / "docs" / "specs" / ".claude" / ".cc-writes").mkdir(parents=True)
        self.assertEqual(snapshot_tree(self.repo), before)
        (self.repo / "docs" / "specs" / ".claude" / ".cc-writes" / "settings.json.tmp.0a1b2c3d").write_bytes(b"x")
        self.assertEqual(snapshot_tree(self.repo), before)
        (self.repo / "docs" / "specs" / ".claude" / "other").write_bytes(b"x")    # 同じ .claude/ の下でも、ほかの物は見る
        self.assertNotEqual(snapshot_tree(self.repo), before)

    def test_snapshot_skips_nested_collapsed_cli_dir(self):
        # 対象の .gitignore が .claude/ を無視すると、git は深い所の物も `<dir>/.claude/` に畳む。中身が控えのフォルダだけなら数えない
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "a.md").write_text("a\n")
        (self.repo / ".gitignore").write_text(".claude/\n")
        git(self.repo, "add", ".gitignore", "docs")
        git(self.repo, "commit", "-qm", "ignore")
        before = snapshot_tree(self.repo)
        (self.repo / "docs" / ".claude" / ".cc-writes").mkdir(parents=True)
        (self.repo / "docs" / ".claude" / ".cc-writes" / "w.tmp.0a1b2c3d").write_bytes(b"x")
        self.assertEqual(snapshot_tree(self.repo), before)
        (self.repo / "docs" / ".claude" / "settings.local.json").write_bytes(b"{}")
        self.assertNotEqual(snapshot_tree(self.repo), before)

    def test_snapshot_skips_untracked_cli_write_ledger(self):
        # 除外の規則が無い対象: 空の控えは git に出ないが、書きかけの一時ファイルが残ると未追跡に出る。これも数えない。
        # Claude Code は全体の除外（~/.config/git/ignore）に **/.claude/.cc-writes/ を足すので、ここではそれを読ませない
        git(self.repo, "config", "core.excludesFile", os.devnull)
        before = snapshot_tree(self.repo)
        (self.repo / "sub" / ".claude" / ".cc-writes").mkdir(parents=True)
        (self.repo / "sub" / ".claude" / ".cc-writes" / "x.json.tmp.0a1b2c3d").write_bytes(b"x")
        self.assertEqual(snapshot_tree(self.repo), before)
        (self.repo / "sub" / "real.txt").write_text("x\n")
        self.assertNotEqual(snapshot_tree(self.repo), before)

    def test_snapshot_sees_untracked_content(self):
        (self.repo / "new.txt").write_text("a\n")
        before = snapshot_tree(self.repo)
        (self.repo / "new.txt").write_text("b\n")
        self.assertEqual(before["porcelain"], snapshot_tree(self.repo)["porcelain"])
        self.assertNotEqual(before["diff_sha256"], snapshot_tree(self.repo)["diff_sha256"])


class TestTreeState(AcceptCase):
    """読むだけの任せ先の役（blk-pr・blk-ci）の前後の作業ツリーの姿（tree_state）と、その違いの文（tree_change）"""

    def test_change_names_content_when_porcelain_is_same(self):
        # 既に変えてあるファイルの中身をさらに書き換えた: porcelain の行は同じまま。違いは差分の中身だと言う（審査 M4）
        with open(self.repo / "stats.py", "a") as f:
            f.write("# 前から在った変更\n")
        before = tree_state(self.repo)
        with open(self.repo / "stats.py", "a") as f:
            f.write("# 役が書いた\n")
        moved = tree_change(before, tree_state(self.repo))
        self.assertTrue(moved)
        self.assertFalse([m for m in moved if m.startswith("git status --porcelain")], moved)
        self.assertTrue([m for m in moved if "中身が変わった" in m], moved)

    def test_change_ignored_only_has_no_porcelain_noise(self):
        # 無視されるパスだけが増えた: porcelain の空の行（『前 [] / 今 []』）を出さない（審査 M4）
        before = tree_state(self.repo)
        (self.repo / "__pycache__").mkdir()
        (self.repo / "__pycache__" / "stats.cpython-314.pyc").write_bytes(b"x")
        moved = tree_change(before, tree_state(self.repo))
        self.assertFalse([m for m in moved if m.startswith("git status --porcelain")], moved)
        self.assertTrue([m for m in moved if "増えた ['__pycache__/']" in m], moved)

    def test_change_shows_porcelain_when_it_differs(self):
        before = tree_state(self.repo)
        (self.repo / "new.txt").write_text("x\n")
        moved = tree_change(before, tree_state(self.repo))
        self.assertIn("git status --porcelain: 役を起こす前 [] / 今 ['?? new.txt']", moved)
        self.assertEqual(tree_change(before, before), [])

    def test_ignored_entries_skip_origin_of_worktree_rename(self):
        # 作業ツリーの rename（intent-to-add を伴う。Y の欄が R）は元の名前の欄が続く。X だけ見ると元の名前を読み違える（審査 M5）
        (self.repo / "!! old.txt").write_text("a\nb\nc\nd\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "old")
        (self.repo / "!! old.txt").rename(self.repo / "new.txt")
        git(self.repo, "add", "-N", "new.txt")
        z = subprocess.run(["git", "-C", str(self.repo), "status", "--porcelain", "-z"], capture_output=True, check=True).stdout
        self.assertTrue(z.startswith(b" R new.txt\0!! old.txt\0"), z)
        self.assertEqual(_ignored_entries(self.repo), [])


if __name__ == "__main__":
    unittest.main()

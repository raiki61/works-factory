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

import accept  # noqa: E402
from accept import _ignored_entries, snapshot_tree, touched_files, tree_change, tree_state  # noqa: E402
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


    def test_test_cache_names_are_lib_only(self):
        """修正の差分から除く名の形は TEST_CACHES だけ（実行器の名は lib に書かない。根の AGENTS.md の E13）"""
        names = ["__pycache__", "a/__pycache__", "b/__pycache__/x.py", "c.pyc", "d/e.pyc", "ok.py", "x/__pycache__y/z.py",
                 ".pytest_cache/v/lastfailed", "y/.pytest_cache_x"]
        self.assertEqual(sorted(n for n in names if not accept._is_test_cache(n)),
                         sorted([".pytest_cache/v/lastfailed", "ok.py", "x/__pycache__y/z.py", "y/.pytest_cache_x"]))

    def test_snapshot_sees_edits_hidden_by_index_marks(self):
        """本物の index の assume-unchanged・skip-worktree の印を付けたファイルの編集も姿を変え、印は消さない（touched_files と同じ見え方）"""
        for name in ("f", "g"):
            (self.repo / name).write_text("1\n", encoding="utf-8")
        git(self.repo, "add", "f", "g")
        git(self.repo, "commit", "-q", "-m", "fg")
        git(self.repo, "update-index", "--assume-unchanged", "f")
        git(self.repo, "update-index", "--skip-worktree", "g")
        for name in ("f", "g"):
            with self.subTest(name=name):
                before = snapshot_tree(self.repo)
                (self.repo / name).write_text(f"{name} を書き換えた\n", encoding="utf-8")
                after = snapshot_tree(self.repo)
                self.assertIn(f" M {name}", after["porcelain"])
                self.assertNotEqual(after["diff_sha256"], before["diff_sha256"])
        self.assertEqual(git(self.repo, "ls-files", "-v", "f", "g").splitlines(), ["h f", "S g"])

    def test_snapshot_leaves_out_of_cone_files_unchanged(self):
        """sparse checkout の範囲外（skip-worktree の印が付き disk に無い）のファイルは、消したと見ない"""
        for name in ("x/a", "y/b"):
            (self.repo / name).parent.mkdir()
            (self.repo / name).write_text("1\n", encoding="utf-8")
        git(self.repo, "add", "x", "y")
        git(self.repo, "commit", "-q", "-m", "xy")
        git(self.repo, "sparse-checkout", "set", "y")
        self.assertEqual(snapshot_tree(self.repo)["porcelain"], "")


class TestTouchedFiles(AcceptCase):
    def test_touched_files_sees_files_hidden_by_index_marks(self):
        """本物の index の assume-unchanged・skip-worktree の印を付けた変更済みのファイルも挙げ、印は消さない"""
        for name in ("f", "g"):
            (self.repo / name).write_text("1\n", encoding="utf-8")
        git(self.repo, "add", "f", "g")
        git(self.repo, "commit", "-q", "-m", "fg")
        git(self.repo, "update-index", "--assume-unchanged", "f")
        git(self.repo, "update-index", "--skip-worktree", "g")
        for name in ("f", "g"):
            (self.repo / name).write_text("2\n", encoding="utf-8")
        self.assertEqual(touched_files(self.repo, "HEAD"), ["f", "g"])
        self.assertEqual(git(self.repo, "ls-files", "-v", "f", "g").splitlines(), ["h f", "S g"])

    def test_sparse_checkout_leaves_out_of_cone_files_untouched(self):
        """sparse checkout の範囲外（skip-worktree の印が付き disk に無い）のファイルは、消したと数えない"""
        for name in ("x/a", "y/b"):
            (self.repo / name).parent.mkdir()
            (self.repo / name).write_text("1\n", encoding="utf-8")
        git(self.repo, "add", "x", "y")
        git(self.repo, "commit", "-q", "-m", "xy")
        git(self.repo, "sparse-checkout", "set", "y")
        self.assertFalse((self.repo / "x" / "a").exists())
        self.assertEqual(touched_files(self.repo, "HEAD"), [])


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



class TestBeyondStatus(AcceptCase):
    """状態の照らしで守られた役の受け付けは accept.BEYOND_STATUS の欄だけを比べる（git status の行の違いは照らしが見る）"""

    def moved(self, before):
        return accept.tree_moved(before, self.repo, keys=accept.BEYOND_STATUS)

    def test_beyond_status_ignores_porcelain_only_change(self):
        with open(self.repo / "stats.py", "a") as f:
            f.write("# 前から在った変更\n")
        before = tree_state(self.repo)
        git(self.repo, "add", "stats.py")
        self.assertNotEqual(tree_state(self.repo)["porcelain"], before["porcelain"])
        self.assertEqual(self.moved(before), [])
        self.assertTrue(accept.tree_moved(before, self.repo), "keys を渡さなければ今のまま全部の欄を比べる")

    def test_beyond_status_still_sees_rewrite_of_dirty_file(self):
        with open(self.repo / "stats.py", "a") as f:
            f.write("# 前から在った変更\n")
        before = tree_state(self.repo)
        with open(self.repo / "stats.py", "a") as f:
            f.write("# 役が書いた\n")
        self.assertTrue([m for m in self.moved(before) if "中身が変わった" in m])

    def test_beyond_status_still_sees_head_branch_and_ignored(self):
        before = tree_state(self.repo)
        git(self.repo, "checkout", "-q", "-b", "other")
        self.assertTrue([m for m in self.moved(before) if m.startswith("ref:")])
        before = tree_state(self.repo)
        (self.repo / "s.txt").write_text("x\n")
        git(self.repo, "add", "s.txt")
        git(self.repo, "commit", "-q", "-m", "moved")
        self.assertTrue([m for m in self.moved(before) if m.startswith("head:")])
        before = tree_state(self.repo)
        (self.repo / "__pycache__").mkdir()
        (self.repo / "__pycache__" / "stats.cpython-314.pyc").write_bytes(b"x")
        self.assertTrue([m for m in self.moved(before) if m.startswith("git が無視するパス")])
        self.assertEqual(set(accept.TREE_KEYS) - set(accept.BEYOND_STATUS), {"porcelain"})

    def test_status_keys_drops_porcelain_only_for_a_true_flag(self):
        """グラフは with: の真偽を字で渡す。字の "false" も全部の欄を比べる（真に読む縮めは状態の照らしの無い役の index の動きを見逃す）"""
        for flag in ("false", False, "", None, "False"):
            with self.subTest(flag=flag):
                self.assertEqual(accept.status_keys(flag), accept.TREE_KEYS)
        for flag in (True, "true", " True "):
            with self.subTest(flag=flag):
                self.assertEqual(accept.status_keys(flag), accept.BEYOND_STATUS)


if __name__ == "__main__":
    unittest.main()

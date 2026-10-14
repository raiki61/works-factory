"""run の作業ツリーの起点（bin/_lib/startpoint.py）の試験。実の git の使い捨ての木で照らす"""
import unittest

from bin._lib import startpoint
from tests.bin import hermetic
from tests.bin.gitkit import git

LINE = "works-factory-line"
PREFIX = "works-factory-"


class StartpointTest(unittest.TestCase):
    def setUp(self):
        self.target = hermetic.tmpdir(self) / "target"
        self.target.mkdir()
        git(self.target, "init", "-q", "-b", "main")
        (self.target / "kept.txt").write_text("kept\n", encoding="utf-8")
        (self.target / ".gitignore").write_text("ignored/\n", encoding="utf-8")
        git(self.target, "add", "-A")
        git(self.target, "commit", "-q", "-m", "seed")
        self.head = git(self.target, "rev-parse", "HEAD")

    def state(self) -> list[str]:
        return [git(self.target, "status", "--porcelain", "--untracked-files=all"), git(self.target, "rev-parse", "HEAD"),
                git(self.target, "branch", "--show-current"), git(self.target, "for-each-ref")]

    def test_clean_target_starts_from_head(self):
        args, said = startpoint.choose([], LINE, self.target, PREFIX)
        self.assertEqual(args, ["--from", self.head])
        self.assertIn(self.head[:12], said)
        self.assertIn("HEAD", said)

    def test_dirty_target_is_wrapped_without_moving_it(self):
        (self.target / "kept.txt").write_text("changed\n", encoding="utf-8")
        (self.target / "new.txt").write_text("new\n", encoding="utf-8")
        (self.target / "ignored").mkdir()
        (self.target / "ignored" / "dep.txt").write_text("dep\n", encoding="utf-8")
        git(self.target, "add", "new.txt")
        (self.target / "untracked.txt").write_text("untracked\n", encoding="utf-8")
        before = self.state()
        args, said = startpoint.choose(["--input", "request=x"], LINE, self.target, PREFIX)
        self.assertEqual(self.state(), before)
        self.assertEqual(args[0], "--from")
        wrapped = args[1]
        self.assertNotEqual(wrapped, self.head)
        self.assertEqual(git(self.target, "rev-parse", f"{wrapped}^"), self.head)
        self.assertEqual(git(self.target, "show", f"{wrapped}:kept.txt"), "changed")
        self.assertEqual(git(self.target, "show", f"{wrapped}:untracked.txt"), "untracked")
        self.assertEqual(git(self.target, "ls-tree", "-r", "--name-only", wrapped).split(),
                         [".gitignore", "kept.txt", "new.txt", "untracked.txt"])
        self.assertIn(wrapped[:12], said)
        self.assertIn("3 件", said)
        self.assertIn("A untracked.txt", said)

    def test_named_start_and_flags_archon_refuses_with_from_add_nothing(self):
        (self.target / "untracked.txt").write_text("untracked\n", encoding="utf-8")
        for flags in (["--from", "x"], ["--from=x"], ["--from-branch", "x"], *([f] for f in startpoint.SKIP_FLAGS)):
            with self.subTest(flags=flags):
                self.assertEqual(startpoint.choose(flags, LINE, self.target, PREFIX), ([], ""))

    def test_graph_not_ours_adds_nothing(self):
        self.assertEqual(startpoint.choose([], "archon-fix-github-issue", self.target, PREFIX), ([], ""))

    def test_tree_without_commit_or_git_adds_nothing(self):
        empty = hermetic.tmpdir(self) / "empty"
        empty.mkdir()
        self.assertEqual(startpoint.choose([], LINE, empty, PREFIX), ([], ""))
        git(empty, "init", "-q")
        (empty / "a.txt").write_text("a\n", encoding="utf-8")
        self.assertEqual(startpoint.choose([], LINE, empty, PREFIX), ([], ""))


if __name__ == "__main__":
    unittest.main()

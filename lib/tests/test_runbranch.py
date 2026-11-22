"""run の枝へ commit を積む口（lib/runbranch.py）の commit_parts の検査。

縛る事:
- パスの並びの並びを順に 1 つずつの commit に積み、パスが多くても（引数の長さの上限を超える量でも）積める。パスは字のまま読む
- i 本目の git が落ちれば、積み始める前の HEAD に戻して何本目かを載せた PartFailed を投げる
- git の誤りでない例外でも、積み始める前の HEAD に戻してから投げ直す。作業ツリーの変更は残す
"""
import os
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import runbranch  # noqa: E402
from tests.bin import hermetic  # noqa: E402
from tests.bin.gitkit import git  # noqa: E402


class CommitParts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name)
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "a.txt").write_text("one\n", encoding="utf-8")
        git(self.repo, "add", "a.txt")
        git(self.repo, "commit", "-q", "-m", "seed")
        self.start = git(self.repo, "rev-parse", "HEAD")
        (self.repo / "a.txt").write_text("two\n", encoding="utf-8")
        (self.repo / "b*.txt").write_text("glob\n", encoding="utf-8")
        self.repo.joinpath("bx.txt").write_text("not mine\n", encoding="utf-8")

    def parts(self, parts, message=lambda i, done: f"part {i}\n", hook_env=None):
        runbranch.staged(self.repo, "copy")
        return runbranch.commit_parts(self.repo, parts, message, hook_env)

    def changed(self, head) -> list:
        return git(self.repo, "diff-tree", "--no-commit-id", "--name-only", "-r", head).split("\n")

    def test_staged_keeps_a_leading_space_in_a_path(self):
        (self.repo / " lead.txt").write_text("x\n", encoding="utf-8")
        self.assertIn(" lead.txt", runbranch.staged(self.repo, "copy"))

    def test_parts_are_commits_in_order_and_paths_are_literal(self):
        heads = self.parts([["b*.txt"], ["a.txt", "bx.txt"]])
        self.assertEqual([self.changed(h) for h in heads], [["b*.txt"], ["a.txt", "bx.txt"]])
        self.assertEqual(heads[-1], git(self.repo, "rev-parse", "HEAD"))

    def test_more_paths_than_the_argument_limit_are_committed(self):
        deep = self.repo / ("d" * 200) / ("e" * 200)
        deep.mkdir(parents=True)
        many = [f"{i:05}{'x' * 200}" for i in range(4000)]
        for name in many:
            (deep / name).write_text("", encoding="utf-8")
        rel = [f"{'d' * 200}/{'e' * 200}/{name}" for name in many]
        self.assertGreater(sum(len(p) + 1 for p in rel), 2 * 1024 * 1024)
        heads = self.parts([rel, ["a.txt", "b*.txt", "bx.txt"]])
        self.assertEqual(len(self.changed(heads[0])), len(rel))

    def test_failing_git_on_a_later_part_rolls_back_and_names_the_part(self):
        hooks = self.repo / ".git" / "hooks"
        hooks.mkdir(exist_ok=True)
        (hooks / "pre-commit").write_text("#!/bin/sh\ngit diff --cached --name-only | grep -q a.txt && { echo no >&2; exit 1; }\nexit 0\n",
                                          encoding="utf-8")
        (hooks / "pre-commit").chmod(0o755)
        git(self.repo, "config", "core.hooksPath", str(hooks))
        with self.assertRaises(runbranch.PartFailed) as caught:
            self.parts([["b*.txt"], ["a.txt", "bx.txt"]], hook_env=hermetic.child_env())
        self.assertEqual(caught.exception.index, 1)
        self.assertIn("no", str(caught.exception))
        self.assertRolledBack()

    def test_other_errors_roll_back_too(self):
        def message(i, done):
            if i == 1:
                raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "hooks の言葉")
            return "part 0\n"
        with self.assertRaises(UnicodeDecodeError):
            self.parts([["b*.txt"], ["a.txt", "bx.txt"]], message)
        self.assertRolledBack()

    def assertRolledBack(self):
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.start)
        self.assertEqual(git(self.repo, "diff", "--cached", "--name-only"), "", "index も戻す")
        self.assertEqual((self.repo / "a.txt").read_text(encoding="utf-8"), "two\n", "作業ツリーは触らない")


class Branches(unittest.TestCase):
    """refusal・commit・branch・default_branch・pr_branches・git の口（実際の git の木で見る）"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        self.main = root / "main"
        self.main.mkdir()
        git(self.main, "init", "-q", "-b", "trunk")
        (self.main / "a.txt").write_text("one\n", encoding="utf-8")
        git(self.main, "add", "a.txt")
        git(self.main, "commit", "-q", "-m", "seed")
        self.tree = root / "tree"
        git(self.main, "worktree", "add", "-q", "-b", "run/x", str(self.tree))
        (root / "plain").mkdir()
        self.remote = root / "remote.git"
        git(root, "clone", "-q", "--bare", str(self.main), str(self.remote))

    def test_refusal_names_why_a_tree_cannot_take_commits(self):
        self.assertEqual(runbranch.refusal(self.main), runbranch.MAIN_TREE)
        self.assertEqual(runbranch.refusal(self.tree), "")
        git(self.tree, "checkout", "-q", "--detach")
        self.assertEqual(runbranch.refusal(self.tree), runbranch.DETACHED)

    def test_commit_stacks_only_real_changes_and_skips_the_excluded_path(self):
        before = git(self.tree, "rev-parse", "HEAD")
        self.assertEqual(runbranch.commit(self.tree, "none\n", "copy"), (False, before))
        (self.tree / "a.txt").write_text("two\n", encoding="utf-8")
        (self.tree / "copy").mkdir()
        (self.tree / "copy" / "c.txt").write_text("x\n", encoding="utf-8")
        changed, head = runbranch.commit(self.tree, "round\n", "copy")
        self.assertTrue(changed)
        self.assertNotEqual(head, before)
        self.assertEqual(head, git(self.tree, "rev-parse", "HEAD"))
        self.assertEqual(git(self.tree, "diff-tree", "--no-commit-id", "--name-only", "-r", head), "a.txt")
        self.assertEqual(git(self.tree, "log", "-1", "--format=%an|%ae|%s"), "works-factory|works-factory@localhost|round")

    def test_branch_names_and_pr_branches(self):
        self.assertEqual(runbranch.branch(self.tree), "run/x")
        self.assertEqual(runbranch.default_branch(self.tree, str(self.remote)), "trunk")
        self.assertEqual(runbranch.pr_branches(self.tree, str(self.remote)), ("run/x", "trunk", ""))

    def test_pr_branches_gives_a_reason_and_no_branch_when_it_cannot_push(self):
        name, base, reason = runbranch.pr_branches(self.main, str(self.remote))
        self.assertEqual((name, base, reason), ("", "", runbranch.MAIN_TREE))
        name, base, reason = runbranch.pr_branches(self.tree, str(self.remote.parent / "no-such"))
        self.assertEqual((name, base), ("", ""))
        self.assertIn("既定の枝を読めない", reason)
        git(self.main, "checkout", "-q", "--detach")  # git 2.44 以降は、ほかの worktree が使う枝への checkout -B を拒む
        git(self.tree, "checkout", "-q", "-B", "trunk")
        name, base, reason = runbranch.pr_branches(self.tree, str(self.remote))
        self.assertEqual((name, base), ("", ""))
        self.assertIn("同じ名", reason)
        with self.assertRaises(runbranch.GitFailed):
            runbranch.default_branch(self.tree, str(self.remote.parent / "no-such"))
        name, base, reason = runbranch.pr_branches(self.remote.parent / "plain", str(self.remote))
        self.assertEqual((name, base), ("", ""))
        self.assertIn("run の枝を読めない", reason)

    def test_git_never_prompts_and_keeps_a_given_ssh_command(self):
        probe = ("-c", "alias.e=!env")
        out = runbranch.git(self.main, *probe, "e", environ={"PATH": os.environ["PATH"]})
        self.assertIn("GIT_TERMINAL_PROMPT=0", out)
        self.assertIn("GIT_SSH_COMMAND=ssh -o BatchMode=yes", out)
        for given in ({"GIT_SSH_COMMAND": "mine"}, {"GIT_SSH": "mine"}):
            out = runbranch.git(self.main, *probe, "e", environ={"PATH": os.environ["PATH"], **given})
            self.assertNotIn("BatchMode", out)
        self.assertIn("GIT_SSH_COMMAND=mine", runbranch.git(self.main, *probe, "e", environ={"PATH": os.environ["PATH"], "GIT_SSH_COMMAND": "mine"}))


if __name__ == "__main__":
    unittest.main()

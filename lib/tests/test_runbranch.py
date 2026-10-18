"""run の枝へ commit を積む口（lib/runbranch.py）の commit_parts の検査。

縛る事:
- パスの並びの並びを順に 1 つずつの commit に積み、パスが多くても（引数の長さの上限を超える量でも）積める。パスは字のまま読む
- i 本目の git が落ちれば、積み始める前の HEAD に戻して何本目かを載せた PartFailed を投げる
- git の誤りでない例外でも、積み始める前の HEAD に戻してから投げ直す。作業ツリーの変更は残す
"""
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


if __name__ == "__main__":
    unittest.main()

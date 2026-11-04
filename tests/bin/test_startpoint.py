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

    def test_named_start_or_branch_and_flags_archon_refuses_with_from_add_nothing(self):
        (self.target / "untracked.txt").write_text("untracked\n", encoding="utf-8")
        valued = ("--from", "--from-branch", "--branch", "--base", "--adopt")
        cases = [*([f, "x"] for f in valued), *([f"{f}=x"] for f in valued),
                 *([f] for f in ("--no-worktree", "--folder", "--container", "--dry-run")),
                 ["-b", "x"], ["-bx"], ["-b=x"], ["-vb", "x"], ["--input", "request=x", "-qb", "x"]]
        for flags in cases:
            with self.subTest(flags=flags):
                self.assertEqual(startpoint.choose(flags, LINE, self.target, PREFIX), ([], ""))

    def test_other_flags_still_start_from_the_current_state(self):
        for flags in (["--input", "request=x"], ["-v"], ["--quiet"], ["--base-branch", "main"], ["--json"]):
            with self.subTest(flags=flags):
                self.assertEqual(startpoint.choose(flags, LINE, self.target, PREFIX)[0], ["--from", self.head])

    def test_graph_not_ours_adds_nothing(self):
        self.assertEqual(startpoint.choose([], "archon-fix-github-issue", self.target, PREFIX), ([], ""))

    def test_tree_without_commit_or_git_adds_nothing(self):
        empty = hermetic.tmpdir(self) / "empty"
        empty.mkdir()
        self.assertEqual(startpoint.choose([], LINE, empty, PREFIX), ([], ""))
        git(empty, "init", "-q")
        (empty / "a.txt").write_text("a\n", encoding="utf-8")
        self.assertEqual(startpoint.choose([], LINE, empty, PREFIX), ([], ""))


# ssh の代わりに起こす偽の口（GIT_SSH_COMMAND）。網に出ず、数えの置き場の回数だけ ssh が断られた時と同じに落ち、その後は手元の裸の
# リポジトリを upload-pack で答える。git は「<口> <host> "git-upload-pack '<path>'"」の形で起こす（GIT_SSH_VARIANT=simple で、口の種類を
# 確かめる -G の空打ちをさせない）。git が口に渡した GIT_TERMINAL_PROMPT の値を FLAKY_PROMPT の置き場に足す
FLAKY_SSH = """#!/bin/sh
echo "${GIT_TERMINAL_PROMPT-unset}" >> "$FLAKY_PROMPT"
count=$(cat "$FLAKY_COUNT" 2>/dev/null || echo 0)
echo $((count + 1)) > "$FLAKY_COUNT"
if [ "$count" -lt "$FLAKY_FAILS" ]; then
  echo "Connection closed by remote host" >&2
  exit 255
fi
exec git-upload-pack "$FLAKY_BARE"
"""


class OriginReachTest(unittest.TestCase):
    """Archon は新しい作業ツリーを切る前に、--from が在っても origin に問い合わせる。殻はその前に同じ問い合わせを打ち、一時の拒みは
    打ち直し、駄目なら訳を返す（bin/_lib/startpoint.py の unreachable）。網には出ない: 手元の裸のリポジトリと偽の ssh の口で照らす"""

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.target = self.tmp / "target"
        self.target.mkdir()
        git(self.target, "init", "-q", "-b", "main")
        git(self.target, "commit", "-q", "--allow-empty", "-m", "seed")
        self.bare = self.tmp / "origin.git"
        git(self.tmp, "init", "-q", "--bare", str(self.bare))
        git(self.target, "push", "-q", str(self.bare), "main")
        self.waits: list[float] = []
        self.env = hermetic.child_env()

    def unreachable(self, env=None) -> str:
        return startpoint.unreachable(self.target, env or self.env, sleep=self.waits.append)

    def flaky(self, fails: int) -> dict:
        ssh = self.tmp / "flaky-ssh"
        ssh.write_text(FLAKY_SSH, encoding="utf-8")
        ssh.chmod(0o755)
        git(self.target, "remote", "add", "origin", "ssh://origin.invalid/repo.git")
        return {**self.env, "GIT_SSH_COMMAND": str(ssh), "GIT_SSH_VARIANT": "simple", "FLAKY_COUNT": str(self.tmp / "count"),
                "FLAKY_FAILS": str(fails), "FLAKY_BARE": str(self.bare), "FLAKY_PROMPT": str(self.tmp / "prompt")}

    def test_reachable_origin_says_nothing(self):
        git(self.target, "remote", "add", "origin", str(self.bare))
        self.assertEqual(self.unreachable(), "")
        self.assertEqual(self.waits, [])

    def test_no_remote_is_left_to_archon(self):
        """remote の無い対象は Archon が自分の文で拒む（殻は確かめない）"""
        self.assertEqual(self.unreachable(), "")

    def test_unreachable_origin_is_retried_then_named(self):
        git(self.target, "remote", "add", "origin", str(self.tmp / "gone.git"))
        said = self.unreachable()
        self.assertIn("origin に届かない", said)
        self.assertIn(f"{startpoint.TRIES} 回", said)
        self.assertEqual(len(self.waits), startpoint.TRIES - 1)
        self.assertNotIn(str(self.tmp / "gone.git"), said.split("（", 1)[0])

    def test_transient_refusal_is_retried_until_it_answers(self):
        env = self.flaky(fails=startpoint.TRIES - 1)
        self.assertEqual(self.unreachable(env), "")
        self.assertEqual(len(self.waits), startpoint.TRIES - 1)
        self.assertEqual((self.tmp / "count").read_text().strip(), str(startpoint.TRIES))

    def test_refusal_that_lasts_is_named_with_the_reason(self):
        env = self.flaky(fails=startpoint.TRIES)
        said = self.unreachable(env)
        self.assertIn("origin に届かない", said)
        self.assertIn("Connection closed by remote host", said)

    def test_single_tries_once(self):
        git(self.target, "remote", "add", "origin", str(self.tmp / "gone.git"))
        self.assertIn("origin に届かない", startpoint.unreachable(self.target, self.env, sleep=self.waits.append, tries=1))
        self.assertEqual(self.waits, [])

    def test_sole_remote_not_named_origin_is_the_one_archon_uses(self):
        """Archon は origin が無ければ、ただ 1 つの remote を使う（packages/git/src/repo.ts の getDefaultRemote）"""
        git(self.target, "remote", "add", "upstream", str(self.tmp / "gone.git"))
        self.assertIn("upstream に届かない", self.unreachable())
        git(self.target, "remote", "add", "second", str(self.bare))
        self.assertEqual(self.unreachable(), "", "remote が 2 つ以上で origin が無ければ Archon が自分の文で拒む")

    def test_configured_remote_comes_first(self):
        """Archon は対象の .archon/config.yaml の worktree.remote を、origin より先に使う（packages/isolation/src/providers/worktree/create.ts
        の resolveRemote）。殻が読んで configured に渡す。空白だけの値は無いのと同じ（Archon も trim して空なら次の段へ進む）"""
        git(self.target, "remote", "add", "origin", str(self.bare))
        git(self.target, "remote", "add", "upstream", str(self.tmp / "gone.git"))
        said = startpoint.unreachable(self.target, self.env, sleep=self.waits.append, configured="upstream")
        self.assertIn("upstream に届かない", said)
        self.assertEqual(startpoint.unreachable(self.target, self.env, sleep=self.waits.append, configured=" \t"), "")
        git(self.target, "remote", "set-url", "origin", str(self.tmp / "gone.git"))
        git(self.target, "remote", "set-url", "upstream", str(self.bare))
        self.assertEqual(startpoint.unreachable(self.target, self.env, sleep=self.waits.append, configured=" upstream "), "",
                         "設定の remote に届けば、届かない origin は問わない")

    def test_configured_remote_that_is_not_there_points_at_the_settings(self):
        """設定が名指した remote が対象の git に無ければ、網や資格でなく remote の設定を確かめよと言う。在って届かない時は今の案内のまま"""
        git(self.target, "remote", "add", "origin", str(self.bare))
        said = startpoint.unreachable(self.target, self.env, sleep=self.waits.append, configured="upstream")
        self.assertIn("upstream に届かない", said)
        self.assertIn("upstream は対象の git の remote に無い。remote の設定", said)
        self.assertIn("worktree.remote", said)
        self.assertNotIn("網・ssh の鍵・資格", said)
        git(self.target, "remote", "add", "upstream", str(self.tmp / "gone.git"))
        said = startpoint.unreachable(self.target, self.env, sleep=self.waits.append, configured="upstream")
        self.assertIn("網・ssh の鍵・資格を確かめて打ち直す", said)
        self.assertNotIn("remote の設定", said)

    def test_query_never_asks_for_credentials_at_the_terminal(self):
        """問い合わせは利用者の env が GIT_TERMINAL_PROMPT を立てていても 0 で打つ（Archon の packages/git/src/credentials.ts の
        gitCredentialOptions と同じ。端末で資格を尋ねて止まらない）"""
        env = {**self.flaky(fails=0), "GIT_TERMINAL_PROMPT": "1"}
        self.assertEqual(self.unreachable(env), "")
        self.assertEqual((self.tmp / "prompt").read_text().split(), ["0"])

    def test_says_what_it_waits_for_before_asking(self):
        """問い合わせの前に、待つ物を 1 行渡す（期限は付けない）。確かめる remote が無ければ何も言わない"""
        said: list[str] = []
        self.assertEqual(startpoint.unreachable(self.target, self.env, say=said.append), "")
        self.assertEqual(said, [])
        env = self.flaky(fails=0)
        self.assertEqual(startpoint.unreachable(self.target, env, say=lambda line: said.append(
            f"{line}|{(self.tmp / 'count').exists()}")), "")
        self.assertEqual(len(said), 1, said)
        self.assertIn("origin に届くかを確かめている", said[0])
        self.assertIn("Ctrl-C", said[0])
        self.assertTrue(said[0].endswith("|False"), "問い合わせを打つ前に言う")


if __name__ == "__main__":
    unittest.main()

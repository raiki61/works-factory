"""メイングラフの頭のノード testcmd（workflows/line/scripts/testcmd.py）と、それを受けて run を止める cancel のノード testcmd-stop の試験（#678）。

test_cmd が対象の手元を試す形なら、AI を起こす前に run が頭で止まり（cancelled）、止める形の文と止めの理由が cancel の理由に出る。
形の見分けそのものは lib/tests/test_testcmd_check.py が縛る。
"""
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

import yaml

from tests import archon
from tests.bin.gitkit import committed_copy, git
from tests.bin.linescripts import SCRIPTS, load
from tests.e2e.test_line_scenarios import blocks

testcmd = load("testcmd")

import testcmd_check  # noqa: E402  （メイングラフの script が lib/ を sys.path に足した後に読む）

SEED = SCRIPTS.parents[2] / "tests" / "e2e" / "target-seed"
LINE = yaml.safe_load((SCRIPTS.parent / "works-factory-line.yaml").read_text(encoding="utf-8"))


class TestCmdNodeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name).resolve()
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, SEED)
        self.run_tree = self.worktree("run-tree")
        env = mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(self.tmp / "artifacts")})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(testcmd.ALLOW_ENV, None)

    def worktree(self, name: str) -> pathlib.Path:
        tree = self.tmp / name
        git(self.repo, "worktree", "add", "-q", "--detach", str(tree))
        return tree

    def test_the_allow_name_is_the_lib_name(self):
        self.assertEqual(testcmd.ALLOW_ENV, testcmd_check.ALLOW_ENV)

    def test_command_running_the_checkout_stops_with_the_lines(self):
        got = testcmd.check(f"cd {self.repo} && make test", self.run_tree)
        self.assertTrue(got["stop"], got)
        lines = got["reason"].splitlines()
        self.assertTrue(lines[0].startswith(f"{testcmd.STOP_HEAD}test_cmd の {self.repo} は対象の手元"), lines)
        self.assertIn(f"test_cmd が対象の手元（{self.repo}）を走らせる形なので、AI を起こす前に run を止めた", lines[-1])
        self.assertIn(f"{testcmd.ALLOW_ENV}=1", lines[-1])

    def test_the_run_tree_itself_is_not_a_checkout(self):
        self.assertTrue(testcmd.check(f"{self.repo}/stats.py", self.run_tree)["stop"])
        self.assertEqual(testcmd.check(f"{self.run_tree}/stats.py", self.run_tree), {"stop": False, "reason": ""})

    def test_a_linked_worktree_of_the_user_is_a_checkout_too(self):
        """利用者が git worktree add で作った作業ツリーを試す形も、主の作業ツリーと同じに止める"""
        mine = self.worktree("mine")
        got = testcmd.check(f"cd {mine} && make test", self.run_tree)
        self.assertTrue(got["stop"], got)
        self.assertTrue(got["reason"].startswith(f"{testcmd.STOP_HEAD}test_cmd の {mine} は対象の手元"), got)
        self.assertIn(f"対象の手元（{mine}）を走らせる形", got["reason"])

    def test_a_relative_word_the_tree_lacks_goes_on_with_a_notice(self):
        """作業ツリーに無い物（git が無視する物）を最初の語より後ろで相対で指す形は、起こす前の証明（lib/tree_run.prove_launchable）
        が見ないので、止めずに注意の行を残す"""
        (self.repo / "sub" / ".venv" / "bin").mkdir(parents=True)
        (self.repo / "sub" / ".venv" / "bin" / "run-tests").write_text("#!/bin/sh\n")
        with open(self.repo / ".gitignore", "a", encoding="utf-8") as f:
            f.write(".venv\n")
        got = testcmd.check("cd sub && .venv/bin/run-tests", self.run_tree)
        self.assertFalse(got["stop"], got)
        lines = got["reason"].splitlines()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(f"{testcmd.ALLOWED_HEAD}test_cmd の .venv/bin/run-tests（cd の後の "
                                            "sub/.venv/bin/run-tests） は対象の git が無視するパス"), lines)

    def test_allowed_or_quiet_commands_go_on(self):
        for cmd in ("", "  ", "make test", "cd sub && uv run pytest"):
            with self.subTest(cmd):
                self.assertEqual(testcmd.check(cmd, self.run_tree), {"stop": False, "reason": ""})
        with mock.patch.dict(os.environ, {testcmd.ALLOW_ENV: "1"}):
            got = testcmd.check(f"cd {self.repo} && make test", self.run_tree)
        self.assertFalse(got["stop"], got)
        self.assertTrue(got["reason"].startswith(testcmd.ALLOWED_HEAD), got)

    def test_a_check_that_fails_stops_unless_allowed(self):
        got = testcmd.fallback("OSError: 落ちた")
        self.assertTrue(got["stop"])
        self.assertIn("OSError: 落ちた", got["reason"])
        with mock.patch.dict(os.environ, {testcmd.ALLOW_ENV: "1"}):
            self.assertFalse(testcmd.fallback("OSError: 落ちた")["stop"])

    def test_the_head_comes_before_start_and_the_cancel_reads_it(self):
        nodes = {n["id"]: n for n in LINE["nodes"]}
        self.assertEqual(LINE["nodes"][0]["id"], "testcmd")
        self.assertEqual(nodes["testcmd-stop"]["cancel"], "$testcmd.output.reason")
        self.assertEqual(nodes["testcmd-stop"]["when"], "$testcmd.output.stop == true")
        self.assertEqual((nodes["start"]["depends_on"], nodes["start"]["when"]), (["testcmd"], "$testcmd.output.stop == false"))


class TestCmdHeadDryRunTest(unittest.TestCase):
    """Archon が頭のノードを走らせ、止める形なら run を cancelled にし、cancel の理由にノードの文が出る。許しで進めれば、注意の行が
    collect を通って報告のブロックへ届く（止めた Archon の dry-run の trace。源か bun が無ければ見送る）"""

    def dry_run(self, tree: pathlib.Path, test_cmd: str, **env) -> dict:
        done = archon.archon(tree, "workflow", "run", archon.PACK["ours"]["line"], "--dry-run", "--exec-code", "--json",
                             "--input", "request=x", "--input", f"test_cmd={test_cmd}", "--cwd", str(tree), **env)
        try:
            return json.JSONDecoder().raw_decode(done.stdout.lstrip())[0]
        except json.JSONDecodeError as error:
            raise AssertionError(f"dry-run の出力が読めない（{error}）: {done.stdout[-2000:]}{done.stderr[-2000:]}") from None

    def test_command_running_the_checkout_cancels_the_run_at_the_head(self):
        with archon.tree(["line", *blocks()]) as root:
            tree = root.parent / "run-tree"   # dry-run は作業ツリーを切らないので、run の作業ツリーの代わりを切って --cwd に渡す
            git(root, "worktree", "add", "-q", "--detach", str(tree))
            got = self.dry_run(tree, f"cd {root} && make test")
            trace = {n["nodeId"]: n for n in got["trace"]}
            self.assertEqual(got["outcome"], "cancelled", json.dumps(got, ensure_ascii=False)[:2000])
            self.assertNotIn("start", trace)
            reason = trace["testcmd-stop"]["resolvedText"]
            self.assertIn(f"{testcmd.STOP_HEAD}test_cmd の {root} は対象の手元", reason)
            self.assertIn("AI を起こす前に run を止めた", reason)
            allowed = self.dry_run(tree, f"cd {root} && make test", **{testcmd.ALLOW_ENV: "1"})
            trace = {n["nodeId"]: n for n in allowed["trace"]}
            self.assertEqual((trace["testcmd-stop"]["state"], trace["start"]["state"]), ("skipped", "completed"))
            notices = json.loads(trace["collect"]["output"])["notices"]   # 報告の冒頭に載せる行（lib/runreport.build）
            self.assertEqual(notices, json.loads(trace["testcmd"]["output"])["reason"].splitlines())
            self.assertTrue(notices[0].startswith(f"{testcmd.ALLOWED_HEAD}test_cmd の {root} は対象の手元"), notices)
            self.assertEqual(trace["report__facts"]["state"], "completed")


if __name__ == "__main__":
    unittest.main()

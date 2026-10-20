"""CI の節を盤面なしで走らせる口（lib/declared_checks.py）の検査。今の works の試験の場合を盤面なしで書き直した物で、各試験の
docstring に元の試験の名を書く（見比べられるように）。元の試験は tests/test_ci_test_cmd.py・tests/test_board_engine_run.py・
tests/test_blk_tests_delta.py（TestTestsModes）。

対象のリポジトリは tests/e2e/target-seed/ の写し（committed_copy）。宣言の段は子のプロセスを本当に起こす（この Python）。
盤面の記録（process.checks）と機械全体の試験の枠（slotted_run の slotwrap.sh）の場合は、その仕組みを持ってこないので写さない。
同じ run の中の控えの使い回し（ReuseCase）と、任せ先に落ちた後の test_cmd の使い回し（RunEngineCase）は盤面なしで書き直した。
"""
import json
import os
import pathlib
import shlex
import sys
import tempfile
import time
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
SEED = LIB.parent / "tests" / "e2e" / "target-seed"
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import checkscope  # noqa: E402
import declared_checks as dc  # noqa: E402
import gatemarks  # noqa: E402
import green_cert  # noqa: E402
import tree_run  # noqa: E402
from tests.bin.gitkit import committed_copy, git  # noqa: E402
from tests.blocks import kit  # noqa: E402

PY = sys.executable
GREEN = [{"name": "suite", "argv": [PY, "-c", "print('1 passed')"]}]
RED = [{"name": "suite", "argv": [PY, "-c", "import sys; print('1 failed'); sys.exit(3)"]}]
SCOPED = [{"name": "far", "argv": [PY, "-c", "print('far')"]}, {"name": "near", "argv": [PY, "-c", "print('near')"]}]
SCOPE = {"far": {"paths_ignore": ["works/"]}}
FAR_SKIPPED = [{"name": "far", "paths_ignore": ["works/"]}]
MISSING = "works-no-such-command-4f1c"


def fake_runner(calls, batches=None):
    """子のプロセスを起こさない runner: tree_runner と同じく log_dir/<段の番号>.out・.err を書く。argv に 'exit 1' で exit 1。
    calls に段の argv を、batches に呼ばれた 1 回ごとの段の名を積む（元 test_ci_test_cmd.py の _runner）"""
    def run(steps, cwd, log_dir, **_):
        if batches is not None:
            batches.append([s["name"] for s in steps])
        log_dir = pathlib.Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        for i, s in enumerate(steps, 1):
            calls.append(list(s["argv"]))
            out, err = log_dir / f"{i}.out", log_dir / f"{i}.err"
            out.write_text(f"{s['name']}-ran\n", encoding="utf-8")
            err.write_text("", encoding="utf-8")
            rows.append({"name": s["name"], "argv": list(s["argv"]), "out": str(out), "err": str(err), "started": 0.0,
                         "exit": 1 if "exit 1" in " ".join(s["argv"]) else 0, "wall_s": 0.0, "tail": f"{s['name']}-ran"})
        return rows
    return run


def never(*a, **kw):
    raise AssertionError(f"runner を呼んではいけない: {a}")


class RepoCase(unittest.TestCase):
    """対象のリポジトリ self.repo（種の写し）と run の置き場 self.work（対象の木の外）"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, SEED)
        self.work = self.tmp / "work"

    def decl(self, steps):
        (self.repo / dc.DECL_NAME).write_text(json.dumps({"suite": steps}), encoding="utf-8")

    def scope(self, scope):
        (self.repo / checkscope.SCOPE_DECL).write_text(json.dumps(scope), encoding="utf-8")

    def run_ci(self, test_cmd="", *, changed=None, after_judge=False, report=True, reuse=None):
        return dc.run_ci(self.repo, test_cmd=test_cmd, log_dir=self.work / "logs", changed=changed, after_judge=after_judge,
                         report_dir=self.work / "junit" if report else None, reuse=reuse)


class RunCiTestCmdRulesCase(RepoCase):
    """元 test_ci_test_cmd.py の RunCiTestCmdRulesCase"""

    def run_fake(self, steps, test_cmd):
        self.decl(steps)
        calls, self.batches = [], []
        with mock.patch.object(dc, "tree_runner", fake_runner(calls, self.batches)):
            got = self.run_ci(test_cmd)
        return got, calls

    def test_declared_and_red_test_cmd_is_found(self):
        """元 test_declared_and_red_test_cmd_is_found: 宣言が在っても test_cmd を黙って捨てない（AND の合成）"""
        got, _ = self.run_fake([{"name": "decl", "argv": ["decl"]}], "exit 1")
        self.assertEqual(got["material"]["status"], "found")

    def test_declared_and_green_test_cmd_runs_both_in_one_runner_call(self):
        """元 test_declared_and_green_test_cmd_runs_both_in_one_runner_call"""
        got, calls = self.run_fake([{"name": "decl", "argv": ["decl"]}], "true")
        self.assertEqual((got["by"], got["material"]["status"]), ("engine", "clean"))
        self.assertEqual([r["name"] for r in got["runs"]], ["decl", dc.TEST_CMD_STEP])
        self.assertIn("true", " ".join(calls[-1]))
        self.assertEqual(self.batches, [["decl", dc.TEST_CMD_STEP]], "runner を steps + [test_cmd の段] の 1 回で呼んでいない")

    def test_same_command_as_declared_step_runs_once(self):
        """元 test_same_command_as_declared_step_runs_once"""
        got, calls = self.run_fake([{"name": "suite", "argv": ["run-tests", "-q"]}], "run-tests -q")
        self.assertEqual(calls, [["run-tests", "-q"]])
        self.assertEqual(got["same_as"], "suite")
        line = dc.suites_line({"by": "engine", "suites": [{"name": "suite", "exit": 0}], "test_cmd_same_as": "suite"})
        self.assertIn("宣言の段 suite と同じコマンドなので 1 度だけ", line)
        self.assertNotIn("渡されていない", line)

    def test_different_command_runs_both_with_separate_logs(self):
        """元 test_different_command_runs_both_with_separate_logs"""
        self.decl([{"name": "suite", "argv": [PY, "-c", "print('decl')"]}])
        got = self.run_ci(f"{PY} -c \"print('cmd')\"")
        self.assertIsNone(got["same_as"])
        self.assertEqual([r["name"] for r in got["runs"]], ["suite", dc.TEST_CMD_STEP])
        logs = sorted((self.work / "logs").glob("*.out"))
        self.assertEqual([p.read_text(encoding="utf-8") for p in logs], ["decl\n", "cmd\n"],
                         "test_cmd の段のログが宣言の段のログを上書きする")
        self.assertIn("cmd", pathlib.Path(got["log"]).read_text(encoding="utf-8"))


class RunHowCase(RepoCase):
    """#687: 直す前のテストの走らせ方の行（run_how。修正役の材料）は、根と、実際に走った宣言の段と test_cmd の命令を字のまま言う"""

    def test_engine_steps_and_test_cmd(self):
        self.decl([{"name": "suite", "argv": [PY, "-c", "print('decl')"]}])
        cmd = f"{PY} -c \"print('cmd')\""
        got = self.run_ci(cmd)
        rows = dc.run_how(self.repo, got, test_cmd=cmd, material=got["material"])
        self.assertIn(f"`{self.repo}`", rows[0])
        self.assertTrue(any(r.startswith("宣言") and "段 suite" in r and f"`{PY} -c " in r for r in rows), rows)
        self.assertTrue(any(r.startswith(f"test_cmd: `{cmd}`") for r in rows), rows)

    def test_test_cmd_alone_and_the_ci_role(self):
        got = self.run_ci("echo 走った")
        rows = dc.run_how(self.repo, got, test_cmd="echo 走った", material=got["material"])
        self.assertEqual(len(rows), 2, rows)
        self.assertTrue(rows[1].startswith("test_cmd: `echo 走った`"), rows)
        role = {"by": dc.ROLE_NEEDED, "runs": []}
        rows = dc.run_how(self.repo, role, test_cmd="", material={"status": "clean", "checked": "make test（終了コード 0）"})
        self.assertEqual(rows[1], "AI が書いた実行器が走らせた物: make test（終了コード 0）")


class LaunchHowRecordedCase(RepoCase):
    """元 test_ci_test_cmd.py の LaunchHowRecordedCase: 起こし方 how は起こす所で 1 度だけ決めて走った行に載せ、読む所は規則で作り直さない"""

    def rule(self):
        real = tree_run.command_argv
        first = iter([real("a | b")])
        return mock.patch.object(tree_run, "command_argv", side_effect=lambda c: next(first, (["zz"], "direct")))

    def test_launch_wrapper_stamps_how_on_rows_it_ran(self):
        """元 test_launch_wrapper_stamps_how_on_rows_it_ran"""
        for cmd, hows in (("a | b", ["direct", "shell"]), ("", ["direct"])):
            with self.subTest(cmd=cmd), mock.patch.object(tree_run, "run", return_value=0):
                rows = dc._with_test_cmd(None, cmd, {})([{"name": "decl", "argv": ["decl"]}], self.tmp, self.tmp / (cmd or "x"))
            self.assertEqual([r["how"] for r in rows], hows)

    def test_engine_runs_carry_how_decided_at_launch(self):
        """元 test_engine_runs_carry_how_decided_at_launch"""
        self.decl([{"name": "decl", "argv": ["decl"]}])
        with self.rule(), mock.patch.object(tree_run, "run", return_value=0):
            got = self.run_ci("a | b")
        self.assertEqual(got["runs"], [{"name": "decl", "exit": 0, "how": "direct"},
                                       {"name": dc.TEST_CMD_STEP, "exit": 0, "how": "shell"}])
        self.assertIn(f"{dc.TEST_CMD_STEP}（起こし方 shell）", pathlib.Path(got["log"]).read_text(encoding="utf-8"))

    def test_role_material_reads_how_decided_at_launch(self):
        """元 test_fallback_material_reads_how_from_ran_row_not_from_rule（宣言の無い run の test_cmd の素材）"""
        with self.rule(), mock.patch.object(tree_run, "run", return_value=1):
            got = self.run_ci("a | b")
        self.assertEqual((got["by"], got["test_cmd_how"]), ("role", "shell"))
        self.assertIn("bash -c 'a | b'（起こし方 shell）", got["material"]["detail"])
        line = dc.suites_line({"by": got["by"], "suites": got["runs"], "test_cmd_how": got["test_cmd_how"]})
        self.assertIn(f"走らせた: {dc.TEST_CMD_STEP}（shell）", line)


class SuitesLineCase(unittest.TestCase):
    """元 test_ci_test_cmd.py の OutOfScopeLineCase・EnvFailureLineCase と LaunchKindCase の行の場合"""

    def test_skipped_steps_are_named_with_their_ignored_paths(self):
        """元 OutOfScopeLineCase.test_skipped_steps_are_named_with_their_ignored_paths"""
        tests = {"by": "engine", "suites": [{"name": "near", "exit": 0}],
                 "skipped_steps": [{"name": "far", "paths_ignore": ["works/", "docs"]}]}
        ran, unrun = dc.suites_line(tests).split("／走らせなかった: ")
        self.assertNotIn("far", ran)
        self.assertIn("範囲の外で回さなかった段 far（変更が全部 works/・docs の下で、段が見ない所）", unrun)

    def test_unlaunchable_step_is_named_apart_from_code_red(self):
        """元 EnvFailureLineCase.test_unlaunchable_step_is_named_apart_from_code_red"""
        tests = {"by": "engine", "suites": [{"name": "suite", "exit": 0}, {"name": "test_cmd", "exit": None}]}
        self.assertIn("環境で起こせなかった（コードの赤ではない）: test_cmd（起こせない）", dc.suites_line(tests))

    def test_missing_command_127_is_red_like_the_material(self):
        """元 EnvFailureLineCase.test_missing_command_127_is_red_like_the_material"""
        tests = {"by": "engine", "suites": [{"name": "suite", "exit": 0}, {"name": "test_cmd", "exit": 127}]}
        self.assertIn("test_cmd（exit 127）", dc.suites_line(tests))

    def test_code_red_is_not_env(self):
        """元 EnvFailureLineCase.test_code_red_is_not_env"""
        tests = {"by": "engine", "suites": [{"name": "suite", "exit": 1}, {"name": "test_cmd", "exit": None}]}
        self.assertIn("suite（exit 1）", dc.suites_line(tests))

    def test_suites_line_reads_shell_exit_127_as_code_red(self):
        """元 LaunchKindCase.test_suites_line_reads_shell_exit_127_as_code_red"""
        for launch in ({}, {"launch": "suspect"}):
            with self.subTest(launch=launch):
                tests = {"by": "engine", "test_cmd_how": "shell",
                         "suites": [{"name": "suite", "exit": 0}, {"name": dc.TEST_CMD_STEP, "exit": 127, **launch}]}
                line = dc.suites_line(tests)
                self.assertIn(f"{dc.TEST_CMD_STEP}（exit 127・shell）", line)
                self.assertNotIn("環境で起こせなかった", line)

    def test_role_status_words(self):
        """元 entry.suites_line の書き分け: 任せ先の役の素材が clean・found なら役が選んだ一式を走らせたと書き、ほかの status・素材が
        無い・役がまだ渡していない回は走らせなかった側に書く。宣言が読めない engine と、test_cmd の段が無い engine も名指す"""
        role = {"by": "role_needed", "suites": []}
        for status, ran, unran in (
                ("clean", "AI が書いた実行器が選んだ、変更に関わる試験（素材の status clean）", f"宣言の段・{dc.TEST_CMD_STEP}（渡されていない）・全体の試験（CI と人に任せた）"),
                ("found", "AI が書いた実行器が選んだ、変更に関わる試験（素材の status found）", f"宣言の段・{dc.TEST_CMD_STEP}（渡されていない）・全体の試験（CI と人に任せた）"),
                ("not_run", "無い", f"宣言の段・{dc.TEST_CMD_STEP}（渡されていない）・変更に関わる試験（実行器が走らせなかった: 素材の status not_run）"),
                ("", "無い", f"宣言の段・{dc.TEST_CMD_STEP}（渡されていない）・変更に関わる試験（実行器が走らせなかった: 素材の status 無い）"),
                (None, "無い", f"宣言の段・{dc.TEST_CMD_STEP}（渡されていない）・変更に関わる試験（実行器が走らせる）")):
            with self.subTest(status=status):
                self.assertEqual(dc.suites_line(role, role_status=status), f"走らせた: {ran}／走らせなかった: {unran}")
        self.assertIn(f"宣言の段・{dc.TEST_CMD_STEP}（宣言が読めないので engine が走らせなかった）",
                      dc.suites_line({"by": "engine", "suites": []}))
        self.assertIn(f"{dc.TEST_CMD_STEP}（渡されていない）", dc.suites_line({"by": "engine", "suites": [{"name": "suite", "exit": 0}]}))

    def test_unlaunched_direct_step_names_how_to_wrap_in_bash(self):
        """元 LaunchKindCase.test_unlaunched_direct_step_names_how_to_wrap_in_bash（行の分）"""
        tests = {"by": "engine", "suites": [{"name": dc.TEST_CMD_STEP, "exit": None, "how": "direct", "launch": "broken"}]}
        line = dc.suites_line(tests)
        self.assertIn(f"{dc.TEST_CMD_STEP}（起こせない・direct）", line)
        self.assertIn(tree_run.DIRECT_HINT, line)

    def test_suites_line_does_not_judge_shell_by_step_name(self):
        """元 LaunchKindCase.test_suites_line_does_not_judge_shell_by_step_name"""
        for name in ("cmd", dc.TEST_CMD_STEP):
            with self.subTest(name=name):
                line = dc.suites_line({"by": "engine", "suites": [{"name": name, "exit": 127}]})
                self.assertNotIn("環境で起こせなかった", line)


class CmdMaterialCase(unittest.TestCase):
    """元 test_ci_test_cmd.py の BaselineNotRunCase・LaunchKindCase の素材の場合"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.log = self.tmp / "t.log"
        self.log.write_text("末尾\n", encoding="utf-8")

    def test_test_cmd_red_says_unverified(self):
        """元 BaselineNotRunCase.test_test_cmd_red_says_unverified: test_cmd の赤は found のまま、走ったかは確かめていないと添える"""
        m = dc._cmd_material(1, self.log, ["bash", "-c", "x"], "shell")["material"]
        self.assertEqual(m["status"], "found")
        self.assertIn(gatemarks.BASELINE_UNVERIFIED, m["detail"])

    def test_material_of_unlaunched_cmd_is_not_run(self):
        """元 LaunchKindCase.test_material_of_unlaunched_cmd_is_not_run"""
        self.assertEqual(dc._cmd_material(None, self.log, *tree_run.command_argv("run-tests"))["material"]["status"], "not_run")

    def test_material_of_exit_126_127_is_code_red(self):
        """元 LaunchKindCase.test_material_of_exit_126_127_is_code_red"""
        for cmd in ("run-tests", "run-tests | tee out"):
            for code in (126, 127):
                with self.subTest(cmd=cmd, code=code):
                    m = dc._cmd_material(code, self.log, *tree_run.command_argv(cmd))["material"]
                    self.assertEqual((m["status"], m["count"]), ("found", 1))

    def test_material_of_direct_same_as_step_127_is_code_red(self):
        """元 LaunchKindCase.test_material_of_direct_same_as_step_127_is_code_red"""
        m = dc._cmd_material(127, self.log, ["run-tests", "-q"], "direct")["material"]
        self.assertEqual(m["status"], "found")
        self.assertNotIn("bash -c", m["detail"])

    def test_unlaunched_material_names_how_to_wrap_in_bash(self):
        """元 LaunchKindCase.test_unlaunched_direct_step_names_how_to_wrap_in_bash（素材の分）"""
        m = dc._cmd_material(None, self.log, ["run-tests"], "direct")["material"]
        self.assertIn(tree_run.DIRECT_HINT, m["reason"])
        shell = dc._cmd_material(None, self.log, ["bash", "-c", "run-tests | tee x"], "shell")["material"]
        self.assertNotIn(tree_run.DIRECT_HINT, shell["reason"])

    def test_test_cmd_callers_launch_by_command_argv(self):
        """元 LaunchKindCase.test_test_cmd_callers_launch_by_command_argv"""
        for cmd, argv, how in (("run-tests -q tests", ["run-tests", "-q", "tests"], "direct"),
                               ("run-tests && lint", ["bash", "-c", "run-tests && lint"], "shell")):
            with self.subTest(cmd=cmd):
                seen = []
                with mock.patch.object(tree_run, "run", lambda a, **_: seen.append(a) or 0):
                    m = dc.local_checks_material(self.tmp, cmd, self.log)["material"]
                self.assertEqual((seen, m["status"]), ([argv], "clean"))
                steps = []
                dc._with_test_cmd(lambda s, *_, **__: steps.extend(s) or [], cmd, {})([], self.tmp, self.tmp)
                self.assertEqual(steps, [{"name": dc.TEST_CMD_STEP, "argv": argv, "how": how}])

    def test_empty_test_cmd_is_not_run_without_launching(self):
        with mock.patch.object(tree_run, "run", never):
            self.assertEqual(dc.local_checks_material(self.tmp, "  ", self.log)["material"]["status"], "not_run")


class LaunchProofCase(unittest.TestCase):
    """元 test_ci_test_cmd.py の LaunchProofCase: test_cmd を起こせないことは起こす前に確かめ、not_run（環境）にする（子のプロセスを本当に起こす）"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)

    def material(self, cmd):
        return dc.local_checks_material(self.tmp, cmd, self.tmp / "logs" / "t.log")["material"]

    def test_material_of_missing_command_is_not_run(self):
        """元 test_material_of_missing_command_is_not_run"""
        self.assertEqual(self.material(f"{MISSING} -q")["status"], "not_run")

    def test_material_of_missing_command_behind_env_prefix_is_not_run(self):
        """元 test_material_of_missing_command_behind_env_prefix_is_not_run"""
        self.assertEqual(self.material(f"FOO=1 {MISSING} -q")["status"], "not_run")

    def test_material_of_missing_command_in_pipeline_is_not_run(self):
        """元 test_material_of_missing_command_in_pipeline_is_not_run"""
        self.assertEqual(self.material(f"{MISSING} -q | cat")["status"], "not_run")

    def test_material_of_non_executable_file_is_not_run(self):
        """元 test_material_of_non_executable_file_is_not_run"""
        script = self.tmp / "t.sh"
        script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        script.chmod(0o644)
        self.assertEqual(self.material("./t.sh")["status"], "not_run")


class RunEngineCase(RepoCase):
    """元 test_board_engine_run.py の RunEngineCase（盤面の run_engine の代わりに run_ci を本物の段で）"""

    def reported_step(self, cases, code, name="suite"):
        """試験の報告 report.xml を宣言した段: cases（<testcase> の並び）を書いて code で終わる。cases が None なら何も書かない"""
        body = "" if cases is None else f"open('report.xml','w').write({f'<testsuite>{cases}</testsuite>'!r});"
        return {"name": name, "argv": [PY, "-c", f"import sys;{body}sys.exit({code})"], "junit": "report.xml"}

    def material_for(self, step, before=None, after_judge=False):
        self.decl([step])
        report = self.repo / "report.xml"
        report.unlink(missing_ok=True)
        if before:
            report.write_text(before[0], encoding="utf-8")
            old = report.stat().st_mtime - before[1]
            os.utime(report, (old, old))
        return self.run_ci(after_judge=after_judge)["material"]

    def test_red_suite_found(self):
        """元 test_red_suite_found: 赤の段 → found・count 1（判定の前でも人待ちに化けない）"""
        self.decl(RED)
        got = self.run_ci()
        self.assertEqual((got["material"]["status"], got["material"]["count"]), ("found", 1))
        self.assertIn("1 failed", got["material"]["detail"])
        self.assertEqual(got["runs"], [{"name": "suite", "exit": 3, "how": "direct"}])

    def test_unran_step_is_not_found(self):
        """元 test_unran_step_is_not_found: 報告を宣言した段が試験を走らせていない形は、赤でなく走らせられない status。唯一の段の
        試験が始まらなかった形は 1 段も走らなかった base なので、判定の前も後も not_run（理由に走らなかった訳）。試験が全部 error の
        段は報告に試験が並んだ（実行器が試験を集めた）形（直したいコードの import の誤りなど）なので、判定の前は awaiting_human で止めずに判定へ進む。終了コードの
        数値でなく件数で分ける"""
        stale = "<testsuite><testcase name='t'><failure/></testcase></testsuite>"
        cases = [(self.reported_step("", 5), None, "試験が 0 件", "not_run"),
                 (self.reported_step("<testcase name='t'><error/></testcase>", 1), None, "全部 error", "awaiting_human"),
                 (self.reported_step(None, 4), None, "report.xml が無い", "not_run"),
                 (self.reported_step(None, 1), (stale, 3600), "段の起動より古い", "not_run"),
                 (self.reported_step("<testcase", 2), None, "XML として読めない", "not_run")]
        for after_judge in (False, True):
            for step, before, want, base_status in cases:
                with self.subTest(want, after_judge=after_judge):
                    m = self.material_for(step, before, after_judge)
                    self.assertEqual(m["status"], "not_run" if after_judge else base_status, m)
                    self.assertIn("基準の検査が走らなかった", m["reason"])
                    self.assertIn(want, m["reason"])
                    self.assertNotIn("count", m)
        noisy = {"name": "suite", "argv": [PY, "-c", "import sys; print('config missing', file=sys.stderr); sys.exit(3)"],
                 "junit": "report.xml"}
        missing = {"name": "gone", "argv": [str(self.tmp / "no-such-command")]}
        for after_judge in (False, True):
            with self.subTest("唯一の JUnit の段が道具の誤りで落ちた", after_judge=after_judge):
                m = self.material_for(noisy, None, after_judge)
                self.assertEqual(m["status"], "not_run", m)
                self.assertIn("config missing", m["reason"])
            with self.subTest("全部が起こせない", after_judge=after_judge):
                self.decl([missing, {**missing, "name": "gone2"}])
                m = self.run_ci(after_judge=after_judge)["material"]
                self.assertEqual(m["status"], "not_run", m)
                self.assertIn("宣言の語を起こせない", m["reason"])
                self.assertIn("gone2", m["reason"])
            with self.subTest("起こせない段と試験を走らせなかった段しか無い", after_judge=after_judge):
                self.decl([missing, {**noisy, "name": "reported"}])
                m = self.run_ci(after_judge=after_judge)["material"]
                self.assertEqual(m["status"], "not_run", m)
                self.assertIn("config missing", m["reason"])
        partly = [("起こせない段と緑の段", [missing, GREEN[0]]), ("走らなかった段と緑の段", [self.reported_step("", 0, "empty"), GREEN[0]])]
        for after_judge, status in ((False, "awaiting_human"), (True, "not_run")):
            for name, steps in partly:
                with self.subTest(name, after_judge=after_judge):
                    self.decl(steps)
                    (self.repo / "report.xml").unlink(missing_ok=True)
                    m = self.run_ci(after_judge=after_judge)["material"]
                    self.assertEqual(m["status"], status, m)

    def test_ran_red_wins_over_unran_step(self):
        """#370: 走った段の赤は、ほかの段が走らなかったことに隠されない。found にし、走らなかった段の訳を detail に添える"""
        def step(name, report, cases, code):
            body = "" if cases is None else f"open({report!r},'w').write({f'<testsuite>{cases}</testsuite>'!r});"
            return {"name": name, "argv": [PY, "-c", f"import sys;{body}sys.exit({code})"], "junit": report}
        for after_judge in (False, True):
            with self.subTest(after_judge=after_judge):
                self.decl([step("unit", "unit.xml", "<testcase name='t'><failure/></testcase>", 1),
                           step("integ", "integ.xml", None, 2)])
                for name in ("unit.xml", "integ.xml"):
                    (self.repo / name).unlink(missing_ok=True)
                m = self.run_ci(after_judge=after_judge)["material"]
                self.assertEqual((m["status"], m["count"]), ("found", 1), m)
                self.assertIn("unit の末尾", m["detail"])
                self.assertIn("基準の検査が走らなかった段（コードの赤ではない）: integ: 報告 integ.xml が無い", m["detail"])

    def test_ran_red_step_is_found(self):
        """元 test_ran_red_step_is_found: 報告に走った試験と failure が在る段は、終了コードが何でも found"""
        m = self.material_for(self.reported_step("<testcase name='t'><failure/></testcase>", 5))
        self.assertEqual((m["status"], m["count"]), ("found", 1))
        self.assertNotIn("走ったかは確かめていない", m["detail"])

    def test_ran_green_step_is_clean(self):
        """元 test_ran_green_step_is_clean"""
        self.assertEqual(self.material_for(self.reported_step("<testcase name='t'/>", 0))["status"], "clean")

    def test_red_step_without_report_says_unverified(self):
        """元 test_red_step_without_report_says_unverified"""
        self.decl(RED)
        self.assertIn("走ったかは確かめていない（試験の報告の宣言が無い段: suite）", self.run_ci()["material"]["detail"])

    def test_junit_key_is_checked_by_parse(self):
        """元 test_junit_key_is_checked_by_parse"""
        step = {"name": "a", "argv": ["x"]}
        steps, err = dc.declared.parse(json.dumps({"suite": [{**step, "junit": "out/r.xml"}]}))
        self.assertIsNone(err)
        self.assertEqual(steps, [{**step, "junit": "out/r.xml"}])
        for bad in ("", "/abs.xml", "../r.xml", 3):
            with self.subTest(bad):
                self.assertIsNone(dc.declared.parse(json.dumps({"suite": [{**step, "junit": bad}]}))[0])

    def test_no_declaration_falls_back(self):
        """元 test_no_declaration_falls_back と test_blk_tests_delta.py の test_final_empty_cmd_on_fallback_role_needed:
        宣言が無く test_cmd も空なら何も走らせず role_needed。素材を渡さない（前の結果を緑に使わない）"""
        with mock.patch.object(dc, "tree_runner", never), mock.patch.object(tree_run, "run", never):
            got = self.run_ci(" ")
        self.assertEqual((got["by"], got["material"], got["runs"], got["log"]), ("role_needed", None, [], ""))

    def test_no_declaration_runs_test_cmd_by_role(self):
        """元 test_blk_tests_delta.py の test_final_fallback_runs_cmd: 宣言が無ければ test_cmd だけを走らせた素材（by role）"""
        for cmd, status in (("echo 走った", "clean"), ("echo 赤; exit 2", "found")):
            with self.subTest(cmd=cmd):
                got = self.run_ci(cmd)
                self.assertEqual((got["by"], got["material"]["status"], got["runs"]), ("role", status, []))
                self.assertIn(cmd.split(";")[0].split()[-1], pathlib.Path(got["log"]).read_text(encoding="utf-8"))

    def test_broken_declaration_is_blocked_without_running(self):
        """元 test_blocked_builds_reply_without_running: 宣言の書式の誤りは走らせず、走らせられない素材に誤りを書く"""
        (self.repo / dc.DECL_NAME).write_text('{"suite": []}', encoding="utf-8")
        for after_judge, status in ((False, "awaiting_human"), (True, "not_run")):
            with self.subTest(after_judge=after_judge), mock.patch.object(dc, "tree_runner", never):
                got = self.run_ci(after_judge=after_judge)
                self.assertEqual((got["by"], got["material"]["status"], got["runs"]), ("engine", status, []))
                self.assertIn(dc.DECL_NAME, got["material"]["reason"])
                self.assertIn("走らせなかった", pathlib.Path(got["log"]).read_text(encoding="utf-8"))


    def rewriting_step(self, once: bool) -> dict:
        """走ると宣言のファイルに段を 1 つ足して書き換える段（対象の木の外の script）。once なら 1 度目だけ書き換える"""
        script = self.tmp / "rewrite.py"
        script.write_text(
            "import json, os, sys\n"
            f"mark = {str(self.tmp / 'rewrote')!r}\n"
            f"if {once!r} and os.path.exists(mark):\n    sys.exit(0)\n"
            "open(mark, 'a').write('1')\n"
            f"path = {str(self.repo / dc.DECL_NAME)!r}\n"
            "doc = json.load(open(path))\n"
            f"doc['suite'].append({{'name': 'added%d' % len(doc['suite']), 'argv': [{PY!r}, '-c', 'pass']}})\n"
            "json.dump(doc, open(path, 'w'))\n", encoding="utf-8")
        return {"name": "suite", "argv": [PY, str(script)]}

    def test_declaration_changed_after_plan_is_replanned_once(self):
        """元 entry.run_ci の relaunch: 走らせた段が宣言を書き換えたら（計画の sha と違う）計画し直して 1 度だけ走らせ直す。素材は
        書き換えた後の宣言から組み、前の走りのログは上書きしない"""
        self.decl([self.rewriting_step(once=True)])
        got = self.run_ci()
        self.assertEqual([r["name"] for r in got["runs"]], ["suite", "added1"])
        self.assertEqual(got["material"]["status"], "clean")
        self.assertIn(f"sha {dc.declared.read(self.repo)['sha'][:12]}", got["material"]["checked"])
        self.assertTrue((self.work / "logs" / "1.out").is_file())
        self.assertTrue((self.work / "logs" / "replan" / "2.out").is_file())

    def test_declaration_changing_twice_is_refused(self):
        """元 entry.run_ci の relaunch の 2 度目: 計画し直しても宣言がまた変われば CiRefused（止める理由に宣言の名）"""
        self.decl([self.rewriting_step(once=False)])
        with self.assertRaises(dc.CiRefused) as cm:
            self.run_ci()
        self.assertIn("2 度変わった", str(cm.exception))
        self.assertIn(dc.DECL_NAME, str(cm.exception))

    def test_clean_names_declaration_sha_and_steps(self):
        """元 review-loop.py の checks_reply の clean: 何を根拠にした緑かを残す——走らせた宣言の sha の頭 12 字と段ごとの終了コードと秒"""
        self.decl(GREEN)
        checked = self.run_ci()["material"]["checked"]
        self.assertIn(f"sha {dc.declared.read(self.repo)['sha'][:12]}", checked)
        self.assertIn("suite: exit 0（", checked)

    def all_materials(self):
        """run_ci の道ごとの (名, after_judge, 返り): engine の clean・found・宣言の誤り・起こせない段・JUnit の走らなかった段・範囲で外した段、
        by role の clean・found・起こせない test_cmd"""
        missing = [self.tmp / "no-such-command"]
        cases = [("clean", GREEN, ""), ("found", RED, ""), ("broken", '{"suite": []}', ""),
                 ("unlaunchable", [{"name": "suite", "argv": [str(m) for m in missing]}], ""),
                 ("unran", [self.reported_step("", 0)], ""), ("scoped", SCOPED, ""),
                 ("role clean", None, "true"), ("role found", None, "exit 2"), ("role unlaunchable", None, f"{MISSING} -q")]
        for name, steps, cmd in cases:
            for after_judge in (False, True):
                (self.repo / dc.DECL_NAME).unlink(missing_ok=True)
                (self.repo / checkscope.SCOPE_DECL).unlink(missing_ok=True)
                if isinstance(steps, str):
                    (self.repo / dc.DECL_NAME).write_text(steps, encoding="utf-8")
                elif steps is not None:
                    self.decl(steps)
                if name == "scoped":
                    self.scope(SCOPE)
                yield name, after_judge, self.run_ci(cmd, changed=lambda: ["works/a.py"], after_judge=after_judge)

    def test_engine_material_meets_material_problems(self):
        """run_ci が組む素材は、どの道でも任せ先の役の素材と同じ欄の決まり（material_problems）を通る（走らせられない status も形に合う）"""
        for name, after_judge, got in self.all_materials():
            with self.subTest(name, after_judge=after_judge):
                self.assertIsNotNone(got["material"])
                self.assertEqual(dc.material_problems(got["material"], mode=dc.MODES[after_judge]), [], got["material"])

    def test_engine_material_that_breaks_the_rules_falls_back_without_rerunning_test_cmd(self):
        """元 board._accept_engine_reply・_fall_back・entry._ci_by_cmd: engine の素材が決まりに外れれば任せ先に落とす。engine が既に
        走らせた test_cmd の段の結果から素材を組み、test_cmd を 2 度走らせない。test_cmd が無ければ任せ先の役が渡す（素材 None）"""
        count = self.tmp / "count"
        cmd = f"{PY} -c \"open({str(count)!r}, 'a').write('1')\""
        self.decl(GREEN)
        with mock.patch.object(dc, "checks_reply", return_value={"status": "clean"}):
            got = self.run_ci(cmd)
            self.assertEqual((got["by"], got["material"]["status"]), ("role", "clean"))
            self.assertEqual(count.read_text(encoding="utf-8"), "1", "test_cmd を 2 度走らせた")
            self.assertIn("checked", got["fell_back"])
            empty = self.run_ci("")
        self.assertEqual((empty["by"], empty["material"]), ("role_needed", None))
        self.assertIn("checked", empty["fell_back"])


class ScopedStepsCase(RepoCase):
    """元 test_board_engine_run.py の ScopedStepsCase と test_blk_tests_delta.py の TestTestsModes の範囲の場合"""

    def test_scope_without_review_declaration_stops(self):
        """元 test_scope_without_review_declaration_stops: 範囲の宣言だけが在れば、任せ先に落とさず名指して止める。何も走らせない"""
        self.scope(SCOPE)
        with mock.patch.object(tree_run, "run", never), self.assertRaises(dc.CiRefused) as cm:
            self.run_ci("true")
        self.assertIn(checkscope.SCOPE_DECL, str(cm.exception))
        self.assertIn(dc.DECL_NAME, str(cm.exception))

    def test_declared_step_named_like_the_factory_step_stops_before_running(self):
        """#531: 宣言の段の名が TEST_CMD_STEP なら、何も走らせずに 1 行の訳で CiRefused（名で段を引く所が取り違えない）"""
        self.decl([{"name": dc.TEST_CMD_STEP, "argv": [PY, "-c", "pass"]}])
        with mock.patch.object(dc, "tree_runner", never), self.assertRaises(dc.CiRefused) as cm:
            self.run_ci("true")
        self.assertIn(dc.TEST_CMD_STEP, str(cm.exception))
        self.assertNotIn("\n", str(cm.exception))

    def test_scope_naming_an_undeclared_step_stops_before_running(self):
        """元 test_scope_naming_an_undeclared_step_stops_before_running"""
        self.decl(SCOPED)
        self.scope({"nope": {"paths_ignore": ["works/"]}})
        with mock.patch.object(dc, "tree_runner", never), self.assertRaises(dc.CiRefused) as cm:
            self.run_ci(changed=lambda: ["works/a.py"])
        self.assertIn("nope", str(cm.exception))
        self.assertIn(checkscope.SCOPE_DECL, str(cm.exception))

    def test_final_skips_step_whose_ignored_paths_hold_every_change(self):
        """元 test_blk_tests_delta.py の test_final_skips_step_whose_ignored_paths_hold_every_change と
        test_board_engine_run.py の test_change_all_under_ignored_skips_step_and_names_it: 回さなかった段を名と範囲で素材と返りに残す"""
        self.decl(SCOPED)
        self.scope(SCOPE)
        got = self.run_ci(changed=lambda: ["works/a.py"], after_judge=True)
        self.assertEqual([r["name"] for r in got["runs"]], ["near"])
        self.assertEqual(got["skipped_steps"], FAR_SKIPPED)
        self.assertEqual(got["material"]["status"], "clean")
        self.assertIn("範囲の外で回さなかった段: far（変更が全部 works/ の下で、段が見ない所）", got["material"]["checked"])

    def test_final_runs_step_when_change_touches_outside_ignored(self):
        """元 test_blk_tests_delta.py の test_final_runs_step_when_change_touches_outside_ignored"""
        self.decl(SCOPED)
        self.scope(SCOPE)
        for changed in (["graphloops/b.py"], ["works/a.py", "graphloops/b.py"]):
            with self.subTest(changed):
                got = self.run_ci(changed=lambda: changed, after_judge=True)
                self.assertEqual([r["name"] for r in got["runs"]], ["far", "near"])
                self.assertEqual(got["skipped_steps"], [])

    def test_test_cmd_same_as_skipped_step_still_runs(self):
        """元 run_ci の docstring の範囲の項: test_cmd が範囲で外した段と同じコマンドなら、外さずに test_cmd の段として走る
        （入力で名指した一式は外さない）"""
        far = {"name": "far", "argv": [PY, "-c", "pass"]}
        self.decl([far, SCOPED[1]])
        self.scope(SCOPE)
        self.assertEqual(tree_run.command_argv(shlex.join(far["argv"])), (far["argv"], "direct"))
        got = self.run_ci(shlex.join(far["argv"]), changed=lambda: ["works/a.py"])
        self.assertEqual(got["skipped_steps"], FAR_SKIPPED)
        self.assertEqual([r["name"] for r in got["runs"]], ["near", dc.TEST_CMD_STEP])
        self.assertIsNone(got["same_as"])

    def test_red_material_names_skipped_step_too(self):
        """元 test_red_material_names_skipped_step_too"""
        self.decl([SCOPED[0], {"name": "near", "argv": RED[0]["argv"]}])
        self.scope(SCOPE)
        m = self.run_ci(changed=lambda: ["works/a.py"])["material"]
        self.assertEqual(m["status"], "found")
        self.assertIn("範囲の外で回さなかった段: far", m["detail"])


class TestModesCase(RepoCase):
    """元 test_blk_tests_delta.py の TestTestsModes（最後のテストの形）"""

    def test_final_red_suite_is_ok(self):
        """元 test_final_red_suite_is_ok: 赤でも返りを出す（赤を見せるのが仕事で、赤で止めない）"""
        self.decl(RED)
        got = self.run_ci(after_judge=True)
        self.assertEqual((got["by"], got["material"]["status"], got["runs"]),
                         ("engine", "found", [{"name": "suite", "exit": 3, "how": "direct"}]))

    def test_final_never_reads_reuse_store(self):
        """元 test_final_never_reads_reuse_store: 同じ木で 2 度呼べば 2 度とも段を走らせる（使い回しの口が無い）"""
        count = self.tmp / "final-count"
        self.decl([{"name": "suite", "argv": [PY, "-c", f"open({str(count)!r}, 'a').write('1\\n')"]}])
        for expected in (1, 2):
            got = self.run_ci(after_judge=True)
            self.assertEqual((got["material"]["status"], len(count.read_text(encoding="utf-8").split())), ("clean", expected))


class ReuseCase(RepoCase):
    """同じ run の中の試験の結果の使い回し（元 test_board_engine_run.py・test_ci_test_cmd.py・test_blk_fix_tdd.py の使い回しの場合）。
    段は対象の木の外の数えのファイルに 1 行足す本物の子のプロセスで、木の中に何も書かない（書く段は前後の木が違って置かれない）"""

    def setUp(self):
        super().setUp()
        self.count = self.tmp / "count"
        self.cmd = f"{PY} -c \"open({str(self.count)!r}, 'a').write('1\\n')\""
        self.step = {"name": "suite", "argv": [PY, "-c", f"open({str(self.count)!r}, 'a').write('1\\n')"]}

    def place(self, run="run-1", rerun=False):
        return tree_run.reuse_place(self.work / "art", run, rerun=rerun)

    def launched(self):
        return len(self.count.read_text(encoding="utf-8").split()) if self.count.exists() else 0

    def test_same_tree_same_suite_runs_once(self):
        """元 test_board_engine_run.py の使い回しの場合: 同じ木・同じ一式の 2 度目は子を起こさない。行の reused に出どころ"""
        self.decl([self.step])
        self.run_ci(reuse=self.place())
        got = self.run_ci(reuse=self.place())
        self.assertEqual((self.launched(), got["material"]["status"]), (1, "clean"))
        self.assertEqual(got["runs"][0]["reused"]["from"], "run-1")

    def test_reused_suite_writes_its_junit_back(self):
        """JUnit を宣言した段の使い回しは報告を書き戻し、段の起動を書き戻す前に取るので、報告は今の段の物として数える。
        段の起動はファイルの時刻の時計で取る: time.time() がファイルの時刻より進んでいても（Linux の粗いファイルの時刻）、報告を落とさない"""
        (self.repo / ".gitignore").write_text("out/\n", encoding="utf-8")
        report = self.repo / "out" / "r.xml"
        write = (f"open({str(self.count)!r}, 'a').write('1\\n'); import os; os.makedirs('out', exist_ok=True); "
                 "open('out/r.xml', 'w').write('<testsuite><testcase classname=\"c\" name=\"t\"/></testsuite>')")
        self.decl([{"name": "suite", "argv": [PY, "-c", write], "junit": "out/r.xml"}])
        real = time.time
        with mock.patch.object(time, "time", lambda: real() + 5):
            fresh = self.run_ci(reuse=self.place())
            report.unlink(missing_ok=True)
            got = self.run_ci(reuse=self.place())
        self.assertEqual((fresh["material"]["status"], fresh["junit_unran"]), ("clean", []))
        self.assertEqual((self.launched(), got["material"]["status"], len(got["cases"]), got["junit_unran"]), (1, "clean", 1, []))
        self.assertIn("reused", got["runs"][0])

    def test_reused_steps_named_in_material_and_rows(self):
        """使い回した段の出どころは素材の checked と段の行に、使い回さなかった理由は段の行の reuse_off に出る。宣言の無い test_cmd も
        同じく素材の checked に出どころ"""
        self.decl([self.step])
        first = self.run_ci(reuse=self.place())
        self.assertIn("同じ指紋の控えが無い", first["runs"][0]["reuse_off"])
        self.assertNotIn("控えから使った", first["material"]["checked"])
        second = self.run_ci(reuse=self.place())
        self.assertIn("控えから使った段: suite（run run-1・", second["material"]["checked"])
        (self.repo / dc.DECL_NAME).unlink()
        self.run_ci(self.cmd, reuse=self.place())
        role = self.run_ci(self.cmd, reuse=self.place())
        self.assertEqual((role["by"], self.launched()), ("role", 2))
        self.assertIn(f"{dc.TEST_CMD_STEP} は控えから使った（run run-1・", role["material"]["checked"])

    def test_rerun_flag_runs_again(self):
        """旗 GRAPHLOOPS_RERUN_CHECKS（reuse_place の rerun）が立てば引かずに走らせ、行の reuse_off に旗の名"""
        self.decl([self.step])
        self.run_ci(reuse=self.place())
        got = self.run_ci(reuse=self.place(rerun=True))
        self.assertEqual(self.launched(), 2)
        self.assertIn(tree_run.RERUN_ENV, got["runs"][0]["reuse_off"])

    def test_other_run_or_moved_tree_is_not_reused(self):
        """別の run の控えは引かない。作業ツリーの木が変われば引かない"""
        self.decl([self.step])
        self.run_ci(reuse=self.place())
        other = self.run_ci(reuse=self.place("run-2"))
        self.assertEqual(self.launched(), 2)
        self.assertIn("別の run の控えは使わない", other["runs"][0]["reuse_off"])
        (self.repo / "moved.txt").write_text("x\n", encoding="utf-8")
        self.run_ci(reuse=self.place("run-2"))
        self.assertEqual(self.launched(), 3)

    def test_tdd_head_test_cmd_reads_the_base_keep(self):
        """元 test_blk_fix_tdd.py の test_loop_head_reuses_test_cmd_step_of_entry_checks: 入口の確かめが宣言の一式の段として走らせた
        test_cmd の緑を、TDD の輪の頭の test_cmd が同じ run の中で引く（子を起こさない）"""
        self.decl(GREEN)
        self.assertEqual(self.run_ci(self.cmd, reuse=self.place())["material"]["status"], "clean")
        exe = self.tmp / "suite.sh"
        exe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        tdd = kit.load("fix", "tdd")   # TDD の輪は fix の src/tdd.py（前は lib/tddloop.py。integration.md 4.3-3）
        gate, why, _ = tdd._test_cmd_gate(exe, self.cmd, self.repo, self.work / "head.log", reuse=self.place())
        self.assertEqual((gate, why, self.launched()), (tdd.GATE_ON, "", 1))


class TreeRunnerCase(unittest.TestCase):
    """元 test_board_engine_run.py の TreeRunnerCase"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)

    def test_tree_runner_shape(self):
        """元 test_tree_runner_shape: 行の鍵と、起こせない argv の exit None と error"""
        steps = [{"name": "ok", "argv": [PY, "-c", "import sys; print('out'); print('err', file=sys.stderr)"]},
                 {"name": "red", "argv": [PY, "-c", "import sys; sys.exit(4)"]},
                 {"name": "gone", "argv": [str(self.tmp / "no-such-command")]}]
        rows = dc.tree_runner(steps, self.tmp, self.tmp / "mine")
        keys = ["name", "argv", "out", "err", "started", "exit", "wall_s", "tail"]
        self.assertEqual([list(r) for r in rows], [keys, keys, ["name", "argv", "out", "err", "started", "error", "exit", "wall_s", "tail"]])
        self.assertEqual([r["exit"] for r in rows], [0, 4, None])
        self.assertEqual(pathlib.Path(rows[0]["out"]), self.tmp / "mine" / "1.out")
        self.assertEqual(pathlib.Path(rows[0]["out"]).read_text(encoding="utf-8"), "out\n")
        self.assertEqual(rows[0]["tail"], "out\n\nerr")
        self.assertIn("no-such-command", rows[2]["error"])

    def test_tree_runner_strips_uv_env(self):
        """元 test_tree_runner_strips_uv_env: uv が起こした環境を子に渡さず、PYTHONDONTWRITEBYTECODE=1 を立てる"""
        env = {"VIRTUAL_ENV": sys.prefix, "UV_RUN_RECURSION_DEPTH": "1", "UV_NO_CONFIG": "1"}
        show = [PY, "-c", "import os, json; print(json.dumps({k: os.environ.get(k) for k in "
                "('VIRTUAL_ENV', 'UV_RUN_RECURSION_DEPTH', 'UV_NO_CONFIG', 'PYTHONDONTWRITEBYTECODE')}))"]
        with mock.patch.dict(os.environ, env):
            rows = dc.tree_runner([{"name": "env", "argv": show}], self.tmp, self.tmp / "logs")
        self.assertEqual(rows[0]["exit"], 0, rows[0]["tail"])
        seen = json.loads(pathlib.Path(rows[0]["out"]).read_text(encoding="utf-8"))
        self.assertEqual(seen, {"VIRTUAL_ENV": None, "UV_RUN_RECURSION_DEPTH": None, "UV_NO_CONFIG": None,
                                "PYTHONDONTWRITEBYTECODE": "1"})


class JunitReportCase(RepoCase):
    """JUnit の報告の後始末: 走らせる前に無かった報告は対象の木から消えて report_dir に写しが在る・前から在った報告は残る・
    後始末の後の作業ツリーの指紋が走らせる前と同じ。報告の 1 件ごとの結末は cases に載る"""
    REPORT = "<testsuite><testcase classname='m' name='a'/><testcase classname='m' name='b'><failure/></testcase></testsuite>"

    def step(self, rel="out/report.xml"):
        body = f"import os; os.makedirs(os.path.dirname({rel!r}) or '.', exist_ok=True); open({rel!r},'w').write({self.REPORT!r})"
        return {"name": "suite", "argv": [PY, "-c", body], "junit": rel}

    def test_new_report_is_moved_out_of_the_tree(self):
        self.decl([self.step()])
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "decl")
        before = green_cert.fingerprint(self.repo)
        got = self.run_ci()
        self.assertFalse((self.repo / "out" / "report.xml").exists())
        self.assertEqual((self.work / "junit" / "1.xml").read_text(encoding="utf-8"), self.REPORT)
        self.assertEqual(green_cert.fingerprint(self.repo), before)
        self.assertEqual(got["junit_steps"], ["suite"])
        self.assertEqual(got["junit_unran"], [])
        self.assertEqual([(c["name"], c["outcome"]) for c in got["cases"]], [("a", "passed"), ("b", "failure")])

    def test_report_present_before_running_stays(self):
        self.decl([self.step("report.xml")])
        (self.repo / "report.xml").write_text("<testsuite/>", encoding="utf-8")
        self.run_ci()
        self.assertEqual((self.repo / "report.xml").read_text(encoding="utf-8"), self.REPORT)
        self.assertTrue((self.work / "junit" / "1.xml").is_file())

    def test_step_name_with_path_separator_is_copied_by_step_number(self):
        """段の名は対象が書く字で、パスの区切りを含みうる。写しの名にしない（落ちて報告が木に残らない）"""
        self.decl([{**self.step(), "name": "tests/unit"}])
        got = self.run_ci()
        self.assertEqual((got["junit_steps"], got["material"]["status"]), (["tests/unit"], "clean"))
        self.assertEqual((self.work / "junit" / "1.xml").read_text(encoding="utf-8"), self.REPORT)
        self.assertFalse((self.repo / "out" / "report.xml").exists())

    def test_stopped_run_removes_new_report(self):
        """段が報告を書いた後に止められても（tree_run.Stopped）、走らせる前に無かった報告は対象の木に残らない"""
        self.decl([self.step()])

        def stopped(steps, cwd, log_dir, **_):
            (self.repo / "out").mkdir()
            (self.repo / "out" / "report.xml").write_text(self.REPORT, encoding="utf-8")
            raise tree_run.Stopped(15)
        with mock.patch.object(dc, "tree_runner", stopped), self.assertRaises(tree_run.Stopped):
            self.run_ci()
        self.assertFalse((self.repo / "out" / "report.xml").exists())

    def test_unran_report_is_named_and_gives_no_cases(self):
        self.decl([{"name": "suite", "argv": [PY, "-c", "open('r.xml','w').write('<testsuite/>')"], "junit": "r.xml"}])
        got = self.run_ci()
        self.assertEqual((got["junit_steps"], got["junit_unran"], got["cases"]), (["suite"], ["suite"], []))
        self.assertFalse((self.repo / "r.xml").exists())


class MaterialProblemsCase(unittest.TestCase):
    """任せ先の CI の役の素材の欄の決まり（新しい関数）"""

    def problems(self, material, mode="base"):
        return dc.material_problems(material, mode=mode)

    def test_good_materials_pass(self):
        for mode, m in (("base", {"status": "found", "count": 2, "detail": "2 件落ちた"}),
                        ("base", {"status": "clean", "checked": "make test: exit 0"}),
                        ("base", {"status": "awaiting_human", "reason": "実機が要る"}),
                        ("final", {"status": "not_run", "reason": "依存が入らない"}),
                        ("final", {"status": "not_applicable", "reason": "CI の定義もテストも無い"}),
                        ("final", {"status": "clean", "count": 0, "checked": "x", "detail": "末尾"})):
            with self.subTest(mode=mode, m=m):
                self.assertEqual(self.problems(m, mode), [])

    def test_base_not_run_is_refused_for_awaiting_human(self):
        """material_problems は base の not_run を通す（機械が走らせて 1 段も走らなかった素材。止めるのは green_cert）。base の任せ先の役の
        素材は role_material_problems が not_run を awaiting_human を名指して拒む"""
        material = {"status": "not_run", "reason": "r"}
        self.assertEqual(self.problems(material, "base"), [])
        got = dc.role_material_problems(material, mode="base")
        self.assertEqual(len(got), 1)
        self.assertIn("awaiting_human", got[0])
        self.assertEqual(dc.role_material_problems({"status": "awaiting_human", "reason": "r"}, mode="base"), [])

    def test_final_awaiting_human_is_refused_for_not_run(self):
        got = self.problems({"status": "awaiting_human", "reason": "r"}, "final")
        self.assertEqual(len(got), 1)
        self.assertIn("not_run", got[0])

    def test_status_fields_are_required(self):
        for m, field in (({"status": "found", "detail": "d"}, "count"), ({"status": "found", "count": 1}, "detail"),
                         ({"status": "clean"}, "checked"), ({"status": "clean", "checked": " "}, "checked"),
                         ({"status": "not_applicable"}, "reason"), ({"status": "awaiting_human"}, "reason")):
            with self.subTest(m):
                got = self.problems(m)
                self.assertTrue(got)
                self.assertIn(field, " ".join(got))

    def test_shape_errors(self):
        for m, word in (([], "object でない"), ({"status": "carried_over", "from_round": 1, "reason": "r"}, "carried_over"),
                        ({"status": "found", "count": -1, "detail": "d"}, "count: 0 未満"),
                        ({"status": "found", "count": True, "detail": "d"}, "count: 型が integer でない"),
                        ({"status": "clean", "checked": 3}, "checked: 型が string でない"),
                        ({"status": "clean", "checked": "x", "from_round": 1}, "from_round")):
            with self.subTest(m):
                self.assertIn(word, " ".join(self.problems(m)))

    def test_statuses_are_the_ones_green_cert_classifies(self):
        """受け付けが通す status は全部 green_cert が読み分ける（知らない status が認証の既定の分けに黙って落ちない）"""
        self.assertLessEqual(set(dc.STATUSES), set(green_cert.NOT_DONE) | set(green_cert.BASE_OK) | set(green_cert.MEASURED))
        self.assertLessEqual(set(green_cert.BASE_OK), set(dc.STATUSES))

    def test_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            self.problems({"status": "clean", "checked": "x"}, "middle")

    def test_role_final_not_run_names_its_systems(self):
        """#514: 任せ先の役の final の not_run は、走らせた系統と走らせられなかった系統の名の分け（systems）が要る。engine の素材と
        base の awaiting_human には要らない"""
        bare = {"status": "not_run", "reason": "e2e は実機が要る"}
        self.assertIn("systems", " ".join(dc.role_material_problems(bare, mode="final")))
        self.assertEqual(self.problems(bare, "final"), [])
        self.assertIn("unran", " ".join(dc.role_material_problems({**bare, "systems": {"ran": ["unit"], "unran": []}}, mode="final")))
        self.assertIn("systems.ran", " ".join(dc.role_material_problems({**bare, "systems": {"ran": "unit", "unran": ["e2e"]}},
                                                                        mode="final")))
        self.assertEqual(dc.role_material_problems({**bare, "systems": {"ran": ["unit"], "unran": ["e2e"]}}, mode="final"), [])
        self.assertEqual(dc.role_material_problems({"status": "awaiting_human", "reason": "r"}, mode="base"), [])
        for mode, status in (("final", "not_run"), ("base", "awaiting_human")):   # #538: 同じ名を両側に書いた系統の分けは拒む
            with self.subTest(mode=mode):
                both = {"status": status, "reason": "r", "systems": {"ran": ["unit"], "unran": ["unit", "e2e"]}}
                self.assertIn("ran と unran の両方に同じ系統の名が在る: unit", " ".join(dc.role_material_problems(both, mode=mode)))


class BaselineLineCase(unittest.TestCase):
    """修正前のテストの行（元 entry.baseline_line。元 test_report_head.py の HeadBaselineCase・test_baseline_*、test_ci_test_cmd.py の
    BaselineScopeLineCase）。盤面の記録の代わりに元の結末（material・exit_codes・skipped_steps）を受ける"""
    SKIPPED = [{"name": "far", "paths_ignore": ["works/"]}]

    def line(self, material, **extra) -> str:
        return dc.baseline_line({"material": material, **extra})

    def test_baseline_missing_is_said_missing(self):
        self.assertTrue(dc.baseline_line(None).startswith("修正前のテスト: 記録が無い"))

    def test_baseline_found_says_known_red(self):
        line = self.line({"status": "found", "count": 1, "detail": "d"}, exit_codes={"suite": 1})
        self.assertIn("修正前から在りうる", line)
        self.assertIn('段ごとの終了コード {"suite": 1}', line)
        self.assertNotIn(gatemarks.BASELINE_NOT_RUN, line)

    def test_baseline_clean_does_not_blame_the_fix(self):
        line = self.line({"status": "clean", "checked": "unit"})
        self.assertIn("修正の後に出た赤でありうる", line)
        self.assertIn("同じ一式とは限らない", line)
        self.assertIn("走らせた物 unit", line)

    def test_baseline_not_run_is_not_said_known_red(self):
        for material in ({"status": "not_run", "reason": "x"}, None):
            with self.subTest(material):
                line = self.line(material)
                self.assertIn(gatemarks.BASELINE_NOT_RUN, line)
                self.assertNotIn("修正前から在りうる", line)

    def test_baseline_other_status_named_plainly(self):
        for status in ("awaiting_human", "not_run", "not_applicable"):
            with self.subTest(status):
                line = self.line({"status": status, "reason": "r"})
                self.assertTrue(line.startswith(f"修正前のテスト: {gatemarks.MATERIAL_WORDS[status]}（"), line)
                self.assertIn(f"status {status}", line)

    def test_baseline_broken_record_not_said_missing(self):
        for broken in ("clean", {"count": 1}, {"status": ["clean"]}, {"status": 1}):
            with self.subTest(broken):
                self.assertTrue(self.line(broken).startswith("修正前のテスト: 記録が壊れている"))

    def test_baseline_line_names_skipped_steps(self):
        word = checkscope.skipped_text(self.SKIPPED)
        self.assertIn(word, self.line({"status": "found", "count": 1, "detail": "near: exit 1"}, skipped_steps=self.SKIPPED))
        self.assertNotIn("範囲の外で回さなかった段", self.line({"status": "found", "count": 1, "detail": f"末尾: {word}"}))


if __name__ == "__main__":
    unittest.main()

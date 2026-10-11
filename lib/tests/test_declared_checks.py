"""CI の節を盤面なしで走らせる口（lib/declared_checks.py）の検査。今の works の試験の場合を盤面なしで書き直した物で、各試験の
docstring に元の試験の名を書く（見比べられるように）。元の試験は tests/test_ci_test_cmd.py・tests/test_board_engine_run.py・
tests/test_blk_tests_delta.py（TestTestsModes）。

対象のリポジトリは tests/e2e/target-seed/ の写し（committed_copy）。宣言の段は子のプロセスを本当に起こす（この Python）。
盤面の記録（process.checks）・同じ run の中の控え（slotted_run・reused）・任せ先に落ちた後の test_cmd の使い回しの場合は、
その仕組みを持ってこないので写さない。
"""
import json
import os
import pathlib
import sys
import tempfile
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
    def run(steps, cwd, log_dir):
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

    def run_ci(self, test_cmd="", *, changed=None, after_judge=False, report=True):
        return dc.run_ci(self.repo, test_cmd=test_cmd, log_dir=self.work / "logs", changed=changed, after_judge=after_judge,
                         report_dir=self.work / "junit" if report else None)


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
        self.assertEqual(got["by"], "role")
        self.assertIn("bash -c 'a | b'（起こし方 shell）", got["material"]["detail"])


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
        self.assertTrue(dc.env_only_red(tests))

    def test_missing_command_127_is_red_like_the_material(self):
        """元 EnvFailureLineCase.test_missing_command_127_is_red_like_the_material"""
        tests = {"by": "engine", "suites": [{"name": "suite", "exit": 0}, {"name": "test_cmd", "exit": 127}]}
        self.assertFalse(dc.env_only_red(tests))
        self.assertIn("test_cmd（exit 127）", dc.suites_line(tests))

    def test_code_red_is_not_env(self):
        """元 EnvFailureLineCase.test_code_red_is_not_env"""
        tests = {"by": "engine", "suites": [{"name": "suite", "exit": 1}, {"name": "test_cmd", "exit": None}]}
        self.assertFalse(dc.env_only_red(tests))
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
                self.assertFalse(dc.env_only_red(tests))

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
                dc._with_test_cmd(lambda s, *_: steps.extend(s) or [], cmd, {})([], self.tmp, self.tmp)
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
        """元 test_unran_step_is_not_found: 報告を宣言した段が試験を走らせていない形は、赤でなく走らせられない status
        （判定の前は awaiting_human・後は not_run）。終了コードの数値でなく件数で分ける"""
        stale = "<testsuite><testcase name='t'><failure/></testcase></testsuite>"
        cases = [(self.reported_step("", 5), None, "試験が 0 件"),
                 (self.reported_step("<testcase name='t'><error/></testcase>", 1), None, "全部 error"),
                 (self.reported_step(None, 4), None, "report.xml が無い"),
                 (self.reported_step(None, 1), (stale, 3600), "段の起動より古い"),
                 (self.reported_step("<testcase", 2), None, "XML として読めない")]
        for after_judge, status in ((False, "awaiting_human"), (True, "not_run")):
            for step, before, want in cases:
                with self.subTest(want, after_judge=after_judge):
                    m = self.material_for(step, before, after_judge)
                    self.assertEqual(m["status"], status, m)
                    self.assertIn("基準の検査が走らなかった", m["reason"])
                    self.assertIn(want, m["reason"])
                    self.assertNotIn("count", m)

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
        with mock.patch.object(dc, "tree_runner", never):
            got = self.run_ci(after_judge=True)
        self.assertEqual((got["by"], got["material"]["status"], got["runs"]), ("engine", "not_run", []))
        self.assertIn(dc.DECL_NAME, got["material"]["reason"])
        self.assertIn("走らせなかった", pathlib.Path(got["log"]).read_text(encoding="utf-8"))


class ScopedStepsCase(RepoCase):
    """元 test_board_engine_run.py の ScopedStepsCase と test_blk_tests_delta.py の TestTestsModes の範囲の場合"""

    def test_scope_without_review_declaration_stops(self):
        """元 test_scope_without_review_declaration_stops: 範囲の宣言だけが在れば、任せ先に落とさず名指して止める。何も走らせない"""
        self.scope(SCOPE)
        with mock.patch.object(tree_run, "run", never), self.assertRaises(dc.CiRefused) as cm:
            self.run_ci("true")
        self.assertIn(checkscope.SCOPE_DECL, str(cm.exception))
        self.assertIn(dc.DECL_NAME, str(cm.exception))

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
        self.assertEqual((self.work / "junit" / "suite.xml").read_text(encoding="utf-8"), self.REPORT)
        self.assertEqual(green_cert.fingerprint(self.repo), before)
        self.assertEqual(got["junit_steps"], ["suite"])
        self.assertEqual(got["junit_unran"], [])
        self.assertEqual([(c["name"], c["outcome"]) for c in got["cases"]], [("a", "passed"), ("b", "failure")])

    def test_report_present_before_running_stays(self):
        self.decl([self.step("report.xml")])
        (self.repo / "report.xml").write_text("<testsuite/>", encoding="utf-8")
        self.run_ci()
        self.assertEqual((self.repo / "report.xml").read_text(encoding="utf-8"), self.REPORT)
        self.assertTrue((self.work / "junit" / "suite.xml").is_file())

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
        got = self.problems({"status": "not_run", "reason": "r"}, "base")
        self.assertEqual(len(got), 1)
        self.assertIn("awaiting_human", got[0])

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
        for m, word in (([], "オブジェクトでない"), ({"status": "carried_over", "from_round": 1, "reason": "r"}, "carried_over"),
                        ({"status": "found", "count": -1, "detail": "d"}, "0 以上の整数"),
                        ({"status": "found", "count": True, "detail": "d"}, "0 以上の整数"),
                        ({"status": "clean", "checked": 3}, "文字列"),
                        ({"status": "clean", "checked": "x", "from_round": 1}, "from_round")):
            with self.subTest(m):
                self.assertIn(word, " ".join(self.problems(m)))

    def test_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            self.problems({"status": "clean", "checked": "x"}, "middle")


if __name__ == "__main__":
    unittest.main()

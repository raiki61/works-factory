"""元から赤の区別（lib/baseline_red.py）の検査。

- run_suite の結末の行に failure の子の message と本文（元 works/tests/test_blk_fix_tdd.py の TestRedKind）
- run_suite が only でない時は外の env の合図 ONLY_ENV を落とす
- run_suite を種（tests/e2e/target-seed/）の写しで走らせ、JUnit を書かない時と XML が壊れた時の problems の文。ファイル名だけの実行器を写しの根から起こす
- parse_junit・red_problems・green_problems の事実の文（元は輪の中からだけ呼ばれていた筋を、関数を直に呼んで写す）
- write_baseline → read_baseline が同じ dict に戻る（extra の欄も）。必須の欄の欠けと型の違い・OUTCOMES に無い outcome は ValueError
- outcomes が同じ鍵の最初の 1 つを取る。_must_pass が元で failure の物を問わず、元に無い物を問う
"""
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

LIB = pathlib.Path(__file__).resolve().parents[1]
SEED = LIB.parent / "tests" / "e2e" / "target-seed"
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import baseline_red  # noqa: E402
from tests.bin.gitkit import committed_copy  # noqa: E402


class TestRedKind(unittest.TestCase):
    def test_run_suite_rows_carry_failure_attrs(self):
        """run_suite の結末の行に failure の子の message と本文（無ければ空）。failure の無い行は空"""
        with tempfile.TemporaryDirectory() as td:
            work = pathlib.Path(td)
            exe = work / "suite.py"
            exe.write_text("import sys\nopen(sys.argv[1], 'w').write('<testsuite>"
                           "<testcase classname=\"a\" name=\"t1\"><failure type=\"x.AssertionError\" message=\"m\">trace\\nm</failure></testcase>"
                           "<testcase classname=\"a\" name=\"t2\"/></testsuite>')\nsys.exit(1)\n", encoding="utf-8")
            cases, _, why = baseline_red.run_suite(str(exe), work, work, "attrs")
        self.assertEqual(why, [])
        self.assertEqual([(c["name"], c["fail_message"], c["fail_text"]) for c in cases], [("t1", "m", "trace\nm"), ("t2", "", "")])
        self.assertTrue(all("fail_type" not in c for c in cases))


JUNIT = ('<testsuite><testcase classname="test_stats.TestStats" name="test_mean_of_three">'
         '<failure message="AssertionError: 3.0 != 2">trace</failure></testcase>'
         '<testcase classname="test_stats.TestStats" name="test_clamp_within_range"/>'
         '<testcase classname="test_stats.TestStats" name="test_clamp_within_range"/></testsuite>')


class RunSuiteSeedCase(unittest.TestCase):
    """種の写しの根で、試験の中で作った小さな実行ファイル（JUnit の書き先を第 1 引数に受ける）を走らせる"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = pathlib.Path(self._tmp.name)
        self.repo = tmp / "repo"
        committed_copy(self.repo, SEED)
        self.work = tmp / "work"
        self.work.mkdir()

    def runner(self, body, name="suite.sh"):
        exe = self.work / name
        exe.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        exe.chmod(0o755)
        return str(exe)

    def test_writes_junit_rows_unique_and_runs_in_repo(self):
        exe = self.runner(f"pwd > {self.work}/cwd; printf '%s' '{JUNIT}' > \"$1\"\n"
                          f"printf '%s' \"${{{baseline_red.ONLY_ENV}:-}}\" > {self.work}/only\nexit 1\n")
        cases, code, why = baseline_red.run_suite(exe, self.repo, self.work, 1)
        self.assertEqual((code, why), (1, []))
        self.assertEqual([(c["name"], c["outcome"]) for c in cases],
                         [("test_mean_of_three", "failure"), ("test_clamp_within_range", "passed")])
        self.assertEqual(cases[0]["fail_message"], "AssertionError: 3.0 != 2")
        self.assertEqual(os.path.realpath((self.work / "cwd").read_text().strip()), os.path.realpath(self.repo))
        self.assertEqual((self.work / "only").read_text(), "")
        self.assertFalse((self.work / "junit-1.xml").exists(), "読んだ JUnit は消す")
        self.assertTrue((self.work / "suite-1.log").is_file())

    def test_only_sets_the_env_signal(self):
        exe = self.runner(f"printf '%s' \"${{{baseline_red.ONLY_ENV}:-}}\" > {self.work}/only\nprintf '%s' '{JUNIT}' > \"$1\"\n")
        baseline_red.run_suite(exe, self.repo, self.work, 2, only=True)
        self.assertEqual((self.work / "only").read_text(), "1")

    def test_without_only_the_inherited_signal_is_dropped(self):
        exe = self.runner(f"printf '%s' \"${{{baseline_red.ONLY_ENV}:-}}\" > {self.work}/only\nprintf '%s' '{JUNIT}' > \"$1\"\n")
        with mock.patch.dict(os.environ, {baseline_red.ONLY_ENV: "1"}):
            baseline_red.run_suite(exe, self.repo, self.work, 3, only=False)
        self.assertEqual((self.work / "only").read_text(), "")

    def test_no_junit_names_exit_and_log(self):
        exe = self.runner("echo 何も書かない\nexit 3\n")
        cases, code, why = baseline_red.run_suite(exe, self.repo, self.work, "none")
        self.assertIsNone(cases)
        self.assertEqual(code, 3)
        self.assertEqual(why, [f"テストの実行器が JUnit XML を書かなかった（exit 3。ログ {self.work / 'suite-none.log'}）"])

    def test_broken_xml_is_a_problem(self):
        exe = self.runner("printf '%s' '<testsuite><testcase' > \"$1\"\nexit 1\n")
        cases, code, why = baseline_red.run_suite(exe, self.repo, self.work, "bad")
        self.assertIsNone(cases)
        self.assertEqual(code, 1)
        self.assertEqual(len(why), 1)
        self.assertTrue(why[0].startswith("JUnit XML が読めない（"), why)
        self.assertIn(str(self.work / "suite-bad.log"), why[0])

    def test_bare_name_runs_from_the_repo_root(self):
        """ファイル名だけの実行器（種の tdd_suite の junit-suite.sh の形）は PATH で探さず repo の根の物を起こす（#340）"""
        exe = self.repo / "bare-suite.sh"
        exe.write_text(f"#!/bin/sh\nprintf '%s' '{JUNIT}' > \"$1\"\nexit 1\n", encoding="utf-8")
        exe.chmod(0o755)
        cases, code, why = baseline_red.run_suite(exe.name, self.repo, self.work, "bare-name")
        self.assertEqual((code, why), (1, []))
        self.assertEqual(len(cases), 2)

    def test_missing_runner_is_a_problem_without_exit(self):
        cases, code, why = baseline_red.run_suite(str(self.work / "無い"), self.repo, self.work, "gone")
        self.assertEqual((cases, code), (None, None))
        self.assertTrue(why[0].startswith("テストの実行器を起こせない（"), why)

    def test_runner_is_niced(self):
        """実行器は nice -n 19 と同じだけ優先度を下げて起こす（元 works/blk-fix/lib/tddloop.py:307。同じ機械で別の run も動く）。
        argv は変えない（起こせるかの証明を走らせる時と同じ形のまま通す）"""
        mine = os.nice(0)
        exe = self.runner(f"ps -o nice= -p $$ > {self.work}/nice\nexit 0\n")
        seen = []
        real = baseline_red.tree_run.run
        with mock.patch.object(baseline_red.tree_run, "run", side_effect=lambda argv, **kw: seen.append(argv) or real(argv, **kw)):
            baseline_red.run_suite(exe, self.repo, self.work, "niced")
        self.assertEqual(seen[0][0], exe)
        self.assertGreaterEqual(int((self.work / "nice").read_text(encoding="utf-8").strip()), min(mine + baseline_red.NICENESS, 19))
        self.assertNotIn(baseline_red.NO_NICE, (self.work / "suite-niced.log").read_text(encoding="utf-8"))

    def test_runner_without_nice_runs_bare_and_says_so(self):
        """優先度を下げられない環境（os.nice が無い）では下げずに起こし、その事実をログに 1 行残す（黙って下げずに走らせない）"""
        exe = self.runner("exit 0\n")
        seen = []
        with mock.patch.object(baseline_red.os, "nice", None), \
                mock.patch.object(baseline_red.tree_run, "run", side_effect=lambda argv, **kw: seen.append(kw) or 0):
            baseline_red.run_suite(exe, self.repo, self.work, "bare")
        self.assertNotIn("preexec_fn", seen[0])
        self.assertIn(baseline_red.NO_NICE, (self.work / "suite-bare.log").read_text(encoding="utf-8"))

def row(name, outcome, cls="test_a.TestA"):
    return {"classname": cls, "name": name, "outcome": outcome}


class JudgeCase(unittest.TestCase):
    """parse_junit・red_problems・green_problems の事実の文"""

    def test_parse_junit_outcomes(self):
        xml = ('<testsuites><testsuite><testcase classname="a.B" name="p"/>'
               '<testcase classname="a.B" name="f"><failure/></testcase>'
               '<testcase classname="a.B" name="e"><failure/><error/></testcase>'
               '<testcase name="s"><skipped/></testcase></testsuite></testsuites>')
        self.assertEqual(baseline_red.parse_junit(xml),
                         [row("p", "passed", "a.B"), row("f", "failure", "a.B"), row("e", "error", "a.B"), row("s", "skipped", "")])
        with self.assertRaises(ET.ParseError):
            baseline_red.parse_junit("<testsuite")

    def test_match_case_by_tail(self):
        cases = [row("test_x", "failure", "pkg.test_a.TestA")]
        self.assertIs(baseline_red.match_case("pkg/test_a.py::TestA::test_x", cases), cases[0])
        self.assertIs(baseline_red.match_case("test_a.py::TestA::test_x", cases), cases[0])
        self.assertIsNone(baseline_red.match_case("test_b.py::TestA::test_x", cases))

    def test_red_problems(self):
        named = ["test_a.py::TestA::test_x"]
        self.assertEqual(baseline_red.red_problems(named, [row("test_x", "failure")], 1), [])
        for outcome, word in (("error", "error で落ちた"), ("passed", "もう通る"), ("skipped", "飛ばされた")):
            with self.subTest(outcome):
                probs = baseline_red.red_problems(named, [row("test_x", outcome)], 1)
                self.assertTrue(any(word in p for p in probs), probs)
        self.assertTrue(any("一式の結末に居ない" in p for p in baseline_red.red_problems(named, [row("test_y", "failure")], 1)))
        self.assertTrue(any("exit 0" in p for p in baseline_red.red_problems(named, [row("test_x", "failure")], 0)))
        self.assertEqual(baseline_red.red_problems([], [], 1), ["名指しのテストが無い"])

    def test_red_problems_reads_others_against_baseline(self):
        named = ["test_a.py::TestA::test_x"]
        cases = [row("test_x", "failure"), row("test_old", "failure"), row("test_was_green", "error")]
        base = {"test_a.TestA::test_old": "failure", "test_a.TestA::test_was_green": "passed"}
        probs = baseline_red.red_problems(named, cases, 1, base)
        self.assertEqual(len(probs), 1, probs)
        self.assertIn("test_a.TestA::test_was_green", probs[0])

    def test_green_problems(self):
        named = ["test_a.py::TestA::test_x"]
        self.assertEqual(baseline_red.green_problems(named, [row("test_x", "passed")], 0), [])
        probs = baseline_red.green_problems(named, [row("test_x", "passed")], 1)
        self.assertTrue(any("exit 1" in p for p in probs), probs)
        self.assertEqual(baseline_red.green_problems(named, [row("test_x", "passed")], 1, baseline_exit=1), [],
                         "元の一式が 0 で終わっていなければ終了コードは問わない")
        probs = baseline_red.green_problems(named, [row("test_x", "failure"), row("test_new", "failure")], 0, {})
        self.assertEqual(len(probs), 2, probs)


class MustPassCase(unittest.TestCase):
    def test_baseline_failure_is_not_asked(self):
        base = baseline_red.outcomes([row("t", "failure")])
        self.assertFalse(baseline_red._must_pass(row("t", "failure"), base))

    def test_case_absent_from_baseline_is_asked(self):
        base = baseline_red.outcomes([row("t", "failure")])
        self.assertTrue(baseline_red._must_pass(row("new", "failure"), base))
        self.assertTrue(baseline_red._must_pass(row("t", "failure"), None))

    def test_outcomes_takes_first_of_same_key(self):
        self.assertEqual(baseline_red.outcomes([row("t", "failure"), row("t", "passed"), row("u", "passed")]),
                         {"test_a.TestA::t": "failure", "test_a.TestA::u": "passed"})


class TestOutcomesCase(unittest.TestCase):
    def test_every_test_with_its_base_and_final_outcome(self):
        """issue #384: 赤→緑だけでなく緑→緑・緑→赤・赤→赤も、片側にしか居ないテストも並べる。fail_message は最後に赤なら最後の、
        でなければ base の物"""
        base = [{**row("t", "failure"), "fail_message": "0 != 10"}, row("u", "passed"), {**row("broke", "passed")},
                {**row("still", "failure"), "fail_message": "old"}, row("gone", "error")]
        now = [row("t", "passed"), row("u", "passed"), {**row("broke", "failure"), "fail_message": "1 != 2"},
               {**row("still", "failure"), "fail_message": "new"}, row("new", "passed")]
        self.assertEqual(baseline_red.test_outcomes(base, now),
                         [{"key": "test_a.TestA::t", "base": "failure", "final": "passed", "fail_message": "0 != 10"},
                          {"key": "test_a.TestA::u", "base": "passed", "final": "passed", "fail_message": ""},
                          {"key": "test_a.TestA::broke", "base": "passed", "final": "failure", "fail_message": "1 != 2"},
                          {"key": "test_a.TestA::still", "base": "failure", "final": "failure", "fail_message": "new"},
                          {"key": "test_a.TestA::gone", "base": "error", "final": "", "fail_message": ""},
                          {"key": "test_a.TestA::new", "base": "", "final": "passed", "fail_message": ""}])


BASE = {"suite": "/home/x/suite.sh", "test_cmd": "make check", "rev": "a" * 40, "exit": 1,
        "cases": [row("t", "failure"), row("u", "passed")]}


class BaselineFileCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = pathlib.Path(self._tmp.name) / "baseline.json"

    def test_round_trip_with_extra(self):
        extra = {"by": "test-gate", "runs": [{"name": "unit", "exit": 1}], "junit_steps": ["unit"],
                 "fingerprint": {"head": "h", "diff_hash": "d"}}
        baseline_red.write_baseline(self.path, **BASE, **extra)
        self.assertEqual(baseline_red.read_baseline(self.path), {**BASE, **extra})

    def test_cases_are_unique_by_key(self):
        baseline_red.write_baseline(self.path, **{**BASE, "cases": [row("t", "failure"), row("t", "passed")]})
        self.assertEqual(baseline_red.read_baseline(self.path)["cases"], [row("t", "failure")])

    def test_exit_none_is_allowed(self):
        baseline_red.write_baseline(self.path, **{**BASE, "exit": None})
        self.assertIsNone(baseline_red.read_baseline(self.path)["exit"])

    def test_missing_field_is_value_error(self):
        for name in BASE:
            with self.subTest(name):
                self.path.write_text(json.dumps({k: v for k, v in BASE.items() if k != name}), encoding="utf-8")
                with self.assertRaises(ValueError) as cm:
                    baseline_red.read_baseline(self.path)
                self.assertIn(name, str(cm.exception))
                self.assertIn(str(self.path), str(cm.exception))

    def test_wrong_type_is_value_error(self):
        for name, bad in (("suite", None), ("test_cmd", 1), ("rev", []), ("exit", "1"), ("exit", True), ("cases", {}),
                          ("cases", [{"classname": "a", "name": "b"}]), ("cases", ["x"]),
                          ("cases", [row("t", "failed")])):
            with self.subTest(name=name, bad=bad):
                self.path.write_text(json.dumps({**BASE, name: bad}), encoding="utf-8")
                with self.assertRaises(ValueError) as cm:
                    baseline_red.read_baseline(self.path)
                self.assertIn(name, str(cm.exception))

    def test_absent_or_unreadable_is_value_error(self):
        with self.assertRaises(ValueError):
            baseline_red.read_baseline(self.path)
        for text in ("{", "[]"):
            self.path.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError):
                baseline_red.read_baseline(self.path)

    def test_extra_named_like_a_required_field_is_refused(self):
        with self.assertRaises((TypeError, ValueError)):
            baseline_red.write_baseline(self.path, **BASE, **{"suite": "again"})
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()

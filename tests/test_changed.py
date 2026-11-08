"""作業中の試験の選びの殻（tests/changed.py）の試験。

使い捨ての git の木（殻と選びと分けの写し COPIED と、小さな lib と試験）で殻を起こし、
unittest の最後の数え（Ran N tests）で何が回ったかを見る。木の試験は test_alpha 1 本・test_beta 2 本・層の柵 1 本。
- lib の 1 ファイルを変えると、その試験のモジュールと層の柵だけが回る
- 選べない時（tests/archon.py などの変更・選びが全部が要ると言った時・起点（origin/main との merge-base）が無い時・git が起こせない時）も
  全部は回さず、選べた範囲と層の柵だけを回し、全部の試験は CI に寄せるの 1 行と訳を出して緑（持ち主の決め full-suite-in-ci）
- 選んだ物が 0 本でも層の柵は回り、選んだ試験の赤は殻の赤
- 頭で読み込めない試験のパッケージの下を変えると赤（パッケージ名の 1 件を選ぶ）
- 集め方の正本（tests/shard.py の PATTERN）を変えると、殻の選び（変わった lib を import する試験も）と CI の分けの両方が変わる
- 地図が届いたが直でない試験（深さ 2 以上）の名は、選べなかった訳とは別の欄に出て回らない。CI に寄せる時と WHOLE の時も出る。
  層の柵の下の試験はその欄に出ない。遠くの分からない物は、CI に寄せる訳を出さずに別の欄へ訳が出る
- 出力の最後は unittest の数え（Ran N tests）で、数えの形 COUNT が最初に当たるのもその行
- 試験は既定で子 WORKERS 個に並べて回す。並べても、選んだモジュールの名と回さないモジュールの数・回った数は 1 つの子で順に回した時と
  同じで、落ちた試験は名と traceback が出て、最後は FAILED。2 つのモジュールは別の子で走り、並べる数の上書き（環境変数）は試験を回す口まで届く
- --junit-xml <パス>: 選んだ試験が 1 本ずつ XML に載り（印字と終了の値は無しの時と同じ）、相対のパスは呼んだ所から。読まない引数は
  標準エラーに 1 行の注記を出して捨て、選びと回しは続く
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree

from tests.bin import hermetic
from tests.bin.gitkit import git

ROOT = pathlib.Path(__file__).resolve().parents[1]
IN_CI = "全部の試験は CI に寄せる（持ち主の決め full-suite-in-ci）"
UNRUN = "地図が届いたが直でないので回さない"
FAR = "どの試験に関わるか読み切れない深さ 2 以上の分からない物"
WORKERS = "3"
COUNT = re.compile(r"Ran (\d+) tests?")
# hermetic は pack.json の ours.folder の .shared/ports.py から Archon の変数の名を読む（docs/design/integration.md の 4.5-8）
COPIED = ("lib/impact.py", "lib/changemap.py", "tests/changed.py", "tests/shard.py", "tests/bin/hermetic.py", "pack.json",
          hermetic.PORTS.relative_to(ROOT).as_posix())
ONE_TEST = "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_one(self):\n        pass\n"
TWO_TESTS = ONE_TEST + "\n    def test_two(self):\n        pass\n"
LIB_TEST = ("import unittest\n\nfrom lib import {name}\n\n\nclass T(unittest.TestCase):\n"
            "    def test_one(self):\n        self.assertEqual({name}.value(), 1)\n")
TREE = {
    "lib/__init__.py": "",
    "lib/alpha.py": "def value():\n    return 1\n",
    "lib/beta.py": "def value():\n    return 1\n",
    "lib/tests/__init__.py": "",
    "lib/tests/test_alpha.py": LIB_TEST.format(name="alpha"),
    "lib/tests/test_beta.py": LIB_TEST.format(name="beta") + "\n    def test_two(self):\n        pass\n",
    "tests/__init__.py": "",
    "tests/archon.py": "",
    "tests/bin/__init__.py": "",
    "tests/shard-seconds.json": "{}\n",
    "tests/layers/__init__.py": "",
    "tests/layers/test_fence.py": ONE_TEST,
    "docs/note.md": "# note\n",
}


class ChangedTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name) / "repo"
        for rel, text in TREE.items():
            self.write(rel, text)
        for rel in COPIED:
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, self.repo / rel)
        git(self.repo, "init", "-q")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "seed")
        git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")

    def write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def run_changed(self, *args, cwd=None, **overrides):
        """殻を子の過程として起こす。args は殻の引数、cwd は呼び手の作業ディレクトリ（既定は木の根）。
        (終了の値, 標準出力, 標準出力 + 標準エラー) を返す"""
        env = hermetic.child_env(**{"WORKS_FACTORY_TEST_WORKERS": WORKERS, **overrides})
        done = subprocess.run([sys.executable, str(self.repo / "tests/changed.py"), *map(str, args)], cwd=cwd or self.repo,
                              capture_output=True, text=True, encoding="utf-8", env=env)
        return done.returncode, done.stdout, done.stdout + done.stderr

    def ran(self, out):
        return int(COUNT.search(out).group(1))

    def test_lib_change_runs_its_test_and_the_fence(self):
        self.write("lib/alpha.py", "def value():\n    return 1  # changed\n")
        rc, stdout, out = self.run_changed()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.ran(out), 2, out)
        self.assertIn("lib.tests.test_alpha", stdout)
        self.assertIn("tests.layers.test_fence", stdout)
        self.assertNotIn("lib.tests.test_beta", stdout)

    def test_committed_change_on_the_branch_counts(self):
        self.write("lib/beta.py", "def value():\n    return 1  # changed\n")
        git(self.repo, "commit", "-q", "-am", "beta")
        rc, stdout, out = self.run_changed()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.ran(out), 3, out)
        self.assertIn("lib.tests.test_beta", stdout)

    def test_new_untracked_test_file_runs(self):
        self.write("lib/tests/test_gamma.py", ONE_TEST)
        rc, stdout, out = self.run_changed()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.ran(out), 2, out)
        self.assertIn("lib.tests.test_gamma", stdout)

    def test_changed_test_file_outside_the_impact_name_rule_runs(self):
        self.write("tests/testzz.py", ONE_TEST)
        rc, stdout, out = self.run_changed()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.ran(out), 2, out)
        self.assertIn("tests.testzz", stdout)

    def test_archon_helper_change_runs_only_the_fence_and_defers_to_ci(self):
        self.write("tests/archon.py", "# changed\n")
        rc, stdout, out = self.run_changed()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.ran(out), 1, out)
        self.assertIn(IN_CI, stdout)
        self.assertIn("tests/archon.py", stdout)

    def test_ci_change_runs_only_the_fence_and_defers_to_ci(self):
        self.write(".github/workflows/tests.yml", "name: tests\n")
        rc, stdout, out = self.run_changed()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.ran(out), 1, out)
        self.assertIn(IN_CI, stdout)
        self.assertIn(".github/workflows/tests.yml", stdout)

    def test_unanalysable_change_runs_what_it_reached_and_defers_to_ci(self):
        self.write("lib/alpha.py", "import importlib\n\n\ndef value():\n    return 1\n\n\n"
                                   "def load(name):\n    return importlib.import_module(name)\n")
        rc, stdout, out = self.run_changed()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.ran(out), 2, out)
        self.assertIn(IN_CI, stdout)
        self.assertIn("dynamic-import", stdout)

    def commit_deep_chain(self, far_source=None):
        self.write("lib/mid.py", "from lib import alpha\n\n\ndef value():\n    return alpha.value()\n")
        self.write("lib/tests/test_far.py", LIB_TEST.format(name="mid"))
        self.write("tests/layers/test_fence.py", LIB_TEST.format(name="mid"))
        if far_source:
            self.write("lib/far.py", far_source)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "deep chain")
        git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")

    def block(self, stdout, head):
        lines = stdout.splitlines()
        for i, line in enumerate(lines):
            if head in line and not line.startswith(" "):
                body = []
                for after in lines[i + 1:]:
                    if not after.startswith(" "):
                        break
                    body.append(after.strip())
                return body
        return None

    def test_reached_tests_that_are_not_direct_are_named_but_not_run(self):
        self.commit_deep_chain()
        self.write("lib/alpha.py", "def value():\n    return 1  # changed\n")
        rc, stdout, out = self.run_changed()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.ran(out), 2, out)
        unrun = self.block(stdout, UNRUN)
        self.assertIsNotNone(unrun, stdout)
        self.assertEqual(unrun, ["lib/tests/test_far.py"], stdout)
        self.assertIn("lib.tests.test_alpha", stdout)
        self.assertIn("tests.layers.test_fence", stdout)
        self.assertNotIn(IN_CI, stdout)

    def test_reached_tests_are_named_even_when_selection_defers_to_ci(self):
        self.commit_deep_chain()
        self.write("lib/alpha.py", "import importlib\n\n\ndef value():\n    return 1\n\n\n"
                                   "def load(name):\n    return importlib.import_module(name)\n")
        with self.subTest(case="selection says everything is needed"):
            rc, stdout, out = self.run_changed()
            self.assertEqual(rc, 0, out)
            self.assertEqual(self.ran(out), 2, out)
            self.assertIn(IN_CI, stdout)
            self.assertEqual(self.block(stdout, UNRUN), ["lib/tests/test_far.py"], stdout)
            self.assertNotIn("lib/tests/test_far.py", self.block(stdout, IN_CI) or [], stdout)
        self.write("lib/alpha.py", "def value():\n    return 1  # changed\n")
        self.write("tests/archon.py", "# changed\n")
        with self.subTest(case="whole"):
            rc, stdout, out = self.run_changed()
            self.assertEqual(rc, 0, out)
            self.assertEqual(self.ran(out), 2, out)
            self.assertIn(IN_CI, stdout)
            self.assertTrue(any("tests/archon.py" in r for r in self.block(stdout, IN_CI) or []), stdout)
            self.assertEqual(self.block(stdout, UNRUN), ["lib/tests/test_far.py"], stdout)
            self.assertNotIn("lib/tests/test_far.py", self.block(stdout, IN_CI) or [], stdout)

    def commit_scenario_copy(self):
        """実行時に workflows/ を読む助け（宣言を持つ stepnames の写し）とそれを import する筋書きの試験の小さな写しと、
        線・ブロックの YAML・script を足して、起点を進める。写しは YAML の名を字で書かない（字の言及の辺でなく、宣言の辺で選ばれる事を見るため）"""
        self.write("tests/bin/stepnames.py", 'RUNTIME_READS = ("workflows/",)\n')
        self.write("tests/e2e/__init__.py", "")
        self.write("tests/e2e/test_scenario.py", "from tests.bin import stepnames  # noqa: F401\n" + ONE_TEST)
        self.write("workflows/line/works-factory-line.yaml", "nodes: []\n")
        self.write("workflows/fix/works-factory-fix.yaml", "nodes: []\n")
        self.write("workflows/fix/scripts/x.py", "VALUE = 1\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "scenario copy")
        git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")

    def test_change_under_the_scenario_reads_runs_the_scenario_test(self):
        self.commit_scenario_copy()
        for rel in ("workflows/line/works-factory-line.yaml", "workflows/fix/works-factory-fix.yaml", "workflows/fix/scripts/x.py"):
            with self.subTest(changed=rel):
                self.write(rel, "# changed\n")
                rc, stdout, out = self.run_changed()
                self.assertEqual(rc, 0, out)
                self.assertIn("tests.e2e.test_scenario", stdout)
                self.assertEqual(self.ran(out), 2, out)
                self.assertNotIn(IN_CI, stdout)
                self.assertNotIn("tests/e2e/test_scenario.py", self.block(stdout, UNRUN) or [], "回す試験を回さない欄に出さない")
                git(self.repo, "checkout", "-q", "--", rel)

    def test_scenario_test_runs_with_a_whole_suite_change(self):
        self.commit_scenario_copy()
        self.write("tests/archon.py", "# changed\n")
        self.write("workflows/fix/works-factory-fix.yaml", "# changed\n")
        rc, stdout, out = self.run_changed()
        self.assertEqual(rc, 0, out)
        self.assertIn(IN_CI, stdout)
        self.assertIn("tests.e2e.test_scenario", stdout)
        self.assertEqual(self.ran(out), 2, out)
        self.assertNotIn("tests/e2e/test_scenario.py", self.block(stdout, UNRUN) or [], "回す試験を回さない欄に出さない")

    def test_far_unanalysable_is_named_without_the_ci_heading(self):
        self.commit_deep_chain("import importlib\nfrom lib import mid\n\n\ndef load(name):\n"
                               "    return importlib.import_module(name)\n")
        self.write("lib/alpha.py", "def value():\n    return 1  # changed\n")
        rc, stdout, out = self.run_changed()
        self.assertEqual(rc, 0, out)
        far = self.block(stdout, FAR)
        self.assertIsNotNone(far, stdout)
        self.assertEqual(far, ["dynamic-import: lib/far.py:6"], stdout)
        self.assertNotIn(IN_CI, stdout)

    def test_no_base_runs_only_the_fence_and_defers_to_ci(self):
        git(self.repo, "update-ref", "-d", "refs/remotes/origin/main")
        self.write("lib/alpha.py", "def value():\n    return 1  # changed\n")
        rc, stdout, out = self.run_changed()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.ran(out), 1, out)
        self.assertIn(IN_CI, stdout)
        self.assertIn("origin/main", stdout)

    def test_no_git_runs_only_the_fence_and_defers_to_ci(self):
        rc, stdout, out = self.run_changed(PATH="")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.ran(out), 1, out)
        self.assertIn(IN_CI, stdout)
        self.assertIn("origin/main", stdout)

    def test_change_with_no_tests_still_runs_the_fence(self):
        self.write("docs/note.md", "# note\n\nchanged\n")
        rc, stdout, out = self.run_changed()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.ran(out), 1, out)
        self.assertIn("tests.layers.test_fence", stdout)

    def test_unselected_import_cannot_change_the_selected_test(self):
        """選ばない試験の import は、選んだ試験の遅延 import に混ざらない。"""
        self.write("lib/tests/test_beta.py", "import sys\nsys.modules['lib.alpha'].value = lambda: 99\n" + TWO_TESTS)
        git(self.repo, "commit", "-q", "-am", "polluting unselected module")
        git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        self.write("lib/alpha.py", "def value():\n    return 1  # changed\n")
        for workers in ("1", "2"):
            with self.subTest(workers=workers):
                rc, stdout, out = self.run_changed(WORKS_FACTORY_TEST_WORKERS=workers)
                self.assertEqual(rc, 0, out)
                self.assertEqual(self.ran(out), 2, out)
                self.assertNotIn("  lib.tests.test_beta\n", stdout)

    def test_red_selected_test_is_red(self):
        self.write("lib/alpha.py", "def value():\n    return 2\n")
        rc, _stdout, out = self.run_changed()
        self.assertNotEqual(rc, 0, out)
        self.assertEqual(self.ran(out), 2, out)

    def test_test_package_that_fails_to_import_is_red(self):
        self.write("lib/tests/__init__.py", "raise ImportError('broken package')\n")
        self.write("lib/tests/test_alpha.py", LIB_TEST.format(name="alpha") + "\n# changed\n")
        rc, stdout, out = self.run_changed()
        self.assertNotEqual(rc, 0, out)
        self.assertIn("lib.tests", stdout)

    def test_changing_the_collection_rule_changes_both_selections(self):
        shard = self.repo / "tests/shard.py"
        shard.write_text(shard.read_text(encoding="utf-8").replace('PATTERN = "test*.py"', 'PATTERN = "check*.py"'),
                         encoding="utf-8")
        git(self.repo, "commit", "-q", "-am", "rule")
        git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        self.write("lib/tests/check_alpha.py", LIB_TEST.format(name="alpha"))
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "check")
        git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        self.write("lib/alpha.py", "def value():\n    return 1  # changed\n")
        rc, stdout, out = self.run_changed()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.ran(out), 1, out)
        self.assertIn("lib.tests.check_alpha", stdout)
        self.assertNotIn("tests.layers.test_fence", stdout)
        done = subprocess.run([sys.executable, "-m", "tests.shard", "--shard", "1/1"], cwd=self.repo, capture_output=True,
                              text=True, encoding="utf-8", env=hermetic.child_env())
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.ran(done.stderr), 1, done.stderr)

    def test_output_ends_with_the_unittest_count(self):
        self.write("lib/alpha.py", "def value():\n    return 1  # changed\n")
        _rc, _stdout, out = self.run_changed()
        lines = [line for line in out.splitlines() if line.strip()]
        self.assertEqual(len(COUNT.findall(out)), 1, out)
        self.assertRegex(lines[-2], r"^Ran \d+ tests? in ")
        self.assertEqual(lines[-1], "OK")

    def test_parallel_run_keeps_the_names_and_counts_of_a_serial_run(self):
        self.write("lib/beta.py", "def value():\n    return 1  # changed\n")
        self.write("lib/tests/test_gamma.py", ONE_TEST)
        runs = {n: self.run_changed(WORKS_FACTORY_TEST_WORKERS=n) for n in ("1", WORKERS)}
        for _rc, stdout, out in runs.values():
            self.assertIn("回さない: 1 モジュール", stdout, out)
            for name in ("lib.tests.test_beta", "lib.tests.test_gamma", "tests.layers.test_fence"):
                self.assertIn(f"  {name}\n", stdout, out)
        (serial_rc, serial_stdout, serial_out), (rc, stdout, out) = runs.values()
        self.assertEqual((rc, self.ran(out), out.splitlines()[-1]), (serial_rc, self.ran(serial_out), "OK"), out)
        self.assertEqual(stdout.split("\n", 1)[1], serial_stdout.split("\n", 1)[1])   # 1 行目は選びの秒数

    def test_parallel_run_names_the_failing_test_with_its_traceback(self):
        self.write("lib/alpha.py", "def value():\n    return 2\n")
        self.write("lib/beta.py", "def value():\n    return 1  # changed\n")
        rc, _stdout, out = self.run_changed()
        self.assertEqual(rc, 1, out)
        self.assertEqual(self.ran(out), 4, out)
        self.assertIn("FAIL: test_one (lib.tests.test_alpha.T.test_one)\n", out)
        self.assertIn("Traceback (most recent call last):", out)
        self.assertIn("AssertionError: 2 != 1", out)
        self.assertEqual(out.splitlines()[-1], "FAILED (failures=1)")

    def test_modules_run_in_separate_children(self):
        pids = self.repo / "pids"
        pids.mkdir()
        for name, other in (("a", "b"), ("b", "a")):
            # 自分の pid を書いた後、もう 1 つのモジュールの pid が書かれるまで抱える（同じ子が両方を回せば、待ちが切れてから
            # 同じ pid が 2 つ書かれて赤になる。機械が重くても、別の子が次のモジュールを取るまで重なりが続く）
            self.write(f"tests/layers/test_pid_{name}.py",
                       "import os, time, unittest\n\n\nclass T(unittest.TestCase):\n    def test_pid(self):\n"
                       f"        open({str(pids / name)!r}, 'w').write(str(os.getpid()))\n"
                       "        end = time.monotonic() + 10\n"
                       f"        while not os.path.exists({str(pids / other)!r}) and time.monotonic() < end:\n"
                       "            time.sleep(0.05)\n")
        rc, _stdout, out = self.run_changed(WORKS_FACTORY_TEST_WORKERS="2")
        self.assertEqual(rc, 0, out)
        self.assertNotEqual((pids / "a").read_text(encoding="utf-8"), (pids / "b").read_text(encoding="utf-8"), out)

    def test_the_worker_count_from_the_environment_reaches_the_runner(self):
        rc, _stdout, out = self.run_changed(WORKS_FACTORY_TEST_WORKERS="0")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("1 以上の整数", out)

    def cases(self, report):
        return {(c.get("classname"), c.get("name")): c for c in ElementTree.parse(report).getroot().iter("testcase")}

    def test_junit_xml_lists_every_selected_test_without_changing_the_output(self):
        self.write("lib/alpha.py", "def value():\n    return 1  # changed\n")
        report = self.repo.parent / "out" / "report.xml"
        plain_rc, plain_stdout, plain_out = self.run_changed()
        self.assertFalse(report.exists())
        rc, stdout, out = self.run_changed("--junit-xml", report)
        self.assertEqual((rc, stdout.split("\n", 1)[1]), (plain_rc, plain_stdout.split("\n", 1)[1]), out)   # 1 行目は選びの秒数
        self.assertEqual(self.ran(out), self.ran(plain_out), out)
        self.assertTrue(report.exists(), out)
        cases = self.cases(report)
        self.assertEqual(sorted(cases), [("lib.tests.test_alpha.T", "test_one"), ("tests.layers.test_fence.T", "test_one")])
        self.assertEqual([list(c) for c in cases.values()], [[], []])
        self.write("lib/alpha.py", "def value():\n    return 2\n")
        rc, _stdout, out = self.run_changed("--junit-xml", report)
        self.assertEqual(rc, 1, out)
        cases = self.cases(report)
        self.assertEqual([e.tag for e in cases[("lib.tests.test_alpha.T", "test_one")]], ["failure"])
        self.assertEqual(list(cases[("tests.layers.test_fence.T", "test_one")]), [])

    def test_relative_junit_xml_path_is_from_the_callers_directory(self):
        self.write("lib/alpha.py", "def value():\n    return 1  # changed\n")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        rc, _stdout, out = self.run_changed("--junit-xml", "report.xml", cwd=tmp.name)
        self.assertEqual(rc, 0, out)
        self.assertTrue((pathlib.Path(tmp.name) / "report.xml").exists(), out)
        self.assertFalse((self.repo / "report.xml").exists())

    def test_unread_arguments_are_dropped_with_a_note_and_the_run_goes_on(self):
        self.write("lib/alpha.py", "def value():\n    return 1  # changed\n")
        report = self.repo.parent / "report.xml"
        rc, stdout, out = self.run_changed("--junit-xml", report, "tests/test_x.py::T::test_one", "-k", "foo")
        self.assertTrue(report.exists(), out)
        self.assertEqual(rc, 0, out)
        self.assertIn("lib.tests.test_alpha", stdout)
        notes = [line for line in out[len(stdout):].splitlines() if line.startswith("changed.py: 読まない引数")]
        self.assertEqual(len(notes), 1, out)
        for dropped in ("tests/test_x.py::T::test_one", "-k", "foo"):
            self.assertIn(dropped, notes[0])
        self.assertNotIn("読まない引数", self.run_changed()[2])

    def test_help_and_an_abbreviated_option_are_dropped_not_obeyed(self):
        self.write("lib/alpha.py", "def value():\n    return 1  # changed\n")
        report = self.repo.parent / "abbrev.xml"
        rc, stdout, out = self.run_changed("-h", "--help", "--junit", report)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.ran(out), 2, out)   # -h で止まらず、選びどおり回る
        self.assertIn("lib.tests.test_alpha", stdout)
        self.assertFalse(report.exists(), out)   # 略は --junit-xml と読まない
        notes = [line for line in out[len(stdout):].splitlines() if line.startswith("changed.py: 読まない引数")]
        self.assertEqual(len(notes), 1, out)
        for dropped in ("-h", "--help", "--junit", str(report)):
            self.assertIn(dropped, notes[0])


if __name__ == "__main__":
    unittest.main()

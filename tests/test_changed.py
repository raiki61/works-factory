"""作業中の試験の選びの殻（tests/changed.py）の試験。

使い捨ての git の木（殻と選びと分けの写し COPIED と、小さな lib と試験）で殻を起こし、
unittest の最後の数え（Ran N tests）で何が回ったかを見る。木の試験は test_alpha 1 本・test_beta 2 本・層の柵 1 本。
- lib の 1 ファイルを変えると、その試験のモジュールと層の柵だけが回る
- 選べない時（tests/archon.py などの変更・選びが全部が要ると言った時・起点（origin/main との merge-base）が無い時・git が起こせない時）も
  全部は回さず、選べた範囲と層の柵だけを回し、全部の試験は CI に寄せるの 1 行と訳を出して緑（持ち主の決め full-suite-in-ci）
- 選んだ物が 0 本でも層の柵は回り、選んだ試験の赤は殻の赤
- 頭で読み込めない試験のパッケージの下を変えると赤（パッケージ名の 1 件を選ぶ）
- 集め方の正本（tests/shard.py の PATTERN）を変えると、殻の選び（変わった lib を import する試験も）と CI の分けの両方が変わる
- 出力の最後は unittest の数え（Ran N tests）で、数えの形 COUNT が最初に当たるのもその行
- 試験は既定で子 WORKERS 個に並べて回す。並べても、選んだモジュールの名と回さないモジュールの数・回った数は 1 つの子で順に回した時と
  同じで、落ちた試験は名と traceback が出て、最後は FAILED
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.bin import hermetic
from tests.bin.gitkit import git

ROOT = pathlib.Path(__file__).resolve().parents[1]
IN_CI = "全部の試験は CI に寄せる（持ち主の決め full-suite-in-ci）"
WORKERS = "3"
COUNT = re.compile(r"Ran (\d+) tests?")
COPIED = ("lib/impact.py", "lib/changemap.py", "tests/changed.py", "tests/shard.py", "tests/bin/hermetic.py",
          "workflows/.shared/boundary.py")
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

    def run_changed(self, **overrides):
        env = hermetic.child_env(**{"WORKS_FACTORY_TEST_WORKERS": WORKERS, **overrides})
        done = subprocess.run([sys.executable, "tests/changed.py"], cwd=self.repo, capture_output=True, text=True,
                              encoding="utf-8", env=env)
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


if __name__ == "__main__":
    unittest.main()

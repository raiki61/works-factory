"""作業中の試験の選びの殻（tests/changed.py）の試験。

使い捨ての git の木（lib/impact.py・lib/changemap.py・tests/changed.py の写しと、小さな lib と試験）で殻を起こし、
unittest の最後の数え（Ran N tests）で何が回ったかを見る。木の試験は test_alpha 1 本・test_beta 2 本・層の柵 1 本。
- lib の 1 ファイルを変えると、その試験のモジュールと層の柵だけが回る
- 全部を回す: tests/archon.py などの変更・起点（origin/main との merge-base）が無い時・git が起こせない時
- 選んだ物が 0 本でも層の柵は回り、選んだ試験の赤は殻の赤
- 出力の最後は unittest の数えで、harness の unit_count_pattern が最初に当たるのもその行
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.bin.gitkit import git

ROOT = pathlib.Path(__file__).resolve().parents[1]
COUNT = re.compile(json.loads((ROOT / "harness" / "harness.config.json").read_text(encoding="utf-8"))["unit_count_pattern"])
COPIED = ("lib/impact.py", "lib/changemap.py", "tests/changed.py")
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
            shutil.copyfile(ROOT / rel, self.repo / rel)
        git(self.repo, "init", "-q")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "seed")
        git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")

    def write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def run_changed(self, env=None):
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

    def test_archon_helper_change_runs_everything(self):
        self.write("tests/archon.py", "# changed\n")
        rc, stdout, out = self.run_changed()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.ran(out), 4, out)
        self.assertIn("tests/archon.py", stdout)

    def test_no_base_runs_everything(self):
        git(self.repo, "update-ref", "-d", "refs/remotes/origin/main")
        self.write("lib/alpha.py", "def value():\n    return 1  # changed\n")
        rc, stdout, out = self.run_changed()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.ran(out), 4, out)
        self.assertIn("origin/main", stdout)

    def test_no_git_runs_everything(self):
        rc, stdout, out = self.run_changed(env={**os.environ, "PATH": ""})
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.ran(out), 4, out)
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

    def test_output_ends_with_the_unittest_count(self):
        self.write("lib/alpha.py", "def value():\n    return 1  # changed\n")
        _rc, _stdout, out = self.run_changed()
        lines = [line for line in out.splitlines() if line.strip()]
        self.assertEqual(len(COUNT.findall(out)), 1, out)
        self.assertRegex(lines[-2], r"^Ran \d+ tests? in ")
        self.assertEqual(lines[-1], "OK")


if __name__ == "__main__":
    unittest.main()

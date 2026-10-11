"""ブロックの script（workflows/*/scripts/*.py）の頭の uv の script の宣言の試験。

Archon は script の節（runtime: uv）を対象の作業ツリーを cwd に `uv run <ファイル>` で起こす。宣言が無いと uv は対象の
pyproject.toml を拾い、作業ツリーに .venv と uv.lock を作る（作業ツリーを変えない約束が破れる）。
- どの script も頭の 4 行が同じ宣言
- pyproject.toml を置いた種の写しを cwd に `uv run` で起こしても、`git status --porcelain --ignored` が前後で同じ
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.bin.gitkit import committed_copy, git

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEED = ROOT / "tests" / "e2e" / "target-seed"
SCRIPTS = sorted((ROOT / "workflows").glob("*/scripts/*.py"))
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))

import tree_run  # noqa: E402

HEADER = ["# /// script", '# requires-python = ">=3.12"', "# dependencies = []", "# ///"]
PYPROJECT = '[project]\nname = "target"\nversion = "0"\nrequires-python = ">=3.12"\n'
WAIT = 120   # uv が script の環境を初めて組む回も入る上限（秒）


class HeaderTest(unittest.TestCase):
    def test_scripts_exist(self):
        self.assertTrue(SCRIPTS, "workflows/*/scripts/*.py が 1 本も無い")

    def test_every_script_declares_itself(self):
        for script in SCRIPTS:
            with self.subTest(script=str(script.relative_to(ROOT))):
                self.assertEqual(script.read_text(encoding="utf-8").splitlines()[:4], HEADER)


class UvRunTest(unittest.TestCase):
    def setUp(self):
        if shutil.which("uv") is None:
            self.skipTest("uv が無い")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, SEED)
        (self.repo / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
        git(self.repo, "add", "pyproject.toml")
        git(self.repo, "commit", "-q", "-m", "pyproject")

    def status(self) -> str:
        return git(self.repo, "status", "--porcelain", "--ignored")

    def test_uv_run_leaves_the_tree_alone(self):
        env = {k: v for k, v in tree_run.outside_env(os.environ).items() if not k.startswith("INPUTS_")}
        env.pop("VIRTUAL_ENV", None)
        for script in SCRIPTS:
            with self.subTest(script=str(script.relative_to(ROOT))):
                artifacts = self.tmp / "artifacts" / script.parent.parent.name / script.stem
                artifacts.mkdir(parents=True)
                before = self.status()
                done = subprocess.run(["uv", "run", str(script)], cwd=self.repo, stdin=subprocess.DEVNULL,
                                      capture_output=True, text=True, encoding="utf-8", timeout=WAIT,
                                      env={**env, "WORKFLOW_ID": "run-uv", "ARTIFACTS_DIR": str(artifacts),
                                           "WORKS_FACTORY_ROOT": str(ROOT)})
                self.assertEqual(self.status(), before, f"作業ツリーを変えた\n{done.stderr}")


if __name__ == "__main__":
    unittest.main()

"""通しの対象の作り手 tests/e2e/make_target.py の試験。

make_target.py は、自分の在る checkout の git の私用の置き場に控えを書くので、本物の checkout では走らせない。
tests/bin/fakelaunch.py の木（写した bin/ と偽の Archon の源）に make_target.py と種を写して git の checkout にし、そこで走らせる。
teardown の殻の後ろの Archon は偽の bun で、受けた命令を控え、workflow status には走っている run を 1 つ答える。
本物の Archon と同じく、--cwd（無ければ cwd）が git のリポジトリでなければ命令を拒む。FAKE_FAILS に並べた命令は落とす。
"""
import ast
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import tokenize
import unittest
import xml.etree.ElementTree as ET

from tests.bin import fakelaunch, hermetic
from tests.bin.gitkit import git

E2E = pathlib.Path(__file__).resolve().parent
LEDGER = ("works-factory-e2e", "homes")

FAKE_BUN = """#!/usr/bin/env python3
import json, os, subprocess, sys
args = sys.argv[sys.argv.index("workflow"):]
with open(os.environ["FAKE_BUN_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"args": args, "archon_home": os.environ.get("ARCHON_HOME")}) + "\\n")
cwd = args[args.index("--cwd") + 1] if "--cwd" in args else os.getcwd()
if subprocess.run(["git", "-C", cwd, "rev-parse", "--git-dir"], capture_output=True).returncode != 0:
    sys.exit("Error: Not in a git repository.")
if args[1] in os.environ.get("FAKE_FAILS", "").split(","):
    sys.exit(1)
if args[1] == "status":
    print(json.dumps({"runs": [{"id": "run-a", "status": "running"}], "scopeFallback": False}))
"""


class MakeTargetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="works-make-target-")
        tree = fakelaunch.build(pathlib.Path(os.path.realpath(cls._tmp.name)))
        cls.repo, cls.tree = tree.repo, tree
        shutil.copytree(E2E / "target-seed", cls.repo / "tests" / "e2e" / "target-seed",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(E2E / "make_target.py", cls.repo / "tests" / "e2e" / "make_target.py")
        git(cls.repo, "init", "-q")
        git(cls.repo, "add", "-A")
        git(cls.repo, "commit", "-q", "-m", "checkout")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        fake = self.tmp / "fake-bin"
        fakelaunch.put(fake / "bun", FAKE_BUN)
        self.bun_log = self.tmp / "bun.jsonl"
        self.env = hermetic.child_env(HOME=str(self.tmp / "user-home"), XDG_CACHE_HOME=str(self.tree.cache_home),
                                      PATH=os.pathsep.join([str(fake), os.environ.get("PATH", "")]),
                                      FAKE_BUN_LOG=str(self.bun_log))
        self.addCleanup(self.clear_ledger, self.repo)

    def clear_ledger(self, checkout):
        self.ledger(checkout).unlink(missing_ok=True)

    def ledger(self, checkout) -> pathlib.Path:
        return pathlib.Path(git(checkout, "rev-parse", "--absolute-git-dir")).joinpath(*LEDGER)

    def make_target(self, *args, checkout=None, **env):
        script = (checkout or self.repo) / "tests" / "e2e" / "make_target.py"
        return subprocess.run([sys.executable, str(script), *args], env={**self.env, **env}, cwd=self.tmp,
                              capture_output=True, text=True, encoding="utf-8", timeout=120)

    def make(self, attempt) -> dict:
        done = self.make_target("make", str(attempt))
        self.assertEqual(done.returncode, 0, done.stderr)
        made = json.loads(done.stdout)
        self.assertEqual(sorted(made), ["home", "origin", "request", "target"])
        for path in made.values():
            self.assertTrue(os.path.isabs(path), path)
        return {k: pathlib.Path(v) for k, v in made.items()}

    def calls(self) -> list[dict]:
        if not self.bun_log.exists():
            return []
        return [json.loads(line) for line in self.bun_log.read_text(encoding="utf-8").splitlines()]

    def test_make_builds_clean_target_with_origin(self):
        before = git(self.repo, "status", "--porcelain", "--untracked-files=normal")
        made = self.make(self.tmp / "attempt")
        target = made["target"]
        self.assertEqual(target, self.tmp / "attempt" / "target")
        self.assertEqual(git(target, "status", "--porcelain"), "")
        self.assertIn("ref: refs/heads/main\tHEAD", git(target, "ls-remote", "--symref", "origin", "HEAD"))
        self.assertEqual(git(target, "symbolic-ref", "refs/remotes/origin/HEAD"), "refs/remotes/origin/main")
        self.assertEqual(git(made["origin"], "rev-parse", "--is-bare-repository"), "true")
        self.assertEqual(git(made["origin"], "rev-list", "--count", "main"), "1")
        self.assertFalse((target / "request_ok.json").exists())
        self.assertEqual(made["request"].read_bytes(), (E2E / "target-seed" / "request_ok.json").read_bytes())
        self.assertFalse(made["request"].is_relative_to(target))
        self.assertEqual(list(made["home"].iterdir()), [])
        self.assertTrue(git(target, "ls-files", "-s", "junit-suite.sh").startswith("100755 "))
        self.assertTrue(os.access(target / "junit-suite.sh", os.X_OK))
        self.assertEqual(git(self.repo, "status", "--porcelain", "--untracked-files=normal"), before)
        self.assertEqual(self.ledger(self.repo).read_text(encoding="utf-8"), f"{made['home']}\t{target}\n")

    def test_seed_target_is_red(self):
        target = self.make(self.tmp / "attempt")["target"]
        done = subprocess.run([sys.executable, "-m", "unittest", "-v"], cwd=target, capture_output=True, text=True,
                              encoding="utf-8", env={**self.env, "PYTHONDONTWRITEBYTECODE": "1"}, timeout=120)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("Ran 3 tests", done.stderr)
        self.assertIn("FAILED (failures=2)", done.stderr)

    @unittest.skipIf(shutil.which("uv") is None, "uv が無い（junit-suite.sh は uv で pytest を起こす）")
    def test_junit_suite_writes_two_failures(self):
        target = self.make(self.tmp / "attempt")["target"]
        out = self.tmp / "junit.xml"
        done = subprocess.run(["./junit-suite.sh", str(out)], cwd=target, capture_output=True, text=True,
                              encoding="utf-8", env=self.env, timeout=600)
        self.assertNotEqual(done.returncode, 0, done.stdout)
        suites = ET.parse(out).getroot()
        failures = [case.get("name") for case in suites.iter("testcase") if case.find("failure") is not None]
        self.assertEqual(sorted(failures), ["test_clamp_above_range", "test_mean_of_three"])
        self.assertEqual(git(target, "status", "--porcelain"), "")

    @unittest.skipIf(shutil.which("uv") is None, "uv が無い（junit-suite.sh は uv で pytest を起こす）")
    def test_junit_suite_runs_only_given_nodes(self):
        target = self.make(self.tmp / "attempt")["target"]
        out = self.tmp / "junit.xml"
        done = subprocess.run(["./junit-suite.sh", str(out), "test_stats.py::TestStats::test_mean_of_three"], cwd=target,
                              capture_output=True, text=True, encoding="utf-8", env=self.env, timeout=600)
        self.assertNotEqual(done.returncode, 0, done.stdout)
        cases = list(ET.parse(out).getroot().iter("testcase"))
        self.assertEqual([(c.get("name"), c.find("failure") is not None) for c in cases], [("test_mean_of_three", True)])

    def test_make_takes_seed_and_request(self):
        seed = self.tmp / "other-seed"
        seed.mkdir()
        (seed / "only.txt").write_text("x\n", encoding="utf-8")
        request = self.tmp / "ask.json"
        request.write_text('[{"where": "only.txt", "text": "y"}]\n', encoding="utf-8")
        done = self.make_target("make", str(self.tmp / "attempt"), "--seed", str(seed), "--request", str(request))
        self.assertEqual(done.returncode, 0, done.stderr)
        made = {k: pathlib.Path(v) for k, v in json.loads(done.stdout).items()}
        self.assertEqual(git(made["target"], "ls-files"), "only.txt")
        self.assertEqual(made["request"].read_bytes(), request.read_bytes())
        self.assertEqual(self.ledger(self.repo).read_text(encoding="utf-8"), f"{made['home']}\t{made['target']}\n")

    def test_make_without_ledger_is_not_torn_down(self):
        done = self.make_target("make", str(self.tmp / "attempt"), "--no-ledger")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(self.ledger(self.repo).exists())
        self.assertEqual(self.make_target("teardown").returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_stop_cancels_only_runs_of_that_attempt(self):
        mine = self.make_target("make", str(self.tmp / "mine"), "--no-ledger")
        self.assertEqual(mine.returncode, 0, mine.stderr)
        mine = {k: pathlib.Path(v) for k, v in json.loads(mine.stdout).items()}
        theirs = self.make(self.tmp / "theirs")
        done = self.make_target("stop", str(self.tmp / "mine"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([c["args"][:3] for c in self.calls()],
                         [["workflow", "status", "--all"], ["workflow", "runs", "--all"], ["workflow", "get", "run-a"], ["workflow", "cancel", "run-a"]])
        self.assertTrue(all(pathlib.Path(c["archon_home"]).is_relative_to(mine["home"]) for c in self.calls()))
        self.assertEqual(self.ledger(self.repo).read_text(encoding="utf-8"), f"{theirs['home']}\t{theirs['target']}\n")

    def test_stop_refuses_a_folder_without_a_home(self):
        done = self.make_target("stop", str(self.tmp))
        self.assertEqual(done.returncode, 1)
        self.assertIn("home/", done.stderr)
        self.assertEqual(self.calls(), [])

    def test_stop_exits_one_when_runs_are_left(self):
        for i, fails in enumerate(("status", "cancel,abandon")):
            with self.subTest(fails=fails):
                attempt = self.tmp / f"attempt-{i}"
                self.assertEqual(self.make_target("make", str(attempt), "--no-ledger").returncode, 0)
                done = self.make_target("stop", str(attempt), FAKE_FAILS=fails)
                self.assertEqual(done.returncode, 1, done.stderr)
                self.assertIn(str(attempt / "home"), done.stderr)

    def test_make_refuses_unknown_arguments(self):
        for args in (["--seed"], ["a", "b"], ["a", "--seed", "x", "--seed", "y"], ["a", "--force"]):
            with self.subTest(args=args):
                self.assertEqual(self.make_target("make", *args).returncode, 2)

    def test_make_refuses_non_empty_or_inside_checkout(self):
        full = self.tmp / "full"
        full.mkdir()
        (full / "x").write_text("x", encoding="utf-8")
        for attempt in (full, self.repo / "attempt"):
            with self.subTest(attempt=attempt):
                done = self.make_target("make", str(attempt))
                self.assertNotEqual(done.returncode, 0)
                self.assertEqual(len(done.stderr.strip().splitlines()), 1, done.stderr)
        self.assertFalse((self.repo / "attempt").exists())
        self.assertFalse(self.ledger(self.repo).exists())

    def test_teardown_cancels_runs_of_each_home(self):
        made = [self.make(self.tmp / f"attempt-{i}") for i in range(2)]
        done = self.make_target("teardown")
        self.assertEqual(done.returncode, 0, done.stderr)
        calls = self.calls()
        for one in made:
            with self.subTest(home=one["home"]):
                mine = [c["args"] for c in calls if pathlib.Path(c["archon_home"]).is_relative_to(one["home"])]
                self.assertEqual([args[:3] for args in mine],
                                 [["workflow", "status", "--all"], ["workflow", "runs", "--all"], ["workflow", "get", "run-a"], ["workflow", "cancel", "run-a"]])
                self.assertTrue(all(args[-2:] == ["--cwd", str(one["target"])] for args in mine), mine)
        self.assertEqual(self.ledger(self.repo).read_text(encoding="utf-8"), "")

    def test_teardown_keeps_home_it_cannot_stop(self):
        for i, fails in enumerate(("status", "cancel,abandon")):
            with self.subTest(fails=fails):
                made = self.make(self.tmp / f"attempt-{i}")
                done = self.make_target("teardown", FAKE_FAILS=fails)
                self.assertEqual(done.returncode, 1, done.stderr)
                self.assertIn(str(made["home"]), done.stderr)
                self.assertEqual(self.ledger(self.repo).read_text(encoding="utf-8"),
                                 f"{made['home']}\t{made['target']}\n")
                self.clear_ledger(self.repo)

    def test_make_target_sets_no_deadline(self):
        tree = ast.parse((E2E / "make_target.py").read_text(encoding="utf-8"))
        self.assertEqual([n.lineno for n in ast.walk(tree) if isinstance(n, ast.keyword) and n.arg == "timeout"], [])

    def test_teardown_abandons_when_cancel_fails(self):
        home = self.make(self.tmp / "attempt")["home"]
        done = self.make_target("teardown", FAKE_FAILS="cancel")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([c["args"][:3] for c in self.calls()],
                         [["workflow", "status", "--all"], ["workflow", "runs", "--all"], ["workflow", "get", "run-a"], ["workflow", "cancel", "run-a"],
                          ["workflow", "abandon", "run-a"]])
        self.assertTrue(all(pathlib.Path(c["archon_home"]).is_relative_to(home) for c in self.calls()))

    def test_teardown_leaves_other_checkout(self):
        other = self.tmp / "other-checkout"
        git(self.repo, "worktree", "add", "-q", "--detach", str(other))
        self.addCleanup(git, self.repo, "worktree", "remove", "--force", str(other))
        theirs = self.make_target("make", str(self.tmp / "theirs"), checkout=other)
        self.assertEqual(theirs.returncode, 0, theirs.stderr)
        their_ledger = self.ledger(other).read_text(encoding="utf-8")
        mine = self.make(self.tmp / "mine")["home"]
        done = self.make_target("teardown")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.ledger(other).read_text(encoding="utf-8"), their_ledger)
        self.assertTrue(all(pathlib.Path(c["archon_home"]).is_relative_to(mine) for c in self.calls()))


class SeedTextCase(unittest.TestCase):
    """種のコードの文（docstring とコメント）が、仕込んだバグの中身を書かない（説明は make_target.py の docstring に置く）"""
    BUG_WORDS = ("バグ", "仕込", "赤", "正しく", "分母", "len(xs)", "lo を返", "hi を返", "3 件中")

    @staticmethod
    def texts(source: str) -> list:
        tree = ast.parse(source)
        docs = [ast.get_docstring(n) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        comments = [t.string for t in tokenize.generate_tokens(io.StringIO(source).readline) if t.type == tokenize.COMMENT]
        return [x for x in docs + comments if x]

    def test_seed_text_does_not_describe_the_bugs(self):
        files = sorted((E2E / "target-seed").glob("*.py"))
        self.assertTrue(files)
        for path in files:
            for text in self.texts(path.read_text(encoding="utf-8")):
                for word in self.BUG_WORDS:
                    with self.subTest(file=path.name, word=word):
                        self.assertNotIn(word, text)

    def test_the_words_catch_the_old_docstring(self):
        old = '"""使い捨ての対象リポジトリの種。\n\n- mean: 分母が len(xs) - 1 になっている（正しくは len(xs)）。\n"""\n# 3 件中 2 件が赤\n'
        self.assertTrue(any(w in t for t in self.texts(old) for w in self.BUG_WORDS))


if __name__ == "__main__":
    unittest.main()

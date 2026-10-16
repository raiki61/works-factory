"""SWE-Bench Pro V2 の口 tests/calibration/swepro.py と Harbor の殻 swepro_agent.py の試験。Harbor・docker・Archon・claude・網を
使わない。殻は sys.modules に差した harbor の stub の上で読み、起こし役 inside は偽の works-factory の殻（test_run.FAKE_SHELL を
差し替え口 WORKS_CALIBRATION_SHELL で渡す）と PATH の頭の偽の claude で回す。

fixture の課題 1 件分（instruction.md と task.toml だけ。正解と隠した試験は写さない）の出どころは
github.com/scaleapi/SWE-bench_Pro-os の commit 66f92766bba642462d4bbe5479e83f91f9211862 の v2/tasks/（MIT。Scale AI）。
"""
import ast
import asyncio
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import types
import unittest
from unittest import mock

import yaml

from tests.bin import hermetic
from tests.bin.gitkit import git
from tests.calibration import run as runner
from tests.calibration import swepro, test_run

import green_cert  # noqa: E402  swepro が lib/ を sys.path に足す

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
OPENLIBRARY = "instance_internetarchive__openlibrary-00bec1e7c8f3272c469a58e1377df03f955ed478-v13642507b4fc1f8d234172bf8129942da2c2ca26"
FIXTURE = HERE / "fixtures" / "swepro" / OPENLIBRARY
ANSIBLE = "instance_ansible__ansible-0ea40e09d1b35bcb69ff4d9cecf3d0defa4b36e8-v30a923fb5c164d6cd18280c02422f75e611e8fb2"
QUTEBROWSER = "instance_qutebrowser__qutebrowser-01d1d1494411380d97cac14614a829d3a69cecaf-v2ef375ac784985212b1805e1d0431dc8f1b3c171"
FLIPT = "instance_flipt-io__flipt-518ec324b66a07fdd95464a5e9ca5fe7681ad8f9"
IMAGE = "ghcr.io/scaleapi/swe-bench_pro-v2:{}"
TOKEN = "sk-ant-oat01-test-zq7-not-a-real-token"
RUN_ID = "a1b2c3d4-0000-run"
DIFF = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
WARNING = 'WARN[0000] The "X" variable is not set. Defaulting to a blank string.\n'
POINTER = {"type": swepro.apply.POINTER_TYPE, "run_id": RUN_ID, "path": swepro.apply.APPLY_DIFF}

FAKE_CLAUDE = """#!PYTHON
import json, os, sys
args = sys.argv[1:]
if args == ["--version"]:
    print(os.environ.get("FAKE_CLAUDE_VERSION", "9.9.9") + " (Claude Code)")
    sys.exit(0)
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"who": "claude", "args": args, "cwd": os.getcwd(), "names": sorted(os.environ),
                        "env": {k: os.environ.get(k) for k in ("HOME", "CLAUDE_CONFIG_DIR")}}) + "\\n")
if os.environ.get("FAKE_CLAUDE_ERROR"):
    print(json.dumps({"is_error": True, "result": os.environ["FAKE_CLAUDE_ERROR"], "session_id": "s"}))
    sys.exit(1)
with open("a.py", "w", encoding="utf-8") as f:
    f.write("x = 3\\n")
print(json.dumps({"is_error": False, "total_cost_usd": 1.5, "duration_ms": 1000, "session_id": "s"}))
"""


def fixture_inputs() -> dict:
    image = tomllib.loads((FIXTURE / "task.toml").read_text(encoding="utf-8"))["environment"]["docker_image"]
    return swepro.task_inputs((FIXTURE / "instruction.md").read_text(encoding="utf-8"), image)


def fake_claude(where: pathlib.Path) -> pathlib.Path:
    where.mkdir(parents=True, exist_ok=True)
    (where / "claude").write_text(FAKE_CLAUDE.replace("PYTHON", sys.executable), encoding="utf-8")
    (where / "claude").chmod(0o755)
    return where


class TaskInputsTest(unittest.TestCase):
    def test_fixture_makes_request_and_test_command(self):
        got = fixture_inputs()
        self.assertEqual(got["instance_id"], OPENLIBRARY)
        self.assertEqual(got["request"], [{"where": f"SWE-Bench Pro V2 {OPENLIBRARY}",
                                           "text": (FIXTURE / "instruction.md").read_text(encoding="utf-8")}])
        self.assertEqual(got["test_cmd"], swepro.TEST_COMMANDS["internetarchive/openlibrary"])

    def test_each_python_repository_has_its_row(self):
        for instance, repo in ((ANSIBLE, "ansible/ansible"), (QUTEBROWSER, "qutebrowser/qutebrowser")):
            with self.subTest(repo=repo):
                self.assertEqual(swepro.task_inputs("x", IMAGE.format(instance))["test_cmd"], swepro.TEST_COMMANDS[repo])
        self.assertEqual(len(swepro.TEST_COMMANDS), 3)

    def test_other_repository_is_refused(self):
        with self.assertRaises(swepro.BenchError) as caught:
            swepro.task_inputs("x", IMAGE.format(FLIPT))
        self.assertIn("flipt-io/flipt", str(caught.exception))
        with self.assertRaises(swepro.BenchError):
            swepro.task_inputs("x", "ghcr.io/scaleapi/swe-bench_pro-v2")

    def test_commands_run_in_the_worktree(self):
        for command in swepro.TEST_COMMANDS.values():
            self.assertNotIn("/app", command)

    def test_pro_limit_is_the_task_agent_timeout(self):
        task = tomllib.loads((FIXTURE / "task.toml").read_text(encoding="utf-8"))
        self.assertEqual(swepro.PRO_SECONDS, task["agent"]["timeout_sec"])

    def test_producers_are_the_runner_producers_but_old_works(self):
        self.assertEqual(set(runner.PRODUCERS) - set(swepro.PRODUCERS), {runner.OldWorks.name})
        self.assertLessEqual(set(swepro.PRODUCERS), set(runner.PRODUCERS))

    def test_test_cmd_is_a_main_graph_input(self):
        graph = yaml.safe_load((ROOT / "workflows" / "line" / "works-factory-line.yaml").read_text(encoding="utf-8"))
        self.assertIn("test_cmd", graph["inputs"])


class UnboundedTest(unittest.TestCase):
    def test_agent_multiplier_or_else_the_general_one_must_be_infinite(self):
        flag = "--agent-timeout-multiplier"
        for argv, want in ((["harbor", "run", flag, "inf"], True), (["harbor", "run", f"{flag}=inf"], True),
                           (["harbor", "run"], False), (["harbor", "run", flag, "2"], False),
                           (["harbor", "run", flag, "inf", flag, "2"], False), (["harbor", "run", flag], False),
                           (["harbor", "run", flag, "many"], False),
                           (["harbor", "run", "--timeout-multiplier", "inf"], True),
                           (["harbor", "run", "--timeout-multiplier=inf"], True),
                           (["harbor", "run", "--timeout-multiplier", "2"], False),
                           (["harbor", "run", "--timeout-multiplier", "inf", flag, "2"], False),
                           (["harbor", "run", "--timeout-multiplier", "2", flag, "inf"], True)):
            with self.subTest(argv=argv):
                self.assertEqual(swepro.unbounded(argv), want)


# 入っている Harbor の harbor run の旗（名 → click の型の名）を JSON で出す。Harbor が無ければ空の object。
# 入っているのに CLI を読めない時（Harbor の上げで模塊が動いた等）は落ちて、試験を赤にする
HARBOR_RUN_FLAGS = """
import importlib.util, json, sys
if importlib.util.find_spec("harbor") is None:
    print("{}")
    sys.exit(0)
import typer
from harbor.cli import main
command = typer.main.get_command(main.app).commands["run"]
print(json.dumps({o: p.type.name for p in command.params for o in p.opts}))
"""


class HarborFlagsTest(unittest.TestCase):
    """unbounded が読む旗が、入っている Harbor の harbor run に在り、inf を読める浮動小数の旗か。Harbor は CI に入れないので、
    uv run --isolated --extra bench で入れた環境でだけ照らす"""

    def test_unbounded_reads_flags_harbor_run_defines(self):
        done = subprocess.run([sys.executable, "-c", HARBOR_RUN_FLAGS], capture_output=True, text=True, encoding="utf-8",
                              env=hermetic.child_env())
        self.assertEqual(done.returncode, 0, f"入っている Harbor の harbor run の旗を読めない:\n{done.stderr}")
        flags = json.loads(done.stdout)
        if not flags:
            self.skipTest("Harbor が入っていない（uv run --isolated --extra bench で入る）")
        for flag in (swepro.AGENT_MULTIPLIER, swepro.MULTIPLIER):
            with self.subTest(flag=flag):
                self.assertEqual(flags.get(flag), "float", f"harbor run に浮動小数の旗 {flag} が無い")


class StoppedTest(unittest.TestCase):
    def test_paused_and_human_kinds_are_stopped(self):
        self.assertTrue(swepro.stopped("paused", ""))
        for word in swepro.report.OUTCOMES:
            with self.subTest(word=word):
                human = swepro.report.OUTCOME_KINDS.get(word) == swepro.chain.KIND_HUMAN
                self.assertEqual(swepro.stopped(runner.DONE, word), human)
        self.assertFalse(swepro.stopped("failed", ""))


class InsideTest(unittest.TestCase):
    """起こし役を子のプロセスで回す。workdir は a.py 1 つを commit した git の置き場"""

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.workdir = self.tmp / "app"
        self.workdir.mkdir()
        git(self.workdir, "init", "-q", "-b", "main")
        (self.workdir / "a.py").write_text("x = 1\n", encoding="utf-8")
        git(self.workdir, "add", "-A")
        git(self.workdir, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
        self.place, self.out = self.tmp / "place", self.tmp / "out"
        (self.place / "secret").mkdir(parents=True)
        (self.place / "task").mkdir()
        (self.place / swepro.TASK).write_text(json.dumps(fixture_inputs()), encoding="utf-8")
        self.secret()
        self.shell = self.tmp / "fake-shell.py"
        self.shell.write_text(test_run.FAKE_SHELL.replace("WATCHED", repr(test_run.WATCHED)).replace("UNITS", repr(test_run.UNITS))
                              .replace("JUDGMENT", repr(test_run.JUDGMENT)), encoding="utf-8")
        self.log, self.plan = self.tmp / "fake.jsonl", self.tmp / "plan.json"
        self.set_plan()
        self.env = hermetic.child_env(PATH=os.pathsep.join([str(fake_claude(self.tmp / "fake-bin")), os.environ.get("PATH", "")]),
                                      HOME=str(self.tmp / "user-home"), WORKS_CALIBRATION_SHELL=str(self.shell),
                                      FAKE_LOG=str(self.log), FAKE_PLAN=str(self.plan))

    def set_plan(self, **plan):
        self.plan.write_text(json.dumps(plan), encoding="utf-8")

    def secret(self, name=swepro.ACCEPTED_AUTH[0], value=TOKEN):
        (self.place / swepro.SECRET).write_text(json.dumps({name: value}), encoding="utf-8")

    def sealed_plan(self, diff=DIFF, **value):
        files = {test_run.JUDGMENT: test_run.UNITS, swepro.apply.APPLY_DIFF: diff}
        self.set_plan(value=value, artifacts=files)

    def inside(self, producer="works-factory"):
        done = subprocess.run([sys.executable, str(HERE / "swepro.py"), "inside", producer, "--workdir", str(self.workdir),
                               "--place", str(self.place), "--out", str(self.out)], env=self.env, capture_output=True, text=True,
                              encoding="utf-8")
        result = json.loads((self.out / swepro.RESULT).read_text(encoding="utf-8")) if (self.out / swepro.RESULT).exists() else None
        return done, result

    def patch(self) -> str:
        subprocess.run(["bash", "-c", swepro.capture_command(str(self.workdir), str(self.out))], check=True, env=hermetic.child_env())
        return (self.out / swepro.PATCH).read_text(encoding="utf-8")

    def calls(self, who="works-factory") -> list[dict]:
        rows = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []
        return [r for r in rows if r["who"] == who]

    def seal(self, diff=DIFF) -> dict:
        return {"ok": True, "hash": swepro.apply.seal.digest(diff.encode()), "diff": POINTER}

    def predicted(self, result, patch="") -> dict:
        return swepro.prediction(OPENLIBRARY, result["producer"], patch, result, 1.0, "f")

    def test_sealed_diff_is_applied_and_captured(self):
        self.sealed_plan(apply=self.seal(), sealed=self.seal())
        done, result = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual((self.workdir / "a.py").read_text(encoding="utf-8"), "x = 2\n")
        self.assertIn("+x = 2", self.patch())
        self.assertEqual((result["apply"]["code"], result["state"], result["error"]), (0, "done", None))
        predicted = self.predicted(result)
        self.assertEqual((predicted["stopped"], predicted["failed"]), (False, False))
        self.assertFalse(result["target_changed_during_run"])
        self.assertTrue((self.out / "evidence" / "record" / "parent.json").is_file())

    def test_factory_starts_with_origin_at_a_copy_of_head_in_the_attempt_place(self):
        self.sealed_plan(apply=self.seal(), sealed=self.seal())
        head = git(self.workdir, "rev-parse", "HEAD")
        done, result = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        copy = self.place / "attempt" / swepro.ORIGIN_COPY
        self.assertEqual(self.calls()[0]["origin"], str(copy))
        self.assertEqual(git(copy, "rev-parse", "HEAD"), head)
        self.assertEqual(git(copy, "symbolic-ref", "HEAD"), f"refs/heads/{swepro.ORIGIN_BRANCH}")
        self.assertEqual(result["error"], None)

    def test_origin_and_its_copy_stay_out_of_the_patch(self):
        self.sealed_plan(apply=self.seal(), sealed=self.seal())
        done, _ = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        patch = self.patch()
        self.assertEqual(re.findall(r"^diff --git .*$", patch, re.MULTILINE), ["diff --git a/a.py b/a.py"])
        self.assertNotIn(swepro.ORIGIN_COPY, patch)
        self.assertNotIn("[remote", patch)

    def test_target_with_a_remote_keeps_it(self):
        git(self.workdir, "remote", "add", "origin", "https://example.invalid/app.git")
        self.sealed_plan(apply=self.seal(), sealed=self.seal())
        done, _ = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.calls()[0]["origin"], "https://example.invalid/app.git")
        self.assertFalse((self.place / "attempt" / swepro.ORIGIN_COPY).exists())

    def test_origin_copy_that_cannot_be_made_stops_before_the_factory(self):
        (self.place / "attempt").mkdir(parents=True, exist_ok=True)
        (self.place / "attempt" / swepro.ORIGIN_COPY).write_text("not a repository\n", encoding="utf-8")
        self.sealed_plan(apply=self.seal(), sealed=self.seal())
        done, result = self.inside()
        self.assertEqual(done.returncode, swepro.run.STOPPED, done.stderr)
        self.assertIn("origin の写しを置けない", result["error"])
        self.assertEqual(self.calls(), [])

    def add_submodule(self, with_history=True):
        """workdir に submodule vendor/sub（中身は r.py と s.py）を名 lib-sub で足す。名と path を違えておく。.gitmodules の
        URL は網の先で、値の無い key（shallow）も持つ。/app の config に URL は無い（実走のイメージと同じ形）。with_history が
        偽なら submodule の git の歴史を消して中身のファイルだけを残す（openlibrary の課題のイメージと同じ形）"""
        sub = self.tmp / "sub"
        sub.mkdir()
        git(sub, "init", "-q", "-b", "main")
        (sub / "r.py").write_text("r = 1\n", encoding="utf-8")
        git(sub, "add", "-A")
        git(sub, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "one")
        (sub / "s.py").write_text("s = 1\n", encoding="utf-8")
        git(sub, "add", "-A")
        git(sub, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "two")
        git(self.workdir, "-c", "protocol.file.allow=always", "submodule", "add", "-q", "--name", "lib-sub", str(sub), "vendor/sub")
        git(self.workdir, "config", "-f", ".gitmodules", "submodule.lib-sub.url", "https://example.invalid/sub.git")
        with (self.workdir / ".gitmodules").open("a", encoding="utf-8") as f:
            f.write("\tshallow\n")
        git(self.workdir, "add", ".gitmodules")
        git(self.workdir, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "submodule")
        git(self.workdir, "config", "--remove-section", "submodule.lib-sub")
        if not with_history:
            shutil.rmtree(self.workdir / ".git" / "modules")
            (self.workdir / "vendor" / "sub" / ".git").unlink()

    def archon_config(self) -> dict:
        return yaml.safe_load((self.workdir / swepro.ARCHON_CONFIG).read_text(encoding="utf-8"))

    def factory_starts_with_archon_config_that_copies_submodule_contents(self, with_history):
        self.add_submodule(with_history=with_history)
        self.sealed_plan(apply=self.seal(), sealed=self.seal())
        done, result = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        expected = {"worktree": {"initSubmodules": False, "copyFiles": ["vendor/sub/r.py", "vendor/sub/s.py"]}}
        self.assertEqual(yaml.safe_load(self.calls()[0]["archon_config"]), expected)
        self.assertEqual(result["error"], None)

    def test_factory_starts_with_archon_config_that_copies_submodule_contents_but_not_its_git(self):
        self.factory_starts_with_archon_config_that_copies_submodule_contents(with_history=True)

    def test_factory_starts_with_archon_config_that_copies_submodule_contents_without_history(self):
        self.factory_starts_with_archon_config_that_copies_submodule_contents(with_history=False)

    def archon_worktree(self) -> pathlib.Path:
        """Archon と同じ形で /app から run の作業ツリーを切る: worktree add の後、initSubmodules が false なら submodule を
        初期化せず、copyFiles の各パスを /app から同じパスへ写す（Archon の packages/isolation/src/worktree-copy.ts の
        copyWorktreeFile。フォルダは中へ重ねて写す）。網は使わない"""
        config = self.archon_config()["worktree"]
        self.assertIs(config["initSubmodules"], False)
        tree = self.tmp / "wt"
        git(self.workdir, "worktree", "add", "-q", str(tree), "-b", "t")
        for rel in config["copyFiles"]:
            source, dest = self.workdir / rel, tree / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(source, dest)
        return tree

    def copied_submodule_contents_stay_out_of_the_seal_and_capture_diffs(self, with_history):
        self.add_submodule(with_history=with_history)
        swepro.give_submodules(self.workdir)
        tree = self.archon_worktree()
        self.assertEqual((tree / "vendor" / "sub" / "s.py").read_text(encoding="utf-8"), "s = 1\n")
        (tree / "a.py").write_text("x = 2\n", encoding="utf-8")
        (tree / "vendor" / "sub" / "r.py").write_text("r = 2\n", encoding="utf-8")
        (tree / "vendor" / "sub" / "n.py").write_text("n = 1\n", encoding="utf-8")
        sealed = green_cert.diff_bytes(tree, "HEAD").decode("utf-8")   # merge-seal が封じる差分の組み方
        self.assertEqual(re.findall(r"^diff --git .*$", sealed, re.MULTILINE), ["diff --git a/a.py b/a.py"])
        subprocess.run(["bash", "-c", swepro.capture_command(str(tree), str(self.out))], check=True, env=hermetic.child_env())
        captured = (self.out / swepro.PATCH).read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^diff --git .*$", captured, re.MULTILINE), ["diff --git a/a.py b/a.py"])

    def test_copied_submodule_contents_stay_out_of_the_seal_and_capture_diffs(self):
        self.copied_submodule_contents_stay_out_of_the_seal_and_capture_diffs(with_history=True)

    def test_copied_submodule_contents_without_history_stay_out_of_the_seal_and_capture_diffs(self):
        self.copied_submodule_contents_stay_out_of_the_seal_and_capture_diffs(with_history=False)

    def test_archon_config_stays_out_of_the_patch(self):
        self.add_submodule()
        self.sealed_plan(apply=self.seal(), sealed=self.seal())
        done, _ = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((self.workdir / swepro.ARCHON_CONFIG).is_file())
        patch = self.patch()
        self.assertEqual(re.findall(r"^diff --git .*$", patch, re.MULTILINE), ["diff --git a/a.py b/a.py"])
        self.assertNotIn(".archon", patch)

    def test_target_with_its_own_archon_config_stops_before_the_factory(self):
        self.add_submodule()
        (self.workdir / ".archon").mkdir()
        (self.workdir / swepro.ARCHON_CONFIG).write_text("worktree: {}\n", encoding="utf-8")
        self.sealed_plan(apply=self.seal(), sealed=self.seal())
        done, result = self.inside()
        self.assertEqual(done.returncode, swepro.run.STOPPED, done.stderr)
        self.assertIn(swepro.ARCHON_CONFIG, result["error"])
        self.assertEqual((self.workdir / swepro.ARCHON_CONFIG).read_text(encoding="utf-8"), "worktree: {}\n")
        self.assertEqual(self.calls(), [])

    def test_target_without_submodules_gets_no_archon_config(self):
        self.sealed_plan(apply=self.seal(), sealed=self.seal())
        done, _ = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIsNone(self.calls()[0]["archon_config"])
        self.assertFalse((self.workdir / ".archon").exists())

    def test_factory_that_leaves_no_run_names_the_shells_last_line(self):
        said = "Error: Could not create isolated workspace (Cannot determine git remote for /app)."
        self.set_plan(refuse=said)
        done, result = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("工場の run が起きなかった", result["error"])
        self.assertIn(said, result["error"])
        self.assertTrue(self.predicted(result)["failed"])
        self.assertIn("starting", done.stdout)
        self.assertIn(said, done.stdout)

    def test_sealed_diff_that_deletes_a_file_is_applied(self):
        (self.workdir / "b.py").write_text("y = 1\n", encoding="utf-8")
        git(self.workdir, "add", "b.py")
        git(self.workdir, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "b")
        git(self.workdir, "rm", "-q", "b.py")
        gone = subprocess.run(["git", "-C", str(self.workdir), "diff", "--cached"], capture_output=True, text=True,
                              check=True, env=hermetic.child_env()).stdout
        git(self.workdir, "reset", "-q", "--hard")
        self.sealed_plan(gone, apply=self.seal(gone), sealed=self.seal(gone))
        done, result = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(result["apply"]["code"], 0, result["apply"])
        self.assertFalse((self.workdir / "b.py").exists())
        self.assertIn("deleted file mode", self.patch())

    def test_sealed_diff_that_does_not_apply_is_a_failed_producer(self):
        stale = DIFF.replace("-x = 1", "-x = 5")
        self.sealed_plan(stale, apply=self.seal(stale), sealed=self.seal(stale))
        done, result = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(result["apply"]["code"], swepro.apply.REFUSED)
        self.assertIn("封じた差分が当たらない", result["error"])
        self.assertTrue(self.predicted(result)["failed"])

    def test_failed_factory_run_is_a_failed_producer(self):
        self.set_plan(status="failed")
        done, result = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(result["state"], "failed")
        self.assertIn(RUN_ID, result["error"])
        predicted = self.predicted(result)
        self.assertEqual((predicted["failed"], predicted["stopped"]), (True, False))

    def test_broken_factory_outcome_is_a_failed_producer(self):
        self.assertLessEqual(set(swepro.BROKE), set(swepro.report.OUTCOMES))
        for word in swepro.BROKE:
            with self.subTest(outcome=word):
                shutil.rmtree(self.place / "attempt", ignore_errors=True)
                self.secret()
                self.set_plan(outcome=word)
                done, result = self.inside()
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertIn(word, result["error"])
                predicted = self.predicted(result)
                self.assertEqual((predicted["failed"], predicted["stopped"]), (True, False))

    def test_empty_or_unknown_factory_outcome_is_a_failed_producer(self):
        for word in ("", "made_up"):
            with self.subTest(outcome=word):
                self.assertNotIn(word, swepro.report.OUTCOME_KINDS)
                shutil.rmtree(self.place / "attempt", ignore_errors=True)
                self.secret()
                self.set_plan(outcome=word)
                done, result = self.inside()
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(result["state"], runner.DONE)
                self.assertIn("OUTCOME_KINDS", result["error"])
                self.assertIn(word or "（空）", result["error"])
                predicted = self.predicted(result)
                self.assertEqual((predicted["failed"], predicted["stopped"]), (True, False))

    def test_every_known_outcome_but_broke_is_no_failure(self):
        for word in swepro.report.OUTCOME_KINDS:
            with self.subTest(outcome=word):
                self.assertEqual(swepro.broken_outcome(RUN_ID, word) is not None, word in swepro.BROKE)

    def test_needs_human_before_seal_gives_empty_patch(self):
        self.set_plan(outcome="needs_human")
        done, result = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual((self.workdir / "a.py").read_text(encoding="utf-8"), "x = 1\n")
        self.assertEqual(self.patch(), "")
        predicted = self.predicted(result)
        self.assertEqual((predicted["stopped"], predicted["failed"], result["apply"]["code"]), (True, False, 1))
        self.assertIn("needs_human", predicted["stop_why"])

    def test_needs_human_with_seal_applies_with_allow_stopped(self):
        self.sealed_plan(outcome="needs_human", sealed=self.seal())
        done, result = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("+x = 2", self.patch())
        self.assertEqual((self.predicted(result)["stopped"], result["apply"]["code"]), (True, 0))

    def test_paused_run_is_stopped_with_the_gate(self):
        self.set_plan(status="paused")
        done, result = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        predicted = self.predicted(result)
        self.assertEqual((predicted["stopped"], predicted["failed"], result["gate"], result.get("apply")),
                         (True, False, "gate-final", None))
        self.assertIn("gate-final", predicted["stop_why"])
        self.assertEqual(self.patch(), "")
        every = [a for c in self.calls() for a in c["args"]]
        self.assertFalse({"respond", "resume", "approve", "reject"} & set(every))

    def test_factory_gets_test_cmd_and_unattended_inputs(self):
        _, result = self.inside()
        [call] = [c for c in self.calls() if c["args"][1] == "run"]
        args = call["args"]
        inputs = dict(args[i + 1].split("=", 1) for i, a in enumerate(args) if a == "--input")
        self.assertEqual(result["inputs"], list(inputs))
        self.assertEqual((inputs["test_cmd"], inputs["unattended"], inputs["base"]),
                         (swepro.TEST_COMMANDS["internetarchive/openlibrary"], "true", ""))
        self.assertEqual(pathlib.Path(args[args.index("--cwd") + 1]).resolve(), self.workdir.resolve())

    def test_auth_reaches_the_child_and_is_written_nowhere(self):
        for name in swepro.ACCEPTED_AUTH:
            for producer in swepro.PRODUCERS:
                with self.subTest(name=name, producer=producer):
                    shutil.rmtree(self.place / "attempt", ignore_errors=True)
                    self.log.unlink(missing_ok=True)
                    self.secret(name)
                    done, result = self.inside(producer)
                    self.assertEqual(done.returncode, 0, done.stderr)
                    self.assertFalse((self.place / swepro.SECRET).exists())
                    self.assertNotIn(TOKEN, done.stdout + done.stderr)
                    self.assertIn(name, result["env_names"])
                    for path in [*self.out.rglob("*"), self.log]:
                        if path.is_file():
                            self.assertNotIn(TOKEN, path.read_text(encoding="utf-8", errors="replace"), path)
                    [call, *_] = self.calls("works-factory" if producer == "works-factory" else "claude")
                    self.assertIn(name, call["names"])

    def test_secret_with_an_unaccepted_name_refuses(self):
        self.secret("ANTHROPIC_AUTH_TOKEN")
        done, result = self.inside()
        self.assertEqual(done.returncode, runner.REFUSED, done.stderr)
        self.assertIsNone(result)
        self.assertFalse((self.place / swepro.SECRET).exists())
        self.assertEqual(self.calls(), [])

    def test_missing_token_refuses(self):
        (self.place / swepro.SECRET).unlink()
        done, result = self.inside()
        self.assertEqual(done.returncode, runner.REFUSED, done.stderr)
        self.assertIsNone(result)
        self.assertEqual(self.calls(), [])

    def test_plain_claude_fixes_with_same_model_and_denied_web(self):
        done, result = self.inside("claude")
        self.assertEqual(done.returncode, 0, done.stderr)
        [call] = self.calls("claude")
        args = call["args"]
        self.assertEqual((args[args.index("--model") + 1], args[args.index("--effort") + 1]), ("opus", "high"))
        at = args.index("--disallowedTools")
        self.assertEqual(args[at + 1:at + 3], ["WebFetch", "WebSearch"])
        self.assertEqual(args[-1], fixture_inputs()["request"][0]["text"])
        self.assertEqual(pathlib.Path(call["cwd"]).resolve(), self.workdir.resolve())
        for name in ("HOME", "CLAUDE_CONFIG_DIR"):
            self.assertTrue(pathlib.Path(call["env"][name]).is_relative_to(self.place), call["env"][name])
        settings = pathlib.Path(call["env"]["CLAUDE_CONFIG_DIR"]) / "settings.json"
        self.assertEqual(json.loads(settings.read_text(encoding="utf-8"))["permissions"], runner.toolset.DENY_WEB)
        self.assertIn("+x = 3", self.patch())
        self.assertNotIn("test_cmd", result["inputs"])
        self.assertEqual((result["state"], result["usd"], result["factory_seconds"], result["error"]), ("done", 1.5, 1.0, None))

    def test_plain_claude_error_is_a_failed_producer(self):
        self.env["FAKE_CLAUDE_ERROR"] = "Invalid bearer token"
        done, result = self.inside("claude")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(result["state"], "failed")
        self.assertIn("Invalid bearer token", result["error"])
        self.assertEqual(self.patch(), "")
        self.assertTrue(self.predicted(result)["failed"])

    def test_capture_outside_git_leaves_no_patch(self):
        (self.out / swepro.PATCH).parent.mkdir(parents=True, exist_ok=True)
        (self.out / swepro.PATCH).write_text("old", encoding="utf-8")
        done = subprocess.run(["bash", "-c", swepro.capture_command(str(self.tmp / "not-a-repo"), str(self.out))],
                              capture_output=True, env=hermetic.child_env())
        self.assertNotEqual(done.returncode, 0)
        self.assertFalse((self.out / swepro.PATCH).exists())


class PredictionTest(unittest.TestCase):
    RESULT = {"producer": "works-factory", "run_id": RUN_ID, "state": "done", "outcome": "needs_human", "error": None,
              "apply": {"code": 0, "line": "当てた"}, "factory_seconds": 10.0, "usd": 2.5,
              "usd_from": "x", "inputs": ["request"], "test_cmd": "t", "env_names": ["HOME"], "target_changed_during_run": False,
              "provenance": {"archon": "c"}}

    def test_pro_limit_marks_over_fifty_minutes(self):
        for seconds, over in ((3000.5, True), (3000, False), (None, None)):
            with self.subTest(seconds=seconds):
                got = swepro.prediction(OPENLIBRARY, "works-factory", "", self.RESULT, seconds, "f")
                self.assertEqual(got["pro_limit"], {"seconds": 3000, "over": over})

    def test_fields(self):
        got = swepro.prediction(OPENLIBRARY, "works-factory", DIFF, self.RESULT, 12.0, "f")
        self.assertEqual({k: got[k] for k in ("instance_id", "model_patch", "stopped", "state", "outcome", "usd", "seconds")},
                         {"instance_id": OPENLIBRARY, "model_patch": DIFF, "stopped": True, "state": "done",
                          "outcome": "needs_human", "usd": 2.5, "seconds": 12.0})
        self.assertEqual(got["provenance"], {"archon": "c", "factory_commit": "f"})
        self.assertEqual(got["apply"], {"code": 0, "line": "当てた"})

    def test_carries_every_result_field(self):
        got = swepro.prediction(OPENLIBRARY, "works-factory", DIFF, {**self.RESULT, "children": ["c1"]}, 12.0, "f")
        self.assertLessEqual(self.RESULT.keys() - {"provenance"}, got.keys())
        self.assertEqual(got["children"], ["c1"])

    def test_missing_result_is_driver_failed(self):
        got = swepro.prediction(OPENLIBRARY, "claude", DIFF, None, 5.0, "f")
        self.assertEqual((got["state"], got["stopped"], got["failed"], got["model_patch"], got["usd"], got["outcome"]),
                         (swepro.DRIVER_FAILED, False, True, DIFF, None, ""))

    def test_stop_why_comes_from_the_result_fields(self):
        got = swepro.prediction(OPENLIBRARY, "works-factory", DIFF, self.RESULT, 12.0, "f")
        self.assertEqual((got["stopped"], got["stop_why"]), (True, "結末 needs_human"))
        fixed = swepro.prediction(OPENLIBRARY, "works-factory", DIFF, {**self.RESULT, "outcome": "fixed"}, 12.0, "f")
        self.assertEqual((fixed["stopped"], fixed["stop_why"], fixed["failed"]), (False, "", False))

    def test_uncaptured_patch_is_stopped_not_empty(self):
        got = swepro.prediction(OPENLIBRARY, "works-factory", None, {**self.RESULT, "outcome": "fixed"}, 12.0, "f")
        self.assertIsNone(got["model_patch"])
        self.assertTrue(got["stopped"])
        self.assertIn(swepro.WORKDIR, got["stop_why"])


class TallyTest(unittest.TestCase):
    def tally(self, job):
        return subprocess.run([sys.executable, str(HERE / "swepro.py"), "tally", str(job)], capture_output=True, text=True,
                              encoding="utf-8", env=hermetic.child_env())

    @staticmethod
    def trial(job, name, exception=None):
        (job / name).mkdir(parents=True, exist_ok=True)
        (job / name / "result.json").write_text(json.dumps({"trial_name": name, "task_name": name, "exception_info": exception}),
                                                encoding="utf-8")

    @staticmethod
    def predict(job, name, failed):
        (job / name / "agent").mkdir(parents=True)
        predicted = swepro.prediction(name, "claude", "", {"state": "done", "error": "落ちた" if failed else None}, 1, "f")
        (job / name / "agent" / swepro.PREDICTION).write_text(json.dumps(predicted), encoding="utf-8")

    def test_counts_and_unreadable_file(self):
        job = hermetic.tmpdir(self)
        rows = [("t1", {"outcome": "needs_human", "model_patch": "", "seconds": 10, "usd": 1.0}),
                ("t2", {"outcome": "fixed", "model_patch": DIFF, "seconds": 4000, "usd": 2.0}),
                ("t3", {"outcome": "fixed", "model_patch": "", "seconds": None, "usd": None, "error": "落ちた"}),
                ("t5", {"outcome": "fixed", "model_patch": None, "seconds": 5, "usd": None})]
        for name, row in rows:
            self.trial(job, name)
            (job / name / "agent").mkdir(parents=True)
            predicted = swepro.prediction(name, "works-factory", row["model_patch"], {**row, "state": "done"}, row["seconds"], "f")
            (job / name / "agent" / swepro.PREDICTION).write_text(json.dumps(predicted), encoding="utf-8")
        done = subprocess.run([sys.executable, str(HERE / "swepro.py"), "tally", str(job)], capture_output=True, text=True,
                              encoding="utf-8", env=hermetic.child_env())
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), {"producers": ["works-factory"], "tasks": 4, "stopped": 2, "failed": 1,
                                                   "over_pro_limit": 1, "empty_patch": 2, "unmeasured_seconds": 1, "usd": 3.0,
                                                   "usd_missing": 2, "trials": 4, "exceptions": [],
                                                   "unaccounted": []})
        (job / "t4" / "agent").mkdir(parents=True)
        (job / "t4" / "agent" / swepro.PREDICTION).write_text("{", encoding="utf-8")
        done = subprocess.run([sys.executable, str(HERE / "swepro.py"), "tally", str(job)], capture_output=True, text=True,
                              encoding="utf-8", env=hermetic.child_env())
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn("t4", done.stderr)

    def test_all_trials_raised_names_them_and_fails(self):
        job = hermetic.tmpdir(self)
        for name in ("a__1", "b__2"):
            self.trial(job, name, {"exception_type": "RuntimeError", "exception_message": f"setup の apt が落ちた:\n{name} E: 無い",
                                   "exception_traceback": "tb", "occurred_at": "2026-10-14T00:00:00"})
        done = self.tally(job)
        self.assertEqual(done.returncode, 1, done.stderr)
        got = json.loads(done.stdout)
        self.assertEqual((got["tasks"], got["trials"], got["failed"]), (0, 2, 2))
        self.assertEqual(got["exceptions"], [{"trial": n, "exception": f"RuntimeError: setup の apt が落ちた: {n} E: 無い",
                                              "predicted": False} for n in ("a__1", "b__2")])
        self.assertIn("全 2 試行が例外", done.stderr)
        for name in ("a__1", "b__2"):
            self.assertIn(f"{name}: RuntimeError: setup の apt が落ちた: {name} E: 無い", done.stderr)

    def test_all_trials_raised_after_predicting_still_fails(self):
        job = hermetic.tmpdir(self)
        for name in ("a__1", "b__2"):
            self.trial(job, name, {"exception_type": "RuntimeError", "exception_message": "起こし役が落ちた"})
            self.predict(job, name, failed=True)
        done = self.tally(job)
        self.assertEqual(done.returncode, 1, done.stderr)
        got = json.loads(done.stdout)
        self.assertEqual((got["tasks"], got["trials"], got["failed"]), (2, 2, 2))
        self.assertIn("全 2 試行が例外", done.stderr)

    def test_trials_with_neither_prediction_nor_exception_fail(self):
        job = hermetic.tmpdir(self)
        for name in ("a__1", "b__2"):
            self.trial(job, name)
        done = self.tally(job)
        self.assertEqual(done.returncode, 1, done.stderr)
        got = json.loads(done.stdout)
        self.assertEqual((got["tasks"], got["trials"], got["failed"], got["unaccounted"]), (0, 2, 2, ["a__1", "b__2"]))
        self.assertIn("全 2 試行が測れていない", done.stderr)
        for name in ("a__1", "b__2"):
            self.assertIn(f"{name}: 予測も exception_info も無い", done.stderr)

    def test_a_predicted_failure_is_counted_once_and_a_measured_job_passes(self):
        job = hermetic.tmpdir(self)
        self.trial(job, "raised", {"exception_type": "RuntimeError", "exception_message": "起こし役が落ちた"})
        self.predict(job, "raised", failed=True)
        self.trial(job, "fine")
        self.predict(job, "fine", failed=False)
        done = self.tally(job)
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(done.stdout)
        self.assertEqual((got["tasks"], got["trials"], got["failed"], len(got["exceptions"])), (2, 2, 1, 1))
        self.assertTrue(got["exceptions"][0]["predicted"])

    def test_empty_job_fails(self):
        done = self.tally(hermetic.tmpdir(self))
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn("試行も予測も無い", done.stderr)


# ---------------------------------------------------------------- 派生のイメージ
FAKE_DOCKER = """#!PYTHON
import json, os, sys
PROXY_ENV = PROXY_NAMES
args = sys.argv[1:]
entry = {"args": args}
if args[0] == "build":
    context = args[-1]
    entry["files"] = sorted(os.listdir(context))
    entry["dockerfile"] = open(os.path.join(context, "Dockerfile"), encoding="utf-8").read()
    entry["proxy_env"] = [name for name in PROXY_ENV if os.environ.get(name)]
with open(os.environ["FAKE_DOCKER_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps(entry) + "\\n")
sys.exit(int(os.environ.get("FAKE_DOCKER_CODE", "0")))
"""
NETWORK = ("curl", "apt-get", "http", "git clone", "plugin marketplace", "works-factory version", "uv python install", "bun.sh")


class BuildTest(unittest.TestCase):
    def test_dockerfile_layers_the_tools_on_the_task_image(self):
        base = IMAGE.format(OPENLIBRARY)
        lines = swepro.dockerfile(base, "9.9.9", "f").splitlines()
        self.assertEqual(lines[0], f"FROM {base}")
        runs = [json.loads(line[len("RUN "):]) for line in lines if line.startswith("RUN ")]
        steps = swepro.build_steps("9.9.9")
        self.assertEqual(runs[:-1], [["/bin/sh", "-c", command] for _, command in steps])
        self.assertEqual([name for name, _ in steps],
                         ["place", "apt", "uv", "python", "bun", "claude", "archon", "plugin"])
        commands = dict(steps)
        self.assertIn("bash -s 9.9.9", commands["claude"])
        self.assertIn("works-factory version", commands["archon"])
        self.assertIn("pr-review-toolkit@claude-plugins-official", commands["plugin"])
        run_of = {name: lines.index(f"RUN {json.dumps(['/bin/sh', '-c', command], ensure_ascii=False)}") for name, command in steps}
        added = lines.index(f"ADD {swepro.REPO_TAR} {swepro.PLACE}/repo/")
        self.assertLess(run_of["claude"], added)
        self.assertLess(added, run_of["archon"])
        self.assertEqual([line.split(" ", 1)[0] for line in lines].count("ADD"), 1)
        self.assertNotIn("COPY", [line.split(" ", 1)[0] for line in lines])
        self.assertNotIn("ARG", [line.split(" ", 1)[0] for line in lines])   # 決まりのプロキシの build 引数を履歴に残さない
        place = hermetic.tmpdir(self)
        self.assertEqual(runs[-1][:2], ["/bin/sh", "-c"])
        stamped = subprocess.run(["/bin/sh", "-c", runs[-1][2].replace(swepro.PLACE, str(place))], env=hermetic.child_env())
        self.assertEqual(stamped.returncode, 0)
        self.assertEqual((place / swepro.STAMP).read_text(encoding="utf-8"), "f 9.9.9\n")
        for line in lines:
            self.assertNotIn(line.split(" ", 1)[0], ("ENV", "WORKDIR", "USER", "ENTRYPOINT", "CMD"), line)

    def test_setup_does_not_touch_the_network(self):
        place = hermetic.tmpdir(self)
        planned = swepro.setup_commands("f", "9.9.9", str(place))
        self.assertEqual([name for name, _ in planned], ["stamp", "sandbox"])
        for name, command in planned:
            for word in NETWORK:
                self.assertNotIn(word, command, name)
        check = dict(planned)["stamp"]
        for written, code in ((None, 1), ("f 9.9.9\n", 0), ("f 9.9.8\n", 1), ("g 9.9.9\n", 1)):
            with self.subTest(written=written):
                (place / swepro.STAMP).unlink(missing_ok=True)
                if written is not None:
                    (place / swepro.STAMP).write_text(written, encoding="utf-8")
                done = subprocess.run(["bash", "-c", check], capture_output=True, text=True, encoding="utf-8", env=hermetic.child_env())
                self.assertEqual(done.returncode, code)
                if code:
                    self.assertIn("prepare", done.stderr)

    def test_failed_sandbox_check_names_the_layers_in_one_line(self):
        fake = hermetic.tmpdir(self)
        (fake / "bwrap").write_text("#!/bin/sh\necho 'bwrap: No permissions to create new namespace' >&2\nexit 1\n")
        (fake / "bwrap").chmod(0o755)
        check = dict(swepro.setup_commands("f", "9.9.9"))["sandbox"]
        done = subprocess.run(["bash", "-c", check], capture_output=True, text=True, encoding="utf-8",
                              env=hermetic.child_env(PATH=f"{fake}{os.pathsep}{os.environ['PATH']}"))
        self.assertEqual(done.returncode, 1)
        bwrap, said = done.stderr.splitlines()
        self.assertIn("No permissions", bwrap)
        self.assertTrue(said.startswith(swepro.SANDBOX_REFUSED), said)
        self.assertTrue(said.removeprefix(swepro.SANDBOX_REFUSED))
        for word in ("台の VM の側で sysctl kernel.apparmor_restrict_unprivileged_userns=0", "seccomp", "apparmor",
                     "Can't mount proc", "systempaths=unconfined", f"-e {swepro.ENVIRONMENT}"):
            self.assertIn(word, said)

    def test_rewrite_image_needs_exactly_one_line(self):
        self.assertEqual(swepro.rewrite_image('a = 1\ndocker_image = "x:1"\n', "x:1", "y:1"), 'a = 1\ndocker_image = "y:1"\n')
        for text in ('a = 1\n', 'docker_image = "x:1"\ndocker_image = "x:1"\n'):
            with self.subTest(text=text), self.assertRaises(swepro.BenchError):
                swepro.rewrite_image(text, "x:1", "y:1")


class PrepareTest(unittest.TestCase):
    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        bin_dir = fake_claude(self.tmp / "fake-bin")
        docker = FAKE_DOCKER.replace("PYTHON", sys.executable).replace("PROXY_NAMES", repr(swepro.PROXY_ENV))
        (bin_dir / "docker").write_text(docker, encoding="utf-8")
        (bin_dir / "docker").chmod(0o755)
        self.log = self.tmp / "docker.log"
        self.tasks, self.out = self.tmp / "tasks", self.tmp / "out"
        shutil.copytree(FIXTURE, self.tasks / OPENLIBRARY)
        self.env = {k: v for k, v in hermetic.child_env(FAKE_DOCKER_LOG=str(self.log)).items()
                    if k != "CLAUDE_BIN_PATH" and k not in swepro.PROXY_ENV}
        self.env["PATH"] = os.pathsep.join([str(bin_dir), os.environ.get("PATH", "")])
        self.env["FAKE_CLAUDE_VERSION"] = swepro.BWRAP_FROM

    def prepare(self, *instances, **env):
        return subprocess.run([sys.executable, str(HERE / "swepro.py"), "prepare", str(self.tasks), str(self.out), *instances],
                              capture_output=True, text=True, encoding="utf-8", env={**self.env, **env})

    def docker_calls(self) -> list[dict]:
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []

    def test_builds_derived_image_and_rewrites_the_copy(self):
        original = (self.tasks / OPENLIBRARY / "task.toml").read_text(encoding="utf-8")
        done = self.prepare(OPENLIBRARY)
        self.assertEqual(done.returncode, 0, done.stderr)
        derived = swepro.derived_image(OPENLIBRARY)
        self.assertEqual(done.stdout.split(), [derived])
        image = IMAGE.format(OPENLIBRARY)
        pull, build = self.docker_calls()
        self.assertEqual(pull["args"], ["pull", "--platform", "linux/amd64", image])
        self.assertEqual(build["args"][:-1], ["build", "--platform", "linux/amd64", "-t", derived])
        self.assertEqual(build["files"], ["Dockerfile", swepro.REPO_TAR])
        self.assertEqual(build["dockerfile"], swepro.dockerfile(image, swepro.BWRAP_FROM, swepro.head_commit()))
        copied = tomllib.loads((self.out / OPENLIBRARY / "task.toml").read_text(encoding="utf-8"))
        before = tomllib.loads(original)
        self.assertEqual(copied["environment"].pop("docker_image"), derived)
        before["environment"].pop("docker_image")
        self.assertEqual(copied, before)
        self.assertEqual(swepro.instance_of(derived), OPENLIBRARY)
        self.assertEqual((self.out / OPENLIBRARY / "instruction.md").read_bytes(), (FIXTURE / "instruction.md").read_bytes())
        self.assertEqual((self.tasks / OPENLIBRARY / "task.toml").read_text(encoding="utf-8"), original)

    def test_proxy_names_reach_build_without_values(self):
        secret = "secret-value-zq7"
        done = self.prepare(OPENLIBRARY, HTTPS_PROXY=f"http://user:{secret}@proxy.invalid:3128", no_proxy="localhost",
                            HTTP_PROXY="")
        self.assertEqual(done.returncode, 0, done.stderr)
        pull, build = self.docker_calls()
        self.assertEqual(pull["args"], ["pull", "--platform", "linux/amd64", IMAGE.format(OPENLIBRARY)])
        self.assertEqual(build["args"][:-1], ["build", "--platform", "linux/amd64", "--build-arg", "HTTPS_PROXY",
                                              "--build-arg", "no_proxy", "-t", swepro.derived_image(OPENLIBRARY)])
        self.assertEqual(build["proxy_env"], ["HTTPS_PROXY", "no_proxy"])
        self.assertNotIn("ARG", [line.split(" ", 1)[0] for line in build["dockerfile"].splitlines()])
        for text in (self.log.read_text(encoding="utf-8"), done.stdout, done.stderr):
            self.assertNotIn(secret, text)

    def test_host_claude_other_than_the_bwrap_copy_stops_before_docker(self):
        done = self.prepare(OPENLIBRARY, FAKE_CLAUDE_VERSION="9.9.9")
        self.assertEqual(done.returncode, 1)
        self.assertIn("ホストの Claude Code 9.9.9 が", done.stderr)
        self.assertIn(f"写した版 {swepro.BWRAP_FROM} と違う", done.stderr)
        self.assertEqual(self.docker_calls(), [])
        self.assertFalse((self.out / OPENLIBRARY).exists())

    def test_failed_docker_names_the_instance(self):
        done = self.prepare(OPENLIBRARY, FAKE_DOCKER_CODE="1")
        self.assertEqual(done.returncode, 1)
        self.assertIn(f"{OPENLIBRARY} の docker pull が落ちた", done.stderr)
        self.assertFalse((self.out / OPENLIBRARY).exists())

    def test_other_repository_or_mismatched_folder_is_refused_before_docker(self):
        flipt = self.tasks / FLIPT
        flipt.mkdir()
        (flipt / "task.toml").write_text(f'[environment]\ndocker_image = "{IMAGE.format(FLIPT)}"\n', encoding="utf-8")
        mismatched = self.tasks / ANSIBLE
        mismatched.mkdir()
        (mismatched / "task.toml").write_text(f'[environment]\ndocker_image = "{IMAGE.format(QUTEBROWSER)}"\n', encoding="utf-8")
        for instance, said in ((FLIPT, "flipt-io/flipt"), (ANSIBLE, ANSIBLE), ("instance_missing__x-" + "0" * 40, "task.toml")):
            with self.subTest(instance=instance):
                done = self.prepare(OPENLIBRARY, instance)
                self.assertEqual(done.returncode, 1)
                self.assertIn(said, done.stderr)
                self.assertEqual(self.docker_calls(), [])


# ---------------------------------------------------------------- プロキシの要る網の付き添い
SIDECAR = swepro.EGRESS / "harbor-docker-egress-control-sidecar"
SECRET_WORD = "secret-value-zq7"
# 写しが Harbor 0.24.0 の物から直した所（Harbor の字, 写しの字）。他のファイルは一字も変えない
EGRESS_EDITS = {
    "harbor-docker-egress-control-sidecar/entrypoint.sh": [(
        'trap cleanup INT TERM EXIT\n\n/bin/gost -C "$GOST_CONFIG" &\n',
        'trap cleanup INT TERM EXIT\n\n'
        '# works-bench: the gost config (with the upstream proxy chain) arrives at start-up, never baked into the image.\n'
        f'printf \'%s\\n\' "${swepro.GOST_CONFIG_ENV}" > "$GOST_CONFIG"\n\n'
        '/bin/gost -C "$GOST_CONFIG" &\n')],
    "harbor-docker-egress-control-sidecar/bin/network-policy": [(
        '  allow-all)\n    remove_nftables\n    : > "$ALLOWLIST"\n    echo "ok: allow all egress"\n',
        '  allow-all)\n'
        '    # works-bench: public egress also goes through gost, so it reaches the upstream proxy.\n'
        '    printf \'%s\\n\' \'*\' > "$ALLOWLIST"\n    wait_reload\n    setup_nftables\n'
        '    echo "ok: allow all egress through the transparent proxy"\n')],
    "docker-compose-egress-control.yaml": [(
        '      EGRESS_CONTROL_INITIAL_ALLOWED_HOSTS: ${EGRESS_CONTROL_INITIAL_ALLOWED_HOSTS:-}\n',
        '      EGRESS_CONTROL_INITIAL_ALLOWED_HOSTS: ${EGRESS_CONTROL_INITIAL_ALLOWED_HOSTS:-}\n'
        f'      {swepro.GOST_CONFIG_ENV}: ${{{swepro.GOST_CONFIG_ENV}:?works-bench starts this sidecar only with a gost config}}\n'
        f'    extra_hosts:\n      - "{swepro.HOST_GATEWAY}:host-gateway"\n')],
}
EGRESS_SAME = ("harbor-docker-egress-control-sidecar/Dockerfile", "harbor-docker-egress-control-sidecar/gost.yaml",
               "harbor-docker-egress-control-sidecar/allowlist.txt")


def gost(env) -> dict:
    return json.loads(swepro.gost_config(env))


def harbor_gost() -> tuple[int, int, str]:
    """写しの gost.yaml の port・so_mark・許す一覧の道。写しの bin/network-policy はこれと同じ字を持つ"""
    config = yaml.safe_load((SIDECAR / "gost.yaml").read_text(encoding="utf-8"))
    [service] = config["services"]
    [allowlist] = [b for b in config["bypasses"] if b["name"] == service["bypass"]]
    return int(service["addr"].removeprefix(":")), service["metadata"]["so_mark"], allowlist["file"]["path"]


class GostConfigTest(unittest.TestCase):
    PROXY = f"http://user:p%40ss{SECRET_WORD}@proxy.invalid:3128"

    def test_without_a_proxy_harbor_keeps_its_own_sidecar(self):
        for env in ({}, {"NO_PROXY": "localhost"}, {"HTTPS_PROXY": "", "https_proxy": ""}):
            with self.subTest(env=env):
                self.assertIsNone(swepro.gost_config(env))

    def test_proxy_becomes_the_chain_of_the_harbor_service(self):
        got = gost({"HTTPS_PROXY": self.PROXY})
        [service] = got["services"]
        [chain_] = got["chains"]
        self.assertEqual(service["handler"]["chain"], chain_["name"])
        [hop] = chain_["hops"]
        [node] = hop["nodes"]
        self.assertEqual(node["addr"], "proxy.invalid:3128")
        self.assertEqual(node["connector"], {"type": "http", "auth": {"username": "user", "password": f"p@ss{SECRET_WORD}"}})
        self.assertEqual(node["metadata"]["so_mark"], harbor_gost()[1])
        self.assertNotIn("bypass", hop)
        self.assertEqual([b["name"] for b in got["bypasses"]], ["allowlist"])

    def test_agent_destinations_are_still_checked_against_the_allowlist(self):
        for env in ({"HTTPS_PROXY": self.PROXY}, {"HTTPS_PROXY": self.PROXY, "NO_PROXY": "b.org"}):
            with self.subTest(env=env):
                got = gost(env)
                [service] = got["services"]
                [allowlist] = [b for b in got["bypasses"] if b["name"] == service["bypass"]]
                self.assertTrue(allowlist["whitelist"])
                self.assertEqual(allowlist["file"]["path"], harbor_gost()[2])

    def test_which_proxy_is_chained(self):
        for env, addr in (({"HTTPS_PROXY": "http://a.invalid:1", "https_proxy": "http://b.invalid:2"}, "b.invalid:2"),
                          ({"HTTP_PROXY": "http://c.invalid:3"}, "c.invalid:3"),
                          ({"HTTP_PROXY": "http://c.invalid:3", "HTTPS_PROXY": "d.invalid:4"}, "d.invalid:4"),
                          ({"HTTPS_PROXY": "http://a.invalid:1", "https_proxy": ""}, "a.invalid:1")):
            with self.subTest(env=env):
                [node] = gost(env)["chains"][0]["hops"][0]["nodes"]
                self.assertEqual(node["addr"], addr)
                self.assertEqual(node["connector"], {"type": "http"})

    def test_host_loopback_is_reached_through_the_docker_host(self):
        for url in ("http://localhost:3128", "http://127.0.0.1:3128", "http://[::1]:3128"):
            with self.subTest(url=url):
                [node] = gost({"HTTP_PROXY": url})["chains"][0]["hops"][0]["nodes"]
                self.assertEqual(node["addr"], f"{swepro.HOST_GATEWAY}:3128")
        [node] = gost({"HTTP_PROXY": "http://[fd00::1]:3128"})["chains"][0]["hops"][0]["nodes"]
        self.assertEqual(node["addr"], "[fd00::1]:3128")

    def test_no_proxy_destinations_skip_the_chain(self):
        got = gost({"HTTPS_PROXY": self.PROXY,
                    "no_proxy": "localhost, .a.com,b.org,*.corp,10.0.0.0/8,192.168.1.1,c.net:8080,"})
        hop = got["chains"][0]["hops"][0]
        [bypass] = [b for b in got["bypasses"] if b["name"] == hop["bypass"]]
        self.assertEqual(bypass, {"name": hop["bypass"],
                                  "matchers": [".localhost", ".a.com", ".b.org", "*.corp", "10.0.0.0/8", "192.168.1.1",
                                               "c.net:8080"]})

    def test_unaccepted_proxies_are_refused_without_the_value(self):
        for url in (f"socks5://user:{SECRET_WORD}@proxy.invalid:1080", f"https://user:{SECRET_WORD}@proxy.invalid:3128",
                    f"http://user:{SECRET_WORD}@proxy.invalid", f"http://user:{SECRET_WORD}@proxy.invalid:port"):
            with self.subTest(url=url.split(":")[0]):
                with self.assertRaises(swepro.BenchError) as caught:
                    swepro.gost_config({"HTTPS_PROXY": url})
                said = str(caught.exception)
                self.assertNotIn(SECRET_WORD, said)
                self.assertNotIn("proxy.invalid", said)


FAKE_NFT = """#!/bin/sh
printf 'nft %s\\n' "$*" >> "$NFT_LOG"
if [ "$1" = "--file" ]; then cat >> "$NFT_LOG"; fi
"""


class EgressPolicyTest(unittest.TestCase):
    """写しの bin/network-policy を、偽の nft・sleep・nl（macOS の nl は GNU の旗を読まない）で打つ。どの段も nftables を張って
    全部の TCP を gost に通す"""

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.allowlist = self.tmp / "allowlist.txt"
        self.script = self.tmp / "network-policy"
        text = (SIDECAR / "bin" / "network-policy").read_text(encoding="utf-8")
        self.port, self.mark, allowlist = harbor_gost()
        line = f"ALLOWLIST={allowlist}\n"
        self.assertEqual(text.count(line), 1)
        self.script.write_text(text.replace(line, f"ALLOWLIST={self.allowlist}\n"), encoding="utf-8")
        fakes = self.tmp / "bin"
        fakes.mkdir()
        for name, body in (("nft", FAKE_NFT), ("sleep", "#!/bin/sh\n"), ("nl", "#!/bin/sh\n")):
            (fakes / name).write_text(body, encoding="utf-8")
            (fakes / name).chmod(0o755)
        self.env = hermetic.child_env(PATH=f"{fakes}{os.pathsep}{os.environ['PATH']}", NFT_LOG=str(self.tmp / "nft.log"))

    def policy(self, *args) -> tuple[list[str], str]:
        log = pathlib.Path(self.env["NFT_LOG"])
        log.unlink(missing_ok=True)
        done = subprocess.run(["sh", str(self.script), *args], env=self.env, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return self.allowlist.read_text(encoding="utf-8").splitlines(), log.read_text(encoding="utf-8")

    def test_every_phase_goes_through_gost(self):
        for args, allowed in ((["allow", "api.anthropic.com"], ["api.anthropic.com"]), (["allow-all"], ["*"]),
                              (["deny-all"], [])):
            with self.subTest(args=args):
                got, nft = self.policy(*args)
                self.assertEqual(got, allowed)
                self.assertIn(f"redirect to :{self.port}", nft)
                self.assertIn(f"meta mark {self.mark} accept", nft)

    def test_constants_match_the_gost_config(self):
        text = (SIDECAR / "bin" / "network-policy").read_text(encoding="utf-8")
        port, mark, allowlist = harbor_gost()
        for line in (f"ALLOWLIST={allowlist}", f"GOST_PORT={port}", f"GOST_MARK={mark}"):
            self.assertIn(f"\n{line}\n", text)


class EgressEditsTest(unittest.TestCase):
    def test_copy_carries_the_edits_with_the_names_swepro_uses(self):
        for name, edits in EGRESS_EDITS.items():
            text = (swepro.EGRESS / name).read_text(encoding="utf-8")
            for _, after in edits:
                with self.subTest(name=name):
                    self.assertEqual(text.count(after), 1)


class EgressCopyTest(unittest.TestCase):
    """写しが入っている Harbor の物に EGRESS_EDITS を当てた物と一致するか。Harbor は CI に入れないので、
    uv run --isolated --extra bench で入れた環境でだけ照らす"""

    def test_copy_is_harbors_with_the_listed_edits(self):
        spec = importlib.util.find_spec("harbor")
        if spec is None:
            self.skipTest("Harbor が入っていない（uv run --isolated --extra bench で入る）")
        self.assertEqual(importlib.metadata.version("harbor"), swepro.EGRESS_FROM, "Harbor の版が写しの元と違う。写し直す")
        harbor = pathlib.Path(spec.origin).parent / "environments" / "docker"
        for name in EGRESS_SAME:
            with self.subTest(name=name):
                self.assertEqual((swepro.EGRESS / name).read_bytes(), (harbor / name).read_bytes())
        for name, edits in EGRESS_EDITS.items():
            with self.subTest(name=name):
                text = (harbor / name).read_text(encoding="utf-8")
                for before, after in edits:
                    self.assertEqual(text.count(before), 1)
                    text = text.replace(before, after)
                self.assertEqual((swepro.EGRESS / name).read_text(encoding="utf-8"), text)
                self.assertEqual(os.access(swepro.EGRESS / name, os.X_OK), os.access(harbor / name, os.X_OK))
        files = {str(f.relative_to(swepro.EGRESS)) for f in swepro.EGRESS.rglob("*") if f.is_file()}
        self.assertEqual(files, {*EGRESS_SAME, *EGRESS_EDITS, "LICENSE", "COPIED_FROM"})
        [license_] = [f for f in importlib.metadata.distribution("harbor").files if f.name == "LICENSE"]
        self.assertEqual((swepro.EGRESS / "LICENSE").read_bytes(), license_.locate().read_bytes())

    def test_harbor_docker_has_the_seams_the_bench_environment_replaces(self):
        if importlib.util.find_spec("harbor") is None:
            self.skipTest("Harbor が入っていない（uv run --isolated --extra bench で入る）")
        from harbor.environments.docker.docker import DockerEnvironment
        for name in ("_DOCKER_COMPOSE_EGRESS_CONTROL_PATH", "_EGRESS_CONTROL_SIDECAR_CONTEXT_PATH",
                     "_egress_control_sidecar_dockerfile_path", "_compose_infra_env_vars", "preflight",
                     "_docker_compose_paths"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(DockerEnvironment, name))
        self.assertIsInstance(DockerEnvironment._docker_compose_paths, property)
        from harbor.constants import MAIN_SERVICE_NAME
        overlay = yaml.safe_load((swepro.SANDBOX / "docker-compose-sandbox.yaml").read_text(encoding="utf-8"))
        self.assertEqual(list(overlay["services"]), [MAIN_SERVICE_NAME])
        self.assertEqual(DockerEnvironment._EGRESS_CONTROL_SIDECAR_CONTEXT_PATH.name, SIDECAR.name)


# ---------------------------------------------------------------- Claude Code の sandbox の緩め
# 写しの seccomp.json が Docker の既定に足した規則と、足す前の字の sha256（写しの COPIED_FROM の元）
SANDBOX_RULE = {"names": ["clone", "mount", "pivot_root", "umount2", "unshare"], "action": "SCMP_ACT_ALLOW"}
SANDBOX_RULE_TEXT = (',\n\t\t{\n\t\t\t"names": [\n\t\t\t\t"clone",\n\t\t\t\t"mount",\n\t\t\t\t"pivot_root",\n'
                     '\t\t\t\t"umount2",\n\t\t\t\t"unshare"\n\t\t\t],\n\t\t\t"action": "SCMP_ACT_ALLOW"\n\t\t}')
DOCKER_SECCOMP_SHA256 = "536529b665dd0972c37bfb569f5d4ac8a53592e7b00752bc39ff063ca9864c74"


class SandboxTest(unittest.TestCase):
    def test_seccomp_copy_is_dockers_default_with_one_rule(self):
        text = (swepro.SANDBOX / "seccomp.json").read_text(encoding="utf-8")
        profile = json.loads(text)
        self.assertEqual(profile["defaultAction"], "SCMP_ACT_ERRNO")
        self.assertEqual(profile["syscalls"][-1], SANDBOX_RULE)
        self.assertEqual(text.count(SANDBOX_RULE_TEXT), 1)
        original = text.replace(SANDBOX_RULE_TEXT, "").removesuffix("\n")
        self.assertEqual(hashlib.sha256(original.encode("utf-8")).hexdigest(), DOCKER_SECCOMP_SHA256)
        files = {f.name for f in swepro.SANDBOX.iterdir()}
        self.assertEqual(files, {"seccomp.json", "docker-compose-sandbox.yaml", "LICENSE", "COPIED_FROM"})

    def test_overlay_loosens_only_the_main_container(self):
        overlay = yaml.safe_load((swepro.SANDBOX / "docker-compose-sandbox.yaml").read_text(encoding="utf-8"))
        self.assertEqual(overlay, {"services": {"main": {"security_opt": [
            f"seccomp=${{{swepro.SECCOMP_ENV}:?works-bench passes the seccomp profile path}}", "apparmor=unconfined",
            "systempaths=unconfined"]}}})


class UsageTest(unittest.TestCase):
    def test_usage_opens_no_extra_network(self):
        usage = swepro.__doc__
        self.assertEqual(usage.count("--allow-agent-host"), 1)
        self.assertIn("--allow-agent-host api.anthropic.com ", usage)
        self.assertNotIn("--allow-environment-host", usage)
        self.assertNotIn("DOCKER_DEFAULT_PLATFORM=", usage)
        self.assertNotIn("export DOCKER_DEFAULT_PLATFORM", usage)
        self.assertIn("swepro.py prepare ", usage)
        self.assertIn("harbor run -p <写しの置き場>", usage)
        self.assertIn(f"-e {swepro.ENVIRONMENT} ", usage)
        self.assertNotIn("-e docker ", usage)
        self.assertNotIn("proxy_refused", usage)
        self.assertIn("Rosetta", usage)
        self.assertIn("kernel.apparmor_restrict_unprivileged_userns=1 を\n  0 に", usage)


# ---------------------------------------------------------------- Harbor の殻
class Done:
    def __init__(self, return_code=0, stdout=""):
        self.return_code, self.stdout, self.stderr = return_code, stdout, ""


class FakeEnvironment:
    """exec・upload_file・download_file を呼ばれた順に控える。upload は呼ばれた時に中身を読む。exec の標準出力の頭には
    Harbor の docker の環境と同じく docker compose の警告（標準エラー）が混ざる"""

    def __init__(self, image, result, inside_code=0, capture_code=0, stamp_code=0):
        """result が None なら起こし役の結果のファイルが無い。stamp_code は焼き印の照らしの終了の値"""
        self.task_env_config = types.SimpleNamespace(docker_image=image)
        self.calls, self.result, self.inside_code, self.capture_code = [], result, inside_code, capture_code
        self.stamp_code = stamp_code

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        self.calls.append({"kind": "exec", "command": command, "env": env, "user": user, "timeout_sec": timeout_sec})
        if f"{swepro.PLACE}/{swepro.STAMP}" in command:
            return Done(self.stamp_code, WARNING)
        if "swepro.py inside" in command:
            return Done(self.inside_code, f"{WARNING}工場の出力")
        if command == swepro.capture_command(swepro.WORKDIR, swepro.OUT):
            return Done(self.capture_code, WARNING)
        return Done(0, WARNING)

    async def download_file(self, source_path, target_path):
        self.calls.append({"kind": "download", "source": source_path})
        if source_path == f"{swepro.OUT}/{swepro.RESULT}":
            if self.result is None:
                raise RuntimeError("Engine cp failed")
            pathlib.Path(target_path).write_text(json.dumps(self.result), encoding="utf-8")
        elif source_path == f"{swepro.OUT}/{swepro.PATCH}":
            pathlib.Path(target_path).write_text(DIFF, encoding="utf-8")
        else:
            raise RuntimeError("Engine cp failed")

    async def upload_file(self, source_path, target_path):
        data = pathlib.Path(source_path).read_bytes()
        self.calls.append({"kind": "upload", "source": str(source_path), "target": target_path,
                           "text": data.decode("utf-8", "replace") if not target_path.endswith(".tar") else ""})


def stub_harbor():
    class BaseAgent:
        def __init__(self, logs_dir, model_name=None, logger=None, **kw):
            self.logs_dir, self.logger = pathlib.Path(logs_dir), logger or mock.Mock()

    class DockerEnvironment:
        _DOCKER_COMPOSE_EGRESS_CONTROL_PATH = pathlib.Path("harbor-compose.yaml")
        _EGRESS_CONTROL_SIDECAR_CONTEXT_PATH = pathlib.Path("harbor-sidecar")

        def __init__(self, *args, **kwargs):
            pass

        @classmethod
        def preflight(cls):
            pass

        @classmethod
        def _egress_control_sidecar_dockerfile_path(cls):
            return cls._EGRESS_CONTROL_SIDECAR_CONTEXT_PATH / "Dockerfile"

        @property
        def _docker_compose_paths(self):
            return [pathlib.Path("harbor-main.yaml")]

        def _compose_infra_env_vars(self):
            return {"BASE": "1"}

    names = ("harbor", "harbor.agents", "harbor.agents.base", "harbor.environments", "harbor.environments.base",
             "harbor.environments.docker", "harbor.environments.docker.docker",
             "harbor.models", "harbor.models.agent", "harbor.models.agent.context")
    modules = {name: types.ModuleType(name) for name in names}
    modules["harbor.environments.docker.docker"].DockerEnvironment = DockerEnvironment
    modules["harbor.agents.base"].BaseAgent = BaseAgent
    modules["harbor.environments.base"].BaseEnvironment = object
    modules["harbor.models.agent.context"].AgentContext = object
    return modules


class AgentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        patcher = mock.patch.dict(sys.modules, stub_harbor())
        patcher.start()
        self.addCleanup(patcher.stop)
        sys.modules.pop("tests.calibration.swepro_agent", None)
        self.addCleanup(sys.modules.pop, "tests.calibration.swepro_agent", None)
        self.agent_module = importlib.import_module("tests.calibration.swepro_agent")
        argv = mock.patch.object(sys, "argv", ["harbor", "run", "--agent-timeout-multiplier", "inf"])
        argv.start()
        self.addCleanup(argv.stop)
        self.environ(**{swepro.ACCEPTED_AUTH[0]: TOKEN})
        self.tempdir = self.tmp / "host-tmp"
        self.tempdir.mkdir()
        temp = mock.patch.object(tempfile, "tempdir", str(self.tempdir))
        temp.start()
        self.addCleanup(temp.stop)

    def environ(self, **extra):
        env = {"PATH": os.pathsep.join([str(fake_claude(self.tmp / "fake-bin")), os.environ.get("PATH", "")]),
               "HOME": str(self.tmp / "user-home"), **extra}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def agent(self, producer="works-factory"):
        return self.agent_module.WorksBench(logs_dir=self.tmp / "logs", producer=producer)

    RESULT = {"state": "done", "outcome": "fixed", "error": None, "usd": 2.0, "provenance": {"archon": "c"}}

    def bench_environment(self, image, result, **kw):
        """殻が setup で受ける環境（WorksBenchDocker）の形をした FakeEnvironment"""
        class Bench(self.agent_module.WorksBenchDocker, FakeEnvironment):
            def __init__(self):
                FakeEnvironment.__init__(self, image, result, **kw)

        return Bench()

    def go(self, image=IMAGE.format(OPENLIBRARY), inside_code=0, result=RESULT, capture_code=0):
        environment = self.bench_environment(swepro.derived_image(swepro.instance_of(image)), result,
                                             inside_code=inside_code, capture_code=capture_code)
        context = types.SimpleNamespace(cost_usd=None, metadata=None)
        agent = self.agent()
        asyncio.run(agent.setup(environment))
        environment.calls_after_setup = len(environment.calls)
        try:
            asyncio.run(agent.run((FIXTURE / "instruction.md").read_text(encoding="utf-8"), environment, context))
        finally:
            self.environment, self.context = environment, context

    def predicted(self) -> dict:
        return json.loads((self.tmp / "logs" / swepro.PREDICTION).read_text(encoding="utf-8"))

    def test_token_goes_only_into_the_secret_upload(self):
        self.go()
        calls = self.environment.calls
        for call in calls:
            if call["kind"] == "exec":
                self.assertNotIn(TOKEN, call["command"])
                self.assertIsNone(call["env"])
        holding = [c for c in calls if c["kind"] == "upload" and TOKEN in c["text"]]
        self.assertEqual([c["target"] for c in holding], [f"{swepro.PLACE}/{swepro.SECRET}"])
        at = calls.index(holding[0])
        self.assertIn(f"rm -f {swepro.PLACE}/{swepro.SECRET}", [c.get("command") for c in calls[at:]])
        self.assertNotIn(TOKEN, (self.tmp / "logs" / swepro.PREDICTION).read_text(encoding="utf-8"))
        self.assertEqual(list(self.tempdir.iterdir()), [])

    def test_setup_checks_the_stamp_and_the_sandbox_and_uploads_nothing(self):
        self.go()
        setup = self.environment.calls[:self.environment.calls_after_setup]
        planned = swepro.setup_commands(swepro.head_commit(), "9.9.9")
        self.assertEqual([name for name, _ in planned], ["stamp", "sandbox"])
        self.assertEqual([c["command"] for c in setup], [command for _, command in planned])
        self.assertEqual({c["kind"] for c in setup}, {"exec"})
        self.assertEqual({c["user"] for c in setup}, {"root"})
        self.assertTrue(planned[-1][1].startswith(
            "bwrap --ro-bind / / --dev /dev --unshare-user --unshare-net --unshare-pid --proc /proc true"))
        for _, command in planned:
            self.assertNotIn(" /app", command)
            self.assertNotIn("/logs", command)

    def test_stamp_mismatch_fails_setup_naming_prepare(self):
        environment = self.bench_environment(swepro.derived_image(OPENLIBRARY), self.RESULT, stamp_code=1)
        with self.assertRaises(RuntimeError) as caught:
            asyncio.run(self.agent().setup(environment))
        self.assertIn("stamp", str(caught.exception))
        [stamp] = environment.calls
        self.assertIn("prepare", stamp["command"])

    def test_failed_driver_still_captures_and_writes_prediction(self):
        with self.assertRaises(RuntimeError):
            self.go(inside_code=1)
        run = [c.get("command") for c in self.environment.calls[self.environment.calls_after_setup:]]
        self.assertIn(swepro.capture_command(swepro.WORKDIR, swepro.OUT), run)
        got = self.predicted()
        self.assertEqual((got["model_patch"], got["instance_id"], got["usd"]), (DIFF, OPENLIBRARY, 2.0))
        self.assertIsNotNone(got["seconds"])
        self.assertEqual(self.context.cost_usd, 2.0)
        self.assertEqual(self.context.metadata["pro_limit"], {"seconds": 3000, "over": False})

    def test_driver_without_result_reaches_harbor_with_metadata(self):
        with self.assertRaises(RuntimeError) as caught:
            self.go(inside_code=1, result=None)
        self.assertIn("終了の値 1", str(caught.exception))
        self.assertIsNone(self.context.cost_usd)
        self.assertEqual({k: self.context.metadata[k] for k in ("state", "failed", "stopped", "outcome")},
                         {"state": swepro.DRIVER_FAILED, "failed": True, "stopped": False, "outcome": ""})
        self.assertEqual(self.context.metadata["pro_limit"]["seconds"], swepro.PRO_SECONDS)

    def test_result_and_patch_are_read_despite_warnings_on_stdout(self):
        self.go()
        got = self.predicted()
        self.assertEqual((got["state"], got["failed"], got["model_patch"]), ("done", False, DIFF))

    def test_driver_output_is_kept(self):
        self.go()
        self.assertEqual((self.tmp / "logs" / swepro.INSIDE_STDOUT).read_text(encoding="utf-8"), f"{WARNING}工場の出力")
        self.assertTrue((self.tmp / "logs" / swepro.INSIDE_STDERR).is_file())

    def test_failed_capture_is_stopped_without_a_patch(self):
        self.go(capture_code=1)
        got = self.predicted()
        self.assertIsNone(got["model_patch"])
        self.assertTrue(got["stopped"])
        run = [c.get("source") for c in self.environment.calls[self.environment.calls_after_setup:]]
        self.assertNotIn(f"{swepro.OUT}/{swepro.PATCH}", run)

    def test_launch_without_unbounded_multiplier_is_refused(self):
        with mock.patch.object(sys, "argv", ["harbor", "run", "-a", "x"]):
            with self.assertRaises(ValueError) as caught:
                self.agent()
        self.assertIn("--agent-timeout-multiplier inf", str(caught.exception))

    def test_proxied_environment_takes_the_copied_sidecar_and_the_gost_config(self):
        proxy = f"http://user:{SECRET_WORD}@proxy.invalid:3128"
        self.environ(HTTPS_PROXY=proxy)
        docker = self.agent_module.WorksBenchDocker()
        self.assertEqual(docker._DOCKER_COMPOSE_EGRESS_CONTROL_PATH, swepro.EGRESS / "docker-compose-egress-control.yaml")
        self.assertEqual(docker._EGRESS_CONTROL_SIDECAR_CONTEXT_PATH, SIDECAR)
        self.assertEqual(docker._egress_control_sidecar_dockerfile_path(), SIDECAR / "Dockerfile")
        for path in (docker._DOCKER_COMPOSE_EGRESS_CONTROL_PATH, docker._egress_control_sidecar_dockerfile_path()):
            self.assertTrue(path.is_file(), path)
        infra = docker._compose_infra_env_vars()
        self.assertEqual(infra["BASE"], "1")
        self.assertEqual(json.loads(infra[swepro.GOST_CONFIG_ENV]), gost({"HTTPS_PROXY": proxy}))
        self.assertEqual(infra[swepro.SECCOMP_ENV], str(swepro.SANDBOX / "seccomp.json"))

    def test_environment_without_a_proxy_keeps_harbors_sidecar(self):
        base = sys.modules["harbor.environments.docker.docker"].DockerEnvironment
        self.environ(NO_PROXY="localhost")
        docker = self.agent_module.WorksBenchDocker()
        self.assertEqual(docker._DOCKER_COMPOSE_EGRESS_CONTROL_PATH, base._DOCKER_COMPOSE_EGRESS_CONTROL_PATH)
        self.assertEqual(docker._egress_control_sidecar_dockerfile_path(), base._egress_control_sidecar_dockerfile_path())
        self.assertEqual(docker._compose_infra_env_vars(), {"BASE": "1", swepro.SECCOMP_ENV: str(swepro.SANDBOX / "seccomp.json")})

    def test_environment_layers_the_sandbox_overlay_last_with_or_without_a_proxy(self):
        for env in ({}, {"HTTPS_PROXY": "http://proxy.invalid:3128"}):
            with self.subTest(env=env):
                self.environ(**env)
                docker = self.agent_module.WorksBenchDocker()
                overlay = swepro.SANDBOX / "docker-compose-sandbox.yaml"
                self.assertEqual(docker._docker_compose_paths, [pathlib.Path("harbor-main.yaml"), overlay])
                self.assertTrue(overlay.is_file())
                self.assertTrue(pathlib.Path(docker._compose_infra_env_vars()[swepro.SECCOMP_ENV]).is_file())

    def test_preflight_refuses_an_unaccepted_proxy(self):
        self.environ(HTTPS_PROXY=f"socks5://user:{SECRET_WORD}@proxy.invalid:1080")
        with self.assertRaises(swepro.BenchError) as caught:
            self.agent_module.WorksBenchDocker.preflight()
        self.assertNotIn(SECRET_WORD, str(caught.exception))

    def test_launch_with_another_environment_is_refused_before_exec(self):
        for name in ("HTTPS_PROXY", "http_proxy", None):
            with self.subTest(name=name):
                proxy = {name: f"http://user:{SECRET_WORD}@proxy.invalid:3128"} if name else {}
                self.environ(**{swepro.ACCEPTED_AUTH[0]: TOKEN, **proxy})
                agent = self.agent()
                environment = FakeEnvironment(swepro.derived_image(OPENLIBRARY), self.RESULT)
                with self.assertRaises(ValueError) as caught:
                    asyncio.run(agent.setup(environment))
                said = str(caught.exception)
                self.assertIn(f"-e {swepro.ENVIRONMENT}", said)
                self.assertNotIn(SECRET_WORD, said)
                self.assertEqual(environment.calls, [])

    def test_proxied_launch_with_the_bench_environment_sets_up(self):
        self.environ(**{swepro.ACCEPTED_AUTH[0]: TOKEN, "HTTPS_PROXY": "http://proxy.invalid:3128"})

        class Proxied(self.agent_module.WorksBenchDocker, FakeEnvironment):
            def __init__(self):
                FakeEnvironment.__init__(self, swepro.derived_image(OPENLIBRARY), None)

        environment = Proxied()
        asyncio.run(self.agent().setup(environment))
        self.assertTrue(environment.calls)

    def test_environment_named_in_the_usage_is_the_bench_environment(self):
        module, name = swepro.ENVIRONMENT.split(":")
        self.assertEqual(module, self.agent_module.__name__)
        self.assertIs(getattr(self.agent_module, name), self.agent_module.WorksBenchDocker)

    def test_old_works_and_unknown_producers_are_refused(self):
        with self.assertRaises(ValueError) as caught:
            self.agent("works")
        self.assertIn("archon-darwin-arm64", str(caught.exception))
        with self.assertRaises(ValueError):
            self.agent("codex")

    def test_api_key_goes_only_into_the_secret_upload(self):
        key = "sk-ant-api03-zq7-not-a-real-key"
        self.environ(ANTHROPIC_API_KEY=key)
        self.go()
        calls = self.environment.calls
        self.assertFalse([c for c in calls if c["kind"] == "exec" and key in c["command"]])
        [holding] = [c for c in calls if c["kind"] == "upload" and key in c["text"]]
        self.assertEqual(holding["target"], f"{swepro.PLACE}/{swepro.SECRET}")
        self.assertEqual(json.loads(holding["text"]), {"ANTHROPIC_API_KEY": key})
        self.assertFalse(self.predicted()["failed"])

    def test_flag_set_to_off_does_not_refuse(self):
        self.environ(ANTHROPIC_API_KEY="sk-ant-api03-zq7", CLAUDE_CODE_USE_BEDROCK="0")
        self.go()
        [holding] = [c for c in self.environment.calls if c["kind"] == "upload" and c["target"].endswith(swepro.SECRET)]
        self.assertEqual(json.loads(holding["text"]), {"ANTHROPIC_API_KEY": "sk-ant-api03-zq7"})
        self.assertFalse(self.predicted()["failed"])

    def test_unaccepted_auth_is_refused_before_upload_with_the_reason_predicted(self):
        for named, env in (("CLAUDE_CODE_USE_BEDROCK", {"CLAUDE_CODE_USE_BEDROCK": "1"}),
                           ("ANTHROPIC_BASE_URL", {"ANTHROPIC_API_KEY": "sk-ant-api03-zq7",
                                                   "ANTHROPIC_BASE_URL": "https://gateway.example"})):
            with self.subTest(named=named):
                self.environ(**env)
                with self.assertRaises(ValueError) as caught:
                    self.go()
                self.assertIn(named, str(caught.exception))
                run = self.environment.calls[self.environment.calls_after_setup:]
                self.assertFalse([c for c in run if c["kind"] == "upload"])
                got = self.predicted()
                self.assertEqual((got["state"], got["failed"], got["stopped"], got["model_patch"]),
                                 (swepro.AUTH_REFUSED, True, False, ""))
                self.assertIn(named, got["error"])
                self.assertEqual(self.context.metadata["state"], swepro.AUTH_REFUSED)

    def test_missing_auth_is_refused_before_upload_with_the_reason_predicted(self):
        why = "no credential found anywhere"
        self.environ()
        # 認証の無い env では macOS の resolve がホストの keychain を読むので、resolve の答えを差す
        with mock.patch.object(self.agent_module.auth_launch, "resolve", return_value=(None, None, why)):
            with self.assertRaises(ValueError) as caught:
                self.go()
        self.assertIn(why, str(caught.exception))
        run = self.environment.calls[self.environment.calls_after_setup:]
        self.assertFalse([c for c in run if c["kind"] == "upload"])
        got = self.predicted()
        self.assertEqual((got["state"], got["failed"], got["stopped"], got["model_patch"]),
                         (swepro.AUTH_REFUSED, True, False, ""))
        self.assertIn(why, got["error"])

    def test_other_repository_is_refused_before_upload(self):
        environment = FakeEnvironment(IMAGE.format(FLIPT), {})
        with self.assertRaises(swepro.BenchError):
            asyncio.run(self.agent().run("x", environment, types.SimpleNamespace()))
        self.assertEqual(environment.calls, [])

    def test_no_timeouts(self):
        self.assertEqual(self.agent_module.WorksBench.DEFAULT_SETUP_TIMEOUT_SEC, math.inf)
        for path in (HERE / "swepro.py", HERE / "swepro_agent.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.keyword) and node.arg in ("timeout", "timeout_sec"):
                    self.assertIsInstance(node.value, ast.Constant, path.name)
                    self.assertIsNone(node.value.value, f"{path.name}:{node.lineno}")


if __name__ == "__main__":
    unittest.main()

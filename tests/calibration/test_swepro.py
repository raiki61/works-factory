"""SWE-Bench Pro V2 の口 tests/calibration/swepro.py と Harbor の殻 swepro_agent.py の試験。Harbor・docker・Archon・claude・網を
使わない。殻は sys.modules に差した harbor の stub の上で読み、起こし役 inside は偽の works-factory の殻（test_run.FAKE_SHELL を
差し替え口 WORKS_CALIBRATION_SHELL で渡す）と PATH の頭の偽の claude で回す。

fixture の課題 1 件分（instruction.md と task.toml だけ。正解と隠した試験は写さない）の出どころは
github.com/scaleapi/SWE-bench_Pro-os の commit 66f92766bba642462d4bbe5479e83f91f9211862 の v2/tasks/（MIT。Scale AI）。
"""
import ast
import asyncio
import importlib
import json
import math
import os
import pathlib
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
POINTER = {"type": swepro.apply.POINTER_TYPE, "run_id": RUN_ID, "path": swepro.apply.APPLY_DIFF}

FAKE_CLAUDE = """#!PYTHON
import json, os, sys
args = sys.argv[1:]
if args == ["--version"]:
    print("9.9.9 (Claude Code)")
    sys.exit(0)
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"who": "claude", "args": args, "cwd": os.getcwd(), "names": sorted(os.environ),
                        "env": {k: os.environ.get(k) for k in ("HOME", "CLAUDE_CONFIG_DIR")}}) + "\\n")
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

    def test_test_cmd_is_a_main_graph_input(self):
        graph = yaml.safe_load((ROOT / "workflows" / "line" / "works-factory-line.yaml").read_text(encoding="utf-8"))
        self.assertIn("test_cmd", graph["inputs"])


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
        (self.place / swepro.SECRET).write_text(TOKEN, encoding="utf-8")
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

    def sealed_plan(self, **value):
        files = {test_run.JUDGMENT: test_run.UNITS, swepro.apply.APPLY_DIFF: DIFF}
        self.set_plan(value=value, artifacts=files)

    def inside(self, producer="works-factory"):
        done = subprocess.run([sys.executable, str(HERE / "swepro.py"), "inside", producer, "--workdir", str(self.workdir),
                               "--place", str(self.place), "--out", str(self.out)], env=self.env, capture_output=True, text=True,
                              encoding="utf-8")
        result = json.loads((self.out / swepro.RESULT).read_text(encoding="utf-8")) if (self.out / swepro.RESULT).exists() else None
        return done, result

    def patch(self) -> str:
        subprocess.run(["bash", "-c", swepro.capture_command(str(self.workdir), str(self.out))], check=True)
        return (self.out / swepro.PATCH).read_text(encoding="utf-8")

    def calls(self, who="works-factory") -> list[dict]:
        rows = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []
        return [r for r in rows if r["who"] == who]

    def seal(self) -> dict:
        return {"ok": True, "hash": swepro.apply.seal.digest(DIFF.encode()), "diff": POINTER}

    def test_sealed_diff_is_applied_and_captured(self):
        self.sealed_plan(apply=self.seal(), sealed=self.seal())
        done, result = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual((self.workdir / "a.py").read_text(encoding="utf-8"), "x = 2\n")
        self.assertIn("+x = 2", self.patch())
        self.assertEqual((result["apply"]["code"], result["stopped"], result["state"]), (0, False, "done"))
        self.assertFalse(result["target_changed_during_run"])
        self.assertTrue((self.out / "evidence" / "record" / "parent.json").is_file())

    def test_needs_human_before_seal_gives_empty_patch(self):
        self.set_plan(outcome="needs_human")
        done, result = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual((self.workdir / "a.py").read_text(encoding="utf-8"), "x = 1\n")
        self.assertEqual(self.patch(), "")
        self.assertEqual((result["stopped"], result["apply"]["code"]), (True, 1))
        self.assertIn("needs_human", result["stop_why"])

    def test_needs_human_with_seal_applies_with_allow_stopped(self):
        self.sealed_plan(outcome="needs_human", sealed=self.seal())
        done, result = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("+x = 2", self.patch())
        self.assertEqual((result["stopped"], result["apply"]["code"]), (True, 0))

    def test_paused_run_is_stopped_with_the_gate(self):
        self.set_plan(status="paused")
        done, result = self.inside()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual((result["stopped"], result["gate"], result["apply"]), (True, "gate-final", None))
        self.assertIn("gate-final", result["stop_why"])
        self.assertEqual(self.patch(), "")
        every = [a for c in self.calls() for a in c["args"]]
        self.assertFalse({"respond", "resume", "approve", "reject"} & set(every))

    def test_factory_gets_test_cmd_and_unattended_inputs(self):
        self.inside()
        [call] = [c for c in self.calls() if c["args"][1] == "run"]
        args = call["args"]
        inputs = dict(args[i + 1].split("=", 1) for i, a in enumerate(args) if a == "--input")
        self.assertEqual((inputs["test_cmd"], inputs["unattended"], inputs["base"]),
                         (swepro.TEST_COMMANDS["internetarchive/openlibrary"], "true", ""))
        self.assertEqual(pathlib.Path(args[args.index("--cwd") + 1]).resolve(), self.workdir.resolve())

    def test_token_reaches_the_child_and_is_written_nowhere(self):
        for producer in swepro.PRODUCERS:
            with self.subTest(producer=producer):
                (self.place / swepro.SECRET).write_text(TOKEN, encoding="utf-8")
                done, result = self.inside(producer)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertFalse((self.place / swepro.SECRET).exists())
                self.assertNotIn(TOKEN, done.stdout + done.stderr)
                self.assertIn(swepro.TOKEN_ENV, result["env_names"])
                for path in [*self.out.rglob("*"), self.log]:
                    if path.is_file():
                        self.assertNotIn(TOKEN, path.read_text(encoding="utf-8", errors="replace"), path)
        for who in ("works-factory", "claude"):
            [call, *_] = self.calls(who)
            self.assertIn(swepro.TOKEN_ENV, call["names"])

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
        self.assertEqual(json.loads(settings.read_text(encoding="utf-8"))["permissions"], swepro.toolset.DENY_WEB)
        self.assertIn("+x = 3", self.patch())
        self.assertNotIn("test_cmd", result["inputs"])
        self.assertEqual((result["state"], result["usd"], result["factory_seconds"]), ("done", 1.5, 1.0))


class PredictionTest(unittest.TestCase):
    RESULT = {"producer": "works-factory", "run_id": RUN_ID, "state": "done", "outcome": "needs_human", "stopped": True,
              "stop_why": "結末 needs_human", "apply": {"code": 0, "line": "当てた"}, "factory_seconds": 10.0, "usd": 2.5,
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

    def test_missing_result_is_driver_failed(self):
        got = swepro.prediction(OPENLIBRARY, "claude", DIFF, None, 5.0, "f")
        self.assertEqual((got["state"], got["stopped"], got["model_patch"]), ("driver_failed", False, DIFF))


class TallyTest(unittest.TestCase):
    def test_counts_and_unreadable_file(self):
        job = hermetic.tmpdir(self)
        rows = [("t1", {"stopped": True, "model_patch": "", "seconds": 10, "usd": 1.0}),
                ("t2", {"stopped": False, "model_patch": DIFF, "seconds": 4000, "usd": 2.0}),
                ("t3", {"stopped": False, "model_patch": "", "seconds": None, "usd": None})]
        for name, row in rows:
            (job / name / "agent").mkdir(parents=True)
            predicted = swepro.prediction(name, "works-factory", row["model_patch"], {**row, "state": "done"}, row["seconds"], "f")
            (job / name / "agent" / swepro.PREDICTION).write_text(json.dumps(predicted), encoding="utf-8")
        done = subprocess.run([sys.executable, str(HERE / "swepro.py"), "tally", str(job)], capture_output=True, text=True,
                              encoding="utf-8", env=hermetic.child_env())
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), {"producers": ["works-factory"], "tasks": 3, "stopped": 1, "over_pro_limit": 1,
                                                   "empty_patch": 2, "unmeasured_seconds": 1, "usd": 3.0, "usd_missing": 1})
        (job / "t4" / "agent").mkdir(parents=True)
        (job / "t4" / "agent" / swepro.PREDICTION).write_text("{", encoding="utf-8")
        done = subprocess.run([sys.executable, str(HERE / "swepro.py"), "tally", str(job)], capture_output=True, text=True,
                              encoding="utf-8", env=hermetic.child_env())
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn("t4", done.stderr)


# ---------------------------------------------------------------- Harbor の殻
class Done:
    def __init__(self, return_code=0, stdout=""):
        self.return_code, self.stdout, self.stderr = return_code, stdout, ""


class FakeEnvironment:
    """exec と upload_file を呼ばれた順に控える。upload は呼ばれた時に中身を読む"""

    def __init__(self, image, result, inside_code=0):
        self.task_env_config = types.SimpleNamespace(docker_image=image)
        self.calls, self.result, self.inside_code = [], result, inside_code

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        self.calls.append({"kind": "exec", "command": command, "env": env, "user": user, "timeout_sec": timeout_sec})
        if command.startswith("cat ") and command.endswith(swepro.RESULT):
            return Done(0, json.dumps(self.result))
        if command.startswith("cat "):
            return Done(0, DIFF)
        if "swepro.py inside" in command:
            return Done(self.inside_code)
        return Done(0)

    async def upload_file(self, source_path, target_path):
        data = pathlib.Path(source_path).read_bytes()
        self.calls.append({"kind": "upload", "source": str(source_path), "target": target_path,
                           "text": data.decode("utf-8", "replace") if not target_path.endswith(".tar") else ""})


def stub_harbor():
    class BaseAgent:
        def __init__(self, logs_dir, model_name=None, logger=None, **kw):
            self.logs_dir, self.logger = pathlib.Path(logs_dir), logger or mock.Mock()

    names = ("harbor", "harbor.agents", "harbor.agents.base", "harbor.environments", "harbor.environments.base",
             "harbor.models", "harbor.models.agent", "harbor.models.agent.context")
    modules = {name: types.ModuleType(name) for name in names}
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
        self.environ(**{swepro.TOKEN_ENV: TOKEN})
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

    def go(self, image=IMAGE.format(OPENLIBRARY), inside_code=0):
        result = {"state": "done", "outcome": "fixed", "stopped": False, "usd": 2.0, "provenance": {"archon": "c"}}
        environment = FakeEnvironment(image, result, inside_code)
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

    def test_setup_order_and_place(self):
        self.go()
        setup = self.environment.calls[:self.environment.calls_after_setup]
        names = [name for name, _ in swepro.setup_commands("9.9.9")]
        self.assertEqual(names, ["place", "apt", "uv", "python", "bun", "claude", swepro.REPO_STEP, "archon", "plugin", "sandbox"])
        commands = [c["command"] for c in setup if c["kind"] == "exec"]
        self.assertEqual(commands, [command for _, command in swepro.setup_commands("9.9.9")])
        self.assertIn("bash -s 9.9.9", commands[names.index("claude")])
        uploads = [i for i, c in enumerate(setup) if c["kind"] == "upload"]
        self.assertEqual([setup[i]["target"] for i in uploads], [f"{swepro.PLACE}/{swepro.REPO_TAR}"])
        self.assertEqual(setup[uploads[0] + 1]["command"], commands[names.index(swepro.REPO_STEP)])
        self.assertIn("works-factory version", commands[names.index("archon")])
        self.assertIn("pr-review-toolkit@claude-plugins-official", commands[names.index("plugin")])
        self.assertTrue(commands[-1].startswith("bwrap --ro-bind / / --unshare-user --unshare-net true"))
        self.assertEqual({c["user"] for c in setup if c["kind"] == "exec"}, {"root"})
        for command in commands:
            self.assertNotIn(" /app", command)
            self.assertNotIn("/logs", command)

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

    def test_old_works_and_unknown_producers_are_refused(self):
        with self.assertRaises(ValueError) as caught:
            self.agent("works")
        self.assertIn("archon-darwin-arm64", str(caught.exception))
        with self.assertRaises(ValueError):
            self.agent("codex")

    def test_api_key_only_is_refused_before_upload(self):
        self.environ(ANTHROPIC_API_KEY="sk-ant-api03-zq7")
        environment = FakeEnvironment(IMAGE.format(OPENLIBRARY), {})
        with self.assertRaises(ValueError) as caught:
            asyncio.run(self.agent().run("x", environment, types.SimpleNamespace()))
        self.assertIn("ANTHROPIC_API_KEY", str(caught.exception))
        self.assertEqual(environment.calls, [])

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

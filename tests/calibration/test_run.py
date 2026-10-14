"""公開ベンチのランナー tests/calibration/run.py の試験。合成の作り手と手元の mirror だけで回し、本物の Archon・claude・判定役・網を
使わない。

ランナーは自分の在る checkout から make_target.py・evidence.py・lib/・bin/_lib/ を読むので、それらを一時の checkout に写して走らせる。
偽の works-factory の殻（差し替え口 WORKS_CALIBRATION_SHELL で渡す）と、偽の今の works（WORKS_FACTORY_OLD_WORKS で渡す。
dev/use.sh・continue.sh・archon.sh を commit した git の置き場で、写した pack.json の works.commit をその commit に替える）と、
PATH の頭の偽の claude・npm は、受けた引数と環境を FAKE_LOG に 1 行ずつ残し、FAKE_PLAN の JSON どおりに run の記録・置き場・
出力の置き場（board）・archon.db・指摘を書く。偽の ReviewBench は manifest だけを持ち、課題の base と head は一時の mirror に在る。
"""
import ast
import fcntl
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests.bin import hermetic
from tests.bin.gitkit import git
from tests.calibration import run as runner
from tests.calibration.test_reviewbench import commit

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
MODULES = [HERE / name for name in ("run.py", "reviewbench.py", "nodes.py")]
COPIED = ["pack.json", "factory/pack.json", "tests/__init__.py", "tests/calibration/__init__.py", "tests/calibration/run.py",
          "tests/calibration/reviewbench.py", "tests/calibration/nodes.py", "tests/e2e/__init__.py",
          "tests/e2e/make_target.py", "tests/e2e/evidence.py"]
ITEMS = {"WORKS_FACTORY_KEYCHAIN_ITEM": "item-of-works-factory-zq7", "WORKS_KEYCHAIN_ITEM": "item-of-old-works-zq7"}
GH = {"GH_TOKEN": "gh-token-zq7"}
WATCHED = [*ITEMS, *GH, "WORKS_FACTORY_HOME", "WORKS_USE_HOME", "WORKS_USE_UNATTENDED", "WORKS_USE_FINAL_GATE",
           "WORKS_DEV_HOME", "GH_CONFIG_DIR", "WORKS_FACTORY_DENY_WEB", "RB_BASE", "RB_HEAD", "RB_OUT", "CLAUDE_CONFIG_DIR",
           "PI_CODING_AGENT_DIR"]
NWO = "owner/repo"
ONE, TWO = 11, 12   # 偽の manifest の Python の 2 つの課題の PR の番号
UNITS = json.dumps({"units": [{"key": "app.py x の値", "label": "block", "reason": "app.py:2 が y を 3 にした"}]})

FAKE_SHELL = """#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
home = pathlib.Path(os.environ["WORKS_FACTORY_HOME"])
plan = json.loads(pathlib.Path(os.environ["FAKE_PLAN"]).read_text(encoding="utf-8"))
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"who": "works-factory", "args": args, "home": str(home),
                        "env": {k: os.environ.get(k) for k in WATCHED}, "names": sorted(os.environ)}) + "\\n")
state_file = home / "fake-state.json"
state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {"runs": []}
verb = args[1]

def save():
    state_file.write_text(json.dumps(state), encoding="utf-8")

def put(root, files):
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")

if verb == "run":
    rid = plan.get("run_id", "a1b2c3d4-0000-run")
    state["runs"].append({"id": rid, "status": plan.get("status", "completed"), "parent_run_id": None,
                          "started_at": "2026-10-12T00:00:00Z"})
    put(home / "art" / rid, plan.get("artifacts", {"judge/judgment.json": UNITS}))
    for n in range(plan.get("children", 0)):
        kid = f"{rid}-child-{n}"
        state["runs"].append({"id": kid, "status": "completed", "parent_run_id": rid, "started_at": f"2026-10-12T00:0{n + 1}:00Z"})
        put(home / "art" / kid, plan.get("child_artifacts", {}))
    save()
elif verb == "runs":
    print(json.dumps({"runs": state["runs"][::-1]}))
elif verb == "status":
    print(json.dumps({"runs": [r for r in state["runs"] if r["status"] in ("running", "paused")]}))
elif verb == "get":
    run = next(r for r in state["runs"] if r["id"] == args[2])
    parent = run["parent_run_id"] is None
    if "--events" in args:
        if plan.get("events_unreadable"):
            print("not json")
            sys.exit(0)
        print(json.dumps({"id": run["id"], "events": [
            {"event_type": "workflow_started", "created_at": "2026-10-12T00:00:00.000Z"},
            {"event_type": "workflow_started", "created_at": "2026-10-12T01:00:00.000Z"}]}))
        sys.exit(0)
    print(json.dumps({"id": run["id"], "status": run["status"], "started_at": "2026-10-12T01:00:00Z",
                      "completed_at": "2026-10-12T01:30:00Z",
                      "metadata": {"total_cost_usd": 3.25,
                                   **({"approval": {"nodeId": plan.get("gate", "gate-final")}} if run["status"] == "paused" else {})},
                      "terminal_record": {"run_id": run["id"], "status": run["status"],
                                          "nodes": plan.get("nodes", []) if parent else [],
                                          "returns": {"availability": "available", "node_id": "result",
                                                      "value": {"outcome": plan.get("outcome", "fixed")}},
                                          "artifacts": {"root": str(home / "art" / run["id"]), "files": [], "limitations": []}}}))
elif verb == "resume":
    for r in state["runs"]:
        if r["id"] == args[2]:
            r["status"] = plan.get("after_resume", "completed")
    save()
"""

FAKE_OLD = """import json, os, pathlib, sqlite3, sys
who, args = sys.argv[1], sys.argv[2:]
plan = json.loads(pathlib.Path(os.environ["FAKE_PLAN"]).read_text(encoding="utf-8"))
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"who": who, "args": args, "cwd": os.getcwd(), "env": {k: os.environ.get(k) for k in WATCHED},
                        "names": sorted(os.environ)}) + "\\n")
home = pathlib.Path(os.environ["WORKS_USE_HOME"])
db = home / "archon-home" / "archon.db"
queue = home / "fake-waits.json"
WAITS = {5: "completed", 0: "paused", 1: "failed", 3: "running"}

def status(word):
    con = sqlite3.connect(db)
    con.execute("UPDATE remote_agent_workflow_runs SET status = ?", (word,))
    con.commit()
    con.close()

if who == "use.sh" and args[0] == "start":
    rid = plan.get("run_id", "b5c6d7e8-0000-old")
    (home / "runs").mkdir(parents=True)
    (home / "runs" / f"{rid}.json").write_text("{}", encoding="utf-8")
    board = home / "out" / "artifacts" / "runs" / rid / "board"
    board.mkdir(parents=True)
    (board / "report.md").write_text(f"# 報告（run {rid}）\\n\\n起きたこと: 直した（{plan.get('outcome', 'fixed')}）\\n",
                                     encoding="utf-8")
    for name, text in plan.get("board", {"out/r1/p2.diagnose.json": UNITS}).items():
        (board / name).parent.mkdir(parents=True, exist_ok=True)
        (board / name).write_text(text, encoding="utf-8")
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE remote_agent_workflow_runs (id TEXT, status TEXT, output_root TEXT, started_at TEXT, "
                "completed_at TEXT, metadata TEXT)")
    con.execute("CREATE TABLE remote_agent_workflow_events (workflow_run_id TEXT, event_type TEXT, step_name TEXT, "
                "data TEXT, created_at TEXT, event_order INTEGER)")
    con.execute("INSERT INTO remote_agent_workflow_runs VALUES (?, 'running', ?, '2026-10-12 00:00:00', "
                "'2026-10-12 02:00:00', ?)", (rid, str(home / "out"), json.dumps({"approval": {"nodeId": "r4.human_gate"}})))
    con.execute("INSERT INTO remote_agent_workflow_events VALUES (?, 'workflow_started', '', '{}', '2026-10-12 00:00:00', 0)",
                (rid,))
    for n, gate in enumerate(plan.get("asks", []), 1):
        con.execute("INSERT INTO remote_agent_workflow_events VALUES (?, 'approval_requested', ?, '{}', '', ?)", (rid, gate, n))
    con.execute("INSERT INTO remote_agent_workflow_events VALUES (?, 'workflow_completed', '', ?, '', 99)",
                (rid, json.dumps({"cost_usd": plan.get("usd", 12.5)})))
    con.commit()
    con.close()
    queue.write_text(json.dumps(plan.get("waits", [5])), encoding="utf-8")
elif who == "use.sh" and args[0] == "wait":
    left = json.loads(queue.read_text(encoding="utf-8"))
    rc = left.pop(0)
    queue.write_text(json.dumps(left), encoding="utf-8")
    status(WAITS[rc])
    sys.exit(rc)
elif who == "continue.sh":
    queue.write_text(json.dumps(plan.get(f"{args[2]}_waits", [5])), encoding="utf-8")
    status("running")
"""


FAKE_CLAUDE = """#!PYTHON
import json, os, sys
args = sys.argv[1:]
if args == ["--version"]:
    print("9.9.9 (Claude Code)")
    sys.exit(0)
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"who": "claude", "args": args, "cwd": os.getcwd(), "env": {k: os.environ.get(k) for k in WATCHED},
                        "names": sorted(os.environ)}) + "\\n")
pr = json.load(open(os.environ["RB_PR_JSON"], encoding="utf-8"))
with open(os.environ["RB_OUT"], "w", encoding="utf-8") as f:
    json.dump({"pr": {k: pr[k] for k in ("repo", "pr_number", "base", "head")}, "agent": "claude",
               "findings": [{"file": "app.py", "start_line": 1, "end_line": 1, "message": "x を 2 にした", "producer": "claude"}]}, f)
print(json.dumps({"type": "result", "is_error": os.environ.get("FAKE_CLAUDE_ERROR") == "1", "total_cost_usd": 1.5,
                  "duration_ms": 60000, "session_id": "s-1"}))
"""

FAKE_NPM = """#!PYTHON
import json, os, sys
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"who": "npm", "args": sys.argv[1:], "cwd": os.getcwd(), "env": {k: os.environ.get(k) for k in WATCHED},
                        "names": sorted(os.environ)}) + "\\n")
print("judge: no API key", file=sys.stderr)
sys.exit(int(os.environ.get("FAKE_NPM_EXIT", "0")))
"""


class RunnerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory(prefix="works-calibration-")
        base = pathlib.Path(os.path.realpath(cls._dir.name))
        cls.repo = base / "checkout"
        for name in COPIED:
            (cls.repo / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, cls.repo / name)
        ignore = shutil.ignore_patterns("tests", "__pycache__", "*.pyc")
        shutil.copytree(ROOT / "lib", cls.repo / "lib", ignore=ignore)
        shutil.copytree(ROOT / "bin" / "_lib", cls.repo / "bin" / "_lib", ignore=ignore)
        cls.shell = base / "fake-shell.py"
        cls.shell.write_text(FAKE_SHELL.replace("WATCHED", repr(WATCHED)).replace("UNITS", repr(UNITS)), encoding="utf-8")
        cls.old = base / "claude-plugins"
        dev = cls.old / "works" / "dev"
        dev.mkdir(parents=True)
        (dev / "fake.py").write_text(FAKE_OLD.replace("WATCHED", repr(WATCHED)).replace("UNITS", repr(UNITS)), encoding="utf-8")
        for name in ("use.sh", "continue.sh"):
            (dev / name).write_text(f'#!/bin/sh\nexec "{sys.executable}" "$(dirname "$0")/fake.py" {name} "$@"\n',
                                    encoding="utf-8")
        (dev / "archon.sh").write_text('#!/bin/sh\nARCHON_VERSION="v0.11.1"\n', encoding="utf-8")
        git(cls.old, "init", "-q", "-b", "main")
        git(cls.old, "add", "-A")
        git(cls.old, "commit", "-q", "-m", "works")
        cls.old_commit = git(cls.old, "rev-parse", "HEAD")
        data = json.loads((cls.repo / "pack.json").read_text(encoding="utf-8"))
        data["works"]["commit"] = cls.old_commit
        (cls.repo / "pack.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        git(cls.repo, "init", "-q", "-b", "main")
        git(cls.repo, "add", "-A")
        git(cls.repo, "commit", "-q", "-m", "checkout")
        source = base / "source"
        source.mkdir()
        git(source, "init", "-q", "-b", "main")
        cls.base_sha = commit(source, {"app.py": "x = 1\n"}, "base")
        cls.head_sha = commit(source, {"app.py": "x = 2\ny = 3\n"}, "head")
        git(base, "clone", "-q", "--bare", str(source), str(base / "mirror" / "owner_repo.git"))
        cls.mirror = f"file://{base / 'mirror'}/{{name}}.git"
        cls.bench = base / "ReviewBench"
        (cls.bench / "corpus").mkdir(parents=True)
        row = {"repo": f"https://github.com/{NWO}", "nwo": NWO, "base": cls.base_sha, "head": cls.head_sha,
               "title": "x を 2 にする", "body": "y も足す", "language": "Python"}
        rows = [{**row, "pr_number": ONE}, {**row, "pr_number": 99, "language": "Go"}, {**row, "pr_number": TWO}]
        (cls.bench / "corpus" / "manifest.json").write_text(json.dumps(rows), encoding="utf-8")
        cls.one, cls.two = (f"owner_repo_{n}-{cls.head_sha[:8]}" for n in (ONE, TWO))

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        fake_bin = self.tmp / "fake-bin"
        fake_bin.mkdir()
        for name, text in (("claude", FAKE_CLAUDE), ("npm", FAKE_NPM)):
            (fake_bin / name).write_text(text.replace("PYTHON", sys.executable).replace("WATCHED", repr(WATCHED)), encoding="utf-8")
            (fake_bin / name).chmod(0o755)
        self.log = self.tmp / "fake.jsonl"
        self.plan = self.tmp / "plan.json"
        self.set_plan()
        self.attempts = self.tmp / "attempts"
        self.out = self.tmp / "out"
        self.env = hermetic.child_env(
            HOME=str(self.tmp / "user-home"), PATH=os.pathsep.join([str(fake_bin), os.environ.get("PATH", "")]),
            WORKS_CALIBRATION_SHELL=str(self.shell), WORKS_FACTORY_OLD_WORKS=str(self.old / "works"),
            WORKS_FACTORY_NO_AUTH="1", FAKE_LOG=str(self.log), FAKE_PLAN=str(self.plan), **ITEMS, **GH)
        self.env.pop("CLAUDE_BIN_PATH", None)

    def set_plan(self, **plan):
        self.plan.write_text(json.dumps(plan), encoding="utf-8")

    def runner(self, *args, **env):
        return subprocess.run([sys.executable, str(self.repo / "tests" / "calibration" / "run.py"), *args],
                              env={**self.env, **env}, cwd=self.tmp, capture_output=True, text=True, encoding="utf-8",
                              timeout=300)

    def run_tasks(self, producer, *keys, extra=(), **env):
        return self.runner("run", producer, "--bench", str(self.bench), "--attempts", str(self.attempts), "--out", str(self.out),
                           "--mirror", self.mirror, *(["--only", ",".join(keys)] if keys else []), *extra, **env)

    def calls(self, who=None) -> list[dict]:
        if not self.log.exists():
            return []
        rows = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]
        return [r for r in rows if who is None or r["who"] == who]

    def verbs(self, who="works-factory") -> list[str]:
        return [c["args"][1] if who == "works-factory" else c["args"][0] for c in self.calls(who)]

    def launches(self) -> list[dict]:
        return [c for c in self.calls() if (c["who"] == "works-factory" and c["args"][1] in ("run", "resume"))
                or (c["who"] == "use.sh" and c["args"][0] == "start") or c["who"] == "claude"]

    def inputs(self) -> dict:
        [call] = [c for c in self.calls("works-factory") if c["args"][1] == "run"]
        args = call["args"]
        return dict(args[i + 1].split("=", 1) for i, a in enumerate(args) if a == "--input")

    def records(self, producer) -> list[dict]:
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((self.out / producer / "convert").glob("*.json"))]

    def attempt(self, key, n=1) -> pathlib.Path:
        return self.attempts / f"{key}--{n}"

    def assertRan(self, done):
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


class RunTest(RunnerCase):
    def test_task_runs_at_head_with_bench_base(self):
        for producer in ("works-factory", "works"):
            with self.subTest(producer=producer):
                self.log.unlink(missing_ok=True)
                shutil.rmtree(self.attempts, ignore_errors=True)
                self.assertRan(self.run_tasks(producer, self.one))
                attempt = self.attempt(self.one)
                self.assertEqual(git(attempt / "target", "rev-parse", "HEAD"), self.head_sha)
                self.assertEqual(git(attempt / "origin", "rev-parse", "main"), self.head_sha)
                self.assertEqual(git(attempt / "origin", "rev-parse", "refs/bench/base"), self.base_sha)
                self.assertEqual(json.loads((attempt / "request.json").read_text(encoding="utf-8")),
                                 [{"where": "app.py", "text": "x を 2 にする\n\ny も足す"}])
                if producer == "works-factory":
                    self.assertEqual(self.inputs()["base"], self.base_sha)
                else:
                    [start] = [c for c in self.calls("use.sh") if c["args"][0] == "start"]
                    self.assertEqual(start["args"][1:3], ["--base", self.base_sha])

    def test_bench_inputs_map_to_each_producer(self):
        self.assertRan(self.run_tasks("works-factory", self.one))
        attempt = self.attempt(self.one)
        self.assertEqual(self.inputs(), {"request": str(attempt / "request.json"), "base": self.base_sha,
                                         "unattended": "true", "final_gate": "when_needed"})
        self.assertRan(self.run_tasks("works", self.one))
        [start] = [c for c in self.calls("use.sh") if c["args"][0] == "start"]
        attempt = self.attempt(self.one, 2)
        self.assertEqual(start["args"][-3:], ["--", str(attempt / "target"), str(attempt / "request.json")])
        self.assertEqual({k: start["env"][k] for k in ("WORKS_USE_HOME", "WORKS_USE_UNATTENDED", "WORKS_USE_FINAL_GATE")},
                         {"WORKS_USE_HOME": str(attempt / "home"), "WORKS_USE_UNATTENDED": "1",
                          "WORKS_USE_FINAL_GATE": "when_needed"})

    def test_works_factory_runs_in_foreground_without_detach(self):
        self.assertRan(self.run_tasks("works-factory", self.one))
        launches = [c["args"] for c in self.calls("works-factory") if c["args"][1] in ("run", "resume")]
        self.assertEqual(len(launches), 1)
        self.assertNotIn("--detach", launches[0])
        for module in MODULES:
            tree = ast.parse(module.read_text(encoding="utf-8"))
            words = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
            self.assertFalse(words & {"--detach", "nohup", "setsid", "&"}, module.name)
            self.assertFalse([n for n in ast.walk(tree) if isinstance(n, ast.keyword) and n.arg == "start_new_session"])

    def test_no_timeouts(self):
        for module in MODULES:
            tree = ast.parse(module.read_text(encoding="utf-8"))
            self.assertEqual([n.lineno for n in ast.walk(tree) if isinstance(n, ast.keyword) and n.arg == "timeout"], [], module.name)
            names = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
            self.assertEqual({x for x in names if any(w in x for w in ("TIMEOUT", "DEADLINE", "LIMIT", "MAX", "TRIES"))}, set())
        self.set_plan(waits=[3, 3, 3, 3, 3, 3, 5])
        self.assertRan(self.run_tasks("works", self.one))
        self.assertEqual(self.verbs("use.sh").count("wait"), 7)

    def test_account_env_passes_through_and_is_never_printed(self):
        before = set(self.env)
        for producer in ("works-factory", "works", "claude"):
            with self.subTest(producer=producer):
                done = self.run_tasks(producer, self.one)
                self.assertRan(done)
                for value in [*ITEMS.values(), *GH.values()]:
                    self.assertNotIn(value, done.stdout + done.stderr)
        launches = self.launches()
        self.assertEqual(len(launches), 3)
        for call in launches:
            self.assertEqual({k: call["env"][k] for k in ITEMS}, ITEMS)
            added = set(call["names"]) - before
            self.assertFalse({n for n in added if "TOKEN" in n or "KEY" in n or "AUTH" in n}, added)
        for path in self.out.rglob("*.json"):
            for value in [*ITEMS.values(), *GH.values()]:
                self.assertNotIn(value, path.read_text(encoding="utf-8"))

    def test_bench_env_withholds_gh_and_denies_web(self):
        for producer in ("works-factory", "works", "claude"):
            self.assertRan(self.run_tasks(producer, self.one))
        launches = self.launches()
        self.assertEqual([c["who"] for c in launches], ["works-factory", "use.sh", "claude"])
        for n, call in enumerate(launches, 1):
            with self.subTest(who=call["who"]):
                none = self.attempt(self.one, n) / "home" / "gh-none"
                self.assertIsNone(call["env"]["GH_TOKEN"])
                self.assertEqual(call["env"]["GH_CONFIG_DIR"], str(none))
                self.assertEqual(list(none.iterdir()), [])
                self.assertEqual(call["env"]["WORKS_FACTORY_DENY_WEB"], "1")
        [record] = self.records("works")
        self.assertEqual(record["leak_guard"]["web"], "open")
        self.assertEqual({self.records(p)[0]["leak_guard"]["web"] for p in ("works-factory", "claude")}, {"denied"})

    def test_plain_claude_settings_deny_web(self):
        self.assertRan(self.run_tasks("claude", self.one))
        settings = self.attempt(self.one) / "home" / "claude-config" / "settings.json"
        deny = json.loads(settings.read_text(encoding="utf-8"))["permissions"]["deny"]
        self.assertEqual(deny, runner.toolset.DENY_WEB["deny"])
        self.assertLessEqual({"WebFetch", "WebSearch"}, set(deny))
        [call] = self.calls("claude")
        self.assertEqual(call["env"]["CLAUDE_CONFIG_DIR"], str(settings.parent))

    def test_plain_claude_runs_once_at_target_with_model_and_effort(self):
        self.assertRan(self.run_tasks("claude", self.one))
        [call] = self.calls("claude")
        args = call["args"]
        self.assertEqual(call["cwd"], str(self.attempt(self.one) / "target"))
        self.assertEqual(args[args.index("--model") + 1], "opus")
        self.assertEqual(args[args.index("--effort") + 1], "high")
        at = args.index("--disallowedTools")
        self.assertEqual(args[at + 1:at + 3], ["WebFetch", "WebSearch"])
        self.assertEqual(args[-2], "-p")
        self.assertEqual((call["env"]["RB_BASE"], call["env"]["RB_HEAD"]), (self.base_sha, self.head_sha))
        [record] = self.records("claude")
        self.assertEqual((record["seconds"], record["usd"], record["outcome"]), (60.0, 1.5, "done"))
        self.assertEqual([f["node"] for f in record["findings"]], ["claude"])
        self.assertEqual(record["provenance"]["model"], "opus")

    def test_plain_claude_error_result_stops_and_resumes(self):
        done = self.run_tasks("claude", self.one, FAKE_CLAUDE_ERROR="1")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertFalse((self.out / "claude" / "findings").exists())
        self.assertEqual(runner.Ledger(self.attempts).last(self.one, "claude")["state"], "stopped")
        self.assertRan(self.run_tasks("claude", self.one, extra=("--resume",)))
        self.assertEqual(len(self.calls("claude")), 2)
        self.assertEqual(runner.Ledger(self.attempts).last(self.one, "claude")["state"], "done")

    def test_claude_bin_path_is_the_claude_run_and_recorded(self):
        other = self.tmp / "other-bin" / "claude"
        other.parent.mkdir()
        text = (self.tmp / "fake-bin" / "claude").read_text(encoding="utf-8")
        other.write_text(text.replace("9.9.9", "8.8.8").replace('"who": "claude"', '"who": "other-claude"'), encoding="utf-8")
        other.chmod(0o755)
        self.assertRan(self.run_tasks("claude", self.one, CLAUDE_BIN_PATH=str(other)))
        self.assertEqual((len(self.calls("claude")), len(self.calls("other-claude"))), (0, 1))
        [record] = self.records("claude")
        self.assertEqual(record["provenance"]["claude_code"], "8.8.8 (Claude Code)")

    def test_run_writes_findings_and_convert_record(self):
        for producer in ("works-factory", "works", "claude"):
            with self.subTest(producer=producer):
                done = self.run_tasks(producer, self.one)
                self.assertRan(done)
                found = json.loads((self.out / producer / "findings" / f"{self.one}.json").read_text(encoding="utf-8"))
                self.assertEqual(found["pr"], {"repo": f"https://github.com/{NWO}", "pr_number": ONE,
                                               "base": self.base_sha, "head": self.head_sha})
                self.assertEqual(len(found["findings"]), 1)
                self.assertEqual(found["findings"][0]["producer"], producer)
                path = self.out / producer / "convert" / f"{self.one}.json"
                record = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(json.loads(done.stdout), record)
                self.assertEqual(record["key"], self.one)
                self.assertEqual(record["provenance"]["claude_code"], "9.9.9 (Claude Code)")
                text = json.dumps({k: v for k, v in record.items() if k != "attempt"}, ensure_ascii=False)
                for word in (str(self.tmp), "/Users/", "/home/", "/private/"):
                    self.assertNotIn(word, text)
        [wf] = self.records("works-factory")
        self.assertEqual((wf["findings"][0]["file"], wf["findings"][0]["start_line"]), ("app.py", 2))
        self.assertEqual((wf["usd"], wf["seconds"]), (3.25, 5400.0))
        self.assertEqual(wf["provenance"]["factory_commit"], git(self.repo, "rev-parse", "HEAD"))
        [old] = self.records("works")
        self.assertEqual((old["usd"], old["seconds"], old["outcome"]), (12.5, 7200.0, "fixed"))
        self.assertEqual(old["provenance"]["archon"], "v0.11.1")

    def test_paused_run_is_not_answered(self):
        for producer, plan in (("works-factory", {"status": "paused"}), ("works", {"waits": [3, 0]})):
            with self.subTest(producer=producer):
                self.log.unlink(missing_ok=True)
                shutil.rmtree(self.attempts, ignore_errors=True)
                self.set_plan(**plan)
                done = self.run_tasks(producer, self.one, self.two)
                self.assertEqual(done.returncode, 1, done.stderr)
                self.assertEqual(len(done.stderr.strip().splitlines()), 1, done.stderr)
                self.assertIn("gate-final" if producer == "works-factory" else "r4.human_gate", done.stderr)
                every = [a for c in self.calls() for a in c["args"]]
                self.assertFalse({"respond", "answer", "approve", "reject"} & set(every))
                self.assertFalse(self.out.exists())
                self.assertFalse(self.attempt(self.two).exists())

    def test_failed_row_stops_and_resume_continues_same_run(self):
        for producer, failing in (("works-factory", {"status": "failed"}), ("works", {"waits": [1]})):
            with self.subTest(producer=producer):
                self.log.unlink(missing_ok=True)
                shutil.rmtree(self.attempts, ignore_errors=True)
                shutil.rmtree(self.out, ignore_errors=True)
                self.set_plan(**failing)
                done = self.run_tasks(producer, self.one, self.two)
                self.assertEqual(done.returncode, 1, done.stderr)
                self.assertFalse(self.attempt(self.two).exists())
                again = self.run_tasks(producer, self.one, self.two)
                self.assertEqual(again.returncode, 2, again.stderr)
                [line] = again.stderr.strip().splitlines()
                self.assertIn("--resume", line)
                self.log.unlink()
                self.set_plan()
                resumed = self.run_tasks(producer, self.one, self.two, extra=["--resume"])
                self.assertRan(resumed)
                if producer == "works-factory":
                    resumes = [c["args"] for c in self.calls("works-factory") if c["args"][1] == "resume"]
                    self.assertEqual([a[2] for a in resumes], ["a1b2c3d4-0000-run"])
                    self.assertEqual(resumes[0][-2:], ["--cwd", str(self.attempt(self.one) / "target")])
                else:
                    [resume] = self.calls("continue.sh")
                    self.assertEqual(resume["args"][1:], ["workflow", "resume", "b5c6d7e8-0000-old"])
                    self.assertEqual(resume["env"]["WORKS_DEV_HOME"], str(self.attempt(self.one) / "home"))
                self.assertEqual(sorted(r["key"] for r in self.records(producer)), sorted([self.one, self.two]))

        shutil.rmtree(self.attempts)
        self.set_plan(status="running")
        self.assertEqual(self.run_tasks("works-factory", self.one).returncode, 1)
        self.log.unlink()
        done = self.run_tasks("works-factory", self.one, extra=["--resume"])
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertNotIn("resume", self.verbs())

    def test_resume_skips_done_rows(self):
        for producer in ("works-factory", "works", "claude"):
            with self.subTest(producer=producer):
                shutil.rmtree(self.attempts, ignore_errors=True)
                self.assertRan(self.run_tasks(producer, self.one))
                self.log.unlink()
                self.assertRan(self.run_tasks(producer, self.one, extra=["--resume"]))
                self.assertEqual(self.calls(), [])
                self.assertFalse(self.attempt(self.one, 2).exists())

    def test_only_names_unknown_task(self):
        done = self.run_tasks("works-factory", "owner_repo_99-nothing")
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn("owner_repo_99-nothing", done.stderr)
        self.assertFalse(self.attempts.exists())

    def test_old_works_commit_must_match_pack(self):
        other = self.tmp / "other-plugins"
        (other / "works" / "dev").mkdir(parents=True)
        git(other, "init", "-q", "-b", "main")
        (other / ".git" / "refs" / "heads" / "main").write_text("1" * 40 + "\n", encoding="utf-8")
        done = self.old_works_at(other / "works", self.attempts)
        self.assertEqual(done.returncode, 2, done.stderr)
        [line] = done.stderr.strip().splitlines()
        self.assertIn("1" * 40, line)
        self.assertIn(self.old_commit, line)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.attempts.exists())

    def old_works_at(self, works: pathlib.Path, attempts: pathlib.Path):
        return self.runner("run", "works", "--bench", str(self.bench), "--attempts", str(attempts), "--out", str(self.out),
                           "--mirror", self.mirror, "--only", self.one, WORKS_FACTORY_OLD_WORKS=str(works))

    def test_old_works_must_be_committed_and_have_use_sh(self):
        copy = self.tmp / "copy-plugins"
        shutil.copytree(self.old, copy)
        (copy / "elsewhere.txt").write_text("outside works/\n", encoding="utf-8")
        self.assertRan(self.old_works_at(copy / "works", self.attempts))
        self.log.unlink()
        changes = {"edited": lambda: (copy / "works" / "dev" / "archon.sh").write_text('ARCHON_VERSION="v9"\n', encoding="utf-8"),
                   "untracked": lambda: (copy / "works" / "dev" / "extra.sh").write_text("", encoding="utf-8")}
        for name, change in changes.items():
            with self.subTest(change=name):
                git(copy, "checkout", "-q", "--", ".")
                git(copy, "clean", "-qfd", "works")
                change()
                done = self.old_works_at(copy / "works", self.tmp / name)
                self.assertEqual(done.returncode, 2, done.stderr)
                [line] = done.stderr.strip().splitlines()
                self.assertIn("commit していない", line)
                self.assertIn("dev/", line)
                self.assertFalse((self.tmp / name).exists())
        done = self.old_works_at(self.old, self.tmp / "root")
        self.assertEqual(done.returncode, 2, done.stderr)
        [line] = done.stderr.strip().splitlines()
        self.assertIn("dev/use.sh が無い", line)
        self.assertEqual(self.calls(), [])
        self.assertFalse((self.tmp / "root").exists())

    def test_old_works_resume_answers_stop_at_human_gate(self):
        self.set_plan(waits=[1])
        self.assertEqual(self.run_tasks("works", self.one).returncode, 1)
        self.log.unlink()
        self.set_plan(resume_waits=[3, 0], respond_waits=[3, 5])
        self.assertRan(self.run_tasks("works", self.one, extra=["--resume"]))
        rid = "b5c6d7e8-0000-old"
        self.assertEqual([c["args"][1:5] for c in self.calls("continue.sh")],
                         [["workflow", "resume", rid], ["workflow", "respond", rid, "stop"]])
        [respond] = [c for c in self.calls("continue.sh") if c["args"][2] == "respond"]
        self.assertIn("WORKS_USE_UNATTENDED=1", respond["args"][5])
        self.assertEqual(respond["env"]["WORKS_DEV_HOME"], str(self.attempt(self.one) / "home"))
        self.assertEqual(self.verbs("use.sh").count("wait"), 4)
        self.assertEqual([r["key"] for r in self.records("works")], [self.one])

    def test_unreadable_events_stop_the_row(self):
        self.set_plan(events_unreadable=True)
        done = self.run_tasks("works-factory", self.one)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn("run a1b2c3d4-0000-run の出来事の列を evidence/ に写せない", done.stderr)
        self.assertFalse(self.out.exists())

    SPANS = {"works-factory": lambda row, events: {"record/parent.json": {**row, "terminal_record": {}},
                                                   "record/parent-events.json": {"events": events}},
             "works": lambda row, events: {"record/parent.json": {"run": row, "events": events}}}

    def test_seconds_span_from_the_first_event_across_resumes(self):
        """Archon は再開のたびに行の started_at を書き直すので、両工場とも時間は最初の出来事から completed_at までで測る"""
        row = {"started_at": "2026-10-12 01:59:50", "completed_at": "2026-10-12 02:00:00"}
        events = [{"event_type": "workflow_started", "created_at": "2026-10-12 01:50:00"},
                  {"event_type": "workflow_started", "created_at": "2026-10-12 01:59:50"},
                  {"event_type": "workflow_completed", "created_at": "2026-10-12 02:00:00", "data": {"cost_usd": 1.0}}]
        for producer, files in self.SPANS.items():
            for given, seconds in ((events, 600.0), ([], None)):
                with self.subTest(producer=producer, events=len(given)), tempfile.TemporaryDirectory() as tmp:
                    ev = pathlib.Path(tmp)
                    (ev / "record").mkdir()
                    for name, doc in files(row, given).items():
                        (ev / name).write_text(json.dumps(doc), encoding="utf-8")
                    self.assertEqual(runner.PRODUCERS[producer].ended(ev)["seconds"], seconds)

    def test_dry_run_launches_nothing(self):
        for producer in ("works-factory", "works", "claude"):
            with self.subTest(producer=producer):
                done = self.run_tasks(producer, extra=["--dry-run"])
                self.assertRan(done)
                lines = [json.loads(line) for line in done.stdout.splitlines()]
                self.assertEqual([x["key"] for x in lines], [self.one, self.two])
                self.assertEqual({x["base"] for x in lines}, {self.base_sha})
                for value in [*ITEMS.values(), *GH.values()]:
                    self.assertNotIn(value, done.stdout + done.stderr)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.attempts.exists())
        self.assertFalse(self.out.exists())

    def test_attempts_inside_repository_refused(self):
        inside = self.repo / "attempts"
        done = self.runner("run", "works-factory", "--bench", str(self.bench), "--attempts", str(inside), "--out", str(self.out),
                           "--only", self.one)
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertEqual(len(done.stderr.strip().splitlines()), 1)
        self.assertFalse(inside.exists())
        self.assertEqual(self.calls(), [])

    def test_second_runner_on_same_attempts_refused(self):
        self.attempts.mkdir()
        fd = os.open(self.attempts / ".lock", os.O_CREAT | os.O_RDWR)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        done = self.run_tasks("works-factory", self.one)
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn("別のランナー", done.stderr)
        self.assertEqual(self.calls(), [])

    def test_works_factory_inputs_exist_in_main_graph(self):
        graph = yaml.safe_load((ROOT / "workflows" / "line" / "works-factory-line.yaml").read_text(encoding="utf-8"))
        self.assertEqual(graph["name"], "works-factory-line")
        self.assertLessEqual(set(runner.BENCH_INPUTS) | {"request", "base"},
                             set(graph["inputs"]))
        self.assertRan(self.run_tasks("works-factory", self.one))
        self.assertLessEqual(set(self.inputs()), set(graph["inputs"]))
        self.assertEqual(self.calls("works-factory")[0]["args"][:3], ["workflow", "run", "works-factory-line"])

    def test_bench_attempts_are_not_listed_for_teardown(self):
        self.assertRan(self.run_tasks("works-factory", self.one))
        book = pathlib.Path(git(self.repo, "rev-parse", "--absolute-git-dir")) / "works-factory-e2e" / "homes"
        self.assertFalse(book.exists())

    def test_judge_writes_models_json_and_calls_npm(self):
        (self.bench / "node_modules").mkdir(exist_ok=True)
        self.addCleanup(shutil.rmtree, self.bench / "node_modules")
        self.assertRan(self.run_tasks("claude", self.one))
        judge = ["judge", "claude", "--bench", str(self.bench), "--out", str(self.out)]
        self.assertRan(self.runner(*judge))
        [call] = self.calls("npm")
        mine = self.out / "claude"
        self.assertEqual(call["cwd"], str(self.bench))
        self.assertEqual(call["env"]["PI_CODING_AGENT_DIR"], str(mine / ".judge"))
        self.assertEqual(call["args"], ["run", "judge", "--", "--candidate", str(mine / "findings"), "--provider", "anthropic",
                                        "--model", "claude-sonnet-5", "--output", str(mine / "scoring" / "results.json")])
        models = json.loads((mine / ".judge" / "models.json").read_text(encoding="utf-8"))
        self.assertEqual([m["id"] for m in models["providers"]["anthropic"]["models"]], ["claude-sonnet-5"])
        failed = self.runner(*judge, FAKE_NPM_EXIT="1")
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertIn("no API key", failed.stderr)
        self.assertIn("#435", failed.stderr)

    def test_judge_needs_npm_ci_first(self):
        done = self.runner("judge", "claude", "--bench", str(self.bench), "--out", str(self.out))
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn("npm ci", done.stderr)
        self.assertEqual(self.calls(), [])

    def test_nodes_command_writes_json_and_md(self):
        self.assertRan(self.run_tasks("works-factory", self.one))
        self.assertRan(self.runner("nodes", "works-factory", "--out", str(self.out)))
        got = json.loads((self.out / "works-factory" / "nodes.json").read_text(encoding="utf-8"))
        self.assertEqual((got["producer"], got["tasks"], got["judged"]), ("works-factory", 1, False))
        self.assertTrue((self.out / "works-factory" / "nodes.md").read_text(encoding="utf-8").startswith("# ノードごとの表"))


class WebCallsTest(unittest.TestCase):
    """web_calls は記録のフック（bin/_lib/record-read.py）が書く形の行から、拒む道具の呼びだけを数える"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.attempt = pathlib.Path(tmp.name)
        self.config = self.attempt / "home" / "claude-config"

    def test_no_record_root_is_none(self):
        self.assertIsNone(runner.web_calls(self.attempt))

    def test_counts_web_rows_across_work_places(self):
        root = runner.reads.root(self.config)
        rows = {"WebFetch": "https://example.com", "WebSearch": "q", "Agent": "general-purpose"}
        for cwd in ("/w/one", "/w/two"):
            log = runner.reads.reads_path(root, cwd)
            log.parent.mkdir(parents=True)
            log.write_text("".join(json.dumps({"ts": "2026-10-14T08:00:00", "tool_name": t, "input": i}) + "\n"
                                   for t, i in rows.items())
                           + json.dumps({"ts": "2026-10-14T08:00:01", "path": "app.py"}) + "\nnot json\n", encoding="utf-8")
        self.assertEqual(runner.web_calls(self.attempt), 4)

    def test_unreadable_record_is_none(self):
        log = runner.reads.reads_path(runner.reads.root(self.config), "/w/one")
        log.mkdir(parents=True)
        self.assertIsNone(runner.web_calls(self.attempt))

    def test_denied_tools_are_recorded_by_the_read_hook(self):
        """数える道具が読んだ証拠のフックの matcher と記録の口に無いと、呼んでも行が無く 0 と数える"""
        denied = set(runner.toolset.DENY_WEB["deny"])
        self.assertLessEqual(denied, set(runner.toolset.READ_MATCHER.split("|")))
        self.assertLessEqual(denied, set(runner.reads.WEB_INPUTS))


if __name__ == "__main__":
    unittest.main()

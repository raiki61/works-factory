"""較正のランナー tests/calibration/run.py の試験。合成の工場だけで回し、本物の Archon・claude・網を使わない。

ランナーは自分の在る checkout の git の私用の置き場に make_target.py の控えを書くので、本物の checkout では走らせない。ランナーが
読む物（束・種・flags.json・make_target.py・evidence.py・lib/・docs/design.md・docs/nodes.json・pack.json・factory/pack.json）を
一時の checkout に写し、そこで走らせる。偽の works-factory の殻（差し替え口 WORKS_CALIBRATION_SHELL で渡し、teardown のために
bin/works-factory にも置く）と、偽の今の works（WORKS_FACTORY_OLD_WORKS で渡す。dev/use.sh・continue.sh・archon.sh を commit した
git の置き場で、写した pack.json の works.commit をその commit に替える）は、
受けた引数と環境の名を FAKE_LOG に 1 行ずつ残し、FAKE_PLAN の JSON どおりに run の記録・置き場・盤面・archon.db を書く。
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
from tests.calibration import corpus
from tests.calibration import run as runner

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
RUNNER = HERE / "run.py"
COPIED = ["pack.json", "factory/pack.json", "bin/_lib/pack.py", "docs/design.md", "docs/nodes.json", "tests/__init__.py",
          "tests/calibration/__init__.py", "tests/calibration/corpus.py", "tests/calibration/corpus.json",
          "tests/calibration/run.py", "tests/calibration/flags.json", "tests/e2e/__init__.py",
          "tests/e2e/make_target.py", "tests/e2e/evidence.py"]
CHANGE, REQUEST, CONTROL = "mean-divides-by-n-minus-one", "clamp-above-returns-lo", "control-clearer-names"
ITEMS = {"WORKS_FACTORY_KEYCHAIN_ITEM": "item-of-works-factory-zq7", "WORKS_KEYCHAIN_ITEM": "item-of-old-works-zq7"}
WATCHED = [*ITEMS, "WORKS_FACTORY_HOME", "WORKS_USE_HOME", "WORKS_USE_UNATTENDED", "WORKS_USE_FINAL_GATE",
           "WORKS_USE_THICKNESS", "WORKS_DEV_HOME"]

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
    put(home / "art" / rid, plan.get("artifacts", {"test-gate/base/baseline.json": '{"material": {"status": "found"}}'}))
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
        if "events_unreadable" in plan:
            print(plan["events_unreadable"])
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
    for name, text in plan.get("board", {"out/r1/p0.local_checks.json": '{"material": {"status": "found"}}'}).items():
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


class RunnerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory(prefix="works-calibration-")
        base = pathlib.Path(os.path.realpath(cls._dir.name))
        cls.repo = base / "checkout"
        for name in COPIED:
            (cls.repo / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, cls.repo / name)
        shutil.copytree(HERE / "seed", cls.repo / "tests" / "calibration" / "seed", ignore=corpus.COPY_IGNORE)
        shutil.copytree(ROOT / "lib", cls.repo / "lib", ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"))
        cls.shell = base / "fake-shell.py"
        cls.shell.write_text(FAKE_SHELL.replace("WATCHED", repr(WATCHED)), encoding="utf-8")
        (cls.repo / "bin").mkdir(exist_ok=True)
        shutil.copy2(cls.shell, cls.repo / "bin" / "works-factory")
        cls.old = base / "claude-plugins"
        dev = cls.old / "works" / "dev"
        dev.mkdir(parents=True)
        (dev / "fake.py").write_text(FAKE_OLD.replace("WATCHED", repr(WATCHED)), encoding="utf-8")
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

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        fake_bin = self.tmp / "fake-bin"
        fake_bin.mkdir()
        (fake_bin / "claude").write_text("#!/bin/sh\necho '9.9.9 (Claude Code)'\n", encoding="utf-8")
        (fake_bin / "claude").chmod(0o755)
        self.log = self.tmp / "fake.jsonl"
        self.plan = self.tmp / "plan.json"
        self.set_plan()
        self.attempts = self.tmp / "attempts"
        self.observed = self.tmp / "observed"
        self.env = hermetic.child_env(
            HOME=str(self.tmp / "user-home"), PATH=os.pathsep.join([str(fake_bin), os.environ.get("PATH", "")]),
            WORKS_CALIBRATION_SHELL=str(self.shell), WORKS_FACTORY_OLD_WORKS=str(self.old / "works"),
            FAKE_LOG=str(self.log), FAKE_PLAN=str(self.plan), **ITEMS)
        self.addCleanup(self.clear_ledger)

    def clear_ledger(self):
        book = pathlib.Path(git(self.repo, "rev-parse", "--absolute-git-dir")) / "works-factory-e2e" / "homes"
        book.unlink(missing_ok=True)

    def set_plan(self, **plan):
        self.plan.write_text(json.dumps(plan), encoding="utf-8")

    def runner(self, *args, **env):
        return subprocess.run([sys.executable, str(self.repo / "tests" / "calibration" / "run.py"), *args],
                              env={**self.env, **env}, cwd=self.tmp, capture_output=True, text=True, encoding="utf-8",
                              timeout=300)

    def run_rows(self, factory, *ids, extra=()):
        return self.runner("run", factory, "--attempts", str(self.attempts), "--observed", str(self.observed),
                           *(["--only", ",".join(ids)] if ids else []), *extra)

    def calls(self, who=None) -> list[dict]:
        if not self.log.exists():
            return []
        rows = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]
        return [r for r in rows if who is None or r["who"] == who]

    def verbs(self, who="works-factory") -> list[str]:
        return [c["args"][1] if who == "works-factory" else c["args"][0] for c in self.calls(who)]

    def inputs(self) -> dict:
        [call] = [c for c in self.calls("works-factory") if c["args"][1] == "run"]
        args = call["args"]
        return dict(args[i + 1].split("=", 1) for i, a in enumerate(args) if a == "--input")

    def observed_files(self, factory) -> list[dict]:
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((self.observed / factory).glob("*.json"))]

    def target_of(self, row_id) -> pathlib.Path:
        return self.attempts / f"{row_id}--1" / "target"

    def assertRan(self, done):
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


class RunTest(RunnerCase):
    def test_change_row_passes_base_and_two_commits(self):
        row = corpus.load()["rows"][0]
        for factory in ("works-factory", "works"):
            with self.subTest(factory=factory):
                self.log.unlink(missing_ok=True)
                shutil.rmtree(self.attempts, ignore_errors=True)
                self.assertRan(self.run_rows(factory, CHANGE))
                origin = self.attempts / f"{CHANGE}--1" / "origin"
                commits = git(origin, "rev-list", "main").split()
                self.assertEqual(len(commits), 2)
                self.assertEqual(git(origin, "log", "-1", "--format=%s", "main"), row["request"][0]["text"])
                self.assertEqual(git(self.target_of(CHANGE), "status", "--porcelain"), "")
                if factory == "works-factory":
                    self.assertEqual(self.inputs()["base"], commits[1])
                else:
                    [start] = [c for c in self.calls("use.sh") if c["args"][0] == "start"]
                    self.assertEqual(start["args"][1:3], ["--base", commits[1]])
                    self.assertIn("stats.py", git(origin, "diff", "--name-only", commits[1], commits[0]))

    def test_request_row_has_one_commit_and_no_base(self):
        for factory in ("works-factory", "works"):
            with self.subTest(factory=factory):
                self.log.unlink(missing_ok=True)
                shutil.rmtree(self.attempts, ignore_errors=True)
                self.assertRan(self.run_rows(factory, REQUEST))
                self.assertEqual(git(self.attempts / f"{REQUEST}--1" / "origin", "rev-list", "--count", "main"), "1")
                if factory == "works-factory":
                    self.assertNotIn("base", self.inputs())
                else:
                    [start] = [c for c in self.calls("use.sh") if c["args"][0] == "start"]
                    self.assertNotIn("--base", start["args"])

    def test_run_inputs_map_to_each_factory(self):
        self.assertRan(self.run_rows("works-factory", REQUEST))
        attempt = self.attempts / f"{REQUEST}--1"
        self.assertEqual(self.inputs(), {"request": str(attempt / "request.json"), "test_cmd": "python3 -m unittest -v",
                                         "tdd_suite": "junit-suite.sh", "unattended": "true", "final_gate": "when_needed",
                                         "thickness": "標準"})
        self.assertRan(self.run_rows("works", CONTROL))
        [start] = [c for c in self.calls("use.sh") if c["args"][0] == "start"]
        attempt = self.attempts / f"{CONTROL}--1"
        self.assertEqual(start["args"][-4:], [str(attempt / "target"), str(attempt / "request.json"),
                                              "python3 -m unittest -v", "junit-suite.sh"])
        self.assertEqual({k: start["env"][k] for k in ("WORKS_USE_HOME", "WORKS_USE_UNATTENDED", "WORKS_USE_FINAL_GATE",
                                                        "WORKS_USE_THICKNESS")},
                         {"WORKS_USE_HOME": str(attempt / "home"), "WORKS_USE_UNATTENDED": "1",
                          "WORKS_USE_FINAL_GATE": "when_needed", "WORKS_USE_THICKNESS": "標準"})

        self.log.unlink()
        data = json.loads((HERE / "corpus.json").read_text(encoding="utf-8"))
        data["run_inputs"]["features_off"] = "tdd"
        odd = self.repo / "tests" / "calibration" / "corpus-odd.json"
        odd.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.addCleanup(odd.unlink)
        for factory in ("works-factory", "works"):
            with self.subTest(factory=factory):
                done = self.run_rows(factory, extra=["--corpus", str(odd), "--attempts", str(self.tmp / "odd")])
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertIn("features_off", done.stderr)
                self.assertEqual(self.calls(), [])
                self.assertFalse((self.tmp / "odd").exists())

    def test_works_factory_runs_in_foreground_without_detach(self):
        self.assertRan(self.run_rows("works-factory", REQUEST))
        launches = [c["args"] for c in self.calls("works-factory") if c["args"][1] in ("run", "resume")]
        self.assertEqual(len(launches), 1)
        self.assertNotIn("--detach", launches[0])
        tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
        words = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        self.assertFalse(words & {"--detach", "nohup", "setsid", "&"}, words & {"--detach", "nohup", "setsid", "&"})
        self.assertFalse([n for n in ast.walk(tree) if isinstance(n, ast.keyword) and n.arg == "start_new_session"])

    def test_no_timeouts(self):
        tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
        self.assertEqual([n.lineno for n in ast.walk(tree) if isinstance(n, ast.keyword) and n.arg == "timeout"], [])
        names = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
        self.assertEqual({x for x in names if any(w in x for w in ("TIMEOUT", "DEADLINE", "LIMIT", "MAX", "TRIES"))}, set())
        self.set_plan(waits=[3, 3, 3, 3, 3, 3, 5])
        self.assertRan(self.run_rows("works", REQUEST))
        self.assertEqual(self.verbs("use.sh").count("wait"), 7)

    def test_account_env_passes_through_and_is_never_printed(self):
        before = set(self.env)
        for factory in ("works-factory", "works"):
            with self.subTest(factory=factory):
                done = self.run_rows(factory, REQUEST if factory == "works-factory" else CONTROL)
                self.assertRan(done)
                for value in ITEMS.values():
                    self.assertNotIn(value, done.stdout + done.stderr)
        launches = [c for c in self.calls() if c["who"] == "use.sh" or c["args"][1:2] in (["run"], ["resume"])]
        self.assertTrue(launches)
        for call in launches:
            self.assertEqual({k: call["env"][k] for k in ITEMS}, ITEMS)
            added = set(call["names"]) - before
            self.assertFalse({n for n in added if "TOKEN" in n or "KEY" in n or "AUTH" in n}, added)
        for path in self.observed.rglob("*.json"):
            for value in ITEMS.values():
                self.assertNotIn(value, path.read_text(encoding="utf-8"))

    def test_paused_run_is_not_answered(self):
        for factory, plan in (("works-factory", {"status": "paused"}), ("works", {"waits": [3, 0]})):
            with self.subTest(factory=factory):
                self.log.unlink(missing_ok=True)
                shutil.rmtree(self.attempts, ignore_errors=True)
                self.set_plan(**plan)
                done = self.run_rows(factory, REQUEST, CONTROL)
                self.assertEqual(done.returncode, 1, done.stderr)
                self.assertEqual(len(done.stderr.strip().splitlines()), 1, done.stderr)
                self.assertIn("gate-final" if factory == "works-factory" else "r4.human_gate", done.stderr)
                every = [a for c in self.calls() for a in c["args"]]
                self.assertFalse({"respond", "answer", "approve", "reject"} & set(every))
                self.assertFalse(self.observed.exists())
                self.assertFalse((self.attempts / f"{CONTROL}--1").exists())

    def test_failed_row_stops_and_resume_continues_same_run(self):
        for factory, failing in (("works-factory", {"status": "failed"}), ("works", {"waits": [1]})):
            with self.subTest(factory=factory):
                self.log.unlink(missing_ok=True)
                shutil.rmtree(self.attempts, ignore_errors=True)
                shutil.rmtree(self.observed, ignore_errors=True)
                self.set_plan(**failing)
                done = self.run_rows(factory, REQUEST, CONTROL)
                self.assertEqual(done.returncode, 1, done.stderr)
                self.assertFalse((self.attempts / f"{CONTROL}--1").exists())
                again = self.run_rows(factory, REQUEST, CONTROL)
                self.assertEqual(again.returncode, 2, again.stderr)
                [line] = again.stderr.strip().splitlines()
                self.assertIn("--resume", line)
                self.log.unlink()
                self.set_plan()
                resumed = self.run_rows(factory, REQUEST, CONTROL, extra=["--resume"])
                self.assertRan(resumed)
                if factory == "works-factory":
                    resumes = [c["args"] for c in self.calls("works-factory") if c["args"][1] == "resume"]
                    self.assertEqual([a[2] for a in resumes], ["a1b2c3d4-0000-run"])
                    self.assertEqual(resumes[0][-2:], ["--cwd", str(self.target_of(REQUEST))])
                else:
                    [resume] = self.calls("continue.sh")
                    self.assertEqual(resume["args"][1:], ["workflow", "resume", "b5c6d7e8-0000-old"])
                    self.assertEqual(resume["env"]["WORKS_DEV_HOME"], str(self.attempts / f"{REQUEST}--1" / "home"))
                self.assertEqual(sorted(o["id"] for o in self.observed_files(factory)), sorted([CONTROL, REQUEST]))

        shutil.rmtree(self.attempts)
        self.set_plan(status="running")
        self.assertEqual(self.run_rows("works-factory", REQUEST).returncode, 1)
        self.log.unlink()
        done = self.run_rows("works-factory", REQUEST, extra=["--resume"])
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertNotIn("resume", self.verbs())

    def test_resume_skips_done_rows(self):
        for factory in ("works-factory", "works"):
            with self.subTest(factory=factory):
                shutil.rmtree(self.attempts, ignore_errors=True)
                self.assertRan(self.run_rows(factory, REQUEST))
                self.log.unlink()
                self.assertRan(self.run_rows(factory, REQUEST, extra=["--resume"]))
                self.assertEqual(self.calls(), [])
                self.assertFalse((self.attempts / f"{REQUEST}--2").exists())
                self.assertEqual(len(self.observed_files(factory)), 1)

    def test_old_works_commit_must_match_pack(self):
        other = self.tmp / "other-plugins"
        (other / "works" / "dev").mkdir(parents=True)
        git(other, "init", "-q", "-b", "main")
        (other / ".git" / "refs" / "heads" / "main").write_text("1" * 40 + "\n", encoding="utf-8")
        done = self.runner("run", "works", "--attempts", str(self.attempts), "--only", REQUEST,
                           WORKS_FACTORY_OLD_WORKS=str(other / "works"))
        self.assertEqual(done.returncode, 2, done.stderr)
        [line] = done.stderr.strip().splitlines()
        self.assertIn("1" * 40, line)
        self.assertIn(self.old_commit, line)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.attempts.exists())

    def test_old_works_must_be_committed_and_have_use_sh(self):
        copy = self.tmp / "copy-plugins"
        shutil.copytree(self.old, copy)
        (copy / "elsewhere.txt").write_text("outside works/\n", encoding="utf-8")
        self.assertRan(self.runner("run", "works", "--attempts", str(self.attempts), "--observed", str(self.observed),
                                   "--only", REQUEST, WORKS_FACTORY_OLD_WORKS=str(copy / "works")))
        self.log.unlink()
        changes = {"edited": lambda: (copy / "works" / "dev" / "archon.sh").write_text('ARCHON_VERSION="v9"\n', encoding="utf-8"),
                   "untracked": lambda: (copy / "works" / "dev" / "extra.sh").write_text("", encoding="utf-8")}
        for name, change in changes.items():
            with self.subTest(change=name):
                git(copy, "checkout", "-q", "--", ".")
                git(copy, "clean", "-qfd", "works")
                change()
                done = self.runner("run", "works", "--attempts", str(self.tmp / name), "--only", REQUEST,
                                   WORKS_FACTORY_OLD_WORKS=str(copy / "works"))
                self.assertEqual(done.returncode, 2, done.stderr)
                [line] = done.stderr.strip().splitlines()
                self.assertIn("commit していない", line)
                self.assertIn("dev/", line)
                self.assertFalse((self.tmp / name).exists())
        done = self.runner("run", "works", "--attempts", str(self.tmp / "root"), "--only", REQUEST,
                           WORKS_FACTORY_OLD_WORKS=str(self.old))
        self.assertEqual(done.returncode, 2, done.stderr)
        [line] = done.stderr.strip().splitlines()
        self.assertIn("dev/use.sh が無い", line)
        self.assertEqual(self.calls(), [])
        self.assertFalse((self.tmp / "root").exists())

    def test_old_works_resume_answers_stop_at_human_gate(self):
        self.set_plan(waits=[1])
        self.assertEqual(self.run_rows("works", REQUEST).returncode, 1)
        self.log.unlink()
        self.set_plan(resume_waits=[3, 0], respond_waits=[3, 5])
        self.assertRan(self.run_rows("works", REQUEST, extra=["--resume"]))
        rid = "b5c6d7e8-0000-old"
        self.assertEqual([c["args"][1:5] for c in self.calls("continue.sh")],
                         [["workflow", "resume", rid], ["workflow", "respond", rid, "stop"]])
        [respond] = [c for c in self.calls("continue.sh") if c["args"][2] == "respond"]
        self.assertIn("WORKS_USE_UNATTENDED=1", respond["args"][5])
        self.assertEqual(respond["env"]["WORKS_DEV_HOME"], str(self.attempts / f"{REQUEST}--1" / "home"))
        self.assertEqual(self.verbs("use.sh").count("wait"), 4)
        self.assertEqual([o["id"] for o in self.observed_files("works")], [REQUEST])

    def test_observed_shape_and_no_absolute_paths(self):
        rows = {r["id"]: r for r in corpus.load()["rows"]}
        for factory in ("works-factory", "works"):
            with self.subTest(factory=factory):
                done = self.run_rows(factory, CHANGE)
                self.assertRan(done)
                [path] = list((self.observed / factory).glob("*.json"))
                text = path.read_text(encoding="utf-8")
                observed = json.loads(text)
                self.assertEqual(json.loads(done.stdout), observed)
                self.assertEqual(path.name, f"{CHANGE}--{observed['run_id'][:8]}.json")
                self.assertEqual(set(observed), {*corpus.OBSERVED_FIELDS, "child_run_ids", "unread", "flag_evidence",
                                                 "units", "asks", "cost", "provenance"})
                self.assertEqual(corpus.score(rows[CHANGE], observed)["verdict"], "CAUGHT")
                self.assertIn("p0.local_checks", observed["flagged"])
                self.assertNotIn("p0.local_checks", observed["unread"])
                self.assertTrue(observed["flag_evidence"]["p0.local_checks"].startswith(
                    "parent/test-gate/base/" if factory == "works-factory" else "board/out/r1/"))
                self.assertEqual(set(observed["provenance"]), {"factory_commit", "archon", "claude_code", "run_inputs",
                                                               "fingerprint", "date"})
                self.assertEqual(observed["provenance"]["claude_code"], "9.9.9 (Claude Code)")
                self.assertEqual(set(observed["cost"]), {"usd", "seconds", "why_null"})
                for word in ("/Users/", "/home/", "/private/", str(self.tmp), *ITEMS, *ITEMS.values()):
                    self.assertNotIn(word, text)
        [new] = self.observed_files("works-factory")
        self.assertEqual((new["cost"]["usd"], new["cost"]["seconds"], new["cost"]["why_null"]), (3.25, 5400.0, ""))
        self.assertEqual(new["provenance"]["factory_commit"], git(self.repo, "rev-parse", "HEAD"))
        [old] = self.observed_files("works")
        self.assertEqual((old["cost"]["usd"], old["cost"]["seconds"]), (12.5, 7200.0))
        self.assertEqual(old["provenance"]["factory_commit"], self.old_commit)
        self.assertEqual(old["provenance"]["archon"], "v0.11.1")

    def test_unread_catcher_makes_row_inconclusive(self):
        row = next(r for r in corpus.load()["rows"] if r["id"] == CHANGE)
        observed = {"id": CHANGE, "factory": "works", "run_id": "r" * 12, "outcome": "fixed", "flagged": [],
                    "unread": [row["catcher"]]}
        (self.observed / "works").mkdir(parents=True)
        (self.observed / "works" / "one.json").write_text(json.dumps(observed), encoding="utf-8")
        done = self.runner("score", "works", "--observed", str(self.observed))
        self.assertRan(done)
        lines = [json.loads(line) for line in done.stdout.splitlines()]
        self.assertEqual(lines[0]["verdict"], "INCONCLUSIVE")
        self.assertIn(row["catcher"], lines[0]["detail"])
        self.assertEqual(lines[-1]["verdicts"]["INCONCLUSIVE"], 1)
        self.assertEqual(lines[-1]["missed_by"], {})
        self.assertEqual(corpus.score(row, observed)["verdict"], "ESCAPED")

    def score_lines(self, factory, **files) -> list[dict]:
        (self.observed / factory).mkdir(parents=True)
        for name, observed in files.items():
            (self.observed / factory / f"{name}.json").write_text(json.dumps(observed), encoding="utf-8")
        done = self.runner("score", factory, "--observed", str(self.observed))
        self.assertRan(done)
        return [json.loads(line) for line in done.stdout.splitlines()]

    def test_unread_gate_makes_quiet_control_inconclusive(self):
        row = next(r for r in corpus.load()["rows"] if r["id"] == CONTROL)
        quiet = {"id": CONTROL, "factory": "works", "run_id": "q" * 12, "outcome": "no_fix_needed", "flagged": [],
                 "unread": ["p1.hygiene"]}
        loud = quiet | {"run_id": "l" * 12, "flagged": ["r1.minimality"]}
        lines = self.score_lines("works", quiet=quiet, loud=loud)
        got = {line["file"]: line for line in lines[:-1]}
        self.assertEqual(got["quiet.json"]["verdict"], "INCONCLUSIVE")
        self.assertIn("p1.hygiene", got["quiet.json"]["detail"])
        self.assertEqual(got["loud.json"]["verdict"], "FALSE_ALARM")
        self.assertEqual(corpus.score(row, quiet)["verdict"], "CLEAN")

    def test_unread_gate_keeps_outcome_false_alarm_on_control(self):
        fixed = {"id": CONTROL, "factory": "works", "run_id": "f" * 12, "outcome": "fixed", "flagged": [],
                 "unread": ["p1.hygiene"]}
        [line, total] = self.score_lines("works", fixed=fixed)
        self.assertEqual(line["verdict"], "FALSE_ALARM", line)
        self.assertIn("fixed", line["detail"])
        self.assertEqual(total["verdicts"]["FALSE_ALARM"], 1)

    def test_unread_units_and_asks_keep_quiet_control_clean(self):
        quiet = {"id": CONTROL, "factory": "works", "run_id": "q" * 12, "outcome": "no_fix_needed", "flagged": [],
                 "unread": ["units", "asks"]}
        [line, _] = self.score_lines("works", quiet=quiet)
        self.assertEqual(line["verdict"], "CLEAN", line)

    def test_score_sums_missed_by_per_gate(self):
        row = next(r for r in corpus.load()["rows"] if r["id"] == REQUEST)
        base = {"id": REQUEST, "factory": "works", "outcome": "fixed", "unread": []}
        lines = self.score_lines("works", escaped=base | {"run_id": "e" * 12, "flagged": []},
                                 caught=base | {"run_id": "c" * 12, "flagged": [row["catcher"]]})
        self.assertEqual(sorted(line["verdict"] for line in lines[:-1]), ["CAUGHT", "ESCAPED"])
        self.assertEqual(lines[-1]["verdicts"], {"CAUGHT": 1, "ESCAPED": 1, "CLEAN": 0, "FALSE_ALARM": 0, "INCONCLUSIVE": 0})
        self.assertEqual(lines[-1]["missed_by"], {row["catcher"]: 1, **{a: 2 for a in row["also"]}})

    def compare_lines(self) -> list[dict]:
        done = self.runner("compare", "--observed", str(self.observed))
        self.assertRan(done)
        return [json.loads(line) for line in done.stdout.splitlines()]

    def test_compare_names_stale_and_one_sided_rows(self):
        self.assertRan(self.run_rows("works-factory", CHANGE, REQUEST))
        self.set_plan(outcome="needs_human")
        self.assertRan(self.run_rows("works", CHANGE))
        stale = self.observed_files("works")[0] | {"id": CONTROL, "provenance": {"fingerprint": "0" * 64}}
        (self.observed / "works" / "stale.json").write_text(json.dumps(stale), encoding="utf-8")
        older = {k: v for k, v in self.observed_files("works")[0].items() if k != "asks"} | {"id": CONTROL}
        (self.observed / "works" / "older.json").write_text(json.dumps(older), encoding="utf-8")
        lines = self.compare_lines()
        self.assertIn({"stale": "works/stale.json"}, lines)
        self.assertIn({"stale": "works/older.json"}, lines)
        [one] = [line for line in lines if "one_sided" in line]
        self.assertEqual((one["one_sided"], one["only"]), (REQUEST, "works-factory"))
        self.assertEqual(set(one["works-factory"][0]), {"verdict", "outcome", "units", "asks", "cost"})
        [both] = [line for line in lines if "compare" in line]
        self.assertEqual(both["compare"], CHANGE)
        self.assertIn("outcome", both["differs"])
        self.assertEqual(both["reason"], "")
        self.assertEqual(both["works"][0]["outcome"], "needs_human")
        self.assertEqual(both["works"][0]["cost"], {"usd": 12.5, "seconds": 7200.0})
        self.assertFalse([line for line in lines if CONTROL in json.dumps(line) and "stale" not in line])

    def test_compare_names_each_field_that_differs(self):
        self.set_plan(outcome="fixed", artifacts={"test-gate/base/baseline.json": '{"material": {"status": "found"}}',
                                                  "fix/fix/groups.json": "{}", "fix/fix/join.json": json.dumps({"units": [{"unit_id": "u1", "status": "fixed"}]})},
                      nodes=[{"node_id": "gate-final", "state": "completed"}])
        self.assertRan(self.run_rows("works-factory", CHANGE))
        self.set_plan(outcome="fixed", asks=["final-gate"],
                      board={"out/r1/p0.local_checks.json": '{"material": {"status": "found"}}',
                             "out/r1/p3.fix.json": json.dumps({"changes": [{"unit_key": "stats.py mean"}]})})
        self.assertRan(self.run_rows("works", CHANGE))
        [same] = [line for line in self.compare_lines() if "compare" in line]
        self.assertEqual(same["differs"], [])
        self.assertEqual(same["works"][0]["units"], {"count": 1, "names": ["stats.py mean"]})
        self.assertEqual(same["works-factory"][0]["asks"], {"count": 1, "gates": ["gate-final"]})

        [path] = (self.observed / "works").glob("*.json")
        observed = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps(observed | {"units": ["a", "b"], "asks": [], "unread": ["units"]}), encoding="utf-8")
        [differs] = [line for line in self.compare_lines() if "compare" in line]
        self.assertEqual(differs["differs"], ["units", "asks"])
        self.assertEqual(differs["reason"], "")

        path.write_text(json.dumps(observed | {"flagged": []}), encoding="utf-8")
        [verdicts] = [line for line in self.compare_lines() if "compare" in line]
        self.assertEqual(verdicts["differs"], ["verdict"])

    FIXED = {
        "works-factory": {"artifacts": {
            "test-gate/base/baseline.json": '{"material": {"status": "found"}}',
            "fix/fix/groups.json": "{}", "fix/refix-run/groups.json": "{}",
            "fix/fix/join.json": json.dumps({"units": [{"unit_id": "u1", "status": "fixed"}, {"unit_id": "u2", "status": "not_done"},
                                                       {"unit_id": "u3", "status": "given_up"}]}),
            "fix/fix/fix-units.json": json.dumps({"u2": {"status": "fixed", "reason": ""}, "u3": {"status": "given_up"}}),
            "fix/refix-run/join.json": json.dumps({"units": [{"unit_id": "u4", "status": "fixed"}, {"unit_id": "u1", "status": "fixed"}]})},
            "nodes": [{"node_id": "gate-start", "state": "skipped"}, {"node_id": "judge", "state": "completed"},
                      {"node_id": "gate-before-fix", "state": "completed"}, {"node_id": "gate-final", "state": "failed"}]},
        "works": {"asks": ["entering__launch", "final-gate"], "board": {
            "out/r1/p0.local_checks.json": '{"material": {"status": "found"}}',
            "out/r1/p3.fix.json": json.dumps({"changes": [{"unit_key": "k1"}, {"unit_key": "k2"}]}),
            "out/r10/p3.fix.json": json.dumps({"changes": [{"unit_key": "k4"}]}),
            "out/r2/p3.fix.json": json.dumps({"changes": [{"unit_key": "k1"}, {"unit_key": "k3"}]})}},
    }
    UNITS = {"works-factory": (["u1", "u2", "u4"], ["gate-before-fix", "gate-final"]),
             "works": (["k1", "k2", "k3", "k4"], ["entering__launch", "final-gate"])}
    BROKEN = {"works-factory": "parent/fix/fix/join.json", "works": "board/out/r2/p3.fix.json"}

    def test_run_writes_units_and_asks(self):
        for factory in ("works-factory", "works"):
            with self.subTest(factory=factory):
                self.set_plan(**self.FIXED[factory])
                self.assertRan(self.run_rows(factory, CHANGE))
                [observed] = self.observed_files(factory)
                self.assertEqual((observed["units"], observed["asks"]), self.UNITS[factory])
                self.assertFalse({"units", "asks"} & set(observed["unread"]))

    def test_unreadable_events_stop_the_row(self):
        for printed in ("not json", "[]"):
            with self.subTest(printed=printed):
                shutil.rmtree(self.attempts, ignore_errors=True)
                self.set_plan(events_unreadable=printed)
                done = self.run_rows("works-factory", REQUEST)
                self.assertEqual(done.returncode, 1, done.stderr)
                self.assertIn("run a1b2c3d4-0000-run の出来事の列を evidence/ に写せない", done.stderr)
                self.assertFalse(self.observed.exists())

    @staticmethod
    def resumed(stamp):
        """再開を 1 度またぐ run の行と出来事の列。stamp は各工場の記録の時刻の書き方"""
        row = {"started_at": stamp("01:59:50"), "completed_at": stamp("02:00:00")}
        events = [{"event_type": "workflow_started", "created_at": stamp("01:50:00")},
                  {"event_type": "workflow_started", "created_at": stamp("01:59:50")},
                  {"event_type": "workflow_completed", "created_at": stamp("02:00:00"), "data": {"cost_usd": 1.0}}]
        return row, events

    # works-factory は Archon の get --events（events[].created_at は ISO の Z）、今の works は SQLite の行の書き方
    SPANS = {"works-factory": (lambda t: f"2026-10-12T{t}.000Z",
                               lambda row, events: {"record/parent.json": {**row, "terminal_record": {}},
                                                    "record/parent-events.json": {"events": events}}),
             "works": (lambda t: f"2026-10-12 {t}",
                       lambda row, events: {"record/parent.json": {"run": row, "events": events}})}

    def test_seconds_span_from_the_first_event_across_resumes(self):
        """Archon は再開のたびに行の started_at を書き直すので、両工場とも時間は最初の出来事から completed_at までで測る"""
        for factory, (stamp, files) in self.SPANS.items():
            row, events = self.resumed(stamp)
            for given, seconds in ((events, 600.0), ([], None)):
                with self.subTest(factory=factory, events=len(given)), tempfile.TemporaryDirectory() as tmp:
                    ev = pathlib.Path(tmp)
                    (ev / "record").mkdir()
                    for name, doc in files(row, given).items():
                        (ev / name).write_text(json.dumps(doc), encoding="utf-8")
                    self.assertEqual(runner.FACTORY[factory].ended(ev)["seconds"], seconds)

    def reobserve(self, factory, *extra):
        return self.runner("reobserve", factory, "--attempts", str(self.attempts), "--observed", str(self.observed), *extra)

    def test_reobserve_reads_evidence_and_launches_nothing(self):
        for factory in ("works-factory", "works"):
            with self.subTest(factory=factory):
                self.set_plan(**self.FIXED[factory])
                self.assertRan(self.run_rows(factory, CHANGE, REQUEST))
                paths = sorted((self.observed / factory).glob("*.json"))
                for path in paths:
                    old = json.loads(path.read_text(encoding="utf-8"))
                    old = {k: v for k, v in old.items() if k not in ("units", "asks")}
                    old["provenance"] |= {"claude_code": "1.0.0 (Claude Code)", "date": "2026-01-01T00:00:00+00:00",
                                          "fingerprint": "0" * 64}
                    path.write_text(json.dumps(old), encoding="utf-8")
                self.log.unlink()
                self.set_plan()
                done = self.reobserve(factory, "--only", CHANGE)
                self.assertRan(done)
                self.assertEqual(self.calls(), [])
                self.assertEqual(sorted((self.observed / factory).glob("*.json")), paths)
                [new] = [o for o in self.observed_files(factory) if o["id"] == CHANGE]
                self.assertEqual((new["units"], new["asks"]), self.UNITS[factory])
                self.assertEqual(new["provenance"]["claude_code"], "1.0.0 (Claude Code)")
                self.assertEqual(new["provenance"]["date"], "2026-01-01T00:00:00+00:00")
                self.assertNotEqual(new["provenance"]["fingerprint"], "0" * 64)
                self.assertEqual(new["outcome"], "fixed")
                self.assertIn("p0.local_checks", new["flagged"])
                self.assertEqual(json.loads(done.stdout), new)
                [untouched] = [o for o in self.observed_files(factory) if o["id"] == REQUEST]
                self.assertNotIn("units", untouched)

    def test_reobserve_without_events_copy_leaves_seconds_null(self):
        """#422 より前の works-factory の試みは出来事の列の写しを持たない。時間は推し量らず null と訳を書く"""
        self.set_plan(**self.FIXED["works-factory"])
        self.assertRan(self.run_rows("works-factory", CHANGE))
        (self.attempts / f"{CHANGE}--1" / "evidence" / runner.EVENTS).unlink()
        self.assertRan(self.reobserve("works-factory"))
        [observed] = self.observed_files("works-factory")
        self.assertIsNone(observed["cost"]["seconds"])
        self.assertIn("seconds: run の最初の出来事と終わりの時刻が読めない", observed["cost"]["why_null"])

    def test_reobserve_names_unreadable_fields_in_unread(self):
        for factory in ("works-factory", "works"):
            with self.subTest(factory=factory):
                shutil.rmtree(self.attempts, ignore_errors=True)
                self.set_plan(**self.FIXED[factory])
                self.assertRan(self.run_rows(factory, CHANGE))
                evidence = self.attempts / f"{CHANGE}--1" / "evidence"
                (evidence / self.BROKEN[factory]).write_text("{", encoding="utf-8")
                record = json.loads((evidence / "record" / "parent.json").read_text(encoding="utf-8"))
                if factory == "works-factory":
                    record["terminal_record"].pop("nodes")
                else:
                    record.pop("events")
                (evidence / "record" / "parent.json").write_text(json.dumps(record), encoding="utf-8")
                self.assertRan(self.reobserve(factory))
                [observed] = self.observed_files(factory)
                self.assertEqual((observed["units"], observed["asks"]), (None, None))
                self.assertLessEqual({"units", "asks"}, set(observed["unread"]))
                self.assertIn(self.BROKEN[factory], observed["flag_evidence"]["units"])
                self.assertIn("record/parent.json", observed["flag_evidence"]["asks"])

    def test_fix_place_without_join_names_units_unread(self):
        artifacts = {k: v for k, v in self.FIXED["works-factory"]["artifacts"].items() if k != "fix/fix/join.json"}
        self.set_plan(**self.FIXED["works-factory"] | {"artifacts": artifacts})
        self.assertRan(self.run_rows("works-factory", CHANGE))
        [observed] = self.observed_files("works-factory")
        self.assertIsNone(observed["units"])
        self.assertIn("units", observed["unread"])
        self.assertIn("parent/fix/fix/join.json: 無い", observed["flag_evidence"]["units"])

    MISSING = {"works-factory": "parent", "works": "board"}

    def test_reobserve_names_missing_record_folder_in_unread(self):
        for factory in ("works-factory", "works"):
            with self.subTest(factory=factory):
                shutil.rmtree(self.attempts, ignore_errors=True)
                self.set_plan(**self.FIXED[factory])
                self.assertRan(self.run_rows(factory, CHANGE))
                shutil.rmtree(self.attempts / f"{CHANGE}--1" / "evidence" / self.MISSING[factory])
                self.assertRan(self.reobserve(factory))
                [observed] = self.observed_files(factory)
                self.assertIsNone(observed["units"])
                self.assertIn("units", observed["unread"])
                self.assertIn(self.MISSING[factory], observed["flag_evidence"]["units"])

    def test_reobserve_refuses_without_evidence_and_keeps_observed(self):
        for factory in ("works-factory", "works"):
            with self.subTest(factory=factory):
                shutil.rmtree(self.attempts, ignore_errors=True)
                shutil.rmtree(self.observed, ignore_errors=True)
                self.set_plan(**self.FIXED[factory])
                self.assertRan(self.run_rows(factory, CHANGE))
                [path] = (self.observed / factory).glob("*.json")
                before = path.read_bytes()
                shutil.rmtree(self.attempts / f"{CHANGE}--1" / "evidence")
                done = self.reobserve(factory)
                self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
                self.assertIn(CHANGE, done.stderr)
                self.assertEqual(path.read_bytes(), before)

    def test_reobserve_keeps_child_run_ids(self):
        self.set_plan(**self.FIXED["works-factory"], children=2)
        self.assertRan(self.run_rows("works-factory", CHANGE))
        [before] = self.observed_files("works-factory")
        self.assertEqual(len(before["child_run_ids"]), 2)
        self.assertRan(self.reobserve("works-factory"))
        [after] = self.observed_files("works-factory")
        self.assertEqual(after["child_run_ids"], before["child_run_ids"])

    def test_reobserve_needs_an_earlier_observed(self):
        self.assertRan(self.run_rows("works", REQUEST))
        shutil.rmtree(self.observed)
        self.log.unlink()
        done = self.reobserve("works")
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn(REQUEST, done.stderr)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.observed.exists())

    def test_works_factory_gates_are_the_main_graph_approvals(self):
        graph = yaml.safe_load((ROOT / "workflows" / "line" / "works-factory-line.yaml").read_text(encoding="utf-8"))
        approvals = [n["id"] for n in graph["nodes"] if "approval" in n]
        self.assertEqual(list(runner.WorksFactory.gates), approvals)

    def test_dry_run_launches_nothing(self):
        for factory in ("works-factory", "works"):
            with self.subTest(factory=factory):
                done = self.run_rows(factory, extra=["--dry-run"])
                self.assertRan(done)
                lines = [json.loads(line) for line in done.stdout.splitlines()]
                self.assertEqual([x["id"] for x in lines], [r["id"] for r in corpus.load()["rows"]])
                self.assertTrue(all(x["ok"] for x in lines), lines)
                for x in lines:
                    self.assertTrue(x.get("red") or x.get("witness") == "assert" or x.get("green"), x)
                for value in ITEMS.values():
                    self.assertNotIn(value, done.stdout + done.stderr)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.attempts.exists())
        self.assertFalse(self.observed.exists())
        self.assertFalse((pathlib.Path(git(self.repo, "rev-parse", "--absolute-git-dir")) / "works-factory-e2e" / "homes").exists())

    def test_attempts_inside_repository_refused(self):
        inside = self.repo / "attempts"
        done = self.runner("run", "works-factory", "--attempts", str(inside), "--only", REQUEST)
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertEqual(len(done.stderr.strip().splitlines()), 1)
        self.assertFalse(inside.exists())
        self.assertEqual(self.calls(), [])

    def test_second_runner_on_same_attempts_refused(self):
        self.attempts.mkdir()
        fd = os.open(self.attempts / ".lock", os.O_CREAT | os.O_RDWR)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        done = self.run_rows("works-factory", REQUEST)
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn("別のランナー", done.stderr)
        self.assertEqual(self.calls(), [])

    def test_works_factory_inputs_exist_in_main_graph(self):
        graph = yaml.safe_load((ROOT / "workflows" / "line" / "works-factory-line.yaml").read_text(encoding="utf-8"))
        self.assertEqual(graph["name"], "works-factory-line")
        self.assertTrue(graph.get("interactive"))
        self.assertRan(self.run_rows("works-factory", CHANGE))
        self.assertLessEqual(set(self.inputs()), set(graph["inputs"]))
        self.assertEqual([a for a in self.calls("works-factory")[0]["args"][:3]], ["workflow", "run", "works-factory-line"])

    def test_teardown_skips_old_works_homes(self):
        self.assertRan(self.run_rows("works", REQUEST))
        self.assertRan(self.run_rows("works-factory", CONTROL))
        self.log.unlink()
        done = subprocess.run([sys.executable, str(self.repo / "tests" / "e2e" / "make_target.py"), "teardown"],
                              env=self.env, cwd=self.tmp, capture_output=True, text=True, encoding="utf-8", timeout=300)
        self.assertEqual(done.returncode, 0, done.stderr)
        homes = {c["home"] for c in self.calls("works-factory")}
        self.assertEqual(homes, {str(self.attempts / f"{CONTROL}--1" / "home")})


if __name__ == "__main__":
    unittest.main()

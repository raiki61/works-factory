"""照らしの道具 tests/e2e/evidence.py の試験（collect と、4 種の照らしの判じ）。照らしの表 evidence.json と check の命令は段 1a の物で、
その試験はここに足す。collect の後ろの Archon は偽の殻で、家の fake-runs.json の run を workflow runs・get で答える。"""
import json
import pathlib
import subprocess
import sys
import unittest

from tests.bin import hermetic
from tests.e2e import evidence

E2E = pathlib.Path(__file__).resolve().parent

FAKE_SHELL = """#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
home = pathlib.Path(os.environ["WORKS_FACTORY_HOME"])
runs = json.loads((home / "fake-runs.json").read_text(encoding="utf-8"))
with open(home / "calls.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps({"args": args, "no_auth": os.environ.get("WORKS_FACTORY_NO_AUTH")}) + "\\n")
if args[1] == "runs":
    print(json.dumps({"runs": [{k: r[k] for k in ("id", "parent_run_id", "started_at")} for r in runs]}))
elif args[1] == "get":
    run = next(r for r in runs if r["id"] == args[2])
    print(json.dumps({"id": run["id"], "status": "completed", "terminal_record": {"artifacts": {"root": run["root"]}}}))
"""


class EvidenceCheckCase(unittest.TestCase):
    def setUp(self):
        self.ev = hermetic.tmpdir(self)

    def put(self, name, text):
        (self.ev / name).parent.mkdir(parents=True, exist_ok=True)
        (self.ev / name).write_text(text, encoding="utf-8")

    def test_each_check_kind_passes_and_fails(self):
        self.put("parent/a.json", json.dumps({"rows": [{"status": "clean"}, {"status": "found", "x": [1]}], "empty": []}))
        self.put("parent/b.md", "- green: false\n")
        self.put("parent/empty.txt", "")
        cases = [
            ({"check": "exists", "where": "parent/*.md"}, evidence.PASS),
            ({"check": "exists", "where": "parent/empty.txt"}, evidence.FAIL),
            ({"check": "exists", "where": "parent/nothing"}, evidence.MISSING),
            ({"check": "json-has", "where": "parent/a.json", "path": "rows.1.x"}, evidence.PASS),
            ({"check": "json-has", "where": "parent/a.json", "path": "empty"}, evidence.FAIL),
            ({"check": "json-has", "where": "parent/a.json", "path": "rows.5"}, evidence.FAIL),
            ({"check": "json-equals", "where": "parent/a.json", "path": "rows.*.status", "value": "found"}, evidence.PASS),
            ({"check": "json-equals", "where": "parent/a.json", "path": "rows.0.status", "value": "found"}, evidence.FAIL),
            ({"check": "text-contains", "where": "parent/b.md", "text": "green: false"}, evidence.PASS),
            ({"check": "text-contains", "where": "parent/b.md", "text": "green: true"}, evidence.FAIL),
        ]
        for rule, want in cases:
            with self.subTest(rule=rule):
                self.assertIsNone(evidence.rule_problem(rule))
                self.assertEqual(evidence.judge(self.ev, rule)[0], want)
        self.assertEqual(evidence.judge(self.ev, cases[6][0])[1], 'parent/a.json: rows.*.status = "found"')

    def test_unreadable_file_is_named(self):
        self.put("parent/bad.json", "{")
        self.put("parent/good.json", json.dumps({"x": 1}))
        state, detail = evidence.judge(self.ev, {"check": "json-has", "where": "parent/bad.json", "path": "x"})
        self.assertEqual(state, evidence.UNREADABLE)
        self.assertIn("parent/bad.json", detail)
        state, _ = evidence.judge(self.ev, {"check": "json-has", "where": "parent/*.json", "path": "x"})
        self.assertEqual(state, evidence.PASS)


class EvidenceCollectCase(unittest.TestCase):
    def test_collect_copies_parent_children_and_records(self):
        tmp = hermetic.tmpdir(self)
        attempt = tmp / "attempt"
        (attempt / "target").mkdir(parents=True)
        (attempt / "home").mkdir()
        shell = tmp / "shell.py"
        shell.write_text(FAKE_SHELL, encoding="utf-8")
        runs = []
        for rid, parent, at in (("p1", None, "1"), ("c2", "p1", "3"), ("c1", "p1", "2"), ("other", "x", "4")):
            root = tmp / "art" / rid
            (root / "sub").mkdir(parents=True)
            (root / "sub" / "out.json").write_text(json.dumps({"run": rid}), encoding="utf-8")
            runs.append({"id": rid, "parent_run_id": parent, "started_at": at, "root": str(root)})
        (attempt / "home" / "fake-runs.json").write_text(json.dumps(runs), encoding="utf-8")
        got = evidence.collect(attempt, "p1", shell)
        self.assertEqual(got, {"run": "p1", "children": ["c1", "c2"], "limits": []})
        ev = attempt / "evidence"
        for name, rid in (("parent", "p1"), ("child-1", "c1"), ("child-2", "c2")):
            self.assertEqual(json.loads((ev / name / "sub" / "out.json").read_text(encoding="utf-8")), {"run": rid})
            self.assertEqual(json.loads((ev / "record" / f"{name}.json").read_text(encoding="utf-8"))["id"], rid)
        calls = [json.loads(line) for line in (attempt / "home" / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertTrue(all(c["no_auth"] == "1" and c["args"][-2:] == ["--cwd", str(attempt / "target")] for c in calls))
        self.assertIn(["workflow", "get", "p1", "--json", "--verbose"], [c["args"][:5] for c in calls])

    def test_cli_names_its_usage(self):
        done = subprocess.run([sys.executable, str(E2E / "evidence.py"), "check"], capture_output=True, text=True,
                              encoding="utf-8", env=hermetic.child_env(), timeout=60)
        self.assertEqual(done.returncode, 2)
        self.assertIn("collect", done.stderr)


if __name__ == "__main__":
    unittest.main()

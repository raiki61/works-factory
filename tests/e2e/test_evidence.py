"""照らしの道具 tests/e2e/evidence.py の試験（collect・4 種の照らしの判じ・check）と、照らしの表 evidence.json の試験。
collect の後ろの Archon は偽の殻で、家の fake-runs.json の run を workflow runs・get で答える。

表の試験は、表を能力の棚卸し docs/plans/2026-10-13-capabilities/ と線の配線の文書 docs/plans/2026-10-13-line-wiring.md に
照らす。棚卸しの行は、区分の ID で始まる頭の箇条で「本物の run」の欄を持つ物（ほかの行を指すだけの参照の行と、穴の要約の再掲は
欄を持たない）。"""
import json
import pathlib
import re
import subprocess
import sys
import unittest

from tests.bin import hermetic, stepnames
from tests.e2e import evidence

E2E = pathlib.Path(__file__).resolve().parent
ROOT = E2E.parents[1]
INVENTORY = ROOT / "docs" / "plans" / "2026-10-13-capabilities"
INVENTORY_FILES = ("line.md", "judge.md", "plan.md", "fix.md", "tail.md")
WIRING = ROOT / "docs" / "plans" / "2026-10-13-line-wiring.md"
ROW_ID = r"(?:L-[EGWD]|[JPFTERM])\d+[a-z]?"
SCENARIO_ONLY = "筋書きでのみ"
# 照らしの where の run の記録 → その run の工程（親は線、子は fix の組ごとの子の run）
RECORDS = {"record/parent.json": "works-factory-line", "record/child-*.json": "works-factory-fix"}
OUTSIDE = "この文書の外"

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


def inventory() -> dict[str, str]:
    """棚卸しの行の ID → 「本物の run」の欄の字"""
    rows, current = {}, None
    for name in INVENTORY_FILES:
        for line in (INVENTORY / name).read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                current = None
            elif head := re.match(rf"- ({ROW_ID})[ 〔]", line):
                current = head.group(1)
            elif current and (real := re.match(r"\s+- 本物の run: (.*)", line)):
                rows.setdefault(current, real.group(1))
    return rows


def wiring() -> tuple[dict[str, set[str]], dict[str, str]]:
    """線の配線の文書の（部分の名 → 閉じる行）と（「この文書の外」の行 → それを名指した節の名）"""
    parts, outside = {}, {}
    part = section = None
    for line in WIRING.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            head = re.match(r"## 部分 (\S+) ", line)
            part = head.group(1) if head else None
            section = OUTSIDE if line.startswith(f"## {OUTSIDE}") else None
        elif section and line.startswith("### "):
            section = line[4:].strip()
        elif part and (closing := re.match(rf"- ({ROW_ID})〔", line)):
            parts.setdefault(part, set()).add(closing.group(1))
        elif section and section != OUTSIDE:
            for named in re.findall(rf"(?<![\w-])({ROW_ID})(?!\d)", line):
                outside.setdefault(named, section)
    return parts, outside


class EvidenceTableCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = evidence.read_table(evidence.TABLE)
        cls.by_id = {row["id"]: row for row in cls.rows}
        cls.inventory = inventory()

    def kind_of(self, kind):
        return {row["id"] for row in self.rows if row["kind"] == kind}

    def test_every_inventory_row_is_in_the_table(self):
        self.assertGreater(len(self.inventory), 1000)
        self.assertEqual(len(self.by_id), len(self.rows), "表に同じ ID の行が 2 つ在る")
        self.assertEqual(set(self.by_id) - set(self.inventory), set(), "棚卸しに無い行が表に在る")
        self.assertEqual(set(self.inventory) - set(self.by_id), set(), "棚卸しの行が表に無い")

    def test_every_row_has_a_known_kind_and_fields(self):
        for row in self.rows:
            with self.subTest(row=row.get("id")):
                self.assertIsNone(evidence.row_problem(row))
        for broken in ({"id": "J1", "kind": "seen"}, {"id": "J1", "kind": "maybe", "why": "x"},
                       {"id": "J1", "kind": "waits-part", "part": "Z"}, {"id": "J1", "kind": "handed-off", "why": "x"},
                       {"id": "J1", "kind": "scenario-only", "why": "x", "check": "exists", "where": "parent/a"},
                       {"id": "J1", "kind": "seen", "check": "exists", "where": "elsewhere/a"}):
            with self.subTest(broken=broken):
                self.assertIsNotNone(evidence.row_problem(broken))

    def test_scenario_only_rows_match_the_inventory(self):
        scenario_only, waiting = self.kind_of("scenario-only"), self.kind_of("waits-part")
        says = {i for i, real in self.inventory.items() if real.startswith(SCENARIO_ONLY)}
        never = {i for i, real in self.inventory.items() if SCENARIO_ONLY not in real}
        self.assertEqual(says - waiting - scenario_only, set(), "棚卸しが筋書きでのみと書く行が scenario-only でない")
        self.assertEqual(scenario_only & never, set(), "棚卸しが筋書きでのみと書かない行が scenario-only")

    def test_waits_part_rows_are_closing_rows_of_that_part(self):
        parts, _ = wiring()
        for part in evidence.PARTS:
            with self.subTest(part=part):
                waiting = {row["id"] for row in self.rows if row["kind"] == "waits-part" and row["part"] == part}
                self.assertTrue(parts.get(part))
                self.assertEqual(waiting, parts[part])

    def test_node_rules_name_node_ids_the_workflow_makes(self):
        """run の記録の節の id を照らす行（json-equals の nodes.*.nodeId と、引用符を含む text-contains）は、その run の工程の
        YAML から組んだ節の id のどれかに当たる。種類を問わない（seen でない行も、当たらなければ unexpected を言えない）"""
        names = {where: stepnames.step_names(flow) for where, flow in RECORDS.items()}
        for row in self.rows:
            if not row.get("where", "").startswith("record/"):
                continue
            with self.subTest(row=row["id"]):
                self.assertIn(row["where"], names)
                shown = [json.dumps({"nodeId": n}, ensure_ascii=False)[1:-1] for n in names[row["where"]]]
                if row["check"] == "json-equals" and row["path"] == "nodes.*.nodeId":
                    self.assertIn(row["value"], names[row["where"]])
                elif row["check"] == "text-contains" and '"' in row["text"]:
                    self.assertTrue(any(row["text"] in line for line in shown), row["text"])

    def test_backlog_and_handed_off_rows_name_their_place(self):
        _, outside = wiring()
        for row in self.rows:
            with self.subTest(row=row["id"]):
                if row["kind"] == "backlog":
                    self.assertEqual(row["why"], outside.get(row["id"]), "backlog の行は「この文書の外」のその節の名を持つ")
                if row["kind"] == "handed-off":
                    self.assertTrue(row["why"].strip() and row["to"].strip())


class EvidenceCheckCase(unittest.TestCase):
    def setUp(self):
        self.ev = hermetic.tmpdir(self) / "evidence"
        self.ev.mkdir()

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

    def table(self, rows):
        """rows を表のファイルに書き、ev を evidence/ に持つ試みのフォルダに run の記録を置く"""
        self.put("record/parent.json", json.dumps({"id": "p1"}))
        table = self.ev.parent / "table.json"
        table.write_text(json.dumps(rows), encoding="utf-8")
        return table

    def checked(self, rows):
        """rows の表で check を当てる。(行ごとの (id, 判じ, 根拠), 終了の値)"""
        got = evidence.check(self.ev.parent, self.table(rows))
        return [(r["id"], r["state"], r["detail"]) for r in got], evidence.exit_code(got)

    def test_absent_row_exits_one_and_unreadable_file_is_named(self):
        self.put("parent/bad.json", "{")
        self.put("parent/good.json", json.dumps({"x": 1}))
        state, detail = evidence.judge(self.ev, {"check": "json-has", "where": "parent/bad.json", "path": "x"})
        self.assertEqual(state, evidence.UNREADABLE)
        self.assertIn("parent/bad.json", detail)
        state, _ = evidence.judge(self.ev, {"check": "json-has", "where": "parent/*.json", "path": "x"})
        self.assertEqual(state, evidence.PASS)
        seen = {"id": "J1", "kind": "seen", "check": "json-has", "where": "parent/good.json", "path": "x"}
        rows, code = self.checked([seen])
        self.assertEqual((rows, code), ([("J1", "seen", "parent/good.json: x = 1")], 0))
        rows, code = self.checked([seen, {**seen, "id": "J2", "path": "y"}])
        self.assertEqual((rows[1][:2], code), (("J2", "absent"), 1))
        rows, code = self.checked([{**seen, "where": "parent/bad.json"}])
        self.assertEqual((rows[0][1], code), ("unreadable", 1))
        self.assertIn("parent/bad.json: 読めない（JSONDecodeError）", rows[0][2])

    def test_unexpected_seen_is_reported(self):
        self.put("parent/a.md", "見えた\n")
        rule = {"check": "text-contains", "where": "parent/a.md", "text": "見えた"}
        rows, code = self.checked([
            {"id": "J1", "kind": "waits-part", "part": "B1", **rule},
            {"id": "J2", "kind": "backlog", "why": "決めた物", **rule, "text": "見えない"},
            {"id": "J3", "kind": "scenario-only", "why": "筋書きでのみ"},
            {"id": "J4", "kind": "seed-cannot", "why": "種に宣言が無い"},
        ])
        self.assertEqual([r[:2] for r in rows], [("J1", "unexpected"), ("J2", "backlog"), ("J3", "scenario-only"),
                                                 ("J4", "seed-cannot")])
        self.assertEqual(code, 0)

    def test_counts_are_by_inventory_category(self):
        self.put("parent/a.md", "x\n")
        rows = [{"id": i, "kind": "seen", "check": "exists", "where": "parent/a.md"} for i in ("L-E01", "L-G02", "J3")]
        got = evidence.check(self.ev.parent, self.table(rows + [{"id": "M4", "kind": "scenario-only", "why": "x"}]))
        self.assertEqual(evidence.counts(got), {"L": {"seen": 2}, "J": {"seen": 1}, "M": {"scenario-only": 1}})

    def test_attempt_without_a_record_stops_by_name(self):
        attempt = self.ev.parent
        done = subprocess.run([sys.executable, str(E2E / "evidence.py"), "check", str(attempt)], capture_output=True,
                              text=True, encoding="utf-8", env=hermetic.child_env(), timeout=60)
        self.assertEqual(done.returncode, 1)
        self.assertIn(str(attempt / "evidence" / "record" / "parent.json"), done.stderr)
        self.assertIn("collect", done.stderr)
        self.assertNotIn("Traceback", done.stderr)


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
        self.assertIn("check", done.stderr)


if __name__ == "__main__":
    unittest.main()

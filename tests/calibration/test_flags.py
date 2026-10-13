"""flagged の表 tests/calibration/flags.json の試験。表の形・鍵の集合・never の訳・works-factory の名指しと、照らしを合成の evidence/ に
当てた結果を縛る。リポジトリに入った observed（運び役が本物の run の後に足す物）の形もここで縛る。"""
import importlib.util
import json
import os
import pathlib
import re
import shutil
import tempfile
import unittest
from unittest import mock

import yaml

from tests.calibration import corpus
from tests.calibration import run as runner
from tests.e2e import evidence

import judge_accept  # noqa: E402  lib/ は corpus が sys.path に足す

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
GRAPH = json.loads((ROOT / "docs" / "nodes.json").read_text(encoding="utf-8"))["graph"]
ABSENT = {gate for gate, row in GRAPH.items() if row["by"] == "absent"}
OLD_ABSENT = {gate for gate, row in GRAPH.items() if (row.get("reason") or "").startswith("今の works では absent")}
# 所見も赤も出さない関門。訳は表の never に書く。足す時は、その工場のその関門が出す物の欄を源で確かめてから
SILENT = {
    "works": {"p0.base", "p0.premises", "p1.worktree_before", "p3.delta_fix", "p3.delta_fix2", "p3.delta_owed",
              "p3.delta_owed2", "p3.fix_delta", "p3.fix_delta2", "p3.gates_cut", "p3.lane_merge", "p4.assemble",
              "p4.scalars", "report", "spec.approve", "spec.freeze", "spec.revise", "spec.write"},
    "works-factory": {"p0.base", "p0.premises", "p1.worktree_before", "p3.delta_fix", "p3.delta_fix2", "p3.delta_owed",
                      "p3.delta_owed2", "p3.fix_delta", "p3.fix_delta2", "p3.gates_cut", "p4.scalars", "report",
                      "report.human_items", "spec.approve", "spec.freeze", "spec.revise", "spec.write"},
}
WHERE_HEADS = {"works": ("board/", "record/"), "works-factory": ("parent/", "child-*/", "record/")}
OWNER_WORDS = ("/Users/", "/home/", "/private/", "KEYCHAIN")
JUDGE = ROOT / "workflows" / "judge" / "works-factory-judge.yaml"
REPLY = "reply."


def _table():
    return runner.load_flags()


def _nodes(doc):
    if isinstance(doc, dict):
        if isinstance(doc.get("id"), str):
            yield doc
        for value in doc.values():
            yield from _nodes(value)
    elif isinstance(doc, list):
        for value in doc:
            yield from _nodes(value)


def _reply_schemas(doc) -> dict:
    """material-*.json を書く受け付けは 2 つ: material_accept は material-<with.role>.json、pr_accept は judge_accept.MATERIAL_PR_FILE。
    どちらも with.reply に受けた書き手の節の返答を reply に写す。置き場の名 → 書き手の output_format"""
    nodes = {n["id"]: n for n in _nodes(doc)}
    files = {"material_accept": lambda given: f"material-{given['role']}.json",
             "pr_accept": lambda given: judge_accept.MATERIAL_PR_FILE}
    schemas = {}
    for node in nodes.values():
        if node.get("script") in files:
            given = node["with"]
            writer = re.fullmatch(r"\$([\w-]+)\.output", given["reply"])[1]
            schemas[f"parent/judge/{files[node['script']](given)}"] = nodes[writer]["output_format"]
    return schemas


def _schema_problem(schema: dict, path: str) -> str | None:
    """照らしの path（. 区切り、* と数は並びの要素）を JSON Schema の properties・items で辿れるか"""
    for part in path.split("."):
        if part == "*" or part.isdigit():
            if schema.get("type") != "array":
                return f"{part}: 並びでない"
            schema = schema.get("items") or {}
        else:
            properties = schema.get("properties") or {}
            if part not in properties:
                return f"{part}: output_format の properties に無い（在る欄: {sorted(properties)}）"
            schema = properties[part]
    return None


class FlagTableTest(unittest.TestCase):
    def test_tables_cover_every_acceptance_id(self):
        table = _table()
        self.assertEqual(sorted(table), sorted(corpus.FACTORIES))
        for factory in corpus.FACTORIES:
            with self.subTest(factory=factory):
                self.assertEqual(set(table[factory]), corpus._acceptance_ids())

    def test_never_only_for_absent_or_silent_gates(self):
        for factory, rows in _table().items():
            allowed = ABSENT | SILENT[factory] | (OLD_ABSENT if factory == "works" else set())
            for gate, entry in rows.items():
                with self.subTest(factory=factory, gate=gate):
                    if "never" in entry:
                        self.assertEqual(set(entry), {"never"})
                        self.assertTrue(entry["never"].strip())
                        self.assertIn(gate, allowed)
                    else:
                        self.assertEqual(set(entry), {"rules", "why"})
                        self.assertTrue(entry["rules"] and entry["why"].strip())

    def test_works_factory_why_names_nodes_of_nodes_json(self):
        for gate, entry in _table()[runner.WorksFactory.name].items():
            if "rules" in entry:
                with self.subTest(gate=gate):
                    named = [w for w in GRAPH[gate].get("where") or [] if re.search(rf"{re.escape(w)}(?![\w-])", entry["why"])]
                    self.assertTrue(named, entry["why"])

    def test_rule_shapes_are_the_four_checks(self):
        for factory, rows in _table().items():
            for gate, entry in rows.items():
                for rule in entry.get("rules", []):
                    with self.subTest(factory=factory, gate=gate, rule=rule):
                        self.assertIsNone(evidence.rule_problem(rule))
                        self.assertTrue(rule["where"].startswith(WHERE_HEADS[factory]), rule["where"])
        self.assertIsNotNone(evidence.rule_problem({"check": "exists", "where": "../x"}))
        self.assertIsNotNone(evidence.rule_problem({"check": "json-has", "where": "x"}))
        self.assertIsNotNone(evidence.rule_problem({"check": "regex", "where": "x"}))

    def test_works_factory_reply_paths_follow_the_writers_output_format(self):
        schemas = _reply_schemas(yaml.safe_load(JUDGE.read_text(encoding="utf-8")))
        replies = [(gate, rule) for gate, entry in _table()[runner.WorksFactory.name].items()
                   for rule in entry.get("rules", []) if rule.get("path", "").startswith(REPLY)]
        self.assertTrue(replies)
        for gate, rule in replies:
            with self.subTest(gate=gate, rule=rule):
                self.assertIn(rule["where"], sorted(schemas))
                self.assertIsNone(_schema_problem(schemas[rule["where"]], rule["path"].removeprefix(REPLY)))
        local = schemas["parent/judge/material-local-review.json"]
        self.assertIsNotNone(_schema_problem(local, "findings.*.item.0"))
        self.assertIsNotNone(_schema_problem(local, "findings.skill"))
        self.assertIsNotNone(_schema_problem(local, "verdict"))

    def test_flags_from_synthetic_evidence(self):
        table = {
            "a.found": {"rules": [{"check": "json-equals", "where": "parent/a.json", "path": "materials.*.status",
                                   "value": "found"}], "why": "-"},
            "a.clean": {"rules": [{"check": "json-equals", "where": "parent/a.json", "path": "materials.x.status",
                                   "value": "clean"}], "why": "-"},
            "b.exists": {"rules": [{"check": "exists", "where": "parent/b/*.md"}], "why": "-"},
            "b.absent": {"rules": [{"check": "exists", "where": "parent/none/*.md"}], "why": "-"},
            "c.text": {"rules": [{"check": "text-contains", "where": "parent/c.md", "text": "- green: false"}], "why": "-"},
            "d.has": {"rules": [{"check": "json-has", "where": "parent/a.json", "path": "findings.0"}], "why": "-"},
            "e.skipped": {"rules": [{"check": "json-has", "where": "parent/a.json", "path": "materials"}], "why": "-"},
            "f.broken": {"rules": [{"check": "json-has", "where": "parent/broken.json", "path": "x"}], "why": "-"},
            "g.missing": {"rules": [{"check": "json-has", "where": "parent/gone.json", "path": "x"},
                                    {"check": "exists", "where": "parent/gone.txt"}], "why": "-"},
            "h.never": {"never": "-"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            ev = pathlib.Path(tmp)
            (ev / "parent" / "b").mkdir(parents=True)
            (ev / "parent" / "a.json").write_text(json.dumps({"materials": {"x": {"status": "found"}}, "findings": []}),
                                                  encoding="utf-8")
            (ev / "parent" / "b" / "one.md").write_text("x", encoding="utf-8")
            (ev / "parent" / "c.md").write_text("- ok: true\n- green: false\n", encoding="utf-8")
            (ev / "parent" / "broken.json").write_text("{", encoding="utf-8")
            got = runner.flags_of(table, ev, {"e.skipped"})
        self.assertEqual(got["flagged"], ["a.found", "b.exists", "c.text"])
        self.assertEqual(got["unread"], ["f.broken", "g.missing"])
        self.assertEqual(got["flag_evidence"]["a.found"], 'parent/a.json: materials.*.status = "found"')
        self.assertEqual(got["flag_evidence"]["e.skipped"], "skipped")
        self.assertIn("読めない", got["flag_evidence"]["f.broken"])
        self.assertNotIn("a.clean", got["flag_evidence"])

    def test_real_table_reads_a_synthetic_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            ev = pathlib.Path(tmp)
            (ev / "parent" / "judge").mkdir(parents=True)
            (ev / "parent" / "judge" / "material-hygiene.json").write_text(
                json.dumps({"materials": {"hygiene": {"status": "found"}}}), encoding="utf-8")
            (ev / "parent" / "judge" / "material-provenance.json").write_text(
                json.dumps({"materials": {"provenance": {"status": "clean"}}}), encoding="utf-8")
            (ev / "record").mkdir()
            (ev / "record" / "parent.json").write_text(json.dumps({"terminal_record": {"nodes": [
                {"node_id": "eyes__r1-minimality", "state": "skipped"},
                {"node_id": "eyes__r1-minimality-verdict", "state": "skipped"}]}}), encoding="utf-8")
            got = runner.flags_of(_table()[runner.WorksFactory.name], ev, runner.WorksFactory.skipped(ev))
        self.assertEqual(got["flagged"], ["p1.hygiene"])
        self.assertEqual(got["flag_evidence"]["r1.minimality"], "skipped")
        self.assertNotIn("p1.provenance", got["unread"])
        self.assertIn("p1.gate_efficacy", got["unread"])

    def test_works_factory_local_review_needs_items_not_lens_rows(self):
        """局所レビューはレンズ 1 本につき findings の行を必ず返すので、行だけ（items が空）では立たず、items に中身がある時だけ立つ"""
        table = _table()[runner.WorksFactory.name]
        rows = [{"skill": "code-review", "items": [], "invoked": True, "failed": "起こしたが所見なし"},
                {"skill": "simplify", "items": [], "invoked": True, "failed": "起こしたが所見なし"}]
        for items, flagged in (([], []), ([{"where": "a.py:1", "text": "境界で落ちる"}], ["p1.local_review"])):
            with self.subTest(items=items), tempfile.TemporaryDirectory() as tmp:
                ev = pathlib.Path(tmp)
                (ev / "parent" / "judge").mkdir(parents=True)
                reply = {"findings": [rows[0], {**rows[1], "items": items}]}
                (ev / "parent" / "judge" / "material-local-review.json").write_text(json.dumps(
                    {"materials": {"local_review": {"status": "clean"}}, "reply": reply}), encoding="utf-8")
                got = runner.flags_of({"p1.local_review": table["p1.local_review"]}, ev, set())
                self.assertEqual(got["flagged"], flagged)

    def test_hidden_scope_counts_surfaced_alike_in_both_factories(self):
        """仕込みに当たらない suggest（surfaced）だけの R4 の返りは、どちらの工場でも返りを読んだうえで旗を立てない。
        policy_conflicts に中身があれば両工場とも立つ（返りを読まずに flagged が空になったのでないことの対照）"""
        quiet = {"status": "pass", "reason": "仕込みの範囲の外の所見だけ", "capability_inventory": {"fired": True, "lost": []},
                 "policy_conflicts": [], "surfaced": [{"where": "b.py:3", "text": "別の所見"}], "seen": [], "unseen": []}
        places = {runner.OldWorks.name: "board/out/r1/r4.hidden_scope.json",
                  runner.WorksFactory.name: "parent/eyes/r4.json"}
        for factory, where in places.items():
            for reply, flagged in ((quiet, []), ({**quiet, "policy_conflicts": ["決めに反する"]}, ["r4.hidden_scope"])):
                with self.subTest(factory=factory, flagged=flagged), tempfile.TemporaryDirectory() as tmp:
                    ev = pathlib.Path(tmp)
                    (ev / where).parent.mkdir(parents=True)
                    (ev / where).write_text(json.dumps(reply), encoding="utf-8")
                    got = runner.flags_of({"r4.hidden_scope": _table()[factory]["r4.hidden_scope"]}, ev, set())
                    self.assertEqual((got["flagged"], got["unread"]), (flagged, []))

    def test_test_gate_flags_read_the_evidence_of_a_fallen_result(self):
        """返す節 test-gate/result が落ちた時に今書く evidence.md で、p0.local_checks・p4.ci の旗が立つ"""
        spec = importlib.util.spec_from_file_location("test_gate_result", ROOT / "workflows" / "test-gate" / "scripts" / "result.py")
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        table = _table()[runner.WorksFactory.name]
        for gate, mode in (("p0.local_checks", "base"), ("p4.ci", "final")):
            with self.subTest(gate=gate), tempfile.TemporaryDirectory() as tmp:
                ev = pathlib.Path(tmp)
                with mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(ev / "parent")}):
                    result.failed(mode, RuntimeError("x"))
                self.assertEqual(runner.flags_of({gate: table[gate]}, ev, set())["flagged"], [gate])

    def test_old_works_skips_come_from_the_board_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            ev = pathlib.Path(tmp)
            (ev / "board").mkdir()
            (ev / "board" / "state.json").write_text(json.dumps({"rounds": [{"skipped": {"r1.minimality": "軽量"}}]}),
                                                     encoding="utf-8")
            self.assertEqual(runner.OldWorks.skipped(ev), {"r1.minimality"})

    def test_fingerprint_covers_corpus_seed_and_own_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus_path = pathlib.Path(tmp) / "corpus.json"
            shutil.copy(corpus.CORPUS, corpus_path)
            shutil.copytree(HERE / "seed", pathlib.Path(tmp) / "seed", ignore=corpus.COPY_IGNORE)
            table = _table()
            first = {f: runner.fingerprint(f, corpus_path, table) for f in corpus.FACTORIES}
            self.assertEqual(first, {f: runner.fingerprint(f, corpus_path, table) for f in corpus.FACTORIES})
            self.assertNotEqual(first["works"], first["works-factory"])

            other = json.loads(json.dumps(table))
            other["works-factory"]["report"] = {"never": "changed"}
            self.assertEqual(runner.fingerprint("works", corpus_path, other), first["works"])
            self.assertNotEqual(runner.fingerprint("works-factory", corpus_path, other), first["works-factory"])
            other["works"]["report"] = {"never": "changed"}
            self.assertNotEqual(runner.fingerprint("works", corpus_path, other), first["works"])

            stats = pathlib.Path(tmp) / "seed" / "stats.py"
            stats.write_bytes(stats.read_bytes() + b"\n")
            self.assertNotEqual(runner.fingerprint("works", corpus_path, table), first["works"])

    def test_dispatch_covers_every_factory(self):
        self.assertEqual(sorted(runner.FACTORY), sorted(corpus.FACTORIES))

    def test_stored_observed_shape(self):
        rows = {r["id"] for r in corpus.load()["rows"]}
        for path in sorted((HERE / "observed").rglob("*")):
            if not path.is_file():
                continue
            with self.subTest(path=path.relative_to(HERE).as_posix()):
                text = path.read_text(encoding="utf-8")
                observed = json.loads(text)
                self.assertEqual(path.suffix, ".json")
                self.assertEqual(path.parent.parent, HERE / "observed")
                self.assertEqual(observed["factory"], path.parent.name)
                self.assertIn(observed["id"], rows)
                self.assertEqual(path.name, f"{observed['id']}--{observed['run_id'][:8]}.json")
                self.assertLessEqual({*corpus.OBSERVED_FIELDS, "child_run_ids", "unread", "flag_evidence", "units", "asks",
                                      "cost", "provenance"}, set(observed))
                for word in OWNER_WORDS:
                    self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main()

"""報告のブロック（workflows/report/）の試験。

- YAML の形: PyYAML で読み、Archon を起こさない（返す節の約束の欄・入力・役の節の鍵）
- 部品と script: scripts/typed.py を一時の一覧で回し、facts.py・report_accept.py・collect.py を子のプロセスで走らせる
  （一時の ARTIFACTS_DIR と環境変数。Archon を起こさない）
- 筋書き: tests/archon.py の使い捨ての木で fixtures/ を archon workflow test で回す。Archon の源か bun が無ければ名前つきで見送る
"""
import ast
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests import archon

ROOT = pathlib.Path(__file__).resolve().parents[2]
BLOCK = ROOT / "workflows" / "report"
SCRIPTS = BLOCK / "scripts"
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
if str(LIB / "graphloops") not in sys.path:
    sys.path.append(str(LIB / "graphloops"))

import outcome  # noqa: E402
import report  # noqa: E402
import report_roles  # noqa: E402
import runreport  # noqa: E402
from engine.schema import validate_schema  # noqa: E402

WORKFLOW = yaml.safe_load((BLOCK / "works-factory-report.yaml").read_text(encoding="utf-8"))
NODES = {n["id"]: n for n in WORKFLOW["nodes"]}
BODY = {n["id"]: n for n in NODES["write-loop"]["loop_group"]["nodes"]}
INPUTS = ("start", "test-gate-base", "judge", "rejudge", "plan", "plan-review", "replan", "replan-review", "fix", "test-gate-final",
          "eyes", "merge-seal", "merge-apply", "gate-start", "gate-before-fix", "gate-replan", "gate-final")
RETURN_FIELDS = {"outcome", "stop_reason", "report", "report_ai", "next_request", "prior_failures", "ok"}
TOP_KEYS_DROPPED_ON_INCLUDE = ("interactive", "worktree", "container", "evidence_policy", "mutates_checkout")
SANDBOX = {"enabled": True, "allowUnsandboxedCommands": False}
RUN = "run-test"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(f"report_block_{name}", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


def env_reads(script: str) -> dict:
    """script の頭の、入力の名 → 読む環境変数の名（RETURNS・GATES の dict と START の os.environ.get の字）"""
    reads = {}
    for node in ast.parse((SCRIPTS / f"{script}.py").read_text(encoding="utf-8")).body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
            continue
        name, value = node.targets[0].id, node.value
        pairs = (zip(value.keys, value.values) if isinstance(value, ast.Dict) and name in ("RETURNS", "GATES")
                 else [(ast.Constant("start"), value)] if name == "START" else [])
        for key, call in pairs:
            reads[key.value] = call.args[0].value
    return reads


typed = load_script("typed")


class ShapeCase(unittest.TestCase):
    def test_name_and_returns(self):
        self.assertEqual(WORKFLOW["name"], "works-factory-report")
        self.assertEqual(WORKFLOW["returns"], "report")
        self.assertEqual(WORKFLOW["outcome_field"], "ok")

    def test_return_fields_are_the_contract(self):
        schema = NODES["report"]["output_format"]
        self.assertEqual(set(schema["properties"]), RETURN_FIELDS)
        self.assertEqual(set(schema["required"]), RETURN_FIELDS)
        self.assertIs(schema["additionalProperties"], False)
        self.assertEqual(tuple(schema["properties"]["outcome"]["enum"]), report.OUTCOMES)
        self.assertEqual(schema["properties"][WORKFLOW["outcome_field"]]["type"], "boolean")

    def test_inputs_are_the_contract(self):
        self.assertEqual(tuple(WORKFLOW["inputs"]), INPUTS)
        self.assertTrue(all(v == {"default": ""} for v in WORKFLOW["inputs"].values()))

    def test_facts_reads_every_input_by_its_own_name(self):
        """facts の読む入力が YAML の inputs と同じで、どれも自分の名の環境変数から読む。outcome の関所の並びは inputs の gate-*"""
        reads = env_reads("facts")
        self.assertEqual(reads, {name: f"INPUTS_{name.upper().replace('-', '_')}" for name in WORKFLOW["inputs"]})
        self.assertEqual(outcome.GATES, tuple(name for name in WORKFLOW["inputs"] if name.startswith("gate-")))

    def test_no_top_keys_dropped_on_include(self):
        for key in TOP_KEYS_DROPPED_ON_INCLUDE:
            self.assertNotIn(key, WORKFLOW)

    def test_every_node_leaves_the_checkout_alone(self):
        for nid, node in {**NODES, **BODY}.items():
            if "loop_group" in node:
                continue
            with self.subTest(nid):
                self.assertIs(node.get("mutates_checkout"), False)

    def test_roles(self):
        write, cold = BODY["write"], BODY["cold"]
        self.assertEqual(write["allowed_tools"], ["Read", "Grep", "Glob", "WebSearch", "WebFetch"])
        self.assertEqual(cold["allowed_tools"], [])
        self.assertEqual(cold["context"], "fresh")
        for node in (write, cold):
            self.assertEqual(node["settingSources"], ["user"])
            self.assertEqual(node["sandbox"], SANDBOX)
            self.assertEqual((node["model"], node["effort"]), ("sonnet", "medium"))
        self.assertEqual(write["output_format"], {k: v for k, v in report_roles.TEXT_SCHEMA.items()})
        self.assertEqual(cold["output_format"], runreport.COLD_SCHEMA)

    def test_return_node_runs_whatever_came_before(self):
        self.assertEqual(NODES["report"]["trigger_rule"], "all_done")
        self.assertEqual(NODES["report"]["depends_on"], ["facts", "write-loop"])

    def test_loop_gives_up_with_the_roles_count(self):
        self.assertEqual(NODES["write-loop"]["loop_group"]["max_iterations"], report_roles.GIVE_UP_AFTER)
        self.assertIs(NODES["write-loop"]["loop_group"]["fresh_context"], False)


class TypedCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)

    def entry(self, node, path, body, loop=None, run=RUN):
        (self.dir / path).parent.mkdir(parents=True, exist_ok=True)
        (self.dir / path).write_text(json.dumps(body), encoding="utf-8")
        row = {"nodeId": node, "outputType": "x", "path": path, "runId": run, "producedAt": "2026-10-12T00:00:00.000Z", "size": 1}
        if loop:
            row["loopGroupPath"] = [{"groupId": g, "iteration": i} for g, i in loop]
        return row

    def listing(self, by_type, errors=(), run=RUN):
        path = self.dir / "listing.json"
        path.write_text(json.dumps({"runId": run, "artifactsByType": by_type, "errors": list(errors)}), encoding="utf-8")
        return str(path)

    def read(self, listing, execution=""):
        return typed.listing(listing, str(self.dir), RUN, execution)

    def test_groups_by_include_and_loop_keep_rounds_and_drop_others(self):
        rows = [self.entry("fix__tdd", "nodes/a.md", [{"group_id": "g1"}], loop=[("fix__loop", 1)]),
                self.entry("fix__tdd", "nodes/b.md", [{"group_id": "g1"}], loop=[("fix__loop", 2)]),
                self.entry("refix__tdd", "nodes/c.md", [{"group_id": "g2"}]),
                self.entry("fix__tdd", "nodes/d.md", [], run="other-run"),
                self.entry("report__x", "nodes/e.md", {})]
        got = self.read(self.listing({"tdd-unit": rows}), json.dumps({"path": "report__facts"}))
        units = got["by_type"]["tdd-unit"]
        self.assertEqual([(u["include"], u["loop"]) for u in units],
                         [("fix", [("fix__loop", 1)]), ("fix", [("fix__loop", 2)]), ("refix", [])])
        self.assertEqual(units[0]["body"], [{"group_id": "g1"}])
        self.assertEqual(got["warnings"], [])

    def test_errors_each_become_a_warning(self):
        errors = [{"path": "nodes/x.meta.json", "kind": "invalid_metadata"}, {"path": "nodes", "kind": "unreadable_directory", "code": "EACCES"}]
        got = self.read(self.listing({}, errors))
        self.assertEqual(len(got["warnings"]), 2)
        self.assertIn("invalid_metadata", got["warnings"][0])
        self.assertIn("EACCES", got["warnings"][1])

    def test_named_limits_without_raising(self):
        cases = {"": "TYPED_ARTIFACTS_FILE が空", str(self.dir / "none.json"): "読めない"}
        bad = self.dir / "bad.json"
        bad.write_text("{壊れた", encoding="utf-8")
        cases[str(bad)] = "読めない"
        cases[self.listing("配列でない")] = "artifactsByType がオブジェクトでない"
        cases[self.listing({"tdd-unit": {"a": 1}})] = "配列でない"
        for listing, word in cases.items():
            with self.subTest(listing=listing):
                got = self.read(listing)
                self.assertEqual(len(got["warnings"]), 1, got)
                self.assertIn(word, got["warnings"][0])

    def test_unreadable_content_is_named(self):
        row = self.entry("eyes__r1", "nodes/r1.md", {})
        (self.dir / "nodes/r1.md").write_text("JSON でない", encoding="utf-8")
        got = self.read(self.listing({"eye-verdict": [row]}))
        self.assertIsNone(got["by_type"]["eye-verdict"][0]["body"])
        self.assertIn("nodes/r1.md", got["warnings"][0])


class Run(unittest.TestCase):
    """script を子のプロセスで走らせる（一時の run の置き場と、Archon が渡すのと同じ名の環境変数）"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)
        self.artifacts = self.dir / "artifacts"
        self.artifacts.mkdir()

    def run_script(self, name: str, **env) -> tuple[int, dict]:
        base = {k: v for k, v in os.environ.items() if not k.startswith("INPUTS_")}
        base.update({"ARTIFACTS_DIR": str(self.artifacts), "WORKFLOW_ID": RUN, "TYPED_ARTIFACTS_FILE": "", "LOG_DIR": "",
                     "WORKS_FACTORY_ROOT": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"})
        base.update(env)
        done = subprocess.run([sys.executable, str(SCRIPTS / f"{name}.py")], env=base, capture_output=True, text=True,
                              encoding="utf-8")
        lines = [line for line in done.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, f"JSON 1 つを出す: {done.stdout}{done.stderr}")
        return done.returncode, json.loads(lines[0])

    def pointer(self, rel: str, doc) -> str:
        path = self.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return json.dumps({"type": "archon_artifact", "run_id": RUN, "path": rel})


class FactsCase(Run):
    def test_empty_inputs_are_record_invalid_and_exit_zero(self):
        code, out = self.run_script("facts")
        self.assertEqual(code, 0)
        self.assertEqual(out["outcome"], "record_invalid")
        self.assertIs(out["ai_go"], False)
        text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
        self.assertIn("始めの記録（入力 start）が届いていない", text)
        self.assertIn("TYPED_ARTIFACTS_FILE が空", text)
        self.assertIn("LOG_DIR", text)

    def test_broken_inputs_and_missing_pointer_do_not_fall(self):
        code, out = self.run_script("facts", INPUTS_START=json.dumps({"type": "archon_artifact", "run_id": RUN, "path": "start/none.json"}),
                                    INPUTS_JUDGE="{壊れた", INPUTS_PLAN="[1, 2]", INPUTS_FIX="null", INPUTS_GATE_FINAL="",
                                    WORKFLOW_ID=RUN, LOG_DIR=str(self.dir))
        self.assertEqual(code, 0)
        self.assertEqual(out["outcome"], "record_invalid")
        text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
        self.assertIn("入力 judge が JSON でない", text)
        self.assertIn("入力 plan が JSON のオブジェクトでない", text)
        self.assertIn("始めの記録を開けない", text)
        self.assertIn(f"run の記録 {self.dir / RUN}.jsonl が読めない", text)

    def test_unexpected_error_still_returns(self):
        """思わぬ誤り（ここでは run の置き場がファイル）でも 0 で終わり、record_invalid と誤りの 1 行を返す"""
        blocker = self.dir / "file"
        blocker.write_text("", encoding="utf-8")
        code, out = self.run_script("facts", ARTIFACTS_DIR=str(blocker))
        self.assertEqual(code, 0)
        self.assertEqual(out["outcome"], "record_invalid")
        self.assertTrue(out["stop_reason"].startswith("report:報告の事実を組めなかった"))

    def test_request_stop_with_dry_run_environment(self):
        start = self.pointer("start/start.json", {"run_id": RUN})
        code, out = self.run_script("facts", INPUTS_START=start, INPUTS_GATE_FINAL='{"decision":"stop","text":"request: 止め札"}',
                                    WORKFLOW_ID="dry-run")
        self.assertEqual(code, 0)
        self.assertEqual((out["outcome"], out["stop_reason"], out["ok"]), ("stopped_by_request", "gate-final:stop", False))

    def test_unknown_answer_word_is_record_invalid_with_its_reason(self):
        start = self.pointer("start/start.json", {"run_id": RUN})
        code, out = self.run_script("facts", INPUTS_START=start, INPUTS_GATE_FINAL='{"decision":"maybe","text":""}')
        self.assertEqual(code, 0)
        self.assertEqual((out["outcome"], out["stop_reason"], out["ok"]), ("record_invalid", "report:record-invalid", False))
        text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
        self.assertIn("結果を名乗れない訳: 関所 gate-final の知らない答えの語 'maybe'", text)

    def test_unreadable_or_missing_conflicts_are_record_invalid(self):
        """人に回した申し出が読めない run は結果を名乗らない（読めなければ人に聞いた申し出が無いと数えて fixed に落ちる）"""
        start = self.pointer("start/start.json", {"run_id": RUN})
        broken = self.pointer("fix/conflicts.json", {})
        (self.artifacts / "fix/conflicts.json").write_text("{not json", encoding="utf-8")
        missing = json.dumps({"type": "archon_artifact", "run_id": RUN, "path": "fix/none.json"})
        for name, conflicts, word in (("JSON でない", broken, "申し出と裁定のファイル"), ("先が無い", missing, "指し札の先")):
            with self.subTest(name):
                fix = json.dumps({"done": True, "units": [], "conflicts": json.loads(conflicts)})
                code, out = self.run_script("facts", INPUTS_START=start, INPUTS_FIX=fix)
                self.assertEqual(code, 0)
                self.assertEqual((out["outcome"], out["stop_reason"]), ("record_invalid", "report:record-invalid"))
                text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
                self.assertIn(f"結果を名乗れない訳: {word}", text)

    def test_returns_with_pointers_reach_the_report(self):
        judgment = self.pointer("judge/judgment.json", {})
        judge = json.dumps({"ready": True, "stop_reason": "", "units": [{"id": "u1"}], "judgment": json.loads(judgment)})
        code, out = self.run_script("facts", INPUTS_START=self.pointer("start/start.json", {"run_id": RUN}), INPUTS_JUDGE=judge)
        self.assertEqual(code, 0)
        self.assertEqual(out["outcome"], "interrupted", "計画の返りが無い")
        text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
        self.assertIn(str(self.artifacts / "judge" / "judgment.json"), text)


class AcceptScriptCase(Run):
    REPLY = json.dumps({"text": "直した。\n\n## 1. 人が決めること\n\n無い", "terms": []}, ensure_ascii=False)
    REDESIGN = json.dumps({"verdict": "redesign-needed", "stops": ["2 行目"], "guessed": [], "decidable": False}, ensure_ascii=False)
    PASS = json.dumps({"verdict": "pass", "stops": [], "guessed": [], "decidable": True})

    def accept(self, reply, cold):
        code, out = self.run_script("report_accept", INPUTS_REPLY=reply, INPUTS_COLD=cold)
        self.assertEqual(code, 0)
        return out

    def test_cold_redesign_three_times(self):
        self.assertIs(self.accept(self.REPLY, self.REDESIGN)["done"], False)
        second = self.accept(self.REPLY, self.REDESIGN)
        self.assertIs(second["done"], False)
        self.assertIn("2 行目", pathlib.Path(second["reason_file"]).read_text(encoding="utf-8"))
        third = self.accept(self.REPLY, self.REDESIGN)
        self.assertIs(third["done"], True)
        ai = json.loads((self.artifacts / "report" / runreport.AI_FILE).read_text(encoding="utf-8"))
        self.assertTrue(ai["accepted"])
        self.assertTrue(ai["not_passed"])

    def test_cells_and_terms_rejected_first_time(self):
        cell = json.dumps({"text": "| 項目 |\n|---|\n| 説明の文である。 |"}, ensure_ascii=False)
        self.assertEqual(self.accept(cell, self.PASS)["kind"], "format")
        terms = json.dumps({"text": "x", "terms": [{"term": "a"}]})
        self.assertEqual(self.accept(terms, self.PASS)["kind"], "answer")


class CollectScriptCase(Run):
    SCHEMA = NODES["report"]["output_format"]

    def facts(self) -> dict:
        code, out = self.run_script("facts", INPUTS_START=self.pointer("start/start.json", {"run_id": RUN}),
                                    INPUTS_GATE_FINAL='{"decision":"stop","text":"止める"}')
        self.assertEqual(code, 0)
        return out

    def collect(self, facts: str, **env) -> dict:
        code, out = self.run_script("collect", INPUTS_FACTS=facts, **env)
        self.assertEqual(code, 0)
        self.assertEqual(validate_schema(out, self.SCHEMA), [], out)
        return out

    def test_without_ai_file_returns_machine_report(self):
        """書き手の輪が落ちた・飛ばされた置き場（report/ai.json が無い）でも機械の報告を返す"""
        facts = self.facts()
        out = self.collect(json.dumps(facts))
        self.assertEqual((out["outcome"], out["ok"]), ("stopped_by_human", False))
        self.assertIsNone(out["report_ai"])
        self.assertEqual(out["report"], facts["report"])

    def test_with_ai_file_returns_ai_report(self):
        facts = self.facts()
        runreport.accept(AcceptScriptCase.REPLY, AcceptScriptCase.PASS, out_dir=self.artifacts / "report")
        out = self.collect(json.dumps(facts))
        text = (self.artifacts / out["report_ai"]["path"]).read_text(encoding="utf-8")
        self.assertTrue(text.startswith(f"works-factory report / run {RUN}"))
        self.assertIn(report_roles.MACHINE_HEADING, text)

    def test_ok_is_passed_through_from_facts(self):
        facts = self.facts()
        for ok in (True, False):
            with self.subTest(ok=ok):
                self.assertIs(self.collect(json.dumps({**facts, "ok": ok}))["ok"], ok)

    def test_broken_inputs_are_record_invalid(self):
        good = self.facts()
        cases = {"空": "", "JSON でない": "{壊れた", "欄が欠けた": json.dumps({"report": good["report"]}),
                 "指し札の先が無い": json.dumps({**good, "report": {"type": "archon_artifact", "run_id": RUN, "path": "report/none.md"}})}
        for name, facts in cases.items():
            with self.subTest(name):
                out = self.collect(facts)
                self.assertEqual((out["outcome"], out["ok"]), ("record_invalid", False))
                self.assertTrue(out["stop_reason"].startswith("report:報告を組めなかった（"))

    def test_unwritable_place_is_record_invalid(self):
        good = self.facts()
        blocker = self.dir / "file"
        blocker.write_text("", encoding="utf-8")
        out = self.collect(json.dumps({**good, "report": None}), ARTIFACTS_DIR=str(blocker))
        self.assertEqual(out["outcome"], "record_invalid")


class FixtureCase(unittest.TestCase):
    """筋書きを止めた Archon の workflow test で回し、同じ木の validate に誤りも警告も無いことを見る"""

    def test_fixtures_pass_and_validate_is_clean(self):
        with archon.tree(["report"]) as tree:
            done = archon.archon(tree, "workflow", "test", "works-factory-report", "--json", "--cwd", str(tree))
            try:
                got = json.loads(done.stdout)
            except json.JSONDecodeError:
                self.fail(f"workflow test の返りが読めない: {done.stdout}{done.stderr}")
            names = sorted(pathlib.Path(r["fixture"]).name for r in got["results"])
            self.assertEqual(names, sorted(p.name for p in (BLOCK / "fixtures").glob("*.stubs.yaml")))
            self.assertEqual([r for r in got["results"] if not r["pass"]], [], done.stdout)
            self.assertEqual(got["errors"], [])
            checked = archon.archon(tree, "validate", "workflows", "--json", "--cwd", str(tree))
            issues = {r["workflowName"]: r["issues"] for r in json.loads(checked.stdout)["results"]}
            self.assertEqual(issues.get("works-factory-report"), [])

    def test_all_empty_and_request_stop_reach_their_words(self):
        """exec-code の筋書きの返す節の出力（dry-run の trace）が、それぞれの結末を返す"""
        for name, word in (("start-missing", "record_invalid"), ("stopped-by-request", "stopped_by_request")):
            with self.subTest(name), archon.tree(["report"]) as tree:
                fixture = yaml.safe_load((BLOCK / "fixtures" / f"{name}.stubs.yaml").read_text(encoding="utf-8"))
                stubs = tree.parent / "stubs.yaml"
                stubs.write_text(yaml.safe_dump({k: v for k, v in fixture.items() if k not in ("fixture", "exec-code")},
                                                allow_unicode=True), encoding="utf-8")
                args = [arg for k, v in (fixture["fixture"].get("inputs") or {}).items() for arg in ("--input", f"{k}={v}")]
                done = archon.archon(tree, "workflow", "run", "works-factory-report", "--dry-run", "--exec-code", "--stubs", str(stubs),
                                     "--json", *args, "--cwd", str(tree))
                trace = {n["nodeId"]: n for n in json.loads(done.stdout)["trace"]}
                self.assertEqual(json.loads(trace["report"]["output"])["outcome"], word, done.stdout)


if __name__ == "__main__":
    unittest.main()

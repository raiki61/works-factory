"""報告の block の筋書き（fixtures/*.stubs.yaml）を止めた Archon の workflow test で回し、同じ木の validate に誤りも警告も無いことを見る。
exec-code の筋書きは dry-run の trace で出口の出力（結末の語）も見る。YAML と src の揃いも照らす（block の形の検査は
tests/layers/test_block_shape.py）。"""
import json
import unittest

import yaml

from tests import archon
from tests.blocks import kit
from tests.blocks.report import base

M = base.src()
import report  # noqa: E402  lib/
import rolekit  # noqa: E402  lib/

BLOCK = base.BLOCK
DOC = yaml.safe_load((BLOCK / "works-factory-report.yaml").read_text(encoding="utf-8"))
NODES = {n["id"]: n for n in DOC["nodes"]}
BODY = {n["id"]: n for n in NODES["write-loop"]["loop_group"]["nodes"]}


class FixtureCase(unittest.TestCase):
    def test_fixtures_pass_and_validate_is_clean(self):
        with archon.blocks_tree(["report"]) as tree:
            done = archon.archon(tree, "workflow", "test", "works-factory-report", "--json", "--cwd", str(tree))
            try:
                got = json.loads(done.stdout)
            except json.JSONDecodeError:
                self.fail(f"workflow test の返りが読めない: {done.stdout}{done.stderr}")
            names = sorted(r["fixture"].rsplit("/", 1)[-1] for r in got["results"])
            self.assertEqual(names, sorted(p.name for p in (BLOCK / "fixtures").glob("*.stubs.yaml")))
            self.assertEqual([r for r in got["results"] if not r["pass"]], [], done.stdout)
            self.assertEqual(got["errors"], [])
            checked = archon.archon(tree, "validate", "workflows", "--json", "--cwd", str(tree))
            issues = {r["workflowName"]: [i for i in r["issues"] if archon.counted(i)] for r in json.loads(checked.stdout)["results"]}
            self.assertEqual(issues.get("works-factory-report"), [])

    def test_scenarios_reach_their_words(self):
        """exec-code の筋書きの出口の出力（dry-run の trace）が、それぞれの結末を返す"""
        want = {"standalone": ("fixed", True), "no-ai-report": ("record_invalid", False), "stopped-by-request": ("stopped_by_request", True),
                "cold-gave-up": ("fixed", False)}
        for name, (word, human) in want.items():
            with self.subTest(name), archon.blocks_tree(["report"]) as tree:
                fixture = kit.fixture("report", name)
                stubs = tree.parent / "stubs.yaml"
                stubs.write_text(yaml.safe_dump({k: v for k, v in fixture.items() if k not in ("fixture", "exec-code")}, allow_unicode=True),
                                 encoding="utf-8")
                args = [arg for k, v in (fixture["fixture"].get("inputs") or {}).items() for arg in ("--input", f"{k}={v}")]
                done = archon.archon(tree, "workflow", "run", "works-factory-report", "--dry-run", "--exec-code", "--stubs", str(stubs),
                                     "--json", *args, "--cwd", str(tree))
                trace = {n["nodeId"]: n for n in json.loads(done.stdout)["trace"]}
                out = json.loads(trace["finish"]["output"])
                self.assertEqual((out["outcome"], out["human"] is not None), (word, human), done.stdout)
                self.assertIn("機械の報告: ", out["report"][2])
                if name == "cold-gave-up":
                    self.assertIn("write-accept", trace)

    def test_every_scenario_stubs_only_ai_nodes(self):
        ai = {"write", "cold"}
        for path in (BLOCK / "fixtures").glob("*.stubs.yaml"):
            with self.subTest(path.name):
                doc = yaml.safe_load(path.read_text(encoding="utf-8"))
                stubbed = set(doc) - {"fixture", "exec-code"}
                self.assertLessEqual(stubbed, ai, "script の node は本当に走らせる（AI の node の台本だけ）")
                self.assertTrue(doc["exec-code"])
                self.assertLessEqual(set(doc["fixture"].get("inputs") or {}), set(DOC["inputs"]))


class ShapeCase(unittest.TestCase):
    """YAML と src の揃い"""

    def test_returns_and_outcome_words(self):
        self.assertEqual((DOC["returns"], DOC["outcome_field"]), ("finish", "ok"))
        props = NODES["finish"]["output_format"]["properties"]
        self.assertEqual(tuple(props["outcome"]["enum"]), report.OUTCOMES)
        self.assertEqual(set(props), {"ok", "outcome", "stop_reason", "machine", "human", "detail", "next_request", "prior_failures", "report"})

    def test_inputs_are_the_three_ports(self):
        self.assertEqual(list(DOC["inputs"]), ["sections", "facts", "lang"])
        self.assertTrue(DOC["inputs"]["sections"]["required"])
        self.assertEqual(DOC["inputs"]["facts"]["default"], "{}")
        for name, spec in DOC["inputs"].items():
            with self.subTest(name):
                self.assertTrue(spec["description"].startswith(("json(", "text:")), spec["description"])

    def test_loop_bound_matches_the_give_up_count(self):
        self.assertEqual(NODES["write-loop"]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER)
        self.assertIs(NODES["write-loop"]["loop_group"]["fresh_context"], True)
        self.assertEqual(NODES["write-loop"]["when"], "$facts.output.ai_go == 'true'")

    def test_node_order_and_trigger(self):
        self.assertEqual(list(NODES), ["facts", "write-loop", "finish"])
        self.assertEqual(list(BODY), ["write-prep", "write", "cold-prep", "cold", "write-accept"])
        self.assertEqual(NODES["finish"]["trigger_rule"], "all_done")
        self.assertEqual(NODES["finish"]["depends_on"], ["facts", "write-loop"])
        self.assertEqual(BODY["write-accept"]["depends_on"], ["write", "cold"])

    def test_roles_keep_the_old_settings(self):
        common = {"model": "@wf-report", "settingSources": ["user"], "mutates_checkout": False,
                  "sandbox": {"enabled": True, "allowUnsandboxedCommands": False}, "idle_timeout": 1728000000,
                  "retry": {"max_attempts": 2, "on_error": "all"}}
        for name, tools in (("write", ["Read", "Grep", "Glob", "WebSearch", "WebFetch"]), ("cold", [])):
            with self.subTest(name):
                node = BODY[name]
                self.assertEqual({k: node.get(k) for k in (*common, "allowed_tools")}, {**common, "allowed_tools": tools})
        self.assertEqual(BODY["cold"]["context"], "fresh")
        self.assertNotIn("context", BODY["write"])

    def test_ai_nodes_take_their_prompt_from_their_prep(self):
        self.assertEqual(BODY["write"]["prompt"], "$write-prep.output.prompt")
        self.assertEqual(BODY["cold"]["prompt"], "$cold-prep.output.prompt")

    def test_prep_nodes_name_the_ai_nodes_of_the_files(self):
        self.assertEqual((M.files.WRITE_NODE, M.files.COLD_NODE, M.files.WRITE_LOOP), ("write", "cold", "write-loop"))
        self.assertTrue((BLOCK / "prompts" / f"{M.files.WRITE_NODE}.md").is_file())
        self.assertTrue((BLOCK / "prompts" / f"{M.files.COLD_NODE}.md").is_file())

    def test_schemas_exist_for_the_json_ports(self):
        for name in ("sections.schema.json", "facts.schema.json"):
            self.assertTrue((BLOCK / "schemas" / name).is_file())
        facts = json.loads((BLOCK / "schemas" / "facts.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(facts["properties"]), set(M.facts_in.DEFAULTS), "欄と既定は同じ並び")

    def test_the_shared_fragments_the_block_adds_exist(self):
        for name in ("handoff", "report-head-check"):
            self.assertTrue((kit.SHARED / "prompts" / f"{name}.md").is_file())


if __name__ == "__main__":
    unittest.main()

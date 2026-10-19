"""block r2 の YAML と指示の md の形（docs/design/r2.md の 8 節）。PyYAML で読み、md を直に読むだけ（Archon を起こさない）。

今の tests/workflows/test_eyes.py の ShapeCase の r2 の場面（道具・群・新しい会話・retry・返答の型・system prompt・指示の文の行）を、
英語の md の決まった文で照らす形に作り直した。
"""
import json
import unittest

import yaml

from tests.blocks import kit

BLOCK = kit.BLOCKS / "r2"
DOC = yaml.safe_load((BLOCK / "works-factory-r2.yaml").read_text(encoding="utf-8"))
NODES = {n["id"]: n for n in DOC["nodes"]}
ROLES = {i: n for i, n in NODES.items() if "prompt" in n}

# 役の返答の型の正本（今の works の review-loop.json の r2.compare・premise-check の schema。tests/workflows/test_eyes.py の GRAPH_SCHEMAS の写し）
GRAPH_SCHEMAS = {
    "r2-compare": {
        "type": "object", "required": ["status", "reason", "differences"], "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": ["pass", "redesign-needed"]},
            "reason": {"type": "string", "minLength": 1},
            "differences": {"type": "array", "items": {
                "type": "object", "required": ["kind", "text"], "additionalProperties": False,
                "properties": {"kind": {"type": "string", "enum": ["構造", "表現"]}, "text": {"type": "string"}}}}}},
    "premise-check": {
        "type": "object", "required": ["key", "assumption", "assumption_false", "evidence", "verdict", "reason"],
        "additionalProperties": False,
        "properties": {
            "key": {"type": "string", "minLength": 1}, "assumption": {"type": "string"}, "assumption_false": {"type": "boolean"},
            "evidence": {"type": "string"}, "verdict": {"type": "string", "enum": ["resolved", "escalate"]},
            "reason": {"type": "string", "minLength": 1}, "resolution": {"type": "string"},
            "facts_to_add": {"type": "array", "items": {"type": "string"}}}},
}
TOOLS = {"r2-compare": ["Read"], "premise-check": ["Read", "Grep", "Glob", "WebSearch", "WebFetch"]}
MODEL = {"r2-compare": ("opus", "high"), "premise-check": ("opus", "high")}


def md(name: str) -> str:
    return (BLOCK / "prompts" / f"{name}.md").read_text(encoding="utf-8")


class RoleCase(unittest.TestCase):
    def test_role_tools(self):
        """比べの役は Read だけ、検算の役は judge の道具（シェルも書く道具も持たない）"""
        self.assertEqual({i: n["allowed_tools"] for i, n in ROLES.items()}, TOOLS)

    def test_roles_use_the_core_group(self):
        kit.load("r2", "files")   # lib/ を sys.path に足す
        import launchgroups
        self.assertEqual({i: launchgroups.default_of(n["model"]) for i, n in ROLES.items()}, MODEL)

    def test_roles_start_fresh_read_only_and_retry(self):
        for nid, node in ROLES.items():
            with self.subTest(nid):
                self.assertEqual(node.get("context"), "fresh")
                self.assertEqual(node.get("settingSources"), ["user"])
                self.assertEqual(node.get("sandbox"), {"enabled": True, "allowUnsandboxedCommands": False})
                self.assertIs(node.get("mutates_checkout"), False)
                self.assertEqual(node.get("retry"), {"max_attempts": 2, "on_error": "all"})
                self.assertNotIn("effort", node)

    def test_role_schemas_match_graph(self):
        for nid, want in GRAPH_SCHEMAS.items():
            with self.subTest(nid):
                self.assertEqual(json.loads(json.dumps(ROLES[nid]["output_format"])), want)

    def test_only_the_compare_role_has_a_system_prompt(self):
        """元の旗 isolated: 比べの役だけ既定の system prompt を替える。文は md に在り、値を持たない"""
        self.assertEqual([i for i, n in ROLES.items() if "systemPrompt" in n], ["r2-compare"])
        self.assertEqual(ROLES["r2-compare"]["systemPrompt"], "$r2-compare-prep.output.system")
        system = md("r2-compare.system")
        self.assertTrue(system.strip())
        self.assertNotIn("$", system)
        self.assertNotIn("{", system)

    def test_the_two_roads_are_exclusive_and_do_not_wait_for_each_other(self):
        self.assertEqual(NODES["r2-compare-prep"]["when"], "$intake.output.compare == true")
        self.assertEqual(NODES["premise-check-prep"]["when"], "$intake.output.premise == true")
        self.assertEqual(NODES["r2-compare-prep"]["depends_on"], ["intake"])
        self.assertEqual(NODES["premise-check-prep"]["depends_on"], ["intake"])
        self.assertNotIn("with", NODES["finish"])
        self.assertEqual(NODES["finish"].get("trigger_rule"), "all_done")

    def test_inputs_carry_no_judgment_or_plan(self):
        """keep-essence の 9 の R2（元 test_r2_compare_gets_no_forbidden_input）: 比べる役に判定・修正案・単位の目録・修正の結末を運ぶ port が無い"""
        self.assertEqual(sorted(DOC["inputs"]), sorted(["base", "head", "base_label", "purpose", "design", "design_reason", "design_premises",
                                                       "answers", "request", "changed", "constraints", "test_outcomes", "tdd", "lang"]))
        self.assertEqual(len(DOC["inputs"]), 14)
        for banned in ("judgment", "plan", "units", "fixes", "materials"):
            self.assertNotIn(banned, DOC["inputs"])

    def test_port_descriptions_name_no_other_block(self):
        for name, spec in DOC["inputs"].items():
            with self.subTest(name):
                self.assertNotIn("block", spec["description"])
                self.assertNotIn("の出力", spec["description"])

        for path in sorted((BLOCK / "schemas").glob("*.schema.json")):
            with self.subTest(path.name):
                description = json.loads(path.read_text(encoding="utf-8")).get("description", "")
                self.assertNotIn("block", description)
                self.assertNotIn("の出力", description)


class TextCase(unittest.TestCase):
    def test_compare_reads_the_whole_diff_file(self):
        """test_r2_compare_reads_the_whole_diff_file（E7）"""
        text = md("r2-compare")
        for ask in ("The cumulative diff is not pasted, whatever its size", "Read the whole file with Read.",
                    "read to the last line (do not judge a difference on a part you left unread)",
                    "the only file you may open is this one", "累積差分を読めなかった: ",
                    "setting it to {st_pass} would let through a diff that was not checked"):
            with self.subTest(ask[:30]):
                self.assertIn(ask, text)

    def test_compare_says_premise_changed(self):
        """test_r2_compare_says_premise_changed（E38）: 設計の前提の見出しが、前提のずれと記録の制約の見出しより先に在る"""
        text = md("r2-compare")
        self.assertIn("設計の前提が変わった: ", text)
        self.assertLess(text.index("{shared:design-premises}"), text.index("## Premises learned after the independent design"))
        self.assertLess(text.index("### Drift of premises"), text.index("### Recorded constraints"))
        self.assertIn("<!-- if late -->", text)

    def test_compare_checks_the_measurements_before_saying_missing(self):
        """test_r2_compare_checks_the_measurements_before_saying_missing（issue #384）"""
        text = md("r2-compare")
        self.assertLess(text.index("{part:measured}"), text.index("Before you write that something is missing from the diff"))
        self.assertIn("look at the names of the green-to-green tests", text)
        self.assertIn("Do not guess to treat as satisfied", text)
        part = md("parts/measured")
        for slot in ("{outcomes}", "{tdd_records}", "{origin}"):
            self.assertIn(slot, part)

    def test_compare_has_no_tool_or_judgment_leak(self):
        text = md("r2-compare")
        self.assertIn("{shared:role-blind-judge}", text)
        self.assertNotIn("{shared:query-rule}", text)
        for shared in ("concept-map", "policy", "recorded-policy"):
            self.assertNotIn(shared, text)
            self.assertNotIn(shared, md("premise-check"))

    def test_premise_check_gets_the_measurements_and_the_origin(self):
        """test_premise_check_gets_the_measurements_and_the_origin（issue #418）"""
        text = md("premise-check")
        self.assertLess(text.index("{part:measured}"), text.index("{fix_diff_row}"))
        self.assertIn("{shared:eye-role}", text)
        self.assertIn("{shared:role-judge}", text)
        for want in ("not uncommitted changes to ask a person about", "(the PR's diff)", "start `reason` with \"足りない: \""):
            self.assertIn(want, text)

    def test_prompts_bind_the_language_and_return_json(self):
        for name in ROLES:
            with self.subTest(name):
                tail = md(name).rstrip().splitlines()[-2:]
                self.assertIn("{lang}", tail[0])
                self.assertEqual(tail[1], "Return only JSON that matches this node's output schema (JSON Schema).")


class FixtureCase(unittest.TestCase):
    def test_fixtures_reach_each_road(self):
        a, b = kit.fixture("r2", "standalone"), kit.fixture("r2", "premise")
        self.assertEqual(a["fixture"]["reached"], ["intake", "r2-compare-prep", "r2-compare", "r2-compare-save", "finish"])
        self.assertEqual(b["fixture"]["reached"], ["intake", "premise-check-prep", "premise-check", "premise-check-save", "finish"])
        self.assertTrue(json.loads(a["fixture"]["inputs"]["design"])["question_stands"])
        self.assertFalse(json.loads(b["fixture"]["inputs"]["design"])["question_stands"])


if __name__ == "__main__":
    unittest.main()

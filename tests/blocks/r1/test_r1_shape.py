"""block r1 の YAML と指示の md の形（docs/design/r1.md の 8 節）。PyYAML で読み、md を組む口を直に呼ぶだけ（Archon を起こさない）。

今の tests/workflows/test_eyes.py の ShapeCase の r1 の 2 役の場面（道具・群・新しい会話・retry・返答の型・comment-analyzer の定義の字・
地図と方針の節・指示の文の行）を、英語の md の決まった文で照らす形に作り直した。返答の型の正本と comment-analyzer の定義の sha256 は、
今の試験から写した（組み込みで今の試験は消える）。
"""
import hashlib
import json
import unittest

import yaml

from tests.blocks import kit

BLOCK = kit.BLOCKS / "r1"
DOC = yaml.safe_load((BLOCK / "works-factory-r1.yaml").read_text(encoding="utf-8"))
NODES = {n["id"]: n for n in DOC["nodes"]}
ROLES = {i: n for i, n in NODES.items() if "prompt" in n}

# pr-review-toolkit:comment-analyzer の定義の本文（anthropics/claude-plugins-official の ce721c1f1d5da2c281588818e072ae01a05d2e73 の
# plugins/pr-review-toolkit/agents/comment-analyzer.md。Apache-2.0）の sha256。tests/workflows/test_eyes.py の写し
COMMENT_ANALYZER_SHA256 = "4a9c1f2eb8234a4b9231983e75739663d512e1aed242388964a165a719b84698"
COMMENT_ANALYZER_FRONT = """---
name: comment-analyzer
description: Use this agent when you need to analyze code comments for accuracy, completeness, and long-term maintainability. This includes (1) after generating large documentation comments or docstrings, (2) before finalizing a pull request that adds or modifies comments, (3) when reviewing existing comments for potential technical debt or comment rot, and (4) when you need to verify that comments accurately reflect the code they describe. See "When to invoke" in the agent body for worked scenarios.
model: inherit
color: green
---

"""
ROLE_HEAD = "## Role definition (pr-review-toolkit:comment-analyzer)\n\n"

# 役の返答の型の正本（今の works の review-loop.json の r1.comment_candidates・r1.minimality の schema。tests/workflows/test_eyes.py の
# GRAPH_SCHEMAS の r1 の 2 つの写し。note は YAML ではコメントに書く）と、r1-minimality に足した物（#663。R1_ADDED）
GRAPH_SCHEMAS = {
    "r1-comments": {
        "type": "object", "required": ["candidates", "kept"], "additionalProperties": False,
        "properties": {
            "candidates": {"type": "array", "items": {
                "type": "object", "required": ["where", "comment", "same_content_at", "reason"], "additionalProperties": False,
                "properties": {"where": {"type": "string"}, "comment": {"type": "string"},
                               "same_content_at": {"type": "string"}, "reason": {"type": "string"}}}},
            "kept": {"type": "array", "items": {
                "type": "object", "required": ["where", "fact"], "additionalProperties": False,
                "properties": {"where": {"type": "string"}, "fact": {"type": "string"}}}}}},
    "r1-minimality": {
        "type": "object", "required": ["status", "reason", "deletions", "ledger_audit", "increments"],
        "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": ["pass", "redesign-needed", "unverifiable"]},
            "reason": {"type": "string", "minLength": 1},
            "deletions": {"type": "array", "items": {
                "type": "object", "required": ["where", "why"], "additionalProperties": False,
                "properties": {"where": {"type": "string", "minLength": 1}, "why": {"type": "string"}}}},
            "ledger_audit": {"type": "array", "items": {"type": "string"}},
            "increments": {"type": "array", "items": {"type": "string"}},
            "candidates_note": {"type": "string"}}},
}
R1_ADDED = {"status_word": "fix-needed", "redesign_points": {"type": "array", "items": {"type": "string", "minLength": 1}}}
# 役の道具・群の既定の模型と effort（今の works の works/blk-eyes/lib/eyes.py:78-81 と blk-eyes.yaml の役の段。test_eyes.py の写し）
TOOLS = {"r1-comments": ["Read", "Grep", "Glob", "WebSearch", "WebFetch"], "r1-minimality": ["Read", "Grep", "Glob", "WebSearch", "WebFetch"]}
MODEL = {"r1-comments": ("sonnet", "medium"), "r1-minimality": ("opus", "high")}


def md(name: str) -> str:
    return (BLOCK / "prompts" / f"{name}.md").read_text(encoding="utf-8")


class RoleCase(unittest.TestCase):
    def test_eye_tools_are_the_role_tools(self):
        """test_eye_tools_are_the_role_tools・test_no_eye_has_shell_or_writer_tools の r1 の 2 役"""
        self.assertEqual({i: n["allowed_tools"] for i, n in ROLES.items()}, TOOLS)

    def test_role_model_and_effort_match_the_works_table(self):
        kit.load("r1", "steps")   # lib/ を sys.path に足す
        import launchgroups
        self.assertEqual({i: launchgroups.default_of(n["model"]) for i, n in ROLES.items()}, MODEL)

    def test_roles_start_fresh_read_only_and_retry(self):
        """test_role_settings_copied・test_retry_gives_three_tries・test_every_role_node_is_read_only の r1 の 2 役"""
        for nid, node in ROLES.items():
            with self.subTest(nid):
                self.assertEqual(node.get("context"), "fresh")
                self.assertEqual(node.get("settingSources"), ["user"])
                self.assertEqual(node.get("sandbox"), {"enabled": True, "allowUnsandboxedCommands": False})
                self.assertIs(node.get("mutates_checkout"), False)
                self.assertEqual(node.get("retry"), {"max_attempts": 2, "on_error": "all"})
                self.assertNotIn("effort", node)

    def test_role_schemas_match_graph(self):
        """test_role_schemas_match_graph の r1"""
        for nid, want in GRAPH_SCHEMAS.items():
            got = json.loads(json.dumps(ROLES[nid]["output_format"]))
            with self.subTest(nid):
                if nid == "r1-minimality":
                    self.assertEqual(got["properties"]["status"]["enum"], ["pass", "fix-needed", "redesign-needed", "unverifiable"])
                    got["properties"]["status"]["enum"].remove(R1_ADDED["status_word"])
                    self.assertEqual(got["properties"].pop("redesign_points"), R1_ADDED["redesign_points"])
                    self.assertNotIn("redesign_points", got["required"])
                self.assertEqual(got, want)

    def test_minimality_runs_without_the_comment_candidates(self):
        """test_r1_minimality_runs_without_the_comment_candidates（E10）: 2 段目の支度は前段の控えを all_done で待ち、with: を結ばない"""
        node = NODES["r1-minimality-prep"]
        self.assertEqual(node.get("trigger_rule"), "all_done")
        self.assertIn("r1-comments-save", node["depends_on"])
        self.assertNotIn("with", node)
        self.assertNotIn("with", NODES["finish"])
        self.assertEqual(NODES["finish"].get("trigger_rule"), "all_done")


class TextCase(unittest.TestCase):
    def test_r1_comments_carries_the_comment_analyzer_definition_verbatim(self):
        """test_r1_comments_carries_the_comment_analyzer_definition_verbatim（E11）"""
        body = md("r1-comments").partition(ROLE_HEAD)[2].partition("\n\n---\n\n")[0]
        self.assertEqual(hashlib.sha256((COMMENT_ANALYZER_FRONT + body + "\n").encode("utf-8")).hexdigest(), COMMENT_ANALYZER_SHA256)

    def test_r1_comments_keeps_the_three_added_asks(self):
        """test_r1_comments_keeps_the_three_added_asks（E12）"""
        text = md("r1-comments")
        for ask in ("1. **For each removal candidate, name where the same content lives**", "if you cannot name it, do not remove",
                    "2. **For each comment you decide to keep, say in one sentence the fact it carries**",
                    "keeping a comment silently becomes the cheaper choice",
                    "3. Search explicitly, as concrete triggers, for commented-out code, running commentary on the edit"):
            with self.subTest(ask[:20]):
                self.assertIn(ask, text)

    def test_minimality_knows_where_handoffs_go(self):
        """test_minimality_knows_where_handoffs_go（E13）"""
        text = md("r1-minimality")
        for want in ("`breaks.accepted`", "they are not in the question ledger", "judge by the content",
                     'write it in `ledger_audit` as one line starting with "breaks.accepted: "'):
            self.assertIn(want, text)

    def test_r1_reads_the_gate_evidence_and_names_unused_additions(self):
        """test_r1_reads_the_gate_evidence_and_names_unused_additions"""
        text = md("r1-minimality")
        for want in ("Evidence of the last test gate: `{checks_file}` (Read it. Also Read the log location the evidence names.)",
                     "public names or functions the diff added that are used from nowhere",
                     "name each with its place in `deletions`", "Grep by name to judge, and say so in `reason`"):
            with self.subTest(want[:30]):
                self.assertIn(want, text)

    def test_r1_status_rule_names_fix_needed_and_points(self):
        """test_r1_status_rule_names_fix_needed_and_points（#663）: 札の決まりは status の段落が正本で、ほかの段落は所見に数えるかだけを書く"""
        text = md("r1-minimality")
        rule = next(line for line in text.splitlines() if line.startswith("`status` is one of "))
        self.assertTrue(rule.startswith("`status` is one of {st_pass}, {st_fix}, {st_redesign}, {st_unverifiable}."), rule)
        self.assertIn("`redesign_points`", rule)
        self.assertIn("closes with a zero prescription", rule)
        pass_cond = rule[rule.index("Use {st_pass} only when"):rule.index("Write what you found")]
        for item in ("`deletions`", "unjustifiable increment", "unjustified prescription", "escape route"):
            self.assertIn(item, pass_cond)
        self.assertEqual(text.count("pick the label by the status rule below"), 3)
        unhoused = text[text.index("If only the places that know a concept with no home"):]
        unhoused = unhoused[:unhoused.index("(not counted as a finding)")]
        self.assertIn("as a justifiable increment", unhoused)
        self.assertNotIn("{st_", unhoused)

    def test_minimality_holds_the_shared_sections(self):
        """test_concept_map_only_on_r1_and_r3・test_policy_section_on_r1_r3_r4・test_concept_map_is_pasted_after_the_concept_head の r1"""
        text = md("r1-minimality")
        self.assertLess(text.index("{after_section}"), text.index("{shared:concept-map}"))
        self.assertIn("<!-- if policy -->\n{shared:eye-policy}\n<!-- end policy -->", text)
        self.assertIn("<!-- if not green -->\n{shared:eye-green}\n<!-- end green -->", text)
        self.assertNotIn("concept-map", md("r1-comments"))
        self.assertNotIn("policy", md("r1-comments"))

    def test_both_prompts_bind_the_language_and_return_json(self):
        """test_every_command_binds_the_language_and_returns_json の r1"""
        for name in ROLES:
            with self.subTest(name):
                tail = md(name).rstrip().splitlines()[-2:]
                self.assertIn("{lang}", tail[0])
                self.assertEqual(tail[1], "Return only JSON that matches this node's output schema (JSON Schema).")


if __name__ == "__main__":
    unittest.main()

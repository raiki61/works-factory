"""block r4 の YAML と指示の md の形（docs/design/r4.md の 8 節）。PyYAML で読み、md を組む口を直に呼ぶだけ（Archon を起こさない）。

今の tests/workflows/test_eyes.py の ShapeCase の r4 の場面（道具・群・retry・輪の形・返答の型・方針と地図の節）を、英語の md の決まった文で
照らす形に作り直した。
"""
import json
import unittest

import yaml

from tests.blocks import kit
from tests.layers.test_block_shape import PROMPT_REF

BLOCK = kit.BLOCKS / "r4"
DOC = yaml.safe_load((BLOCK / "works-factory-r4.yaml").read_text(encoding="utf-8"))
LOOP = next(n for n in DOC["nodes"] if "loop_group" in n)
NODES = {n["id"]: n for n in [*DOC["nodes"], *LOOP["loop_group"]["nodes"]]}
ROLES = {i: n for i, n in NODES.items() if "prompt" in n}

# 役の返答の型の正本（今の works の review-loop.json の r4.hidden_scope の schema に、seen と unseen と、必須でない r3 を足した物。
# 今の workflows/eyes の &r4_reply・&one_reply の写し）
R3_REPLY = {"type": "object", "required": ["status", "reason", "seen", "unseen"],
            "properties": {"status": {"type": "string", "enum": ["pass", "redesign-needed", "unverifiable"]},
                           "reason": {"type": "string", "minLength": 1}, "seen": {"type": "array", "items": {"type": "string"}},
                           "unseen": {"type": "array", "items": {"type": "string"}}}}
R4_REPLY = {
    "type": "object", "additionalProperties": False,
    "required": ["status", "reason", "capability_inventory", "policy_conflicts", "surfaced", "seen", "unseen"],
    "properties": {
        "status": {"type": "string", "enum": ["pass", "redesign-needed", "unverifiable"]},
        "reason": {"type": "string", "minLength": 1},
        "capability_inventory": {"type": "object", "required": ["fired"], "additionalProperties": False,
                                 "properties": {"fired": {"type": "boolean"}, "lost": {"type": "array", "items": {"type": "string"}},
                                                "note": {"type": "string"}}},
        "policy_conflicts": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "surfaced": {"type": "array", "items": {
            "type": "object", "required": ["where", "text"], "additionalProperties": False,
            "properties": {"where": {"type": "string"}, "text": {"type": "string"}, "mechanism": {"type": "string"},
                           "measured": {"type": "string"}, "false_positive_if": {"type": "string"}}}},
        "seen": {"type": "array", "items": {"type": "string"}},
        "unseen": {"type": "array", "items": {"type": "string"}},
        "r3": R3_REPLY},
    "if": {"properties": {"capability_inventory": {"properties": {"fired": {"const": True}}}}},
    "then": {"properties": {"capability_inventory": {"required": ["fired", "lost"]}}},
}


def md(name: str) -> str:
    return (BLOCK / "prompts" / f"{name}.md").read_text(encoding="utf-8")


class RoleCase(unittest.TestCase):
    def test_both_roles_are_read_only_and_retry(self):
        """test_eye_tools_are_the_role_tools・test_retry_gives_three_tries・test_every_role_node_is_read_only の r4"""
        self.assertEqual(set(ROLES), {"r4-scope", "r4-scope-fix"})
        for nid, node in ROLES.items():
            with self.subTest(nid):
                self.assertEqual(node["allowed_tools"], ["Read", "Grep", "Glob"])
                self.assertEqual(node["model"], "@wf-eyes-scope")
                self.assertEqual(node.get("settingSources"), ["user"])
                self.assertEqual(node.get("sandbox"), {"enabled": True, "allowUnsandboxedCommands": False})
                self.assertIs(node.get("mutates_checkout"), False)
                self.assertEqual(node.get("retry"), {"max_attempts": 2, "on_error": "all"})
                self.assertNotIn("effort", node)
                self.assertNotIn("context", node, "輪の会話は fresh_context: false が持つ")

    def test_model_group_matches_the_works_table(self):
        kit.load("r4", "steps")
        import launchgroups
        self.assertEqual(launchgroups.default_of("@wf-eyes-scope"), ("sonnet", "medium"))

    def test_loop_is_an_accept_loop(self):
        """test_r4_runs_in_an_accept_loop（#455）"""
        import rolekit
        loop = LOOP["loop_group"]
        self.assertEqual(loop["max_iterations"], rolekit.GIVE_UP_AFTER)
        self.assertIs(loop["fresh_context"], False)
        self.assertIn("$r4-scope-accept.output.done", loop["until_bash"])
        self.assertEqual([n["id"] for n in loop["nodes"]],
                         ["r4-scope-prep", "r4-scope", "r4-scope-fix-prep", "r4-scope-fix", "r4-scope-accept"])
        self.assertEqual(LOOP["when"], "$intake.output.due == true")

    def test_resubmit_role_follows_the_first_role_in_its_own_layer(self):
        """#571 と、輪の中で役の前に並んだ層を置かない形: 出し直しの prep は r4-scope の後ろの層に置き、役の起きる層に節が 1 つだけ"""
        fix, prep, first = NODES["r4-scope-fix"], NODES["r4-scope-fix-prep"], NODES["r4-scope"]
        self.assertEqual((fix["when"], fix["prompt"], fix["trigger_rule"]),
                         ("$r4-scope-prep.output.resubmit == true", "$r4-scope-fix-prep.output.prompt", "none_failed_min_one_success"))
        self.assertEqual((prep["when"], prep["depends_on"], prep["trigger_rule"]),
                         ("$r4-scope-prep.output.resubmit == true", ["r4-scope-prep", "r4-scope"], "none_failed_min_one_success"))
        self.assertEqual((first["when"], first["depends_on"]), ("$r4-scope-prep.output.resubmit != true", ["r4-scope-prep"]))
        self.assertEqual(fix["output_format"]["required"], [])
        self.assertEqual(NODES["r4-scope-accept"]["trigger_rule"], "none_failed_min_one_success")

    def test_loop_does_not_paste_previous_reject_by_loop_prev(self):
        """前の回の拒否の文は $LOOP_PREV で with: に貼らない（元の裁定 R44）。結ぶのは前の周の受け付けの ok だけ"""
        for n in LOOP["loop_group"]["nodes"]:
            with self.subTest(n["id"]):
                pasted = [v for v in (n.get("with") or {}).values() if "$LOOP_PREV" in json.dumps(v)]
                self.assertEqual(pasted, ["$LOOP_PREV.r4-scope-accept.output.ok"] if n["id"] == "r4-scope-prep" else [])

    def test_role_schemas_match_graph(self):
        """test_role_schemas_match_graph の R4（seen・unseen と必須でない r3 を足した物）と、出し直しの型は required: [] の同じ物"""
        self.assertEqual(json.loads(json.dumps(NODES["r4-scope"]["output_format"])), R4_REPLY)
        self.assertEqual(json.loads(json.dumps(NODES["r4-scope-fix"]["output_format"])), {**R4_REPLY, "required": []})

    def test_inventory_requires_lost(self):
        """test_r4_inventory_requires_lost: 棚卸しが発火した返答（fired: true）は lost が要る。if/then は Archon の Ajv が照らす（lib の
        engine.schema は if/then を読まないので、型の形で縛り、読める部分だけ照らす）"""
        from engine.schema import validate_schema
        for nid in ROLES:
            schema = NODES[nid]["output_format"]
            self.assertEqual(schema["if"], {"properties": {"capability_inventory": {"properties": {"fired": {"const": True}}}}})
            self.assertEqual(schema["then"], {"properties": {"capability_inventory": {"required": ["fired", "lost"]}}})
        schema = NODES["r4-scope"]["output_format"]
        reply = {"status": "pass", "reason": "なし", "policy_conflicts": [], "surfaced": [], "seen": [], "unseen": [],
                 "capability_inventory": {"fired": True, "lost": []}}
        self.assertEqual(validate_schema(reply, schema), [])
        self.assertNotEqual(validate_schema({**reply, "status": "weird"}, schema), [])

    def test_prompt_refs_come_from_their_own_preps(self):
        for nid, prep in (("r4-scope", "r4-scope-prep"), ("r4-scope-fix", "r4-scope-fix-prep")):
            self.assertEqual(PROMPT_REF.match(NODES[nid]["prompt"]).group(1), prep)


class TextCase(unittest.TestCase):
    def test_the_first_role_does_not_say_new_conversation(self):
        """輪の中の役は出し直しが同じ会話の続きなので「新しい会話で起きている」と言わない"""
        for name in ROLES:
            with self.subTest(name):
                self.assertNotIn("new conversation", md(name))
        self.assertTrue(md("r4-scope").startswith("You are one of the independent eyes (R4: the scope the change does not see). "
                                                  "If the machine's check rejects your answer, you resubmit in this same conversation."))

    def test_fixed_asks_are_kept(self):
        """2.3 の一覧の 12〜16 など、決まった文の要の句"""
        text = md("r4-scope")
        for want in ("say explicitly in `lost`", "a silent omission is forbidden", "a sentence a person already passed is not asked again",
                     "Do not count what you list in `policy_conflicts` toward `status`",
                     "making it redesign-needed would have the role decide before the person does",
                     "copy the row's body as it is", "A risk this change introduced or exposed is redesign-needed",
                     "never use [block]", "match the kind in [ ] (regression goes to `lost`, policy goes to `policy_conflicts`)",
                     "copy the body without changing a single character", 'Read "横断リスク観点" and follow it',
                     "The list is examples, not a limit",
                     "whether to accept a lost capability is also for a person to decide at the approval node"):
            with self.subTest(want[:30]):
                self.assertIn(want, text)

    def test_role_sections_are_the_shared_ones(self):
        text = md("r4-scope")
        for frag in ("eye-role", "role-inspector", "eye-diff", "eye-seen", "eye-frozen", "eye-recorded-policy", "rejected", "policy",
                     "eye-coherence", "concept-map-found", "concept-map-none"):
            with self.subTest(frag):
                self.assertIn("{shared:%s}" % frag, text)
        self.assertIn("<!-- if not green -->\n{shared:eye-green}\n<!-- end green -->", text)
        self.assertNotIn("{shared:concept-map}", text, "地図は段落 coherence の外から選ぶ 2 本で差し込む")
        coherence = text[text.index("<!-- if coherence -->"):text.index("<!-- end coherence -->")]
        self.assertIn("{shared:eye-coherence}", coherence)
        self.assertNotIn("{shared:concept-map", coherence)

    def test_both_prompts_end_with_the_language_and_json(self):
        self.assertIn("{lang}", md("r4-scope").rstrip().splitlines()[-2])
        self.assertEqual(md("r4-scope").rstrip().splitlines()[-1], "Return only JSON that matches this node's output schema (JSON Schema).")
        self.assertTrue(md("r4-scope-fix").startswith("{shared:resubmit}"))
        self.assertIn("{lang}", md("r4-scope-fix"))


if __name__ == "__main__":
    unittest.main()

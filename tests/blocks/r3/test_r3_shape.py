"""block r3 の YAML と指示の md の形（docs/design/r3.md の 7 節）。PyYAML で読み、md を組む口を直に呼ぶだけ（Archon を起こさない）。

今の tests/workflows/test_eyes.py の ShapeCase の r3 の場面（道具・群・新しい会話・retry・返答の型・地図と方針と記録された方針の節・対象の
REVIEW.md の行）を、英語の md の決まった文で照らす形に作り直した。返答の型の正本は今の試験から写した（組み込みで今の試験は消える）。
"""
import json
import unittest

import yaml

from tests.blocks import kit

BLOCK = kit.BLOCKS / "r3"
DOC = yaml.safe_load((BLOCK / "works-factory-r3.yaml").read_text(encoding="utf-8"))
NODES = {n["id"]: n for n in DOC["nodes"]}
ROLES = {i: n for i, n in NODES.items() if "prompt" in n}

# 役の返答の型の正本（今の works の review-loop.json の r3.coherence の schema に seen・unseen を足した物。tests/workflows/test_eyes.py の
# GRAPH_SCHEMAS の r3-coherence の写しと SEEN_UNSEEN）
GRAPH_SCHEMA = {
    "type": "object", "required": ["status", "reason", "seen", "unseen"],
    "properties": {
        "status": {"type": "string", "enum": ["pass", "redesign-needed", "unverifiable"]},
        "reason": {"type": "string", "minLength": 1},
        "seen": {"type": "array", "items": {"type": "string"}},
        "unseen": {"type": "array", "items": {"type": "string"}}}}
# 役の道具・群の既定の模型と effort（今の works の works/blk-eyes/lib/eyes.py:78-81 と blk-eyes.yaml の役の段）
MODEL = ("sonnet", "medium")


def md() -> str:
    return (BLOCK / "prompts" / "r3-coherence.md").read_text(encoding="utf-8")


def fragment(name: str) -> str:
    return (kit.SHARED / "prompts" / f"{name}.md").read_text(encoding="utf-8")


class RoleCase(unittest.TestCase):
    def test_the_only_role_reads_and_nothing_else(self):
        """test_eye_tools_are_the_role_tools・test_no_eye_has_shell_or_writer_tools の r3: 読む道具だけ（shell も書く道具も無い）"""
        self.assertEqual(list(ROLES), ["r3-coherence"])
        self.assertEqual(ROLES["r3-coherence"]["allowed_tools"], ["Read", "Grep", "Glob"])

    def test_role_model_is_the_scope_group(self):
        kit.load("r3", "steps")   # lib/ を sys.path に足す
        import launchgroups
        node = ROLES["r3-coherence"]
        self.assertEqual(launchgroups.default_of(node["model"]), MODEL)

    def test_role_starts_fresh_read_only_and_retries(self):
        """test_role_settings_copied・test_retry_gives_three_tries・test_every_role_node_is_read_only の r3"""
        node = ROLES["r3-coherence"]
        self.assertEqual(node.get("context"), "fresh")
        self.assertEqual(node.get("settingSources"), ["user"])
        self.assertEqual(node.get("sandbox"), {"enabled": True, "allowUnsandboxedCommands": False})
        self.assertIs(node.get("mutates_checkout"), False)
        self.assertEqual(node.get("retry"), {"max_attempts": 2, "on_error": "all"})
        self.assertNotIn("effort", node)

    def test_role_schema_matches_graph(self):
        """test_role_schemas_match_graph の r3（今の型に seen・unseen を足した物。additionalProperties は今のまま書かない）"""
        self.assertEqual(json.loads(json.dumps(ROLES["r3-coherence"]["output_format"])), GRAPH_SCHEMA)

    def test_finish_waits_for_every_node_and_binds_no_reply(self):
        """落ちた役へ with: を結ばない（Archon が誤りで止める）。出口は all_done で、返ったファイルを読む"""
        self.assertEqual(NODES["finish"].get("trigger_rule"), "all_done")
        self.assertNotIn("with", NODES["finish"])
        self.assertNotIn("with", NODES["r3-coherence-prep"])
        self.assertEqual(NODES["r3-coherence-prep"]["when"], "$intake.output.due == true")


class TextCase(unittest.TestCase):
    def test_prompt_is_the_shared_fragments_in_the_sheet_order(self):
        """設計書の 2.3 の順: 役の 1 行目・eye-role・role-inspector・eye-coherence・concept-map・eye-diff・eye-green・eye-frozen・eye-policy・
        eye-recorded-policy・言語と JSON"""
        text = md()
        order = ["You are one of the independent eyes (R3 overall coherence), started in a new conversation.", "{shared:eye-role}",
                 "{shared:role-inspector}", "{shared:eye-coherence}", "{shared:concept-map}", "{shared:eye-diff}", "{shared:eye-green}",
                 "{shared:eye-frozen}", "{shared:eye-policy}", "{shared:eye-recorded-policy}", "in {lang}.",
                 "Return only JSON that matches this node's output schema (JSON Schema)."]
        at = [text.index(part) for part in order]
        self.assertEqual(at, sorted(at))
        self.assertTrue(text.startswith(order[0]))

    def test_sections_are_chosen_by_paragraph_marks(self):
        """test_policy_section_on_r1_r3_r4・test_recorded_policy_only_on_r3_r4 の r3: 方針の節は方針の在る run だけ、緑の文は緑が認証されない時だけ、
        記録された方針の節は段落の外（方針の無い run にも「無い」と載る）"""
        text = md()
        self.assertIn("<!-- if policy -->\n{shared:eye-policy}\n<!-- end policy -->", text)
        self.assertIn("<!-- if not green -->\n{shared:eye-green}\n<!-- end green -->", text)
        self.assertNotIn("<!-- if recorded_none -->", text)
        self.assertIn("\n{shared:eye-recorded-policy}\n", text)

    def test_map_follows_the_concept_head(self):
        """test_concept_map_is_pasted_after_the_concept_head の r3: 住処の観点は地図の節を「この観点の後ろに機械が貼った」と読ませ、
        地図の節は観点の断片の後ろに在る（断片は地図を持たない）"""
        head = fragment("eye-coherence")
        self.assertIn("the machine pasted it after this viewpoint", head)
        self.assertNotIn("concept-map", head)
        text = md()
        self.assertLess(text.index("{shared:eye-coherence}"), text.index("{shared:concept-map}"))

    def test_viewpoint_fragment_has_no_paragraph_marks_and_names_the_target_review_md(self):
        """r4 の coherence の段落の中からも差し込めるよう、断片は段落の印を持たない。対象の REVIEW.md の行の口を持つ（E24）"""
        head = fragment("eye-coherence")
        self.assertNotIn("<!--", head)
        self.assertIn("(on the target repository's side: {repo_review_md})", head)

    def test_viewpoint_fragment_writes_the_home_head_as_the_readers_do(self):
        """考えの住処の頭の字は断片が直に持つ（lib の頭の定数を値で渡さない）。報告と承認ノードの読み手の字と同じ（r3・r4 が読む）"""
        import concepthome   # lib/（kit.load が sys.path に足す）
        head = fragment("eye-coherence")
        self.assertIn(f'start `reason` with "{concepthome.PREFIX}"', head)
        self.assertNotIn("{home_prefix}", head)

    def test_prompt_binds_the_language_and_returns_json(self):
        """test_every_command_binds_the_language_and_returns_json の r3"""
        tail = md().rstrip().splitlines()[-2:]
        self.assertIn("{lang}", tail[0])
        self.assertEqual(tail[1], "Return only JSON that matches this node's output schema (JSON Schema).")

    def test_prompt_does_not_claim_a_new_conversation_in_a_shared_fragment(self):
        """役は輪の外で毎回新しい会話（context: fresh）なので、1 行目で名乗ってよい。名乗りは md に在り、共通の断片（eye-role）には無い
        （輪の中の r4 が差し込むため）"""
        self.assertNotIn("new conversation", fragment("eye-role"))


if __name__ == "__main__":
    unittest.main()

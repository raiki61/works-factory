"""YAML・形のファイル・指示の揃い（docs/design/delta-review.md の 10.2 の ShapeCase・PortsCase）。block の形の検査は tests/layers/test_block_shape.py。"""
import importlib
import json
import unittest

import yaml

from tests.blocks import kit

BLOCK = kit.BLOCKS / "delta-review"
doc = yaml.safe_load((BLOCK / "works-factory-delta-review.yaml").read_text(encoding="utf-8"))
NODES = {n["id"]: n for n in doc["nodes"]}
LOOPS = {n["id"]: {x["id"]: x for x in n["loop_group"]["nodes"]} for n in doc["nodes"] if "loop_group" in n}
ROLES = {role: nodes[role] for loop, nodes in LOOPS.items() for role in nodes if "prompt" in nodes[role]}


class ShapeCase(unittest.TestCase):
    def setUp(self):
        self.files, self.review, self.verdicts, self.touchup = (kit.load("delta-review", m) for m in ("files", "review", "verdicts", "touchup"))
        self.rolekit = importlib.import_module("rolekit")   # kit.load が ports を読み込んだので lib/ が見える

    def props(self, role):
        return ROLES[role]["output_format"]["properties"]

    def test_the_four_roles_are_the_four_nodes_of_the_table(self):
        self.assertEqual(sorted(ROLES), sorted([*self.files.REVIEW.values(), *self.files.REFIX.values()]))
        self.assertEqual(sorted(LOOPS), ["refix-1-loop", "refix-2-loop", "review-1-loop", "review-2-loop"])

    def test_hole_kinds_match_the_acceptance(self):
        for role in ("review-1", "review-2"):
            kinds = self.props(role)["faces"]["items"]["properties"]["kind"]["enum"]
            self.assertEqual(tuple(kinds), self.review.FACE_KINDS, role)

    def test_string_lengths_match_the_numbers_the_prompts_say(self):
        face = self.props("review-1")["faces"]["items"]["properties"]
        self.assertEqual((face["key"]["minLength"], face["cite"]["minLength"], face["why"]["minLength"]),
                         (self.review.MIN_KEY, self.review.MIN_CITE, self.review.MIN_WHY))
        self.assertEqual(self.props("refix-1")["handled"]["items"]["properties"]["how"]["minLength"], self.touchup.MIN_HOW)
        self.assertEqual(self.props("review-1")["compliance"]["properties"]["read"]["minLength"], self.verdicts.MIN_WHY)

    def test_verdict_words_match_the_acceptance(self):
        comp = self.props("review-1")["compliance"]["properties"]
        self.assertEqual(tuple(comp["verdict"]["enum"]), self.verdicts.COMPLIANCE)
        self.assertEqual(tuple(comp["items"]["items"]["properties"]["kind"]["enum"]), self.verdicts.KINDS)
        self.assertEqual(tuple(self.props("review-1")["quality"]["properties"]["verdict"]["enum"]), self.verdicts.QUALITY)
        for key, schema in self.verdicts.FIELD_SCHEMA.items():
            self.assertEqual(schema["properties"]["verdict"]["enum"], self.props("review-1")[key]["properties"]["verdict"]["enum"])

    def test_handled_words_match_the_acceptance(self):
        for role in ("refix-1", "refix-2"):
            self.assertEqual(tuple(self.props(role)["handled"]["items"]["properties"]["handled"]["enum"]), self.touchup.HANDLED)

    def test_loop_bound_is_the_give_up_count(self):
        for loop in LOOPS:
            self.assertEqual(NODES[loop]["loop_group"]["max_iterations"], self.rolekit.GIVE_UP_AFTER)

    def test_every_loop_continues_the_conversation_in_one_straight_line(self):
        for loop, nodes in LOOPS.items():
            with self.subTest(loop=loop):
                group = NODES[loop]["loop_group"]
                self.assertIs(group["fresh_context"], False)
                prep, role, accept = nodes
                self.assertEqual((nodes[prep].get("depends_on"), nodes[role]["depends_on"], nodes[accept]["depends_on"]), (None, [prep], [role]))
                self.assertEqual(group["until_bash"], f'done=${accept}.output.done; test "$done" = true')
                self.assertEqual(nodes[role]["prompt"], f"${prep}.output.prompt")

    def test_roles_have_only_their_tools_and_the_closed_settings(self):
        for role, node in ROLES.items():
            with self.subTest(role=role):
                self.assertEqual(node["settingSources"], ["user"])
                self.assertEqual(node["sandbox"], {"enabled": True, "allowUnsandboxedCommands": False})
                self.assertEqual(node["idle_timeout"], 1728000000)
                self.assertEqual(node["retry"], {"max_attempts": 2, "on_error": "all"})
                if role.startswith("review"):
                    self.assertEqual((node["model"], node["allowed_tools"], node["mutates_checkout"]), ("@wf-fix-review", ["Read", "Grep", "Glob"], False))
                    self.assertNotIn("skills", node)
                else:
                    self.assertEqual(node["model"], "@wf-fix-writers")
                    self.assertEqual(node["allowed_tools"], ["Read", "Grep", "Glob", "Edit", "Write", "Bash", "WebSearch", "WebFetch", "Skill"])
                    self.assertEqual(node["skills"], ["receiving-code-review"])
                    self.assertNotIn("mutates_checkout", node, "作業ツリーを書く役は印を書かない")

    def test_every_script_node_leaves_the_work_tree_alone_and_the_loops_are_wired_by_n(self):
        for node in doc["nodes"]:
            for inner in [node, *LOOPS.get(node["id"], {}).values()]:
                if "script" in inner:
                    self.assertIs(inner["mutates_checkout"], False, inner["id"])
                    self.assertEqual(inner["runtime"], "uv")
        for n in (1, 2):
            self.assertEqual(LOOPS[f"review-{n}-loop"][f"review-{n}-prep"]["with"], {"n": n})
            seal = "$intake.output.seal"   # 入口の凍結の印は Archon が持ち、役の手の届かない with: で受け付けへ渡る
            self.assertEqual(LOOPS[f"review-{n}-loop"][f"review-{n}-accept"]["with"], {"n": n, "reply": f"$review-{n}.output", "seal": seal})
            self.assertEqual(LOOPS[f"refix-{n}-loop"][f"refix-{n}-accept"]["with"], {"n": n, "reply": f"$refix-{n}.output", "seal": seal})
            self.assertEqual(LOOPS[f"refix-{n}-loop"][f"refix-{n}-prep"]["with"], {"n": n})
            self.assertEqual(NODES[f"owed-{n}"]["with"], {"n": n})

    def test_loops_are_started_by_the_scripts_outside_them(self):
        self.assertEqual(NODES["review-1-loop"]["when"], "$intake.output.due == true")
        self.assertEqual(NODES["refix-1-loop"]["when"], "$owed-1.output.due == true")
        self.assertEqual(NODES["review-2-loop"]["when"], "$cut-2.output.due == true")
        self.assertEqual(NODES["refix-2-loop"]["when"], "$owed-2.output.due == true")
        self.assertEqual(NODES["cut-2"]["depends_on"], ["owed-1", "refix-1-loop"])
        self.assertEqual(NODES["cut-2"]["trigger_rule"], "all_done")
        self.assertEqual(NODES["finish"]["depends_on"], ["intake", "review-1-loop", "owed-1", "refix-1-loop", "cut-2", "review-2-loop", "owed-2", "refix-2-loop"])

    def test_return_carries_the_outcome_and_all_fields(self):
        self.assertEqual((doc["returns"], doc["outcome_field"]), ("finish", "ok"))
        shape = NODES["finish"]["output_format"]
        self.assertEqual(sorted(shape["required"]), sorted(shape["properties"]))
        self.assertEqual(shape["properties"]["status"]["enum"], ["ok", "gave_up", "failed"])
        self.assertEqual(shape["properties"]["rounds"], {"type": "integer", "minimum": 0, "maximum": 2})

    def test_prompts_name_the_words_the_acceptance_uses(self):
        text = (BLOCK / "prompts" / "review-1.md").read_text(encoding="utf-8")
        self.assertIn("{absorbed}", text)
        self.assertEqual(self.review.CLAIMED, {1: "absorbed", 2: "fixed"})
        self.assertIn("{fixed}", (BLOCK / "prompts" / "review-2.md").read_text(encoding="utf-8"))


class PortsCase(unittest.TestCase):
    def test_the_inputs_are_exactly_the_nine_of_the_design(self):
        self.assertEqual(sorted(doc["inputs"]), sorted(["base", "plan", "lens_rows", "fix_reply", "permits", "plan_review", "policy", "request", "lang"]))
        self.assertEqual([k for k, v in doc["inputs"].items() if v.get("required")], ["base"])

    def test_the_shapes_accept_null_where_the_design_says_null(self):
        materials = kit.load("delta-review", "materials")
        with kit.Run(self, "delta-review").env():
            self.assertIsNone(materials.fix_reply("null"))
            self.assertIsNone(materials.plan_review("null"))
            self.assertEqual(materials.permit_paths("[]"), [])
            with self.assertRaises(ValueError):
                materials.fix_reply('{"plan_faces": [{"key": "only-a-key"}]}')
            with self.assertRaises(ValueError):
                materials.permit_paths('{"a": 1}')
            with self.assertRaises(ValueError):
                materials.plan_review("[1]")
            with self.assertRaises(ValueError):
                materials.permit_paths("[1]")

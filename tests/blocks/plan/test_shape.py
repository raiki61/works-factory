"""plan の block の形（docs/design/plan.md の 1.2・1.3・9.2）: 入力と出口の約束・AI の node の起こし方・輪の並び・型が lib の持ち主と同じ・
md に旧い言い回しが残らない・script の名と fallback の字が揃う。今の tests/workflows/test_plan.py の ShapeCase から。"""
import json
import pathlib
import re
import sys
import unittest

from tests.blocks import kit
from tests.blocks.plan import base
from tests.layers import scan

for _path in (kit.ROOT / "lib" / "graphloops", kit.ROOT / "lib"):
    if str(_path) not in sys.path:
        sys.path.append(str(_path))

import carry  # noqa: E402
import converge  # noqa: E402
import gatemarks  # noqa: E402
import handoff  # noqa: E402
import launchgroups  # noqa: E402
import planmarks  # noqa: E402
import replan  # noqa: E402
import rolekit  # noqa: E402

BLOCK = base.BLOCK
NO_DEADLINE = 1728000000
PORTS = ["judgment", "units", "answer_ties", "materials", "answers", "takes_push", "verify", "excluded", "depth_record", "decisions",
         "world_rows", "structure", "spec", "spec_doc", "policy", "prior_failures", "prior", "ruling", "conflicts", "base", "review_rev", "diff_base", "routes", "lang"]
RETURNED = ["ok", "status", "reason", "mode", "round", "owed", "plan", "fix_plan", "reply", "handoff", "replan", "ripple", "rejects",
            "gave_up", "report"]


class ShapeCase(unittest.TestCase):
    def setUp(self):
        self.doc = base.doc()
        self.steps = kit.load("plan", "steps")
        self.files = sys.modules["src.files"]

    def test_name_inputs_and_return(self):
        self.assertEqual(self.doc["name"], "works-factory-plan")
        self.assertEqual(sorted(self.doc["inputs"]), sorted(PORTS))
        self.assertEqual(len(PORTS), 24)
        self.assertEqual((self.doc["returns"], self.doc["outcome_field"]), ("finish", "ok"))

    def test_return_node_carries_exactly_the_contract(self):
        fmt = base.node("finish")["output_format"]
        self.assertEqual(fmt["required"], RETURNED)
        self.assertEqual(sorted(fmt["properties"]), sorted(RETURNED))
        self.assertIs(fmt["additionalProperties"], False)
        self.assertEqual(fmt["properties"]["status"]["enum"], ["ok", "nothing_owed", "held", "gave_up", "failed"])
        self.assertEqual(fmt["properties"]["mode"]["enum"], ["plan", "replan"])
        for key in ("plan", "ripple"):
            ptr = fmt["properties"][key]
            self.assertEqual((ptr["type"], sorted(ptr["required"])), (["object", "null"], ["path", "run_id", "type"]), key)
        self.assertNotIn("anyOf", repr(fmt))

    def test_ai_roles_are_read_only_and_isolated(self):
        roles = [n for n in base.nodes() if any(k in n for k in scan.ROLE_KINDS)]
        self.assertEqual([n["id"] for n in roles], ["plan-writer", "plan-writer-fix"])
        for n in roles:
            self.assertIs(n["mutates_checkout"], False, n["id"])
            self.assertEqual(n["settingSources"], ["user"], n["id"])
            self.assertEqual(n["sandbox"], {"enabled": True, "allowUnsandboxedCommands": False}, n["id"])
            self.assertEqual(launchgroups.default_of(n["model"])[0], "opus", n["id"])
        writer, fix = roles
        self.assertEqual(writer["allowed_tools"], ["Read", "Grep", "Glob", "WebSearch", "WebFetch"])
        launch = ("model", "allowed_tools", "settingSources", "sandbox", "mutates_checkout", "idle_timeout", "retry")
        self.assertEqual({k: fix[k] for k in launch}, {k: writer[k] for k in launch})

    def test_resubmit_role_continues_the_writer_conversation(self):
        """出し直しの役は修正案の役の後ろの層で、どの層も node 1 つ（Archon は 2 つ以上の層で会話を切る）。輪は会話を続ける"""
        loop = base.node("plan-loop")
        body = {n["id"]: n for n in loop["loop_group"]["nodes"]}
        self.assertEqual(list(body), ["plan-prep", "plan-writer", "plan-fix-prep", "plan-writer-fix", "plan-accept"])
        self.assertIs(loop["loop_group"]["fresh_context"], False)
        self.assertEqual(body["plan-prep"]["with"], {"prev": "$LOOP_PREV.plan-accept.output.ok"})
        self.assertEqual(body["plan-writer"]["when"], "$plan-prep.output.resubmit != true")
        prep = body["plan-fix-prep"]
        self.assertEqual((prep["depends_on"], prep["trigger_rule"]), (["plan-prep", "plan-writer"], "none_failed_min_one_success"))
        fix = body["plan-writer-fix"]
        self.assertEqual(fix["when"], "$plan-prep.output.resubmit == true")
        self.assertEqual(fix["depends_on"], ["plan-prep", "plan-fix-prep"])
        self.assertEqual(fix["prompt"], "$plan-fix-prep.output.prompt")
        accept = body["plan-accept"]
        self.assertEqual((accept["depends_on"], accept["trigger_rule"]), (["plan-writer", "plan-writer-fix"], "none_failed_min_one_success"))
        self.assertEqual((accept["with"]["reply"], accept["with"]["fix_reply"]),
                         ({"from": "$plan-writer.output", "if_skipped": None}, {"from": "$plan-writer-fix.output", "if_skipped": None}))
        # 層: 各 node の層の深さを依存から数え、続きの役の層が node 1 つ
        depth = {}
        for nid, n in body.items():
            depth[nid] = 1 + max([depth[d] for d in n.get("depends_on", []) if d in depth] or [0])
        layers = list(depth.values())
        self.assertEqual(len(layers), len(set(layers)), depth)

    def test_loop_variable_only_in_plan_prep_and_inputs_only_where_allowed(self):
        users = [n["id"] for n in base.nodes() if "$LOOP_PREV" in repr(n.get("with"))]
        self.assertEqual(users, ["plan-prep"])
        readers = {p.stem for p in (BLOCK / "scripts").glob("*.py") if "INPUTS_" in p.read_text(encoding="utf-8")}
        self.assertEqual(readers, {"intake", "plan_prep", "plan_accept"})

    def test_resubmit_schema_is_the_writer_schema(self):
        """#832: 出し直しの役の型は 1 回目の役と同じ。根の欄 plan は型でなく受け付けが要り、出し直しの役だけの whole_plan も型に在る"""
        first, fix = base.node("plan-writer")["output_format"], base.node("plan-writer-fix")["output_format"]
        self.assertEqual(fix, first)
        self.assertEqual(first["required"], [])
        self.assertEqual(self.files.REQUIRED, ("plan",))
        self.assertEqual(first["properties"][self.steps.WHOLE_PLAN], {"type": "boolean"})

    def test_ai_deadlines_are_twenty_days_and_others_have_none(self):
        for n in base.nodes():
            self.assertNotIn("timeout", n, n["id"])
            if "prompt" in n:
                self.assertEqual(n.get("idle_timeout"), NO_DEADLINE, n["id"])

    def test_loop_gives_up_in_the_body_before_max_iterations(self):
        lg = base.node("plan-loop")["loop_group"]
        self.assertEqual(lg["max_iterations"], rolekit.NET_AFTER)
        self.assertEqual(lg["until_bash"], 'done=$plan-accept.output.done; test "$done" = true')

    def test_writer_output_carries_works_fields_and_gate_marks(self):
        fmt = base.node("plan-writer")["output_format"]
        row = fmt["properties"]["plan"]["items"]
        self.assertIn("structure", row["properties"])
        self.assertEqual(row["properties"]["unit_keys"]["items"]["type"], ["integer", "string"])
        marks = row["properties"]["narrows"]["items"]["properties"]
        self.assertLessEqual({"decided_by", "undecided_because", "fences", "world", "recommend", "no_narrow"}, set(marks))
        self.assertNotIn("description", fmt)

    def test_writer_files_schema_is_the_planmarks_owner(self):
        row = base.node("plan-writer")["output_format"]["properties"]["plan"]["items"]
        self.assertEqual(row["properties"]["files"], planmarks.FILES_SCHEMA)
        self.assertEqual(row["properties"][planmarks.DEPENDS_KEY], planmarks.FIELD_SCHEMA[planmarks.DEPENDS_KEY])
        self.assertNotIn("adds", row["properties"])
        self.assertNotIn("removes", row["properties"])
        self.assertIn("files", row["required"])
        self.assertNotIn(planmarks.DEPENDS_KEY, row["required"], "依存は任意の欄")
        fix = base.node("plan-writer-fix")["output_format"]["properties"]["plan"]["items"]
        self.assertEqual(fix["properties"]["files"], planmarks.FILES_SCHEMA)

    def test_plan_fields_port_names_the_planmarks_row_shape(self):
        """盤面の控えの port の宣言 shared:plan-fields.schema.json の fields の行は、planmarks が型を引く形のファイル 1 つを名指す
        （#851 の落ちるはずの所の 4 番。写しを 2 つ置かない）。型に外れた行は読み手の照らしで落ちる"""
        gate = kit._gate()
        shape = json.loads((kit.SHARED / "schemas" / "plan-fields.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(gate.form_of(shape["properties"]["fields"]["items"].get("description")),
                         ("json", f"lib:{planmarks.ROW_SCHEMA_FILE}"))
        row = {"route": "tdd", "tests": [], "rewrite_tests": [], "refactor": {"declared": False, "why": ""},
               "allowed_paths": ["src/a.py"], "out_of_scope": []}
        self.assertEqual(gate.shape_errors({"round": 1, "fields": [row]}, "shared:plan-fields.schema.json"), [])
        for key, bad in (("route", "maybe"), ("allowed_paths", []), ("tests", [{"id": "t.py::x"}])):
            with self.subTest(key=key):
                self.assertNotEqual(gate.shape_errors({"round": 1, "fields": [{**row, key: bad}]}, "shared:plan-fields.schema.json"), [])

    def test_role_schemas_match_their_lib_owners(self):
        def bare(schema):
            if isinstance(schema, dict):
                return {k: bare(v) for k, v in schema.items() if not (k in ("note", "description") and isinstance(v, str))}
            return [bare(v) for v in schema] if isinstance(schema, list) else schema

        fmt = base.node("plan-writer")["output_format"]["properties"]
        row = fmt["plan"]["items"]["properties"]
        for key, want in planmarks.FIELD_SCHEMA.items():
            self.assertEqual(row[key], want, key)
        self.assertEqual(set(fmt["plan"]["items"]["required"]), set(planmarks.CORE_KEYS + planmarks.REQUIRED))
        self.assertIn(gatemarks.NO_NARROW, row["narrows"]["items"]["required"])
        marks = row["narrows"]["items"]["properties"]
        for key in gatemarks.FIELDS:
            self.assertEqual(marks[key], bare(gatemarks.MARK_SCHEMA[key]), key)
        self.assertEqual(marks[gatemarks.NO_NARROW], bare(gatemarks.NO_NARROW_SCHEMA))
        self.assertEqual(fmt[converge.ANSWERS], converge.ANSWER_SCHEMA)
        self.assertEqual(fmt[handoff.FIELD], handoff.SCHEMA)
        self.assertNotIn(handoff.FIELD, self.files.REQUIRED, "引き継ぎのメモは任意の欄")
        self.assertEqual(base.node("plan-writer-fix")["output_format"]["properties"][handoff.FIELD], handoff.SCHEMA)

    def test_scripts_are_read_only_uv_scripts(self):
        for n in base.nodes():
            if "script" in n:
                self.assertIs(n.get("mutates_checkout"), False, n["id"])
                text = (BLOCK / "scripts" / f"{n['script']}.py").read_text(encoding="utf-8")
                self.assertTrue(text.startswith("# /// script\n"), n["script"])
                self.assertIn("sys.dont_write_bytecode = True", text, n["script"])

    def test_script_names_differ_from_lib_modules(self):
        lib = {p.stem for p in (kit.ROOT / "lib").glob("*.py")}
        mine = {p.stem for p in (BLOCK / "scripts").glob("*.py")}
        self.assertEqual(mine & lib, set())
        self.assertEqual(mine, {n["script"] for n in base.nodes() if "script" in n})

    def test_file_names_match_their_lib_owners(self):
        """標準ライブラリだけの落ちない道が書く名は、lib の持ち主と同じ字"""
        f = self.files
        self.assertEqual(f.REJECTS, rolekit.rejects_path(pathlib.Path(), f.ROLE).name)
        self.assertEqual(f.CANDIDATE, rolekit.candidate_path(pathlib.Path(), f.ROLE).name)
        self.assertEqual((f.FIELDS, f.TRACE), (planmarks.FIELDS_FILE, planmarks.TRACE_FILE))
        self.assertEqual(f.HANDOFF, handoff.path_of(pathlib.Path()).name)
        self.assertEqual(f.REPLAN, replan.TRIP_FILE)
        self.assertEqual(f.PRIOR_FAILURES_IN, carry.PRIOR_IN_FILE)

    def test_prompts_do_not_say_started_in_a_new_conversation(self):
        """出し直しで続く役の指示に『新しい会話で起きた』と書かない（断片 handoff の『次の周の自分』は別の会話の話で数えない）"""
        for name in ("plan-writer", "plan-writer-fix"):
            text = (BLOCK / "prompts" / f"{name}.md").read_text(encoding="utf-8")
            self.assertNotIn("started in a new conversation", text, name)

    def test_whole_plan_field_is_named_by_the_resubmit_prompt(self):
        text = (BLOCK / "prompts" / "plan-writer-fix.md").read_text(encoding="utf-8")
        self.assertIn("{" + self.steps.WHOLE_PLAN + "}", text)
        self.assertEqual(re.findall(r"\{[a-z_]+\}", text).count("{whole_plan}"), 1)


class RecommendShapeCase(unittest.TestCase):
    """lib/tests/test_gate_drafts.py の SchemaCase にあった、役の頭の文の試験 2 本（#765 の組み込みで lib の試験から外れた物）の plan の分。
    元の gatemarks.HEAD["p2.fix_plan"]（役の頭の文）に当たるのは、この block では plan-writer の md"""

    def setUp(self):
        self.steps = kit.load("plan", "steps")
        self.md = (BLOCK / "prompts" / "plan-writer.md").read_text(encoding="utf-8")

    def test_rule_text_asks_for_recommend(self):
        """元 test_rule_text_asks_for_recommend: 修正案の役の指示が、人に回す行の推しの欄を求める"""
        self.assertIn(f"write {gatemarks.RECOMMEND} = the one answer you recommend", self.md)

    def test_shape_text_is_built_from_the_keys(self):
        """元 test_shape_text_is_built_from_the_keys の役の頭と受け付けの拒みの 2 つ: 役への指示が書かせる推しの形（欄の名・答え・字の下限）が
        lib の持ち主の欄と語と下限に揃い、拒みの文は持ち主の 1 つの文 RECOMMEND_SHAPE を持つ"""
        shape = gatemarks.RECOMMEND_SHAPE
        for word in (*gatemarks.RECOMMEND_KEYS, *gatemarks.RECOMMEND_ANSWERS, f"{gatemarks.RECOMMEND_MIN} characters or more"):
            self.assertIn(word, self.md)
        self.assertIn(shape, self.steps.RECOMMEND_REJECT)
        self.assertFalse(hasattr(gatemarks, "RECOMMEND_REJECT"))


if __name__ == "__main__":
    unittest.main()

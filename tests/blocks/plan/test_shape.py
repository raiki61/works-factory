"""plan の block の形（docs/design/plan.md の 9.2）: 役の返答の型と port の型が lib の持ち主と同じ・輪の上限が受け付けの網の回。
元の test_plan.py の ShapeCase から。YAML の形の残り（役の起こし方・層・script）は tests/layers と tests/workflows の全体の検査が見る。"""
import json
import sys
import unittest

from tests.blocks import kit
from tests.blocks.plan import base

for _path in (kit.ROOT / "lib" / "graphloops", kit.ROOT / "lib"):
    if str(_path) not in sys.path:
        sys.path.append(str(_path))

import converge  # noqa: E402
import gatemarks  # noqa: E402
import handoff  # noqa: E402
import planmarks  # noqa: E402
import rolekit  # noqa: E402


class ShapeCase(unittest.TestCase):
    def setUp(self):
        kit.load("plan", "steps")
        self.files = sys.modules["src.files"]

    def test_loop_gives_up_in_the_body_before_max_iterations(self):
        lg = base.node("plan-loop")["loop_group"]
        self.assertEqual(lg["max_iterations"], rolekit.NET_AFTER)
        self.assertEqual(lg["until_bash"], 'done=$plan-accept.output.done; test "$done" = true')

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


if __name__ == "__main__":
    unittest.main()

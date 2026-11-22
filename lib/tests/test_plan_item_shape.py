"""計画の項目の型（converge.PlanItem・ItemState）が、形の正本 plan-converge.schema.json の欄と同じ鍵を持つことと、
作り手（plan_rows・_item_states）が型の必須の鍵を全部置くことを照らす。型は注記で実行時の値は dict のまま（json の読み書きは変わらない）"""
import json
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import converge  # noqa: E402

SCHEMA = pathlib.Path(__file__).resolve().parents[2] / "workflows/.shared/schemas/plan-converge.schema.json"


class PlanItemShape(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_plan_item_keys_match_schema(self):
        props = self.schema["properties"]["plan"]["items"]["properties"]
        self.assertEqual(set(converge.PlanItem.__annotations__), set(props))

    def test_item_state_keys_match_schema(self):
        props = self.schema["properties"]["passes"]["items"]["properties"]["items"]["items"]["properties"]
        self.assertEqual(set(converge.ItemState.__annotations__), set(props))

    def test_builders_set_the_always_keys(self):
        plan = converge.plan_rows([{"unit_keys": ["a", "b"], "approach": "x"}], marks=[[{"world": "w"}]])
        self.assertEqual(set(plan[0]), {"id", "unit_keys", "hash", "row", converge.PLAN_MARKS})
        state = converge._item_states(plan, [], {}, [], set())
        self.assertEqual(set(state[0]), {"n", "id", "unit_keys", "hash", "state", "blocks", "reopened", "row"})
        self.assertIsInstance(state[0], dict)


if __name__ == "__main__":
    unittest.main()

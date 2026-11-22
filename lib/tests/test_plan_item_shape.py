"""計画の項目の型（converge.PlanItem・ItemState）が、形の正本 plan-converge.schema.json の欄と同じ鍵を持つことと、
作り手（plan_rows・_item_states）が型の必須の鍵を全部置くことを照らす。型は注記で実行時の値は dict のまま（json の読み書きは変わらない）。
必須の鍵の組は型の `__required_keys__` から取る（試験に鍵の一覧を写さない）。作り手を照らす関数 `missing_required` は、line の block が
持つ写し（workflows/line/src/rounds.py の _item_states）にも tests/blocks/line/test_rounds.py から同じ関数で当てる"""
import json
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import converge  # noqa: E402

SCHEMA = pathlib.Path(__file__).resolve().parents[2] / "workflows/.shared/schemas/plan-converge.schema.json"


def missing_required(td, row: dict) -> set:
    """型 td の必須の鍵のうち、作り手が作った row に無い物（空なら置いている）。型に無い鍵を置いていても不足にしない"""
    return set(td.__required_keys__) - set(row)


def undeclared(td, row: dict) -> set:
    """作り手が作った row の鍵のうち、型（必須と任意）に無い物"""
    return set(row) - set(td.__annotations__)


class PlanItemShape(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_plan_item_keys_match_schema(self):
        props = self.schema["properties"]["plan"]["items"]["properties"]
        self.assertEqual(set(converge.PlanItem.__annotations__), set(props))

    def test_item_state_keys_match_schema(self):
        props = self.schema["properties"]["passes"]["items"]["properties"]["items"]["items"]["properties"]
        self.assertEqual(set(converge.ItemState.__annotations__), set(props))

    def test_hits_type_matches_schema_array(self):
        props = self.schema["properties"]["passes"]["items"]["properties"]["items"]["items"]["properties"]
        self.assertEqual(props["hits"]["type"], "array")
        self.assertIn("list[", str(converge.ItemState.__annotations__["hits"]))

    def test_required_keys_are_the_always_keys(self):
        self.assertEqual(set(converge.PlanItem.__required_keys__), {"id", "unit_keys", "hash"})
        self.assertEqual(set(converge.ItemState.__required_keys__),
                         {"n", "id", "unit_keys", "hash", "state", "blocks", "reopened"})

    def test_builders_set_the_required_keys(self):
        plan = converge.plan_rows([{"unit_keys": ["a", "b"], "approach": "x"}], marks=[[{"world": "w"}]])
        self.assertEqual(missing_required(converge.PlanItem, plan[0]), set())
        self.assertEqual(undeclared(converge.PlanItem, plan[0]), set())
        state = converge._item_states(plan, [], {}, [], set())
        self.assertEqual(missing_required(converge.ItemState, state[0]), set())
        self.assertEqual(undeclared(converge.ItemState, state[0]), set())
        self.assertIsInstance(state[0], dict)

    def test_check_catches_a_renamed_key(self):
        plan = converge.plan_rows([{"unit_keys": ["a"], "approach": "x"}])
        state = converge._item_states(plan, [], {}, [], set())[0]
        state["status"] = state.pop("state")
        self.assertEqual(missing_required(converge.ItemState, state), {"state"})
        self.assertEqual(undeclared(converge.ItemState, state), {"status"})


if __name__ == "__main__":
    unittest.main()

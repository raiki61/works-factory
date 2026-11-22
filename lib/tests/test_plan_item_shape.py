"""計画の項目の型（converge.PlanItem・ItemState）が、形の正本 plan-converge.schema.json の欄と同じ鍵を持つことと、
作り手（plan_rows・_item_states）が型の必須の鍵を全部置くことを照らす。型は注記で実行時の値は dict のまま（json の読み書きは変わらない）。
必須の鍵の組は型の `__required_keys__` から取る（試験に鍵の一覧を写さない）。作り手を照らす助け（tests/bin/itemshape.py）は、line の block が
持つ写し（workflows/line/src/rounds.py の _item_states）にも tests/blocks/line/test_rounds.py から同じ物で当てる。plan の行の row は必須で、
往復の行の row は plan の行に在れば置く物なので、作り手が row を落とせば dropped_row と鍵の組の突き合わせが赤になる"""
import json
import pathlib
import sys
import typing
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import converge  # noqa: E402
from tests.bin.itemshape import dropped_row, missing_required, undeclared  # noqa: E402

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

    def test_hits_type_matches_schema_array(self):
        props = self.schema["properties"]["passes"]["items"]["properties"]["items"]["items"]["properties"]
        self.assertEqual(props["hits"]["type"], "array")
        hint = typing.get_type_hints(converge.ItemState)["hits"]
        self.assertIs(typing.get_origin(hint), list)

    def test_required_keys_are_what_the_builders_always_set(self):
        """必須の鍵の組は、作り手が（任意の物を持たない入力で）必ず置く鍵の組と一致する。row は plan の行に必ず在り（plan_rows）、往復の行は
        plan の行に row が在れば置く"""
        plan = converge.plan_rows([{"unit_keys": ["a"], "approach": "x"}])
        self.assertEqual(set(plan[0]), set(converge.PlanItem.__required_keys__))
        bare = [{k: v for k, v in plan[0].items() if k != "row"}]
        self.assertEqual(set(converge._item_states(bare, [], {}, [], set())[0]), set(converge.ItemState.__required_keys__))
        self.assertEqual(set(converge._item_states(plan, [], {}, [], set())[0]),
                         set(converge.ItemState.__required_keys__) | {"row"})

    def test_builders_set_the_required_keys(self):
        plan = converge.plan_rows([{"unit_keys": ["a", "b"], "approach": "x"}], marks=[[{"world": "w"}]])
        self.assertEqual(missing_required(converge.PlanItem, plan[0]), set())
        self.assertEqual(undeclared(converge.PlanItem, plan[0]), set())
        state = converge._item_states(plan, [], {}, [], set())
        self.assertEqual(missing_required(converge.ItemState, state[0]), set())
        self.assertEqual(undeclared(converge.ItemState, state[0]), set())
        self.assertEqual(dropped_row(plan, state), [])
        self.assertIsInstance(state[0], dict)

    def test_check_catches_a_dropped_row(self):
        plan = converge.plan_rows([{"unit_keys": ["a"], "approach": "x"}])
        state = converge._item_states(plan, [], {}, [], set())
        del state[0]["row"]
        self.assertEqual(dropped_row(plan, state), [plan[0]["id"]])
        del plan[0]["row"]
        self.assertEqual(missing_required(converge.PlanItem, plan[0]), {"row"})

    def test_check_catches_a_renamed_key(self):
        plan = converge.plan_rows([{"unit_keys": ["a"], "approach": "x"}])
        state = converge._item_states(plan, [], {}, [], set())[0]
        state["status"] = state.pop("state")
        self.assertEqual(missing_required(converge.ItemState, state), {"state"})
        self.assertEqual(undeclared(converge.ItemState, state), {"status"})


if __name__ == "__main__":
    unittest.main()

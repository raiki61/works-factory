"""修正案の narrows を承認ノードの行にする芯（gatemarks.narrow_asks）と、行に 4 つの軸の揃わない訳を付ける所（gatemarks.axis_why）。

計画の審査の block（workflows/plan-review/src/gate.py）と、本線の仕様駆動の道の spec-rounds の 2 か所が使う（docs/design/spec-driven.md の
6.2 の足す node の 8）。芯は値だけを受ける（place も block の入力の口も読まない）ので、ここは値を組んで直に呼ぶ。計画の審査の block の
振る舞いが変わらないことは tests/blocks/plan_review/test_gate.py が照らす。
"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import gatemarks  # noqa: E402

NARROW = {"what": "空の列の mean", "why": "空の列の平均は 0 割りの例外のまま"}
DECIDED = {"decided_by": "https://docs.python.org/3/library/statistics.html の定義", "undecided_because": "", "fences": [],
           "world": "Python 公式の statistics.mean は空の列で例外を投げる"}


def facts(**over) -> gatemarks.AxisFacts:
    """全部の軸が揃う材料（over で 1 つずつ崩す）"""
    base = {"cite_ok": lambda text: "", "world_rows": False, "ups": frozenset(), "dirty": frozenset(), "answered": None,
            "planned": frozenset({"u"})}
    return gatemarks.AxisFacts(**{**base, **over})


def plan(*narrows, units=("u",)) -> list:
    return [{"unit_keys": list(units), "narrows": list(narrows)}]


class NarrowAsksCase(unittest.TestCase):
    def test_rows_have_the_gate_head_and_the_plan_node(self):
        """行は修正案ごとの narrows 1 つに 1 行。字の頭は line の照らし NARROW_HEAD、節は修正案の札、単位は項目の unit_keys"""
        [got] = gatemarks.narrow_asks(plan({**NARROW, **DECIDED}), None, facts())
        self.assertEqual(got["text"], f"修正案 1 が狭める能力: {NARROW['what']}——{NARROW['why']}")
        self.assertTrue(gatemarks.NARROW_HEAD.match(got["text"]))
        self.assertEqual((got["kind"], got["node"], got["units"]), ("regression", gatemarks.NARROW_NODE, ["u"]))
        self.assertEqual((got["decided"], got["why"]), (True, {}))
        self.assertEqual(got["mark"], DECIDED)

    def test_row_without_decided_by_is_not_decided(self):
        """decided_by の無い narrows は decided が偽で、軸 obvious に訳が付く（承認ノードに出る行）"""
        [got] = gatemarks.narrow_asks(plan(dict(NARROW)), None, facts())
        self.assertFalse(got["decided"])
        self.assertEqual(got["why"]["obvious"], [gatemarks.NOT_DECIDED])

    def test_separated_marks_are_joined_onto_the_rows(self):
        """入口が外した決め手の欄（項目の番号 → narrows の番号の並び）を行に重ねて読む"""
        [got] = gatemarks.narrow_asks(plan(dict(NARROW)), [[DECIDED]], facts())
        self.assertEqual((got["decided"], got["mark"]), (True, DECIDED))

    def test_items_that_are_not_objects_are_skipped(self):
        self.assertEqual(gatemarks.narrow_asks([None, {"narrows": ["x"]}], None, facts()), [])
        self.assertEqual(gatemarks.narrow_asks(None, None, facts()), [])

    def test_no_world_rows_and_no_world_or_url_is_not_world(self):
        """世界の解の行の無い run で、行の world も URL の決め手も無い narrows は軸 world が揃わない（今の本線と同じ当たり方）"""
        mark = {**DECIDED, "decided_by": "docs/keep.md:1", "world": ""}
        [got] = gatemarks.narrow_asks(plan({**NARROW, **mark}), None, facts())
        self.assertEqual(got["why"], {"world": [gatemarks.NO_WORLD]})
        [got] = gatemarks.narrow_asks(plan({**NARROW, **mark}), None, facts(world_rows=True))
        self.assertEqual(got["why"], {})


class AxisWhyCase(unittest.TestCase):
    def test_all_axes_are_keys(self):
        self.assertEqual(gatemarks.axis_why(facts(), DECIDED, ["u"]), {axis: [] for axis in gatemarks.AXES})

    def test_cite_problem_is_obvious(self):
        got = gatemarks.axis_why(facts(cite_ok=lambda text: "決め手の出どころが現物に無い"), DECIDED, ["u"])
        self.assertEqual(got["obvious"], ["決め手の出どころが現物に無い"])

    def test_no_standard_row_needs_no_cited_source_or_world(self):
        """decided_by が「定石が見つからなかった」形（NO_STANDARD と探した所）の行は、引ける出どころが無いことが中身なので、出どころが
        無い訳（cite.NO_SOURCE）を軸 obvious に付けず、探した所を世界の解を当たった結果として軸 world も揃える。引いた物が現物に無い
        訳は今どおり付ける"""
        mark = {"decided_by": f"{gatemarks.NO_STANDARD} 公式の文書と主要な OSS を探したが既定は無い", "undecided_because": "", "fences": []}
        got = gatemarks.axis_why(facts(cite_ok=lambda text: gatemarks.cite.NO_SOURCE), mark, ["u"])
        self.assertEqual(got, {axis: [] for axis in gatemarks.AXES})
        got = gatemarks.axis_why(facts(cite_ok=lambda text: "決め手の出どころが現物に無い: x"), mark, ["u"])
        self.assertEqual(got["obvious"], ["決め手の出どころが現物に無い: x"])
        bare = {**mark, "decided_by": gatemarks.NO_STANDARD}
        self.assertEqual(gatemarks.axis_why(facts(), bare, ["u"])["obvious"], [gatemarks.NOT_DECIDED])

    def test_fences_are_overkill(self):
        got = gatemarks.axis_why(facts(), {**DECIDED, "fences": ["irreversible"]}, ["u"])
        self.assertEqual(got["not_overkill"], [gatemarks.FENCED.format(fences="irreversible")])

    def test_route_up_and_dirty_without_answer_are_not_clean(self):
        got = gatemarks.axis_why(facts(ups=frozenset({"u"})), DECIDED, ["u"])
        self.assertEqual(got["clean"], ["構造の目が人に上げた単位（u）に当たる"])
        got = gatemarks.axis_why(facts(dirty=frozenset({"u"}), answered=frozenset()), DECIDED, ["u"])
        self.assertEqual(got["clean"], ["構造の目が汚れると見た単位（u）に修正案の答えが無い"])
        self.assertEqual(gatemarks.axis_why(facts(dirty=frozenset({"u"}), answered=None), DECIDED, ["u"])["clean"], [])
        self.assertEqual(gatemarks.axis_why(facts(dirty=frozenset({"u"}), answered=frozenset({"u"})), DECIDED, ["u"])["clean"], [])

    def test_units_outside_the_plan_are_overkill(self):
        got = gatemarks.axis_why(facts(), DECIDED, ["u", "v"])
        self.assertEqual(got["not_overkill"], ["修正案の単位の外を名指す（v）"])


if __name__ == "__main__":
    unittest.main()

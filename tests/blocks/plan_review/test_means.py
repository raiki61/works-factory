"""頼みの解き方と独立の目の食い違い（計画 means-answers の 3.2。持ち主の決め means-ask）: 事前審査の受け付けが means_departs・
means_drifts を照らし、往復をまたいで積み、外れの行 deviations の source means の行にする。block の script を本当に回す（Flow）。

- means_departs: 計画の外れの行ごとに推しの行が要る（今の返答と往復の記録に積んだ行を合わせて数える）。外れを指さない行は拒む
- means_drifts: 項目 item が follows: true で答えた番号だけ・引用は字のまま・同じ食い違いを穴にも書いた行は拒む。2 往復目の返答に
  無くても積んだ行が残り、plan_quote が今の案の項目から消えれば落ちる
- 指示: means_drifts の段（従うという答えの確かめも）は形 plan だけ、means_departs の段（means-ask）は両方の形と項目の下請けの指示
"""
import json
import tempfile
import unittest

import yaml

from tests.blocks import kit
from tests.blocks.plan_review.test_take import (DESIGN_TEXT, UNIT_CLAMP, UNIT_MEAN, Flow, answer, dump, face, fields, full_map, item,
                                                review, summary, synergy)

BLOCK = "plan-review"
MEANS = ["分母を len(xs) にする", "上限の枝を hi にする"]
WHY = "リポジトリの決まりが別の層に置くと決めているので、頼みの置き場から外して直す"
REC = {"answer": "continue", "note": "計画のまま進めてよい", "why": "リポジトリの決まりに合う"}


def depart(n=1, means="M1", **kw):
    return {"item": n, "means": means, "why": "決まりに合うので計画のまま進めてよい", "recommend": REC, **kw}


def drift(n=2, means="M2", **kw):
    return {"item": n, "means": means, "design_quote": "上限は入口 1 箇所で掛け", "plan_quote": f"項目 {n} の直し",
            "why": "独立設計は上限を入口で掛けるが、計画は頼みどおり各所で直す", "recommend": REC, **kw}


class MeansBase(unittest.TestCase):
    def setUp(self):
        self.flow = Flow(self)
        self.take = kit.load(BLOCK, "take")
        f = self.flow
        f.inputs["means"] = json.dumps(MEANS, ensure_ascii=False)
        f.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2)],
               field_rows=[fields(UNIT_MEAN, structure=[{"means": "M1", "deviation": WHY}]),
                           fields(UNIT_CLAMP, structure=[{"means": "M2", "follows": True}])])

    def prepped(self, **inputs):
        self.flow.intake(**inputs)
        self.flow.prep()

    def means_rows(self, got) -> list:
        return [d for d in got["deviations"] if d.get("source") == "means"]


class MeansCase(MeansBase):
    def test_departure_needs_a_recommendation_and_becomes_a_means_row(self):
        self.prepped()
        got = self.flow.accept(review())
        self.assertFalse(got["ok"])
        self.assertIn("頼みの解き方 M1 からの外れに means_departs の推しの行が無い", got["reason"])
        got = self.flow.accept(review(means_departs=[depart(2, "M1")]))
        self.assertFalse(got["ok"])
        self.assertIn("その頼みの解き方からの外れ（structure の deviation）が無い", got["reason"])
        got = self.flow.accept(review(means_departs=[depart(why="stats.py:3 を見た上で計画のまま進めてよい")]))
        self.assertFalse(got["ok"], "推しの訳は人に聞く文の決まりで照らす")
        self.assertTrue(self.flow.accept(review(means_departs=[depart()]))["ok"])
        rows = self.means_rows(self.flow.finish())
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["item"], 1)
        self.assertTrue(rows[0]["text"].startswith("修正案 1 は頼みの解き方 M1「分母を len(xs) にする」に従わない——"), rows[0]["text"])
        self.assertEqual(rows[0]["mark"]["recommend"], REC)

    def test_follows_only_makes_no_row(self):
        f = self.flow
        f.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2)],
               field_rows=[fields(UNIT_MEAN, structure=[{"means": "M1", "follows": True}]),
                           fields(UNIT_CLAMP, structure=[{"means": "M2", "follows": True}])])
        self.prepped()
        self.assertTrue(f.accept(review())["ok"])
        self.assertEqual(self.means_rows(f.finish()), [])


class PrescriptionCase(unittest.TestCase):
    """判定の処方からの外れ: 計画の structure の {prescription, deviation} の外れごとに推しの行 prescription_departs が要り、外れを指さない
    行は拒む。行が在れば finish の deviations の source prescription の行になる"""
    PRESCRIBED = ["分母を len(xs) にする", "上限の枝を hi にする"]

    def setUp(self):
        self.flow = Flow(self)
        f = self.flow
        f.units[0]["prescriptions"] = self.PRESCRIBED
        f.judgment()
        f.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2)],
               field_rows=[fields(UNIT_MEAN, structure=[{"prescription": UNIT_MEAN, "deviation": WHY}]),
                           fields(UNIT_CLAMP, structure=[{"prescription": UNIT_MEAN, "follows": True}])])
        f.intake()
        f.prep()

    @staticmethod
    def depart(n=1, **kw):
        return {"item": n, "prescription": UNIT_MEAN, "why": "決まりに合うので計画のまま進めてよい", "recommend": REC, **kw}

    def test_the_prompt_asks_for_prescription_departs_only_when_the_plan_departs(self):
        heading = "## Departures from the judgment's prescription"
        self.assertIn(heading, self.flow.prompt())
        f = self.flow
        f.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2)],
               field_rows=[fields(UNIT_MEAN, structure=[{"prescription": UNIT_MEAN, "follows": True}]),
                           fields(UNIT_CLAMP, structure=[{"prescription": UNIT_MEAN, "follows": True}])])
        f.intake()
        self.assertNotIn(heading, f.prompt())

    def test_prescription_departure_needs_a_recommendation_and_becomes_a_prescription_row(self):
        f = self.flow
        got = f.accept(review())
        self.assertFalse(got["ok"], "推しの行が無い返答は拒む")
        self.assertIn("prescription_departs", got["reason"])
        got = f.accept(review(prescription_departs=[self.depart(2)]))
        self.assertFalse(got["ok"], "外れを指さない行は拒む")
        self.assertIn("prescription_departs", got["reason"])
        self.assertTrue(f.accept(review(prescription_departs=[self.depart()]))["ok"])
        done = f.finish()
        rows = [d for d in done["deviations"] if d.get("source") == "prescription"]
        self.assertEqual(len(rows), 1, done["deviations"])
        self.assertEqual(rows[0]["item"], 1)
        self.assertTrue(rows[0]["text"].startswith("修正案 1 は単位"), rows[0]["text"])
        self.assertIn(self.PRESCRIBED[0], rows[0]["text"])
        self.assertEqual(rows[0]["mark"]["recommend"], REC)
        self.assertTrue(rows[0]["why"][0].startswith("①"), rows[0]["why"])
        from engine.schema import validate_schema
        node = next(n for n in yaml.safe_load((kit.BLOCKS / BLOCK / "works-factory-plan-review.yaml").read_text(encoding="utf-8"))["nodes"]
                    if n["id"] == "finish")
        self.assertEqual(validate_schema(done, kit._gate()._expanded(node["output_format"], kit.BLOCKS / BLOCK)), [])


class DriftBase(MeansBase):
    def setUp(self):
        super().setUp()
        self.flow.design()

    def reply(self, *faces, **extra):
        return review(*faces, design_map=full_map(), means_departs=[depart()], **extra)


class DriftCase(DriftBase):
    def test_drift_rows_are_checked(self):
        self.prepped()
        for bad, word in ((drift(1, "M1"), "follows: true で答えていない"), (drift(means="M3"), "頼みの解き方の番号でない"),
                          (drift(design_quote="設計に無い字の並び"), "design_quote"), (drift(plan_quote="案に無い字の並び"), "plan_quote")):
            with self.subTest(word=word):
                got = self.flow.accept(self.reply(means_drifts=[bad]))
                self.assertFalse(got["ok"])
                self.assertIn(word, got["reason"])
        same = face("same-drift-as-face", UNIT_CLAMP, why=f"独立設計との構造の食い違い: 「{DESIGN_TEXT[:12]}」と「項目 2 の直し」が食い違う")
        got = self.flow.accept(self.reply(same, means_drifts=[drift()]))
        self.assertFalse(got["ok"])
        self.assertIn("どちらか 1 つ", got["reason"])

    def test_drift_stacks_across_passes_and_drops_when_the_quote_is_gone(self):
        f = self.flow
        self.prepped()
        self.assertTrue(f.accept(self.reply(means_drifts=[drift()]))["ok"])
        self.assertEqual(len(self.means_rows(f.finish())), 2)
        f.carry()
        f.intake()
        f.prep()
        self.assertTrue(f.accept(review(design_map=full_map()))["ok"], "前の往復の推しと食い違いは書き直さなくてよい")
        rows = self.means_rows(f.finish())
        self.assertEqual(sorted(r["text"][:20] for r in rows), sorted(["修正案 1 は頼みの解き方 M1「分母を", "修正案 2 は頼みの解き方 M2「上限の"]))
        f.carry()
        f.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, approach="上限の枝を hi にして入口で掛ける")], rnd=3,
               field_rows=[fields(UNIT_MEAN, structure=[{"means": "M1", "deviation": WHY}]),
                           fields(UNIT_CLAMP, structure=[{"means": "M2", "follows": True}])])
        f.intake()
        f.prep()
        self.assertTrue(f.accept(review(design_map=full_map()))["ok"])
        self.assertEqual([r["item"] for r in self.means_rows(f.finish())], [1], "plan_quote が案から消えた食い違いは落ちる")

    def test_drift_drops_when_its_item_no_longer_follows(self):
        """項目 2 が M2 から外れ、項目 1 が M2 に従った時、古い行 (2, M2) は落ちる（ほかの項目が同じ番号に従っても残さない）"""
        f = self.flow
        self.prepped()
        self.assertTrue(f.accept(self.reply(means_drifts=[drift()]))["ok"])
        f.carry()
        f.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2)], rnd=2,
               field_rows=[fields(UNIT_MEAN, structure=[{"means": "M1", "deviation": WHY}, {"means": "M2", "follows": True}]),
                           fields(UNIT_CLAMP, structure=[{"means": "M2", "deviation": WHY}])])
        f.intake()
        f.prep()
        self.assertTrue(f.accept(review(design_map=full_map(), means_departs=[depart(2, "M2")]))["ok"])
        rows = self.means_rows(f.finish())
        self.assertFalse([r for r in rows if "独立設計と食い違う" in r["text"]], rows)

    def test_prompts_carry_the_steps_by_form(self):
        f = self.flow
        f.intake()
        text = f.prompt()
        self.assertIn("## The request's means against the independent design", text)
        self.assertIn("Check each follows answer", text)
        self.assertIn("`means_departs`", text)
        self.assertIn("## The request's means and the plan's answers", f.text("review-material-1.md"))

    def test_replan_form_has_the_departs_step_but_not_the_drift_step(self):
        """形 replan（案の直しの事前審査）は means_departs の段だけ（3.4 の 2）。独立設計が立っても means_drifts の段は立たない"""
        import types
        material = kit.load(BLOCK, "material")
        for form, drift_ in (("plan", True), ("replan", False)):
            c = types.SimpleNamespace(intake={"form": form, "means": MEANS}, stands=lambda: "stands")
            with self.subTest(form=form):
                self.assertTrue(material.WHEN["means_ask"](c))
                self.assertEqual(material.WHEN["means_drift"](c), drift_)
        c = types.SimpleNamespace(intake={"form": "plan", "means": []}, stands=lambda: "stands")
        self.assertFalse(material.WHEN["means_ask"](c) or material.WHEN["means_drift"](c))


class TreeMeansCase(DriftBase):
    """木の形: 項目の下請けの means_drifts・means_departs が item_schema を通り、tree_merge の後の返答に在る。ほかの項目の行は拒む"""

    def test_item_answers_carry_means_rows(self):
        tree = kit.load(BLOCK, "tree")
        f = self.flow
        f.intake(tree="on")
        f.prep()
        b = f.view()
        schema = tree.item_schema(b)
        self.assertIn("means_drifts", schema["properties"])
        self.assertIn("means_departs", schema["properties"])
        self.assertEqual(tree._means_item_gaps(2, {"means_drifts": [drift()], "means_departs": [depart(1)]}),
                         ["$.means_departs[0].item: 2 でない（1。項目の下請けは自分の項目の行だけを書く）"])
        brief = f.text("items/brief.md")
        self.assertIn("`means_departs`", brief)
        self.assertIn("## The request's means and the plan's answers", f.text("items/item-1.md"))

    def test_tree_merge_carries_the_item_departs_to_the_deviations(self):
        """木の往復: 項目の下請けの答えの means_departs が tree_merge で返答に並び、受け付けを通り、finish の deviations の source means の
        行に推しが載る（tree_merge が converge.MEANS_AND_PRESCRIPTION_ROWS を並べないと、推しの行が無いと拒まれる）"""
        tree = kit.load(BLOCK, "tree")
        f = self.flow
        f.intake(tree="on")
        f.prep()
        b = f.view()
        maps = {n: [r for r in full_map() if r["item"] == n] for n in (1, 2)}
        rows = {1: answer(1, means_departs=[depart()], design_map=maps[1]), 2: answer(2, design_map=maps[2])}
        for n, row in rows.items():
            path = tree.answer_file(b, n)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(dump(row), encoding="utf-8")
        tree.synergy_file(b).write_text(dump(synergy()), encoding="utf-8")
        got = f.accept(tree=summary({1: [], 2: []}))
        self.assertTrue(got["ok"], got)
        rows = self.means_rows(f.finish())
        self.assertEqual([(r["item"], r["mark"].get("recommend")) for r in rows], [(1, REC)], rows)


class LatestWinsCase(unittest.TestCase):
    """take.stacked は欄ごとの後勝ちの鍵で行を合わせる。欄と鍵の結びは converge の組の並びで位置に決まるので、並べ替えで鍵が別の欄に
    付けば、鍵の最後の欄だけ違う 2 行が 1 行に潰れる"""

    def stacked(self, name, rows):
        take = kit.load(BLOCK, "take")
        with tempfile.TemporaryDirectory() as place:
            return take.stacked(place, {name: rows}, name)

    def test_each_column_keeps_its_own_latest_wins_key(self):
        one, two = "first why", "second why"
        self.assertEqual(self.stacked("means_drifts", [drift(plan_quote="a"), drift(plan_quote="b")]),
                         [drift(plan_quote="a"), drift(plan_quote="b")])
        self.assertEqual(self.stacked("means_departs", [depart(means="M1"), depart(means="M2")]),
                         [depart(means="M1"), depart(means="M2")])
        self.assertEqual(self.stacked("means_departs", [depart(why=one), depart(why=two)]), [depart(why=two)])
        rx = {"item": 1, "why": one, "recommend": REC}
        self.assertEqual(self.stacked("prescription_departs", [{**rx, "prescription": "p1"}, {**rx, "prescription": "p2"}]),
                         [{**rx, "prescription": "p1"}, {**rx, "prescription": "p2"}])
        self.assertEqual(self.stacked("prescription_departs", [{**rx, "prescription": "p1"}, {**rx, "prescription": "p1", "why": two}]),
                         [{**rx, "prescription": "p1", "why": two}])


if __name__ == "__main__":
    unittest.main()

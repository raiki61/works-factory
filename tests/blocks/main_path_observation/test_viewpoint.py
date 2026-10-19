"""観点の宣言 workflows/main-path-observation/src/viewpoint.py のこの観点だけの中身（族の全部に当てる照らしは tests/blocks/materials/）"""
import unittest

from tests.blocks import kit


class ViewpointCase(unittest.TestCase):
    def setUp(self):
        self.vp = kit.load("main-path-observation", "viewpoint")
        self.mk = self.vp.materialkit
        self.empty = self.mk.View(".", "b", "r", "d", (), "c", "", 0)
        self.diffed = self.mk.View(".", "b", "r", "d", ("x.py",), "c", "", 0)

    def test_declaration(self):
        self.assertEqual((self.vp.MATERIALS, self.vp.GUARDED, self.vp.NA, self.vp.NA_PARAGRAPH),
                         (("main_path_observation",), False, "cond", True))
        self.assertEqual(self.vp.NA_REASON, "対象差分は利用者から見える経路・外部との継ぎ目を変えていない")

    def test_due_follows_the_entry_run(self):
        self.assertTrue(self.vp.due(self.empty, {"entry": ""}).run)
        self.assertTrue(self.vp.due(self.diffed, {"entry": "e"}).run, "差分が在れば entry が在っても入口の周でない")
        got = self.vp.due(self.empty, {"entry": "e"})
        self.assertFalse(got.run)
        self.assertIn("主経路の観察", got.why)

    def test_fill_names_the_origin_and_no_request_count(self):
        got = self.vp.fill(self.empty, {"entry": "人の依頼（/p/r.json）"}, self.vp.due(self.empty, {"entry": "e"}))
        self.assertEqual(list(got), ["main_path_observation"])
        self.assertEqual(got["main_path_observation"]["status"], "not_applicable")
        self.assertIn("人の依頼（/p/r.json）", got["main_path_observation"]["reason"])
        self.assertIn("件数は渡されていない", got["main_path_observation"]["reason"])

    def test_condition_always_holds_and_is_never_judged(self):
        self.assertTrue(self.vp.applies(self.diffed, {}).run)
        self.assertEqual(self.vp.applies(self.diffed, {}).why, "差分が利用者から見える経路に触れる")
        self.assertFalse(self.vp.judged_na(self.diffed, {}))

    def test_after_requires_observed_rows_for_seen_statuses(self):
        row = {"path": "p", "value": "v"}
        for st in ("found", "clean"):
            self.assertIn(f"観点 main-path-observation: status={st} なのに観測した値（observed）が 1 つも無い",
                          self.vp.after(None, {}, {"material": {"status": st}, "observed": []}, None))
            self.assertIsNone(self.vp.after(None, {}, {"material": {"status": st}, "observed": [row]}, None))
        for st in ("awaiting_human", "not_run", "not_applicable"):
            self.assertIsNone(self.vp.after(None, {}, {"material": {"status": st}, "observed": []}, None))

    def test_after_survives_a_material_that_is_not_an_object(self):
        self.assertIsNone(self.vp.after(None, {}, {"material": "x", "observed": []}, None))

    def test_material_and_report(self):
        self.assertEqual(self.vp.materials_of({}), {})
        self.assertEqual(self.vp.materials_of({"material": {"status": "clean"}}), {"main_path_observation": {"status": "clean"}})
        self.assertEqual(self.vp.report_lines({"reply": None}), [])
        self.assertEqual(self.vp.report_lines({"reply": {"observed": []}}), [])
        self.assertEqual(self.vp.report_lines({"reply": {"observed": [{"path": "a\nb", "value": "ok"}]}}), ["  - 観測: a b → ok"])


if __name__ == "__main__":
    unittest.main()

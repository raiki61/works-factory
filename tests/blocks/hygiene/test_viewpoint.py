"""観点の宣言 blocks/hygiene/src/viewpoint.py のこの観点だけの中身（族の全部に当てる照らしは tests/blocks/materials/）"""
import unittest

from tests.blocks import kit


class ViewpointCase(unittest.TestCase):
    def setUp(self):
        self.vp = kit.load("hygiene", "viewpoint")
        self.mk = self.vp.materialkit

    def test_declaration(self):
        self.assertEqual((self.vp.MATERIALS, self.vp.GUARDED, self.vp.NA, self.vp.NA_PARAGRAPH),
                         (("hygiene",), True, "never", False))

    def test_never_viewpoint_does_not_answer_applies(self):
        with self.assertRaises(NotImplementedError):
            self.vp.applies(None, {})
        self.assertFalse(self.vp.judged_na(None, {}))

    def test_due_follows_the_entry_run(self):
        empty = self.mk.View(".", "b", "r", "d", (), "c", "", 0)
        diffed = self.mk.View(".", "b", "r", "d", ("x.py",), "c", "", 0)
        self.assertTrue(self.vp.due(empty, {"entry": ""}).run)
        self.assertFalse(self.vp.due(empty, {"entry": "人の依頼（x）"}).run)
        self.assertTrue(self.vp.due(diffed, {"entry": "人の依頼（x）"}).run, "差分の在る run は入口の周でない")
        fill = self.vp.fill(empty, {"entry": "人の依頼（x）"}, self.vp.due(empty, {"entry": "人の依頼（x）"}))
        self.assertEqual(list(fill), ["hygiene"])
        self.assertEqual(fill["hygiene"]["status"], "not_applicable")
        self.assertIn("人の依頼（x）", fill["hygiene"]["reason"])
        self.assertEqual(self.mk.fill_problems(self.vp, fill), [])

    def test_material_is_made_from_the_reply(self):
        self.assertEqual(self.vp.materials_of({"findings": [], "seen": "差分の全部"}),
                         {"hygiene": {"status": "clean", "checked": "差分の全部"}})
        got = self.vp.materials_of({"findings": [{"where": "a.py:3", "text": "閉じ忘れ"}], "seen": "a.py"})
        self.assertEqual(got, {"hygiene": {"status": "found", "checked": "a.py", "count": 1, "detail": "a.py:3: 閉じ忘れ"}})
        self.assertEqual(self.vp.report_lines({"reply": None}), [])


if __name__ == "__main__":
    unittest.main()

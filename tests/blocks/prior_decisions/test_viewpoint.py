"""観点の宣言 blocks/prior-decisions/src/viewpoint.py が docs/design/materials.md の 5.1 の名を全部持つ（共通の口が既定で埋めない）"""
import unittest

from tests.blocks import kit

NAMES = ("NAME", "MATERIALS", "GUARDED", "NA", "NA_REASON", "NA_PARAGRAPH", "due", "fill", "applies", "judged_na", "values",
         "when", "before", "after", "after_accept", "materials_of", "report_lines")


class ViewpointCase(unittest.TestCase):
    def setUp(self):
        self.vp = kit.load("prior-decisions", "viewpoint")
        self.mk = self.vp.materialkit

    def test_declares_every_name(self):
        for name in NAMES:
            with self.subTest(name=name):
                self.assertTrue(hasattr(self.vp, name))
        self.assertEqual(self.vp.NAME, "prior-decisions")
        self.assertTrue(set(self.vp.MATERIALS) <= set(self.mk.MATERIALS))
        self.assertIn(self.vp.NA, ("never", "cond"))

    def test_never_viewpoint_does_not_answer_applies_or_fill(self):
        with self.assertRaises(NotImplementedError):
            self.vp.applies(None, {})
        with self.assertRaises(NotImplementedError):
            self.vp.fill(None, {}, self.vp.due(None, {}))
        self.assertTrue(self.vp.due(None, {}).run)
        self.assertFalse(self.vp.judged_na(None, {}))

    def test_request_wheres_and_material(self):
        rows = [{"where": "a", "text": "x"}, {"where": 3, "text": "y"}]
        self.assertEqual(self.vp.request_wheres({"entry": "", "request": rows}), [])
        self.assertEqual(self.vp.request_wheres({"entry": "e", "request": rows}), ["a"])
        self.assertEqual(self.vp.request_wheres({"entry": "e", "request": {"findings": rows}}), ["a"])
        self.assertEqual(self.vp.materials_of({}), {})
        self.assertEqual(self.vp.report_lines({"reply": None}), [])
        self.assertEqual(self.vp.report_lines({"reply": {"settled": [{"topic": "t"}]}}), ["  - 決着済みの論点: t（書いてある所の記録が無い）"])


if __name__ == "__main__":
    unittest.main()

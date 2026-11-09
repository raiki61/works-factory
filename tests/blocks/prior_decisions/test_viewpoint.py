"""観点の宣言 workflows/prior-decisions/src/viewpoint.py のこの観点だけの中身（族の全部に当てる照らしは tests/blocks/materials/）"""
import unittest

from tests.blocks import kit


class ViewpointCase(unittest.TestCase):
    def setUp(self):
        self.vp = kit.load("prior-decisions", "viewpoint")
        self.mk = self.vp.materialkit

    def test_never_viewpoint_does_not_answer_applies_or_fill(self):
        with self.assertRaises(NotImplementedError):
            self.vp.applies(None, {})
        with self.assertRaises(NotImplementedError):
            self.vp.fill(None, {}, self.vp.due(None, {}))
        self.assertTrue(self.vp.due(None, {}).run)
        self.assertFalse(self.vp.judged_na(None, {}))

    def test_request_lines_and_material(self):
        rows = [{"where": "a", "text": "x"}, {"where": 3, "text": "y"}]
        empty = self.mk.View(".", "b", "r", "d", (), "c", "", 0)
        diffed = self.mk.View(".", "b", "r", "d", ("x.py",), "c", "", 0)
        self.assertEqual(self.vp.request_lines(empty, {"entry": "", "request": rows}), [])
        self.assertEqual(self.vp.request_lines(empty, {"entry": "e", "request": rows}), [{"where": "a", "text": "x"}])
        self.assertEqual(self.vp.request_lines(diffed, {"entry": "e", "request": rows}), [])
        self.assertEqual(self.vp.request_lines(empty, {"entry": "e", "request": {"findings": rows}}), [{"where": "a", "text": "x"}])
        self.assertEqual(self.vp.materials_of({}), {})


if __name__ == "__main__":
    unittest.main()

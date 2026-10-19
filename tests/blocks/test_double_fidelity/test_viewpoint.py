"""観点の宣言 blocks/test-double-fidelity/src/viewpoint.py のこの観点だけの中身（族の全部に当てる照らしは tests/blocks/materials/）"""
import unittest

from tests.blocks import kit


class ViewpointCase(unittest.TestCase):
    def setUp(self):
        self.vp = kit.load("test-double-fidelity", "viewpoint")
        self.mk = self.vp.materialkit

    def test_declaration(self):
        self.assertEqual((self.vp.MATERIALS, self.vp.GUARDED, self.vp.NA, self.vp.NA_PARAGRAPH),
                         (("test_double_fidelity",), False, "cond", True))

    def test_due_and_fill(self):
        empty = self.mk.View(".", "b", "r", "d", (), "c", "", 0)
        changed = self.mk.View(".", "b", "r", "d", ("a.py",), "c", "", 0)
        self.assertTrue(self.vp.due(empty, {"entry": ""}).run)
        self.assertFalse(self.vp.due(empty, {"entry": "人の依頼"}).run)
        self.assertTrue(self.vp.due(changed, {"entry": "人の依頼"}).run)   # 修正が入って差分が出来た run は入口の周でない
        filled = self.vp.fill(empty, {"entry": "人の依頼"}, self.vp.due(empty, {"entry": "人の依頼"}))
        self.assertEqual(filled["test_double_fidelity"]["status"], "not_applicable")
        self.assertIn("人の依頼", filled["test_double_fidelity"]["reason"])
        self.assertIn("件数は渡されていない", filled["test_double_fidelity"]["reason"])

    def test_condition_always_holds_and_role_never_judges(self):
        self.assertTrue(self.vp.applies(None, {}).run)
        self.assertFalse(self.vp.judged_na(None, {}))

    def test_materials_and_report(self):
        self.assertEqual(self.vp.materials_of({}), {})
        self.assertEqual(self.vp.materials_of({"material": {"status": "clean"}}), {"test_double_fidelity": {"status": "clean"}})
        self.assertEqual(self.vp.report_lines({"reply": None}), [])
        rows = [{"where": "a.py:3", "text": "形が\n違う"}, {"where": "b.py:1", "text": "x"}]
        self.assertEqual(self.vp.report_lines({"reply": {"mismatches": rows}}),
                         ["  - 代役の不一致: 形が 違う（a.py:3）", "  - 代役の不一致: x（b.py:1）"])


if __name__ == "__main__":
    unittest.main()

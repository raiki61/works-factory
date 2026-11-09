"""観点の宣言 workflows/provenance/src/viewpoint.py のこの観点だけの中身（族の全部に当てる照らしは tests/blocks/materials/）"""
import types
import unittest

from tests.blocks import kit


class ViewpointCase(unittest.TestCase):
    def setUp(self):
        self.vp = kit.load("provenance", "viewpoint")
        self.mk = self.vp.materialkit

    def test_entry_with_empty_diff_is_not_due(self):
        view = types.SimpleNamespace(empty=True)
        self.assertTrue(self.vp.due(view, {"entry": ""}).run)
        got = self.vp.due(view, {"entry": "人の依頼"})
        self.assertEqual((got.run, got.why), (False, self.mk.entry_skip("出典の確かめ").why))
        self.assertEqual(self.vp.fill(view, {"entry": "人の依頼"}, got), {"provenance": self.mk.fill_entry("人の依頼", None)})
        with self.assertRaises(NotImplementedError):
            self.vp.applies(None, {})
        self.assertFalse(self.vp.judged_na(None, {}))

    def test_entry_with_diff_is_due(self):
        """修正が入った後に古い entry が渡されても、入口の周と取り違えない"""
        got = self.vp.due(types.SimpleNamespace(empty=False), {"entry": "人の依頼"})
        self.assertTrue(got.run)

    def test_material(self):
        self.assertEqual(self.vp.materials_of({}), {})
        self.assertEqual(self.vp.materials_of({"material": {"status": "clean"}}), {"provenance": {"status": "clean"}})
        self.assertEqual(self.vp.when(None, {}), {"spawns": False})


if __name__ == "__main__":
    unittest.main()

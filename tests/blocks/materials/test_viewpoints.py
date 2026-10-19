"""素材の観点の族の全部の block（src/viewpoint.py を持つ block）に当てる yes/no（docs/design/materials.md の 5.1・8 節）。

新しい観点の block は、ここに何も足さずにこの照らしを受ける:
- 宣言は 5.1 の名を全部持つ（共通の口が既定で埋めない）。NAME は block のフォルダの名で、AI の node の id でもある
- MATERIALS は materialkit.MATERIALS の中の名
- GUARDED は、AI の node が mutates_checkout: false を持つか と同じ（作業ツリーの照らしの欄を実行基盤の照らしと合わせる。
  今の tests/workflows/test_nodeflags.py の status_guarded の照らしの block 版）
- NA は never か cond。never なら applies は NotImplementedError を上げる
"""
import unittest

import yaml

from tests.blocks import kit

NAMES = ("NAME", "MATERIALS", "GUARDED", "NA", "NA_REASON", "NA_PARAGRAPH", "due", "fill", "applies", "judged_na", "values",
         "when", "before", "after", "after_accept", "materials_of", "report_lines")
VIEWPOINTS = sorted(p.parents[1].name for p in kit.BLOCKS.glob("*/src/viewpoint.py"))


def ai_node(block: str, nid: str) -> dict:
    doc = yaml.safe_load((kit.BLOCKS / block / f"works-factory-{block}.yaml").read_text(encoding="utf-8"))
    nodes = [n for top in doc["nodes"] for n in [top, *((top.get("loop_group") or {}).get("nodes") or [])]]
    return next(n for n in nodes if n["id"] == nid and "prompt" in n)


class ViewpointsCase(unittest.TestCase):
    def test_there_is_a_viewpoint(self):
        self.assertIn("prior-decisions", VIEWPOINTS)

    def test_every_viewpoint_holds_the_declaration(self):
        for block in VIEWPOINTS:
            with self.subTest(block=block):
                vp = kit.load(block, "viewpoint")
                self.assertEqual([n for n in NAMES if not hasattr(vp, n)], [])
                self.assertEqual(vp.NAME, block)
                self.assertTrue(set(vp.MATERIALS) <= set(vp.materialkit.MATERIALS), vp.MATERIALS)
                self.assertIn(vp.NA, ("never", "cond"))
                self.assertIsInstance(vp.NA_PARAGRAPH, bool)
                if vp.NA == "never":
                    self.assertEqual(vp.NA_REASON, "")
                    with self.assertRaises(NotImplementedError):
                        vp.applies(None, {})

    def test_guarded_matches_the_role_node(self):
        for block in VIEWPOINTS:
            with self.subTest(block=block):
                vp = kit.load(block, "viewpoint")
                self.assertIs(vp.GUARDED, ai_node(block, vp.NAME).get("mutates_checkout") is False)


if __name__ == "__main__":
    unittest.main()

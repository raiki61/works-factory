"""観点の宣言 blocks/external-standards/src/viewpoint.py のこの観点だけの中身（族の全部に当てる照らしは tests/blocks/materials/）"""
import unittest

from tests.blocks import kit


class ViewpointCase(unittest.TestCase):
    def setUp(self):
        self.vp = kit.load("external-standards", "viewpoint")
        self.mk = self.vp.materialkit
        self.view = self.mk.View(".", "b", "r", "d", ("x.py",), "c", "", 0)

    def test_declaration(self):
        self.assertEqual((self.vp.MATERIALS, self.vp.GUARDED, self.vp.NA, self.vp.NA_PARAGRAPH),
                         (("external_standards",), False, "never", True))

    def test_never_viewpoint_does_not_answer_applies(self):
        with self.assertRaises(NotImplementedError):
            self.vp.applies(None, {})
        self.assertFalse(self.vp.judged_na(None, {}))

    def test_due_follows_the_entry_port_only(self):
        self.assertTrue(self.vp.due(self.view, {"entry": ""}).run)
        got = self.vp.due(self.view, {"entry": "人の依頼（x）"})
        self.assertFalse(got.run, "差分が在っても entry に字が在れば判定から入る run")
        self.assertEqual(self.vp.fill(self.view, {"entry": "人の依頼（x）"}, got),
                         {"external_standards": self.mk.fill_entry("人の依頼（x）", None)})
        self.assertIn("件数は渡されていない", self.vp.fill(self.view, {"entry": "e"}, got)["external_standards"]["reason"])

    def test_values_and_paragraphs_follow_purpose_and_repo_review(self):
        purpose = {"purpose_text": "目的", "source": "①PR 説明", "known_weaknesses": ["弱点"], "source_files": []}
        view = self.mk.View(str(kit.ROOT), "b", "r", "d", ("x.py",), "c", "", 0)
        got = self.vp.values(view, {"purpose": purpose})
        self.assertEqual((got["purpose_text"], got["known_weaknesses"]), ("目的", '[\n "弱点"\n]'))
        self.assertEqual(got["standards_section"], "外部標準照合観点")
        self.assertNotIn("repo_review_md", got, "対象の根に REVIEW.md が無ければ値を渡さない")
        self.assertEqual(self.vp.when(view, {"purpose": purpose}), {"spawns": False, "purpose": True, "repo_review": False})
        bare = self.vp.values(view, {"purpose": None})
        self.assertNotIn("purpose_text", bare)
        self.assertFalse(self.vp.when(view, {"purpose": None})["purpose"])

    def test_materials_and_report_lines(self):
        self.assertEqual(self.vp.materials_of({}), {})
        self.assertEqual(self.vp.materials_of({"material": {"status": "clean"}}), {"external_standards": {"status": "clean"}})
        self.assertEqual(self.vp.report_lines({"reply": None}), [])
        rows = [{"problem": "p q r s", "ranked": ["a", "b"], "diff_at": "b"}]
        self.assertEqual(self.vp.report_lines({"reply": {"rankings": rows}}), ["  - 順位: p q r s——差分は 2 位／2 位中（b）"])
        self.assertEqual(self.vp.report_lines({"reply": {"rankings": [], "rankings_none": "定番解なし"}}),
                         ["  - 順位: 付けられる問題なし（定番解なし）"])

    def test_section_names_are_headings_of_the_source_of_truth(self):
        heads = [line[3:] for line in (kit.ROOT / "lib" / "REVIEW.md").read_text(encoding="utf-8").splitlines() if line.startswith("## ")]
        for name in (self.vp.STANDARDS_SECTION, self.vp.CRITERIA_SECTION):
            with self.subTest(name=name):
                self.assertTrue(any(h.startswith(name) for h in heads), name)


if __name__ == "__main__":
    unittest.main()

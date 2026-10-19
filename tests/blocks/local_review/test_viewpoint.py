"""観点の宣言 blocks/local-review/src/viewpoint.py のこの観点だけの中身（族の全部に当てる照らしは tests/blocks/materials/）"""
import unittest

from tests.blocks import kit


class ViewpointCase(unittest.TestCase):
    def setUp(self):
        self.vp = kit.load("local-review", "viewpoint")
        self.mk = self.vp.materialkit
        self.view = self.mk.View(".", "b", "r", "/d/diff.patch", ("x.py",), "/d/changed.txt", "", 1)

    def test_declaration(self):
        self.assertEqual((self.vp.MATERIALS, self.vp.GUARDED, self.vp.NA, self.vp.NA_REASON, self.vp.NA_PARAGRAPH),
                         (("local_review",), False, "never", "", True))

    def test_never_viewpoint_does_not_answer_applies(self):
        with self.assertRaises(NotImplementedError):
            self.vp.applies(self.view, {})
        self.assertFalse(self.vp.judged_na(self.view, {}))

    def test_due_follows_the_entry_run_rule(self):
        """判定から入る run（entry が空でなく差分が空）だけ回さず、素材を fill_entry の字で埋める。差分が在れば entry が在っても通常の run"""
        with_diff = self.view
        empty = self.mk.View(".", "b", "r", "/d/diff.patch", (), "/d/changed.txt", "", 0)
        self.assertEqual(self.vp.due(with_diff, {"entry": ""}), self.mk.normal_run("P1 の役"))
        self.assertEqual(self.vp.due(empty, {"entry": ""}), self.mk.normal_run("P1 の役"))
        self.assertEqual(self.vp.due(with_diff, {"entry": "人の依頼（x）"}), self.mk.normal_run("P1 の役"))
        entry = self.vp.due(empty, {"entry": "人の依頼（x）"})
        self.assertEqual(entry, self.mk.entry_skip("P1 の役"))
        self.assertEqual(self.vp.fill(empty, {"entry": "人の依頼（x）"}, entry),
                         {"local_review": self.mk.fill_entry("人の依頼（x）", None)})

    def test_values_and_when(self):
        got = self.vp.values(self.view, {})
        self.assertEqual(set(got), {"diff_file", "base", "changed_files_file", "review_md", "repo_review_md", "skills", "unattended"})
        self.assertEqual((got["diff_file"], got["base"], got["changed_files_file"]), ("/d/diff.patch", "b", "/d/changed.txt"))
        self.assertEqual(got["repo_review_md"], "", "対象の根に REVIEW.md が無い")
        self.assertEqual(self.vp.when(self.view, {}), {"spawns": True, "repo_review": False})

    def test_materials_and_report_lines(self):
        self.assertEqual(self.vp.materials_of({}), {})
        self.assertEqual(self.vp.materials_of({"material": {"status": "clean"}}), {"local_review": {"status": "clean"}})
        self.assertEqual(self.vp.report_lines({"reply": None}), [])
        self.assertEqual(self.vp.report_lines({"reply": {"findings": []}}), [])


if __name__ == "__main__":
    unittest.main()

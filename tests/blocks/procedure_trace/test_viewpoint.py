"""観点の宣言 workflows/procedure-trace/src/viewpoint.py のこの観点だけの中身（族の全部に当てる照らしは tests/blocks/materials/）"""
import unittest

from tests.blocks import kit


class ViewpointCase(unittest.TestCase):
    def setUp(self):
        self.vp = kit.load("procedure-trace", "viewpoint")
        self.mk = self.vp.materialkit

    def view(self, *files):
        return self.mk.View(".", "b", "r", "d", tuple(files), "c", "", 0)

    def test_declaration(self):
        self.assertEqual((self.vp.MATERIALS, self.vp.GUARDED, self.vp.NA, self.vp.NA_PARAGRAPH, self.vp.NA_REASON),
                         (("procedure_trace",), False, "cond", True, "対象差分に手順書・スクリプト・CI 定義の変更が無い"))

    def test_applies_names_the_procedure_files(self):
        self.assertEqual(self.vp.procedure_files(self.view("src/a.txt", "docs/x.md", "run.sh", "run.sh")), ["docs/x.md", "run.sh"])
        self.assertEqual(self.vp.applies(self.view("run.sh"), {}), (True, "差分に手順書・スクリプト・CI 定義が 1 件"))
        self.assertEqual(self.vp.applies(self.view("src/a.txt"), {}), (False, "差分に手順書・スクリプト・CI 定義が無い"))

    def test_due(self):
        why = "対象差分に手順書・スクリプト・CI 定義の変更が在る（差分に手順書・スクリプト・CI 定義が 1 件）——手順の追跡を回す"
        self.assertEqual(self.vp.due(self.view("run.sh"), {"entry": ""}), (True, why))
        self.assertEqual(self.vp.due(self.view("run.sh"), {"entry": "人の依頼"}), (True, why), "差分が在れば入口の周でない")
        self.assertEqual(self.vp.due(self.view("a.txt"), {"entry": ""}),
                         (False, "対象差分に手順書・スクリプト・CI 定義の変更が無い（差分に手順書・スクリプト・CI 定義が無い）——手順の追跡を起こさない"))
        self.assertEqual(self.vp.due(self.view(), {"entry": "人の依頼"}), self.mk.entry_skip("手順の追跡"))

    def test_fill_is_the_out_of_condition_text(self):
        want = {"procedure_trace": {"status": "not_applicable", "reason": "対象差分に手順書・スクリプト・CI 定義の変更が無い"
                                                                         "（差分に手順書・スクリプト・CI 定義が無い）"}}
        for entry in ("", "人の依頼"):
            view = self.view()
            self.assertEqual(self.vp.fill(view, {"entry": entry}, self.vp.due(view, {"entry": entry})), want)
        self.assertEqual(self.mk.fill_problems(self.vp, want), [])

    def test_material_and_report(self):
        self.assertFalse(self.vp.judged_na(None, {}))
        self.assertEqual(self.vp.materials_of({}), {})
        self.assertEqual(self.vp.materials_of({"material": {"status": "clean"}}), {"procedure_trace": {"status": "clean"}})
        self.assertEqual(self.vp.report_lines({"reply": None}), [])
        self.assertEqual(self.vp.report_lines({"reply": {"findings": [{"where": "run.sh:3", "text": "前提が\n欠ける"}],
                                                          "unmeasured": ["網が要る"]}}),
                         ["  - 所見: run.sh:3: 前提が 欠ける", "  - 未実測: 網が要る"])


if __name__ == "__main__":
    unittest.main()

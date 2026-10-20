"""観点の宣言 workflows/gate-efficacy/src/viewpoint.py のこの観点だけの中身（族の全部に当てる照らしは tests/blocks/materials/）"""
import json
import unittest

from tests.blocks import kit


class ViewpointCase(unittest.TestCase):
    def setUp(self):
        self.vp = kit.load("gate-efficacy", "viewpoint")
        self.mk = self.vp.materialkit

    def view(self, repo, files=("x.py",), diff="/nonexistent/diff.patch"):
        return self.mk.View(repo, "b", "r", diff, tuple(files), "c", "", 0)

    def test_declaration(self):
        self.assertEqual((self.vp.NAME, self.vp.MATERIALS, self.vp.GUARDED, self.vp.NA, self.vp.NA_PARAGRAPH),
                         ("gate-efficacy", ("gate_efficacy",), False, "cond", True))

    def test_applies_is_always_true_and_fill_is_not_called_when_due(self):
        view = self.view(".")
        self.assertTrue(self.vp.applies(view, {}).run)
        due = self.vp.due(view, {"gates": "", "entry": ""})
        self.assertTrue(due.run)
        with self.assertRaises(NotImplementedError):
            self.vp.fill(view, {"gates": "", "entry": ""}, due)

    def test_due_order_merge_first_then_entry(self):
        empty = self.view(".", files=())
        merge = self.vp.due(empty, {"gates": "merge", "entry": "人の依頼（x）"})
        self.assertEqual((merge.run, merge.why), (False, self.vp.GATES_MERGE_WHY))
        entry = self.vp.due(empty, {"gates": "", "entry": "人の依頼（x）"})
        self.assertFalse(entry.run)
        self.assertEqual(entry, self.mk.entry_skip("ゲートの検算"))
        self.assertTrue(self.vp.due(empty, {"gates": "other", "entry": ""}).run, "merge 以外の字は回す")
        both = {"gates": "merge", "entry": "人の依頼（x）"}
        self.assertTrue(self.vp.fill(empty, both, self.vp.due(empty, both))["gate_efficacy"]["reason"].startswith(self.vp.GATES_MERGE_WHY))
        only_entry = {"gates": "", "entry": "人の依頼（x）"}
        self.assertEqual(self.vp.fill(empty, only_entry, None), {"gate_efficacy": self.mk.fill_entry("人の依頼（x）", None)})
        self.assertEqual(self.vp.fill(empty, only_entry, None)["gate_efficacy"]["status"], "not_applicable")

    def test_entry_with_a_diff_is_not_an_entry_run(self):
        """修正が入って差分が出来た run は、古い entry が残っていても検算を回す（materialkit.is_entry_run）"""
        view = self.view(".", files=("tests/test_a.py",))
        values = {"gates": "", "entry": "人の依頼（x）"}
        self.assertTrue(self.vp.due(view, values).run)
        with self.assertRaises(NotImplementedError):
            self.vp.fill(view, values, self.vp.due(view, values))

    def test_judged_na_follows_the_signals(self):
        import pathlib
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            plain = pathlib.Path(tmp) / "plain.patch"
            plain.write_text("diff --git a/app.txt b/app.txt\n+++ b/app.txt\n+x\n", encoding="utf-8")
            self.assertTrue(self.vp.judged_na(self.view(tmp, ("app.txt",), str(plain)), {}))
            self.assertFalse(self.vp.judged_na(self.view(tmp, ("app.txt", "tests/test_a.py"), str(plain)), {}))
        self.assertFalse(self.vp.judged_na(self.view(".", ("app.txt",)), {}), "差分が読めなければ受けない")

    def test_mutation_values_and_paragraphs(self):
        import pathlib
        import tempfile
        decl = {"suite": [{"name": "t", "argv": ["true"]}], "mutation": {"argv": ["mutate", "--fast"], "arms": "arms.txt"}}
        cases = (
            ("declared", json.dumps(decl), (True, False, False), ("[\"mutate\", \"--fast\"]", "arms.txt", "")),
            ("no stage", json.dumps({"suite": decl["suite"]}), (False, True, False), ("", "", "")),
            ("broken stage", json.dumps({**decl, "mutation": {"argv": []}}), (False, True, True), None),
            ("not json", "{", (False, True, True), None),
            ("empty suite", json.dumps({**decl, "suite": []}), (False, True, True), None),
        )
        for label, text, flags, wanted in cases:
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                (root / "arms.txt").write_text("arm-1\n", encoding="utf-8")
                (root / self.vp.mutation.DECL_NAME).write_text(text, encoding="utf-8")
                view = self.view(root)
                when, values = self.vp.when(view, {}), self.vp.values(view, {})
                self.assertEqual((when["mutation_declared"], when["mutation_undeclared"], when["mutation_unreadable"]), flags)
                self.assertFalse(when["spawns"])
                self.assertEqual(values["decl_name"], ".review-checks.json")
                if wanted:
                    self.assertEqual((values["mutation_argv"], values["mutation_arms"], values["mutation_error"]), wanted)
                else:
                    self.assertTrue(values["mutation_error"])
                    self.assertEqual((values["mutation_argv"], values["mutation_arms"]), ("", ""))

    def test_materials_and_report(self):
        self.assertEqual(self.vp.materials_of({}), {})
        self.assertEqual(self.vp.materials_of({"material": {"status": "clean"}}), {"gate_efficacy": {"status": "clean"}})
        self.assertEqual(self.vp.report_lines({"reply": None}), [])
        row = {"gate": "ci", "arm": "the fence", "red_confirmed": True, "control_green": False, "hit_evidence": "x"}
        self.assertEqual(self.vp.report_lines({"reply": {"arms": [row]}}),
                         ["  - 腕: the fence（ci。赤 見た・対照の緑 見ていない・守る行の通過 見ていない）"])

    def test_declared_stage_suppresses_the_error_even_if_state_carries_one(self):
        """段が在れば読みの誤りは値にも段落の条件にも出ない（state が段と誤りを同時に返しても）"""
        from unittest import mock
        view = self.view(".")
        both = {"declared": True, "argv": "[\"m\"]", "arms": "a.txt", "error": "壊れた"}
        with mock.patch.object(self.vp.mutation, "state", return_value=both):
            self.assertEqual(self.vp.values(view, {})["mutation_error"], "")
            when = self.vp.when(view, {})
        self.assertEqual((when["mutation_declared"], when["mutation_undeclared"], when["mutation_unreadable"]),
                         (True, False, False))
        unread = {"declared": False, "argv": "", "arms": "", "error": "壊れた"}
        with mock.patch.object(self.vp.mutation, "state", return_value=unread):
            self.assertEqual(self.vp.values(view, {})["mutation_error"], "壊れた")
            self.assertTrue(self.vp.when(view, {})["mutation_unreadable"])

    def test_non_ascii_argv_is_kept_as_is(self):
        import pathlib
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "arms.txt").write_text("arm-1\n", encoding="utf-8")
            decl = {"suite": [{"name": "t", "argv": ["true"]}], "mutation": {"argv": ["変異", "--fast"], "arms": "arms.txt"}}
            (root / self.vp.mutation.DECL_NAME).write_text(json.dumps(decl), encoding="utf-8")
            self.assertEqual(self.vp.values(self.view(root), {})["mutation_argv"], '["変異", "--fast"]')


class ArmsCase(unittest.TestCase):
    """腕の照らし（docs/design/gate-efficacy.md の 4 節。写す元 test_accept_rules の gate-efficacy の部分）"""
    GOOD = {"gate": "g", "arm": "a1", "red_confirmed": True, "control_green": True, "hit_evidence": "the marker was in the output"}

    def setUp(self):
        self.arms = kit.load("gate-efficacy", "arms")

    def problem(self, status, rows):
        return self.arms.arms_problem("gate-efficacy", {"material": {"status": status}, "arms": rows})

    def test_zero_arms_cannot_claim_a_finding_or_clean(self):
        for status in ("found", "clean"):
            self.assertIn("腕が 0 行", self.problem(status, []))
        self.assertIsNone(self.problem("not_run", []))

    def test_clean_needs_red_control_and_hit(self):
        for key, value in (("red_confirmed", False), ("control_green", False), ("hit_evidence", "なし")):
            with self.subTest(key):
                got = self.problem("clean", [{**self.GOOD, key: value}])
                self.assertIn("status=clean", got)
        self.assertIsNone(self.problem("clean", [self.GOOD]))

    def test_found_and_awaiting_human_pass_the_second_check(self):
        bad = {**self.GOOD, "red_confirmed": False}
        self.assertIsNone(self.problem("found", [bad]))
        self.assertIsNone(self.problem("awaiting_human", [bad]))

    def test_red_and_control_without_hit_is_refused_whatever_the_status(self):
        got = self.problem("found", [{**self.GOOD, "hit_evidence": ""}])
        self.assertIn("守る行を通ったこと", got)
        self.assertIn("'a1'", got)

    def test_unconfirmed_control_is_not_a_hit_complaint(self):
        """赤を見て control を見ていない腕は、守る行の通過の句では拒まない（found なら通る）"""
        row = {**self.GOOD, "control_green": False, "hit_evidence": ""}
        self.assertIsNone(self.problem("found", [row]))
        self.assertIsNone(self.problem("awaiting_human", [row]))

    def test_hit_evidence_boundary_is_ten_characters(self):
        nine, ten = "a" * 9, "a" * 10
        got = self.problem("clean", [{**self.GOOD, "hit_evidence": nine}])
        self.assertIn("status=clean", got)
        self.assertIsNone(self.problem("clean", [{**self.GOOD, "hit_evidence": ten}]))
        self.assertIn("守る行を通ったこと", self.problem("found", [{**self.GOOD, "hit_evidence": nine}]))
        self.assertIsNone(self.problem("found", [{**self.GOOD, "hit_evidence": ten}]))
        two = [{**self.GOOD, "arm": "short", "hit_evidence": nine}, {**self.GOOD, "arm": "long", "hit_evidence": ten}]
        self.assertIn("測っていない腕 ['short']", self.problem("clean", two))


if __name__ == "__main__":
    unittest.main()

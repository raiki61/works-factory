"""入口と 1 回目の差分・材料（docs/design/delta-review.md の 6 節の 1・10.2 の IntakeCase）。"""
import json

from tests.bin.gitkit import git
from tests.blocks.delta_review import support as s


class IntakeCase(s.Case):
    def test_each_unreadable_port_fails_the_intake_naming_the_port(self):
        missing = str(self.run.artifacts / "absent.json")
        for port, value in (("plan", missing), ("lens_rows", missing), ("policy", missing), ("fix_reply", "{"), ("permits", '{"a": 1}'),
                            ("plan_review", "[]"), ("request", '[{"nope": 1}]'), ("base", "no-such-version")):
            with self.subTest(port=port):
                got = self.intake(**{port: value})
                if port == "lens_rows":
                    self.assertEqual(got["due"], False)   # レンズの控えが読めないのは入口の誤りでなく、材料の lens_error
                    self.assertTrue(self.read("intake.json")["lens_error"])
                    continue
                self.assertEqual(got["due"], False)
                self.assertIn(f"入力 {port}", got["reason"])
                self.assertTrue(self.read("intake.json")["failed"])
                fin = self.run.script("finish")
                self.assertEqual((fin["ok"], fin["status"], fin["rounds"], fin["pass"], fin["holes"], fin["diff"]), (False, "failed", 0, False, None, None))
                self.assertIn(f"入力 {port}", fin["reason"])

    def test_a_plan_of_the_wrong_shape_fails_the_intake_naming_the_field(self):
        # 型の外れは範囲の欄の形（shared:scope-fields.schema.json）が欄の道で名指し、型の中の下限（item が 1 以上の整数）は受け付けが名指す
        for doc, said in (("text", "$: 型が object/array"), ({"plan_items": {}}, "$.plan_items"),
                          ([{"item": 0}], "plan_items[0]"), ([{"item": True}], "$[0].item"), (["x"], "$[0]"),
                          ({"plan_items": [], "ruled_paths": [1]}, "ruled_paths"), ({"plan_items": [], "agreed": ["x"]}, "agreed")):
            with self.subTest(doc=doc):
                got = self.intake(plan=self.file("plan.json", doc))
                self.assertEqual(got["due"], False)
                self.assertIn("入力 plan", got["reason"])
                self.assertIn(said, got["reason"])

    def test_an_empty_base_fails_the_intake(self):
        got = self.intake(base="")
        self.assertEqual(got["due"], False)
        self.assertIn("入力 base: 空", got["reason"])
        self.assertTrue(self.read("intake.json")["failed"])

    def test_empty_diff_without_a_claimed_hole_skips_the_review(self):
        got = self.intake()
        self.assertFalse(got["due"])
        self.assertIn("差分が空で、塞いだと言われた穴も無い", got["reason"])
        self.assertEqual(self.read("skipped.json"), {"reason": got["reason"]})
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"], fin["rounds"], fin["pass"], fin["holes"], fin["diff"], fin["carry"]), (True, "ok", 0, True, None, None, []))
        self.assertIn("差分の審査: 回っていない", fin["report"][0])

    def test_empty_diff_with_a_claimed_hole_still_runs(self):
        got = self.intake(fix_reply=json.dumps(s.CLAIMED))
        self.assertEqual((got["due"], got["reason"], sorted(got["seal"])), (True, "", ["cut-1.json", "permits.json", "scope.json"]))
        self.assertFalse(self.exists("skipped.json"))
        self.assertEqual(self.read("cut-1.json")["files"], [])
        self.assertTrue(self.exists("review-1-brief.json") and self.exists("review-1-tree.json"))

    def test_declared_but_not_claimed_holes_do_not_run_an_empty_review(self):
        claimed = {**s.CLAIMED, "plan_faces": [{"key": "left-alone-hole", "handled": "declared"}]}
        self.assertFalse(self.intake(fix_reply=json.dumps(claimed))["due"])

    def test_changed_files_go_into_the_diff_and_the_brief(self):
        self.write("a.py", "alpha = 1\nbeta = 22\n")
        self.write("new.py", "fresh = 1\n")
        (self.run.repo / "b.py").unlink()
        got = self.intake()
        self.assertTrue(got["due"])
        cut = self.read("cut-1.json")
        self.assertEqual(sorted(cut["files"]), ["a.py", "b.py", "new.py"])
        patch = (self.run.artifacts / "delta-1.patch").read_text(encoding="utf-8")
        self.assertIn("+beta = 22", patch)
        self.assertIn("+fresh = 1", patch, "未追跡の新しいファイルも差分に載る")
        self.assertEqual(cut["base"], git(self.run.repo, "rev-parse", "HEAD^{tree}"))
        brief = self.read("review-1-brief.json")
        self.assertEqual(sorted(brief["files"]), sorted(cut["files"]))
        self.assertEqual((brief["plan_review"], brief["plan_faces"], brief["lens"], brief["plan_items"], brief["fix_report"]), (None, [], [], [], {}))

    def test_runtime_copy_is_not_in_the_diff(self):
        self.write(".archon/workflows/x.yaml", "name: x\n")
        got = self.intake()
        self.assertFalse(got["due"], "Archon の写しの置き場の下の変更は数えない")
        self.write("a.py", "alpha = 2\n")
        self.intake()
        self.assertEqual(self.read("cut-1.json")["files"], ["a.py"])

    def test_untracked_japanese_named_file_is_in_the_diff(self):
        self.write("docs/日本語の文書.md", "# 文書\n")
        self.intake()
        cut = self.read("cut-1.json")
        self.assertEqual(cut["files"], ["docs/日本語の文書.md"], "名前は引用の形でなく字のまま")
        self.assertIn("文書", (self.run.artifacts / "delta-1.patch").read_text(encoding="utf-8"))

    def test_own_files_from_an_earlier_try_are_removed_and_other_names_kept(self):
        for name in ("review-1-reply.json", "rejects-review-1.json", "refix-1-head.json", "delta.diff", "review-1-prompt-1.md", "refix-2-system-3.md"):
            self.write_artifact(name, "old")
        self.write_artifact("world.jsonl", "keep")
        self.write_artifact("rejects-other.json", "keep")
        self.intake()
        for name in ("review-1-reply.json", "rejects-review-1.json", "refix-1-head.json", "delta.diff", "review-1-prompt-1.md", "refix-2-system-3.md"):
            self.assertFalse(self.exists(name), name)
        self.assertTrue(self.exists("world.jsonl") and self.exists("rejects-other.json"))

    def write_artifact(self, name, text):
        (self.run.artifacts / name).write_text(text, encoding="utf-8")

    def test_materials_reach_the_brief_and_the_copies(self):
        self.write("a.py", "alpha = 1\nbeta = 22\n")
        item = s.plan_item(1, held="a ruling took it out", held_units={"unit-1": "ruled"}, out_of_scope_lifted=["lifted.py"])
        plan = self.file("plan.json", {"plan_items": [item], "ruled_paths": ["docs/ruled.md"], "agreed": [{"id": "c1-1", "item": 1}]})
        lens_rows = self.file("lens.json", {"rows": [{"lens": "silent-failure-hunter", "agent": "x", "go": True, "reason": "", "state": "ran",
                                                      "findings": [{"lens": "silent-failure-hunter", "where": "a.py", "cite": "beta", "why": "w"}],
                                                      "dropped": 0}]})
        review = {"faces": [{"key": "predicted-hole", "unit_keys": ["unit-1"]}], "shrink": []}
        got = self.intake(plan=plan, lens_rows=lens_rows, fix_reply=json.dumps({**s.CLAIMED, "changes": [{"unit_key": "unit-1", "files": ["a.py"]}],
                                                                                "not_done": []}),
                          plan_review=json.dumps(review), permits='[{"path": "tests/x.py", "permit": "rewrite", "source": "plan"}, "tests/x.py", "tests/y.py"]')
        self.assertTrue(got["due"])
        brief = self.read("review-1-brief.json")
        self.assertEqual(brief["plan_items"][0]["held"], "a ruling took it out")
        self.assertEqual(brief["plan_items"][0]["held_units"], {"unit-1": "ruled"})
        self.assertEqual((brief["ruled_paths"], brief["agreed"]), (["docs/ruled.md"], [{"id": "c1-1", "item": 1}]))
        self.assertEqual(brief["plan_review"], review)
        self.assertEqual([r["key"] for r in brief["plan_faces"]], ["claimed-closed-hole"])
        self.assertEqual(brief["fix_report"]["changes"], [{"unit_key": "unit-1", "files": ["a.py"]}])
        self.assertEqual(brief["lens"][0]["lens"], "silent-failure-hunter")
        self.assertEqual(self.read("permits.json"), ["tests/x.py", "tests/y.py"], "行も字も同じパスになり、重ねない")
        self.assertTrue(self.exists("lens.json") and self.exists("scope.json") and self.exists("fix-reply.json") and self.exists("plan-review.json"))

    def test_a_bare_array_of_items_is_a_scope_without_agreements(self):
        self.write("a.py", "alpha = 2\n")
        self.intake(plan=self.file("plan.json", [s.plan_item(1)]))
        self.assertEqual(self.read("scope.json"), {"plan_items": [s.plan_item(1)], "ruled_paths": [], "agreed": []})

    def test_items_without_a_scope_field_are_a_run_without_a_plan(self):
        self.write("a.py", "alpha = 2\n")
        bare = {k: v for k, v in s.plan_item(1).items() if k != "allowed_paths"}
        self.intake(plan=self.file("plan.json", [bare]))
        self.assertEqual(self.read("scope.json")["plan_items"], [])

    def test_unreadable_lens_rows_do_not_stop_the_review(self):
        self.write("a.py", "alpha = 2\n")
        got = self.intake(lens_rows=self.file("lens.json", {"rows": "oops"}))
        self.assertTrue(got["due"])
        brief = self.read("review-1-brief.json")
        self.assertEqual(brief["lens"], [])
        self.assertIn("lens-rows.schema.json", brief["lens_error"])
        self.assertFalse(self.exists("lens.json"), "読めない写しは残さない")

    def test_protected_files_come_from_own_list_and_the_target_declaration(self):
        self.write(".works-protected.json", json.dumps({"rules": [{"id": "guard", "glob": "b.py", "why": "the target guards b"}]}))
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "declare")
        self.write("b.py", "gamma = 4\n")
        self.write("lib/protect.py", "x = 1\n")
        self.intake(base=git(self.run.repo, "rev-parse", "HEAD"))
        hits = {r["path"]: r["id"] for r in self.read("review-1-brief.json")["protected_files"]}
        self.assertEqual(hits, {"b.py": "target:guard", "lib/protect.py": "checker"})

    def test_a_tree_as_base_reads_the_declaration_at_head(self):
        self.write(".works-protected.json", json.dumps({"rules": [{"id": "guard", "glob": "b.py", "why": "the target guards b"}]}))
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "declare")
        tree = git(self.run.repo, "rev-parse", "HEAD^{tree}")
        self.write("b.py", "gamma = 4\n")
        self.assertTrue(self.intake(base=tree)["due"])
        brief = self.read("review-1-brief.json")
        self.assertEqual([r["path"] for r in brief["protected_files"]], ["b.py"])
        self.assertNotIn("protected_files_error", brief)

    def test_broken_target_declaration_is_named_not_hidden(self):
        self.write(".works-protected.json", "not json")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "declare")
        self.write("a.py", "alpha = 2\n")
        self.intake(base=git(self.run.repo, "rev-parse", "HEAD"))
        brief = self.read("review-1-brief.json")
        self.assertEqual(brief["protected_files"], [])
        self.assertIn("守りの宣言", brief["protected_files_error"])

    def test_lang_defaults_to_the_language_of_the_request(self):
        self.intake()
        self.assertEqual(self.read("intake.json")["lang"], "the language of the request (the user's language)")
        self.intake(lang="Japanese")
        self.assertEqual(self.read("intake.json")["lang"], "Japanese")

    def test_request_rows_are_copied_only_when_there_are_rows(self):
        self.write("a.py", "alpha = 2\n")
        self.intake()
        self.assertFalse(self.exists("request.json"))
        self.intake(request='[{"where": "a.py", "text": "fix it"}]')
        self.assertEqual(self.read("request.json"), [{"where": "a.py", "text": "fix it"}])

    def test_included_block_writes_in_its_own_place(self):
        self.write("a.py", "alpha = 2\n")
        self.run.script("intake", "delta-review__intake", base=self.base, plan="", lens_rows="", fix_reply="null", permits="[]",
                        plan_review="null", policy="", request="[]", lang="")
        self.assertTrue((self.run.artifacts / "delta-review" / "cut-1.json").is_file())
        self.assertFalse(self.exists("cut-1.json"))

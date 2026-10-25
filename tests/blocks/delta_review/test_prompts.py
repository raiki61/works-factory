"""審査役の指示とまとめて使う断片（docs/design/delta-review.md の 2.3・4 節の 3・11 節の 6。手直しの役の指示は test_refix.py の RefixPromptCase）。"""
import json
import re
from unittest import mock

from tests.blocks import kit
from tests.blocks.delta_review import support as s

WRITER_RULES = kit.SHARED / "prompts" / "writer-rules.md"


class ReviewPromptCase(s.Flow):
    def first(self, **inputs):
        self.write("a.py", "alpha = 1\nbeta = 22\n")
        self.assertTrue(self.intake(fix_reply=json.dumps(s.CLAIMED), **inputs)["due"])
        return self.step("review_prep", 1)["prompt"]

    def test_the_first_review_names_the_material_the_verdict_words_and_the_borrowed_template(self):
        text = self.first(lang="Japanese")
        self.assertTrue(text.startswith("You are the inspector for the diff of this round's fix."))
        brief = self.read("review-1-brief.json")
        for key in brief:
            if key not in ("diff_file", "files", "rev", "base"):
                self.assertIn(f"`{key}`", text, f"材料の欄 {key} の説明が指示に無い")
        self.assertIn(f"`{self.run.artifacts / 'delta-1.patch'}`", text)
        self.assertIn('Changed files: ["a.py"]', text)
        for line in ("| ✅ Spec compliant | compliance_pass | `compliance.verdict`: `pass` |", "| Needs fixes | quality_fail | `quality.verdict`: `fail` |",
                     "Sub-agent template (superpowers' skills/subagent-driven-development/task-reviewer-prompt.md, wrapped in works' sections)",
                     "Do not crawl the broader codebase", "state` is `failed` or `not_routed`", "answered `absorbed` to",
                     "`missing`", "`extra`", "`misunderstood`", "`unverifiable`", "`scope_creep`", "`dead_path`", "in Japanese"):
            self.assertIn(line, text)
        self.assertIn("this prompt wins", text)
        self.assertIn(f"Read this file: {kit.ROOT / 'lib' / 'borrow' / 'unattended.md'}", text)
        self.assertNotIn("new conversation", text, "会話を続ける輪の役の指示に「新しい会話」と書かない")
        self.assertNotIn("Do not silently drop", text, "初回は拒まれていない")

    def test_the_diff_and_the_template_agree_on_where_the_diff_is(self):
        text = self.first()
        brief = str(self.run.artifacts / "review-1-brief.json")
        self.assertIn(f"Read the task brief: {brief}", text)
        self.assertIn(str(self.run.artifacts / "delta-1.patch"), text)
        self.assertNotIn("[BRIEF_FILE]", text)

    def test_the_policy_is_pasted_and_cut_with_a_pointer_when_long(self):
        policy = self.run.artifacts / "policy.md"
        policy.write_text("# Policy\nNever weaken a test.\n", encoding="utf-8")
        text = self.first(policy=str(policy))
        self.assertIn("Never weaken a test.", text)
        self.assertIn("write in the `why` of a hole which item it conflicts with", text)
        self.assertIn(str(policy), text, "型の穴 GLOBAL_CONSTRAINTS に方針の文書のパスが入る")
        policy.write_text("x" * 50000, encoding="utf-8")
        self.intake(fix_reply=json.dumps(s.CLAIMED), policy=str(policy))
        long = self.step("review_prep", 1)["prompt"]
        self.assertIn("バイトまでを貼った。続きは " + str(policy), long)

    def test_without_a_policy_no_policy_paragraph(self):
        text = self.first()
        self.assertNotIn("The person's policy", text)

    def test_a_rejected_round_brings_the_reasons_and_the_keep_the_holes_paragraph(self):
        self.first()
        self.review(1, s.review_reply(checks=[]))
        again = self.step("review_prep", 1)["prompt"]
        self.assertTrue(again.startswith("## Why your previous answer was rejected"))
        self.assertIn("検算が無い", again)
        self.assertIn("Do not silently drop a hole that was rejected", again)
        self.assertEqual(len(list(self.run.artifacts.glob("review-1-prompt-*.md"))), 2)

    def test_the_second_review_has_no_verdicts_no_seat_no_lens(self):
        self.start()
        self.write("a.py", "alpha = 1\nbeta = 22\ngamma = 5\n")
        self.assertTrue(self.refix(1, self.handled(self.answer("copy-of-the-rule"), self.answer("claimed-closed-hole")))["ok"])
        self.run.script("cut2")
        text = self.step("review_prep", 2)["prompt"]
        self.assertTrue(text.startswith("You are the inspector for the diff of the touch-up."))
        for gone in ("Two verdicts", "Borrowed template", "plan_items", "`lens`:", "Why your previous answer", "new conversation"):
            self.assertNotIn(gone, text)
        for here in ("`handled`", "answered `fixed` to", "Look only at the same three points as the first review", "what the touch-up added",
                     "will not be reviewed once more", str(self.run.artifacts / "delta-2.patch")):
            self.assertIn(here, text)
        self.assertNotIn("quality points", text)
        self.assertNotIn("- `lens`: add it only", text)

    def test_the_two_reviews_share_the_hole_row_rules(self):
        self.start()
        self.write("a.py", "alpha = 1\nbeta = 22\ngamma = 5\n")
        self.refix(1, self.handled(self.answer("copy-of-the-rule"), self.answer("claimed-closed-hole")))
        self.run.script("cut2")
        one, two = self.step("review_prep", 1)["prompt"], self.step("review_prep", 2)["prompt"]
        rules = ["`key`: a name that calls the hole uniquely, at least 8 characters.", "**only the path of a changed file**", "at least 4 characters",
                 "If there is no hole, leave `faces` empty and write in `faces_none`", "`regression`, `policy`, and `precedent` are words of the review before the fix only"]
        for rule in rules:
            self.assertIn(rule, one)
            self.assertIn(rule, two)

    def test_the_hole_words_in_the_prompt_are_the_ones_the_acceptance_takes(self):
        review = kit.load("delta-review", "review")
        text = self.first()
        for kind in review.FACE_KINDS:
            self.assertIn(f"`{kind}`", text)


class BorrowedCase(s.Flow):
    """借りた写しが固定と違えば、指示を組まずに errors.json に node と訳を積んで落ちる"""

    def broken_pin(self, n, kind):
        steps = kit.load(s.BLOCK_NAME, "steps")
        with self.run.env(), mock.patch.object(steps.borrowed.seat, "pinned", side_effect=ValueError("the pin differs")):
            with self.assertRaises(ValueError):
                getattr(steps, f"{kind}_prompt")(self.run.artifacts, n)
        row = self.read("errors.json")[-1]
        self.assertEqual(row["node"], f"{kind}-{n}")
        self.assertIn("借りた写しが使えない: the pin differs", row["reason"])

    def test_the_review_seat(self):
        self.write("a.py", "alpha = 1\nbeta = 22\n")
        self.intake(fix_reply=json.dumps(s.CLAIMED))
        self.broken_pin(1, "review")

    def test_the_touch_up_seat(self):
        self.start()
        self.broken_pin(1, "refix")


class WriterRulesCase(s.Case):
    def test_the_paragraph_names_are_the_ones_the_fragment_list_says(self):
        text = WRITER_RULES.read_text(encoding="utf-8")
        names = set(re.findall(r"<!-- if ([a-z_]+) -->", text))
        self.assertEqual(names, {"conflict", "conflict_change", "evidence", "docs", "prompts_kind", "config", "code", "where_writer", "where_tdd", "where_rework"})
        self.assertEqual(sorted(re.findall(r"<!-- end ([a-z_]+) -->", text)), sorted(re.findall(r"<!-- if ([a-z_]+) -->", text)))
        self.assertFalse(re.findall(r"(?<!\{)\{[a-z0-9_]+\}(?!\})", text), "断片は差し込み口を持たない")
        listed = (kit.SHARED / "AGENTS.md").read_text(encoding="utf-8")
        [row] = [line for line in listed.splitlines() if line.startswith("  - `writer-rules`:")]
        for name in names:
            self.assertIn(f"`{name}`", row)

    def test_the_conflict_paragraph_names_the_seven_scenes(self):
        text = WRITER_RULES.read_text(encoding="utf-8")
        block = "\n".join(re.findall(r"<!-- if conflict(?:_change)? -->\n(.*?)<!-- end conflict(?:_change)? -->", text, re.S))
        for kind in ("brief_vs_judgment", "unnamed_test_broke", "not_red", "scope_needed", "query_hits_fixed", "needs_context", "red_at_base"):
            self.assertIn(f"`{kind}`", block)
        self.assertEqual(len(re.findall(r"^  - `", block, re.M)), 7)

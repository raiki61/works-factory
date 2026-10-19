"""2 本の指示 md（prompts/diagnose.md・prompts/rejudge.md）と、使う共通の断片の試験（docs/design/diagnose.md の 9.2）。
古い指示を日本語のまま組んだ物と同じ字にする試験は置かない（2 波目の決め）。英語の md と古い指示の照らしは、設計書の 9.4 の一覧で審査役が
1 件ずつ行う。ここは md が組めること・語と鍵が md に在ること・「新しい会話」と言わないことを見る。"""
import itertools
import json
import re
import unittest

from tests.blocks import kit
from tests.blocks.diagnose import support
from tests.blocks.diagnose.test_inputs import PORTS

BLOCK = kit.BLOCKS / "diagnose"
PROMPTS = BLOCK / "prompts"
SHARED_PROMPTS = kit.SHARED / "prompts"
FRAGMENT = re.compile(r"\{shared:([a-z0-9-]+)\}")


def expanded(name: str) -> str:
    """md に共通の断片を入れた字（断片の中の断片も）"""
    def one(match):
        return expanded_text((SHARED_PROMPTS / f"{match.group(1)}.md").read_text(encoding="utf-8"))
    def expanded_text(text):
        return FRAGMENT.sub(one, text)
    return expanded_text((PROMPTS / name).read_text(encoding="utf-8"))


class _Base(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "diagnose")
        support.seeded(self.run)
        self.mod = support.modules()
        import importlib
        self.prompt = importlib.import_module("prompt")


class RenderCase(_Base):
    def compose(self, node, values, when):
        return self.prompt._compose(BLOCK, node, values, when)["prompt"]

    def test_diagnose_renders_for_every_combination_of_paragraphs(self):
        self.run.script("intake", **PORTS)
        values, when = self.mod["inputs"].diagnose_values(self.run.artifacts)
        names = sorted(when)
        self.assertEqual(set(names), {"rejected", "spawns", "purpose", "repo_review", "pr_text", "policy", "prior_notes", "prior_redesign",
                                      "recorded_none", "unknown_rows", "unknown_none"})
        for combo in itertools.product([False, True], repeat=len(names)):
            with self.subTest(dict(zip(names, combo))):
                text = self.compose("diagnose", values, dict(zip(names, combo)))
                self.assertIn("You are the judgment role of this run.", text)
                self.assertNotIn("{shared:", text)
                self.assertNotRegex(text, r"\{[a-z0-9_]+\}")

    def test_rejudge_renders_for_every_combination_of_paragraphs(self):
        self.run.script("intake", **{**PORTS, "objection": "異議", "prior": json.dumps({"units": []})})
        values, when = self.mod["inputs"].rejudge_values(self.run.artifacts)
        names = sorted(when)
        self.assertEqual(set(names), {"rejected", "spawns", "questions", "diagnosis", "prior_brief", "prior_inputs", "world_rows", "purpose",
                                      "spec", "verify", "excluded", "policy"})
        for combo in itertools.product([False, True], repeat=len(names)):
            with self.subTest(dict(zip(names, combo))):
                text = self.compose("rejudge", values, dict(zip(names, combo)))
                self.assertIn("You are woken to reconsider this run's judgment.", text)
                self.assertNotRegex(text, r"\{[a-z0-9_]+\}")

    def test_the_values_the_machine_gives_appear_in_the_prompt(self):
        self.run.script("intake", **{**PORTS, "row_asks": json.dumps([{"item": 1, "unknown": "原因", "cause_quote": "落ちる"}])})
        values, when = self.mod["inputs"].diagnose_values(self.run.artifacts)
        text = self.compose("diagnose", values, when)
        self.assertIn(values["inputs_file"], text)
        self.assertIn(values["diff_file"], text)
        self.assertIn("- line 1 (原因)", text)
        self.assertIn("- Policy document: none", text)
        self.assertIn("Recorded policy: none", text)
        self.assertNotIn("Why your previous answer was rejected", text)

    def test_rejection_paragraph_is_in_only_when_rejected(self):
        import rolekit
        self.run.script("intake", **PORTS)
        rolekit.with_done(self.run.artifacts, "diagnose", {"ok": False, "reason": "拒否の印ABC"})
        values, when = self.mod["inputs"].diagnose_values(self.run.artifacts)
        self.assertIn("拒否の印ABC", self.compose("diagnose", values, when))


class WordsCase(unittest.TestCase):
    def setUp(self):
        self.mod = support.modules()
        self.diagnose = expanded("diagnose.md")
        self.rejudge = expanded("rejudge.md")

    def test_md_holds_every_table_word(self):
        judge, rejudge = self.mod["judge"], self.mod["rejudge"]
        for word in (*judge.LABELS, *judge.QUESTION_KINDS, *judge.QUESTION_STATUS):
            self.assertIn(word, self.diagnose, word)
        for word in judge.QUESTION_FIELDS:
            self.assertIn(f"`{word}`", self.diagnose, word)
        for word in rejudge.REJUDGE_VERDICTS:
            self.assertIn(word, self.rejudge)

    def test_ledger_kinds_are_explained_with_their_origin(self):
        for kind in self.mod["judge"].QUESTION_KINDS:
            self.assertRegex(self.diagnose, rf"- `{kind}` \(")

    def test_every_key_of_the_input_doc_is_described(self):
        run = kit.Run(self, "diagnose")
        support.seeded(run)
        run.script("intake", **PORTS)
        doc = json.loads((run.artifacts / "diagnose-input.json").read_text(encoding="utf-8"))
        for key in doc:
            self.assertIn(f"`{key}`", self.diagnose, key)

    def test_no_prompt_says_it_started_in_a_new_conversation(self):
        for text in (self.diagnose, self.rejudge):
            self.assertNotRegex(text.lower(), r"new conversation")

    def test_fix_prompt_is_the_shared_resubmit_fragment(self):
        text = expanded("rejudge-fix.md")
        self.assertIn("Your previous answer was rejected by the machine's check.", text)
        self.assertNotRegex(text.lower(), r"new conversation")
        self.assertEqual((PROMPTS / "rejudge-fix.md").read_text(encoding="utf-8").strip(), "{shared:resubmit}")

    def test_prompts_have_no_dollar_variables(self):
        for text in (self.diagnose, self.rejudge):
            self.assertNotRegex(text, r"\$[A-Za-z{]")

    def test_role_texts_are_shared_not_copied(self):
        for name in ("diagnose.md", "rejudge.md"):
            text = (PROMPTS / name).read_text(encoding="utf-8")
            self.assertIn("{shared:role-judge}", text)
            self.assertNotIn("Try to refute", text)

    def test_diagnose_names_the_stop_for_unreadable_inputs(self):
        self.assertIn("`inputs_file` or `review_md`", self.diagnose)
        self.assertIn("carried_r1", self.diagnose)

    def test_final_line_is_the_schema_sentence(self):
        for name in ("diagnose.md", "rejudge.md"):
            self.assertEqual((PROMPTS / name).read_text(encoding="utf-8").rstrip().splitlines()[-1],
                             "Return only JSON that matches the output schema.")

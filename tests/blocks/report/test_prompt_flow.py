"""AI の node の指示（prompts/write.md・prompts/cold.md）を、script を子のプロセスで回して組んだ字で確かめる。"""
import json
import unittest

from tests.blocks.report import base
from tests.blocks.report.base import LOOP, Flow

M = base.src()
import handoff  # noqa: E402  lib/


class PrepCase(Flow):
    def test_first_prompt_has_the_values_and_no_rejection(self):
        self.facts(facts=json.dumps({**base.READY, "head": {"after": ["試験は走っていない"]}}), lang="日本語")
        prompt = self.prep()
        self.assertIn("The outcome word of this run is **fixed** (the stage that stopped it and the reason word: ``)", prompt)
        self.assertIn(f"`{self.place / 'report.md'}`", prompt)
        self.assertIn("Write the report in 日本語.", prompt)
        self.assertIn('the facts\' section "3. 見る所"', prompt)
        self.assertIn("longer than 50 characters", prompt)
        self.assertNotIn("Why your previous answer was rejected", prompt)
        self.assertNotIn("Your previous answer was rejected", prompt)
        self.assertNotIn("Notes that earlier rounds of you wrote", prompt)
        self.assertIn("Notes handed over between rounds", prompt)
        self.assertTrue((self.place / "write-prompt-1.md").is_file())

    def test_json_example_keeps_both_closing_braces(self):
        self.facts()
        self.assertIn('"handoff": {<the notes, with the fields the request below names>}}`', self.prep())

    def test_empty_lang_is_the_requests_language(self):
        self.facts()
        self.assertIn("Write the report in the language of the request (the user's language).", self.prep())

    def test_old_fallen_writer_note_is_dropped_before_the_writer(self):
        self.facts()
        M.writer.note_writer_fell(self.place / "report.md", {"error": "used up", "quota": True}, run_id="run-test")
        self.assertIn("AI が書く報告の本文は無い", self.machine())
        self.prep()
        self.assertNotIn("AI が書く報告の本文は無い", self.machine())

    def test_rejection_previous_answer_and_every_prior_note_reach_the_next_prompt(self):
        self.facts()
        first = self.prep()
        reply = base.reply("一回目。\n\n## 人が決めること\n\n- A", note={"read": [], "kept": ["保つ"], "set_aside": [], "open": []})
        self.cold_prep(reply)
        got = self.accept(reply, base.BAD_COLD)
        self.assertEqual((got["done"], got["kind"]), (False, "cold"))
        second = self.prep()
        self.assertIn("Why your previous answer was rejected", second)
        self.assertIn("1 回目の拒否:\n初見の読み手（道具なし・報告の頭だけを読む）が redesign-needed を返した", second)
        self.assertIn("- 止まった所: 何の話か分からない", second)
        self.assertIn("returned redesign-needed, rewrite the body so that the places listed can be understood from the head alone", second)
        self.assertIn("cut each cell to a few words and write the explanation outside the table", second)
        self.assertNotIn("cut each cell to a few words", first)
        self.assertIn("- 推測で埋めた所: PR だと推測した", second)
        self.assertIn(f"Read your previous answer at `{self.place / 'candidate-report.json'}`", second)
        self.assertIn("Notes that earlier rounds of you wrote", second)
        self.assertIn(f"- r1: {handoff.path_of(self.place / 'r1')}", second)
        self.assertNotIn("Why your previous answer was rejected", first)
        self.accept(reply, base.BAD_COLD)
        third = self.prep()
        self.assertIn("2 回目の拒否:", third)
        self.assertIn(f"- r2: {handoff.path_of(self.place / 'r2')}", third)
        self.assertEqual([p.name for p in sorted(self.place.glob("write-prompt-*.md"))],
                         ["write-prompt-1.md", "write-prompt-2.md", "write-prompt-3.md"])

    def test_prep_without_facts_fails_loudly(self):
        self.assertIn("facts.json が無いか読めない", self.run.failing("write_prep", LOOP + "write-prep"))


class ColdPrepCase(Flow):
    def test_body_is_the_human_head(self):
        self.facts()
        reply = base.reply("承認ノードで止めた。\n\n## 人が決めること\n\n- A\n\n## 経緯\n\n長い経緯")
        prompt = self.cold_prep(reply)
        self.assertIn("==== text begins ====\n# 報告（run run-test）\n\n起きたこと: 直して、最後のテストまで通った（fixed）", prompt)
        self.assertIn("先へ進めるかを決める所で止めた。", prompt)
        self.assertNotIn("長い経緯", prompt)
        self.assertIn('under the heading "機械が各段の出力と run の記録から組んだ事実（AI は書き換えていない）"', prompt)
        self.assertTrue((self.place / "cold-prompt-1.md").is_file())

    def test_unreadable_reply_is_said_in_the_body(self):
        self.facts()
        self.assertIn("（書き手の返答を読めない:", self.cold_prep("壊れた"))


if __name__ == "__main__":
    unittest.main()

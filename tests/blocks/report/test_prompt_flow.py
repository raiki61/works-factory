"""AI の node の指示（prompts/write.md・prompts/cold.md）を、script を子のプロセスで回して組んだ字で確かめる。"""
import json
import re
import unittest

from tests.blocks.report import base
from tests.blocks.report.base import LOOP, Flow

M = base.src()
import handoff  # noqa: E402  lib/


class PrepCase(Flow):
    def test_first_prompt_has_the_values_and_no_rejection(self):
        ran = {"kind": "tests_not_run", "slots": {}, "text": "試験は走っていない"}
        self.facts(facts=json.dumps({**base.READY, "head": {"after": [ran]}}), lang="日本語")
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

    def fell_rows(self) -> list:
        H = M.head
        return [x for x in M.writer.machine_head(self.machine()).splitlines()
                if H.parse(x) and H.parse(x).kind in (H.Line.WRITER_FELL_OTHER, H.Line.WRITER_FELL_QUOTA)]

    def test_old_fallen_writer_note_is_dropped_before_the_writer(self):
        self.facts()
        for quota in (True, False):
            with self.subTest(quota=quota):
                M.writer.note_writer_fell(self.place / "report.md", {"error": "used up", "quota": quota}, run_id="run-test")
                self.assertEqual(len(self.fell_rows()), 1, "頭の表の行（使用枠の切れも、ほかの落ちも）")
                self.assertIn("書き手の段が落ちた誤り: used up", self.machine(), "誤りの行は注意の節に在る")
                self.prep()
                self.assertEqual(self.fell_rows(), [])
                self.assertNotIn("used up", self.machine())

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
        self.assertIn("==== lines the machine built begin ====\nM1 | # 報告（run run-test）\nM3 | 起きたこと: 直して、最後のテストまで通った", prompt)
        machine, writer = prompt.split("==== lines the machine built end ====")
        self.assertIn("==== text the writer wrote begins ====\nW1 | 先へ進めるかを決める所で止めた。", writer)
        self.assertNotIn("先へ進めるかを決める所で止めた。", machine)
        pasted = machine.split("begin ====\n", 1)[1].splitlines() + writer.split("begins ====\n", 1)[1].split("\n==== text the writer wrote ends")[0].splitlines()
        self.assertTrue(pasted and all(re.fullmatch(r"[MW][0-9]+ \| .+", x) for x in pasted), pasted)
        self.assertIn("write only the mark characters", prompt)
        self.assertNotIn("machine_lines", prompt)
        self.assertNotIn("長い経緯", prompt)
        self.assertIn('under the heading "機械が各段の出力と run の記録から組んだ事実（AI は書き換えていない）"', prompt)
        self.assertTrue((self.place / "cold-prompt-1.md").is_file())

    def test_lang_reaches_the_cold_reader(self):
        """書き手と同じ言語で、止まった所・推測した所を返させる（言語の行が無いと読み手は指示の英語で返す）。
        空の lang は貼った本文の言語（cold-read の block の cold.md と同じ形）"""
        self.facts(lang="日本語")
        self.assertIn("- Write the `text` of `stops` and `guessed` in 日本語.", self.cold_prep(base.reply()))
        self.facts()
        prompt = self.cold_prep(base.reply())
        self.assertIn("- Write the `text` of `stops` and `guessed` in the language of the text.", prompt)
        self.assertNotIn("machine_lines", prompt)

    def test_unreadable_reply_is_said_in_the_body(self):
        self.facts()
        self.assertIn("（書き手の返答を読めない:", self.cold_prep("壊れた"))


if __name__ == "__main__":
    unittest.main()

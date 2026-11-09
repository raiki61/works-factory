"""AI の node の指示（prompts/write.md・prompts/cold.md）を、script を子のプロセスで回して組んだ字で確かめる。"""
import unittest

from tests.blocks.report import base
from tests.blocks.report.base import LOOP, Flow

M = base.src()
import handoff  # noqa: E402  lib/


class PrepCase(Flow):
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


if __name__ == "__main__":
    unittest.main()

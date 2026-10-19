"""指示の比べ（1 つ目の commit。docs/design/README.md の 11.4）: prep が md から組んだ指示が、今の指示書（workflows/report/commands/）に同じ値を
入れた字と、空白の違いを除いて同じ。この試験は 2 つ目の commit（英語にする）で消す。

今の指示書に先に当てる置き換えは 2 つだけ: (a) `$ARTIFACTS_DIR/` で始まる相対のパスを絶対パスに、(b)「の、run の置き場からの相対のパス」を
「のパス」に、「（`$ARTIFACTS_DIR/` の下のそのパス）」を空に（新しい値が絶対パスなので）。
"""
import json
import pathlib
import unittest

from tests.blocks import kit
from tests.blocks.report import base
from tests.blocks.report.base import LOOP, Flow

M = base.src()
import handoff  # noqa: E402  lib/
import rolekit  # noqa: E402  lib/

COMMANDS = kit.ROOT / "workflows" / "report" / "commands"


def squeezed(text: str) -> str:
    return "".join(text.split())


def current(name: str, values: dict) -> str:
    """今の指示書に、Archon が入れていた値を入れた字（置き換え (a)(b) を当てた上で）"""
    text = (COMMANDS / name).read_text(encoding="utf-8")
    text = text.replace("の、run の置き場からの相対のパス", "のパス").replace("（`$ARTIFACTS_DIR/` の下のそのパス）", "")
    text = text.replace("$ARTIFACTS_DIR/$facts.output.facts_file", values.get("facts_file", "$ARTIFACTS_DIR/$facts.output.facts_file")).replace(
        "$ARTIFACTS_DIR/eyes/", values["eyes_dir"] + "/" if "eyes_dir" in values else "$ARTIFACTS_DIR/eyes/")
    for token, key in (("$facts.output.lang_line", "lang_line"), ("$facts.output.outcome", "outcome"),
                       ("$facts.output.stop_reason", "stop_reason"), ("$write-reject.output.reason", "reason_file"),
                       ("$write-reject.output.prev", "prev"), ("$write-reject.output.handoff", "handoff"),
                       ("$cold-prep.output.body", "body")):
        text = text.replace(token, values.get(key, token))
    return text


class WriterPromptCase(Flow):
    def values(self, **over) -> dict:
        place = self.place
        return {"lang_line": rolekit.lang_line({"lang": "日本語"}), "outcome": "fixed", "stop_reason": "", "facts_file": str(place / "report.md"),
                "eyes_dir": str(place / "eyes"), "reason_file": "", "prev": "",
                "handoff": handoff.ASK, **over}

    def test_first_round_equals_the_current_instruction(self):
        self.facts(lang="日本語")
        got = self.prep()
        self.assertEqual(squeezed(got), squeezed(current("report.md", self.values())))

    def test_rejected_round_equals_the_current_instruction_with_the_same_values(self):
        self.facts(lang="日本語")
        self.prep()
        reply = base.reply("一回目。\n\n## 人が決めること\n\n- A", note={"read": [], "kept": ["保つ"], "set_aside": [], "open": []})
        self.accept(reply, base.BAD_COLD)
        got = self.prep()
        rounds = [self.place / "r1"]
        values = self.values(reason_file=str(self.place / "rejects-report.md"), prev=str(self.place / "candidate-report.json"),
                             handoff="\n\n".join([handoff.ASK, handoff.section(rounds)]))
        self.assertEqual(squeezed(got), squeezed(current("report.md", values)))
        self.assertIn(str(handoff.path_of(rounds[0])), got)

    def test_empty_language_uses_the_default_line(self):
        self.facts()
        got = self.prep()
        self.assertEqual(squeezed(got), squeezed(current("report.md", self.values(lang_line=rolekit.lang_line({})))))


class ColdPromptCase(Flow):
    def test_cold_instruction_equals_the_current_one(self):
        self.facts()
        reply = base.reply("承認ノードで止めた。\n\n## 人が決めること\n\n- A\n\n## 経緯\n\n長い経緯")
        body = M.writer.cold_body(reply, place=self.place)
        got = self.cold_prep(reply)
        self.assertEqual(squeezed(got), squeezed(current("cold-check.md", {"body": body})))
        self.assertIn(body, got)


if __name__ == "__main__":
    unittest.main()

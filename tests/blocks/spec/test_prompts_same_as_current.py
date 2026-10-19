"""6 本の md が、今の工場の指示と同じ字になる（docs/design/README.md の 11.4。1 つ目の commit の試験で、英語にする 2 つ目の commit で消す）。

prep が組んだ指示を、今の指示（workflows/judge/commands/ の spec.md・spec-review.md・spec-revise.md を Archon が置き換えた字と、
lib/rolekit.py の write_resubmit が書く出し直しの指示書）に同じ値を入れた物と、空白の違いを除いて比べる。値の入れ方:
`$spec-<役>-reject.output.reason` は rolekit.rejects_text（1 回目は空）、`...lang_line` は rolekit.LANG_RULE に port lang の値
（空なら共通の断片の既定の文）、`$ARTIFACTS_DIR/judge` は place。
"""
import json
import pathlib

from tests.blocks import kit
from tests.blocks.spec.test_spec import REQUEST, _Case, review_reply, revise_reply, write_reply

OLD = kit.ROOT / "workflows" / "judge" / "commands"
FILES = {"write": "spec", "review": "spec-review", "revise": "spec-revise"}
REJECT = {"write": "spec-reject", "review": "spec-review-reject", "revise": "spec-revise-reject"}


def squeeze(text: str) -> str:
    return "".join(text.split())


class SameAsCurrentCase(_Case):
    def current(self, role, lang_value, reasons):
        rolekit, prompt = self.steps.rolekit, self.steps.prompt
        text = (OLD / f"{FILES[role]}.md").read_text(encoding="utf-8")
        text = text.replace(f"${REJECT[role]}.output.lang_line", rolekit.LANG_RULE.format(lang=prompt.lang(lang_value)))
        text = text.replace(f"${REJECT[role]}.output.reason", rolekit.rejects_text(reasons))
        return text.replace("$ARTIFACTS_DIR/judge", str(self.place))

    def reach(self, role, lang=""):
        """役 role の指示を組める所まで進める"""
        self.intake(lang=lang)
        if role != "write":
            self.write_tests()
            self.assertTrue(self.take("write", write_reply())["ok"])
        if role == "revise":
            self.assertTrue(self.take("review", review_reply())["ok"])

    def reject(self, role, n):
        bad = {"write": write_reply("missing.txt"), "review": {**review_reply(), "faces": [review_reply()["faces"][0]] * 2},
               "revise": {**revise_reply(), "handled": []}}[role]
        for _ in range(n):
            self.assertFalse(self.take(role, bad)["ok"])

    def test_first_round_prompts(self):
        for role in FILES:
            for lang in ("", "Japanese"):
                with self.subTest(role=role, lang=lang):
                    self.setUp()
                    self.reach(role, lang=lang)
                    got = self.prep(role)["prompt"]
                    self.assertEqual(squeeze(got), squeeze(self.current(role, lang, [])))

    def test_prompts_with_rejections(self):
        rolekit = self.steps.rolekit
        for role in FILES:
            with self.subTest(role=role):
                self.setUp()
                self.reach(role)
                self.reject(role, 2)
                reasons = rolekit.rejected(self.place, self.steps.files.ROLES[role])
                self.assertEqual(len(reasons), 2)
                got = self.prep(role)["prompt"]
                self.assertEqual(squeeze(got), squeeze(self.current(role, "", reasons)))
                self.assertIn(reasons[0].split("：")[0][:20], got)

    def test_resubmit_prompts(self):
        rolekit = self.steps.rolekit
        for role in FILES:
            with self.subTest(role=role):
                self.setUp()
                self.reach(role)
                self.reject(role, 1)
                name = self.steps.files.ROLES[role]
                path, _ = rolekit.write_resubmit(self.place, name, "old-{n}.md", rolekit.FIELD_RULES)
                self.assertEqual(squeeze(self.fix_prep(role)["prompt"]), squeeze(path.read_text(encoding="utf-8")))

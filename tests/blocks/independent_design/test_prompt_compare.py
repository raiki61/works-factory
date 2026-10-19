"""指示の比べ（docs/design/README.md の 11.4。1 つ目の commit だけ。2 つ目の commit で英語にする時に消す）。

block の design_prep が日本語の md から組む指示と system prompt が、今の事前審査の指示（workflows/plan-review/commands/r2-design.md に
lib/boardview.py の r2_prompt が組む本文を差し込んだ物）と今の YAML の systemPrompt の字と、空白と改行の違いを除いて同じになることを、
同じ値で照らす。却下の段落は断片 rejected（共通の断片）に替わったので照らさない。
"""
import json
import pathlib

import yaml

from tests.blocks import kit
from tests.blocks.independent_design import values
from tests.blocks.independent_design.test_independent_design import HOOK, _RepoCase, dump

PLAN_REVIEW = kit.ROOT / "workflows" / "plan-review"
REVIEW = {"verdict": "狭めている", "reason": "r", "findings": [{"text": "cite の無い行"}]}


def squeeze(text: str) -> str:
    return "".join(text.split())


class CompareCase(_RepoCase):
    def setUp(self):
        super().setUp()
        self.boardview = __import__("boardview")
        self.old = self.run.artifacts.parent / "old"
        self.old.mkdir()

    def old_text(self, *, constraints, answers=None, request="", policy="", review=None, base="") -> str:
        """今の指示: r2-design.md の差し込みの所に r2_prompt の本文を入れた字"""
        files = {"purpose.json": {"purpose_text": values.PURPOSE}, "premises.json": {"constraints": constraints}}
        for name, doc in files.items():
            (self.old / name).write_text(dump(doc), encoding="utf-8")
        start = {}
        if request:
            start["request_file"] = request
        if base:
            start["input"] = {"base": {"rev": base}}
        (self.old / "start.json").write_text(dump(start), encoding="utf-8")
        review_file = None
        if review is not None:
            review_file = self.old / "review.json"
            review_file.write_text(dump(review), encoding="utf-8")
        folder = self.old / "folder"
        if policy:
            folder.mkdir()
            (folder / self.boardview.POLICY_FILE).write_text(dump({"copy": policy}), encoding="utf-8")
        body = self.boardview.r2_prompt(
            folder, cwd=self.run.repo, purpose=self.old / "purpose.json", premises=self.old / "premises.json",
            purpose_review=review_file, start=self.old / "start.json", answers=answers)
        return (PLAN_REVIEW / "commands" / "r2-design.md").read_text(encoding="utf-8").replace("$r2-prep.output.prompt", body)

    def new_text(self, **inputs) -> dict:
        self.assertTrue(self.intake(**inputs)["due"])
        return self.prep()

    def same(self, old: str, new: dict):
        self.assertEqual(squeeze(new["prompt"]), squeeze(old))
        doc = yaml.safe_load((PLAN_REVIEW / "works-factory-plan-review.yaml").read_text(encoding="utf-8"))
        nodes = next(n for n in doc["nodes"] if n["id"] == "r2-design-loop")["loop_group"]["nodes"]
        self.assertEqual(squeeze(new["system"]), squeeze(next(n for n in nodes if n["id"] == "r2-design")["systemPrompt"]))

    def test_example_run_values(self):
        """例の run の値（承認ノードの答え 1 つ・実測した制約 2 つ・依頼のファイル無し・方針無し・監査無し）"""
        old = self.old_text(constraints=values.CONSTRAINTS, answers=values.ANSWERS)
        self.same(old, self.new_text(constraints=dump(values.CONSTRAINTS), answers=dump(values.ANSWERS)))

    def test_no_answers_no_constraints(self):
        self.same(self.old_text(constraints=[]), self.new_text())

    def test_request_policy_unvetted_review_and_marks(self):
        request = self.write("request.md", "`docs/design.md` 2 節 の通りに直す\n")
        policy = self.write("policy.md", "方針の印 POLICY-QRS: 環境は 1 か所で組む\n")
        rows = [{"text": f"{HOOK}:74 が足した行", "measured_how": "sed", "kind": "仮説"}]
        old = self.old_text(constraints=rows, answers=values.ANSWERS, request=request, policy=policy, review=REVIEW, base=self.base)
        new = self.new_text(constraints=dump(rows), answers=dump(values.ANSWERS), request=request, policy=policy,
                            purpose_review=dump(REVIEW), base=self.base)
        self.same(old, new)
        self.assertIn("POLICY-QRS", new["prompt"])
        self.assertIn("足した行", new["prompt"])

    def test_big_policy_is_cut_like_today(self):
        policy = self.write("policy.md", "あ" * 20000)
        self.same(self.old_text(constraints=[], policy=policy), self.new_text(policy=policy))

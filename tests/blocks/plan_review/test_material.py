"""事前審査の block の材料の試験の代表 2 本（docs/design/plan-review.md の 15.4）: 形 replan の材料に、裁かれた項目の前の形・修正の段の
申し出と裁定・直した形が載り（keep-essence の 8 の読み手）、独立設計の節がその前に在る（9 の読み手）。script（intake → review_prep）を
子のプロセスで回し、place に書かれた材料のファイル review-material-<n>.md と組んだ指示を読む。ほかの材料と指示の字の照らしは持ち主の決め
tests-guard-writes で落とした（値が md の印に渡ることは workflows/.shared/prompt.py の emit が全体に照らす）。
"""
import json
import re
import unittest

from tests.blocks import kit
from tests.blocks.plan_review import values as V

material = kit.load("plan-review", "material")
files = material.files
import converge   # noqa: E402  lib/（kit.load が ports を通して sys.path に足した）

CONFLICT = {"id": "c-clamp", "unit_key": V.UNIT_CLAMP, "between": ["項目 2", "test_stats.py"],
            "why_both_cannot_hold": "上限の枝の試験が lo を期待していて案と両立しない", "kind": "brief_vs_judgment",
            "which_is_right": "test", "ruling": {"decision": "fix_plan_item", "text": "RULING-MARK-3131 試験の側を正とせよ"}}


class _Case(unittest.TestCase):
    def setUp(self):
        self.r = V.Block(self)

    def intake(self, **over) -> dict:
        got = self.r.intake(**self.r.plan_inputs(**over))
        self.assertTrue(got["due"], got)
        return got

    def prep(self, prev="") -> dict:
        return self.r.script("review_prep", prev=prev)

    def latest(self, pattern: str) -> str:
        got = sorted(self.r.artifacts.glob(pattern), key=lambda p: int(re.search(r"-(\d+)\.md$", p.name).group(1)))
        self.assertTrue(got, pattern)
        return got[-1].read_text(encoding="utf-8")

    def prior(self, first_review) -> str:
        """1 往復目の place の往復の記録の作業の写しに、受けた返答の往復の行を足した物（line が持つ記録）の pointer"""
        doc = json.loads((self.r.artifacts / files.CONVERGE).read_text(encoding="utf-8"))
        converge.add_pass(doc, first_review, answers=doc["open"].get("answers", []), resolved=[])
        doc["precedent_checks"] = {}
        return self.r.put("line/prior.json", doc)

    def replan(self, **over) -> tuple[str, str]:
        """1 往復目を穴なしで通した後、項目 2 を直した案の形 replan の (指示, 材料)"""
        self.intake(**over)
        prior = self.prior(V.review())
        items = [V.item(V.UNIT_MEAN, 1), V.item(V.UNIT_CLAMP, 2, approach=f"{V.PLAN_MARK} 直した項目 2")]
        got = self.r.intake(**self.r.plan_inputs(items, rnd=2, prior=prior, ruling=json.dumps(["2"]),
                                                 conflicts=self.r.put("fix/conflicts.json", {"items": [CONFLICT]}), **over))
        self.assertEqual((got["due"], got["form"], got["tree"]), (True, "replan", False), got)
        out = self.prep()
        return out["prompt"], self.latest("review-material-*.md")


class ReplanCase(_Case):
    def test_replan_is_one_shot(self):
        """元 ReplanCase.test_replan_is_one_shot の材料の半分: 裁かれた項目ごとに前の形・申し出と裁定・直した形を貼り、指示は案の直しの
        頼みと works の欄の見方を持つ。往復の頼みは無い"""
        prompt, mat = self.replan()
        for want in (material.MAT_HEADS["replan"], material.LABELS["replan_item"].format(n=2), material.LABELS["approved"],
                     material.LABELS["revised"], material.LABELS["objection"].format(id="c-clamp"), "RULING-MARK-3131", "直した項目 2"):
            self.assertIn(want, mat, want)
        self.assertNotIn(material.LABELS["replan_item"].format(n=1), mat)
        for want in ("## Review of a replan", "## How to read the works fields"):
            self.assertIn(want, prompt)
        self.assertNotIn("Answers to earlier passes", prompt)
        self.assertNotIn(material.MAT_HEADS["passes"], mat)

    def test_replan_material_carries_the_independent_design(self):
        """元 ReplanCase.test_replan_material_carries_the_independent_design: 設計の節が裁かれた項目の節より前（独立設計の使い回しの
        読み手。docs/design/independent-design.md の 9 節）"""
        prompt, mat = self.replan(design=V.dump(V.DESIGN_OK))
        at = [mat.index(w) for w in (material.MAT_HEADS["design"], V.DESIGN_TEXT, material.MAT_HEADS["replan"],
                                     material.LABELS["replan_item"].format(n=2))]
        self.assertEqual(at, sorted(at))
        self.assertIn("Compare the plan with the independent design", prompt)

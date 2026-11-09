"""block r2 の入力の形（docs/design/r2.md の 8 節）。keep-essence の 9 の R2: 比べる役に判定・修正案・単位の目録・修正の結末を運ぶ
port が無いことを、YAML の入力の鍵で照らす（独立の守り）。役の形（道具・群・返答の型）は tests/layers の全体の検査が見る。"""
import unittest

import yaml

from tests.blocks import kit

DOC = yaml.safe_load((kit.BLOCKS / "r2" / "works-factory-r2.yaml").read_text(encoding="utf-8"))


class IsolationCase(unittest.TestCase):
    def test_inputs_carry_no_judgment_or_plan(self):
        """keep-essence の 9 の R2（元 test_r2_compare_gets_no_forbidden_input）: 比べる役に判定・修正案・単位の目録・修正の結末を運ぶ port が無い。
        means は依頼の文から外した頼みの解き方で、そのどれでもない（docs/design/plan-review.md の 20 章の 6.2 の 1）"""
        self.assertEqual(sorted(DOC["inputs"]), sorted(["base", "head", "base_label", "purpose", "means", "design", "design_reason",
                                                       "design_premises", "answers", "request", "changed", "constraints", "test_outcomes",
                                                       "tdd", "lang"]))
        for banned in ("judgment", "plan", "units", "fixes", "materials"):
            self.assertNotIn(banned, DOC["inputs"])


if __name__ == "__main__":
    unittest.main()

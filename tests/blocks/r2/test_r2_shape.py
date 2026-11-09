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


class StatusWordsCase(unittest.TestCase):
    def test_status_words_are_the_seal_words(self):
        """比べる役の返答の型の status の語が lib/seal.py の目の状態の語のうち R2 が言える物（unverifiable は前提の検算の道が持つ）と
        同じ（元 test_r2_shape.py の test_role_schemas_match_graph の status の照らし）。redesign-needed が型から落ちると作り直しを返せない"""
        kit.load("r2", "files")   # lib/ を sys.path に足す
        import seal
        node = next(n for n in DOC["nodes"] if n["id"] == "r2-compare")
        self.assertEqual(tuple(node["output_format"]["properties"]["status"]["enum"]),
                         tuple(s for s in seal.STATUSES if s != seal.UNVERIFIABLE))


if __name__ == "__main__":
    unittest.main()

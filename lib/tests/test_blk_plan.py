"""修正案と事前審査のブロック（blk-plan。P1 計画 Task 25・〔線A計〕T11・裁定 P1-R10・R44・R50）の検査。

- 独立設計（r2.design）: 修正案より前に道具ゼロの役で作り、盤面の根の design.json に控える（core の design）。事前審査の指示書の
  頭にその設計が載る。3 回とも拒まれても止めず、事前審査は「設計が無い」と読んで進む（人の条件 (2)）。目的の出典が R2 に使えない
  run は起こさない（写しの p4.assemble と同じ式を、p4.assemble より前に元の出典から出す）

- YAML の形: 役の output_format が planblk.output_format（写しの schema に印）と同じ・輪の中の id が全部のブロックをまたいで一意・
  役の輪は 1 輪 1 AI の節で fresh_context（直しの役の輪だけは会話の続きで false）・諦めの数と max_iterations が同じ・until_bash は
  同じ輪の受け付けの done・事前審査は壁打ちの外の輪 converge-loop の中（輪の中の輪。依頼 231）・スクリプトが読む INPUTS_* と
  with: の鍵が同じ・役に届く文に $LOOP_PREV が無い・筋書き 3 本
- スクリプト: 別のプロセスで実行基盤と同じ形（cwd は対象・成果物の置き場・INPUTS_*）に回す。盤面は linekit の種で start →
  並行 PR・前提・判定を entry.take で受けた物（p2.fix_plan が待つ）。指示書は本線の写し（gl-prompts）を rolekit の描き方で描いた物
"""
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True
LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import planblk  # noqa: E402
import planmarks  # noqa: E402


class PlanFieldsCase(unittest.TestCase):
    """修正案の項目の works の欄（planmarks）: 受け付けが欠けを盤面へ渡す前に拒み、通った案は欄を外して盤面に渡し、欄は盤面の
    plan-fields.json に控える（盤面が受けた時だけ）。修正案の役の頭に欄の指示、事前審査の役の頭に欄の JSON が載る"""

    def test_heads(self):
        self.assertIn(planmarks.HEAD, planblk.head("plan"))
        self.assertNotIn(planmarks.HEAD, planblk.head("plan-review"))


class ConceptRuleCase(unittest.TestCase):
    """修正案と事前審査の頭に判断の 1 軸と考えの住処の観点（core の concepthome）が載り、考えの地図の節は包みの差し込みの表が
    旗 concept-map の起動に配る（計画 2026-10-09-clean-whole の Task 2.7）"""

    def test_plan_head_has_concept_rule(self):
        import concepthome
        self.assertIn(concepthome.PLAN_RULE, planblk.HEAD["plan"])
        self.assertIn(concepthome.REVIEW_ASK, planblk.HEAD["plan-review"])
        self.assertNotIn(concepthome.REVIEW_ASK, planblk.HEAD["plan"])


class QuoteFoldCase(unittest.TestCase):
    """引用の照らし（cite.missing_quotes）は両側を NFKC にし、空白の並びを 1 つに畳んでから字のまま在るかを見る。字の 1 つ違いは見逃さない"""

    def test_width_and_whitespace_folded_but_one_char_difference_missing(self):
        import cite
        source = "上限は入口 1 箇所で掛ける。\n呼び手は値を渡すだけにする"
        self.assertEqual(cite.missing_quotes("「上限は入口 1 箇所で掛ける。 呼び手は値を渡す」", source), [])
        self.assertEqual(cite.missing_quotes("「上限は入口 １ 箇所で掛ける」", source), [], "全角の数字は NFKC で半角と同じ")
        self.assertEqual(cite.missing_quotes("「上限は入口 2 箇所で掛ける」", source), ["上限は入口 2 箇所で掛ける"])
        self.assertEqual(cite.missing_quotes("引用の無い文", source), [])
        self.assertEqual(cite.quotes("短い「ab」と「四文字以上の引用」"), ["四文字以上の引用"], "4 字未満は引用に数えない")

    def test_request_quote_check_of_sources_stays_literal(self):
        """関所の決め手の依頼の引用の照らし（cite.sources_problem）は畳まない: 全角と半角・空白だけが違う引用は依頼の文に無いと拒む"""
        import cite
        request = "上限は入口 1 箇所で掛ける"
        for quote in ("上限は入口 １ 箇所で掛ける", "上限は入口  1 箇所で掛ける", "上限は入口 1箇所で掛ける"):
            with self.subTest(quote):
                self.assertIn("依頼の文に無い", cite.sources_problem(f"依頼の本文「{quote}」", ".", quoted=request))
        self.assertEqual(cite.sources_problem("依頼の本文「上限は入口 1 箇所で掛ける」", ".", quoted=request), "")


if __name__ == "__main__":
    unittest.main()

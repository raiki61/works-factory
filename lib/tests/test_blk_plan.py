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
import json
import pathlib
import sys
import tempfile
import types
import unittest

sys.dont_write_bytecode = True
LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import converge  # noqa: E402
import design  # noqa: E402
import gatemarks  # noqa: E402
import planblk  # noqa: E402
import planmarks  # noqa: E402

# r2.design の役の型のうち design_only が読む欄（本物の型はブロックが盤面に持たせる）
DESIGN_SCHEMA = {"type": "object", "required": ["question_stands", "reason", "design"],
                 "properties": {"question_stands": {"type": "boolean"}, "reason": {"type": "string"},
                                "design": {"type": "string"}}}


class PlanFieldsCase(unittest.TestCase):
    """修正案の項目の works の欄（planmarks）: 受け付けが欠けを盤面へ渡す前に拒み、通った案は欄を外して盤面に渡し、欄は盤面の
    plan-fields.json に控える（盤面が受けた時だけ）。修正案の役の頭に欄の指示、事前審査の役の頭に欄の JSON が載る"""

    def test_heads(self):
        self.assertIn(planmarks.HEAD, planblk.head("plan"))
        self.assertNotIn(planmarks.HEAD, planblk.head("plan-review"))


class ScriptCase(unittest.TestCase):
    def test_head_asks_no_narrow_first(self):
        """修正案の役の頭は、narrows を書く前に狭めない案を探し、無い時だけ no_narrow に結果を書けと言う。事前審査の役の頭は、
        regression の穴に示せる時だけ添えよと言う"""
        plan, review = planblk.head("plan"), planblk.head("plan-review")
        self.assertIn("狭めない案を先に探せ", plan)
        self.assertIn(f"{gatemarks.NO_NARROW}＝探した結果", plan)
        self.assertIn("狭めない案を添えよ", review)
        self.assertNotIn("狭めない案を先に探せ", review)

    def test_design_ask_names_unpaired_mechanisms_and_item_size_gap(self):
        """事前審査の頭に貼る DESIGN_ASK は、対の無い仕組みも大きさの開きも、食い違いなら contract_drift・block で挙げさせる。判じる根拠は
        独立設計の行と案の行（approach・adds・allowed_paths・shrink_first）の「…」の引用で、設計から引用できない所は開きでも対の無さでも
        食い違いに数えない（1 つの決まり）。why の頭は design.DRIFT_HEAD・design.UNPAIRED_HEAD、対応表 design_map は項目の答えが書き
        （相乗りの審査と束ね役は書かない）、「」は 2 つの頭の穴の why と design_map では独立設計と案の行の引用だけに使う。実装の細部は
        挙げない決まりと REUSE_REVIEW の copy を挙げ直さない決まりは残る"""
        ask = planblk.DESIGN_ASK
        self.assertIn("contract_drift", ask)
        self.assertIn("severity block", ask)
        self.assertIn("設計から引用できない所は、大きさの開きでも対の無さでも食い違いに数えない", ask)
        for name in ("approach", "adds", "allowed_paths", "shrink_first", "「…」", design.DRIFT_HEAD, design.UNPAIRED_HEAD):
            self.assertIn(name, ask, f"DESIGN_ASK に {name!r} の名指しが無い")
        self.assertIn(converge.DESIGN_MAP, ask)
        self.assertIn("相乗りの審査と束ね役は書かない", ask)
        self.assertIn("「」を独立設計と案の行の引用だけに使い", ask)
        self.assertIn("単位を閉じるのに要る実装の細部は挙げない", ask)
        self.assertIn("REUSE_REVIEW", ask)
        self.assertNotIn("設計が触れていない所は食い違いでない", ask, "引用の決まりと食い違う除外の文は残さない")
        self.assertNotIn("kind scope_creep", ask, "対の無い仕組みは suggest に回さず contract_drift・block で挙げる")


class ConvergeReviseCase(unittest.TestCase):
    def test_revise_role_is_fix_plan_node(self):
        role = planblk.REVISE_ROLE
        self.assertEqual(role, "plan-revise")
        self.assertEqual(planblk.known_role(role), "p2.fix_plan")
        self.assertEqual(planblk.snapshot_name(role), "plan-revise-snapshot.json")
        self.assertNotIn(role, planblk.NODE_OF)   # collect の役の並びは今のまま
        self.assertNotIn(role, planblk.ROLES)


class DesignReadCase(unittest.TestCase):
    """盤面の根の design.json は r2.design の役の型（盤面の design_schema）で確かめてから読む。型に合わない控えは壊れた控えとして
    設計が無い理由に回し、design_only は欄を引いて落ちない"""

    def board(self, doc):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        (pathlib.Path(tmp.name) / design.DESIGN_FILE).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return types.SimpleNamespace(dir=pathlib.Path(tmp.name), design_schema=DESIGN_SCHEMA)

    def test_design_off_the_schema_is_missing_not_a_key_error(self):
        text = planblk.design_only(self.board({"missing": "型の外の控え"}))
        self.assertIn(planblk.DESIGN_HEAD, text)
        self.assertIn(design.MISSING, text)
        self.assertIn("型が合わない", text)

    def test_design_on_the_schema_is_pasted(self):
        text = planblk.design_only(self.board({"question_stands": True, "reason": "立つ", "design": "DESIGN-本文"}))
        self.assertIn("DESIGN-本文", text)


class ConceptRuleCase(unittest.TestCase):
    """修正案と事前審査の頭に判断の 1 軸と考えの住処の観点（core の concepthome）が載り、考えの地図の節は包みの差し込みの表が
    旗 concept-map の起動に配る（計画 2026-10-09-clean-whole の Task 2.7）"""

    def test_plan_head_has_concept_rule(self):
        import concepthome
        self.assertIn(concepthome.PLAN_RULE, planblk.HEAD["plan"])
        self.assertIn(concepthome.REVIEW_ASK, planblk.HEAD["plan-review"])
        self.assertNotIn(concepthome.REVIEW_ASK, planblk.HEAD["plan"])


class RejectHeadOwnerCase(unittest.TestCase):
    """受け付けの拒みの頭と木の下限は planblk が 1 つだけ持ち、plan の受け付け（planfile）と事前審査の受け付け（boardview）は
    それを読む。事前審査の役の頭は works-factory に無い盤面を名指さない（issue #81）"""

    NAMES = ("NO_NARROW_REJECT", "RECOMMEND_REJECT", "NOT_OWED_REJECT", "RESOLVED_REJECT", "ANSWERS_REJECT",
             "TREE_REJECT", "CLOSED_REJECT", "DESIGN_QUOTE_REJECT", "TREE_AUTO_MIN")

    def test_reject_heads_live_in_planblk(self):
        import boardview
        import planfile
        for name in self.NAMES:
            with self.subTest(name=name):
                self.assertTrue(hasattr(planblk, name))
                for reader in (planfile, boardview):
                    self.assertFalse(hasattr(reader, name), f"{reader.__name__}.{name}")

    def test_review_head_names_no_board(self):
        self.assertNotIn("盤面", planblk.HEAD["plan-review"])
        self.assertNotIn("盤面", planblk.head("plan-review"))


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

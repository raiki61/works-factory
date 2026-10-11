"""ラインの入力の名の集合を正本（darkfactory.yaml の inputs）に縛る。YAML とスクリプトを読み、entry.check_inputs を直に呼び、
linekit.LineRun を種の git を差し替えて組むだけ（FAST。git・子のプロセスなし）。前は重い段の test_line にしか無く、名の食い違いが速い段で見えなかった。

- yaml の inputs の名 == ラインの節（inputs の外の全部の値）が参照する $INPUTS.<名>（test_yaml_inputs_are_all_referenced）
- 線とブロックの全部の script の節で、with: の鍵を INPUTS_<大文字> にした集合 == スクリプトの定数 INPUTS（TA16。
  test_script_inputs_match_with）。既定の在る入力は定数 OPTIONAL_INPUTS に名指した物だけ with: に無くてよい
- start.py の INPUTS の名ごとに、entry.check_inputs が渡した値を同じ名で返す（test_check_inputs_passes_every_start_name）。
  変更の入口の base・pr だけは base_rev・change に解いて返す（merge-base は差し替え、pr は番号でない値の拒みで読みを見る）
- 報告の言語 lang がラインから start の with に渡り、start.py が読み、空は空のまま返る（LangInputCase）
- 器 linekit.LineRun が start へ渡す入力の鍵は LINE_ORDER の start の with から導く（test_linerun_inputs_follow_line_order_start。
  種の git は作らない）
- 出力の側（OutputNamesCase。実行基盤の穴 #2・#3）: 本文の $<節>.output.<欄> が同じ工程の節と出力の型の欄を名指す
  （test_output_refs_name_real_fields）。ラインの節の出力の欄に読み手が在る（無い欄は UNREAD_OUTPUTS に理由つき。
  test_line_outputs_have_readers）
"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import entry  # noqa: E402


class FeaturesOffCase(unittest.TestCase):
    """切る機能と入れる機能（入力 features_off・features_on。持ち主の依頼 2026-10-07: 同じ依頼を機能を替えて回して比べる）:
    check_inputs が語を確かめて語の順の配列にし、start の出口の機能ごとの on・off・auto（entry.feature_words）を線がブロックの
    切り替えの入力へ写す。既定は持ち主の決め 2026-10-08（測りで後の段を変えなかった判定の裏取りは off・事前審査の木は開いた項目が
    2 つ以上の往復だけ＝auto・ほかは on）。名指した語は既定に勝ち、同じ語を両方に名指せば拒む"""
    DEFAULTS = {"fix_lanes": "on", "graph_map": "on", "judge_verify": "off", "review_tree": "auto", "tdd_lanes": "on",
                "world": "on"}

    def test_named_words_beat_defaults(self):
        """features_on は既定の off・auto を on にし、features_off は既定の auto を off にする（名指した語が既定に勝つ）"""
        got = entry.feature_words([], ["judge_verify", "review_tree"])
        self.assertEqual(got, {k: "on" for k in entry.FEATURES})
        self.assertEqual(entry.features_part([], ["judge_verify", "review_tree"]), "機能: 全部 on")
        self.assertEqual(entry.feature_words(["tdd_lanes"], ["judge_verify"]),
                         {**self.DEFAULTS, "judge_verify": "on", "tdd_lanes": "off"})
        self.assertEqual(entry.features_part(["tdd_lanes"], ["judge_verify"]), "機能: review_tree auto・tdd_lanes off")
        self.assertEqual(entry.feature_words([], ["fix_lanes"]), self.DEFAULTS)   # 既定で on の語を入れても同じ

    def test_features_on_of_reads_any_board(self):
        """features_on_of（canary_check がどの版の盤面も読む口）: features_on の欄の無い前の版の控えは、その版の既定（全部 on）で
        読む"""
        old = {"features_off": ["tdd_lanes"]}
        self.assertEqual(entry.features_on_of(old), ["judge_verify", "review_tree"])
        self.assertEqual(entry.features_on_of({"features_off": ["judge_verify"]}), ["review_tree"])
        self.assertEqual(entry.features_on_of({"features_off": [], "features_on": []}), [])
        self.assertEqual(entry.features_cut([], []), ["judge_verify"])
        self.assertEqual(entry.features_cut(["tdd_lanes"], ["judge_verify"]), ["tdd_lanes"])


if __name__ == "__main__":
    unittest.main()

"""line の入力の機能の語の決まり（元 lib/tests/test_line_inputs.py の写し。integration.md の 4.2-9。段の表は blocks/line/src/tiers.py）。

元の試験のうち残っていた FeaturesOffCase: 切る機能と入れる機能（入力 features_off・features_on）を start が確かめて語の順の配列にし、
機能ごとの on・off・auto（lib/entry.py の feature_words）を line が配る値に写す。名指した語は既定に勝ち、段の足しは名指しの切りに負ける。
"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[3] / "lib"
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import entry  # noqa: E402

from tests.blocks import kit  # noqa: E402

depth = kit.load("line", "tiers")   # 元 lib/depth.py の段の表は line の src/tiers.py（docs/design/line.md の 5.1）


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

    def test_heavy_adds_features_unless_named_off(self):
        """重厚の深さの足し（depth.tier_adds）は judge_verify と review_tree を on にし、features_off で名指して切った機能は off のまま
        （名指し > 足し > 既定）。足しが空なら今の既定"""
        heavy = depth.tier_adds(depth.HEAVY)
        self.assertEqual(heavy, ("judge_verify", "review_tree"))
        self.assertEqual(entry.feature_words([], [], heavy), {**self.DEFAULTS, "judge_verify": "on", "review_tree": "on"})
        self.assertEqual(entry.feature_words(["judge_verify"], [], heavy), {**self.DEFAULTS, "review_tree": "on"})
        self.assertEqual(entry.feature_words([], [], ()), self.DEFAULTS)
        self.assertEqual(entry.features_cut(["judge_verify"], [], heavy), ["judge_verify"])
        self.assertEqual(entry.features_cut([], [], heavy), [])
        self.assertEqual(entry.features_part([], [], heavy), "機能: 全部 on")
        self.assertEqual(entry.features_part(["judge_verify"], [], heavy), "機能: judge_verify off")
        for adds, off, want in ((heavy, [], ("on", "on")), (heavy, ["judge_verify"], ("off", "on")),
                                (heavy, ["review_tree"], ("on", "off")), ((), [], ("off", "auto"))):
            doc = {"features_off": off, "features_on": []}
            with self.subTest(adds=adds, off=off):
                self.assertEqual((entry.switch(doc, "judge_verify", adds), entry.switch(doc, "review_tree", adds)), want)
        self.assertEqual(entry.switch(None, "review_tree"), "auto")
        self.assertEqual(entry.switch({"features_on": ["review_tree"]}, "review_tree"), "on")
        self.assertEqual(depth.tier_adds(depth.STANDARD), ())
        self.assertEqual((depth.tier_adds(""), depth.tier_adds("極厚"), depth.tier_adds(None)), ((), (), ()))

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

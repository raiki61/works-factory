"""単位ごとの深さ（darkfactory/lib/depth.py。計画 docs/plans/2026-10-06-variable-depth.md）の検査。関数を直に呼び、一時の置き場に
控えを書くだけ（FAST。盤面・git・子のプロセスなし）。

語:
- 深さ: 単位の工程の厚さ。標準は今の振る舞いのすべて、軽量は測りで何も見つけなかった確かめ（レンズ・コメントの削除候補）を省く。
- 項目の欄: 修正案の項目ごとの works の欄（allowed_paths・tests・rewrite_tests・unit_keys）。
- 上げる信号: 修正の後に単位を標準へ上げる事実（食い違いの申し出・止めた単位・案の直し・再審・答えていない問い・引用の外の差分・
  TDD のループでの修正役の拒否・範囲の相談）。

見る物:
- 決め 3 の 5 つの条件を全部満たす単位だけが軽量で、1 つ外れれば標準と理由
- thickness の名指しで全部の単位を固定する（自動と空は機械が決める）
- 信号で上げる（単位に結べる物はその単位、結べない物は全部）・下げない。修正の後の 3 つの事実の理由の文と、引用の外のパスの拾い方
- run の深さは全部が軽量の時だけ軽量（単位が無ければ標準）
- 省く理由と報告の行（軽量で省いた物を名指す）
- 控えの書き読み
"""
import json
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように
LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import depth  # noqa: E402
import tddloop  # noqa: E402

U1, U2 = "u1: 一つ目の根本", "u2: 二つ目の根本"


def item(keys, paths=("a/b.py",), tests=1, rewrites=0):
    return {"unit_keys": list(keys), "allowed_paths": list(paths),
            "tests": [{"id": f"t.py::T::t{i}"} for i in range(tests)],
            "rewrite_tests": [{"id": f"r.py::R::r{i}"} for i in range(rewrites)]}


class UnitDepthCase(unittest.TestCase):
    def test_small_unit_with_checks_is_light(self):
        got, why = depth.unit_depth([item([U1], paths=("a.py", "b.py", "tests/t.py"), tests=1, rewrites=1)], U1, checked=True)
        self.assertEqual(got, depth.LIGHT)
        self.assertTrue(why)

    def test_each_condition_falls_to_standard_with_reason(self):
        cases = {
            "項目": ([item([U2])], True),
            "4 個": ([item([U1], paths=("a.py", "b.py", "c.py", "d.py"))], True),
            "glob": ([item([U1], paths=("tests/*.json",))], True),
            "3 本": ([item([U1], tests=2, rewrites=1)], True),
            "約束の形": ([item([U1], paths=("blk-x/schemas/a.schema.json",))], True),
            ".yml": ([item([U1], paths=(".github/workflows/test.yml",))], True),
            "darkfactory.yaml": ([item([U1], paths=("a.py", "darkfactory/darkfactory.yaml"))], True),   # 配線とコードを一緒に触る
            "機械の確かめ": ([item([U1])], False),
        }
        for word, (items, checked) in cases.items():
            with self.subTest(word=word):
                got, why = depth.unit_depth(items, U1, checked=checked)
                self.assertEqual(got, depth.STANDARD)
                self.assertTrue(any(word in w for w in why), why)

    def test_wiring_only_unit_is_light(self):
        """配線だけの単位（線とブロックの YAML（<名>/<名>.yaml）と manifest.json だけを触る）は、約束の形の条件に数えず軽量"""
        for paths in (("darkfactory/darkfactory.yaml",), ("blk-fix/blk-fix.yaml", "blk-fix/manifest.json"),
                      ("works/blk-plan/blk-plan.yml", "works/darkfactory/manifest.json", "works/darkfactory/darkfactory.yaml")):
            with self.subTest(paths=paths):
                got, why = depth.unit_depth([item([U1], paths=paths, tests=0)], U1, checked=True)
                self.assertEqual(got, depth.LIGHT, why)
                self.assertTrue(any("配線だけ" in w for w in why), why)

    def test_wiring_only_still_needs_the_other_conditions(self):
        for word, (items, checked) in {
            "4 個": ([item([U1], paths=("a/a.yaml", "b/b.yaml", "c/c.yaml", "d/manifest.json"))], True),
            "3 本": ([item([U1], paths=("a/a.yaml",), tests=3)], True),
            "機械の確かめ": ([item([U1], paths=("a/a.yaml",))], False),
            "約束の形": ([item([U1], paths=("a/a.yaml", "a/schemas/x.yaml"))], True),   # schemas/ の下は配線でない
            "nodes.json": ([item([U1], paths=("a/a.yaml", "a/nodes.json"))], True),     # 表は配線でない
        }.items():
            with self.subTest(word=word):
                got, why = depth.unit_depth(items, U1, checked=checked)
                self.assertEqual(got, depth.STANDARD)
                self.assertTrue(any(word in w for w in why), why)

    def test_no_items_is_standard(self):
        self.assertEqual(depth.unit_depth(None, U1, checked=True)[0], depth.STANDARD)


class DecideCase(unittest.TestCase):
    def test_auto_decides_per_unit(self):
        doc = depth.decide_doc([item([U1]), item([U2], paths=("a", "b", "c", "d"))], [U1, U2], forced="自動", checked=True)
        self.assertEqual({k: v["depth"] for k, v in doc["units"].items()}, {U1: depth.LIGHT, U2: depth.STANDARD})
        self.assertEqual(depth.run_depth(doc), depth.STANDARD)

    def test_empty_forced_is_auto(self):
        doc = depth.decide_doc([item([U1])], [U1], forced="", checked=True)
        self.assertEqual(doc["units"][U1]["depth"], depth.LIGHT)

    def test_forced_word_fixes_every_unit(self):
        big = item([U1], paths=("a", "b", "c", "d", "e"), tests=5)
        doc = depth.decide_doc([big], [U1], forced=depth.LIGHT, checked=False)
        self.assertEqual(doc["units"][U1]["depth"], depth.LIGHT)
        self.assertIn("名指し", " ".join(doc["units"][U1]["why"]))
        doc = depth.decide_doc([item([U1])], [U1], forced=depth.STANDARD, checked=True)
        self.assertEqual(doc["units"][U1]["depth"], depth.STANDARD)

    def test_no_units_is_standard_run(self):
        doc = depth.decide_doc(None, [], forced="", checked=True)
        self.assertEqual(depth.run_depth(doc), depth.STANDARD)
        self.assertEqual(depth.skip_reason(doc, depth.LIGHT), "")


class RaiseCase(unittest.TestCase):
    def setUp(self):
        self.doc = depth.decide_doc([item([U1]), item([U2])], [U1, U2], forced="", checked=True)
        self.assertEqual(depth.run_depth(self.doc), depth.LIGHT)

    def test_unit_signal_raises_only_that_unit(self):
        got = depth.raise_doc(self.doc, units={U1: "食い違いの申し出"}, run=[])
        self.assertEqual(got["units"][U1]["depth"], depth.STANDARD)
        self.assertEqual(got["units"][U2]["depth"], depth.LIGHT)
        self.assertIn("食い違いの申し出", " ".join(got["units"][U1]["why"]))
        self.assertEqual(depth.run_depth(got), depth.STANDARD)

    def test_run_signal_raises_every_unit(self):
        got = depth.raise_doc(self.doc, units={}, run=["案の直しが走った"])
        self.assertEqual({v["depth"] for v in got["units"].values()}, {depth.STANDARD})
        self.assertIn("案の直しが走った", got["raised"])

    def test_signal_on_unknown_unit_is_kept_as_raised(self):
        got = depth.raise_doc(self.doc, units={"u9": "止めた"}, run=[])
        self.assertEqual(depth.run_depth(got), depth.LIGHT)
        self.assertTrue(any("u9" in r for r in got["raised"]))

    def test_no_signal_keeps_light(self):
        got = depth.raise_doc(self.doc, units={}, run=[])
        self.assertEqual(depth.run_depth(got), depth.LIGHT)

    def test_late_signals_name_each_fact(self):
        """修正の後の 3 つの事実（引用の外の差分・TDD の拒否・範囲の相談）がそれぞれ run の理由 1 つになり、空の欄は理由を出さない。
        raise_doc に渡すと軽量の単位が標準へ上がり、下がらない"""
        self.assertEqual(depth.late_signals(), [])
        self.assertEqual(depth.late_signals(outside=[], refused=[], consulted=[]), [])
        got = depth.late_signals(outside=["x.py", "y.py"])
        self.assertEqual(len(got), 1)
        self.assertIn("修正の差分が頭の深さの引用した where の外に出た", got[0])
        self.assertIn("x.py", got[0])
        self.assertIn("y.py", got[0])
        got = depth.late_signals(refused=[U1, tddloop.ROUTE_REFUSED])
        self.assertEqual(len(got), 1)
        self.assertIn("TDD のループで修正役が拒まれた", got[0])
        self.assertIn(U1, got[0])
        self.assertIn(tddloop.ROUTE_REFUSED, got[0])
        got = depth.late_signals(consulted=["項目 2"])
        self.assertEqual(len(got), 1)
        self.assertIn("修正役が範囲の相談をした", got[0])
        self.assertIn("項目 2", got[0])
        every = depth.late_signals(outside=["x.py"], refused=[U1], consulted=[U2])
        self.assertEqual(len(every), 3)
        for run in ([r] for r in every):
            raised = depth.raise_doc(self.doc, units={}, run=run)
            self.assertEqual({v["depth"] for v in raised["units"].values()}, {depth.STANDARD}, run)
            self.assertEqual(raised["raised"], run)
        again = depth.raise_doc(depth.raise_doc(self.doc, units={}, run=every), units={}, run=[])
        self.assertEqual(depth.run_depth(again), depth.STANDARD, "上げた後に信号が無くても下げない")

    def test_outside_cited_skips_test_files(self):
        """cited の外のコードのファイルだけを返し（慣習の名と項目の tests で宣言したテストのファイルは除く）、cited が空なら空。
        run_wide と同じ除きで数える"""
        items = [item([U1], paths=("a/b.py",), tests=0)]
        items[0]["tests"] = [{"id": "checks/odd.py::T::t0"}]
        touched = ["a/b.py", "c/d.py", "tests/test_d.py", "checks/odd.py", "e/f.py", "c/d.py"]
        self.assertEqual(depth.outside_cited(items, [U1], touched, {"a/b.py"}), ["c/d.py", "e/f.py"])
        self.assertEqual(depth.outside_cited(items, [U1], touched, {"a/b.py", "c/d.py", "e/f.py"}), [])
        self.assertEqual(depth.outside_cited(items, [U1], ["tests/test_d.py", "checks/odd.py"], {"a/b.py"}), [])
        self.assertEqual(depth.outside_cited(items, [U1], touched, set()), [], "引用した where の無い run は外を持たない")
        self.assertEqual(depth.outside_cited(items, [U1], touched, ["./a/b.py", "c/d.py"]), ["e/f.py"])
        paths, _ = depth._wide(items, [U1], touched)
        self.assertEqual(paths, {"a/b.py", "c/d.py", "e/f.py"}, "run_wide の数えが除くテストのファイルと同じ")
        wide, count = depth.run_wide(items, [U1], touched)
        self.assertEqual(count, 3)


class LinesCase(unittest.TestCase):
    def test_light_run_names_what_it_skipped(self):
        doc = depth.decide_doc([item([U1])], [U1], forced="", checked=True)
        reason = depth.skip_reason(doc, depth.LIGHT)
        self.assertIn("軽量", reason)
        text = "\n".join(depth.lines(doc, depth.LIGHT, cmd_skipped=1))
        skipped = [x for x in depth.lines(doc, depth.LIGHT, cmd_skipped=1) if x.startswith("軽量で省いた: ")]
        self.assertEqual(len(skipped), 1, "省いた物は 1 行にまとめる（2026-10-09 の片付け）")
        for word in ("差分の審査", "レンズ", "r1.comment_candidates", "R1", "R2", "R3", "R4", "test_cmd"):
            self.assertIn(word, skipped[0])
        self.assertNotIn("AI の報告", text, "AI の報告は省かない（計画の決め 10）")

    def test_standard_run_skips_nothing(self):
        doc = depth.decide_doc([item([U1], tests=4)], [U1], forced="", checked=True)
        self.assertEqual(depth.skip_reason(doc, depth.LIGHT), "")
        text = "\n".join(depth.lines(doc, depth.LIGHT, cmd_skipped=0))
        self.assertNotIn("軽量で省いた", text)
        self.assertIn("標準", text)

    def test_only_a_light_head_omits(self):
        """issue #561: 単位がどれも軽量でも、run の頭の深さが標準・重厚・不明なら何も省かず、深さの行が省かない訳を言う。省く物は
        TIERS の omits"""
        doc = depth.decide_doc([item([U1])], [U1], forced="", checked=True)
        self.assertEqual(depth.run_depth(doc), depth.LIGHT)
        for head in (depth.STANDARD, depth.HEAVY, "", None, "極厚"):
            with self.subTest(head=head):
                self.assertEqual(depth.skip_reason(doc, head), "")
                text = "\n".join(depth.lines(doc, head, cmd_skipped=0))
                self.assertNotIn("軽量で省いた", text)
                self.assertIn("なので省かない", text)
        self.assertEqual(depth.TIERS[depth.LIGHT]["omits"], tuple(depth.OMITS))
        self.assertEqual((depth.TIERS[depth.STANDARD]["omits"], depth.TIERS[depth.HEAVY]["omits"]), ((), ()))


    def test_light_head_names_test_cmd_skip_of_light_units(self):
        """issue #561: 頭が軽量で軽量と標準の単位が混ざる run は、差分の審査と目は省かず、軽量の単位の test_cmd の省きだけを名指す。
        頭が標準・重厚なら test_cmd も省かない（fixboard.unit_depths が空）ので何も言わない"""
        doc = depth.decide_doc([item([U1]), item([U2], tests=4)], [U1, U2], forced="", checked=True)
        self.assertEqual(depth.skip_reason(doc, depth.LIGHT), "")
        self.assertIn(f"軽量の単位 1 個で省いた: {depth.UNIT_OMIT}", depth.lines(doc, depth.LIGHT, cmd_skipped=1))
        for head in (depth.STANDARD, depth.HEAVY, ""):
            with self.subTest(head=head):
                self.assertNotIn("省いた", "\n".join(depth.lines(doc, head, cmd_skipped=0)))


    def test_test_cmd_skip_is_named_only_when_the_loop_skipped_it(self):
        """PR #597: test_cmd が空・関門が off で TDD の輪が何も省かなかった run は、頭が軽量で単位が軽量でも test_cmd の省きを言わない。
        省いた数は輪の記録（cmd_skipped）で、上げ直しの後の深さからは数えない"""
        light = depth.decide_doc([item([U1])], [U1], forced="", checked=True)
        mixed = depth.decide_doc([item([U1]), item([U2], tests=4)], [U1, U2], forced="", checked=True)
        skipped = [x for x in depth.lines(light, depth.LIGHT, cmd_skipped=0) if x.startswith("軽量で省いた: ")]
        self.assertEqual(len(skipped), 1)
        self.assertNotIn("test_cmd", skipped[0])
        self.assertNotIn("省いた", "\n".join(depth.lines(mixed, depth.LIGHT, cmd_skipped=0)))
        raised = depth.raise_doc(light, units={}, run=["再審が走った"])
        self.assertIn(f"軽量の単位 1 個で省いた: {depth.UNIT_OMIT}", depth.lines(raised, depth.LIGHT, cmd_skipped=1))


class WordsCase(unittest.TestCase):
    def test_skipped_review_has_plain_word(self):
        """省いた目（記録の reviews の skipped）は、最後の関所と報告の目の行に平易な語で出る"""
        import gatemarks
        self.assertEqual(gatemarks.eye_named("R1", "skipped"), f"{gatemarks.EYES['R1']}（R1）: 軽量で省いた（skipped）")


def put(path: pathlib.Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

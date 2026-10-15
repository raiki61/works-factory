"""判定のブロック（blk-judge）の検査。

- YAML の口: 判定役の節の output_format が受け付けの規則の型（role_schema("p2.diagnose")）と同じか、良い返答の見本が
  YAML の output_format を通るか（設計書 5.4 節）。入口・出口・輪の形がブリーフどおりか
- つなぎのスクリプト: intake（依頼を読んで check_request。拒めば終了コード 1）・accept（単独の run は core の check_judge を
  script_io で包み、ラインの盤面は judgetake.take を rolekit.accept_round に渡す）・collect（盤面の judgment.json から出口を組む）を
  別のプロセスで回す
- class_query の例（QueryExamplesCase）: 当たるべき hits・当たってはならない misses で問いを試し、合わなければ拒み、通れば
  例を judgment.json に戻す（querytest。受け付けの口の中で試す）
- 筋書き（fixtures/）が 3 本在り、期待の形がブリーフどおりか。実行基盤で回すのは dev/check.sh（workflow test）
"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))


class UnprovenQueryCase(unittest.TestCase):
    """例の無い開いた単位は拒まずに「例で証明できない」印を付けて通す（querytest.unproven）。例を出せない単位は理由
    （examples_unavailable）で、defects の問いの misses を書けない単位は理由（misses_omitted_why）で出口を持つ。
    理由の欄は例の欄と同じく盤面へ渡す前に外す（split）。盤面・子のプロセスは使わない"""

    MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
    CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
    HOW = {"patterns": ["(len(xs) - 1)"], "fixed": True, "paths": ["stats.py"], "count": "lines"}
    WHY = "在るべき検査が無い形で、直した後の行を 1 行に書けない"

    def unit(self, key, **cq):
        return {"key": key, "class_query": {"how": self.HOW, "counts": "defects", "total": 1, **cq}}

    def querytest(self):
        import querytest
        return querytest

    def test_units_without_examples_are_marked_unproven(self):
        qt = self.querytest()
        self.assertTrue(hasattr(qt, "unproven"), "例で証明できない単位を返す口が無い")
        units = [self.unit(self.MEAN), self.unit(self.CLAMP, examples_unavailable=self.WHY),
                 self.unit("stats.py x: 例の在る単位", hits=["    return sum(xs) / (len(xs) - 1)"],
                           misses=["    return sum(xs) / len(xs)"])]
        got = {row["key"]: row["why"] for row in qt.unproven(units, lambda u: True)}
        self.assertEqual(set(got), {self.MEAN, self.CLAMP}, "例の在る単位は印の外")
        self.assertIn(self.WHY, got[self.CLAMP], "例を出せない理由を印に載せる")
        self.assertEqual(qt.unproven(units, lambda u: False), [], "開いていない単位は見ない")
        self.assertEqual(qt.problems(units[:2], lambda u: True), [], "例の無い単位は拒まない（印で人に見せる）")

    def test_misses_omitted_with_reason_is_accepted(self):
        qt = self.querytest()
        u = self.unit(self.MEAN, hits=["    return sum(xs) / (len(xs) - 1)"], misses_omitted_why=self.WHY)
        self.assertEqual(qt.problems([u], lambda u: True), [])
        self.assertTrue(qt.problems([self.unit(self.MEAN, hits=["    return sum(xs) / (len(xs) - 1)"])], lambda u: True),
                        "理由の無い misses の欠けは今までどおり拒む")

    def test_examples_unavailable_with_examples_is_rejected(self):
        qt = self.querytest()
        u = self.unit(self.MEAN, examples_unavailable=self.WHY, hits=["    return sum(xs) / (len(xs) - 1)"],
                      misses=["    return sum(xs) / len(xs)"])
        errs = qt.problems([u], lambda u: True)
        self.assertTrue(any("examples_unavailable" in e for e in errs), errs)

    def test_reason_fields_are_split_off(self):
        qt = self.querytest()
        reply = {"units": [self.unit(self.MEAN, examples_unavailable=self.WHY),
                           self.unit(self.CLAMP, hits=["    return sum(xs) / (len(xs) - 1)"], misses_omitted_why=self.WHY)]}
        out, _ = qt.split(reply)
        for u in out["units"]:
            with self.subTest(key=u["key"]):
                self.assertFalse({"examples_unavailable", "misses_omitted_why"} & set(u["class_query"]),
                                 "盤面へ渡す写しの class_query に理由の欄を残さない（写しの型は additionalProperties: false）")


if __name__ == "__main__":
    unittest.main()

"""修正の後のレンズ（lenses）の集めと、その控え lens.json を読む口（差分の審査の支度 refix.cut の brief・集計）。元
works/tests/test_blk_lens.py の場合のうち、盤面を使わずに回る物を、置き場のフォルダと引数の形に写した物。

振り分け（route）・境（exit_）・ブロックの YAML・報告（report）の試験は、盤面と blk-* を使うので持ってこない。振り分けの代わりに
控えの pending の行は lens.write_routes で置く（lens-prep の script が置く物と同じ形）。
"""
import json
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from lib.tests import test_blk_refix as RF  # noqa: E402
import lens  # noqa: E402
import lenses  # noqa: E402
import refix  # noqa: E402

FINDING = {"where": "stats.py", "cite": "return hi", "why": "上限を超えた値を黙って hi に丸め、呼び元は丸めたことに気づけない"}
LENS_REPLY = {"findings": [], "findings_none": "差分の stats.py と呼び元を読み、黙って失敗する所は無かった"}


class LensPlaceCase(RF.DeltaPlaceCase):
    def routed(self, go=True):
        """振り分けの代わり: 置き場の lens.json にレンズごとの pending（go 偽なら not_routed）の行を置く"""
        lens.write_routes(self.place, [{"lens": r["lens"], "agent": r["agent"], "go": go,
                                        "reason": "" if go else "変わったファイルに例外の扱いが無い"} for r in lenses.LENSES])

    def collect(self, raw):
        return lenses.collect(self.place, {"silent-failure-hunter": raw})

    # -- 集め役
    def test_collect_marks_findings_with_lens_name(self):
        """走ったレンズの指摘は出どころ（レンズの名）つきで ran"""
        self.routed()
        out = self.collect(json.dumps({"findings": [FINDING]}, ensure_ascii=False))
        self.assertEqual((out["ok"], out["ran"], out["failed"], out["not_routed"]), (True, 1, 0, 0))
        self.assertEqual(out["lens_file"], str(self.place / lens.LENS_FILE))
        row = lens.read(self.place)[0]
        self.assertEqual((row["state"], row["findings"]), ("ran", [{"lens": "silent-failure-hunter", **FINDING}]))

    def test_collect_records_failed_lens_and_succeeds(self):
        """落ちたレンズ（出口 null）・形の違う出口は failed と理由を記録し、集め役そのものは ok"""
        for given, why in (("null", "出口が無い"), ('{"findings": "x"}', "形が違う")):
            with self.subTest(given):
                self.routed()
                out = self.collect(given)
                self.assertEqual((out["ok"], out["failed"]), (True, 1))
                row = lens.read(self.place)[0]
                self.assertEqual(row["state"], "failed")
                self.assertIn(why, row["reason"])

    def test_collect_without_routes_is_not_ok(self):
        """振り分けが控えを書いていない（落ちた）なら集め役は ok: false と理由"""
        out = self.collect("null")
        self.assertIs(out["ok"], False)
        self.assertIn("控えが無い", out["reason"])

    def test_not_routed_lens_is_counted(self):
        self.routed(go=False)
        out = self.collect("null")
        self.assertEqual((out["ok"], out["not_routed"], out["ran"]), (True, 1, 0))
        self.assertIn("silent-failure-hunter: 起こさなかった（変わったファイルに例外の扱いが無い）", lens.report_lines(self.place))

    # -- 集計
    def test_findings_keeps_valid_and_counts_dropped(self):
        """1 件の形の誤りは捨てて件数を行の dropped に書き、形の合った発見は残す。findings が配列でなければ failed"""
        self.routed()
        bad = {"where": "stats.py", "cite": "", "why": "cite が空の発見"}
        self.collect(json.dumps({"findings": [FINDING, bad, "x"]}, ensure_ascii=False))
        row = lens.read(self.place)[0]
        self.assertEqual((row["state"], row["dropped"], row["findings"]), ("ran", 2, [{"lens": "silent-failure-hunter", **FINDING}]))
        self.routed()
        self.collect(json.dumps({"findings": "x"}))
        row = lens.read(self.place)[0]
        self.assertEqual(row["state"], "failed")
        self.assertNotIn("dropped", row)

    def test_count_line_always_names_failed_lens_count(self):
        self.routed()
        self.collect(json.dumps(LENS_REPLY, ensure_ascii=False))
        self.assertIn("落ちたレンズ 0 件", lens.count_line(lens.summary(self.place)))
        self.assertIn("落ちたレンズ 0 件", lens.report_lines(self.place)[-1])
        self.routed()
        self.collect("null")
        self.assertIn("落ちたレンズ 1 件", lens.count_line(lens.summary(self.place)))

    def test_summary_counts_adopted_by_lens_field(self):
        """採った件数は審査の faces の lens 欄がレンズの名の穴の数。審査の返答は受け付けが置き場に置いたファイルで渡す"""
        self.fixed()
        self.routed()
        self.collect(json.dumps({"findings": [FINDING, {**FINDING, "where": "other.py"}]}, ensure_ascii=False))
        self.cut()
        reply = RF.review_faces()
        base = reply["faces"][0]
        reply["faces"] = [{**base, "key": f"{base['key']} {i}", **({"lens": v} if v else {})}
                          for i, v in enumerate(["silent-failure-hunter", None, "no-such-lens"])]
        got = refix.accept_review(reply, self.place, self.base, self.repo, n=1)
        self.assertTrue(got["ok"], got)
        s = lens.summary(self.place, got["reply_file"])
        self.assertEqual((s["ran"], s["readable"], s["adopted"], s["not_adopted"], s["unmatched"]), (True, True, 1, 1, 1))

    # -- 差分の審査の brief
    def test_cut_brief_carries_lens_rows(self):
        """1 回目の審査役の brief の lens に、指摘を出どころつきで載せる"""
        self.fixed()
        self.routed()
        self.collect(json.dumps({"findings": [FINDING]}, ensure_ascii=False))
        brief = self.brief(self.cut())
        self.assertEqual(brief["lens"], [{"lens": "silent-failure-hunter", "state": "ran", "reason": "",
                                          "findings": [{"lens": "silent-failure-hunter", **FINDING}]}])
        self.assertNotIn("lens_error", brief)

    def test_cut_brief_without_lens_run_and_broken_file(self):
        """レンズを走らせていない run は lens が空。控えが壊れていれば空と lens_error（黙って空にしない）"""
        self.fixed()
        brief = self.brief(self.cut())
        self.assertEqual(brief["lens"], [])
        self.assertNotIn("lens_error", brief)
        (self.place / lens.LENS_FILE).write_text("{", encoding="utf-8")
        brief = self.brief(self.cut())
        self.assertEqual(brief["lens"], [])
        self.assertIn("読めない", brief["lens_error"])

    def test_review2_brief_has_no_lens(self):
        """手直しの差分にはレンズが当たらないので、2 回目の審査役の brief は lens を持たない"""
        self.refixed()
        self.assertNotIn("lens", self.brief(self.cut(2)))


if __name__ == "__main__":
    unittest.main()

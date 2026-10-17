"""run の頭の深さ（lib/headdepth.py。issue #441）の検査。関数を直に呼び、一時の置き場に小さな木と控えを書くだけ。

見る物:
- 役を起こす前の機械の止め 5 つ（thickness の名指し・仕様の段・設計だけ・依頼の行が無い・試験のコマンドが無い）
- 行ごとの未知の種類（UNKNOWNS）と、一番重い種類から段を引く tier_of
- 引用の照らし（行の抜け・2 度指し・依頼に無い引用・無いファイル・範囲の外・.git の中・コードに無い引用・why が空・cite の下限より
  短い引用・WHERE_SPAN より広い行の範囲・依頼の行が無い・表に無い種類。どの段の返答にも当てる。形・範囲は『無し』と同じ照らしで
  行の範囲の幅は問わず、原因は cause_quote を必ず照らし、where を書いた行だけ where と code_quote も照らす）
- 控えが無い・壊れた時は標準
- 報告の 1 行の 3 つの形（段の名・根拠と、段の省く物〔単位がどれも軽量の時〕・足す物。切った足しは名指しで切ったと添える）
"""
import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import headdepth  # noqa: E402

ROWS = [{"where": "stats.py:2", "text": "空の列の mean が 0 割りで落ちる"}]
START = {"test_cmd": "make test", "input": {"spec": False}}
LIGHT_REPLY = {"why": "原因と直す行が名指されている",
               "items": [{"item": 1, "unknown": "無し", "cause_quote": "mean が 0 割り", "where": "stats.py:1-2",
                          "code_quote": "return sum(xs) / len(xs)"}]}


class Repo(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name)
        (self.repo / "stats.py").write_text("def mean(xs):\n    return sum(xs) / len(xs)\n", encoding="utf-8")
        (self.repo / "long.py").write_text("value = 1\n" * (headdepth.WHERE_SPAN + 1), encoding="utf-8")
        (self.repo / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")


class GateTest(Repo):
    def gate(self, start, rows=ROWS):
        return headdepth.gate(headdepth.facts(rows, start, self.repo))

    def test_plain_request_wakes_the_role(self):
        self.assertEqual(self.gate(START), (True, "", ""))

    def test_thickness_names_the_depth_without_the_role(self):
        for word in ("軽量", "標準"):
            with self.subTest(word=word):
                go, got, why = self.gate({**START, "thickness": word})
                self.assertEqual((go, got), (False, word))
                self.assertIn("thickness", why)

    def test_heavy_thickness_names_the_depth_without_the_role(self):
        go, got, why = self.gate({**START, "thickness": "重厚"})
        self.assertEqual((go, got), (False, "重厚"))
        self.assertIn("thickness", why)
        self.assertEqual(headdepth.facts(ROWS, {**START, "thickness": "重厚"}, self.repo)["forced"], "重厚")

    def test_stops_fall_to_standard(self):
        for name, start, rows in (("spec", {**START, "input": {"spec": True}}, ROWS),
                                  ("design_only", {**START, "design_only": "true"}, ROWS),
                                  ("no rows", START, []),
                                  ("no test command", {"input": {}}, ROWS)):
            with self.subTest(name):
                go, got, why = self.gate(start, rows)
                self.assertEqual((go, got), (False, "標準"))
                self.assertTrue(why)

    def test_facts_measure_the_place(self):
        f = headdepth.facts([*ROWS, {"where": "stats.py:9", "text": "x"}, {"where": "nope.py", "text": "y"},
                             {"where": ".git", "text": "z"}], START, self.repo)
        self.assertEqual([(it["path_ok"], it["lines_ok"]) for it in f["items"]],
                         [(True, True), (True, False), (False, False), (False, False)])
        self.assertIn("行 3: y", headdepth.brief(f))


class CheckTest(Repo):
    def check(self, reply, rows=ROWS):
        return headdepth.check(reply, rows, self.repo)

    def item(self, **kw):
        return {**LIGHT_REPLY, "items": [{**LIGHT_REPLY["items"][0], **kw}]}

    def test_quoted_light_passes(self):
        """軽量は役が名乗る段でなく、全部の行が『無し』の時に機械が引く段"""
        self.assertEqual(self.check(LIGHT_REPLY), [])
        self.assertEqual(headdepth.tier_of(LIGHT_REPLY["items"]), "軽量")

    def test_quoted_heavy_passes(self):
        """重厚は範囲の行から決まる。形・範囲の行は where の行の範囲の幅を問わない"""
        wide = dict(where=f"long.py:1-{headdepth.WHERE_SPAN + 1}", code_quote="value = 1")
        for kind, tier in (("形", "標準"), ("範囲", "重厚")):
            with self.subTest(kind):
                reply = self.item(unknown=kind, **wide)
                self.assertEqual(self.check(reply), [])
                self.assertEqual(headdepth.tier_of(reply["items"]), tier)
                self.assertTrue(self.check(self.item(unknown=kind, cause_quote="書いていない字")))
        self.assertTrue(self.check(self.item(unknown="無し", **wide)))
        self.assertTrue(self.check({**LIGHT_REPLY, "items": []}))
        self.assertEqual(self.check({"why": "設計の選び", "items": []}, rows=[]), [headdepth.NO_ROWS])

    def test_standard_needs_only_a_reason(self):
        """標準の返答も行ごとに種類と引用を書かせて照らす（items 空の素通しは無い）"""
        cause = {"item": 1, "unknown": "原因", "cause_quote": "mean が 0 割り"}
        self.assertTrue(self.check({"why": "症状だけ"}))
        self.assertTrue(self.check({"why": "症状だけ", "items": []}))
        self.assertEqual(self.check({"why": "症状だけ", "items": [cause]}), [])
        self.assertTrue(self.check({"why": " ", "items": [cause]}))

    def test_bad_quotes_are_refused(self):
        two = [*ROWS, {"where": "stats.py", "text": "二つ目"}]
        for name, reply, rows in (("missing row", LIGHT_REPLY, two),
                                  ("twice", {**LIGHT_REPLY, "items": LIGHT_REPLY["items"] * 2}, two),
                                  ("cause not in request", self.item(cause_quote="書いていない字"), ROWS),
                                  ("no file", self.item(where="nope.py:1"), ROWS),
                                  ("outside the file", self.item(where="stats.py:2-9"), ROWS),
                                  ("no line", self.item(where="stats.py"), ROWS),
                                  ("escapes the root", self.item(where="../stats.py:1"), ROWS),
                                  ("inside .git", self.item(where=".git:1", code_quote="gitdir:"), ROWS),
                                  ("code not in lines", self.item(code_quote="return 0"), ROWS),
                                  ("unknown kind", self.item(unknown="極厚"), ROWS),
                                  ("one-char cause", self.item(cause_quote="空"), ROWS),
                                  ("one-char code", self.item(code_quote="/"), ROWS),
                                  ("whole-file range", self.item(where=f"long.py:1-{headdepth.WHERE_SPAN + 1}",
                                                                 code_quote="value = 1"), ROWS)):
            with self.subTest(name):
                self.assertTrue(self.check(reply, rows))


    def test_short_quotes_name_the_cite_floor(self):
        got = self.check(self.item(cause_quote="空", code_quote="/"))
        self.assertIn(f"行 1: cause_quote が {headdepth.cite.QUOTE_MIN} 字より短い", got)
        self.assertIn(f"行 1: code_quote が {headdepth.cite.QUOTE_MIN} 字より短い", got)

    def test_range_up_to_the_span_passes(self):
        reply = self.item(where=f"long.py:1-{headdepth.WHERE_SPAN}", code_quote="value = 1")
        self.assertEqual(self.check(reply), [])

    def test_light_without_request_rows_is_refused(self):
        self.assertEqual(self.check({**LIGHT_REPLY, "items": []}, rows=[]), [headdepth.NO_ROWS])

    def test_tier_is_the_heaviest_row_kind(self):
        """段は行の未知の種類の一番重い物から機械が引く"""
        for kinds, tier in ((("無し",), "軽量"), (("原因",), "標準"), (("形",), "標準"), (("範囲",), "重厚"),
                            (("無し", "無し"), "軽量"), (("無し", "原因"), "標準"), (("原因", "形", "無し"), "標準"),
                            (("原因", "形"), "標準"), (("形", "範囲"), "重厚"),
                            (("無し", "範囲", "原因"), "重厚")):
            with self.subTest(kinds=kinds):
                self.assertEqual(headdepth.tier_of([{"unknown": k} for k in kinds]), tier)
        self.assertEqual(list(headdepth.UNKNOWNS), ["無し", "原因", "形", "範囲"])
        self.assertEqual(set(headdepth.UNKNOWNS.values()), set(headdepth.depth.HEADS))

    def test_rules_follow_each_row_kind(self):
        wide = dict(where=f"long.py:1-{headdepth.WHERE_SPAN + 1}", code_quote="value = 1")
        cause = {"item": 1, "unknown": "原因", "cause_quote": "mean が 0 割り"}
        self.assertEqual(self.check({"why": "x", "items": [cause]}), [])
        self.assertEqual(self.check(self.item(unknown="原因", **wide)), [])
        none = {k: v for k, v in LIGHT_REPLY["items"][0].items() if k != "code_quote"}
        got = self.check({**LIGHT_REPLY, "items": [none]})
        self.assertTrue(got and all("code_quote" in why for why in got), got)
        got = self.check(self.item(unknown="無し", **wide))
        self.assertTrue(got and any("行の範囲" in why for why in got), got)
        self.assertEqual(self.check(self.item(unknown="形", **wide)), [])
        got = self.check(self.item(unknown="極厚"))
        self.assertTrue(got and all("unknown" in why for why in got), got)

    def test_standard_rows_are_checked_too(self):
        cause = {"item": 1, "unknown": "原因", "cause_quote": "mean が 0 割り"}
        got = self.check({"why": "x", "items": [{**cause, "cause_quote": "書いていない字"}]})
        self.assertTrue(got and all("cause_quote" in why for why in got), got)
        two = [*ROWS, {"where": "stats.py", "text": "二つ目の行"}]
        got = self.check({"why": "x", "items": [cause]}, rows=two)
        self.assertTrue(got and "items" in got[0], got)
        self.assertTrue(self.check({"why": "x", "items": [cause, cause]}, rows=two))
        got = self.check({"why": "x", "items": [{**cause, "cause_quote": "空"}]})
        self.assertIn(f"行 1: cause_quote が {headdepth.cite.QUOTE_MIN} 字より短い", got)

    def test_cause_rows_check_a_given_where(self):
        cause = {"item": 1, "unknown": "原因", "cause_quote": "mean が 0 割り"}
        good = {**cause, "where": "stats.py:1-2", "code_quote": "return sum(xs) / len(xs)"}
        self.assertEqual(self.check({"why": "x", "items": [good]}), [])
        wide = {**cause, "where": f"long.py:1-{headdepth.WHERE_SPAN + 1}", "code_quote": "value = 1"}
        self.assertEqual(self.check({"why": "x", "items": [wide]}), [])
        for name, bad, word in (("outside the file", {**good, "where": "stats.py:2-9"}, "where"),
                                ("no file", {**good, "where": "nope.py:1"}, "where"),
                                ("code not in range", {**good, "code_quote": "return 0"}, "code_quote"),
                                ("where without code", {k: v for k, v in good.items() if k != "code_quote"}, "code_quote")):
            with self.subTest(name):
                got = self.check({"why": "x", "items": [bad]})
                self.assertTrue(got and all(word in why for why in got), got)


class RecordTest(unittest.TestCase):
    def test_missing_or_broken_record_reads_standard(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(headdepth.read(tmp)["depth"], "標準")
            (pathlib.Path(tmp) / headdepth.RECORD).write_text("{", encoding="utf-8")
            self.assertEqual(headdepth.read(tmp)["depth"], "標準")
            headdepth.write(tmp, headdepth.record("軽量", "根拠"))
            self.assertEqual(headdepth.read(tmp)["depth"], "軽量")


class SectionTest(unittest.TestCase):
    ITEMS = [{"item": 1, "unknown": "無し", "cause_quote": "mean が 0 割り", "where": "stats.py:1-2",
              "code_quote": "return sum(xs) / len(xs)"},
             {"item": 2, "unknown": "原因", "cause_quote": "空の列で落ちる"},
             {"item": 3, "unknown": "形", "cause_quote": "二通りの直し方", "where": "a.py:1-9", "code_quote": "def pick():"},
             {"item": 4, "unknown": "範囲", "cause_quote": "設定の鍵に響く", "where": "b.py:3", "code_quote": "KEY = 1"}]

    def path(self, doc=None, name=headdepth.RECORD):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        if doc is not None:
            headdepth.write(tmp.name, doc)
        return str(pathlib.Path(tmp.name) / name)

    def test_rows_carry_kind_where_quote_and_ask(self):
        """行ごとに番号・種類・依頼の字・番地と引用（原因の where 無しは『無い』）・種類の指示が載る。決まっていない run は訳の 1 行"""
        text = headdepth.section(self.path(headdepth.record("重厚", "根拠", items=self.ITEMS)))
        self.assertTrue(text.startswith(headdepth.UNKNOWN_HEAD), text)
        lines = text.splitlines()
        rows = [x for x in lines if x.startswith("- 行 ")]
        self.assertEqual(len(rows), 4, text)
        self.assertIn("- 行 1（無し）: 依頼の字「mean が 0 割り」・番地 stats.py:1-2「return sum(xs) / len(xs)」", rows[0])
        self.assertIn("番地: 無い（原因がコードに見えない）", rows[1])
        self.assertNotIn("番地 ", rows[1])
        self.assertIn("- 行 3（形）: 依頼の字「二通りの直し方」・番地 a.py:1-9「def pick():」", rows[2])
        self.assertIn("- 行 4（範囲）: 依頼の字「設定の鍵に響く」・番地 b.py:3「KEY = 1」", rows[3])
        for row, it in zip(rows, self.ITEMS):
            self.assertTrue(row.endswith(f"指示: {headdepth.ASKS[it['unknown']]}"), row)
        self.assertNotIn(headdepth.ASKS["形"], rows[0])   # 種類ごとに違う指示
        for name, path, why in (("no file", self.path(), headdepth.NO_RECORD),
                                ("empty path", "", headdepth.NO_RECORD),
                                ("no kinds", self.path(headdepth.record("標準", "機械の止め")), "機械の止め"),
                                ("unknown kind", self.path(headdepth.record("標準", "x", items=[{"item": 1, "unknown": "極厚"}])), "x")):
            with self.subTest(name):
                got = headdepth.section(path)
                self.assertEqual(got, f"{headdepth.UNKNOWN_HEAD}\n\n行ごとの未知の種類は決まっていない（訳: {why}）\n")
        # 指示の表は種類の表と同じ鍵で、受け手の役に無い口を名指さない
        self.assertEqual(list(headdepth.ASKS), list(headdepth.UNKNOWNS))
        for kind, ask in headdepth.ASKS.items():
            with self.subTest(kind):
                self.assertTrue(ask.strip())
                for word in ("範囲の相談", "申し出"):
                    self.assertNotIn(word, ask)
        # 形の指示の字は今のまま、ここ 1 か所で縛る（段を下げても設計の選びの指示を落とさない。他の試験は ASKS の参照で載ることだけを見る）
        self.assertEqual(headdepth.ASKS[headdepth.SHAPE], "形を 2 つ以上並べ、選んだ訳と退けた訳を書け。")
        self.assertEqual(headdepth.UNKNOWN_HEAD.source, "fn:headdepth.section")

    def test_scope_ask_keeps_the_shape_ask(self):
        """範囲になった行も、選びが要る時の指示（形の行の指示）を失わない"""
        self.assertIn(headdepth.ASKS[headdepth.SHAPE], headdepth.ASKS[headdepth.SCOPE])


class ReportLineTest(unittest.TestCase):
    def test_three_shapes(self):
        omits = "・".join(headdepth.depth.OMITS)
        self.assertEqual(headdepth.report_line("軽量", "根拠"),
                         f"run の頭の深さ: 軽量（根拠: 根拠）／省く物（単位がどれも軽量の時）: {omits}／足した物: 無い")
        self.assertEqual(headdepth.report_line("標準", "試験のコマンドが無い"),
                         "run の頭の深さ: 標準（根拠: 試験のコマンドが無い）／省く物: 無い／足した物: 無い")
        self.assertEqual(headdepth.report_line("重厚", "公開の約束を変える"),
                         "run の頭の深さ: 重厚（根拠: 公開の約束を変える）／省く物: 無い／足した物: judge_verify・review_tree")
        self.assertEqual(headdepth.report_line("重厚", "公開の約束を変える", cut=("judge_verify",)),
                         "run の頭の深さ: 重厚（根拠: 公開の約束を変える）／省く物: 無い／"
                         "足した物: judge_verify（名指しで切った）・review_tree")
        self.assertEqual(headdepth.report_line("", ""), "run の頭の深さ: 標準／省く物: 無い／足した物: 無い")
        self.assertEqual(headdepth.report_line("極厚", "x"), "run の頭の深さ: 標準（根拠: x）／省く物: 無い／足した物: 無い")


if __name__ == "__main__":
    unittest.main()

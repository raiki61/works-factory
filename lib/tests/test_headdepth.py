"""run の頭の深さ（lib/headdepth.py。issue #441）の検査。関数を直に呼び、一時の置き場に小さな木と控えを書くだけ。

見る物:
- 役を起こす前の機械の止め 5 つ（thickness の名指し・仕様の段・設計だけ・依頼の行が無い・試験のコマンドが無い）
- 引用の照らし（行の抜け・2 度指し・依頼に無い引用・無いファイル・範囲の外・.git の中・コードに無い引用・why が空・cite の下限より
  短い引用・WHERE_SPAN より広い行の範囲・依頼の行が無い軽量。重厚は軽量と同じ照らしで、行の範囲の幅は問わない）
- 控えが無い・壊れた時は標準
- 報告の 1 行の 3 つの形（段の名・根拠と、段の省く物・足す物。切った足しは名指しで切ったと添える）
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
LIGHT_REPLY = {"depth": "軽量", "why": "原因と直す行が名指されている",
               "items": [{"item": 1, "cause_quote": "mean が 0 割り", "where": "stats.py:1-2",
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
        self.assertEqual(self.check(LIGHT_REPLY), [])

    def test_quoted_heavy_passes(self):
        """重厚は軽量と同じ引用の照らしを通り、where の行の範囲が WHERE_SPAN より広くても受ける"""
        self.assertEqual(self.check({**LIGHT_REPLY, "depth": "重厚"}), [])
        wide = self.item(where=f"long.py:1-{headdepth.WHERE_SPAN + 1}", code_quote="value = 1")
        self.assertEqual(self.check({**wide, "depth": "重厚"}), [])
        self.assertTrue(self.check(wide))   # 軽量には範囲の幅の上限を当てる
        self.assertTrue(self.check({**self.item(cause_quote="書いていない字"), "depth": "重厚"}))
        self.assertTrue(self.check({**LIGHT_REPLY, "depth": "重厚", "items": []}))
        self.assertEqual(self.check({"depth": "重厚", "why": "設計の選び", "items": []}, rows=[]), [headdepth.NO_ROWS])

    def test_standard_needs_only_a_reason(self):
        self.assertEqual(self.check({"depth": "標準", "why": "設計の選びが要る"}), [])
        self.assertTrue(self.check({"depth": "標準", "why": " "}))

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
                                  ("unknown depth", {**LIGHT_REPLY, "depth": "極厚"}, ROWS),
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


class RecordTest(unittest.TestCase):
    def test_missing_or_broken_record_reads_standard(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(headdepth.read(tmp)["depth"], "標準")
            (pathlib.Path(tmp) / headdepth.RECORD).write_text("{", encoding="utf-8")
            self.assertEqual(headdepth.read(tmp)["depth"], "標準")
            headdepth.write(tmp, headdepth.record("軽量", "根拠"))
            self.assertEqual(headdepth.read(tmp)["depth"], "軽量")


class ReportLineTest(unittest.TestCase):
    def test_three_shapes(self):
        self.assertEqual(headdepth.report_line("軽量", "根拠"), "run の頭の深さ: 軽量（根拠: 根拠）／省いた物: 無い／足した物: 無い")
        self.assertEqual(headdepth.report_line("標準", "試験のコマンドが無い"),
                         "run の頭の深さ: 標準（根拠: 試験のコマンドが無い）／省いた物: 無い／足した物: 無い")
        self.assertEqual(headdepth.report_line("重厚", "設計の選びが要る"),
                         "run の頭の深さ: 重厚（根拠: 設計の選びが要る）／省いた物: 無い／足した物: judge_verify・review_tree")
        self.assertEqual(headdepth.report_line("重厚", "設計の選びが要る", cut=("judge_verify",)),
                         "run の頭の深さ: 重厚（根拠: 設計の選びが要る）／省いた物: 無い／"
                         "足した物: judge_verify（名指しで切った）・review_tree")
        self.assertEqual(headdepth.report_line("", ""), "run の頭の深さ: 標準／省いた物: 無い／足した物: 無い")
        self.assertEqual(headdepth.report_line("極厚", "x"), "run の頭の深さ: 標準（根拠: x）／省いた物: 無い／足した物: 無い")


if __name__ == "__main__":
    unittest.main()

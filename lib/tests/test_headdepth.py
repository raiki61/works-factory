"""run の頭の深さ（lib/headdepth.py。issue #441）の検査。関数を直に呼び、一時の置き場に小さな木と控えを書くだけ。

見る物:
- 役を起こす前の機械の止め 5 つ（thickness の名指し・仕様の段・設計だけ・依頼の行が無い・試験のコマンドが無い）
- 引用の照らし（行の抜け・2 度指し・依頼に無い引用・無いファイル・範囲の外・コードに無い引用・why が空）
- 計画の往復の 1 周で事前審査を飛ばすか（頭が標準なら飛ばさない・単位に標準が在れば上げる・全部軽量で飛ばす）
- 控えが無い・壊れた時は標準
- 報告の 1 行の 3 つの形
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
        f = headdepth.facts([*ROWS, {"where": "stats.py:9", "text": "x"}, {"where": "nope.py", "text": "y"}], START, self.repo)
        self.assertEqual([(it["path_ok"], it["lines_ok"]) for it in f["items"]], [(True, True), (True, False), (False, False)])
        self.assertIn("行 3: y", headdepth.brief(f))


class CheckTest(Repo):
    def check(self, reply, rows=ROWS):
        return headdepth.check(reply, rows, self.repo)

    def item(self, **kw):
        return {**LIGHT_REPLY, "items": [{**LIGHT_REPLY["items"][0], **kw}]}

    def test_quoted_light_passes(self):
        self.assertEqual(self.check(LIGHT_REPLY), [])

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
                                  ("code not in lines", self.item(code_quote="return 0"), ROWS),
                                  ("unknown depth", {**LIGHT_REPLY, "depth": "重厚"}, ROWS)):
            with self.subTest(name):
                self.assertTrue(self.check(reply, rows))


class DueTest(unittest.TestCase):
    LIGHT_UNITS = [{"unit_id": "u1", "depth": "軽量", "why": "配線だけ"}]

    def test_standard_head_never_skips(self):
        self.assertEqual(headdepth.due("標準", True, self.LIGHT_UNITS), {"skip": False, "why": "", "raised": []})

    def test_no_plan_never_skips(self):
        self.assertFalse(headdepth.due("軽量", False, self.LIGHT_UNITS)["skip"])

    def test_a_standard_unit_raises(self):
        got = headdepth.due("軽量", True, [*self.LIGHT_UNITS, {"unit_id": "u2", "depth": "標準", "why": "触るファイルが 5 個"}])
        self.assertFalse(got["skip"])
        self.assertEqual(got["raised"], ["計画の単位ごとの深さに標準が在る（u2: 触るファイルが 5 個）"])

    def test_all_light_skips(self):
        got = headdepth.due("軽量", True, self.LIGHT_UNITS)
        self.assertEqual((got["skip"], got["raised"]), (True, []))
        self.assertTrue(got["why"])


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
        self.assertEqual(headdepth.report_line("軽量", "根拠", ["plan-review-run__review-loop"], []),
                         "run の頭の深さ: 軽量（根拠: 根拠）／飛ばしたノード: plan-review-run__review-loop")
        self.assertEqual(headdepth.report_line("軽量", "根拠", [], ["u2 が標準"]),
                         "run の頭の深さ: 軽量 → 標準へ上げた（u2 が標準）／飛ばしたノード: 無い")
        self.assertEqual(headdepth.report_line("標準", "試験のコマンドが無い", [], []),
                         "run の頭の深さ: 標準（根拠: 試験のコマンドが無い）／飛ばしたノード: 無い")


if __name__ == "__main__":
    unittest.main()

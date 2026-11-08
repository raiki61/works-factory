"""人に聞く文の照らし（lib/plainask.py）。run の中を指す 2 つの形（<パス>:<行>・<名>[<番号>]）だけを拒み、URL の中と平易な文は通す"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import gatemarks  # noqa: E402
import plainask  # noqa: E402


class RefsTest(unittest.TestCase):
    def test_finds_line_and_index_refs_in_order(self):
        text = "plan[0] の案は src/stats.py:12 と docs/a.md:3-5 を直す。faces[2] と同じ。plan[0] を再び"
        self.assertEqual(plainask.refs(text), ["plan[0]", "src/stats.py:12", "docs/a.md:3-5", "faces[2]"])

    def test_plain_text_and_urls_pass(self):
        for text in ("平均を出す関数は、空の列で 0 割りの例外を投げる。推し: 案どおり",
                     "出典 https://example.com/spec.html:8080/a[1] の 3 節",
                     "時刻 12:30 に版 1.2 を出す", "", None, 3):
            with self.subTest(text=text):
                self.assertEqual(plainask.refs(text), [])

    def test_ordinary_text_that_only_looks_like_a_ref_passes(self):
        """番地とポート・製品の名と版・対象のコードの添え字・脚注は数えない。バッククォートの中の <名>[<番号>] は字のままの引用なので
        数えず、<パス>:<行> は拡張子の表（lib/changemap.py）に在る拡張子だけ、<名>[<番号>] は小文字の名（返答の JSON の欄の名の形）だけを数える"""
        for text in ("試験の台は example.com:8080 で受ける",
                     "引数は `argv[1]` と `items[0]` で受ける", "Smith[1] の 3 章が同じ形を勧める"):
            with self.subTest(text=text):
                self.assertEqual(plainask.refs(text), [])
        self.assertEqual(plainask.refs("`argv[1]` を読む所は stats.py:3 と items[0] に在る"), ["stats.py:3", "items[0]"])

    def test_line_refs_in_backticks_are_still_counted(self):
        """バッククォートで囲んでも <パス>:<行> は数える（役がいちばんよく書く形。拡張子が表に在れば囲んでも当たる）"""
        self.assertEqual(plainask.refs("直す所は `stats.py:3` に在る"), ["stats.py:3"])
        self.assertEqual(plainask.refs("版は `Node.js:18` の image に揃える"), ["Node.js:18"])
        self.assertEqual(plainask.refs("`items[0]` を読む所は `a/b.py:12` と plan[1]"), ["a/b.py:12", "plan[1]"])

    def test_gaps_names_the_field_and_the_refs(self):
        self.assertEqual(plainask.gaps("questions[0].reason", "平易な文"), [])
        [line] = plainask.gaps("questions[0].reason", "stats.py:3 を見よ")
        self.assertTrue(line.startswith("questions[0].reason: "))
        self.assertIn("stats.py:3", line)



class GateRowsTest(unittest.TestCase):
    """関所の項目に字のまま載る行の欄（gatemarks.plain_gaps。修正案の narrows と事前審査の faces・止まった時の推し）"""

    def test_fix_plan_narrows_and_review_faces(self):
        plan = {"plan": [{"narrows": [{"what": "x", "undecided_because": "平易な訳", "no_narrow": "a.py:1 を当たった",
                                       "recommend": {"answer": "continue", "note": "通す", "why": "faces[1] と同じ"}}]}]}
        self.assertEqual([g.split(":")[0] for g in gatemarks.plain_gaps("p2.fix_plan", plan)],
                         ["plan[0].narrows[0].no_narrow", "plan[0].narrows[0].recommend.why"])
        review = {"faces": [{"world": "平易", "undecided_because": "x.md:2 が割れる"}], "stuck_recommend": {"note": "units[3] を通す"}}
        self.assertEqual([g.split(":")[0] for g in gatemarks.plain_gaps("p2.plan_review", review)],
                         ["faces[0].undecided_because", "stuck_recommend.note"])
        self.assertEqual(gatemarks.plain_gaps("other", review), [])


class ItemRowCase(unittest.TestCase):
    """人に聞く項目の行の読み口 item_text・item_title。要素は字でも {text, title} の行でもよい（役が書いた題は読む所が 1 行に畳む）"""

    def test_item_title_folds_newlines_and_drops_blank_titles(self):
        self.assertTrue(hasattr(plainask, "item_title"), "題の読み口 item_title が無い")
        self.assertEqual(plainask.item_title({"text": "本文", "title": "拒まずに\n通す検査へ  緩める"}), "拒まずに 通す検査へ 緩める", "改行と空白の並びを 1 つの空白に")
        long_title = "長い題" * 40
        self.assertEqual(plainask.item_title({"text": "本文", "title": long_title}), long_title, "字数では切らない")
        for blank in ({"text": "本文", "title": " \n\t "}, {"text": "本文", "title": ""}, {"text": "本文"}, {"text": "本文", "title": None},
                      {"text": "本文", "title": 3}, "字の要素", None, 3):
            with self.subTest(blank=blank):
                self.assertIsNone(plainask.item_title(blank))

    def test_items_read_as_text_and_title_whether_string_or_row(self):
        self.assertTrue(hasattr(plainask, "item_text") and hasattr(plainask, "item_title"), "読み口 item_text・item_title が無い")
        self.assertEqual((plainask.item_text("字の要素"), plainask.item_title("字の要素")), ("字の要素", None))
        row = {"text": "行の本文", "title": "行の題"}
        self.assertEqual((plainask.item_text(row), plainask.item_title(row)), ("行の本文", "行の題"))
        self.assertEqual((plainask.item_text({"title": "題だけ"}), plainask.item_title({"title": "題だけ"})), ("", "題だけ"), "本文が無い行の本文は空の字")
        self.assertEqual(plainask.item_text({"text": 3}), "")
        self.assertEqual(plainask.item_text(None), "")


if __name__ == "__main__":
    unittest.main()

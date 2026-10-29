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


if __name__ == "__main__":
    unittest.main()

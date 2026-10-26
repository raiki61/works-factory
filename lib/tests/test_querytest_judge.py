"""判定の写しのパスから食い違いの申し出の問いの確かめを組む口（lib/querytest.py の judge_query）と、brief の行（lib/planbrief.py の
brief_rows）の検査。修正の block の board.judge_query の本体と rules.brief_rows を出した物。
"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import planbrief  # noqa: E402
import querytest  # noqa: E402


class JudgeQueryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="works-judgeq-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.file = self.tmp / "judgment.json"

    def test_a_missing_judgment_names_the_file_and_that_it_is_missing(self):
        got = querytest.judge_query(self.file)("k", ["line"])
        self.assertEqual(got, querytest.JUDGE_UNREAD.format(name="judgment.json", why="無い"))
        self.assertIn("置き場の判定の写し judgment.json が読めない（無い）", got)

    def test_a_judgment_that_is_not_a_dict_is_unreadable(self):
        self.file.write_text("[]", encoding="utf-8")
        self.assertIn("（dict でない）", querytest.judge_query(self.file)("k", []))

    def test_broken_json_is_unreadable_with_the_reader_message(self):
        self.file.write_text("{", encoding="utf-8")
        got = querytest.judge_query(self.file)("k", [])
        self.assertIn(str(self.file), got)
        self.assertIn("読めない", got)

    def test_every_key_gets_the_unreadable_sentence(self):
        hits = querytest.judge_query(self.file)
        self.assertEqual(hits("a", ["x"]), hits("b", []))

    def how(self, pattern):
        return {"patterns": [pattern], "fixed": True, "paths": ["stats.py"], "count": "lines"}

    def test_a_readable_judgment_tries_the_unit_query_against_the_lines(self):
        self.file.write_text(json.dumps({"units": [{"key": "u", "class_query": {"how": self.how("len(xs) - 1")}}]}), encoding="utf-8")
        hits = querytest.judge_query(self.file)
        self.assertEqual(hits("u", ["return s / (len(xs) - 1)"]), "")
        self.assertIn("どの行にも当たらない", hits("u", ["return s / len(xs)"]))
        self.assertEqual(hits("no-such-unit", ["whatever"]), "", "問いの無い単位は見ない")

    def test_a_replaced_query_wins_over_the_judgment_query(self):
        self.file.write_text(json.dumps({"units": [{"key": "u", "class_query": {"how": self.how("len(xs) - 1")}}]}), encoding="utf-8")
        lines = ["return s / len(xs)"]
        self.assertIn("どの行にも当たらない", querytest.judge_query(self.file)("u", lines))
        self.assertEqual(querytest.judge_query(self.file, {"u": {"how": self.how("len(xs)")}})("u", lines), "")

    def test_the_same_hits_as_judge_hits_built_directly(self):
        units = [{"key": "u", "class_query": {"how": self.how("zzz")}}]
        self.file.write_text(json.dumps({"units": units}), encoding="utf-8")
        lines = ["nothing here"]
        self.assertEqual(querytest.judge_query(self.file)("u", lines), querytest.judge_hits(units)("u", lines))


class BriefRowsTest(unittest.TestCase):
    ROW = {"item": 1, "file": "/b/brief-1.md", "sha256": "abc", "unit_keys": ["a", "b"]}

    def test_no_briefs_is_the_empty_string(self):
        self.assertEqual(planbrief.brief_rows([]), "")

    def test_one_row_per_item_with_the_file_the_hash_and_the_units(self):
        got = planbrief.brief_rows([self.ROW, {**self.ROW, "item": 2, "file": "/b/brief-2.md", "unit_keys": ["b"]}])
        self.assertEqual(got.splitlines(), ["- 項目 1: /b/brief-1.md（sha256 abc・単位 a、b）",
                                            "- 項目 2: /b/brief-2.md（sha256 abc・単位 b）"])

    def test_units_not_owed_now_are_marked_as_not_to_fix_yet(self):
        got = planbrief.brief_rows([self.ROW], owed=["a"])
        self.assertEqual(got, f"- 項目 1: /b/brief-1.md（sha256 abc・単位 a・{planbrief.NOT_NOW}: b）")


if __name__ == "__main__":
    unittest.main()

"""報告の役の小道具（lib/report_roles.py）の検査。

元の試験 works/tests/test_blk_report.py と works/tests/test_report_cold.py のうち、盤面に頼らない関数（format_problems・head_of・
_terms_problems・count_rejects）を縛る物だけを 1 つにまとめた。FormatCase の 4 本と RejectCountRowsCase.test_rows_without_kind_count_as_unknown
は元の test_blk_report.py の同じ名の試験。head_of と _terms_problems を縛る元の試験は盤面の描き方の試験の中にしか無いので、
ここに新しく書いた。
"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import report_roles as rr  # noqa: E402
from engine.schema import validate_schema  # noqa: E402  report_roles が写しの engine の置き場を sys.path に足す


class FormatCase(unittest.TestCase):
    def test_short_cells_pass(self):
        text = "結果\n\n| 項目 | 件数 |\n|---|---|\n| 直した | 3 |\n| `src/very/long/path/to/some/module_name.py` | 済み |\n"
        self.assertEqual(rr.format_problems(text), [])

    def test_sentence_in_cell_rejected(self):
        text = "| 項目 | 説明 |\n|---|---|\n| A | これは説明の文である。 |\n"
        got = rr.format_problems(text)
        self.assertEqual(len(got), 1)
        self.assertIn("3 行目", got[0])

    def test_long_cell_rejected(self):
        text = "| 項目 |\n|---|\n| " + "あ" * (rr.CELL_LIMIT + 1) + " |\n"
        self.assertEqual(len(rr.format_problems(text)), 1)

    def test_pipes_in_code_are_not_cells(self):
        text = "```\n| " + "あ" * 80 + "。 |\n```\n"
        self.assertEqual(rr.format_problems(text), [])

    def test_code_span_is_not_counted(self):
        """`コード` の部分は字数にも「。」にも数えない"""
        text = "| 項目 |\n|---|\n| `" + "。" * 80 + "` |\n"
        self.assertEqual(rr.format_problems(text), [])


class HeadCase(unittest.TestCase):
    def test_head_keeps_lead_and_decisions_only(self):
        text = "1 行目\n2 行目\n3 行目\n\n## 1. 人が決めること\n\n- 問い A\n\n## 2. 経緯\n\n長い経緯"
        head = rr.head_of(text)
        self.assertIn("3 行目", head)
        self.assertIn("問い A", head)
        self.assertNotIn("長い経緯", head)

    def test_no_heading_keeps_all(self):
        self.assertEqual(rr.head_of(" 本文だけ \n"), "本文だけ")


class TermsCase(unittest.TestCase):
    def test_terms_must_be_term_and_definition(self):
        self.assertEqual(rr._terms_problems({"text": "x"}), [])
        self.assertEqual(rr._terms_problems({"text": "x", "terms": [{"term": "盤面", "definition": "置き場"}]}), [])
        self.assertNotEqual(rr._terms_problems({"text": "x", "terms": [{"term": ""}]}), [])
        self.assertNotEqual(rr._terms_problems({"text": "x", "terms": [{"term": "a", "definition": "b", "extra": 1}]}), [])


class HandoffCase(unittest.TestCase):
    def test_text_schema_requires_the_four_handoff_lists(self):
        schema = rr.TEXT_SCHEMA
        self.assertIn("handoff", schema["required"])
        handoff = schema["properties"]["handoff"]
        self.assertEqual(sorted(handoff["required"]), ["decided", "doubts", "read", "rejected"])
        self.assertIs(handoff["additionalProperties"], False)
        for key in handoff["required"]:
            self.assertEqual(handoff["properties"][key], {"type": "array", "items": {"type": "string"}})
        full = {"read": ["a.py:1"], "decided": [], "rejected": [], "doubts": []}
        self.assertEqual(validate_schema({"text": "x", "handoff": full}, schema, "$"), [])
        self.assertNotEqual(validate_schema({"text": "x"}, schema, "$"), [], "handoff の無い返答は破れ")
        self.assertNotEqual(validate_schema({"text": "x", "handoff": {"read": []}}, schema, "$"), [], "欄の欠けた handoff は破れ")


class RejectCountRowsCase(unittest.TestCase):
    """拒否の行の配列を数える純粋な関数 count_rejects。kind の無い行（kind が入る前の run の行）・知らない kind の行は
    捨てずに unknown へ数える（無い欄を既定値で読む）。node が REPORT_NODES（頭と初見検査が回っていた前の版の節も）に無い行は数えない"""

    def test_rows_without_kind_count_as_unknown(self):
        count = getattr(rr, "count_rejects", None)
        self.assertIsNotNone(count, "report_roles に拒否の行の配列を数える count_rejects が無い")
        rows = [{"node": "report", "reason": "kind が入る前の行"},
                {"node": "report.human_items", "reason": "kind が入る前の行"},
                {"node": "report", "kind": "cold"},
                {"node": "report", "kind": "answer"},
                {"node": "report.human_items", "kind": "format"},
                {"node": "report", "kind": "何か"},
                {"node": "よその節", "kind": "cold"}]
        got = count(rows)
        self.assertEqual(got["report"], {"cold": 1, "format": 0, "answer": 1, "unknown": 2})
        self.assertEqual(got["report.human_items"], {"cold": 0, "format": 1, "answer": 0, "unknown": 1})
        self.assertEqual(got["report.cold_check"], {"cold": 0, "format": 0, "answer": 0, "unknown": 0})
        self.assertNotIn("よその節", got)
        self.assertEqual(rr.REJECT_KINDS, ("cold", "format", "answer"), "unknown は読むときだけの種類で、書ける種類は 3 つのまま")


if __name__ == "__main__":
    unittest.main()

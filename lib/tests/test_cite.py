"""名指しの形と場所の文の読みの住処 cite の試験（本物の cite・holeties・conflict・material を直に呼ぶ。FAST）"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import cite  # noqa: E402


class WhereCase(unittest.TestCase):
    def test_where_cites_carries_previous_path(self):
        self.assertEqual(cite.where_cites("works/a.py:3 と :5-7、b.md:2"),
                         [("works/a.py", "3", None), ("works/a.py", "5", "7"), ("b.md", "2", None)])
        self.assertEqual(cite.where_cites(":4 の話"), [("", "4", None)])


class QuotedInCase(unittest.TestCase):
    def test_one_quote_by_norm(self):
        """引用 1 つの照らしは quoted_in 1 つ: 字数の下限は無く、空の引用は偽。寄せ方は norm（既定 flat。独立設計の引用は fold、
        依頼の引用は字のまま str）"""
        self.assertTrue(cite.quoted_in("上限", "上限は入口 1 箇所で掛ける", norm=cite.fold))
        self.assertFalse(cite.quoted_in("下限", "上限は入口 1 箇所で掛ける", norm=cite.fold))
        self.assertFalse(cite.quoted_in("", "上限", norm=cite.fold))
        self.assertFalse(cite.quoted_in("  ", "上限", norm=cite.fold))
        self.assertTrue(cite.quoted_in("入口 １  箇所", "上限は入口 1 箇所で掛ける", norm=cite.fold))
        self.assertFalse(cite.quoted_in("入口 １ 箇所", "上限は入口 1 箇所で掛ける", norm=str))
        self.assertFalse(cite.quoted_in("入口 １ 箇所", "上限は入口 1 箇所で掛ける"), "既定の flat は NFKC にしない")
        self.assertTrue(cite.quoted_in("入口 1\n箇所", "\x1b[31m上限は入口 1  箇所\x1b[0m"), "既定の flat は空白と色を寄せる")


class MovedReadsCase(unittest.TestCase):
    """指し先の照らしと Markdown の読みの住処は cite の 1 か所（前は judge_accept・boardview。integration.md 4.3-4・4.5-5）"""

    def test_markdown_reads(self):
        text = "# 頭\n```\n# 囲いの中\n```\n## 頭\n[a](b.md#x)\n"
        self.assertEqual([n for n, _ in cite._md_lines(text)], [1, 5, 6])
        self.assertEqual(cite._md_slugs(text), {"頭", "頭-1"})
        self.assertEqual(cite.MD_LINK.findall("[a](b.md#x) ![i](c.png)"), [("", "b.md#x")])

    def test_resolve_target_and_precedent_gap(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        self.assertEqual(cite._resolve_target("lib/cite.py", root), ("lib/cite.py", ""))
        self.assertIsNone(cite._resolve_target("./lib/cite.py", root)[0])
        self.assertIsNone(cite._resolve_target("../x", root)[0])
        self.assertEqual(cite._precedent_gap({"verdict": "adopt", "source": "https://example.org"}), "")
        self.assertTrue(cite._precedent_gap({"verdict": "not_found", "searched": "無し"}))
        self.assertTrue(cite.blank("なし", 4))
        self.assertEqual(cite.Reject.__module__, "engine.util")


if __name__ == "__main__":
    unittest.main()

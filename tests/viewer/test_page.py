"""見る道具の 1 枚のページ（viewer/page.tpl.html と viewer/src/page.py。docs/design/viewer.md の照らしの 4）。

- 雛形は別のファイルからスクリプトを読まない（viewer/AGENTS.md の E25 の 3）: `<script src`・`import(`・`fetch(` が無い。見た目は縛らない（E25 の 4）
- データの字（記録の </script> や <!-- を含む）は script の中身を閉じず、データはそのまま読み戻せる
- 終わった run の終わりの無いまま残った出来事（頭の帯の 1 文）は、読む部品が run の終わりで閉じて付けた印 cut で見つける（閉じた出来事は
  終わりの欄が埋まるので、終わりの欄の空では 1 件も見つからない。docs/design/viewer.md の 5 章）
"""
import json
import re
import unittest

from viewer.src import page

OUTSIDE = (re.compile(r"<script\b[^>]*\bsrc\b", re.I), re.compile(r"\bimport\s*\("), re.compile(r"\bfetch\s*\("))


class PageCase(unittest.TestCase):
    def test_template_reads_no_other_file(self):
        text = page.TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual([p.pattern for p in OUTSIDE if p.search(text)], [])

    def test_endless_events_are_found_by_their_cut_mark(self):
        text = page.TEMPLATE.read_text(encoding="utf-8")
        self.assertRegex(text, r"const ENDLESS = [^\n]*\.filter\(e => e\.cut\)")

    def test_page_is_one_file(self):
        data = {"texts": {"a": "</script><!-- <script>x</script> </SCRIPT"}, "made_at": "now"}
        made = page.render(data)
        self.assertEqual(made.lower().count("</script"), page.TEMPLATE.read_text(encoding="utf-8").lower().count("</script"))
        embedded = re.search(r'<script type="application/json" id="data">(.*?)</script>', made, re.S)[1]
        self.assertEqual(json.loads(embedded), data)


if __name__ == "__main__":
    unittest.main()

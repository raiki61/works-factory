"""見る道具の 1 枚のページ（viewer/page.tpl.html と viewer/src/page.py。docs/design/viewer.md の照らしの 4）。

- 雛形は別のファイルからスクリプトを読まない（viewer/AGENTS.md の E25 の 3）: `<script src`・`import(`・`fetch(` が無い。見た目は縛らない（E25 の 4）
- データの字（記録の </script> や <!-- を含む）は script の中身を閉じず、データはそのまま読み戻せる
- 終わった run の終わりの無いまま残った出来事（頭の帯の 1 文）は、読む部品が run の終わりで閉じて付けた印 cut で見つける（閉じた出来事は
  終わりの欄が埋まるので、終わりの欄の空では 1 件も見つからない。docs/design/viewer.md の 5 章）
- 出来事の語（板・ログの行・再生の帯の終わり）は 1 つの関数 evWord で出し、印 cut の出来事は段と札と同じ止まり方の語（openLook）にする
  （状態の語のままだと、終わった run の閉じた出来事が「走り中」「人の答え待ち」と出る。docs/design/viewer.md の 6 章）
- 落ちた後に起き直した run で、読む部品がその落ちで閉じて状態を落ちたにした出来事（印 cut で状態 failed）は、run の止まり方でなく
  「落ちた」と言い、終わりの無いまま残った出来事（頭の帯の 1 文）に数えない（落ちた手番に数える。完了した run が「止めた」と出ない）
- 雛形の頭の「比」の行（「比 <下限>: <札>/<札> ...」。色の札の組と、WCAG の比の下限）の組は、light と dark の両方の札の値で下限以上
  （dark は書いた札だけを替え、ほかは light の値）。どの組の色を比べるかは雛形が書き、ここは計るだけ（見た目の形は縛らない。E25 の 4）
"""
import json
import re
import unittest

from viewer.src import page

RATIO = re.compile(r"^\s*比 ([\d.]+): (.+?)(?:\s*\*/)?$", re.M)


def palette(text: str, head: str) -> dict[str, str]:
    """雛形の CSS の頭（:root か :root[data-theme=dark]）の札の値"""
    body = re.search(re.escape(head) + r"\{(.*?)\}", text, re.S)[1]
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{3,6})\b", body))


def contrast(a: str, b: str) -> float:
    """WCAG 2 の比（相対の明るさの比）"""
    def lum(color: str) -> float:
        h = color.lstrip("#")
        h = "".join(c * 2 for c in h) if len(h) == 3 else h
        rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        r, g, b_ = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * r + 0.7152 * g + 0.0722 * b_
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


OUTSIDE = (re.compile(r"<script\b[^>]*\bsrc\b", re.I), re.compile(r"\bimport\s*\("), re.compile(r"\bfetch\s*\("))


class PageCase(unittest.TestCase):
    def test_template_reads_no_other_file(self):
        text = page.TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual([p.pattern for p in OUTSIDE if p.search(text)], [])

    def test_endless_events_are_found_by_their_cut_mark(self):
        text = page.TEMPLATE.read_text(encoding="utf-8")
        self.assertRegex(text, r"const ENDLESS = [^\n]*\.filter\(e => e\.cut && e\.status !== 'failed'\)")

    def test_event_words_say_how_a_cut_event_stopped(self):
        text = page.TEMPLATE.read_text(encoding="utf-8")
        self.assertRegex(text, r"const evWord = e => e\.cut \? \(e\.status === 'failed' \? '落ちた' : openLook\(e\.status\)\.word\) : ")
        others = [line for line in text.splitlines() if not line.startswith("const evWord = ")]
        self.assertEqual([line.strip() for line in others if re.search(r"stWord\([\w.]*\bstatus\)", line)], [])

    def test_page_is_one_file(self):
        data = {"texts": {"a": "</script><!-- <script>x</script> </SCRIPT"}, "made_at": "now"}
        made = page.render(data)
        self.assertEqual(made.lower().count("</script"), page.TEMPLATE.read_text(encoding="utf-8").lower().count("</script"))
        embedded = re.search(r'<script type="application/json" id="data">(.*?)</script>', made, re.S)[1]
        self.assertEqual(json.loads(embedded), data)

    def test_declared_color_pairs_meet_their_ratio(self):
        text = page.TEMPLATE.read_text(encoding="utf-8")
        light = palette(text, ":root")
        themes = {"light": light, "dark": {**light, **palette(text, ":root[data-theme=dark]")}}
        rules = [(float(floor), pair.split("/")) for floor, pairs in RATIO.findall(text) for pair in pairs.split()]
        self.assertTrue(rules, "雛形に「比」の行が無い")
        short = [f"{name} {a}/{b} {contrast(colors[a], colors[b]):.2f} < {floor}" for name, colors in themes.items()
                 for floor, (a, b) in rules if contrast(colors[a], colors[b]) < floor]
        self.assertEqual(short, [])


if __name__ == "__main__":
    unittest.main()

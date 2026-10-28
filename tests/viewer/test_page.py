"""見る道具の 1 枚のページ（viewer/page.tpl.html と viewer/src/page.py。docs/design/viewer.md の照らしの 4）。

- 雛形は別のファイルからスクリプトを読まない（viewer/AGENTS.md の E25 の 3）: `<script src`・`import(`・`fetch(` が無い。見た目は縛らない（E25 の 4）
- elkjs は照らしの値（viewer/elkjs.json の integrity）が合う tarball だけを使う: 取った物もキャッシュの物も、合わなければページを書かずに
  止まり、合わない物をキャッシュに置かない。網に届かない時は、置くべきパスと照らしの値を出して止まる
- 合う tarball はキャッシュに置き、次からは網を使わない。データの字（記録の </script> や <!-- を含む）と elkjs の字と注（大文字の
  </SCRIPT も）は script の中身を閉じず、データはそのまま読み戻せる

試験は網に出ない（網の口 get を差し替える）。合う tarball は小さな偽の tarball を作り、照らしの値をその値に差し替えて使う。
"""
import io
import json
import re
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from viewer.src import page

OUTSIDE = (re.compile(r"<script\b[^>]*\bsrc\b", re.I), re.compile(r"\bimport\s*\("), re.compile(r"\bfetch\s*\("))


def tarball(bundle: str) -> bytes:
    body = io.BytesIO()
    with tarfile.open(fileobj=body, mode="w:gz") as tar:
        for name, text in ((page.ELK["bundle"], bundle), (page.ELK["license_file"], "license */ </Script> text")):
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return body.getvalue()


class PageCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.env = {"HOME": tmp.name, "XDG_CACHE_HOME": str(Path(tmp.name) / "cache")}
        self.cached = Path(self.env["XDG_CACHE_HOME"]) / "works-factory" / "viewer" / f"elkjs-{page.ELK['version']}" / Path(page.ELK["tarball"]).name

    def test_template_reads_no_other_file(self):
        text = page.TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual([p.pattern for p in OUTSIDE if p.search(text)], [])

    def test_mismatched_elk_stops(self):
        got = lambda url, headers, size: (200, tarball("var ELK = 1;"))  # noqa: E731
        with self.assertRaises(page.Unfetched) as stop:
            page.render({}, self.env, got)
        self.assertIn("照らしの値が合わない", str(stop.exception))
        self.assertFalse(self.cached.exists())
        self.cached.parent.mkdir(parents=True)
        self.cached.write_bytes(tarball("var ELK = 2;"))
        with self.assertRaises(page.Unfetched):
            page.render({}, self.env, got)

    def test_unreachable_elk_names_the_place(self):
        def down(url, headers, size):
            raise page.webget.FetchError("URLError: down")
        with self.assertRaises(page.Unfetched) as stop:
            page.render({}, self.env, down)
        self.assertIn(str(self.cached), str(stop.exception))
        self.assertIn(page.ELK["integrity"], str(stop.exception))

    def test_page_is_one_file(self):
        body = tarball("window.ELK = function () {}; // </script> and </SCRIPT inside")
        calls = []

        def get(url, headers, size):
            calls.append(url)
            return 200, body

        data = {"texts": {"a": "</script><!-- <script>x</script>"}, "made_at": "now"}
        with mock.patch.dict(page.ELK, integrity=page.integrity(body)):
            first = page.render(data, self.env, get)

            def down(url, headers, size):
                raise page.webget.FetchError("URLError: down")
            again = page.render(data, self.env, down)
        self.assertEqual((calls, first), ([page.ELK["tarball"]], again))
        self.assertEqual(first.lower().count("</script"), page.TEMPLATE.read_text(encoding="utf-8").lower().count("</script"))
        embedded = re.search(r'<script type="application/json" id="data">(.*?)</script>', first, re.S)[1]
        self.assertEqual(json.loads(embedded), data)
        self.assertIn("window.ELK = function", first)


if __name__ == "__main__":
    unittest.main()

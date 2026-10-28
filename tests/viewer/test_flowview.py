"""見る道具の入口（viewer/flowview.py）の止まり方と終了の値（viewer/AGENTS.md の E25 の 2・docs/design/viewer.md の 6.6）。

- --ja-import は、置き場が無い時と拒んだ訳が在る時に 0 でない値で終わる（取り込めた訳は取り込む）
- --ja-import と --ja-prune はページを書かない（出力の名を添えても）
- --ja-batches の置き場が工場の clone の下なら、何も書かずに止まる
- 出力の HTML が無ければ止まる

試験は一時のフォルダに木と控えと置き場を組み（tests/viewer/test_ja.py の Base）、利用者の環境の置き場を一時のフォルダへ向ける。
"""
import contextlib
import io
import os
from unittest import mock

from tests.viewer.test_ja import HEAD, OTHER, Base
from viewer import flowview
from viewer.src import ja


class FlowviewCase(Base):
    def setUp(self):
        super().setUp()
        patch = mock.patch.dict(os.environ, self.env)
        patch.start()
        self.addCleanup(patch.stop)
        self.out = self.tmp / "out" / "page.html"

    def main(self, *argv: str) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            try:
                code = flowview.main(list(argv))
            except SystemExit as stop:
                code = stop.code
        return code, err.getvalue()

    def test_import_from_a_missing_folder_fails(self):
        code, err = self.main("--ja-import", str(self.tmp / "nowhere"), str(self.out))
        self.assertNotEqual(code, 0)
        self.assertIn("nowhere", err)
        self.assertFalse(self.repo.exists())
        self.assertFalse(self.out.exists())

    def test_import_with_a_refused_translation_fails_but_keeps_the_good_ones(self):
        folder = self.tmp / "b"
        ja.export({ja.key(HEAD): HEAD, ja.key(OTHER): OTHER}, folder)
        (folder / "batch-0.ja.txt").write_text(f"%%% {ja.key(HEAD)}\n{{file}} を読む。\n%%% {ja.key(OTHER)}\n{{lost}} 会話から来た。\n",
                                               encoding="utf-8")
        code, err = self.main("--ja-import", str(folder))
        self.assertNotEqual(code, 0)
        self.assertIn(ja.key(OTHER), err)
        self.assertEqual(list(ja._load(self.repo)), [ja.key(HEAD)])

    def test_prune_writes_no_page(self):
        code, _ = self.main("--ja-prune", str(self.out))
        self.assertEqual(code, 0)
        self.assertFalse(self.out.exists())

    def test_batches_in_the_clone_are_refused(self):
        inside = flowview.ROOT / "viewer-batches-must-not-be-written"
        code, err = self.main("--ja-batches", str(inside), str(self.out))
        self.assertEqual(code, 2)
        self.assertIn("clone", err)
        self.assertFalse(inside.exists())
        self.assertFalse(self.out.exists())

    def test_page_needs_an_output(self):
        code, err = self.main()
        self.assertEqual(code, 2)
        self.assertIn("出力の HTML", err)

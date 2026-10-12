"""差分が足した Markdown のリンクの照らし（recount.md_link_errors。元 works/.shared/core/graphloops/rules/review-loop.py:2804-2809・
`_added_md_links` :2852・`_walk_as_written` :2896・`_md_link_errors` :2915）の細目。元の works にもこの細目の試験は無かった
（元の試験は graphloops 側）ので、lib の今の口を tests/e2e/target-seed/ の写しの小さなリポジトリで縛る。

縛る事（1 本ずつ、返りに出る／出ないを照らす）:
- 未追跡の .md は中身の全行を足された行として数え、追跡している .md は差分の行だけを見る
- 指し先は symlink の部品だけを実体へ解く
- 綴りの大小が違う指し先は版の一覧で引いて届かない
- リポジトリの外を指すリンクは名指す
- 版に入る物の無いディレクトリ（空のディレクトリ）は届かない。版に在るファイルを持つディレクトリは届く
- コードブロックの囲いとコードスパンの中のリンクは拾わない
- URL の scheme（https: mailto: …）の付いたリンクは引かない
"""
import os
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from tests.bin.gitkit import committed_copy, git  # noqa: E402
import accept  # noqa: E402
import recount  # noqa: E402

SEED = LIB.parent / "tests" / "e2e" / "target-seed"
GUIDE = "# 案内\n\n## 節の名\n\n[古いリンク](gone-old.md)\n"


class MdLinkCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="works-md-links-")
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name).resolve()
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, SEED)
        (self.repo / "guide.md").write_text(GUIDE, encoding="utf-8")
        (self.repo / "real").mkdir()
        (self.repo / "real" / "doc.md").write_text("# 実体\n", encoding="utf-8")
        os.symlink("real", self.repo / "link")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "案内と実体と symlink")
        self.base = git(self.repo, "rev-parse", "HEAD")

    def errors(self, **files) -> list:
        """files {パス: 中身} を作業ツリーに書き、足したリンクの照らしの返り"""
        for name, text in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        with accept.in_repo(self.repo):
            return recount.md_link_errors(self.base, str(self.repo))

    def test_untracked_md_counts_every_line(self):
        got = self.errors(**{"new.md": "# 新しい\n\n[壊れた](gone.md)\n"})
        self.assertEqual(len(got), 1, got)
        self.assertIn("new.md:3 の (gone.md)", got[0])
        self.assertFalse(any("gone-old.md" in e for e in got), "追跡している .md の変えていない行は見ない")
        got = self.errors(**{"guide.md": GUIDE + "\n[足した](gone-added.md)\n"})
        self.assertEqual(sorted(e.split(" ")[0] for e in got), ["guide.md:7", "new.md:3"], got)

    def test_symlink_part_is_resolved(self):
        self.assertEqual(self.errors(**{"new.md": "[実体](link/doc.md) と [直](real/doc.md)\n"}), [])

    def test_case_mismatch_is_not_in_the_version(self):
        got = self.errors(**{"new.md": "[大](STATS.py)\n"})
        self.assertEqual(len(got), 1, got)
        self.assertIn("版に無い", got[0])
        self.assertEqual(self.errors(**{"new.md": "[小](stats.py)\n"}), [])

    def test_outside_the_repository_is_named(self):
        (self.tmp / "outside.md").write_text("# 外\n", encoding="utf-8")
        got = self.errors(**{"new.md": "[外](../outside.md)\n"})
        self.assertEqual(len(got), 1, got)
        self.assertIn("リポジトリの外を指す", got[0])

    def test_empty_directory_is_not_in_the_version(self):
        (self.repo / "empty").mkdir()
        got = self.errors(**{"new.md": "[空](empty)\n"})
        self.assertEqual(len(got), 1, got)
        self.assertIn("版に無い", got[0])
        self.assertEqual(self.errors(**{"new.md": "[在る](real)\n"}), [])

    def test_links_in_fences_and_code_spans_are_not_picked(self):
        text = "```\n[囲い](gone-a.md)\n```\n\n`[スパン](gone-b.md)`\n\n~~~\n[波](gone-c.md)\n~~~\n"
        self.assertEqual(self.errors(**{"new.md": text}), [])
        got = self.errors(**{"new.md": text + "[外の](gone-d.md)\n"})
        self.assertEqual([("gone-d.md" in e) for e in got], [True], got)

    def test_urls_are_not_followed(self):
        text = "[網](https://example.invalid/gone.md) と [便](mailto:a@example.invalid) と [端](ftp://example.invalid/x)\n"
        self.assertEqual(self.errors(**{"new.md": text}), [])


if __name__ == "__main__":
    unittest.main()

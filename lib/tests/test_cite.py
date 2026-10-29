"""名指しの形と場所の文の読みの住処 cite の試験（本物の cite・holeties・conflict・material を直に呼ぶ。FAST）"""
import pathlib
import subprocess
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import cite  # noqa: E402
from tests.bin.gitkit import GIT_ID  # noqa: E402
from tests.bin.hermetic import child_env  # noqa: E402


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


class ElsewhereCase(unittest.TestCase):
    """文が名指したファイルのうち版に無い物を、ほかの版で探して読む（人の答えや指示ファイルが指した文書が、まだ取り込まれていない枝に
    だけ在る時。guided-resolver #2177 の run）"""

    def git(self, *args):
        return subprocess.run(["git", *GIT_ID, "-C", str(self.repo), *args], env=child_env(), capture_output=True, text=True,
                              encoding="utf-8", check=True).stdout.strip()

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name)
        self.git("init", "-q", "-b", "main")
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "AGENTS.md").write_text("決まり\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "main")
        self.git("checkout", "-q", "-b", "canon")
        (self.repo / "infra" / "docs").mkdir(parents=True)
        (self.repo / "infra" / "docs" / "principles.adoc").write_text("正典の本文\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "canon")
        self.git("checkout", "-q", "main")

    def test_named_files_are_paths_with_a_name_and_an_extension(self):
        text = ("正典（infra/docs/principles.adoc。git show origin/canon:<path> で読める）と docs/AGENTS.md:3、"
                "https://example.com/a/b.md と chart の _helpers.tpl、フォルダ deploy/chart/ と ./x/y.md と ../z/w.md、infra/docs/principles.adoc")
        self.assertEqual(cite.named_files(text), ["infra/docs/principles.adoc", "docs/AGENTS.md", "x/y.md"])
        self.assertEqual(cite.named_files(None), [])

    def test_a_file_only_on_another_branch_is_read_from_there(self):
        rows = cite.elsewhere(self.repo, "main", ["infra/docs/principles.adoc", "docs/AGENTS.md", "AGENTS.md", "new/file.md"])
        self.assertEqual([r["path"] for r in rows], ["infra/docs/principles.adoc", "new/file.md"],
                         "版に在る物と、在るパスで終わる名（フォルダからの相対）は数えない")
        got, none = rows
        self.assertEqual((got["found"], got["commit"], got["text"]), ("infra/docs/principles.adoc", self.git("rev-parse", "canon"), "正典の本文\n"))
        self.assertIn("canon", got["at"])
        self.assertEqual((none["found"], none["commit"], none["at"], none["text"]), ("", "", "", ""))

    def test_a_name_relative_to_a_folder_is_found_on_another_branch(self):
        rows = cite.elsewhere(self.repo, "main", ["docs/principles.adoc"])
        self.assertEqual((rows[0]["found"], rows[0]["text"]), ("infra/docs/principles.adoc", "正典の本文\n"))

    def test_unreadable_version_raises(self):
        with self.assertRaises(OSError):
            cite.elsewhere(self.repo, "no-such-rev", ["a/b.md"])

    def test_a_file_deleted_in_the_history_of_the_version_is_not_found(self):
        (self.repo / "docs" / "gone.md").write_text("古い決まり\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "add")
        self.git("rm", "-q", "docs/gone.md")
        self.git("commit", "-q", "-m", "drop")
        row, = cite.elsewhere(self.repo, "main", ["docs/gone.md"])
        self.assertEqual((row["found"], row["commit"], row["at"], row["text"]), ("", "", "", ""),
                         "読む版の祖先で消した文書は、まだ取り込まれていない枝の本文ではない")

    def test_a_file_only_in_the_stash_is_not_found(self):
        (self.repo / "wip").mkdir()
        (self.repo / "wip" / "note.md").write_text("書きかけ\n", encoding="utf-8")
        self.git("add", "wip/note.md")
        self.git("stash", "push", "-q", "-m", "wip")
        row, = cite.elsewhere(self.repo, "main", ["wip/note.md"])
        self.assertEqual((row["found"], row["commit"], row["at"], row["text"]), ("", "", "", ""),
                         "commit していない書きかけ（stash）は読まない")


if __name__ == "__main__":
    unittest.main()

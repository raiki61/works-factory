"""地図の探し方（lib/concepthome.py。計画 2026-10-09-clean-whole の Task 2.1）。
名前の一覧だけを見る"""
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import concepthome as ch  # noqa: E402
from tests.bin.gitkit import git  # noqa: E402


class PickCase(unittest.TestCase):
    def test_pick_root_and_nested(self):
        self.assertEqual(ch.pick_maps(["docs/x.md", "works/docs/concepts.md", "docs/concepts.md", "a/docs/concepts.md.bak"]),
                         (["docs/concepts.md", "works/docs/concepts.md"], 2))

    def test_pick_caps(self):
        names = [f"p{i}/docs/concepts.md" for i in range(7)]
        self.assertEqual(ch.pick_maps(names), (names[:5], 7))

    def test_pick_tables_and_base(self):
        got = ch.pick_tables(["works/docs/concepts.json", "docs/concepts.json", "x/concepts.json"])
        self.assertEqual(got, ["docs/concepts.json", "works/docs/concepts.json"])
        self.assertEqual([ch.base_of(n) for n in got], ["", "works"])


class TrackedNamesCase(unittest.TestCase):
    def test_lists_tracked_files_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp)
            git(repo, "init", "-q")
            (repo / "a.txt").write_text("x", encoding="utf-8")
            (repo / "b c.txt").write_text("x", encoding="utf-8")
            (repo / "untracked.txt").write_text("x", encoding="utf-8")
            git(repo, "add", "a.txt", "b c.txt")
            self.assertEqual(ch.tracked_names(repo), (["a.txt", "b c.txt"], ""))

    def test_git_failure_is_a_reason_not_an_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            names, why = ch.tracked_names(tmp)
            self.assertEqual(names, [])
            self.assertTrue(why)
            self.assertLessEqual(len(why), 300)


if __name__ == "__main__":
    unittest.main()

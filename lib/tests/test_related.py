"""変更に関わる試験だけを選ぶ口（lib/related.py。持ち主の決め related-tests-only）の検査。

- applies: test_cmd が空で、対象の根に走らせる段の宣言が無い対象（走らせ方が決まらない道）だけ真
- pick: rev から今の作業ツリーまでに触ったファイルと seeds を起点に、直に関わる試験だけを選ぶ。選べない時は whole。
  関わる試験が無いのは whole でなく files が空。届いただけの試験は left に名前で残す
- args: 選んだ試験を絶対パスにする
- lines: 報告の行（走らせた数・走らせなかった試験の名・全体の試験を CI と人に任せたこと・一式を走らせた理由）
"""
import pathlib
import shutil
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import related  # noqa: E402
from tests.bin.gitkit import committed_copy, git  # noqa: E402

PROJ = {
    "pkg/__init__.py": "",
    "pkg/core.py": "def compute_total(x):\n    return x + 1\n",
    "pkg/mid.py": "from pkg.core import compute_total\n\n\ndef use():\n    return compute_total(1)\n",
    "tests/test_core.py": "from pkg import core\n\nassert core.compute_total(1) == 2\n",
    "tests/test_mid.py": "from pkg.mid import use\n\nassert use() == 2\n",
    "tests/test_other.py": "import json\n\nassert json.loads('1') == 1\n",
    "docs/note.md": "# note\n",
    "web/widget.js": "export function widget() { return 1 }\n",
}
_SRC = None


def setUpModule():
    global _SRC
    _SRC = pathlib.Path(tempfile.mkdtemp(prefix="works-related-src-"))
    for rel, text in PROJ.items():
        p = _SRC / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def tearDownModule():
    shutil.rmtree(_SRC, ignore_errors=True)


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="works-related-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = self.tmp / "repo"
        self.head = committed_copy(self.repo, _SRC)
        self.cache = self.tmp / "cache"

    def write(self, rel, text):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def pick(self, **kw):
        return related.pick(self.repo, **{"rev": self.head, "seeds": (), "cache_dir": self.cache, **kw})


class AppliesCase(RepoCase):
    def test_no_command_and_no_declaration_is_the_undecided_way(self):
        self.assertTrue(related.applies(self.repo, ""))
        self.assertTrue(related.applies(self.repo, "  \n"))

    def test_a_given_command_or_a_declaration_is_the_users_way_and_is_left_alone(self):
        self.assertFalse(related.applies(self.repo, "make test"))
        self.write(".review-checks.json", '{"steps": []}\n')
        self.assertFalse(related.applies(self.repo, ""))


class PickCase(RepoCase):
    def test_a_change_selects_the_tests_that_touch_it_directly_and_leaves_the_far_ones_by_name(self):
        self.write("pkg/core.py", PROJ["pkg/core.py"] + "\n# touched\n")
        got = self.pick()
        self.assertFalse(got["whole"])
        self.assertEqual(got["files"], ["tests/test_core.py"])
        self.assertEqual(got["left"], ["tests/test_mid.py"])

    def test_seeds_stand_for_the_change_when_the_tree_is_untouched(self):
        got = self.pick(seeds=["pkg/mid.py"])
        self.assertEqual(got["files"], ["tests/test_mid.py"])
        self.assertEqual(got["left"], [])

    def test_nothing_related_is_an_empty_pick_not_a_whole_run(self):
        self.write("docs/note.md", "# note\n\nchanged\n")
        got = self.pick()
        self.assertFalse(got["whole"])
        self.assertEqual(got["files"], [])

    def test_something_unreadable_near_the_change_runs_everything_and_says_why(self):
        self.write("web/widget.js", "export function widget() { return 2 }\n")
        got = self.pick()
        self.assertTrue(got["whole"])
        self.assertTrue(got["reasons"])
        self.assertEqual(got["files"], [])

    def test_a_revision_that_cannot_be_read_runs_everything(self):
        got = self.pick(rev="no-such-rev")
        self.assertTrue(got["whole"])
        self.assertIn("地図", " ".join(got["reasons"]))

    def test_a_file_that_is_gone_is_not_handed_to_the_runner(self):
        self.write("pkg/core.py", PROJ["pkg/core.py"] + "\n# touched\n")
        (self.repo / "tests" / "test_core.py").unlink()
        self.assertNotIn("tests/test_core.py", self.pick()["files"])


class ArgsAndLinesCase(RepoCase):
    def test_args_are_absolute_paths_in_the_root(self):
        picked = {"whole": False, "files": ["tests/test_core.py"], "left": [], "far": [], "reasons": []}
        self.assertEqual(related.args(self.repo, picked), [str((self.repo / "tests/test_core.py").resolve())])
        self.assertEqual(related.args(self.repo, {**picked, "whole": True}), [])

    def test_lines_name_what_ran_what_was_left_and_who_takes_the_rest(self):
        picked = {"whole": False, "files": ["tests/test_core.py"], "left": ["tests/test_mid.py"], "far": [], "reasons": []}
        text = "\n".join(related.lines(picked))
        self.assertIn("1 件", text)
        self.assertIn("tests/test_mid.py", text)
        self.assertIn("CI と人", text)

    def test_lines_say_when_everything_ran_and_why(self):
        picked = {"whole": True, "files": [], "left": [], "far": [], "reasons": ["分からない物が近くに在る"]}
        text = "\n".join(related.lines(picked))
        self.assertIn("一式", text)
        self.assertIn("分からない物が近くに在る", text)

    def test_lines_say_when_nothing_is_related(self):
        picked = {"whole": False, "files": [], "left": [], "far": [], "reasons": []}
        self.assertIn("関わる試験が無い", "\n".join(related.lines(picked)))


if __name__ == "__main__":
    unittest.main()

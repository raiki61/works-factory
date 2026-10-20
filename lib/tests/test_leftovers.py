"""lib/leftovers.py の試験（元 test_fix_seams の TestLeftovers と test_blk_fix の TestLeftoversModule。integration.md 4.2-6・4.2-7）。

- record_ignored・remove_new_ignored: 控えに無かった無視されるファイルだけを消し、前から在った無視されるフォルダの中は残し、
  除くパスの頭の下は消さない。既定の () では除かない。控えは置き場のフォルダに置く
- leftovers は標準ライブラリだけを読む
"""
import ast
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from tests.bin.gitkit import committed_copy, git  # noqa: E402
import leftovers  # noqa: E402

SEED = LIB.parent / "tests" / "e2e" / "target-seed"
SKIP = ("vendored/",)


class TempCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="works-leftovers-")
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        self.rev = committed_copy(self.repo, SEED)
        self.place = self.tmp / "place"
        self.place.mkdir()


class TestLeftovers(TempCase):
    """控えは置き場のフォルダに置く。消すのは控えに無かった無視されるファイルだけ"""

    def setUp(self):
        super().setUp()
        (self.repo / ".gitignore").write_text("*.log\n.venv/\nvendored/\n", encoding="utf-8")
        git(self.repo, "add", ".gitignore")
        git(self.repo, "commit", "-q", "-m", "ignore")
        (self.repo / ".venv").mkdir()
        (self.repo / ".venv" / "old.txt").write_text("前から\n", encoding="utf-8")
        (self.repo / "old.log").write_text("前から\n", encoding="utf-8")

    def make_new(self):
        (self.repo / "new.log").write_text("修正役が残した\n", encoding="utf-8")
        (self.repo / ".venv" / "new.txt").write_text("前から在ったフォルダの中\n", encoding="utf-8")
        (self.repo / "vendored").mkdir(exist_ok=True)
        (self.repo / "vendored" / "copy.log").write_text("除く頭の下\n", encoding="utf-8")

    def test_record_writes_before_into_the_place(self):
        got = leftovers.record_ignored(self.place, self.repo)
        self.assertEqual(got["file"], str(self.place / leftovers.IGNORED_BEFORE_FILE))
        before = json.loads((self.place / leftovers.IGNORED_BEFORE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(set(before), {"ignored", "ignored_dirs", "dirs", "head_tree"})
        self.assertEqual(before["ignored_dirs"], [".venv/"])
        self.assertIn("old.log", before["ignored"])
        self.assertEqual(leftovers.head_tree(self.place), leftovers.snapshot(self.repo))

    def test_removes_only_new_ignored_and_keeps_skip_prefix(self):
        leftovers.record_ignored(self.place, self.repo)
        self.make_new()
        got = leftovers.remove_new_ignored(self.place, self.repo, skip=SKIP)
        self.assertEqual(got["count"], 1)
        self.assertEqual(json.loads((self.place / leftovers.REMOVED_FILE).read_text(encoding="utf-8")), {"removed": ["new.log"]})
        self.assertFalse((self.repo / "new.log").exists())
        self.assertTrue((self.repo / "old.log").is_file(), "前から在った無視されるファイルは残す")
        self.assertTrue((self.repo / ".venv" / "new.txt").is_file(), "前から在った無視されるフォルダの中は残す")
        self.assertTrue((self.repo / "vendored" / "copy.log").is_file(), "除くパスの頭の下は消さない")

    def test_default_skips_nothing(self):
        leftovers.record_ignored(self.place, self.repo)
        self.make_new()
        got = leftovers.remove_new_ignored(self.place, self.repo)
        self.assertEqual(got["count"], 2)
        self.assertFalse((self.repo / "vendored").exists(), "既定の () では除かない（空になった親も消す）")
        self.assertTrue((self.repo / ".venv" / "new.txt").is_file())

    def test_no_before_is_unreadable(self):
        with self.assertRaises(leftovers.Unreadable):
            leftovers.remove_new_ignored(self.place, self.repo, skip=SKIP)

    def test_keeps_files_inside_old_ignored_dirs_and_empty_dirs(self):
        """F418: 前から在った無視されるフォルダ（svc/.venv）に足したファイルは 1 本も消さず、新しく出来た無視されるフォルダは丸ごと
        消す。前から在った空のフォルダ（build/empty・追跡するフォルダの下の src/cache）に置かれた無視されるファイルは消すがフォルダは
        残し、後から出来たフォルダは消す。フォルダの控えの無い古い形の控えは拒んで何も消さない（元 works/tests/test_blk_fix.py:1641
        test_keeps_new_files_inside_ignored_dir_that_was_there_before・:1661 test_keeps_empty_dir_that_was_there_before・:1682
        test_refuses_old_record_without_dirs の写し）"""
        (self.repo / ".gitignore").write_text("*.log\n.venv/\nvendored/\n__pycache__/\n*.pyc\n**/.venv\n", encoding="utf-8")
        (self.repo / "src").mkdir()
        (self.repo / "src" / "keep.txt").write_text("k\n", encoding="utf-8")
        git(self.repo, "add", ".gitignore", "src/keep.txt")
        git(self.repo, "commit", "-q", "-m", "ignore")
        venv = self.repo / "svc" / ".venv"
        (venv / "lib").mkdir(parents=True)
        (venv / "lib" / "old.py").write_text("o\n", encoding="utf-8")
        (self.repo / "build" / "empty").mkdir(parents=True)
        (self.repo / "src" / "cache").mkdir()
        leftovers.record_ignored(self.place, self.repo)
        added = [venv / "lib" / "pkg" / f"m{i}.py" for i in range(5)]
        added[0].parent.mkdir()
        for p in added:
            p.write_text("m\n", encoding="utf-8")
        (self.repo / "svc2" / ".venv" / "lib").mkdir(parents=True)
        (self.repo / "svc2" / ".venv" / "lib" / "n.py").write_text("n\n", encoding="utf-8")
        (self.repo / "build" / "empty" / "x.pyc").write_bytes(b"x")
        (self.repo / "src" / "cache" / "y.pyc").write_bytes(b"y")
        (self.repo / "src" / "new" / "__pycache__").mkdir(parents=True)
        (self.repo / "src" / "new" / "__pycache__" / "z.pyc").write_bytes(b"z")
        got = leftovers.remove_new_ignored(self.place, self.repo, skip=SKIP)
        removed = json.loads((self.place / leftovers.REMOVED_FILE).read_text(encoding="utf-8"))["removed"]
        self.assertEqual(got["count"], len(removed))
        self.assertEqual([p for p in added if not p.exists()], [], "前から在った .venv に足したファイルは残す")
        self.assertTrue((venv / "lib" / "old.py").exists())
        self.assertFalse((self.repo / "svc2").exists(), "修正役の後に出来た無視のフォルダは消す")
        self.assertTrue((self.repo / "build" / "empty").is_dir(), "前から在った空のフォルダは残す")
        self.assertFalse((self.repo / "build" / "empty" / "x.pyc").exists())
        self.assertTrue((self.repo / "src" / "cache").is_dir(), "前から在った空のフォルダは残す")
        self.assertFalse((self.repo / "src" / "cache" / "y.pyc").exists())
        self.assertFalse((self.repo / "src" / "new").exists(), "修正役の後に出来たフォルダは消す")
        self.assertTrue((self.repo / "src" / "keep.txt").exists())
        with self.subTest("フォルダの控えの無い古い形の控え"):
            (self.place / leftovers.IGNORED_BEFORE_FILE).write_text(json.dumps({"ignored": []}), encoding="utf-8")
            (self.repo / "__pycache__").mkdir()
            (self.repo / "__pycache__" / "x.pyc").write_bytes(b"x")
            with self.assertRaisesRegex(leftovers.Unreadable, "dirs"):
                leftovers.remove_new_ignored(self.place, self.repo, skip=SKIP)
            self.assertTrue((self.repo / "__pycache__" / "x.pyc").exists())


class TestLeftoversModule(unittest.TestCase):
    def test_leftovers_is_stdlib_only(self):
        """標準ライブラリだけ（lib のほかのモジュールは読まない。消した物のファイルの名も自分で持つ）"""
        tree = ast.parse((LIB / "leftovers.py").read_text(encoding="utf-8"))
        self.assertFalse(any(isinstance(n, ast.ImportFrom) and n.level for n in ast.walk(tree)))
        names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level == 0}
        self.assertTrue(names)
        self.assertEqual(sorted(names - set(sys.stdlib_module_names)), [])


if __name__ == "__main__":
    unittest.main()

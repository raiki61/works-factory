"""lib/groups.py の試験（元 test_fix_seams の TestGroups。integration.md 4.2-6）。tests/bin/gitkit.py と tests/e2e/target-seed/ の写しで
小さなリポジトリを作る。

- groups.adopt_tree・end_tree・diff_since: 同じ clone の 2 つの worktree の間で親の姿の木を子に写し、子の変更の差分を取り、
  unittrees.apply で 2 つの組の差分を順に当てる。2 つ目が当たらない時に 1 つ目が残り、2 つ目は当たらないと返る
"""
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from tests.bin.gitkit import committed_copy, git  # noqa: E402
import groups  # noqa: E402
import leftovers  # noqa: E402
import unittrees  # noqa: E402

SEED = LIB.parent / "tests" / "e2e" / "target-seed"


class TempCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="works-groups-")
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        self.rev = committed_copy(self.repo, SEED)
        self.place = self.tmp / "place"
        self.place.mkdir()


class TestGroups(TempCase):
    """親の作業ツリー（未 commit の直しを持つ）の姿を木で子の worktree に写し、子の差分を親へ順に当てる"""

    def child(self, name: str) -> pathlib.Path:
        path = self.tmp / name
        git(self.repo, "worktree", "add", "--detach", "--quiet", str(path), "HEAD")
        return path

    def test_adopt_copies_parent_shape_and_diffs_apply_in_order(self):
        stats = (self.repo / "stats.py").read_text(encoding="utf-8")
        (self.repo / "stats.py").write_text(stats + "\n# 親の直し\n", encoding="utf-8")
        (self.repo / "NOTES.md").write_text("親の新しいファイル\n", encoding="utf-8")
        tree = groups.end_tree(self.repo)
        self.assertEqual(tree, leftovers.snapshot(self.repo))

        c1, c2 = self.child("c1"), self.child("c2")
        (c1 / "NOTES.md").write_text("子に前から在った追跡外のファイル\n", encoding="utf-8")   # 木にも在る名
        for c in (c1, c2):
            groups.adopt_tree(c, tree)
            self.assertEqual((c / "stats.py").read_text(encoding="utf-8"), stats + "\n# 親の直し\n", "親の未 commit の直しが見える")
            self.assertEqual((c / "NOTES.md").read_text(encoding="utf-8"), "親の新しいファイル\n", "木の姿に替わる")
            self.assertEqual(groups.end_tree(c), tree, "写した後の子の姿は親の木と同じ")
            self.assertEqual(groups.diff_since(c, tree, groups.end_tree(c)), "", "変えていなければ差分は空")

        (c1 / "NOTES.md").write_text("組 1 の直し\n", encoding="utf-8")
        (c1 / "ONE.md").write_text("組 1 の新しいファイル\n", encoding="utf-8")
        (c2 / "NOTES.md").write_text("組 2 の直し\n", encoding="utf-8")   # 組 1 と同じ行
        d1 = groups.diff_since(c1, tree, groups.end_tree(c1))
        d2 = groups.diff_since(c2, tree, groups.end_tree(c2))
        self.assertIn("diff --git a/NOTES.md b/NOTES.md", d1)
        self.assertIn("diff --git a/ONE.md b/ONE.md", d1)

        self.assertEqual(unittrees.apply(self.repo, d1), (True, ""))
        ok, why = unittrees.apply(self.repo, d2)
        self.assertFalse(ok)
        self.assertTrue(why)
        self.assertEqual((self.repo / "NOTES.md").read_text(encoding="utf-8"), "組 1 の直し\n", "1 つ目が残る")
        self.assertEqual((self.repo / "ONE.md").read_text(encoding="utf-8"), "組 1 の新しいファイル\n")
        self.assertEqual((self.repo / "stats.py").read_text(encoding="utf-8"), stats + "\n# 親の直し\n")


if __name__ == "__main__":
    unittest.main()

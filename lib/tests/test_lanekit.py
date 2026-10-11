"""並べの枝の部品（lib/lanekit.py。元 blk-fix/lib/lanekit.py）の純粋な口の検査。TDD の輪の並べ（tddlanes）と修正役の並べ（fixlanes）が同じ形で
使う物は lanekit に 1 つだけ在る（計画 docs/plans/2026-10-09-lanes-home.md）。

縛る事:
- groups(rows): タグを共にする物どうしを 1 組に（つながりは推移的・組の中と組の並びは rows の順・タグの無い物は 1 つで 1 組）
- relocate(path, repo, tree): run の作業ツリーの中のパスは単位の worktree の同じ所へ、外のパスはそのまま
- tree_ok(row): 行の tree の `.git` の 1 行が行の git と同じなら空、違う・git が空なら理由
- merge_in_order(lanes, merge_one): 枝を順に当て、前に当てた枝の差分のパスを後の枝の earlier に渡す（当てなかった枝のパスは渡さない）
- 締めの結末の語 JOINED・MERGED・BACK
"""
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import lanekit  # noqa: E402


class Names(unittest.TestCase):
    def test_outcome_words(self):
        self.assertEqual((lanekit.JOINED, lanekit.MERGED, lanekit.BACK), ("joined", "merged", "serial"))


class Groups(unittest.TestCase):
    def test_transitive_and_ordered(self):
        got = lanekit.groups([(1, ["a"]), (2, ["b"]), (3, ["a", "c"]), (4, ["c"]), (5, ["d"])])
        self.assertEqual(got, [[1, 3, 4], [2], [5]])

    def test_untagged_alone(self):
        self.assertEqual(lanekit.groups([("u1", []), ("u2", None), ("u3", [7])]), [["u1"], ["u2"], ["u3"]])

    def test_later_link_joins_earlier_groups(self):
        self.assertEqual(lanekit.groups([("p", [1]), ("q", [2]), ("r", [1, 2])]), [["p", "q", "r"]])

    def test_empty(self):
        self.assertEqual(lanekit.groups([]), [])


class Relocate(unittest.TestCase):
    def test_inside_moves_to_tree(self):
        self.assertEqual(lanekit.relocate("/r/repo/bin/run", "/r/repo", "/t/item-1"), pathlib.Path("/t/item-1/bin/run"))

    def test_outside_stays(self):
        self.assertEqual(lanekit.relocate("/usr/bin/python3", "/r/repo", "/t/item-1"), pathlib.Path("/usr/bin/python3"))


class TreeOk(unittest.TestCase):
    def test_same_line(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / ".git").write_text("gitdir: /x/wt/item-1\n", encoding="utf-8")
            self.assertEqual(lanekit.tree_ok({"tree": d, "git": "gitdir: /x/wt/item-1"}), "")
            self.assertIn(d, lanekit.tree_ok({"tree": d, "git": "gitdir: /x/wt/item-2"}))
            self.assertTrue(lanekit.tree_ok({"tree": d}), "切った時の git の 1 行が無い行は通さない")


class MergeInOrder(unittest.TestCase):
    def test_earlier_grows_only_with_applied(self):
        seen = []

        def one(lane, earlier):
            seen.append((lane, set(earlier)))
            if lane == "b":
                return lanekit.Merge("当たらない", "b.patch", [], [], True)
            return lanekit.Merge("", f"{lane}.patch", [f"{lane}.py", "shared.py"], [], False)
        got = lanekit.merge_in_order(["a", "b", "c"], one)
        self.assertEqual(seen, [("a", set()), ("b", {"a.py", "shared.py"}), ("c", {"a.py", "shared.py"})])
        self.assertEqual([(lane, m.why) for lane, m in got], [("a", ""), ("b", "当たらない"), ("c", "")])


if __name__ == "__main__":
    unittest.main()

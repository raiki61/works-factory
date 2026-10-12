"""組の部品（lib/lanekit.py。元 blk-fix/lib/lanekit.py）の純粋な口の検査。

縛る事:
- groups(rows): タグを共にする物どうしを 1 組に（つながりは推移的・組の中と組の並びは rows の順・タグの無い物は 1 つで 1 組）
- merge_in_order(lanes, merge_one): 組を順に当て、前に当てた組の差分のパスを後の組の earlier に渡す（当てなかった組のパスは渡さない）
"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import lanekit  # noqa: E402


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

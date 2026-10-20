"""組の差分を親の作業ツリーへ当てる口（lib/unittrees.py。元 .shared/core/unittrees.py）の検査。種の git は gitkit の型の写し。
差分は締めの節と同じく、組の作業ツリー（同じリポジトリの worktree）の始めの木と終わりの木（groups.end_tree）の差分
（groups.diff_since）で作る。

縛る事:
- 2 つの組が別のファイルを直す → 両方が親の作業ツリーに当たる
- 2 つの組が同じ行を直す → 2 つ目は当たらず (False, 理由)、作業ツリーは 1 つ目を当てたまま
- どの口も本物の index・HEAD・枝を動かさない
- union の中のファイルで両方が同じ所（末尾）に行を足しただけの食い違いは、作業ツリーの側の行の後に patch の側の行を置いて
  当たる（unioned に積む）。行を変えた塊・union の外のファイルは今どおり当たらず、作業ツリーは前のまま
- marked（dict）を渡すと、同じ行の食い違いも印つきで当たり（印を書いたパスとその印の長さを marked に積む。印の長さは中身の
  どの行とも重ならない長さを 7 から選ぶ）、union の中の挿しだけの食い違いは合わせて印を書かない。markers_left はそのパスの長さの
  印の頭か区切りの行が 1 行でも残るファイルと、長さの値が正しくないパスを引く。union の挿しだけの読みも同じ長さで読む
- 合わせ役の指示書（fix の prompts/parts/clash.md）は印の両側を MARK_LABELS の名のまま名指し、印の長さ（brief の markers）は {marker_size} として md の clash.md に渡り、拒まれる行の決まりも clash.md が持つ
- tests_unique: 合わせた中身に同じ名のテストの定義が 2 つ在れば合わせない。patch_names: 差分の行先のパス
"""
import pathlib
import shutil
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import groups  # noqa: E402
import unittrees  # noqa: E402
from tests.bin.gitkit import committed_copy, git  # noqa: E402
from tests.blocks.kit import BLOCKS as WORKFLOWS  # noqa: E402  （pack のフォルダ。入れ替えの前も後も同じ口）

CLASH_PART = WORKFLOWS / "fix" / "prompts" / "parts" / "clash.md"   # 合わせ役の指示（fix の block。pack のフォルダから引く）

SEED = {"a.txt": "a1\na2\na3\n", "b.txt": "b1\nb2\nb3\n", "bin.dat": None, ".gitignore": "ignored.log\n"}
_SRC = None


def setUpModule():
    global _SRC
    _SRC = pathlib.Path(tempfile.mkdtemp(prefix="works-unittrees-src-"))
    for rel, text in SEED.items():
        p = _SRC / rel
        if text is None:
            p.write_bytes(bytes(range(256)))
        else:
            p.write_text(text, encoding="utf-8")


def tearDownModule():
    shutil.rmtree(_SRC, ignore_errors=True)


class UnitTrees(unittest.TestCase):
    def setUp(self):
        self.home = pathlib.Path(tempfile.mkdtemp(prefix="works-unittrees-"))
        self.addCleanup(shutil.rmtree, self.home, True)
        self.repo = self.home / "run"
        committed_copy(self.repo, _SRC)
        self.places = self.home / "units"

    def real_state(self):
        """本物の index・HEAD・枝（動いていないことを見る）"""
        return (git(self.repo, "rev-parse", "HEAD"), git(self.repo, "symbolic-ref", "-q", "HEAD"),
                git(self.repo, "ls-files", "-s"), git(self.repo, "diff", "--cached", "--name-only"))

    def unit(self, base, name, edits):
        """親の HEAD から組の作業ツリーを切り、edits を書いて、base（親の始めの木）からの差分を返す"""
        path = self.places / name
        git(self.repo, "worktree", "add", "--detach", "-q", str(path), "HEAD")
        for rel, text in edits.items():
            (path / rel).write_text(text, encoding="utf-8")
        return path, groups.diff_since(path, base, groups.end_tree(path))

    def test_two_units_different_files_both_apply(self):
        state = self.real_state()
        base = groups.end_tree(self.repo)
        _, p1 = self.unit(base, "u1", {"a.txt": "a1\nA2\na3\n"})
        _, p2 = self.unit(base, "u2", {"b.txt": "b1\nb2\nB3\n", "new.txt": "new\n"})
        self.assertEqual(unittrees.apply(self.repo, p1), (True, ""))
        self.assertEqual(unittrees.apply(self.repo, p2), (True, ""))
        self.assertEqual((self.repo / "a.txt").read_text(), "a1\nA2\na3\n")
        self.assertEqual((self.repo / "b.txt").read_text(), "b1\nb2\nB3\n")
        self.assertEqual((self.repo / "new.txt").read_text(), "new\n")
        self.assertEqual(self.real_state(), state)

    def test_same_line_second_does_not_apply_and_tree_keeps_first(self):
        state = self.real_state()
        base = groups.end_tree(self.repo)
        _, p1 = self.unit(base, "u1", {"a.txt": "a1\nX\na3\n"})
        _, p2 = self.unit(base, "u2", {"a.txt": "a1\nY\na3\n", "b.txt": "b1\nb2\nB3\n"})
        self.assertEqual(unittrees.apply(self.repo, p1), (True, ""))
        ok, why = unittrees.apply(self.repo, p2)
        self.assertFalse(ok)
        self.assertTrue(why)
        self.assertEqual((self.repo / "a.txt").read_text(), "a1\nX\na3\n")
        self.assertEqual((self.repo / "b.txt").read_text(), "b1\nb2\nb3\n")   # 全部か無し
        self.assertNotIn("<<<<<<<", (self.repo / "a.txt").read_text())
        self.assertEqual(self.real_state(), state)

    def test_same_line_with_marked_leaves_markers_in_the_conflicted_file(self):
        state = self.real_state()
        base = groups.end_tree(self.repo)
        _, p1 = self.unit(base, "u1", {"a.txt": "a1\nX\na3\n"})
        _, p2 = self.unit(base, "u2", {"a.txt": "a1\nY\na3\n", "b.txt": "b1\nb2\nB3\n"})
        self.assertEqual(unittrees.apply(self.repo, p1), (True, ""))
        marked = {}
        self.assertEqual(unittrees.apply(self.repo, p2, marked=marked), (True, ""))
        a = (self.repo / "a.txt").read_text(encoding="utf-8").splitlines()
        for line in ("<<<<<<< 今の作業ツリー", "X", "Y", ">>>>>>> 当てる差分"):
            self.assertIn(line, a)
        self.assertEqual((self.repo / "b.txt").read_text(), "b1\nb2\nB3\n")
        self.assertEqual(marked, {"a.txt": 7})
        self.assertEqual(unittrees.markers_left(self.repo, {**marked, "b.txt": 7, "gone.txt": 7}), ["a.txt"])
        self.assertEqual(self.real_state(), state)

    def test_marked_merges_union_files_and_marks_only_the_rest(self):
        base = groups.end_tree(self.repo)
        _, p1 = self.unit(base, "u1", {"a.txt": "a1\nX\na3\n", "b.txt": "b1\nb2\nb3\nB4\n"})
        _, p2 = self.unit(base, "u2", {"a.txt": "a1\nY\na3\n", "b.txt": "b1\nb2\nb3\nB5\n"})
        self.assertEqual(unittrees.apply(self.repo, p1), (True, ""))
        marked, unioned = {}, []
        self.assertEqual(unittrees.apply(self.repo, p2, union=["b.txt"], unioned=unioned, marked=marked), (True, ""))
        self.assertEqual((marked, unioned), ({"a.txt": 7}, ["b.txt"]))
        self.assertEqual((self.repo / "b.txt").read_text(), "b1\nb2\nb3\nB4\nB5\n")
        self.assertIn("<<<<<<< 今の作業ツリー", (self.repo / "a.txt").read_text(encoding="utf-8").splitlines())
        self.assertEqual(unittrees.markers_left(self.repo, {"a.txt": 7, "b.txt": 7}), ["a.txt"])

    def test_markers_left_sees_every_marker_line(self):
        """パスごとの長さの印の行（区切りを除いた 3 つの印の頭は名つきでも名なしでも、区切りは行全体）が 1 行でも残るファイルを
        数える。長さは marked の値から取り、別の長さの行は数えない"""
        (self.repo / "mid.txt").write_text("a\n||||||| 元\nold\n=======\nY\nb\n", encoding="utf-8")
        (self.repo / "sep.txt").write_text("a\n=======\nb\n", encoding="utf-8")
        (self.repo / "plain.txt").write_text("a\n========\n<<<<<<<<b\n", encoding="utf-8")
        (self.repo / "half.txt").write_text("a\n<<<<<<< 今の作業ツリー\nb\n", encoding="utf-8")
        (self.repo / "bare.txt").write_text("a\n<<<<<<<\nb\n", encoding="utf-8")
        paths = ["mid.txt", "sep.txt", "plain.txt", "half.txt", "bare.txt"]
        self.assertEqual(unittrees.markers_left(self.repo, dict.fromkeys(paths, 7)), ["mid.txt", "sep.txt", "half.txt", "bare.txt"])
        (self.repo / "wide.txt").write_text("a\n========\nb\n", encoding="utf-8")
        (self.repo / "narrow.txt").write_text("a\n=======\n<<<<<<< x\nb\n", encoding="utf-8")
        self.assertEqual(unittrees.markers_left(self.repo, {"wide.txt": 8, "narrow.txt": 8}), ["wide.txt"])

    def test_markers_left_skips_a_lone_separator_line(self):
        """区切りの行を見逃すのは、印の長さと違う長さの = だけの行（setext の下線）だけ。根拠は印の長さの違い"""
        (self.repo / "r.md").write_text("Heading\n=======\ntext\n", encoding="utf-8")
        self.assertEqual(unittrees.markers_left(self.repo, {"r.md": 8}), [])
        self.assertEqual(unittrees.markers_left(self.repo, {"r.md": 7}), ["r.md"])

    def test_markers_left_returns_a_path_without_a_usable_marker_size(self):
        """長さの値が 7 以上の整数でないパス（7 未満・字・無し・bool）は、ファイルの中身を見ずに残りとして返す（通さず拒む）"""
        size = unittrees.DEFAULT_MARKER_SIZE
        for name in ("ok.txt", "short.txt", "text.txt", "none.txt", "flag.txt"):
            (self.repo / name).write_text("a\nb\n", encoding="utf-8")
        got = unittrees.markers_left(self.repo, {"ok.txt": size, "short.txt": size - 1, "text.txt": "8", "none.txt": None,
                                                 "flag.txt": True})
        self.assertEqual(got, ["short.txt", "text.txt", "none.txt", "flag.txt"])

    def marked_md(self, name, seed, edit1, edit2):
        """seed の中身の name を親に commit し、2 つの組が edit1・edit2 に書き換えて、後の組を印つきで当てる。
        (印を書いたパス→印の長さの marked, 印を書いた中身) を返す"""
        self.commit_seed(name, seed)
        base = groups.end_tree(self.repo)
        _, p1 = self.unit(base, f"{name}-1", {name: edit1})
        _, p2 = self.unit(base, f"{name}-2", {name: edit2})
        self.assertEqual(unittrees.apply(self.repo, p1), (True, ""))
        marked = {}
        self.assertEqual(unittrees.apply(self.repo, p2, marked=marked), (True, ""))
        self.assertEqual(list(marked), [name])
        text = (self.repo / name).read_text(encoding="utf-8")
        self.assertIn("<" * marked[name] + " 今の作業ツリー\n", text)
        return marked, text

    def commit_seed(self, name, seed):
        (self.repo / name).write_text(seed, encoding="utf-8")
        git(self.repo, "add", name)
        git(self.repo, "commit", "-q", "-m", name)

    def test_markers_left_tells_the_marker_length_from_an_underline(self):
        """中身に setext の見出し（見出しの次の行が =======）を持つ .md では、印は 8 字で書かれ、7 字の下線と印の区切りを長さで
        見分ける。8 字の区切りを残した合わせは、下線を残しても別の見出しの下線に書き換えても返す。印を全部解いて元の下線だけを
        残した合わせと、7 字の下線つきの見出しを新しく足した合わせは返さない（印と長さが違う）"""
        sep = unittrees.marks(8)[2].decode()
        marked, text = self.marked_md("s.md", "Title\n=======\nbody\n", "Title\n=======\nX\n", "Title\n=======\nY\n")
        self.assertEqual(marked, {"s.md": 8})
        self.assertIn(f"\n{sep}\n", text)
        for merged, left in ((f"Title\n=======\nX\n{sep}\nY\n", ["s.md"]), (f"Title\n-------\nX\n{sep}\nY\n", ["s.md"]),
                             ("Title\n=======\nY\n", []), ("Title\n=======\nX\nSub\n=======\nY\n", [])):
            with self.subTest(merged=merged):
                (self.repo / "s.md").write_text(merged, encoding="utf-8")
                self.assertEqual(unittrees.markers_left(self.repo, marked), left)

    def test_marker_grows_past_a_base_side_separator_and_a_half_merge_is_rejected(self):
        """塊の base の側に 7 字の ======= が入る時、印は 8 字で書かれて base の側の ======= は区切りに読まれない。印の頭の 3 行と
        base の行を消し、8 字の区切りと両側を残した合わせは残りとして返り、base の側の見出しと下線を戻して印を解いた合わせは返らない"""
        heads = unittrees.marks(8)
        sep = heads[2].decode()
        marked, text = self.marked_md("t.md", "Head\n=======\nbody\n", "Head1\n-----\nbody\n", "Head2\n#####\nbody\n")
        self.assertEqual(marked, {"t.md": 8})
        self.assertIn(f"{heads[1].decode()} 元\nHead\n=======\n{sep}\n", text)
        for merged, left in ((f"Head1\n-----\n{sep}\nHead2\n#####\nbody\n", ["t.md"]), ("Head\n=======\nbody\n", [])):
            with self.subTest(merged=merged):
                (self.repo / "t.md").write_text(merged, encoding="utf-8")
                self.assertEqual(unittrees.markers_left(self.repo, marked), left)

    def test_union_refuses_a_base_side_separator_line(self):
        """base の側の行が 7 字の ======= の塊は、行を変えた塊なので挿しだけと読まず合わせない（印は 8 字で読む）"""
        self.commit_seed("a.txt", "x\n=======\ny\n")
        base = groups.end_tree(self.repo)
        _, p1 = self.unit(base, "u1", {"a.txt": "x\nA\ny\n"})
        _, p2 = self.unit(base, "u2", {"a.txt": "x\nB\ny\n"})
        self.assertEqual(unittrees.apply(self.repo, p1), (True, ""))
        got = []
        ok, why = unittrees.apply(self.repo, p2, union=["a.txt"], unioned=got)
        self.assertFalse(ok)
        self.assertTrue(why)
        self.assertEqual((self.repo / "a.txt").read_text(), "x\nA\ny\n")
        self.assertEqual(got, [])

    def test_insert_only_conflict_in_a_union_file_is_merged_in_order(self):
        state = self.real_state()
        base = groups.end_tree(self.repo)
        _, p1 = self.unit(base, "u1", {"a.txt": "a1\na2\na3\n\nclass B:\n    pass\n"})
        _, p2 = self.unit(base, "u2", {"a.txt": "a1\na2\na3\n\nclass C:\n    pass\n", "b.txt": "b1\nb2\nB3\n"})
        self.assertEqual(unittrees.apply(self.repo, p1), (True, ""))
        self.assertFalse(unittrees.apply(self.repo, p2)[0])   # union を渡さなければ今どおり当たらない
        got = []
        self.assertEqual(unittrees.apply(self.repo, p2, union=["a.txt"], unioned=got), (True, ""))
        self.assertEqual((self.repo / "a.txt").read_text(), "a1\na2\na3\n\nclass B:\n    pass\n\nclass C:\n    pass\n")
        self.assertEqual((self.repo / "b.txt").read_text(), "b1\nb2\nB3\n")
        self.assertEqual(got, ["a.txt"])
        self.assertEqual(self.real_state(), state)

    def test_union_refuses_a_conflict_that_changed_lines(self):
        base = groups.end_tree(self.repo)
        _, p1 = self.unit(base, "u1", {"a.txt": "a1\nX\na3\n"})
        _, p2 = self.unit(base, "u2", {"a.txt": "a1\nY\na3\n"})
        self.assertEqual(unittrees.apply(self.repo, p1), (True, ""))
        got = []
        ok, why = unittrees.apply(self.repo, p2, union=["a.txt"], unioned=got)
        self.assertFalse(ok)
        self.assertTrue(why)
        self.assertEqual((self.repo / "a.txt").read_text(), "a1\nX\na3\n")
        self.assertEqual(got, [])

    def test_union_asks_the_check_before_merging(self):
        base = groups.end_tree(self.repo)
        _, p1 = self.unit(base, "u1", {"a.txt": "a1\na2\na3\nB\n"})
        _, p2 = self.unit(base, "u2", {"a.txt": "a1\na2\na3\nC\n"})
        self.assertEqual(unittrees.apply(self.repo, p1), (True, ""))
        seen = []
        ok, _ = unittrees.apply(self.repo, p2, union=["a.txt"], check=lambda path, text: seen.append((path, text)) and False)
        self.assertFalse(ok)
        self.assertEqual(seen, [("a.txt", b"a1\na2\na3\nB\nC\n")])
        self.assertEqual((self.repo / "a.txt").read_text(), "a1\na2\na3\nB\n")

    def test_union_refuses_files_outside_the_list(self):
        base = groups.end_tree(self.repo)
        _, p1 = self.unit(base, "u1", {"a.txt": "a1\na2\na3\nB\n", "b.txt": "b1\nb2\nb3\nB\n"})
        _, p2 = self.unit(base, "u2", {"a.txt": "a1\na2\na3\nC\n", "b.txt": "b1\nb2\nb3\nC\n"})
        self.assertEqual(unittrees.apply(self.repo, p1), (True, ""))
        self.assertFalse(unittrees.apply(self.repo, p2, union=["a.txt"])[0])   # b.txt は並びの外
        self.assertEqual((self.repo / "a.txt").read_text(), "a1\na2\na3\nB\n")

    def test_untracked_and_binary_in_unit_diff(self):
        base = groups.end_tree(self.repo)
        path, _ = self.unit(base, "u1", {"fresh.txt": "unit new\n"})
        (path / "bin.dat").write_bytes(bytes(reversed(range(256))))
        (path / "b.txt").unlink()
        patch = groups.diff_since(path, base, groups.end_tree(path))
        self.assertIn("GIT binary patch", patch)
        self.assertEqual(unittrees.apply(self.repo, patch), (True, ""))
        self.assertEqual((self.repo / "fresh.txt").read_text(), "unit new\n")
        self.assertEqual((self.repo / "bin.dat").read_bytes(), bytes(reversed(range(256))))
        self.assertFalse((self.repo / "b.txt").exists())

    def test_empty_patch_is_ok(self):
        base = groups.end_tree(self.repo)
        path, patch = self.unit(base, "u1", {})
        self.assertEqual(patch, "")
        self.assertEqual(unittrees.apply(self.repo, patch), (True, ""))



class Checks(unittest.TestCase):
    def test_tests_unique_refuses_a_name_defined_twice(self):
        ok = b"class TestA:\n    def test_x(self):\n        pass\n\nclass TestB:\n    def test_x(self):\n        pass\n"
        self.assertTrue(unittrees.tests_unique("tests/test_a.py", ok), "別のクラスの同じ名は隠さない")
        twice = b"def test_x():\n    pass\n\ndef test_x():\n    pass\n"
        self.assertFalse(unittrees.tests_unique("tests/test_a.py", twice))
        cls = b"class TestA:\n    def test_y(self):\n        pass\n\n    def test_y(self):\n        pass\n"
        self.assertFalse(unittrees.tests_unique("tests/test_a.py", cls))
        self.assertFalse(unittrees.tests_unique("tests/test_a.py", b"def test_(:\n"), "読めない中身は合わせない")
        self.assertTrue(unittrees.tests_unique("tests/a.txt", b"x\nx\n"), ".py でなければ照らさない")

    def test_patch_names_are_the_b_side_once(self):
        patch = ("diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n"
                 "diff --git a/d/y.txt b/d/y.txt\nnew file mode 100644\n")
        self.assertEqual(unittrees.patch_names(patch), ["x.py", "d/y.txt"])
        self.assertEqual(unittrees.patch_names(""), [])

    def test_clash_prompt_names_the_marker_sides_by_their_labels(self):
        rules = CLASH_PART.read_text(encoding="utf-8")
        ours, _, theirs = unittrees.MARK_LABELS
        self.assertIn(f"the `{ours}` side of the markers", rules)
        self.assertIn(f"the `{theirs}` side", rules)

    def test_clash_prompt_points_to_the_marker_fields_of_the_brief(self):
        rules = CLASH_PART.read_text(encoding="utf-8")
        self.assertIn("`markers`", rules)
        self.assertIn("{marker_size}", rules)
        self.assertNotIn("`=======`", rules)


if __name__ == "__main__":
    unittest.main()

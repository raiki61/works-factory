"""件数の決まらない一覧を行に切る口（lib/listcut）。先頭 SHOWN 件と『ほか K 件（全件: 置き場）』の行の形（FAST。lib の字を読むだけ）"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import listcut  # noqa: E402


class ListcutCase(unittest.TestCase):
    def test_short_list_is_kept_whole(self):
        """件数が SHOWN 以下の一覧は全件を prefix つきで返し、残りの行を足さない"""
        self.assertEqual(listcut.lines(["a", "b", "c"]), ["  - a", "  - b", "  - c"])
        self.assertEqual(listcut.lines(["a", "b"], prefix="* "), ["* a", "* b"])
        edge = [f"p{i}" for i in range(listcut.SHOWN)]
        self.assertEqual(listcut.lines(edge, where="x/fix-removed.json"), [f"  - {x}" for x in edge])
        self.assertEqual(listcut.lines([]), [])

    def test_long_list_keeps_head_rest_and_where(self):
        """件数が SHOWN を超える一覧は先頭 SHOWN 件と『ほか K 件（全件: <where>）』の 1 行だけを返す"""
        items = [f"cache/a/{i}.bin" for i in range(20000)]
        got = listcut.lines(items, where="out/fix-removed.json")
        self.assertEqual(len(got), listcut.SHOWN + 1)
        self.assertEqual(got[:listcut.SHOWN], [f"  - {x}" for x in items[:listcut.SHOWN]])
        self.assertEqual(got[-1], "  - " + listcut.REST.format(n=20000 - listcut.SHOWN) + "（全件: out/fix-removed.json）")
        self.assertIn(str(20000 - listcut.SHOWN), got[-1])
        small = listcut.lines(list("abcdef"), shown=2, prefix="    - ")
        self.assertEqual(small, ["    - a", "    - b", "    - " + listcut.REST.format(n=4)])

    def test_rest_row_names_its_list(self):
        """name を渡すと残りの行が一覧の名と欄の名で始まり、同じ置き場を指す 2 本の一覧の残りが読み分けられる。全件を返す時は name を使わない"""
        many = [str(i) for i in range(listcut.SHOWN + 3)]
        a = listcut.lines(many, name="増え（after.fence_up）", where="b/structure-after.json")[-1]
        b = listcut.lines(many, name="新しい名（after.new_names）", where="b/structure-after.json")[-1]
        self.assertEqual(a, "  - 増え（after.fence_up）の" + listcut.REST.format(n=3) + "（全件: b/structure-after.json）")
        self.assertNotEqual(a, b)
        self.assertEqual(listcut.lines(["x"], name="増え（after.fence_up）"), ["  - x"])


class CapBytesCase(unittest.TestCase):
    """役に貼る本文をバイトで切る口（前は graphloops/engine/render.py。integration.md 4.3-6）"""

    def test_cuts_at_bytes_and_names_the_cut(self):
        cut = []
        self.assertEqual(listcut.cap_bytes("あい", "x", cut, cap=6), "あい")
        self.assertEqual(cut, [])
        got = listcut.cap_bytes("あいう", "x", cut, cap=6)
        self.assertTrue(got.startswith("あい\n\n［"), got)
        self.assertEqual(cut, ["x: 9 バイトを 6 バイトで切った"])
        self.assertEqual(listcut.cap_bytes("あいう", "x", [], cap=None), "あいう")
        self.assertEqual(listcut.FILE_CAP, 40000)


if __name__ == "__main__":
    unittest.main()

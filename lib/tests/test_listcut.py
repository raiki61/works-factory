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


if __name__ == "__main__":
    unittest.main()

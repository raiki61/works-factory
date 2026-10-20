"""地図の探し方（.shared/core/concepthome.py。計画 2026-10-09-clean-whole の Task 2.1）。
名前の一覧だけを見る"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import concepthome as ch  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()

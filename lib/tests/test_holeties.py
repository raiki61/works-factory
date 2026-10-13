"""差分の審査の穴に枝の名札を付ける（線の木の段 4a。設計 docs/plans/2026-10-07-hole-to-branch.md の 2.2・2.3）。

holeties の純粋な関数（tie・groups・spread・earlier・lines）を見本の入力で、refix.hole_ties を偽の盤面（state・dir・work と
output_of_round だけ。盤面を開かない）で直に呼ぶ（FAST。git・子のプロセスなし）"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import holeties  # noqa: E402

U1 = "works/a.py+f: 一つ目"
U2 = "works/b.py+g: 二つ目"
U3 = "works/c.py+h: 三つ目"
LOOSE = "works/d.py+k: どの項目にも無い単位"
ITEMS = [
    {"item": 1, "unit_keys": [U1], "allowed_paths": ["works/a.py", "works/lib/*.py"],
     "tests": [{"id": "works/tests/test_a.py::ACase::test_x"}], "rewrite_tests": []},
    {"item": 2, "unit_keys": [U2], "allowed_paths": ["works/b.py", "works/lib/*.py"], "tests": [], "rewrite_tests": []},
    {"item": 3, "unit_keys": [U3], "allowed_paths": ["works/c.py"], "tests": [], "rewrite_tests": [], "held": "ask_human の裁定 c1"},
]


def hole(key, where="", check=False):
    return {"key": key, "from": "p3.delta_review.checks" if check else "p3.delta_review", "where": where, "check": check}


def by_key(ties):
    return {t["key"]: t for t in ties}


class TieCase(unittest.TestCase):
    def test_compliance_row_names_item(self):
        """準拠の落ちた行の face_key が穴の key なら、その行の項目に結ぶ（場所が無くても）"""
        got = by_key(holeties.tie([hole("missing-thing-in-a")], ITEMS,
                                  compliance=[{"item": 2, "kind": "missing", "face_key": "missing-thing-in-a", "why": "x" * 20}]))
        self.assertEqual(got["missing-thing-in-a"]["branches"], ["item:2"])
        self.assertIn("compliance", got["missing-thing-in-a"]["via"])

    def test_check_follows_plan_face_units(self):
        """塞がっていない検算は、事前審査の穴の unit_keys を持つ項目に結ぶ"""
        got = by_key(holeties.tie([hole("plan-face-one", check=True)], ITEMS,
                                  plan_faces=[{"key": "plan-face-one", "unit_keys": [U1]}]))
        self.assertEqual(got["plan-face-one"]["branches"], ["item:1"])
        self.assertEqual(got["plan-face-one"]["via"], ["check"])

    def test_where_in_allowed_paths(self):
        """where が項目の allowed_paths の glob か受け入れのテストのファイルに当たれば、その項目"""
        got = by_key(holeties.tie([hole("hole-in-a-file", "works/a.py"), hole("hole-in-test", "works/tests/test_a.py")], ITEMS))
        self.assertEqual(got["hole-in-a-file"]["branches"], ["item:1"])
        self.assertEqual(got["hole-in-test"]["branches"], ["item:1"])
        self.assertIn("path", got["hole-in-a-file"]["via"])

    def test_shared_glob_is_two_branches(self):
        """2 つの項目の glob に当たる where は枝 2 つ（相乗りの組へ行く）"""
        got = by_key(holeties.tie([hole("hole-in-shared-lib", "works/lib/x.py")], ITEMS))
        self.assertEqual(got["hole-in-shared-lib"]["branches"], ["item:1", "item:2"])

    def test_change_of_unit_outside_items(self):
        """修正の changes で where を変えた単位がどの項目にも無ければ、その単位の枝"""
        got = by_key(holeties.tie([hole("hole-in-d-file", "works/d.py")], ITEMS,
                                  changes=[{"unit_key": LOOSE, "files": ["works/d.py"]}]))
        self.assertEqual(got["hole-in-d-file"]["branches"], [f"unit:{LOOSE}"])
        self.assertIn("change", got["hole-in-d-file"]["via"])

    def test_change_of_unit_in_item(self):
        """changes の単位が項目に在れば、その項目（範囲の外のファイルでも）"""
        got = by_key(holeties.tie([hole("hole-in-other-file", "works/zzz.py")], ITEMS,
                                  changes=[{"unit_key": U2, "files": ["works/zzz.py"]}]))
        self.assertEqual(got["hole-in-other-file"]["branches"], ["item:2"])

    def test_unit_key_path(self):
        """単位の key の頭のパスが where と同じなら、その単位の項目（範囲も changes も無い時の手）"""
        items = [{"item": 1, "unit_keys": ["works/x.py: 何か"]}]
        got = by_key(holeties.tie([hole("hole-in-x-file", "works/x.py")], items))
        self.assertEqual(got["hole-in-x-file"]["branches"], ["item:1"])
        self.assertEqual(got["hole-in-x-file"]["via"], ["unit"])

    def test_nothing_matches(self):
        got = by_key(holeties.tie([hole("hole-nowhere", "works/zzz.py")], ITEMS))
        self.assertEqual(got["hole-nowhere"]["branches"], [])
        self.assertEqual(got["hole-nowhere"]["via"], [])

    def test_held_only(self):
        """裁定で外れた項目にだけ結ばれた穴は held に理由を持つ。外れていない項目にも結ばれれば held は空"""
        got = by_key(holeties.tie([hole("hole-in-c-file", "works/c.py"), hole("hole-in-a-file", "works/a.py")], ITEMS))
        self.assertEqual(got["hole-in-c-file"]["branches"], ["item:3"])
        self.assertEqual(got["hole-in-c-file"]["held"], "ask_human の裁定 c1")
        self.assertEqual(got["hole-in-a-file"]["held"], "")

    def test_order_kept(self):
        keys = ["hole-b-first", "hole-a-second"]
        got = holeties.tie([hole(keys[0], "works/b.py"), hole(keys[1], "works/a.py")], ITEMS)
        self.assertEqual([t["key"] for t in got], keys)

    def test_earlier_for_second_pass(self):
        """2 回目: 検算の key は 1 回目にその key に結んだ枝、where は 1 回目の手直しがそのファイルを変えた穴の枝"""
        first = holeties.tie([hole("first-hole-in-a", "works/a.py"), hole("first-hole-in-b", "works/b.py")], ITEMS)
        handled = [{"key": "first-hole-in-a", "handled": "fixed", "how": "x" * 20, "files": ["works/zzz.py"]},
                   {"key": "first-hole-in-b", "handled": "declared", "how": "y" * 20}]
        earlier = holeties.earlier(first, handled)
        got = by_key(holeties.tie([hole("first-hole-in-a", check=True), hole("second-hole-in-zzz", "works/zzz.py")],
                                  ITEMS, earlier=earlier))
        self.assertEqual(got["first-hole-in-a"]["branches"], ["item:1"])
        self.assertEqual(got["second-hole-in-zzz"]["branches"], ["item:1"])
        self.assertEqual(got["second-hole-in-zzz"]["via"], ["earlier"])


class GroupCase(unittest.TestCase):
    def setUp(self):
        self.ties = holeties.tie([hole("hole-a-one", "works/a.py"), hole("hole-a-two", "works/a.py"),
                                  hole("hole-shared", "works/lib/x.py"), hole("hole-nowhere", "works/zzz.py"),
                                  hole("hole-held", "works/c.py")], ITEMS)

    def test_groups(self):
        got = holeties.groups(self.ties)
        self.assertEqual(got["lanes"], {"item:1": ["hole-a-one", "hole-a-two"]})
        self.assertEqual(got["synergy"], ["hole-shared", "hole-nowhere", "hole-held"])

    def test_spread(self):
        got = holeties.spread(self.ties)
        self.assertEqual(got, {"holes": 5, "single": 2, "multi": 1, "none": 1, "held": 1, "groups": 2,
                               "branches": {"item:1": 2}})

    def test_spread_empty(self):
        self.assertEqual(holeties.spread([])["groups"], 0)

    def test_lines(self):
        text = "\n".join(holeties.lines(self.ties))
        self.assertIn("hole-a-one: 項目 1", text)
        self.assertIn("hole-shared: 項目 1・項目 2（2 つ以上の枝にまたがる）", text)
        self.assertIn("hole-nowhere: どの枝にも結べない", text)
        self.assertIn("hole-held: 項目 3（裁定で外れた項目だけ: ask_human の裁定 c1）", text)

    def test_note_of_unit(self):
        t = holeties.tie([hole("hole-in-d-file", "works/d.py")], ITEMS, changes=[{"unit_key": LOOSE, "files": ["works/d.py"]}])
        self.assertEqual(holeties.note(t[0]), f"単位 {LOOSE}")


class PathCase(unittest.TestCase):
    def test_unit_path(self):
        self.assertEqual(holeties.unit_path("works/a.py+f: 一言"), "works/a.py")
        self.assertEqual(holeties.unit_path("works/a.py: 一言"), "works/a.py")
        self.assertEqual(holeties.unit_path("名だけ: 一言"), "")


if __name__ == "__main__":
    unittest.main()

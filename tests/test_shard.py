"""CI の試験の分け（tests/shard.py）の試験。

- (a) 全部のモジュールがちょうど 1 つの分けに入る（漏れも重なりも 0）
- (b) 秒数の表に無いモジュールも入る
- (c) 分けの秒数の最大と最小の差が、表の 1 モジュールの最大より小さい
- (d) 新しい試験のファイルを足すと、どれかの分けに入る
"""
import json
import pathlib
import tempfile
import unittest

from tests import shard

ROOT = pathlib.Path(__file__).resolve().parents[1]
N = 4


class RealTreeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = shard.modules(ROOT)
        cls.seconds = shard.load_seconds(shard.TABLE)
        cls.shards = shard.plan(cls.modules, cls.seconds, N)

    def test_every_module_in_exactly_one_shard(self):
        placed = [m for s in self.shards for m in s]
        self.assertEqual(sorted(placed), sorted(self.modules))
        self.assertEqual(len(placed), len(set(placed)))
        shard.check(self.modules, self.shards)

    def test_shards_balanced_within_largest_module(self):
        totals = [shard.total(s, self.seconds) for s in self.shards]
        self.assertLess(max(totals) - min(totals), max(self.seconds.values()), totals)


class PlanTest(unittest.TestCase):
    def test_module_missing_from_table_is_placed(self):
        shards = shard.plan(["a.test_a", "b.test_b", "c.test_new"], {"a.test_a": 3.0, "b.test_b": 1.0}, 2)
        self.assertIn("c.test_new", [m for s in shards for m in s])

    def test_missing_module_counts_as_table_median(self):
        seconds = {"a": 1.0, "b": 5.0, "c": 9.0}
        self.assertEqual(shard.total(["new"], seconds), 5.0)

    def test_check_catches_left_out_and_doubled(self):
        with self.assertRaises(SystemExit):
            shard.check(["a", "b"], [["a"], []])
        with self.assertRaises(SystemExit):
            shard.check(["a", "b"], [["a", "b"], ["b"]])

    def test_merge_joins_shard_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            one, two = pathlib.Path(tmp, "1.json"), pathlib.Path(tmp, "2.json")
            one.write_text(json.dumps({"a": 1.26}), encoding="utf-8")
            two.write_text(json.dumps({"b": 2.0}), encoding="utf-8")
            self.assertEqual(shard.merge([one, two]), {"a": 1.3, "b": 2.0})


TEST_CASE = "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n"


class NewFileTest(unittest.TestCase):
    def test_new_test_file_lands_in_a_shard(self):
        pkg = "shard_newfile_pkg"   # discover が import するので、他の試験のモジュール名と重ならない名にする
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / pkg / "deep").mkdir(parents=True)
            (root / "loose").mkdir()
            for path in [f"{pkg}/__init__.py", f"{pkg}/deep/__init__.py", f"{pkg}/helper.py"]:
                (root / path).write_text("", encoding="utf-8")
            for path in [f"{pkg}/test_old.py", "loose/test_hidden.py"]:
                (root / path).write_text(TEST_CASE, encoding="utf-8")
            self.assertEqual(shard.modules(root), [f"{pkg}.test_old"])
            (root / pkg / "deep" / "test_new.py").write_text(TEST_CASE, encoding="utf-8")
            shards = shard.plan(shard.modules(root), {f"{pkg}.test_old": 4.0}, N)
            self.assertIn(f"{pkg}.deep.test_new", [m for s in shards for m in s])


if __name__ == "__main__":
    unittest.main()

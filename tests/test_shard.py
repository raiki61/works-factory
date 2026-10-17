"""CI の試験の分け（tests/shard.py）の試験。

- (a) 全部のモジュールがちょうど 1 つの分けに入る（漏れも重なりも 0）
- (b) 秒数の表に無いモジュールも入る
- (c) 分けの秒数の最大と最小の差が、表の 1 モジュールの最大より小さい
- (d) 新しい試験のファイルを足すと、どれかの分けに入る
- (e) --paths の選び（pick）は、名指しのファイルと、名指しのフォルダの下のモジュールだけを取る。何も取らなければ全部に広げず赤（終了の値 5）
- (f) 並べる子の数は CPU の数を SHARING で割った数（1 以上）で、環境変数 WORKERS_ENV が上書きする
"""
import contextlib
import io
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

from tests import shard
from tests.bin import hermetic

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


class PickTest(unittest.TestCase):
    NAMES = ["lib.tests.test_alpha", "lib.tests.test_beta", "tests.layers.test_x"]

    def test_exact_file_path(self):
        self.assertEqual(shard.pick(self.NAMES, ["lib/tests/test_beta.py"]), ["lib.tests.test_beta"])

    def test_directory_with_or_without_slash(self):
        both = ["lib.tests.test_alpha", "lib.tests.test_beta"]
        self.assertEqual(shard.pick(self.NAMES, ["lib/tests"]), both)
        self.assertEqual(shard.pick(self.NAMES, ["lib/tests/"]), both)

    def test_directory_prefix_stops_at_a_slash(self):
        self.assertEqual(shard.pick(self.NAMES, ["tests/lay"]), [])

    def test_path_that_is_not_a_test_module_picks_nothing(self):
        self.assertEqual(shard.pick(self.NAMES, ["lib/alpha.py"]), [])

    def test_package_that_fails_to_import_is_picked_by_a_path_under_it(self):
        names = [*self.NAMES, "tests.e2e"]
        self.assertEqual(shard.pick(names, ["tests/e2e/test_x.py"]), ["tests.e2e"])
        self.assertEqual(shard.pick(names, ["tests/e2e/__init__.py"]), ["tests.e2e"])
        self.assertEqual(shard.pick(names, ["tests/e2e"]), ["tests.e2e"])
        self.assertEqual(shard.pick(names, ["tests/e2ex/test_x.py"]), [])


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


FAILING_CASE = "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_fail(self):\n        self.fail()\n"


def tree(root: pathlib.Path, pkg: str, files: dict[str, str]) -> None:
    (root / pkg).mkdir()
    (root / pkg / "__init__.py").write_text("", encoding="utf-8")
    for name, body in files.items():
        (root / pkg / name).write_text(body, encoding="utf-8")


def run_quietly(suites: dict, record: pathlib.Path | None = None) -> int:
    with contextlib.redirect_stderr(io.StringIO()):
        return shard.run(suites, record, 2)


class SameAsDiscoverTest(unittest.TestCase):
    # discover が import するので、パッケージの名は他の試験のモジュール名と重ならない名にする

    def test_reexported_case_runs_under_each_importing_module(self):
        pkg = "shard_reexport_pkg"
        reexport = f"from {pkg}.base import Base\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            tree(root, pkg, {"base.py": TEST_CASE.replace("class T", "class Base"), "test_one.py": reexport, "test_two.py": reexport})
            found = shard.suites(root)
            self.assertEqual(sorted(found), [f"{pkg}.test_one", f"{pkg}.test_two"])
            self.assertEqual(sum(s.countTestCases() for s in found.values()), 2)

    def test_module_level_skip_is_a_skip(self):
        pkg = "shard_skip_pkg"
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            tree(root, pkg, {"test_skip.py": "import unittest\nraise unittest.SkipTest('no')\n"})
            found = shard.suites(root)
            self.assertEqual(sorted(found), [f"{pkg}.test_skip"])
            self.assertEqual(run_quietly(found), 0)

    def test_broken_module_is_placed_and_red_without_stopping_the_rest(self):
        pkg = "shard_broken_pkg"
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            tree(root, pkg, {"test_import.py": "import shard_no_such_module_zz\n", "test_syntax.py": "x = (\n", "test_ok.py": TEST_CASE})
            found = shard.suites(root)
            self.assertEqual(sorted(found), [f"{pkg}.test_import", f"{pkg}.test_ok", f"{pkg}.test_syntax"])
            record = root / "seconds.json"
            self.assertEqual(run_quietly(found, record), 1)
            self.assertEqual(sorted(json.loads(record.read_text(encoding="utf-8"))), sorted(found))


class RunExitTest(unittest.TestCase):
    def test_exit_status(self):
        pkg = "shard_exit_pkg"
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            tree(root, pkg, {"test_ok.py": TEST_CASE, "test_fail.py": FAILING_CASE})
            found = shard.suites(root)
            self.assertEqual(run_quietly({f"{pkg}.test_ok": found[f"{pkg}.test_ok"]}), 0)
            self.assertEqual(run_quietly({f"{pkg}.test_fail": found[f"{pkg}.test_fail"]}), 1)
            self.assertEqual(run_quietly({}), 5)

    def test_paths_that_pick_nothing_are_red_not_everything(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), mock.patch.dict(os.environ):
            self.assertEqual(shard.main(["--paths", "no/such/dir"]), 5)


class WorkersTest(unittest.TestCase):
    def test_default_divides_the_cpus_among_the_runs_sharing_the_machine(self):
        with mock.patch.dict(os.environ), mock.patch("os.cpu_count", return_value=24):
            os.environ.pop(shard.WORKERS_ENV, None)
            self.assertEqual(shard.workers(), 24 // shard.SHARING)
        with mock.patch.dict(os.environ), mock.patch("os.cpu_count", return_value=4):
            os.environ.pop(shard.WORKERS_ENV, None)
            self.assertEqual(shard.workers(), 1)

    def test_the_environment_overrides_the_default(self):
        with mock.patch.dict(os.environ, {shard.WORKERS_ENV: "7"}):
            self.assertEqual(shard.workers(), 7)
        for value in ("0", "x", "-2", ""):
            with self.subTest(value=value), mock.patch.dict(os.environ, {shard.WORKERS_ENV: value}):
                with self.assertRaises(SystemExit):
                    shard.workers()


class ScrubTest(unittest.TestCase):
    def test_the_run_drops_the_parents_names_before_the_tests_read_them(self):
        """工場の中の run が立てる名は、試験の過程の既定の環境にも残らない。Archon の源の置き場と見送りを赤にする旗は残る"""
        parent = {"WORKS_ANSWER_CMD": "sh respond", "CLAUDE_CONFIG_DIR": "/parent/config", "INPUTS_REPLY": "{}",
                  hermetic.ARCHON_CACHE_ENV: "/cache", hermetic.ARCHON_REQUIRED_ENV: "1"}
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), \
                mock.patch.dict(os.environ, parent), mock.patch.dict(hermetic._SCRUBBED):
            shard.main(["--paths", "no/such/dir"])
            left = {k: os.environ.get(k) for k in parent}
            named = hermetic.inherited("CLAUDE_CONFIG_DIR", "WORKS_ANSWER_CMD", hermetic.ARCHON_CACHE_ENV)
        self.assertEqual(left, {"WORKS_ANSWER_CMD": None, "CLAUDE_CONFIG_DIR": None, "INPUTS_REPLY": None,
                                hermetic.ARCHON_CACHE_ENV: "/cache", hermetic.ARCHON_REQUIRED_ENV: "1"})
        self.assertEqual(named, {"CLAUDE_CONFIG_DIR": "/parent/config", "WORKS_ANSWER_CMD": "sh respond",
                                 hermetic.ARCHON_CACHE_ENV: "/cache"})

    def test_a_real_run_still_sees_its_flag_and_auth_by_name(self):
        """本物の役で回す試験の旗と認証は、過程の環境から外れても、その試験が名指しで引ける（子の環境には入らない）"""
        parent = {"WORKS_FACTORY_REAL_RUN": "1", "ANTHROPIC_API_KEY": "key"}
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), \
                mock.patch.dict(os.environ, parent), mock.patch.dict(hermetic._SCRUBBED):
            shard.main(["--paths", "no/such/dir"])
            self.assertEqual(hermetic.inherited("WORKS_FACTORY_REAL_RUN", "ANTHROPIC_"), parent)
            self.assertFalse(set(parent) & set(hermetic.child_env()))


if __name__ == "__main__":
    unittest.main()

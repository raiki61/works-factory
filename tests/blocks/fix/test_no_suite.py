"""止めの語 no-suite（docs/plans/2026-10-24-fix-weapons.md の 3.9 と 4.4 の作る物 6）の試験。

試験の実行器が無いか走らない組で、計画の語が static でない単位が在れば、確かめていない直しを書き進めずに組を止め、組の形の出口が
stopby.NO_SUITE を名乗る。止める所は 3 つ: 組の頭（orders.no_suite_why。実行器が無く元の結末が取れない）・TDD のループ（実行器が
結末を返さない。tdd._abort の段 runner）・受け付け（board.no_suite_at_accept。実行器が結末を返さないか、試験の無い対象で工場の書いた
実行器が 0 件を返す）。static だけの組は止めない。下ごしらえ（pin）の設定のファイルの例外は、起点の版に無い物だけを通す（9.1 の 13）。
報告の冒頭の句（line の facts.suite_broken_notes）は tests/blocks/line/test_head_plain.py。
"""
import json
import pathlib
import sys
import tempfile
import unittest
import unittest.mock

from tests.bin.gitkit import git
from tests.blocks import kit
from tests.blocks.fix import test_group as tg
from tests.blocks.fix.support import SUITE

ROOT = kit.ROOT
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))

import stopby  # noqa: E402

orders = kit.load("fix", "orders")
from src import basecase, board, duties, pin  # noqa: E402  （kit.load が fix の src を sys.path に入れる）

# 対象のどれかの .py に NOXML の字が在れば JUnit XML を書かずに落ちる実行器（ほかは SUITE と同じ）。組の頭の元の結末は取れ、
# 後の回で実行器が結末を返さない形を作る
MARKED = ('import pathlib, sys\n'
          'if any("NOXML" in p.read_text(encoding="utf-8") for p in pathlib.Path(".").glob("*.py")):\n'
          '    sys.exit(1)\n') + SUITE


class NoSuiteGroupCase(tg.GroupChildScriptsCase):
    """組の子の scripts の道具立て（tg.GroupChildScriptsCase）を借りる。借りた元の試験は load_tests で外す"""

    def setUp(self):
        super().setUp()
        self.marked = self.tmp / "marked.py"
        self.marked.write_text(MARKED, encoding="utf-8")

    def result(self) -> dict:
        return json.loads(pathlib.Path(self.run_script("group_end")["result_file"]).read_text(encoding="utf-8"))

    def assert_stopped(self, phrase: str):
        """組の結果の tdd に no_suite が載り、組の形の出口が stopby.NO_SUITE を名乗って訳に phrase を言う"""
        tdd = self.result()["tdd"]
        self.assertIs(tdd.get("no_suite"), True, tdd)
        out = self.run_script("finish")
        self.assertEqual((out["ok"], out["stop_reason"]), (False, stopby.NO_SUITE), out)
        self.assertIn(phrase, out["reason"])
        self.assertIs(next(r for r in out["tdd"] if r["group_id"] == "g1")["no_suite"], True)

    def test_a_group_without_a_runner_stops_at_its_head(self):
        """実行器の無い組（元の結末が取れない）で計画の語の無い単位が在れば、組の頭が止め、振り分け・注文・修正役の輪を回さない"""
        self.intake()
        self.assertIs(self.run_script("group_start")["no_suite"], True)
        self.assertEqual(self.run_script("route_go"), {"route": False, "stop": True})
        got = self.run_script("orders")
        self.assertEqual((got["tdd"], got["writer"], got["stop"]), (False, False, True), got)
        self.assertIn(tg.MEAN, got["reason"])
        self.assertFalse(self.run_script("fix_prep")["go"], "修正役を起こさない")
        self.assert_stopped("計画の語が static でない単位")

    def test_a_group_with_a_runner_is_not_stopped_at_its_head(self):
        self.parent_inputs(str(self.suite))
        self.intake()
        self.assertIs(self.run_script("group_start")["no_suite"], False)
        self.assertEqual(self.run_script("route_go"), {"route": True, "stop": False})

    def test_a_static_only_group_is_not_stopped(self):
        """計画の語が全部 static の組は、実行器が無くても組の頭で止めない（static は試験を求めない型）"""
        self.intake()
        with unittest.mock.patch.object(orders.route, "plan_words", return_value={tg.MEAN: "static"}):
            self.assertEqual(orders.no_suite_why(self.place), "")
        with unittest.mock.patch.object(orders.route, "plan_words", return_value={tg.MEAN: "tidy"}):
            self.assertIn(tg.MEAN, orders.no_suite_why(self.place), "static でない計画の語は止める")

    def test_a_runner_that_gives_no_result_in_the_tdd_loop_stops_the_group(self):
        """TDD のループで実行器が結末を返さなければ（段 runner）、修正役の輪を起こさずに組を止める"""
        self.parent_inputs(str(self.marked))
        self.start()
        self.assertEqual(self.step({"phase": "route", "units": [{"unit_key": tg.MEAN, "route": "tdd"}]})["phase"], "test")
        test_file = self.repo / "test_stats.py"
        test_file.write_text(test_file.read_text(encoding="utf-8").replace("\n\nif __name__", tg.NEW_TEST + "    # NOXML\n\nif __name__"),
                             encoding="utf-8")
        self.step({"phase": "test", "unit_key": tg.MEAN, "test_files": ["test_stats.py"],
                   "tests": ["test_stats.py::TestStats::test_mean_of_two"]})
        self.assertTrue(board.no_suite_stop(self.place), "輪の状態に no_suite の印")
        self.assertFalse(self.run_script("fix_prep")["go"], "修正役を起こさない")
        self.assert_stopped("実行器")

    def test_a_runner_that_gives_no_result_at_the_accept_stops_the_group(self):
        """受け付けで変更に当たる試験を走らせて実行器が結末を返さなければ、拒否で出し直させずに組を止める"""
        self.parent_inputs(str(self.marked))
        self.start()
        self.step({"phase": "route", "units": [{"unit_key": tg.MEAN, "route": "direct"}]})
        self.assertTrue(self.run_script("fix_prep")["go"])
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)") + "# NOXML\n", encoding="utf-8")
        out = self.accept({"changes": [tg._change(tg.MEAN, ["stats.py"])]})
        self.assertEqual((out["ok"], out["done"]), (False, True), out)
        self.assertIn("実行器が結末を返さない", out["reason"])
        self.assertFalse(self.run_script("fix_prep")["go"], "止めた後に修正役を起こし直さない")
        self.assert_stopped("実行器が結末を返さない")


class AcceptStopCase(unittest.TestCase):
    """受け付けの止め board.no_suite_at_accept の yes/no（seen は common.selected_problems が走らせた回の {cases, why, log}）"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.place = pathlib.Path(tmp.name)
        self.seen = {"cases": [], "why": [], "log": "/p/suite-accept.log"}

    def based(self, **doc):
        board.write_json(basecase.path(self.place), {"taken": True, "no_tests": True, "suite_by_factory": True, **doc})

    def test_nothing_run_does_not_stop(self):
        self.based()
        self.assertEqual(board.no_suite_at_accept(self.place, {}), "")

    def test_no_result_stops(self):
        got = board.no_suite_at_accept(self.place, {"cases": None, "why": ["XML が無い"], "log": "/p/suite-accept.log"})
        self.assertIn("XML が無い", got)
        self.assertIn("/p/suite-accept.log", got)

    def test_zero_cases_from_a_factory_runner_on_a_target_without_tests_stops(self):
        self.based()
        got = board.no_suite_at_accept(self.place, self.seen)
        self.assertIn("一覧が 0 件", got)
        self.assertIn("/p/suite-accept.log", got)

    def test_zero_cases_does_not_stop_when_tests_exist_or_the_runner_was_given_or_cases_ran(self):
        for doc, seen in (({"no_tests": False, "test_list": {"status": basecase.LISTED}}, self.seen),
                          ({"suite_by_factory": False}, self.seen),
                          ({}, {**self.seen, "cases": [{"id": "t", "status": "passed"}]})):
            with self.subTest(doc=doc):
                self.based(**doc)
                self.assertEqual(board.no_suite_at_accept(self.place, seen), "")

    def test_an_undecided_list_names_the_hint_and_the_kept_config(self):
        """一覧が試験の有無を決められない時は一覧の訳と宣言の案内を、下ごしらえが起点の版に在る設定のファイルで拒まれていたらそのパスを言う"""
        import rolekit
        from graphloops.engine import declared
        self.based(no_tests=False, test_list={"status": basecase.ABSENT, "why": "list の鍵が無い"})
        reason = f"受け付けが拒んだ\n  - setup.cfg: {pin.KEPT_CONFIG}\n  - stats.py: ほかの拒否"
        rolekit.rejects_path(self.place, "fix-accept").write_text(json.dumps([{"at": 1, "reason": reason}]), encoding="utf-8")
        got = board.no_suite_at_accept(self.place, self.seen)
        self.assertIn("一覧で決まらない", got)
        self.assertIn("list の鍵が無い", got)
        self.assertIn(declared.LIST_HINT, got)
        self.assertIn(board.NO_SUITE_CONFIG.format(paths="setup.cfg"), got)


class PinConfigCase(unittest.TestCase):
    """下ごしらえの設定のファイルの例外を事実（duties.unit_facts の absent_at_base。起点の版 rev は run の直す前の版）から引く"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        for name, text in {"stats.py": "X = 1\n", "setup.cfg": "[x]\n", ".review-checks.json": "{}\n"}.items():
            (self.repo / name).write_text(text, encoding="utf-8")
        self.commit("seed")
        self.rev = git(self.repo, "rev-parse", "HEAD").strip()
        (self.repo / "test_stats.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
        self.place = pathlib.Path(tmp.name) / "place"
        self.place.mkdir()

    def commit(self, msg):
        git(self.repo, "add", "-A")
        git(self.repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", msg)

    def problems(self, files):
        f = duties.unit_facts(self.place, self.repo, self.rev, "u", "pin", [{"unit_key": "u", "files": ["test_stats.py", *files]}],
                              order={}, base={"no_tests": True}, cases=None)
        return pin.tests_only(f)

    def test_a_new_config_passes(self):
        (self.repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        self.assertEqual(self.problems(["pytest.ini"]), [])

    def test_a_config_made_earlier_in_the_same_run_passes(self):
        """起点の版は run の直す前の版なので、同じ run の前の段が作って commit した設定のファイルも起点の版に無い物として通す"""
        (self.repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        self.commit("前の段")
        (self.repo / "pytest.ini").write_text("[pytest]\naddopts = -q\n", encoding="utf-8")
        self.assertEqual(self.problems(["pytest.ini"]), [])

    def test_rewriting_or_deleting_a_config_at_the_base_is_rejected(self):
        (self.repo / "setup.cfg").write_text("[x]\ny = 1\n", encoding="utf-8")
        (self.repo / ".review-checks.json").unlink()
        got = self.problems(["setup.cfg", ".review-checks.json"])
        self.assertEqual(got, [f"setup.cfg: {pin.KEPT_CONFIG}", f".review-checks.json: {pin.KEPT_CONFIG}"])


def load_tests(loader, tests, pattern):
    """借りた tg.GroupChildScriptsCase の試験を回し直さない（このファイルに書いた試験だけ）"""
    suite = unittest.TestSuite(NoSuiteGroupCase(name) for name in loader.getTestCaseNames(NoSuiteGroupCase)
                               if name in NoSuiteGroupCase.__dict__)
    for case in (AcceptStopCase, PinConfigCase):
        suite.addTests(loader.loadTestsFromTestCase(case))
    return suite


if __name__ == "__main__":
    unittest.main()

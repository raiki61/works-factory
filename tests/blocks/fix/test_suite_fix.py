"""修正の block の起動スクリプトの書き直し（docs/design/fix.md の 19 節。#836・持ち主の決め base-runs-nothing）の試験。

工場の書いた実行器（values の suite_made）が、TDD の輪の頭で関わる試験を中身に届く前に落とし（JUnit の error）、test_cmd の単体は通る時、
group-start が壊れと見て取り置きから捨て、suite-fix-prep・suite-fix（書き手。試験は返りを差し替える）・suite-fix-try が 1 回だけ書き直させて
輪の頭をやり直す。直れば輪が続き、直した実行器を取り置く。直らなければ組を止め、組の形の出口が stopby.SUITE_BROKEN を名乗る。
人が渡した実行器と、test_cmd も赤の時は止めない。
"""
import hashlib
import json
import pathlib
import sys
import unittest

from bin._lib import launcher
from tests.blocks import kit
from tests.blocks.fix import test_group as tg

ROOT = kit.ROOT
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))

import stopby  # noqa: E402

# 関わる試験を、試験の中身に届く前の読み込みの誤り（JUnit の error）で落とす壊れた起動スクリプト（run 96f35545 の形）
BROKEN = ("#!/bin/sh\nprintf '%s' \"<testsuite><testcase classname='test_stats.TestStats' name='test_mean_of_three'>"
          "<error message=\\\"No module named 'yaml'\\\"/></testcase></testsuite>\" > \"$1\"\necho \"ModuleNotFoundError: No module named 'yaml'\"\nexit 1\n")
# 同じ試験が中身まで届いて通る起動スクリプト（書き直した後の形）
GOOD = ("#!/bin/sh\nprintf '%s' \"<testsuite><testcase classname='test_stats.TestStats' name='test_mean_of_three'/></testsuite>\" "
        "> \"$1\"\nexit 0\n")


class SuiteFixCase(tg.GroupChildScriptsCase):
    """組の子の scripts の道具立て（tg.GroupChildScriptsCase）を借りる。借りた元の試験は load_tests で外して、ここの試験だけを回す"""
    def setUp(self):
        super().setUp()
        self.runner = self.tmp / "gate" / "suite" / "runner"   # 試験の関門の place の実行器（対象の作業ツリーの外）
        self.runner.parent.mkdir(parents=True)
        self.put(self.runner, BROKEN)
        self.keep = self.tmp / "suites"
        self.grp_env = {launcher.SUITE_KEEP_ENV: str(self.keep)}

    @staticmethod
    def put(path: pathlib.Path, body: str) -> None:
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)

    def kept(self, cmd: str) -> pathlib.Path:
        return self.keep / hashlib.sha256(cmd.encode("utf-8")).hexdigest()

    def started(self) -> dict:
        return json.loads((self.place / "tdd-start.json").read_text(encoding="utf-8"))

    def broken_start(self, test_cmd: str = "true", made: bool = True) -> dict:
        self.kept(test_cmd).parent.mkdir(parents=True, exist_ok=True)
        self.kept(test_cmd).write_bytes(self.runner.read_bytes())   # 前の run が取り置いた同じ壊れた実行器
        self.parent_inputs(str(self.runner), test_cmd=test_cmd, suite_made=made)
        return self.start()

    def test_a_runner_that_breaks_only_itself_is_found_at_the_loop_head(self):
        """工場の書いた実行器で関わる試験が error になり、test_cmd の単体は通れば、輪を回さず suite_broken。取り置きからも捨て、訳に
        両方のログのパスが載る"""
        out = self.broken_start()
        self.assertEqual((out["tdd"], out["suite_broken"]), (False, True))
        self.assertFalse(self.kept("true").exists(), "壊れた起動スクリプトが取り置きに残った")
        started = self.started()
        self.assertIn(started["runner_log"], started["reason"])
        self.assertIn(started["cmd_log"], started["reason"])
        self.assertEqual(self.run_script("tdd_go"), {"tdd": False, "stop": True})

    def test_a_runner_the_person_gave_is_not_called_broken(self):
        """人が渡した実行器（suite_made が偽）は書き直させない（今までどおり）"""
        out = self.broken_start(made=False)
        self.assertIs(out["suite_broken"], False)
        self.assertTrue(self.kept("true").exists())

    def test_a_red_test_cmd_alone_means_the_tests_are_red_not_the_runner(self):
        """test_cmd の単体も赤なら、試験そのものの赤で、起動スクリプトの壊れと読まない"""
        self.assertIs(self.broken_start(test_cmd="false")["suite_broken"], False)

    def test_a_rewritten_runner_lets_the_loop_go_on_and_is_kept(self):
        """書き手の指示に壊れた本文とログの末尾が入り、書き直した本文で輪の頭をやり直して通れば、輪が続き、直した実行器を取り置く"""
        self.broken_start()
        prep = self.run_script("suite_fix_prep")
        self.assertTrue(prep["write"])
        self.assertIn("No module named 'yaml'", prep["prompt"])
        from tests.blocks.fix.test_prompts import RENDERED
        self.assertIn(RENDERED["suite-fix"], prep["prompt"])
        self.assertIn("## The runner's contract", prep["prompt"], "共通の断片 runner-writer が入る")
        self.assertIn("printf", prep["prompt"])
        self.assertTrue((self.place / "suite-fix-prompt-1.md").is_file())
        got = self.run_script("suite_fix_try", reply=json.dumps({"made": True, "body": GOOD, "why": ""}))
        self.assertEqual((got["tdd"], got["stop"]), (True, False))
        self.assertEqual(self.runner.read_text(encoding="utf-8"), GOOD)
        self.assertEqual(self.kept("true").read_text(encoding="utf-8"), GOOD)
        self.assertEqual(self.run_script("tdd_go"), {"tdd": True, "stop": False})

    def test_a_runner_still_broken_after_the_rewrite_stops_the_group(self):
        """書き直しても壊れたままなら組を止める: 修正役の輪を回さず（tdd-go の stop）、組の結果の tdd に suite_broken が載り、組の形の
        出口が stopby.SUITE_BROKEN を名乗る"""
        self.broken_start()
        got = self.run_script("suite_fix_try", reply=json.dumps({"made": True, "body": BROKEN, "why": ""}))
        self.assertEqual((got["tdd"], got["stop"]), (False, True))
        self.assertIn("書き直した起動スクリプトも壊れている", got["reason"])
        self.assertEqual(self.run_script("tdd_go"), {"tdd": False, "stop": True})
        result = json.loads(pathlib.Path(self.run_script("group_end")["result_file"]).read_text(encoding="utf-8"))
        self.assertIs(result["tdd"]["suite_broken"], True)
        out = self.run_script("finish")
        self.assertEqual((out["ok"], out["stop_reason"]), (False, stopby.SUITE_BROKEN))
        self.assertIn("書き直した起動スクリプトも壊れている", out["reason"])
        self.assertIs(next(r for r in out["tdd"] if r["group_id"] == "g1")["suite_broken"], True)

    def test_a_writer_that_could_not_rewrite_stops_the_group(self):
        """書き手が作れなかった（made が偽）・返答が無い時も、確かめていない直しを書き進めずに組を止める"""
        self.broken_start()
        for reply in ({"made": False, "body": "", "why": "読めなかった"}, None):
            with self.subTest(reply=reply):
                got = self.run_script("suite_fix_try", reply=json.dumps(reply))
                self.assertEqual((got["tdd"], got["stop"]), (False, True))
                self.assertIn("起動スクリプトを書き直せなかった", got["reason"])

    def test_the_fix_loop_waits_for_the_rewrite(self):
        """配線: 書き直しの node は group-start の suite_broken の時だけ回り、TDD の輪と修正役の輪は tdd-go の後ろ"""
        NODES = tg.NODES
        self.assertEqual(NODES["suite-fix-prep"]["when"], "$group-start.output.suite_broken == true")
        self.assertEqual(NODES["tdd-loop"]["when"], "$tdd-go.output.tdd == true")
        self.assertEqual(NODES["fix-loop"]["when"], "$tdd-go.output.stop == false")
        self.assertIn("tdd-go", NODES["fix-loop"]["depends_on"])
        self.assertEqual(NODES["suite-fix-try"]["trigger_rule"], "none_failed_min_one_success")
        self.assertEqual(NODES["suite-fix-try"]["when"], "$group-start.output.suite_broken == true",
                         "前が飛んでも走る: 壊れていない組で書き直せなかったと読んで止めない")
        self.assertEqual(NODES["suite-fix"]["model"], "@wf-test-gate")


class BrokenBeforeCase(unittest.TestCase):
    """#836 の 1（docs/design/fix.md の 19 節）: 関わる試験で直す前から壊れていた物のファイルを TDD の輪の頭が選び、許しの 6 つ目の
    元（出どころ broken）にする"""

    def setUp(self):
        import tempfile
        from tests.bin.gitkit import committed_copy
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, ROOT / "tests" / "e2e" / "target-seed")
        self.tdd = kit.load("fix", "tdd")

    def test_only_failing_tests_near_the_fix_are_picked(self):
        cases = [{"classname": "test_stats.TestStats", "name": "test_mean", "outcome": "failure"},
                 {"classname": "test_stats.TestStats", "name": "test_ok", "outcome": "passed"}]
        near = {"whole": False, "files": ["test_stats.py"], "left": [], "far": [], "reasons": []}
        got = self.tdd.broken_related(self.tmp, self.repo, [], 1, self.tmp, cases, near)
        self.assertEqual(got, [{"path": "test_stats.py", "ids": ["test_stats.TestStats::test_mean"]}])
        self.assertEqual(self.tdd.broken_related(self.tmp, self.repo, [], 1, self.tmp, cases, {**near, "files": []}), [],
                         "修正案が触る所に直に関わらない試験はついでに直してよい物に入れない")
        self.assertEqual(self.tdd.broken_related(self.tmp, self.repo, [], 1, self.tmp, cases, {**near, "whole": True}), [],
                         "関わるかを選べない時は入れない")
        self.assertEqual(self.tdd.broken_related(self.tmp, self.repo, [], 1, self.tmp, cases[1:], near), [])

    def test_the_file_becomes_a_permit_from_the_broken_source(self):
        import conflict
        import fixboard
        place = self.tmp / "place"
        place.mkdir()
        self.assertEqual(conflict.edit_permits(place, "first")["broken"], [])
        (place / conflict.BROKEN_TESTS_FILE).write_text(
            json.dumps({"tests": [{"path": "test_stats.py", "ids": ["test_stats.TestStats::test_mean"]}]}), encoding="utf-8")
        rows = [p for p in conflict.test_permits(place) if p.get("broken")]
        self.assertEqual([(r["limit"], r["source"]) for r in rows], [("test_stats.py", fixboard.ALLOWED_SOURCES[3])])
        self.assertEqual(conflict.edit_permits(place, "first")["broken"], ["test_stats.py"])
        self.assertIn("test_stats.py", conflict.edit_permits(place, "first")["limits"], "受け付けの事後の関門も同じ範囲を許す")
        self.assertEqual([r["source"] for r in fixboard.allowed_test_rows(place)], ["broken"])


class BeforeCasesCase(unittest.TestCase):
    """確かめ直しの「前から同じ形で赤」（#837。docs/design/fix.md の 18 節）が照らす直す前の結末は、試験の関門が直す前に試験を走らせなく
    なった（持ち主の決め base-runs-nothing）ので、組の子の TDD の輪の頭が取った失敗の文つきの結末を足して読む"""

    def test_the_loop_head_cases_of_the_children_are_read(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        place = pathlib.Path(tmp.name)
        board = kit.load("fix", "board")
        row = {"classname": "test_stats.TestStats", "name": "test_mean", "outcome": "error", "fail_message": "No module named 'yaml'",
               "fail_text": ""}
        state = place / "g1-art" / "tdd-1" / "state.json"
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps({"baseline_cases": [row]}), encoding="utf-8")
        (place / "groups" / "g1").mkdir(parents=True)
        (place / "groups" / "g1" / board.RESULT_FILE).write_text(json.dumps({"group_id": "g1", "end_tree": "t", "tdd_state": str(state)}), encoding="utf-8")
        (place / board.GROUPS_FILE).write_text(json.dumps({"groups": [{"group_id": "g1"}], "out_dir": str(place / "groups")}),
                                                encoding="utf-8")
        (place / board.BASELINE_FILE).write_text(json.dumps({"cases": [], "exit": None, "how": []}), encoding="utf-8")
        got = board.before_cases(place)
        self.assertEqual([(c["name"], c["fail_message"]) for c in got], [("test_mean", "No module named 'yaml'")])


def load_tests(loader, tests, pattern):
    """借りた tg.GroupChildScriptsCase の試験を回し直さない（このクラスに書いた試験だけ）"""
    suite = unittest.TestSuite(SuiteFixCase(name) for name in loader.getTestCaseNames(SuiteFixCase) if name in SuiteFixCase.__dict__)
    suite.addTests(loader.loadTestsFromTestCase(BrokenBeforeCase))
    suite.addTests(loader.loadTestsFromTestCase(BeforeCasesCase))
    return suite


if __name__ == "__main__":
    unittest.main()

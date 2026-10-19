"""fix の block の TDD の輪（workflows/fix/src/tdd.py。lib/tddloop.py の写し）と、輪の赤の判定を読む事後の関門の赤緑
（src/gates.py の red_green）の検査。lib/tests/test_blk_fix_tdd.py・test_tdd_outside.py・test_tdd_frozen_function_span.py・
test_fix_gates.py の TestRedGreen を src の写しに向け直した物（docs/design/fix.md の 14.2）。

- 実行器が無い run: tdd.start は何も書かずに go: false を返し、出口の tdd は ran: false
- 実行器が在る run: 種の git（tests/e2e/target-seed の写し）と、unittest を回して JUnit XML を書く小さな実行器（試験の中の SUITE）で、
  振り分け → テスト → 直す → 整える を役の代わりに作業ツリーを書き換えて回す
- 指示: tdd.prep は材料（{go, new_unit, state, path, briefs}）だけを返し、文は src/prompts.tdd が prompts/parts/tdd.md に値と段落の
  真偽（prompts.tdd_values）を入れて組む。指示の検査は文の見出しでなく、値と段落の真偽で見る（文は md の側の検査が持つ）
- 軽量の単位（port skip_rerun）: group-start が values.json の skip_rerun を tdd.start の unit_depths（{key: tdd.LIGHT}）に渡し、
  その単位は緑の後の test_cmd を走らせない
置き場は fix の run の place（状態は place の tdd-<k>/）。parse_junit・red_problems・green_problems・_failure_attrs・run_suite は
lib の baseline_red の物（写していない）なので、その場合は lib/tests/test_baseline_red.py が持つ。
"""
import importlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

from tests.bin import hermetic
from tests.bin.gitkit import committed_copy, git
from tests.blocks import kit

tdd = kit.load("fix", "tdd")
from src import board, facts, gates, prompts, runvals  # noqa: E402
for _name in ("files", "rules", "runvals", "carry", "lanes", "intake", "scope", "unitrows", "consult", "clash", "ruling", "parking"):
    importlib.import_module(f"src.{_name}")   # 遅れて読む src の名（board の関数の中の import）もこの block の物に揃える
FIX_SRC = {n: m for n, m in sys.modules.items() if n == "src" or n.startswith("src.")}

import conflict  # noqa: E402  （lib）
import planbrief  # noqa: E402  （lib）
import planmarks  # noqa: E402  （lib）
import seat  # noqa: E402  （lib）

SEED = kit.ROOT / "tests" / "e2e" / "target-seed"
RULER = kit.BLOCKS / "fix" / "prompts" / "ruler.md"


def pin_src():
    """sys.modules の src をこの block の物に戻す（ほかの block の試験の kit.load が同じ過程で src を読み替えるので、src の関数の
    中の遅れた import がこの block の物を引くように、各試験の前に置き直す）"""
    for name in [n for n in sys.modules if (n == "src" or n.startswith("src.")) and n not in FIX_SRC]:
        del sys.modules[name]
    sys.modules.update(FIX_SRC)


class Case(unittest.TestCase):
    def run(self, result=None):
        pin_src()
        return super().run(result)


DEADLINE = 1728000000
MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
OPEN = json.dumps([MEAN, CLAMP], ensure_ascii=False)
V1 = {"ok", "files", "changes_file", "removed"}

from tests.blocks.fix.support import SUITE  # noqa: E402

# SUITE の写しで、pytest の JUnit に合わせる実行器: 断言の失敗も本体の例外も failure と書き、message に「<型>: <文>」を付ける
# （pytest は本体の例外を failure と書く。引用の照らし tdd.red_check はこの message を読む）
PYTEST_LIKE = '''
import sys, unittest, xml.etree.ElementTree as ET
sys.dont_write_bytecode = True
sys.path.insert(0, ".")
out = sys.argv[1]
rows = []
class R(unittest.TestResult):
    def addSuccess(self, t): rows.append((t, None, ""))
    def addFailure(self, t, e): rows.append((t, "failure", f"{e[0].__name__}: {e[1]}"))
    def addError(self, t, e): rows.append((t, "failure", f"{e[0].__name__}: {e[1]}"))
    def addSkip(self, t, r): rows.append((t, "skipped", ""))
unittest.defaultTestLoader.discover(".", pattern="test_*.py", top_level_dir=".").run(R())
root = ET.Element("testsuite")
for t, kind, msg in rows:
    cls, name = t.id().rsplit(".", 1)
    tc = ET.SubElement(root, "testcase", classname=cls, name=name)
    if kind:
        ET.SubElement(tc, kind, message=msg)
ET.ElementTree(root).write(out)
sys.exit(0 if all(k in (None, "skipped") for _, k, _ in rows) else 1)
'''

NEW_TEST = '''
    def test_mean_of_two(self):
        self.assertEqual(mean([2, 4]), 3)
'''
PASSING_TEST = '''
    def test_clamp_below_range(self):
        self.assertEqual(clamp(-5, 0, 10), 0)
'''


class RunnerSeamCase(Case):
    """TDD の輪の実行器と failure の文の読みは baseline_red の物で、諦めは 3 回目（元 lib/tests/test_fix_seams.py の SmallGapsSeamCase。
    keep-essence の 4。申し出の頼みの文が種類を全部言うことは test_prompts.py の ConflictWordsCase）"""

    def test_tdd_loop_takes_the_runner_from_baseline_red_and_gives_up_on_the_third(self):
        import baseline_red
        self.assertIs(tdd.run_suite, baseline_red.run_suite)
        self.assertIs(tdd._failure_attrs, baseline_red._failure_attrs)
        self.assertEqual(tdd.retry_max(), 3)


class StepLogCase(Case):
    """tdd.step は作業ツリーと書き込みの記録を別に受け、記録も申告も無い変更は段を拒み、記録が在れば通す（元 lib/tests/test_fix_seams.py の
    LaneChecksSeamCase.test_tdd_step_matches_writes_with_the_given_log。元 works/tests/test_tdd_lanes.py の
    TestLaneCommand.test_unrecorded_write_in_lane_is_rejected）"""

    def test_tdd_step_matches_writes_with_the_given_log(self):
        import writes
        tmp = hermetic.tmpdir(self, prefix="works-tdd-step-log-")
        repo, place = tmp / "repo", tmp / "place"
        committed_copy(repo, SEED)
        place.mkdir()
        suite = tmp / "suite.py"
        suite.write_text(SUITE, encoding="utf-8")
        start = tdd.start(place, repo, str(suite), OPEN)
        self.assertTrue(start["go"], start)
        state = start["state_file"]
        log = tmp / "run-writes.jsonl"   # 置き場の外の記録（既定の置き場の記録は使わない）
        log.write_text("", encoding="utf-8")
        got = tdd.step(state, {"phase": "route", "units": [
            {"unit_key": MEAN, "route": "tdd"},
            {"unit_key": CLAMP, "route": "direct", "why": "文書の直しと同じで、先にテストを書けない単位"}]}, repo, log=log)
        self.assertTrue(got["ok"], got)
        tests = repo / "test_stats.py"
        tests.write_text(tests.read_text(encoding="utf-8").replace("\n\nif __name__", NEW_TEST + "\n\nif __name__"), encoding="utf-8")
        reply = {"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                 "tests": ["test_stats.py::TestStats::test_mean_of_two"]}
        got = tdd.step(state, dict(reply), repo, log=log)
        self.assertEqual((got["ok"], got["phase"]), (False, "test"), got)
        self.assertIn(writes.REJECT, got["reason"])
        self.assertIn("test_stats.py", got["reason"])
        real = os.path.realpath(tests)
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"tool_name": "Write", "path": real, "file_sha": writes._sha(real)}) + "\n")
        got = tdd.step(state, dict(reply), repo, log=log)
        self.assertEqual((got["ok"], got["phase"]), (True, "fix"), got)


class TestNoSuite(Case):
    """実行器が無い run は今と同じ: tdd-start は何も書かず go: false。出口の tdd は ran: false"""

    def test_start_without_suite_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            repo = tmp / "repo"
            committed_copy(repo, SEED)
            got = tdd.start(tmp / "art", repo, "", OPEN)
            self.assertEqual(got, {"go": False, "reason": tdd.NO_SUITE, "suite": "", "state_file": "",
                                   "summary_file": ""})
            self.assertFalse((tmp / "art").exists(), "置き場に何も書かない")
            self.assertEqual(git(repo, "status", "--porcelain"), "")

    def test_exit_fields_without_suite(self):
        start = {"go": False, "reason": tdd.NO_SUITE, "suite": "", "state_file": "", "summary_file": ""}
        self.assertEqual(tdd.exit_fields(start), {"ran": False, "suite": "", "reason": tdd.NO_SUITE, "units": []})

    def test_missing_suite_file_falls_back_to_direct(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            repo = tmp / "repo"
            committed_copy(repo, SEED)
            got = tdd.start(tmp / "board", repo, "no/such/suite.sh", OPEN)
            self.assertIs(got["go"], False)
            self.assertIn("no/such/suite.sh", got["reason"])
            self.assertEqual(got["state_file"], "")

    def test_freeze_check_skips_without_state(self):
        self.assertEqual(tdd.frozen_problems("", pathlib.Path(".")), [])


DECLARED = {"declared": True, "why": "分母の式を名前の付いた変数に分けたい"}   # fix の段の整えの申告（理由は MIN_WHY 字以上）
PLAN_REFACTOR = {"item": 1, "why": "分母の計算を補助の関数に寄せる"}   # 約束の refactor の 1 行（修正案の項目の申告）


class LoopCase(Case):
    """種の git と小さな実行器で輪を回す（役の代わりに作業ツリーを書き換える）"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = pathlib.Path(self._tmp.name)
        self.repo = tmp / "repo"
        committed_copy(self.repo, SEED)
        self.suite = tmp / "suite.py"
        self.suite.write_text(SUITE, encoding="utf-8")
        self.board = tmp / "art" / "board"
        self.start = tdd.start(self.board, self.repo, str(self.suite), OPEN)
        self.assertTrue(self.start["go"], self.start)
        self.state = self.start["state_file"]

    def restart(self, test_cmd=""):
        """tdd-start を起こし直す（test_cmd は線の入力）"""
        self.start = tdd.start(self.board, self.repo, str(self.suite), OPEN, test_cmd=test_cmd)
        self.assertTrue(self.start["go"], self.start)
        self.state = self.start["state_file"]

    def st(self):
        return json.loads(pathlib.Path(self.state).read_text(encoding="utf-8"))

    def values(self, values=None):
        """今の周の指示の (値, 段落の真偽)（tdd.prep の材料を prompts.tdd_values が組む物。node tdd-prep と同じ）"""
        vals, when, _ = prompts.tdd_values(self.board, self.repo, tdd.prep(self.state), values or {})
        return vals, when

    def prompt(self, values=None):
        """今の周の組んだ指示の字（prompts.tdd が place に書く物。place は輪の置き場の根 self.board）"""
        view = tdd.prep(self.state)
        with mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(self.board), "ARCHON_NODE_EXECUTION": ""}):
            return prompts.tdd(self.board, self.repo, view, values or {})["prompt"]

    def step(self, reply):
        return tdd.step(self.state, reply, self.repo)

    def edit(self, name, old, new):
        p = self.repo / name
        text = p.read_text(encoding="utf-8")
        self.assertIn(old, text)
        p.write_text(text.replace(old, new), encoding="utf-8")

    def add_test(self, body):
        self.edit("test_stats.py", "\n\nif __name__", body + "\n\nif __name__")

    def route(self, mean="tdd", clamp="direct"):
        rows = [{"unit_key": MEAN, "route": mean}, {"unit_key": CLAMP, "route": clamp}]
        for r in rows:
            if r["route"] == "direct":
                r["why"] = "文書の直しと同じで、先にテストを書けない単位"
        got = self.step({"phase": "route", "units": rows})
        self.assertTrue(got["ok"], got)
        return got

    def red(self):
        self.add_test(NEW_TEST)
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                         "tests": ["test_stats.py::TestStats::test_mean_of_two"]})
        self.assertTrue(got["ok"], got)
        return got

    def fix_mean(self, refactor=None):
        """mean を直して fix の段を返す。refactor は整えの申告（{declared, why}。None は欄を書かない）"""
        self.edit("stats.py", "return sum(xs) / (len(xs) - 1)", "return sum(xs) / len(xs)")
        reply = {"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を len(xs) にした"}
        if refactor is not None:
            reply["refactor"] = refactor
        got = self.step(reply)
        self.assertTrue(got["ok"], got)
        return got

class TestStart(LoopCase):
    def test_baseline_and_first_prompt(self):
        st = self.st()
        self.assertEqual(st["phase"], "route")
        self.assertEqual(st["baseline"]["test_stats.TestStats::test_mean_of_three"], "failure")
        self.assertEqual(st["baseline"]["test_stats.TestStats::test_clamp_within_range"], "passed")
        self.assertNotEqual(st["baseline_exit"], 0)
        prompt = self.prompt()
        for w in ("route", MEAN, CLAMP, str(self.suite)):
            self.assertIn(w, prompt)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "", "元の結末を取っても作業ツリーは変わらない")

    def test_prompt_carries_the_borrowed_skill_seat(self):
        """TDD の役の指示に借りたスキルの座（Skill で test-driven-development を読む 1 文と読み替えの TDD の役の節）が載る（元 tddloop の
        seat.section。今は値 skill・seat_applies・seat_not_applies・unattended を md の座の節に入れる）"""
        vals, _ = self.values()
        self.assertEqual(vals["skill"], "test-driven-development")
        self.assertTrue(vals["seat_applies"] and vals["seat_not_applies"], vals)
        full = self.prompt()
        self.assertIn("`test-driven-development`", full)
        self.assertIn(seat.overlay_body(seat.OVERLAY_KINDS["tdd"]).strip(), full)

    def test_prep_marks_a_new_unit_only_when_the_unit_changes(self):
        """支度の返りの new_unit は、前の周の支度と単位の鍵（振り分けの段は route、ほかの段は今の単位）が違う周だけ真（YAML が
        新しい会話の役と続きの役を振り分ける。元 works/blk-fix/lib/tddloop.py:880 write_key の鍵と同じ切れ目）。拒まれた出し直し・
        同じ単位の次の段は偽、単位が替われば真"""
        def new_unit():
            return tdd.prep(self.state)["new_unit"]
        self.assertTrue(new_unit(), "1 周目は新しい会話")
        self.assertFalse(new_unit(), "同じ振り分けの段の出し直し")
        self.route(clamp="tdd")
        self.assertTrue(new_unit(), "振り分けから単位の段へ")
        self.assertFalse(self.step({"phase": "test", "unit_key": MEAN, "test_files": [], "tests": []})["ok"])
        self.assertFalse(new_unit(), "拒まれた出し直しは同じ会話")
        self.red()
        self.assertFalse(new_unit(), "同じ単位の次の段（fix）は同じ会話")
        self.fix_mean()
        self.assertEqual(self.st()["queue"][self.st()["cur"]], CLAMP)
        self.assertTrue(new_unit(), "次の単位は新しい会話")

    def test_seat_failure_stops_with_broken(self):
        """座を組めない（写しが固定と違う）時は座の無い指示書に逃げず Broken で止め、指示書を書かない
        （元 works/blk-fix/lib/tddloop.py:807 prep、旧試験 works/tests/test_blk_fix_tdd.py:536 test_tdd_seat_failure_stops_with_broken）"""
        with mock.patch.object(seat, "pinned", side_effect=ValueError("写しが固定と違う")):
            with self.assertRaises(prompts.Broken) as got:
                self.prompt()
        self.assertIn("座を組めない", str(got.exception))
        self.assertIn("写しが固定と違う", str(got.exception))
        self.assertEqual(sorted(p.name for p in self.board.glob("tdd*-prompt-*.md")), [], "座の無い指示書を書かない")
        self.assertFalse((pathlib.Path(self.st()["work"]) / tdd.PROMPT).exists())

    def test_prompt_is_composed_from_the_shared_rules(self):
        """tdd-prep の指示: 修正の決まりの正本（.shared の writer-rules）・TDD の読み替え・今の段の約束（今の段の段落だけ真）・
        今の段の指示。周ごとに決まりを全部載せる（差分版は無い）。周の数は状態の iterations + 1"""
        rules = (kit.SHARED / "prompts" / "writer-rules.md").read_text(encoding="utf-8").split("\n", 1)[0]
        vals, when = self.values({"judgment_file": "/b/j.json"})
        self.assertEqual([k for k, v in when.items() if k.startswith("phase_") and v], ["phase_route"], "今の段の約束だけ")
        self.assertEqual((vals["judgment_file"], vals["iteration"], vals["phase"]), ("/b/j.json", 1, "route"))
        full = self.prompt({"judgment_file": "/b/j.json"})
        for s in (rules, "- **route**:", "/b/j.json"):
            self.assertIn(s, full)
        self.assertNotIn("- **test**:", full, "今の段の約束だけ")
        self.route()
        vals, when = self.values({"judgment_file": "/b/j.json"})
        self.assertEqual([k for k, v in when.items() if k.startswith("phase_") and v], ["phase_test"])
        self.assertEqual((vals["iteration"], vals["phase"]), (2, "test"))
        full2 = self.prompt({"judgment_file": "/b/j.json"})
        self.assertIn(rules, full2, "2 回目も決まりを全部")
        self.assertIn("- **test**:", full2)
        self.assertNotIn("- **route**:", full2)
        self.assertEqual(sorted(p.name for p in self.board.glob("tdd*-prompt-*.md")),
                         ["tdd-prompt-1.md", "tdd-prompt-2.md"],
                         "周ごとに place に書く（先の self.values の支度が単位の鍵を進めたので、どちらも続きの役 tdd の周）")

    def test_owed_units_are_conflict_fix_duty_not_the_is_open_list(self):
        """TDD が振り分ける義務は受け付けと同じ conflict.fix_duty の owed。渡された open_units（is_open）に無くても、関所で答えて
        直す義務に戻った単位は載り、外れた単位は載らない"""
        back = "stats.py returned: 関所で答えて直す義務に戻った単位"
        with mock.patch.object(tdd.fixboard, "fix_duty", return_value=({MEAN, back}, {CLAMP: "答え待ちの問い q1"})) as duty:
            got = tdd.start(self.board, self.repo, str(self.suite), OPEN, owed={MEAN, CLAMP, back},
                                withheld_by={CLAMP: "q1"})
        self.assertEqual(duty.call_args.args, (self.board, {MEAN, CLAMP, back}), "直す義務の値は呼び手が渡す（元は盤面）")
        self.assertTrue(got["go"], got)
        st = json.loads(pathlib.Path(got["state_file"]).read_text(encoding="utf-8"))
        self.assertEqual(sorted(tdd._owed(st)), sorted([MEAN, back]))

    def test_second_start_gets_its_own_state(self):
        again = tdd.start(self.board, self.repo, str(self.suite), OPEN)
        self.assertNotEqual(again["state_file"], self.state)

    def test_head_reuses_the_green_baseline_of_the_same_run(self):
        """元 works/blk-fix/lib/tddloop.py:598 の run_suite(note=reuse["suite"]): 同じ run の中で同じ木の輪の頭は、緑の元の結末を
        控えから使い回して実行器を起こさない（JUnit は書き戻すので元の結末は同じ）。出どころは状態の reused.suite に出る（tdd の出口の reused に載る）"""
        import tree_run
        count = self.board.parent / "suite-count"
        green = self.board.parent / "green.py"
        green.write_text(f"import sys\nopen({str(count)!r}, 'a').write('1\\n')\nopen(sys.argv[1], 'w').write("
                         "'<testsuite><testcase classname=\"c\" name=\"t\"/></testsuite>')\n", encoding="utf-8")
        place = tree_run.reuse_place(self.board.parent, "run-1", rerun=False)
        first = tdd.start(self.board, self.repo, str(green), OPEN, reuse=place)
        again = tdd.start(self.board, self.repo, str(green), OPEN, reuse=place)
        states = [json.loads(pathlib.Path(s["state_file"]).read_text(encoding="utf-8")) for s in (first, again)]
        self.assertEqual(len(count.read_text(encoding="utf-8").split()), 1)
        self.assertEqual(states[1]["baseline"], {"c::t": "passed"})
        self.assertEqual(states[0]["reused"], {})
        self.assertIn("run run-1", states[1]["reused"]["suite"])

    def test_tdd_prep_puts_brief_of_current_unit(self):
        """振り分けの段は直す義務の単位の全部の brief、ほかの段は今の単位の brief だけを頭で名指す"""
        rows = [{"item": 1, "unit_keys": [MEAN], "file": "/b/r1/brief-1.md", "sha256": "a" * 64},
                {"item": 2, "unit_keys": [CLAMP], "file": "/b/r1/brief-2.md", "sha256": "b" * 64}]
        with mock.patch.object(tdd.planbrief, "cut_at", return_value=rows) as cut:
            route, when = self.values()
            self.assertEqual(pathlib.Path(cut.call_args[0][0]).resolve(), self.board.resolve(), "fix の置き場で切る")
            self.assertTrue(when["briefs"])
            self.assertIn("brief-1.md", route["brief_rows"])
            self.assertIn("brief-2.md", route["brief_rows"])
            self.route()   # MEAN は tdd、CLAMP は direct
            test, _ = self.values()
            self.assertIn("brief-1.md", test["brief_rows"])
            self.assertNotIn("brief-2.md", test["brief_rows"], "今の単位は MEAN だけ")
            self.assertIn("brief-1.md", self.prompt())

    def test_tdd_prep_hands_off_finished_units(self):
        """依頼 243 の 2: 次の単位の指示書に、前に済んだ単位の引き継ぎ（単位の key・直したファイル・緑にしたテスト・整え）を
        機械が書く（会話の履歴に頼らない）。周ごとに新しい会話で起きるので、引き継ぎの節はいつも載り、振り分けの段と最初の単位
        には前の単位の行が無い"""
        route, when = self.values()
        self.assertFalse(when["handoff"], "振り分けの段には前の単位の行が無い")
        self.assertIn("- 今の段: route", route["handoff_rows"])
        self.assertIn("## Handoff from the previous units", self.prompt(), "引き継ぎの節はいつも載る")
        self.route(clamp="tdd")
        first, when = self.values()
        self.assertFalse(when["handoff"], "最初の単位には前の単位の行が無い")
        self.assertIn(f"- 今の段: test・今の単位: {MEAN}", first["handoff_rows"])
        self.red()
        self.fix_mean()
        st = self.st()
        self.assertEqual(st["units"][st["queue"][st["cur"]]]["unit_key"], CLAMP)
        nxt, when = self.values()
        self.assertTrue(when["handoff"])
        part = nxt["handoff_rows"]
        for w in (MEAN, "stats.py", "test_stats.py::TestStats::test_mean_of_two"):
            self.assertIn(w, part)
        done = part.split("- 今の段:", 1)[0]
        self.assertNotIn(CLAMP, done, "今の単位は前の単位の行に載せない")
        self.assertIn(f"- 今の段: test・今の単位: {CLAMP}", part)

    def test_tdd_prep_hands_off_the_current_units_earlier_phases(self):
        """周ごとに新しい会話（実行基盤の輪の fresh_context）で起きるので、同じ単位の前の段の結果も引き継ぎの節に載る: fix の段は
        test の段の名指し・テストのファイル・仮の実装のファイル、refactor の段は fix の段の直しと整えの申告の理由。拒まれた回も"""
        self.route()
        self.add_test(NEW_TEST)
        (self.repo / "helper_stub.py").write_text("X = 0\n", encoding="utf-8")   # test の段の仮の実装
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                         "tests": ["test_stats.py::TestStats::test_mean_of_two"]})
        self.assertTrue(got["ok"], got)
        part = self.values()[0]["handoff_rows"]
        for w in (f"- 今の段: fix・今の単位: {MEAN}", "test の段の結果", "test_stats.py::TestStats::test_mean_of_two",
                  "helper_stub.py"):
            self.assertIn(w, part)
        got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "直せていない"})
        self.assertFalse(got["ok"])
        self.assertIn("この段の返答は 1 回拒まれた", self.values()[0]["handoff_rows"])
        self.fix_mean(refactor=DECLARED)
        part = self.values()[0]["handoff_rows"]
        for w in ("- 今の段: refactor", "fix の段の結果", "分母を len(xs) にした", DECLARED["why"]):
            self.assertIn(w, part)

    def test_tdd_prep_without_board_has_no_brief(self):
        """brief の控えの無い置き場（修正案の無い run と同じ）では brief の節を置かない"""
        vals, when = self.values()
        self.assertEqual((vals["brief_rows"], when["briefs"]), ("", False))
        self.assertNotIn("## The requirement (briefs)", self.prompt())

    def test_tdd_prep_broken_ledger_stops_with_reason(self):
        """brief の控えが壊れていれば、brief の無い指示書として続けず、控えを名指す理由の Broken で止める（traceback にしない）"""
        broken = planbrief.LedgerBroken(f"brief の控え /b/r1/{planbrief.LEDGER} を読めない: 壊れた")
        with mock.patch.object(tdd.planbrief, "cut_at", side_effect=broken):
            with self.assertRaisesRegex(tdd.Broken, planbrief.LEDGER):
                tdd.prep(self.state)
            with self.assertRaisesRegex(tdd.Broken, planbrief.LEDGER):
                self.prompt()

class TestRoute(LoopCase):
    def test_rejects_bad_routing_with_reason_in_next_prompt(self):
        bad = {"phase": "route", "units": [{"unit_key": MEAN, "route": "direct", "why": "短い"},
                                           {"unit_key": "作り話", "route": "tdd"}]}
        got = self.step(bad)
        self.assertEqual((got["ok"], got["done"]), (False, False))
        for w in (CLAMP, "作り話", "10 字"):
            self.assertIn(w, got["reason"])
        vals, when = self.values()
        self.assertTrue(when["rejected"])
        self.assertIn("作り話", vals["rejection"], "理由は次の指示に届く")
        self.assertIn("作り話", self.prompt())

    def test_route_gives_up_after_retry_max_to_all_direct(self):
        for _ in range(tdd.retry_max()):
            got = self.step({"phase": "route", "units": []})
        self.assertEqual((got["ok"], got["done"]), (False, True))
        ex = tdd.exit_fields(self.start)
        self.assertEqual([(u["unit_key"], u["route"]) for u in ex["units"]], [(MEAN, "direct"), (CLAMP, "direct")])
        self.assertTrue(all(len(u["why"]) >= 10 for u in ex["units"]))

    def test_all_direct_ends_loop(self):
        got = self.route(mean="direct", clamp="direct")
        self.assertTrue(got["done"])


class TestUnitLoop(LoopCase):
    def test_happy_path(self):
        self.route()
        self.assertEqual(self.st()["phase"], "test")
        self.red()
        self.assertEqual(self.st()["phase"], "fix")
        got = self.fix_mean()
        self.assertEqual((got["ok"], got["done"]), (True, True), "申告が無ければ整えの段は来ない")
        ex = tdd.exit_fields(self.start)
        self.assertTrue(ex["ran"])
        rows = {u["unit_key"]: u for u in ex["units"]}
        m = rows[MEAN]
        self.assertEqual((m["route"], m["red"], m["green"], m["refactor"], m["gave_up"]), ("tdd", "ok", "ok", "skipped", ""))
        self.assertEqual(m["tests"], ["test_stats.py::TestStats::test_mean_of_two"])
        self.assertEqual(m["test_files"], ["test_stats.py"])
        self.assertEqual(rows[CLAMP]["route"], "direct")
        self.assertIn("先にテストを書けない", rows[CLAMP]["why"])
        summary = pathlib.Path(self.start["summary_file"]).read_text(encoding="utf-8")
        for w in (MEAN, CLAMP, "test_stats.py"):
            self.assertIn(w, summary)
        self.assertEqual(tdd.frozen_problems(self.state, self.repo), [])
        self.edit("test_stats.py", "mean([2, 4]), 3", "mean([2, 4]), 3.0")
        self.assertTrue(tdd.frozen_problems(self.state, self.repo), "輪の後の修正役がテストを変えたら拒む")

    def test_refactor_rechecked(self):
        self.route()
        self.red()
        self.fix_mean(refactor=DECLARED)
        self.edit("stats.py", "return sum(xs) / len(xs)", "total = sum(xs)\n    return total / len(xs)")
        got = self.step({"phase": "refactor", "unit_key": MEAN, "what": "式を 2 行にした"})
        self.assertTrue(got["done"], got)
        self.assertEqual(tdd.exit_fields(self.start)["units"][0]["refactor"], "ok")

    def test_red_rejects_already_passing_test(self):
        self.route()
        self.add_test(PASSING_TEST)
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                         "tests": ["test_stats.py::TestStats::test_clamp_below_range"]})
        self.assertFalse(got["ok"])
        self.assertIn("もう通る", got["reason"])
        self.assertEqual(self.st()["phase"], "test")

    def test_red_rejects_touching_outside_test_files(self):
        """test の段でテストでないファイルに書くことは拒まない。直しまで書いて名指しが通ると、書き込みでなく『もう通る』で拒む"""
        self.route()
        self.add_test(NEW_TEST)
        self.edit("stats.py", "len(xs) - 1", "len(xs)")
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                         "tests": ["test_stats.py::TestStats::test_mean_of_two"]})
        self.assertFalse(got["ok"])
        self.assertIn("もう通る", got["reason"])
        self.assertNotIn("外", got["reason"])
        self.assertEqual(self.st()["phase"], "test")
        (self.repo / "test_other.py").write_text("import unittest\n", encoding="utf-8")   # 宣言の外のテストのファイルへの書き込みは今どおり拒む
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                         "tests": ["test_stats.py::TestStats::test_mean_of_two"]})
        self.assertFalse(got["ok"])
        self.assertIn("test_other.py", got["reason"])
        self.assertIn("テストのファイルの外", got["reason"])

    def test_red_rejects_wrong_unit(self):
        self.route()
        got = self.step({"phase": "test", "unit_key": CLAMP, "test_files": ["test_stats.py"], "tests": ["x"]})
        self.assertFalse(got["ok"])
        self.assertIn(MEAN, got["reason"])

    def test_fix_rejects_frozen_test_change(self):
        self.route()
        self.red()
        self.edit("test_stats.py", "mean([2, 4]), 3", "mean([2, 4]), 6")
        got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "テストを直した"})
        self.assertFalse(got["ok"])
        self.assertIn("test_stats.py", got["reason"])

    def test_green_gives_up_and_restores_unit_head(self):
        self.route()
        before = (self.repo / "test_stats.py").read_text(encoding="utf-8")
        self.red()
        (self.repo / "helper.py").write_text("X = 1\n", encoding="utf-8")   # 直す段が足した新しいファイル
        for i in range(tdd.retry_max()):
            got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["helper.py"], "what": "直せていない"})
            self.assertFalse(got["ok"])
        self.assertTrue(got["done"], "tdd の単位が 1 つなので輪は済む")
        self.assertEqual((self.repo / "test_stats.py").read_text(encoding="utf-8"), before, "書いたテストを外す")
        self.assertFalse((self.repo / "helper.py").exists(), "単位の頭に戻す")
        u = tdd.exit_fields(self.start)["units"][0]
        self.assertEqual((u["route"], u["gave_up"]), ("parked", "green"))
        self.assertTrue(u["problems"])
        self.assertIn("緑", u["why"])

    def test_green_give_up_parks_unit_for_ruling_and_moves_on(self):
        self.route(clamp="tdd")
        before = (self.repo / "test_stats.py").read_text(encoding="utf-8")
        self.red()
        (self.repo / "helper.py").write_text("X = 1\n", encoding="utf-8")   # 直す段が足した新しいファイル
        for _ in range(tdd.retry_max()):
            got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["helper.py"], "what": "直せていない"})
            self.assertFalse(got["ok"])
        self.assertNotIn("conflict", got, "止めた申し出の出口は状態の未送の並び 1 つ")
        unsent = self.st()[tdd.UNSENT]
        self.assertEqual([r["source"] for r in unsent], [conflict.GAVE_UP_SOURCE], "3 回拒まれた単位は機械の申し出 1 件を状態の未送に積む")
        item = unsent[0]["item"]
        self.assertEqual((item["unit_key"], item["kind"], item["which_is_right"]), (MEAN, "needs_context", "unknown"))
        self.assertEqual(item["between"], [], "brief の無い run では名指しは空")
        last = got["reason"].splitlines()[0][:100]
        for w in (str(tdd.retry_max()), "緑", last, tdd.GAVE_UP_WHY):
            self.assertIn(w, item["why_both_cannot_hold"])
        st = self.st()
        self.assertEqual(st["parked"], [MEAN])
        u = st["units"][MEAN]
        self.assertEqual((u["route"], u["gave_up"]), ("parked", "green"))
        self.assertTrue(u["problems"])
        self.assertEqual((self.repo / "test_stats.py").read_text(encoding="utf-8"), before, "書いたテストを外す")
        self.assertFalse((self.repo / "helper.py").exists(), "単位の頭に戻す")
        self.assertEqual((got["done"], st["phase"], st["queue"][st["cur"]]), (False, "test", CLAMP))
        lines = "\n".join(tdd.handoff_lines(st))
        self.assertIn(f"- {MEAN}: 食い違いの申し出で止めた", lines)
        self.assertNotIn("direct に回した", lines)
        ruler = RULER.read_text(encoding="utf-8")
        self.assertIn(conflict.GAVE_UP_SOURCE, ruler, "裁定役の指示書は機械の申し出を出どころの欄 source で名指す")
        self.assertNotIn(tdd.GAVE_UP_WHY, ruler, "理由の頭の文の写しで見分けない")

    def test_role_claim_and_machine_give_up_carry_their_sources(self):
        """役の申し出（phase conflict）は source tdd、3 回拒まれて機械が止めた単位の申し出は source tdd-gave-up で未送に積まれ、
        flush_unsent が積む口にその欄のまま渡す（理由の文の写しでなく欄で見分ける。元 works/.shared/core/conflict.py:138-141、
        旧試験 works/tests/test_blk_fix_tdd.py:690 test_red_give_up_parks_machine_claim_with_source）"""
        self.route(clamp="tdd")
        got = self.step({"phase": "conflict", "unit_key": MEAN, "between": ["stats.py:9", "test_stats.py:9"],
                         "why_both_cannot_hold": "期待値と依頼の分母が食い違い、どちらを正とするか決められない",
                         "which_is_right": "unknown", "kind": "needs_context"})
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.st()["queue"][self.st()["cur"]], CLAMP)
        for _ in range(tdd.retry_max()):
            got = self.step({"phase": "test", "unit_key": CLAMP, "test_files": [], "tests": []})
            self.assertFalse(got["ok"])
        self.assertTrue(got["done"])
        parked = []
        tdd.flush_unsent(self.state, parked.extend)
        self.assertEqual([(r["source"], r["item"]["unit_key"]) for r in parked],
                         [(conflict.TDD_SOURCE, MEAN), (conflict.GAVE_UP_SOURCE, CLAMP)])
        self.assertEqual(self.st()[tdd.UNSENT], [], "渡せた行は未送から外す")

    def test_give_up_reads_briefs_before_moving_tree(self):
        """止める前に置き場の brief を読む。読めずに落ちた周は、作業ツリーを単位の頭に戻さず、状態も進めない"""
        self.route()
        self.red()
        (self.repo / "helper.py").write_text("X = 1\n", encoding="utf-8")   # 直す段が足した新しいファイル
        reply = {"phase": "fix", "unit_key": MEAN, "files": ["helper.py"], "what": "直せていない"}
        for _ in range(tdd.retry_max() - 1):
            self.assertFalse(self.step(reply)["ok"])
        with mock.patch.object(planbrief, "by_unit_at", side_effect=OSError("brief が読めない")):
            with self.assertRaises(OSError):
                self.step(reply)
        self.assertTrue((self.repo / "helper.py").exists(), "読めずに落ちたので単位の頭に戻していない")
        st = self.st()
        self.assertEqual((st["cur"], st["parked"]), (0, []))

    def test_refactor_gives_up_back_to_green_tree(self):
        self.route()
        self.red()
        self.fix_mean(refactor=DECLARED)
        green = (self.repo / "stats.py").read_text(encoding="utf-8")
        self.edit("stats.py", "return x\n", "return lo\n")   # 整えで壊す
        for _ in range(tdd.retry_max()):
            got = self.step({"phase": "refactor", "unit_key": MEAN, "what": "壊した"})
            self.assertFalse(got["ok"])
        self.assertTrue(got["done"])
        self.assertEqual((self.repo / "stats.py").read_text(encoding="utf-8"), green)
        u = tdd.exit_fields(self.start)["units"][0]
        self.assertEqual((u["route"], u["green"], u["refactor"]), ("tdd", "ok", "reverted"))

    def test_writer_can_hand_unit_to_direct(self):
        self.route()
        self.add_test(NEW_TEST)
        got = self.step({"phase": "test", "unit_key": MEAN, "direct_why": "既存の名前だけでは再現できないと分かった"})
        self.assertTrue(got["done"])
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        u = tdd.exit_fields(self.start)["units"][0]
        self.assertEqual((u["route"], u["gave_up"]), ("direct", "writer"))

    def test_runner_failure_ends_loop_all_direct(self):
        self.route(clamp="tdd")
        self.add_test(NEW_TEST)
        self.suite.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")   # JUnit を書かない
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                         "tests": ["test_stats.py::TestStats::test_mean_of_two"]})
        self.assertTrue(got["done"])
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        ex = tdd.exit_fields(self.start)
        self.assertIn("JUnit", ex["reason"])
        self.assertEqual([(u["route"], u["gave_up"]) for u in ex["units"]], [("direct", "runner"), ("direct", "runner")])

    def test_budget_ends_loop_before_max_iterations(self):
        self.route()
        st = self.st()
        st["iterations"] = tdd.MAX_ITERATIONS - 1
        pathlib.Path(self.state).write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": [], "tests": []})
        self.assertTrue(got["done"], "max_iterations に届く周で印を立てる（R50）")
        self.assertEqual(tdd.exit_fields(self.start)["units"][0]["gave_up"], "budget")

MEAN_ID = "test_stats.py::TestStats::test_mean_of_two"
WRONG_KIND_TEST = "\n    def test_mean_of_two(self):\n        import stats\n        self.assertEqual(stats.mean2([2, 4]), 3)\n"


class ContractCase(LoopCase):
    """約束を持つ run。tdd-start を plan_contract の差し替えで起こし直す（実行器は pytest に似せた PYTEST_LIKE）"""
    CONTRACT = {MEAN: {"items": [1], "route": "tdd", "rewrites": [], "refactor": [],
                       "tests": [{"id": MEAN_ID, "red_kind": "assertion"}]}}

    def setUp(self):
        super().setUp()
        self.suite.write_text(PYTEST_LIKE, encoding="utf-8")
        with mock.patch.object(tdd, "plan_contract", return_value=self.CONTRACT) as pc:
            self.start = tdd.start(self.board, self.repo, str(self.suite), OPEN)
        self.assertTrue(self.start["go"], self.start)
        self.state = self.start["state_file"]
        self.assertEqual(sorted(pc.call_args[0][1]), sorted([MEAN, CLAMP]))

    def quotes_for(self, tests):
        """名指しを実行器で 1 回走らせ、結末の failure の文から赤の引用を作る（役が結末を読んで引く代わり）。{id: {quote, why}}。
        failure の文の無い名指し（落ちていない・文を書かない実行器）は載せない"""
        with tempfile.TemporaryDirectory() as td:
            cases, _, why = tdd.run_suite(str(self.suite), self.repo, pathlib.Path(td), "q", tdd._abs_ids(self.repo, tests))
        self.assertEqual(why, [])
        out = {}
        for t in tests:
            c = tdd.rules().match_case(t, cases) or {}
            if c.get("fail_message"):
                out[t] = {"quote": c["fail_message"], "why": "今のコードの欠陥で期待どおりに落ちた（打ち間違いではない）"}
        return out

    def step(self, reply):
        """test の段の返答に red_quotes が無ければ、結末の failure の文から作って足す（red_quotes を書いた返答はそのまま。
        failure の文を書かない実行器の結末からは作れず、{} を足す）"""
        if isinstance(reply, dict) and reply.get("phase") == "test" and reply.get("tests") and tdd.QUOTES_FIELD not in reply:
            reply = {**reply, tdd.QUOTES_FIELD: self.quotes_for(reply["tests"])}
        return super().step(reply)

    def wrong_kind(self):
        """今のコードに無い名前を呼んで AttributeError で落ちるテスト（案は assertion）を書いて出す"""
        return self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"], "tests": [MEAN_ID]})


class TestPlanContract(ContractCase):
    def test_contract_lands_in_state(self):
        self.assertEqual(self.st()["contract"], self.CONTRACT)

    def test_plan_tdd_unit_cannot_be_routed_direct(self):
        got = self.step({"phase": "route", "units": [{"unit_key": MEAN, "route": "direct", "why": "文書だけの直しで書けない"},
                                                     {"unit_key": CLAMP, "route": "direct", "why": "文書だけの直しで書けない"}]})
        self.assertFalse(got["ok"])
        self.assertIn(MEAN, got["reason"])
        self.assertIn("conflict", got["reason"])
        self.assertNotIn(CLAMP, got["reason"].split("\n")[0])   # 約束の無い単位は今どおり direct に振れる

    def test_plan_tdd_unit_cannot_hand_off_by_direct_why(self):
        self.route()
        got = self.step({"phase": "test", "unit_key": MEAN, "direct_why": "既存の名前だけでは再現できないと分かった"})
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertIn("conflict", got["reason"])
        self.assertEqual((self.st()["phase"], self.st()["units"][MEAN]["route"]), ("test", "tdd"))

    def test_test_phase_must_name_plan_tests(self):
        self.route()
        self.add_test(NEW_TEST.replace("test_mean_of_two", "test_other_name"))
        runs = self.st()["runs"]
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                         "tests": ["test_stats.py::TestStats::test_other_name"]})
        self.assertFalse(got["ok"])
        self.assertIn(MEAN_ID, got["reason"])
        self.assertEqual(self.st()["runs"], runs, "実行器を走らせる前に拒む")

    def test_plan_test_named_with_dot_path_counts(self):
        """名指しのパスの部分は posixpath.normpath で整えて比べる"""
        self.route()
        self.add_test(NEW_TEST)
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                         "tests": ["./test_stats.py::TestStats::test_mean_of_two"]})
        self.assertTrue(got["ok"], got)

    def test_red_quotes_are_required_and_recorded(self):
        """約束の在る単位の test の段は、red_quotes の無い返答を拒む。結末の失敗の文（6.0 != 3）を引いた返答なら通し、単位の記録に残す"""
        self.route()
        self.add_test(NEW_TEST)
        reply = {"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"], "tests": [MEAN_ID]}
        got = self.step({**reply, tdd.QUOTES_FIELD: {}})
        self.assertFalse(got["ok"])
        self.assertIn(MEAN_ID, got["reason"])
        self.assertIn(tdd.QUOTES_FIELD, got["reason"])
        quotes = {MEAN_ID: {"quote": "6.0 != 3", "why": "mean が分母を 1 つ少なく割るので 6.0 になる（期待は 3）"}}
        got = self.step({**reply, tdd.QUOTES_FIELD: quotes})
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.st()["units"][MEAN][tdd.QUOTES_FIELD], quotes)

    def test_red_kind_matches_and_is_recorded(self):
        """赤の記録は、機械が分けた種類でなく、役が返答に書いた引用と理由（結末の失敗の文に在ると照らし済み）がそのまま残る"""
        self.route()
        self.add_test(NEW_TEST)
        quotes = {MEAN_ID: {"quote": "6.0 != 3", "why": "mean が分母を 1 つ少なく割るので 6.0 になる（期待は 3）"}}
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"], "tests": [MEAN_ID],
                         tdd.QUOTES_FIELD: quotes})
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.st()["units"][MEAN][tdd.QUOTES_FIELD], quotes)
        self.assertEqual(self.st()["units"][MEAN]["quote_unchecked"], [])

    def test_red_rejects_wrong_kind(self):
        """宣言の外の名前（AttributeError）で落ちた failure も機械は種類で拒まない。引用が結末の文に在れば赤として通り、引用が
        単位の記録に残る（打ち間違いかは役の理由と報告の行で見る）"""
        self.route()
        self.add_test(WRONG_KIND_TEST)
        got = self.wrong_kind()
        self.assertTrue(got["ok"], got)
        self.assertIn("AttributeError", self.st()["units"][MEAN][tdd.QUOTES_FIELD][MEAN_ID]["quote"])

    def test_crash_red_with_assertion_plan_passes_and_is_recorded(self):
        """今のコードが例外で落ちる種類のバグ（ZeroDivisionError）は、案が assertion でも拒まず、引いた失敗の文を記録する"""
        self.route()
        self.add_test("\n    def test_mean_of_two(self):\n        self.assertEqual(mean([5]), 5)\n")
        got = self.wrong_kind()
        self.assertTrue(got["ok"], got)
        self.assertIn("ZeroDivisionError", self.st()["units"][MEAN][tdd.QUOTES_FIELD][MEAN_ID]["quote"])

    def test_name_error_red_with_assertion_plan_rejected(self):
        """NameError の failure も機械は種類で拒まず、引用が結末の文に在れば赤として通る"""
        self.route()
        self.add_test("\n    def test_mean_of_two(self):\n        self.assertEqual(mean_of([2, 4]), 3)\n")
        got = self.wrong_kind()
        self.assertTrue(got["ok"], got)
        self.assertIn("NameError", self.st()["units"][MEAN][tdd.QUOTES_FIELD][MEAN_ID]["quote"])

    def test_wrong_kind_three_times_gives_up_and_parks_for_ruling(self):
        """結末に無い引用で 3 回拒まれ、食い違いの申し出で止めて裁定に回し、木が単位の頭に戻る（gave_up red）"""
        self.route()
        head = (self.repo / "test_stats.py").read_text(encoding="utf-8")
        self.add_test(WRONG_KIND_TEST)
        made_up = {MEAN_ID: {"quote": "結末に無い作り話の失敗の文", "why": "期待どおりの理由で落ちたと思う（作り話）"}}
        for _ in range(tdd.retry_max()):
            got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"], "tests": [MEAN_ID],
                             tdd.QUOTES_FIELD: made_up})
            self.assertFalse(got["ok"])
        self.assertTrue(got["done"], "tdd の単位が 1 つなので輪は済む")
        self.assertEqual((self.repo / "test_stats.py").read_text(encoding="utf-8"), head, "作業ツリーは単位の頭")
        u = self.st()["units"][MEAN]
        self.assertEqual((u["route"], u["gave_up"]), ("parked", "red"))

    def test_unknown_kind_is_recorded_not_rejected(self):
        """実行器が failure に message も本文も書かず（SUITE）、ログも空なら、引用を照らす先が無い。引用なしに拒まず通し、
        単位の quote_unchecked にその名指しを残す"""
        self.suite.write_text(SUITE, encoding="utf-8")
        self.route()
        self.red()
        u = self.st()["units"][MEAN]
        self.assertEqual((u[tdd.QUOTES_FIELD], u["quote_unchecked"]), ({}, [MEAN_ID]))

    def test_missing_named_test_then_stub_outside_test_files_passes(self):
        """まだ無い名を読むテストで名指しが一式に居ない回は、NOT_RAN つきで拒まれる。仮の実装を足して出し直すと赤が通り、
        単位の stub_files に仮の実装のファイルが残る"""
        self.route()
        self.edit("test_stats.py", "from stats import clamp, mean", "from stats import average, clamp, mean")
        self.add_test("\n    def test_mean_of_two(self):\n        self.assertEqual(average([2, 4]), 3)\n")
        reply = {"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"], "tests": [MEAN_ID]}
        got = self.step(reply)
        self.assertFalse(got["ok"])
        self.assertIn("一式の結末に居ない", got["reason"])
        self.assertIn(tdd.NOT_RAN, got["reason"])
        self.edit("stats.py", "def clamp(", "def average(xs):\n    return 0\n\n\ndef clamp(")   # 最小の仮の実装（形だけ）
        got = self.step(reply)
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.st()["units"][MEAN]["stub_files"], ["stats.py"])
        self.assertTrue(self.st()["units"][MEAN]["red_tree"])


class TestNoContract(LoopCase):
    def test_no_contract_same_as_before(self):
        """約束の無い run（LoopCase）は、名指しの名前を見ず、red_quotes も求めない。引用を照らす先の無い名指しは quote_unchecked に残る"""
        self.assertEqual(self.st()["contract"], {})
        self.assertEqual(tdd.plan_contract(self.board, [MEAN, CLAMP]), {}, "欄の控えの無い置き場は空")
        self.route()
        self.add_test(NEW_TEST.replace("test_mean_of_two", "test_other_name"))
        other = "test_stats.py::TestStats::test_other_name"
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"], "tests": [other]})
        self.assertTrue(got["ok"], got)
        u = self.st()["units"][MEAN]
        self.assertEqual((u[tdd.QUOTES_FIELD], u["quote_unchecked"]), ({}, [other]))

    def test_board_without_fields_has_no_contract(self):
        """欄の控えが無ければ（frozen_fields が None）約束は空。置き場と周をそのまま渡す"""
        with mock.patch.object(tdd.conflict, "frozen_fields", return_value=None) as ff:
            self.assertEqual(tdd.plan_contract(self.board, [MEAN, CLAMP], 2), {})
        self.assertEqual(ff.call_args.args, (self.board, 2))


REWRITE = "test_stats.py::TestStats::test_clamp_above_range"


class TestPlanRewrites(ContractCase):
    """修正案が書き換えを名指した既存のテスト（約束の rewrites）は、テストの段の名指しに入れて同じ赤→緑の関門を通す。
    名指しの外の既存のテストの本体（.py の test* 関数）は凍っている"""
    CONTRACT = {CLAMP: {"items": [1], "route": "tdd", "tests": [], "rewrites": [REWRITE], "refactor": []}}

    def rewrite(self):
        self.edit("test_stats.py", "self.assertEqual(clamp(15, 0, 10), 10)",
                  "self.assertEqual(clamp(15, 0, 10), 10)\n        self.assertEqual(clamp(99, 0, 10), 10)")

    def test_rewrite_must_be_named(self):
        self.route(mean="direct", clamp="tdd"); self.rewrite()
        got = self.step({"phase": "test", "unit_key": CLAMP, "test_files": ["test_stats.py"], "tests": []})
        self.assertFalse(got["ok"]); self.assertIn(REWRITE, got["reason"])

    def test_rewrite_red_then_green_then_frozen(self):
        self.route(mean="direct", clamp="tdd"); self.rewrite()
        got = self.step({"phase": "test", "unit_key": CLAMP, "test_files": ["test_stats.py"], "tests": [REWRITE]})
        self.assertTrue(got["ok"], got)
        self.edit("stats.py", "    if x > hi:\n        return lo", "    if x > hi:\n        return hi")
        got = self.step({"phase": "fix", "unit_key": CLAMP, "files": ["stats.py"], "what": "上限の枝で hi を返す"})
        self.assertTrue(got["ok"], got)
        if self.st()["phase"] == "refactor":   # Task 4 の前は整えの段が来る。後は申告なしで done
            self.step({"phase": "refactor", "unit_key": CLAMP, "what": "整える物は無い"})
        self.assertTrue(self.st()["done"])
        self.assertIn("test_stats.py", self.st()["frozen"])

    def test_unnamed_existing_test_edit_rejected(self):
        self.route(mean="direct", clamp="tdd"); self.rewrite()
        self.edit("test_stats.py", "self.assertEqual(clamp(5, 0, 10), 5)", "self.assertTrue(True)")
        got = self.step({"phase": "test", "unit_key": CLAMP, "test_files": ["test_stats.py"], "tests": [REWRITE]})
        self.assertFalse(got["ok"])
        self.assertIn("test_stats.py::TestStats::test_clamp_within_range", got["reason"])

    def test_import_and_new_test_edits_pass(self):
        self.route(mean="direct", clamp="tdd"); self.rewrite()
        self.edit("test_stats.py", "from stats import clamp, mean", "from stats import clamp, mean  # noqa")
        self.add_test("\n    def test_clamp_at_hi(self):\n        self.assertEqual(clamp(10, 0, 10), 10)\n")
        got = self.step({"phase": "test", "unit_key": CLAMP, "test_files": ["test_stats.py"], "tests": [REWRITE]})
        self.assertTrue(got["ok"], got)

    def test_rewrite_still_green_is_rejected(self):
        """書き換えが今のコードで通る（clamp(5, 0, 10) の行に書き換えた）→ 写しの red_problems の『もう通る』"""
        self.route(mean="direct", clamp="tdd")
        self.edit("test_stats.py", "self.assertEqual(clamp(15, 0, 10), 10)", "self.assertEqual(clamp(5, 0, 10), 5)")
        got = self.step({"phase": "test", "unit_key": CLAMP, "test_files": ["test_stats.py"], "tests": [REWRITE]})
        self.assertFalse(got["ok"])
        self.assertIn(REWRITE, got["reason"])
        self.assertIn("もう通る", got["reason"])

    def test_rewrite_name_error_red_is_rejected(self):
        """書き換えが今のコードに無い名前で落ちる（NameError）赤も、機械は種類で拒まない。引用が結末の文に在れば赤として通り、
        red_quotes が単位の記録に残る"""
        self.route(mean="direct", clamp="tdd")
        self.edit("test_stats.py", "self.assertEqual(clamp(15, 0, 10), 10)", "self.assertEqual(clamp_to(15, 0, 10), 10)")
        got = self.step({"phase": "test", "unit_key": CLAMP, "test_files": ["test_stats.py"], "tests": [REWRITE]})
        self.assertTrue(got["ok"], got)
        self.assertIn("NameError", self.st()["units"][CLAMP][tdd.QUOTES_FIELD][REWRITE]["quote"])
        self.assertEqual(self.st()["phase"], "fix")

    def test_unnamed_edit_rejected_before_running(self):
        """名指しの外の書き換えは実行器を走らせる前に拒む"""
        self.route(mean="direct", clamp="tdd"); self.rewrite()
        self.edit("test_stats.py", "self.assertEqual(clamp(5, 0, 10), 5)", "self.assertTrue(True)")
        runs = self.st()["runs"]
        got = self.step({"phase": "test", "unit_key": CLAMP, "test_files": ["test_stats.py"], "tests": [REWRITE]})
        self.assertFalse(got["ok"])
        self.assertIn("rewrite_tests", got["reason"])
        self.assertEqual(self.st()["runs"], runs)


class TestPlanVanishedTests(ContractCase):
    """約束の在る単位のテストの段: 元の結末で通っていたテストが飛ばされた・結末から消えたら拒む（名指しの外の本体を変えずに
    クラスの setUp・モジュールの末尾で外す抜け道）"""
    CONTRACT = TestPlanRewrites.CONTRACT

    def red_with(self, old, new):
        self.route(mean="direct", clamp="tdd")
        self.edit("test_stats.py", "self.assertEqual(clamp(15, 0, 10), 10)", "self.assertEqual(clamp(99, 0, 10), 10)")
        self.edit("test_stats.py", old, new)
        return self.step({"phase": "test", "unit_key": CLAMP, "test_files": ["test_stats.py"], "tests": [REWRITE]})

    def test_skipped_in_setup_rejected(self):
        got = self.red_with("class TestStats(unittest.TestCase):\n",
                            "class TestStats(unittest.TestCase):\n    def setUp(self):\n"
                            "        if self._testMethodName == \"test_clamp_within_range\":\n            self.skipTest(\"外す\")\n\n")
        self.assertFalse(got["ok"])
        self.assertIn("test_clamp_within_range", got["reason"])
        self.assertIn("skipped", got["reason"])

    def test_syntax_error_named_as_such(self):
        """テストのファイルが構文として読めなければ、関数を全部『書き換えた』と並べず、構文の誤りとして名指す"""
        got = self.red_with("\n\nif __name__", "\n\ndef (\n\nif __name__")
        self.assertFalse(got["ok"])
        self.assertIn("構文", got["reason"])
        self.assertNotIn("test_clamp_within_range", got["reason"])


OTHER_TEST = ("import os\nimport unittest\n\nfrom stats import clamp\n\n\nclass TestOther(unittest.TestCase):\n"
              "    def test_low(self):\n        self.assertEqual(clamp(-1, 0, 10), 0)\n")
LOW_KEY = "test_other.TestOther::test_low"
OTHER_SKIP = ("class TestOther(unittest.TestCase):\n",
              "class TestOther(unittest.TestCase):\n    def setUp(self):\n        self.skipTest(\"外す\")\n\n")
OTHER_DEL = ("        self.assertEqual(clamp(-1, 0, 10), 0)\n",
             "        self.assertEqual(clamp(-1, 0, 10), 0)\n\n\ndel TestOther.test_low\n")
# PYTEST_LIKE の写しで、後ろに試験を渡されたらそれだけを走らせる実行器（`pytest --junitxml="$1" "${@:2}"` の形。node id は
# その名のテスト、:: の無いパスはそのファイルのモジュールの全部）。gate が真なら、後ろの試験だけにするのは TDD_SUITE_ONLY=1 の時だけ
def _only_runner(gate):
    return PYTEST_LIKE.replace(
        'unittest.defaultTestLoader.discover(".", pattern="test_*.py", top_level_dir=".").run(R())',
        'import os, pathlib\n'
        'def flat(s):\n'
        '    for x in s:\n'
        '        yield from (flat(x) if isinstance(x, unittest.TestSuite) else [x])\n'
        'tests = list(flat(unittest.defaultTestLoader.discover(".", pattern="test_*.py", top_level_dir=".")))\n'
        'if sys.argv[2:] and ' + ('os.environ.get("TDD_SUITE_ONLY") == "1"' if gate else 'True') + ':\n'
        '    names = {a.rsplit("::", 1)[-1] for a in sys.argv[2:] if "::" in a}\n'
        '    mods = {pathlib.Path(a).stem for a in sys.argv[2:] if "::" not in a}\n'
        '    tests = [t for t in tests if t.id().rsplit(".", 1)[-1] in names or t.id().split(".", 1)[0] in mods]\n'
        'unittest.TestSuite(tests).run(R())')


NAMED_ONLY = _only_runner(False)
ONLY_AWARE = _only_runner(True)   # TDD_SUITE_ONLY=1 を解く実行器（輪の赤・緑の回は後ろの試験だけ。元の結末は一式）


def _with_other_test(case, body=OTHER_TEST):
    """case の setUp の tdd.start の前に、対象リポジトリへ既存のテストのファイル test_other.py を置く（元の結末にも載る）"""
    orig = tdd.start

    def start(board_dir, repo, *a, **k):
        other = pathlib.Path(repo) / "test_other.py"
        if not other.exists():
            other.write_text(body, encoding="utf-8")
        return orig(board_dir, repo, *a, **k)
    return mock.patch.object(tdd, "start", start)


class TestFixPhaseFreezesOtherTests(ContractCase):
    """約束の在る単位の直し・整えの段で、単位のテストのファイルの外の既存のテスト（テストのファイルの名の .py の test* 関数）を
    書き換えたら拒む"""
    CONTRACT = {CLAMP: {**TestPlanRewrites.CONTRACT[CLAMP],   # 整えの段を申告で必ず通す
                        "refactor": [{"item": 1, "why": "テストの補助の重なりを寄せる"}]}}
    LOW = "test_other.py::TestOther::test_low"

    def setUp(self):
        with _with_other_test(self):
            super().setUp()

    def red(self):
        self.route(mean="direct", clamp="tdd")
        self.edit("test_stats.py", "self.assertEqual(clamp(15, 0, 10), 10)", "self.assertEqual(clamp(99, 0, 10), 10)")
        got = self.step({"phase": "test", "unit_key": CLAMP, "test_files": ["test_stats.py"], "tests": [REWRITE]})
        self.assertTrue(got["ok"], got)
        self.edit("stats.py", "    if x > hi:\n        return lo", "    if x > hi:\n        return hi")

    def test_fix_phase_edit_of_other_test_rejected(self):
        self.red()
        self.edit("test_other.py", "self.assertEqual(clamp(-1, 0, 10), 0)", "self.assertTrue(True)")
        got = self.step({"phase": "fix", "unit_key": CLAMP, "files": ["stats.py", "test_other.py"], "what": "上限の枝で hi を返す"})
        self.assertFalse(got["ok"])
        self.assertIn(self.LOW, got["reason"])

    def test_refactor_phase_edit_of_other_test_rejected(self):
        self.red()
        got = self.step({"phase": "fix", "unit_key": CLAMP, "files": ["stats.py"], "what": "上限の枝で hi を返す"})
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.st()["phase"], "refactor")
        self.edit("test_other.py", "self.assertEqual(clamp(-1, 0, 10), 0)", "self.assertTrue(True)")
        got = self.step({"phase": "refactor", "unit_key": CLAMP, "what": "テストの補助を整えた"})
        self.assertFalse(got["ok"])
        self.assertIn(self.LOW, got["reason"])

    def fix_with(self, old, new):
        self.red()
        self.edit("test_other.py", old, new)
        return self.step({"phase": "fix", "unit_key": CLAMP, "files": ["stats.py"], "what": "上限の枝で hi を返す"})

    def refactor_with(self, old, new):
        self.red()
        got = self.step({"phase": "fix", "unit_key": CLAMP, "files": ["stats.py"], "what": "上限の枝で hi を返す"})
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.st()["phase"], "refactor")
        self.edit("test_other.py", old, new)
        return self.step({"phase": "refactor", "unit_key": CLAMP, "what": "テストの補助を整えた"})

    def assert_vanished(self, got, outcome):
        self.assertFalse(got["ok"])
        self.assertIn(LOW_KEY, got["reason"])
        self.assertIn(outcome, got["reason"])
        self.assertIn(CLAMP, got["reason"], "変えた単位を名指す")

    def test_fix_phase_skip_rejected(self):
        self.assert_vanished(self.fix_with(*OTHER_SKIP), "skipped")

    def test_fix_phase_del_rejected(self):
        self.assert_vanished(self.fix_with(*OTHER_DEL), "missing")

    def test_refactor_phase_skip_rejected(self):
        self.assert_vanished(self.refactor_with(*OTHER_SKIP), "skipped")

    def test_refactor_phase_del_rejected(self):
        self.assert_vanished(self.refactor_with(*OTHER_DEL), "missing")

    def test_fix_phase_syntax_error_named_as_such(self):
        got = self.fix_with("    def test_low(self):\n", "    def test_low(self:\n")
        self.assertFalse(got["ok"])
        self.assertIn("構文", got["reason"])
        self.assertIn("test_other.py", got["reason"])

    def test_test_functions_in_implementation_files_not_frozen(self):
        """テストのファイルの名でない .py（実装）の test* 関数は見ない"""
        self.red()
        self.edit("stats.py", "def mean(xs):", "def test_helper():\n    return 1\n\n\ndef mean(xs):")
        got = self.step({"phase": "fix", "unit_key": CLAMP, "files": ["stats.py"], "what": "上限の枝で hi を返す"})
        self.assertTrue(got["ok"], got)


class TestFixPhaseFreezesOtherTestsOnlyRunner(TestFixPhaseFreezesOtherTests):
    """同じ確かめを TDD_SUITE_ONLY=1 を解く実行器で: 緑の回は名指しと届いたモジュールのファイルだけなので、消えた（missing）は
    同じ選びの回でなく、その回にファイルごと走ったモジュール（whole）から外れた物として拾う"""

    def setUp(self):
        super().setUp()
        self.suite.write_text(ONLY_AWARE, encoding="utf-8")

    def test_green_run_was_narrowed(self):
        self.red()
        got = self.step({"phase": "fix", "unit_key": CLAMP, "files": ["stats.py"], "what": "上限の枝で hi を返す"})
        self.assertTrue(got["ok"], got)
        run = self.st()["green_run"]
        self.assertFalse(run["full"])
        self.assertEqual(sorted(run["whole"]), ["test_other", "test_stats"])


OTHER_GO = "package stats\n\nfunc TestLow(t *testing.T) {\n\tif Clamp(-1, 0, 10) != 0 {\n\t\tt.Fatal(\"low\")\n\t}\n}\n"


class TestFixPhaseFreezesNonPythonTests(ContractCase):
    """.py でない既存のテストのファイル（名の慣習か宣言で見分ける）も、直し・整えの段で行を消した・置き換えたら拒む
    （関数の幅は言語に依らず引けないので、足すだけの差分だけを通す）"""
    CONTRACT = TestFixPhaseFreezesOtherTests.CONTRACT

    def setUp(self):
        orig = tdd.start

        def start(board_dir, repo, *a, **k):
            other = pathlib.Path(repo) / "stats_test.go"
            if not other.exists():
                other.write_text(OTHER_GO, encoding="utf-8")
                (pathlib.Path(repo) / "KeySpec.java").write_text("class KeySpec { int v = 1; }\n", encoding="utf-8")
            return orig(board_dir, repo, *a, **k)
        with mock.patch.object(tdd, "start", start):
            super().setUp()

    red = TestFixPhaseFreezesOtherTests.red

    def test_fix_phase_edit_of_non_python_test_rejected(self):
        self.red()
        self.edit("stats_test.go", "Clamp(-1, 0, 10) != 0", "false")
        got = self.step({"phase": "fix", "unit_key": CLAMP, "files": ["stats.py", "stats_test.go"], "what": "上限の枝で hi を返す"})
        self.assertFalse(got["ok"], got)
        self.assertIn("stats_test.go", got["reason"])

    def test_fix_phase_edit_of_spec_named_implementation_passes(self):
        """名の尾が Spec でもテストのフォルダの外の実装（KeySpec.java）は凍らせない（直しの段で直してよい）"""
        self.red()
        self.edit("KeySpec.java", "int v = 1;", "int v = 2;")
        got = self.step({"phase": "fix", "unit_key": CLAMP, "files": ["stats.py", "KeySpec.java"], "what": "上限の枝で hi を返す"})
        self.assertTrue(got["ok"], got)

    def test_fix_phase_append_to_non_python_test_passes(self):
        self.red()
        self.edit("stats_test.go", "\t}\n}\n", "\t}\n}\n\nfunc helper() int { return 1 }\n")
        got = self.step({"phase": "fix", "unit_key": CLAMP, "files": ["stats.py", "stats_test.go"], "what": "上限の枝で hi を返す"})
        self.assertTrue(got["ok"], got)


class TestFixPhaseOtherTestsWithoutContract(LoopCase):
    def setUp(self):
        with _with_other_test(self):
            super().setUp()

    def test_no_contract_same_as_before(self):
        """約束の無い run の直しの段は、ほかのテストのファイルの書き換えを今どおり見ない"""
        self.route()
        self.red()
        self.edit("test_other.py", "self.assertEqual(clamp(-1, 0, 10), 0)", "self.assertTrue(True)")
        self.fix_mean()


class TestNamedOnlyRunner(ContractCase):
    """後ろの node id だけを走らせる実行器: 名指しの外のテストは結末に居ないが、単位の頭の結末と選び（後ろの引数）が違う回の
    居ないは消えたに数えない（輪は通る）"""
    CONTRACT = TestPlanRewrites.CONTRACT

    def setUp(self):
        with _with_other_test(self):
            super().setUp()
        self.suite.write_text(NAMED_ONLY, encoding="utf-8")

    def test_loop_passes(self):
        self.route(mean="direct", clamp="tdd")
        self.edit("test_stats.py", "self.assertEqual(clamp(15, 0, 10), 10)", "self.assertEqual(clamp(99, 0, 10), 10)")
        got = self.step({"phase": "test", "unit_key": CLAMP, "test_files": ["test_stats.py"], "tests": [REWRITE]})
        self.assertTrue(got["ok"], got)
        self.edit("stats.py", "    if x > hi:\n        return lo", "    if x > hi:\n        return hi")
        got = self.step({"phase": "fix", "unit_key": CLAMP, "files": ["stats.py"], "what": "上限の枝で hi を返す"})
        self.assertTrue(got["ok"], got)


class TestUntouchedModuleSkipIgnored(ContractCase):
    """触れていないモジュールのテストが環境で飛ばされても（単位の頭から変わったテストのファイルの外）、消えたに数えない"""
    CONTRACT = TestPlanRewrites.CONTRACT

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.flag = pathlib.Path(td.name) / "skip.flag"
        body = OTHER_TEST.replace("    def test_low(self):\n", "    def test_low(self):\n"
                                  f"        if os.path.exists({str(self.flag)!r}):\n            self.skipTest(\"環境\")\n")
        with _with_other_test(self, body):
            super().setUp()

    def test_env_skip_in_untouched_module_passes(self):
        self.route(mean="direct", clamp="tdd")
        self.edit("test_stats.py", "self.assertEqual(clamp(15, 0, 10), 10)", "self.assertEqual(clamp(99, 0, 10), 10)")
        self.flag.write_text("x", encoding="utf-8")
        got = self.step({"phase": "test", "unit_key": CLAMP, "test_files": ["test_stats.py"], "tests": [REWRITE]})
        self.assertTrue(got["ok"], got)
        self.edit("stats.py", "    if x > hi:\n        return lo", "    if x > hi:\n        return hi")
        got = self.step({"phase": "fix", "unit_key": CLAMP, "files": ["stats.py"], "what": "上限の枝で hi を返す"})
        self.assertTrue(got["ok"], got)


class TestVanished(Case):
    """消えたテストの照らし（tdd._vanished。純粋）"""
    HEAD = {"outcome": {"test_x.T::test_a[1]": "passed", "test_x.T::test_b": "passed", "test_y.U::test_c": "passed",
                        "test_x.T::test_s": "skipped"}, "args": []}

    def test_parametrized_rewrite_and_verified_excluded(self):
        now = {"test_x.T::test_a[2]": "passed", "test_x.T::test_b": "skipped", "test_y.U::test_c": "passed"}
        self.assertEqual(tdd._vanished(self.HEAD, [self.HEAD], now, [], None, ["t/test_x.py::T::test_a", "./test_x.py::T::test_b"]),
                         [])
        self.assertEqual(tdd._vanished(self.HEAD, [self.HEAD], now, [], None, ["t/test_x.py::T::test_a"]),
                         [("test_x.T::test_b", "skipped")])

    def test_absent_counts_only_with_same_selection(self):
        now = {"test_x.T::test_b": "passed"}
        self.assertEqual(tdd._vanished(self.HEAD, [self.HEAD], now, ["x::y"], None, []), [], "選びが違う")
        self.assertEqual(sorted(tdd._vanished(self.HEAD, [self.HEAD], now, [], None, [])),
                         [("test_x.T::test_a[1]", "missing"), ("test_y.U::test_c", "missing")])

    def test_absent_counts_in_module_run_whole(self):
        now = {"test_x.T::test_b": "passed"}
        self.assertEqual(tdd._vanished(self.HEAD, [self.HEAD], now, ["x::y"], None, [], whole={"test_x"}),
                         [("test_x.T::test_a[1]", "missing")], "ファイルごと走ったモジュールから消えた（test_y は走っていない）")

    def test_head_merges_partial_green_run(self):
        prev = {"outcome": {"test_x.T::a": "passed", "test_x.T::gone": "passed", "test_y.U::c": "passed"}, "args": []}
        run = {"outcome": {"test_x.T::a": "failure", "test_x.T::new": "passed"}, "args": ["test_x.py"], "whole": ["test_x"],
               "full": False}
        self.assertEqual(tdd._next_head(prev, run),
                         {"outcome": {"test_x.T::a": "failure", "test_x.T::new": "passed", "test_y.U::c": "passed"},
                          "args": None, "whole": [], "full": False})
        full = {**run, "full": True, "whole": []}
        self.assertEqual(tdd._next_head(prev, full), full, "一式の回はそのまま次の単位の頭")

    def test_scope_limits_modules(self):
        now = {}
        self.assertEqual(tdd._vanished(self.HEAD, [self.HEAD], now, [], {"test_y"}, []), [("test_y.U::test_c", "missing")])

    def test_scope_of_touched_files(self):
        self.assertEqual(tdd._vanish_scope(["a/test_y.py", "stats.py", "b/x_test.py"]), {"test_y", "x_test"})
        self.assertIsNone(tdd._vanish_scope(["test_y.py", "tests/conftest.py"]), "conftest.py に触れたら一式")

    def test_vanish_scope_non_python_is_whole(self):
        # .py でないテストのファイルは JUnit の行とモジュールを言語に依らず結べない——分からない＝一式の全部を照らす
        self.assertIsNone(tdd._vanish_scope(["a/test_y.py", "pkg/calc_test.go"]))


class TestTestFileIdentity(Case):
    """テストのファイルの見分け: 宣言（単位の申告・約束の tests と rewrites のパス）を正本に、名の慣習（impact.is_test）を予備に"""

    def test_declared_test_files_from_state(self):
        st = {"units": {"u1": {"test_files": ["./a/checks.go", " d/x_test.py ", None, "", 3]}, "u2": {}, "u3": {"test_files": 5},
                        "u4": {"test_files": "e.py"}},
              "contract": {"u1": {"tests": [{"id": "b/verify.kt::Verify::adds"}], "rewrites": ["./c/legacy.rb::old"]},
                           "u2": None}}
        self.assertEqual(tdd.declared_test_files(st), {"a/checks.go", "d/x_test.py", "b/verify.kt", "c/legacy.rb"})

    def test_writer_and_reader_share_the_test_file_rule(self):
        """test_files の要素の決まりは board.test_file の 1 か所: 書き手（tdd._paths）が整えた並びを読み手
        （board.unit_test_files）は同じに読み、決まりに外れた要素は書き手が並びごと拒み、読み手が落とす（#343）"""
        files = ["./a/x_test.py", " b/y_test.py "]
        written, problems = tdd._paths(files, "test_files")
        self.assertEqual((written, problems), (["a/x_test.py", "b/y_test.py"], []))
        self.assertEqual(board.unit_test_files({"test_files": files}), written)
        self.assertEqual(board.unit_test_files({"test_files": written}), written)
        for bad in ([*files, None], [*files, "  "], [], "a/x_test.py"):
            with self.subTest(bad=bad):
                self.assertEqual(tdd._paths(bad, "test_files")[0], [])
                self.assertEqual(board.unit_test_files({"test_files": bad}), written if isinstance(bad, list) and bad else [])


class TestRewriteSharedAcrossUnits(ContractCase):
    """1 つの項目が 2 つの単位にまたがると、同じ書き換えの名指しが両方の単位の約束に載る。前の単位で赤→緑を確かめた id は、
    後の単位で名指しを強いない（もう通るので強いると後の単位は必ず落ちる）。確かめた後は凍っていて、後の単位では書き換えられない"""
    CONTRACT = {CLAMP: {"items": [1], "route": "tdd", "tests": [], "rewrites": [REWRITE], "refactor": []},
                MEAN: {"items": [1], "route": "tdd", "tests": [{"id": MEAN_ID, "red_kind": "assertion"}], "rewrites": [REWRITE],
                       "refactor": []}}

    def clamp_done(self):
        got = self.step({"phase": "route", "units": [{"unit_key": CLAMP, "route": "tdd"}, {"unit_key": MEAN, "route": "tdd"}]})
        self.assertTrue(got["ok"], got)
        self.edit("test_stats.py", "self.assertEqual(clamp(15, 0, 10), 10)",
                  "self.assertEqual(clamp(15, 0, 10), 10)\n        self.assertEqual(clamp(99, 0, 10), 10)")
        got = self.step({"phase": "test", "unit_key": CLAMP, "test_files": ["test_stats.py"], "tests": [REWRITE]})
        self.assertTrue(got["ok"], got)
        self.edit("stats.py", "    if x > hi:\n        return lo", "    if x > hi:\n        return hi")
        got = self.step({"phase": "fix", "unit_key": CLAMP, "files": ["stats.py"], "what": "上限の枝で hi を返す"})
        self.assertTrue(got["ok"], got)
        if self.st()["phase"] == "refactor":
            self.step({"phase": "refactor", "unit_key": CLAMP, "what": "整える物は無い"})
        self.assertEqual(self.st()["queue"][self.st()["cur"]], MEAN)

    def test_verified_rewrite_not_forced_in_later_unit(self):
        self.clamp_done()
        self.add_test(NEW_TEST)
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"], "tests": [MEAN_ID]})
        self.assertTrue(got["ok"], got)

    def test_verified_rewrite_frozen_in_later_unit(self):
        self.clamp_done()
        self.add_test(NEW_TEST)
        self.edit("test_stats.py", "self.assertEqual(clamp(99, 0, 10), 10)", "self.assertEqual(clamp(98, 0, 10), 10)")
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"], "tests": [MEAN_ID]})
        self.assertFalse(got["ok"])
        self.assertIn(REWRITE, got["reason"])


def pasted_line(text: str, head: str) -> set:
    """修正役の指示書の節（planrange.tests_text）の head で始まる行のバッククオートの名"""
    (line,) = [ln for ln in text.splitlines() if ln.lstrip().startswith(head)]
    return set(re.findall(r"`([^`]+)`", line.split("）: ", 1)[1]))


class TestPastedVerifiedRewrite(ContractCase):
    """#603: 輪が赤→緑を確かめた書き換えは、指示書の「本体を変えてよい名指し」から外れ「もう変えるな」の行に在り、凍ったテストの確かめ
    （facts.check_frozen）がその変更を拒む。貼る値と拒む値は facts.frozen_tests の verified（check_frozen と同じ _verified）"""
    CONTRACT = TestPlanRewrites.CONTRACT

    def test_verified_rewrite_is_pasted_as_frozen_and_rejected(self):
        import planmarks
        import planrange
        self.route(mean="direct", clamp="tdd")
        self.edit("test_stats.py", "self.assertEqual(clamp(15, 0, 10), 10)",
                  "self.assertEqual(clamp(15, 0, 10), 10)\n        self.assertEqual(clamp(99, 0, 10), 10)")
        self.assertTrue(self.step({"phase": "test", "unit_key": CLAMP, "test_files": ["test_stats.py"], "tests": [REWRITE]})["ok"])
        self.edit("stats.py", "    if x > hi:\n        return lo", "    if x > hi:\n        return hi")
        self.assertTrue(self.step({"phase": "fix", "unit_key": CLAMP, "files": ["stats.py"], "what": "上限の枝で hi を返す"})["ok"])
        if self.st()["phase"] == "refactor":
            self.step({"phase": "refactor", "unit_key": CLAMP, "what": "整える物は無い"})
        self.assertTrue(self.st()["done"])
        planmarks.save(self.board, 1, [{"unit_keys": [CLAMP], "route": "tdd", "route_why": "", "tests": [],
                                        "rewrite_tests": [{"id": REWRITE, "behavior": "上限を超えた値", "old": "10 だけ",
                                                           "new": "99 も 10 に", "limit": "test_stats.py:14"}],
                                        "refactor": {"declared": False, "why": ""}}])
        edits = conflict.edit_permits(self.board, "first")
        self.assertIn(REWRITE, edits["tests"], "事後の関門は id で許す")
        text = planrange.tests_text(None, edits, facts.frozen_tests(self.board, self.state, "first"))
        self.assertNotIn(REWRITE, pasted_line(text, "- 本体を変えてよい既存のテストの名指し"))
        self.assertEqual(pasted_line(text, "- ループが書き換えて凍らせた名指し"), {REWRITE})
        self.assertEqual(facts.check_frozen(self.board, self.state, self.repo, "first"), [])
        self.edit("test_stats.py", "clamp(99, 0, 10), 10)", "clamp(98, 0, 10), 10)")
        got = facts.check_frozen(self.board, self.state, self.repo, "first")
        self.assertTrue(got and "test_stats.py" in got[0], got)


class TestPastedUnruledFrozen(LoopCase):
    """#603: 2 回目の修正の段（conflict.second_pass）の first では、事後の関門は裁定 fix_test_scope の範囲を許す（conflict.edit_rulings）が、
    凍ったテストの確かめは今の輪の凍ったファイルを裁定の範囲で解かない。指示書はそのファイルを字のまま貼り、段 ruled では貼らない。
    貼る側（facts.frozen_tests の unruled）と拒む側（check_frozen）の片方だけ変えれば赤"""

    def test_unruled_files_are_what_check_frozen_keeps_frozen_under_rulings(self):
        import planrange
        self.route()
        self.red()
        self.assertTrue(self.fix_mean()["done"])
        rows = [{"id": "c1-1", "unit_key": MEAN, "between": ["stats.py:9", "test_stats.py:9"],
                 "why_both_cannot_hold": "期待の型が依頼と食い違う", "which_is_right": "test", "status": "ruled",
                 "ruling": {"decision": "fix_test_scope", "text": "期待を書き直してよい", "limits": ["test_stats.py"]}},
                {"id": "c1-2", "unit_key": CLAMP, "between": ["stats.py:12", "test_stats.py:12"],
                 "why_both_cannot_hold": "案の項目が誤り", "which_is_right": "request", "status": "ruled",
                 "ruling": {"decision": conflict.REPLAN, "text": "項目を直せ", "limits": []}, conflict.REPLAN_STATE: conflict.AMENDED}]
        (self.board / conflict.FILE).write_text(json.dumps({"items": rows}, ensure_ascii=False), encoding="utf-8")
        self.assertTrue(conflict.second_pass(self.board))
        self.edit("test_stats.py", "mean([2, 4]), 3", "mean([2, 4]), 3.0")   # 裁定の範囲の中で、輪が凍らせたテストを変えた
        for pass_, frozen in (("first", True), ("ruled", False)):
            with self.subTest(pass_=pass_):
                edits = conflict.edit_permits(self.board, pass_)
                self.assertIn("test_stats.py", edits["limits"], "事後の関門は裁定の範囲を許す")
                got = facts.frozen_tests(self.board, self.state, pass_)
                self.assertEqual(got["unruled"], ["test_stats.py"] if frozen else [])
                text = planrange.tests_text(None, edits, got)
                head = "- 今の段の TDD のループが凍らせたファイル"
                if frozen:
                    self.assertEqual(pasted_line(text, head), {"test_stats.py"})
                else:
                    self.assertNotIn(head, text)
                problems = facts.check_frozen(self.board, self.state, self.repo, pass_)
                self.assertEqual(bool(problems), frozen, problems)


SAME_ITEM_TESTS = [{"id": MEAN_ID, "red_kind": "assertion"}, {"id": "test_stats.py::TestStats::test_clamp_far_above",
                                                              "red_kind": "assertion"}]
SAME_ITEM_FAR = """
    def test_clamp_far_above(self):
        self.assertEqual(clamp(20, 0, 10), 10)
"""


class TestOneItemTwoUnits(ContractCase):
    """修正案の 1 つの項目に 2 つの単位（MEAN・CLAMP）が載り、項目の受け入れのテスト 2 本が両方の単位の約束に在る（canary の run
    245042a7・4c32bf37 の形）。前の単位の段は項目の受け入れのテストを全部名指して緑にするので、同じ項目の後の単位を「今は直すな」
    と言わず、一緒に直させる。後の単位は受け入れのテストを輪が確かめ済みなので、機械が段を回さずに閉じる（食い違いの申し出を
    生まない）"""
    CONTRACT = {MEAN: {"items": [1], "route": "tdd", "rewrites": [], "refactor": [], "tests": SAME_ITEM_TESTS},
                CLAMP: {"items": [1], "route": "tdd", "rewrites": [], "refactor": [], "tests": SAME_ITEM_TESTS}}
    BRIEFS = [{"item": 1, "unit_keys": [MEAN, CLAMP], "file": "/b/r1/brief-1.md", "sha256": "a" * 64}]

    def route_both(self):
        got = self.step({"phase": "route", "units": [{"unit_key": MEAN, "route": "tdd"}, {"unit_key": CLAMP, "route": "tdd"}]})
        self.assertTrue(got["ok"], got)

    def briefed(self):
        """brief の控えが BRIEFS の置き場での今の周の指示の (値, 段落の真偽)"""
        with mock.patch.object(tdd.planbrief, "cut_at", return_value=self.BRIEFS):
            return self.values()

    def test_step_does_not_hold_off_unit_of_same_item(self):
        self.route_both()
        vals, when = self.briefed()
        row = next(ln for ln in vals["brief_rows"].splitlines() if ln.startswith("- 項目 1:"))
        self.assertIn(f"単位 {MEAN}、{CLAMP}", row)
        self.assertNotIn(planbrief.NOT_NOW, row, "同じ項目の単位に「今は直すな」と言わない")
        self.assertEqual((when["later"], vals["later_rows"]), (False, ""), "同じ項目の後の単位を「この後の単位」に並べない")
        self.assertTrue(when["together"])
        self.assertIn(CLAMP, vals["together_rows"])

    def test_one_item_two_units_files_no_conflict(self):
        self.route_both()
        self.add_test(NEW_TEST + SAME_ITEM_FAR)
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                         "tests": [t["id"] for t in SAME_ITEM_TESTS]})
        self.assertTrue(got["ok"], got)
        self.edit("stats.py", "return sum(xs) / (len(xs) - 1)", "return sum(xs) / len(xs)")
        self.edit("stats.py", "    if x > hi:\n        return lo", "    if x > hi:\n        return hi")
        got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母と上限の枝を項目どおりに直した"})
        self.assertTrue(got["ok"], got)
        self.assertEqual((got["done"], self.st().get(tdd.UNSENT)), (True, None), "同じ項目の後の単位は機械が閉じ、輪は済む")
        st = self.st()
        self.assertEqual(st["parked"], [])
        self.assertNotIn("conflict", [c["phase"] for c in st["calls"]])
        self.assertEqual([c["unit_key"] for c in st["calls"] if c["phase"] != "route"], [MEAN, MEAN], "CLAMP の段は回らない")
        rows = {u["unit_key"]: u for u in tdd.exit_fields(self.start)["units"]}
        c = rows[CLAMP]
        self.assertEqual((c["route"], c["red"], c["green"], c["gave_up"]), ("tdd", "ok", "ok", ""))
        self.assertEqual(sorted(c["tests"]), sorted(t["id"] for t in SAME_ITEM_TESTS))
        self.assertIn(MEAN, c["why"], "どの単位の段で一緒に直したかを残す")
        self.assertEqual(st["units"][CLAMP]["covered_by"], [MEAN])
        summary = pathlib.Path(self.start["summary_file"]).read_text(encoding="utf-8")
        done = summary.split("## ループで直した単位", 1)[1].split("\n## ", 1)[0]
        self.assertIn(f"- {CLAMP}", done, "閉じた単位はループで直した単位に並ぶ（direct に並べない）")
        self.assertEqual(tdd.frozen_problems(self.state, self.repo), [])

    def test_later_unit_is_not_closed_when_its_tests_are_not_verified(self):
        """前の単位が申し出で止まれば（受け入れのテストを確かめていない）、後の単位は今どおり自分の段を回す"""
        self.route_both()
        got = self.step({"phase": "conflict", "unit_key": MEAN, "between": ["stats.py:9", "test_stats.py:9"],
                         "why_both_cannot_hold": "期待値と依頼の分母が食い違い、どちらを正とするか決められない",
                         "which_is_right": "unknown", "kind": "needs_context"})
        self.assertTrue(got["ok"], got)
        st = self.st()
        self.assertEqual((st["phase"], st["queue"][st["cur"]]), ("test", CLAMP))
        self.assertFalse(st["units"][CLAMP].get("covered_by"))


class TestTwoItemsKeepHoldOff(ContractCase):
    """別の項目の単位は今どおり「この後の単位（今は手を付けるな）」に並び、機械は閉じない（単位ごとの赤→緑の順を保つ）"""
    CONTRACT = {MEAN: {"items": [1], "route": "tdd", "rewrites": [], "refactor": [], "tests": SAME_ITEM_TESTS[:1]},
                CLAMP: {"items": [2], "route": "tdd", "rewrites": [], "refactor": [], "tests": SAME_ITEM_TESTS[1:]}}
    BRIEFS = [{"item": 1, "unit_keys": [MEAN], "file": "/b/r1/brief-1.md", "sha256": "a" * 64},
              {"item": 2, "unit_keys": [CLAMP], "file": "/b/r1/brief-2.md", "sha256": "b" * 64}]
    route_both, briefed = TestOneItemTwoUnits.route_both, TestOneItemTwoUnits.briefed

    def test_unit_of_other_item_is_held_off(self):
        self.route_both()
        vals, when = self.briefed()
        self.assertEqual((when["later"], vals["later_rows"]), (True, CLAMP), "この後の tdd の単位（今は手を付けるな）")
        self.assertEqual((when["together"], vals["together_rows"]), (False, ""))
        self.assertNotIn("brief-2.md", vals["brief_rows"])
        self.red()
        got = self.fix_mean()
        self.assertFalse(got["done"])
        st = self.st()
        self.assertEqual((st["phase"], st["queue"][st["cur"]]), ("test", CLAMP), "別の項目の単位は自分の段を回す")
        self.assertFalse(st["units"][CLAMP].get("covered_by"))


class TestSharedItemPartlyCovered(ContractCase):
    """後の単位が前の単位に無い項目にも載るなら、一緒に直す単位にせず（今どおり「今は手を付けるな」）、機械も閉じない
    （残りの項目の受け入れのテストを自分の段で赤→緑にする。一緒に直させると後の単位の赤が書けなくなる）"""
    CONTRACT = {MEAN: {"items": [1], "route": "tdd", "rewrites": [], "refactor": [], "tests": SAME_ITEM_TESTS[:1]},
                CLAMP: {"items": [1, 2], "route": "tdd", "rewrites": [], "refactor": [], "tests": SAME_ITEM_TESTS}}
    route_both = TestOneItemTwoUnits.route_both

    def test_partly_covered_unit_runs_its_own_step(self):
        self.route_both()
        self.assertEqual(tdd.together(self.st(), MEAN), [])
        self.red()
        got = self.fix_mean()
        self.assertFalse(got["done"])
        st = self.st()
        self.assertEqual((st["phase"], st["queue"][st["cur"]]), ("test", CLAMP))
        self.assertFalse(st["units"][CLAMP].get("covered_by"))


class TestUnnamedEditsWithoutContract(LoopCase):
    def test_no_contract_does_not_freeze_existing_tests(self):
        """約束の無い run は、既存のテストの本体の書き換えも今どおり見ない"""
        self.route()
        self.add_test(NEW_TEST)
        self.edit("test_stats.py", "self.assertEqual(clamp(5, 0, 10), 5)", "self.assertEqual(clamp(6, 0, 10), 6)")
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                         "tests": ["test_stats.py::TestStats::test_mean_of_two"]})
        self.assertTrue(got["ok"], got)


class TestTestFunctions(Case):
    def test_ids_and_sources(self):
        src = "import x\n\nclass T:\n    @d\n    def test_a(self):\n        pass\n\n    def helper(self):\n        pass\n\ndef test_b():\n    pass\n"
        got = tdd.test_functions(src, "t.py")
        self.assertEqual(set(got), {"t.py::T::test_a", "t.py::test_b"})
        self.assertTrue(got["t.py::T::test_a"].startswith("@d"))
        self.assertEqual(tdd.test_functions("def (", "t.py"), {})
        self.assertEqual(tdd.test_functions(src, "t.sh"), {})

    def test_nested_class_ids(self):
        """入れ子のクラスのメソッドも pytest の node id の形（<パス>::A::B::test_x）で引く"""
        src = "class A:\n    class B:\n        def test_x(self):\n            pass\n\n    def test_y(self):\n        pass\n"
        self.assertEqual(set(tdd.test_functions(src, "t.py")), {"t.py::A::B::test_x", "t.py::A::test_y"})

    def test_parametrized_permission_covers_function(self):
        """許しが parametrize の id（<id>[1]）でも、その関数の書き換えは名指しの外に数えない"""
        with tempfile.TemporaryDirectory() as td:
            repo = pathlib.Path(td) / "repo"
            committed_copy(repo, SEED)
            tree = tdd.snapshot(repo)
            p = repo / "test_stats.py"
            p.write_text(p.read_text(encoding="utf-8").replace("clamp(5, 0, 10), 5)", "clamp(6, 0, 10), 6)"), encoding="utf-8")
            self.assertEqual(tdd._unnamed_edits(repo, tree, ["test_stats.py"],
                                                    {"test_stats.py::TestStats::test_clamp_within_range[1]"}), [])

    def test_unnamed_edits(self):
        """木の時に在った test* 関数の本体が変わった・消えた物のうち、許しに無い id（整えた id で比べる）"""
        with tempfile.TemporaryDirectory() as td:
            repo = pathlib.Path(td) / "repo"
            committed_copy(repo, SEED)
            tree = tdd.snapshot(repo)
            p = repo / "test_stats.py"
            text = p.read_text(encoding="utf-8")
            text = text.replace("clamp(5, 0, 10), 5)", "clamp(6, 0, 10), 6)").replace("clamp(15, 0, 10), 10)", "clamp(16, 0, 10), 10)")
            text = text.replace("    def test_mean_of_three(self):\n        self.assertEqual(mean([1, 2, 3]), 2)\n", "")
            p.write_text(text, encoding="utf-8")
            (repo / "notes.txt").write_text("x\n", encoding="utf-8")
            got = tdd._unnamed_edits(repo, tree, ["test_stats.py", "notes.txt", "test_new.py"],
                                         {"./test_stats.py::TestStats::test_clamp_above_range"})
            self.assertEqual(sorted(got), ["test_stats.py::TestStats::test_clamp_within_range",
                                           "test_stats.py::TestStats::test_mean_of_three"])


class TestContractBroken(LoopCase):
    def test_broken_fields_stop_start(self):
        """欄の控えが凍結の印と食い違う（conflict.frozen_fields の ValueError）→ plan_contract は Broken（理由の文は
        conflict.FIELDS_BROKEN で始まる）"""
        gap = ValueError(f"{tdd.conflict.FIELDS_BROKEN}: 控えの sha256 が印と違う")
        with mock.patch.object(tdd.conflict, "frozen_fields", side_effect=gap):
            with self.assertRaises(tdd.Broken) as got:
                tdd.plan_contract(self.board, [MEAN])
            self.assertTrue(str(got.exception).startswith(tdd.conflict.FIELDS_BROKEN), got.exception)
            with self.assertRaises(tdd.Broken) as again:
                tdd.start(self.board, self.repo, str(self.suite), OPEN)
            self.assertTrue(str(again.exception).startswith(tdd.conflict.FIELDS_BROKEN), again.exception)

RC_ID = "test_a.py::TestA::test_x"
RC_WHY = "Foo はこれから足す名前で、まだ無いので落ちる（打ち間違いではない）"


def _junit(*rows) -> str:
    """実行器が書く JUnit XML の文字列。rows は (テストの名前, 種類（failure・error・空は通る）, message, 本文)"""
    root = ET.Element("testsuite")
    for name, kind, message, body in rows:
        tc = ET.SubElement(root, "testcase", classname="test_a.TestA", name=name)
        if kind:
            f = ET.SubElement(tc, kind)
            if message:
                f.set("message", message)
            if body:
                f.text = body
    return ET.tostring(root, encoding="unicode")


class TestRedCheck(Case):
    """赤の判定 red_check（輪・並べの締め・事後の関門が呼ぶ 1 つの口）: 言語に依らない事実と、失敗の文の引用の照らし"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.td = pathlib.Path(self._tmp.name)

    def suite(self, xml, out="", n="rc"):
        """中に書いた実行器（JUnit を xml のとおりに書き、out を標準出力に出して exit 1）を run_suite で走らせた
        （結末の行, 終了コード, その回のログのパス）"""
        exe = self.td / f"runner-{n}.py"
        exe.write_text(f"import sys\nsys.stdout.write({out!r})\nopen(sys.argv[1], 'w', encoding='utf-8').write({xml!r})\nsys.exit(1)\n",
                       encoding="utf-8")
        cases, code, why = tdd.run_suite(str(exe), self.td, self.td, n)
        self.assertEqual(why, [])
        return cases, code, self.td / f"suite-{n}.log"

    def check(self, xml, quote=None, why=RC_WHY, out="", **kw):
        cases, code, log = self.suite(xml, out)
        quotes = None if quote is None else {RC_ID: {"quote": quote, "why": why}}
        return tdd.red_check([RC_ID], cases, code, {}, kw.get("quotes", quotes), log)

    def test_failure_with_any_language_text_is_red(self):
        """failure の message が Python でない文でも、名指しが failure で落ち、引用がその文に在れば赤として通る"""
        self.assertEqual(self.check(_junit(("test_x", "failure", "undefined: Foo", "")), "undefined: Foo"), ([], []))
        self.assertEqual(self.check(_junit(("test_x", "failure", "undefined: Foo", ""))), ([], []), "引用を見ない呼びは事実だけ")

    def test_error_and_missing_are_not_red_and_carry_facts_only(self):
        """名指しが error か一式に居ない時は拒む。返す文は事実だけで、NOT_RAN の言い足しを含まない（言い足しは輪の _test だけ）"""
        probs, _ = self.check(_junit(("test_x", "error", "ImportError: boom", "")))
        self.assertEqual(len(probs), 1)
        self.assertIn("error で落ちた", probs[0])
        probs, _ = self.check(_junit(("test_other", "failure", "x", "")))
        self.assertTrue(any("一式の結末に居ない" in p for p in probs), probs)
        self.assertFalse(any(tdd.NOT_RAN in p for p in probs))
        probs, _ = self.check(_junit(("test_x", "", "", "")))
        self.assertTrue(any("もう通る" in p for p in probs), probs)

    def test_quote_absent_from_failure_is_rejected(self):
        probs, _ = self.check(_junit(("test_x", "failure", "undefined: Foo", "")), "結末に無い作り話の文")
        self.assertEqual(len(probs), 1)
        self.assertIn(RC_ID, probs[0])
        self.assertIn("結末の失敗の文に無い", probs[0])
        probs, _ = self.check(_junit(("test_x", "failure", "undefined: Foo", "")), "")
        self.assertIn(RC_ID, probs[0])
        probs, _ = self.check(_junit(("test_x", "failure", "undefined: Foo", "")), quotes={})
        self.assertIn("引用と理由が無い", probs[0], "約束の在る単位は、失敗の文が在る名指しに引用を求める")

    def test_quote_matches_across_whitespace_and_color_codes(self):
        """改行・連続する空白・色の制御文字だけが違う引用は通る。XML の属性に色の制御文字は書けないので、色の付くログに引いた物でも見る"""
        xml = _junit(("test_x", "failure", "AssertionError:\n    6.0\t!=   3", ""))
        self.assertEqual(self.check(xml, "AssertionError: 6.0 != 3"), ([], []))
        self.assertEqual(self.check(xml, "AssertionError:   6.0 !=\n3"), ([], []))
        bare = _junit(("test_x", "failure", "", ""))
        self.assertEqual(self.check(bare, "AssertionError: 6.0 != 3", out="\x1b[31mAssertionError:\x1b[0m\n  6.0 != 3\n"), ([], []))

    def test_quote_found_in_failure_body_when_message_empty(self):
        """failure の message が空で本文に失敗の文が在る時、本文に在る引用は通る（本文を読む所は _failure_attrs の 1 か所）"""
        xml = _junit(("test_x", "failure", "", "Traceback (most recent call last):\n  File x\nNameError: name 'Foo' is not defined"))
        self.assertEqual(self.check(xml, "NameError: name 'Foo' is not defined"), ([], []))
        probs, _ = self.check(xml, "ValueError: boom")
        self.assertIn("結末の失敗の文に無い", probs[0])

    def test_quote_checked_against_log_when_failure_has_no_text(self):
        """failure に message も本文も無く、役が引いた時は、その回のログと照らす（ログに在れば通り、無ければ拒む）"""
        xml = _junit(("test_x", "failure", "", ""))
        out = "FAILED test_a.py::TestA::test_x - assert 6.0 == 3\n"
        self.assertEqual(self.check(xml, "assert 6.0 == 3", out=out), ([], []))
        probs, _ = self.check(xml, "ログに無い文", out=out)
        self.assertIn("結末の失敗の文に無い", probs[0])

    def test_nothing_to_quote_is_recorded_unchecked(self):
        """failure の文もログも空の時は、引用が無くても拒まず、その名指しを unchecked に返す。引用を求めるのは文が在る名指しだけ"""
        xml = _junit(("test_x", "failure", "", ""))
        self.assertEqual(self.check(xml, quotes={}), ([], [RC_ID]))
        self.assertEqual(self.check(xml), ([], [RC_ID]))
        self.assertEqual(self.check(_junit(("test_x", "failure", "undefined: Foo", "")), "undefined: Foo")[1], [])

    def test_short_why_and_trivial_quote_are_rejected(self):
        """理由が MIN_WHY 字に満たない時と、引用が 1〜2 字（照らす先が長い時）の時は拒む。3 字からは通る"""
        xml = _junit(("test_x", "failure", "AssertionError: 6.0 != 3 (mean が分母を間違えている)", ""))
        probs, _ = self.check(xml, "AssertionError: 6.0 != 3", why="短い理由")
        self.assertIn("why", probs[0])
        for trivial in ("e", "6."):
            probs, _ = self.check(xml, trivial)
            self.assertIn("短すぎる", probs[0], trivial)
        self.assertEqual(self.check(xml, "6.0"), ([], []))


LINT = "import pathlib, sys\nsys.exit(1 if 'print(' in pathlib.Path('stats.py').read_text() else 0)\n"
# 整形の真似: 直した後の stats.py（分母が len(xs)）だけを書き換え、新しいファイル fmt.cache も作って 0 で抜ける
FMT = ("import pathlib\np = pathlib.Path('stats.py')\nt = p.read_text()\n"
       "p.write_text(t.replace('sum(xs) / len(xs)', 'sum(xs)/len(xs)'))\npathlib.Path('fmt.cache').write_text('x')\n")
# いつも stats.py を書き換える test_cmd（輪の頭で書き換えが見える）
FMT_ALWAYS = "import pathlib\np = pathlib.Path('stats.py')\np.write_text(p.read_text() + '\\n# formatted\\n')\n"


class TestTestCmdGate(LoopCase):
    """緑の後に run の test_cmd（線の入力）の緑も確かめる。元から赤なら関門を切って理由を残し、実行器が同じコマンドを
    包んだ物なら 2 度走らせない（Review Focus 5）"""

    def restart(self, cmd, unit_depths=""):
        (self.repo / "lint.py").write_text(LINT, encoding="utf-8")
        git(self.repo, "add", "lint.py")
        git(self.repo, "commit", "-qm", "lint")
        self.start = tdd.start(self.board, self.repo, str(self.suite), OPEN, test_cmd=cmd, unit_depths=unit_depths)
        self.state = self.start["state_file"]

    def lint(self):
        return f"{sys.executable} lint.py"

    def test_fix_rejected_when_test_cmd_red(self):
        self.restart(self.lint())
        self.assertEqual(self.st()["test_cmd_gate"], tdd.GATE_ON)
        self.route()
        self.red()
        self.edit("stats.py", "return sum(xs) / (len(xs) - 1)", "print('debug')\n    return sum(xs) / len(xs)")
        got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を直した"})
        self.assertFalse(got["ok"])
        self.assertIn("test_cmd", got["reason"])
        self.assertIn("test-cmd-", got["reason"])
        self.assertEqual(self.st()["phase"], "fix")
        self.assertTrue(pathlib.Path(self.st()["work"], f"test-cmd-{self.st()['runs'] - 1}.log").is_file())

    def test_light_unit_does_not_run_test_cmd_after_green(self):
        # 軽量の単位は緑の後の test_cmd を走らせない（同じコマンドを線の最後のテストが木の全部で走らせる）。赤・緑の確かめは今どおり
        self.restart(self.lint(), unit_depths=json.dumps({MEAN: "軽量", CLAMP: "標準"}))
        self.assertEqual(self.st()["test_cmd_gate"], tdd.GATE_ON)
        self.route()
        self.red()
        runs = self.st()["runs"]
        vals, when = self.values()
        self.assertEqual((when["gate"], vals["test_cmd"]), (False, ""), "緑の後に機械が run の test_cmd も走らせる、と言わない")
        self.assertNotIn(self.lint(), self.prompt())
        self.edit("stats.py", "return sum(xs) / (len(xs) - 1)", "print('debug')\n    return sum(xs) / len(xs)")
        got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を直した"})
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.st()["runs"], runs + 1, "一式の緑の 1 回だけで、test_cmd は走らせない")
        self.assertEqual(self.st()["units"][MEAN]["test_cmd"], tdd.CMD_LIGHT)

    def standard_mean_rejected(self, depths):
        self.restart(self.lint(), unit_depths=depths)
        self.route()
        self.red()
        self.edit("stats.py", "return sum(xs) / (len(xs) - 1)", "print('debug')\n    return sum(xs) / len(xs)")
        got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を直した"})
        self.assertFalse(got["ok"])
        self.assertIn("test_cmd", got["reason"])

    def test_unit_named_standard_runs_test_cmd(self):
        self.standard_mean_rejected(json.dumps({MEAN: "標準"}))

    def test_unit_not_named_runs_test_cmd(self):
        self.standard_mean_rejected(json.dumps({CLAMP: "軽量"}))

    def test_skip_rerun_shape_skips_the_test_cmd_after_green(self):
        """port skip_rerun の単位: group-start は values.json の skip_rerun のうち組の単位だけを {key: tdd.LIGHT} の unit_depths で
        渡す（省く単位だけ。標準の単位は名指さない）。その単位は緑の後の test_cmd を走らせない（名指さない単位は次の試験）"""
        self.restart(self.lint(), unit_depths=json.dumps({MEAN: tdd.LIGHT}))
        st = self.st()
        self.assertEqual((st["test_cmd_gate"], st["light"]), (tdd.GATE_ON, [MEAN]))
        self.route()
        self.red()
        runs = self.st()["runs"]
        self.edit("stats.py", "return sum(xs) / (len(xs) - 1)", "print('debug')\n    return sum(xs) / len(xs)")
        got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を直した"})
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.st()["runs"], runs + 1, "一式の緑の 1 回だけで、test_cmd は走らせない")
        self.assertEqual(self.st()["units"][MEAN]["test_cmd"], tdd.CMD_LIGHT)

    def test_skip_rerun_shape_leaves_other_units_standard(self):
        self.standard_mean_rejected(json.dumps({CLAMP: tdd.LIGHT}))

    def test_test_cmd_is_niced(self):
        """run の test_cmd も実行器と同じ口（baseline_red.lowered）で優先度を下げて起こす（元 works/.shared/core/entry.py:680 の
        _nice19）。argv は command_argv の形のまま"""
        seen = []
        log = pathlib.Path(self.st()["work"]) / "test-cmd-niced.log"
        with mock.patch.object(tdd.tree_run, "run", side_effect=lambda argv, **kw: seen.append((argv, kw)) or 0):
            mat = tdd._cmd_material(self.repo, self.lint(), log)
        self.assertEqual(mat["status"], "clean", mat)
        self.assertEqual([(argv, kw.get("preexec_fn")) for argv, kw in seen],
                         [(tdd.tree_run.command_argv(self.lint())[0], tdd.baseline_red.nice19)])

    def test_shell_test_cmd_that_cannot_launch_is_not_run_under_nice(self):
        """shell の形の test_cmd の先頭の語が無ければ、優先度を下げても起こす前の証明（tree_run.prove_launchable）を通らず
        not_run（証明を飛ばすと exit 127 の赤やパイプの後ろの緑に化ける）"""
        log = pathlib.Path(self.st()["work"]) / "test-cmd-missing.log"
        for cmd in ("no_such_cmd_xyz --x | cat", "no_such_cmd_xyz --x"):
            with self.subTest(cmd=cmd):
                mat = tdd._cmd_material(self.repo, cmd, log)
                self.assertEqual(mat["status"], "not_run", mat)
                self.assertIn("no_such_cmd_xyz", mat["reason"])

    def test_command_only_on_the_uv_run_path_is_not_run(self):
        """起こせるかの証明は走らせる時と同じ環境で行う: 実行基盤は script を uv run で起こし、uv は PATH の頭に自分の python の bin
        を足すが、test_cmd には外した環境（tree_run.outside_env）を渡す。そこにしか無い語（uv の下の python など）を先頭に持つ
        shell の形の test_cmd は、パイプの後ろが緑でも clean でなく not_run（review が再現した `python … | cat` の偽の clean）"""
        uv_bin = pathlib.Path(self._tmp.name) / "uv-bin"
        uv_bin.mkdir()
        only = uv_bin / "only_on_uv_path"
        only.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        only.chmod(0o755)
        env = {"PATH": f"{uv_bin}{os.pathsep}{os.environ.get('PATH', '')}", "UV_RUN_RECURSION_DEPTH": "1"}
        log = pathlib.Path(self.st()["work"]) / "test-cmd-uv.log"
        with mock.patch.dict(os.environ, env), mock.patch.object(tdd.tree_run.sys, "executable", str(uv_bin / "python3")):
            self.assertIsNotNone(__import__("shutil").which("only_on_uv_path"), "この process からは見える")
            mat = tdd._cmd_material(self.repo, "only_on_uv_path --x | cat", log)
        self.assertEqual(mat["status"], "not_run", mat)
        self.assertIn("only_on_uv_path", mat["reason"])

    def test_unit_depths_of_wrong_shape_is_broken(self):
        for raw in ("{", "[]", json.dumps({MEAN: 1})):
            with self.subTest(raw=raw), self.assertRaises(tdd.Broken):
                tdd.start(self.board, self.repo, str(self.suite), OPEN, unit_depths=raw)

    def test_fix_passes_and_records(self):
        self.restart(self.lint())
        self.route()
        self.red()
        self.fix_mean(refactor=DECLARED)
        self.assertEqual(self.st()["units"][MEAN]["test_cmd"], "ok")
        self.step({"phase": "refactor", "unit_key": MEAN, "what": "整える物は無い"})
        ex = tdd.exit_fields(self.start)
        self.assertEqual(ex["test_cmd"], {"gate": tdd.GATE_ON, "note": ""})
        rows = {u["unit_key"]: u for u in ex["units"]}
        self.assertEqual((rows[MEAN]["test_cmd"], rows[CLAMP]["test_cmd"]), ("ok", ""))

    def test_changed_refactor_rejected_when_test_cmd_red(self):
        self.restart(self.lint())
        self.route()
        self.red()
        self.fix_mean(refactor=DECLARED)
        self.edit("stats.py", "return sum(xs) / len(xs)", "print('debug')\n    return sum(xs) / len(xs)")
        got = self.step({"phase": "refactor", "unit_key": MEAN, "what": "出力を足した"})
        self.assertFalse(got["ok"])
        self.assertIn("test_cmd", got["reason"])

    def test_baseline_red_test_cmd_turns_gate_off(self):
        self.restart(f"{sys.executable} -c 'raise SystemExit(1)'")
        st = self.st()
        self.assertEqual(st["test_cmd_gate"], tdd.GATE_OFF)
        self.assertTrue(st["test_cmd_note"])
        self.route()
        self.red()
        self.fix_mean(refactor=DECLARED)   # 毎単位を拒まない
        self.assertEqual(self.st()["units"][MEAN]["test_cmd"], "")
        self.step({"phase": "refactor", "unit_key": MEAN, "what": "整える物は無い"})
        self.assertEqual(tdd.exit_fields(self.start)["test_cmd"], {"gate": tdd.GATE_OFF, "note": st["test_cmd_note"]})

    def test_same_command_as_suite_runs_once(self):
        cmd = f"{sys.executable} {self.suite}"
        with mock.patch.object(tdd, "_cmd_material") as lcm:
            self.suite.write_text(SUITE + f"\n# {cmd}\n", encoding="utf-8")
            self.restart(cmd)
            self.route()
            self.red()
            self.fix_mean()
        lcm.assert_not_called()
        self.assertEqual(self.st()["test_cmd_gate"], tdd.GATE_SAME)

    def test_empty_test_cmd_is_off(self):
        with mock.patch.object(tdd, "_cmd_material") as lcm:
            self.restart("")
            self.route()
            self.red()
            self.fix_mean()
        lcm.assert_not_called()
        st = self.st()
        self.assertEqual((st["test_cmd"], st["test_cmd_gate"], st["test_cmd_note"]), ("", tdd.GATE_OFF, ""))

    def test_default_start_has_gate_off(self):
        """LoopCase の既定（test_cmd を渡さない start）も関門は off・理由は空"""
        st = self.st()
        self.assertEqual((st["test_cmd"], st["test_cmd_gate"], st["test_cmd_note"]), ("", tdd.GATE_OFF, ""))

    def test_test_cmd_not_run_leaves_loop_like_runner_down(self):
        self.restart(self.lint())
        self.route()
        self.red()
        down = {"status": "not_run", "reason": "起こせない"}
        self.edit("stats.py", "return sum(xs) / (len(xs) - 1)", "return sum(xs) / len(xs)")
        with mock.patch.object(tdd, "_cmd_material", return_value=down):
            got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を直した"})
        self.assertTrue(got["done"])
        self.assertIn("起こせない", got["reason"])
        self.assertTrue(got["reason"].startswith("テストのコマンドが走らない"), got["reason"])
        self.assertEqual(self.st()["units"][MEAN]["gave_up"], "runner")

    def tool(self, name, src):
        (self.repo / name).write_text(src, encoding="utf-8")
        git(self.repo, "add", name)
        git(self.repo, "commit", "-qm", name)
        return f"{sys.executable} {name}"

    def test_rewriting_test_cmd_is_restored_and_not_excused(self):
        """既存のファイルを書き換えた test_cmd は緑でない: 拒み、理由に書き換えたパスを載せ、元に戻して suite_made に積まない
        （書き込みの出どころの照合から外さない）。新しく出来たファイルは今どおり積む"""
        self.restart(self.tool("fmt.py", FMT))
        self.assertEqual(self.st()["test_cmd_gate"], tdd.GATE_ON)
        self.route()
        self.red()
        self.edit("stats.py", "return sum(xs) / (len(xs) - 1)", "return sum(xs) / len(xs)")
        got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を len(xs) にした"})
        self.assertFalse(got["ok"], got)
        self.assertIn("stats.py", got["reason"])
        self.assertIn("元に戻した", got["reason"])
        self.assertIn("phase conflict", got["reason"])
        st = self.st()
        self.assertEqual(st["phase"], "fix")
        self.assertNotIn("stats.py", st["suite_made"])
        self.assertIn("fmt.cache", st["suite_made"])
        self.assertIn("return sum(xs) / len(xs)", (self.repo / "stats.py").read_text(encoding="utf-8"), "役の直しの姿に戻す")

    def test_red_test_cmd_reason_names_conflict_for_frozen_tests(self):
        """赤の元が凍ったテストのファイルなら直しの段では直せないので、拒む文が申し出の道を名指す"""
        self.restart(self.lint())
        self.route()
        self.red()
        self.edit("stats.py", "return sum(xs) / (len(xs) - 1)", "print('debug')\n    return sum(xs) / len(xs)")
        got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を直した"})
        self.assertIn("赤の元が凍ったテストのファイルなら phase conflict で申し出よ", got["reason"])

    def test_start_rewriting_test_cmd_turns_gate_off(self):
        self.restart(self.tool("fmt_always.py", FMT_ALWAYS))
        st = self.st()
        self.assertEqual(st["test_cmd_gate"], tdd.GATE_OFF)
        self.assertIn("test_cmd が作業ツリーの既存のファイルを書き換える", st["test_cmd_note"])
        self.assertIn("stats.py", st["test_cmd_note"])
        self.assertNotIn("stats.py", st["suite_made"])
        self.assertNotIn("# formatted", (self.repo / "stats.py").read_text(encoding="utf-8"))

    def test_prompt_names_test_cmd_only_when_gate_on(self):
        """関門が on の時だけ、直し・整えの段の指示書に test_cmd の文字列が載る（拒まれて初めて知るのを防ぐ）"""
        cmd = self.lint()
        self.restart(cmd)
        self.route()
        self.assertEqual(self.values()[1]["gate"], False, "test の段")
        self.assertNotIn(cmd, self.prompt(), "test の段")
        self.red()
        vals, when = self.values()
        self.assertEqual((when["gate"], vals["test_cmd"]), (True, cmd), "fix の段")
        self.assertIn(cmd, self.prompt(), "fix の段")
        self.fix_mean(refactor=DECLARED)
        vals, when = self.values()
        self.assertEqual((when["gate"], vals["test_cmd"]), (True, cmd), "refactor の段")
        self.assertIn(cmd, self.prompt(), "refactor の段")

    def test_prompt_omits_test_cmd_when_gate_off(self):
        off = f"{sys.executable} -c 'raise SystemExit(1)'"
        self.restart(off)
        self.route()
        self.red()
        vals, when = self.values()
        self.assertEqual((when["gate"], vals["test_cmd"]), (False, ""), "関門が off")
        self.assertNotIn(off, self.prompt(), "関門が off")

    def test_start_not_run_turns_gate_off_with_reason(self):
        down = {"status": "not_run", "reason": "起こせない"}
        with mock.patch.object(tdd, "_cmd_material", return_value=down):
            self.restart(self.lint())
        st = self.st()
        self.assertEqual(st["test_cmd_gate"], tdd.GATE_OFF)
        self.assertIn("起こせない", st["test_cmd_note"])


class TestSkipRerunScript(Case):
    """script の段: intake が port skip_rerun を values.json に置き、group-start がそのうち組の単位を軽量（状態の light）にして輪を置く
    （元の始めの記録の深さ unit_depths の代わり）"""

    def test_group_start_marks_skip_rerun_units_light(self):
        run = kit.Run(self, "fix")
        shutil.rmtree(run.repo)
        committed_copy(run.repo, SEED)
        (run.repo / "lint.py").write_text(LINT, encoding="utf-8")
        git(run.repo, "add", "lint.py")
        git(run.repo, "commit", "-qm", "lint")
        suite = run.artifacts.parent / "suite.py"
        suite.write_text(SUITE, encoding="utf-8")
        judgment = {"units": [{"key": k, "label": "block", "reason": "試験の単位"} for k in (MEAN, CLAMP)], "questions": []}
        got = run.script("intake", mode="group", group=json.dumps({"group_id": "g1", "unit_ids": [MEAN, CLAMP], "items": []},
                                                                  ensure_ascii=False),
                         judgment=json.dumps(judgment, ensure_ascii=False), tdd_suite=str(suite),
                         test_cmd=f"{sys.executable} lint.py", skip_rerun=json.dumps([MEAN, "組の外の単位"], ensure_ascii=False))
        self.assertTrue(got["ok"], got)
        self.assertEqual(runvals.read(run.artifacts)["skip_rerun"], [MEAN, "組の外の単位"])
        got = run.script("group_start")
        self.assertEqual((got["tdd"], got["units"]), (True, 2), got)
        started = json.loads((run.artifacts / board.TDD_START_FILE).read_text(encoding="utf-8"))
        st = tdd.load_state(started["state_file"])
        self.assertEqual((st["test_cmd_gate"], st["light"]), (tdd.GATE_ON, [MEAN]), "組の単位のうち skip_rerun の物だけが軽量")

    def test_group_start_without_skip_rerun_has_no_light_unit(self):
        run = kit.Run(self, "fix")
        shutil.rmtree(run.repo)
        committed_copy(run.repo, SEED)
        suite = run.artifacts.parent / "suite.py"
        suite.write_text(SUITE, encoding="utf-8")
        judgment = {"units": [{"key": MEAN, "label": "block", "reason": "試験の単位"}], "questions": []}
        self.assertTrue(run.script("intake", mode="group", group=json.dumps({"group_id": "g1", "unit_ids": [MEAN]}, ensure_ascii=False),
                                   judgment=json.dumps(judgment, ensure_ascii=False), tdd_suite=str(suite))["ok"])
        self.assertTrue(run.script("group_start")["tdd"])
        started = json.loads((run.artifacts / board.TDD_START_FILE).read_text(encoding="utf-8"))
        self.assertEqual(tdd.load_state(started["state_file"])["light"], [])


class TestRefactorGate(LoopCase):
    """整えの段は、fix の段で役が理由つきで申告した単位か、修正案の項目が refactor.declared の単位だけに来る。来ない単位は
    skipped。段ごとの呼び出しの記録（calls）を状態と出口に残す"""

    def test_fix_without_declaration_skips_refactor(self):
        self.route()
        self.red()
        got = self.fix_mean()
        self.assertTrue(got["done"], got)
        u = tdd.exit_fields(self.start)["units"][0]
        self.assertEqual((u["refactor"], u["refactor_why"]), ("skipped", ""))
        self.assertIn("整え: skipped", pathlib.Path(self.start["summary_file"]).read_text(encoding="utf-8"))

    def test_declared_fix_goes_to_refactor(self):
        self.route()
        self.red()
        self.fix_mean(refactor=DECLARED)
        self.assertEqual(self.st()["phase"], "refactor")
        self.assertEqual(self.st()["units"][MEAN]["refactor_why"], DECLARED["why"])
        self.assertTrue(self.values()[1]["phase_refactor"])
        self.assertIn("- **refactor**:", self.prompt())
        self.step({"phase": "refactor", "unit_key": MEAN, "what": "整える物は無い"})
        self.assertIn(f"整え: none（{DECLARED['why']}）", pathlib.Path(self.start["summary_file"]).read_text(encoding="utf-8"))

    def test_declared_without_why_rejected(self):
        self.route()
        self.red()
        self.edit("stats.py", "return sum(xs) / (len(xs) - 1)", "return sum(xs) / len(xs)")
        got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を直した",
                         "refactor": {"declared": True, "why": "短い"}})
        self.assertFalse(got["ok"])
        self.assertIn("refactor", got["reason"])
        self.assertEqual(self.st()["phase"], "fix")

    def test_malformed_declaration_rejected(self):
        self.route()
        self.red()
        self.edit("stats.py", "return sum(xs) / (len(xs) - 1)", "return sum(xs) / len(xs)")
        got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を直した",
                         "refactor": {"declared": "yes", "why": DECLARED["why"]}})
        self.assertFalse(got["ok"])
        self.assertIn("refactor", got["reason"])

    def test_not_declared_with_why_skips(self):
        self.route()
        self.red()
        got = self.fix_mean(refactor={"declared": False, "why": ""})
        self.assertTrue(got["done"], got)
        self.assertEqual(self.st()["units"][MEAN]["refactor"], "skipped")

    def test_plan_declared_goes_to_refactor_without_reply(self):
        """案の項目が refactor.declared の単位は、役が申告しなくても整えの段が来る"""
        contract = {MEAN: {"items": [1], "route": "tdd", "tests": [], "rewrites": [], "refactor": [PLAN_REFACTOR]}}
        with mock.patch.object(tdd, "plan_contract", return_value=contract):
            self.start = tdd.start(self.board, self.repo, str(self.suite), OPEN)
        self.state = self.start["state_file"]
        self.route()
        self.red()
        self.fix_mean()
        self.assertEqual(self.st()["phase"], "refactor")
        self.assertIn(f"項目 1: {PLAN_REFACTOR['why']}", self.st()["units"][MEAN]["refactor_why"])

    def test_role_and_plan_reasons_are_joined(self):
        """役と修正案の両方が申告したら、空でない理由を全部つなぐ"""
        contract = {MEAN: {"items": [1], "route": "tdd", "tests": [], "rewrites": [], "refactor": [PLAN_REFACTOR]}}
        with mock.patch.object(tdd, "plan_contract", return_value=contract):
            self.start = tdd.start(self.board, self.repo, str(self.suite), OPEN)
        self.state = self.start["state_file"]
        self.route()
        self.red()
        self.fix_mean(refactor=DECLARED)
        why = self.st()["units"][MEAN]["refactor_why"]
        self.assertIn(DECLARED["why"], why)
        self.assertIn(f"項目 1: {PLAN_REFACTOR['why']}", why)

    def test_calls_mark_runner_down(self):
        """実行器が走らずに輪を抜けた回は、役の拒否と分けて phase runner の行"""
        self.route()
        self.add_test(NEW_TEST)
        self.suite.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")   # JUnit を書かない
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                         "tests": ["test_stats.py::TestStats::test_mean_of_two"]})
        self.assertTrue(got["done"])
        last = self.st()["calls"][-1]
        self.assertEqual((last["phase"], last["unit_key"], last["ok"], last["runs"]), ("runner", MEAN, False, 1))

    def test_calls_mark_passed_conflict(self):
        got = self.step({"phase": "conflict", "unit_key": MEAN, "between": ["stats.py:9", "test_stats.py:9"],
                         "why_both_cannot_hold": "テストは分母 len(xs) - 1 の値を期待しているが、依頼は算術平均を求めている",
                         "which_is_right": "request", "kind": "unnamed_test_broke"})
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.st()["calls"], [{**self.st()["calls"][0], "n": 1, "phase": "conflict", "unit_key": "",
                                               "ok": True, "runs": 0}])

    def test_calls_mark_give_up(self):
        """諦めた回も、その段の ok: false の行（数えは retry_max 行）"""
        self.route()
        self.red()
        for _ in range(tdd.retry_max()):
            got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "直せていない"})
        self.assertTrue(got["done"])
        rows = self.st()["calls"][2:]
        self.assertEqual([(c["phase"], c["ok"]) for c in rows], [("fix", False)] * tdd.retry_max())

    def test_skipped_unit_moves_to_next_unit(self):
        """飛ばした単位の次の単位は、緑の木を頭に test の段から始まる"""
        self.route(clamp="tdd")
        self.red()
        self.fix_mean()
        st = self.st()
        self.assertEqual((st["phase"], st["queue"][st["cur"]], st["done"]), ("test", CLAMP, False))
        self.assertEqual(st["units"][MEAN]["refactor"], "skipped")

    def test_calls_recorded(self):
        self.route()
        self.red()
        self.fix_mean()
        calls = self.st()["calls"]
        self.assertEqual([c["n"] for c in calls], [1, 2, 3])
        self.assertEqual([c["phase"] for c in calls], ["route", "test", "fix"])
        self.assertEqual([c["unit_key"] for c in calls], ["", MEAN, MEAN])
        self.assertTrue(all(c["ok"] for c in calls))
        self.assertEqual([c["runs"] for c in calls], [0, 1, 1])
        self.assertTrue(all(isinstance(c["secs"], float) for c in calls))
        self.assertEqual(tdd.exit_fields(self.start)["calls"], calls)

    def test_calls_record_rejection_and_conflict_phase(self):
        self.route()
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"], "tests": []})
        self.assertFalse(got["ok"])
        self.step({"phase": "conflict", "unit_key": MEAN, "between": ["nope.py:1", "nope.py:2"],
                   "why_both_cannot_hold": "試験のための申し出", "which_is_right": "unknown"})
        calls = self.st()["calls"]
        self.assertEqual([(c["phase"], c["ok"]) for c in calls[1:]], [("test", False), ("conflict", False)])
        self.assertEqual(calls[1]["unit_key"], MEAN)


FAR_TEST = """
    def test_clamp_far_above(self):
        self.assertEqual(clamp(20, 0, 10), 10)
"""
FAR_ID = "test_stats.py::TestStats::test_clamp_far_above"


class TestCrossLoopFreeze(LoopCase):
    """凍結は run の全部の輪で効く（依頼 226 の 2 回目の修正の段）: 1 回目の段の輪（tdd-1）が凍らせたテストのファイルは、2 回目の
    段の輪（tdd-2）の後も、2 回目の輪の状態の handoff の木（since）からの変更で見る。2 回目の輪が同じファイルに足したテストは
    2 回目の輪の凍結で見る。直した項目の単位の tdd-1 の受け入れのテストの関数（skip_spans）だけは書き直してよい"""

    def first_loop(self):
        """tdd-1: MEAN を tdd で緑にして test_stats.py を凍らせる"""
        self.route()
        self.red()
        self.assertTrue(self.fix_mean()["done"])
        self.assertEqual(list(self.st()["frozen"]), ["test_stats.py"])

    def second_loop(self, keys, route="direct") -> str:
        """tdd-2 を keys で起こして振り分ける（direct なら輪は済む）。返りは tdd-2 の状態のファイル"""
        got = tdd.start(self.board, self.repo, str(self.suite), json.dumps(keys, ensure_ascii=False))
        self.assertTrue(got["go"], got)
        rows = [{"unit_key": k, "route": route, **({"why": "2 回目の段で先にテストを書かない単位"} if route == "direct" else {})}
                for k in keys]
        self.assertTrue(tdd.step(got["state_file"], {"phase": "route", "units": rows}, self.repo)["ok"])
        return got["state_file"]

    def since(self, state2) -> str:
        return tdd.load_state(state2)["handoff"]

    def test_states_in_order_and_suite_made_all(self):
        self.first_loop()
        state2 = self.second_loop([CLAMP])
        self.assertEqual(tdd.states(self.board), [pathlib.Path(self.state), pathlib.Path(state2)])
        for f, made in ((self.state, ["one.log"]), (state2, ["two.log"])):
            st = tdd.load_state(f)
            st["suite_made"] = made
            pathlib.Path(f).write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(tdd.suite_made_all(self.board), {"one.log", "two.log"})
        self.assertEqual(tdd.states(self.tmp_board()), [])

    def tmp_board(self):
        return pathlib.Path(self._tmp.name) / "no-board"

    def test_second_pass_cannot_touch_first_loop_frozen_tests(self):
        self.first_loop()
        state2 = self.second_loop([CLAMP])
        since = self.since(state2)
        self.assertEqual(tdd.frozen_problems(self.state, self.repo, since=since), [])
        self.edit("test_stats.py", "mean([2, 4]), 3", "mean([2, 4]), 3.0")   # 2 回目の修正役が tdd-1 の凍ったテストを変えた
        got = tdd.frozen_problems(self.state, self.repo, since=since)
        self.assertTrue(got and "test_stats.py" in got[0], got)
        self.assertEqual(tdd.frozen_problems(state2, self.repo), [], "tdd-2 は何も凍らせていない")

    def test_second_place_sees_the_first_place_loops(self):
        """F018: 2 度目の修正の差し込み（線の include refix-run）は置き場が 1 回目と分かれるが、1 回目の段の置き場の輪（tdd-1）が凍らせた
        テストは 2 回目の段の受け付けでも変えられない。prep が入力 prior_conflicts の先から輪の状態を写し（board.adopt_prior_pass）、
        組の子も親から写す（board.adopt_inputs）。写した輪は今の段の輪に数えない（board.ruled_states）"""
        self.first_loop()
        second, child = self.board.parent / "refix-run", self.board.parent / "child"
        second.mkdir()
        child.mkdir()
        board.adopt_prior_pass(second, self.board, ["1"], self.repo)
        board.adopt_inputs(second, child, self.repo)
        for place in (second, child):
            with self.subTest(place=place.name):
                got = tdd.start(place, self.repo, str(self.suite), json.dumps([CLAMP]))
                self.assertTrue(got["go"], got)
                rows = [{"unit_key": CLAMP, "route": "direct", "why": "2 回目の段で先にテストを書かない単位"}]
                self.assertTrue(tdd.step(got["state_file"], {"phase": "route", "units": rows}, self.repo)["ok"])
                self.assertEqual(len(tdd.states(place)), 2)
                self.assertEqual(board.ruled_states(place), (got["state_file"], got["state_file"]))
                self.assertEqual(facts.check_frozen(place, got["state_file"], self.repo, "first"), [])
                self.edit("test_stats.py", "mean([2, 4]), 3", "mean([2, 4]), 3.0")   # 2 回目の修正役が tdd-1 の凍ったテストを変えた
                problems = facts.check_frozen(place, got["state_file"], self.repo, "first")
                self.assertTrue(problems and "test_stats.py" in problems[0], problems)
                self.edit("test_stats.py", "mean([2, 4]), 3.0", "mean([2, 4]), 3")

    def test_second_loop_may_add_test_to_first_loop_file(self):
        self.first_loop()
        state2 = self.second_loop([CLAMP], route="tdd")
        self.add_test(FAR_TEST)
        got = tdd.step(state2, {"phase": "test", "unit_key": CLAMP, "test_files": ["test_stats.py"], "tests": [FAR_ID]},
                           self.repo)
        self.assertTrue(got["ok"], got)
        self.edit("stats.py", "    if x > hi:\n        return lo", "    if x > hi:\n        return hi")
        got = tdd.step(state2, {"phase": "fix", "unit_key": CLAMP, "files": ["stats.py"], "what": "上限で hi を返す"},
                           self.repo)
        self.assertTrue(got["done"], got)
        self.assertEqual(tdd.frozen_problems(self.state, self.repo), [],
                         "tdd-1 の関数を変えずに足しただけは since が無くても凍結に数えない（依頼 195i の 2）")
        self.assertEqual(tdd.frozen_problems(self.state, self.repo, since=self.since(state2)), [])
        self.edit("test_stats.py", "clamp(20, 0, 10), 10", "clamp(20, 0, 10), 0")
        self.assertTrue(tdd.frozen_problems(state2, self.repo), "足したテストは tdd-2 の凍結で見る")

    def test_amended_units_old_test_span_is_not_frozen(self):
        self.first_loop()
        state2 = self.second_loop([MEAN])
        since = self.since(state2)
        spans = tdd.test_spans(self.state, {MEAN})
        self.assertEqual(spans, [("test_stats.py", "TestStats::test_mean_of_two")])
        self.assertEqual(tdd.test_spans(self.state, {CLAMP}), [], "tdd-1 で緑にしていない単位の関数は無い")
        self.edit("test_stats.py", "mean([2, 4]), 3", "mean([2, 4, 6]), 4")
        self.assertTrue(tdd.frozen_problems(self.state, self.repo, since=since))
        self.assertEqual(tdd.frozen_problems(self.state, self.repo, since=since, skip_spans=spans), [])
        self.edit("test_stats.py", "clamp(5, 0, 10), 5", "clamp(6, 0, 10), 6")   # 関数の範囲の外
        got = tdd.frozen_problems(self.state, self.repo, since=since, skip_spans=spans)
        self.assertTrue(got and "範囲の外" in got[0], got)

    def test_frozen_source_reads_since_tree(self):
        """テストの変更の許しの行を引き直す木は、凍結の検査が比べる木（since）と同じ"""
        self.first_loop()
        state2 = self.second_loop([CLAMP])
        since = self.since(state2)
        self.edit("test_stats.py", "mean([2, 4]), 3", "mean([2, 4]), 3.0")
        read = tdd.frozen_source(self.state, self.repo, since=since)
        self.assertEqual(read("test_stats.py").rstrip("\n"), git(self.repo, "show", f"{since}:test_stats.py").rstrip("\n"))
        self.assertIn("mean([2, 4]), 3)", read("test_stats.py"))


class TestShapeless(LoopCase):
    """修正の形は g3 だけ（2026-10-09）: 輪の頭はいつも修正案の約束を読み、test_cmd の関門を決め、申告の無い単位は整えを飛ばす"""

    def test_contract_reads_the_fields(self):
        """欄の控えが在れば約束を組む"""
        fields = [{"unit_keys": [MEAN], "route": "tdd", "route_why": "", "rewrite_tests": [],
                   "tests": [{"id": "test_stats.py::TestStats::test_mean_of_two", "behavior": "2 つの値の平均",
                              "path": "stats.mean を直に呼ぶ", "red_kind": "assertion", "red_why": "今は len-1 で割る"}],
                   "refactor": {"declared": False, "why": ""}}]
        with mock.patch.object(tdd.conflict, "frozen_fields", return_value=fields):
            self.restart()
            self.assertEqual(list(self.st()["contract"]), [MEAN])
        self.assertNotIn("plain", self.st())

    def test_green_test_cmd_gate_is_on_and_refactor_needs_a_declaration(self):
        """緑の test_cmd は関門 on。申告の無い単位は整えを飛ばす"""
        self.restart(test_cmd=f"{sys.executable} -c pass")
        self.assertEqual(self.st()["test_cmd_gate"], tdd.GATE_ON)
        self.route()
        self.red()
        _, when = self.values()
        self.assertEqual([k for k, v in when.items() if k.startswith("phase_") and v], ["phase_fix"])
        self.assertTrue(when["gate"])
        self.assertIn("- **fix**:", self.prompt())
        self.assertTrue(self.fix_mean()["done"])
        self.assertEqual(self.st()["units"][MEAN]["refactor"], "skipped")


class TestResume(LoopCase):
    """実行基盤の resume（v0.11.1）は済みと記録していない輪を 1 周目から回し直す。確かめの節が状態に「済んだ」（か段 lanes）を保存した後、
    実行基盤が輪の済みを記録する前に止まった run の resume でも、支度は役を起こさずに go: false を返し、確かめは返答 null で何も
    動かさずに輪を抜ける（並べの枝の輪と同じ形。docs/plans/2026-10-07-lane-nodes.md の 4 の resume の項）"""

    def done_loop(self):
        self.route()
        self.red()
        self.assertTrue(self.fix_mean()["done"])

    def snap(self):
        return (pathlib.Path(self.state).read_bytes(),
                {n: (self.repo / n).read_bytes() for n in ("stats.py", "test_stats.py")})

    def test_running_loop_prep_says_go(self):
        self.route()
        got = tdd.prep(self.state)
        self.assertIs(got["go"], True)
        self.assertEqual(set(got), {"go", "new_unit", "state", "path", "briefs"})
        self.assertTrue(self.prompt())
        self.assertTrue(list(self.board.glob("tdd*-prompt-1.md")), "組んだ指示を place に書く")

    def test_done_loop_ends_without_the_role(self):
        self.done_loop()
        before = self.snap()
        self.assertEqual(tdd.prep(self.state), {"go": False, "new_unit": False})
        got = self.step(None)
        self.assertEqual((got["ok"], got["done"], got["phase"], got["reason"]), (True, True, "done", ""), got)
        self.assertEqual(self.snap(), before, "済んだ輪の周は状態と作業ツリーを動かさない")

    def test_reply_for_a_done_loop_is_still_refused(self):
        self.done_loop()
        with self.assertRaises(tdd.Broken):
            self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "x"})

    def test_missing_reply_in_a_running_loop_is_refused(self):
        """役が返さなかった周（済んでいない輪）は今どおり拒否に数える（役を飛ばしたのと取り違えない）"""
        self.route()
        got = self.step(None)
        self.assertFalse(got["ok"])
        self.assertEqual(self.st()["tries"], 1)

    def test_park_failure_then_next_call_parks_once(self):
        """単位を止めた周で申し出の積み（park）が落ちても（状態は止めた単位の分だけ進んで保存済み）、次の呼びの flush_unsent で
        同じ申し出がちょうど 1 件積まれ、その後の呼びは積み増さない（元は節 tdd-step が盤面の控えへ積んだ。積む口は呼び手が渡す）"""
        self.route()
        for _ in range(tdd.retry_max()):
            self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"], "tests": []})
        self.assertEqual(self.st()["parked"], [MEAN], "止めた単位は状態に保存済み")
        parked = []

        def broken(rows):
            raise ValueError("食い違いの控えが読めない")
        with self.assertRaises(ValueError):
            tdd.flush_unsent(self.state, broken)
        self.assertEqual(len(self.st()[tdd.UNSENT]), 1, "積めなかった申し出は状態に残る")
        for call in ("積み直す呼び", "積み増さない呼び"):
            tdd.flush_unsent(self.state, parked.extend)
            self.assertEqual([r["item"]["unit_key"] for r in parked], [MEAN], call)
            self.assertEqual(self.st().get(tdd.UNSENT), [], call)


class TddloopSeamsGoneCase(Case):
    def test_board_and_wrapper_seams_are_gone(self):
        """盤面・包みに届く名は持たない（元の rules の写しの読み・会話の鍵の書き）"""
        for name in ("RULES_GRAPH", "write_key", "RECEIVES", "adapter", "board", "entry", "script_io"):
            self.assertFalse(hasattr(tdd, name), name)




# ---------------------------------------------------------------- 実行器の段の一覧の外の試験（元 lib/tests/test_tdd_outside.py）
OUTSIDE = "heavy/test_outside.py"   # 実行器の既定の一覧（TIER）に無い置き場
NAMED = f"{OUTSIDE}::TestOutside::test_mean_of_two"

RUNNER = '''
import importlib.util, os, pathlib, sys, unittest, xml.etree.ElementTree as ET
sys.dont_write_bytecode = True
sys.path.insert(0, ".")
TIER = ["test_stats.py"]
out, rest = sys.argv[1], sys.argv[2:]
words, extra, i = None, [], 0
while i < len(rest):
    if rest[i] == "-k":
        words = [w.strip() for w in rest[i + 1].split(" or ") if w.strip()]
        i += 2
        continue
    extra.append(rest[i])
    i += 1
targets = ([] if os.environ.get("TDD_SUITE_ONLY") == "1" and extra else list(TIER)) + extra
rows, seen = [], set()
for target in targets:
    path, _, sel = target.partition("::")
    p = pathlib.Path(path)
    spec = importlib.util.spec_from_file_location(p.stem, str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    def flat(s):
        for t in s:
            yield from (flat(t) if isinstance(t, unittest.TestSuite) else [t])
    for t in flat(unittest.defaultTestLoader.loadTestsFromModule(mod)):
        tid = t.id()
        if sel and not tid.endswith("." + sel.replace("::", ".")):
            continue
        if words is not None and not any(w in tid for w in words):
            continue
        if tid in seen:
            continue
        seen.add(tid)
        r = unittest.TestResult()
        t.run(r)
        kind = "error" if r.errors else "failure" if r.failures else "skipped" if r.skipped else None
        rows.append((tid, kind))
root = ET.Element("testsuite")
for tid, kind in rows:
    cls, name = tid.rsplit(".", 1)
    tc = ET.SubElement(root, "testcase", classname=cls, name=name)
    if kind:
        ET.SubElement(tc, kind)
ET.ElementTree(root).write(out)
sys.exit(0 if all(k in (None, "skipped") for _, k in rows) else 1)
'''

EMPTY_RUNNER = '''
import sys
open(sys.argv[1], "w").write("<testsuite></testsuite>")
'''

OUTSIDE_TEST = '''import unittest

from stats import mean


class TestOutside(unittest.TestCase):
    def test_mean_of_two(self):
        self.assertEqual(mean([2, 4]), 3)
'''

OUTSIDE_PASSING = '''import unittest


class TestOutside(unittest.TestCase):
    def test_sum(self):
        self.assertEqual(1 + 1, 2)
'''


class OutsideCase(Case):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name)
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, SEED)

    def begin(self, runner=RUNNER):
        suite = self.tmp / "suite.py"
        suite.write_text(runner, encoding="utf-8")
        got = tdd.start(self.tmp / "art" / "board", self.repo, str(suite), json.dumps([MEAN], ensure_ascii=False))
        self.assertTrue(got["go"], got)
        return got["state_file"]

    def write(self, rel, text):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


class TestLoopOutsideTier(OutsideCase):
    def test_named_test_outside_tier_goes_red_then_green(self):
        state = self.begin()
        got = tdd.step(state, {"phase": "route", "units": [{"unit_key": MEAN, "route": "tdd"}]}, self.repo)
        self.assertTrue(got["ok"], got)
        self.write(OUTSIDE, OUTSIDE_TEST)
        got = tdd.step(state, {"phase": "test", "unit_key": MEAN, "test_files": [OUTSIDE], "tests": [NAMED]}, self.repo)
        self.assertTrue(got["ok"], f"段の外のファイルの名指しが赤として受からない: {got['reason']}")
        p = self.repo / "stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        got = tdd.step(state, {"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を len(xs) にした"},
                           self.repo)
        self.assertTrue(got["ok"], f"段の外のファイルの名指しが緑として受からない: {got['reason']}")


NAMED_IN_TIER = "test_stats.py::TestStats::test_mean_of_two"


class TestLoopRunsOnlyWhatItChecks(OutsideCase):
    """輪の赤・緑の回は一式を回さない: 赤は名指しだけ、緑は名指しと単位の変更（単位の頭から）が届く試験のうち元の一式に
    載ったモジュールのファイルだけを TDD_SUITE_ONLY=1 で走らせる（届いただけで元の一式の外の試験は受け付け・最後のテストの段へ）"""

    def setUp(self):
        super().setUp()
        self.write(OUTSIDE, OUTSIDE_TEST)   # stats に届くが、元の一式（TIER）の外
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "段の外の試験（stats に届く）")
        self.log = self.tmp / "runs.jsonl"
        self.state = self.begin("import json, os, sys\nopen(%r, 'a').write(json.dumps([os.environ.get('TDD_SUITE_ONLY'), "
                                "sys.argv[2:]]) + '\\n')\n" % str(self.log) + RUNNER)

    def runs(self):
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def step(self, reply):
        return tdd.step(self.state, reply, self.repo)

    def red(self):
        self.assertTrue(self.step({"phase": "route", "units": [{"unit_key": MEAN, "route": "tdd"}]})["ok"])
        p = self.repo / "test_stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("\n\nif __name__", NEW_TEST + "\n\nif __name__"), encoding="utf-8")
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"], "tests": [NAMED_IN_TIER]})
        self.assertTrue(got["ok"], got)

    def fix(self, also=None):
        p = self.repo / "stats.py"
        text = p.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)")
        p.write_text(also(text) if also else text, encoding="utf-8")
        return self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を len(xs) にした"})

    def test_baseline_is_the_whole_suite(self):
        self.assertEqual(self.runs(), [[None, []]], "元の結末は合図なしの一式")

    def test_red_runs_only_the_named_tests(self):
        self.red()
        self.assertEqual(self.runs()[1], ["1", [str(self.repo.absolute() / NAMED_IN_TIER)]])

    def test_green_runs_named_and_reached_files_of_the_baseline(self):
        self.red()
        got = self.fix()
        self.assertTrue(got["ok"], got)
        only, args = self.runs()[2]
        self.assertEqual(only, "1")
        self.assertEqual(sorted(args), sorted([str(self.repo.absolute() / NAMED_IN_TIER),
                                               str(self.repo.absolute() / "test_stats.py")]))
        self.assertFalse([a for a in args if OUTSIDE in a], "届いただけで元の一式の外の試験は輪で回さない")

    def test_regression_in_reached_test_is_caught_at_green(self):
        self.red()
        got = self.fix(lambda t: t.replace("    return x\n", "    return lo\n"))
        self.assertFalse(got["ok"])
        self.assertIn("test_clamp_within_range", got["reason"])

    def test_map_failure_runs_the_whole_suite(self):
        self.red()
        with mock.patch.object(tdd.impact, "map", side_effect=RuntimeError("地図が引けない")):
            got = self.fix()
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.runs()[2], [None, [str(self.repo.absolute() / NAMED_IN_TIER)]], "地図が引けなければ一式と名指し")


class TestAcceptOutsideTier(OutsideCase):
    def test_changed_test_outside_tier_is_run_and_new_red_is_caught(self):
        self.write(OUTSIDE, OUTSIDE_PASSING)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "段の外の試験")
        state = self.begin()
        self.write(OUTSIDE, OUTSIDE_PASSING.replace("1 + 1, 2", "1 + 1, 3"))
        probs, note = tdd.selected_problems(state, self.repo, "HEAD")
        self.assertTrue(probs, f"版で通っていた段の外の試験の赤を受け付けが拾わない（知らせ: {note}）")
        self.assertEqual(len(probs), 1, "行はテストのファイルごと")
        self.assertIn("test_sum", probs[0])
        self.assertIn(f"（ファイル {OUTSIDE}）", probs[0], "行は段の外のテストのファイルのパスを名指す")
        self.assertEqual(git(self.repo, "diff", "--name-only"), OUTSIDE, "比べた後も作業ツリーは直した後の姿のまま")

    def test_base_copy_runs_once_per_rev_and_args(self):
        """元の結末に無い赤を版の写しで比べる回（_base_reds）は、版と実行器と後ろの引数が同じなら run に 1 回だけ走らせ、
        受け付けの回をまたいで結末を使い回す（版は run の中で動かない。195g は回ごとに一式を版の写しで 3 分半走らせ直した）。
        版が変われば走らせ直す"""
        self.write(OUTSIDE, OUTSIDE_PASSING)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "段の外の試験")
        cwd_log = self.tmp / "cwd.txt"
        state = self.begin("import os\nopen(%r, 'a').write(os.getcwd() + '\\n')\n" % str(cwd_log) + RUNNER)
        self.write(OUTSIDE, OUTSIDE_PASSING.replace("1 + 1, 2", "1 + 1, 3"))

        def copies():
            return [d for d in cwd_log.read_text(encoding="utf-8").splitlines()
                    if pathlib.Path(d).resolve() != self.repo.resolve()]
        first = tdd.selected_problems(state, self.repo, "HEAD")
        self.assertTrue(first[0], first)
        self.assertEqual(len(copies()), 1, "版の写しで 1 回走る")
        again = tdd.selected_problems(state, self.repo, "HEAD")
        self.assertEqual(again, first, "使い回しても判定は同じ")
        self.assertEqual(len(copies()), 1, "同じ版・同じ引数の 2 回目は版の写しを走らせない")
        (self.repo / "note.txt").write_text("x", encoding="utf-8")
        git(self.repo, "add", "note.txt")
        git(self.repo, "commit", "-q", "-m", "版を進める")
        self.write(OUTSIDE, OUTSIDE_PASSING.replace("1 + 1, 2", "1 + 1, 3"))
        tdd.selected_problems(state, self.repo, "HEAD~0")
        self.assertEqual(len(copies()), 2, "版が変われば走らせ直す")

    def test_base_copy_args_lie_under_real_cwd(self):
        """版の写しの回で実行器に渡す絶対パスの引数は、実行器の起こし場所（os.getcwd() が返す実のパス）の下に在る。
        一時の置き場の根が symlink を経ても、名指しの絶対パスの綴りと、実行器が起こし場所から解く相対の段のファイルの綴りが
        分かれると、引数どうしの共通の祖先が「/」に落ち、pytest の rootdir が変わって写しの結末の鍵が今の木の鍵と合わなくなる"""
        self.write(OUTSIDE, OUTSIDE_PASSING)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "段の外の試験")
        log = self.tmp / "runs.jsonl"
        state = self.begin("import json, os, sys\nopen(%r, 'a').write(json.dumps([os.getcwd(), sys.argv[2:]]) + '\\n')\n"
                           % str(log) + RUNNER)
        self.write(OUTSIDE, OUTSIDE_PASSING.replace("1 + 1, 2", "1 + 1, 3"))
        real, link = self.tmp / "real-tmp", self.tmp / "link-tmp"
        real.mkdir()
        link.symlink_to(real)
        with mock.patch.object(tempfile, "tempdir", str(link)):
            first = tdd.selected_problems(state, self.repo, "HEAD")
        self.assertTrue(first[0], first)
        rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        copies = [(cwd, args) for cwd, args in rows if pathlib.Path(cwd) != self.repo.resolve()]
        self.assertEqual(len(copies), 1, "版の写しで 1 回走る")
        cwd, args = copies[0]
        paths = [a.partition("::")[0] for a in args if a.startswith("/")]
        self.assertTrue(paths, f"版の写しの回に絶対パスの引数が無い: {args}")
        self.assertTrue(pathlib.Path(cwd).is_relative_to(real.resolve()), f"版の写しが実の置き場の下に無い: {cwd}")
        for p in paths:
            self.assertTrue(pathlib.Path(p).is_relative_to(cwd), f"引数 {p} が起こし場所 {cwd} の下に無い（symlink の綴りのまま）")

    def test_base_copy_lets_tests_read_git(self):
        """版の写しは git の保管庫を持つので、git を読む試験は版で緑になり、今の木で壊した時に新しい赤として拾われる。
        比べた後に一時の木は残らず、作業ツリーと枝は元のまま"""
        reads_git = (
            "import subprocess\nimport unittest\n\n\n"
            "class TestOutside(unittest.TestCase):\n"
            "    def test_lists_itself(self):\n"
            "        got = subprocess.run([\"git\", \"ls-files\", \"heavy\"], capture_output=True, text=True).stdout\n"
            f"        self.assertIn(\"{OUTSIDE}\", got)\n")
        self.write(OUTSIDE, reads_git)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "git を読む段の外の試験")
        state = self.begin()
        self.write(OUTSIDE, reads_git.replace(f'assertIn("{OUTSIDE}"', 'assertIn("heavy/nothing.py"'))
        branch = git(self.repo, "rev-parse", "--abbrev-ref", "HEAD")
        probs, note = tdd.selected_problems(state, self.repo, "HEAD")
        self.assertTrue(probs, f"版の写しで git を読めず、版でも赤と数えて新しい赤から外した（知らせ: {note}）")
        self.assertIn("test_lists_itself", probs[0])
        self.assertEqual(len(git(self.repo, "worktree", "list").splitlines()), 1, "比べた後に一時の木が残る")
        self.assertEqual(git(self.repo, "diff", "--name-only"), OUTSIDE, "比べた後も作業ツリーは直した後の姿のまま")
        self.assertEqual(git(self.repo, "rev-parse", "--abbrev-ref", "HEAD"), branch, "枝が動いた")

    def test_base_reds_left_out_are_named_in_note(self):
        """版の写しでも赤だったので新しい赤から外した試験は、黙って外さず、件数と名を知らせに出す。外した物が無い時は足さない"""
        failing = OUTSIDE_PASSING.replace("1 + 1, 2", "1 + 1, 3")
        self.write(OUTSIDE, failing)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "版でも赤の段の外の試験")
        state = self.begin()
        self.write(OUTSIDE, failing + "\n# 版と同じく赤のまま\n")
        probs, note = tdd.selected_problems(state, self.repo, "HEAD")
        self.assertEqual(probs, [], "版でも赤の試験は新しい赤に数えない")
        self.assertIn("新しい赤なし", note)
        self.assertIn("版の写しでも赤だったので外した 1 件", note)
        self.assertIn("test_sum", note, "外した試験の名を出す")

        self.write(OUTSIDE, OUTSIDE_PASSING)
        _, quiet = tdd.selected_problems(state, self.repo, "HEAD")
        self.assertNotIn("外した", quiet, "外した物が 0 件なら何も足さない")

    def test_zero_selected_cases_are_not_reported_as_no_new_red(self):
        state = self.begin(EMPTY_RUNNER)
        p = self.repo / "stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        probs, note = tdd.selected_problems(state, self.repo, "HEAD")
        self.assertNotIn("新しい赤なし", note, "選んだ試験が 1 件も走らないのを緑に見せる（fail-open）")
        self.assertIn("0 件", " ".join(probs) + note)
        # 修正の受け付けはその知らせを捨てず、置き場の隣のファイル accept-trace.json に盤面の trace の行の形で積む
        # （元 works/blk-fix/scripts/accept.py:708 の TESTS_OP の行。読むのは最後の関所と報告）
        import impact
        place = pathlib.Path(state).parent.parent
        for attempt in (1, 2):
            board.accept_reply({"changes": []}, place, self.repo, pass_="first", iteration=attempt, owed=[], state=state,
                                  base_rev="HEAD")
        rows = json.loads((place / board.ACCEPT_TRACE_FILE).read_text(encoding="utf-8"))
        self.assertEqual([(r["op"], r["pass"], r["attempt"]) for r in rows],
                         [(impact.ACCEPT_TRACE_OP, "first", 1), (impact.ACCEPT_TRACE_OP, "first", 2)], "回ごとに足す（上書きしない）")
        self.assertIn("0 件", rows[0]["note"])
        self.assertNotIn("新しい赤なし", rows[0]["note"])
        self.assertEqual({k for k in ("ci_left", "final_left", "final_far") if isinstance(rows[0].get(k), list)},
                         {"ci_left", "final_left", "final_far"})

    def test_unchanged_test_outside_tier_is_left_out_of_local_run(self):
        # ADR 0071 の 3 の 1: 手元は速い段と変えた・足した試験だけ。届いただけで変えていない段の外の試験は走らせない
        self.write(OUTSIDE, OUTSIDE_TEST)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "段の外の試験（stats に届く）")
        argv_log = self.tmp / "argv.jsonl"
        state = self.begin("import json, sys\nopen(%r, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n" % str(argv_log)
                           + RUNNER)
        p = self.repo / "stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        tdd.selected_problems(state, self.repo, "HEAD")
        runs = [json.loads(line) for line in argv_log.read_text(encoding="utf-8").splitlines()][1:]   # 頭は元の結末の回
        self.assertTrue(runs, "受け付けが実行器を走らせていない")
        for argv in runs:
            self.assertFalse([a for a in argv if a.endswith(OUTSIDE)],
                             f"変えていない段の外の試験のファイルを受け付けが実行器の後ろに足した: {argv}")

    def test_tests_left_out_are_named_as_left_to_ci(self):
        # 手元で回さなかった試験は黙って減らさず、知らせと状態のファイルに『手元で回さなかった』として名前で残す
        self.write(OUTSIDE, OUTSIDE_TEST)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "段の外の試験（stats に届く）")
        state = self.begin()
        p = self.repo / "stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        probs, note = tdd.selected_problems(state, self.repo, "HEAD")
        self.assertEqual(probs, [], note)
        self.assertIn("手元で回さなかった", note)
        self.assertIn(OUTSIDE, note)
        self.assertNotIn("test_stats.py", note.split("手元で回さなかった", 1)[1], "手元で走った試験を回さなかったと言う")
        self.assertEqual(tdd.load_state(state).get("ci_left"), [OUTSIDE])

    def test_accept_args_name_only_pytest_modules(self):
        # impact がテストと呼ぶ物のうち、pytest の試験のモジュールでない物（conftest・実行器の台本・シェルの試験）は足さない
        names = ["t/test_a.py", "t/b_test.py", "t/conftest.py", "t/run-suite.py", "t/x-case.py", "t/y.bats", "t/gone_test.py"]
        for n in names[:-1]:
            self.write(n, "")
        self.assertEqual(tdd._args(self.repo, names, "a or b"),
                         [str(self.repo.absolute() / "t/test_a.py"), str(self.repo.absolute() / "t/b_test.py"), "-k", "a or b"])




WRAP = "from stats import mean\n\n\ndef mean_twice(xs):\n    return 2 * mean(xs)\n"
WRAP_FAR = "test_far.py"   # stats を wrap 越しに読む（深さ 2。変更に直には関わらない）
WRAP_FAR_TEST = '''import unittest

from wrap import mean_twice


class TestFar(unittest.TestCase):
    def test_twice(self):
        self.assertEqual(mean_twice([2, 4]), 6)
'''


class TestDirectOnly(OutsideCase):
    """受け付けと輪の緑は、変更に直に関わる試験（変えた試験・変えた file を直に読む・言及する試験・修正案が名指す試験）だけを
    回す。届いただけの先の試験は回さず、受け付けは『最後のテストの段に任せた』として名前で残す（一式は線の最後のテストの段で 1 回）"""

    def setUp(self):
        super().setUp()
        self.write("wrap.py", WRAP)
        self.write(WRAP_FAR, WRAP_FAR_TEST)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "stats に深さ 2 で届く試験")
        self.log = self.tmp / "runs.jsonl"
        self.state = self.begin("import json, os, sys\nopen(%r, 'a').write(json.dumps([os.environ.get('TDD_SUITE_ONLY'), "
                                "sys.argv[2:]]) + '\\n')\n" % str(self.log)
                                + RUNNER.replace('TIER = ["test_stats.py"]', f'TIER = ["test_stats.py", "{WRAP_FAR}"]'))

    def runs(self):
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def fix_stats(self):
        p = self.repo / "stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")

    def test_accept_runs_only_direct_tests_and_leaves_far_ones_to_final_stage(self):
        self.fix_stats()
        probs, note = tdd.selected_problems(self.state, self.repo, "HEAD")
        self.assertEqual(probs, [], note)
        self.assertEqual(self.runs()[-1], [None, ["-k", "test_stats"]], "先の試験を -k に入れた")
        self.assertEqual(tdd.final_left(self.state), [WRAP_FAR])
        self.assertIn("最後のテストの段に任せた", note)
        self.assertIn(WRAP_FAR, note.split("最後のテストの段に任せた", 1)[1])

    def test_far_unanalysable_does_not_force_the_whole_suite(self):
        self.write("far_loader.py", "import importlib\nimport wrap\n\n\ndef load(name):\n"
                                    "    return importlib.import_module(name)\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "深さ 2 の動的 import")
        self.fix_stats()
        probs, note = tdd.selected_problems(self.state, self.repo, "HEAD")
        self.assertEqual(probs, [], note)
        self.assertEqual(self.runs()[-1], [None, ["-k", "test_stats"]], "遠くの分からない物で一式を回した")
        self.assertEqual(tdd.final_far(self.state), ["dynamic-import: far_loader.py:6"])
        self.assertIn("far_loader.py", note.split("最後のテストの段に任せた", 1)[1])

    def test_accept_runs_tests_named_by_the_plan(self):
        st = tdd.load_state(self.state)
        st["contract"] = {MEAN: {"route": "tdd", "tests": [{"id": f"{WRAP_FAR}::TestFar::test_twice"}], "rewrites": []}}
        pathlib.Path(self.state).write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
        self.fix_stats()
        tdd.selected_problems(self.state, self.repo, "HEAD")
        self.assertEqual(self.runs()[-1], [None, ["-k", "test_far or test_stats"]], "修正案が名指す試験を回さない")
        self.assertEqual(tdd.final_left(self.state), [])

    def test_green_adds_only_direct_files_of_the_baseline(self):
        self.assertTrue(tdd.step(self.state, {"phase": "route", "units": [{"unit_key": MEAN, "route": "tdd"}]},
                                     self.repo)["ok"])
        p = self.repo / "test_stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("\n\nif __name__", NEW_TEST + "\n\nif __name__"), encoding="utf-8")
        got = tdd.step(self.state, {"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                                        "tests": [NAMED_IN_TIER]}, self.repo)
        self.assertTrue(got["ok"], got)
        self.fix_stats()
        got = tdd.step(self.state, {"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を len(xs) にした"},
                           self.repo)
        self.assertTrue(got["ok"], got)
        only, args = self.runs()[-1]
        self.assertEqual(only, "1")
        self.assertFalse([a for a in args if a.endswith(WRAP_FAR)], f"深さ 2 の試験を緑の回に足した: {args}")


# ---------------------------------------------------------------- 裁定の範囲の関数の幅（元 lib/tests/test_tdd_frozen_function_span.py）
SPAN_SRC = """import unittest


class T(unittest.TestCase):
    def test_a(self):
        self.assertEqual(1, 1)

    # b の説明
    @unittest.skipIf(False, "x")
    def test_b(self):
        # 本体のコメント
        self.assertEqual(2, 2)

    def test_c(self):
        self.assertEqual(3, 3)
"""
F = "test_span.py"
N = "notes.txt"


class FunctionSpanCase(Case):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = pathlib.Path(self._tmp.name)
        self.repo = tmp / "repo"
        committed_copy(self.repo, SEED)
        (self.repo / F).write_text(SPAN_SRC, encoding="utf-8")
        (self.repo / N).write_text("a\nb\nc\n", encoding="utf-8")
        self.state = tmp / "state.json"
        st = {"frozen": tdd.hashes(self.repo, [F, N]), "frozen_tree": tdd.snapshot(self.repo)}
        self.state.write_text(json.dumps(st), encoding="utf-8")

    def edit(self, old, new, path=F):
        p = self.repo / path
        text = p.read_text(encoding="utf-8")
        self.assertIn(old, text)
        p.write_text(text.replace(old, new, 1), encoding="utf-8")

    def frozen(self, *allowed):
        return tdd.frozen_problems(str(self.state), self.repo, allowed=list(allowed))

    def test_def_line_allows_decorator_comment_def_and_body(self):
        for old, new in [("@unittest.skipIf(False", "@unittest.skipIf(True"), ("# b の説明", "# b を直した説明"),
                         ("def test_b", "def test_bb"), ("# 本体のコメント", "# 本体"), ("assertEqual(2, 2)", "assertEqual(2, 2.0)")]:
            with self.subTest(old=old):
                self.setUp()
                self.edit(old, new)
                self.assertEqual(self.frozen(f"{F}:10"), [])

    def test_body_line_allows_def_of_same_function(self):
        self.edit("def test_b", "def test_bb")
        self.assertEqual(self.frozen(f"{F}:12"), [])

    def test_neighbour_function_is_rejected(self):
        for old in ("assertEqual(1, 1)", "assertEqual(3, 3)"):
            with self.subTest(old=old):
                self.setUp()
                self.edit(old, old.replace(")", ".0)"))
                self.assertTrue(self.frozen(f"{F}:10"))

    def test_class_line_is_not_widened(self):
        self.edit("class T(", "class U(")
        self.assertTrue(self.frozen(f"{F}:10"))

    def test_insert_above_decorator_is_inside(self):
        self.edit("    # b の説明\n", "    @unittest.expectedFailure\n    # b の説明\n")
        self.assertEqual(self.frozen(f"{F}:10"), [])

    def test_previous_trailing_comment_is_not_absorbed(self):
        (self.repo / F).write_text("class T:\n    def a(self):\n        pass\n        # a の末尾\n    def b(self):\n        pass\n",
                                   encoding="utf-8")
        st = json.loads(self.state.read_text())
        st["frozen_tree"] = tdd.snapshot(self.repo)
        st["frozen"] = tdd.hashes(self.repo, [F, N])
        self.state.write_text(json.dumps(st), encoding="utf-8")
        self.edit("# a の末尾", "# a の末尾を直した")
        self.assertTrue(self.frozen(f"{F}:6"))

    def test_explicit_range_is_not_widened(self):
        self.edit("def test_b", "def test_bb")
        self.assertTrue(self.frozen(f"{F}:12-12"))
        self.assertEqual(self.frozen(f"{F}:8-12"), [])

    def test_non_python_stays_one_line(self):
        self.edit("b", "B", N)
        self.assertTrue(self.frozen(f"{N}:1"))
        self.assertEqual(self.frozen(f"{N}:2"), [])

    def test_unparsable_old_text_stays_one_line(self):
        (self.repo / F).write_text("def f(:\n  x\n", encoding="utf-8")
        st = json.loads(self.state.read_text())
        st["frozen_tree"] = tdd.snapshot(self.repo)
        st["frozen"] = tdd.hashes(self.repo, [F, N])
        self.state.write_text(json.dumps(st), encoding="utf-8")
        self.edit("  x", "  y")
        self.assertTrue(self.frozen(f"{F}:1"))




# ---------------------------------------------------------------- 事後の関門の赤緑（元 lib/tests/test_fix_gates.py の TestRedGreen。src/gates.py）
THREE_ID = "test_stats.py::TestStats::test_mean_of_three"
TEST_ROW = {"id": MEAN_ID, "behavior": "2 つの値の平均", "path": "stats.mean を直に呼ぶ", "red_kind": "assertion",
            "red_why": "今は len-1 で割る"}
# 欄の形は test_plan_brief.FIELDS と同じ（unit_keys は修正案の項目の名指し。planmarks.split が欄に写す）
FIELDS = [{"unit_keys": [MEAN], "route": "tdd", "route_why": "", "tests": [TEST_ROW], "rewrite_tests": [],
           "refactor": {"declared": False, "why": ""}}]
MEAN_FIX = {"return sum(xs) / (len(xs) - 1)": "return sum(xs) / len(xs)"}
THREE_EDIT = ("self.assertEqual(mean([1, 2, 3]), 2)", "self.assertEqual(mean([1, 2, 3]), 2.0)")   # 既存のテストの期待の書き換え
HALVE = {"def clamp(x, lo, hi):": "def halve(x):\n    return x / 2\n\n\ndef clamp(x, lo, hi):"}   # 今の木で足す関数
TWO_ID = "test_two.py::TestTwo::test_halve"
TWO_FILE = ("import unittest\n\nfrom stats import halve\n\n\nclass TestTwo(unittest.TestCase):\n    def test_halve(self):\n"
            "        self.assertEqual(halve(4), 2)\n")   # base では読み込みで落ちる（halve が無い）新しいテストのファイル
NO_JUNIT = "import sys\nsys.exit(0)\n"   # JUnit を書かない実行器


def asked_row(paths=(), new_tests=(), decision="deny", granted_new_tests=(), **over):
    """範囲の相談の確かめの行（conflict.ASKED_OP。受け付けが見つけたはみ出しを聞いた物。origin accept）"""
    return {"id": 1, "at": "2026-10-10T00:00:00+09:00", "turn": 2, "pass": "first", "round": 1, "node": "plan-answer", "item": "1",
            "unit_keys": [MEAN], "paths": list(paths), "tests": [], "new_tests": list(new_tests), "why": "案の外のはみ出しを聞いた",
            "status": "answered", "decision": decision, "granted_paths": [], "granted_tests": [],
            "granted_new_tests": list(granted_new_tests), "spec": "", "reason": "範囲の中で直せる", "notes": [], "out_of_scope": [],
            "overrode_out_of_scope": [], "session": None, "origin": "accept", **over}


def direct_fields(**over):
    """受け入れのテストの無い direct の項目（red_green を回さず test_edits だけを見る）"""
    return [{**FIELDS[0], "route": "direct", "route_why": "既存の期待の書き換えだけの項目", "tests": [], **over}]


class FixGatesCase(Case):
    """種の git（self.repo）と fix の run の置き場（self.board。元の盤面の代わり）と小さな実行器"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="works-fix-gates-")
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name).resolve()
        self.repo = self.tmp / "repo"
        self.base = committed_copy(self.repo, SEED)
        self.board = self.tmp / "place"
        self.board.mkdir()
        self.suite = self.tmp / "suite.py"
        self.suite.write_text(PYTEST_LIKE, encoding="utf-8")
        self.SUITE = str(self.suite)

    def ready_with_fields(self, fields=None):
        """置き場に承認済みの修正案の欄の控え（凍結の印つき）を置く。base は種の commit"""
        planmarks.save(self.board, 1, FIELDS if fields is None else fields)
        return self.board

    def edit_tree(self, subs):
        path = self.repo / "stats.py"
        text = path.read_text(encoding="utf-8")
        for old, new in subs.items():
            self.assertIn(old, text)
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")

    def edit_tests(self, old, new):
        path = self.repo / "test_stats.py"
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def add_test(self, body):
        self.edit_tests("\n\nif __name__", body + "\n\nif __name__")

    def add_test_mean_of_two(self):
        self.add_test(NEW_TEST)

    def add_test_that_passes_on_base(self, name):
        self.add_test(f"\n    def {name}(self):\n        self.assertEqual(clamp(5, 0, 10), 5)\n")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True, encoding="utf-8", check=True,
                              env=hermetic.child_env()).stdout.strip()

    def fields_for(self, test_id):
        """受け入れのテスト test_id を 1 本持つ tdd の項目（単位は mean）"""
        return [{**FIELDS[0], "tests": [{**TEST_ROW, "id": test_id}]}]

    def problems(self, suite=None, attempt=1, base=None, **kw):
        return gates.problems(self.board, self.repo, self.base if base is None else base,
                                 self.SUITE if suite is None else suite, attempt, **kw)

    def ledger(self):
        return json.loads((self.board / gates.LEDGER).read_text(encoding="utf-8"))

    def worktrees(self):
        out = subprocess.run(["git", "worktree", "list"], cwd=self.repo, capture_output=True, text=True, encoding="utf-8", check=True,
                             env=hermetic.child_env()).stdout
        return out.strip().splitlines()


class TestRedGreen(FixGatesCase):
    def test_real_red_green_passes(self):
        self.ready_with_fields()                  # 項目 1: tdd・tests=[test_mean_of_two（red_kind assertion）]
        self.add_test_mean_of_two()
        self.edit_tree(MEAN_FIX)
        self.assertEqual(self.problems(), [])
        self.assertFalse((self.board / gates.LEDGER).exists(), "積む物が無ければ帳面を書かない")

    def test_test_green_at_base_is_a_miss(self):
        self.ready_with_fields()
        self.add_test_that_passes_on_base("test_mean_of_two")
        rows = self.problems()
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", MEAN_ID)])
        self.assertTrue(rows[0]["detail"].startswith("base で "), rows[0]["detail"])
        self.assertIn("もう通る", rows[0]["detail"])
        self.assertEqual(rows[0]["unit_keys"], [MEAN], "行は項目の単位を持つ（最後の回に unit_key で単位に結ぶ）")

    def test_wrong_red_kind_is_a_miss(self):
        """新しいテストが base で NameError（機能が無い）で落ちる failure でも、機械は赤の種類で拒まない。今の木で緑なら行は無い"""
        self.ready_with_fields()
        self.edit_tests("from stats import clamp, mean", "from stats import *  # noqa: F403")
        self.add_test("\n    def test_mean_of_two(self):\n        self.assertEqual(halve(4), 2)  # noqa: F405\n")
        self.edit_tree({"def clamp(x, lo, hi):": "def halve(x):\n    return x / 2\n\n\ndef clamp(x, lo, hi):"})
        self.assertEqual(self.problems(), [])

    def agree(self, tid, red_kind, **over):
        """範囲の相談の合意（allow の行）で、項目 1 に新しいテスト tid が入った置き場にする"""
        row = asked_row(new_tests=[tid], decision="allow", granted_new_tests=[{"id": tid, "red_kind": red_kind}], **over)
        board.trace(self.board, conflict.ASKED_OP, **row)

    def test_agreed_new_test_is_checked_red_green(self):
        """範囲の相談の合意で項目に入った新しいテストは、項目が direct（受け入れのテストが無い）でも事後の関門の red_green が
        確かめ、base で緑なら抜けの行になる"""
        self.ready_with_fields(direct_fields())
        self.agree(MEAN_ID, planmarks.AGREED_RED)
        self.add_test_that_passes_on_base("test_mean_of_two")
        rows = self.problems()
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", MEAN_ID)])
        self.assertIn("もう通る", rows[0]["detail"])

    def test_agreed_test_not_written_is_not_a_miss(self):
        """合意で入ったテストは許しで義務でない: 修正役が書かなければ関門に入れない（一式の結末に居ないの行にしない）"""
        self.ready_with_fields(direct_fields())
        self.agree(MEAN_ID, planmarks.AGREED_RED, origin="gate")
        self.edit_tree(MEAN_FIX)
        self.assertEqual(self.problems(), [])

    def test_agreed_test_written_under_other_name_is_not_a_miss(self):
        """合意の id と別の名で書いた時も、合意の id は関門に入れない（別の名のテストは範囲の照らしのはみ出しの側）"""
        self.ready_with_fields(direct_fields())
        self.agree(MEAN_ID, planmarks.AGREED_RED, origin="gate")
        self.add_test(NEW_TEST.replace("test_mean_of_two", "test_mean_pair"))
        self.edit_tree(MEAN_FIX)
        self.assertEqual(self.problems(), [])

    def test_later_agreement_fixes_red_kind(self):
        """同じ id を後の相談で守りのテストに直すと、後の合意が勝つ: base で緑でも抜けの行にならない"""
        self.ready_with_fields(direct_fields())
        self.agree(MEAN_ID, planmarks.AGREED_RED, origin="gate")
        self.agree(MEAN_ID, planmarks.GUARD_KIND, id=2, turn=3)
        self.add_test_that_passes_on_base("test_mean_of_two")
        self.assertEqual(self.problems(), [])

    def test_agreed_red_green_row_is_marked_for_revert(self):
        """合意のテストの red_green の行は印 agreed を持ち、overflow_asks がそのテストだけを戻す頼み（revert）にする"""
        self.ready_with_fields(direct_fields())
        self.agree(MEAN_ID, planmarks.AGREED_RED, origin="gate")
        self.add_test_that_passes_on_base("test_mean_of_two")
        (row,) = self.problems()
        self.assertTrue(row.get("agreed"), row)
        (ask,) = gates.overflow_asks([row], self.repo, self.base, [{"item": 1, "allowed_paths": ["test_stats.py"]}])
        self.assertEqual((ask["new_tests"], ask.get("revert")), ([MEAN_ID], True))

    def test_agreed_guard_test_needs_only_green_now(self):
        """合意の red_kind が守りのテスト（GUARD_KIND）の新しいテストは、base で緑でも抜けの行にならない。今の木で赤なら抜けの行"""
        self.ready_with_fields(direct_fields())
        self.agree(MEAN_ID, planmarks.GUARD_KIND)
        self.add_test_that_passes_on_base("test_mean_of_two")
        self.assertEqual(self.problems(), [], "base で緑でも守りのテストは抜けにならない")
        self.assertEqual(gates.guards(self.board, pass_="first", attempt=1), [{"id": MEAN_ID, "base": "passed"}],
                         "base の結末は帳面の guards に残る")
        self.edit_tests("    def test_mean_of_two(self):\n        self.assertEqual(clamp(5, 0, 10), 5)",
                        "    def test_mean_of_two(self):\n        self.assertEqual(clamp(5, 0, 10), 6)")
        rows = self.problems(attempt=2)
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", MEAN_ID)])
        self.assertIn("今の木", rows[0]["detail"])

    def test_guards_of_an_earlier_attempt_survive_a_later_write(self):
        """後の回が帳面に行を積んでも、前の回の守りのテストの base の結末は残る（元 works の誤りを直す）"""
        self.ready_with_fields(direct_fields())
        self.agree(MEAN_ID, planmarks.GUARD_KIND)
        self.add_test_that_passes_on_base("test_mean_of_two")
        self.assertEqual(self.problems(), [])
        self.edit_tests("    def test_mean_of_two(self):\n        self.assertEqual(clamp(5, 0, 10), 5)",
                        "    def test_mean_of_two(self):\n        self.assertEqual(clamp(5, 0, 10), 6)")
        self.assertTrue(self.problems(attempt=2), "2 回目は行を積む")
        self.assertEqual(gates.guards(self.board, pass_="first", attempt=1), [{"id": MEAN_ID, "base": "passed"}])

    def test_not_green_now_is_a_miss(self):
        """受け入れのテストが base で正しく赤でも、今の木で緑でなければ行（直していない）"""
        self.ready_with_fields()
        self.add_test_mean_of_two()
        rows = self.problems()
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", MEAN_ID)])
        self.assertIn("今の木で failure", rows[0]["detail"])

    def test_base_missing_and_non_failure_are_misses(self):
        with self.subTest("base で一式の結末に居ない（読み込みで落ちる）"):
            self.ready_with_fields(self.fields_for(TWO_ID))
            (self.repo / "test_two.py").write_text(TWO_FILE, encoding="utf-8")
            self.edit_tree(HALVE)
            rows = self.problems()
            self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", TWO_ID)])
            self.assertTrue(rows[0]["detail"].startswith("base で "), rows[0]["detail"])
            self.assertIn("一式の結末に居ない", rows[0]["detail"])
        with self.subTest("base で error（failure でない赤）"):
            self.suite.write_text(SUITE, encoding="utf-8")   # 本体の例外を error と書く実行器
            (self.repo / "test_two.py").unlink()
            self.edit_tests("from stats import clamp, mean", "from stats import *  # noqa: F403")
            self.add_test("\n    def test_mean_of_two(self):\n        self.assertEqual(halve(4), 2)  # noqa: F405\n")
            planmarks.save(self.board, 1, FIELDS)
            rows = self.problems(attempt=2)
            self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", MEAN_ID)])
            self.assertTrue(rows[0]["detail"].startswith("base で "), rows[0]["detail"])
            self.assertIn("error で落ちた", rows[0]["detail"])
            self.assertNotIn(gates.tddloop.NOT_RAN, rows[0]["detail"], "言い足しは輪の呼び手だけで、事後の関門の行には入らない")

    def test_base_row_carries_loop_red_check_text(self):
        """base の木の行の detail は『base で 』と、輪と同じ red_check が同じ JUnit の行に返す事実の文で出来ている（NOT_RAN を含まない）"""
        self.ready_with_fields()
        self.suite.write_text(SUITE, encoding="utf-8")   # 本体の例外を error と書く実行器（base の木で mean の名指しが error）
        self.edit_tests("from stats import clamp, mean", "from stats import *  # noqa: F403")
        self.add_test("\n    def test_mean_of_two(self):\n        self.assertEqual(halve(4), 2)  # noqa: F405\n")
        self.edit_tree(HALVE)
        rows = self.problems()
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", MEAN_ID)])
        row = {"classname": "test_stats.TestStats", "name": "test_mean_of_two", "outcome": "error", "fail_message": "", "fail_text": ""}
        probs, _ = gates.tddloop.red_check([MEAN_ID], [row], None, None)
        self.assertEqual(rows[0]["detail"], "base で " + "；".join(probs))
        self.assertIn("error で落ちた", rows[0]["detail"])
        self.assertNotIn(gates.tddloop.NOT_RAN, rows[0]["detail"])

    def test_runner_inside_repo_runs_its_base_copy(self):
        """実行器が対象のリポジトリの中に在れば、base の木では worktree の中の base の版を走らせる"""
        self.ready_with_fields()
        runner = self.repo / "runner.py"
        runner.write_text(PYTEST_LIKE, encoding="utf-8")
        self.git("add", "runner.py")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "runner")
        head = self.git("rev-parse", "HEAD")
        # 今の木の実行器は、印のファイルが無い置き場（base の worktree）では受け入れのテストを緑と書く（base の版を走らせない誤りを露わにする）
        runner.write_text("import os, sys\nif not os.path.exists('now-only.txt'):\n    open(sys.argv[1], 'w').write("
                          "'<testsuite><testcase classname=\"test_stats.TestStats\" name=\"test_mean_of_two\"/></testsuite>')\n"
                          "    sys.exit(0)\n" + PYTEST_LIKE, encoding="utf-8")
        (self.repo / "now-only.txt").write_text("", encoding="utf-8")
        self.add_test_mean_of_two()
        self.edit_tree(MEAN_FIX)
        self.assertEqual(self.problems(suite=str(runner), base=head), [])

    def test_runner_without_junit_skips_and_records(self):
        """今の木で実行器が JUnit を書かない → 拒まず、帳面の skipped に理由（受けた回は呼び手が trace にも載せる）"""
        self.ready_with_fields()
        self.add_test_that_passes_on_base("test_mean_of_two")
        self.suite.write_text(NO_JUNIT, encoding="utf-8")
        self.assertEqual(self.problems(), [])
        why = gates.skipped(self.board, pass_="first", attempt=1)
        self.assertEqual(len(why), 1, why)
        self.assertTrue(why[0].startswith(gates.NO_RUN), why)
        self.assertIn("今の木", why[0])
        self.assertEqual(gates.unchecked(self.board, pass_="first", attempt=1), why, "確かめずに通した理由に数える")

    def test_base_tree_that_cannot_be_made_skips_and_records(self):
        """base の版から worktree を作れない（commit でない版）→ 拒まず、帳面の skipped に理由。worktree は残さない"""
        self.ready_with_fields()
        self.add_test_that_passes_on_base("test_mean_of_two")
        tree = self.git("rev-parse", f"{self.base}^{{tree}}")
        self.assertEqual(self.problems(base=tree), [])
        why = gates.skipped(self.board, pass_="first", attempt=1)
        self.assertEqual(len(why), 1, why)
        self.assertTrue(why[0].startswith(gates.NO_RUN), why)
        self.assertIn("base の木", why[0])
        self.assertEqual(len(self.worktrees()), 1, self.worktrees())

    def test_no_suite_skips_and_records(self):
        self.ready_with_fields()
        self.add_test_that_passes_on_base("test_mean_of_two")
        self.assertEqual([r for r in self.problems(suite="") if r["gate"] == "red_green"], [])
        self.assertEqual(self.ledger()["skipped"][0]["why"], gates.NO_SUITE)

    def test_board_without_loop_freeze_gets_both_gates(self):
        """受け付けに輪の凍結の控えが無い run: 束が赤緑と既存テストの変更の両方を当てる（輪の凍結の検査 1b は控えの無い run で
        何も見ないので、その凍結はこの束だけが受け持つ。Preflight F13）"""
        self.ready_with_fields()
        self.add_test_that_passes_on_base("test_mean_of_two")
        self.edit_tests(*THREE_EDIT)
        rows = self.problems()
        self.assertEqual(sorted((r["gate"], r["id"]) for r in rows), [("red_green", MEAN_ID), ("test_edits", THREE_ID)])

    def park_mean(self):
        conflict.park(self.board, [{"unit_key": MEAN, "between": [], "why_both_cannot_hold": "試験で止めた単位",
                                    "which_is_right": "unknown"}], source="fix",
                      ruling={"decision": conflict.ASK, "text": "試験で止めた", "limits": [], "by": "works:fix-accept"})

    def test_unit_out_of_duty_is_not_checked(self):
        """最後の回に止めた（ask_human に裁いた）単位だけを名指す項目は見ない（戻したテストを抜けに数えない）"""
        for owed in (None, [MEAN, CLAMP]):
            with self.subTest(owed=owed):
                self.setUp()
                self.ready_with_fields()
                self.park_mean()
                self.add_test_that_passes_on_base("test_mean_of_two")
                self.assertEqual(self.problems(owed=owed), [])
                why = gates.skipped(self.board, pass_="first", attempt=1)
                self.assertEqual(len(why), 1, why)
                for w in (gates.OUT_OF_DUTY, "項目 1", MEAN):   # 見なかった項目と単位を名指して残す
                    self.assertIn(w, why[0])
                self.assertEqual(gates.unchecked(self.board, pass_="first", attempt=1), [],
                                 "義務の外の項目は確かめずに通したに数えない")

    def test_withheld_unit_is_out_of_duty(self):
        """答え待ちの問いの出どころ（withheld）の単位だけを名指す項目も見ない。関所で答えて戻した単位（returned）は見る"""
        self.ready_with_fields()
        self.add_test_that_passes_on_base("test_mean_of_two")
        self.assertEqual(self.problems(owed=[MEAN, CLAMP], withheld=[MEAN]), [])
        self.assertTrue(gates.skipped(self.board, pass_="first", attempt=1)[0].startswith(gates.OUT_OF_DUTY))
        rows = self.problems(attempt=2, owed=[CLAMP], returned=[MEAN])
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", MEAN_ID)])

    def test_worktree_removed_after(self):
        self.ready_with_fields()
        self.add_test_that_passes_on_base("test_mean_of_two")
        self.problems()
        self.assertEqual(len(self.worktrees()), 1, self.worktrees())

    def test_worktree_removed_when_base_run_breaks(self):
        """base の木で実行器を走らせる所が落ちても、一時の worktree は消す"""
        self.ready_with_fields()
        self.add_test_that_passes_on_base("test_mean_of_two")
        real = gates.tddloop.run_suite

        def broken(exe, repo, *a, **k):
            if pathlib.Path(repo).resolve() != self.repo.resolve():
                raise RuntimeError("base の木で落ちた")
            return real(exe, repo, *a, **k)
        with mock.patch.object(gates.tddloop, "run_suite", side_effect=broken):
            with self.assertRaises(RuntimeError):
                self.problems()
        self.assertEqual(len(self.worktrees()), 1, self.worktrees())

    def test_suite_leftovers_are_removed_from_tree(self):
        """今の木で一式を走らせて出来たファイルは消す（書き込みの出どころの突き合わせに載せない）"""
        self.ready_with_fields()
        self.add_test_mean_of_two()
        self.edit_tree(MEAN_FIX)
        self.suite.write_text(PYTEST_LIKE.replace("out = sys.argv[1]", "out = sys.argv[1]\nopen('made.txt', 'w').close()"),
                              encoding="utf-8")
        self.assertEqual(self.problems(), [])
        self.assertFalse((self.repo / "made.txt").exists())

    def test_review_rev_of_state_wins_over_given(self):
        """修正前の版は board.base_rev（state の inputs.review_rev が先、無ければ渡した版）。元 writes.base_rev と同じ順"""
        self.ready_with_fields()
        self.add_test_that_passes_on_base("test_mean_of_two")
        tree = self.git("rev-parse", f"{self.base}^{{tree}}")
        rows = self.problems(base=tree, state={"inputs": {"review_rev": self.base}})
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", MEAN_ID)], "state の版で base の木を作った")



"""修正のブロックの単位ごとの TDD の輪（lib/tddloop.py。設計 works/docs/specs/2026-09-27-fix-tdd-block-design.md の 2 節 3）の検査。

- 実行器が無い run: tdd-start は何も書かずに go: false を返し、出口の tdd は ran: false
- 実行器が在る run: 種の git（tests/e2e/target-seed の写し）と、unittest を回して JUnit XML を書く小さな実行器（試験の中の SUITE）で、
  振り分け → テスト（赤は baseline_red の red_problems）→ 直す（緑は baseline_red の green_problems）→ 整える（緑のまま・テストが
  変わらない）を役の代わりに作業ツリーを書き換えて回す。拒否の理由は次の指示書に届き、上限で諦めた単位は作業ツリーを
  単位の頭に戻して止める
- 輪の役は周ごとに新しい会話で起きるので、指示書の引き継ぎの節に前の単位と今の単位のこれまで（段・前の段の結果）が必ず載る
置き場は fix の run の置き場（元の盤面の代わり。状態は置き場の tdd-<k>/）。parse_junit・red_problems・green_problems・
_failure_attrs・run_suite の場合は lib/tests/test_baseline_red.py が持つ。
"""
import json
import os
import pathlib
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

LIB = pathlib.Path(__file__).resolve().parents[1]
SEED = LIB.parent / "tests" / "e2e" / "target-seed"
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import conflict  # noqa: E402
from tests.bin.gitkit import committed_copy, git  # noqa: E402
import fixrules  # noqa: E402
import planbrief  # noqa: E402
import rulebook  # noqa: E402
import tddloop  # noqa: E402
from unittest import mock  # noqa: E402

# 決まりの文の本体の置き場（scripts が import の後にする置き替えと同じ。lib/ の字にパスを書かない）
FR = LIB.parent / "workflows" / "fix" / "commands" / "fix-rules"
rulebook.CANON = FR / "common.md"
fixrules.SHARED = rulebook.CANON
fixrules.RULES_DIR = FR

DEADLINE = 1728000000
MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
OPEN = json.dumps([MEAN, CLAMP], ensure_ascii=False)
V1 = {"ok", "files", "changes_file", "removed"}

# 対象リポジトリの根で test_*.py を unittest で回し、JUnit XML を第 1 引数に書く実行器（本線の tdd_suite の約束と同じ形）
SUITE = '''
import sys, unittest, xml.etree.ElementTree as ET
sys.dont_write_bytecode = True
sys.path.insert(0, ".")
out = sys.argv[1]
rows = []
class R(unittest.TestResult):
    def addSuccess(self, t): rows.append((t, None))
    def addFailure(self, t, e): rows.append((t, "failure"))
    def addError(self, t, e): rows.append((t, "error"))
    def addSkip(self, t, r): rows.append((t, "skipped"))
unittest.defaultTestLoader.discover(".", pattern="test_*.py", top_level_dir=".").run(R())
root = ET.Element("testsuite")
for t, kind in rows:
    cls, name = t.id().rsplit(".", 1)
    tc = ET.SubElement(root, "testcase", classname=cls, name=name)
    if kind:
        ET.SubElement(tc, kind)
ET.ElementTree(root).write(out)
sys.exit(0 if all(k in (None, "skipped") for _, k in rows) else 1)
'''

# SUITE の写しで、pytest の JUnit に合わせる実行器: 断言の失敗も本体の例外も failure と書き、message に「<型>: <文>」を付ける
# （pytest は本体の例外を failure と書く。引用の照らし tddloop.red_check はこの message を読む）
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


class TestNoSuite(unittest.TestCase):
    """実行器が無い run は今と同じ: tdd-start は何も書かず go: false。出口の tdd は ran: false"""

    def test_start_without_suite_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            repo = tmp / "repo"
            committed_copy(repo, SEED)
            got = tddloop.start(tmp / "art", repo, "", OPEN)
            self.assertEqual(got, {"go": False, "reason": tddloop.NO_SUITE, "suite": "", "state_file": "",
                                   "summary_file": ""})
            self.assertFalse((tmp / "art").exists(), "置き場に何も書かない")
            self.assertEqual(git(repo, "status", "--porcelain"), "")

    def test_exit_fields_without_suite(self):
        start = {"go": False, "reason": tddloop.NO_SUITE, "suite": "", "state_file": "", "summary_file": ""}
        self.assertEqual(tddloop.exit_fields(start), {"ran": False, "suite": "", "reason": tddloop.NO_SUITE, "units": []})

    def test_missing_suite_file_falls_back_to_direct(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            repo = tmp / "repo"
            committed_copy(repo, SEED)
            got = tddloop.start(tmp / "board", repo, "no/such/suite.sh", OPEN)
            self.assertIs(got["go"], False)
            self.assertIn("no/such/suite.sh", got["reason"])
            self.assertEqual(got["state_file"], "")

    def test_freeze_check_skips_without_state(self):
        self.assertEqual(tddloop.frozen_problems("", pathlib.Path(".")), [])


DECLARED = {"declared": True, "why": "分母の式を名前の付いた変数に分けたい"}   # fix の段の整えの申告（理由は MIN_WHY 字以上）
PLAN_REFACTOR = {"item": 1, "why": "分母の計算を補助の関数に寄せる"}   # 約束の refactor の 1 行（修正案の項目の申告）


class LoopCase(unittest.TestCase):
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
        self.start = tddloop.start(self.board, self.repo, str(self.suite), OPEN)
        self.assertTrue(self.start["go"], self.start)
        self.state = self.start["state_file"]

    def restart(self, test_cmd=""):
        """tdd-start を起こし直す（test_cmd は線の入力）"""
        self.start = tddloop.start(self.board, self.repo, str(self.suite), OPEN, test_cmd=test_cmd)
        self.assertTrue(self.start["go"], self.start)
        self.state = self.start["state_file"]

    def st(self):
        return json.loads(pathlib.Path(self.state).read_text(encoding="utf-8"))

    def step(self, reply):
        return tddloop.step(self.state, reply, self.repo)

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
        prompt = pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8")
        for w in ("route", MEAN, CLAMP, str(self.suite)):
            self.assertIn(w, prompt)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "", "元の結末を取っても作業ツリーは変わらない")

    def test_prompt_is_composed_from_the_shared_rules(self):
        """tdd-prep の指示書: 修正の決まりの正本の核・TDD の読み替え・今の段の約束（今の段だけ）・今の段の指示。next.md は毎回
        決まりを全部載せる（全文版・差分版の控えは書かない）"""
        import fixrules
        core = fixrules.sections(fixrules.SHARED)["core-fix"]
        out = tddloop.prep(self.state, {"judgment_file": "/b/j.json"}, self.repo)
        prompt = pathlib.Path(out["prompt_file"])
        full = prompt.read_text(encoding="utf-8")
        for s in (core, fixrules.sections(fixrules.SHARED)["core-keep"], "## この輪での読み替え", "- **route**:",
                  "## この段ですること", "`/b/j.json`"):
            self.assertIn(s, full)
        self.assertNotIn("- **test**:", full, "今の段の約束だけ")
        self.assertFalse(fixrules.beside(prompt, ".delta.md").exists(), "差分版を書かない")
        self.route()
        tddloop.prep(self.state, {"judgment_file": "/b/j.json"}, self.repo)
        full2 = prompt.read_text(encoding="utf-8")
        self.assertIn(core, full2, "2 回目も決まりを全部")
        for s in ("- **test**:", "## この段ですること", "段 test"):
            self.assertIn(s, full2)
        self.assertEqual(fixrules.iteration_next(prompt), 3)

    def test_owed_units_are_conflict_fix_duty_not_the_is_open_list(self):
        """TDD が振り分ける義務は受け付けと同じ conflict.fix_duty の owed。渡された open_units（is_open）に無くても、関所で答えて
        直す義務に戻った単位は載り、外れた単位は載らない"""
        back = "stats.py returned: 関所で答えて直す義務に戻った単位"
        with mock.patch.object(tddloop.fixboard, "fix_duty", return_value=({MEAN, back}, {CLAMP: "答え待ちの問い q1"})) as duty:
            got = tddloop.start(self.board, self.repo, str(self.suite), OPEN, owed={MEAN, CLAMP, back},
                                withheld_by={CLAMP: "q1"})
        self.assertEqual(duty.call_args.args, (self.board, {MEAN, CLAMP, back}), "直す義務の値は呼び手が渡す（元は盤面）")
        self.assertTrue(got["go"], got)
        st = json.loads(pathlib.Path(got["state_file"]).read_text(encoding="utf-8"))
        self.assertEqual(sorted(tddloop._owed(st)), sorted([MEAN, back]))

    def test_second_start_gets_its_own_state(self):
        again = tddloop.start(self.board, self.repo, str(self.suite), OPEN)
        self.assertNotEqual(again["state_file"], self.state)

    def test_tdd_prep_puts_brief_of_current_unit(self):
        """振り分けの段は直す義務の単位の全部の brief、ほかの段は今の単位の brief だけを頭で名指す"""
        rows = [{"item": 1, "unit_keys": [MEAN], "file": "/b/r1/brief-1.md", "sha256": "a" * 64},
                {"item": 2, "unit_keys": [CLAMP], "file": "/b/r1/brief-2.md", "sha256": "b" * 64}]
        with mock.patch.object(tddloop.planbrief, "cut_at", return_value=rows) as cut:
            route = pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8")
            self.assertEqual(pathlib.Path(cut.call_args[0][0]).resolve(), self.board.resolve(), "fix の置き場で切る")
            self.assertIn("brief-1.md", route)
            self.assertIn("brief-2.md", route)
            self.route()   # MEAN は tdd、CLAMP は direct
            test = pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8")
            self.assertIn("brief-1.md", test)
            self.assertNotIn("brief-2.md", test, "今の単位は MEAN だけ")

    def test_tdd_prep_hands_off_finished_units(self):
        """依頼 243 の 2: 次の単位の指示書に、前に済んだ単位の引き継ぎ（単位の key・直したファイル・緑にしたテスト・整え）を
        機械が書く（会話の履歴に頼らない）。周ごとに新しい会話で起きるので、引き継ぎの節はいつも載り、振り分けの段と最初の単位
        には前の単位の行が無い"""
        route = pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(tddloop.HANDOFF_HEAD, route)
        self.assertIn("- 今の段: route", route.split(tddloop.HANDOFF_HEAD, 1)[1])
        self.route(clamp="tdd")
        first = pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8")
        part = first.split(tddloop.HANDOFF_HEAD, 1)[1].split("\n## ", 1)[0]
        self.assertNotIn("前の単位の直しは作業ツリーに在る", part, "最初の単位には前の単位の行が無い")
        self.assertIn(f"- 今の段: test・今の単位: {MEAN}", part)
        self.red()
        self.fix_mean()
        st = self.st()
        self.assertEqual(st["units"][st["queue"][st["cur"]]]["unit_key"], CLAMP)
        nxt = pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(tddloop.HANDOFF_HEAD, nxt)
        part = nxt.split(tddloop.HANDOFF_HEAD, 1)[1].split("\n## ", 1)[0]
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
        fix = pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8")
        part = fix.split(tddloop.HANDOFF_HEAD, 1)[1].split("\n## ", 1)[0]
        for w in (f"- 今の段: fix・今の単位: {MEAN}", "test の段の結果", "test_stats.py::TestStats::test_mean_of_two",
                  "helper_stub.py"):
            self.assertIn(w, part)
        got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "直せていない"})
        self.assertFalse(got["ok"])
        again = pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn("この段の返答は 1 回拒まれた", again.split(tddloop.HANDOFF_HEAD, 1)[1])
        self.fix_mean(refactor=DECLARED)
        ref = pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8")
        part = ref.split(tddloop.HANDOFF_HEAD, 1)[1].split("\n## ", 1)[0]
        for w in ("- 今の段: refactor", "fix の段の結果", "分母を len(xs) にした", DECLARED["why"]):
            self.assertIn(w, part)

    def test_tdd_prep_without_board_has_no_brief(self):
        """brief の控えの無い置き場（修正案の無い run と同じ）では brief の節を置かない"""
        self.assertNotIn(planbrief.HEAD, pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8"))

    def test_tdd_prep_broken_ledger_stops_with_reason(self):
        """brief の控えが壊れていれば、brief の無い指示書として続けず、控えを名指す理由の Broken で止める（traceback にしない）"""
        broken = planbrief.LedgerBroken(f"brief の控え /b/r1/{planbrief.LEDGER} を読めない: 壊れた")
        with mock.patch.object(tddloop.planbrief, "cut_at", side_effect=broken):
            with self.assertRaisesRegex(tddloop.Broken, planbrief.LEDGER):
                tddloop.prep(self.state)

class TestRoute(LoopCase):
    def test_rejects_bad_routing_with_reason_in_next_prompt(self):
        bad = {"phase": "route", "units": [{"unit_key": MEAN, "route": "direct", "why": "短い"},
                                           {"unit_key": "作り話", "route": "tdd"}]}
        got = self.step(bad)
        self.assertEqual((got["ok"], got["done"]), (False, False))
        for w in (CLAMP, "作り話", "10 字"):
            self.assertIn(w, got["reason"])
        prompt = pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn("作り話", prompt, "理由は次の指示書に届く")

    def test_route_gives_up_after_retry_max_to_all_direct(self):
        for _ in range(tddloop.retry_max()):
            got = self.step({"phase": "route", "units": []})
        self.assertEqual((got["ok"], got["done"]), (False, True))
        ex = tddloop.exit_fields(self.start)
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
        ex = tddloop.exit_fields(self.start)
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
        self.assertEqual(tddloop.frozen_problems(self.state, self.repo), [])
        self.edit("test_stats.py", "mean([2, 4]), 3", "mean([2, 4]), 3.0")
        self.assertTrue(tddloop.frozen_problems(self.state, self.repo), "輪の後の修正役がテストを変えたら拒む")

    def test_refactor_rechecked(self):
        self.route()
        self.red()
        self.fix_mean(refactor=DECLARED)
        self.edit("stats.py", "return sum(xs) / len(xs)", "total = sum(xs)\n    return total / len(xs)")
        got = self.step({"phase": "refactor", "unit_key": MEAN, "what": "式を 2 行にした"})
        self.assertTrue(got["done"], got)
        self.assertEqual(tddloop.exit_fields(self.start)["units"][0]["refactor"], "ok")

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
        for i in range(tddloop.retry_max()):
            got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["helper.py"], "what": "直せていない"})
            self.assertFalse(got["ok"])
        self.assertTrue(got["done"], "tdd の単位が 1 つなので輪は済む")
        self.assertEqual((self.repo / "test_stats.py").read_text(encoding="utf-8"), before, "書いたテストを外す")
        self.assertFalse((self.repo / "helper.py").exists(), "単位の頭に戻す")
        u = tddloop.exit_fields(self.start)["units"][0]
        self.assertEqual((u["route"], u["gave_up"]), ("parked", "green"))
        self.assertTrue(u["problems"])
        self.assertIn("緑", u["why"])

    def test_green_give_up_parks_unit_for_ruling_and_moves_on(self):
        self.route(clamp="tdd")
        before = (self.repo / "test_stats.py").read_text(encoding="utf-8")
        self.red()
        (self.repo / "helper.py").write_text("X = 1\n", encoding="utf-8")   # 直す段が足した新しいファイル
        for _ in range(tddloop.retry_max()):
            got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["helper.py"], "what": "直せていない"})
            self.assertFalse(got["ok"])
        self.assertNotIn("conflict", got, "止めた申し出の出口は状態の未送の並び 1 つ")
        unsent = self.st()[tddloop.UNSENT]
        self.assertEqual([r["source"] for r in unsent], [conflict.GAVE_UP_SOURCE], "3 回拒まれた単位は機械の申し出 1 件を状態の未送に積む")
        item = unsent[0]["item"]
        self.assertEqual((item["unit_key"], item["kind"], item["which_is_right"]), (MEAN, "needs_context", "unknown"))
        self.assertEqual(item["between"], [], "brief の無い run では名指しは空")
        last = got["reason"].splitlines()[0][:100]
        for w in (str(tddloop.retry_max()), "緑", last, tddloop.GAVE_UP_WHY):
            self.assertIn(w, item["why_both_cannot_hold"])
        st = self.st()
        self.assertEqual(st["parked"], [MEAN])
        u = st["units"][MEAN]
        self.assertEqual((u["route"], u["gave_up"]), ("parked", "green"))
        self.assertTrue(u["problems"])
        self.assertEqual((self.repo / "test_stats.py").read_text(encoding="utf-8"), before, "書いたテストを外す")
        self.assertFalse((self.repo / "helper.py").exists(), "単位の頭に戻す")
        self.assertEqual((got["done"], st["phase"], st["queue"][st["cur"]]), (False, "test", CLAMP))
        lines = "\n".join(tddloop.handoff_lines(st))
        self.assertIn(f"- {MEAN}: 食い違いの申し出で止めた", lines)
        self.assertNotIn("direct に回した", lines)
        ruler = "\n".join(fixrules.sections("ruler.md").values())
        self.assertIn(conflict.GAVE_UP_SOURCE, ruler, "裁定役の指示書は機械の申し出を出どころの欄 source で名指す")
        self.assertNotIn(tddloop.GAVE_UP_WHY, ruler, "理由の頭の文の写しで見分けない")

    def test_give_up_reads_briefs_before_moving_tree(self):
        """止める前に置き場の brief を読む。読めずに落ちた周は、作業ツリーを単位の頭に戻さず、状態も進めない"""
        self.route()
        self.red()
        (self.repo / "helper.py").write_text("X = 1\n", encoding="utf-8")   # 直す段が足した新しいファイル
        reply = {"phase": "fix", "unit_key": MEAN, "files": ["helper.py"], "what": "直せていない"}
        for _ in range(tddloop.retry_max() - 1):
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
        for _ in range(tddloop.retry_max()):
            got = self.step({"phase": "refactor", "unit_key": MEAN, "what": "壊した"})
            self.assertFalse(got["ok"])
        self.assertTrue(got["done"])
        self.assertEqual((self.repo / "stats.py").read_text(encoding="utf-8"), green)
        u = tddloop.exit_fields(self.start)["units"][0]
        self.assertEqual((u["route"], u["green"], u["refactor"]), ("tdd", "ok", "reverted"))

    def test_writer_can_hand_unit_to_direct(self):
        self.route()
        self.add_test(NEW_TEST)
        got = self.step({"phase": "test", "unit_key": MEAN, "direct_why": "既存の名前だけでは再現できないと分かった"})
        self.assertTrue(got["done"])
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        u = tddloop.exit_fields(self.start)["units"][0]
        self.assertEqual((u["route"], u["gave_up"]), ("direct", "writer"))

    def test_runner_failure_ends_loop_all_direct(self):
        self.route(clamp="tdd")
        self.add_test(NEW_TEST)
        self.suite.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")   # JUnit を書かない
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                         "tests": ["test_stats.py::TestStats::test_mean_of_two"]})
        self.assertTrue(got["done"])
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        ex = tddloop.exit_fields(self.start)
        self.assertIn("JUnit", ex["reason"])
        self.assertEqual([(u["route"], u["gave_up"]) for u in ex["units"]], [("direct", "runner"), ("direct", "runner")])

    def test_budget_ends_loop_before_max_iterations(self):
        self.route()
        st = self.st()
        st["iterations"] = tddloop.MAX_ITERATIONS - 1
        pathlib.Path(self.state).write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": [], "tests": []})
        self.assertTrue(got["done"], "max_iterations に届く周で印を立てる（R50）")
        self.assertEqual(tddloop.exit_fields(self.start)["units"][0]["gave_up"], "budget")

MEAN_ID = "test_stats.py::TestStats::test_mean_of_two"
WRONG_KIND_TEST = "\n    def test_mean_of_two(self):\n        import stats\n        self.assertEqual(stats.mean2([2, 4]), 3)\n"


class ContractCase(LoopCase):
    """約束を持つ run。tdd-start を plan_contract の差し替えで起こし直す（実行器は pytest に似せた PYTEST_LIKE）"""
    CONTRACT = {MEAN: {"items": [1], "route": "tdd", "rewrites": [], "refactor": [],
                       "tests": [{"id": MEAN_ID, "red_kind": "assertion"}]}}

    def setUp(self):
        super().setUp()
        self.suite.write_text(PYTEST_LIKE, encoding="utf-8")
        with mock.patch.object(tddloop, "plan_contract", return_value=self.CONTRACT) as pc:
            self.start = tddloop.start(self.board, self.repo, str(self.suite), OPEN)
        self.assertTrue(self.start["go"], self.start)
        self.state = self.start["state_file"]
        self.assertEqual(sorted(pc.call_args[0][1]), sorted([MEAN, CLAMP]))

    def quotes_for(self, tests):
        """名指しを実行器で 1 回走らせ、結末の failure の文から赤の引用を作る（役が結末を読んで引く代わり）。{id: {quote, why}}。
        failure の文の無い名指し（落ちていない・文を書かない実行器）は載せない"""
        with tempfile.TemporaryDirectory() as td:
            cases, _, why = tddloop.run_suite(str(self.suite), self.repo, pathlib.Path(td), "q", tddloop._abs_ids(self.repo, tests))
        self.assertEqual(why, [])
        out = {}
        for t in tests:
            c = tddloop.rules().match_case(t, cases) or {}
            if c.get("fail_message"):
                out[t] = {"quote": c["fail_message"], "why": "今のコードの欠陥で期待どおりに落ちた（打ち間違いではない）"}
        return out

    def step(self, reply):
        """test の段の返答に red_quotes が無ければ、結末の failure の文から作って足す（red_quotes を書いた返答はそのまま。
        failure の文を書かない実行器の結末からは作れず、{} を足す）"""
        if isinstance(reply, dict) and reply.get("phase") == "test" and reply.get("tests") and tddloop.QUOTES_FIELD not in reply:
            reply = {**reply, tddloop.QUOTES_FIELD: self.quotes_for(reply["tests"])}
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
        got = self.step({**reply, tddloop.QUOTES_FIELD: {}})
        self.assertFalse(got["ok"])
        self.assertIn(MEAN_ID, got["reason"])
        self.assertIn(tddloop.QUOTES_FIELD, got["reason"])
        quotes = {MEAN_ID: {"quote": "6.0 != 3", "why": "mean が分母を 1 つ少なく割るので 6.0 になる（期待は 3）"}}
        got = self.step({**reply, tddloop.QUOTES_FIELD: quotes})
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.st()["units"][MEAN][tddloop.QUOTES_FIELD], quotes)

    def test_red_kind_matches_and_is_recorded(self):
        """赤の記録は、機械が分けた種類でなく、役が返答に書いた引用と理由（結末の失敗の文に在ると照らし済み）がそのまま残る"""
        self.route()
        self.add_test(NEW_TEST)
        quotes = {MEAN_ID: {"quote": "6.0 != 3", "why": "mean が分母を 1 つ少なく割るので 6.0 になる（期待は 3）"}}
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"], "tests": [MEAN_ID],
                         tddloop.QUOTES_FIELD: quotes})
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.st()["units"][MEAN][tddloop.QUOTES_FIELD], quotes)
        self.assertEqual(self.st()["units"][MEAN]["quote_unchecked"], [])

    def test_red_rejects_wrong_kind(self):
        """宣言の外の名前（AttributeError）で落ちた failure も機械は種類で拒まない。引用が結末の文に在れば赤として通り、引用が
        単位の記録に残る（打ち間違いかは役の理由と報告の行で見る）"""
        self.route()
        self.add_test(WRONG_KIND_TEST)
        got = self.wrong_kind()
        self.assertTrue(got["ok"], got)
        self.assertIn("AttributeError", self.st()["units"][MEAN][tddloop.QUOTES_FIELD][MEAN_ID]["quote"])

    def test_crash_red_with_assertion_plan_passes_and_is_recorded(self):
        """今のコードが例外で落ちる種類のバグ（ZeroDivisionError）は、案が assertion でも拒まず、引いた失敗の文を記録する"""
        self.route()
        self.add_test("\n    def test_mean_of_two(self):\n        self.assertEqual(mean([5]), 5)\n")
        got = self.wrong_kind()
        self.assertTrue(got["ok"], got)
        self.assertIn("ZeroDivisionError", self.st()["units"][MEAN][tddloop.QUOTES_FIELD][MEAN_ID]["quote"])

    def test_name_error_red_with_assertion_plan_rejected(self):
        """NameError の failure も機械は種類で拒まず、引用が結末の文に在れば赤として通る"""
        self.route()
        self.add_test("\n    def test_mean_of_two(self):\n        self.assertEqual(mean_of([2, 4]), 3)\n")
        got = self.wrong_kind()
        self.assertTrue(got["ok"], got)
        self.assertIn("NameError", self.st()["units"][MEAN][tddloop.QUOTES_FIELD][MEAN_ID]["quote"])

    def test_wrong_kind_three_times_gives_up_and_parks_for_ruling(self):
        """結末に無い引用で 3 回拒まれ、食い違いの申し出で止めて裁定に回し、木が単位の頭に戻る（gave_up red）"""
        self.route()
        head = (self.repo / "test_stats.py").read_text(encoding="utf-8")
        self.add_test(WRONG_KIND_TEST)
        made_up = {MEAN_ID: {"quote": "結末に無い作り話の失敗の文", "why": "期待どおりの理由で落ちたと思う（作り話）"}}
        for _ in range(tddloop.retry_max()):
            got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"], "tests": [MEAN_ID],
                             tddloop.QUOTES_FIELD: made_up})
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
        self.assertEqual((u[tddloop.QUOTES_FIELD], u["quote_unchecked"]), ({}, [MEAN_ID]))

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
        self.assertIn(tddloop.NOT_RAN, got["reason"])
        self.edit("stats.py", "def clamp(", "def average(xs):\n    return 0\n\n\ndef clamp(")   # 最小の仮の実装（形だけ）
        got = self.step(reply)
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.st()["units"][MEAN]["stub_files"], ["stats.py"])
        self.assertTrue(self.st()["units"][MEAN]["red_tree"])


class TestNoContract(LoopCase):
    def test_no_contract_same_as_before(self):
        """約束の無い run（LoopCase）は、名指しの名前を見ず、red_quotes も求めない。引用を照らす先の無い名指しは quote_unchecked に残る"""
        self.assertEqual(self.st()["contract"], {})
        self.assertEqual(tddloop.plan_contract(self.board, [MEAN, CLAMP]), {}, "欄の控えの無い置き場は空")
        self.route()
        self.add_test(NEW_TEST.replace("test_mean_of_two", "test_other_name"))
        other = "test_stats.py::TestStats::test_other_name"
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"], "tests": [other]})
        self.assertTrue(got["ok"], got)
        u = self.st()["units"][MEAN]
        self.assertEqual((u[tddloop.QUOTES_FIELD], u["quote_unchecked"]), ({}, [other]))

    def test_board_without_fields_has_no_contract(self):
        """欄の控えが無ければ（frozen_fields が None）約束は空。置き場と周をそのまま渡す"""
        with mock.patch.object(tddloop.conflict, "frozen_fields", return_value=None) as ff:
            self.assertEqual(tddloop.plan_contract(self.board, [MEAN, CLAMP], 2), {})
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
        self.assertIn("NameError", self.st()["units"][CLAMP][tddloop.QUOTES_FIELD][REWRITE]["quote"])
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
    """case の setUp の tddloop.start の前に、対象リポジトリへ既存のテストのファイル test_other.py を置く（元の結末にも載る）"""
    orig = tddloop.start

    def start(board_dir, repo, *a, **k):
        other = pathlib.Path(repo) / "test_other.py"
        if not other.exists():
            other.write_text(body, encoding="utf-8")
        return orig(board_dir, repo, *a, **k)
    return mock.patch.object(tddloop, "start", start)


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
        orig = tddloop.start

        def start(board_dir, repo, *a, **k):
            other = pathlib.Path(repo) / "stats_test.go"
            if not other.exists():
                other.write_text(OTHER_GO, encoding="utf-8")
                (pathlib.Path(repo) / "KeySpec.java").write_text("class KeySpec { int v = 1; }\n", encoding="utf-8")
            return orig(board_dir, repo, *a, **k)
        with mock.patch.object(tddloop, "start", start):
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


class TestVanished(unittest.TestCase):
    """消えたテストの照らし（tddloop._vanished。純粋）"""
    HEAD = {"outcome": {"test_x.T::test_a[1]": "passed", "test_x.T::test_b": "passed", "test_y.U::test_c": "passed",
                        "test_x.T::test_s": "skipped"}, "args": []}

    def test_parametrized_rewrite_and_verified_excluded(self):
        now = {"test_x.T::test_a[2]": "passed", "test_x.T::test_b": "skipped", "test_y.U::test_c": "passed"}
        self.assertEqual(tddloop._vanished(self.HEAD, [self.HEAD], now, [], None, ["t/test_x.py::T::test_a", "./test_x.py::T::test_b"]),
                         [])
        self.assertEqual(tddloop._vanished(self.HEAD, [self.HEAD], now, [], None, ["t/test_x.py::T::test_a"]),
                         [("test_x.T::test_b", "skipped")])

    def test_absent_counts_only_with_same_selection(self):
        now = {"test_x.T::test_b": "passed"}
        self.assertEqual(tddloop._vanished(self.HEAD, [self.HEAD], now, ["x::y"], None, []), [], "選びが違う")
        self.assertEqual(sorted(tddloop._vanished(self.HEAD, [self.HEAD], now, [], None, [])),
                         [("test_x.T::test_a[1]", "missing"), ("test_y.U::test_c", "missing")])

    def test_absent_counts_in_module_run_whole(self):
        now = {"test_x.T::test_b": "passed"}
        self.assertEqual(tddloop._vanished(self.HEAD, [self.HEAD], now, ["x::y"], None, [], whole={"test_x"}),
                         [("test_x.T::test_a[1]", "missing")], "ファイルごと走ったモジュールから消えた（test_y は走っていない）")

    def test_head_merges_partial_green_run(self):
        prev = {"outcome": {"test_x.T::a": "passed", "test_x.T::gone": "passed", "test_y.U::c": "passed"}, "args": []}
        run = {"outcome": {"test_x.T::a": "failure", "test_x.T::new": "passed"}, "args": ["test_x.py"], "whole": ["test_x"],
               "full": False}
        self.assertEqual(tddloop._next_head(prev, run),
                         {"outcome": {"test_x.T::a": "failure", "test_x.T::new": "passed", "test_y.U::c": "passed"},
                          "args": None, "whole": [], "full": False})
        full = {**run, "full": True, "whole": []}
        self.assertEqual(tddloop._next_head(prev, full), full, "一式の回はそのまま次の単位の頭")

    def test_scope_limits_modules(self):
        now = {}
        self.assertEqual(tddloop._vanished(self.HEAD, [self.HEAD], now, [], {"test_y"}, []), [("test_y.U::test_c", "missing")])

    def test_scope_of_touched_files(self):
        self.assertEqual(tddloop._vanish_scope(["a/test_y.py", "stats.py", "b/x_test.py"]), {"test_y", "x_test"})
        self.assertIsNone(tddloop._vanish_scope(["test_y.py", "tests/conftest.py"]), "conftest.py に触れたら一式")

    def test_vanish_scope_non_python_is_whole(self):
        # .py でないテストのファイルは JUnit の行とモジュールを言語に依らず結べない——分からない＝一式の全部を照らす
        self.assertIsNone(tddloop._vanish_scope(["a/test_y.py", "pkg/calc_test.go"]))


class TestTestFileIdentity(unittest.TestCase):
    """テストのファイルの見分け: 宣言（単位の申告・約束の tests と rewrites のパス）を正本に、名の慣習（impact.is_test）を予備に"""

    def test_declared_test_files_from_state(self):
        st = {"units": {"u1": {"test_files": ["a/checks.go"]}, "u2": {}},
              "contract": {"u1": {"tests": [{"id": "b/verify.kt::Verify::adds"}], "rewrites": ["./c/legacy.rb::old"]},
                           "u2": None}}
        self.assertEqual(tddloop.declared_test_files(st), {"a/checks.go", "b/verify.kt", "c/legacy.rb"})


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

    def prompt(self):
        with mock.patch.object(tddloop.planbrief, "cut_at", return_value=self.BRIEFS):
            return pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8")

    def test_step_does_not_hold_off_unit_of_same_item(self):
        self.route_both()
        prompt = self.prompt()
        row = next(ln for ln in prompt[prompt.index(planbrief.HEAD):].splitlines() if ln.startswith("- 項目 1:"))
        self.assertIn(f"単位 {MEAN}、{CLAMP}", row)
        self.assertNotIn(planbrief.NOT_NOW, row, "同じ項目の単位に「今は直すな」と言わない")
        self.assertNotIn("今は手を付けるな", prompt, "同じ項目の後の単位を「この後の単位」に並べない")
        self.assertIn(tddloop.TOGETHER_HEAD, prompt)
        self.assertIn(CLAMP, prompt.split(tddloop.TOGETHER_HEAD, 1)[1].split("\n## ", 1)[0])

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
        self.assertEqual((got["done"], self.st().get(tddloop.UNSENT)), (True, None), "同じ項目の後の単位は機械が閉じ、輪は済む")
        st = self.st()
        self.assertEqual(st["parked"], [])
        self.assertNotIn("conflict", [c["phase"] for c in st["calls"]])
        self.assertEqual([c["unit_key"] for c in st["calls"] if c["phase"] != "route"], [MEAN, MEAN], "CLAMP の段は回らない")
        rows = {u["unit_key"]: u for u in tddloop.exit_fields(self.start)["units"]}
        c = rows[CLAMP]
        self.assertEqual((c["route"], c["red"], c["green"], c["gave_up"]), ("tdd", "ok", "ok", ""))
        self.assertEqual(sorted(c["tests"]), sorted(t["id"] for t in SAME_ITEM_TESTS))
        self.assertIn(MEAN, c["why"], "どの単位の段で一緒に直したかを残す")
        self.assertEqual(st["units"][CLAMP]["covered_by"], [MEAN])
        summary = pathlib.Path(self.start["summary_file"]).read_text(encoding="utf-8")
        done = summary.split("## 輪で直した単位", 1)[1].split("\n## ", 1)[0]
        self.assertIn(f"- {CLAMP}", done, "閉じた単位は輪で直した単位に並ぶ（direct に並べない）")
        self.assertEqual(tddloop.frozen_problems(self.state, self.repo), [])

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
    route_both, prompt = TestOneItemTwoUnits.route_both, TestOneItemTwoUnits.prompt

    def test_unit_of_other_item_is_held_off(self):
        self.route_both()
        prompt = self.prompt()
        self.assertIn(f"この後の tdd の単位（今は手を付けるな）: {CLAMP}", prompt)
        self.assertNotIn(tddloop.TOGETHER_HEAD, prompt)
        self.assertNotIn("brief-2.md", prompt)
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
        self.assertEqual(tddloop.together(self.st(), MEAN), [])
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


class TestTestFunctions(unittest.TestCase):
    def test_ids_and_sources(self):
        src = "import x\n\nclass T:\n    @d\n    def test_a(self):\n        pass\n\n    def helper(self):\n        pass\n\ndef test_b():\n    pass\n"
        got = tddloop.test_functions(src, "t.py")
        self.assertEqual(set(got), {"t.py::T::test_a", "t.py::test_b"})
        self.assertTrue(got["t.py::T::test_a"].startswith("@d"))
        self.assertEqual(tddloop.test_functions("def (", "t.py"), {})
        self.assertEqual(tddloop.test_functions(src, "t.sh"), {})

    def test_nested_class_ids(self):
        """入れ子のクラスのメソッドも pytest の node id の形（<パス>::A::B::test_x）で引く"""
        src = "class A:\n    class B:\n        def test_x(self):\n            pass\n\n    def test_y(self):\n        pass\n"
        self.assertEqual(set(tddloop.test_functions(src, "t.py")), {"t.py::A::B::test_x", "t.py::A::test_y"})

    def test_parametrized_permission_covers_function(self):
        """許しが parametrize の id（<id>[1]）でも、その関数の書き換えは名指しの外に数えない"""
        with tempfile.TemporaryDirectory() as td:
            repo = pathlib.Path(td) / "repo"
            committed_copy(repo, SEED)
            tree = tddloop.snapshot(repo)
            p = repo / "test_stats.py"
            p.write_text(p.read_text(encoding="utf-8").replace("clamp(5, 0, 10), 5)", "clamp(6, 0, 10), 6)"), encoding="utf-8")
            self.assertEqual(tddloop._unnamed_edits(repo, tree, ["test_stats.py"],
                                                    {"test_stats.py::TestStats::test_clamp_within_range[1]"}), [])

    def test_unnamed_edits(self):
        """木の時に在った test* 関数の本体が変わった・消えた物のうち、許しに無い id（整えた id で比べる）"""
        with tempfile.TemporaryDirectory() as td:
            repo = pathlib.Path(td) / "repo"
            committed_copy(repo, SEED)
            tree = tddloop.snapshot(repo)
            p = repo / "test_stats.py"
            text = p.read_text(encoding="utf-8")
            text = text.replace("clamp(5, 0, 10), 5)", "clamp(6, 0, 10), 6)").replace("clamp(15, 0, 10), 10)", "clamp(16, 0, 10), 10)")
            text = text.replace("    def test_mean_of_three(self):\n        self.assertEqual(mean([1, 2, 3]), 2)\n", "")
            p.write_text(text, encoding="utf-8")
            (repo / "notes.txt").write_text("x\n", encoding="utf-8")
            got = tddloop._unnamed_edits(repo, tree, ["test_stats.py", "notes.txt", "test_new.py"],
                                         {"./test_stats.py::TestStats::test_clamp_above_range"})
            self.assertEqual(sorted(got), ["test_stats.py::TestStats::test_clamp_within_range",
                                           "test_stats.py::TestStats::test_mean_of_three"])


class TestContractBroken(LoopCase):
    def test_broken_fields_stop_start(self):
        """欄の控えが凍結の印と食い違う（conflict.frozen_fields の ValueError）→ plan_contract は Broken（理由の文は
        conflict.FIELDS_BROKEN で始まる）"""
        gap = ValueError(f"{tddloop.conflict.FIELDS_BROKEN}: 控えの sha256 が印と違う")
        with mock.patch.object(tddloop.conflict, "frozen_fields", side_effect=gap):
            with self.assertRaises(tddloop.Broken) as got:
                tddloop.plan_contract(self.board, [MEAN])
            self.assertTrue(str(got.exception).startswith(tddloop.conflict.FIELDS_BROKEN), got.exception)
            with self.assertRaises(tddloop.Broken) as again:
                tddloop.start(self.board, self.repo, str(self.suite), OPEN)
            self.assertTrue(str(again.exception).startswith(tddloop.conflict.FIELDS_BROKEN), again.exception)

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


class TestRedCheck(unittest.TestCase):
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
        cases, code, why = tddloop.run_suite(str(exe), self.td, self.td, n)
        self.assertEqual(why, [])
        return cases, code, self.td / f"suite-{n}.log"

    def check(self, xml, quote=None, why=RC_WHY, out="", **kw):
        cases, code, log = self.suite(xml, out)
        quotes = None if quote is None else {RC_ID: {"quote": quote, "why": why}}
        return tddloop.red_check([RC_ID], cases, code, {}, kw.get("quotes", quotes), log)

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
        self.assertFalse(any(tddloop.NOT_RAN in p for p in probs))
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
        self.start = tddloop.start(self.board, self.repo, str(self.suite), OPEN, test_cmd=cmd, unit_depths=unit_depths)
        self.state = self.start["state_file"]

    def lint(self):
        return f"{sys.executable} lint.py"

    def test_fix_rejected_when_test_cmd_red(self):
        self.restart(self.lint())
        self.assertEqual(self.st()["test_cmd_gate"], tddloop.GATE_ON)
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
        self.assertEqual(self.st()["test_cmd_gate"], tddloop.GATE_ON)
        self.route()
        self.red()
        runs = self.st()["runs"]
        prompt = pathlib.Path(self.step_prompt()).read_text(encoding="utf-8")
        self.assertNotIn("緑の後に機械が run の test_cmd", prompt)
        self.edit("stats.py", "return sum(xs) / (len(xs) - 1)", "print('debug')\n    return sum(xs) / len(xs)")
        got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を直した"})
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.st()["runs"], runs + 1, "一式の緑の 1 回だけで、test_cmd は走らせない")
        self.assertEqual(self.st()["units"][MEAN]["test_cmd"], tddloop.CMD_LIGHT)

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

    def test_unit_depths_of_wrong_shape_is_broken(self):
        for raw in ("{", "[]", json.dumps({MEAN: 1})):
            with self.subTest(raw=raw), self.assertRaises(tddloop.Broken):
                tddloop.start(self.board, self.repo, str(self.suite), OPEN, unit_depths=raw)

    def step_prompt(self):
        return tddloop.prep(self.state)["prompt_file"]

    def test_fix_passes_and_records(self):
        self.restart(self.lint())
        self.route()
        self.red()
        self.fix_mean(refactor=DECLARED)
        self.assertEqual(self.st()["units"][MEAN]["test_cmd"], "ok")
        self.step({"phase": "refactor", "unit_key": MEAN, "what": "整える物は無い"})
        ex = tddloop.exit_fields(self.start)
        self.assertEqual(ex["test_cmd"], {"gate": tddloop.GATE_ON, "note": ""})
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
        self.assertEqual(st["test_cmd_gate"], tddloop.GATE_OFF)
        self.assertTrue(st["test_cmd_note"])
        self.route()
        self.red()
        self.fix_mean(refactor=DECLARED)   # 毎単位を拒まない
        self.assertEqual(self.st()["units"][MEAN]["test_cmd"], "")
        self.step({"phase": "refactor", "unit_key": MEAN, "what": "整える物は無い"})
        self.assertEqual(tddloop.exit_fields(self.start)["test_cmd"], {"gate": tddloop.GATE_OFF, "note": st["test_cmd_note"]})

    def test_same_command_as_suite_runs_once(self):
        cmd = f"{sys.executable} {self.suite}"
        with mock.patch.object(tddloop, "_cmd_material") as lcm:
            self.suite.write_text(SUITE + f"\n# {cmd}\n", encoding="utf-8")
            self.restart(cmd)
            self.route()
            self.red()
            self.fix_mean()
        lcm.assert_not_called()
        self.assertEqual(self.st()["test_cmd_gate"], tddloop.GATE_SAME)

    def test_empty_test_cmd_is_off(self):
        with mock.patch.object(tddloop, "_cmd_material") as lcm:
            self.restart("")
            self.route()
            self.red()
            self.fix_mean()
        lcm.assert_not_called()
        st = self.st()
        self.assertEqual((st["test_cmd"], st["test_cmd_gate"], st["test_cmd_note"]), ("", tddloop.GATE_OFF, ""))

    def test_default_start_has_gate_off(self):
        """LoopCase の既定（test_cmd を渡さない start）も関門は off・理由は空"""
        st = self.st()
        self.assertEqual((st["test_cmd"], st["test_cmd_gate"], st["test_cmd_note"]), ("", tddloop.GATE_OFF, ""))

    def test_test_cmd_not_run_leaves_loop_like_runner_down(self):
        self.restart(self.lint())
        self.route()
        self.red()
        down = {"status": "not_run", "reason": "起こせない"}
        self.edit("stats.py", "return sum(xs) / (len(xs) - 1)", "return sum(xs) / len(xs)")
        with mock.patch.object(tddloop, "_cmd_material", return_value=down):
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
        self.assertEqual(self.st()["test_cmd_gate"], tddloop.GATE_ON)
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
        self.assertEqual(st["test_cmd_gate"], tddloop.GATE_OFF)
        self.assertIn("test_cmd が作業ツリーの既存のファイルを書き換える", st["test_cmd_note"])
        self.assertIn("stats.py", st["test_cmd_note"])
        self.assertNotIn("stats.py", st["suite_made"])
        self.assertNotIn("# formatted", (self.repo / "stats.py").read_text(encoding="utf-8"))

    def test_prompt_names_test_cmd_only_when_gate_on(self):
        """関門が on の時だけ、直し・整えの段の指示書に test_cmd の文字列が載る（拒まれて初めて知るのを防ぐ）"""
        cmd = self.lint()
        self.restart(cmd)
        self.route()
        self.assertNotIn(cmd, pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8"), "test の段")
        self.red()
        self.assertIn(cmd, pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8"), "fix の段")
        self.fix_mean(refactor=DECLARED)
        self.assertIn(cmd, pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8"), "refactor の段")

    def test_prompt_omits_test_cmd_when_gate_off(self):
        off = f"{sys.executable} -c 'raise SystemExit(1)'"
        self.restart(off)
        self.route()
        self.red()
        self.assertNotIn(off, pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8"), "関門が off")

    def test_start_not_run_turns_gate_off_with_reason(self):
        down = {"status": "not_run", "reason": "起こせない"}
        with mock.patch.object(tddloop, "_cmd_material", return_value=down):
            self.restart(self.lint())
        st = self.st()
        self.assertEqual(st["test_cmd_gate"], tddloop.GATE_OFF)
        self.assertIn("起こせない", st["test_cmd_note"])


class TestRefactorGate(LoopCase):
    """整えの段は、fix の段で役が理由つきで申告した単位か、修正案の項目が refactor.declared の単位だけに来る。来ない単位は
    skipped。段ごとの呼び出しの記録（calls）を状態と出口に残す"""

    def test_fix_without_declaration_skips_refactor(self):
        self.route()
        self.red()
        got = self.fix_mean()
        self.assertTrue(got["done"], got)
        u = tddloop.exit_fields(self.start)["units"][0]
        self.assertEqual((u["refactor"], u["refactor_why"]), ("skipped", ""))
        self.assertIn("整え: skipped", pathlib.Path(self.start["summary_file"]).read_text(encoding="utf-8"))

    def test_declared_fix_goes_to_refactor(self):
        self.route()
        self.red()
        self.fix_mean(refactor=DECLARED)
        self.assertEqual(self.st()["phase"], "refactor")
        self.assertEqual(self.st()["units"][MEAN]["refactor_why"], DECLARED["why"])
        self.assertIn("refactor", pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8"))
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
        with mock.patch.object(tddloop, "plan_contract", return_value=contract):
            self.start = tddloop.start(self.board, self.repo, str(self.suite), OPEN)
        self.state = self.start["state_file"]
        self.route()
        self.red()
        self.fix_mean()
        self.assertEqual(self.st()["phase"], "refactor")
        self.assertIn(f"項目 1: {PLAN_REFACTOR['why']}", self.st()["units"][MEAN]["refactor_why"])

    def test_role_and_plan_reasons_are_joined(self):
        """役と修正案の両方が申告したら、空でない理由を全部つなぐ"""
        contract = {MEAN: {"items": [1], "route": "tdd", "tests": [], "rewrites": [], "refactor": [PLAN_REFACTOR]}}
        with mock.patch.object(tddloop, "plan_contract", return_value=contract):
            self.start = tddloop.start(self.board, self.repo, str(self.suite), OPEN)
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
        for _ in range(tddloop.retry_max()):
            got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "直せていない"})
        self.assertTrue(got["done"])
        rows = self.st()["calls"][2:]
        self.assertEqual([(c["phase"], c["ok"]) for c in rows], [("fix", False)] * tddloop.retry_max())

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
        self.assertEqual(tddloop.exit_fields(self.start)["calls"], calls)

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
        got = tddloop.start(self.board, self.repo, str(self.suite), json.dumps(keys, ensure_ascii=False))
        self.assertTrue(got["go"], got)
        rows = [{"unit_key": k, "route": route, **({"why": "2 回目の段で先にテストを書かない単位"} if route == "direct" else {})}
                for k in keys]
        self.assertTrue(tddloop.step(got["state_file"], {"phase": "route", "units": rows}, self.repo)["ok"])
        return got["state_file"]

    def since(self, state2) -> str:
        return tddloop.load_state(state2)["handoff"]

    def test_states_in_order_and_suite_made_all(self):
        self.first_loop()
        state2 = self.second_loop([CLAMP])
        self.assertEqual(tddloop.states(self.board), [pathlib.Path(self.state), pathlib.Path(state2)])
        for f, made in ((self.state, ["one.log"]), (state2, ["two.log"])):
            st = tddloop.load_state(f)
            st["suite_made"] = made
            pathlib.Path(f).write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(tddloop.suite_made_all(self.board), {"one.log", "two.log"})
        self.assertEqual(tddloop.states(self.tmp_board()), [])

    def tmp_board(self):
        return pathlib.Path(self._tmp.name) / "no-board"

    def test_second_pass_cannot_touch_first_loop_frozen_tests(self):
        self.first_loop()
        state2 = self.second_loop([CLAMP])
        since = self.since(state2)
        self.assertEqual(tddloop.frozen_problems(self.state, self.repo, since=since), [])
        self.edit("test_stats.py", "mean([2, 4]), 3", "mean([2, 4]), 3.0")   # 2 回目の修正役が tdd-1 の凍ったテストを変えた
        got = tddloop.frozen_problems(self.state, self.repo, since=since)
        self.assertTrue(got and "test_stats.py" in got[0], got)
        self.assertEqual(tddloop.frozen_problems(state2, self.repo), [], "tdd-2 は何も凍らせていない")

    def test_second_loop_may_add_test_to_first_loop_file(self):
        self.first_loop()
        state2 = self.second_loop([CLAMP], route="tdd")
        self.add_test(FAR_TEST)
        got = tddloop.step(state2, {"phase": "test", "unit_key": CLAMP, "test_files": ["test_stats.py"], "tests": [FAR_ID]},
                           self.repo)
        self.assertTrue(got["ok"], got)
        self.edit("stats.py", "    if x > hi:\n        return lo", "    if x > hi:\n        return hi")
        got = tddloop.step(state2, {"phase": "fix", "unit_key": CLAMP, "files": ["stats.py"], "what": "上限で hi を返す"},
                           self.repo)
        self.assertTrue(got["done"], got)
        self.assertEqual(tddloop.frozen_problems(self.state, self.repo), [],
                         "tdd-1 の関数を変えずに足しただけは since が無くても凍結に数えない（依頼 195i の 2）")
        self.assertEqual(tddloop.frozen_problems(self.state, self.repo, since=self.since(state2)), [])
        self.edit("test_stats.py", "clamp(20, 0, 10), 10", "clamp(20, 0, 10), 0")
        self.assertTrue(tddloop.frozen_problems(state2, self.repo), "足したテストは tdd-2 の凍結で見る")

    def test_amended_units_old_test_span_is_not_frozen(self):
        self.first_loop()
        state2 = self.second_loop([MEAN])
        since = self.since(state2)
        spans = tddloop.test_spans(self.state, {MEAN})
        self.assertEqual(spans, [("test_stats.py", "TestStats::test_mean_of_two")])
        self.assertEqual(tddloop.test_spans(self.state, {CLAMP}), [], "tdd-1 で緑にしていない単位の関数は無い")
        self.edit("test_stats.py", "mean([2, 4]), 3", "mean([2, 4, 6]), 4")
        self.assertTrue(tddloop.frozen_problems(self.state, self.repo, since=since))
        self.assertEqual(tddloop.frozen_problems(self.state, self.repo, since=since, skip_spans=spans), [])
        self.edit("test_stats.py", "clamp(5, 0, 10), 5", "clamp(6, 0, 10), 6")   # 関数の範囲の外
        got = tddloop.frozen_problems(self.state, self.repo, since=since, skip_spans=spans)
        self.assertTrue(got and "範囲の外" in got[0], got)

    def test_frozen_source_reads_since_tree(self):
        """テストの変更の許しの行を引き直す木は、凍結の検査が比べる木（since）と同じ"""
        self.first_loop()
        state2 = self.second_loop([CLAMP])
        since = self.since(state2)
        self.edit("test_stats.py", "mean([2, 4]), 3", "mean([2, 4]), 3.0")
        read = tddloop.frozen_source(self.state, self.repo, since=since)
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
        with mock.patch.object(tddloop.conflict, "frozen_fields", return_value=fields):
            self.restart()
            self.assertEqual(list(self.st()["contract"]), [MEAN])
        self.assertNotIn("plain", self.st())

    def test_green_test_cmd_gate_is_on_and_refactor_needs_a_declaration(self):
        """緑の test_cmd は関門 on。申告の無い単位は整えを飛ばす"""
        self.restart(test_cmd=f"{sys.executable} -c pass")
        self.assertEqual(self.st()["test_cmd_gate"], tddloop.GATE_ON)
        self.route()
        self.red()
        fix = pathlib.Path(tddloop.prep(self.state)["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(tddloop.DO["fix"], fix)
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
        got = tddloop.prep(self.state)
        self.assertIs(got["go"], True)
        self.assertTrue(pathlib.Path(got["prompt_file"]).is_file())

    def test_done_loop_ends_without_the_role(self):
        self.done_loop()
        before = self.snap()
        self.assertEqual(tddloop.prep(self.state), {"prompt_file": "", "go": False})
        got = self.step(None)
        self.assertEqual((got["ok"], got["done"], got["phase"], got["reason"]), (True, True, "done", ""), got)
        self.assertEqual(self.snap(), before, "済んだ輪の周は状態と作業ツリーを動かさない")

    def test_reply_for_a_done_loop_is_still_refused(self):
        self.done_loop()
        with self.assertRaises(tddloop.Broken):
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
        for _ in range(tddloop.retry_max()):
            self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"], "tests": []})
        self.assertEqual(self.st()["parked"], [MEAN], "止めた単位は状態に保存済み")
        parked = []

        def broken(rows):
            raise ValueError("食い違いの控えが読めない")
        with self.assertRaises(ValueError):
            tddloop.flush_unsent(self.state, broken)
        self.assertEqual(len(self.st()[tddloop.UNSENT]), 1, "積めなかった申し出は状態に残る")
        for call in ("積み直す呼び", "積み増さない呼び"):
            tddloop.flush_unsent(self.state, parked.extend)
            self.assertEqual([r["item"]["unit_key"] for r in parked], [MEAN], call)
            self.assertEqual(self.st().get(tddloop.UNSENT), [], call)


class TddloopSeamsGoneCase(unittest.TestCase):
    def test_board_and_wrapper_seams_are_gone(self):
        """盤面・包み・借りた座に届く名は持たない（元の rules の写しの読み・会話の鍵の書き・座の節）"""
        for name in ("RULES_GRAPH", "write_key", "RECEIVES", "adapter", "board", "entry", "seat", "script_io"):
            self.assertFalse(hasattr(tddloop, name), name)


if __name__ == "__main__":
    unittest.main()

"""事後の関門の束（lib/fixgates.py。計画 220 Task 4）の検査。

束は修正の受け付け（fix-accept・fix-ruled-accept の script）の最後の段で、修正の形に依らず base（修正前の版）から今の木までを相手に
- red_green: 承認済みの修正案の tdd の項目の受け入れのテストが、今の木で緑・base で failure の赤か（輪と同じ tddloop.red_check の事実で見る）
- test_edits: base に在った既存のテストの関数の本体を、名指し（修正案の rewrite_tests・裁定 fix_test_scope の範囲）の外で変えていないか
を確かめる。置き場（元の盤面の代わり。fix の run の置き場のフォルダ）は使い捨てのフォルダで、承認済みの修正案の欄の控えは
planmarks.save、範囲の相談の合意は fixboard.trace、裁定は置き場の conflicts.json に置く。種の git は tests/e2e/target-seed の写し、
実行器は test_blk_fix_tdd の PYTEST_LIKE（失敗の文を message に書く）。種の stats.mean は len-1 で割る誤りを持つ。
元 works/tests/test_fix_gates.py の盤面の BoardCase を、置き場のフォルダと版の引数に替えた（ほかの場合は元のまま）。
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
SEED = LIB.parent / "tests" / "e2e" / "target-seed"
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from tests.bin.gitkit import committed_copy  # noqa: E402
from lib.tests import test_blk_fix_tdd as tbt  # noqa: E402
import conflict  # noqa: E402
import fixboard  # noqa: E402
import fixgates  # noqa: E402
import planmarks  # noqa: E402
from tests.bin import hermetic  # noqa: E402

MEAN, CLAMP = tbt.MEAN, tbt.CLAMP
MEAN_ID = "test_stats.py::TestStats::test_mean_of_two"
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
REWRITE = {"id": THREE_ID, "behavior": "3 つの値の平均の期待", "old": "期待は 2", "new": "期待を 2.0 に書き換える",
           "limit": "test_stats.py:8"}


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


class FixGatesCase(unittest.TestCase):
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
        self.suite.write_text(tbt.PYTEST_LIKE, encoding="utf-8")
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
        self.add_test(tbt.NEW_TEST)

    def add_test_that_passes_on_base(self, name):
        self.add_test(f"\n    def {name}(self):\n        self.assertEqual(clamp(5, 0, 10), 5)\n")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True, encoding="utf-8", check=True,
                              env=hermetic.child_env()).stdout.strip()

    def fields_for(self, test_id):
        """受け入れのテスト test_id を 1 本持つ tdd の項目（単位は mean）"""
        return [{**FIELDS[0], "tests": [{**TEST_ROW, "id": test_id}]}]

    def problems(self, suite=None, attempt=1, base=None, **kw):
        return fixgates.problems(self.board, self.repo, self.base if base is None else base,
                                 self.SUITE if suite is None else suite, attempt, **kw)

    def ledger(self):
        return json.loads((self.board / fixgates.LEDGER).read_text(encoding="utf-8"))

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
        self.assertFalse((self.board / fixgates.LEDGER).exists(), "積む物が無ければ帳面を書かない")

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
        fixboard.trace(self.board, conflict.ASKED_OP, **row)

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
        self.add_test(tbt.NEW_TEST.replace("test_mean_of_two", "test_mean_pair"))
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
        (ask,) = fixgates.overflow_asks([row], self.repo, self.base, [{"item": 1, "allowed_paths": ["test_stats.py"]}])
        self.assertEqual((ask["new_tests"], ask.get("revert")), ([MEAN_ID], True))

    def test_agreed_guard_test_needs_only_green_now(self):
        """合意の red_kind が守りのテスト（GUARD_KIND）の新しいテストは、base で緑でも抜けの行にならない。今の木で赤なら抜けの行"""
        self.ready_with_fields(direct_fields())
        self.agree(MEAN_ID, planmarks.GUARD_KIND)
        self.add_test_that_passes_on_base("test_mean_of_two")
        self.assertEqual(self.problems(), [], "base で緑でも守りのテストは抜けにならない")
        self.assertEqual(fixgates.guards(self.board, pass_="first", attempt=1), [{"id": MEAN_ID, "base": "passed"}],
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
        self.assertEqual(fixgates.guards(self.board, pass_="first", attempt=1), [{"id": MEAN_ID, "base": "passed"}])

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
            self.suite.write_text(tbt.SUITE, encoding="utf-8")   # 本体の例外を error と書く実行器
            (self.repo / "test_two.py").unlink()
            self.edit_tests("from stats import clamp, mean", "from stats import *  # noqa: F403")
            self.add_test("\n    def test_mean_of_two(self):\n        self.assertEqual(halve(4), 2)  # noqa: F405\n")
            planmarks.save(self.board, 1, FIELDS)
            rows = self.problems(attempt=2)
            self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", MEAN_ID)])
            self.assertTrue(rows[0]["detail"].startswith("base で "), rows[0]["detail"])
            self.assertIn("error で落ちた", rows[0]["detail"])
            self.assertNotIn(fixgates.tddloop.NOT_RAN, rows[0]["detail"], "言い足しは輪の呼び手だけで、事後の関門の行には入らない")

    def test_base_row_carries_loop_red_check_text(self):
        """base の木の行の detail は『base で 』と、輪と同じ red_check が同じ JUnit の行に返す事実の文で出来ている（NOT_RAN を含まない）"""
        self.ready_with_fields()
        self.suite.write_text(tbt.SUITE, encoding="utf-8")   # 本体の例外を error と書く実行器（base の木で mean の名指しが error）
        self.edit_tests("from stats import clamp, mean", "from stats import *  # noqa: F403")
        self.add_test("\n    def test_mean_of_two(self):\n        self.assertEqual(halve(4), 2)  # noqa: F405\n")
        self.edit_tree(HALVE)
        rows = self.problems()
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", MEAN_ID)])
        row = {"classname": "test_stats.TestStats", "name": "test_mean_of_two", "outcome": "error", "fail_message": "", "fail_text": ""}
        probs, _ = fixgates.tddloop.red_check([MEAN_ID], [row], None, None)
        self.assertEqual(rows[0]["detail"], "base で " + "；".join(probs))
        self.assertIn("error で落ちた", rows[0]["detail"])
        self.assertNotIn(fixgates.tddloop.NOT_RAN, rows[0]["detail"])

    def test_runner_inside_repo_runs_its_base_copy(self):
        """実行器が対象のリポジトリの中に在れば、base の木では worktree の中の base の版を走らせる"""
        self.ready_with_fields()
        runner = self.repo / "runner.py"
        runner.write_text(tbt.PYTEST_LIKE, encoding="utf-8")
        self.git("add", "runner.py")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "runner")
        head = self.git("rev-parse", "HEAD")
        # 今の木の実行器は、印のファイルが無い置き場（base の worktree）では受け入れのテストを緑と書く（base の版を走らせない誤りを露わにする）
        runner.write_text("import os, sys\nif not os.path.exists('now-only.txt'):\n    open(sys.argv[1], 'w').write("
                          "'<testsuite><testcase classname=\"test_stats.TestStats\" name=\"test_mean_of_two\"/></testsuite>')\n"
                          "    sys.exit(0)\n" + tbt.PYTEST_LIKE, encoding="utf-8")
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
        why = fixgates.skipped(self.board, pass_="first", attempt=1)
        self.assertEqual(len(why), 1, why)
        self.assertTrue(why[0].startswith(fixgates.NO_RUN), why)
        self.assertIn("今の木", why[0])
        self.assertEqual(fixgates.unchecked(self.board, pass_="first", attempt=1), why, "確かめずに通した理由に数える")

    def test_base_tree_that_cannot_be_made_skips_and_records(self):
        """base の版から worktree を作れない（commit でない版）→ 拒まず、帳面の skipped に理由。worktree は残さない"""
        self.ready_with_fields()
        self.add_test_that_passes_on_base("test_mean_of_two")
        tree = self.git("rev-parse", f"{self.base}^{{tree}}")
        self.assertEqual(self.problems(base=tree), [])
        why = fixgates.skipped(self.board, pass_="first", attempt=1)
        self.assertEqual(len(why), 1, why)
        self.assertTrue(why[0].startswith(fixgates.NO_RUN), why)
        self.assertIn("base の木", why[0])
        self.assertEqual(len(self.worktrees()), 1, self.worktrees())

    def test_no_suite_skips_and_records(self):
        self.ready_with_fields()
        self.add_test_that_passes_on_base("test_mean_of_two")
        self.assertEqual([r for r in self.problems(suite="") if r["gate"] == "red_green"], [])
        self.assertEqual(self.ledger()["skipped"][0]["why"], fixgates.NO_SUITE)

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
                why = fixgates.skipped(self.board, pass_="first", attempt=1)
                self.assertEqual(len(why), 1, why)
                for w in (fixgates.OUT_OF_DUTY, "項目 1", MEAN):   # 見なかった項目と単位を名指して残す
                    self.assertIn(w, why[0])
                self.assertEqual(fixgates.unchecked(self.board, pass_="first", attempt=1), [],
                                 "義務の外の項目は確かめずに通したに数えない")

    def test_withheld_unit_is_out_of_duty(self):
        """答え待ちの問いの出どころ（withheld）の単位だけを名指す項目も見ない。関所で答えて戻した単位（returned）は見る"""
        self.ready_with_fields()
        self.add_test_that_passes_on_base("test_mean_of_two")
        self.assertEqual(self.problems(owed=[MEAN, CLAMP], withheld=[MEAN]), [])
        self.assertTrue(fixgates.skipped(self.board, pass_="first", attempt=1)[0].startswith(fixgates.OUT_OF_DUTY))
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
        real = fixgates.tddloop.run_suite

        def broken(exe, repo, *a, **k):
            if pathlib.Path(repo).resolve() != self.repo.resolve():
                raise RuntimeError("base の木で落ちた")
            return real(exe, repo, *a, **k)
        with mock.patch.object(fixgates.tddloop, "run_suite", side_effect=broken):
            with self.assertRaises(RuntimeError):
                self.problems()
        self.assertEqual(len(self.worktrees()), 1, self.worktrees())

    def test_suite_leftovers_are_removed_from_tree(self):
        """今の木で一式を走らせて出来たファイルは消す（書き込みの出どころの突き合わせに載せない）"""
        self.ready_with_fields()
        self.add_test_mean_of_two()
        self.edit_tree(MEAN_FIX)
        self.suite.write_text(tbt.PYTEST_LIKE.replace("out = sys.argv[1]", "out = sys.argv[1]\nopen('made.txt', 'w').close()"),
                              encoding="utf-8")
        self.assertEqual(self.problems(), [])
        self.assertFalse((self.repo / "made.txt").exists())

    def test_review_rev_of_state_wins_over_given(self):
        """修正前の版は fixboard.base_rev（state の inputs.review_rev が先、無ければ渡した版）。元 writes.base_rev と同じ順"""
        self.ready_with_fields()
        self.add_test_that_passes_on_base("test_mean_of_two")
        tree = self.git("rev-parse", f"{self.base}^{{tree}}")
        rows = self.problems(base=tree, state={"inputs": {"review_rev": self.base}})
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", MEAN_ID)], "state の版で base の木を作った")


class TestBaseCache(FixGatesCase):
    """base の木の結末は base の版・実行器・受け入れのテストの id・そのテストのファイル（と写す conftest.py）の
    中身で鍵を作り、置き場に残して受け付けの回をまたいで使い回す（base は run の中で動かない）。決まり（今の木で緑・base で案の
    種類の赤）は変えない"""

    def counted(self):
        """tddloop.run_suite を数える {"now": 今の木の回数, "base": それ以外の回数}"""
        real = fixgates.tddloop.run_suite
        calls = {"now": 0, "base": 0}

        def run(exe, repo, *a, **k):
            calls["now" if pathlib.Path(repo).resolve() == self.repo.resolve() else "base"] += 1
            return real(exe, repo, *a, **k)
        return calls, mock.patch.object(fixgates.tddloop, "run_suite", side_effect=run)

    def test_base_runs_once_across_attempts(self):
        self.ready_with_fields()
        self.add_test_mean_of_two()
        self.edit_tree(MEAN_FIX)
        calls, patch = self.counted()
        with patch:
            self.assertEqual(self.problems(attempt=1), [])
            self.assertEqual(self.problems(attempt=2), [])
            self.assertEqual(self.problems(attempt=1, pass_="ruled"), [])
        self.assertEqual(calls, {"now": 3, "base": 1}, "今の木は回ごと・base は 1 回")
        self.assertTrue((self.board / fixgates.BASE_CACHE).is_file(), "控えは置き場に在る")

    def test_cached_base_keeps_the_rule(self):
        """使い回した base の結末でも決まりは同じ: base で緑なら回をまたいでも行"""
        self.ready_with_fields()
        self.add_test_that_passes_on_base("test_mean_of_two")
        calls, patch = self.counted()
        with patch:
            first = self.problems(attempt=1)
            second = self.problems(attempt=2)
        self.assertEqual([(r["gate"], r["id"], r["detail"]) for r in first],
                         [(r["gate"], r["id"], r["detail"]) for r in second])
        self.assertTrue(second[0]["detail"].startswith("base で "), second[0]["detail"])
        self.assertIn("もう通る", second[0]["detail"])
        self.assertEqual(calls["base"], 1)

    def test_changed_test_file_reruns_base(self):
        """受け入れのテストのファイルの中身が変われば鍵が変わり、base を走らせ直す（古い結末で通さない）"""
        self.ready_with_fields()
        self.add_test_mean_of_two()
        self.edit_tree(MEAN_FIX)
        calls, patch = self.counted()
        with patch:
            self.assertEqual(self.problems(attempt=1), [])
            self.edit_tests("self.assertEqual(mean([2, 4]), 3)", "self.assertEqual(clamp(5, 0, 10), 5)")
            rows = self.problems(attempt=2)
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", MEAN_ID)])
        self.assertTrue(rows[0]["detail"].startswith("base で "), rows[0]["detail"])
        self.assertIn("もう通る", rows[0]["detail"])
        self.assertEqual(calls["base"], 2)

    def test_other_base_rev_reruns_base(self):
        self.ready_with_fields()
        self.add_test_mean_of_two()
        self.edit_tree(MEAN_FIX)
        calls, patch = self.counted()
        with patch:
            self.assertEqual(self.problems(attempt=1), [])
            (self.repo / "note.txt").write_text("x", encoding="utf-8")
            self.git("add", "note.txt")
            self.git("-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "版を進める")
            head = self.git("rev-parse", "HEAD")
            self.problems(attempt=2, base=head)
        self.assertEqual(calls["base"], 2)

    def test_failed_base_run_is_not_cached(self):
        """base で実行器が結末を出さなかった回は残さない（次の回は走らせ直す）"""
        self.ready_with_fields()
        self.add_test_mean_of_two()
        self.edit_tree(MEAN_FIX)
        real = fixgates.tddloop.run_suite
        calls = {"base": 0}

        def run(exe, repo, *a, **k):
            if pathlib.Path(repo).resolve() != self.repo.resolve():
                calls["base"] += 1
                if calls["base"] == 1:
                    return None, None, ["base で JUnit を書かなかった"]
            return real(exe, repo, *a, **k)
        with mock.patch.object(fixgates.tddloop, "run_suite", side_effect=run):
            self.assertEqual(self.problems(attempt=1), [])
            self.assertTrue(fixgates.skipped(self.board, pass_="first", attempt=1))
            self.assertEqual(self.problems(attempt=2), [])
        self.assertEqual(calls["base"], 2)
        self.assertEqual(fixgates.skipped(self.board, pass_="first", attempt=2), [])


STUB = "def halve(x):\n    return 0  # 仮の実装\n\n\ndef clamp(x, lo, hi):"   # test の段で赤を作るために足す最小の仮の実装
TWICE_ID = "test_two.py::TestTwo::test_twice"
SAB_ID = "test_sab.py::TestSab::test_clamp_in_range"
SAB = ("import unittest\n\nfrom stats import clamp\n\n\nclass TestSab(unittest.TestCase):\n    def test_clamp_in_range(self):\n"
       "        self.assertEqual(clamp(5, 0, 10), 5)\n")   # base で通るテスト（直す前から緑）


class TestLoopRedTree(FixGatesCase):
    """輪が仮の実装（テストでないファイル）を足して赤を確かめた単位の受け入れのテストは、事後の関門も輪の記録した赤の木
    （red_tree。仮の実装を含む）で名指しを走らせ直して failure を見る（持ち主の直す前の関所の答え (3) A）。base の木にテストの
    ファイルだけを写すと、仮の実装が無く組み立てで落ちて『一式の結末に居ない』と拒むため。今の木のテストのファイルが赤の記録と
    輪が終わった時（frozen）と違う単位は、赤の木が今のテストを表さないので base の木で見る（今どおり）。赤の木を使う名指しも
    base の木＋テストのファイルで 1 回走らせ、passed（直す前から通る）なら拒む（仮の実装の名目で既存の実装を壊した偽の赤を拒む）"""

    def stub_red(self):
        """test_two.py（halve を読む）を書き、仮の実装で赤にした木を輪の単位の記録に残し、本物の実装に直す"""
        self.ready_with_fields(self.fields_for(TWO_ID))
        (self.repo / "test_two.py").write_text(TWO_FILE, encoding="utf-8")
        self.edit_tree({"def clamp(x, lo, hi):": STUB})
        red = fixgates.tddloop.snapshot(self.repo)
        self.save_unit(red)
        self.edit_tree({"return 0  # 仮の実装": "return x / 2"})
        return red

    def save_unit(self, red_tree, **over):
        """置き場の輪の状態 tdd-1/state.json に、赤を確かめた単位の記録を置く（輪の _test が残す欄だけ。frozen は輪が終わった
        時のテストのファイルの hash で、今の姿）"""
        unit = {"unit_key": MEAN, "route": "tdd", "red": "ok", "tests": [TWO_ID], "test_files": ["test_two.py"],
                "test_hashes": fixgates.tddloop.hashes(self.repo, ["test_two.py"]), "red_tree": red_tree, "stub_files": ["stats.py"],
                **over}
        self.save_units({MEAN: unit})

    def save_units(self, units):
        files = sorted({f for u in units.values() for f in u["test_files"]})
        d = self.board / "tdd-1"
        d.mkdir(parents=True, exist_ok=True)
        (d / fixgates.tddloop.STATE).write_text(json.dumps({"units": units, "frozen": fixgates.tddloop.hashes(self.repo, files)},
                                                           ensure_ascii=False), encoding="utf-8")

    def test_stub_red_rechecked_on_loop_red_tree(self):
        """base の木では一式の結末に居ないテストでも、輪の赤の木で failure なら行は無い"""
        self.stub_red()
        self.assertEqual(self.problems(), [])
        self.assertEqual(self.worktrees(), self.worktrees()[:1], "走らせ直した一時の worktree は残さない")

    def test_red_tree_that_passes_is_a_miss(self):
        """赤の木で名指しが通る（記録が赤を映していない）なら行。文は『輪の赤の木で 』と red_check の事実"""
        self.stub_red()
        self.save_unit(fixgates.tddloop.snapshot(self.repo))   # 直した後の木を赤の木と書く
        rows = self.problems()
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", TWO_ID)])
        self.assertTrue(rows[0]["detail"].startswith(fixgates.RED_TREE_HEAD), rows[0]["detail"])
        self.assertIn("もう通る", rows[0]["detail"])

    def test_test_file_moved_after_loop_falls_back_to_base(self):
        """輪が終わった後（やり直し・裁定）にテストのファイルが変わった単位は、赤の木が今のテストを表さないので base の木で見る
        （仮の実装が無く拒む）"""
        self.stub_red()
        path = self.repo / "test_two.py"
        path.write_text(path.read_text(encoding="utf-8") + "\n# 赤の後の書き足し\n", encoding="utf-8")
        rows = self.problems()
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", TWO_ID)])
        self.assertTrue(rows[0]["detail"].startswith("base で "), rows[0]["detail"])
        self.assertIn("一式の結末に居ない", rows[0]["detail"])

    def test_two_units_share_a_test_file(self):
        """後の単位が同じテストのファイルに足し、後の単位の仮の実装を頭で読んでも、先の単位は輪の赤の木で見る（輪が終わった時の
        テストのファイルと今が同じなら、赤の時の hash と違っても base に戻さない）"""
        self.ready_with_fields([{**FIELDS[0], "tests": [{**TEST_ROW, "id": TWO_ID}, {**TEST_ROW, "id": TWICE_ID}]}])
        path = self.repo / "test_two.py"
        path.write_text(TWO_FILE, encoding="utf-8")
        self.edit_tree({"def clamp(x, lo, hi):": STUB})
        a = {"unit_key": "a", "route": "tdd", "red": "ok", "tests": [TWO_ID], "test_files": ["test_two.py"],
             "test_hashes": fixgates.tddloop.hashes(self.repo, ["test_two.py"]), "red_tree": fixgates.tddloop.snapshot(self.repo)}
        self.edit_tree({"return 0  # 仮の実装": "return x / 2"})   # 単位 a を直す
        path.write_text(path.read_text(encoding="utf-8").replace("from stats import halve", "from stats import halve, twice")
                        + "\n    def test_twice(self):\n        self.assertEqual(twice(2), 4)\n", encoding="utf-8")
        self.edit_tree({"def clamp(x, lo, hi):": "def twice(x):\n    return 0  # 仮の実装\n\n\ndef clamp(x, lo, hi):"})
        b = {"unit_key": "b", "route": "tdd", "red": "ok", "tests": [TWICE_ID], "test_files": ["test_two.py"],
             "test_hashes": fixgates.tddloop.hashes(self.repo, ["test_two.py"]), "red_tree": fixgates.tddloop.snapshot(self.repo)}
        self.edit_tree({"return 0  # 仮の実装": "return x * 2"})   # 単位 b を直す
        self.save_units({"a": a, "b": b})
        self.assertEqual(self.problems(), [])

    def test_sabotaged_red_tree_green_at_base_is_a_miss(self):
        """test の段が既存の実装を壊した木を赤の木に残し、fix の段で戻しても、base の木＋テストのファイルで通る（直す前から緑）
        なら行（別の目 R1 の写し）"""
        self.ready_with_fields(self.fields_for(SAB_ID))
        (self.repo / "test_sab.py").write_text(SAB, encoding="utf-8")
        self.edit_tree({"def clamp(x, lo, hi):": "def clamp(x, lo, hi):\n    return -1  # 壊す\n"})
        self.save_unit(fixgates.tddloop.snapshot(self.repo), tests=[SAB_ID], test_files=["test_sab.py"],
                       test_hashes=fixgates.tddloop.hashes(self.repo, ["test_sab.py"]))
        self.edit_tree({"    return -1  # 壊す\n": ""})
        rows = self.problems()
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", SAB_ID)])
        self.assertTrue(rows[0]["detail"].startswith("base で "), rows[0]["detail"])
        self.assertIn("もう通る", rows[0]["detail"])

    def test_red_tree_result_is_cached(self):
        """赤の木は run の中で動かないので、結末を控えて回をまたいで使い回す"""
        self.stub_red()
        real = fixgates.tddloop.run_suite
        calls = []

        def run(exe, repo, *a, **k):
            calls.append(pathlib.Path(repo).resolve() == self.repo.resolve())
            return real(exe, repo, *a, **k)
        with mock.patch.object(fixgates.tddloop, "run_suite", side_effect=run):
            self.assertEqual(self.problems(attempt=1), [])
            self.assertEqual(self.problems(attempt=2), [])
        self.assertEqual(calls.count(False), 2, "赤の木と base の木は 1 回ずつだけ走らせる")


class TestTestEdits(FixGatesCase):
    def test_unnamed_existing_edit_is_a_miss(self):
        self.ready_with_fields(direct_fields())
        self.edit_tests(*THREE_EDIT)
        rows = self.problems()
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("test_edits", THREE_ID)])

    def test_named_rewrite_and_ruled_limit_pass(self):
        with self.subTest("修正案の rewrite_tests の名指し"):
            self.ready_with_fields(direct_fields(rewrite_tests=[REWRITE]))
            self.edit_tests(*THREE_EDIT)
            self.assertEqual(self.problems(), [])

    def test_ruled_limit_passes_after_ruling(self):
        """裁定 fix_test_scope の範囲 test_stats.py:9（test_mean_of_three の本体の行）を含む関数は通す。1 回目（裁定の前）は通さない"""
        b = self.ready_with_fields(direct_fields())
        (b / conflict.FILE).write_text(json.dumps({"items": [
            {"id": "c1-1", "unit_key": MEAN, "between": ["stats.py:9", "test_stats.py:9"],
             "why_both_cannot_hold": "期待の型が依頼と食い違う", "which_is_right": "test", "status": "ruled",
             "ruling": {"decision": "fix_test_scope", "text": "期待を float で書いてよい", "limits": ["test_stats.py:9"]}}]},
            ensure_ascii=False), encoding="utf-8")
        self.edit_tests(*THREE_EDIT)
        self.assertEqual(self.problems(pass_="ruled"), [])
        self.assertEqual([(r["gate"], r["id"]) for r in self.problems(pass_="first")], [("test_edits", THREE_ID)])

    def test_second_pass_keeps_first_pass_ruled_limit(self):
        """2 回目の修正の段（案を直した行が在る。conflict.second_pass。依頼 226）の受け付けは、裁定の前（first）でも 1 回目の段の
        裁定 fix_test_scope の範囲の直しを通す（base からの差分に 1 回目の直しが在る）"""
        self.ready_with_fields(direct_fields())
        self.rule(["test_stats.py:9"])
        self.edit_tests(*THREE_EDIT)
        self.assertEqual([(r["gate"], r["id"]) for r in self.problems(pass_="first")], [("test_edits", THREE_ID)],
                         "1 回目の段の裁定の前は今どおり")
        self.rule(["test_stats.py:9"], amended=True)
        self.assertEqual(self.problems(pass_="first"), [])

    CLAMP_TESTS = [("test_stats.py::TestStats::test_clamp_within_range", "test_stats.py:11"),
                   ("test_stats.py::TestStats::test_clamp_above_range", "test_stats.py:14")]   # 本体で clamp を名指す種のテスト

    def removes_fields(self, *, base_tests=None, rows=()):
        """removes に stats.clamp を持つ direct の項目の欄を、種の木を相手に planmarks.split で作る（リポジトリの複製はまだ無い）。
        base_tests を渡せば split が removes_tests を引き、rows を渡せばその行（{id, limit}）を欄にそのまま足す"""
        gone = {"name": "stats.clamp", "kind": "function", "change": "remove", "why": "境の判定は mean に寄せたので消す"}
        files = [{"path": "stats.py", "op": "modify", "responsibility": "境の判定", "symbols": [gone], "canonical": "既存の正本"}]
        it = {"unit_keys": [MEAN], "approach": "x" * 20, "files": files, "shrink_first": "y" * 20,
              "narrows": [], "route": "direct", "route_why": "既存の期待の書き換えだけの項目", "tests": [], "rewrite_tests": [],
              "refactor": {"declared": False, "why": ""}}
        kw = {} if base_tests is None else {"base_tests": base_tests}
        _, fields = planmarks.split({"plan": [it]}, SEED, **kw)
        if rows:
            fields[0]["removes_tests"] = [{"id": i, "limit": lim} for i, lim in rows]
        return fields

    def test_removes_permit_is_a_test_permits_row(self):
        """files の change=remove の symbol（消す名）を名指すテストの許しは conflict.test_permits の行（test にテストの id、limit つき）として返り、凍結の検査が読む
        ruled_test_limits にも同じ limit が入る（許しの元は test_permits の 1 本だけ）"""
        b = self.ready_with_fields(self.removes_fields(rows=self.CLAMP_TESTS))
        rows = [p for p in conflict.test_permits(b) if p.get("test") in dict(self.CLAMP_TESTS)]
        self.assertEqual(sorted((p["test"], p["limit"]) for p in rows), sorted(self.CLAMP_TESTS))
        self.assertTrue(all(p["id"] == f"{conflict.REMOVES_TEST_ID}-1" and p["why"] for p in rows), rows)
        self.assertTrue({lim for _, lim in self.CLAMP_TESTS} <= set(conflict.ruled_test_limits(b)))

    def test_edit_of_test_naming_removes_passes(self):
        """run 6a51125d: 修正案の項目の files の change=remove の symbol（消す名）を本体で名指す既存のテストは、書き換え・消しを許す（消す
        仕組みを縛るテストは変えざるを得ない）。許しは split が base の版のテストの本体から引いて凍結した欄の removes_tests
        （conflict.test_permits の行）。消す名を名指さないテストの書き換えは今までどおり拒む"""
        base_tests = {"test_stats.py": (SEED / "test_stats.py").read_text(encoding="utf-8")}
        self.ready_with_fields(self.removes_fields(base_tests=base_tests))
        self.edit_tests("self.assertEqual(clamp(15, 0, 10), 10)", "pass")   # test_clamp_above_range（clamp を名指す）の書き換え
        self.edit_tests("    def test_clamp_within_range(self):\n        self.assertEqual(clamp(5, 0, 10), 5)\n\n", "")   # 消し
        self.assertEqual(self.problems(), [])
        self.edit_tests(*THREE_EDIT)   # test_mean_of_three は clamp を名指さない
        self.assertEqual([(r["gate"], r["id"]) for r in self.problems()], [("test_edits", THREE_ID)])

    def rule(self, limits, *, amended=False):
        """裁定 fix_test_scope の行（範囲 limits）を置く。amended なら案を直した fix_plan_item の行も（2 回目の修正の段の置き場）"""
        rows = [{"id": "c1-1", "unit_key": MEAN, "between": ["stats.py:9", "test_stats.py:9"],
                 "why_both_cannot_hold": "期待の型が依頼と食い違う", "which_is_right": "test", "status": "ruled",
                 "ruling": {"decision": "fix_test_scope", "text": "期待を float で書いてよい", "limits": limits}}]
        if amended:
            rows.append({"id": "c1-2", "unit_key": CLAMP, "between": ["stats.py:12", "test_stats.py:12"],
                         "why_both_cannot_hold": "案の項目が誤り", "which_is_right": "request", "status": "ruled",
                         "ruling": {"decision": conflict.REPLAN, "text": "項目を直せ", "limits": []},
                         conflict.REPLAN_STATE: conflict.AMENDED})
        (self.board / conflict.FILE).write_text(json.dumps({"items": rows}, ensure_ascii=False), encoding="utf-8")

    def test_ruled_scope_reads_like_the_frozen_check(self):
        """範囲の読みは輪の凍結の検査と同じ: ファイルだけは全部・1 行の指しは関数の全体・`<行>-<行>` は書いたとおり"""
        self.ready_with_fields(direct_fields())
        self.edit_tests(*THREE_EDIT)   # test_mean_of_three の本体の 9 行目
        for limits, ok in ((["test_stats.py"], True), (["test_stats.py:8"], True), (["test_stats.py:9-9"], True),
                           (["test_stats.py:8-8"], False), (["test_stats.py:11-12"], False)):
            with self.subTest(limits):
                self.rule(limits)
                got = [(r["gate"], r["id"]) for r in self.problems(pass_="ruled")]
                self.assertEqual(got, [] if ok else [("test_edits", THREE_ID)])

    def test_test_edits_row_becomes_an_ask_on_base_lines(self):
        """test_edits の行は overflow_asks が範囲の相談の頼み（base の定義の行。項目は planrange.owner で結ぶ）にする"""
        self.ready_with_fields(direct_fields())
        self.edit_tests(*THREE_EDIT)
        rows = self.problems()
        (ask,) = fixgates.overflow_asks(rows, self.repo, self.base, [{"item": 1, "allowed_paths": ["test_stats.py"]}])
        self.assertEqual((ask["item"], ask["tests"], ask["new_tests"]), (1, ["test_stats.py:8"], []))
        self.assertEqual(ask["line"], fixgates.reject_line(rows[0]))


class TestTestFilesDeclared(FixGatesCase):
    def test_declared_path_counts_as_test_file(self):
        """名の慣習に当たらないファイルも、受け入れのテスト・書き換えの名指しのパスならテストのファイル（写す・凍結の照らし）"""
        self.ready_with_fields(direct_fields())
        (self.repo / "checks.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
        (self.repo / "calc_test.go").write_text("package calc\n", encoding="utf-8")
        tree = fixgates.tddloop.snapshot(self.repo)
        self.assertEqual(fixgates._test_files(self.repo, self.base, tree), ["calc_test.go"])
        self.assertEqual(sorted(fixgates._test_files(self.repo, self.base, tree, ["./checks.py::test_x"])),
                         ["calc_test.go", "checks.py"])


class TestLedgerAndText(FixGatesCase):
    def test_ledger_marks_the_attempt_and_does_not_repeat_rows(self):
        """帳面の行は受け付けの回の印（pass・attempt）を持つ。最後の回の通し直しで同じ回に 2 度走っても行は 1 度だけ（preflight F23）"""
        self.ready_with_fields()
        self.add_test_that_passes_on_base("test_mean_of_two")
        self.edit_tests(*THREE_EDIT)
        first = self.problems(attempt=3)
        again = self.problems(attempt=3)
        self.assertEqual(first, again)
        self.assertEqual(sorted(r["gate"] for r in first), ["red_green", "test_edits"], "どちらの関門の行も返す")
        rows = self.ledger()["rows"]
        self.assertEqual(len(rows), 2, rows)
        self.assertEqual({(r["pass"], r["attempt"]) for r in rows}, {("first", 3)})
        self.assertEqual(set(rows[0]), {"pass", "attempt", "gate", "id", "detail", "unit_keys"})
        self.problems(attempt=1, pass_="ruled")
        self.assertEqual(len(self.ledger()["rows"]), 4, "裁定の後の 1 回目は別の回")

    def test_reject_text_lists_every_row(self):
        rows = [{"gate": "red_green", "id": MEAN_ID, "detail": "base で緑", "unit_keys": [MEAN]},
                {"gate": "test_edits", "id": THREE_ID, "detail": "名指しの外", "unit_keys": []}]
        lines = fixgates.reject_lines(rows)
        self.assertEqual(len(lines), 2, "行ごとに 1 つの文（最後の回に文ごとに単位に結ぶ）")
        self.assertTrue(all(t.startswith(fixgates.REJECT) for t in lines), lines)
        self.assertIn(MEAN, lines[0], "red_green の文は項目の単位を名指す")
        self.assertTrue(lines[-1].endswith(fixgates.REDO) and fixgates.REDO not in lines[0], "出し直しの頼みは最後の文の末だけ")
        text = fixgates.reject_text(rows)
        self.assertEqual(text, " / ".join(lines))
        for w in (f"red_green {MEAN_ID}: base で緑", f"test_edits {THREE_ID}: 名指しの外", "全部"):
            self.assertIn(w, text)
        self.assertEqual(fixgates.GATES, ("red_green", "test_edits"))

    def test_unchecked_whys_drop_out_of_duty(self):
        """確かめなかった理由は OUT_OF_DUTY を除いた物（呼び手が受けた回の trace の SKIPPED_OP に載せる）"""
        whys = [f"{fixgates.OUT_OF_DUTY}: 修正案の項目 2（単位 u2）", fixgates.NO_SUITE, None]
        self.assertEqual(fixgates.unchecked_whys(whys), [fixgates.NO_SUITE])
        self.assertEqual(fixgates.skipped(self.board, pass_="first", attempt=1), [], "帳面が無ければ空")
        self.assertEqual(fixgates.guards(self.board, pass_="first", attempt=1), [])

    def test_every_section_is_kept_and_counted(self):
        """帳面の節は SECTIONS の 1 か所が持つ。節を足せば、前の行の読み込み・組み直し・積み増しの数えが全部その節も回る（#97 の落とし）"""
        self.board.mkdir(parents=True, exist_ok=True)
        old = {"pass": "first", "attempt": 1, "note": "前の回"}
        (self.board / fixgates.LEDGER).write_text(json.dumps({"rows": [], "notes": [old]}), encoding="utf-8")
        with mock.patch.object(fixgates, "SECTIONS", (*fixgates.SECTIONS, "notes")):
            fixgates._record(self.board, {"pass": "first", "attempt": 2}, {"notes": [{"note": "この回"}]})
        self.assertEqual(self.ledger()["notes"], [old, {"pass": "first", "attempt": 2, "note": "この回"}])
        self.assertEqual(self.ledger()["guards"], [])


class TestAgreedPermitTrees(unittest.TestCase):
    """範囲の相談の合意の範囲の行は修正前の版の行（読む木は 1 つ）。凍結の検査のように別の木を読む側へは conflict.agreed_permits が移す"""
    BASE = "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertEqual(1, 1)\n\n    def test_b(self):\n        self.assertEqual(2, 2)\n"
    LOOP = BASE.replace("class T(unittest.TestCase):\n", "class T(unittest.TestCase):\n    def test_new(self):\n        self.assertEqual(0, 0)\n\n")

    def limits(self, lim, *, source=True, base=True):
        rows = [{"item": "1", "id": 1, "granted_tests": [lim], "reason": "許した"}]
        src = {"t.py": self.LOOP}.get if source else None
        old = {"t.py": self.BASE}.get if base else None
        return [p["limit"] for p in conflict.agreed_permits(rows, source=src, base=old)]

    def test_single_line_follows_the_function(self):
        self.assertEqual(self.limits("t.py:8"), ["t.py:11"], "test_b の定義の行は 3 行ずれる")
        self.assertEqual(self.limits("t.py:9"), ["t.py:11"], "関数の中の行も、その関数の定義の行へ")

    def test_range_moves_both_ends_or_is_dropped(self):
        self.assertEqual(self.limits("t.py:8-9"), ["t.py:11-12"])
        self.assertEqual(self.limits("t.py:3-5"), [], "書き換わった行を含む範囲は移せない")

    def test_whole_file_and_unread_trees(self):
        self.assertEqual(self.limits("t.py"), ["t.py"], "ファイルだけの指しは木に依らない")
        self.assertEqual(self.limits("t.py:8", source=False), ["t.py:8"], "読む木が修正前の版ならそのまま")
        self.assertEqual(self.limits("t.py:8", base=False), [], "修正前の版が読めないなら許しを捨てる（広げない）")
        self.assertEqual(self.limits("u.py:8"), [], "読む木に無いファイルの許しは捨てる")


if __name__ == "__main__":
    unittest.main()

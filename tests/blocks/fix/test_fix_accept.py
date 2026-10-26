"""修正の受け付けの試験（docs/design/fix.md の 8.1・8.2・10 節の 5 と 7・14.2 の test_fix_accept.py）。workflows/fix/src の写し
（board・facts・gates・scope・unitrows・parking・rules）を kit.load で読み、script は kit.Run で子のプロセスで回す。

写した元と、この中の 3 つの部分:
1. 部品（_l_ の名）: lib/tests/test_fix_gates.py〔TestRedGreen は test_tdd.py〕・test_plan_scope.py・test_fix_units.py・
   test_fix_duty.py・test_duty_sets.py。元の試験の lib の名（fixgates・planscope・unitrows・parking・fixboard・fixrules・tddloop・ruling）は
   試験ごとに setUp で src の写しに結び直す（_l_bind。src の関数は呼ぶ時に `from src import …` で同じ block の写しを引く）
   - 事後の関門の束（src/gates.py）: base の木の結末の使い回し・輪の記録した赤の木・既存のテストの変更・テストのファイルの申告・帳面と文
   - 承認済みの修正案の項目と修正の差分の照らし（src/scope.py の problems・new_test_ids・added_removed・with_agreed・reject_head）
   - 単位ごとの閉鎖の表（src/unitrows.py の build）と裁定の出どころの縛り（src/ruling.py の problems の grounds）・git が期限を持たない
   - 直す義務の正本（src/board.py の fix_duty・nothing_owed_but_excused）と最後の回の拒否の行の結び（src/parking.py の settle の declared）
   - 直す義務の集合を消費する所の入口（rules.owed_values・board.fix_duty・tdd.start・gates._accept_tests）から作って突き合わせる
2. 継ぎ目（SeamTemp・_s_ の名）: lib/tests/test_fix_seams.py の FixAcceptSeamCase・SettleOverflowSeamCase・OverflowTraceSeamCase・
   FactchecksSeamCase・FixgatesSeamCase・ScopeTextSeamCase・PlanrangeSeamCase・GateItemsSeamCase。RecountSeamCase は受け付け
   （board.accept_reply）を通す振る舞いの試験に作り直した（10 節の 7）
   - 受け付け（board.accept_reply）: 単位の行・申し出・範囲・閉鎖の数え直し・写しの照らし・最後の回の諦め・はみ出しの相談
   - 書き込みの出どころ（board.undeclared_writes。keep-essence の 5）
   - class_query の数え直し（recount.accept_fix を board.accept_reply の中で。keep-essence の 7）
   - 範囲の相談の頼み（board.consult_ask が src/prompts.consult_render の md の字で答えの役の指示を組む）
3. script（_XPlace・_x_ の名）: tests/workflows/test_fix.py の FixLoopScriptsCase・FixAcceptCase・HandoffCase。intake・group_start・
   fix_prep・fix_accept・fix_ruled_prep・fix_ruled_accept を、始めの記録の無い使い捨ての run directory と tests/e2e/target-seed/ の
   写しの git のリポジトリで、port の値（INPUTS_<名>）だけを渡して回す。置き場は ports.place()（単独の run は $ARTIFACTS_DIR）。
   修正役の指示は fix_prep・fix_ruled_prep の返りの prompt の字（prompts/parts/fixer.md）。拒否の理由は指示に貼られる
   （{shared:rejected}）。裁定の輪（rule_prep・rule_accept）は test_ruling.py、consult_check の答えの役の起こしは test_consult.py
"""
import ast
import contextlib
import copy
import hashlib
import importlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

from tests.bin import hermetic
from tests.bin.gitkit import committed_copy, git
from tests.blocks import kit
from tests.blocks.fix import support

_l_SEED = kit.ROOT / "tests" / "e2e" / "target-seed"
_L_SRC = {"fixboard": "board", "fixgates": "gates", "planscope": "scope", "unitrows": "unitrows", "parking": "parking",
          "fixrules": "rules", "tddloop": "tdd", "ruling": "ruling", "common": "common", "basecase": "basecase"}


def _l_bind() -> None:
    """block fix の src を読み直し、このモジュールの名（元の試験の lib の名）に結ぶ。lib のまま呼ぶ物も結ぶ"""
    kit.load("fix", "board")
    names = globals()
    for name, module in _L_SRC.items():
        names[name] = importlib.import_module(f"src.{module}")
    for name in ("conflict", "planmarks", "planrange", "querytest"):
        names[name] = importlib.import_module(name)


_l_bind()


# 修正役の範囲の相談の頼みが必ず持つ 3 つの欄（#833。docs/design/fix.md の 13.3 の 1）
SUMMARY = {"tried": ["stats.py の平均の分母を直した"], "blocked": "直しは済んだが、記録の置き場が範囲の外にしか無い",
           "evidence": [{"path": "stats.py", "line": 4}]}


class _LSrc(unittest.TestCase):
    def setUp(self):
        super().setUp()
        _l_bind()


_l_MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
_l_CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"

# 対象リポジトリの根で test_*.py を unittest で回し、JUnit XML を第 1 引数に書く実行器で、pytest の JUnit に合わせる物: 断言の失敗も
# 本体の例外も failure と書き、message に「<型>: <文>」を付ける（元 lib/tests/test_blk_fix_tdd.py の PYTEST_LIKE）
_l_PYTEST_LIKE = '''
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

_l_NEW_TEST = '''
    def test_mean_of_two(self):
        self.assertEqual(mean([2, 4]), 3)
'''


# ---- lib/tests/test_fix_gates.py の写し
_l_MEAN_ID = "test_stats.py::TestStats::test_mean_of_two"
_l_THREE_ID = "test_stats.py::TestStats::test_mean_of_three"
_l_TEST_ROW = {"id": _l_MEAN_ID, "behavior": "2 つの値の平均", "path": "stats.mean を直に呼ぶ", "red_kind": "assertion",
            "red_why": "今は len-1 で割る"}
# 欄の形は test_plan_brief.FIELDS と同じ（unit_keys は修正案の項目の名指し。planmarks.split が欄に写す）
_l_FIELDS = [{"unit_keys": [_l_MEAN], "route": "tdd", "route_why": "", "tests": [_l_TEST_ROW], "rewrite_tests": [],
           "refactor": {"declared": False, "why": ""}}]
_l_MEAN_FIX = {"return sum(xs) / (len(xs) - 1)": "return sum(xs) / len(xs)"}
_l_THREE_EDIT = ("self.assertEqual(mean([1, 2, 3]), 2)", "self.assertEqual(mean([1, 2, 3]), 2.0)")   # 既存のテストの期待の書き換え
_l_HALVE = {"def clamp(x, lo, hi):": "def halve(x):\n    return x / 2\n\n\ndef clamp(x, lo, hi):"}   # 今の木で足す関数
_l_TWO_ID = "test_two.py::TestTwo::test_halve"
_l_TWO_FILE = ("import unittest\n\nfrom stats import halve\n\n\nclass TestTwo(unittest.TestCase):\n    def test_halve(self):\n"
            "        self.assertEqual(halve(4), 2)\n")   # base では読み込みで落ちる（halve が無い）新しいテストのファイル
_l_NO_JUNIT = "import sys\nsys.exit(0)\n"   # JUnit を書かない実行器
_l_REWRITE = {"id": _l_THREE_ID, "behavior": "3 つの値の平均の期待", "old": "期待は 2", "new": "期待を 2.0 に書き換える",
           "limit": "test_stats.py:8"}


def _l_asked_row(paths=(), new_tests=(), decision="deny", granted_new_tests=(), **over):
    """範囲の相談の確かめの行（conflict.ASKED_OP。受け付けが見つけたはみ出しを聞いた物。origin accept）"""
    return {"id": 1, "at": "2026-10-10T00:00:00+09:00", "turn": 2, "pass": "first", "round": 1, "node": "plan-answer", "item": "1",
            "unit_keys": [_l_MEAN], "paths": list(paths), "tests": [], "new_tests": list(new_tests), "why": "案の外のはみ出しを聞いた",
            "status": "answered", "decision": decision, "granted_paths": [], "granted_tests": [],
            "granted_new_tests": list(granted_new_tests), "spec": "", "reason": "範囲の中で直せる", "notes": [], "out_of_scope": [],
            "overrode_out_of_scope": [], "session": None, "origin": "accept", **over}


def _l_direct_fields(**over):
    """受け入れのテストの無い direct の項目（red_green を回さず test_edits だけを見る）"""
    return [{**_l_FIELDS[0], "route": "direct", "route_why": "既存の期待の書き換えだけの項目", "tests": [], **over}]


class FixGatesCase(_LSrc):
    """種の git（self.repo）と fix の run の置き場（self.board。元の盤面の代わり）と小さな実行器"""

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory(prefix="works-fix-gates-")
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name).resolve()
        self.repo = self.tmp / "repo"
        self.base = committed_copy(self.repo, _l_SEED)
        self.board = self.tmp / "place"
        self.board.mkdir()
        self.suite = self.tmp / "suite.py"
        self.suite.write_text(_l_PYTEST_LIKE, encoding="utf-8")
        self.SUITE = str(self.suite)

    def ready_with_fields(self, fields=None):
        """置き場に承認済みの修正案の欄の控え（凍結の印つき）を置く。base は種の commit"""
        planmarks.save(self.board, 1, _l_FIELDS if fields is None else fields)
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
        self.add_test(_l_NEW_TEST)

    def add_test_that_passes_on_base(self, name):
        self.add_test(f"\n    def {name}(self):\n        self.assertEqual(clamp(5, 0, 10), 5)\n")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True, encoding="utf-8", check=True,
                              env=hermetic.child_env()).stdout.strip()

    def fields_for(self, test_id):
        """受け入れのテスト test_id を 1 本持つ tdd の項目（単位は mean）"""
        return [{**_l_FIELDS[0], "tests": [{**_l_TEST_ROW, "id": test_id}]}]

    def problems(self, suite=None, attempt=1, base=None, **kw):
        return fixgates.problems(self.board, self.repo, self.base if base is None else base,
                                 self.SUITE if suite is None else suite, attempt, **kw)

    def ledger(self):
        return json.loads((self.board / fixgates.LEDGER).read_text(encoding="utf-8"))

    def worktrees(self):
        out = subprocess.run(["git", "worktree", "list"], cwd=self.repo, capture_output=True, text=True, encoding="utf-8", check=True,
                             env=hermetic.child_env()).stdout
        return out.strip().splitlines()


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
        self.edit_tree(_l_MEAN_FIX)
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
        self.edit_tree(_l_MEAN_FIX)
        calls, patch = self.counted()
        with patch:
            self.assertEqual(self.problems(attempt=1), [])
            self.edit_tests("self.assertEqual(mean([2, 4]), 3)", "self.assertEqual(clamp(5, 0, 10), 5)")
            rows = self.problems(attempt=2)
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", _l_MEAN_ID)])
        self.assertTrue(rows[0]["detail"].startswith("base で "), rows[0]["detail"])
        self.assertIn("もう通る", rows[0]["detail"])
        self.assertEqual(calls["base"], 2)

    def test_other_base_rev_reruns_base(self):
        self.ready_with_fields()
        self.add_test_mean_of_two()
        self.edit_tree(_l_MEAN_FIX)
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
        self.edit_tree(_l_MEAN_FIX)
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


_l_STUB = "def halve(x):\n    return 0  # 仮の実装\n\n\ndef clamp(x, lo, hi):"   # test の段で赤を作るために足す最小の仮の実装
_l_TWICE_ID = "test_two.py::TestTwo::test_twice"
_l_SAB_ID = "test_sab.py::TestSab::test_clamp_in_range"
_l_SAB = ("import unittest\n\nfrom stats import clamp\n\n\nclass TestSab(unittest.TestCase):\n    def test_clamp_in_range(self):\n"
       "        self.assertEqual(clamp(5, 0, 10), 5)\n")   # base で通るテスト（直す前から緑）


class TestLoopRedTree(FixGatesCase):
    """輪が仮の実装（テストでないファイル）を足して赤を確かめた単位の受け入れのテストは、事後の関門も輪の記録した赤の木
    （red_tree。仮の実装を含む）で名指しを走らせ直して failure を見る（持ち主の直す前の関所の答え (3) A）。base の木にテストの
    ファイルだけを写すと、仮の実装が無く組み立てで落ちて『一式の結末に居ない』と拒むため。今の木のテストのファイルが赤の記録と
    輪が終わった時（frozen）と違う単位は、赤の木が今のテストを表さないので base の木で見る（今どおり）。赤の木を使う名指しも
    base の木＋テストのファイルで 1 回走らせ、passed（直す前から通る）なら拒む（仮の実装の名目で既存の実装を壊した偽の赤を拒む）"""

    def stub_red(self):
        """test_two.py（halve を読む）を書き、仮の実装で赤にした木を輪の単位の記録に残し、本物の実装に直す"""
        self.ready_with_fields(self.fields_for(_l_TWO_ID))
        (self.repo / "test_two.py").write_text(_l_TWO_FILE, encoding="utf-8")
        self.edit_tree({"def clamp(x, lo, hi):": _l_STUB})
        red = fixgates.tddloop.snapshot(self.repo)
        self.save_unit(red)
        self.edit_tree({"return 0  # 仮の実装": "return x / 2"})
        return red

    def save_unit(self, red_tree, **over):
        """置き場の輪の状態 tdd-1/state.json に、赤を確かめた単位の記録を置く（輪の _test が残す欄だけ。frozen は輪が終わった
        時のテストのファイルの hash で、今の姿）"""
        unit = {"unit_key": _l_MEAN, "route": "tdd", "red": "ok", "tests": [_l_TWO_ID], "test_files": ["test_two.py"],
                "test_hashes": fixgates.tddloop.hashes(self.repo, ["test_two.py"]), "red_tree": red_tree, "stub_files": ["stats.py"],
                **over}
        self.save_units({_l_MEAN: unit})

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
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", _l_TWO_ID)])
        self.assertTrue(rows[0]["detail"].startswith(fixgates.RED_TREE_HEAD), rows[0]["detail"])
        self.assertIn("もう通る", rows[0]["detail"])

    def test_test_file_moved_after_loop_falls_back_to_base(self):
        """輪が終わった後（やり直し・裁定）にテストのファイルが変わった単位は、赤の木が今のテストを表さないので base の木で見る
        （仮の実装が無く拒む）"""
        self.stub_red()
        path = self.repo / "test_two.py"
        path.write_text(path.read_text(encoding="utf-8") + "\n# 赤の後の書き足し\n", encoding="utf-8")
        rows = self.problems()
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", _l_TWO_ID)])
        self.assertTrue(rows[0]["detail"].startswith("base で "), rows[0]["detail"])
        self.assertIn("一式の結末に居ない", rows[0]["detail"])

    def test_two_units_share_a_test_file(self):
        """後の単位が同じテストのファイルに足し、後の単位の仮の実装を頭で読んでも、先の単位は輪の赤の木で見る（輪が終わった時の
        テストのファイルと今が同じなら、赤の時の hash と違っても base に戻さない）"""
        self.ready_with_fields([{**_l_FIELDS[0], "tests": [{**_l_TEST_ROW, "id": _l_TWO_ID}, {**_l_TEST_ROW, "id": _l_TWICE_ID}]}])
        path = self.repo / "test_two.py"
        path.write_text(_l_TWO_FILE, encoding="utf-8")
        self.edit_tree({"def clamp(x, lo, hi):": _l_STUB})
        a = {"unit_key": "a", "route": "tdd", "red": "ok", "tests": [_l_TWO_ID], "test_files": ["test_two.py"],
             "test_hashes": fixgates.tddloop.hashes(self.repo, ["test_two.py"]), "red_tree": fixgates.tddloop.snapshot(self.repo)}
        self.edit_tree({"return 0  # 仮の実装": "return x / 2"})   # 単位 a を直す
        path.write_text(path.read_text(encoding="utf-8").replace("from stats import halve", "from stats import halve, twice")
                        + "\n    def test_twice(self):\n        self.assertEqual(twice(2), 4)\n", encoding="utf-8")
        self.edit_tree({"def clamp(x, lo, hi):": "def twice(x):\n    return 0  # 仮の実装\n\n\ndef clamp(x, lo, hi):"})
        b = {"unit_key": "b", "route": "tdd", "red": "ok", "tests": [_l_TWICE_ID], "test_files": ["test_two.py"],
             "test_hashes": fixgates.tddloop.hashes(self.repo, ["test_two.py"]), "red_tree": fixgates.tddloop.snapshot(self.repo)}
        self.edit_tree({"return 0  # 仮の実装": "return x * 2"})   # 単位 b を直す
        self.save_units({"a": a, "b": b})
        self.assertEqual(self.problems(), [])

    def test_sabotaged_red_tree_green_at_base_is_a_miss(self):
        """test の段が既存の実装を壊した木を赤の木に残し、fix の段で戻しても、base の木＋テストのファイルで通る（直す前から緑）
        なら行（別の目 R1 の写し）"""
        self.ready_with_fields(self.fields_for(_l_SAB_ID))
        (self.repo / "test_sab.py").write_text(_l_SAB, encoding="utf-8")
        self.edit_tree({"def clamp(x, lo, hi):": "def clamp(x, lo, hi):\n    return -1  # 壊す\n"})
        self.save_unit(fixgates.tddloop.snapshot(self.repo), tests=[_l_SAB_ID], test_files=["test_sab.py"],
                       test_hashes=fixgates.tddloop.hashes(self.repo, ["test_sab.py"]))
        self.edit_tree({"    return -1  # 壊す\n": ""})
        rows = self.problems()
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("red_green", _l_SAB_ID)])
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
        # 赤の木の走らせ直しは common.red_rerun の口（common.run_suite）、base の木は関門の口（tddloop.run_suite）
        with mock.patch.object(fixgates.tddloop, "run_suite", side_effect=run), \
                mock.patch.object(common, "run_suite", side_effect=run):
            self.assertEqual(self.problems(attempt=1), [])
            self.assertEqual(self.problems(attempt=2), [])
        self.assertEqual(calls.count(False), 2, "赤の木と base の木は 1 回ずつだけ走らせる")


class TestTestEdits(FixGatesCase):
    def test_unnamed_existing_edit_is_a_miss(self):
        self.ready_with_fields(_l_direct_fields())
        self.edit_tests(*_l_THREE_EDIT)
        rows = self.problems()
        self.assertEqual([(r["gate"], r["id"]) for r in rows], [("test_edits", _l_THREE_ID)])

    def test_named_rewrite_and_ruled_limit_pass(self):
        with self.subTest("修正案の rewrite_tests の名指し"):
            self.ready_with_fields(_l_direct_fields(rewrite_tests=[_l_REWRITE]))
            self.edit_tests(*_l_THREE_EDIT)
            self.assertEqual(self.problems(), [])

    def test_ruled_limit_passes_after_ruling(self):
        """裁定 fix_test_scope の範囲 test_stats.py:9（test_mean_of_three の本体の行）を含む関数は通す。1 回目（裁定の前）は通さない"""
        b = self.ready_with_fields(_l_direct_fields())
        (b / conflict.FILE).write_text(json.dumps({"items": [
            {"id": "c1-1", "unit_key": _l_MEAN, "between": ["stats.py:9", "test_stats.py:9"],
             "why_both_cannot_hold": "期待の型が依頼と食い違う", "which_is_right": "test", "status": "ruled",
             "ruling": {"decision": "fix_test_scope", "text": "期待を float で書いてよい", "limits": ["test_stats.py:9"]}}]},
            ensure_ascii=False), encoding="utf-8")
        self.edit_tests(*_l_THREE_EDIT)
        self.assertEqual(self.problems(pass_="ruled"), [])
        self.assertEqual([(r["gate"], r["id"]) for r in self.problems(pass_="first")], [("test_edits", _l_THREE_ID)])

    def test_second_pass_keeps_first_pass_ruled_limit(self):
        """2 回目の修正の段（案を直した行が在る。conflict.second_pass。依頼 226）の受け付けは、裁定の前（first）でも 1 回目の段の
        裁定 fix_test_scope の範囲の直しを通す（base からの差分に 1 回目の直しが在る）"""
        self.ready_with_fields(_l_direct_fields())
        self.rule(["test_stats.py:9"])
        self.edit_tests(*_l_THREE_EDIT)
        self.assertEqual([(r["gate"], r["id"]) for r in self.problems(pass_="first")], [("test_edits", _l_THREE_ID)],
                         "1 回目の段の裁定の前は今どおり")
        self.rule(["test_stats.py:9"], amended=True)
        self.assertEqual(self.problems(pass_="first"), [])

    CLAMP_TESTS = [("test_stats.py::TestStats::test_clamp_within_range", "test_stats.py:11"),
                   ("test_stats.py::TestStats::test_clamp_above_range", "test_stats.py:14")]   # 本体で clamp を名指す種のテスト

    def removes_fields(self, *, base_tests=None, rows=()):
        """removes に stats.clamp を持つ direct の項目の欄を、種の木を相手に planmarks.split で作る（リポジトリの複製はまだ無い）。
        base_tests を渡せば split が removes_tests を引き、rows を渡せばその行（{id, limit}）を欄にそのまま足す"""
        gone = {"name": "stats.clamp", "change": "remove", "why": "境の判定は mean に寄せたので消す"}
        files = [{"path": "stats.py", "op": "modify", "responsibility": "境の判定", "symbols": [gone],
                  "home": {"concept": "境の判定", "why": "境の判定は stats.py が持つ"},
                  "considered": [{"path": "alt_home.py", "why_not": "同じ仕事の助け手が alt_home.py:3 に無かった"}]}]
        it = {"unit_keys": [_l_MEAN], "approach": "x" * 20, "files": files, "shrink_first": "y" * 20,
              "narrows": [], "route": "direct", "route_why": "既存の期待の書き換えだけの項目", "tests": [], "rewrite_tests": [],
              "refactor": {"declared": False, "why": ""}}
        kw = {} if base_tests is None else {"base_tests": base_tests}
        _, fields = planmarks.split({"plan": [it]}, _l_SEED, **kw)
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
        base_tests = {"test_stats.py": (_l_SEED / "test_stats.py").read_text(encoding="utf-8")}
        self.ready_with_fields(self.removes_fields(base_tests=base_tests))
        self.edit_tests("self.assertEqual(clamp(15, 0, 10), 10)", "pass")   # test_clamp_above_range（clamp を名指す）の書き換え
        self.edit_tests("    def test_clamp_within_range(self):\n        self.assertEqual(clamp(5, 0, 10), 5)\n\n", "")   # 消し
        self.assertEqual(self.problems(), [])
        self.edit_tests(*_l_THREE_EDIT)   # test_mean_of_three は clamp を名指さない
        self.assertEqual([(r["gate"], r["id"]) for r in self.problems()], [("test_edits", _l_THREE_ID)])

    def rule(self, limits, *, amended=False):
        """裁定 fix_test_scope の行（範囲 limits）を置く。amended なら案を直した fix_plan_item の行も（2 回目の修正の段の置き場）"""
        rows = [{"id": "c1-1", "unit_key": _l_MEAN, "between": ["stats.py:9", "test_stats.py:9"],
                 "why_both_cannot_hold": "期待の型が依頼と食い違う", "which_is_right": "test", "status": "ruled",
                 "ruling": {"decision": "fix_test_scope", "text": "期待を float で書いてよい", "limits": limits}}]
        if amended:
            rows.append({"id": "c1-2", "unit_key": _l_CLAMP, "between": ["stats.py:12", "test_stats.py:12"],
                         "why_both_cannot_hold": "案の項目が誤り", "which_is_right": "request", "status": "ruled",
                         "ruling": {"decision": conflict.REPLAN, "text": "項目を直せ", "limits": []},
                         conflict.REPLAN_STATE: conflict.AMENDED})
        (self.board / conflict.FILE).write_text(json.dumps({"items": rows}, ensure_ascii=False), encoding="utf-8")

    def pasted(self, pass_: str, label: str) -> set:
        """修正役の指示の行（fixrules.tests_rows）の label で始まる行のバッククオートの名"""
        text = fixrules.tests_rows(None, conflict.edit_permits(self.board, pass_), None)
        (line,) = [ln for ln in text.splitlines() if ln.startswith(f"- {label}")]
        return set(re.findall(r"`([^`]+)`", re.split(r"）?: ", line, maxsplit=1)[1]))

    def test_pasted_edit_permits_are_what_test_edits_lets_through(self):
        """指示書に貼る名指しと範囲は、事後の関門が通す物と同じ値（conflict.edit_permits）。片方だけ変えれば赤になる"""
        named, limits = "本体を変えてよい既存のテストの名指し", "本体を変えてよい既存のテストの範囲"
        self.edit_tests(*_l_THREE_EDIT)
        with self.subTest("修正案の rewrite_tests の名指しは貼られ、通る"):
            b = self.ready_with_fields(_l_direct_fields(rewrite_tests=[_l_REWRITE]))
            self.assertEqual(self.pasted("first", named), set(conflict.edit_permits(b, "first")["tests"]))
            self.assertIn(_l_THREE_ID, self.pasted("first", named))
            self.assertEqual(self.problems(), [])
        with self.subTest("名指しが無ければ貼られず、拒む"):
            self.ready_with_fields(_l_direct_fields())
            self.assertNotIn(_l_THREE_ID, self.pasted("first", named))
            self.assertEqual([(r["gate"], r["id"]) for r in self.problems()], [("test_edits", _l_THREE_ID)])
        with self.subTest("裁定の範囲は段 ruled にだけ貼られ、そこでだけ通る"):
            self.rule(["test_stats.py:9"])
            self.assertNotIn("test_stats.py:9", self.pasted("first", limits))
            self.assertIn("test_stats.py:9", self.pasted("ruled", limits))
            self.assertEqual(self.problems(pass_="ruled"), [])
            self.assertEqual([(r["gate"], r["id"]) for r in self.problems(pass_="first")], [("test_edits", _l_THREE_ID)])

    def test_ruled_scope_reads_like_the_frozen_check(self):
        """範囲の読みは輪の凍結の検査と同じ: ファイルだけは全部・1 行の指しは関数の全体・`<行>-<行>` は書いたとおり"""
        self.ready_with_fields(_l_direct_fields())
        self.edit_tests(*_l_THREE_EDIT)   # test_mean_of_three の本体の 9 行目
        for limits, ok in ((["test_stats.py"], True), (["test_stats.py:8"], True), (["test_stats.py:9-9"], True),
                           (["test_stats.py:8-8"], False), (["test_stats.py:11-12"], False)):
            with self.subTest(limits):
                self.rule(limits)
                got = [(r["gate"], r["id"]) for r in self.problems(pass_="ruled")]
                self.assertEqual(got, [] if ok else [("test_edits", _l_THREE_ID)])

    def test_test_edits_row_becomes_an_ask_on_base_lines(self):
        """test_edits の行は overflow_asks が範囲の相談の頼み（base の定義の行。項目は planrange.owner で結ぶ）にする"""
        self.ready_with_fields(_l_direct_fields())
        self.edit_tests(*_l_THREE_EDIT)
        rows = self.problems()
        (ask,) = fixgates.overflow_asks(rows, self.repo, self.base, [{"item": 1, "allowed_paths": ["test_stats.py"]}])
        self.assertEqual((ask["item"], ask["tests"], ask["new_tests"]), (1, ["test_stats.py:8"], []))
        self.assertEqual(ask["line"], fixgates.reject_line(rows[0]))


class TestTestFilesDeclared(FixGatesCase):
    def test_declared_path_counts_as_test_file(self):
        """名の慣習に当たらないファイルも、受け入れのテスト・書き換えの名指しのパスならテストのファイル（写す・凍結の照らし）"""
        self.ready_with_fields(_l_direct_fields())
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
        self.edit_tests(*_l_THREE_EDIT)
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
        rows = [{"gate": "red_green", "id": _l_MEAN_ID, "detail": "base で緑", "unit_keys": [_l_MEAN]},
                {"gate": "test_edits", "id": _l_THREE_ID, "detail": "名指しの外", "unit_keys": []}]
        lines = fixgates.reject_lines(rows)
        self.assertEqual(len(lines), 2, "行ごとに 1 つの文（最後の回に文ごとに単位に結ぶ）")
        self.assertTrue(all(t.startswith(fixgates.REJECT) for t in lines), lines)
        self.assertIn(_l_MEAN, lines[0], "red_green の文は項目の単位を名指す")
        self.assertTrue(lines[-1].endswith(fixgates.REDO) and fixgates.REDO not in lines[0], "出し直しの頼みは最後の文の末だけ")
        text = fixgates.reject_text(rows)
        self.assertEqual(text, " / ".join(lines))
        for w in (f"red_green {_l_MEAN_ID}: base で緑", f"test_edits {_l_THREE_ID}: 名指しの外", "全部"):
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


class TestAgreedPermitTrees(_LSrc):
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




# ---- lib/tests/test_plan_scope.py の写し
_l_ITEM = {"item": 1, "unit_keys": [_l_MEAN], "files": [], "route": "direct", "tests": [], "rewrite_tests": [],
        "allowed_paths": ["stats.py"], "out_of_scope": []}
_l_ROW = {"unit_key": _l_MEAN, "files": ["stats.py"]}
_l_STATS = {"stats.py": ("def mean(xs):\n    return 0\n", "def mean(xs):\n    return 1\n")}


def _l_item(**over):
    return {**_l_ITEM, **over}


def _l_add(name):
    """files の symbols の行（足す）"""
    return {"name": name, "change": "add"}


def _l_rm(name):
    """files の symbols の行（消す。消す訳 why つき）"""
    return {"name": name, "change": "remove", "why": "古い名で、呼び手は新しい名に寄せた"}


def _l_frow(path, *symbols, op="modify", **extra):
    """files の行（path・操作・symbols）。受け持ちは照らしに関わらない固定の字。home・considered は照らしに当たらない既定"""
    return {"path": path, "op": op, "responsibility": "この行の受け持ち", "symbols": list(symbols),
            "home": {"concept": f"{path} の考え", "why": "この行の path が住処だから"},
            "considered": [{"path": "alt_home.py", "why_not": "同じ仕事の助け手が alt_home.py:3 に無かった"}], **extra}


class ProblemsCase(_LSrc):
    def test_inside_allowed_passes(self):
        self.assertEqual(planscope.problems([_l_ITEM], [_l_ROW], _l_STATS)[0], [])

    def test_file_outside_allowed_names_unit_and_item(self):
        got, _ = planscope.problems([_l_ITEM], [{"unit_key": _l_MEAN, "files": ["other.py"]}], {**_l_STATS, "other.py": (None, "x = 1\n")})
        self.assertTrue(any(_l_MEAN in p and "other.py" in p and "項目 1" in p for p in got), got)

    def test_out_of_scope_wins_over_allowed(self):
        it = _l_item(allowed_paths=["*.py"], out_of_scope=[{"glob": "test_*.py", "why": "既存の試験は触らない"}])
        got, _ = planscope.problems([it], [{"unit_key": _l_MEAN, "files": ["test_stats.py"]}], {"test_stats.py": ("a\n", "b\n")})
        self.assertTrue(any("out_of_scope" in p and "test_*.py" in p for p in got), got)

    def test_undeclared_change_outside_every_item(self):
        got, _ = planscope.problems([_l_ITEM], [_l_ROW], {**_l_STATS, "stray.py": (None, "x\n")})
        self.assertTrue(any("stray.py" in p for p in got), got)

    def test_item_without_footprint_is_missing(self):
        got, _ = planscope.problems([_l_ITEM], [_l_ROW], {})
        self.assertTrue(any("範囲の中に変えたファイルが無い" in p and _l_MEAN in p for p in got), got)

    def test_adds_identifier_must_appear_in_added_lines(self):
        it = _l_item(files=[_l_frow("stats.py", _l_add("median"))])
        self.assertTrue(any("median" in p for p in planscope.problems([it], [_l_ROW], _l_STATS)[0]))
        ok = {"stats.py": ("", "def median(xs):\n    return xs[0]\n")}
        self.assertEqual(planscope.problems([it], [_l_ROW], ok)[0], [])

    def test_files_rows_check_same_name_per_path(self):
        """同じ名 median を stats.py と other.py の 2 行で足すと言い、差分が stats.py にだけ median を足した時、other.py の行だけが
        欠けとして名指される（名だけで数えると 2 行が潰れ、stats.py の足しで other.py の欠けも通る）。同じ path で名の違う 2 行も
        1 行ずつ照らされる"""
        two = _l_item(allowed_paths=["*.py"], files=[_l_frow("stats.py", _l_add("median")), _l_frow("other.py", _l_add("median"))])
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "other.py"]}]
        only_stats = {"stats.py": ("", "def median(xs):\n    return xs[0]\n"), "other.py": ("a\n", "b\n")}
        got, _ = planscope.problems([two], rows, only_stats)
        self.assertEqual([p for p in got if "median" in p and "other.py" in p and "足した行に無い" in p].__len__(), 1, got)
        self.assertFalse(any("stats.py の add median" in p for p in got), got)
        both = {**only_stats, "other.py": ("a\n", "def median(xs):\n    return xs[-1]\n")}
        self.assertEqual(planscope.problems([two], rows, both)[0], [])
        pair = _l_item(files=[_l_frow("stats.py", _l_add("median"), _l_add("mode"))])
        got, _ = planscope.problems([pair], [_l_ROW], {"stats.py": ("", "def median(xs):\n    return xs[0]\n")})
        self.assertEqual([p for p in got if "足した行に無い" in p and "mode" in p].__len__(), 1, got)
        self.assertFalse(any("add median" in p for p in got), got)

    def test_files_ops_create_and_delete_follow_the_diff(self):
        """op=create の path が差分で新設されていない時と、op=delete の path が差分で消えていない時に、それぞれ行を名指して拒む。
        op=rename は元のパスが消え、移し先が新設されていることを見る（modify の差分は test_files_modify_path_must_change_in_diff）"""
        mk = _l_item(allowed_paths=["*.py"], files=[_l_frow("app.py", op="create")])
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "app.py"]}]
        exists = {**_l_STATS, "app.py": ("x = 1\n", "x = 2\n")}
        self.assertTrue(any("app.py" in p and "op=create" in p for p in planscope.problems([mk], rows, exists)[0]))
        self.assertTrue(any("app.py" in p and "op=create" in p for p in planscope.problems([mk], rows, _l_STATS)[0]), "差分に無い")
        self.assertEqual(planscope.problems([mk], rows, {**_l_STATS, "app.py": (None, "x = 1\n")})[0], [])
        rm_ = _l_item(allowed_paths=["*.py"], files=[_l_frow("old.py", op="delete", why="呼び手は stats に寄せたので要らない")])
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "old.py"]}]
        self.assertTrue(any("old.py" in p and "op=delete" in p
                            for p in planscope.problems([rm_], rows, {**_l_STATS, "old.py": ("a\n", "b\n")})[0]))
        self.assertEqual(planscope.problems([rm_], rows, {**_l_STATS, "old.py": ("a\n", None)})[0], [])
        mv = _l_item(allowed_paths=["*.py"], files=[_l_frow("new.py", op="rename", **{"from": "old.py"}, why="名を実体に合わせた")])
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "old.py", "new.py"]}]
        moved = {**_l_STATS, "old.py": ("a\n", None), "new.py": (None, "a\n")}
        self.assertEqual(planscope.problems([mv], rows, moved)[0], [])
        got, _ = planscope.problems([mv], rows, {**_l_STATS, "old.py": ("a\n", "b\n"), "new.py": ("c\n", "d\n")})
        self.assertTrue(any("old.py" in p and "op=rename" in p for p in got), got)
        self.assertTrue(any("new.py" in p and "op=rename" in p for p in got), got)

    def test_files_modify_path_must_change_in_diff(self):
        """op=modify の行は symbols が無くても、path が差分に無ければ欠けとして名指して拒む（前の欄 adds に既存の foo.py を書いた時と
        同じ照らし）。path を変えれば通る"""
        it = _l_item(allowed_paths=["*.py"], files=[_l_frow("foo.py")])
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "foo.py"]}]
        got, _ = planscope.problems([it], rows, _l_STATS)
        self.assertTrue(any("foo.py" in p and "op=modify" in p and _l_MEAN in p for p in got), got)
        self.assertEqual(planscope.problems([it], rows, {**_l_STATS, "foo.py": ("a\n", "b\n")})[0], [])

    def test_definition_outside_add_paths_is_extra(self):
        """同名の定義が足す行の path の外に在れば余分に数える"""
        it = _l_item(allowed_paths=["*.py"], files=[_l_frow("stats.py", _l_add("median"))])
        ch = {"stats.py": ("", "def median(xs):\n    pass\n"), "util.py": ("", "def median(xs):\n    pass\n")}
        got, _ = planscope.problems([it], [{"unit_key": _l_MEAN, "files": ["stats.py", "util.py"]}], ch)
        self.assertTrue(any("util.py" in p and "足す行の path" in p for p in got), got)
        both = _l_item(allowed_paths=["*.py"], files=[_l_frow("stats.py", _l_add("median")), _l_frow("util.py", _l_add("median"))])
        self.assertEqual(planscope.problems([both], [{"unit_key": _l_MEAN, "files": ["stats.py", "util.py"]}], ch)[0], [],
                         "同じ名を足すと言った行の path は、どれも足す先")

    def test_removes_identifier_must_be_gone(self):
        it = _l_item(files=[_l_frow("stats.py", _l_rm("old_mean"))])
        kept = {"stats.py": ("def old_mean():\n    pass\n", "def old_mean():\n    return 1\n")}
        self.assertTrue(any("old_mean" in p for p in planscope.problems([it], [_l_ROW], kept)[0]))
        gone = {"stats.py": ("def old_mean():\n    pass\n", "def mean():\n    pass\n")}
        self.assertEqual(planscope.problems([it], [_l_ROW], gone)[0], [])

    def test_prose_names_not_checked(self):
        it = _l_item(files=[_l_frow("stats.py", _l_add("平均の定義の注記"), _l_rm("古い注記の文"))])
        got, note = planscope.problems([it], [_l_ROW], _l_STATS)
        self.assertEqual(got, [])
        self.assertEqual(note["unchecked"], ["平均の定義の注記", "古い注記の文"])

    def test_new_test_must_be_named_in_tests(self):
        """tests に無い新しいテストは拒み、記録の overflow に名指す（申告した単位が無くても同じ）。tests に名指せば拒否の行も
        overflow も空"""
        base = "class TestStats:\n    def test_a(self):\n        pass\n"
        ch = {**_l_STATS, "test_stats.py": (base, base + "    def test_extra(self):\n        pass\n")}
        it = _l_item(allowed_paths=["stats.py", "test_stats.py"])
        got, note = planscope.problems([it], [_l_ROW], ch)
        self.assertTrue(any("test_stats.py::TestStats::test_extra" in p and "tests にも無い" in p for p in got), got)
        self.assertEqual([t for o in note.get("overflow") or [] for t in o["new_tests"]], ["test_stats.py::TestStats::test_extra"])
        named = _l_item(tests=[{"id": "test_stats.py::TestStats::test_extra"}])
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "test_stats.py"]}]
        got, note = planscope.problems([named], rows, ch)
        self.assertEqual((got, note.get("overflow")), ([], []))

    def test_new_test_in_unit_files_is_recorded_not_rejected(self):
        """run 75d8ed4e: 人の関所の条件に合わせて、単位が申告したファイルに tests に無いテストを足した。赤を確かめずに通さず、
        拒否の行にして記録の overflow に（その id・項目・単位を）並べる。unproven の欄は無い"""
        base = "class TestStats:\n    def test_a(self):\n        pass\n"
        ch = {**_l_STATS, "test_stats.py": (base, base + "    def test_extra(self):\n        pass\n")}
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "test_stats.py"]}]
        it = _l_item(allowed_paths=["stats.py", "test_stats.py"])
        got, note = planscope.problems([it], rows, ch)
        tid = "test_stats.py::TestStats::test_extra"
        self.assertTrue(any(tid in p for p in got), got)
        (over,) = note["overflow"]
        self.assertEqual((over["item"], over["unit_key"], over["new_tests"]), (1, _l_MEAN, [tid]))
        self.assertIn(over["line"], got)
        self.assertNotIn("unproven", note)

    def test_new_test_outside_plan_is_overflow(self):
        """単位が申告したファイルに、どの項目の tests にも無いテストを足すと、拒否の行に入り、記録の overflow にその id と項目の
        番号と単位が並ぶ（応急処置の unproven の欄は無い）"""
        base = "class TestStats:\n    def test_a(self):\n        pass\n"
        ch = {**_l_STATS, "test_stats.py": (base, base + "    def test_extra(self):\n        pass\n")}
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "test_stats.py"]}]
        got, note = planscope.problems([_l_item(allowed_paths=["stats.py", "test_stats.py"])], rows, ch)
        tid = "test_stats.py::TestStats::test_extra"
        self.assertTrue(any(tid in p for p in got), got)
        over = note.get("overflow")
        self.assertEqual([(o["item"], o["unit_key"], o["new_tests"]) for o in over or []], [(1, _l_MEAN, [tid])], note)
        self.assertTrue(all(o["line"] in got for o in over), (over, got))
        self.assertNotIn("unproven", note)

    def test_outside_path_is_overflow_with_item(self):
        """行の申告したパスが項目の allowed_paths の外なら、拒否の行と同じ文が overflow の line に入り、item はその単位の項目、
        paths はそのパス"""
        got, note = planscope.problems([_l_ITEM], [{"unit_key": _l_MEAN, "files": ["other.py"]}], {**_l_STATS, "other.py": (None, "x = 1\n")})
        line = next(p for p in got if _l_MEAN in p and "other.py" in p and "項目 1" in p)
        over = note.get("overflow")
        self.assertEqual([(o["line"], o["item"], o["unit_key"], o["paths"]) for o in over or []], [(line, 1, _l_MEAN, ["other.py"])], note)

    def agreed_items(self, *kinds, tid="test_stats.py::TestStats::test_extra"):
        """項目 1 に、範囲の相談の合意で新しいテスト tid が入った写し（kinds の順に合意を重ねる）"""
        rows = [{"item": "1", "granted_paths": [], "granted_tests": [], "granted_new_tests": [{"id": tid, "red_kind": k}]}
                for k in kinds]
        return planscope.with_agreed([_l_item(allowed_paths=["stats.py", "test_stats.py"])], rows)

    def test_agreed_test_not_written_is_not_missing(self):
        """合意で入ったテストは許しで義務でない: 修正役が書かなくても『tests の X が修正の後の木に無い』の欠けにしない"""
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py"]}]
        self.assertEqual(planscope.problems(self.agreed_items("red"), rows, _l_STATS)[0], [])

    def test_agreed_test_written_under_other_name_is_overflow_not_missing(self):
        """合意の id と別の名で書いたテストは、案の外のテスト（はみ出し。相談に回る）で、合意の id の欠けにはしない"""
        base = "class TestStats:\n    def test_a(self):\n        pass\n"
        ch = {**_l_STATS, "test_stats.py": (base, base + "    def test_other(self):\n        pass\n")}
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "test_stats.py"]}]
        got, note = planscope.problems(self.agreed_items("red"), rows, ch)
        self.assertFalse([p for p in got if "修正の後の木に無い" in p], got)
        self.assertEqual([o["new_tests"] for o in note["overflow"]], [["test_stats.py::TestStats::test_other"]])

    def test_later_agreement_wins_for_same_id(self):
        """同じ id の合意を重ねると、後の合意の赤の種類が勝つ（相談で種類を直せる）"""
        (row,) = self.agreed_items("red", "guard")[0]["tests"]
        self.assertEqual(row["red_kind"], "guard")

    def test_agreed_new_test_joins_item_tests(self):
        """範囲の相談の合意（granted_new_tests）を持つ行を with_agreed に通した項目では、その新しいテストが項目の写しの tests に
        印 agreed と red_kind つきで並び、tests に無いテストの拒否の行（6）にならない"""
        base = "class TestStats:\n    def test_a(self):\n        pass\n"
        ch = {**_l_STATS, "test_stats.py": (base, base + "    def test_extra(self):\n        pass\n")}
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "test_stats.py"]}]
        tid = "test_stats.py::TestStats::test_extra"
        agreed = [{"item": "1", "granted_paths": [], "granted_tests": [],
                   "granted_new_tests": [{"id": tid, "red_kind": "red"}]}]
        got = planscope.with_agreed([_l_ITEM], agreed)
        (row,) = got[0]["tests"]
        self.assertEqual((row["id"], row["red_kind"]), (tid, "red"))
        self.assertTrue(row.get("agreed"), row)
        self.assertEqual(_l_ITEM["tests"], [], "元の項目は変えない")
        self.assertEqual(planscope.problems(got, rows, ch)[0], [])

    def test_named_test_missing_after_fix(self):
        it = _l_item(tests=[{"id": "test_stats.py::TestStats::test_mean_of_two"}])
        self.assertTrue(any("test_mean_of_two" in p and _l_MEAN in p for p in planscope.problems([it], [_l_ROW], _l_STATS)[0]))

    def test_out_of_scope_wins_over_permits(self):
        """out_of_scope は permits（テストの変更の許し・直す裁定の limits）にも勝つ（案が外したパスが要るのは案の項目の誤りで、
        fix_plan_item の道）。行の申告したパスも、申告の無い変わったパスも拒む"""
        it = _l_item(allowed_paths=["*.py"], out_of_scope=[{"glob": "legacy.py", "why": "古い置き場は触らない"}])
        ch = {**_l_STATS, "legacy.py": ("a\n", "b\n")}
        for rows in ([{"unit_key": _l_MEAN, "files": ["stats.py", "legacy.py"]}], [_l_ROW]):
            got, _ = planscope.problems([it], rows, ch, permits=("legacy.py",))
            self.assertTrue(any("out_of_scope" in p and "legacy.py" in p for p in got), (rows, got))

    def test_agreed_paths_join_their_item_only(self):
        """範囲の相談の合意（conflict.agreed の行）は、その項目の allowed_paths に足す（ほかの項目・out_of_scope は変えない）"""
        other = _l_item(item=2, unit_keys=[_l_CLAMP], allowed_paths=["clamp.py"])
        agreed = [{"item": "1", "granted_paths": ["CHANGELOG.md"], "granted_tests": ["test_stats.py:3"]}]
        got = planscope.with_agreed([_l_ITEM, other], agreed)
        self.assertEqual(got[0]["allowed_paths"], ["stats.py", "CHANGELOG.md"])
        self.assertEqual(got[1]["allowed_paths"], ["clamp.py"])
        self.assertEqual(_l_ITEM["allowed_paths"], ["stats.py"], "元の項目は変えない")
        ch = {**_l_STATS, "CHANGELOG.md": ("a\n", "b\n")}
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "CHANGELOG.md"]}]
        self.assertTrue(planscope.problems([_l_ITEM], rows, ch)[0], "合意の無い時は拒む")
        self.assertEqual(planscope.problems(got, rows, ch)[0], [])

    def test_permit_paths_are_in_scope(self):
        ch = {**_l_STATS, "test_stats.py": ("a\n", "b\n")}
        self.assertEqual(planscope.problems([_l_ITEM], [_l_ROW], ch, permits=("test_stats.py",))[0], [])

    def test_new_test_ids_only_test_modules(self):
        src = "def test_x():\n    pass\n"
        self.assertEqual(planscope.new_test_ids("util.py", None, src), [], "試験のモジュールの名でない .py は数えない")
        self.assertEqual(planscope.new_test_ids("test_util.py", None, src), ["test_util.py::test_x"])
        self.assertEqual(planscope.new_test_ids("util_test.py", "", src), ["util_test.py::test_x"])
        self.assertEqual(planscope.new_test_ids("test_util.py", None, "def test_x(:\n"), [], "構文の壊れた now は []")
        self.assertEqual(planscope.new_test_ids("test_util.md", None, src), [])

    def test_added_removed_replace(self):
        self.assertEqual(planscope.added_removed("a\nb\n", "a\nc\n"), (["c"], ["b"]))
        self.assertEqual(planscope.added_removed(None, "x\n"), (["x"], []), "None は空の中身")
        self.assertEqual(planscope.added_removed("x\n", None), ([], ["x"]))

    def test_note_records_checked_items(self):
        _, note = planscope.problems([_l_ITEM, _l_item(item=2, unit_keys=[_l_CLAMP])], [_l_ROW], _l_STATS)
        self.assertEqual((note["checked"], note["items"]), (True, [1]), "見る項目は rows の単位と重なる項目だけ")

    def test_problem_lines_carry_unit_keys_for_binding(self):
        """拒否の行は単位の key か項目の unit_keys の全部を字のまま含める（3 回目の拒否で単位に結ぶ）"""
        it = _l_item(unit_keys=[_l_MEAN, _l_CLAMP], files=[_l_frow("stats.py", _l_add("median"), _l_rm("old_mean"))],
                  tests=[{"id": "test_stats.py::TestStats::test_two"}])
        got, _ = planscope.problems([it], [{"unit_key": _l_MEAN, "files": ["other.py"]}, {"unit_key": _l_CLAMP, "files": ["stats.py"]}],
                                    {"other.py": (None, "x\n")})
        unit_lines = [p for p in got if "どの項目の allowed_paths にも無い" not in p]
        self.assertTrue(unit_lines)
        for p in unit_lines:
            self.assertTrue(_l_MEAN in p or _l_CLAMP in p, p)


class HeldItemCase(_LSrc):
    """裁定で外れた単位の項目も範囲を与える（依頼 241。外れた単位を直させない守りは受け付けの check_excused_units）"""

    def test_held_item_grants_like_any_item(self):
        mean = _l_item(allowed_paths=["stats.py", "mean_util.py"], out_of_scope=[{"glob": "legacy.py", "why": "古い置き場は触らない"}],
                    tests=[{"id": "test_stats.py::TestStats::test_mean_of_two"}])
        clamp = _l_item(item=2, unit_keys=[_l_CLAMP], allowed_paths=["stats.py", "test_stats.py", "legacy.py"])
        base = "class TestStats:\n    def test_a(self):\n        pass\n"
        ch = {**_l_STATS, "mean_util.py": (None, "x = 1\n"),
              "test_stats.py": (base, base + "    def test_mean_of_two(self):\n        pass\n")}
        rows = [{"unit_key": _l_CLAMP, "files": ["stats.py", "test_stats.py"]}]
        self.assertEqual(planscope.problems([mean, clamp], rows, ch)[0], [], "外れた項目 1 の範囲と tests にも入る")
        got, _ = planscope.problems([mean, clamp], [{"unit_key": _l_MEAN, "files": ["legacy.py"]}], {"legacy.py": ("a\n", "b\n")})
        self.assertTrue(any("out_of_scope" in p and "legacy.py" in p for p in got), "外れた項目の単位には今どおり拒む")
        got, _ = planscope.problems([mean, clamp], [{"unit_key": _l_CLAMP, "files": ["stats.py"]}],
                                    {"stats.py": _l_STATS["stats.py"], "legacy.py": ("a\n", "b\n")})
        self.assertTrue(any("out_of_scope" in p and "legacy.py" in p for p in got), "単位に結べない変更は今どおり拒む")
        self.assertEqual(planscope.problems([mean, clamp], [{"unit_key": _l_CLAMP, "files": ["legacy.py"]}],
                                            {"legacy.py": ("a\n", "b\n")})[0], [],
                         "項目 2 が明示に許したパスは、項目 2 の単位では項目 1 の out_of_scope に負けない（run 249b）")


class FalseRejectCase(_LSrc):
    """正しい修正を誤って拒まない（審査の Important 2・3）"""

    def test_absent_partner_unit_does_not_reject_live_unit(self):
        """項目 [_l_MEAN, _l_CLAMP] の _l_MEAN が行に無い（止めた・外した）とき、足す物・消す物・tests の欠けで _l_CLAMP を拒まない
        （Missing 側は項目の単位が全部生きている時だけ見る）。範囲の検査は残る"""
        it = _l_item(unit_keys=[_l_MEAN, _l_CLAMP], files=[_l_frow("stats.py", _l_add("median"), _l_rm("old_mean"))],
                  tests=[{"id": "test_stats.py::TestStats::test_mean_of_two"}])
        rows = [{"unit_key": _l_CLAMP, "files": ["stats.py"]}]
        self.assertEqual(planscope.problems([it], rows, _l_STATS)[0], [])
        got, _ = planscope.problems([it], [{"unit_key": _l_CLAMP, "files": ["other.py"]}], {"other.py": (None, "x\n")})
        self.assertTrue(any(_l_CLAMP in p and "other.py" in p for p in got), got)
        both = [{"unit_key": _l_MEAN, "files": ["stats.py"]}, {"unit_key": _l_CLAMP, "files": ["stats.py"]}]
        self.assertTrue(any("median" in p for p in planscope.problems([it], both, _l_STATS)[0]), "全部の単位が生きていれば見る")

    def test_mentioned_removed_name_is_gone(self):
        """消した名が足した行に定義でなく現れる（消えたことを確かめる hasattr・CHANGELOG の注記）だけなら、残ったと見ない"""
        it = _l_item(allowed_paths=["*.py", "CHANGELOG.md"], files=[_l_frow("stats.py", _l_rm("old_mean"))])
        ch = {"stats.py": ("def old_mean():\n    pass\n", "def mean():\n    pass\n"),
              "check_gone.py": (None, "import stats\nassert not hasattr(stats, 'old_mean')\n"),
              "CHANGELOG.md": ("# 変更\n", "# 変更\n- `old_mean` を消した\n")}
        rows = [{"unit_key": _l_MEAN, "files": sorted(ch)}]
        self.assertEqual(planscope.problems([it], rows, ch)[0], [])
        again = {**ch, "util.py": (None, "def old_mean():\n    pass\n")}
        got, _ = planscope.problems([it], [{"unit_key": _l_MEAN, "files": sorted(again)}], again)
        self.assertTrue(any("old_mean" in p for p in got), "足した行に定義が在れば残ったと見る")

    CONCEPTS_LINE = '  "pattern": "def where_paths|def lead_path",\n'

    def test_definition_text_in_data_file_is_not_outside_add_paths(self):
        """行の頭（字下げは許す）で始まる定義だけを定義と数える: 表（JSON）の文字列の中の `def <名>` は足す行の path の外の定義でなく、
        字下げした本物の定義（async def）は数え続ける"""
        it = _l_item(allowed_paths=["stats.py", "util.py", "docs/**"],
                  files=[_l_frow("stats.py", _l_add("where_paths"))])
        ch = {"stats.py": ("", "def where_paths(xs):\n    return xs\n"),
              "docs/concepts.json": ("", self.CONCEPTS_LINE),
              "util.py": ("", "    async def where_paths(xs):\n        return xs\n")}
        got, _ = planscope.problems([it], [{"unit_key": _l_MEAN, "files": sorted(ch)}], ch)
        outside = [p for p in got if "足す行の path" in p]
        self.assertTrue(any("util.py" in p for p in outside), got)
        self.assertFalse(any("docs/concepts.json" in p for p in got), got)

    def test_removed_name_in_data_file_string_is_gone(self):
        """files の change=remove の名を消した差分に、その名を `def <名>` の字で含む表（JSON）の文字列を足しても、足した行に定義が残ったと見ない"""
        it = _l_item(allowed_paths=["stats.py", "docs/**"], files=[_l_frow("stats.py", _l_rm("lead_path"))])
        ch = {"stats.py": ("def lead_path(xs):\n    return xs\n", "def where_paths(xs):\n    return xs\n"),
              "docs/concepts.json": ("", self.CONCEPTS_LINE)}
        got, _ = planscope.problems([it], [{"unit_key": _l_MEAN, "files": sorted(ch)}], ch)
        self.assertEqual(got, [])

    def test_dotted_name_found_by_last_segment(self):
        """名は :: と . で割った最後の段で探す。/ を含む名は確かめず unchecked に回す"""
        it = _l_item(files=[_l_frow("stats.py", _l_add("Stats.median"), _l_add("平均の注記"))])
        ch = {"stats.py": ("", "class Stats:\n    def median(self):\n        pass\n")}
        got, note = planscope.problems([it], [_l_ROW], ch)
        self.assertEqual(got, [])
        self.assertEqual(note["unchecked"], ["平均の注記"])

    def test_py_file_name_is_module_not_extension(self):
        """.py のファイルは symbols の名でなく、行の path と op で見る: op=create の行は path が差分で新設されたか（足した行の 'py' の
        語で通さない）、op=delete の行は path が差分で消えたか（ファイルの中身が自分の名を書かないので語では探せない）"""
        it = _l_item(allowed_paths=["*.py", "app/**"], files=[_l_frow("app/receivers.py", op="create")])
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "app/receivers.py"]}]
        word_only = {"stats.py": ("a\n", "a\np = \"data.py\"\n")}
        self.assertTrue(any("app/receivers.py" in p for p in planscope.problems([it], rows, word_only)[0]),
                        "モジュールのファイルが無ければ、足した行の 'py' の語で通さない")
        added = {"stats.py": ("a\n", "b\n"), "app/receivers.py": (None, "def handle():\n    pass\n")}
        self.assertEqual(planscope.problems([it], rows, added)[0], [], "モジュールのファイルを足せば、中身に自分の名が無くても通る")
        pkg = _l_item(allowed_paths=["*.py", "app/**"], files=[_l_frow("app/receivers/__init__.py", op="create")])
        files = {"stats.py": ("a\n", "b\n"), "app/receivers/__init__.py": (None, "X = 1\n")}
        self.assertEqual(planscope.problems([pkg], [{"unit_key": _l_MEAN, "files": sorted(files)}], files)[0], [])
        rm_ = _l_item(allowed_paths=["*.py"], files=[_l_frow("old.py", op="delete", why="呼び手は stats に寄せたので要らない")])
        gone = {"stats.py": ("a\n", "b\n"), "old.py": ("def f():\n    pass\n", None)}
        self.assertEqual(planscope.problems([rm_], [{"unit_key": _l_MEAN, "files": sorted(gone)}], gone)[0], [])
        kept = {"stats.py": ("a\n", "b\n"), "old.py": ("import x.py\n", "y = 1\n")}
        self.assertTrue(any("old.py" in p for p in planscope.problems([rm_], [{"unit_key": _l_MEAN, "files": sorted(kept)}], kept)[0]),
                        "ファイルが残れば、消した行の 'py' の語で通さない")

    def test_py_file_name_edge_shapes(self):
        """空の __init__.py で新設したパッケージも新設に数える（新しいファイルは足した行が無くてもよい）。パスは op=create の行の path
        そのもので見る（拡張子の前に . を含む名も、名の字の読み分けでなく path の一致）"""
        it = _l_item(allowed_paths=["*.py", "app/**"],
                  files=[_l_frow("app/receivers/__init__.py", op="create"), _l_frow("app/receivers/core.py", op="create")])
        pkg = {"stats.py": ("a\n", "b\n"), "app/receivers/__init__.py": (None, ""), "app/receivers/core.py": (None, "X = 1\n")}
        self.assertEqual(planscope.problems([it], [{"unit_key": _l_MEAN, "files": sorted(pkg)}], pkg)[0], [])
        dotted = _l_item(allowed_paths=["*.py"], files=[_l_frow("app.receivers.py", op="create")])
        got, note = planscope.problems([dotted], [{"unit_key": _l_MEAN, "files": ["stats.py", "app.receivers.py"]}],
                                       {**_l_STATS, "app.receivers.py": (None, "")})
        self.assertEqual((got, note["unchecked"]), ([], []))

    # docstring の __doc__（run 35ad1c2a: stats.mode.__doc__ を足すと言った案を、def の直下に足した docstring の差分で拒んだ）
    SRC = "def mean(xs):\n    return 0\n\n\ndef mode(xs):\n    return max(xs, key=xs.count)\n"

    def test_doc_attribute_found_by_docstring(self):
        """名の最後の段が __doc__ なら、足した行の語でなく、その前の段の def・class が差分で docstring を得たかを ast で見る
        （docstring の字は __doc__ を書かない）"""
        it = _l_item(files=[_l_frow("stats.py", _l_add("mode.__doc__"))])
        now = self.SRC.replace("def mode(xs):\n", "def mode(xs):\n    \"\"\"最頻値。空の xs は ValueError\"\"\"\n")
        got, note = planscope.problems([it], [_l_ROW], {"stats.py": (self.SRC, now)})
        self.assertEqual((got, note["unchecked"]), ([], []))

    def test_doc_attribute_missing_when_owner_gains_no_docstring(self):
        """名指した def が docstring を得なければ Missing（ほかの関数の docstring・本体の変更では通さない）"""
        it = _l_item(files=[_l_frow("stats.py", _l_add("mode.__doc__"))])
        body = self.SRC.replace("key=xs.count", "key=xs.count)  # 最頻値\n    (0")
        other = self.SRC.replace("def mean(xs):\n", "def mean(xs):\n    \"\"\"平均\"\"\"\n")
        for now in (body, other):
            got, _ = planscope.problems([it], [_l_ROW], {"stats.py": (self.SRC, now)})
            self.assertTrue(any("mode.__doc__" in p and _l_MEAN in p for p in got), got)

    def test_doc_attribute_same_docstring_is_not_added(self):
        """版に既に在る docstring と同じ字のままなら足していない（変えた docstring は足した物に数える）"""
        it = _l_item(files=[_l_frow("stats.py", _l_add("mode.__doc__"))])
        base = self.SRC.replace("def mode(xs):\n", "def mode(xs):\n    \"\"\"最頻値\"\"\"\n")
        same = base.replace("key=xs.count", "key=lambda x: xs.count(x)")
        self.assertTrue(planscope.problems([it], [_l_ROW], {"stats.py": (base, same)})[0])
        changed = base.replace("最頻値", "最頻値。空の xs は ValueError")
        self.assertEqual(planscope.problems([it], [_l_ROW], {"stats.py": (base, changed)})[0], [])

    def test_doc_attribute_of_method_module_and_path_forms(self):
        """クラスの中の def（Stats.median.__doc__）・モジュール（名だけの __doc__）は行の path のファイルで同じに見る。パスは行の
        path 欄に移ったので、<パス>::<名>.__doc__ の形は要らない"""
        base = "class Stats:\n    def median(self):\n        pass\n"
        meth = _l_item(files=[_l_frow("stats.py", _l_add("Stats.median.__doc__"))])
        now = base.replace("def median(self):\n", "def median(self):\n        \"\"\"中央値\"\"\"\n")
        self.assertEqual(planscope.problems([meth], [_l_ROW], {"stats.py": (base, now)})[0], [])
        mod = _l_item(files=[_l_frow("stats.py", _l_add("__doc__"))])
        self.assertEqual(planscope.problems([mod], [_l_ROW], {"stats.py": (base, "\"\"\"数の道具\"\"\"\n" + base)})[0], [])
        self.assertTrue(planscope.problems([mod], [_l_ROW], {"stats.py": (base, now)})[0], "def の docstring はモジュールの物でない")
        other = _l_item(allowed_paths=["*.py"], files=[_l_frow("other.py", _l_add("Stats.median.__doc__"))])
        got, _ = planscope.problems([other], [{"unit_key": _l_MEAN, "files": ["stats.py", "other.py"]}],
                                    {"stats.py": (base, now), "other.py": ("a\n", "b\n")})
        self.assertTrue(any("other.py" in p and "Stats.median.__doc__" in p for p in got), "別の path の docstring では通さない")

    def test_doc_attribute_literal_assignment_still_passes(self):
        """__doc__ の字を書いて足す形（mode.__doc__ = ...）は今までどおり足した行の語で通る"""
        it = _l_item(files=[_l_frow("stats.py", _l_add("mode.__doc__"))])
        now = self.SRC + "\n\nmode.__doc__ = \"最頻値\"\n"
        self.assertEqual(planscope.problems([it], [_l_ROW], {"stats.py": (self.SRC, now)})[0], [])


class LoopFrozenCase(_LSrc):
    """TDD の輪が凍らせたファイル（loop: パス → 凍った時の中身）。修正役に問うのは凍った後に変えた分だけ、欠けは版から見る"""
    BASE = "class TestStats:\n    def test_a(self):\n        pass\n"
    FROZEN = BASE + "    def test_new(self):\n        pass\n"

    def test_untouched_frozen_file_not_charged(self):
        it = _l_item(tests=[{"id": "test_stats.py::TestStats::test_new"}])
        ch = {**_l_STATS, "test_stats.py": (self.BASE, self.FROZEN), "data.json": (None, "[]\n")}
        loop = {"test_stats.py": self.FROZEN, "data.json": "[]\n"}
        self.assertEqual(planscope.problems([it], [_l_ROW], ch, loop=loop)[0], [])
        got = planscope.problems([it], [_l_ROW], ch)[0]
        self.assertTrue(any("data.json" in p for p in got), "輪の無い run なら範囲の外")

    def test_test_added_after_freeze_counts(self):
        it = _l_item(tests=[{"id": "test_stats.py::TestStats::test_new"}])
        now = self.FROZEN + "    def test_after(self):\n        pass\n"
        ch = {**_l_STATS, "test_stats.py": (self.BASE, now)}
        got = planscope.problems([it], [_l_ROW], ch, loop={"test_stats.py": self.FROZEN}, permits=("test_stats.py",))[0]
        self.assertTrue(any("test_after" in p for p in got), got)
        self.assertFalse(any("test_new" in p for p in got), got)

    def test_qualified_remove_sees_other_class(self):
        """消す名 Stats.median は、Legacy.median を消して Stats.median を残した差分を拒む（ast の名で見る）"""
        base = "class Legacy:\n    def median(self):\n        pass\n\n\nclass Stats:\n    def median(self):\n        pass\n"
        now = "class Legacy:\n    pass\n\n\nclass Stats:\n    def median(self):\n        pass\n"
        ch = {"stats.py": (base, now)}
        got = planscope.problems([_l_item(files=[_l_frow("stats.py", _l_rm("Stats.median"))])], [_l_ROW], ch)[0]
        self.assertTrue(any("Stats.median" in p for p in got), got)
        self.assertEqual(planscope.problems([_l_item(files=[_l_frow("stats.py", _l_rm("Legacy.median"))])], [_l_ROW], ch)[0], [])

    def test_removed_call_with_kept_definition_remains(self):
        """呼び出しの行だけを消して定義を残した差分は、消えていない"""
        base = "def old_mean():\n    pass\n\n\nx = old_mean()\n"
        now = "def old_mean():\n    pass\n\n\nx = 1\n"
        got = planscope.problems([_l_item(files=[_l_frow("stats.py", _l_rm("old_mean"))])], [_l_ROW], {"stats.py": (base, now)})[0]
        self.assertTrue(any("old_mean" in p for p in got), got)


class Round3Case(_LSrc):
    """修飾子をファイルごとに解く規則・凍った時の中身が無いファイル・凍ったファイルの外れと余分（審査の M1〜M4）"""
    FROZEN_HELPER = "def median(xs):\n    return xs[0]\n"

    def test_module_qualified_moved_definition_remains(self):
        """stats.old_mean（モジュール名の修飾子）・stats.py::old_mean の定義を同じファイルの中で移しただけの差分は拒む"""
        base = "def old_mean():\n    pass\n\n\ndef a():\n    pass\n\n\ndef b():\n    pass\n"
        now = "def a():\n    pass\n\n\ndef b():\n    pass\n\n\ndef old_mean():\n    pass\n"
        self.assertIn("def old_mean():", planscope.added_removed(base, now)[1], "定義の行は消した行にも出る（移した）")
        for raw in ("stats.old_mean", "stats.py::old_mean"):
            with self.subTest(raw):
                got = planscope.problems([_l_item(files=[_l_frow("stats.py", _l_rm(raw))])], [_l_ROW], {"stats.py": (base, now)})[0]
                self.assertTrue(any(raw in p for p in got), got)

    def test_module_qualified_other_module_keeps_own_name(self):
        """legacy.median を消し、stats.py が自前の median を残す（その名を含む行は消した）差分は通る"""
        it = _l_item(allowed_paths=["*.py"], files=[_l_frow("legacy.py", _l_rm("legacy.median"))])
        ch = {"legacy.py": ("def median(xs):\n    return 0\n", "x = 1\n"),
              "stats.py": ("def median(xs):\n    return 0\n\n\ny = median([1])\n", "def median(xs):\n    return 0\n")}
        rows = [{"unit_key": _l_MEAN, "files": ["legacy.py", "stats.py"]}]
        self.assertEqual(planscope.problems([it], rows, ch)[0], [])

    def test_unreadable_frozen_content_falls_back_to_base(self):
        """凍った時の中身が無い（None）ファイルは、版からの差分で数える（版から在るテストを足した物と見ない）"""
        base = "class TestStats:\n    def test_a(self):\n        pass\n"
        ch = {**_l_STATS, "test_stats.py": (base, base + "    def test_b(self):\n        pass\n")}
        it = _l_item(allowed_paths=["stats.py", "test_stats.py"], tests=[{"id": "test_stats.py::TestStats::test_b"}])
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "test_stats.py"]}]
        self.assertEqual(planscope.problems([it], rows, ch, loop={"test_stats.py": None})[0], [])

    def test_definition_outside_add_paths_in_frozen_file(self):
        """輪が書いて凍らせたファイルの同名の定義は足す行の path の外として問わない。凍った後に修正役が足した物は拒む"""
        it = _l_item(allowed_paths=["*.py"], files=[_l_frow("stats.py", _l_add("median"))])
        stats = ("", "def median(xs):\n    return xs[0]\n")
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py"]}]
        loop_written = {"stats.py": stats, "helper.py": (None, self.FROZEN_HELPER)}
        self.assertEqual(planscope.problems([it], rows, loop_written, loop={"helper.py": self.FROZEN_HELPER})[0], [])
        after = {"stats.py": stats, "helper.py": (None, "x = 1\n" + self.FROZEN_HELPER)}
        got = planscope.problems([it], rows, after, loop={"helper.py": "x = 1\n"})[0]
        self.assertTrue(any("helper.py" in p and "足す行の path" in p for p in got), got)

    def test_tdd_shape_with_test_adds_passes(self):
        """TDD の形: 試験のファイルの行の symbol test_mean_of_two は輪が書いて凍らせ、凍った後に変わっていなくても、版からの差分で在る"""
        base = "class TestStats:\n    def test_a(self):\n        pass\n"
        frozen = base + "    def test_mean_of_two(self):\n        pass\n"
        it = _l_item(allowed_paths=["stats.py"], tests=[{"id": "test_stats.py::TestStats::test_mean_of_two"}],
                  files=[_l_frow("test_stats.py", _l_add("TestStats::test_mean_of_two"))])
        ch = {**_l_STATS, "test_stats.py": (base, frozen)}
        self.assertEqual(planscope.problems([it], [_l_ROW], ch, loop={"test_stats.py": frozen})[0], [])

    def test_declared_untouched_frozen_file_not_rejected(self):
        """行が凍った後に変わっていないファイル（範囲の外）を申告しても拒まない"""
        ch = {**_l_STATS, "data.json": (None, "[]\n")}
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "data.json"]}]
        self.assertEqual(planscope.problems([_l_ITEM], rows, ch, loop={"data.json": "[]\n"})[0], [])

    def test_same_name_in_untouched_lines_of_other_file_is_gone(self):
        """名を含む行に触れていない別の .py に同じ名の定義が在っても、残ったとは見ない"""
        it = _l_item(allowed_paths=["*.py"], files=[_l_frow("stats.py", _l_rm("old_mean"))])
        ch = {"stats.py": ("def old_mean():\n    pass\n", "def mean():\n    pass\n"),
              "util.py": ("def old_mean():\n    pass\n\n\nA = 1\n", "def old_mean():\n    pass\n\n\nA = 2\n")}
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "util.py"]}]
        self.assertEqual(planscope.problems([it], rows, ch)[0], [])


class CrossItemScopeCase(_LSrc):
    """ほかの項目の out_of_scope は、行の単位の項目が明示に許したパス（allowed_paths・tests の id のファイル・範囲の相談の合意）を
    拒まない（run 249b: 項目 1 の out_of_scope の core/** が、項目 2 の allowed_paths の core の 1 ファイルを直した項目 2 の
    単位を 2 回拒み、単位が止まった）。単位に結べない変更と、単位の項目が許していないパスは今どおり全部の項目の out_of_scope で拒む"""
    ONE = _l_item(allowed_paths=["stats.py"], out_of_scope=[{"glob": "core/**", "why": "項目 1 は共有の core を変えない"}])
    TWO = _l_item(item=2, unit_keys=[_l_CLAMP], allowed_paths=["core/seam.py"])
    CH = {**_l_STATS, "core/seam.py": ("a\n", "b\n")}

    def test_owner_item_allowed_path_passes(self):
        rows = [_l_ROW, {"unit_key": _l_CLAMP, "files": ["core/seam.py"]}]
        self.assertEqual(planscope.problems([self.ONE, self.TWO], rows, self.CH)[0], [])

    def test_owner_item_test_file_passes(self):
        two = _l_item(item=2, unit_keys=[_l_CLAMP], allowed_paths=["clamp.py"], tests=[{"id": "core/test_seam.py::test_clamp"}])
        ch = {**_l_STATS, "clamp.py": ("a\n", "b\n"), "core/test_seam.py": ("", "def test_clamp():\n    pass\n")}
        rows = [_l_ROW, {"unit_key": _l_CLAMP, "files": ["clamp.py", "core/test_seam.py"]}]
        self.assertEqual(planscope.problems([self.ONE, two], rows, ch)[0], [])

    def test_owner_item_granted_path_passes(self):
        """範囲の相談で項目 2 に許したパス（with_agreed が allowed_paths に足す）も、項目 2 の単位では項目 1 の out_of_scope に負けない"""
        items = planscope.with_agreed([self.ONE, self.TWO], [{"item": "2", "granted_paths": ["core/doc.md"]}])
        ch = {**self.CH, "core/doc.md": ("a\n", "b\n")}
        rows = [_l_ROW, {"unit_key": _l_CLAMP, "files": ["core/seam.py", "core/doc.md"]}]
        self.assertEqual(planscope.problems(items, rows, ch)[0], [])

    def test_excluding_item_unit_still_rejected(self):
        """項目 1 の単位が同じパスを申告すれば、項目 1 の out_of_scope で拒む"""
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "core/seam.py"]}]
        got, _ = planscope.problems([self.ONE, self.TWO], rows, self.CH)
        self.assertTrue(any(_l_MEAN in p and "core/seam.py" in p and "項目 1 の out_of_scope" in p for p in got), got)

    def test_path_outside_owner_scope_still_rejected(self):
        """行の単位の項目が許していないパスは、ほかの項目の out_of_scope で今どおり拒む（permits に入っていても）"""
        ch = {**self.CH, "core/other.py": ("a\n", "b\n")}
        rows = [_l_ROW, {"unit_key": _l_CLAMP, "files": ["core/seam.py", "core/other.py"]}]
        got, _ = planscope.problems([self.ONE, self.TWO], rows, ch, permits=("core/other.py",))
        self.assertTrue(any(_l_CLAMP in p and "core/other.py" in p and "out_of_scope" in p for p in got), got)
        self.assertFalse(any("core/seam.py" in p for p in got), got)

    def test_own_item_out_of_scope_still_wins(self):
        two = _l_item(item=2, unit_keys=[_l_CLAMP], allowed_paths=["core/**"],
                   out_of_scope=[{"glob": "core/seam.py", "why": "項目 2 も継ぎ目は変えない"}])
        got, _ = planscope.problems([self.ONE, two], [_l_ROW, {"unit_key": _l_CLAMP, "files": ["core/seam.py"]}], self.CH)
        self.assertTrue(any(_l_CLAMP in p and "項目 2 の out_of_scope" in p for p in got), got)

    def test_unattributed_change_still_rejected_and_names_owner(self):
        """どの行も申告していない変わったパスは単位に結べないので、全部の項目の out_of_scope で拒む。行は許す項目を名指し、
        その項目の単位の files に申告する道を言う"""
        got, _ = planscope.problems([self.ONE, self.TWO], [_l_ROW], self.CH)
        hit = [p for p in got if "core/seam.py" in p]
        self.assertTrue(hit and "項目 1 の out_of_scope" in hit[0] and "項目 2" in hit[0] and "files" in hit[0], got)



class AgreedOverridesOutOfScopeCase(_LSrc):
    """範囲の相談で修正案を書いた役が、その項目の out_of_scope に当たるパスを考え直して許した時（持ち主 2026-10-07「相談で
    考え直させる」）、許したパスに限ってその項目の out_of_scope を外す（with_agreed）。許したパスと字のまま同じパスだけを外し
    （glob の許しで広げない）、ほかの項目の out_of_scope は外さない。合意の無い時は今どおり拒む"""
    ONE = _l_item(allowed_paths=["stats.py"], out_of_scope=[{"glob": "CHANGELOG.md", "why": "記録は別の依頼でまとめて書く"},
                                                         {"glob": "docs/**", "why": "文書は触らない"}])
    CH = {**_l_STATS, "CHANGELOG.md": ("a\n", "b\n")}
    ROWS = [{"unit_key": _l_MEAN, "files": ["stats.py", "CHANGELOG.md"]}]

    def test_without_agreement_still_rejected(self):
        got, _ = planscope.problems(planscope.with_agreed([self.ONE], []), self.ROWS, self.CH)
        self.assertTrue(any("CHANGELOG.md" in p and "out_of_scope" in p for p in got), got)

    def test_granted_path_overrides_own_out_of_scope(self):
        items = planscope.with_agreed([self.ONE], [{"item": "1", "granted_paths": ["CHANGELOG.md"]}])
        self.assertEqual(planscope.problems(items, self.ROWS, self.CH)[0], [])
        self.assertEqual(planscope.problems(items, [_l_ROW], self.CH)[0], [], "申告の無い変更も、外した項目の out_of_scope では拒まない")
        self.assertEqual(self.ONE["out_of_scope"][0]["glob"], "CHANGELOG.md", "元の項目は変えない")

    def test_override_is_exact_path_only(self):
        """docs/a.md を許しても、同じ glob docs/** の docs/b.md は外さない"""
        items = planscope.with_agreed([self.ONE], [{"item": "1", "granted_paths": ["docs/a.md"]}])
        ch = {**_l_STATS, "docs/a.md": ("a\n", "b\n"), "docs/b.md": ("a\n", "b\n")}
        got, _ = planscope.problems(items, [{"unit_key": _l_MEAN, "files": ["stats.py", "docs/a.md", "docs/b.md"]}], ch)
        self.assertFalse(any("docs/a.md" in p for p in got), got)
        self.assertTrue(any("docs/b.md" in p and "out_of_scope" in p for p in got), got)

    def test_granted_test_file_overrides_own_out_of_scope(self):
        """書き換えを許したテスト（granted_tests。permits に入る）のファイルも、その項目の out_of_scope から外す"""
        one = _l_item(allowed_paths=["stats.py"], out_of_scope=[{"glob": "test_old.py", "why": "古い試験は触らない"}])
        items = planscope.with_agreed([one], [{"item": "1", "granted_paths": [], "granted_tests": ["test_old.py:3"]}])
        ch = {**_l_STATS, "test_old.py": ("a\n", "b\n")}
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "test_old.py"]}]
        self.assertTrue(planscope.problems([one], rows, ch, permits=("test_old.py",))[0])
        self.assertEqual(planscope.problems(items, rows, ch, permits=("test_old.py",))[0], [])

    def test_other_item_out_of_scope_is_not_lifted(self):
        """項目 2 に許したパスは項目 1 の out_of_scope を外さない: 項目 2 の単位では通り（e7906845）、項目 1 の単位と申告の無い
        変更は項目 1 の out_of_scope で今どおり拒む"""
        two = _l_item(item=2, unit_keys=[_l_CLAMP], allowed_paths=["clamp.py"])
        items = planscope.with_agreed([self.ONE, two], [{"item": "2", "granted_paths": ["CHANGELOG.md"]}])
        ch = {**self.CH, "clamp.py": ("a\n", "b\n")}
        ok = [_l_ROW, {"unit_key": _l_CLAMP, "files": ["clamp.py", "CHANGELOG.md"]}]
        self.assertEqual(planscope.problems(items, ok, ch)[0], [])
        got, _ = planscope.problems(items, [_l_ROW, {"unit_key": _l_CLAMP, "files": ["clamp.py"]}], ch)
        self.assertTrue(any("CHANGELOG.md" in p and "項目 1 の out_of_scope" in p for p in got), got)


class NameOverlapCase(_LSrc):
    """名が字で同じでも、言語と在り処の違う物は別の物と読み、人に回る申し出を作らない（#664。本物の run で人に回った 3 件と、
    無関係な局所の助け手の改名を強いた 1 件の形）。言語の同じ別のファイルの同名は、テストと本体の間でも今どおり拒み、直す裁定が
    limits に挙げたパス（ruled）なら通す。ほかの許し（permits）では通さない"""
    UNIT = [{"unit_key": _l_MEAN, "files": ["deploy/values.yaml", ".env.sample"]}]

    def test_env_var_in_deploy_values_and_local_sample_is_not_outside_add_paths(self):
        it = _l_item(allowed_paths=["deploy/values.yaml", ".env.sample"], files=[_l_frow("deploy/values.yaml", _l_add("APP_NOTICE_FILE"))])
        ch = {"deploy/values.yaml": ("env:\n", "env:\n  APP_NOTICE_FILE: /data/notice.json\n"),
              ".env.sample": ("", "APP_NOTICE_FILE=./notice.json\n")}
        self.assertEqual(planscope.problems([it], self.UNIT, ch)[0], [])

    def test_same_type_name_in_other_language_is_not_outside_add_paths(self):
        model, iface = ("api/models.py", "class Notice(BaseModel):\n    title: str\n"), \
            ("web/src/notice.ts", "export interface Notice {\n  title: string\n}\n")
        for (path, _), (other, text) in ((model, iface), (iface, model)):
            with self.subTest(add=path):
                it = _l_item(allowed_paths=["api/**", "web/**"], files=[_l_frow(path, _l_add("Notice"))])
                ch = {model[0]: ("", model[1]), iface[0]: ("", iface[1])}
                rows = [{"unit_key": _l_MEAN, "files": sorted(ch)}]
                self.assertEqual(planscope.problems([it], rows, ch)[0], [], other)

    def test_test_function_named_like_product_function_is_rejected_until_ruled(self):
        it = _l_item(allowed_paths=["stats.py", "test_stats.py"], files=[_l_frow("stats.py", _l_add("median"))])
        ch = {"stats.py": ("", "def median(xs):\n    pass\n"), "test_stats.py": ("", "def median():\n    pass\n")}
        rows = [{"unit_key": _l_MEAN, "files": sorted(ch)}]
        self.assertTrue(any("test_stats.py" in p and "足す行の path" in p for p in planscope.problems([it], rows, ch)[0]))
        self.assertEqual(planscope.problems([it], rows, ch, ruled=("test_stats.py",))[0], [])

    def test_removed_name_redefined_in_test_file_is_rejected(self):
        """案が stats.py から _parse を消すと決めたのに、修正役が書き換えを許されたテストのファイルに def _parse を足して古い
        テストを緑に残す: テストのファイルも残りに数えて拒む"""
        it = _l_item(allowed_paths=["stats.py"], files=[_l_frow("stats.py", _l_rm("_parse"))])
        ch = {"stats.py": ("def _parse(s):\n    return s\n", "def mean():\n    pass\n"),
              "tests/test_stats.py": ("from stats import _parse\n", "def _parse(s):\n    return s\n")}
        rows = [{"unit_key": _l_MEAN, "files": sorted(ch)}]
        got, _ = planscope.problems([it], rows, ch, permits=("tests/test_stats.py",))
        self.assertTrue(any("_parse" in p and "消えていない" in p for p in got), got)

    def test_permit_other_than_ruling_does_not_waive_name_check(self):
        """案が tests/test_a.py から _h を消し、修正役が _h を使う tests/test_b.py（書き換えの許し permits に入る）に def _h を足した:
        裁定の前の許しでは数えるので拒み、直す裁定が limits に挙げれば通す"""
        it = _l_item(allowed_paths=["tests/test_a.py"], files=[_l_frow("tests/test_a.py", _l_rm("_h"))])
        ch = {"tests/test_a.py": ("def _h():\n    pass\n", "def _g():\n    pass\n"),
              "tests/test_b.py": ("from tests.test_a import _h\n", "def _h():\n    pass\n")}
        rows = [{"unit_key": _l_MEAN, "files": sorted(ch)}]
        got, _ = planscope.problems([it], rows, ch, permits=("tests/test_b.py",))
        self.assertTrue(any("_h" in p and "消えていない" in p for p in got), got)
        self.assertEqual(planscope.problems([it], rows, ch, permits=("tests/test_b.py",), ruled=("tests/test_b.py",))[0], [])

    def test_same_kind_other_file_still_rejected_until_ruled(self):
        """種類の同じ別のファイルの同名の定義は拒み、ほかの許し（permits）でも拒み、直す裁定のパス（ruled）なら別の物と裁いた物として通す"""
        it = _l_item(allowed_paths=["*.py"], files=[_l_frow("stats.py", _l_add("median"))])
        ch = {"stats.py": ("", "def median(xs):\n    pass\n"), "util.py": ("", "def median(xs):\n    pass\n")}
        rows = [{"unit_key": _l_MEAN, "files": ["stats.py", "util.py"]}]
        self.assertTrue(any("util.py" in p and "足す行の path" in p for p in planscope.problems([it], rows, ch)[0]))
        self.assertTrue(any("util.py" in p and "足す行の path" in p
                            for p in planscope.problems([it], rows, ch, permits=("util.py",))[0]))
        self.assertEqual(planscope.problems([it], rows, ch, ruled=("util.py",))[0], [])

    def test_unrelated_local_helper_with_removed_name(self):
        """消す名と同じ字の局所の助け手を別のファイルに足した: 種類の同じファイルは拒み、裁定が許せば通す。種類の違う文書の
        字下げのコード例は残りに数えない。行の path に残る名は許しがあっても拒む"""
        it = _l_item(allowed_paths=["*.py", "docs/**"], files=[_l_frow("stats.py", _l_rm("_entry"))])
        gone = ("def _entry():\n    pass\n", "def mean():\n    pass\n")
        ch = {"stats.py": gone, "report.py": (None, "def _entry(row):\n    return row\n")}
        rows = [{"unit_key": _l_MEAN, "files": sorted(ch)}]
        self.assertTrue(any("_entry" in p for p in planscope.problems([it], rows, ch)[0]))
        self.assertEqual(planscope.problems([it], rows, ch, ruled=("report.py",))[0], [])
        doc = {"stats.py": gone, "docs/howto.md": (None, "例:\n\n    def _entry():\n        pass\n")}
        self.assertEqual(planscope.problems([it], [{"unit_key": _l_MEAN, "files": sorted(doc)}], doc)[0], [])
        kept = {"stats.py": ("def _entry():\n    pass\n", "def _entry():\n    return 1\n")}
        self.assertTrue(any("_entry" in p for p in planscope.problems([it], [_l_ROW], kept, ruled=("stats.py",))[0]))


class RejectHeadCase(_LSrc):
    """拒否の行の頭（reject_head）: 範囲の相談がその段に在れば、範囲の外が要る時の先の道を相談と言い、申し出は聞けない・
    許されない・out_of_scope の時の道に下げる（run 249・249b は相談の控えが在ったのに、拒否の文が申し出の道だけを言った）"""

    def test_without_ask_keeps_conflict_route(self):
        self.assertEqual(planscope.reject_head(False), planscope.REJECT)

    def test_with_ask_puts_planner_first(self):
        head = planscope.reject_head(True)
        self.assertIn("範囲の相談", head)
        self.assertLess(head.index("範囲の相談"), head.index("食い違いの申し出"))
        self.assertIn("out_of_scope", head)
        self.assertNotIn("範囲の外が要るなら変えずに食い違いの申し出で返せ", head)
        self.assertNotIn("out_of_scope に当たる物が要る時だけ", head,
                         "out_of_scope の物も先に相談する（持ち主 2026-10-07。案を書いた役が考え直す）")
        self.assertTrue(head.startswith("承認済みの修正案の項目から外れた"), "拒否の行を単位に結ぶ・見出しで探す頭の語は同じ")



# ---- lib/tests/test_fix_units.py の写し
_l_KEY = "stats.py clamp: 上限を超えた値に lo を返す"
_l_HOW = {"patterns": ["return lo"], "paths": ["stats.py"], "count": "lines", "fixed": True}


def _l_blank(s, n):
    return len((s or "").strip()) < n


def _l_change(sites=1, remaining=None, how=None):
    c = {"unit_key": _l_KEY, "files": ["stats.py"], "what": "直した",
         "closure": {"mechanism": "m", "fix_mechanism": "f", "verified_how": "v",
                     "sites": [{"site": f"s{i}", "red_seen": i == sites - 1} for i in range(sites)]}}
    if remaining or how:
        c["coverage"] = {**({"remaining": remaining} if remaining else {}), **({"how": how} if how else {})}
    return c


class BuildCase(_LSrc):
    def build(self, c, *, total, after, counts="defects", judged_total=None, replaced=None):
        seen = []

        def count(how, at_rev):
            seen.append((how, at_rev))
            return (total if at_rev else after), ""
        jq = {"how": _l_HOW, "counts": counts, **({"total": judged_total} if judged_total is not None else {})}
        out, rows = unitrows.build([c], {_l_KEY: jq}, count=count, blank=_l_blank, replaced=replaced)
        return out[0], rows[0], seen

    def test_honest_closed_reply_is_passed_as_is(self):
        c = _l_change(sites=2)
        got, row, _ = self.build(c, total=2, after=0)
        self.assertEqual((row["closed"], row["discrepancies"]), (True, []))
        self.assertEqual(got["closure"], c["closure"])
        self.assertNotIn("remaining", got["coverage"])
        self.assertEqual(got["coverage"]["how"], _l_HOW, "写しと同じ問い（判定者の how）で数えたことを返答に残す")

    def test_defects_left_after_claimed_all_is_recorded_not_rejected(self):
        got, row, _ = self.build(_l_change(sites=2), total=2, after=1)
        self.assertIs(row["closed"], False)
        self.assertTrue(any("修正後も 1 件" in d for d in row["discrepancies"]), row)
        self.assertTrue(got["coverage"]["remaining"].startswith(unitrows.MACHINE_REMAINING),
                        "写しの defects の拒否が発火しないように、機械の記録を remaining に書く")

    def test_sites_over_population_are_cut_keeping_red(self):
        got, row, _ = self.build(_l_change(sites=3), total=1, after=0)
        self.assertTrue(any("超える" in d for d in row["discrepancies"]), row)
        self.assertEqual(len(got["closure"]["sites"]), 1)
        self.assertTrue(got["closure"]["sites"][0]["red_seen"], "赤を見た site を先に残す（写しの fix_closure の柵）")
        self.assertEqual(row["claimed"], 3, "表には申告の元の件数を残す")

    def test_missing_remaining_is_recorded(self):
        got, row, _ = self.build(_l_change(sites=1), total=3, after=2, counts="population")
        self.assertIs(row["closed"], False)
        self.assertTrue(any("remaining が無い" in d for d in row["discrepancies"]), row)
        self.assertIn("remaining", got["coverage"])

    def test_fixer_remaining_is_no_discrepancy(self):
        got, row, _ = self.build(_l_change(sites=1, remaining="残りの 2 か所は次の周で塞ぐ（別の単位の直しを待つ）"),
                                 total=3, after=2, counts="population")
        self.assertEqual(row["discrepancies"], [])
        self.assertEqual(got["coverage"]["remaining"], "残りの 2 か所は次の周で塞ぐ（別の単位の直しを待つ）")

    def test_replaced_query_counts_and_names_the_ruling(self):
        new = {**_l_HOW, "patterns": ["return lo  # hi"]}
        got, row, seen = self.build(_l_change(sites=1), total=1, after=0, judged_total=2,
                                    replaced={_l_KEY: {"id": "c1-1", "how": new, "counts": "defects", "hits": ["x"], "misses": []}})
        self.assertEqual({h["patterns"][0] for h, _ in seen}, {"return lo  # hi"}, "置き換えた問いで数える")
        self.assertEqual((row["how_from"], row["closed"], row["discrepancies"]), ("裁定 c1-1", True, []))
        self.assertEqual(got["coverage"]["how"], new)
        self.assertIn("c1-1", got["coverage"]["remaining"], "判定者の母数より狭い問いの理由は裁定")

    def test_replaced_query_counts_direction_comes_from_the_ruling(self):
        # 判定者は population、裁定は defects: 向きは裁定の counts。修正後も数えれば site が母数に届いても閉じていない
        got, row, _ = self.build(_l_change(sites=1), total=1, after=1, counts="population",
                                 replaced={_l_KEY: {"id": "c1-1", "how": _l_HOW, "counts": "defects", "hits": ["x"], "misses": []}})
        self.assertEqual((row["counts"], row["closed"]), ("defects", False), row)
        self.assertTrue(any("修正後も 1 件" in d for d in row["discrepancies"]), row)

    def test_closed_is_decided_by_the_judge_query_not_the_fixer_how(self):
        narrow = {**_l_HOW, "patterns": ["return lo  # none"]}

        def count(how, at_rev):
            if how == narrow:
                return (0, "") if not at_rev else (0, "")
            return (2, "") if at_rev else (1, "")
        c = _l_change(sites=0, remaining="判定者の問いは広すぎるので狭めた（下限の枝も数える）", how=narrow)
        out, rows = unitrows.build([c], {_l_KEY: {"how": _l_HOW, "counts": "defects", "total": 2}}, count=count, blank=_l_blank)
        self.assertEqual(rows[0]["how_from"], "修正役")
        self.assertIs(rows[0]["closed"], False, "修正役が狭めた問いで 0 件でも、判定者の問いで残れば閉じていない")
        self.assertEqual((rows[0]["total"], rows[0]["after"]), (2, 1))
        self.assertEqual(out[0]["coverage"]["how"], narrow, "写しには修正役の how を渡す（写しは作り直しとして採る）")

    def test_uncountable_judge_query_does_not_close_on_the_fixer_how(self):
        narrow = {**_l_HOW, "patterns": ["return lo  # none"]}

        def count(how, at_rev):
            if how == narrow:
                return 0, ""
            return (2, "") if at_rev else (None, "git grep が stderr に書いた")
        c = _l_change(sites=0, remaining="判定者の問いは広すぎるので狭めた（下限の枝も数える）", how=narrow)
        _, rows = unitrows.build([c], {_l_KEY: {"how": _l_HOW, "counts": "defects", "total": 2}}, count=count, blank=_l_blank)
        self.assertIsNone(rows[0]["closed"], "判定者の問いが数えられない時に、修正役が狭めた問いの 0 件で閉じたとしない")
        self.assertTrue(any("git grep が stderr に書いた" in d for d in rows[0]["discrepancies"]), rows[0])
        self.assertEqual(unitrows.unclosed_defects(rows), rows)

    def test_uncountable_row_is_left_to_the_copy(self):
        c = _l_change()
        out, rows = unitrows.build([c], {_l_KEY: {"how": _l_HOW, "counts": "defects"}}, count=lambda h, r: (None, "走らない"),
                                   blank=_l_blank)
        self.assertEqual((out, rows), ([c], []))


class SitePathCase(_LSrc):
    """site の path（works だけの任意の欄）で申告を問いの当たりにファイル単位で結び、単位の違う数（site の件数と行数）を直に比べない"""

    def build(self, sites, *, total, after, files, counts="defects", remaining=None, touched=("stats.py", "a.py")):
        """touched は修正が変えたファイル（site の path が指す当たりのファイルも、変わっていなければ覆いに数えない。SiteNeedsChangeCase）"""
        import inspect
        if "per_file" not in inspect.signature(unitrows.build).parameters:
            self.fail("unitrows.build がファイルごとの数（per_file）を受けない: site の件数を行数の母数と直に比べるしかない")
        c = {"unit_key": _l_KEY, "files": ["stats.py"], "what": "直した",
             "closure": {"mechanism": "m", "fix_mechanism": "f", "verified_how": "v", "sites": sites}}
        if remaining:
            c["coverage"] = {"remaining": remaining}

        def count(how, at_rev):
            return (total if at_rev else after), ""

        def per_file(how, at_rev):
            return (files if at_rev else {}), ""
        out, rows = unitrows.build([c], {_l_KEY: {"how": _l_HOW, "counts": counts}}, count=count, blank=_l_blank,
                                   per_file=per_file, touched=list(touched))
        return out[0], rows[0]

    def test_sites_outside_the_query_are_listed_not_counted_as_mismatch(self):
        sites = [{"site": "上限の枝", "red_seen": True, "path": "stats.py"},
                 {"site": "下限の枝", "red_seen": False, "path": "./stats.py"},
                 {"site": "試験", "red_seen": False, "path": "tests/test_stats.py"},
                 {"site": "文書", "red_seen": False, "path": "README.md"}]
        got, row = self.build(sites, total=2, after=0, files={"stats.py": 2})
        self.assertEqual(row["discrepancies"], [], "試験・文書の site と同じファイルの 2 件目は『超える』に数えない")
        self.assertEqual(row["covered"], 2)
        self.assertEqual(sorted(row["out_of_query"]), ["README.md", "tests/test_stats.py"],
                         "問いの外に並べた site のパスは見えるまま表に残す")
        self.assertIs(row["closed"], True)
        self.assertEqual(row["claimed"], 4)
        self.assertFalse(any("path" in s for s in got["closure"]["sites"]), "写しの sites は additionalProperties: false")

    def test_sites_piled_on_one_file_do_not_cover_other_files(self):
        sites = [{"site": f"s{i}", "red_seen": i == 0, "path": "a.py"} for i in range(3)]
        _, row = self.build(sites, total=3, after=1, files={"a.py": 2, "b.py": 1}, counts="population",
                              remaining="b.py の 1 件は並行の線の担当")
        self.assertEqual(row["covered"], 2, "同じファイルの site はそのファイルの件数を 1 回だけ足す")
        self.assertEqual(row["discrepancies"], [], row)
        self.assertIs(row["closed"], False, "population の closed は覆った当たりの件数で決める（同じファイルの site は増えない）")

    def test_sites_without_path_are_not_counted_with_a_reason(self):
        """path の無い site は覆いに数えず、ほかの site はファイルごとの数で結ぶ（申告の件数で『超える』と比べない）"""
        sites = [{"site": "上限の枝", "red_seen": True, "path": "stats.py"}, {"site": "試験", "red_seen": False}]
        _, row = self.build(sites, total=1, after=0, files={"stats.py": 1})
        self.assertTrue(row["discrepancies"][0].startswith("path が無い site 1 件"), row)
        self.assertEqual((row["covered"], row["bound"], row["closed"], len(row["discrepancies"])), (1, True, True, 1), row)

    def test_per_file_sum_not_matching_the_total_is_not_used_silently(self):
        sites = [{"site": "上限の枝", "red_seen": True, "path": "stats.py"}, {"site": "試験", "red_seen": False,
                                                                          "path": "tests/test_stats.py"}]
        _, row = self.build(sites, total=1, after=0, files={"stats.py": 3})
        self.assertTrue(any("ファイルごとの数が合計と合わない" in d for d in row["discrepancies"]), row)
        self.assertTrue(any("超える" in d for d in row["discrepancies"]), "今の数え方（len(sites)）で比べる")

    def test_shaping_leaves_the_callers_rows_as_written(self):
        """写しに渡す形に揃える（path を外す・coverage.how と remaining を書く・sites を切る）のは写しの上で、渡した行は変えない
        （受け付けは揃える前の行を 1 回目の返答の控えに残し、2 回目の修正の段がそれを数え直しに当て直す。依頼 195i の 1）"""
        sites = [{"site": f"s{i}", "red_seen": i == 0, "path": "stats.py"} for i in range(3)]
        c = {"unit_key": _l_KEY, "files": ["stats.py"], "what": "直した",
             "closure": {"mechanism": "m", "fix_mechanism": "f", "verified_how": "v", "sites": sites},
             "coverage": {"counts": "defects"}}
        before = json.loads(json.dumps(c))
        out, rows = unitrows.build([c], {_l_KEY: {"how": _l_HOW, "counts": "defects"}}, count=lambda h, r: (1, ""), blank=_l_blank,
                                   per_file=lambda h, r: ({"stats.py": 1} if r else {}, ""))
        self.assertEqual(c, before, "揃えは写しの上で（渡した行を変えない）")
        self.assertNotEqual(out[0], before)
        self.assertIs(rows[0]["bound"], True)
        again, rows2 = unitrows.build([c], {_l_KEY: {"how": _l_HOW, "counts": "defects"}}, count=lambda h, r: (1, ""), blank=_l_blank,
                                      per_file=lambda h, r: ({"stats.py": 1} if r else {}, ""))
        self.assertEqual((again, rows2), (out, rows), "書いた形の行に当て直せば 1 回目と同じ表（2 回目の段の数え直し）")
        _, shaped_rows = unitrows.build(out, {_l_KEY: {"how": _l_HOW, "counts": "defects"}}, count=lambda h, r: (1, ""),
                                        blank=_l_blank, per_file=lambda h, r: ({"stats.py": 1} if r else {}, ""))
        self.assertIs(shaped_rows[0]["bound"], False, "揃えた後の行（path が無い）では結べない（だから控えは書いた形で残す）")

    def test_uncountable_row_still_drops_path_before_the_copy(self):
        c = {"unit_key": _l_KEY, "files": ["stats.py"], "what": "直した",
             "closure": {"mechanism": "m", "fix_mechanism": "f", "verified_how": "v",
                         "sites": [{"site": "s", "red_seen": True, "path": "stats.py"}]}}
        out, rows = unitrows.build([c], {_l_KEY: {"how": _l_HOW, "counts": "defects"}}, count=lambda h, r: (None, "走らない"),
                                   blank=_l_blank)
        self.assertEqual(rows, [])
        self.assertEqual(out[0]["closure"]["sites"], [{"site": "s", "red_seen": True}], "写しに任せる行も path を外す")


class ChangedFilesCoverCase(_LSrc):
    """population の問いの当たりのファイルは、site の path が名指さなくても、その単位の files に在って修正前の版から実際に
    変わったファイル（touched）なら覆ったと数える。canary の run a2097fd6（2026-10-07）の盤面の形: 判定の問いは mean の定義・
    TestCalc のクラス・CHANGELOG の [Unreleased] の 3 行（3 ファイルに 1 行ずつ）で、修正役は 3 ファイルを全部直して files に
    並べたのに、site はコードの 1 か所（path calc.py）だけを書いた。表は covered 1・closed false になり、検証器の『未解消』が
    報告に残って round_limit になった（差分は 2 単位とも正しく直し、最後のテストは緑）"""
    MEAN = "calc.py:mean — 分母が個数でなく個数-1で docstring の算術平均に反する"
    HOW3 = {"patterns": ["def mean(", "class TestCalc(", "## [Unreleased]"],
            "paths": ["calc.py", "test_lib.py", "CHANGELOG.md"], "count": "lines", "fixed": True}
    HITS = {"calc.py": 1, "test_lib.py": 1, "CHANGELOG.md": 1}

    def build(self, touched, files=("calc.py", "test_lib.py", "CHANGELOG.md")):
        import inspect
        if "touched" not in inspect.signature(unitrows.build).parameters:
            self.fail("unitrows.build が修正の変えたファイル（touched）を受けない: site の path だけで覆いを数え、"
                      "直して files に並べた当たりのファイルを覆っていないと数える")
        c = {"unit_key": self.MEAN, "files": list(files), "what": "直した",
             "closure": {"mechanism": "m", "fix_mechanism": "f", "verified_how": "v",
                         "sites": [{"site": "calc.py:8 mean の分母", "red_seen": True, "path": "calc.py"}]}}
        out, rows = unitrows.build([c], {self.MEAN: {"how": self.HOW3, "counts": "population", "total": 3}},
                                   count=lambda h, at_rev: (3, ""), blank=_l_blank,
                                   per_file=lambda h, at_rev: (dict(self.HITS), ""), touched=touched)
        return out[0], rows[0]

    def test_board_shape_of_run_a2097fd6_is_closed(self):
        got, row = self.build(["CHANGELOG.md", "calc.py", "test_lib.py", "textfmt.py"])
        self.assertEqual((row["covered"], row["closed"], row["discrepancies"]), (3, True, []), row)
        self.assertEqual(row["claimed"], 1, "表には申告の site の件数を残す")
        self.assertEqual(row["changed_cover"], ["CHANGELOG.md", "test_lib.py"],
                         "site が名指さず、単位の files と修正の変更で覆った当たりのファイルを表に残す")
        self.assertGreaterEqual(len(got["coverage"].get("remaining") or ""), unitrows.MIN_REMAINING,
                                "写しは site の件数（1 < 母数 3）で拒むので、機械が remaining を書いて渡す")

    def test_hit_file_not_changed_stays_open(self):
        _, row = self.build(["calc.py", "test_lib.py"])
        self.assertEqual((row["covered"], row["closed"]), (2, False), row)
        self.assertTrue(any("remaining が無い" in d for d in row["discrepancies"]), row)

    def test_changed_file_not_in_the_units_files_does_not_cover(self):
        _, row = self.build(["CHANGELOG.md", "calc.py", "test_lib.py"], files=("calc.py", "test_lib.py"))
        self.assertEqual((row["covered"], row["closed"]), (2, False), "別の単位の直しで変わったファイルを、この単位の覆いに数えない")

    def test_without_touched_nothing_covers(self):
        """変更が読めなければ site の path が指す calc.py も変わったと確かめられないので覆わない（前は site の path だけで 1 件を
        覆った。path だけで覆うと、名指して変えなかったファイルも閉じる。SiteNeedsChangeCase）"""
        _, row = self.build(None)
        self.assertEqual((row["covered"], row["closed"], row["changed_cover"]), (0, False, []), row)
        self.assertEqual(row["discrepancies"][0], unitrows.UNKNOWN_CHANGES, row)


class PopulationMembersCase(_LSrc):
    """population の当たりは修正が変える物の全部（直す対象の母集団）で、閉じたかは当たりを全部覆ったかで決める。canary の
    large の 2 つの run の盤面の形（2026-10-07）: 『公開の関数に docstring が無い』単位で、b44c480f の判定は欠けた 2 つの def を
    名指す問い（当たり 2）にして、修正役が 2 つのファイルに docstring を足して閉じた。a2fcf33a の判定は決まりがかかる範囲の全部
    （5 つのモジュールの公開関数 14 本。うち 12 本はもう docstring を持つ）を数え、同じ正しい直しが覆うのは 4 件で閉じず、
    検証器の『未解消』で round_limit になった。もう正しい物は修正が変えないので、機械は『直さなくてよい物』と『直し漏らした物』を
    分けられない——閉鎖の決まりは緩めず、広すぎる問いは判定の問いの書き方（diagnose.md 6 項）と、修正役の申し出 query
    （裁定 replace_query が問いを置き換える）で直す"""
    KEY = "money.py:split_even・slugs.py:slugify — 公開の関数に約束の docstring が無く help() に約束が出ない"
    RULE = {"patterns": ["^def [a-z]"], "paths": ["stats.py", "textfmt.py", "units.py", "money.py", "slugs.py"], "count": "lines"}
    RULE_HITS = {"stats.py": 4, "textfmt.py": 3, "units.py": 3, "money.py": 2, "slugs.py": 2}
    MEMBERS = {"patterns": ["def split_even(", "def slugify("], "paths": ["money.py", "slugs.py"], "count": "lines", "fixed": True}
    MEMBER_HITS = {"money.py": 1, "slugs.py": 1}

    def build(self, judged_how, *, touched=("money.py", "slugs.py"), remaining=None, replaced=None):
        hits = {json.dumps(self.RULE): self.RULE_HITS, json.dumps(self.MEMBERS): self.MEMBER_HITS}
        # 修正役は変えたファイルだけを files と site に書く（直し漏らした物は名指さない）
        names = {"money.py": "money.py:split_even", "slugs.py": "slugs.py:slugify"}
        c = {"unit_key": self.KEY, "files": list(touched), "what": "docstring を足した",
             "closure": {"mechanism": "m", "fix_mechanism": "f", "verified_how": "v",
                         "sites": [{"site": names[p], "red_seen": False, "path": p} for p in touched]}}
        if remaining:
            c["coverage"] = {"remaining": remaining}
        total = sum(hits[json.dumps(judged_how)].values())
        out, rows = unitrows.build([c], {self.KEY: {"how": judged_how, "counts": "population", "total": total}},
                                   count=lambda h, at_rev: (sum(hits[json.dumps(h)].values()), ""), blank=_l_blank,
                                   per_file=lambda h, at_rev: (dict(hits[json.dumps(h)]), ""), touched=list(touched),
                                   replaced=replaced)
        return out[0], rows[0]

    def test_members_query_closes_the_correct_fix(self):
        """b44c480f の形: 問いは欠けた物だけを名指し（当たり 2）、正しい直しは 2 つとも覆って閉じる"""
        _, row = self.build(self.MEMBERS)
        self.assertEqual((row["total"], row["after"], row["covered"], row["closed"], row["discrepancies"]),
                         (2, 2, 2, True, []), row)

    def test_members_query_stays_open_when_the_fix_misses_a_member(self):
        """直し漏らした物（slugs.py を変えず、名指してもいない）は閉じない（閉鎖の決まりを緩めていない）"""
        _, row = self.build(self.MEMBERS, touched=("money.py",))
        self.assertEqual((row["covered"], row["closed"]), (1, False), row)

    def test_rule_domain_query_stays_open_even_with_remaining(self):
        """a2fcf33a の形: 問いがもう正しい 12 本も数えると、正しい直しも 4 件しか覆わず閉じない。remaining は黙って残さない
        ための記録で、閉じる理由にはならない（『直さなくてよい』と書くだけで閉じるなら、直し漏らしも同じ文で閉じる）"""
        for remaining in (None, "残りの 12 本はもう docstring を持つので直さない"):
            with self.subTest(remaining=remaining):
                _, row = self.build(self.RULE, remaining=remaining)
                self.assertEqual((row["total"], row["after"], row["covered"], row["closed"]), (14, 14, 4, False), row)
                self.assertEqual(any("remaining が無い" in d for d in row["discrepancies"]), remaining is None, row)

    def test_rule_domain_query_replaced_by_a_ruling_closes(self):
        """同じ形で修正役が query の申し出を出し、裁定 replace_query が欠けた物だけを名指す問いに置き換えれば、正しい直しは閉じ、
        直し漏らしは閉じない"""
        ruled = {self.KEY: {"id": "c1-1", "how": self.MEMBERS, "counts": "population",
                            "hits": ["def split_even(total, n):"], "misses": ["def format_yen(amount):"]}}
        got, row = self.build(self.RULE, replaced=ruled)
        self.assertEqual((row["how_from"], row["total"], row["covered"], row["closed"], row["discrepancies"]),
                         ("裁定 c1-1", 2, 2, True, []), row)
        self.assertIn("c1-1", got["coverage"]["remaining"], "判定者の母数より狭い理由は裁定（機械が書く）")
        _, row = self.build(self.RULE, replaced=ruled, touched=("money.py",))
        self.assertEqual((row["covered"], row["closed"]), (1, False), row)



class SiteNeedsChangeCase(_LSrc):
    """site の path が名指す当たりのファイルも、修正前の版から実際に変わったファイル（touched）でなければ覆ったと数えない
    （問いの種類に依らない）。審査の再現: population の問いの当たりが 5 ファイルに 14 行で、修正役が 5 ファイルを全部 site に
    並べて 2 ファイルだけを変えると、site の path だけで 14 件を覆ったと数えて単位が閉じた（直し漏らしが閉じたと報告される）"""
    KEY = PopulationMembersCase.KEY
    RULE, RULE_HITS = PopulationMembersCase.RULE, PopulationMembersCase.RULE_HITS
    DEF_HOW = {"patterns": ["return lo"], "paths": ["a.py", "b.py"], "count": "lines", "fixed": True}
    DEF_HITS = {"a.py": 2, "b.py": 1}

    def build(self, how, hits, *, counts, sites, files, touched, after, remaining=None):
        c = {"unit_key": self.KEY, "files": list(files), "what": "直した",
             "closure": {"mechanism": "m", "fix_mechanism": "f", "verified_how": "v",
                         "sites": [{"site": f"{p}:1", "red_seen": False, "path": p} for p in sites]}}
        if remaining:
            c["coverage"] = {"remaining": remaining}
        total = sum(hits.values())
        out, rows = unitrows.build([c], {self.KEY: {"how": how, "counts": counts, "total": total}},
                                   count=lambda h, at_rev: ((total if at_rev else after), ""), blank=_l_blank,
                                   per_file=lambda h, at_rev: (dict(hits), ""), touched=touched)
        return out[0], rows[0]

    def test_reviewer_reproduction_stays_open(self):
        """5 ファイルを site に並べ、2 ファイルだけを変えた直しは閉じない（files に 5 つ並べても、2 つだけ並べても）"""
        five = sorted(self.RULE_HITS)
        for files in (("money.py", "slugs.py"), five):
            with self.subTest(files=files):
                _, row = self.build(self.RULE, self.RULE_HITS, counts="population", sites=five, files=files,
                                    touched=["money.py", "slugs.py"], after=14)
                self.assertEqual((row["total"], row["covered"], row["closed"]), (14, 4, False), row)
                self.assertEqual(row["unchanged_sites"], ["stats.py", "textfmt.py", "units.py"],
                                 "site が名指したが修正で変わっていない当たりのファイルを表に残す")
                self.assertTrue(any("remaining が無い" in d for d in row["discrepancies"]), row)

    def test_population_fix_changing_every_named_file_closes(self):
        five = sorted(self.RULE_HITS)
        _, row = self.build(self.RULE, self.RULE_HITS, counts="population", sites=five, files=five, touched=five, after=14)
        self.assertEqual((row["covered"], row["closed"], row["discrepancies"], row["unchanged_sites"]),
                         (14, True, [], []), row)

    def test_defects_fix_closes_when_the_hits_drop_to_zero(self):
        _, row = self.build(self.DEF_HOW, self.DEF_HITS, counts="defects", sites=["a.py", "b.py"], files=["a.py", "b.py"],
                            touched=["a.py", "b.py"], after=0)
        self.assertEqual((row["covered"], row["closed"], row["discrepancies"], row["unchanged_sites"]),
                         (3, True, [], []), row)

    def test_defects_site_on_an_unchanged_file_does_not_cover(self):
        """defects の closed は修正後の数で決まる（変わっていないファイルの当たりは減らない）。覆いの数も変わった物だけにする"""
        _, row = self.build(self.DEF_HOW, self.DEF_HITS, counts="defects", sites=["a.py", "b.py"], files=["a.py", "b.py"],
                            touched=["a.py"], after=1)
        self.assertEqual((row["covered"], row["closed"], row["unchanged_sites"]), (2, False, ["b.py"]), row)
        self.assertFalse(any("全部塞いだと申告" in d for d in row["discrepancies"]),
                         "変わっていないファイルを名指した site は塞いだ申告に数えない")

    def test_without_touched_sites_do_not_cover(self):
        """修正の変えたファイルが読めない時は、site の path が指すファイルも変わったと確かめられないので覆いに数えず、理由を残す"""
        five = sorted(self.RULE_HITS)
        _, row = self.build(self.RULE, self.RULE_HITS, counts="population", sites=five, files=five, touched=None, after=14)
        self.assertEqual((row["covered"], row["closed"], row["changed_cover"]), (0, False, []), row)
        self.assertEqual(row["discrepancies"], [unitrows.UNKNOWN_CHANGES],
                         "覆いを数えなかった理由だけを書き、覆いから出る食い違い（remaining が無い）を重ねない")

    def test_shortfall_reads_as_covered_by_the_fix(self):
        """食い違いの文は覆いの新しい意味（修正で変わった当たり）で書く（site は 14 件全部を名指している）"""
        five = sorted(self.RULE_HITS)
        _, row = self.build(self.RULE, self.RULE_HITS, counts="population", sites=five, files=five,
                            touched=["money.py", "slugs.py"], after=14)
        self.assertIn("母数 14 のうち修正で覆った当たりは 4 件で、remaining が無い", row["discrepancies"], row)

    def test_judged_query_that_cannot_be_bound_is_named(self):
        """修正役が問いを作り直した単位は判定者の問いで結び直す。そこで結べない（site の件数で数えた）理由も表に出す
        （捨てると、site を名指しただけで変えていない単位が黙って閉じる）"""
        mine = {**self.RULE, "paths": ["money.py", "slugs.py", "units.py"]}
        c = {"unit_key": self.KEY, "files": ["units.py"], "what": "直した",
             "coverage": {"how": mine, "remaining": "money.py と slugs.py は並行の線の担当で、今の周では塞がない"},
             "closure": {"mechanism": "m", "fix_mechanism": "f", "verified_how": "v",
                         "sites": [{"site": f"{p}:1", "red_seen": False, "path": p} for p in ("money.py", "slugs.py", "units.py")]}}
        mine_hits = {"money.py": 2, "slugs.py": 2, "units.py": 3}

        def per_file(h, at_rev):
            return (dict(mine_hits), "") if h == mine else (None, "走らない")
        _, rows = unitrows.build([c], {self.KEY: {"how": self.RULE, "counts": "population", "total": 14}},
                                 count=lambda h, at_rev: ((7, "") if h == mine else (14, "")), blank=_l_blank,
                                 per_file=per_file, touched=[])
        row = rows[0]
        self.assertTrue(any(d.startswith("判定者の問いで") and "走らない" in d for d in row["discrepancies"]), row)


class UnboundSitesNeedChangeCase(_LSrc):
    """site を問いの当たりのファイルに結べない時（path の無い site・ファイルごとに数えられない・ファイルごとの数が合計と合わない）も、
    覆いは site の件数のまま数えず、修正前の版から実際に変わったファイル（touched）を path が指す site だけを数える（0.2.40 の
    「site の path が名指すファイルも変わった物だけを覆いに数える」と同じ 1 本の規則。修正役の指示書もそう言う）。前は結べない時に
    len(sites) で数え、population の当たり 5 ファイルを site に並べて 2 ファイルだけ変えた直しが、ファイルごとの数が引けないだけで
    閉じた（食い違いの行は出るが closed は真で、報告は直ったと数えた）。結べない理由は今どおり食い違いの頭に残す"""
    KEY = PopulationMembersCase.KEY
    HOW = {"patterns": ["TODO"], "paths": ["."], "count": "files", "fixed": True}
    FIVE = ["a.py", "b.py", "c.py", "d.py", "e.py"]

    def build(self, sites, *, touched, per_file=lambda h, at_rev: (None, "時間切れ"), remaining=None):
        c = {"unit_key": self.KEY, "files": list(self.FIVE), "what": "直した",
             "closure": {"mechanism": "m", "fix_mechanism": "f", "verified_how": "v", "sites": sites}}
        if remaining:
            c["coverage"] = {"remaining": remaining}
        out, rows = unitrows.build([c], {self.KEY: {"how": self.HOW, "counts": "population", "total": 5}},
                                   count=lambda h, at_rev: (5, ""), blank=_l_blank, per_file=per_file, touched=touched)
        return out[0], rows[0]

    def sites(self, paths):
        return [{"site": f"s{i}", "red_seen": i == 0, **({"path": p} if p else {})} for i, p in enumerate(paths)]

    def test_uncountable_per_file_counts_only_sites_on_changed_files(self):
        _, row = self.build(self.sites(self.FIVE), touched=["a.py", "b.py"])
        self.assertEqual((row["covered"], row["closed"], row["bound"]), (2, False, False), row)
        self.assertTrue(row["discrepancies"][0].startswith("ファイルごとに数えられない"), row)
        self.assertTrue(any("remaining が無い" in d for d in row["discrepancies"]), row)

    def test_uncountable_per_file_closes_when_every_named_file_changed(self):
        _, row = self.build(self.sites(self.FIVE), touched=self.FIVE)
        self.assertEqual((row["covered"], row["closed"], len(row["discrepancies"])), (5, True, 1), row)

    def test_sum_mismatch_counts_only_sites_on_changed_files(self):
        _, row = self.build(self.sites(self.FIVE), touched=["a.py"], per_file=lambda h, at_rev: ({"a.py": 1}, ""),
                            remaining="残りの 4 ファイルは別の線が直す")
        self.assertEqual((row["covered"], row["closed"]), (1, False), row)
        self.assertTrue(row["discrepancies"][0].startswith("ファイルごとの数が合計と合わない"), row)

    def test_site_without_path_does_not_cover(self):
        """path の無い site はどのファイルが変わったかを指さないので覆いに数えない（申告だけで閉じたと言わない）。ファイルごとの数が
        引ければ、path の在る site と単位の files で、結べた時と同じ規則で数える（e.py は site が名指さないが単位の files に在り
        変わった）"""
        per_file = lambda h, at_rev: ({p: 1 for p in self.FIVE}, "")   # noqa: E731
        _, row = self.build(self.sites(["a.py", "b.py", "c.py", "d.py", None]), touched=self.FIVE, per_file=per_file)
        self.assertEqual((row["covered"], row["closed"], row["changed_cover"]), (5, True, ["e.py"]), row)
        self.assertTrue(row["discrepancies"][0].startswith("path が無い site 1 件"), row)
        _, row = self.build(self.sites(["a.py", "b.py", "c.py", "d.py", None]), touched=["a.py", "b.py", "c.py", "d.py"],
                            per_file=per_file)
        self.assertEqual((row["covered"], row["closed"]), (4, False), row)

    def test_pathless_site_does_not_switch_to_a_looser_count(self):
        """審査の再現: 結べば閉じない申告に path の無い site を 1 件足しても閉じない（当たりの外の site・同じファイルの site の
        重なりを、結べない時の数え方で覆いに足さない）"""
        per_file = lambda h, at_rev: ({p: 1 for p in self.FIVE}, "")   # noqa: E731
        tests = ["tests/t1.py", "tests/t2.py", "tests/t3.py"]
        _, row = self.build(self.sites(["a.py", "b.py", *tests, None]), touched=["a.py", "b.py", *tests], per_file=per_file)
        self.assertEqual((row["covered"], row["closed"], row["out_of_query"]), (2, False, tests), row)
        _, row = self.build(self.sites(["a.py"] * 5 + [None]), touched=["a.py"], per_file=per_file)
        self.assertEqual((row["covered"], row["closed"]), (1, False), row)

    def test_uncountable_per_file_counts_a_file_once_for_files_queries(self):
        """ファイルごとの数が引けない時、count が files の問いは同じファイルを指す site を 1 件に数える（当たりは 1 ファイル 1 件）"""
        _, row = self.build(self.sites(["a.py"] * 5), touched=["a.py"])
        self.assertEqual((row["covered"], row["closed"]), (1, False), row)

    def test_unbound_without_touched_covers_nothing_and_says_why(self):
        _, row = self.build(self.sites(self.FIVE), touched=None)
        self.assertEqual((row["covered"], row["closed"]), (0, False), row)
        self.assertTrue(row["discrepancies"][0].startswith("ファイルごとに数えられない"), row)
        self.assertEqual(row["discrepancies"][1:], [unitrows.UNKNOWN_CHANGES],
                         "覆いを数えなかった理由を足し、覆いから出る食い違い（remaining が無い）を重ねない")


class GroundsCase(_LSrc):
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name) / "repo"
        self.repo.mkdir()
        (self.repo / "stats.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
        self.request = pathlib.Path(tmp.name) / "request.md"
        self.request.write_text("# 依頼\n- 分母は len(xs)\n", encoding="utf-8")
        self.todo = {"c1-1": {"id": "c1-1", "unit_key": _l_KEY, "which_is_right": "unknown"}}

    WHY = {"ask_why": {"changes": "direction", "line": "分母を len(xs) と len(xs) - 1 のどちらにするかで直しの向きが変わる"}}

    def errs(self, **extra):
        reply = {"rulings": [{"id": "c1-1", "decision": "ask_human", "text": "方針の変更で人が決める", "limits": [], **self.WHY, **extra}]}
        return ruling.problems(reply, self.todo, self.repo, str(self.request), (str(self.request),))

    def test_ask_human_needs_request_line_or_search(self):
        self.assertTrue(any("request_searched" in e for e in self.errs()), "依頼の在る run の出どころの無い ask_human は拒む")
        self.assertEqual(self.errs(request_searched="依頼に分母の答えを探したが無い"), [])
        self.assertEqual(self.errs(grounds=[f"{self.request}:2"]), [])
        self.assertTrue(self.errs(grounds=["stats.py:1"]), "依頼の外の名指しだけでは、依頼を当たった証拠にならない")

    def test_grounds_are_checked_against_the_tree(self):
        self.assertTrue(any("無い" in e or "外" in e for e in self.errs(grounds=[f"{self.request}:9"])))
        self.assertTrue(self.errs(grounds=["nope.py:1"], request_searched="依頼に分母の答えを探したが無い"))

    def test_run_without_request_does_not_bind(self):
        reply = {"rulings": [{"id": "c1-1", "decision": "ask_human", "text": "方針の変更で人が決める", "limits": [], **self.WHY}]}
        self.assertEqual(ruling.problems(reply, self.todo, self.repo), [])




class GitWaitsWithoutDeadlineCase(_LSrc):
    """受け付けと修正の後始末の git・判定の問いの git grep は期限を付けずに待つ（台帳 R4: 新しい期限を足さない。止まった git は
    ほかの所と同じく待ち、run の外の止め方で止める）"""

    def test_accept_and_leftovers_git_have_no_timeout(self):
        from unittest import mock
        import subprocess
        import accept
        import leftovers
        done = subprocess.CompletedProcess([], 0, stdout=b"", stderr=b"")
        for mod, call in ((accept, lambda d: accept._git(d, "status")), (leftovers, lambda d: leftovers.git(d, "status"))):
            with self.subTest(mod.__name__), tempfile.TemporaryDirectory() as d, \
                    mock.patch.object(mod.subprocess, "run", return_value=done) as run:
                call(d)
                self.assertIsNone(run.call_args.kwargs.get("timeout"), run.call_args)

    def test_git_and_count_have_no_deadline(self):
        """engine の git・run_count（rev の確かめ・下調べ・本体の git grep）が、子のプロセスに期限を渡さず、
        止めの Timer も作らない（E12）"""
        import subprocess
        import threading
        from unittest import mock
        util = querytest._util
        runs, popens = [], []
        real_run, real_popen = subprocess.run, subprocess.Popen

        def run(*a, **k):
            runs.append(k)
            return real_run(*a, **k)

        def popen(*a, **k):
            popens.append(k)
            return real_popen(*a, **k)
        with tempfile.TemporaryDirectory() as d:
            real_run(["git", "init", "-q", d], check=True)
            (pathlib.Path(d) / "a.txt").write_text("x\n", encoding="utf-8")
            real_run(["git", "-C", d, "add", "a.txt"], check=True)
            real_run(["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c"], check=True)
            with mock.patch.object(util.subprocess, "run", side_effect=run), \
                    mock.patch.object(util.subprocess, "Popen", side_effect=popen), \
                    mock.patch.object(threading, "Timer", side_effect=AssertionError("Timer を作った")), \
                    mock.patch.object(util, "GIT_CWD", d):
                self.assertIsNotNone(util.git("status"))
                got, why = util.run_count({"patterns": ["x"], "paths": ["a.txt"], "count": "lines"}, d, rev="HEAD")
        self.assertEqual((got, why), (1, ""))
        self.assertTrue(runs and popens)
        for k in runs + popens:
            self.assertNotIn("timeout", k)
        self.assertFalse(hasattr(util, "GIT_TIMEOUT"))


# ---- lib/tests/test_fix_duty.py の写し
_l_FORK_UNIT = "stats.py mean: 空の列の扱いが決まらない"
_l_OTHER_UNIT = "stats.py clamp: 上限を超えた値に lo を返す"
_l_FORK = {"key": "q-empty-mean", "kind": "fork", "status": "held", "origin": _l_FORK_UNIT, "options": ["例外", "0 を返す"],
        "reason": "推し: 例外"}
_l_ESC_UNIT = "stats.py median: 偶数の長さの中央値が決まらない"
_l_ASKED_UNIT = "stats.py clamp: 下限と上限が逆の時の扱い"
_l_BACK_UNIT = "stats.py mode: 同数の時の選び方"
_l_ESC = {"key": "q-median", "kind": "stuck", "status": "escalate", "origin": _l_ESC_UNIT, "reason": "推し: 平均を返す"}
_l_BACK = {**_l_FORK, "key": "q-mode", "origin": _l_BACK_UNIT}
_l_ALL_UNITS = [_l_FORK_UNIT, _l_OTHER_UNIT, _l_ESC_UNIT, _l_ASKED_UNIT, _l_BACK_UNIT]
# 元の盤面の値: 写しの規則の直す義務（開いた単位から、人に諮っている fork の出どころ _l_BACK_UNIT を除く）、答えていない問い
# （fork と escalate の出どころ）、関所で人が答えた問いの出どころ
_l_OWED = {_l_FORK_UNIT, _l_OTHER_UNIT, _l_ESC_UNIT, _l_ASKED_UNIT}
_l_WITHHELD_BY = {_l_FORK_UNIT: _l_FORK, _l_ESC_UNIT: _l_ESC}
_l_RETURNED = {_l_BACK_UNIT}


def _l_put_rulings(place: pathlib.Path) -> None:
    """ASKED_UNIT に ask_human の裁定の行を置く（置き場の conflicts.json）"""
    (place / conflict.FILE).write_text(json.dumps({"items": [
        {"id": "c1-1", "unit_key": _l_ASKED_UNIT, "ruling": {"decision": conflict.ASK}}]}), encoding="utf-8")


class DutyCase(_LSrc):
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory(prefix="works-fix-duty-")
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        _l_put_rulings(self.tmp)

    def duty(self, withheld_by=None):
        return fixboard.fix_duty(self.tmp, _l_OWED, withheld_by=_l_WITHHELD_BY if withheld_by is None else withheld_by,
                                 returned=_l_RETURNED)


class TestFixDuty(DutyCase):
    def test_owed_and_excused_split_fixable_with_reasons(self):
        owed, excused = self.duty()
        self.assertEqual(owed, {_l_OTHER_UNIT, _l_BACK_UNIT}, "関所で答えて戻した単位は義務に残る")
        self.assertEqual(owed & set(excused), set())
        self.assertLessEqual(set(_l_ALL_UNITS), owed | set(excused), "開いた単位と戻した単位を覆う")
        self.assertIn(_l_FORK["key"], excused[_l_FORK_UNIT])
        self.assertIn(_l_ESC["key"], excused[_l_ESC_UNIT])
        self.assertIn("ask_human の裁定 c1-1", excused[_l_ASKED_UNIT])
        self.assertEqual(fixboard.nothing_owed_but_excused(self.tmp, _l_OWED, withheld_by=_l_WITHHELD_BY, returned=_l_RETURNED), {},
                         "義務が残る置き場は空の changes を通さない")

    def test_excused_reason_reads_withheld_by_not_a_copy(self):
        _, excused = self.duty(withheld_by={_l_FORK_UNIT: _l_ESC})
        self.assertIn(_l_ESC["key"], excused[_l_FORK_UNIT])
        self.assertNotIn(_l_ESC_UNIT, excused)

    def test_unreadable_conflicts_keep_asked_unit_owed(self):
        (self.tmp / conflict.FILE).write_text("{", encoding="utf-8")
        owed, excused = self.duty()
        self.assertIn(_l_ASKED_UNIT, owed, "控えが読めなければ ask_human を義務から外さない")
        self.assertNotIn(_l_ASKED_UNIT, excused)


class TestDeclaredBinding(_LSrc):
    def test_declared_keys_bind_without_text_matching(self):
        """declared の文は文照合を使わず declared の単位に結ぶ（別の単位の足跡のパスを名指しても）。declared に無い文は今の bind"""
        import inspect
        self.assertIn("declared", inspect.signature(parking.settle).parameters)
        A, B = "a.py f: 直す", "b.py g: 直す"
        feet = {A: {"a.py"}, B: {"b.py"}}
        base = dict(keys={A, B}, feet=feet, reached={}, owed={A, B}, out_of_duty=set(), changed=set())
        declared_text = "食い違い[0]: 名指し 'b.py:99' の行がファイルに無い"
        by_path = "b.py を直した行の拒否"
        nothing = "どの単位も名指さない行"
        got = parking.settle([declared_text], declared={declared_text: {A}}, **base)
        self.assertEqual(sorted(got.park), [A], got)
        self.assertEqual(got.unbound, {})
        self.assertEqual(got.how, {declared_text: "declared"})
        got = parking.settle([declared_text, by_path], declared={declared_text: {A}}, **base)
        self.assertEqual(sorted(got.park), [A, B], got)
        self.assertEqual(got.how, {declared_text: "declared", by_path: "text"})
        got = parking.settle([nothing], declared={declared_text: {A}}, **base)
        self.assertEqual(sorted(got.park), [A, B], "declared に無い文は結べず義務の全部")
        self.assertEqual(got.how, {nothing: "unbound"})
        self.assertEqual(list(got.unbound), [nothing])




# ---- lib/tests/test_duty_sets.py の写し
_l_IS_OPEN = [_l_FORK_UNIT, _l_OTHER_UNIT, _l_ESC_UNIT, _l_ASKED_UNIT]   # 判定の出口の is_open の並び（関所で諮った BACK_UNIT は無い）


class DutySets(DutyCase):
    def kw(self):
        return {"withheld_by": _l_WITHHELD_BY, "returned": _l_RETURNED}

    # ---- 集合を、消費する所の入口から作る
    def promised(self) -> set:
        got = fixrules.owed_values(self.tmp, {"open_units": json.dumps(_l_IS_OPEN, ensure_ascii=False)}, owed=_l_OWED, **self.kw())
        return set(json.loads(got["open_units"]))

    def accepted(self) -> tuple:
        owed, excused = fixboard.fix_duty(self.tmp, _l_OWED, **self.kw())
        return set(owed), dict(excused)

    def tdd_owed(self) -> tuple:
        suite = self.tmp / "suite.py"
        suite.write_text("", encoding="utf-8")
        with mock.patch.object(basecase, "run_suite", return_value=([], 0, [])), \
                mock.patch.object(tddloop, "snapshot", return_value=""), mock.patch.object(common, "snapshot", return_value=""):
            got = tddloop.start(self.tmp, self.tmp, str(suite), json.dumps(_l_IS_OPEN, ensure_ascii=False), owed=_l_OWED,
                                **self.kw())
        self.assertTrue(got["go"], got)
        st = json.loads(pathlib.Path(got["state_file"]).read_text(encoding="utf-8"))
        return set(common._owed(st)), set(st["excused"])

    def gated_items(self) -> set:
        """事後の関門が見る項目の単位: 単位ごとに 1 項目の tdd の欄を置き、OUT_OF_DUTY で飛ばさなかった項目の単位"""
        fields = [{"unit_keys": [k], "route": "tdd", "route_why": "", "rewrite_tests": [], "refactor": {"declared": False, "why": ""},
                   "tests": [{"id": f"test_x.py::T::test_{n}", "behavior": "b", "path": "p", "red_kind": "assertion", "red_why": "w"}]}
                  for n, k in enumerate(_l_ALL_UNITS)]
        planmarks.save(self.tmp, 1, fields)
        tests, _ = fixgates._accept_tests(self.tmp, fields, None, owed=_l_OWED, withheld=set(_l_WITHHELD_BY),
                                          returned=_l_RETURNED)
        return {k for t in tests for k in t["unit_keys"]}

    # ---- 関係
    def test_promise_and_acceptance_and_tdd_read_one_owed(self):
        owed, excused = self.accepted()
        self.assertEqual(owed, {_l_OTHER_UNIT, _l_BACK_UNIT}, "答えを返した単位は義務に残り、答え待ち・ask_human は外れる")
        self.assertEqual(self.promised(), owed, "約束の一覧 = 受け付けの義務（関所で答えて戻った単位を含み、外れた単位を含まない）")
        tdd_owed, tdd_excused = self.tdd_owed()
        self.assertEqual(tdd_owed, owed, "TDD の義務 = 受け付けの義務 − 食い違いで止めた単位（無し）")
        self.assertEqual(tdd_excused, set(excused), "TDD が外す単位 = 受け付けの外れた単位")
        self.assertEqual(owed & set(excused), set())

    def test_post_gates_check_the_owed_items(self):
        owed, _ = self.accepted()
        self.assertEqual(self.gated_items(), owed, "事後の関門が見る項目の単位 = 受け付けの義務")

    def test_nothing_owed_only_when_owed_is_empty_and_excused_is_not(self):
        self.assertEqual(fixboard.nothing_owed_but_excused(self.tmp, _l_OWED, **self.kw()), {}, "義務が残る置き場は空の申告を通さない")
        shrunk = _l_OWED - {_l_OTHER_UNIT}
        owed, excused = fixboard.fix_duty(self.tmp, shrunk, withheld_by=_l_WITHHELD_BY, returned=())
        self.assertEqual((owed, bool(excused)), (set(), True))
        self.assertEqual(fixboard.nothing_owed_but_excused(self.tmp, shrunk, withheld_by=_l_WITHHELD_BY, returned=()), excused,
                         "義務が空で外れた単位が在る時だけ通し、外れた単位を並べる")



# ------------------------------------------------------------ 2 継ぎ目（lib/tests/test_fix_seams.py の写し）
kit.load("fix", "board")   # lib/ を sys.path に足す（src は試験ごとに _s_load で読み直す）

import conflict  # noqa: E402
import jsonfile  # noqa: E402
import leftovers  # noqa: E402
import rolekit  # noqa: E402
import writelog  # noqa: E402
import writes  # noqa: E402
SEED = kit.ROOT / "tests" / "e2e" / "target-seed"
SKIP = ("vendored/",)
WHY = "整形の道具で 40 ファイルを一度に書き換えた"
_S_MODS = ("board", "facts", "gates", "scope", "unitrows", "parking", "rules", "consult", "prompts", "runvals", "ruling", "duties")


def _s_load() -> types.SimpleNamespace:
    """workflows/fix の src を読み直し、試験が使うモジュールを 1 つの名前空間で返す（ほかの block の試験が src を読み替えても、
    同じ試験の中では 1 組の写しを使う）"""
    kit.load("fix", "board")
    return types.SimpleNamespace(**{n: importlib.import_module(f"src.{n}") for n in _S_MODS})


def _traced(place) -> list:
    p = pathlib.Path(place) / "trace.jsonl"
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []


@contextlib.contextmanager
def _s_env(place):
    """src の関数が ports.place()・prompt.emit を呼ぶ間、place を単独の run の run directory（ARTIFACTS_DIR）に置く"""
    with mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(place), "WORKFLOW_ID": kit.RUN_ID,
                                      "WORKS_FACTORY_ROOT": str(kit.ROOT)}):
        os.environ.pop("ARCHON_NODE_EXECUTION", None)
        yield


class SeamTemp(unittest.TestCase):
    def setUp(self):
        self.m = _s_load()
        self.b = self.m.board
        self.tmp = hermetic.tmpdir(self, prefix="works-fix-accept-")
        self.repo = self.tmp / "repo"
        self.rev = committed_copy(self.repo, SEED)
        self.place = self.tmp / "place"
        self.place.mkdir()

    def render(self, pass_="first", plan_file="", ripple_file=""):
        """board.consult_ask に渡す答えの役の指示の口（script consult_check と同じ src/prompts.consult_render）"""
        inner = self.m.prompts.consult_render(self.place, pass_, plan_file=plan_file, ripple_file=ripple_file)

        def render(table, asked):
            with _s_env(self.place):
                return inner(table, asked)
        return render


KEY_A = "stats.py clamp: 上限を超えた値に lo を返す"
KEY_B = "stats.py mean: 分母が len - 1"
CLAIM = {"unit_key": KEY_A, "between": ["stats.py:3", "test_stats.py:2"],
         "why_both_cannot_hold": "テストは上限 hi を期待し、今のコードは lo を返す——両方は成り立たない",
         "which_is_right": "request", "kind": "brief_vs_judgment"}

R_MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
R_CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
# 判定の units（元 works/tests/replies/judge_ok.json の class_query）
R_JUDGED = [{"key": R_MEAN, "class_query": {"how": {"patterns": ["(len(xs) - 1)"], "fixed": True, "paths": ["stats.py"],
                                                     "count": "lines"}, "counts": "defects", "total": 1}},
            {"key": R_CLAMP, "class_query": {"how": {"patterns": ["return lo"], "fixed": True, "paths": ["stats.py"],
                                                      "count": "lines"}, "counts": "population", "total": 2}}]
R_FIXED = {"sum(xs) / (len(xs) - 1)": "sum(xs) / len(xs)", "    if x > hi:\n        return lo": "    if x > hi:\n        return hi"}
R_RESIDUE = {"sum(xs) / (len(xs) - 1)": "sum(xs) / len(xs)  # 前は sum(xs) / (len(xs) - 1)",
             "    if x > hi:\n        return lo": "    if x > hi:\n        return hi"}


# 修正役の返答の changes の行の自己申告の欄（recount._reply_shape_problems が照らす。数え直しの試験の外の欄）
SELF_REPORT = {"bypass_tried": "修正を残したまま空の並びを渡して破りに行き、例外で止まるのを見た",
                "breaks": {"how": "git grep -n mean", "result": "呼び手は 1 か所で、戻り値の型は変わらない"},
                "precedent": {"problem": "平均の分母の誤り", "verdict": "adopt", "reason": "標準の定義に合わせる",
                              "source": "https://docs.python.org/3/library/statistics.html"},
                "root_or_symptom": {"kind": "root", "why": "分母の式そのものを直した"}}


def _fix_row(key, sites, **cov):
    return {"unit_key": key, "what": "直した", "files": ["stats.py"], "coverage": cov, **SELF_REPORT,
            "closure": {"sites": [{"site": f"s{i}", "red_seen": True} for i in range(sites)]}}


def _fix_ok() -> dict:
    """元 works/tests/replies/fix2_ok.json の数え直しに効く欄（mean の site 1・clamp の site 2）"""
    return {"changes": [_fix_row(R_MEAN, 1), _fix_row(R_CLAMP, 2)], "not_done": [],
            "interactions": [{"surface": "stats.py", "checked": "mean と clamp は別の関数で、順序を入れ替えても結果が同じ"}]}


class PlanrangeSeamCase(unittest.TestCase):
    """planrange の継ぎ目: 承認済みの修正案の項目は値 items で受け、合意と裁定は置き場（conflict と同じ置き場）から読む"""

    ITEMS = [{"item": 1, "unit_keys": [KEY_A], "allowed_paths": ["stats.py"], "tests": [], "rewrite_tests": [],
              "out_of_scope": [{"glob": "vendored/**", "why": "外の写し"}]}]

    def setUp(self):
        import planrange
        self.conflict, self.planrange = conflict, planrange
        self.b = _s_load().board
        self.place = hermetic.tmpdir(self)

    def test_outside_the_items_range_is_rejected_inside_passes(self):
        pr = self.planrange
        lines, rec = pr.check_paths(self.place, ["stats.py"], items=self.ITEMS)
        self.assertEqual((lines, rec), ([], {"checked": True, "items": [1]}))
        lines, rec = pr.check_paths(self.place, ["stats.py", "other.py", "vendored/x.py"], items=self.ITEMS)
        self.assertTrue(rec["checked"])
        self.assertEqual(len(lines), 2, lines)
        self.assertTrue(any("other.py" in x and "allowed_paths" in x for x in lines), lines)
        self.assertTrue(any("vendored/x.py" in x and "out_of_scope" in x for x in lines), lines)

    def test_trailing_slash_scope_globs_cover_paths_underneath(self):
        """末尾 / の allowed_paths・out_of_scope の glob は、その下の全部に効く（前は何にも当たらず、範囲が空・柵が空だった）"""
        items = [{"item": 1, "unit_keys": [KEY_A], "allowed_paths": ["lib/"], "tests": [], "rewrite_tests": [],
                  "out_of_scope": [{"glob": "lib/vendored/", "why": "外の写し"}]}]
        lines, rec = self.planrange.check_paths(self.place, ["lib/x.py", "docs/x.md", "lib/vendored/y.py"], items=items)
        self.assertTrue(rec["checked"])
        self.assertEqual(len(lines), 2, lines)
        self.assertFalse(any("lib/x.py" in x for x in lines), lines)
        self.assertTrue(any("docs/x.md" in x and "allowed_paths" in x for x in lines), lines)
        self.assertTrue(any("lib/vendored/y.py" in x and "out_of_scope" in x for x in lines), lines)

    def test_unchecked_without_a_scoped_plan(self):
        pr = self.planrange
        self.assertEqual(pr.check_paths(self.place, ["x.py"], items=None), ([], {"checked": False, "why": pr.NO_PLAN}))
        self.assertEqual(pr.check_paths(self.place, ["x.py"], items=[{"item": 1}]),
                         ([], {"checked": False, "why": pr.NO_SCOPE}))
        self.assertEqual(pr.approved(self.ITEMS), (self.ITEMS, ""))

    def test_agreed_and_ruled_paths_widen_from_the_place(self):
        c, pr = self.conflict, self.planrange
        self.b.trace(self.place, c.ASKED_OP, id="a1", item=1, status="answered", decision="allow",
                       granted_paths=["docs/x.md"])
        c.park(self.place, [CLAIM], source=c.FIX_SOURCE)
        c.apply_rulings(self.place, {"c1-1": {"decision": "fix_code_as", "text": "設定のファイルも直してよい",
                                              "limits": ["conf.ini"]}}, by="t")
        self.assertEqual(pr.check_paths(self.place, ["docs/x.md", "conf.ini"], items=self.ITEMS)[0], [])
        lines, _ = pr.check_paths(self.place, ["conf.ini"], items=self.ITEMS, ruled=False)
        self.assertTrue(any("conf.ini" in x for x in lines), lines)
        self.assertEqual(pr.permit_paths(self.place, ruled=True), ["conf.ini"])


class ScopeTextSeamCase(SeamTemp):
    """#570: 役の指示に貼る範囲の行（rules.scope_rows）は、受け付けが照らす値（planrange.scope）と同じ関数から引く。貼った
    具体のパスは照らしが通し、貼っていないパスと out_of_scope は拒む。引数を変えれば節と照らしが揃って動く"""

    ITEMS = PlanrangeSeamCase.ITEMS

    def setUp(self):
        super().setUp()
        import conflict
        self.b.trace(self.place, conflict.ASKED_OP, id="a1", item=1, status="answered", decision="allow",
                       granted_paths=["docs/x.md"])
        conflict.park(self.place, [CLAIM], source=conflict.FIX_SOURCE)
        conflict.apply_rulings(self.place, {"c1-1": {"decision": "fix_code_as", "text": "設定のファイルも直してよい",
                                                     "limits": ["conf.ini"]}}, by="t")

    def test_refix_scope_text_lists_what_check_paths_lets_through(self):
        import planrange as pr
        text = self.m.rules.scope_rows(pr.scope(self.place, items=self.ITEMS, ruled=True)[0])
        for path in ("stats.py", "docs/x.md", "conf.ini", "vendored/**"):
            self.assertIn(f"`{path}`", text)
        self.assertIn("外の写し", text)
        for path in ("stats.py", "docs/x.md", "conf.ini"):
            self.assertEqual(pr.check_paths(self.place, [path], items=self.ITEMS, ruled=True)[0], [], path)
        for path in ("vendored/x.py", "other.py"):
            self.assertTrue(pr.check_paths(self.place, [path], items=self.ITEMS, ruled=True)[0], path)
        self.assertNotIn("other.py", text)
        loose = self.m.rules.scope_rows(pr.scope(self.place, items=self.ITEMS, ruled=False)[0])
        self.assertNotIn("conf.ini", loose, "裁定の前は直す裁定のパスを貼らない")
        self.assertTrue(pr.check_paths(self.place, ["conf.ini"], items=self.ITEMS, ruled=False)[0], "照らしも通さない")
        self.assertEqual(self.m.rules.scope_rows(pr.scope(self.place, items=None, ruled=True)[0]), "", "照らさない run は節を置かない")

    def test_fix_scope_text_lists_what_planscope_lets_through(self):
        import planrange as pr
        planscope = self.m.scope
        text = self.m.rules.scope_rows(pr.fix_scope(self.place, "first", items=self.ITEMS)[0])
        self.assertIn("`docs/x.md`", text)
        self.assertNotIn("conf.ini", text, "段 first は直す裁定のパスを許さない")
        lines, rec = planscope.check([], self.place, self.repo, self.rev, ["docs/x.md"], pass_="first", items=self.ITEMS)
        self.assertEqual((lines, rec.get("checked", True)), ([], True))
        lines, _ = planscope.check([], self.place, self.repo, self.rev, ["conf.ini"], pass_="first", items=self.ITEMS)
        self.assertTrue(any("conf.ini" in x for x in lines), lines)
        self.assertIn("`conf.ini`", self.m.rules.scope_rows(pr.fix_scope(self.place, "ruled", items=self.ITEMS)[0]))
        self.assertEqual(planscope.check([], self.place, self.repo, self.rev, ["conf.ini"], pass_="ruled", items=self.ITEMS)[0], [])

    def test_ruled_paths_waive_the_name_check_after_ruling(self):
        """直す裁定が limits に挙げたパス（conf.ini）の同じ言語の同名の定義は、裁定の後の照らしで足す行の path の外に数えない"""
        planscope = self.m.scope
        items = [{**self.ITEMS[0], "allowed_paths": ["stats.py", "app.ini"],
                  "files": [{"path": "app.ini", "op": "create", "symbols": [{"name": "LIMIT", "change": "add"}]}]}]
        for path, text in (("app.ini", "LIMIT = 1\n"), ("conf.ini", "LIMIT = 2\n")):
            (self.repo / path).write_text(text, encoding="utf-8")
        rows = [{"unit_key": KEY_A, "files": ["app.ini", "conf.ini"]}]
        lines, _ = planscope.check(rows, self.place, self.repo, self.rev, ["app.ini", "conf.ini"], pass_="ruled", items=items)
        self.assertEqual(lines, [])

    def test_each_stage_applies_its_out_of_scope_rule(self):
        """修正の段は申告した単位の項目が明示に許したパスをその項目の out_of_scope だけで照らし、手直しの段は全部の項目で照らす"""
        import planrange as pr
        planscope = self.m.scope
        items = [{"item": 1, "unit_keys": [KEY_A], "allowed_paths": ["shared/x.py"], "tests": [], "rewrite_tests": [],
                  "out_of_scope": []},
                 {"item": 2, "unit_keys": [KEY_B], "allowed_paths": ["stats.py"], "tests": [], "rewrite_tests": [],
                  "out_of_scope": [{"glob": "shared/**", "why": "別の項目の物"}]}]
        lines, _ = planscope.problems(items, [{"unit_key": KEY_A, "files": ["shared/x.py"]}],
                                      {"shared/x.py": ("A = 1\n", "A = 2\n")})
        self.assertFalse([x for x in lines if "shared/x.py" in x], lines)
        self.assertTrue(pr.outside(items, ["shared/x.py"]), "手直しの段は別の項目の out_of_scope でも拒む")

    def test_tests_text_lists_the_new_tests_planscope_lets_through(self):
        """#603: 修正役の指示に貼る足してよい新しいテスト（rules.tests_rows）は、受け付けが照らす項目の tests（planrange.test_ids）
        と同じ値。範囲の相談で許した新しいテストは、節にも照らしにも揃って入る"""
        import conflict
        import planrange as pr
        planscope = self.m.scope
        items = [{"item": 1, "unit_keys": [KEY_A], "allowed_paths": ["stats.py"], "rewrite_tests": [], "out_of_scope": [],
                  "tests": [{"id": "test_stats.py::test_mean", "red_kind": "assertion"}]}]
        changes = {"test_stats.py": ("import stats\n",
                                     "import stats\n\ndef test_mean():\n    pass\n\ndef test_other():\n    pass\n")}
        rows = [{"unit_key": KEY_A, "files": ["test_stats.py"]}]

        def pasted_and_rejected():
            got = pr.fix_scope(self.place, "first", items=items)[0]
            text = self.m.rules.tests_rows(got, conflict.edit_permits(self.place, "first"), None)
            lines, _ = planscope.problems(got["items"], rows, changes)
            return text, [x for x in lines if "どの項目の tests にも無い" in x]

        text, rejected = pasted_and_rejected()
        self.assertIn("`test_stats.py::test_mean`", text)
        self.assertNotIn("test_stats.py::test_other", text)
        self.assertEqual(rejected, ["test_stats.py::test_other は修正案のどの項目の tests にも無いテストを足した"])
        self.b.trace(self.place, conflict.ASKED_OP, id="a2", item=1, status="answered", decision="allow",
                       granted_new_tests=[{"id": "test_stats.py::test_other", "red_kind": "assertion"}])
        text, rejected = pasted_and_rejected()
        self.assertIn("`test_stats.py::test_other`", text)
        self.assertEqual(rejected, [])


class FactchecksSeamCase(SeamTemp):
    """factchecks の継ぎ目: 事前の確かめと受け付けの事実の確かめは、置き場（board）のファイルと引数の値で回り、置き場を書かない
    （元 works/tests/test_fix_precheck.py の PrecheckCase の場合を写した。盤面の代わりに承認済みの修正案の項目 items を値で渡し、
    合意は置き場の trace.jsonl に置く）。直す義務は board.fix_duty、書き込みの記録は引数 log、除くパスの頭は skip"""

    ITEM = {"item": 1, "unit_keys": [R_MEAN], "files": [], "route": "direct", "tests": [], "rewrite_tests": [],
            "allowed_paths": ["docs/**"], "out_of_scope": []}

    def setUp(self):
        super().setUp()
        factchecks = self.m.facts
        self.fc = factchecks
        path = self.repo / "stats.py"
        text = path.read_text(encoding="utf-8")
        for old, new in R_FIXED.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
        self.reply = {"changes": [{"unit_key": R_MEAN, "files": ["stats.py"]}]}
        self.cfg = {"board": str(self.place), "repo": str(self.repo), "base_rev": self.rev, "tdd_state": "", "pass": "first"}

    def shas(self) -> dict:
        import hashlib
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(self.place.rglob("*")) if p.is_file()}

    def agree(self, paths):
        """確かめの節が書く合意の行（allow）を置き場の trace に直に置く"""
        import conflict
        self.b.trace(self.place, conflict.ASKED_OP, id=1, item="1", status="answered", decision="allow",
                       granted_paths=paths, granted_tests=[], reason="直しに伴うので足してよい")

    def test_scope_reject_listed_and_place_untouched(self):
        planscope = self.m.scope
        before = self.shas()
        got = self.fc.precheck(self.cfg, self.reply, items=[self.ITEM])
        self.assertFalse(got["ok"])
        scope = [r["text"] for r in got["rejects"] if r["check"] == "scope"]
        self.assertTrue(any("stats.py" in t for t in scope), got)
        self.assertTrue(scope[0].startswith(planscope.REJECT_ASK), "事前の確かめは相談の節の道具なので、拒否の頭は相談を先の道に言う")
        self.assertEqual(self.shas(), before, "置き場を書かない")

    def test_precheck_rejects_the_wrote_refs_the_acceptance_rejects(self):
        """#603: 事前の確かめは、受け付けと同じ口（recount.ref_problems）で書いた指しを照らす。置き場は書かない"""
        import recount
        (self.repo / "NOTES.md").write_text("# 覚え\n\n平均は stats.py の mean\n", encoding="utf-8")
        reply = {"changes": [{"unit_key": R_MEAN, "files": ["stats.py", "NOTES.md"]}],
                 "wrote_refs": [{"kind": "text", "cite": "def median", "target": "stats.py", "where": "NOTES.md"}]}
        before = self.shas()
        refs = [r["text"] for r in self.fc.precheck(self.cfg, reply)["rejects"] if r["check"] == "refs"]
        self.assertEqual(refs, recount.ref_problems(reply, self.place, self.rev, self.repo))
        self.assertTrue(any("'def median' は指し先 'stats.py' の中に無い" in t for t in refs), refs)
        reply["wrote_refs"][0]["cite"] = "def mean"
        self.assertEqual([r for r in self.fc.precheck(self.cfg, reply)["rejects"] if r["check"] == "refs"], [])
        self.assertEqual(self.shas(), before, "置き場を書かない")

    def test_precheck_checks_the_frozen_files_of_the_returns_the_acceptance_checks(self):
        """事前の確かめは、受け付けと同じく返しの控えの凍ったファイルを注文の許しで照らす（duties.frozen_by_returns）。置き場は書かない"""
        import hashlib
        test_file = self.repo / "test_stats.py"
        (self.place / "returns").mkdir()
        (self.place / "returns" / "1.json").write_text(json.dumps(
            {"stage": 1, "weapon": "tdd", "group": "g1", "tree": self.rev, "units": [], "frozen_tree": self.rev,
             "frozen": {"test_stats.py": hashlib.sha256(test_file.read_bytes()).hexdigest()}}), encoding="utf-8")
        (self.place / "orders.json").write_text(json.dumps({"sequence": [], "weapons": {}, "stage": 1, "since": self.rev}),
                                                encoding="utf-8")
        self.assertEqual([r for r in self.fc.precheck(self.cfg, self.reply)["rejects"] if r["check"] == "frozen"], [])
        test_file.write_text(test_file.read_text(encoding="utf-8").replace("clamp(15, 0, 10), 10", "clamp(15, 0, 10), 10.0"),
                             encoding="utf-8")
        before = self.shas()
        frozen = [r["text"] for r in self.fc.precheck(self.cfg, self.reply)["rejects"] if r["check"] == "frozen"]
        self.assertEqual(frozen, self.m.duties.frozen_by_returns(self.place, self.repo))
        self.assertTrue(frozen)
        self.assertEqual(self.shas(), before, "置き場を書かない")

    def test_place_agreement_counts(self):
        self.agree(["stats.py"])
        self.assertEqual(self.fc.precheck(self.cfg, self.reply, items=[self.ITEM]), {"ok": True, "rejects": []})

    def test_other_place_rows_do_not_count(self):
        """置き場の trace の allow の行だけが合意（前の形の記録 exchanges.jsonl を偽っても範囲は広がらない）"""
        (self.place / "exchanges.jsonl").write_text(json.dumps(
            {"id": 1, "item": "1", "status": "answered", "decision": "allow", "granted_paths": ["stats.py"],
             "granted_tests": [], "reason": "偽の合意の行"}) + "\n", encoding="utf-8")
        self.assertFalse(self.fc.precheck(self.cfg, self.reply, items=[self.ITEM])["ok"])

    def test_no_plan_items_is_not_scoped(self):
        self.assertEqual(self.fc.precheck(self.cfg, self.reply)["rejects"], [])
        self.assertTrue(self.fc.precheck(self.cfg, self.reply, items=[{**self.ITEM, "allowed_paths": ["stats.py"]}])["ok"])

    def test_precheck_reads_the_fixer_tree_the_acceptance_reads(self):
        """事前の確かめと受け付けは、修正役が変え始めた木（段の頭）を同じ所から読む: 段の頭より前に変わった stats.py を、
        段の頭を見ない照らし（輪の凍った木に戻る）は修正役に問い、受け付けは問わない。その場面で 2 つの範囲の行が揃う（#332）"""
        for pass_, name in (("first", self.b.FIX_HEAD_FILE), ("ruled", self.b.RULED_HEAD_FILE)):
            with self.subTest(pass_=pass_):
                (self.place / name).write_text(json.dumps({"tree": leftovers.snapshot(self.repo)}), encoding="utf-8")
                args = (self.reply, [R_MEAN], self.place, self.rev, self.repo, "", pass_)
                accepted, _ = self.fc.check_plan_scope(*args, ask=True, since=self.b.stage_head(self.place, name),
                                                       items=[self.ITEM])
                headless, _ = self.fc.check_plan_scope(*args, ask=True, items=[self.ITEM])
                self.assertNotEqual(headless, accepted, "2 つの木で照らしが食い違う場面")
                got = self.fc.precheck({**self.cfg, "pass": pass_}, self.reply, items=[self.ITEM])
                self.assertEqual([r["text"] for r in got["rejects"] if r["check"] == "scope"], accepted)
                (self.place / name).unlink()

    def test_fixer_head_rejects_a_pass_outside_the_passes(self):
        """#357: 段の頭のファイルは fixrules.PASSES を鍵にした表から引く。表に無い段は 1 回目の段の頭に黙って落とさず例外"""
        fixrules = self.m.rules
        (self.place / self.b.FIX_HEAD_FILE).write_text(json.dumps({"tree": "1 回目の段の頭"}), encoding="utf-8")
        self.assertEqual(self.b.fixer_head(self.place, "first"), "1 回目の段の頭")
        with self.assertRaises(ValueError):
            self.b.fixer_head(self.place, "refix")
        self.assertEqual(tuple(fixrules.HEAD_FILES), fixrules.PASSES)

    def test_scope_head_follows_the_consult_place(self):
        consult = self.m.consult
        planscope = self.m.scope
        args = (self.reply, [R_MEAN], self.place, self.rev, self.repo, "", "first")
        lines, _ = self.fc.check_plan_scope(*args, items=[self.ITEM])
        self.assertTrue(lines[0].startswith(planscope.REJECT), "相談の控えが無ければ申し出の道")
        consult.write_config(self.place, {"board": str(self.place), "repo": str(self.repo), "pass": "first",
                                          "items": {"1": {"unit_keys": [R_MEAN]}}})
        lines, _ = self.fc.check_plan_scope(*args, items=[self.ITEM], consult_place=self.place)
        self.assertTrue(lines[0].startswith(planscope.REJECT_ASK), lines)

    def test_writes_use_the_log_and_skip(self):
        log = self.place / writelog.LOG
        log.write_text("", encoding="utf-8")   # 記録の在る run（Edit・Write の行は無い）
        (self.repo / "vendored").mkdir()
        (self.repo / "vendored" / "x.py").write_text("x = 1\n", encoding="utf-8")
        got = self.fc.check_writes(self.reply, self.place, self.rev, self.repo, "")
        self.assertTrue(any("stats.py" in p for p in got["problems"]), got)
        self.assertTrue(any("vendored/x.py" in p for p in got["problems"]), got)
        got = self.fc.check_writes(self.reply, self.place, self.rev, self.repo, "", skip=SKIP)
        self.assertFalse(any("vendored/x.py" in p for p in got["problems"]), got)
        declared = {**self.reply, writes.FIELD: [{"path": "stats.py", "why": WHY}]}
        got = self.fc.check_writes(declared, self.place, self.rev, self.repo, "", log=log, skip=SKIP)
        self.assertEqual(got["problems"], [], got)
        self.assertNotIn(writes.FIELD, got["reply"])

    def test_fix_unit_keys_and_duty(self):
        got = self.fc.fix_unit_keys(self.reply, self.place, {R_MEAN, R_CLAMP})
        self.assertEqual(got, ([R_MEAN], {R_MEAN, R_CLAMP}, {}))
        self.assertIsNone(self.fc.fix_unit_keys({"changes": "x"}, self.place, set()))
        self.assertIsNone(self.fc.fix_unit_keys({"changes": [{"unit_key": 1}]}, self.place, set()))

    def test_no_loop_has_no_frozen_rejects(self):
        self.assertEqual(self.fc.check_frozen(self.place, "", self.repo, "first", base_rev=self.rev), [])

    def test_declared_files(self):
        rows = [{"files": [str(self.repo / "a" / ".." / "stats.py"), " docs/x.md ", "", 3]}]
        self.assertEqual(self.fc.declared_files(rows, self.repo), {"stats.py", "docs/x.md"})
        linked = self.tmp / "linked"
        linked.symlink_to(self.repo)
        (self.repo / "alias.py").symlink_to(self.repo / "stats.py")
        rows = [{"files": [str(linked / "stats.py"), str(self.repo / "alias.py")]}]
        self.assertEqual(self.fc.declared_files(rows, self.repo), {"stats.py", "alias.py"}, "根のリンクは解き、ファイルのリンクは解かない")

    def run_main(self, allowed):
        """置き場に修正案の控え（planmarks.save の欄・p2.fix_plan.json・judgment.json）と相談の控えを置き、下書きの返答で main を
        子のプロセスで回す（修正役の指示書に書くコマンド `<python> factchecks.py <相談の控え> --reply <下書き>` の形）"""

        consult = self.m.consult
        import planmarks
        planmarks.save(self.place, 1, [{"route": "direct", "tests": [], "rewrite_tests": [], "allowed_paths": allowed,
                                         "out_of_scope": []}])
        (self.place / self.b.PLAN_REPLY_FILE).write_text(json.dumps(
            {"plan": [{"unit_keys": [R_MEAN], "approach": "分母を直す", "files": []}]}, ensure_ascii=False),
            encoding="utf-8")
        (self.place / self.b.JUDGMENT_FILE).write_text(json.dumps({"units": R_JUDGED}, ensure_ascii=False), encoding="utf-8")
        cfg = consult.write_config(self.place, {**self.cfg, "items": {"1": {"unit_keys": [R_MEAN]}}})
        draft = self.tmp / "draft.json"
        draft.write_text(json.dumps(self.reply, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, str(kit.BLOCKS / "fix" / "src" / "facts.py"), str(cfg), "--reply", str(draft)], cwd=str(self.repo),
                           capture_output=True, text=True, encoding="utf-8", env=hermetic.child_env())
        return r.returncode, r.stdout, r.stderr

    def test_main_reads_the_plan_in_the_place(self):
        planscope = self.m.scope
        code, out, err = self.run_main(["docs/**"])
        self.assertEqual(code, 1, out + err)
        got = json.loads(out)
        self.assertTrue(any(r["check"] == "scope" and "stats.py" in r["text"] and r["text"].startswith(planscope.REJECT_ASK)
                            for r in got["rejects"]), got)

    def test_main_passes_inside_the_plan(self):
        code, out, err = self.run_main(["stats.py"])
        self.assertEqual((code, json.loads(out)), (0, {"ok": True, "rejects": []}), out + err)

    def test_main_wiring_error_is_two(self):
        r = subprocess.run([sys.executable, str(kit.BLOCKS / "fix" / "src" / "facts.py"), str(self.place / "none.json")],
                           capture_output=True, text=True, encoding="utf-8", env=hermetic.child_env())
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


class FixgatesSeamCase(SeamTemp):
    """fixgates の継ぎ目: 盤面の b.work・b.dir/r<周> を置き場のパスに、writes.base_rev を board.base_rev に、
    conflict.owed_units_but_asked を board.owed_units_but_asked（値で受ける）に、entry.open_board を置き場のパスに替えた所"""

    MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
    ID = "test_stats.py::TestStats::test_mean_of_three"   # 種で赤（len-1 で割る）の既存のテスト
    FIELDS = [{"unit_keys": [MEAN], "route": "tdd", "route_why": "", "rewrite_tests": [], "refactor": {"declared": False, "why": ""},
               "tests": [{"id": ID, "behavior": "3 つの平均", "path": "p", "red_kind": "assertion", "red_why": "len-1"}]}]

    def setUp(self):
        super().setUp()
        import planmarks
        planmarks.save(self.place, 1, self.FIELDS)
        self.suite = self.tmp / "suite.py"
        self.suite.write_text(_l_PYTEST_LIKE, encoding="utf-8")
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")

    def test_ledger_cache_and_logs_live_in_the_place(self):
        """帳面・base の木の控え・一式のログは置き場の中だけに書き、skipped・guards・unchecked は置き場の帳面を読む"""
        fixgates = self.m.gates
        self.assertEqual(fixgates.problems(self.place, self.repo, self.rev, str(self.suite), 1), [])
        self.assertTrue((self.place / fixgates.BASE_CACHE).is_file())
        self.assertTrue((self.place / f"{fixgates.RUN}-first-1").is_dir())
        self.assertFalse((self.place / "r1").exists(), "盤面の周のフォルダは作らない")
        self.assertEqual(fixgates.problems(self.place, self.repo, self.rev, "", 2), [])
        self.assertEqual(json.loads((self.place / fixgates.LEDGER).read_text(encoding="utf-8"))["skipped"],
                         [{"pass": "first", "attempt": 2, "why": fixgates.NO_SUITE}])
        self.assertEqual(fixgates.skipped(self.place, pass_="first", attempt=2), [fixgates.NO_SUITE])
        self.assertEqual(fixgates.unchecked(self.place, pass_="first", attempt=2), [fixgates.NO_SUITE])
        self.assertEqual(git(self.repo, "status", "--porcelain"), "M stats.py", "作業ツリーに走らせた跡を残さない")

    def test_base_rev_and_duty_come_from_arguments(self):
        """修正前の版は board.base_rev(state, base_rev) の順、直す義務は owed・withheld・returned の値で受ける"""
        fixgates = self.m.gates
        with mock.patch.object(fixgates.fixboard, "base_rev", wraps=self.b.base_rev) as rev, \
                mock.patch.object(fixgates.fixboard, "owed_units_but_asked", wraps=self.b.owed_units_but_asked) as duty:
            fixgates.problems(self.place, self.repo, "HEAD", "", 1, state={"inputs": {"review_rev": self.rev}},
                              owed=[self.MEAN], withheld=[self.MEAN], returned=())
        rev.assert_called_once_with({"inputs": {"review_rev": self.rev}}, "HEAD")
        duty.assert_called_once_with(self.place, [self.MEAN], withheld=[self.MEAN], returned=())
        why = fixgates.skipped(self.place, pass_="first", attempt=1)
        self.assertTrue(why and why[0].startswith(fixgates.OUT_OF_DUTY), why)

    def test_broken_fields_are_a_value_error(self):
        """凍結の印と食い違う欄の控えは、盤面を止める BoardGap でなく ValueError（止めるのは呼び手）"""
        fixgates = self.m.gates
        self.b.marks_path(self.place).write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            fixgates.problems(self.place, self.repo, self.rev, "", 1)
        self.assertFalse((self.place / fixgates.LEDGER).exists())


class FixAcceptSeamCase(SeamTemp):
    """修正役の受け付けと範囲の相談の部品（fixboard の check_*_units・fix_reject_text・undeclared_writes・reply_marks・unit_outcomes・
    allowed_tests・ruled_owed・ruled_reply_line・consult_ask・accept_reply）。元 works/blk-fix/scripts/accept.py の単位の行の照らしと
    元 works/blk-fix/lib/consult.py:522 の頼みの節を、置き場と値で回す"""

    def test_unit_row_checks(self):
        """同じ unit_key の 2 行・義務にも外れにも無い key・外れた単位の行（元 accept.py:258・268・297）"""
        keys = ["a", "b", "a", "x", "c", "x"]
        self.assertEqual(self.b.check_unique_units(keys), ["a", "x"])
        self.assertEqual(self.b.check_opened_units(keys, {"a", "b", "c"}), ["x"])
        self.assertEqual(self.b.check_excused_units(keys, {"a", "b"}, {"c": "人が決める"}), {"c": "人が決める"})

    def test_closure_reply_takes_the_replaced_query_and_the_zero_units(self):
        """閉鎖の数え直しは、裁定 replace_query を受けた単位を置き換えた問いで数え（conflict.replaced_queries）、判定者の問いが
        修正前の版で 0 件なのに total が 0 でない単位を 0 件の単位にする（元 unitrows.take の engine_zero）"""
        import conflict
        how = {"patterns": ["return lo"], "fixed": True, "paths": ["stats.py"], "count": "lines"}
        judged = [*R_JUDGED, {"key": "zero-unit", "class_query": {
            "how": {"patterns": ["zzz-none"], "fixed": True, "paths": ["stats.py"], "count": "lines"},
            "counts": "defects", "total": 3}}]
        conflict.park(self.place, [{"unit_key": R_MEAN, "between": ["stats.py:9", "stats.py:9"],
                                    "why_both_cannot_hold": "判定者の問いが直した後の正しい形にも当たる",
                                    "which_is_right": "query", "kind": "query_hits_fixed"}], source=conflict.FIX_SOURCE,
                      ruling={"decision": "replace_query", "text": "問いを置き換える", "limits": [],
                              "query": {"how": how, "counts": "population", "hits": ["return lo"], "misses": []}})
        shaped, rows, zero = self.b.closure_reply({"changes": [_fix_row(R_MEAN, 1)]}, self.place, self.repo, self.rev, judged)
        self.assertEqual(zero, {"zero-unit"})
        self.assertTrue(rows[0]["how_from"].startswith("裁定"), rows)
        self.assertNotIn("path", shaped["changes"][0]["closure"]["sites"][0])

    def test_reject_text_follows_the_check_order(self):
        found = [("copy", "数えが合わない"), ("writes", "記録が無い"), ("writes", "記録が無い"), ("duplicate", "a")]
        text = self.b.fix_reject_text(found)
        self.assertTrue(text.startswith("## "), "決まった頭の文は md が持ち、本文は確かめの見出しから始まる")
        self.assertLess(text.index("確かめ writes・1 件"), text.index("確かめ duplicate"))
        self.assertLess(text.index("確かめ duplicate"), text.index("確かめ copy"))
        self.assertEqual(self.b.fix_reject_rows(found), [("writes", "記録が無い"), ("duplicate", "a"), ("copy", "数えが合わない")])

    def test_undeclared_writes_bind_to_changes_and_bash_writes(self):
        tree = leftovers.snapshot(self.repo)
        (self.repo / "stats.py").write_text("x = 1\n", encoding="utf-8")
        (self.repo / "gen.txt").write_text("生成\n", encoding="utf-8")
        (self.repo / "vendored").mkdir()
        (self.repo / "vendored" / "w.txt").write_text("工程の写し\n", encoding="utf-8")
        reply = {"changes": [{"unit_key": "a", "files": ["stats.py"]}]}
        got = self.b.undeclared_writes(reply, self.repo, tree, skip=SKIP)
        self.assertEqual(got, [self.b.UNDECLARED + "gen.txt"])
        self.assertEqual(self.b.undeclared_writes(reply, self.repo, tree, made={"gen.txt"}, skip=SKIP), [])
        told = {**reply, "bash_writes": [{"path": "gen.txt", "why": WHY}]}
        self.assertEqual(self.b.undeclared_writes(told, self.repo, tree, skip=SKIP), [])
        self.assertEqual(len(self.b.undeclared_writes(reply, self.repo, tree)), 1, "既定の () では除かない")
        self.assertIn("vendored/w.txt", self.b.undeclared_writes(reply, self.repo, tree)[0])

    def test_reply_marks_or_over_the_previous(self):
        before = self.b.reply_marks({"gates_changed": True, "rejudge_requested": "前の異議", "premise_drift_note": "前の申告"})
        got = self.b.reply_marks({"changes": [], "path_changed": True, "rejudge_requested": "今の異議",
                                    "premise_drift_note": "今の申告"}, before)
        self.assertEqual(got["changed"], {**{k: k in ("gates_changed", "path_changed") for k in self.b.CHANGED_MARKS},
                                          self.b.DRIFT_NOTE: "前の申告\n今の申告"})
        self.assertEqual(got["rejudge_requested"], "前の異議\n今の異議")
        self.assertTrue(got["gates_changed"])

    def test_unit_outcomes(self):
        reply = {"changes": [{"unit_key": "a"}], "not_done": [{"unit_key": "b", "why": "答え待ち"}]}
        got = self.b.unit_outcomes(["a", "b", "c"], reply, excused={"d": "人が決める"}, parked={"c": "諦めた"})
        self.assertEqual(got, {"a": {"status": "fixed", "reason": ""}, "b": {"status": "not_done", "reason": "答え待ち"},
                               "c": {"status": "given_up", "reason": "諦めた"},
                               "d": {"status": "not_done", "reason": "人が決める"}})
        got = self.b.unit_outcomes(["a"], {}, conflicted={"a": self.b.PARKED_FOR_RULING})
        self.assertEqual(got["a"], {"status": "not_done", "reason": self.b.PARKED_FOR_RULING})

    def test_allowed_tests_take_rulings_and_agreements(self):
        import conflict
        conflict.park(self.place, [{"unit_key": "a", "between": ["stats.py:9", "test_stats.py:8"],
                                    "why_both_cannot_hold": "テストの期待が誤っている", "which_is_right": "request",
                                    "kind": "unnamed_test_broke"}], source=conflict.FIX_SOURCE,
                      ruling={"decision": "fix_test_scope", "text": "直してよい", "limits": ["test_stats.py:8"]})
        self.b.trace(self.place, conflict.ASKED_OP, id=1, item="1", status="answered", decision="allow", granted_paths=[],
                       granted_tests=["tests/test_b.py:3"], granted_new_tests=[{"id": "tests/test_c.py::T::t", "red_kind": "red"}],
                       reason="足してよい")
        self.assertEqual(self.b.allowed_tests(self.place), ["test_stats.py", "tests/test_b.py", "tests/test_c.py"])
        import planmarks
        planmarks.save(self.place, 1, [{"unit_keys": ["a"], "rewrite_tests": [
            {"id": "tests/test_d.py::test_d", "new": "hi を期待する", "limit": "tests/test_d.py:1"}]}])
        self.assertEqual(self.b.allowed_test_rows(self.place), [
            {"path": "test_stats.py", "permit": f"{conflict.RULED_TEST_ID}-c1-1", "source": "ruling"},
            {"path": "tests/test_b.py", "permit": f"{conflict.AGREED_TEST_ID}-1", "source": "consult"},
            {"path": "tests/test_c.py", "permit": f"{conflict.AGREED_TEST_ID}-1", "source": "consult"},
            {"path": "tests/test_d.py", "permit": f"{conflict.PLAN_TEST_ID}-1", "source": "plan"}],
            "許しの出どころは許しの行が持つ（id の頭から引き直さない）")

    def test_ruled_owed_reads_the_join(self):
        (self.place / "judgment.json").write_text(json.dumps({"units": [{"key": k, "label": "block"} for k in "abc"]}),
                                                  encoding="utf-8")
        self.assertEqual(self.b.ruled_owed(self.place), ["a", "b", "c"])
        (self.place / "join.json").write_text(json.dumps({
            "groups": [{"group_id": "g1", "returned": True}, {"group_id": "g2", "returned": False}],
            "units": [{"unit_id": "a", "group_id": "g1", "status": "fixed"}, {"unit_id": "b", "group_id": "g1", "status": "not_done"},
                      {"unit_id": "c", "group_id": "g2", "status": "not_done"}]}), encoding="utf-8")
        self.assertEqual(self.b.ruled_owed(self.place), ["b"])
        self.assertEqual(self.b.group_owed(self.place, ["c", "z"]), ["c"])

    def test_group_owed_keeps_the_unit_ids_order(self):
        """group_owed(place, [後, 前]) が、判定の順でなく、渡した unit_ids の順（組の中の依存の順）で返す。重なりは 1 つ。直す義務に無い単位は落ちる"""
        (self.place / "judgment.json").write_text(json.dumps({"units": [{"key": k, "label": "block"} for k in "abc"]}),
                                                  encoding="utf-8")
        self.assertEqual(self.b.group_owed(self.place), ["a", "b", "c"])
        self.assertEqual(self.b.group_owed(self.place, ["c", "a", "z", "c"]), ["c", "a"])

    def test_ruled_reply_line_is_the_saved_reply_path(self):
        """裁定の後の修正役の段落 ruled_reply に入れる値は、1 回目の返答の保存したファイルのパス（文は md。無ければ空）。
        元は指示書の題の後に 1 度だけ行を足した（行の差し込みは md の段落に替わった）"""
        self.assertEqual(self.b.ruled_reply_line("/x/fix-reply.json"), "/x/fix-reply.json")
        self.assertEqual(self.b.ruled_reply_line(pathlib.Path("/x/fix-reply.json")), "/x/fix-reply.json")
        self.assertEqual(self.b.ruled_reply_line(None), "")

    def test_consult_ask_screens_and_writes_the_question(self):
        consult = self.m.consult
        items = [{"item": 1, "unit_keys": ["a"], "allowed_paths": ["stats.py"], "out_of_scope": [], "tests": []}]
        reply = {consult.conflict.CONSULT_FIELD: [
            {"item": 1, "paths": ["docs/n.md"], "tests": [], "why": "直しに伴う記録を残す要が在る（範囲の外）", **SUMMARY},
            {"item": 9, "paths": ["x.py"], "tests": [], "why": "知らない項目への頼みの理由の文", **SUMMARY},
            {"item": 1, "paths": ["docs/m.md"], "tests": [], "why": "経緯の欄を書かなかった頼みの理由の文"}]}
        got = self.b.consult_ask(self.place, reply, "first", items, node="consult-answer",
                                 render=self.render(plan_file="/p/plan.json"))
        self.assertEqual((got["consulted"], got["go"], got["turn"]), (True, True, 1))
        text = pathlib.Path(got["prompt_file"]).read_text(encoding="utf-8")
        self.assertEqual(text, got["prompt"], "置き場の控えと返りの prompt は同じ字")
        self.assertIn("/p/plan.json", text)
        self.assertNotIn("x.py", text, "断った頼みは聞かない")
        self.assertNotIn("docs/m.md", text, "試したこと・直せない訳・根拠の無い修正役の頼みは聞かない（#833）")
        self.assertIn(SUMMARY["blocked"], text, "修正役の経緯は答えの役の指示に入る（#833）")
        st = consult.state(self.place, "first")
        self.assertEqual([r["status"] for r in st["rows"]], [consult.ASKED, consult.REFUSED, consult.REFUSED])
        self.assertIn("試したこと", st["rows"][2]["why_refused"])
        self.assertEqual(self.b.consult_ask(self.place, {"changes": []}, "first", items, node="x",
                                            render=self.render())["consulted"], False)
        jsonfile.write(consult.state_path(self.place, "first"), {"turns": consult.BUDGET})
        self.assertTrue(self.b.consult_ask(self.place, reply, "first", items, node="x", render=self.render())["spent"])

    def test_accept_reply_parks_the_bound_unit_on_the_last_turn(self):
        """3 回目の拒否は名指しの単位だけを段の頭の木に戻して諦め、残りを受ける（元 accept.py の last_settle・park_units）"""
        import conflict
        (self.place / "judgment.json").write_text(json.dumps({"units": [{"key": "alpha-unit", "label": "block"},
                                                                        {"key": "beta-unit", "label": "block"}]}), encoding="utf-8")
        head = leftovers.snapshot(self.repo)
        (self.repo / "a.txt").write_text("a\n", encoding="utf-8")
        (self.repo / "b.txt").write_text("b\n", encoding="utf-8")
        how = {"patterns": ["zzz-none"], "fixed": True, "paths": ["stats.py"], "count": "lines"}
        reply = {"changes": [{"unit_key": "alpha-unit", "what": "足した", "files": ["a.txt"], "coverage": {"how": how, "counts": "population"},
                              "closure": {"sites": []}, **SELF_REPORT},
                             {"unit_key": "beta-unit", "what": "足した", "files": ["b.txt"], **SELF_REPORT}]}
        kw = dict(pass_="first", owed=["alpha-unit", "beta-unit"], judged=[], head=head, skip=SKIP)
        got = self.b.accept_reply(reply, self.place, self.repo, iteration=2, **kw)
        self.assertFalse(got["ok"])
        self.assertTrue(any(r["check"] == "copy" and r["text"].startswith("beta-unit:") for r in got["rejects"]), got["rejects"])
        self.assertTrue((self.repo / "b.txt").exists(), "最後の回でなければ戻さない")
        got = self.b.accept_reply(reply, self.place, self.repo, iteration=3, **kw)
        self.assertTrue(got["ok"], got["reason"])
        self.assertEqual({k: v["status"] for k, v in got["units"].items()}, {"alpha-unit": "fixed", "beta-unit": "given_up"}, got["units"])
        self.assertFalse((self.repo / "b.txt").exists())
        self.assertTrue((self.repo / "a.txt").exists())
        self.assertEqual([r["unit_key"] for r in conflict.items(self.place)], ["beta-unit"])
        self.assertEqual([r["op"] for r in _traced(self.place) if r["op"] == conflict.ACCEPT_PARKED_OP], [conflict.ACCEPT_PARKED_OP])


    def _accept_fixed(self, reply, precedents=()):
        """判定の写し（R_JUDGED と precedents）を置き、R_FIXED で直した木で 1 回目の受け付けを回す"""
        (self.place / "judgment.json").write_text(json.dumps({"units": R_JUDGED, "precedents": list(precedents)},
                                                             ensure_ascii=False), encoding="utf-8")
        head = leftovers.snapshot(self.repo)
        path = self.repo / "stats.py"
        text = path.read_text(encoding="utf-8")
        for old, new in R_FIXED.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
        return self.b.accept_reply(reply, self.place, self.repo, pass_="first", iteration=1, owed=[R_MEAN, R_CLAMP],
                                     judged=R_JUDGED, head=head, base_rev=self.rev, skip=SKIP)

    def test_accept_reply_saves_the_closure_table_it_recounted(self):
        """受けた返答は閉鎖の数え直し（closure_reply）を通り、単位ごとの表を置き場に置く（querytest.save_closure）"""
        import querytest
        got = self._accept_fixed(_fix_ok())
        self.assertTrue(got["ok"], got["reason"])
        rows = json.loads((self.place / querytest.CLOSURE_FILE).read_text(encoding="utf-8"))["rows"]
        self.assertEqual({r["unit_key"]: r["how_from"] for r in rows}, {R_MEAN: "判定者", R_CLAMP: "判定者"})

    # ---- 欠陥を数える問いが直した後の正しい行にも当たる（#313。#154 の通しの clamp の単位の判定と、上限の分岐だけを直した stats.py）
    D_CLAMP = "stats.py clamp: 上限を超えた入力に下限 lo を返す"
    D_JUDGED = [{"key": D_CLAMP, "class_query": {"how": {"patterns": ["return lo"], "paths": ["stats.py"], "count": "lines",
                                                         "fixed": True}, "counts": "defects", "total": 2}}]

    def _accept_clamp(self, *, iteration=1, conflicts=None, pass_="first", coverage=None):
        (self.place / "judgment.json").write_text(json.dumps({"units": self.D_JUDGED}, ensure_ascii=False), encoding="utf-8")
        head = leftovers.snapshot(self.repo)
        path = self.repo / "stats.py"
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count("return lo"), 2, text)
        path.write_text(text.replace("    if x > hi:\n        return lo", "    if x > hi:\n        return hi"), encoding="utf-8")
        row = _fix_row(self.D_CLAMP, 1)
        row["closure"]["sites"][0]["path"] = "stats.py"
        row["coverage"].update(coverage or {})
        reply = {"changes": [] if conflicts else [row], "not_done": [], **({"conflicts": conflicts} if conflicts else {})}
        return self.b.accept_reply(reply, self.place, self.repo, pass_=pass_, iteration=iteration, owed=[self.D_CLAMP],
                                     judged=self.D_JUDGED, head=head, base_rev=self.rev, skip=SKIP)

    def test_unclosed_defects_count_goes_back_to_the_fixer(self):
        """欠陥を数える問いが直した後も 1 件を数える単位は、申し出が無ければ修正役に戻す（remaining を機械が埋めても受けない）。
        戻しの文は単位と query_hits_fixed の申し出を名指す。拒んだ返答の数え直しと閉鎖の表は置き場に置かない"""
        import querytest
        import recount
        got = self._accept_clamp()
        self.assertFalse(got["ok"], "閉じない欠陥の数えを申し出無しで受けた")
        texts = [r["text"] for r in got["rejects"] if r["check"] == "closure"]
        self.assertEqual(len(texts), 1, got["rejects"])
        self.assertIn(self.D_CLAMP, texts[0])
        self.assertIn("query_hits_fixed", texts[0])
        self.assertFalse((self.place / recount.COVERAGE_FILE).exists(), "拒んだ返答の数え直しを置き場に刻んだ")
        self.assertFalse((self.place / querytest.CLOSURE_FILE).exists(), "拒んだ返答の閉鎖の表を置き場に置いた")

    def test_uncountable_judge_query_goes_back_with_its_reason(self):
        """判定者の問いを修正後に数えられない単位は、修正役が狭めた問いの数でなく、数えられない理由を名指して戻す"""
        import recount
        run = recount._run_query

        def flaky(place, where, how, root, **kw):
            if how.get("patterns") == ["return lo"] and "修正後" in where:
                return None, "git grep が stderr に書いた"
            return run(place, where, how, root, **kw)
        narrow = {**self.D_JUDGED[0]["class_query"]["how"], "patterns": ["return lo  # none"]}
        with mock.patch.object(recount, "_run_query", flaky):
            got = self._accept_clamp(coverage={"how": narrow, "remaining": "判定者の問いは下限の正しい分岐にも当たるので狭めた"})
        texts = [r["text"] for r in got["rejects"] if r["check"] == "closure"]
        self.assertEqual(len(texts), 1, got["rejects"])
        self.assertIn("git grep が stderr に書いた", texts[0])
        self.assertNotIn("query_hits_fixed", texts[0], "数えられない単位に閉じない数えの文を返した")

    def test_unclosed_defects_count_with_query_hits_fixed_goes_to_the_ruling(self):
        """同じ木で正しい行を query_hits_fixed で名指した返答は、受け付けが単位を止めて裁定に回す"""
        got = self._accept_clamp(conflicts=[{
            "unit_key": self.D_CLAMP, "between": ["stats.py:10", "stats.py:12"],
            "why_both_cannot_hold": "判定の問い return lo は下限の正しい分岐にも当たり、正しく直しても 0 にならない",
            "which_is_right": "query", "kind": "query_hits_fixed", "correct_lines": ["        return lo"]}])
        self.assertTrue(got["ok"] and got["conflicted"], got)
        self.assertEqual(got["units"][self.D_CLAMP], {"status": "not_done", "reason": self.b.QUERY_PARKED},
                         "直してから申し出た単位を、直さずに裁定へ回したと書いた（#355）")

    def test_population_query_naming_the_branch_closes_the_same_text_fix(self):
        """欠陥の行と正しい行が同じ字（どちらも `return lo`）でも、裁定が分岐の条件の行を名指す population の問いに置き換えれば、
        例の試しを通り、上限の分岐だけを直した木で閉じる（#355。c38831c2 の裁定役が書けないとして人に回した置き換え）"""
        import conflict
        import querytest
        ruling = self.m.ruling
        claim = {"unit_key": self.D_CLAMP, "between": ["stats.py:10", "stats.py:12"],
                 "why_both_cannot_hold": "判定の問い return lo は下限の正しい分岐にも当たり、正しく直しても 0 にならない",
                 "which_is_right": "query", "kind": "query_hits_fixed", "correct_lines": ["        return lo"]}
        replaced = {"how": {"patterns": ["if x > hi:"], "paths": ["stats.py"], "count": "lines", "fixed": True},
                    "counts": "population", "hits": ["    if x > hi:"], "misses": ["    if x < lo:"]}
        decided = {"decision": conflict.REPLACE, "text": "上限の分岐の条件の行を名指す", "limits": [], "query": replaced}
        self.assertEqual(ruling.query_problems(decided, claim), [])
        conflict.park(self.place, [claim], source=conflict.FIX_SOURCE, ruling={**decided, "by": "test"})
        got = self._accept_clamp(pass_="ruled")
        self.assertTrue(got["ok"], got["reason"])
        rows = json.loads((self.place / querytest.CLOSURE_FILE).read_text(encoding="utf-8"))["rows"]
        self.assertEqual([(r["unit_key"], r["counts"], r["closed"]) for r in rows], [(self.D_CLAMP, "population", True)], rows)

    def test_query_hits_fixed_after_replace_query_tries_the_replaced_query(self):
        """裁定 replace_query の後の回は、閉鎖を数える問い（置き換えた問い）で申し出の correct_lines を試す。判定者の問いが当たらず、
        置き換えた問いが当たる正しい行の申し出は、拒まずに人に回す"""
        import conflict
        claim = {"unit_key": self.D_CLAMP, "between": ["stats.py:10", "stats.py:12"],
                 "why_both_cannot_hold": "判定の問い return lo は下限の正しい分岐にも当たり、正しく直しても 0 にならない",
                 "which_is_right": "query", "kind": "query_hits_fixed", "correct_lines": ["        return lo"]}
        replaced = {"how": {"patterns": ["return"], "paths": ["stats.py"], "count": "lines", "fixed": True},
                    "counts": "defects", "hits": ["        return lo"], "misses": []}
        conflict.park(self.place, [claim], source=conflict.FIX_SOURCE,
                      ruling={"decision": conflict.REPLACE, "text": "問いを置き換える", "limits": [], "by": "test",
                              "query": replaced})
        second = {**claim, "why_both_cannot_hold": "置き換えた問い return は上限の正しい分岐 return hi にも当たる",
                  "correct_lines": ["        return hi"]}
        got = self._accept_clamp(conflicts=[second], pass_="ruled")
        self.assertEqual(self._conflict_rejects(got), [], got)
        self.assertIn("ask_human", got["units"][self.D_CLAMP]["reason"], got)
        self.assertEqual([r["ruling"]["decision"] for r in conflict.items(self.place) if r["correct_lines"] == ["        return hi"]],
                         [conflict.ASK])

    def test_reverted_query_hits_fixed_fix_is_not_said_to_be_in_the_diff(self):
        """裁定の後の段の最後の回に、同じファイルの別の単位を止めて段の頭へ戻すと、人に回した query_hits_fixed の単位の直しも
        控えの patch へ移る。関所の行と単位の結末の理由は「直しは差分に在り」と言わず、控えの patch を名指す（#355）"""
        import conflict
        (self.place / self.b.JUDGMENT_FILE).write_text(json.dumps({"units": R_JUDGED}, ensure_ascii=False), encoding="utf-8")
        head = leftovers.snapshot(self.repo)
        path = self.repo / "stats.py"
        text = path.read_text(encoding="utf-8")
        for old, new in R_FIXED.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
        claim = {"unit_key": R_CLAMP, "between": ["stats.py:10", "stats.py:12"],
                 "why_both_cannot_hold": "判定の問い return lo は下限の正しい分岐にも当たり、正しく直しても 0 にならない",
                 "which_is_right": "query", "kind": "query_hits_fixed", "correct_lines": ["        return lo"]}
        reply = {"changes": [_fix_row(R_MEAN, 1), _fix_row(R_MEAN, 1)], "not_done": [], "conflicts": [claim]}
        got = self.b.accept_reply(reply, self.place, self.repo, pass_="ruled", iteration=rolekit.GIVE_UP_AFTER,
                                    owed=[R_MEAN, R_CLAMP], judged=R_JUDGED, head=head, base_rev=self.rev, skip=SKIP)
        self.assertEqual(got["units"][R_MEAN]["status"], "given_up", got)
        self.assertNotIn("return hi", path.read_text(encoding="utf-8"), "clamp の直しが作業ツリーに残った（場面が崩れた）")
        row = next(r for r in conflict.human_lines(self.place) if r.startswith(R_CLAMP))
        self.assertNotIn(conflict.FIX_IN_DIFF, row)
        self.assertIn(self.b.PARKED_PATCH, row)
        self.assertNotIn(conflict.FIX_IN_DIFF, conflict.held_by_rulings(self.place)[R_CLAMP])

    def _revert_after_head(self, park_clamp):
        """clamp の直しと人に回した query_hits_fixed の clamp の行（park_clamp が積む）を段の頭より前に置き、頭の後に mean を直して、
        裁定の後の段の最後の回に mean を止めて stats.py を段の頭へ戻す。返りは clamp の関所の行"""
        import conflict
        (self.place / self.b.JUDGMENT_FILE).write_text(json.dumps({"units": R_JUDGED}, ensure_ascii=False), encoding="utf-8")
        path = self.repo / "stats.py"
        old, new = list(R_FIXED.items())[1]
        path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
        park_clamp({"unit_key": R_CLAMP, "between": ["stats.py:10", "stats.py:12"],
                    "why_both_cannot_hold": "判定の問い return lo は下限の正しい分岐にも当たり、正しく直しても 0 にならない",
                    "which_is_right": "query", "kind": "query_hits_fixed", "correct_lines": ["        return lo"]},
                   {"decision": conflict.ASK, "text": "人が決める", "limits": [], "by": "test"})
        head = leftovers.snapshot(self.repo)
        old, new = list(R_FIXED.items())[0]
        path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
        reply = {"changes": [_fix_row(R_MEAN, 1), _fix_row(R_MEAN, 1)], "not_done": [], "conflicts": []}
        got = self.b.accept_reply(reply, self.place, self.repo, pass_="ruled", iteration=rolekit.GIVE_UP_AFTER,
                                    owed=[R_MEAN], judged=R_JUDGED, head=head, base_rev=self.rev, skip=SKIP)
        self.assertEqual(got["units"][R_MEAN]["status"], "given_up", got)
        self.assertIn("return hi", path.read_text(encoding="utf-8"), "段の頭より前の clamp の直しが戻った（場面が崩れた）")
        return next(r for r in conflict.human_lines(self.place) if r.startswith(R_CLAMP))

    def test_revert_keeps_fix_in_diff_for_first_pass_rows(self):
        """1 回目の段に積んだ query_hits_fixed の行の直しは裁定の後の段の頭の木に在り、機械が同じファイルを段の頭へ戻しても差分に
        残る。関所の行は「直しは差分に在り」のままで、控えの patch を名指さない（#355）"""
        import conflict
        row = self._revert_after_head(lambda claim, ruling: conflict.park(self.place, [claim], source=conflict.FIX_SOURCE,
                                                                           ruling=ruling))
        self.assertIn(conflict.FIX_IN_DIFF, row)
        self.assertNotIn(self.b.PARKED_PATCH, row)

    def test_revert_keeps_fix_in_diff_for_rows_copied_from_the_prior_stage(self):
        """adopt_prior が写した前の修正の段の行（PRIOR）も、直しは段の頭の木に在る。戻しても控えの patch を名指さない（#355）"""
        import conflict
        prior = self.tmp / "prior-place"
        prior.mkdir()

        def park_clamp(claim, ruling):
            conflict.park(prior, [claim], source=conflict.FIX_SOURCE, ruling=ruling, pass_="ruled")
            conflict.adopt_prior(self.place, prior, [])
        row = self._revert_after_head(park_clamp)
        self.assertIn(conflict.FIX_IN_DIFF, row)
        self.assertNotIn(self.b.PARKED_PATCH, row)

    def test_ruled_pass_asked_unit_reason_says_where_the_fix_is_by_kind(self):
        """裁定の後の段の単位の結末（fix-units.json に写る units）も、人に回した query_hits_fixed の単位は「直しは差分に在り」と
        書き、ほかの種類の単位には書かない（1 回目の段の QUERY_PARKED と同じ分け。#355）"""
        import conflict
        asked = {"decision": conflict.ASK, "text": "人が決める", "limits": [], "by": "test"}
        conflict.park(self.place, [{"unit_key": R_CLAMP, "between": ["stats.py:10", "stats.py:12"],
                                    "why_both_cannot_hold": "判定の問い return lo は下限の正しい分岐にも当たる",
                                    "which_is_right": "query", "kind": "query_hits_fixed",
                                    "correct_lines": ["        return lo"]}], source=conflict.FIX_SOURCE, ruling=asked)
        conflict.park(self.place, [self._claim()], source=conflict.FIX_SOURCE, ruling=asked)
        got = self._accept_claims([], pass_="ruled")
        self.assertTrue(got["ok"], got["reason"])
        self.assertEqual({k: v["status"] for k, v in got["units"].items()}, {R_MEAN: "not_done", R_CLAMP: "not_done"}, got)
        self.assertIn(conflict.FIX_IN_DIFF, got["units"][R_CLAMP]["reason"])
        self.assertNotIn(conflict.FIX_IN_DIFF, got["units"][R_MEAN]["reason"])

    def test_first_pass_conflict_rows_carry_no_filed_in(self):
        """#369: 1 回目の段の受け付けが積んだ申し出の行は、積んだ段の欄 FILED_IN を持たない（読むのは裁定の後の段の
        mark_reverted だけ）。park が受ける段は ruled だけ"""
        import conflict
        got = self._accept_claims([self._claim()])
        self.assertTrue(got["conflicted"], got)
        self.assertEqual([conflict.FILED_IN in r for r in conflict.items(self.place)], [False])
        with self.assertRaises(ValueError):
            conflict.park(self.place, [self._claim()], source=conflict.FIX_SOURCE, pass_="first")

    def test_first_pass_parked_reason_says_fix_in_diff_only_for_query_hits_fixed_alone(self):
        """1 回目の段で裁定へ回した単位の理由は、裁かれていない申し出が query_hits_fixed だけの単位だけ QUERY_PARKED。
        unnamed_test_broke の単位も、query_hits_fixed とほかの種類が混ざる単位も PARKED_FOR_RULING（#355）"""
        import conflict
        got = self._accept_claims([self._claim()])
        self.assertTrue(got["conflicted"], got)
        self.assertEqual(got["units"][R_MEAN], {"status": "not_done", "reason": self.b.PARKED_FOR_RULING})
        conflict.park(self.place, [self._claim("stats.py:9", "stats.py:10", which_is_right="query", kind="query_hits_fixed",
                                               correct_lines=["    return sum(xs) / len(xs)"])], source=conflict.FIX_SOURCE)
        self.assertEqual(self.b.parked_reasons(self.place, [R_MEAN]), {R_MEAN: self.b.PARKED_FOR_RULING})

    def test_unclosed_defects_count_on_the_last_round_stops_the_unit(self):
        """最後の回まで申し出が無ければ、その単位を止めて人に回す（閉じない数えのまま受けて round_limit で終えない）"""
        import conflict
        got = self._accept_clamp(iteration=rolekit.GIVE_UP_AFTER)
        self.assertEqual(got["units"][self.D_CLAMP]["status"], "given_up", got)
        self.assertEqual([r["unit_key"] for r in conflict.items(self.place)], [self.D_CLAMP])

    def test_accept_reply_passes_the_judged_precedents_to_the_recount(self):
        """判定の写しの precedents に在る単位の from_judge_row は通る（判定の写しを数え直しに渡す。元 review-loop.py の
        precedent.from_judge_row の照らし）"""
        reply = _fix_ok()
        reply["changes"][0]["precedent"] = {"from_judge_row": True, "verdict": "adopt", "reason": "判定者の行"}
        got = self._accept_fixed(reply, precedents=[{"key": R_MEAN}])
        self.assertTrue(got["ok"], got["reason"])

    # ---- 食い違いの申し出の道（take_conflicts）を accept_reply から通す（元 works/tests/test_blk_fix_conflict.py の写し）
    def _claim(self, *cites, **over):
        return {"unit_key": R_MEAN, "between": list(cites or ("stats.py:9", "test_stats.py:9")),
                "why_both_cannot_hold": "テストは分母 len(xs) - 1 の値を期待しているが、依頼は算術平均を求めている",
                "which_is_right": "request", "kind": "unnamed_test_broke", **over}

    def _accept_claims(self, conflicts, *, pass_="first", iteration=1, judgment=True, changes=()):
        """判定の写し（R_JUDGED。judgment が偽なら置かない）の置き場で、申し出 conflicts を持つ返答を受け付けに通す"""
        if judgment:
            (self.place / self.b.JUDGMENT_FILE).write_text(json.dumps({"units": R_JUDGED}, ensure_ascii=False), encoding="utf-8")
        head = leftovers.snapshot(self.repo)
        return self.b.accept_reply({"changes": list(changes), "conflicts": conflicts}, self.place, self.repo, pass_=pass_,
                                     iteration=iteration, owed=[R_MEAN, R_CLAMP], judged=R_JUDGED, head=head,
                                     base_rev=self.rev, skip=SKIP)

    def _conflict_rejects(self, got) -> list:
        return [r["text"] for r in got["rejects"] if r["check"] == "conflict"]

    def test_fake_citation_is_a_normal_reject(self):
        """F202: 名指しの行がファイルに無い・無いファイルの申し出は普通の拒否（check conflict。3 回の枠に数える）で、置き場の
        conflicts.json に積まない。依頼の行（run の依頼のファイルの絶対パス:行）は名指せ、行が無ければ拒む（元
        test_blk_fix_conflict.py:141 test_fake_citation_is_a_normal_reject・:162 test_request_line_citation_resolves）"""
        import conflict
        got = self._accept_claims([self._claim("stats.py:900", "no_such_test.py:1")])
        self.assertEqual((got["ok"], got["conflicted"]), (False, False), got)
        bad = " ".join(self._conflict_rejects(got))
        for w in ("stats.py:900", "行がファイルに無い", "no_such_test.py:1", "ファイルが無い"):
            self.assertIn(w, bad)
        self.assertEqual(conflict.items(self.place), [], "拒んだ申し出は積まない")
        req = self.tmp / "request.json"
        req.write_text('{"request": "平均を直す"}\n', encoding="utf-8")
        self.m.runvals.write(self.place, {"request_file": str(req)})
        got = self._accept_claims([self._claim(f"{req}:999", "test_stats.py:9")], iteration=2)
        self.assertFalse(got["ok"], got)
        self.assertIn("行がファイルに無い", " ".join(self._conflict_rejects(got)))
        got = self._accept_claims([self._claim(f"{req}:1", "test_stats.py:9")], iteration=3)
        self.assertEqual((got["ok"], got["conflicted"]), (True, True), got)
        self.assertEqual([r["unit_key"] for r in conflict.unruled(self.place)], [R_MEAN])

    def test_fixer_query_claim_tries_the_judge_query(self):
        """F205: 修正役の which_is_right: query の申し出も、置き場の判定の写し judgment.json の単位の class_query を correct_lines に
        当てて試す。当たらなければ拒み、当たれば積む。判定の写しが読めなければ「読めない」と名指して拒む（黙って試さずに通さない）
        （元 works/blk-fix/scripts/accept.py:325-326 の try_query。元 test_blk_fix_conflict.py:470 の修正役の版）"""
        import conflict
        query = dict(which_is_right="query", kind="query_hits_fixed")
        got = self._accept_claims([self._claim(**query, correct_lines=["    return sum(xs) / len(xs)"])])
        self.assertEqual((got["ok"], got["conflicted"]), (False, False), got)
        self.assertIn("どの行にも当たらない", " ".join(self._conflict_rejects(got)))
        self.assertEqual(conflict.items(self.place), [])
        (self.place / "judgment.json").unlink()
        got = self._accept_claims([self._claim(**query, correct_lines=["    return sum(xs) / (len(xs) - 1)"])],
                                  iteration=2, judgment=False)
        self.assertFalse(got["ok"], got)
        self.assertIn("judgment.json が読めない", " ".join(self._conflict_rejects(got)))
        got = self._accept_claims([self._claim(**query, correct_lines=["    return sum(xs) / (len(xs) - 1)"])], iteration=2)
        self.assertEqual((got["ok"], got["conflicted"]), (True, True), got)
        self.assertEqual([r["which_is_right"] for r in conflict.unruled(self.place)], ["query"])

    def test_resent_claim_on_a_ruled_unit_is_dropped(self):
        """F206: 裁定がもう外した単位（conflict.held_by_rulings）の申し出は、出し直されても知っている申し出として確かめずに外し、
        積み増さない（名指しが現物に無くても拒否の行にしない）（元 test_blk_fix_conflict.py:339
        test_resent_conflict_on_parked_unit_does_not_halt_last_round）"""
        import conflict
        conflict.park(self.place, [self._claim()], source=conflict.FIX_SOURCE,
                      ruling={"decision": conflict.ASK, "text": self.b.SECOND_CONFLICT, "limits": [],
                              "by": self.b.FIX_ACCEPT_BY})
        self.assertIn(R_MEAN, conflict.held_by_rulings(self.place))
        again = self._claim("stats.py:900", "test_stats.py:9", why_both_cannot_hold="裁定の後にもう一度、同じ単位を申し出た")
        got = self._accept_claims([again], pass_="ruled", iteration=2)
        self.assertEqual(self._conflict_rejects(got), [], got["rejects"])
        self.assertFalse(got["conflicted"])
        self.assertEqual([(r["unit_key"], r["ruling"]["decision"]) for r in conflict.items(self.place)], [(R_MEAN, conflict.ASK)],
                         "積み増さない")

    def test_consult_after_budget_is_rejected_and_dropped(self):
        """範囲の相談の周でない回に来た consult は枠を使い切った後の物: 確かめ consult の行で拒み、欄を外した返答を後の確かめに
        当てる（元 works/blk-fix/scripts/accept.py:629-631。元の試験 works/tests/test_fix_precheck.py:145・test_fix_lanes.py:223）"""
        import conflict
        consult = self.m.consult
        ask = [{"item": 1, "paths": ["docs/n.md"], "tests": [], "why": "直しに伴う記録を残す要が在る（範囲の外）"}]
        got = self._accept_fixed({**_fix_ok(), conflict.CONSULT_FIELD: ask})
        self.assertFalse(got["ok"], got)
        self.assertEqual(got["rejects"], [{"check": "consult", "text": self.b.CONSULT_SPENT.format(n=consult.BUDGET)}])
        self.assertNotIn(conflict.CONSULT_FIELD, got["reply"])
        self.assertEqual(len(got["reply"]["changes"]), 2, "欄を外した返答を後の確かめに当てた")

    def _hold_clamp(self) -> str:
        """R_CLAMP を ask_human の裁定で直す義務から外し（conflict.held_by_rulings）、外れた理由を返す"""
        import conflict
        conflict.park(self.place, [{"unit_key": R_CLAMP, "between": [], "why_both_cannot_hold": "上限を超えた値の扱いを人が決める",
                                    "which_is_right": conflict.UNKNOWN, "kind": conflict.NEEDS_CONTEXT}],
                      source=conflict.FIX_SOURCE, ruling={"decision": conflict.ASK, "text": "人が決める", "limits": [], "by": "t"})
        self.b.write_rulings(self.place)
        return self.b.fix_duty(self.place, [R_MEAN, R_CLAMP])[1][R_CLAMP]

    def _held_turns(self, held_files: dict):
        """判定の写しを置き、段の頭の木を控えてから MEAN を直し、外れた単位 CLAMP の直し held_files {パス: 中身} を書く。返りは
        受け付けを回す口 accept(返答, iteration)"""
        (self.place / self.b.JUDGMENT_FILE).write_text(json.dumps({"units": R_JUDGED}, ensure_ascii=False), encoding="utf-8")
        head = leftovers.snapshot(self.repo)
        path = self.repo / "stats.py"
        path.write_text(path.read_text(encoding="utf-8").replace("sum(xs) / (len(xs) - 1)", "sum(xs) / len(xs)"),
                        encoding="utf-8")
        for rel, text in held_files.items():
            (self.repo / rel).write_text(text, encoding="utf-8")

        def accept(reply, iteration):
            return self.b.accept_reply(reply, self.place, self.repo, pass_="first", iteration=iteration,
                                         owed=[R_MEAN, R_CLAMP], judged=R_JUDGED, head=head, base_rev=self.rev, skip=SKIP)
        return accept

    def _held_row(self, files):
        return {"unit_key": R_CLAMP, "what": "上限の枝を直した", "files": files, **SELF_REPORT}

    def test_accept_reply_rejects_duplicate_unknown_and_excused_rows(self):
        """受け付けは単位の行を照らす: 同じ unit_key の 2 行・義務にも外れにも無い key・外れた単位の行（外れた理由を名指す）。
        元 works/blk-fix/scripts/accept.py:664-672（元の試験 works/tests/test_fix_duty.py:148・:193）"""
        why = self._hold_clamp()
        accept = self._held_turns({"held.txt": "上限の枝\n", "made-up.txt": "x\n"})
        reply = {"changes": [_fix_row(R_MEAN, 1), _fix_row(R_MEAN, 1), {**_fix_row("作り話の単位", 0), "files": ["made-up.txt"]},
                             self._held_row(["held.txt"])], "not_done": []}
        got = accept(reply, 1)
        self.assertFalse(got["ok"], got)
        rows = [(r["check"], r["text"]) for r in got["rejects"] if r["check"] in ("duplicate", "not_opened", "excused")]
        self.assertEqual(rows, [("duplicate", self.b.DUPLICATE + R_MEAN), ("not_opened", self.b.NOT_OPENED + "作り話の単位"),
                                ("excused", f"{self.b.EXCUSED}{R_CLAMP}（{why}）")])
        self.assertNotIn(self.b.NOT_OPENED + R_CLAMP, got["reason"], "外れた単位は作り話の key と分けて名指す")

    def test_last_turn_drops_only_the_excused_row(self):
        """最後の回: 外れた単位にだけ結んだ拒否の行は数えず、その単位の行を changes から外して残りで受ける。外れた単位の直しは
        作業ツリーに残し、ほかの単位を止めない（trace に ABSORBED_OP）。元 works/blk-fix/scripts/accept.py:636-645・:725-726
        （元の試験 works/tests/test_fix_duty.py:157 test_last_round_drops_only_the_excused_unit・:167 の bash_writes の申告）"""
        import conflict
        why = self._hold_clamp()
        accept = self._held_turns({"held.txt": "上限の枝\n", "held-gen.txt": "生成\n"})
        reply = {"changes": [_fix_row(R_MEAN, 1), self._held_row(["held.txt"])], "not_done": [],
                 "bash_writes": [{"path": "held-gen.txt", "why": WHY}]}
        excused = f"{self.b.EXCUSED}{R_CLAMP}（{why}）"
        got = accept(reply, 1)
        self.assertEqual((got["ok"], got["rejects"]), (False, [{"check": "excused", "text": excused}]), got)
        got = accept(reply, 3)
        self.assertTrue(got["ok"], got["reason"])
        self.assertEqual([c["unit_key"] for c in got["reply"]["changes"]], [R_MEAN])
        self.assertEqual(got["parked"], {})
        self.assertEqual(got["units"], {R_MEAN: {"status": "fixed", "reason": ""}, R_CLAMP: {"status": "not_done", "reason": why}})
        self.assertIn("sum(xs) / len(xs)", (self.repo / "stats.py").read_text(encoding="utf-8"), "残りの単位の直しを戻さない")
        self.assertEqual((self.repo / "held.txt").read_text(encoding="utf-8"), "上限の枝\n", "外れた単位の直しは作業ツリーに残す")
        self.assertEqual([r["unit_key"] for r in conflict.items(self.place)], [R_CLAMP], "新しく止めた単位は無い")
        rows = [r for r in _traced(self.place) if r["op"] in (self.b.ABSORBED_OP, conflict.ACCEPT_PARKED_OP)]
        self.assertEqual([(r["op"], r["dropped"], r["absorbed"]) for r in rows], [(self.b.ABSORBED_OP, [R_CLAMP], [excused])])

    def test_last_turn_parks_the_duplicate_and_absorbs_the_excused_row(self):
        """最後の回: 重なりの行は MEAN に結んで止め（stats.py を戻す）、外れた単位の行は数えずに行だけを外す（held.txt は戻さない）。
        元の試験 works/tests/test_fix_duty.py:181 test_last_round_duplicate_parks_and_excused_row_is_absorbed"""
        import conflict
        self._hold_clamp()
        accept = self._held_turns({"held.txt": "上限の枝\n"})
        reply = {"changes": [_fix_row(R_MEAN, 1), self._held_row(["held.txt"]), _fix_row(R_MEAN, 1)], "not_done": []}
        got = accept(reply, 3)
        self.assertTrue(got["ok"], got["reason"])
        self.assertEqual((got["reply"]["changes"], list(got["parked"])), ([], [R_MEAN]))
        self.assertIn("(len(xs) - 1)", (self.repo / "stats.py").read_text(encoding="utf-8"), "止めた単位の直しは戻した")
        self.assertTrue((self.repo / "held.txt").is_file(), "外れた単位の直しは戻さない")
        self.assertEqual([r["unit_key"] for r in conflict.items(self.place)], [R_CLAMP, R_MEAN])
        self.assertEqual([r["dropped"] for r in _traced(self.place) if r["op"] == self.b.ABSORBED_OP], [[R_CLAMP]])

    def test_last_turn_without_bound_unit_parks_the_rest_or_gives_up(self):
        """最後の回に止める単位が残らないのに写しの拒否が残れば（外れた単位の足跡の Markdown のリンクが届かない）、義務の残りを
        全部止めて通し直し（parking.park_owed）、それでも残れば受けずに諦める（NOT_SETTLED）。元 works/blk-fix/scripts/accept.py:738-740
        （止めた後に残れば元は機械の空の返答 hand_empty を渡した。今は受けずに諦める）"""
        import conflict
        parking = self.m.parking
        self._hold_clamp()
        accept = self._held_turns({"held.md": "# 覚え\n\n[無い](gone.md)\n"})
        reply = {"changes": [_fix_row(R_MEAN, 1), self._held_row(["held.md"])], "not_done": []}
        got = accept(reply, 3)
        self.assertFalse(got["ok"], got)
        self.assertTrue(got["reason"].startswith(self.b.NOT_SETTLED), got["reason"])
        self.assertIn("gone.md", got["reason"])
        self.assertEqual(list(got["parked"]), [R_MEAN], "義務の残りを全部止めた")
        self.assertEqual(got["units"][R_MEAN]["status"], "given_up")
        self.assertIn(parking.OUT_ONLY, got["parked"][R_MEAN])
        self.assertIn("(len(xs) - 1)", (self.repo / "stats.py").read_text(encoding="utf-8"), "止めた単位の直しは戻した")
        self.assertTrue((self.repo / "held.md").is_file(), "外れた単位の直しは戻さない")
        self.assertEqual([r["unit_key"] for r in conflict.items(self.place)], [R_CLAMP, R_MEAN])

    def test_pack_copy_change_is_rejected(self):
        """除くパスの頭（script が渡す実行基盤の工程の写しの置き場。ここでは SKIP）の下を changes[].files に申告した・修正の段の
        頭の控え（record_skipped）から中身を変えた・足した・消した返答を拒む。触れなければ通る。元 works/blk-fix/scripts/accept.py:234
        check_pack_copy・:663（元の試験 works/tests/test_blk_fix.py:1154-1175）"""
        copy = self.repo / "vendored" / "workflows" / "x.yaml"
        copy.parent.mkdir(parents=True)
        copy.write_text("a: 1\n", encoding="utf-8")
        self.b.record_skipped(self.place, self.repo, SKIP)
        (self.place / self.b.JUDGMENT_FILE).write_text(json.dumps({"units": R_JUDGED}, ensure_ascii=False), encoding="utf-8")
        head = leftovers.snapshot(self.repo)
        path = self.repo / "stats.py"
        text = path.read_text(encoding="utf-8")
        for old, new in R_FIXED.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")

        def accept(reply):
            return self.b.accept_reply(reply, self.place, self.repo, pass_="first", iteration=1, owed=[R_MEAN, R_CLAMP],
                                         judged=R_JUDGED, head=head, base_rev=self.rev, skip=SKIP)
        declared = _fix_ok()
        declared["changes"][0]["files"].append("vendored/workflows/x.yaml")
        got = accept(declared)
        self.assertFalse(got["ok"], got)
        packs = [r["text"] for r in got["rejects"] if r["check"] == "pack"]
        self.assertEqual(len(packs), 1, got["rejects"])
        self.assertIn("vendored/workflows/x.yaml", packs[0])
        self.assertIn("vendored/", packs[0])
        copy.write_text("a: 2\n", encoding="utf-8")
        (copy.parent / "added.txt").write_text("x\n", encoding="utf-8")
        got = accept(_fix_ok())
        packs = [r["text"] for r in got["rejects"] if r["check"] == "pack"]
        self.assertEqual(len(packs), 1, got["rejects"])
        for word in ("vendored/workflows/x.yaml", "vendored/workflows/added.txt", "戻"):
            self.assertIn(word, packs[0])
        copy.unlink()
        (copy.parent / "added.txt").unlink()
        packs = [r["text"] for r in accept(_fix_ok())["rejects"] if r["check"] == "pack"]
        self.assertEqual(len(packs), 1, "消した写しも拒む")
        self.assertIn("vendored/workflows/x.yaml", packs[0])
        copy.write_text("a: 1\n", encoding="utf-8")
        self.assertTrue(accept(_fix_ok())["ok"], "前から在る写しに触れない修正は通る")


class OverflowTraceSeamCase(SeamTemp):
    """受けた回の impact.ACCEPT_OVERFLOW_OP の行（board.overflow_trace。元 works/blk-fix/scripts/accept.py:715）が、守りのテストと
    関所の条件の相談で認めた新しいテストを元と同じ字で名指す"""

    GATE_ID = "test_stats.py::TestStats::test_mean_of_three"   # 種の今の木に在る
    GONE_ID = "test_stats.py::TestStats::test_not_written"

    def overflow_rows(self, attempt=1):
        import impact
        self.b.overflow_trace(self.place, {"reverted": []}, self.repo, pass_="first", attempt=attempt)
        return [r for r in _traced(self.place) if r["op"] == impact.ACCEPT_OVERFLOW_OP]

    def test_nothing_to_name_writes_no_row(self):
        self.assertEqual(self.overflow_rows(), [])

    def test_accepted_guard_test_is_named_in_the_overflow_trace(self):
        fixgates = self.m.gates
        import impact
        (self.place / fixgates.LEDGER).write_text(json.dumps({"rows": [], "skipped": [], "guards": [
            {"pass": "first", "attempt": 1, "id": self.GATE_ID, "base": "passed"},
            {"pass": "first", "attempt": 2, "id": self.GONE_ID, "base": "passed"}]}), encoding="utf-8")
        (row,) = self.overflow_rows()
        self.assertEqual(row["guards"], [f"{self.GATE_ID}: 守りのテスト（base で passed）"])
        self.assertEqual((row["agreed"], row["reverted"], row["gate_tests"]), ([], [], []))
        self.assertEqual(set(row) - {"op", "node"}, set(impact.ACCEPT_OVERFLOW_KEYS), "行の鍵は impact の定数が持つ")

    def asked(self, *grants):
        import conflict
        for i, (origin, tid) in enumerate(grants, 1):
            self.b.trace(self.place, conflict.ASKED_OP, id=i, item="1", status="answered", decision="allow", origin=origin,
                           granted_paths=[], granted_tests=[], granted_new_tests=[{"id": tid, "red_kind": "assertion"}],
                           reason="足してよい")

    def test_gate_agreed_new_test_is_named_in_the_overflow_trace(self):
        consult = self.m.consult
        self.asked((consult.ORIGIN_GATE, self.GATE_ID), (consult.ORIGIN_GATE, self.GONE_ID))
        (row,) = self.overflow_rows()
        self.assertEqual(row["gate_tests"], [f"{self.GATE_ID}（assertion）"], "今の木に無いテストは名指さない")
        self.assertEqual((row["agreed"], row["reverted"], row["guards"]), ([], [], []))

    def test_accept_agreed_test_is_not_a_gate_test(self):
        consult = self.m.consult
        self.asked((consult.ORIGIN_ACCEPT, self.GATE_ID))
        (row,) = self.overflow_rows()
        self.assertEqual((row["agreed"], row["gate_tests"]), ([1], []))


class OverflowRowCase(SeamTemp):
    """はみ出しの trace の行の鍵の正本は impact の行の形。fix の board.overflow_trace は値を選び、lib の fixboard.overflow_trace に名で
    渡す（元 lib/tests/test_impact.py の OverflowRowCase。lib の書き手は値を受ける形になった）"""

    def written_row(self):
        import conflict
        import fixboard
        consult, gates = self.m.consult, self.m.gates
        rows = [{"origin": consult.ORIGIN_ACCEPT, "id": "合意"},
                {"origin": consult.ORIGIN_GATE, "granted_new_tests": [{"id": "関所の試験", "red_kind": "assertion"}]}]
        written = []
        with mock.patch.object(conflict, "agreed", return_value=rows), \
                mock.patch.object(gates, "present", return_value=True), \
                mock.patch.object(gates, "guards", return_value=[{"id": "守り", "base": "passed"}]), \
                mock.patch.object(fixboard, "trace", lambda place, op, **row: written.append(row)):
            self.b.overflow_trace("盤面", {"reverted": ["戻した"]}, "木", pass_="first", attempt=1)
        (row,) = written
        return row

    def test_values_bind_to_keys_by_name(self):
        import impact
        want = {"agreed": ["合意"], "reverted": ["戻した"], "guards": ["守り: 守りのテスト（base で passed）"],
                "gate_tests": ["関所の試験（assertion）"]}
        self.assertEqual({k: self.written_row()[k] for k in impact.ACCEPT_OVERFLOW_KEYS}, want)
        with mock.patch.object(impact, "ACCEPT_OVERFLOW_KEYS", tuple(reversed(impact.ACCEPT_OVERFLOW_KEYS))):
            self.assertEqual({k: self.written_row()[k] for k in want}, want, "鍵の並びの順は値の行き先を変えない")


class WritesLogNameCase(SeamTemp):
    """書き込みの記録の名の持ち主は writelog.LOG の 1 か所。fix の受け付けの既定の置き場はその名を引き、src にほかの写しの字が無い
    （元 lib/tests/test_writes.py の WritesLogNameCase。block の src の字を照らす）"""

    def test_default_record_name_is_writelog_log(self):
        import writelog
        import writes
        seen = []

        def check(reply, repo, paths, log, **kw):
            seen.append(pathlib.Path(log))
            return {"problems": ["止める"], "reply": reply}

        with mock.patch.object(writelog, "LOG", "renamed.jsonl"), mock.patch.object(writes, "check", check), \
                mock.patch.object(writes, "changed", return_value=[]):
            self.m.facts.check_writes({}, self.place, "HEAD", self.place, "")
        self.assertEqual([p.name for p in seen], ["renamed.jsonl"])

    def test_no_second_copy_of_the_record_name_in_src(self):
        copies = []
        for path in sorted((kit.BLOCKS / "fix" / "src").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            docs = {id(n.body[0].value) for n in ast.walk(tree)
                    if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body
                    and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
            copies += [f"{path.name}:{n.lineno} {n.value!r}" for n in ast.walk(tree)
                       if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs
                       and "writes" in n.value and n.value.endswith(".jsonl")]
        self.assertEqual(copies, [], "書き込みの記録の名は writelog.LOG を引く")


class ParkingSkipCase(SeamTemp):
    """parking の除くパスの頭（引数 skip。既定 () では除かない）。元 lib/tests/test_fix_seams.py の SmallGapsSeamCase"""

    SKIP = ("vendored/",)

    def test_parking_ours_skips_only_the_given_heads(self):
        parking = self.m.parking
        self.assertTrue(parking._ours("vendored/x.py"), "既定の () では除かない")
        self.assertFalse(parking._ours("vendored/x.py", self.SKIP))
        self.assertFalse(parking._ours("vendored", self.SKIP), "頭のフォルダそのものも除く")
        self.assertTrue(parking._ours("vendoredx/x.py", self.SKIP), "頭の字で始まるだけの別のフォルダは除かない")
        self.assertTrue(parking._ours("stats.py", self.SKIP))

    def test_parking_footprint_and_settle_pass_the_skip(self):
        parking = self.m.parking
        rows = [{"unit_key": "a", "files": ["stats.py", "vendored/copy.py"]}]
        self.assertEqual(parking.footprint(rows, [], "/home/x/repo"), {"a": {"stats.py", "vendored/copy.py"}})
        feet = parking.footprint(rows, [], "/home/x/repo", self.SKIP)
        self.assertEqual(feet, {"a": {"stats.py"}})
        both = {"a": {"stats.py", "vendored/copy.py"}}
        args = dict(keys={"a"}, feet=both, reached={}, owed={"a"}, out_of_duty=set(), changed=set())
        self.assertEqual(parking.settle(["a: 落ちた"], **args).files, {"stats.py", "vendored/copy.py"})
        got = parking.settle(["a: 落ちた"], **args, skip=self.SKIP)
        self.assertEqual((set(got.park), got.files), ({"a"}, {"stats.py"}))
        owed = parking.park_owed(["写しの行"], feet=both, owed={"a"}, out_of_duty=set(), skip=self.SKIP)
        self.assertEqual((set(owed.park), owed.files), ({"a"}, {"stats.py"}))


class SinceCase(SeamTemp):
    """修正の段の受け付けと事前の確かめの since: 見る変更は since の木からの物だけで、その前の変更を範囲と出どころで照らさない。since の後に
    自分の out_of_scope を触れば今どおり拒む（元 lib/tests/test_fix_seams.py の LaneChecksSeamCase。元 works/tests/test_fix_lanes.py の
    TestItemStartPoint の test_second_item_is_checked_from_its_own_start・test_second_item_touching_its_own_out_of_scope_is_still_rejected）"""

    def record(self, log, path):
        import writes
        real = os.path.realpath(path)
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"tool_name": "Write", "path": real, "file_sha": writes._sha(real)}) + "\n")

    def since_case(self):
        """1 つ目の項目の直し（test_stats.py に行を足し、新しい NOTES.md を作る。記録は無い）の後の木を since に取り、
        2 つ目の項目の直し（stats.py）を足す。2 つ目の項目は NOTES.md と test_stats.py を out_of_scope に持つ"""
        import leftovers
        tests = self.repo / "test_stats.py"
        tests.write_text(tests.read_text(encoding="utf-8") + "# 項目 1 の注記\n", encoding="utf-8")
        (self.repo / "NOTES.md").write_text("項目 1 の記録\n", encoding="utf-8")
        since = leftovers.snapshot(self.repo)
        stats = self.repo / "stats.py"
        text = stats.read_text(encoding="utf-8")
        for old, new in R_FIXED.items():
            text = text.replace(old, new)
        stats.write_text(text, encoding="utf-8")
        item = {"item": 2, "unit_keys": [R_MEAN], "files": [], "route": "direct", "tests": [],
                "rewrite_tests": [], "allowed_paths": ["stats.py"],
                "out_of_scope": [{"glob": "NOTES.md", "why": "記録は項目 2 では触らない"},
                                 {"glob": "test_stats.py", "why": "試験は項目 2 では触らない"}]}
        reply = {"changes": [{"unit_key": R_MEAN, "files": ["stats.py"]}]}
        return self.m.facts, since, item, reply

    def test_plan_scope_looks_only_after_since(self):
        fc, since, item, reply = self.since_case()
        args = (reply, [R_MEAN], self.place, self.rev, self.repo, "", "first")
        lines, _ = fc.check_plan_scope(*args, items=[item])
        self.assertTrue(any("NOTES.md" in t for t in lines), "since が無ければ版からの変更を全部照らす")
        lines, _ = fc.check_plan_scope(*args, since=since, items=[item])
        self.assertEqual(lines, [], "since の前の変更は照らさない")
        (self.repo / "NOTES.md").write_text("項目 2 が書き足した\n", encoding="utf-8")
        lines, _ = fc.check_plan_scope(*args, since=since, items=[item])
        self.assertTrue(any("NOTES.md" in t for t in lines), lines)
        self.assertFalse(any("test_stats.py" in t for t in lines), "since の前に変えたファイルは照らさない")

    def test_plan_scope_asks_about_every_change_after_since(self):
        """since の後に版の中身へ戻した・since の前に作ったファイルを消した・読めない（UTF-8 でない）ファイルを書いた変更も、
        版からの差分に残らなくても out_of_scope で照らす"""
        fc, since, item, reply = self.since_case()
        args = (reply, [R_MEAN], self.place, self.rev, self.repo, "", "first")
        git(self.repo, "checkout", self.rev, "--", "test_stats.py")
        (self.repo / "NOTES.md").unlink()
        (self.repo / "NOTES.bin").write_bytes(b"\xff\xfe\x00bad")
        item["out_of_scope"].append({"glob": "NOTES.bin", "why": "記録は項目 2 では触らない"})
        lines, _ = fc.check_plan_scope(*args, since=since, items=[item])
        for path in ("test_stats.py", "NOTES.md", "NOTES.bin"):
            self.assertTrue(any(f"{path} は項目 2 の out_of_scope" in t for t in lines), (path, lines))

    def test_plan_scope_skips_a_file_deleted_before_since(self):
        """版に在り since の前に消えたファイルは、since の後に触っていなければ後の項目の out_of_scope で照らさない（run 97fd532f）"""
        (self.repo / "LEGACY.md").write_text("古い記録\n", encoding="utf-8")
        git(self.repo, "add", "LEGACY.md")
        git(self.repo, "commit", "-q", "-m", "legacy")
        self.rev = git(self.repo, "rev-parse", "HEAD")
        (self.repo / "LEGACY.md").unlink()
        fc, since, item, reply = self.since_case()
        item["out_of_scope"].append({"glob": "LEGACY.md", "why": "記録は項目 2 では触らない"})
        lines, _ = fc.check_plan_scope(reply, [R_MEAN], self.place, self.rev, self.repo, "", "first", since=since, items=[item])
        self.assertEqual(lines, [])

    def test_plan_scope_skips_untouched_binary_and_crlf_files_written_before_since(self):
        """since の前に書いた UTF-8 でない・CRLF のファイルも、since の後に触っていなければ後の項目の out_of_scope で照らさない
        （触ったかは git の比べで決める。読み方の違う 2 つの文字列を比べない）"""
        (self.repo / "IMG.bin").write_bytes(b"\xff\xfe\x00img")
        (self.repo / "WIN.md").write_bytes(b"line one\r\nline two\r\n")
        fc, since, item, reply = self.since_case()
        item["out_of_scope"] += [{"glob": "IMG.bin", "why": "項目 2 では触らない"}, {"glob": "WIN.md", "why": "項目 2 では触らない"}]
        lines, _ = fc.check_plan_scope(reply, [R_MEAN], self.place, self.rev, self.repo, "", "first", since=since, items=[item])
        self.assertEqual(lines, [])

    def test_plan_scope_skips_a_file_only_the_git_filter_shows_changed(self):
        """since の前に書いた ident のファイルは、作業ツリーの中身（$Id: <sha> $）と since の木の中身（$Id$）が違っても git の
        比べでは触っていない: 修正役が足した行（足す行の path の外の同名の定義）として照らさない（#333）"""
        import leftovers
        import writes
        (self.repo / ".gitattributes").write_text("helper.py ident\n", encoding="utf-8")
        (self.repo / "helper.py").write_text(f'def helper(): return "$Id: {"0" * 40} $"\n', encoding="utf-8")
        stats = self.repo / "stats.py"
        since = leftovers.snapshot(self.repo)
        stats.write_text(stats.read_text(encoding="utf-8") + "\n\ndef helper():\n    return 1\n", encoding="utf-8")
        item = {"item": 1, "unit_keys": [R_MEAN], "route": "direct", "tests": [], "rewrite_tests": [],
                "files": [{"path": "stats.py", "op": "modify", "responsibility": "平均の助け手",
                           "home": {"concept": "平均の助け手", "why": "平均の式の置き場"},
                           "considered": [{"path": "alt_home.py", "why_not": "同じ仕事の助け手が alt_home.py:3 に無かった"}],
                           "symbols": [{"name": "helper", "change": "add"}]}],
                "allowed_paths": ["stats.py"], "out_of_scope": []}
        reply = {"changes": [{"unit_key": R_MEAN, "files": ["stats.py"]}]}
        self.assertEqual(writes.changed_from(self.repo, since), ["stats.py"], "git の比べでは helper.py を触っていない")
        lines, _ = self.m.facts.check_plan_scope(reply, [R_MEAN], self.place, self.rev, self.repo, "", "first", since=since,
                                                 items=[item])
        self.assertEqual(lines, [])

    def test_plan_scope_counts_what_the_loop_fixed_before_since(self):
        """TDD の輪が直し終えた単位（stats.py の直しと files の add・tests の test_mean_of_two）の後の木を since（段の頭）に取り、修正役が
        何も変えずにその単位の行だけを返せば、欠けにしない（修正役の指示書は輪の単位を直し直させない。較正 clamp-above）"""
        import leftovers
        tests = self.repo / "test_stats.py"
        tests.write_text(tests.read_text(encoding="utf-8").replace("\n\nif __name__", _l_NEW_TEST + "\n\nif __name__"),
                         encoding="utf-8")
        stats = self.repo / "stats.py"
        text = stats.read_text(encoding="utf-8")
        for old, new in R_FIXED.items():
            text = text.replace(old, new)
        stats.write_text(text, encoding="utf-8")
        since = leftovers.snapshot(self.repo)
        item = {"item": 1, "unit_keys": [R_MEAN], "route": "tdd", "tests": [{"id": _l_MEAN_ID}], "rewrite_tests": [],
                "files": [{"path": "test_stats.py", "op": "modify", "responsibility": "平均の試験",
                           "home": {"concept": "平均の試験", "why": "平均の試験の置き場"},
                           "considered": [{"path": "alt_home.py", "why_not": "同じ仕事の助け手が alt_home.py:3 に無かった"}],
                           "symbols": [{"name": "TestStats::test_mean_of_two", "change": "add"}]}],
                "allowed_paths": ["stats.py", "test_stats.py"], "out_of_scope": []}
        reply = {"changes": [{"unit_key": R_MEAN, "files": ["stats.py", "test_stats.py"]}]}
        args = (reply, [R_MEAN], self.place, self.rev, self.repo, "", "first")
        lines, _ = self.m.facts.check_plan_scope(*args, since=since, items=[item])
        self.assertEqual(lines, [])

    def test_writes_look_only_after_since(self):
        import writelog
        fc, since, _, reply = self.since_case()
        log = self.place / writelog.LOG
        log.write_text("", encoding="utf-8")
        got = fc.check_writes(reply, self.place, self.rev, self.repo, "")
        self.assertTrue(any("NOTES.md" in p for p in got["problems"]), got)
        got = fc.check_writes(reply, self.place, self.rev, self.repo, "", since=since)
        self.assertTrue(any("stats.py" in p for p in got["problems"]), got)
        self.assertFalse(any("NOTES.md" in p or "test_stats.py" in p for p in got["problems"]), got)
        self.record(log, self.repo / "stats.py")
        self.assertEqual(fc.check_writes(reply, self.place, self.rev, self.repo, "", since=since)["problems"], [])


class GateItemsSeamCase(unittest.TestCase):
    """直す前の人の関所の答え {decision, text} が、範囲の相談の人の条件（consult.gate_notes）に届く"""

    def setUp(self):
        self.m = _s_load()
        self.b = self.m.board

    def test_pass_word_with_text_becomes_a_note(self):
        consult = self.m.consult
        for word in ("approve", "continue"):
            rows = self.b.gate_items({"decision": word, "text": "テストの名は変えないこと"})
            self.assertEqual(consult.gate_notes("unused", rows), "テストの名は変えないこと")

    def test_no_note_without_text_or_on_stop(self):
        consult = self.m.consult
        for answers in (None, "", {"decision": "stop", "text": "止める"}):
            self.assertEqual(self.b.gate_items(answers), [])
        for answers in ({"decision": "approve", "text": ""}, {"decision": "approve"}):
            self.assertEqual(consult.gate_notes("unused", self.b.gate_items(answers)), "")


class SettleOverflowSeamCase(SeamTemp):
    """はみ出しの行だけの回の道筋（board.settle_overflow。元 works/blk-fix/scripts/accept.py:549）: 承認済みの項目の範囲の外に
    触れた返答は、まだ聞いていなければ拒まずに範囲の相談に積み（次の consult_ask が頼みにする）、聞いて deny された同じはみ出しは
    機械が段の頭の木に戻して受け付ける"""

    DENY = {"answers": [{"ask": 1, "decision": "deny", "reason": "見本の入力は直しに要らないので範囲に足さない"}]}

    def setUp(self):
        super().setUp()
        import planmarks
        planmarks.save(self.place, 1, [{"route": "direct", "tests": [], "rewrite_tests": [], "allowed_paths": ["stats.py"],
                                         "out_of_scope": []}])
        (self.place / self.b.PLAN_REPLY_FILE).write_text(json.dumps(
            {"plan": [{"unit_keys": [R_MEAN], "approach": "分母を直す", "files": []}]}, ensure_ascii=False),
            encoding="utf-8")
        (self.place / self.b.JUDGMENT_FILE).write_text(json.dumps({"units": [R_JUDGED[0]]}, ensure_ascii=False), encoding="utf-8")
        self.head = leftovers.snapshot(self.repo)
        self.extra = self.repo / "request_ok.json"
        self.before = self.extra.read_bytes()
        path = self.repo / "stats.py"
        path.write_text(path.read_text(encoding="utf-8").replace("sum(xs) / (len(xs) - 1)", "sum(xs) / len(xs)"),
                        encoding="utf-8")
        self.extra.write_bytes(self.before + b"\n")
        self.reply = {"changes": [{**_fix_row(R_MEAN, 1), "files": ["stats.py", "request_ok.json"]}], "not_done": []}
        self.kw = dict(pass_="first", owed=[R_MEAN], judged=[R_JUDGED[0]], head=self.head, skip=SKIP, base_rev=self.rev)

    def items(self):
        return self.b.place_items(self.place)

    def test_unasked_overflow_is_queued_not_rejected(self):
        consult = self.m.consult
        got = self.b.accept_reply(self.reply, self.place, self.repo, iteration=1, **self.kw)
        self.assertFalse(got["ok"], got)
        self.assertTrue(got.get("queued"), got["reason"])
        self.assertTrue(got["reason"].startswith(self.b.QUEUED), got["reason"])
        self.assertEqual(self.extra.read_bytes(), self.before + b"\n", "積んだ回は作業ツリーを変えない")
        rows = consult.queued(self.place, "first")
        self.assertEqual([(r["paths"], r["origin"]) for r in rows], [(["request_ok.json"], consult.ORIGIN_ACCEPT)])
        ask = self.b.consult_ask(self.place, self.reply, "first", self.items(), node="consult-answer", render=self.render())
        self.assertEqual((ask["consulted"], ask["go"]), (True, True), ask)
        self.assertIn("request_ok.json", ask["prompt"])
        self.assertEqual(consult.queued(self.place, "first"), [], "頼みにした後は積んだ物を空にする")

    def test_denied_overflow_is_reverted_and_accepted(self):
        consult = self.m.consult
        import impact
        self.assertTrue(self.b.accept_reply(self.reply, self.place, self.repo, iteration=1, **self.kw).get("queued"))
        self.b.consult_ask(self.place, self.reply, "first", self.items(), node="consult-answer", render=self.render())
        consult.settle(self.place, self.DENY, "first", "consult-answer")
        got = self.b.accept_reply(self.reply, self.place, self.repo, iteration=2, **self.kw)
        self.assertTrue(got["ok"], got["reason"])
        self.assertEqual(self.extra.read_bytes(), self.before, "deny されたはみ出しは段の頭の姿に戻す")
        self.assertIn("sum(xs) / len(xs)", (self.repo / "stats.py").read_text(encoding="utf-8"))
        self.assertEqual([c["files"] for c in got["reply"]["changes"]], [["stats.py"]])
        rows = [r for r in _traced(self.place) if r["op"] == impact.ACCEPT_OVERFLOW_OP]
        self.assertEqual([r["reverted"][0]["paths"] for r in rows], [["request_ok.json"]], rows)
        self.assertTrue(pathlib.Path(rows[0]["reverted"][0]["patch"]).is_file())

    def test_copy_reject_turns_overflow_into_a_reject(self):
        """はみ出しだけに見える回でも、写しの照らし（数え直し）を乾いた形で先に当て、写しの拒否が在れば相談に積まずに拒む
        （後で見つかる写しの拒否で相談の周を無駄にしない。元 works/blk-fix/scripts/accept.py:675-681）"""
        consult = self.m.consult
        import recount
        reply = {"changes": [{**_fix_row(R_MEAN, 1), "bypass_tried": "なし", "files": ["stats.py", "request_ok.json"]}],
                 "not_done": []}
        got = self.b.accept_reply(reply, self.place, self.repo, iteration=1, **self.kw)
        self.assertFalse(got["ok"], got)
        self.assertFalse(got.get("queued"), got["reason"])
        self.assertTrue(any(r["check"] == "copy" and "bypass_tried が空同然" in r["text"] for r in got["rejects"]), got["rejects"])
        self.assertTrue(any(r["check"] == "scope" and "request_ok.json" in r["text"] for r in got["rejects"]), got["rejects"])
        self.assertEqual(consult.queued(self.place, "first"), [], "相談に積まない")
        self.assertEqual(self.extra.read_bytes(), self.before + b"\n", "拒んだ回は作業ツリーを変えない")
        self.assertFalse((self.place / recount.COVERAGE_FILE).exists(), "写しの照らしは乾いた形（件数を書かない）")


class RecountSeamCase(SeamTemp):
    """class_query の数え直し（keep-essence の 7）を、修正役の受け付け（board.accept_reply）の振る舞いとして照らす。元は
    recount.accept_fix を直に呼んだ継ぎ目の試験（lib/tests/test_fix_seams.py の RecountSeamCase）。ここでは判定の写しを置き場に
    置き、段の頭の木を控えてから作業ツリーを直し、返答を受け付けに通す。拒否は確かめ copy（と closure）の行に出て、拒んだ回は
    件数（recount.COVERAGE_FILE）を書かない"""

    def setUp(self):
        super().setUp()
        import recount
        self.recount = recount
        self.head = leftovers.snapshot(self.repo)

    def edit_tree(self, subs):
        path = self.repo / "stats.py"
        text = path.read_text(encoding="utf-8")
        for old, new in subs.items():
            self.assertIn(old, text)
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")

    def accept(self, reply, *, judged=R_JUDGED, owed=(R_MEAN, R_CLAMP), precedents=()):
        (self.place / self.b.JUDGMENT_FILE).write_text(json.dumps({"units": judged, "precedents": list(precedents)},
                                                                  ensure_ascii=False), encoding="utf-8")
        return self.b.accept_reply(json.loads(json.dumps(reply)), self.place, self.repo, pass_="first", iteration=1,
                                   owed=list(owed), judged=judged, head=self.head, base_rev=self.rev, skip=SKIP)

    def copy_rows(self, got) -> list:
        return [r["text"] for r in got["rejects"] if r["check"] == "copy"]

    def calls(self) -> int:
        p = self.place / self.recount.COUNT_BUDGET_FILE
        return json.loads(p.read_text(encoding="utf-8"))["calls"] if p.is_file() else 0

    def assert_rejected(self, reply, *words, **kw):
        got = self.accept(reply, **kw)
        self.assertFalse(got["ok"], got)
        for w in words:
            self.assertIn(w, got["reason"])
        self.assertFalse((self.place / self.recount.COVERAGE_FILE).exists(), "拒んだ受け付けは件数を書かない")
        return got

    def test_rejects_self_reports_the_machine_can_check(self):
        """黙って通る閉鎖の状態・赤を見ない clean・同じファイルの interactions・bypass_tried・breaks.result・判定者の行の無い
        from_judge_row・理由の短い symptom を、受け付けが確かめ copy の 1 誤り 1 行で全部並べて拒む。判定の写しの precedents に在る
        単位の from_judge_row は拒まない"""
        self.edit_tree(R_FIXED)
        bad = _fix_ok()
        bad["fix_closure"] = {"status": "not_applicable"}
        bad["interactions"] = []
        bad["changes"][0].update({"bypass_tried": "なし", "breaks": {"how": "x", "result": ""},
                                  "precedent": {"from_judge_row": True, "verdict": "adopt", "reason": "判定者の行"}})
        bad["changes"][1]["root_or_symptom"] = {"kind": "symptom", "why": "後で"}
        got = self.assert_rejected(bad, "fix_closure が not_applicable", "interactions に無い", "bypass_tried が空同然",
                                   "breaks.result が空同然", "from_judge_row", "症状を塞ぐ")
        self.assertGreaterEqual(len(self.copy_rows(got)), 6, got["rejects"])
        judged_row = self.accept(bad, precedents=[{"key": R_MEAN}])
        self.assertTrue(self.copy_rows(judged_row), judged_row)
        self.assertFalse(any("from_judge_row" in t for t in self.copy_rows(judged_row)))
        clean = _fix_ok()
        clean["fix_closure"] = {"status": "clean"}
        for c in clean["changes"]:
            for site in c["closure"]["sites"]:
                site["red_seen"] = False
        self.assertIn("赤を一度も見ていない", self.accept(clean)["reason"])

    def test_rejects_wrote_refs_and_added_links_that_do_not_resolve(self):
        """修正が書いた指し（wrote_refs）は指し先の中で数え直し、差分が足した Markdown のリンクは申告に依らず指し先を引く"""
        self.edit_tree(R_FIXED)
        (self.repo / "NOTES.md").write_text("# 覚え\n\n[式](stats.py) と [無い](gone.md) と [節](NOTES.md#無い見出し)\n",
                                            encoding="utf-8")
        reply = {**_fix_ok(), "wrote_refs": [{"kind": "text", "cite": "def median", "target": "stats.py", "where": "NOTES.md"}]}
        reply["changes"][0]["files"] = ["stats.py", "NOTES.md"]
        got = self.assert_rejected(reply, "'def median' は指し先 'stats.py' の中に無い", "gone.md", "#無い見出し")
        self.assertNotIn("(stats.py)", got["reason"])
        (self.repo / "NOTES.md").write_text("# 覚え\n\n[式](stats.py)\n", encoding="utf-8")
        reply["wrote_refs"] = [{"kind": "text", "cite": "def mean", "target": "stats.py", "where": "NOTES.md"}]
        got = self.accept(reply)
        self.assertTrue(got["ok"], got["reason"])

    def test_accepts_real_fix_and_keeps_counts(self):
        """本当に直した返答は受け、単位ごとの母数と修正後の数（recount.COVERAGE_FILE）と閉鎖の表を置き場に置く"""
        import querytest
        self.edit_tree(R_FIXED)
        got = self.accept(_fix_ok())
        self.assertTrue(got["ok"], got["reason"])
        self.assertEqual([(c["unit_key"], c["files"]) for c in got["reply"]["changes"]],
                         [(R_MEAN, ["stats.py"]), (R_CLAMP, ["stats.py"])])
        self.assertEqual({k: v["status"] for k, v in got["units"].items()}, {R_MEAN: "fixed", R_CLAMP: "fixed"})
        cov = json.loads((self.place / self.recount.COVERAGE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(cov["round"], 1)
        self.assertEqual({i["unit_key"]: (i["total"], i["after"]) for i in cov["items"]}, {R_MEAN: (1, 0), R_CLAMP: (2, 1)})
        rows = json.loads((self.place / querytest.CLOSURE_FILE).read_text(encoding="utf-8"))["rows"]
        self.assertEqual({r["unit_key"] for r in rows}, {R_MEAN, R_CLAMP})

    def test_rejects_count_not_dropped(self):
        """直していない・注記に元の式を残しただけの木は、判定者の欠陥の問いの数が落ちないので、閉鎖の数え直し（確かめ closure）が
        単位を名指して拒む（申し出の道 query_hits_fixed を添えて）"""
        for subs in ({}, R_RESIDUE):
            with self.subTest(subs=bool(subs)):
                self.edit_tree(subs)
                got = self.assert_rejected(_fix_ok(), R_MEAN, "修正前 1 件・修正後 1 件で閉じていない", "query_hits_fixed")
                self.assertEqual([r["check"] for r in got["rejects"]], ["closure"], got["rejects"])

    def test_sites_mismatch_is_recounted_by_the_machine_and_recorded(self):
        """申告の closure.sites の件数が母数と合わない返答は、受け付けの閉鎖の数え直し（closure_reply → unitrows.build）が機械の数で
        揃え（足りなければ remaining を機械が埋め、多ければ母数まで切る）、写しの照らし（recount.accept_fix）で拒まずに受ける。
        食い違いは閉鎖の表（querytest.CLOSURE_FILE）の discrepancies に残る（元の seam の試験は recount.accept_fix を直に呼び、
        黙って残すのを拒んだ）"""
        import querytest
        self.edit_tree(R_FIXED)
        short = _fix_ok()
        short["changes"][1]["closure"]["sites"] = short["changes"][1]["closure"]["sites"][:1]
        got = self.accept(short)
        self.assertTrue(got["ok"], got["reason"])
        rows = {r["unit_key"]: r for r in json.loads((self.place / querytest.CLOSURE_FILE).read_text(encoding="utf-8"))["rows"]}
        self.assertEqual((rows[R_CLAMP]["claimed"], rows[R_CLAMP]["total"]), (1, 2))
        over = _fix_ok()
        over["changes"][0]["closure"]["sites"] *= 3
        got = self.accept(over)
        self.assertTrue(got["ok"], got["reason"])
        rows = {r["unit_key"]: r for r in json.loads((self.place / querytest.CLOSURE_FILE).read_text(encoding="utf-8"))["rows"]}
        self.assertEqual((rows[R_MEAN]["claimed"], rows[R_MEAN]["total"]), (3, 1))
        self.assertTrue(any("3 件が母数 1 を超える" in d for d in rows[R_MEAN]["discrepancies"]), rows[R_MEAN])

    def test_rejects_uncovered_owed_unit(self):
        self.edit_tree(R_FIXED)
        reply = _fix_ok()
        del reply["changes"][1]
        self.assert_rejected(reply, "直していない", R_CLAMP)
        got = self.accept(reply, owed=(R_MEAN,))
        self.assertTrue(got["ok"], "直す義務に無い単位は求めない: " + got["reason"])

    def test_narrowed_query_is_recorded_and_unknown_direction_rejected(self):
        """修正役が判定者の問いより狭めた how は、閉じたかを判定者の問いで決め（how_from は修正役のまま）、狭めた事を閉鎖の表の
        discrepancies に残して受ける。判定者の class_query も役の how も無い単位・数える向きの決まらない単位は写しの照らしが拒む"""
        import querytest
        self.edit_tree(R_FIXED)
        narrow = _fix_ok()
        narrow["changes"][1]["coverage"] = {"how": {"patterns": ["return lo"], "fixed": True, "paths": ["stats.py"],
                                                    "count": "files"}}
        narrow["changes"][1]["closure"]["sites"] = narrow["changes"][1]["closure"]["sites"][:1]
        got = self.accept(narrow)
        self.assertTrue(got["ok"], got["reason"])
        rows = {r["unit_key"]: r for r in json.loads((self.place / querytest.CLOSURE_FILE).read_text(encoding="utf-8"))["rows"]}
        self.assertEqual((rows[R_CLAMP]["how_from"], rows[R_CLAMP]["total"]), ("修正役", 2))
        self.assertTrue(any("判定者の母数 2 より狭い" in d for d in rows[R_CLAMP]["discrepancies"]), rows[R_CLAMP])
        bare = _fix_ok()
        got = self.accept(bare, judged=[])
        self.assertFalse(got["ok"])
        self.assertIn("coverage.how", got["reason"], "判定者の class_query も役の how も無い単位は拒む")
        bare["changes"][0]["coverage"] = {"how": R_JUDGED[0]["class_query"]["how"]}
        self.assertIn("数えるものの向きが決まらない", self.accept(bare, judged=[])["reason"])

    def test_budget_exhausted_is_a_reject_line(self):
        """1 周に数える問いを走らせる量の上限（COUNT_BUDGET）に達した後の受け付けは、問いを走らせずに『上限に達した』の行で拒む"""
        self.edit_tree(R_FIXED)
        spent = {"round": 1, "calls": self.recount.COUNT_BUDGET["calls"], "seconds": 0.0}
        (self.place / self.recount.COUNT_BUDGET_FILE).write_text(json.dumps(spent), encoding="utf-8")
        self.assert_rejected(_fix_ok(), f"上限（{self.recount.COUNT_BUDGET['calls']} 回か "
                                        f"{self.recount.COUNT_BUDGET['seconds']} 秒）に達した")
        self.assertEqual(self.calls(), spent["calls"], "上限の後は走らせない")

    def test_zero_unit_is_not_rejected_as_narrowed(self):
        """判定者の問いが修正前の版で 0 件なのに total が 0 でない単位は、受け付けが 0 件の単位と数え（closure_reply）、
        判定者の母数より修正前の数が少なくても『問いを狭めている』で拒まない"""
        judged = [{"key": R_MEAN, "class_query": {"how": {"patterns": ["zzz-none"], "fixed": True, "paths": ["stats.py"],
                                                           "count": "lines"}, "counts": "population", "total": 2}}]
        self.edit_tree(R_FIXED)
        got = self.accept({"changes": [_fix_row(R_MEAN, 0)], "not_done": []}, judged=judged, owed=(R_MEAN,))
        self.assertTrue(got["ok"], got["reason"])
        self.assertNotIn("狭めている", got["reason"])

    def test_rejects_blank_interaction_check(self):
        """2 つの修正が同じファイルを触った時、interactions のそのファイルの checked が空同然なら拒む"""
        self.edit_tree(R_FIXED)
        reply = _fix_ok()
        reply["interactions"] = [{"surface": "stats.py", "checked": "済み"}]
        self.assert_rejected(reply, "interactions[stats.py] の checked が空同然")
        got = self.accept(_fix_ok())
        self.assertTrue(got["ok"], "突き合わせた結果を書けば通す: " + got["reason"])

    def test_rejects_precedent_without_problem_or_source(self):
        """precedent は from_judge_row でなければ problem と source（verdict が not_found なら searched）を求める"""
        self.edit_tree(R_FIXED)
        bare = _fix_ok()
        bare["changes"][0]["precedent"] = {"verdict": "adopt", "reason": "標準の定義に合わせる"}
        self.assert_rejected(bare, f"{R_MEAN[:60]}: precedent に problem と source")
        unsourced = _fix_ok()
        unsourced["changes"][0]["precedent"] = {"problem": "平均の分母の誤り", "verdict": "adopt", "reason": "標準の定義に合わせる"}
        self.assert_rejected(unsourced, "precedent に problem と source")
        unsearched = _fix_ok()
        unsearched["changes"][0]["precedent"] = {"problem": "平均の分母の誤り", "verdict": "not_found", "reason": "見つからない"}
        self.assert_rejected(unsearched, "precedent に problem と source")
        unsearched["changes"][0]["precedent"]["searched"] = "標準ライブラリの文書と課題の一覧を引いた"
        got = self.accept(unsearched)
        self.assertTrue(got["ok"], "not_found は searched が在れば通す: " + got["reason"])



# ------------------------------------------------------------ 3 script（tests/workflows/test_fix.py の写し）
ROOT = pathlib.Path(__file__).resolve().parents[3]

_X_MEAN = "u-mean"     # 判定者の問いの在る単位（stats.py の mean の分母）
_X_BOUND = "u-bound"   # 判定者の問いの無い単位（coverage.how が無いと数え直しが名指して拒む）
_X_JUDGMENT = {"units": [
    {"key": _X_MEAN, "label": "block", "class_query": {
        "how": {"patterns": ["(len(xs) - 1)"], "fixed": True, "paths": ["stats.py"], "count": "lines"},
        "counts": "defects", "total": 1}},
    {"key": _X_BOUND, "label": "block"}], "questions": []}
# 修正役の返答の自己申告の欄（lib/tests/test_fix_seams.py の SELF_REPORT と同じ値）
_X_SELF_REPORT = {"bypass_tried": "修正を残したまま空の並びを渡して破りに行き、例外で止まるのを見た",
                  "breaks": {"how": "git grep -n mean", "result": "呼び手は 1 か所で、戻り値の型は変わらない"},
                  "precedent": {"problem": "平均の分母の誤り", "verdict": "adopt", "reason": "標準の定義に合わせる",
                                "source": "https://docs.python.org/3/library/statistics.html"},
                  "root_or_symptom": {"kind": "root", "why": "分母の式そのものを直した"}}
_X_CHANGED_MARKS = {"mechanism_changed", "premise_drift", "gates_changed", "seams_changed", "security_surface_changed",
                    "path_changed"}
_X_CLAIM = {"between": ["stats.py:9", "test_stats.py:8"], "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
            "which_is_right": "request", "kind": "unnamed_test_broke"}
_X_SCOPE_RULING = {"decision": "fix_test_scope", "text": "テストの期待を直してよい", "limits": ["test_stats.py"]}
# 網に出ようとした子をすぐ落とす宛先（控えを読めなかった時に本物の網へ出ない）
_X_NO_NET = {"https_proxy": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9"}
_X_FACES_HEAD = "## Pre-review keys to answer (plan_faces)"


def _x_change(unit, files, **extra):
    """修正役の返答の changes の 1 行（closure の site は 1 つ）"""
    return {"unit_key": unit, "files": files, "what": "直した", **_X_SELF_REPORT, **extra,
            "closure": {"mechanism": "分母", "fix_mechanism": "len(xs)", "verified_how": "読んだ",
                        "sites": [{"site": f"{files[0]}:9", "red_seen": True}]}}


def _x_recorder_root(tmp):
    """記録の根を持つ隔離した設定の置き場（toolset.install が作る形）。(子の環境に足す物, 記録の根)"""
    import writelog
    cfg = pathlib.Path(tmp) / "claude-config"
    root = writelog.root(cfg)
    root.mkdir(parents=True)
    return {"CLAUDE_CONFIG_DIR": str(cfg)}, root


def _x_record(log, path, tool="Edit"):
    """記録のフックが書く形の 1 行を log に足す"""
    log.parent.mkdir(parents=True, exist_ok=True)
    real = os.path.realpath(str(path))
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"tool_name": tool, "path": real,
                            "file_sha": hashlib.sha256(pathlib.Path(real).read_bytes()).hexdigest()}) + "\n")


class _XPlace(unittest.TestCase):
    """組 1 つの単独の run（mode group・out_dir 空）。intake と group_start を回した後の置き場と、target-seed の写しの作業ツリー"""

    def setUp(self):
        self.board = kit.load("fix", "board")   # lib も sys.path に入る
        from src import gates
        self.gates = gates
        self.run = kit.Run(self, "fix")
        shutil.rmtree(self.run.repo)
        committed_copy(self.run.repo, SEED)
        self.repo, self.place, self.tmp = self.run.repo, self.run.artifacts, self.run.artifacts.parent
        self._x_intake([_X_MEAN])
        self._x_ok("group_start")

    def _x_run(self, script, *, art=None, env_extra=None, **inputs):
        """scripts/<script>.py を子のプロセスで回す。(終了の値, 標準出力の JSON か None, 標準エラー)"""
        run = self.run
        if art is not None:   # 別の置き場: 書き手の返りのファイルもそこに置く
            run = copy.copy(self.run)
            run.artifacts = pathlib.Path(art)
        env = run.environ(**inputs)
        env.update(env_extra or {})
        done = subprocess.run([sys.executable, str(self.run.block / "scripts" / f"{script}.py")], cwd=self.repo,
                              env=hermetic.child_env(**env), capture_output=True, text=True, encoding="utf-8")
        try:
            out = json.loads(done.stdout)
        except ValueError:
            out = None
        return done.returncode, out, done.stderr

    def _x_ok(self, script, **kw):
        code, out, err = self._x_run(script, **kw)
        self.assertEqual(code, 0, err)
        return out

    def _x_prompt(self, out) -> str:
        """支度 fix_prep・fix_ruled_prep の返り out の周に起こす型の書き手の block が、渡された order・slots から組む指示（その block の
        writer_prep.py を回す。指示は block の place の <型>-prompt-<n>.md にも書かれる）"""
        return support.writer_prompt(self.run.environ(), out, self.repo)

    def _x_intake(self, units, *, art=None):
        """組の単位を port group で、判定を port judgment で渡す（組を替える時も intake を回し直す）"""
        out = self._x_ok("intake", art=art, mode="group", judgment=json.dumps(_X_JUDGMENT, ensure_ascii=False),
                         group=json.dumps({"group_id": "g1", "unit_ids": units, "items": []}), tdd_suite=str(self.repo / "junit-suite.sh"))
        self.assertTrue(out["ok"], out)

    def _x_json(self, name, doc):
        path = self.place / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return path

    def _x_fix_mean(self):
        path = self.repo / "stats.py"
        path.write_text(path.read_text(encoding="utf-8").replace("sum(xs) / (len(xs) - 1)", "sum(xs) / len(xs)"),
                        encoding="utf-8")

    def _x_accept(self, script, reply, iteration, *, units=None, art=None, env_extra=None):
        if units is not None:
            self._x_intake(units, art=art)
        return self._x_ok(script, art=art, env_extra=env_extra, reply_variant=support.reply_json(reply),
                          consulted="false", iteration=str(iteration))

    def _x_park(self, ruling=None, **claim):
        import conflict
        conflict.park(self.place, [{"unit_key": _X_MEAN, **_X_CLAIM, **claim}], source=conflict.FIX_SOURCE,
                      **({"ruling": ruling} if ruling is not None else {}))

    def _x_join(self, bound_status="fixed"):
        self._x_json("join.json", {"groups": [{"group_id": "g1", "unit_ids": [_X_MEAN, _X_BOUND], "returned": True, "reason": ""}],
                                   "units": [{"unit_id": _X_MEAN, "group_id": "g1", "status": "not_done", "reason": ""},
                                             {"unit_id": _X_BOUND, "group_id": "g1", "status": bound_status, "reason": ""}]})


class FixLoopScriptsCase(_XPlace):
    """修正の輪・裁定の後の修正の輪・範囲の相談の script を、使い捨ての run directory と作業ツリーで起こす"""

    def test_third_reject_gives_up_only_the_named_unit(self):
        """3 回目の拒否で、拒否が名指す単位だけを段の頭の木に戻して諦め、ほかの単位の直しを受けて輪を抜ける（keep-essence の 4）"""
        self._x_fix_mean()
        (self.repo / "bounds.py").write_text("def bound(x):\n    return x\n", encoding="utf-8")
        reply = {"changes": [_x_change(_X_MEAN, ["stats.py"]), _x_change(_X_BOUND, ["bounds.py"])]}
        units = [_X_MEAN, _X_BOUND]
        for n in (1, 2):
            out = self._x_accept("fix_accept", reply, n, units=units)
            self.assertEqual((out["ok"], out["done"]), (False, False), out)
            self.assertIn(_X_BOUND, out["reason"])
            self.assertTrue(pathlib.Path(out["reason_file"]).is_file())
        out = self._x_accept("fix_accept", reply, 3, units=units)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        got = json.loads((self.place / "fix-units.json").read_text(encoding="utf-8"))
        self.assertEqual({k: v["status"] for k, v in got.items()}, {_X_MEAN: "fixed", _X_BOUND: "given_up"})
        self.assertFalse((self.repo / "bounds.py").exists(), "諦めた単位の直しは段の頭の木に戻す")
        self.assertIn("sum(xs) / len(xs)", (self.repo / "stats.py").read_text(encoding="utf-8"), "ほかの単位の直しは残す")
        self.assertIn("bounds.py", (self.place / "fix-parked-1.patch").read_text(encoding="utf-8"))
        rows = json.loads((self.place / "conflicts.json").read_text(encoding="utf-8"))["items"]
        self.assertEqual([(r["unit_key"], r["ruling"]["decision"]) for r in rows], [(_X_BOUND, "ask_human")])
        kept = json.loads((self.place / "fix-reply.json").read_text(encoding="utf-8"))
        self.assertEqual([c["unit_key"] for c in kept["changes"]], [_X_MEAN])
        self.assertEqual(set(kept["changed"]), _X_CHANGED_MARKS | {"premise_drift_note"})

    def test_accept_traces_tests_left_to_ci_and_final_stage(self):
        """F013: 受け付けの回ごとに accept-trace.json に impact.ACCEPT_TRACE_OP の行（ci_left・final_left・final_far）を積み、
        読み手は組と段ごとに最後の回＝受けた回の行を読む（fix の finish._accepted_tests）。名は受け付けが書き戻した置き場の accept.json
        から引く（下書き docs/plans/2026-10-24-fix-weapons.md の 2.1。輪の状態の同じ名の欄は読まない）"""
        import impact
        finish = importlib.import_module("src.finish")
        board = self.board
        self._x_fix_mean()
        self._x_accept("fix_accept", {"changes": []}, 1)
        out = self._x_accept("fix_accept", {"changes": [_x_change(_X_MEAN, ["stats.py"])]}, 2)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        rows = [r for r in board.accept_trace_rows(self.place) if r["op"] == impact.ACCEPT_TRACE_OP]
        self.assertEqual([(r["pass"], r["attempt"]) for r in rows], [("first", 1), ("first", 2)])
        self.assertEqual([(r["attempt"], r["ci_left"], r["final_left"]) for r in finish._accepted_tests(rows)], [(2, [], [])])
        state = self._x_json("tdd-state.json", {"ci_left": ["stale.py"], "final_left": ["stale.py"], "final_far": ["stale.py"]})
        (self.place / "accept.json").write_text(json.dumps({"ci_left": ["tests/test_slow.py"], "final_left": ["tests/test_far.py"],
                                                            "final_far": ["lib/far.py"]}), encoding="utf-8")
        board.tests_trace(self.place, str(state), "", pass_="ruled", attempt=1)
        last = [r for r in board.accept_trace_rows(self.place) if r["op"] == impact.ACCEPT_TRACE_OP][-1]
        self.assertEqual((last["ci_left"], last["final_left"], last["final_far"]),
                         (["tests/test_slow.py"], ["tests/test_far.py"], ["lib/far.py"]))

    def test_accept_traces_skipped_gates(self):
        """F041: 事後の関門の束が受け入れのテストの赤緑を確かめずに受けた回は、置き場の trace に gates.SKIPPED_OP の行と訳を積み
        （義務の外 OUT_OF_DUTY は除く。board.gates_trace）、accept_trace_rows が運ぶ（報告の「受け付け N 回・理由」の数え方は report の試験）"""
        board, gates = self.board, self.gates
        self._x_fix_mean()
        out = self._x_accept("fix_accept", {"changes": [_x_change(_X_MEAN, ["stats.py"])]}, 1)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        self.assertEqual([r for r in board.accept_trace_rows(self.place) if r["op"] == gates.SKIPPED_OP], [],
                         "受け入れのテストの無い項目は確かめる物が無い")
        gates._record(self.place, {"pass": "first", "attempt": 2},
                      {"skipped": [{"why": gates.NO_SUITE}, {"why": gates.OUT_OF_DUTY}]})
        board.gates_trace(self.place, pass_="first", attempt=2)
        rows = [r for r in board.accept_trace_rows(self.place) if r["op"] == gates.SKIPPED_OP]
        self.assertEqual([r["why"] for r in rows], [[gates.NO_SUITE]])

    def test_undeclared_change_is_rejected(self):
        """書き込みの記録が無い run は、段の頭の木からの変更が changes[].files にも bash_writes にも無ければ拒む（keep-essence の 5）"""
        self._x_fix_mean()
        (self.repo / "scratch.txt").write_text("下書き\n", encoding="utf-8")
        out = self._x_accept("fix_accept", {"changes": [_x_change(_X_MEAN, ["stats.py"])]}, 1)
        self.assertEqual((out["ok"], out["done"]), (False, False), out)
        self.assertIn(self.board.UNDECLARED + "scratch.txt", out["reason"])
        declared = {"changes": [_x_change(_X_MEAN, ["stats.py"])],
                    "bash_writes": [{"path": "scratch.txt", "why": "Bash で生成した下書きのファイル"}]}
        out = self._x_accept("fix_accept", declared, 2)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)

    def test_accept_rejects_unrecorded_change_when_log_exists(self):
        """記録の根が在る run は、修正の受け付けも裁定の後の修正の受け付けも、記録も申告も無い変更を拒み、記録が在れば通す
        （keep-essence の 5）"""
        import writelog
        import writes
        env, root = _x_recorder_root(self.tmp)
        log = writelog.log_path(root, self.repo)
        log.parent.mkdir()
        reply = {"changes": [_x_change(_X_MEAN, ["stats.py"])]}
        for script in ("fix_accept", "fix_ruled_accept"):
            with self.subTest(script=script):
                git(self.repo, "checkout", "--", "stats.py")
                log.write_text("", encoding="utf-8")   # 始めの節（group-start）が作る物
                if script == "fix_ruled_accept":   # 直す義務は戻せた組の fixed でない単位だけ
                    self._x_join()
                self._x_fix_mean()
                out = self._x_accept(script, reply, 1, env_extra=env)
                self.assertEqual((out["ok"], out["done"]), (False, False), out)
                self.assertIn(writes.REJECT + "stats.py", out["reason"])
                _x_record(log, self.repo / "stats.py")
                out = self._x_accept(script, reply, 2, env_extra=env)
                self.assertEqual((out["ok"], out["done"]), (True, True), out)

    def test_no_recorder_root_keeps_no_record_path(self):
        """記録の根が無い起動は記録の無い run の道（記録を求めず、段の頭からの変更を申告に縛る）のまま"""
        cfg = self.tmp / "claude-config"
        cfg.mkdir()
        self._x_fix_mean()
        out = self._x_accept("fix_accept", {"changes": [_x_change(_X_MEAN, ["stats.py"])]}, 1,
                             env_extra={"CLAUDE_CONFIG_DIR": str(cfg)})
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        self.assertEqual(list(cfg.iterdir()), [], "根も記録も作らない")

    def test_tdd_loop_writes_are_not_the_fixers(self):
        """修正の段の頭は TDD の輪の後の木（fix-prep が 1 回目に控える）。輪が書いた物を修正役の申告に求めない"""
        (self.repo / "tdd_note.txt").write_text("TDD の輪が書いた物\n", encoding="utf-8")
        self._x_ok("fix_prep")
        self.assertTrue((self.place / "fix-head.json").is_file())
        self._x_fix_mean()
        out = self._x_accept("fix_accept", {"changes": [_x_change(_X_MEAN, ["stats.py"])]}, 1)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        self.assertTrue((self.repo / "tdd_note.txt").is_file())

    def test_ruled_fixer_head_is_the_ruled_prep_tree(self):
        """#332: 裁定の後の修正の段の頭は fix-ruled-prep が控える木。1 回目の修正の段の頭（fix-head.json）の後に書かれた物を
        裁定の後の修正役の申告に求めない"""
        self._x_ok("fix_prep")
        (self.repo / "tdd_note.txt").write_text("1 回目の修正・join が書いた物\n", encoding="utf-8")
        self._x_park(_X_SCOPE_RULING)
        self._x_ok("fix_ruled_prep")
        self._x_json("join.json", {"groups": [{"group_id": "g1", "unit_ids": [_X_MEAN], "returned": True, "reason": ""}],
                                   "units": [{"unit_id": _X_MEAN, "group_id": "g1", "status": "not_done", "reason": ""}]})
        self._x_fix_mean()
        out = self._x_accept("fix_ruled_accept", {"changes": [_x_change(_X_MEAN, ["stats.py"])]}, 1)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)

    def test_consulted_turn_and_skipped_fixer(self):
        out = self._x_accept("fix_accept", {"changes": []}, 1)
        self.assertFalse(out["ok"])
        code, out, err = self._x_run("fix_accept", reply_variant=support.reply_json({}), consulted="true", iteration="1")
        self.assertEqual((code, out["ok"], out["done"]), (0, False, False), err)
        code, out, err = self._x_run("fix_accept", reply_variant="null", consulted="false", iteration="1")
        self.assertEqual((code, out["ok"], out["done"]), (0, True, True), err)

    def test_ruled_pass_allows_ruled_test_scope_and_first_does_not(self):
        """裁定 fix_test_scope の limits のテストの変更を、親の置き場の裁定の後の受け付け（ruled）は通し、組の子の置き場の 1 回目
        （first）は通さない"""
        child_art = self.tmp / "child-art"
        child_art.mkdir()
        self._x_intake([_X_MEAN], art=child_art)
        self._x_ok("group_start", art=child_art)
        self._x_fix_mean()
        path = self.repo / "test_stats.py"
        path.write_text(path.read_text(encoding="utf-8").replace("mean([1, 2, 3]), 2", "mean([2, 4]), 3"), encoding="utf-8")
        reply = {"changes": [_x_change(_X_MEAN, ["stats.py", "test_stats.py"])]}
        out = self._x_accept("fix_accept", reply, 1, art=child_art)
        self.assertFalse(out["ok"], out)
        self.assertIn("test_stats.py", out["reason"])
        self._x_park(_X_SCOPE_RULING)
        self._x_join()
        out = self._x_accept("fix_ruled_accept", reply, 1)   # 直す義務は戻せた組の fixed でない単位だけ
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        kept = json.loads((self.place / "fix-ruled-reply.json").read_text(encoding="utf-8"))
        self.assertEqual(set(kept["changed"]), _X_CHANGED_MARKS | {"premise_drift_note"})

    @unittest.skipIf(os.geteuid() == 0, "root は読めない印のファイルも読める")
    def test_prep_snapshots_the_skip_head_before_marking_the_stage_head(self):
        """F107: 段の頭の印（fix-head.json・fix-ruled-head.json）は .archon/ の下の控え skip-before.json を書いた後に置く。控えを
        書けずに落ちた prep を回し直すと控えも書く"""
        board = self.board
        copy = self.repo / ".archon" / "workflows" / "x.yaml"
        copy.parent.mkdir(parents=True)
        copy.write_text("a: 1\n", encoding="utf-8")
        with open(self.repo / ".git" / "info" / "exclude", "a", encoding="utf-8") as f:
            f.write(".archon/\n")   # 木の姿（git add）は読まず、控え（skip_digests）だけが読んで落ちる
        self._x_park(_X_SCOPE_RULING)
        for script, head in (("fix_prep", board.FIX_HEAD_FILE), ("fix_ruled_prep", board.RULED_HEAD_FILE)):
            with self.subTest(script=script):
                (self.place / board.SKIP_BEFORE_FILE).unlink(missing_ok=True)
                copy.chmod(0)
                try:
                    code, _, err = self._x_run(script)
                finally:
                    copy.chmod(0o644)
                self.assertNotEqual(code, 0, "控えが書けない prep は落ちる")
                self.assertIn("x.yaml", err)
                self.assertFalse((self.place / head).exists(), "控えの無いまま段の頭の印を置かない")
                self._x_ok(script)
                self.assertIn(".archon/workflows/x.yaml", board.read_json(self.place / board.SKIP_BEFORE_FILE))
                self.assertTrue((self.place / head).is_file())

    def test_third_fix_prompt_names_every_reject_of_the_loop(self):
        """どの回の修正役も輪の拒否の全部を読む（#345）。修正の輪と裁定の後の修正の輪で 2 回続けて拒まれた後の 3 回目の指示に、
        1 回目と 2 回目の拒否の理由が古い順に在る（今は指示に貼る。{shared:rejected}）"""
        self._x_park(_X_SCOPE_RULING)
        self._x_join()
        for prep, accept in (("fix_prep", "fix_accept"), ("fix_ruled_prep", "fix_ruled_accept")):
            with self.subTest(prep=prep):
                reasons = []
                for k, reply in ((1, {"changes": []}), (2, {"changes": [_x_change(_X_BOUND, ["bounds.py"])]})):
                    out = self._x_ok(prep)
                    self.assertEqual(out["iteration"], k, out)
                    bad = self._x_accept(accept, reply, k)
                    self.assertEqual((bad["ok"], bad["done"]), (False, False), bad)
                    reasons.append(bad["reason"])
                self.assertNotEqual(*reasons)
                out = self._x_ok(prep)
                self.assertEqual(out["iteration"], 3, out)
                text = self._x_prompt(out)
                self.assertIn("## Why your previous answer was rejected", text)
                self.assertLess(text.index(reasons[0]), text.index(reasons[1]), "1 回目の拒否も古い順に届く")

    def test_fix_ruled_prep_without_fix_ruling_does_not_launch(self):
        out = self._x_ok("fix_ruled_prep")
        self.assertEqual(out, {"go": False, "iteration": 1, "writer": ""})
        self._x_park({"decision": "ask_human", "text": "人が決める", "limits": []},
                     why_both_cannot_hold="材料から決められない食い違いが在る", which_is_right="unknown", kind="needs_context")
        self.assertFalse(self._x_ok("fix_ruled_prep")["go"])

    def test_fix_ruled_prep_names_the_saved_reply_and_rulings(self):
        """直す裁定が在れば、組の修正役の返答の控えと裁定の文のファイルを名指す新しい会話の指示を組む"""
        import conflict
        self._x_park({"decision": "fix_code_as", "text": "分母を len(xs) にせよ", "limits": []})
        out_dir = self.place / "groups"
        child = self.tmp / "child-reply.json"
        child.write_text(json.dumps({"changes": [_x_change(_X_MEAN, ["stats.py"])], "not_done": []}), encoding="utf-8")
        self._x_json("groups/g1/result.json", {"group_id": "g1", "reply_file": str(child)})
        self._x_json("groups.json", {"groups": [{"group_id": "g1", "unit_ids": [_X_MEAN], "items": []}], "count": 1,
                                     "par": False, "start_tree": "", "out_dir": str(out_dir)})
        out = self._x_ok("fix_ruled_prep")
        self.assertEqual((out["go"], out["iteration"]), (True, 1), out)
        text = self._x_prompt(out)
        self.assertIn(str(self.place / "fix-reply.json"), text)
        self.assertIn(conflict.RULINGS_FILE, text)
        self.assertTrue((self.place / "fix-ruled-head.json").is_file())

    def test_first_pass_conflict_leaves_the_loop_for_ruling(self):
        """1 回目の受け付けが裁かれていない申し出を積むと、輪を抜け（done: true）単位は not_done で裁定へ回る"""
        import conflict
        reply = {"changes": [], "conflicts": [{"unit_key": _X_MEAN, **_X_CLAIM}]}
        out = self._x_accept("fix_accept", reply, 1)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        self.assertEqual([r["unit_key"] for r in conflict.unruled(self.place)], [_X_MEAN])
        got = json.loads((self.place / "fix-units.json").read_text(encoding="utf-8"))
        self.assertEqual(got[_X_MEAN]["status"], "not_done")

    def test_ruled_new_claim_is_parked_as_ask_human(self):
        """F207: 裁定の後の受け付けの新しい申し出は、機械が ask_human に裁いて積み（by fix-accept）、返答がほかの確かめで拒まれても
        積んだまま残す"""
        import conflict
        board = self.board
        self._x_join(bound_status="not_done")
        (self.repo / "bounds.py").write_text("def bound(x):\n    return x\n", encoding="utf-8")
        reply = {"changes": [_x_change(_X_BOUND, ["bounds.py"])],
                 "conflicts": [{"unit_key": _X_MEAN, **_X_CLAIM, "between": ["stats.py:9", "test_stats.py:9"]}]}
        out = self._x_accept("fix_ruled_accept", reply, 1)
        self.assertEqual((out["ok"], out["done"]), (False, False), out)
        self.assertIn(_X_BOUND, out["reason"], "ほかの確かめの拒否")
        rows = conflict.items(self.place)
        self.assertEqual([(r["unit_key"], r["ruling"]["decision"], r["ruling"]["by"], r["ruling"]["text"]) for r in rows],
                         [(_X_MEAN, conflict.ASK, board.FIX_ACCEPT_BY, board.SECOND_CONFLICT)], "拒否の後も積んだまま残す")
        self.assertEqual(conflict.unruled(self.place), [])
        self.assertTrue((self.place / conflict.RULINGS_FILE).is_file())

    def test_fix_prep_writes_the_prompt_and_skips_without_duty(self):
        from src import consult
        out = self._x_ok("fix_prep")
        self.assertEqual((out["go"], out["iteration"]), (True, 1), out)
        self.assertEqual(out["writer"], "w-variant", "注文の無い置き場の直す義務の全部を受ける型は variant")
        text = self._x_prompt(out)
        self.assertIn(_X_MEAN, text)
        self.assertFalse((self.place / consult.CONFIG).exists(), "修正案の無い run は相談の控えを書かない")
        # TDD の輪が緑にしていない単位は、修正役が項目ごとに下請け（実装役・審査役）を Agent で起こす（元の g1）。ファイルは型の block の place
        self.assertIn("## Running subagents", text)
        block_place = self.place / out["writer"]
        impl = (block_place / "g1-impl-1.md").read_text(encoding="utf-8")
        self.assertIn(_X_MEAN, impl)
        self.assertIn("## works rules (for the subagent", impl)
        self.assertIn(str(block_place / "g1-1.patch"), (block_place / "g1-review-1.md").read_text(encoding="utf-8"))
        self._x_intake(["not-owed"])
        self.assertFalse(self._x_ok("fix_prep")["go"])

    def test_prep_passes_state_dir_cache_root(self):
        """修正役の指示のライブラリの文書の節は、STATE_DIR の下 works-factory/ の run をまたぐ控えを読む（網に出ない）"""
        import libdocs
        from lib.tests.test_libdocs import FakeBoard, ok_http
        (self.repo / "app.py").write_text("import requests\n", encoding="utf-8")
        (self.repo / "requirements.txt").write_text("requests==2.32.3\n", encoding="utf-8")
        state = self.tmp / "state"
        libdocs.section(FakeBoard(self.tmp / "earlier").work(""), self.repo, ["app.py"], get=ok_http(), env={},
                        shared=state / "works-factory")
        out = self._x_ok("fix_prep", env_extra={"STATE_DIR": str(state), **_X_NO_NET})
        self.assertIn("ほかの run 1 本", self._x_prompt(out))

    def _x_overflow(self):
        """承認済みの項目 1（stats.py だけ）の範囲の外の request_ok.json にも触れた返答。返り (返答, 触る前の中身)"""
        import planmarks
        planmarks.save(self.place, 1, [{"route": "direct", "tests": [], "rewrite_tests": [], "allowed_paths": ["stats.py"],
                                        "out_of_scope": []}])
        self._x_json(self.board.PLAN_REPLY_FILE, {"plan": [{"unit_keys": [_X_MEAN], "approach": "分母を直す", "adds": [],
                                                            "removes": []}]})
        self._x_fix_mean()
        extra = self.repo / "request_ok.json"
        before = extra.read_bytes()
        extra.write_bytes(before + b"\n")
        return {"changes": [_x_change(_X_MEAN, ["stats.py", "request_ok.json"])]}, before

    def test_fix_accept_counts_in_the_rolekit_ledger_not_the_prompt_number(self):
        """fix_accept は INPUTS_ITERATION=1 のまま 3 回拒ませても、控えの拒否の数で最後の回が来る。拒否は rolekit の
        rejects-fix-accept-variant.json に積まれ、reason_file は rejects-fix-accept-variant.md でそれまでの拒否を全部持つ。最後の回は名指しの単位だけを
        諦めて done 真で返る"""
        import rolekit
        self._x_fix_mean()
        (self.repo / "bounds.py").write_text("def bound(x):\n    return x\n", encoding="utf-8")
        reply = {"changes": [_x_change(_X_MEAN, ["stats.py"]), _x_change(_X_BOUND, ["bounds.py"])]}
        units = [_X_MEAN, _X_BOUND]
        reasons = []
        for _ in (1, 2):
            out = self._x_accept("fix_accept", reply, 1, units=units)
            self.assertEqual((out["ok"], out["done"]), (False, False), out)
            reasons.append(out["reason"])
            self.assertEqual(out["reason_file"], str(self.place / "rejects-fix-accept-variant.md"))
            self.assertEqual(rolekit.rejected(self.place, "fix-accept-variant"), reasons)
            text = pathlib.Path(out["reason_file"]).read_text(encoding="utf-8")
            self.assertEqual(text, rolekit.rejects_text(reasons) + "\n", "それまでの拒否を古い順に全部持つ")
        out = self._x_accept("fix_accept", reply, 1, units=units)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        got = json.loads((self.place / "fix-units.json").read_text(encoding="utf-8"))
        self.assertEqual({k: v["status"] for k, v in got.items()}, {_X_MEAN: "fixed", _X_BOUND: "given_up"})
        self.assertEqual(list(self.place.glob("reject-fix-accept-*.md")), [])

    def test_fix_ruled_accept_counts_in_the_rolekit_ledger_not_the_prompt_number(self):
        """fix_ruled_accept も INPUTS_ITERATION=1 のまま、控え rejects-fix-ruled-accept-variant.json の拒否の数で最後の回が来る"""
        import rolekit
        self._x_park(_X_SCOPE_RULING)
        self._x_ok("fix_ruled_prep")
        self._x_json("join.json", {"groups": [{"group_id": "g1", "unit_ids": [_X_MEAN], "returned": True, "reason": ""}],
                                   "units": [{"unit_id": _X_MEAN, "group_id": "g1", "status": "not_done", "reason": ""}]})
        reasons = []
        for _ in (1, 2):
            out = self._x_accept("fix_ruled_accept", {"changes": []}, 1)
            self.assertEqual((out["ok"], out["done"]), (False, False), out)
            reasons.append(out["reason"])
            self.assertEqual(out["reason_file"], str(self.place / "rejects-fix-ruled-accept-variant.md"))
            self.assertEqual(rolekit.rejected(self.place, "fix-ruled-accept-variant"), reasons)
        out = self._x_accept("fix_ruled_accept", {"changes": []}, 1)
        self.assertTrue(out["done"], out)
        self.assertEqual(list(self.place.glob("reject-fix-ruled-accept-*.md")), [])
        # 拒否の控えの名のディレクトリ（読めない控え）でも、script は非 0 で落ちず、done 真の拒否（理由『拒否の控えが扱えない』・
        # reason_file は空）を返す（rule_accept の分は test_ruling.py）
        for script, name in (("fix_accept", "fix-accept-variant"), ("fix_ruled_accept", "fix-ruled-accept-variant")):
            with self.subTest(script=script):
                (self.place / f"rejects-{name}.json").unlink(missing_ok=True)
                (self.place / f"rejects-{name}.json").mkdir()
                out = self._x_ok(script, reply_variant=support.reply_json({"changes": []}), consulted="false", iteration="1")
                self.assertEqual((out["ok"], out["done"], out["reason_file"]), (False, True, ""), out)
                self.assertIn("拒否の控えが扱えない", out["reason"])

    def test_unasked_overflow_is_queued_for_the_next_consult_check(self):
        """範囲の外のはみ出しだけの返答は、まだ聞いていなければ拒まずに相談に積み（最後の回でも輪を抜けない）、次の周の
        consult-check が積んだ頼みで答えの役を起こす"""
        import rolekit
        reply, before = self._x_overflow()
        for k in (1, 2):   # 最後の回かは指示の番号でなく rolekit の控え rejects-fix-accept-variant.json の拒否の数で決まる
            rolekit.accept_round(self.place, "fix-accept-variant", None, lambda _, k=k: {"ok": False, "reason": f"{k} 回目の拒否"})
        out = self._x_accept("fix_accept", reply, 1)
        self.assertEqual((out["ok"], out["done"]), (False, False), out)
        self.assertTrue(out["reason"].startswith(self.board.QUEUED), out["reason"])
        self.assertEqual(len(rolekit.rejected(self.place, "fix-accept-variant")), 2, "積んだ回は控えに数えない")
        self.assertEqual((self.repo / "request_ok.json").read_bytes(), before + b"\n", "積んだ回は作業ツリーを変えない")
        out = self._x_ok("consult_check", reply_variant=support.reply_json(reply), **{"pass": "first"})
        self.assertEqual((out["consulted"], out["go"]), (True, True), out)
        self.assertIn("request_ok.json", out["prompt"])

    def test_denied_overflow_is_reverted_by_the_machine(self):
        """相談で deny された後の同じはみ出しは、機械が段の頭の木に戻して受け付ける"""
        reply, before = self._x_overflow()
        self.assertFalse(self._x_accept("fix_accept", reply, 1)["ok"])
        out = self._x_ok("consult_check", reply_variant=support.reply_json(reply), **{"pass": "first"})
        self.assertTrue(out["go"], out)
        answer = {"answers": [{"ask": 1, "decision": "deny", "reason": "見本の入力は直しに要らないので範囲に足さない"}]}
        out = self._x_ok("consult_accept", answer=json.dumps(answer, ensure_ascii=False), **{"pass": "first"})
        self.assertTrue(out["consulted"], out)
        out = self._x_accept("fix_accept", reply, 2)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        self.assertEqual((self.repo / "request_ok.json").read_bytes(), before, "戻したファイルは段の頭の姿")
        self.assertIn("sum(xs) / len(xs)", (self.repo / "stats.py").read_text(encoding="utf-8"))
        kept = json.loads((self.place / "fix-reply.json").read_text(encoding="utf-8"))
        self.assertEqual([c["files"] for c in kept["changes"]], [["stats.py"]])


class FixAcceptCase(_XPlace):
    """修正役の返答の受け付けの、事前審査への応答の照らし"""

    REVIEW = {"faces": [{"key": "穴-平均の分母が空の列で割れる", "kind": "contract_drift", "unit_keys": [_X_MEAN]},
                        {"key": "穴-上限の単位の別の組", "kind": "contract_drift", "unit_keys": [_X_BOUND]}],
              "shrink": [{"key": "別案-len を直に使う", "unit_keys": []}]}

    def test_unanswered_plan_face_is_rejected(self):
        """L-W19・F130: 修正役は事前審査の穴と別案に key ごとに 1 度だけ答える（plan_faces）。答えない key・事前審査に無い key・
        重複を 1 行ずつ拒み、組の子は自分の単位の穴（と単位の無い別案）だけに答える"""
        self._x_json("p2.plan_review.json", self.REVIEW)
        self._x_fix_mean()
        answer = {"key": "穴-平均の分母が空の列で割れる", "handled": "absorbed", "how": "空の列は 0 を返すように分母の前で分けた"}
        bad = {"changes": [_x_change(_X_MEAN, ["stats.py"])],
               "plan_faces": [answer, answer, {**answer, "key": "穴-事前審査に無い key を答えた"}]}
        out = self._x_accept("fix_accept", bad, 1)
        self.assertFalse(out["ok"], out)
        for phrase in ("plan_faces[1] の key が重複", "'穴-事前審査に無い key を答えた' は事前審査に無い", "'別案-len を直に使う' に応答が無い"):
            self.assertIn(phrase, out["reason"])
        self.assertNotIn("穴-上限の単位の別の組", out["reason"], "ほかの組の単位の穴は問わない")
        good = {"changes": [_x_change(_X_MEAN, ["stats.py"])],
                "plan_faces": [answer, {"key": "別案-len を直に使う", "handled": "declared", "how": "len は空の列で 0 割りになるので採らない"}]}
        out = self._x_accept("fix_accept", good, 2)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)

    def test_fix_prompt_pastes_every_key_the_accept_asks(self):
        """#570: 組の子の修正役の指示が貼る事前審査の key は、同じ組の受け付けが「応答が無い」と拒む key と同じ集合"""
        self._x_json("p2.plan_review.json", self.REVIEW)
        out = self._x_ok("fix_prep")
        section = self._x_prompt(out).split(_X_FACES_HEAD, 1)[1]
        pasted = set(re.findall(r"^- `([^`]+)`（(?:穴|別案)", section, re.M))
        self.assertEqual(pasted, {"穴-平均の分母が空の列で割れる", "別案-len を直に使う"})
        self._x_fix_mean()
        out = self._x_accept("fix_accept", {"changes": [_x_change(_X_MEAN, ["stats.py"])]}, 1)
        self.assertFalse(out["ok"], out)
        self.assertEqual(set(re.findall(r"事前審査の '(.+?)' に応答が無い", out["reason"])), pasted)


class HandoffCase(_XPlace):
    """修正役が人に回した物（breaks.accepted）が報告の人が決めることに届く"""

    def test_common_rules_breaks_promise_reaches_the_decisions(self):
        """部分 D2 やる事 1（S03）: 修正役の指示の共通の決まり（workflows/.shared/prompts/writer-rules.md）の「人に回す物は
        breaks.accepted に書け……機械が人に見せる一覧（報告の「人が決めること」）に載せる」が本当になる: 組の子の返答の
        breaks.accepted が組の結果の handoffs と fix の出力の handoffs を通って報告の人が決めることのセクションに 1 件 1 行で出る"""
        board = self.board
        text = self._x_prompt(self._x_ok("fix_prep"))
        self.assertIn("**Write what goes to a person in `breaks.accepted`.**", text)
        self.assertIn("The machine puts them in the list shown to the person (the report's \"what the person decides\")", text)
        reply = {"changes": [{"unit_key": "u1", "breaks": {"accepted": "ADR-3 と食い違う既定を残す（docs/adr/3.md:4）"}}]}
        child = board.group_result({"group_id": "g1", "unit_ids": ["u1"]}, start_tree="t", end_tree="t", tdd=None, reply=reply)
        # 報告の「人が決めること」への組み立ては report の試験。ここは fix の出力の handoffs の欄まで: 1 件 1 行で単位と理由を持つ
        (line,) = board.final_lines([child], "handoffs")
        self.assertIn("u1", line)
        self.assertIn("壊すと分かって通した——ADR-3 と食い違う既定を残す（docs/adr/3.md:4）", line)


if __name__ == "__main__":
    unittest.main()

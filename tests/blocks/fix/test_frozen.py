"""keep-essence の 3（テストの変更の許しは 1 か所。docs/design/fix.md の 10 節）: TDD の輪で凍ったテストのファイルと、裁定
fix_test_scope の範囲（src/tdd.frozen_problems の allowed）の検査と、許しを読む道が lib の conflict.test_permits の 1 つだけかの検査。

裁定が範囲（limits。`<パス>` か `<パス>:<行>[-<行>]`）に並べた所の直しは、凍ったファイルでも拒まない。範囲の外の行・
範囲の無いファイルの変更は今どおり拒む。行は凍った時の木（st["frozen_tree"]。_finish が書く）に対する旧い側で見る。
st["handoff"] は frozen_tree の無い古い状態の時だけの控え。輪で足した未追跡のテストのファイルも同じに見る。
.py の `<パス>:<行>` 1 つは、その行を含む関数の全体に広がる（`<行>-<行>` は書いたとおり）。この試験の「範囲の外の行」は
その広がりの外を指す（広がりの試験は test_tdd.py の FunctionSpanCase）。
種の git は gitkit の型の写し（盤面・子の実行器なし）。元 lib/tests/test_tdd_frozen.py の FrozenRuledScopeCase と
lib/tests/test_conflict_kinds.py の TestReplanState.test_permit_sources_are_read_in_one_place を blocks/fix に向けた物。
"""
import ast
import json
import pathlib
import re
import sys
import tempfile
import unittest

from tests.bin.gitkit import committed_copy
from tests.blocks import kit

tdd = kit.load("fix", "tdd")
FIX_SRC = {n: m for n, m in sys.modules.items() if n == "src" or n.startswith("src.")}
SEED = kit.ROOT / "tests" / "e2e" / "target-seed"
FIX = kit.BLOCKS / "fix"


class Case(unittest.TestCase):
    def run(self, result=None):
        """sys.modules の src をこの block の物に戻す（同じ過程のほかの block の試験の kit.load が src を読み替える）"""
        for name in [n for n in sys.modules if (n == "src" or n.startswith("src.")) and n not in FIX_SRC]:
            del sys.modules[name]
        sys.modules.update(FIX_SRC)
        return super().run(result)


TEST_FILE = "test_stats.py"
NEW_FILE = "test_new.py"   # 輪で足した、まだ追跡されていないテストのファイル
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"   # どのファイルも無い木（控えに使われれば、どの変更も外になる）


class FrozenRuledScopeCase(Case):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = pathlib.Path(self._tmp.name)
        self.repo = tmp / "repo"
        committed_copy(self.repo, SEED)
        (self.repo / NEW_FILE).write_text("import unittest\n\n\nclass T(unittest.TestCase):\n"
                                          "    def test_one(self):\n        self.assertEqual(1, 1)\n", encoding="utf-8")
        self.state = tmp / "state.json"
        self.freeze(frozen_tree=tdd.snapshot(self.repo), handoff=EMPTY_TREE)

    def freeze(self, **trees):
        st = {"frozen": tdd.hashes(self.repo, [TEST_FILE, NEW_FILE]), **trees}
        self.state.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")

    def edit(self, old, new, path=TEST_FILE):
        p = self.repo / path
        text = p.read_text(encoding="utf-8")
        self.assertIn(old, text)
        p.write_text(text.replace(old, new), encoding="utf-8")

    def frozen(self, allowed):
        try:
            return tdd.frozen_problems(str(self.state), self.repo, allowed=allowed)
        except TypeError as e:
            self.fail(f"frozen_problems が裁定の範囲（allowed）を受けない: {e}")

    def test_change_inside_ruled_lines_is_allowed(self):
        self.edit("mean([1, 2, 3]), 2)", "mean([1, 2, 3]), 2.0)")   # 9 行目
        self.assertEqual(self.frozen([f"{TEST_FILE}:9"]), [], "frozen_tree で見る（handoff の空の木で見れば外になる）")

    def test_change_outside_ruled_lines_is_rejected(self):
        self.edit("clamp(5, 0, 10), 5)", "clamp(5, 0, 10), 5.0)")   # 12 行目
        got = self.frozen([f"{TEST_FILE}:9"])
        self.assertTrue(got, "範囲の外の行の変更は拒む")
        self.assertIn(TEST_FILE, " ".join(got))

    def test_ruled_whole_file_allows_any_line(self):
        self.edit("clamp(5, 0, 10), 5)", "clamp(5, 0, 10), 5.0)")
        self.assertEqual(self.frozen([TEST_FILE]), [])

    def test_no_ruling_still_rejects(self):
        self.edit("mean([1, 2, 3]), 2)", "mean([1, 2, 3]), 2.0)")
        self.assertTrue(self.frozen([]), "裁定の無い変更は今どおり拒む")

    def test_untracked_new_file_inside_ruled_lines_is_allowed(self):
        self.edit("assertEqual(1, 1)", "assertEqual(1, 1.0)", NEW_FILE)   # 6 行目
        self.assertEqual(self.frozen([f"{NEW_FILE}:6"]), [])

    def test_untracked_new_file_outside_ruled_lines_is_rejected(self):
        self.edit("class T(", "class U(", NEW_FILE)   # 4 行目（6 行目を含む関数の幅の外）
        got = self.frozen([f"{NEW_FILE}:6"])
        self.assertTrue(got, "未追跡のファイルでも範囲の外の行の変更は拒む")
        self.assertIn(NEW_FILE, " ".join(got))

    # 足しただけの変更（依頼 195i の 2）: 凍ったファイルの既存の文（関数・クラスの頭・モジュールの文・コメント）を 1 つも変えず、
    # 新しい関数・クラス（既存のクラスの中の新しいメソッドも）と、新しい名の import・代入を足しただけなら凍結に数えない。
    # 既存のテストが読む名・枠の掛け金（setUp・pytestmark・autouse の fixture など）に当たる追加は今どおり拒む
    ADDED_METHOD = ("    def test_clamp_below_range(self):\n        self.assertEqual(clamp(-5, 0, 10), 0)\n\n"
                    "    def test_clamp_far_above(self):\n        self.assertEqual(clamp(20, 0, 10), 10)\n")
    ADDED_TOP = ("\n\n# 測りの補い\ndef make_values(n):\n    return list(range(n))\n\n\nLIMIT = 10\n\n\n"
                 "class TestMeasure(unittest.TestCase):\n    def test_values(self):\n        self.assertEqual(len(make_values(3)), 3)\n")

    def test_pure_additions_are_not_frozen(self):
        self.edit("        self.assertEqual(clamp(15, 0, 10), 10)\n",
                  "        self.assertEqual(clamp(15, 0, 10), 10)\n\n" + self.ADDED_METHOD)
        self.edit("\n\nif __name__", self.ADDED_TOP + "\n\nif __name__")
        self.edit("from stats import clamp, mean\n", "from stats import clamp, mean\nimport json\n")
        self.assertEqual(self.frozen([]), [], "既存の文を変えずに足しただけは凍結に数えない")
        self.edit("    def test_values(self):\n", "    def setUp(self):\n        pass\n\n    def test_values(self):\n")
        self.assertEqual(self.frozen([]), [], "新しいクラスの中は自由（既存のテストに効かない）")

    def test_importing_the_module_of_an_existing_from_import_is_not_frozen(self):
        """`from stats import clamp, mean` は名前空間に stats を作らないので、`import stats` を足すのは既存のテストに効かない"""
        self.edit("from stats import clamp, mean\n", "from stats import clamp, mean\nimport stats\n")
        self.edit("\n\nif __name__", "\n\nclass TestModule(unittest.TestCase):\n    def test_mean(self):\n"
                  "        self.assertEqual(stats.mean([2]), 2)\n\n\nif __name__")
        self.assertEqual(self.frozen([]), [])

    def test_additions_with_an_edit_of_existing_lines_are_rejected(self):
        for old, new in [("clamp(5, 0, 10), 5)", "clamp(5, 0, 10), 5.0)"),               # 既存のテストの本体
                         ("class TestStats(unittest.TestCase):", "@unittest.skip('x')\nclass TestStats(unittest.TestCase):"),
                         ("    def test_mean_of_three(self):\n", "    @unittest.skip('x')\n    def test_mean_of_three(self):\n"),
                         ("    def test_clamp_within_range(self):\n        self.assertEqual(clamp(5, 0, 10), 5)\n\n", ""),  # 消した
                         ("if __name__", "# 末尾の書き足し\nif __name__"),                    # 追加に付かないコメント
                         ('"""stats.py の単体テスト。', '"""stats.py の単体テスト（直した）。')]:
            with self.subTest(old=old):
                self.setUp()
                self.edit("\n\nif __name__", self.ADDED_TOP + "\n\nif __name__")
                self.edit(old, new)
                got = self.frozen([])
                self.assertTrue(got and TEST_FILE in got[0], got)

    def test_additions_that_reach_existing_tests_are_rejected(self):
        hooks = [
            "\n\ndef mean(xs):\n    return 2\n",                                   # 既存のテストが読む名を上書き
            "\n\ndef setUpModule():\n    pass\n",                                  # モジュールの掛け金
            "\n\npytestmark = None\n",                                             # pytest の印
            "\n\nimport pytest\n\n\n@pytest.fixture(autouse=True)\ndef _quiet():\n    yield\n",   # 全部のテストに効く fixture
            "\n\nprint('import の時に走る')\n",                                     # 関数・クラス・import・代入でない文
            "\n\ndef test_mean_of_three():\n    pass\n",                             # 既存の名
        ]
        for added in hooks:
            with self.subTest(added=added):
                self.setUp()
                self.edit("\n\nif __name__", added + "\n\nif __name__")
                got = self.frozen([])
                self.assertTrue(got and TEST_FILE in got[0], got)
        for method in ("    def setUp(self):\n        pass\n", "    def assertListEqual(self, a, b):\n        pass\n",
                       "    def _helper(self):\n        pass\n", "    maxDiff = None\n"):
            with self.subTest(method=method):
                self.setUp()
                self.edit("        self.assertEqual(clamp(15, 0, 10), 10)\n",
                          "        self.assertEqual(clamp(15, 0, 10), 10)\n\n" + method)
                got = self.frozen([])
                self.assertTrue(got and TEST_FILE in got[0], f"既存のクラスの掛け金・継いだメソッド・属性: {got}")

    def test_additions_next_to_ruled_lines_are_allowed(self):
        """許しの範囲の中の直しと、範囲の外への足しただけの変更が同じファイルに在っても、足した分は凍結に数えない"""
        self.edit("mean([1, 2, 3]), 2)", "mean([1, 2, 3]), 2.0)")   # 9 行目（範囲の中）
        self.edit("\n\nif __name__", self.ADDED_TOP + "\n\nif __name__")
        self.assertEqual(self.frozen([f"{TEST_FILE}:9"]), [])
        self.edit("clamp(5, 0, 10), 5)", "clamp(5, 0, 10), 5.0)")   # 範囲の外の既存の行
        self.assertTrue(self.frozen([f"{TEST_FILE}:9"]))

    def test_old_state_without_frozen_tree_falls_back_to_handoff(self):
        self.freeze(handoff=tdd.snapshot(self.repo))
        self.edit("mean([1, 2, 3]), 2)", "mean([1, 2, 3]), 2.0)")
        self.assertEqual(self.frozen([f"{TEST_FILE}:9"]), [])


class PermitPathCase(unittest.TestCase):
    """許す元（修正案の rewrite_tests・範囲の相談の合意・裁定 fix_test_scope・案の直しで直した項目）を読むのは lib の
    conflict.test_permits の 1 か所。fix の block（src と scripts）は凍結の検査・事後の関門・範囲の照らしでその行を読み、元を直に読まない"""

    def py_files(self):
        return sorted(p for p in FIX.rglob("*.py") if "__pycache__" not in p.parts)

    def test_permit_sources_are_read_in_one_place(self):
        direct = re.compile(r"\b(?:planmarks\.rewrites|amended_keys|agreed_permits|ruled_limits)\(")
        found = [f"{p.relative_to(FIX)}:{i}" for p in self.py_files()
                 for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if direct.search(line)]
        self.assertEqual(found, [])

    def test_permit_path_is_one(self):
        """src は test_permits・edit_permits を定義せず、呼ぶ時はいつも lib の conflict（`import conflict`）の属性として呼ぶ
        （写しの道を 2 つにしない）"""
        names = {"test_permits", "edit_permits"}
        src = sorted((FIX / "src").glob("*.py"))
        self.assertTrue(src)
        defined, stray, calls = [], [], 0
        for path in self.py_files():
            tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
            lib_conflict = any(isinstance(n, ast.Import) and any(a.name == "conflict" and a.asname in (None, "conflict")
                                                                  for a in n.names) for n in ast.walk(tree))
            for node in ast.walk(tree):
                where = f"{path.relative_to(FIX)}:{getattr(node, 'lineno', 0)}"
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names and path in src:
                    defined.append(where)
                elif isinstance(node, ast.ImportFrom) and any(a.name in names for a in node.names):
                    stray.append(where)
                elif isinstance(node, ast.Call):
                    f = node.func
                    if isinstance(f, ast.Name) and f.id in names:
                        stray.append(where)
                    elif isinstance(f, ast.Attribute) and f.attr in names:
                        if isinstance(f.value, ast.Name) and f.value.id == "conflict" and lib_conflict:
                            calls += 1
                        else:
                            stray.append(where)
        self.assertEqual(defined, [], "src に許しの読みの写しを持たない")
        self.assertEqual(stray, [], "許しの読みは lib の conflict の属性としてだけ呼ぶ")
        self.assertGreater(calls, 0, "src は許しを lib の conflict から読む（読む所が在る）")
        self.assertEqual(pathlib.Path(sys.modules["conflict"].__file__).resolve().parent.name, "lib", "conflict は lib の物")

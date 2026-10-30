"""works の範囲の宣言（lib/checkscope.py）の検査。元の場合は今の works の tests/test_ci_test_cmd.py の ScopeDeclarationShapeCase・
RepoDeclarationScopeCase と tests/test_board_engine_run.py の ScopedStepsCase（各試験の docstring に元の名）。

- read_scope: 無ければ空。書式の誤り・宣言の段に無い名は、宣言の名を名指した理由
- skipped_steps: 変更が全部 paths_ignore の下の段だけを外す。全段が外れる時・変更を測れない時・口が無い時は絞らない。
  範囲を持つ段が無ければ変更を測らない
- scope_word・skipped_text: 素材の文と報告の行が出す字
"""
import pathlib
import shutil
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import checkscope  # noqa: E402
from tests.bin.gitkit import git  # noqa: E402

STEPS = [{"name": "far", "argv": ["x"]}, {"name": "near", "argv": ["y"]}]
SCOPE = {"far": ["works/"]}
FAR_SKIPPED = [{"name": "far", "paths_ignore": ["works/"]}]


class ReadScopeCase(unittest.TestCase):
    """元 test_ci_test_cmd.py の ScopeDeclarationShapeCase"""
    SHAPE_STEPS = [{"name": "suite", "argv": ["x"]}, {"name": "root", "argv": ["y"]}]

    def read(self, text):
        d = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        if text is not None:
            (d / checkscope.SCOPE_DECL).write_text(text, encoding="utf-8")
        return checkscope.read_scope(d, self.SHAPE_STEPS)

    def test_absent_declaration_scopes_nothing(self):
        """元 ScopeDeclarationShapeCase.test_absent_declaration_scopes_nothing"""
        self.assertEqual(self.read(None), ({}, None))

    def test_good_declaration_maps_step_to_ignored_paths(self):
        """元 ScopeDeclarationShapeCase.test_good_declaration_maps_step_to_ignored_paths"""
        self.assertEqual(self.read('{"suite": {"paths_ignore": ["works/", "docs"]}}'), ({"suite": ["works/", "docs"]}, None))

    def test_bad_shapes_are_named(self):
        """元 ScopeDeclarationShapeCase.test_bad_shapes_are_named"""
        for bad in ("{", "[]", '{"suite": ["works/"]}', '{"suite": {}}', '{"suite": {"paths_ignore": ["works/"], "x": 1}}',
                    '{"suite": {"paths_ignore": "works/"}}', '{"suite": {"paths_ignore": 3}}', '{"suite": {"paths_ignore": []}}',
                    '{"suite": {"paths_ignore": [""]}}', '{"suite": {"paths_ignore": ["/abs"]}}',
                    '{"suite": {"paths_ignore": ["../x"]}}', '{"suite": {"paths_ignore": ["./"]}}', '{"suite": {"paths_ignore": [3]}}'):
            with self.subTest(bad):
                ignores, why = self.read(bad)
                self.assertIsNone(ignores)
                self.assertIn(checkscope.SCOPE_DECL, why)

    def test_undeclared_step_name_is_named(self):
        """元 ScopeDeclarationShapeCase.test_undeclared_step_name_is_named"""
        ignores, why = self.read('{"siute": {"paths_ignore": ["works/"]}}')
        self.assertIsNone(ignores)
        self.assertIn("siute", why)
        self.assertIn(".review-checks.json", why)


class SkippedStepsCase(unittest.TestCase):
    """元 test_board_engine_run.py の ScopedStepsCase と test_ci_test_cmd.py の RepoDeclarationScopeCase（盤面と本物の宣言を外し、
    skipped_steps を直に呼ぶ）"""

    def skipped(self, changed, steps=STEPS, ignores=SCOPE):
        return checkscope.skipped_steps(steps, ignores, changed)

    def test_change_all_under_ignored_skips_step_and_names_it(self):
        """元 ScopedStepsCase.test_change_all_under_ignored_skips_step_and_names_it・RepoDeclarationScopeCase.test_works_only_change_skips_graphloops_suite"""
        self.assertEqual(self.skipped(lambda: ["works/a.py", "works/b/c.py"]), FAR_SKIPPED)

    def test_change_outside_ignored_runs_every_step(self):
        """元 ScopedStepsCase.test_change_outside_ignored_runs_every_step・RepoDeclarationScopeCase.test_change_outside_works_runs_graphloops_suite"""
        for changed in (["works/a.py", "graphloops/b.py"], ["graphloops/b.py"], ["worksX/a.py"], ["README.md"]):
            with self.subTest(changed):
                self.assertEqual(self.skipped(lambda: changed), [])

    def test_ignored_path_matches_file_or_folder_head(self):
        self.assertEqual(self.skipped(lambda: ["works"], ignores={"far": ["works"]}), [{"name": "far", "paths_ignore": ["works"]}])

    def test_sibling_with_same_prefix_is_not_under(self):
        """範囲はパスの頭の字でなく区切りで見る: 頭の字だけが同じ隣のフォルダ（works2）は works の下でない"""
        self.assertEqual(self.skipped(lambda: ["works2/a.py"], ignores={"far": ["works"]}), [])

    def test_unmeasured_change_runs_every_step(self):
        """元 ScopedStepsCase.test_unmeasured_change_runs_every_step: 変更を測れない（口が None・空を返す）・口が無い回は絞らない"""
        for changed in (lambda: None, lambda: [], None):
            with self.subTest(changed):
                self.assertEqual(self.skipped(changed), [])

    def test_changed_is_not_asked_without_scoped_step(self):
        """元 ScopedStepsCase.test_changed_is_not_asked_without_scope_declaration: 範囲を持つ段が無ければ変更を測らない"""
        self.assertEqual(self.skipped(lambda: self.fail("変更を測った"), ignores={}), [])

    def test_every_step_out_of_scope_runs_them_all(self):
        """元 ScopedStepsCase.test_every_step_out_of_scope_runs_them_all: 全段が外れる変更では絞らない——1 段も回さない緑を作らない"""
        self.assertEqual(self.skipped(lambda: ["works/a.py"], steps=[STEPS[0]]), [])
        self.assertEqual(self.skipped(lambda: ["works/a.py"], ignores={"far": ["works/"], "near": ["works/"]}), [])


class WordsCase(unittest.TestCase):
    def test_scope_word_and_skipped_text(self):
        """元 test_ci_test_cmd.py の OutOfScopeLineCase と ScopedStepsCase の素材の字"""
        two = {"name": "far", "paths_ignore": ["works/", "docs"]}
        self.assertEqual(checkscope.scope_word(two), "far（変更が全部 works/・docs の下で、段が見ない所）")
        self.assertEqual(checkscope.skipped_text(FAR_SKIPPED),
                         "範囲の外で回さなかった段: far（変更が全部 works/ の下で、段が見ない所）")



class RequestFilesCase(unittest.TestCase):
    def test_where_names_a_tracked_path_by_its_whole_name(self):
        """where の字に区切りを見て現れる追跡中のパスだけ（長い名の一部の字は数えない）"""
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("a.py", "data.py", "pkg/b.py"):
                (pathlib.Path(tmp) / name).parent.mkdir(parents=True, exist_ok=True)
                (pathlib.Path(tmp) / name).write_text("x\n", encoding="utf-8")
            git(tmp, "init", "-q")
            git(tmp, "add", "-A")
            self.assertEqual(checkscope.request_files(tmp, ["data.py:3 の数え", "pkg/b.py の頭"]), ["data.py", "pkg/b.py"])
            self.assertEqual(checkscope.request_files(tmp, ["mypkg/b.pyc"]), [])

    def test_where_names_a_path_with_dot_or_absolute_head(self):
        """頭の ./ と絶対パスの中の、追跡中のパスも拾う"""
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("src/a.py", "src/b.py"):
                (pathlib.Path(tmp) / name).parent.mkdir(parents=True, exist_ok=True)
                (pathlib.Path(tmp) / name).write_text("x\n", encoding="utf-8")
            git(tmp, "init", "-q")
            git(tmp, "add", "-A")
            self.assertEqual(checkscope.request_files(tmp, ["./src/a.py:3 の数え", "/home/u/proj/src/b.py の頭"]), ["src/a.py", "src/b.py"])


if __name__ == "__main__":
    unittest.main()

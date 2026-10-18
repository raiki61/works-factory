"""根からの相対のパスの glob の読み（globs）。誤りの文（glob_problem）・当たり（glob_match）・交わり（globs_meet）が同じ読み
（末尾 / はその下の全部）を引くことと、守りのファイルの当て方（protect.match）がその読みのままであることを、関数を直に呼んで見る"""
import ast
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import globs  # noqa: E402
import protect  # noqa: E402


class GlobsCase(unittest.TestCase):
    def test_glob_without_a_literal_character_is_a_whole_tree_allowance(self):
        """字の無い glob（* と ? と [..] と / と . だけ）は全部に当たり得る丸ごとの許しなので拒む（**/?* は全部の段が * か ** でないが
        全部のファイルに当たる）。字の在る glob は通す"""
        for g in ("**/?*", "?*", "?", "*/?", "**/[a-z]*", "[!.]*", "**/*?", "*/**/*", "[]]*",
                  "**/*.*", "*.*", "**/.*"):   # 字が . だけの glob も拡張子を持つ全部・隠しの全部に当たる
            with self.subTest(g):
                self.assertIn("丸ごと", globs.glob_problem(g) or "")
        for g in ("*.py", "**/*.md", "src/**", "a?.py", "[ab].py", "docs/*", "**/test_*.py", "x", ".github/**"):
            with self.subTest(g):
                self.assertIsNone(globs.glob_problem(g))

    def test_globs_meet_only_says_no_when_no_path_can_match_both(self):
        for a, b in (("stats.py", "stats.py"), ("lib/a.py", "lib/*.py"), ("lib/**", "lib/x/y.py"), ("**/x.py", "a/x.py"),
                     ("tests/test_*.py", "tests/test_a*.py")):
            with self.subTest(a=a, b=b):
                self.assertTrue(globs.globs_meet(a, b))
                self.assertTrue(globs.globs_meet(b, a))
        for a, b in (("lib/a.py", "lib/b.py"), ("lib/*.py", "lib/*.md"), ("docs/**", "lib/**"), ("lib/*.py", "lib/x/a.py")):
            with self.subTest(a=a, b=b):
                self.assertFalse(globs.globs_meet(a, b))
                self.assertFalse(globs.globs_meet(b, a))

    def test_globs_meet_is_true_when_an_argument_is_not_a_string(self):
        """文字列でない引数は言い切れない時なので、交わると見る（組分けの保守側）"""
        for a, b in ((None, "a"), ("a", None), ("a", 1), (1, "a")):
            with self.subTest(a=a, b=b):
                self.assertTrue(globs.globs_meet(a, b))

    def test_globs_meet_reads_trailing_slash_like_glob_match(self):
        """末尾 / はその下の全部（glob_match と同じ _dir_glob の 1 か所から引く）と読む: 'a/' は 'a' と交わらず、a/x・a/** と交わり、
        同じパスに当たる glob の対は交わる"""
        self.assertFalse(globs.globs_meet("a/", "a"))
        self.assertFalse(globs.globs_meet("a", "a/"))
        self.assertTrue(globs.globs_meet("a/", "a/x"))
        self.assertTrue(globs.globs_meet("a/", "a/**"))
        pats = ["a/", "a", "a/*", "a/**", "lib/*.py", "lib/a.py"]
        paths = ["a/", "a", "a/x", "a/x/y", "lib/a.py"]
        for x in pats:
            for y in pats:
                for p in paths:
                    if globs.glob_match(p, x) and globs.glob_match(p, y):
                        with self.subTest(x=x, y=y, path=p):
                            self.assertTrue(globs.globs_meet(x, y))
        for g in ("a/", "a/**/", "lib/*/"):
            for p in ("a", "a/x", "a/x/y", "lib", "lib/a", "lib/a/x.py"):
                with self.subTest(glob=g, path=p):
                    self.assertEqual(globs.glob_match(p, g), globs.globs_meet(g, p))

    def test_glob_problem_reads_trailing_slash_as_dir_and_rejects_doubled_slash(self):
        """末尾 / はその下の全部（'/**' と同じ）と読む: 'lib/'・'a/**/'・'lib/*/' は通し、整えない綴り 'lib//'・'a//' と丸ごとの許し
        '**/'・'*/' は拒む"""
        for g in ("lib/", "a/**/", "lib/*/"):
            with self.subTest(g):
                self.assertIsNone(globs.glob_problem(g))
        for g in ("lib//", "a//"):
            with self.subTest(g):
                self.assertIn("整えた形でない", globs.glob_problem(g) or "")
        for g in ("**/", "*/"):
            with self.subTest(g):
                self.assertIn("丸ごと", globs.glob_problem(g) or "")

    def test_glob_match_reads_trailing_slash_as_everything_underneath(self):
        """末尾 / の glob は根からの相対の 'lib/**' と読む: その下のどの深さにも当たり、'lib' そのもの・名の似た別のディレクトリ・
        深い所の同じ名には当たらない"""
        for p in ("lib/planmarks.py", "lib/a/x.py", "lib/"):
            with self.subTest(p):
                self.assertTrue(globs.glob_match(p, "lib/"))
        self.assertTrue(globs.glob_match("lib/t/x.py", "lib/*/"))
        for p in ("lib", "libx/a.py", "docs/lib/a.py"):
            with self.subTest(p):
                self.assertFalse(globs.glob_match(p, "lib/"))


class ProtectReadsGlobsCase(unittest.TestCase):
    def test_protect_matches_with_globs_and_does_not_import_planmarks(self):
        """守りのファイルの当て方は範囲の欄と同じ読みで、計画の欄のモジュール（planmarks）に頼らない"""
        for pattern, path in (("a/*.py", "a/x.py"), ("a/**/c.py", "a/c.py"), ("lib/", "lib/a/x.py"), ("lib/", "lib"),
                              ("a/[!x].py", "a/y.py")):
            with self.subTest(pattern=pattern, path=path):
                self.assertEqual(protect.match(path, pattern), globs.glob_match(path, pattern))
        tree = ast.parse((LIB / "protect.py").read_text(encoding="utf-8"))
        names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        names |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        self.assertIn("globs", names)
        self.assertNotIn("planmarks", names)


if __name__ == "__main__":
    unittest.main()

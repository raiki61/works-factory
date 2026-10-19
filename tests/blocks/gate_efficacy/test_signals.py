"""ゲートの印 blocks/gate-efficacy/src/signals.py（写す元 lib/tests/test_judge_accept.py の GateSignalsCase）"""
import unittest

from tests.blocks import kit


class GateSignalsCase(unittest.TestCase):
    """差分に機械が見るゲートの印（テスト・CI・pre-commit・変異の腕の一覧などの定義のファイルと、assert を足す・消す行）"""
    DOCSTRING_DIFF = ('diff --git a/calc.py b/calc.py\n--- a/calc.py\n+++ b/calc.py\n@@ -9,7 +9,7 @@ def mean(xs):\n def median(xs):\n'
                      '-    """中央値"""\n+    """中央値（並べた真ん中）"""\n     if not xs:\n')

    def setUp(self):
        self.signals = kit.load("gate-efficacy", "signals")

    @staticmethod
    def assert_diff(sign):
        return ("diff --git a/calc.py b/calc.py\n--- a/calc.py\n+++ b/calc.py\n@@ -1,3 +1,3 @@\n def clamp(x, lo, hi):\n"
                f"{sign}    assert lo <= hi, 'lo > hi'\n     return min(max(x, lo), hi)\n")

    def test_docstring_only_diff_has_no_signal(self):
        self.assertEqual(self.signals.gate_signals(["calc.py"], self.DOCSTRING_DIFF), [])

    def test_gate_files_are_signals(self):
        for f in ("tests/test_calc.py", "test_calc.py", "calc_test.go", "src/calc.test.ts", "conftest.py",
                  ".github/workflows/ci.yml", ".gitlab-ci.yml", ".pre-commit-config.yaml", ".husky/pre-commit",
                  ".review-checks.json", ".works-checks.json", "pyproject.toml", "Makefile", "package.json", ".eslintrc.json",
                  "tox.ini", "pytest.ini", "mypy.ini", "setup.cfg"):
            with self.subTest(f):
                got = self.signals.gate_signals(["calc.py", f], "")
                self.assertEqual(len(got), 1, got)
                self.assertIn(f, got[0])

    def test_added_or_removed_assert_is_a_signal(self):
        for sign in "+-":
            with self.subTest(sign):
                got = self.signals.gate_signals(["calc.py"], self.assert_diff(sign))
                self.assertEqual(len(got), 1, got)
                self.assertIn("assert", got[0])

    def test_context_assert_is_not_a_signal(self):
        """変えていない行（頭が空白）の assert は差分がゲートを変えた印にならない"""
        self.assertEqual(self.signals.gate_signals(["calc.py"], self.assert_diff(" ")), [])

    def test_diff_header_lines_are_not_assert_lines(self):
        """ファイル名に assert を含む差分の頭の ---/+++ の行は assert の行に数えない"""
        diff = ("diff --git a/assert_util.py b/assert_util.py\n--- a/assert_util.py\n+++ b/assert_util.py\n"
                "@@ -1,2 +1,2 @@\n-x = 1\n+x = 2\n")
        self.assertEqual(self.signals.gate_signals(["assert_util.py"], diff), [])

    def test_file_under_tests_dir_is_a_signal_without_test_prefix(self):
        for f in ("tests/helper.py", "test/helper.py", "src/tests/helper.py"):
            with self.subTest(f):
                got = self.signals.gate_signals(["calc.py", f], "")
                self.assertEqual(len(got), 1, got)
                self.assertIn(f, got[0])

    def test_unreadable_diff_gives_no_answer(self):
        """差分のファイルが読めなければ印の有無を言えない（None。役の『条件外』を受けない側）"""
        view = type("V", (), {"diff_file": "/nonexistent/diff.patch", "changed_files": ("calc.py",)})()
        self.assertIsNone(self.signals.signals_of(view))


if __name__ == "__main__":
    unittest.main()

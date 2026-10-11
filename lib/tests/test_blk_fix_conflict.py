"""食い違いの申し出と裁定の検査のうち、lib/ の部品（conflict・planmarks）を直に呼ぶ物。

- テストの変更の許しの行の引き方（修正案の時と凍結の検査の時）と、最後の関所の行の組み方（同じ理由は 1 度だけ）
- 範囲の文字列の読み（`..foo/` は根の中のフォルダ、`../` の上りと絶対パスは捨てる）
- 止めた単位の trace の語の正本は conflict に 1 つ（lib のほかのモジュールは字の写しを持たない）
盤面・git・子のプロセスは使わない（一時の置き場のフォルダに控えのファイルを書くだけ）。
"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import conflict  # noqa: E402
import planmarks  # noqa: E402

WHY = "テストは分母 len(xs) - 1 の値を期待しているが、依頼は算術平均を求めている"
MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"


class TestPermitsOnRawBoard(unittest.TestCase):
    """控えのファイルだけを置いた置き場のフォルダで、許しの行の引き方と最後の関所の行の組み方を見る"""
    TWO = "import unittest\nclass A(unittest.TestCase):\n    def test_x(self):\n        pass\nclass B(unittest.TestCase):\n" \
          "    def test_x(self):\n        pass\n"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)
        self.b = self.dir   # 置き場のフォルダのパス（元は dir・round・work を持つ軽い盤面）

    def test_trailing_slash_id_names_the_class_at_plan_and_frozen_time(self):
        """id のパスを書いたまま（t.py/）でなく、整えたパス（t.py）で .py かを決める（A::test_x の行に広げない）"""
        repo = self.dir / "repo"
        repo.mkdir()
        (repo / "t.py").write_text(self.TWO, encoding="utf-8")
        tid = "t.py/::B::test_x"
        self.assertEqual(planmarks.find_test(repo, tid), 6)
        row = {"id": tid, "behavior": "B の振る舞いが依頼で変わる", "old": "pass のまま", "new": "新しい期待を書く行に変える"}
        _, fields = planmarks.split({"plan": [{"rewrite_tests": [row]}]}, repo)
        self.assertEqual(fields[0]["rewrite_tests"][0]["limit"], "t.py:6", "修正案の時")
        planmarks.save(self.dir, 1, fields)
        self.assertEqual(conflict.ruled_test_limits(self.b, rulings=False, source=lambda p: self.TWO if p == "t.py" else None),
                         ["t.py:6"], "凍結の検査の時")

    def test_same_reason_with_slash_listed_once(self):
        """1 つの裁定が同じファイルに 2 つの範囲を許しても、理由は 1 度だけ（理由の文に " / " が在っても）"""
        text = "期待は float / int のどちらでもよいと依頼に在るので、範囲の 2 か所を直してよい"
        (self.dir / conflict.FILE).write_text(json.dumps({"items": [
            {"id": "c1-1", "unit_key": MEAN, "between": ["stats.py:9", "test_stats.py:9"], "why_both_cannot_hold": WHY,
             "which_is_right": "test", "ruling": {"decision": "fix_test_scope", "text": text,
                                                   "limits": ["test_stats.py:8", "test_stats.py:14"]}}]}, ensure_ascii=False),
            encoding="utf-8")
        rows = conflict.ruled_test_doc(self.b)["rules"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["why"].count(text), 1, rows[0]["why"])


class TestParseLimitDots(unittest.TestCase):
    def test_dotdot_prefixed_dir_kept_and_climb_dropped(self):
        """`..foo/x.py` は根の中のディレクトリ `..foo` の物（planmarks.gaps が通す範囲を受け付けで捨てない）。`../` の上りは今どおり捨てる"""
        self.assertEqual(conflict.parse_limit("..foo/x.py:3"), ("..foo/x.py", (3, 3)))
        self.assertIsNone(conflict.parse_limit("../x.py:3"))
        self.assertIsNone(conflict.parse_limit("/x.py:3"))


class TestParkedOpSingleSource(unittest.TestCase):
    """止めた単位の trace の語 fix_bound_parked の正本は conflict に 1 つ。lib のほかのモジュールは字の写しを持たない"""

    WORD = "fix_bound_parked"

    def test_word_has_one_source_in_lib(self):
        self.assertEqual(getattr(conflict, "ACCEPT_PARKED_OP", None), self.WORD)
        for path in sorted(LIB.glob("*.py")):
            if path.name == "conflict.py":
                continue
            src = path.read_text(encoding="utf-8")
            self.assertNotIn(f'"{self.WORD}"', src, f"{path.name} に字の写しが残っている")
            self.assertNotIn(f"'{self.WORD}'", src, f"{path.name} に字の写しが残っている")


if __name__ == "__main__":
    unittest.main()

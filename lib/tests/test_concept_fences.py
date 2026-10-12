"""考えの住処の柵の表の読み（lib/conceptfence.py の check_table。run の中の構造のブロックが対象の表に当てる）。
"""
import pathlib
import re
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import conceptfence  # noqa: E402


class CheckTableCase(unittest.TestCase):
    BOUND = {"what": "語", "pattern": r"\bmodel\b", "allowed": [], "known": {},
             "bound": [{"paths": ["blk-*/*.yaml"], "lines": r"^\s*model:", "by": "tests/test_b.py", "why": "試験が源と縛る"}]}

    def test_check_table_refuses_broken_bound(self):
        """表の読み（tables が対象の表に当てる確かめ）は、bound が配列でない・paths が配列でない・lines が正規表現でない・
        by が無い表を拒む（ValueError か re.error）"""
        conceptfence.check_table({"concepts": {"a": {"fences": [self.BOUND]}}})
        for bad in ("x", ["x"], [{"paths": "x", "lines": "a", "by": "t"}], [{"paths": ["x"], "lines": "(", "by": "t"}],
                    [{"paths": ["x"], "lines": "a"}]):
            with self.subTest(bad=bad):
                with self.assertRaises((ValueError, re.error)):
                    conceptfence.check_table({"concepts": {"a": {"fences": [dict(self.BOUND, bound=bad)]}}})



# 柵 entry-kind（元 works/docs/concepts.json の entry-kind の 2 つの柵。語の形は元の字。2 つ目の「base.from での分岐」の形だけは、
# 比べる相手を入口の種の語（head・base・pr）に限る: 元の形は `["from"] != ...` を全部数え、判定の受け付けの写しの道の
# 指し先（lib/judge_accept.py の w["from"] != "$"。入口の種類と別の考え）にも当たる）
ENTRY_KIND = (
    {"what": "入口の生の入力（差分の根の名指し base・pr）を読む・渡す形",
     "pattern": r"_word\(raw, [\"'](base|pr)[\"']\)|\bINPUTS_(BASE|PR)\b|\$INPUTS\.(base|pr)\b|\bCHANGE_INPUT\b|--(base|pr)\b",
     "allowed": ["lib/entryshape.py", "workflows/line/scripts/start.py"], "known": {}},
    {"what": "入口の種類で分かれる形と消した種の名（差分の根の出どころ base.from での分岐ほか）",
     "pattern": r"\bentry_words\b|\bENTRIES\b|\bchange_only\b|add_pending_request|PENDING_WAIT_NODE|PENDING_REQUEST_BY|"
                r"\[[\"']from[\"']\]\s*[!=]=\s*[\"'](head|base|pr)[\"']|\.get\([\"']from[\"']\)\s*[!=]=\s*[\"'](head|base|pr)[\"']|"
                r"kind == [\"'](request|change|both)[\"']",
     "allowed": ["lib/entryshape.py"], "known": {}},
)
ENTRY_KIND_EXCLUDE = ["tests/**", "lib/tests/**", "docs/**", "README.md", "**/fixtures/**", "lib/graphloops/**", "factory/**",
                      "harness/**", ".github/**", "*.md"]


class FenceCase(unittest.TestCase):
    def test_entry_kind_read_only_by_entryshape(self):
        """L-E55: 入口の種類（依頼・base・PR）を知るのは入口の変換（lib/entryshape.py と線の start）だけ（元 works/tests/
        test_entry_block.py の ConversionLayerCase.test_only_conversion_layer_knows_entry_kind）。外の当たりは 0 件"""
        paths = cf().tracked(LIB.parent)
        self.assertIn("lib/entryshape.py", paths)
        for fence in ENTRY_KIND:
            with self.subTest(fence["what"]):
                self.assertEqual(cf().scan(LIB.parent, paths, fence, ENTRY_KIND_EXCLUDE), {})
        with tempfile.TemporaryDirectory() as tmp:   # 柵が本当に当たる: 入口の種類で分かれる行と生の入力の読みを数える
            (pathlib.Path(tmp) / "x.py").write_text('if base["from"] == "pr":\n    pass\nb = _word(raw, "base")\n'
                                                     'w = step["from"] != "$"\n', encoding="utf-8")
            self.assertEqual([cf().scan(tmp, ["x.py"], fence, []) for fence in ENTRY_KIND], [{"x.py": 1}, {"x.py": 1}])


if __name__ == "__main__":
    unittest.main()

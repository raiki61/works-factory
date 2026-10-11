"""止めの理由の住処（.shared/core/stopby.py。考え stop-reasons）の検査。

表の名と定数が揃うこと・ブロックとラインが足す口（declare）の決まり・pack の中の declare の名が重ならないこと・
語の字が変わっていないこと（盤面・報告・固定材料に残る字。前の盤面の止めを読み違えない）・住処の外に語の字が漏れないことを見る。
関数を直に呼ぶのと、pack の .py を ast で読むだけ（git ls-files のほか、盤面・子のプロセスなし）。
"""
import ast
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

SKIP = ("graphloops/",)


def stopby():
    import stopby as m   # 住処（遅らせて読む。無ければその試験だけが落ちる）
    return m


def pack_py():
    """pack（dev・tests・docs と写しの外）の .py"""
    for p in sorted(LIB.rglob("*.py")):
        rel = p.relative_to(LIB).as_posix()
        if rel.split("/")[0] in ("dev", "tests", "docs") or rel.startswith(SKIP):
            continue
        yield rel, ast.parse(p.read_text(encoding="utf-8"))


class Table(unittest.TestCase):
    def test_constants_match_table(self):
        """定数はちょうど表の名に頭を付けた語（名の - は _、大文字）"""
        m = stopby()
        consts = {k: v for k, v in vars(m).items() if k.isupper() and isinstance(v, str) and v.startswith(m.HEAD) and v != m.HEAD}
        self.assertEqual(consts, {n.upper().replace("-", "_"): m.HEAD + n for n in m.REASONS})
        for n, why in m.REASONS.items():
            self.assertTrue(m.NAME.fullmatch(n), n)
            self.assertTrue(why.strip(), n)

    def test_word_refuses_unknown(self):
        with self.assertRaises(KeyError):
            stopby().word("no-such-reason")

    def test_is_line(self):
        m = stopby()
        self.assertTrue(m.is_line(m.FIX))
        for by in ("human:final-gate", "request:me", "answer", "hand-placed", "", None, 3):
            self.assertFalse(m.is_line(by), by)


class Declare(unittest.TestCase):
    def setUp(self):
        self.m = stopby()
        saved = dict(self.m._DECLARED)   # 足した名を試験の外へ持ち越さない（読み込んだブロックが足した名は戻す）
        self.m._DECLARED.clear()

        def back():
            self.m._DECLARED.clear()
            self.m._DECLARED.update(saved)
        self.addCleanup(back)

    def test_declare_returns_word_and_is_idempotent(self):
        self.assertEqual(self.m.declare("t-own", "試験の語"), "works:t-own")
        self.assertEqual(self.m.declare("t-own", "試験の語"), "works:t-own")   # 読み直し（reload・2 度の import）
        self.assertEqual(self.m.declared(), {"t-own": "試験の語"})
        self.assertEqual(self.m.word("t-own"), "works:t-own")

    def test_declare_refuses(self):
        self.m.declare("t-own", "試験の語")
        for name, meaning in (("t-own", "別の意味"), ("fix", "修正の段"), ("Bad", "x"), ("a--b", "x"), ("t-x", " "),
                              ("works:x", "x")):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.m.declare(name, meaning)


class Pack(unittest.TestCase):
    def test_attributes_exist(self):
        """pack が引く stopby.<名> は住処に在る（字の誤りを走る前に見る）"""
        m = stopby()
        for rel, tree in pack_py():
            for n in ast.walk(tree):
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "stopby":
                    with self.subTest(file=rel, attr=n.attr):
                        self.assertTrue(hasattr(m, n.attr))


if __name__ == "__main__":
    unittest.main()

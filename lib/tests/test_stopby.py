"""止めの理由の住処（lib/stopby.py。考え stop-reasons）の検査。

表の名と定数が揃うこと・ブロックとラインが足す口（declare）の決まり・同じ名の declare は同じ意味であること・
pack が引く stopby の名が在ることを見る。関数を直に呼ぶのと、lib と pack（block の src・scripts）の .py を ast で読むだけ（子のプロセスなし）。
"""
import ast
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
ROOT = LIB.parent
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from tests.blocks.kit import BLOCKS as WORKFLOWS  # noqa: E402  （pack のフォルダ。入れ替えの前も後も同じ口）

SKIP = ("graphloops/",)
WAITING_WORDS = frozenset({
    "works:answer-redirected", "works:conflict", "works:needs-human", "works:replan", "works:spec-changed", "works:tdd-repeat",
    "works:unrestored",
})


def stopby():
    import stopby as m   # 住処（遅らせて読む。無ければその試験だけが落ちる）
    return m


def pack_py():
    """lib（試験と写しの外）の .py と、pack の block の src・scripts の .py（組み込みで止めの語の declare は block へ移った）"""
    for p in sorted(LIB.rglob("*.py")):
        rel = p.relative_to(LIB).as_posix()
        if rel.split("/")[0] in ("dev", "tests", "docs") or rel.startswith(SKIP):
            continue
        yield rel, ast.parse(p.read_text(encoding="utf-8"))
    for p in sorted([*WORKFLOWS.glob("*/src/*.py"), *WORKFLOWS.glob("*/scripts/*.py")]):
        yield p.relative_to(ROOT).as_posix(), ast.parse(p.read_text(encoding="utf-8"))


def declares():
    """[(ファイル, 名, 意味)]: lib の stopby.declare("名", "意味") の呼び出し（字の定数だけ）"""
    out = []
    for rel, tree in pack_py():
        for n in ast.walk(tree):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "declare"
                    and isinstance(n.func.value, ast.Name) and n.func.value.id == "stopby"):
                args = [a.value if isinstance(a, ast.Constant) else None for a in n.args]
                out.append((rel, *args))
    return out


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
    def test_declares_are_literal_unique_and_outside_table(self):
        """lib と block の declare は字の定数で、表の名でなく、同じ名を足す所はどれも同じ意味を言う（declare は同じ意味なら何度でも
        通る。judge の graph は diagnose・spec の block と同じ名を同じ意味で足す）"""
        m = stopby()
        rows = declares()
        self.assertTrue(rows)
        for rel, name, meaning in rows:
            with self.subTest(file=rel, name=name):
                self.assertIsInstance(name, str)
                self.assertIsInstance(meaning, str)
                self.assertTrue(m.NAME.fullmatch(name), name)
                self.assertNotIn(name, m.REASONS)
        meanings = {}
        for _, name, meaning in rows:
            meanings.setdefault(name, set()).add(meaning)
        self.assertEqual({n: m for n, m in meanings.items() if len(m) > 1}, {})

    def test_waiting_words_unchanged(self):
        """人の答えを待つ語の集まり WAITING は WAITING_WORDS と同じ（足す・外すなら WAITING_WORDS も直す）。語が WAITING から抜けると、
        報告の結末が needs_human でなく stopped_by_line（種 halted）になり、周の鎖の pick がその周の差分を採らずに飛ばす。
        この照らしのほかに、それを赤にする試験は無い（2026-11-10 の削りで壊して確かめた）"""
        m = stopby()
        self.assertEqual(m.WAITING, WAITING_WORDS)

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

"""止めの理由の住処（lib/stopby.py。考え stop-reasons）の検査。

表の名と定数が揃うこと・ブロックとラインが足す口（declare）の決まり・同じ名の declare は同じ意味であること・
語の字が変わっていないこと（報告・次の run の依頼に残る字。前の run の止めを読み違えない）・住処の外に語の字が漏れないことを見る。
関数を直に呼ぶのと、lib と pack（block の src・scripts）と線の script と境の .py を ast で読むだけ（子のプロセスなし）。
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
# 報告と次の run の依頼に残る語の字（変えると前の run の止めを読み違える）。表の語と、lib と block が declare で足す語
WORDS = frozenset({
    "works:adapter", "works:ci", "works:conflict", "works:delta", "works:empty-fix", "works:fix", "works:lens",
    "works:plan-converge", "works:pr", "works:premises", "works:purpose", "works:refix", "works:rejudge",
    "works:rejudge-session", "works:replan", "works:scope-check", "works:spec-changed", "works:suite-broken", "works:tdd-repeat", "works:unrestored",
    "works:start-refused", "works:needs-human", "works:line-script",
    "works:rule-give-up", "works:clash-ruled-give-up", "works:judge", "works:judge-verify", "works:spec", "works:material", "works:request",
    "works:spec-entry", "works:spec-mismatch", "works:spec-objection",
})
# 線の script と境（workflows/line/scripts/・workflows/.shared/）で止めの語の字の写しを持ってよい所: lib を読めない時の返り
# （lib を読めないので stopby を引けない）。値は stopby の定数と同じでなければならない
COPIES = {
    ("workflows/line/scripts/result.py", "LINE_SCRIPT"): "LINE_SCRIPT",
}


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


def line_py():
    """線の script と境の .py（リポジトリの根からのパス, 木）"""
    for folder in (ROOT / "workflows" / "line" / "scripts", ROOT / "workflows" / ".shared"):
        for p in sorted(folder.glob("*.py")):
            yield p.relative_to(ROOT).as_posix(), ast.parse(p.read_text(encoding="utf-8"))


def word_copies(tree, words) -> list:
    """[(行, 字, 代入した名か None)]: 止めの語か人の止めの頭か頭 works: で始まる字の定数（docstring のような文の中の言及は数えない）"""
    named = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant):
            for target in n.targets:
                if isinstance(target, ast.Name):
                    named[id(n.value)] = target.id
    m = stopby()
    return [(n.lineno, n.value, named.get(id(n))) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and (n.value in words or n.value == m.HUMAN or n.value.startswith(m.HEAD))]


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

    def test_words_unchanged(self):
        """表と declare の語の字は WORDS と同じ（語を足すなら WORDS にも足す。字を変えない）"""
        m = stopby()
        got = {m.HEAD + n for n in m.REASONS} | {m.HEAD + n for _, n, _ in declares()}
        self.assertEqual(got, WORDS)

    def test_attributes_exist(self):
        """pack が引く stopby.<名> は住処に在る（字の誤りを走る前に見る）"""
        m = stopby()
        for rel, tree in pack_py():
            for n in ast.walk(tree):
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "stopby":
                    with self.subTest(file=rel, attr=n.attr):
                        self.assertTrue(hasattr(m, n.attr))


class LineWordsCase(unittest.TestCase):
    """線が足す止めの語と人の止めの頭は stopby に在り、線の script と境は stopby の定数を引く（字の写しを持たない）。
    lib を読めない時の返りの写し（COPIES）だけを許し、その値は stopby の定数と同じ"""

    def test_line_words_live_in_stopby_only(self):
        m = stopby()
        words = {m.HEAD + n for n in m.REASONS} | {m.HEAD + n for _, n, _ in declares()}
        for rel, tree in line_py():
            for line, value, name in word_copies(tree, words):
                with self.subTest(file=rel, line=line, value=value):
                    self.assertIn((rel, name), COPIES, f"{rel}:{line} に止めの語の字 {value!r} の写しが在る（stopby の定数を引く）")
                    self.assertEqual(value, getattr(m, COPIES[(rel, name)]))

    def test_copies_are_in_the_tree(self):
        """COPIES の行は木に在る（古い行を残さない）"""
        found = {(rel, name) for rel, tree in line_py() for _, _, name in word_copies(tree, set())}
        self.assertEqual(set(COPIES) - found, set())

    def test_a_copied_word_is_caught(self):
        m = stopby()
        tree = ast.parse(f'STOP = "{m.NEEDS_HUMAN}"\nHEAD = "{m.HUMAN}"\n"""止めの理由 {m.LINE_SCRIPT} を返す"""\n')
        self.assertEqual([(line, name) for line, _, name in word_copies(tree, {m.NEEDS_HUMAN})], [(1, "STOP"), (2, "HEAD")])


if __name__ == "__main__":
    unittest.main()

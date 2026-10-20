"""AI への決まった指示の文が、`lib/` と block の `src/`・`scripts/` の Python に戻らない（憲法の 2。`workflows/AGENTS.md`・`lib/AGENTS.md`・`docs/design/README.md` の 5.3。issue #764）。

指示の文の在りかは、ノードの md（`prompts/`・`.shared/prompts/`）だけ。Python が持つのは、返答や run ごとに変わる材料（行・名・数）と、却下の理由（どの欄がなぜ駄目か。人に見せる文として日本語）。
文は「文の終わりを持つ字」で見分ける（字数の上限も許す定数の名の表も置かない）: 日本語は `。`、英語は 4 語以上に続く `.`。見る物は 2 つ、どちらも yes/no。

1. 指示を組む関数は、文の定数を使わない: `prompt.render`・`prompt.emit`・`prompt.render_part` を呼ぶ関数（block の `src/`・`scripts/`）の中で、文を持つ文字列の定数（同じファイルの直下の `NAME = "…"`、`import`・`from … import` した `lib/` のモジュールの定数）の名を読めば落ちる。文は md に置き、`{name}` に材料を渡す。
2. 英語の文を定数に持たない: `lib/` と block の `src/`・`scripts/` の直下（モジュールと class の直下）の文字列の定数に、英語の文が在れば落ちる。AI への指示は英語の md に書く（持ち主の決め `prompts-english`）ので、Python の定数の英語の文は指示が戻った印。

拾えない形（機械では縛らず、人が見る）: 関数の中で組む文（f 字や連結でその場で作る文）と、定数を経由せず直に書いた文。強い形は、prompt に渡す値の型で文を渡せなくすること（呼び出しの全部の書き換えが要るので、今は置かない）。
見ない物: docstring・コメント・試験（`lib/tests/`）・関数の中で組む行（材料の見出しと札は 5.3 で Python が持つ）・借りた写し `lib/borrow/`。
"""
import ast
import pathlib
import re
import unittest

from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]

SINKS = frozenset({"render", "emit", "render_part"})
JAPANESE_SENTENCE = re.compile("。")
ENGLISH_SENTENCE = re.compile(r"(?:[A-Za-z0-9_'`]+ ){3,}[A-Za-z0-9_'`)]+\.(?:\s|$)")


def has_sentence(text: str) -> bool:
    return JAPANESE_SENTENCE.search(text) is not None or ENGLISH_SENTENCE.search(text) is not None


def _constants(module: ast.Module) -> dict[str, tuple[int, str]]:
    """直下（モジュールと class）の `NAME = <字のリテラル・連結・f 字>` の名 → (行, 字の全部)"""
    found = {}
    for scope in (module, *(n for n in module.body if isinstance(n, ast.ClassDef))):
        for node in scope.body:
            if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
                continue
            parts = [c.value for c in ast.walk(node.value) if isinstance(c, ast.Constant) and isinstance(c.value, str)]
            if parts:
                found[node.targets[0].id] = (node.lineno, "".join(parts))
    return found


def _is_sink(call: ast.AST) -> bool:
    return (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr in SINKS
            and isinstance(call.func.value, ast.Name) and call.func.value.id == "prompt")


def _parse(path: pathlib.Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None


def _block_pythons(root: pathlib.Path):
    for sub in ("src", "scripts"):
        yield from sorted(root.glob(f"workflows/*/{sub}/*.py"))


def problems(root: pathlib.Path) -> list[str]:
    root = pathlib.Path(root)
    libs = {}
    for path in sorted(root.glob("lib/*.py")):
        if (module := _parse(path)) is not None:
            libs[path.stem] = _constants(module)
    out = []
    for path in [*sorted(root.glob("lib/*.py")), *_block_pythons(root)]:
        rel = path.relative_to(root).as_posix()
        module = _parse(path)
        if module is None:
            out.append(f"{rel}:1: 読めない・構文の誤り")
            continue
        own = _constants(module)
        for name, (line, text) in own.items():
            if ENGLISH_SENTENCE.search(text):
                out.append(f"{rel}:{line}: 定数 {name} に英語の文が在る（AI への指示は md に置く）")
        if rel.startswith("lib/"):
            continue
        imported = {}
        for node in ast.walk(module):
            if isinstance(node, ast.ImportFrom) and node.module in libs:
                imported.update({(a.asname or a.name): (node.module, a.name) for a in node.names})
        for fn in ast.walk(module):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or not any(_is_sink(c) for c in ast.walk(fn)):
                continue
            for node in ast.walk(fn):
                hit = None
                if isinstance(node, ast.Name) and node.id in own and has_sentence(own[node.id][1]):
                    hit = node.id
                elif isinstance(node, ast.Name) and node.id in imported:
                    mod, name = imported[node.id]
                    hit = f"{mod}.{name}" if name in libs[mod] and has_sentence(libs[mod][name][1]) else None
                elif (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in libs
                      and node.attr in libs[node.value.id] and has_sentence(libs[node.value.id][node.attr][1])):
                    hit = f"{node.value.id}.{node.attr}"
                if hit:
                    out.append(f"{rel}:{node.lineno}: 指示を組む関数 {fn.name} が文の定数 {hit} を使う（文は md に置き、材料を {{name}} で渡す）")
    return out


class NoPromptTextInPythonTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(problems(ROOT), [])

    def test_sentence_constant_read_by_a_prompt_builder_is_red(self):
        files = {"workflows/fix/src/p.py": 'import prompt\nRULE = "直す前に全部読め。"\n\ndef build():\n    return prompt.emit("n", {"rule": RULE}, {}, 1)\n'}
        with tree(files) as root:
            got = problems(root)
        self.assertEqual(len(got), 1, got)
        self.assertIn("workflows/fix/src/p.py:5", got[0])

    def test_sentence_constant_of_a_lib_module_is_red(self):
        files = {"lib/rk.py": 'HEAD = "拒まれた。全部直せ。"\n',
                 "workflows/fix/src/p.py": 'import prompt\nimport rk\nfrom rk import HEAD\n\ndef a():\n    return prompt.render("n", {"h": rk.HEAD})\n\ndef b():\n    return prompt.render_part("n", {"h": HEAD})\n'}
        with tree(files) as root:
            got = problems(root)
        self.assertEqual(sorted(line.split(": ")[0] for line in got), ["workflows/fix/src/p.py:6", "workflows/fix/src/p.py:9"], got)

    def test_english_sentence_constant_is_red_in_lib_and_src(self):
        files = {"lib/a.py": 'RULE = "Read all of it before you answer."\n',
                 "workflows/fix/src/b.py": 'class K:\n    RULE = ("Read all of it "\n            "before you answer.")\n',
                 "workflows/fix/scripts/c.py": 'RULE = "Read all of it before you answer."\n'}
        with tree(files) as root:
            got = problems(root)
        self.assertEqual(sorted(line.split(": ")[0] for line in got),
                         ["lib/a.py:1", "workflows/fix/scripts/c.py:1", "workflows/fix/src/b.py:2"], got)

    def test_materials_and_labels_pass(self):
        files = {"lib/a.py": 'LABEL = "Names changed and their hits:"\nREASON = "返答が空だった。"\n',
                 "workflows/fix/src/p.py": 'import prompt\nLABEL = "### Class"\nWORD = "light"\n\ndef build(rows):\n    reason = f"- {LABEL} {len(rows)}: {WORD}"\n    return prompt.emit("n", {"rows": reason}, {}, 1)\n'}
        with tree(files) as root:
            self.assertEqual(problems(root), [])

    def test_sentence_constant_used_outside_a_prompt_builder_passes(self):
        """却下の理由は Python が持つ（指示を組まない関数が読む）"""
        files = {"workflows/fix/src/p.py": 'REASON = "返答が空だった。"\n\ndef accept(reply):\n    return {"ok": bool(reply), "reason": REASON}\n'}
        with tree(files) as root:
            self.assertEqual(problems(root), [])


if __name__ == "__main__":
    unittest.main()

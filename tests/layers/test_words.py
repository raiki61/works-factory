"""文書・役の指示書・lib が人や役に見せる字に、グラフの語にそろえる前の旧い語が無い（`docs/design.md` の「語」。
持ち主の決め `graph-words`）。

見る字（`scope`）: `docs/` の直下の `*.md`・`AGENTS.md`（ASF の物を除く）・根の `README.md`・`lib/` の直下の `*.md`・`*.json`・
役の指示書（`workflows/*/commands/` の下の全部・`lib/agents/*.md`・`bin/_lib/borrow/unattended.md`）・グラフの YAML の `description`・`prompt`・`systemPrompt`・`message` の値・
`lib/` の直下・`workflows/*/scripts/`・境 `workflows/.shared/` の Python の文字列（docstring とコメントは開発者の字なので見ない）。
旧い語は部分一致で探す。外す規則は `EXCEPT` の 1 か所。
"""
import ast
import io
import pathlib
import re
import tokenize
import unittest
from unittest import mock

import yaml

from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]

BANNED = ("節", "線", "輪", "関所", "指し札", "盤面", "お前")
YAML_TEXT_KEYS = frozenset({"description", "prompt", "systemPrompt", "message"})
ASF_DIRS = ("factory", "harness", ".factory")
BORROWED_PROMPT = "bin/_lib/borrow/unattended.md"   # 局所レビューの役の指示書の末尾に全文で載る

# 外す規則の全部。ここの外で字を外さない。
EXCEPT = {
    # 1. `…` の中は識別子とパス（ファイル名・YAML の id・欄の名）。識別子は変えない。
    "code": re.compile(r"`[^`\n]*`"),
    # 2. 「持ち主の言葉」を持つ行の「…」は持ち主の言葉のまま（docs/owner-decisions.md の頭）。入れ子の「」も 1 つの引用として外す。
    "owner_quote_line": "持ち主の言葉",
    # 3. 線・節をグラフの語でない意味で含む語。
    "compounds": ("配線", "導線", "動線", "点線", "下線", "上線", "実線", "罫線", "条件節", "節約"),
}
# 4. lib・script の文字列のうち、字でなく値の物（前の run が書いたファイルから読み戻す語など）。{(パス, 文字列の 1 行): 訳}。
# どの行も木の文字列に当たる（当たらない行は test_keep_rows_hit_the_tree が赤にする）。
_SECTION_NUMBER = "依頼が設計書のセクションを番号で名指す書き方（「`<path>` 3 節」）。依頼の字を読むので変えない"
KEEP: dict[tuple[str, str], str] = {
    ("lib/design.py", r'r"`([^`\s#]+\.[A-Za-z0-9]+)`\s*(?:の\s*)?(?:§\s*(\d+(?:\.\d+)*)|(\d+(?:\.\d+)*)\s*節)"'): _SECTION_NUMBER,
    ("lib/design.py", r'r"(?:\s+|\s*の\s*)(?:§\s*(\d+(?:\.\d+)*)|(\d+(?:\.\d+)*)\s*節)"'): _SECTION_NUMBER,
    ("lib/design.py", r'r"§\s*(\d+(?:\.\d+)*)|(\d+(?:\.\d+)*)\s*節"'): _SECTION_NUMBER,
    ("lib/design.py", " 節"): _SECTION_NUMBER + "（名指しの `<path> <N> 節` の形を組む）",
    ("lib/design.py", '"結び付けられる形の設計書の名指しが依頼に無い（リンク・`<path>#<見出し>`・`<path>` N 節・<名前> N 節 の形だけを数える）"'):
        _SECTION_NUMBER + "（数える形を依頼の字のまま並べる）",
    ("lib/design.py", r"(?:\.?(?:\s|$)|節)"): _SECTION_NUMBER + "（見出しの頭の番号を引く）",
    ("lib/design.py", r'r"(.+) (\S+) 節"'): _SECTION_NUMBER + "（名指しの `<path> <N> 節` の形を解く）",
    ("lib/design.py", r"\s*節"): _SECTION_NUMBER + "（返答が名指しを挙げたかを照らす）",
    ("lib/report.py", '"盤面"'): "直しが対象に漏らした works の内側の語を探す字。旧い語も漏れうる",
    ("lib/report.py", '"関所"'): "直しが対象に漏らした works の内側の語を探す字。旧い語も漏れうる",
}


def scope(root):
    """`(根からのパス, 種類)` を並べる。種類は md・yaml・py"""
    root = pathlib.Path(root)
    found = []
    found += [p for p in root.glob("docs/*.md")]
    found += [p for p in root.rglob("AGENTS.md") if p.relative_to(root).parts[0] not in ASF_DIRS]
    found += [p for p in root.glob("README.md")]
    found += [p for p in root.glob("lib/*.md")] + [p for p in root.glob("lib/*.json")]
    found += [p for p in root.glob(BORROWED_PROMPT)]
    found += [p for p in root.glob("workflows/*/commands/**/*") if p.is_file()]
    found += [p for p in root.glob("lib/agents/*.md")]
    for path in sorted(set(found)):
        yield path.relative_to(root).as_posix(), "md"
    for path in sorted(root.glob("workflows/*/*.yaml")):
        yield path.relative_to(root).as_posix(), "yaml"
    for path in sorted([*root.glob("lib/*.py"), *root.glob("workflows/*/scripts/*.py"), *root.glob("workflows/.shared/*.py")]):
        yield path.relative_to(root).as_posix(), "py"


def texts(path, kind):
    """`(行, 字)` を並べる。md は行ごと、yaml は見る鍵の値、py は docstring を除く文字列"""
    body = path.read_text(encoding="utf-8")
    if kind == "md":
        yield from enumerate(body.splitlines(), 1)
    elif kind == "yaml":
        yield from _yaml_texts(yaml.compose(body))
    else:
        yield from _py_texts(body)


def _yaml_texts(node, key=None):
    if isinstance(node, yaml.MappingNode):
        for k, v in node.value:
            yield from _yaml_texts(v, k.value)
    elif isinstance(node, yaml.SequenceNode):
        for v in node.value:
            yield from _yaml_texts(v, key)
    elif key in YAML_TEXT_KEYS:
        first = node.start_mark.line + (2 if node.style in ("|", ">") else 1)
        for i, line in enumerate(node.value.splitlines()):
            yield first + i, line


def _py_texts(body):
    docstrings = set()
    for node in ast.walk(ast.parse(body)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                docstrings.add((first.lineno, first.col_offset))
    kinds = {tokenize.STRING, getattr(tokenize, "FSTRING_MIDDLE", tokenize.STRING)}
    for tok in tokenize.generate_tokens(io.StringIO(body).readline):
        if tok.type in kinds and tok.start not in docstrings:
            for i, line in enumerate(tok.string.splitlines()):
                yield tok.start[0] + i, line


def _owner_quotes_masked(line):
    out, depth = [], 0
    for ch in line:
        if ch == "「":
            depth += 1
        out.append(" " if depth else ch)
        if ch == "」" and depth:
            depth -= 1
    return "".join(out)


def masked(line):
    """`EXCEPT` を当てた後の字"""
    line = EXCEPT["code"].sub(lambda m: " " * len(m.group()), line)
    if EXCEPT["owner_quote_line"] in line:
        line = _owner_quotes_masked(line)
    for word in EXCEPT["compounds"]:
        line = line.replace(word, " " * len(word))
    return line


def problems(root):
    """1 つの当たりに 1 行 `<パス>:<行>: 旧い語 <語>`"""
    root = pathlib.Path(root)
    out = []
    for rel, kind in scope(root):
        for lineno, line in texts(root / rel, kind):
            if (rel, line) in KEEP:
                continue
            rest = masked(line)
            out += [f"{rel}:{lineno}: 旧い語 {word}" for word in BANNED if word in rest]
    return out


def stale_keep(root):
    """`KEEP` の行のうち、木の文字列に当たらない物"""
    root = pathlib.Path(root)
    found = {(rel, line) for rel, kind in scope(root) if kind == "py" for _, line in texts(root / rel, kind)}
    return [f"KEEP: {rel} の {line!r} が木の文字列に当たらない" for rel, line in KEEP if (rel, line) not in found]


class WordsTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(problems(ROOT), [])

    def test_keep_rows_hit_the_tree(self):
        self.assertEqual(stale_keep(ROOT), [])

    def test_keep_row_skips_its_literal_and_a_stale_row_is_red(self):
        row = ("lib/a.py", '"関所"')
        with mock.patch.dict(KEEP, {row: "前の run の記録から読み戻す語"}, clear=True), tree({"lib/a.py": 'X = "関所"\n'}) as root:
            self.assertEqual((problems(root), stale_keep(root)), ([], []))
        with mock.patch.dict(KEEP, {row: "前の run の記録から読み戻す語"}, clear=True), tree({"lib/a.py": 'X = "承認ノード"\n'}) as root:
            self.assertEqual(stale_keep(root), ["KEEP: lib/a.py の '\"関所\"' が木の文字列に当たらない"])

    def red(self, files, where, word):
        with tree(files) as root:
            got = problems(root)
        self.assertIn(f"{where}: 旧い語 {word}", got)

    def clean(self, files):
        with tree(files) as root:
            self.assertEqual(problems(root), [])

    def test_doc_is_red(self):
        self.red({"docs/a.md": "# 題\n\n人の関所で止まる\n"}, "docs/a.md:3", "関所")

    def test_agents_and_readme_are_red(self):
        self.red({"workflows/AGENTS.md": "線を並べる\n"}, "workflows/AGENTS.md:1", "線")
        self.red({"README.md": "盤面\n"}, "README.md:1", "盤面")

    def test_command_and_agent_are_red(self):
        self.red({"workflows/judge/commands/fix-rules/a.md": "x\nお前は判定役\n"}, "workflows/judge/commands/fix-rules/a.md:2", "お前")
        self.red({"lib/agents/judge.md": "指し札を読む\n"}, "lib/agents/judge.md:1", "指し札")

    def test_yaml_text_keys_are_red_and_the_rest_is_not(self):
        body = ("name: x\ndescription: 線の部品\n# 輪のコメント\nnodes:\n  - id: a\n    prompt: |\n      読め\n      TDD の輪\n"
                "    when: \"$x.output.節 == 'y'\"\n")
        with tree({"workflows/judge/works-factory-judge.yaml": body}) as root:
            got = problems(root)
        self.assertEqual(got, ["workflows/judge/works-factory-judge.yaml:2: 旧い語 線",
                               "workflows/judge/works-factory-judge.yaml:8: 旧い語 輪"])

    def test_lib_literal_is_red_but_docstring_and_comment_are_not(self):
        body = '"""節の docstring"""\n# 節のコメント\n\n\ndef f():\n    """輪の docstring"""\n    return f"{1} 個の節"   # 線\n'
        with tree({"lib/a.py": body}) as root:
            got = problems(root)
        self.assertEqual(got, ["lib/a.py:7: 旧い語 節"])

    def test_script_literal_is_red(self):
        self.red({"workflows/fix/scripts/a.py": 'MSG = "盤面"\n'}, "workflows/fix/scripts/a.py:1", "盤面")

    def test_out_of_scope_is_not_read(self):
        self.clean({"docs/plans/a.md": "節\n", "factory/AGENTS.md": "節\n", "lib/tests/test_a.py": 'X = "節"\n',
                    "lib/graphloops/a.py": 'X = "節"\n', "tests/a.py": 'X = "節"\n'})

    def test_inline_code_is_allowed(self):
        self.clean({"docs/a.md": "`works/線/節.md` を読む\n"})

    def test_owner_quote_is_allowed_only_on_its_line(self):
        self.clean({"docs/a.md": "- 持ち主の言葉: 「関所に「線」をあげる」（2026-10-12）\n"})
        self.red({"docs/a.md": "- 持ち主の言葉: 「関所」の後の線\n"}, "docs/a.md:1", "線")
        self.red({"docs/a.md": "- 決め: 「関所」\n"}, "docs/a.md:1", "関所")

    def test_compounds_are_allowed(self):
        self.clean({"docs/a.md": "配線と導線と動線、点線・下線・上線・実線・罫線、条件節で節約\n"})
        self.red({"docs/a.md": "本線\n"}, "docs/a.md:1", "線")


if __name__ == "__main__":
    unittest.main()

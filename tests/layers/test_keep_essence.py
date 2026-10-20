"""keep-essence の 12 の仕組み（docs/design/README.md の 10 節）のどれもが、「新しい守り」に `path::名` の指しを 1 つ以上持ち、
その名が木に在る（yes/no。docs/design/integration.md の 4.2-1a。能力の棚卸しの指しの照らし test_capability_pointers の後継）。

指しの形は `path::名`（path はリポジトリの根からのパス、名は Python の最上位の関数・クラス・代入の名か `クラス.名`、YAML なら
節の id）。行番号は試験や関数を 1 つ足すたびに関係の無い行までずれるので書かない。数の下限や許す表は持たない（持ち主の決め
shape-checks-only）。項目の「新しい守り」は、その項目の字の「新しい守り」の後ろ（項目の終わりまで）。指しの読みと名の在りかの
照らし（POINTER・python_definitions・yaml_definitions）は tests/e2e/test_evidence.py も使う。
"""
import ast
import functools
import pathlib
import re
import unittest

from tests.layers import scan

ROOT = pathlib.Path(__file__).resolve().parents[2]
README = ROOT / "docs" / "design" / "README.md"
SECTION = "## 10 keep-essence"
ITEMS = 12
ITEM = re.compile(r"^(\d+)\. ")
NEW = "新しい守り"
# 名はハイフンも読む（YAML の節の id は `ask-final` の形。Python の名にハイフンは無いので、読めば無い名として赤になる）
POINTER = re.compile(r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+\.(?:py|yaml))::([A-Za-z_][\w-]*(?:\.[A-Za-z_]\w*)?)")


def python_definitions(text: str) -> dict[str, tuple[int, int]]:
    """最上位の関数・クラス・代入の名と、クラスの中のそれを `クラス.名` で → 定義の文の (頭の行, 終わりの行)（1 から。同じ名は先の定義）"""
    def defined(body):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                yield node.name, node
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        yield target.id, node
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                yield node.target.id, node

    spans = {}
    for name, node in defined(ast.parse(text).body):
        spans.setdefault(name, (node.lineno, node.end_lineno))
        if isinstance(node, ast.ClassDef):
            for member, inner in defined(node.body):
                spans.setdefault(f"{name}.{member}", (inner.lineno, inner.end_lineno))
    return spans


def yaml_definitions(text: str) -> dict:
    """工程の YAML の字の節の id → 節の node（同じ id は先の節）"""
    found = {}
    for node in scan.text_nodes(text):
        found.setdefault(scan._top(node, "id").value, node)
    return found


@functools.cache
def names(path: str) -> frozenset[str]:
    text = (ROOT / path).read_text(encoding="utf-8")
    return frozenset(yaml_definitions(text) if path.endswith(".yaml") else python_definitions(text))


def items(text: str) -> dict[int, str]:
    """10 節の番号 → 項目の字（番号の行から次の番号の行か節の終わりまで）"""
    found, current, inside = {}, None, False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.startswith(SECTION)
            current = None
            continue
        if not inside:
            continue
        head = ITEM.match(line)
        if head:
            current = int(head.group(1))
            found[current] = line
        elif current is not None and line.strip():
            found[current] += "\n" + line
    return found


def guards(item: str) -> list[tuple[str, str]]:
    """項目の「新しい守り」の後ろの `path::名` の指し"""
    _, sep, after = item.partition(NEW)
    return POINTER.findall(after) if sep else []


class KeepEssenceCase(unittest.TestCase):
    def test_every_item_names_a_new_guard_that_exists(self):
        found = items(README.read_text(encoding="utf-8"))
        self.assertEqual(sorted(found), list(range(1, ITEMS + 1)), f"{README.name} の 10 節の項目が 1〜{ITEMS} でない")
        for number, item in found.items():
            with self.subTest(number):
                pointers = guards(item)
                self.assertTrue(pointers, f"10 節の {number} に「{NEW}」の `path::名` の指しが無い")
                for path, name in pointers:
                    self.assertTrue((ROOT / path).is_file(), f"10 節の {number}: {path} が無い")
                    self.assertIn(name, names(path), f"10 節の {number}: {path}::{name} が無い")

    def test_reading_of_items_and_pointers(self):
        text = (f"{SECTION} の仕組み\n\n1. 甲。今の守り `a.py::Old`。{NEW} `tests/x/test_a.py::Case.test_b` と `w/g.yaml::ask-final`。\n"
                "   続きの行\n2. 乙。守りは無い\n\n## 11 次\n3. 外\n")
        found = items(text)
        self.assertEqual(sorted(found), [1, 2])
        self.assertEqual(guards(found[1]), [("tests/x/test_a.py", "Case.test_b"), ("w/g.yaml", "ask-final")])
        self.assertEqual(guards(found[2]), [])
        self.assertEqual(sorted(python_definitions("X = 1\nclass C:\n    def m(self): pass\n")), ["C", "C.m", "X"])


if __name__ == "__main__":
    unittest.main()

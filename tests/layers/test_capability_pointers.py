"""能力の棚卸し（docs/plans/2026-10-13-capabilities/）の「今」と「証」が、行番号でなく名で指し、その名が main に在る（#220）。

指しの形は棚卸しの README.md の「指しの形」: 今は `path::名`（関数・クラス・定数・`クラス.名`。YAML は節の id）、証は
`path::Class.test_name`。行番号は試験や関数を 1 つ足すたびに関係の無い行までずれるので書かない。「元」は版を止めた今の works の
`file:line` でずれないので照らさない。「要追加:」の後の名は、まだ無い名なので照らさない。
"""
import ast
import functools
import pathlib
import re
import unittest

from tests.layers import scan

ROOT = pathlib.Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "docs" / "plans" / "2026-10-13-capabilities"
# 照らす欄はこれだけ（元・本物の run・狭めなどは照らさない）。pitfalls.md の「今の機械」は証と同じく試験を指す欄
POINTING_FIELDS = ("今", "証", "今の機械")
FIELD = re.compile(r"^  - ([^:：（(\s]+)")
LINE_NUMBER = re.compile(r"\.(?:py|yaml):\d")
# 名はハイフンも読む（YAML の節の id は `ask-final` の形。Python の名にハイフンは無いので、読めば無い名として赤になる）
POINTER = re.compile(r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+\.(?:py|yaml))::([A-Za-z_][\w-]*(?:\.[A-Za-z_]\w*)?)")
NOT_YET = "要追加"


def pointing_fields() -> list[tuple[str, str]]:
    """(ファイル:行, 欄の字)。欄は `  - <名>:` の行と、それより深く字下げした続きの行"""
    found = []
    for md in sorted(INVENTORY.glob("*.md")):
        current = None
        for no, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            head = FIELD.match(line)
            if head:
                current = [f"{md.name}:{no}", line] if head.group(1) in POINTING_FIELDS else None
                if current:
                    found.append(current)
            elif current and line.startswith("    "):
                current[1] += "\n" + line
            else:
                current = None
    return [(where, text) for where, text in found]


def pointers() -> list[tuple[str, str, str]]:
    """(ファイル:行, path, 名)。「要追加」より後ろは、まだ無い名なので外す"""
    return [(where, path, name) for where, text in pointing_fields()
            for path, name in POINTER.findall(text.split(NOT_YET, 1)[0])]


@functools.cache
def python_names(path: str) -> frozenset[str]:
    """最上位の関数・クラス・代入の名と、クラスの中のそれを `クラス.名` で"""
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

    names = set()
    for name, node in defined(ast.parse((ROOT / path).read_text(encoding="utf-8")).body):
        names.add(name)
        if isinstance(node, ast.ClassDef):
            names.update(f"{name}.{member}" for member, _ in defined(node.body))
    return frozenset(names)


@functools.cache
def yaml_node_ids(path: str) -> frozenset[str]:
    return frozenset(scan._top(node, "id").value for node in scan.nodes(ROOT, path))


def missing(want_tests: bool) -> list[str]:
    out = []
    for where, path, name in pointers():
        if pathlib.PurePosixPath(path).name.startswith("test_") != want_tests:
            continue
        if not (ROOT / path).is_file():
            out.append(f"{where}: {path} が無い")
        elif name not in (yaml_node_ids(path) if path.endswith(".yaml") else python_names(path)):
            out.append(f"{where}: {path}::{name} が無い")
    return out


class PointerCase(unittest.TestCase):
    def test_reads_the_inventory(self):
        self.assertGreater(len(pointers()), 500)

    def test_current_and_evidence_carry_no_line_numbers(self):
        found = [f"{where}: {line.strip()}" for where, text in pointing_fields()
                 for line in text.splitlines() if LINE_NUMBER.search(line)]
        self.assertEqual(found, [])

    def test_named_code_exists(self):
        self.assertEqual(missing(want_tests=False), [])

    def test_named_tests_exist(self):
        self.assertEqual(missing(want_tests=True), [])


if __name__ == "__main__":
    unittest.main()

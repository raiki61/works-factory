"""能力の棚卸し（docs/plans/2026-10-13-capabilities/）の「今」と「証」と、較正の旗の表（tests/calibration/flags.json）の
works-factory の節の why・never が、行番号でなく名で指し、その名が main に在る（#220・#315）。

指しの形は棚卸しの README.md の「指しの形」: 今は `path::名`（関数・クラス・定数・`クラス.名`。YAML は節の id）、証は
`path::Class.test_name`。行番号は試験や関数を 1 つ足すたびに関係の無い行までずれるので書かない。「元」と旗の表の works の節は
版を止めた今の works の `file:line` でずれないので照らさない。「要追加」から文の終わり（「。」か行の終わり）までの名は、まだ無い名
なので照らさない。
"""
import ast
import collections
import functools
import json
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
# `path::名` の形に外れた指し（`::` の前後の欠け・1 つのコロン）。POINTER に合わない指しは名を照らされないので赤にする
MALFORMED = re.compile(r"\.(?:py|yaml)::?(?!\d)")
BARE_PATH = re.compile(r"(?<![\w./*-])((?:lib|bin|workflows|tests|docs)/[\w./-]*\.(?:py|yaml|md|json))(?![\w*-])")
NOT_YET = re.compile(r"要追加[^。\n]*")
# 欄ごとの読めた指しの数の下限。欄の読み落とし（POINTING_FIELDS の欠け・欄の頭の形の変わり）で総数が保っても赤にする
FIELD_FLOOR = {"今": 1800, "証": 1700, "今の機械": 70}
FLAGS = ROOT / "tests" / "calibration" / "flags.json"
FLAG_FACTORY = "works-factory"
FLAG_FIELDS = ("why", "never")
FLAG_FLOOR = 70


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


def flag_fields() -> list[tuple[str, str]]:
    """(flags.json:旗, 欄の字)。旗の表の works-factory の節の why・never"""
    table = json.loads(FLAGS.read_text(encoding="utf-8"))[FLAG_FACTORY]
    return [(f"{FLAGS.name}:{gate}", entry[f]) for gate, entry in table.items() for f in FLAG_FIELDS if f in entry]


def present(text: str) -> str:
    """「要追加」の文（まだ無い名）を外した字"""
    return NOT_YET.sub("", text)


def present_tense() -> list[tuple[str, str]]:
    """(どこ, 字)。棚卸しの欄は「要追加」の文を外し、旗の欄はそのまま"""
    return [(where, present(text)) for where, text in pointing_fields()] + flag_fields()


def pointers() -> list[tuple[str, str, str]]:
    """(ファイル:行, path, 名)"""
    return [(where, path, name) for where, text in present_tense() for path, name in POINTER.findall(text)]


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
    def test_reads_every_pointing_field(self):
        read = collections.Counter(FIELD.match(text).group(1) for _, text in pointing_fields()
                                   for _ in POINTER.findall(present(text)))
        self.assertEqual({field: read[field] >= least for field, least in FIELD_FLOOR.items()},
                         dict.fromkeys(FIELD_FLOOR, True), read)

    def test_names_after_the_not_yet_sentence_are_read(self):
        text = "  - 証: a/b.py::Now。後は要追加: a/c.py::Later — まだ無い。今の形: a/d.py::Kept\n    a/e.py::Next"
        self.assertEqual(POINTER.findall(present(text)), [("a/b.py", "Now"), ("a/d.py", "Kept"), ("a/e.py", "Next")])

    def test_reads_the_flags(self):
        self.assertGreaterEqual(len([where for where, _, _ in pointers() if where.startswith(f"{FLAGS.name}:")]), FLAG_FLOOR)

    def test_current_and_evidence_carry_no_line_numbers(self):
        found = [f"{where}: {line.strip()}" for where, text in pointing_fields() + flag_fields()
                 for line in text.splitlines() if LINE_NUMBER.search(line)]
        self.assertEqual(found, [])

    def test_named_code_exists(self):
        self.assertEqual(missing(want_tests=False), [])

    def test_named_tests_exist(self):
        self.assertEqual(missing(want_tests=True), [])

    def test_pointers_take_the_named_form(self):
        found = [f"{where}: {hit.group(0)}" for where, text in present_tense()
                 for hit in MALFORMED.finditer(POINTER.sub("", text))]
        self.assertEqual(found, [])

    def test_named_paths_exist(self):
        found = [f"{where}: {path} が無い" for where, text in present_tense()
                 for path in BARE_PATH.findall(text) if not (ROOT / path).exists()]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()

"""能力の棚卸し（docs/plans/2026-10-13-capabilities/）の「今」と「証」と、較正の旗の表（tests/calibration/flags.json）の
works-factory の節の why・never が、行番号でなく名で指し、その名が main に在る（#220・#315）。

指しの形は棚卸しの README.md の「指しの形」: 今は `path::名`（関数・クラス・定数・`クラス.名`。YAML は節の id）、証は
`path::Class.test_name`。行番号は試験や関数を 1 つ足すたびに関係の無い行までずれるので書かない。「元」と旗の表の works の節は
版を止めた今の works の `file:line` でずれないので照らさない。「要追加」から文の終わり（「。」か行の終わり）までの名は、まだ無い名
なので照らさない。

tail.md の各領域の穴の「数」と末尾の「穴の要約」は、README.md の「穴の数え方」のとおり行の欄から数えた今の値で、要約は各領域の
数の足し算（#336・#339）。狭めの並びは欄を読んで人が選ぶので、数と並びの長さ・並びの ID がその領域の行に在ること・
要約の足し算だけを照らす。
"""
import ast
import collections
import functools
import pathlib
import re
import unittest

from tests.calibration import run as calibration
from tests.layers import scan

ROOT = pathlib.Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "docs" / "plans" / "2026-10-13-capabilities"
FIELD = re.compile(r"^  - ([^:：（(\s]+)")
LINE_NUMBER = re.compile(r"\.(?:py|yaml):\d")
# 名はハイフンも読む（YAML の節の id は `ask-final` の形。Python の名にハイフンは無いので、読めば無い名として赤になる）
POINTER = re.compile(r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+\.(?:py|yaml))::([A-Za-z_][\w-]*(?:\.[A-Za-z_]\w*)?)")
# `path::名` の形に外れた指し（`::` の前後の欠け・1 つのコロン）。POINTER に合わない指しは名を照らされないので赤にする
MALFORMED = re.compile(r"\.(?:py|yaml)::?(?!\d)")
BARE_PATH = re.compile(r"(?<![\w./*-])((?:lib|bin|workflows|tests|docs)/[\w./-]*\.(?:py|yaml|md|json))(?![\w*-])")
NOT_YET = re.compile(r"要追加[^。\n]*")
# 照らす欄（元・本物の run・狭めなどは照らさない。pitfalls.md の「今の機械」は証と同じく試験を指す欄）と、ファイルごとの読めた
# 指しの数の下限。1 つのファイルの欄の読み落とし（欄の頭の形の変わり）で他のファイルの数が保っても赤にする
FIELD_FLOOR = {
    "今": {"fix.md": 300, "gaps-fix.md": 70, "gaps-plan.md": 100, "judge.md": 170, "line.md": 330, "plan.md": 430,
          "tail.md": 430},
    "証": {"fix.md": 330, "gaps-fix.md": 50, "gaps-plan.md": 60, "judge.md": 160, "line.md": 320, "plan.md": 380,
          "tail.md": 470},
    "今の機械": {"pitfalls.md": 70},
}
FLAG_FIELDS = ("why", "never")
FLAG_FLOOR = 70
TAIL = INVENTORY / "tail.md"
ROW = re.compile(r"^- ([TERM]\d+b?) ")
AREA_HOLES = re.compile(r"^### ([TERM]) の穴")
SUMMARY = "## 穴の要約"
TOTAL = "行の総数"
NARROWED = "狭めたのに Archon が強いていない"
COUNTED = {
    "今: 無し": lambda row: row["今"].startswith("無し"),
    "証が要追加か弱い": lambda row: row["証"].startswith("要追加") or "弱い:" in row["証"],
}
HOLE = re.compile(rf"^- ({TOTAL}|{'|'.join(COUNTED)}|{NARROWED}): (\d+)(?:（([^）]*)）)?")


def row_fields() -> list[tuple[str, str | None, str]]:
    """(ファイル:行, 行 ID, 欄の字)。欄は `  - <名>:` の行と、それより深く字下げした続きの行。行 ID は欄の属す `- <ID> ` の行
    （ROW の形。無ければ None）"""
    found = []
    for md in sorted(INVENTORY.glob("*.md")):
        current, row = None, None
        for no, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            head = FIELD.match(line)
            if head:
                current = [f"{md.name}:{no}", row, line] if head.group(1) in FIELD_FLOOR else None
                if current:
                    found.append(current)
            elif current and line.startswith("    "):
                current[2] += "\n" + line
            else:
                current = None
                if line.strip():
                    row = head.group(1) if (head := ROW.match(line)) else None
    return [(where, row, text) for where, row, text in found]


def pointing_fields() -> list[tuple[str, str]]:
    """(ファイル:行, 欄の字)"""
    return [(where, text) for where, _, text in row_fields()]


def flag_fields() -> list[tuple[str, str]]:
    """(flags.json:旗, 欄の字)。旗の表の works-factory の節の why・never"""
    table = calibration.load_flags()[calibration.WorksFactory.name]
    return [(f"{calibration.FLAGS.name}:{gate}", entry[f]) for gate, entry in table.items() for f in FLAG_FIELDS if f in entry]


def present(text: str) -> str:
    """「要追加」の文（まだ無い名）を外した字"""
    return NOT_YET.sub("", text)


def present_tense() -> list[tuple[str, str]]:
    """(どこ, 字)。棚卸しの欄は「要追加」の文を外し、旗の欄はそのまま"""
    return [(where, present(text)) for where, text in pointing_fields()] + flag_fields()


def pointers() -> list[tuple[str, str, str]]:
    """(ファイル:行, path, 名)"""
    return [(where, path, name) for where, text in present_tense() for path, name in POINTER.findall(text)]


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


@functools.cache
def python_names(path: str) -> frozenset[str]:
    return frozenset(python_definitions((ROOT / path).read_text(encoding="utf-8")))


@functools.cache
def yaml_nodes(path: str) -> dict:
    """節の id → 節の node（同じ id は先の節）"""
    found = {}
    for node in scan.nodes(ROOT, path):
        found.setdefault(scan._top(node, "id").value, node)
    return found


def exists(path: str, name: str) -> bool:
    return (ROOT / path).is_file() and name in (yaml_nodes(path) if path.endswith(".yaml") else python_names(path))


def missing(want_tests: bool) -> list[str]:
    out = []
    for where, path, name in pointers():
        if pathlib.PurePosixPath(path).name.startswith("test_") != want_tests:
            continue
        if not (ROOT / path).is_file():
            out.append(f"{where}: {path} が無い")
        elif not exists(path, name):
            out.append(f"{where}: {path}::{name} が無い")
    return out


def tail_rows() -> dict[str, dict[str, str]]:
    """tail.md の行 ID → 欄の名 → 欄の字"""
    rows = {}
    for where, row, text in row_fields():
        if row is not None and where.startswith(f"{TAIL.name}:"):
            rows.setdefault(row, {})[FIELD.match(text).group(1)] = text.split(":", 1)[1].strip()
    return rows


def hole_counts() -> tuple[dict[str, dict[str, tuple[int, str]]], dict[str, tuple[int, str]]]:
    """({領域: {数の名: (数, 括弧の中)}}, 穴の要約の {数の名: (数, 括弧の中)})"""
    areas, summary, current = {}, {}, None
    for line in TAIL.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            area = AREA_HOLES.match(line)
            current = areas.setdefault(area.group(1), {}) if area else summary if line == SUMMARY else None
        elif current is not None and (hole := HOLE.match(line)):
            current[hole.group(1)] = (int(hole.group(2)), hole.group(3) or "")
    return areas, summary


class PointerCase(unittest.TestCase):
    def test_reads_every_pointing_field(self):
        read = collections.Counter((field, where.split(":")[0]) for where, text in pointing_fields()
                                   for field in [FIELD.match(text).group(1)] for _ in POINTER.findall(present(text)))
        floor = {(field, md): least for field, files in FIELD_FLOOR.items() for md, least in files.items()}
        self.assertEqual({key: read[key] >= least for key, least in floor.items()}, dict.fromkeys(floor, True), read)
        self.assertLessEqual(set(read), set(floor), read)

    def test_no_present_name_hides_in_a_not_yet_sentence(self):
        hidden = [f"{where}: {path}::{name}" for where, text in pointing_fields() for span in NOT_YET.findall(text)
                  for path, name in POINTER.findall(span) if exists(path, name)]
        self.assertEqual(hidden, [])

    def test_names_after_the_not_yet_sentence_are_read(self):
        text = "  - 証: a/b.py::Now。後は要追加: a/c.py::Later — まだ無い。今の形: a/d.py::Kept\n    a/e.py::Next"
        self.assertEqual(POINTER.findall(present(text)), [("a/b.py", "Now"), ("a/d.py", "Kept"), ("a/e.py", "Next")])

    def test_reads_the_flags(self):
        self.assertGreaterEqual(len([where for where, _, _ in pointers() if where.startswith(f"{calibration.FLAGS.name}:")]), FLAG_FLOOR)

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

    def test_tail_hole_counts_are_counted_from_the_rows(self):
        rows = tail_rows()
        areas, _ = hole_counts()
        self.assertEqual(sorted(areas), sorted("TERM"))
        for area, counts in areas.items():
            with self.subTest(area=area):
                self.assertEqual(set(counts), {TOTAL, *COUNTED, NARROWED})
                self.assertEqual(counts[TOTAL][0], len([key for key in rows if key[0] == area]))
                for name, (number, listed) in counts.items():
                    if name == TOTAL:
                        continue
                    ids = listed.split("・") if listed else []
                    self.assertEqual(number, len(ids), name)
                    self.assertLessEqual(set(ids), {key for key in rows if key[0] == area}, name)
                    if name in COUNTED:
                        self.assertEqual(ids, [key for key, row in rows.items() if key[0] == area and COUNTED[name](row)], name)

    def test_hole_summary_adds_up_the_areas(self):
        areas, summary = hole_counts()
        self.assertEqual(set(summary), {TOTAL, *COUNTED, NARROWED})
        for name, (number, listed) in summary.items():
            with self.subTest(name=name):
                parts = {area: int(n) for area, n in re.findall(r"([TERM]) (\d+)", listed)}
                self.assertEqual(parts, {area: counts[name][0] for area, counts in areas.items()})
                self.assertEqual(number, sum(parts.values()))


if __name__ == "__main__":
    unittest.main()

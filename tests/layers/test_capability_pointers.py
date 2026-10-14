"""能力の棚卸し（docs/plans/2026-10-13-capabilities/）の「証」と「今の機械」が、行番号でなく名で試験を指し、その名が main に在る
（#220・#315）。「今」は名を持たず、字は docs/works-parity.md の「前の棚卸しの今」の、自分のファイルと行 ID の行が持つ（#521）。

指しの形は棚卸しの README.md の「指しの形」: 証は `path::Class.test_name`。行番号は試験や関数を 1 つ足すたびに関係の無い行まで
ずれるので書かない。「元」は版を止めた今の works の `file:line` でずれないので照らさない。「要追加」から文の終わり（「。」か行の
終わり）までの名は、まだ無い名なので照らさない。棚卸しの指しは試験だけを指すので、試験でない名を変える PR は
docs/works-parity.md の 1 か所だけを直す（その名は tests/layers/test_works_parity.py が照らす）。

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
# 読む欄（元・本物の run・狭めなどは読まない。pitfalls.md の「今の機械」は証と同じく試験を指す欄）
FIELDS = ("今", "証", "今の機械")
# 指しを持つ欄の、ファイルごとの読めた指しの数の下限。1 つのファイルの欄の読み落とし（欄の頭の形の変わり）で他のファイルの数が
# 保っても赤にする
FIELD_FLOOR = {
    "証": {"fix.md": 330, "gaps-fix.md": 50, "gaps-plan.md": 60, "judge.md": 160, "line.md": 320, "plan.md": 380,
          "tail.md": 470},
    "今の機械": {"pitfalls.md": 70},
}
TAIL = INVENTORY / "tail.md"
# 行の ID の型の持ち主はここ 1 か所（#537）。棚卸しの行の ID と、照らしの表 tests/e2e/evidence.json の行の ID は別の集合。
# 表は線への申し送り（S）と落とし穴（K）の行を持たず、線の配線の文書は部分の名（D1）や今の works の名（U6）を書くので、
# 表の側の読みに棚卸しの型を使うとそれらを行と読む
INVENTORY_ROW_ID = r"(?:L-[EGWD]|[A-Z])\d+[a-z]?"
EVIDENCE_ROW_ID = r"(?:L-[EGWD]|[JPFTERM])\d+[a-z]?"
ROW = re.compile(rf"^- ({INVENTORY_ROW_ID})[ 〔]")
# 「今」の字を docs/works-parity.md の「前の棚卸しの今」へ移した印。移した字が「無し」で始まる行は HOLE_MARK（tail.md の穴に数える）
MOVED_MARK, HOLE_MARK = "表", "無し（表）"
# 「今」の欄に書ける字
CURRENT = ("", "無し", MOVED_MARK, HOLE_MARK)
AREA_HOLES = re.compile(r"^### ([TERM]) の穴")
SUMMARY = "## 穴の要約"
TOTAL = "行の総数"
NARROWED = "狭めたのに Archon が強いていない"
COUNTED = {
    "今: 無し": lambda row: row["今"].startswith("無し"),
    "証が要追加か弱い": lambda row: row["証"].startswith("要追加") or "弱い:" in row["証"],
}
HOLE = re.compile(rf"^- ({TOTAL}|{'|'.join(COUNTED)}|{NARROWED}): (\d+)(?:（([^）]*)）)?")


def mention(row_id: str) -> re.Pattern[str]:
    """字の中で row_id の型の ID を名指す所。日本語の字は \\w に入るので、ID の前後は ASCII の字で区切る（L-E02 の E02・
    T80 の T8 を別の ID と読まない）"""
    return re.compile(rf"(?<![A-Za-z0-9-])({row_id})(?![A-Za-z0-9])")


def row_fields(fields=FIELDS) -> list[tuple[str, str | None, str]]:
    """(ファイル:行, 行 ID, 欄の字)。欄は名が fields に在る `  - <名>:` の行と、それより深く字下げした続きの行。行 ID は欄の
    属す `- <ID> ` の行（ROW の形。無ければ None）"""
    found = []
    for md in sorted(INVENTORY.glob("*.md")):
        current, row = None, None
        for no, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            head = FIELD.match(line)
            if head:
                current = [f"{md.name}:{no}", row, line] if head.group(1) in fields else None
                if current:
                    found.append(current)
            elif line.startswith("    "):
                if current:
                    current[2] += "\n" + line
            else:
                current = None
                if line.strip():
                    row = head.group(1) if (head := ROW.match(line)) else None
    return [(where, row, text) for where, row, text in found]


def current_value(text: str) -> str | None:
    """「今」の欄の字なら欄の値、ほかの欄なら None"""
    return text.split(":", 1)[1].strip() if FIELD.match(text).group(1) == "今" else None


def moved_rows(fields: list[tuple[str, str | None, str]]) -> dict[str, str]:
    """「今」の字を docs/works-parity.md へ移した行の鍵 `<ファイル> <行 ID>` → 印（MOVED_MARK か HOLE_MARK）。fields は row_fields() の形。
    2 度在る鍵は落とす（表の行と 1 つずつ合うことを照らすので、重ねた行を 1 つに畳まない）"""
    found = {}
    for where, row, text in fields:
        if (value := current_value(text)) not in (MOVED_MARK, HOLE_MARK):
            continue
        key = f"{where.split(':')[0]} {row}"
        if key in found:
            raise ValueError(f"前の棚卸しの {key} の「今」が 2 度在る（{where}）")
        found[key] = value
    return found


def pointing_fields() -> list[tuple[str, str]]:
    """(ファイル:行, 欄の字)"""
    return [(where, text) for where, _, text in row_fields()]


def present(text: str) -> str:
    """「要追加」の文（まだ無い名）を外した字"""
    return NOT_YET.sub("", text)


def present_tense() -> list[tuple[str, str]]:
    """(どこ, 字)。棚卸しの欄から「要追加」の文を外した物"""
    return [(where, present(text)) for where, text in pointing_fields()]


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


def yaml_definitions(text: str) -> dict:
    """工程の YAML の字の節の id → 節の node（同じ id は先の節）"""
    found = {}
    for node in scan.text_nodes(text):
        found.setdefault(scan._top(node, "id").value, node)
    return found


@functools.cache
def yaml_node_ids(path: str) -> frozenset[str]:
    return frozenset(yaml_definitions((ROOT / path).read_text(encoding="utf-8")))


def exists(path: str, name: str) -> bool:
    return (ROOT / path).is_file() and name in (yaml_node_ids(path) if path.endswith(".yaml") else python_names(path))


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

    def test_current_holds_only_a_moved_mark(self):
        self.assertEqual([f"{where}: 今 {value!r}" for where, _, text in row_fields()
                          if (value := current_value(text)) is not None and value not in CURRENT], [])

    def test_pointers_name_only_tests(self):
        self.assertEqual([f"{where}: {path}::{name}" for where, path, name in pointers()
                          if "tests" not in pathlib.PurePosixPath(path).parts], [])

    def test_no_present_name_hides_in_a_not_yet_sentence(self):
        hidden = [f"{where}: {path}::{name}" for where, text in pointing_fields() for span in NOT_YET.findall(text)
                  for path, name in POINTER.findall(span) if exists(path, name)]
        self.assertEqual(hidden, [])

    def test_names_after_the_not_yet_sentence_are_read(self):
        text = "  - 証: a/b.py::Now。後は要追加: a/c.py::Later — まだ無い。今の形: a/d.py::Kept\n    a/e.py::Next"
        self.assertEqual(POINTER.findall(present(text)), [("a/b.py", "Now"), ("a/d.py", "Kept"), ("a/e.py", "Next")])

    def test_current_and_evidence_carry_no_line_numbers(self):
        found = [f"{where}: {line.strip()}" for where, text in pointing_fields()
                 for line in text.splitlines() if LINE_NUMBER.search(line)]
        self.assertEqual(found, [])

    def test_moved_rows_refuse_a_duplicated_key(self):
        field = ("line.md:3", "L-E01", f"  - 今: {MOVED_MARK}")
        self.assertEqual(moved_rows([field]), {"line.md L-E01": MOVED_MARK})
        with self.assertRaises(ValueError):
            moved_rows([field, ("line.md:9", "L-E01", f"  - 今: {HOLE_MARK}")])

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


class RowIdCase(unittest.TestCase):
    def test_row_id_patterns_have_one_owner(self):
        """型の写しをほかのファイルに書くと、ここの型を変えても写しは追わない"""
        here = pathlib.Path(__file__).resolve()
        copies = [str(path.relative_to(ROOT)) for top in ("tests", "lib", "workflows", "bin") for path in (ROOT / top).rglob("*.py")
                  if path.resolve() != here and "L-[EGWD]" in path.read_text(encoding="utf-8")]
        self.assertEqual(copies, [])

    def test_every_row_head_is_read(self):
        """棚卸しの型から区分を落とすと、その区分の行が照らしから黙って消える"""
        unread = [f"{md.name}:{no}" for md in sorted(INVENTORY.glob("*.md"))
                  for no, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1)
                  if re.match(r"- [A-Z][A-Z-]*\d+[a-z]?[ 〔]", line) and not ROW.match(line)]
        self.assertEqual(unread, [])

    def test_mention_reads_ids_whole(self):
        """L-E02 の E02・T80 の T8 を別の ID と読まず、日本語の字に挟まれた ID は読む"""
        self.assertEqual(mention(INVENTORY_ROW_ID).findall("L-E02・T80・T8：R5b と行S07の"), ["L-E02", "T80", "T8", "R5b", "S07"])
        self.assertEqual(mention(EVIDENCE_ROW_ID).findall("部分 D1・U6・S07・区分 T の issue（T16）"), ["T16"])


if __name__ == "__main__":
    unittest.main()

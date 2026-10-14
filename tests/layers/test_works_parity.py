"""今の works の利用者に見える能力の照らし（docs/works-parity.md。#505）が、源の目録を全部覆い、行の欄が決まりの形を守る。

源（版を止めた今の works の SKILL.md・use.sh・keep-essence.md）は CI で取れないので、源と目録の食い違いは表の頭の抜き方の命令を
版を上げる時に打ち直して見る。ここは目録と表の食い違いと、行の欄の形を照らす:
- 目録の錨が全部、どれかの行の「印」（`…` で囲んだ字）か「元」に在る。目録の種類ごとの数が並びの長さと合う
- 「状態」は 在る・形を変えて在る（…）・無い のどれか。「無い」行は「処置」を持ち、処置は #<issue>・戻した: <指し>・要らない: <訳>
  のどれか
- 「今」と「戻した:」の指しは、前の棚卸しと同じ規則（tests/layers/test_capability_pointers.py）で行番号を持たず、名が main に在る
- 「## 数」が行から数えた値と合う
"""
import collections
import pathlib
import re
import unittest

from tests.layers.test_capability_pointers import BARE_PATH, LINE_NUMBER, MALFORMED, POINTER, ROOT, exists

TABLE = ROOT / "docs" / "works-parity.md"
ROW = re.compile(r"^- ([SUK]\d+[a-z]?) ")
FIELD = re.compile(r"^  - (元|印|今|状態|処置|旧棚卸し): ?(.*)$")
CATALOG_HEAD = "## 源の目録"
COUNT_HEAD = "## 数"
KIND = re.compile(r"^- ([^（\n]+)（(\d+)）: (.+)$")
CODE = re.compile(r"`([^`\n]+)`")
STATE = re.compile(r"^(在る|無い)$|^形を変えて在る（.+）$")
DISPOSITION = re.compile(r"^(#\d+|戻した: \S.*|要らない: \S.*)$")
README_SECTION = re.compile(r"README\.md「[^」]+」")
MISSING_ROWS = "無い行"


def rows(text: str) -> dict[str, dict[str, str]]:
    """行 ID → {欄の名: 字}。欄は `  - <名>: ` の行と、4 字下げの続きの行"""
    found, row, field = {}, None, None
    for line in text.splitlines():
        if head := ROW.match(line):
            row, field = head.group(1), None
            if row in found:
                raise ValueError(f"行 {row} が 2 度在る")
            found[row] = {}
        elif row and (head := FIELD.match(line)):
            field = head.group(1)
            found[row][field] = head.group(2)
        elif row and field and line.startswith("    "):
            found[row][field] += "\n" + line.strip()
        elif not line.startswith("  "):
            row = field = None
    return found


def section(text: str, head: str) -> list[str]:
    """見出し head の下の行（次の `## ` まで）"""
    lines = text.splitlines()
    start = lines.index(head) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start:end]


def catalog(text: str) -> list[tuple[str, int, list[str]]]:
    """(種類, 書いた数, 錨の並び)。錨は `…` で囲んだ字"""
    return [(m.group(1), int(m.group(2)), CODE.findall(m.group(3))) for line in section(text, CATALOG_HEAD)
            if (m := KIND.match(line))]


def uncovered(text: str) -> list[str]:
    """どの行の「印」にも「元」にも無い目録の錨"""
    table = rows(text)
    marked = {code for row in table.values() for code in CODE.findall(row.get("印", ""))}
    origins = {part.strip() for row in table.values() for part in row.get("元", "").split("・")}
    return [f"{kind}: {anchor}" for kind, _, anchors in catalog(text) for anchor in anchors
            if anchor not in marked and anchor not in origins]


def field_problems(text: str) -> list[str]:
    """状態と処置の形の外れ"""
    out = []
    for rid, row in rows(text).items():
        missing = [name for name in ("元", "印", "今", "状態", "旧棚卸し") if not row.get(name, "").strip()]
        if missing:
            out.append(f"{rid}: 欄 {'・'.join(missing)} が無い")
        state, done = row.get("状態", ""), row.get("処置")
        if not STATE.match(state):
            out.append(f"{rid}: 状態 {state!r} が 在る・形を変えて在る（…）・無い のどれでもない")
        if state == "無い" and done is None:
            out.append(f"{rid}: 無い行に処置が無い")
        if done is not None and not DISPOSITION.match(done):
            out.append(f"{rid}: 処置 {done!r} が #<issue>・戻した: <指し>・要らない: <訳> のどれでもない")
        if done is not None and done.startswith("戻した:") and not (POINTER.search(done) or README_SECTION.search(done)):
            out.append(f"{rid}: 戻した: が戻した先の `path::名` か README.md「…」を名指さない")
    return out


def pointing(text: str) -> list[tuple[str, str]]:
    """(行 ID, 指しを照らす欄の字)。「今」と「処置」（戻した: の先）"""
    return [(rid, row[name]) for rid, row in rows(text).items() for name in ("今", "処置") if name in row]


def counts(text: str) -> dict[str, int]:
    """行から数えた「## 数」の値: 行・状態ごと・処置の種類ごと"""
    table = rows(text)
    got = collections.Counter({"行": len(table)})
    for row in table.values():
        state = row["状態"]
        got["状態 " + ("形を変えて在る" if state.startswith("形を変えて在る") else state)] += 1
        if done := row.get("処置"):
            got["処置 " + (done if done.startswith("#") else done.split(":")[0])] += 1
    return dict(got)


def written_counts(text: str) -> tuple[dict[str, int], list[str]]:
    """「## 数」に書いた (名 → 数, 無い行の ID の並び)"""
    nums, missing = {}, []
    for line in section(text, COUNT_HEAD):
        if line.startswith(f"- {MISSING_ROWS}: "):
            missing = line.removeprefix(f"- {MISSING_ROWS}: ").split("・")
        elif m := re.match(r"^- (.+): (\d+)$", line):
            nums[m.group(1)] = int(m.group(2))
    return nums, missing


TEXT = TABLE.read_text(encoding="utf-8")


class WorksParityCase(unittest.TestCase):
    def test_every_catalog_anchor_has_a_row(self):
        self.assertEqual(uncovered(TEXT), [])

    def test_catalog_counts_match_their_lists(self):
        kinds = catalog(TEXT)
        self.assertGreaterEqual(len(kinds), 10, "目録の種類の読み落とし")
        self.assertEqual([(kind, n, len(anchors)) for kind, n, anchors in kinds if n != len(anchors)], [])

    def test_rows_read_and_ids_unique(self):
        table = rows(TEXT)
        self.assertGreaterEqual(len(table), 400, "行の読み落とし")
        self.assertEqual({rid[0] for rid in table}, set("SUK"))

    def test_states_and_dispositions_take_the_set_forms(self):
        self.assertEqual(field_problems(TEXT), [])

    def test_pointers_carry_no_line_numbers(self):
        self.assertEqual([f"{rid}: {line}" for rid, text in pointing(TEXT) for line in text.splitlines() if LINE_NUMBER.search(line)], [])

    def test_pointers_take_the_named_form(self):
        self.assertEqual([f"{rid}: {hit.group(0)}" for rid, text in pointing(TEXT) for hit in MALFORMED.finditer(POINTER.sub("", text))],
                         [])

    def test_named_code_exists(self):
        self.assertEqual([f"{rid}: {path}::{name}" for rid, text in pointing(TEXT) for path, name in POINTER.findall(text)
                          if not exists(path, name)], [])

    def test_named_paths_exist(self):
        self.assertEqual([f"{rid}: {path}" for rid, text in pointing(TEXT) for path in BARE_PATH.findall(text)
                          if not (ROOT / path).exists()], [])

    def test_count_section_matches_rows(self):
        nums, missing = written_counts(TEXT)
        self.assertEqual(nums, counts(TEXT))
        self.assertEqual(missing, [rid for rid, row in rows(TEXT).items() if row["状態"] == "無い"])


SAMPLE = """## 源の目録

- 旗（2）: `--a`・`--b`

## 表

- S001 a を受ける
  - 元: SKILL.md:3
  - 印: `--a`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: 訳
  - 旧棚卸し: 無し
"""


class NegativeCase(unittest.TestCase):
    def test_uncovered_anchor_is_named(self):
        self.assertEqual(uncovered(SAMPLE), ["旗: --b"])
        self.assertEqual(uncovered(SAMPLE.replace("`--a`\n", "`--a`・`--b`\n")), [])

    def test_missing_row_without_disposition_is_named(self):
        self.assertEqual(field_problems(SAMPLE), [])
        self.assertEqual(field_problems(SAMPLE.replace("  - 処置: 要らない: 訳\n", "")), ["S001: 無い行に処置が無い"])
        self.assertEqual(len(field_problems(SAMPLE.replace("要らない: 訳", "戻した: 何か"))), 1)

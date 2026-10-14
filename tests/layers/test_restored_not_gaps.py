"""能力の棚卸し（docs/plans/2026-10-13-capabilities/）が戻したとした行の ID が、節の表 docs/nodes.json の gaps と照らしの表
tests/e2e/evidence.json の why にまだ在れば赤にする（#527・#528・#530）。

戻した行は棚卸しの README.md の「穴の数え方」と同じく、「狭め」の欄に「→ … 戻した」（か「→ … 戻っていた」）が在る行。欄が
戻したと書くのにこの形でない行と、この形でも一部だけを戻した行は PARTIAL に名を挙げる。照らしは ID の在る無しだけで、
gaps と why の言い回しは読まない（棚卸しの戻した行を名指したければ、ID を書かずに今の住処を書く）。tracker は読まない。

棚卸しの中でも、ほかの行の ID を名指す行と名指された行の一方が戻した、一方が開いていると書けば赤にする（#536）。照らしは
名指す ID と、戻したか開いているかの形の在る無しだけで、同じ能力かは読まない。「狭め」の欄の無い行（線への申し送りの S の行）は
行の字の形を読む。

tail.md の各領域の穴の「狭めたのに Archon が強いていない」の並びに、戻した行が残っていれば赤にする（#349）。
"""
import copy
import json
import pathlib
import re
import unittest

from tests.layers.test_capability_pointers import INVENTORY, INVENTORY_ROW_ID, NARROWED, ROW, hole_counts, mention

ROOT = pathlib.Path(__file__).resolve().parents[2]
NODES = ROOT / "docs" / "nodes.json"
EVIDENCE = ROOT / "tests" / "e2e" / "evidence.json"
RESTORED = re.compile(r"→[^→]*戻(?:した|っていた)")
SAYS_RESTORED = re.compile(r"戻(?:した|っていた)")
# 狭めの欄が戻したと書くが、能力が戻り切っていない行。照らす ID に入れない
PARTIAL = {
    "F026": "試験の枠は持ち主の決めで戻さない",
    "F410": "「戻した」は戻した枝の単位の事で、直し直す道は無いまま",
    "F411": "(3) は持ち主の答え待ち",
    "F429": "最後の関所の文に並べるのは持ち主の手に渡した",
    "R38": "仕組みの異常は U6 で取れない",
    "R46": "一部だけ戻した（包み・会話を継いだ起動の数・即時の失敗は戻していない）",
}
MENTION = mention(INVENTORY_ROW_ID)
NARROWING = re.compile(r"^  - 狭め[:：（(\s].*(?:\n    .*)*", re.M)
OPEN = re.compile(r"→(?!.*→).*開いている", re.S)


def rows() -> list[tuple[str, str, str]]:
    """(ファイル:行, 行 ID, 行の字)。同じ ID の行が 2 つのファイルに在れば（gaps-plan.md と plan.md など）両方"""
    return [row for md in sorted(INVENTORY.glob("*.md")) for row in rows_of(md.name, md.read_text(encoding="utf-8"))]


def rows_of(name: str, text: str) -> list[tuple[str, str, str]]:
    """(ファイル:行, 行 ID, 行の字（頭の行と、字下げした続きの行）)。空の行は行を閉じない（row_fields と同じ読み）"""
    found = []
    current = None
    for no, line in enumerate(text.splitlines(), 1):
        if head := ROW.match(line):
            current = [f"{name}:{no}", head.group(1), line]
            found.append(current)
        elif current and line.startswith("  "):
            current[2] += "\n" + line
        elif line.strip():
            current = None
    return [(where, row, text) for where, row, text in found]


def state_text(text: str) -> str:
    """戻したか開いているかを書く字。「狭め」の欄（4 字下げの続きの行を含む）が在る行はその欄、無い行（線への申し送りの
    S の行・pitfalls.md の K の行）は行の字"""
    return field.group(0) if (field := NARROWING.search(text)) else text


def narrowings(texts: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """(ファイル:行, 行 ID, 狭めの欄の字)。狭めの欄の在る行だけ"""
    return [(where, row, field.group(0)) for where, row, text in texts if (field := NARROWING.search(text))]


def says_restored(row: str, text: str) -> bool:
    return bool(RESTORED.search(state_text(text))) and row not in PARTIAL


def says_open(row: str, text: str) -> bool:
    """最後の「→」の後に「開いている」"""
    return not says_restored(row, text) and bool(OPEN.search(state_text(text)))


def restored_ids(texts: list[tuple[str, str, str]]) -> set[str]:
    """棚卸しの行のうち、state_text の字に「→ … 戻した」が在り、PARTIAL に無い行の ID（同じ ID の行のどれか 1 つでも）"""
    return {row for _, row, text in texts if says_restored(row, text)}


def disagreements(texts: list[tuple[str, str, str]]) -> list[str]:
    """ほかの行の ID を名指す行と名指された行、と同じ ID の行どうしで、一方が戻した、一方が開いていると書く所。
    同じ能力を 2 つの区分の行が書く時（S07 と T16 など）、片方だけを直して食い違ったままにしない（#536）"""
    restored = restored_ids(texts)
    opened = {row for _, row, text in texts if says_open(row, text)}
    found = []
    for where, row, text in texts:
        is_open, is_restored = says_open(row, text), says_restored(row, text)
        if is_open and row in restored:
            found.append(f"{where} {row} は開いている、同じ ID の別の行は戻した")
        for named in sorted(set(MENTION.findall(text)) - {row}):
            if is_open and named in restored:
                found.append(f"{where} {row} は開いている、名指す {named} は戻した")
            elif is_restored and named in opened:
                found.append(f"{where} {row} は戻した、名指す {named} は開いている")
    return found


def rewritten(texts: list[tuple[str, str, str]], row: str, edit) -> list[tuple[str, str, str]]:
    """ID が row の行の字を edit で書き換えた写し"""
    return [(where, r, edit(text) if r == row else text) for where, r, text in texts]


def off_form(texts: list[tuple[str, str, str]]) -> list[str]:
    """狭めの欄が戻したと書くのに「→ … 戻した」の形でなく、PARTIAL にも無い所"""
    return [f"{where} {row}" for where, row, text in narrowings(texts)
            if SAYS_RESTORED.search(text) and not RESTORED.search(text) and row not in PARTIAL]


def narrowed_but_restored(areas: dict[str, dict[str, tuple[int, str]]], restored: set[str]) -> list[str]:
    """tail.md の狭めの並びに残る、戻した行"""
    return [f"{area} の {NARROWED}: {row} は戻した行" for area, counts in sorted(areas.items())
            for row in counts[NARROWED][1].split("・") if row in restored]


def gaps(node, where: str = ""):
    """(どこ, gaps の値)。表のどの深さの gaps も読む（graph の節も keep の行も）"""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "gaps" and isinstance(value, list):
                yield from ((f"{where}.gaps", gap) for gap in value)
            else:
                yield from gaps(value, f"{where}.{key}" if where else key)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from gaps(value, f"{where}[{i}]")


def still_holes(nodes: dict, evidence: list, restored: set[str]) -> list[str]:
    """戻した ID を穴として名指す所"""
    places = [(f"docs/nodes.json {where}", text) for where, text in gaps(nodes)]
    places += [(f"tests/e2e/evidence.json {row['id']}.why", row["why"]) for row in evidence if "why" in row]
    return [f"{where}: {i} は棚卸しが戻したとした行" for where, text in places
            for i in sorted(set(MENTION.findall(text)) & restored)]


def load(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


class RestoredNotGapsCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows()
        cls.restored = restored_ids(cls.rows)
        cls.nodes = load(NODES)
        cls.evidence = load(EVIDENCE)

    def test_reads_the_restored_rows(self):
        """読み落とし（欄の頭の形の変わり）で照らす ID が減っても緑のままにしない"""
        self.assertLessEqual({"T8", "T9", "T16", "T62", "T63", "F102", "F216", "F302", "F310", "J40", "J41",
                              "L-W07", "R5b", "S07"},
                             self.restored)
        self.assertGreater(len(self.restored), 100)

    def test_every_restored_row_is_in_the_form(self):
        """戻したと書く欄が形から外れると、その行の ID は照らされないまま緑になる"""
        self.assertEqual(off_form(self.rows), [])

    def test_rows_naming_each_other_agree(self):
        self.assertEqual(disagreements(self.rows), [])

    def where(self, row: str) -> str:
        return next(where for where, r, _ in self.rows if r == row)

    def test_a_naming_row_written_back_to_open_is_red(self):
        rows = rewritten(self.rows, "S07", lambda text: text.split(" → #122 で戻した")[0])
        self.assertEqual(disagreements(rows), [f"{self.where('S07')} S07 は開いている、名指す T16 は戻した"])

    def test_a_named_row_written_back_to_open_is_red(self):
        rows = rewritten(self.rows, "T16", lambda text: text.replace("→ #122 で戻した", "→ **開いている**"))
        self.assertEqual(disagreements(rows), [f"{self.where('S07')} S07 は戻した、名指す T16 は開いている"])

    def test_only_the_last_step_says_open(self):
        """「→ 開いている → 部分 D1 で閉じた」は閉じた行"""
        rows = [("a", "S1", "- S1 x → **開いている** → 部分 D1 で閉じた（T1）"), ("b", "S2", "- S2 x → **開いている**（T1）"),
                ("c", "T1", "- T1 y\n  - 狭め: 狭めた → #1 で戻した")]
        self.assertEqual(disagreements(rows), ["b S2 は開いている、名指す T1 は戻した"])

    def test_every_copy_of_a_row_is_read(self):
        """同じ ID の行が 2 つのファイルに在る時（gaps-plan.md と plan.md）、片方の行だけの「戻した」も落とさない"""
        copies = [where for where, row, _ in self.rows if row == "P057"]
        self.assertEqual([where.split(":")[0] for where in copies], ["gaps-plan.md", "plan.md"])
        first = copies[0]
        rows = [(where, row, text + " → #999 で戻した" if where == first else text) for where, row, text in self.rows]
        self.assertNotIn("P057", self.restored)
        self.assertIn("P057", restored_ids(rows))

    def test_a_blank_line_does_not_end_a_row(self):
        """空の行の後の狭めの欄も、その行の欄として読む"""
        texts = rows_of("x.md", "- T1 y\n  - 今: a\n\n  - 狭め: 狭めた → #1 で戻した\n\n## 次\n  - 狭め: → #2 で戻した")
        self.assertEqual(texts, [("x.md:1", "T1", "- T1 y\n  - 今: a\n  - 狭め: 狭めた → #1 で戻した")])
        self.assertEqual(restored_ids(texts), {"T1"})

    def test_copies_of_one_row_that_disagree_are_red(self):
        rows = self.rows + [("x.md:1", "T16", "- T16 y\n  - 狭め: 狭めた → **開いている**")]
        self.assertEqual(disagreements(rows), [f"{self.where('S07')} S07 は戻した、名指す T16 は開いている",
                                               "x.md:1 T16 は開いている、同じ ID の別の行は戻した"])

    def test_partial_rows_still_say_restored_and_are_not_read(self):
        self.assertTrue(PARTIAL.keys() <= {row for _, row, text in narrowings(self.rows) if SAYS_RESTORED.search(text)})
        self.assertFalse(PARTIAL.keys() & self.restored)

    def test_no_restored_row_stays_in_a_narrowed_list(self):
        self.assertEqual(narrowed_but_restored(hole_counts()[0], self.restored), [])

    def test_a_restored_row_left_in_a_narrowed_list_is_red(self):
        areas = {"R": {NARROWED: (2, "R2・R5b")}, "T": {NARROWED: (0, "")}}
        self.assertEqual(narrowed_but_restored(areas, self.restored), [f"R の {NARROWED}: R5b は戻した行"])

    def test_no_restored_row_is_still_named_as_a_hole(self):
        self.assertEqual(still_holes(self.nodes, self.evidence, self.restored), [])

    def test_a_restored_id_written_back_into_a_gap_is_red(self):
        nodes = copy.deepcopy(self.nodes)
        nodes["keep"]["5"]["gaps"] = ["#122 T8: 宣言の sha の照合を照らさない"]
        self.assertEqual(still_holes(nodes, self.evidence, self.restored),
                         ["docs/nodes.json keep.5.gaps: T8 は棚卸しが戻したとした行"])

    def test_a_restored_id_written_back_into_a_why_is_red(self):
        evidence = copy.deepcopy(self.evidence)
        row = next(r for r in evidence if r["id"] == "F310")
        row["why"] += "（F102 と同じ）"
        self.assertEqual(still_holes(self.nodes, evidence, self.restored),
                         ["tests/e2e/evidence.json F310.why: F102 は棚卸しが戻したとした行"])


if __name__ == "__main__":
    unittest.main()

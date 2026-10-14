"""能力の棚卸し（docs/plans/2026-10-13-capabilities/）が戻したとした行の ID が、節の表 docs/nodes.json の gaps と照らしの表
tests/e2e/evidence.json の why にまだ在れば赤にする（#527・#528・#530）。

戻した行は棚卸しの README.md の「穴の数え方」と同じく、「狭め」の欄に「→ … で戻した」が在る行。照らしは ID の在る無しだけで、
gaps と why の言い回しは読まない（棚卸しの戻した行を名指したければ、ID を書かずに今の住処を書く）。tracker は読まない。
"""
import copy
import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "docs" / "plans" / "2026-10-13-capabilities"
NODES = ROOT / "docs" / "nodes.json"
EVIDENCE = ROOT / "tests" / "e2e" / "evidence.json"
ROW_ID = r"(?:L-[EGWD]|[A-Z])\d+[a-z]?"
ROW = re.compile(rf"^- ({ROW_ID})[ 〔]")
FIELD = re.compile(r"^  - ([^:：（(\s]+)")
RESTORED = re.compile(r"→[^→]*で戻した")
# 日本語の字は \w に入るので、ID の前後は ASCII の字で区切る
MENTION = re.compile(rf"(?<![A-Za-z0-9-])({ROW_ID})(?![A-Za-z0-9])")


def restored_ids(folder: pathlib.Path = INVENTORY) -> set[str]:
    """棚卸しの行のうち、「狭め」の欄（4 字下げの続きの行を含む）に「→ … で戻した」が在る行の ID"""
    found = set()
    for md in sorted(folder.glob("*.md")):
        row = field = None
        for line in md.read_text(encoding="utf-8").splitlines():
            if head := FIELD.match(line):
                field = head.group(1)
            elif not line.startswith("    "):
                field = None
                if line.strip():
                    row = head.group(1) if (head := ROW.match(line)) else None
            if row and field == "狭め" and RESTORED.search(line):
                found.add(row)
    return found


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
        cls.restored = restored_ids()
        cls.nodes = load(NODES)
        cls.evidence = load(EVIDENCE)

    def test_reads_the_restored_rows(self):
        """読み落とし（欄の頭の形の変わり）で照らす ID が減っても緑のままにしない"""
        self.assertLessEqual({"T8", "T9", "T16", "T62", "T63", "F102", "F216", "F302", "J41", "L-W07", "R5b"},
                             self.restored)
        self.assertGreater(len(self.restored), 100)

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

    def test_ids_are_read_whole(self):
        """L-E02 の E02・T80 の T8 を別の ID と読まない"""
        self.assertEqual(MENTION.findall("L-E02・T80・T8：R5b と"), ["L-E02", "T80", "T8", "R5b"])


if __name__ == "__main__":
    unittest.main()

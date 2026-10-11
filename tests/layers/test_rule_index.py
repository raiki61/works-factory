"""決まりの番号（E1 など）が、根の AGENTS.md の表の置き場にちょうど 1 つずつ在ることを確かめる（根の AGENTS.md の「決まりの置き場」）。"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
ROW = re.compile(r"^\| (E\d+) \| `([^`]+)` \|$", re.M)
HEADING = re.compile(r"^## (E\d+) ", re.M)


def problems(root):
    """表と各 AGENTS.md の見出しの食い違いを 1 行ずつ返す（無ければ空）"""
    table = dict(ROW.findall((root / "AGENTS.md").read_text(encoding="utf-8")))
    found = {}
    for path in sorted(root.rglob("AGENTS.md")):
        rel = path.relative_to(root).as_posix()
        for rule in HEADING.findall(path.read_text(encoding="utf-8")):
            found.setdefault(rule, []).append(rel)
    out = []
    for rule in sorted(set(table) | set(found), key=lambda r: int(r[1:])):
        where = found.get(rule, [])
        if rule not in table:
            out.append(f"{rule}: 表に無い（見出しは {', '.join(where)}）")
        elif where != [table[rule]]:
            out.append(f"{rule}: 表は {table[rule]}、見出しは {', '.join(where) or '無し'}")
    return out


class RuleIndexTest(unittest.TestCase):
    def test_each_rule_lives_where_the_table_says(self):
        self.assertEqual(problems(ROOT), [])

    def test_rules_are_numbered_without_gaps(self):
        table = ROW.findall((ROOT / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertEqual([r for r, _ in table], [f"E{i}" for i in range(1, len(table) + 1)])


if __name__ == "__main__":
    unittest.main()

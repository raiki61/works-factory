"""決まりの番号（E1 など）が、根の `AGENTS.md` の「決まりの置き場」の表の置き場にちょうど 1 つずつ在る（根の `AGENTS.md` の「決まりの置き場」）。

- 表の行は `| E<番号> | `<置き場>` |`、見出しは `## E<番号> `。表の番号は 1 から欠けずに並ぶ。
- 置き場の `AGENTS.md` は git が知る（追跡中と、無視されない未追跡の）全部の階層を探す（`workflows/AGENTS.md`・`lib/AGENTS.md`・`tests/AGENTS.md`・`bin/AGENTS.md` と根）。
"""
import inspect
import pathlib
import re
import unittest

from tests.bin import gitkit
from tests.layers import trees
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
ROW = re.compile(r"^\| (E\d+) \| `([^`]+)` \|$", re.M)
HEADING = re.compile(r"^## (E\d+) ", re.M)


def problems(root):
    """表と各 AGENTS.md の見出しの食い違いを 1 行ずつ返す（無ければ空）"""
    table = dict(ROW.findall((root / "AGENTS.md").read_text(encoding="utf-8")))
    found = {}
    for path in trees.agents_files(root):
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

    def test_copy_under_git_dir_and_ignored_folder_are_not_read(self):
        self.assertTrue(hasattr(trees, "agents_files"), "tests.layers.trees に agents_files が無い")
        index = "| E1 | `AGENTS.md` |\n\n## E1 決まり\n"
        files = {"AGENTS.md": index, ".gitignore": "backup/\n", "backup/AGENTS.md": "## E1 写し\n"}
        with tree(files) as root:
            gitkit.git(root, "init", "-q")
            gitkit.git(root, "add", "-f", "--", "AGENTS.md")
            copy = root / ".git" / "company" / "old" / "AGENTS.md"
            copy.parent.mkdir(parents=True)
            copy.write_text("## E1 写し\n", encoding="utf-8")
            self.assertEqual(problems(root), [])

    def test_unmerged_agents_md_is_read_once(self):
        self.assertTrue(hasattr(trees, "agents_files"), "tests.layers.trees に agents_files が無い")
        self.assertIn("git_init", inspect.signature(tree).parameters, "tests.layers.trees.tree に git_init が無い")
        self.assertTrue(hasattr(gitkit, "known_files"), "tests.bin.gitkit に known_files が無い")
        with tree({"AGENTS.md": "| E1 | `AGENTS.md` |\n\n## E1 決まり\n"}, git_init=True) as root:
            blob = gitkit.git(root, "hash-object", "-w", "--stdin", stdin="x\n")
            gitkit.git(root, "update-index", "--index-info",
                       stdin="".join(f"100644 {blob} {stage}\tAGENTS.md\n" for stage in (1, 2, 3)))
            self.assertEqual(gitkit.known_files(root).count("AGENTS.md"), 1)
            self.assertEqual(trees.agents_files(root), [root / "AGENTS.md"])
            self.assertEqual(problems(root), [])


if __name__ == "__main__":
    unittest.main()

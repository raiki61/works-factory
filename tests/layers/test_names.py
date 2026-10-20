"""グラフの名が `works-factory-<フォルダの名>` で、`archon-` で始まらない（根の `AGENTS.md` の E9 の機械の行）。自分の層のパスの部分が ASF の物の名で始まらない（E18 の機械の行）。

- E9: `workflows/<名>/works-factory-<名>.yaml` の `name:` がフォルダの名と同じ `works-factory-<名>`。
- E18: `bin/`・`workflows/`・`lib/`・`tests/`・`docs/` の下のパスの部分（フォルダとファイルの名）に、`factory`・`FACTORY`・`harness`・`.factory`・`archon-` で始まる物が無い（持ち主の決め `name-by-origin`）。ASF の物が根の `AGENTS.md` の木の場所の外に無いことは人が見る。
"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"


class NamesTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E9", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E9", SEEDS / "e9")
        self.assertGreaterEqual(len(got), 1)
        self.assertTrue(any("workflows/judge/works-factory-judge.yaml" in line for line in got), got)

    def test_name_of_another_folder_is_red(self):
        with tree({"workflows/judge/works-factory-judge.yaml": "name: works-factory-plan\nnodes: []\n"}) as root:
            got = scan.problems("E9", root)
        self.assertTrue(any("works-factory-judge.yaml:1" in line and "works-factory-judge" in line for line in got), got)

    def test_missing_name_is_red(self):
        with tree({"workflows/judge/works-factory-judge.yaml": "nodes: []\n"}) as root:
            got = scan.problems("E9", root)
        self.assertTrue(any("works-factory-judge.yaml" in line for line in got), got)


class OriginNamesTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E18", ROOT), [])

    def test_asf_named_path_part_is_red(self):
        files = {
            "docs/archon-notes.md": "x",
            "lib/factory/a.py": "",
            "tests/harness_x.py": "",
            "workflows/judge/FACTORY.md": "x",
            "bin/.factory/a": "x",
        }
        with tree(files) as root:
            got = scan.problems("E18", root)
        for rel in files:
            self.assertTrue(any(line.startswith(rel + ":") for line in got), (rel, got))

    def test_other_names_pass(self):
        with tree({"docs/polyfills.md": "x", "lib/carry.py": "", "workflows/judge/works-factory-judge.yaml": "x"}) as root:
            self.assertEqual(scan.problems("E18", root), [])


if __name__ == "__main__":
    unittest.main()

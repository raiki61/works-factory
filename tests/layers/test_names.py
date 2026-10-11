"""工程の名が `works-factory-<フォルダの名>` で、`archon-` で始まらない（根の AGENTS.md の E9 の機械の行）。

E9 だけ。E18 の機械の行はまだ作らない（`scan.problems` の決まりの組に無い）。"""
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


if __name__ == "__main__":
    unittest.main()

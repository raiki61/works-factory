"""ブロックの script と YAML の字に、ほかのブロックを指すパスと、`lib/`・`workflows/.shared/` の外への相対パスが無い（workflows/AGENTS.md の E4 の機械の行）。"""
import pathlib
import re
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"


class BlockPathsTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E4", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E4", SEEDS / "e4")
        self.assertGreaterEqual(len(got), 1)
        self.assertTrue(any("workflows/judge/scripts/a.py" in line for line in got), got)

    def test_relative_path_outside_allowed_places_is_red(self):
        with tree({"workflows/judge/scripts/a.py": 'X = "../../../bin/tool"\n'}) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("a.py:1" in line and "外" in line for line in got), got)

    def test_relative_path_into_lib_is_clean(self):
        with tree({"workflows/judge/scripts/a.py": 'X = "../../../lib/x.py"\n'}) as root:
            self.assertEqual(scan.problems("E4", root), [])

    def test_other_block_named_in_full_is_red(self):
        with tree({"workflows/judge/scripts/a.py": 'X = "workflows/plan/out.json"\n'}) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("a.py:1" in line and "plan" in line for line in got), got)

    def test_archon_read_path_of_other_block_is_red(self):
        with tree({"workflows/judge/scripts/a.py": 'X = "$SRC/.archon/workflows/plan/out.json"\n'}) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("a.py:1" in line and "plan" in line for line in got), got)

    def test_archon_pack_path_of_other_block_is_red(self):
        for text in ('X = "$SRC/.archon/workflows/works-factory/plan/out.json"\n',
                     'X = "../../../.archon/workflows/works-factory/plan/out.json"\n'):
            with self.subTest(text=text), tree({"workflows/judge/scripts/a.py": text}) as root:
                got = scan.problems("E4", root)
                self.assertTrue(any("a.py:1" in line and "plan" in line for line in got), got)

    def test_archon_pack_path_of_own_block_is_clean(self):
        with tree({"workflows/judge/scripts/a.py": 'X = "$SRC/.archon/workflows/works-factory/judge/out.json"\n'}) as root:
            self.assertEqual(scan.problems("E4", root), [])

    def test_inline_script_in_yaml_pointing_at_other_block_through_pack_is_red(self):
        yaml = "name: works-factory-judge\nnodes:\n  - id: a\n    script: cat ../works-factory/plan/out.json\n"
        with tree({"workflows/judge/works-factory-judge.yaml": yaml}) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("works-factory-judge.yaml:4" in line and "plan" in line for line in got), got)

    def test_inline_script_in_yaml_pointing_at_other_block_is_red(self):
        yaml = "name: works-factory-judge\nnodes:\n  - id: a\n    script: cat ../../plan/out.json\n"
        with tree({"workflows/judge/works-factory-judge.yaml": yaml}) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("works-factory-judge.yaml:4" in line and "plan" in line for line in got), got)

    def test_inline_script_in_yaml_into_lib_is_clean(self):
        yaml = "name: works-factory-judge\nnodes:\n  - id: a\n    script: run ../../lib/x.py\n"
        with tree({"workflows/judge/works-factory-judge.yaml": yaml}) as root:
            self.assertEqual(scan.problems("E4", root), [])

    def test_block_names_match_root_tree(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        listed = re.search(r"<ブロック>/\s+(\S+) の \d+ つ", text)[1].split("・")
        self.assertIn("── line/", text)
        self.assertEqual(sorted(scan.BLOCKS), sorted(["line", *listed]))

    def test_block_only_on_disk_counts_as_other(self):
        files = {"workflows/judge/scripts/a.py": 'X = "workflows/newblock/out.json"\n', "workflows/newblock/x": ""}
        with tree(files) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("a.py:1" in line and "newblock" in line for line in got), got)


if __name__ == "__main__":
    unittest.main()

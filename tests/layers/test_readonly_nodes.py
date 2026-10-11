"""作業ツリーを変えない節が `mutates_checkout: false` を書く（workflows/AGENTS.md の E7 の機械の行）。

ブロック judge・plan・plan-review・eyes・report の役の節（`prompt:`・`command:`。`loop:` の節は Archon が mutates_checkout を無視するので数えない）は全部。ただし judge の役のうち
作業ツリーに書く役と対象のリポジトリでコマンドを走らせる役（scan.JUDGE_WRITERS）は除く。ほかのブロックと線は表
scan.READONLY_NODES で名指した節。
"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"
JUDGE = "workflows/judge/works-factory-judge.yaml"
LINE = "workflows/line/works-factory-line.yaml"


class ReadonlyNodesTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E7", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E7", SEEDS / "e7")
        self.assertEqual(len(got), 1, got)
        self.assertIn(f"{JUDGE}:3", got[0])

    def problems(self, files):
        with tree(files) as root:
            return scan.problems("E7", root)

    def test_role_nodes_with_the_mark_are_clean(self):
        yaml = (
            "name: works-factory-judge\nnodes:\n  - id: diagnose\n    prompt: x\n    idle_timeout: 1728000000\n"
            "    mutates_checkout: false\n  - id: g\n    loop_group:\n      nodes:\n"
            "        - id: again\n          command: judge\n          mutates_checkout: false\n"
            "  - id: take\n    script: take\n    timeout: 1728000000\n"
        )
        self.assertEqual(self.problems({JUDGE: yaml}), [])

    def test_nested_role_node_without_the_mark_is_red(self):
        yaml = "name: works-factory-judge\nnodes:\n  - id: g\n    loop_group:\n      nodes:\n        - id: again\n          command: judge\n"
        got = self.problems({JUDGE: yaml})
        self.assertEqual(len(got), 1, got)
        self.assertIn("again", got[0])

    def test_judge_writers_are_excused(self):
        nodes = "".join(f"  - id: {name}\n    prompt: x\n" for name in scan.JUDGE_WRITERS)
        self.assertEqual(self.problems({JUDGE: "name: works-factory-judge\nnodes:\n" + nodes}), [])

    def test_mark_set_to_true_is_red(self):
        yaml = "name: works-factory-plan\nnodes:\n  - id: plan\n    prompt: x\n    mutates_checkout: true\n"
        got = self.problems({"workflows/plan/works-factory-plan.yaml": yaml})
        self.assertEqual(len(got), 1, got)

    def test_loop_node_is_not_asked_for_the_mark(self):
        yaml = "name: works-factory-judge\nnodes:\n  - id: again\n    loop:\n      prompt: x\n"
        self.assertEqual(self.problems({JUDGE: yaml}), [])

    def test_role_nodes_of_other_blocks_are_free(self):
        yaml = "name: works-factory-fix\nnodes:\n  - id: fixer\n    prompt: x\n"
        self.assertEqual(self.problems({"workflows/fix/works-factory-fix.yaml": yaml}), [])

    def test_named_line_node_without_the_mark_is_red(self):
        named = scan.READONLY_NODES["line"]
        nodes = "".join(f"  - id: {name}\n    script: x\n    mutates_checkout: false\n" for name in named[1:])
        got = self.problems({LINE: f"name: works-factory-line\nnodes:\n  - id: {named[0]}\n    script: x\n" + nodes})
        self.assertEqual(len(got), 1, got)
        self.assertIn(named[0], got[0])

    def test_named_node_missing_from_its_workflow_is_red(self):
        """表が名指した節が工程に無ければ赤（表が古くなって黙って照らさなくならない）"""
        got = self.problems({LINE: "name: works-factory-line\nnodes: []\n"})
        self.assertEqual(len(got), len(scan.READONLY_NODES["line"]), got)


if __name__ == "__main__":
    unittest.main()

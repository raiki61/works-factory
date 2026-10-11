"""人の関所の形（workflows/AGENTS.md の E16 の機械の行）。

`approval:` の節を持つ工程を（差し込みを辿って）含む一番上の工程に `interactive: true` が在る。差し込まれるブロックは工程の頭に
`interactive`・`worktree`・`container`・`evidence_policy`・`mutates_checkout` を書かない。ただし自分の節に `approval:` を持つブロックの
`interactive: true` だけは許す（外すと止めた Archon の単独の validate が警告を出す）。並べの形は人が見る。
"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"
JUDGE = "workflows/judge/works-factory-judge.yaml"
PLAN = "workflows/plan/works-factory-plan.yaml"
LINE = "workflows/line/works-factory-line.yaml"
GATE = "  - id: g\n    approval:\n      message: m\n      decisions: [{id: approve}, {id: stop}]\n    idle_timeout: 1728000000\n"


class GatesTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E16", ROOT), [])

    def test_seed_caught(self):
        """種: 関所を持つ judge の interactive: true は許し、関所の無い plan の interactive: true と、judge を差し込む線に
        interactive: true が無いことを赤にする"""
        got = scan.problems("E16", SEEDS / "e16")
        self.assertEqual(len(got), 2, got)
        self.assertTrue(any(PLAN in line and "interactive" in line for line in got), got)
        self.assertTrue(any(LINE in line and "interactive" in line for line in got), got)
        self.assertFalse([line for line in got if JUDGE in line], got)

    def problems(self, files):
        with tree(files) as root:
            return scan.problems("E16", root)

    def test_line_with_its_own_gate_is_interactive(self):
        self.assertEqual(self.problems({LINE: "name: works-factory-line\ninteractive: true\nnodes:\n" + GATE}), [])
        got = self.problems({LINE: "name: works-factory-line\nnodes:\n" + GATE})
        self.assertEqual(len(got), 1, got)

    def test_gate_inside_an_included_block_needs_the_line_interactive(self):
        files = {JUDGE: "name: works-factory-judge\nnodes:\n" + GATE,
                 LINE: "name: works-factory-line\nnodes:\n  - id: g\n    loop_group:\n      nodes:\n"
                       "        - id: judge\n          include: works-factory-judge\n"}
        got = self.problems(files)
        self.assertEqual(len(got), 1, got)
        self.assertIn(LINE, got[0])

    def test_interactive_false_is_red(self):
        got = self.problems({LINE: "name: works-factory-line\ninteractive: false\nnodes:\n" + GATE})
        self.assertEqual(len(got), 1, got)

    def test_block_head_keys_are_red(self):
        for key in scan.BLOCK_HEAD_KEYS:
            with self.subTest(key=key):
                got = self.problems({JUDGE: f"name: works-factory-judge\n{key}: x\nnodes: []\n"})
                self.assertEqual(len(got), 1, got)
                self.assertIn(f"{JUDGE}:2", got[0])

    def test_block_with_its_own_gate_may_say_interactive_true_only(self):
        self.assertEqual(self.problems({JUDGE: "name: works-factory-judge\ninteractive: true\nnodes:\n" + GATE}), [])
        looped = ("name: works-factory-judge\ninteractive: true\nnodes:\n  - id: l\n    loop_group:\n      nodes:\n"
                  + GATE.replace("\n  ", "\n      ").replace("  - id: g", "        - id: g", 1))
        self.assertEqual(self.problems({JUDGE: looped}), [])
        for head in ("interactive: false", "interactive: \"true\""):
            with self.subTest(head=head):
                got = self.problems({JUDGE: f"name: works-factory-judge\n{head}\nnodes:\n" + GATE})
                self.assertEqual(len(got), 1, got)
                self.assertIn(f"{JUDGE}:2", got[0])

    def test_gate_only_through_an_include_does_not_allow_interactive(self):
        files = {PLAN: "name: works-factory-plan\nnodes:\n" + GATE,
                 JUDGE: "name: works-factory-judge\ninteractive: true\nnodes:\n  - id: p\n    include: works-factory-plan\n"}
        got = self.problems(files)
        self.assertEqual(len(got), 1, got)
        self.assertIn(f"{JUDGE}:2", got[0])

    def test_workflow_without_gates_needs_nothing(self):
        self.assertEqual(self.problems({LINE: "name: works-factory-line\nnodes: []\n"}), [])


if __name__ == "__main__":
    unittest.main()

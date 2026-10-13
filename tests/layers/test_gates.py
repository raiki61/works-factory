"""人の関所の形（workflows/AGENTS.md の E16 の機械の行）。

`approval:` の節を持つ工程を（差し込みを辿って）含む一番上の工程に `interactive: true` が在る。差し込まれるブロックは工程の頭に
`interactive`・`worktree`・`container`・`evidence_policy`・`mutates_checkout` を書かない。ただし自分の節に `approval:` を持つブロックの
`interactive: true` だけは許す（外すと止めた Archon の単独の validate が警告を出す）。どの工程の関所も decisions に答えの語
（lib/answer.py の GO_WORDS・STOP_WORDS・REJECT）を全部持ち、on_reject を持たない（K10）。輪（loop_group）の本体に関所を置かない（K18）。並べの形は人が見る。
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
GATE = "  - id: g\n    approval:\n      message: m\n      decisions: [{id: approve}, {id: continue}, {id: stop}, {id: reject}]\n    idle_timeout: 1728000000\n"


def in_loop(nodes: str) -> str:
    """節の並び（2 字下げ）を、輪 l の本体に入れた節の並びにする"""
    return "  - id: l\n    loop_group:\n      nodes:\n" + "".join(f"      {line}\n" for line in nodes.splitlines())


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
        got = self.problems({JUDGE: "name: works-factory-judge\ninteractive: true\nnodes:\n" + in_loop(GATE)})
        self.assertEqual(len(got), 1, got)
        self.assertIn("輪の本体に関所 g", got[0], "輪の中の関所も自分の関所として interactive: true を許す。赤は輪の本体の関所だけ")
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

    def test_gate_without_an_answer_word_is_red(self):
        """decisions に答えの語が 1 つでも無い関所は赤（reject が無いと Archon が run の取り消しにし、報告が出ない）"""
        for word in ("approve", "continue", "stop", "reject"):
            with self.subTest(word=word):
                gate = GATE.replace(f"{{id: {word}}}, ", "").replace(f", {{id: {word}}}", "")
                self.assertNotIn(word, gate)
                got = self.problems({LINE: "name: works-factory-line\ninteractive: true\nnodes:\n" + gate})
                self.assertEqual(len(got), 1, got)
                self.assertIn(f"{word} が無い", got[0])

    def test_gate_with_on_reject_is_red(self):
        gate = GATE.replace("      message: m\n", "      message: m\n      on_reject: {prompt: x}\n")
        got = self.problems({LINE: "name: works-factory-line\ninteractive: true\nnodes:\n" + gate})
        self.assertEqual(len(got), 1, got)
        self.assertIn("on_reject", got[0])

    def test_gate_inside_a_loop_body_is_red(self):
        got = self.problems({LINE: "name: works-factory-line\ninteractive: true\nnodes:\n" + in_loop(GATE)})
        self.assertEqual(len(got), 1, got)
        self.assertIn("輪の本体に関所 g", got[0])

    def test_gate_seeds_are_one_violation_each(self):
        """違反の見本（tests/layers/seeds/k10・k18）は 1 本 1 違反"""
        for seed, words in (("k10-no-reject", "reject が無い"), ("k10-on-reject", "on_reject"), ("k18-gate-in-loop", "輪の本体")):
            with self.subTest(seed=seed):
                got = scan.problems("E16", SEEDS / seed)
                self.assertEqual(len(got), 1, got)
                self.assertIn(words, got[0])


if __name__ == "__main__":
    unittest.main()

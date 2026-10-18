"""`workflows/` の YAML で、節の種類が全部知った物で、どの節も `timeout` を書かず、期限を持つ節の `idle_timeout`・`wait.deadline_ms` が全部 `1728000000`（workflows/AGENTS.md の E12 の機械の行）。"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"
BLOCK = "workflows/judge/works-factory-judge.yaml"


class NoTimeoutsTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E12", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E12", SEEDS / "e12")
        self.assertGreaterEqual(len(got), 1)
        self.assertTrue(any("workflows/judge/works-factory-judge.yaml" in line for line in got), got)

    def problems(self, nodes):
        with tree({BLOCK: "name: works-factory-judge\nnodes:\n" + nodes}) as root:
            return scan.problems("E12", root)

    def test_every_deadline_set_is_clean(self):
        nodes = (
            "  - id: run\n    script: stub\n"
            "  - id: ask\n    prompt: hi\n    idle_timeout: 1728000000\n"
            "  - id: retry\n    loop: {prompt: judge, until: DONE, max_iterations: 3}\n"
            "    idle_timeout: 1728000000\n"
            "  - id: g\n    loop_group: {until_bash: 'true', max_iterations: 3, nodes: [{id: x, cancel: stop}]}\n"
            "  - id: ok\n    approval: {message: hi}\n    idle_timeout: 1728000000\n"
            "  - id: ci\n    wait: {event: ci, deadline_ms: 1728000000}\n"
            "  - id: sub\n    include: works-factory-plan\n"
        )
        self.assertEqual(self.problems(nodes), [])

    def test_merge_key_supplies_kind_and_deadline(self):
        nodes = (
            "  - id: a\n    <<: &launch\n      prompt: hi\n      idle_timeout: 1728000000\n"
            "  - id: b\n    <<: *launch\n"
            "  - id: c\n    <<: *launch\n    idle_timeout: 600\n"
        )
        got = self.problems(nodes)
        self.assertEqual(len(got), 1, got)
        self.assertIn(f"{BLOCK}:11: idle_timeout", got[0])

    def test_written_timeout_is_red(self):
        got = self.problems("  - id: run\n    script: stub\n    timeout: 1728000000\n")
        self.assertEqual(got, [f"{BLOCK}:5: timeout を書かない（書かなければ期限が無い）"])

    def test_short_idle_timeout_is_red(self):
        got = self.problems("  - id: ask\n    prompt: hi\n    idle_timeout: 600\n")
        self.assertTrue(any(f"{BLOCK}:5" in line and "idle_timeout" in line for line in got), got)

    def test_ai_node_without_idle_timeout_is_red(self):
        got = self.problems("  - id: ask\n    prompt: hi\n  - id: judge\n    command: judge\n")
        self.assertEqual(len(got), 2, got)
        self.assertTrue(all(BLOCK in line and "idle_timeout" in line for line in got), got)

    def test_loop_node_without_idle_timeout_is_red(self):
        got = self.problems("  - id: retry\n    loop: {prompt: judge, until: DONE, max_iterations: 3}\n")
        self.assertEqual(got, [f"{BLOCK}:3: 節に idle_timeout が無い（Archon の既定の期限が当たる）"])

    def test_loop_group_check_with_timeout_is_red(self):
        got = self.problems("  - id: g\n    loop_group: {until_bash: 'true', max_iterations: 3, nodes: [{id: x, cancel: stop}]}\n"
                            "    timeout: 1728000000\n")
        self.assertEqual(got, [f"{BLOCK}:5: timeout を書かない（書かなければ期限が無い）"])

    def test_approval_without_idle_timeout_is_red(self):
        got = self.problems("  - id: ok\n    approval: {message: hi, on_reject: {prompt: fix}}\n")
        self.assertEqual(got, [f"{BLOCK}:3: 節に idle_timeout が無い（Archon の既定の期限が当たる）"])

    def test_short_wait_deadline_is_red(self):
        got = self.problems("  - id: ci\n    wait:\n      event: ci\n      deadline_ms: 300000\n")
        self.assertEqual(got, [f"{BLOCK}:6: deadline_ms が 1728000000 でない"])

    def test_unknown_node_kind_is_red(self):
        got = self.problems("  - id: new\n    sleep: 10\n")
        self.assertTrue(any(f"{BLOCK}:3" in line and "種類" in line for line in got), got)

    def test_nested_node_with_timeout_is_red(self):
        nodes = (
            "  - id: g\n    loop_group:\n      nodes:\n"
            "        - id: run\n          script: stub\n          timeout: 10\n"
        )
        got = self.problems(nodes)
        self.assertTrue(any(f"{BLOCK}:8" in line and "timeout" in line for line in got), got)

    def test_nodes_inside_with_values_are_not_nodes(self):
        nodes = "  - id: sub\n    include: works-factory-plan\n    with:\n      nodes: [{id: x, script: stub}]\n"
        self.assertEqual(self.problems(nodes), [])

    def test_schema_field_named_timeout_is_clean(self):
        nodes = (
            "  - id: result\n    script: stub\n"
            "    output_format:\n      type: object\n      properties:\n        timeout: {type: boolean}\n"
        )
        self.assertEqual(self.problems(nodes), [])


if __name__ == "__main__":
    unittest.main()

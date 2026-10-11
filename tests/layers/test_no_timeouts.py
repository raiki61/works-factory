"""`workflows/` の YAML で、期限を持つ節の `timeout`・`idle_timeout` が全部 `1728000000`（workflows/AGENTS.md の E12 の機械の行）。"""
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
            "  - id: run\n    script: stub\n    timeout: 1728000000\n"
            "  - id: ask\n    prompt: hi\n    idle_timeout: 1728000000\n"
            "  - id: retry\n    loop: {prompt: judge, until: DONE, max_iterations: 3}\n    idle_timeout: 1728000000\n"
        )
        self.assertEqual(self.problems(nodes), [])

    def test_missing_timeout_is_red(self):
        got = self.problems("  - id: run\n    script: stub\n")
        self.assertTrue(any(BLOCK in line and "timeout" in line for line in got), got)

    def test_short_idle_timeout_is_red(self):
        got = self.problems("  - id: ask\n    prompt: hi\n    idle_timeout: 600\n")
        self.assertTrue(any(f"{BLOCK}:5" in line and "idle_timeout" in line for line in got), got)

    def test_ai_node_without_idle_timeout_is_red(self):
        got = self.problems("  - id: ask\n    prompt: hi\n  - id: judge\n    command: judge\n")
        self.assertEqual(len(got), 2, got)
        self.assertTrue(all(BLOCK in line and "idle_timeout" in line for line in got), got)

    def test_loop_node_without_idle_timeout_is_red(self):
        got = self.problems("  - id: retry\n    loop: {prompt: judge, until: DONE, max_iterations: 3}\n")
        self.assertTrue(any(BLOCK in line and "idle_timeout" in line for line in got), got)

    def test_nested_node_with_short_timeout_is_red(self):
        nodes = (
            "  - id: g\n    loop_group:\n      nodes:\n"
            "        - id: run\n          script: stub\n          timeout: 10\n"
        )
        got = self.problems(nodes)
        self.assertTrue(any(f"{BLOCK}:8" in line and "timeout" in line for line in got), got)

    def test_schema_field_named_timeout_is_clean(self):
        nodes = (
            "  - id: result\n    script: stub\n    timeout: 1728000000\n"
            "    output_format:\n      type: object\n      properties:\n        timeout: {type: boolean}\n"
        )
        self.assertEqual(self.problems(nodes), [])


if __name__ == "__main__":
    unittest.main()

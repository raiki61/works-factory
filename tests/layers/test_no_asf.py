"""`workflows/` の YAML の `include:`・`workflow:` の値が `works-factory-` で始まる（根の AGENTS.md の E8 の機械の行）。"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"


class NoAsfTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E8", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E8", SEEDS / "e8")
        self.assertGreaterEqual(len(got), 1)
        self.assertTrue(any("workflows/judge/works-factory-judge.yaml" in line for line in got), got)

    def test_workflow_call_is_red(self):
        yaml = "name: works-factory-judge\nnodes:\n  - id: f\n    workflow: archon-fix\n"
        with tree({"workflows/judge/works-factory-judge.yaml": yaml}) as root:
            got = scan.problems("E8", root)
        self.assertTrue(any("works-factory-judge.yaml:4" in line and "workflow" in line for line in got), got)

    def test_include_in_nested_nodes_is_red(self):
        yaml = (
            "name: works-factory-judge\nnodes:\n  - id: g\n    loop_group:\n      nodes:\n"
            "        - id: p\n          include: archon-plan\n"
        )
        with tree({"workflows/judge/works-factory-judge.yaml": yaml}) as root:
            got = scan.problems("E8", root)
        self.assertTrue(any("works-factory-judge.yaml:7" in line and "include" in line for line in got), got)

    def test_schema_field_named_workflow_is_clean(self):
        yaml = (
            "name: works-factory-report\nnodes:\n  - id: result\n    script: stub\n    timeout: 1728000000\n"
            "    output_format:\n      type: object\n      properties:\n        workflow: {type: string}\n"
        )
        with tree({"workflows/report/works-factory-report.yaml": yaml}) as root:
            self.assertEqual(scan.problems("E8", root), [])


if __name__ == "__main__":
    unittest.main()

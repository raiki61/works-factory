"""ブロックの返りが 1 つの節の構造体で、返りの欄に読み手が在る（workflows/AGENTS.md の E5 の機械の行）。

在るブロックに `returns:` と `outcome_field:` が在り、返す節が `output_format` を持ち、`outcome_field` の欄がその `required` に在る。
返りの欄のうち、線の `with:`・`when:`・返しの節の `from` の誰も `$<include の id>.output.<欄>` で読まない物は赤。
線の読む欄が返す節に在るかは Archon の `validate` が照らす（tests/layers/test_archon_validate.py）ので、ここでは照らさない。
"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"
BLOCK = "workflows/judge/works-factory-judge.yaml"
LINE = "workflows/line/works-factory-line.yaml"
RETURNING = (
    "name: works-factory-judge\nreturns: verdict\noutcome_field: ready\nnodes:\n"
    "  - id: verdict\n    script: stub\n    timeout: 1728000000\n"
    "    output_format:\n      type: object\n      properties:\n        ready: {type: boolean}\n        units: {type: array}\n"
    "      required: [ready, units]\n"
)


class BlockReturnsTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E5", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E5", SEEDS / "e5")
        self.assertEqual(len(got), 1, got)
        self.assertIn(BLOCK, got[0])
        self.assertIn("unread", got[0])

    def problems(self, block, line):
        with tree({BLOCK: block, LINE: line}) as root:
            return scan.problems("E5", root)

    def test_every_field_read_by_the_line_is_clean(self):
        line = (
            "name: works-factory-line\nnodes:\n  - id: judge\n    include: works-factory-judge\n"
            "  - id: plan\n    include: works-factory-plan\n    when: \"$judge.output.ready == true\"\n"
            "    with:\n      units: $judge.output.units\n"
        )
        self.assertEqual(self.problems(RETURNING, line), [])

    def test_field_read_through_another_include_of_the_same_block_counts(self):
        line = (
            "name: works-factory-line\nnodes:\n  - id: judge\n    include: works-factory-judge\n"
            "  - id: rejudge\n    include: works-factory-judge\n"
            "  - id: collect\n    script: collect\n    timeout: 1728000000\n    with:\n"
            "      ready: $judge.output.ready\n      units: { from: \"$rejudge.output.units\", if_skipped: null }\n"
        )
        self.assertEqual(self.problems(RETURNING, line), [])

    def test_field_read_inside_a_loop_group_body_counts(self):
        line = (
            "name: works-factory-line\nnodes:\n  - id: rounds\n    loop_group:\n      max_iterations: 3\n"
            "      until_bash: '[ $out.output.done = \"true\" ]'\n      nodes:\n"
            "        - id: judge\n          include: works-factory-judge\n"
            "        - id: out\n          script: out\n          depends_on: [judge]\n          with:\n"
            "            ready: $judge.output.ready\n            units: $LOOP_PREV.judge.output.units\n"
        )
        self.assertEqual(self.problems(RETURNING, line), [])

    def test_unread_field_is_red(self):
        line = "name: works-factory-line\nnodes:\n  - id: judge\n    include: works-factory-judge\n    when: \"$judge.output.ready\"\n"
        got = self.problems(RETURNING, line)
        self.assertEqual(len(got), 1, got)
        self.assertIn(f"{BLOCK}:", got[0])
        self.assertIn("units", got[0])

    def test_same_field_name_of_another_node_is_not_a_reader(self):
        line = (
            "name: works-factory-line\nnodes:\n  - id: judge\n    include: works-factory-judge\n"
            "  - id: x\n    script: x\n    timeout: 1728000000\n    with:\n      ready: $judge.output.ready\n"
            "      units: $x.output.units\n"
        )
        got = self.problems(RETURNING, line)
        self.assertTrue(any("units" in line for line in got), got)

    def test_missing_returns_or_outcome_field_is_red(self):
        for drop in ("returns: verdict\n", "outcome_field: ready\n"):
            with self.subTest(drop=drop):
                got = self.problems(RETURNING.replace(drop, ""), "name: works-factory-line\nnodes: []\n")
                self.assertTrue(any(drop.split(":")[0] in line for line in got), got)

    def test_returning_node_without_output_format_is_red(self):
        block = (
            "name: works-factory-judge\nreturns: verdict\noutcome_field: ready\nnodes:\n"
            "  - id: verdict\n    script: stub\n    timeout: 1728000000\n"
        )
        got = self.problems(block, "name: works-factory-line\nnodes: []\n")
        self.assertTrue(any("output_format" in line for line in got), got)

    def test_outcome_field_not_required_is_red(self):
        block = RETURNING.replace("required: [ready, units]", "required: [units]")
        line = (
            "name: works-factory-line\nnodes:\n  - id: judge\n    include: works-factory-judge\n"
            "    when: \"$judge.output.ready == true\"\n  - id: x\n    script: x\n    timeout: 1728000000\n"
            "    with:\n      units: $judge.output.units\n"
        )
        got = self.problems(block, line)
        self.assertEqual(len(got), 1, got)
        self.assertIn("required", got[0])

    def test_the_line_itself_is_not_a_block(self):
        line = "name: works-factory-line\nreturns: result\nnodes: []\n"
        with tree({LINE: line}) as root:
            self.assertEqual(scan.problems("E5", root), [])


if __name__ == "__main__":
    unittest.main()

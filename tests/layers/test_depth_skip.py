"""深さで飛ばすノードの表と `when` の句の一致（workflows/AGENTS.md の E20 の機械の行）。今の木は緑、小さな木で 1 本 1 違反の赤を作る。"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
LINE = "workflows/line/works-factory-line.yaml"
BLOCK = "workflows/plan-review/works-factory-plan-review.yaml"
CLAUSE = "$open.output.depth_skip != true"


def line(passed='"$due.output.skip"', tail="") -> str:
    return ("name: works-factory-line\nnodes:\n"
            f"  - id: pr\n    include: works-factory-plan-review\n    with: {{depth_skip: {passed}}}\n"
            "  - id: design-only\n    include: works-factory-plan-review\n    with: {}\n"
            f"  - id: tg\n    script: x\n{tail}")


def block(clause=CLAUSE) -> str:
    when = f'    when: "$open.output.ok == true && {clause}"\n' if clause else ""
    return ("name: works-factory-plan-review\nnodes:\n  - id: open\n    script: o\n"
            f"  - id: loop\n{when}    loop_group:\n      nodes:\n        - id: inner\n          script: i\n")


def design(node="pr__loop", depth="軽量", why="目的: 叩く。代わり: `tg`。材料: 数") -> str:
    return f"# 設計\n\n{scan.DEPTH_HEAD}\n\n| ノード | 飛ばしてよい深さ | 理由 |\n| --- | --- | --- |\n| `{node}` | {depth} | {why} |\n\n## 次\n"


class DepthSkipTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E20", ROOT), [])

    def problems(self, line_text=None, block_text=None, design_text=None):
        with tree({LINE: line_text or line(), BLOCK: block_text or block(), scan.DEPTH_TABLE: design_text or design()}) as root:
            return scan.problems("E20", root)

    def red(self, want: str, **kw):
        got = self.problems(**kw)
        self.assertEqual(len(got), 1, got)
        self.assertIn(want, got[0])

    def test_small_tree_clean(self):
        self.assertEqual(self.problems(), [])

    def test_clause_on_a_node_outside_the_table_is_red(self):
        self.red(f"{LINE}:9: tg の depth_skip の句が", line_text=line(tail=f'    when: "{CLAUSE}"\n'))

    def test_row_without_a_clause_is_red(self):
        self.red("表の行 pr__loop に当たる depth_skip の句がグラフに無い", block_text=block(clause=""))

    def test_clause_other_than_not_true_is_red(self):
        self.red("の形でない", block_text=block(clause="$open.output.depth_skip == true"))

    def test_standard_depth_is_red(self):
        self.red("飛ばしてよい深さが 軽量 でない", design_text=design(depth="標準"))

    def test_reason_without_substitute_is_red(self):
        self.red("「代わり:」と「材料:」が無い", design_text=design(why="目的: 叩く。`tg` が見る。材料: 数"))

    def test_named_substitute_missing_from_the_graph_is_red(self):
        self.red("名指すノード no-such がグラフに無い", design_text=design(why="代わり: `no-such`。材料: 数"))

    def test_include_that_does_not_pass_the_input_is_red(self):
        got = self.problems(line_text=line(passed="false"))
        self.assertTrue(any("depth_skip を渡さない" in g for g in got), got)


if __name__ == "__main__":
    unittest.main()

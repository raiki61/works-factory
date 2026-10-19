"""深さの段の表と line の段の表 TIERS（scan.tiers()。line の src/tiers.py）の一致、深さを読む when の句の無さ（workflows/AGENTS.md の E20 の機械の行）。今の木は緑、小さな木で 1 本 1 違反の赤を作る。"""
import pathlib
import unittest

from lib import headdepth
from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
LINE = "workflows/line/works-factory-line.yaml"
BLOCK = "workflows/plan-review/works-factory-plan-review.yaml"
CLAUSE = "$open.output.head_depth != '軽量'"


def line(tail="") -> str:
    return ("name: works-factory-line\nnodes:\n"
            "  - id: pr\n    include: works-factory-plan-review\n    with: {head_depth: x}\n"
            "  - id: design-only\n    include: works-factory-plan-review\n    with: {}\n"
            f"  - id: tg\n    script: x\n{tail}")


def block(clause="") -> str:
    when = f'    when: "$open.output.ok == true && {clause}"\n' if clause else ""
    return ("name: works-factory-plan-review\nnodes:\n  - id: open\n    script: o\n"
            f"  - id: loop\n{when}    loop_group:\n      nodes:\n        - id: inner\n          script: i\n")


def cell(names) -> str:
    return "・".join(f"`{n}`" for n in names) or scan.DEPTH_NONE


def design(heavy=None) -> str:
    rows = []
    for tier, spec in scan.tiers().items():
        adds = heavy if heavy is not None and tier == headdepth.HEAVY else spec["adds"]
        rows.append(f"| {tier} | {cell(spec['omits'])} | {cell(adds)} | 理由 |")
    return "\n".join(["# 設計", "", scan.DEPTH_HEAD, "", "| 段 | 省く物 | 足す物 | 理由 |", "| --- | --- | --- | --- |", *rows, "", "## 次", ""])


class DepthSkipTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E20", ROOT), [])

    def test_design_rows_are_the_tier_table(self):
        rows, broken = scan._tier_rows(ROOT)
        self.assertEqual(broken, [])
        self.assertEqual({tier: (omits, adds) for _, tier, omits, adds in rows},
                         {tier: (tuple(spec["omits"]), tuple(spec["adds"])) for tier, spec in scan.tiers().items()})
        self.assertEqual(scan.problems("E20", ROOT), [])
        text = design().replace(f"| {headdepth.STANDARD} |", "| 標準x |", 1)
        with tree({LINE: line(), BLOCK: block(), scan.DEPTH_TABLE: text}) as root:
            got = scan.problems("E20", root)
        self.assertTrue(any(f"段 {headdepth.STANDARD} の行が無い" in g for g in got), got)
        self.assertTrue(any("標準x が line の TIERS に無い" in g for g in got), got)

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
        self.red("ノード tg の when の句 `$judge.output.depth == '軽量'`", line_text=line(tail="    when: \"$judge.output.depth == '軽量'\"\n"))

    def test_depth_clause_inside_a_block_loop_is_red(self):
        self.red("ノード pr__loop", block_text=block(clause=CLAUSE))

    def test_heavy_adds_drifting_from_tiers_is_red(self):
        self.red(f"段 {headdepth.HEAVY} の省く物・足す物が line の TIERS と違う", design_text=design(heavy=("judge_verify",)))


if __name__ == "__main__":
    unittest.main()

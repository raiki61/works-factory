"""返す節は、上の階層のどの節も直にか間を通して待つ（pack の全部の graph と block）。

返す節（YAML の returns:）は block の出口で、上の階層の節の結末を集めて返す。どれかの節を待たない返す節は、その節が走り終わる前に返り
得る（trigger_rule: all_done の返す節も、待たない節の結末は知らない）。形 theme の輪を足した時、事前審査の出口が輪を待つ照らしを場面ごとの
試験で書いていた（tests/blocks/plan_review/test_plan_review.py の旧 test_theme_loop_is_waited_for）。輪や節を足すたびに場面の試験を
継ぎ足さず、ここで全部の workflow に同じ yes/no を当てる（持ち主の決め mechanism-over-tests）。

外し（返りを持たない柵だけ）: 上の階層の節のうち、待たれなくてよいのは、run を止める柵（cancel: の節。例 line の testcmd-stop）と、
落ちを出口に見せる柵（output_format を持たない bash の節。例 fix の nodes-ok）だけ。どちらも返りを持たず、どの節もその出力を読まない。
"""
import unittest

import yaml

from tests.archon import WORKFLOWS

PREFIX = "works-factory-"


def _workflows():
    for path in sorted(WORKFLOWS.glob(f"*/{PREFIX}*.yaml")):
        if path.stem == f"{PREFIX}{path.parent.name}":
            yield path.parent.name, yaml.safe_load(path.read_text(encoding="utf-8"))


def fence(node: dict) -> bool:
    """返りを持たない柵（cancel: の節か、output_format を持たない bash の節）"""
    return "cancel" in node or ("bash" in node and "output_format" not in node)


def unwaited(doc: dict) -> list:
    """返す節が直にも間を通しても待たない、上の階層の節の id（柵を除く）"""
    nodes = {n["id"]: n for n in doc.get("nodes") or []}
    ret = doc.get("returns")
    if ret not in nodes:
        return []
    seen, stack = set(), [ret]
    while stack:
        for dep in nodes[stack.pop()].get("depends_on") or []:
            if dep not in seen:
                seen.add(dep)
                stack.append(dep)
    return [nid for nid, node in nodes.items() if nid != ret and nid not in seen and not fence(node)]


class ReturnsWaitTest(unittest.TestCase):
    def test_returns_waits_for_every_top_node(self):
        for name, doc in _workflows():
            with self.subTest(name):
                self.assertEqual(unwaited(doc), [], f"{name} の返す節 {doc.get('returns')} が待たない節")

    def test_the_check_bites(self):
        """待たない節を 1 つ足すと照らしが拾う（柵は拾わない）"""
        doc = {"returns": "finish", "nodes": [{"id": "a"}, {"id": "loop", "loop_group": {}}, {"id": "stop", "cancel": "x"},
                                               {"id": "fence", "bash": "true"}, {"id": "finish", "depends_on": ["a"]}]}
        self.assertEqual(unwaited(doc), ["loop"])


if __name__ == "__main__":
    unittest.main()

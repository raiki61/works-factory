"""pack（tests/archon.py の WORKFLOWS）の会話を続ける輪（loop_group の fresh_context: false）で、役の節の層とその前に 2 つ以上の節の層が無いかの yes/no。

Archon は 2 つ以上の節が並んだ層で会話を切るので、そこを越えた役は宣言に反して新しい会話で起きる。判定は workflows/ の検査
（tests/workflows/test_loop_sessions.py の parallel_before_role）をそのまま使う。
"""
import unittest

import yaml

from tests.archon import WORKFLOWS
from tests.bin.stepnames import walk
from tests.workflows.test_loop_sessions import parallel_before_role

PACK = WORKFLOWS


def loops():
    for path in sorted(PACK.glob("*/*.yaml")):
        for n in walk(yaml.safe_load(path.read_text(encoding="utf-8")).get("nodes") or []):
            if "loop_group" in n:
                yield path.parent.name, n


class BlockLoopSessionsTest(unittest.TestCase):
    def test_blocks_have_loops(self):
        self.assertTrue(any(True for _ in loops()), "blocks/ に loop_group が 1 つも見えない（探し方が壊れた）")

    def test_continued_loops_have_no_parallel_layer_before_a_role(self):
        for block, n in loops():
            if n["loop_group"].get("fresh_context") is not False:
                continue
            with self.subTest(block=block, loop=n["id"]):
                self.assertEqual(parallel_before_role(n), [],
                                 f"{block} の {n['id']}: 役の前に並んだ層が在り、会話を続ける宣言に反して役が新しい会話で起きる")

    def test_guard_catches_a_parallel_layer(self):
        group = {"id": "x", "loop_group": {"fresh_context": False, "nodes": [
            {"id": "a-prep", "script": "x"}, {"id": "a-other", "script": "y"},
            {"id": "a", "prompt": "$a-prep.output.prompt", "depends_on": ["a-prep", "a-other"]},
            {"id": "a-accept", "script": "z", "depends_on": ["a"]}]}}
        self.assertEqual(parallel_before_role(group), ["a"])


if __name__ == "__main__":
    unittest.main()

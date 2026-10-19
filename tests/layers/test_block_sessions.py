"""blocks/ の会話を続ける輪（fresh_context: false）で、会話を続ける役（context: fresh でない AI の node）の層とその前に、並んだ層
（2 つ以上の node の層）が無い。Archon は並んだ層で会話を切るので、在ると役は宣言に反して新しい会話で起きる。規則と層の数え方は
tests/workflows/test_loop_sessions.py の parallel_before_role をそのまま使う（workflows/ と同じ規則を blocks/ に当てる）"""
import pathlib
import unittest

import yaml

from tests.bin.stepnames import walk
from tests.workflows.test_loop_sessions import parallel_before_role

ROOT = pathlib.Path(__file__).resolve().parents[2]


class BlockSessionsTest(unittest.TestCase):
    def test_continuing_loops_have_no_parallel_layer_before_the_role(self):
        for path in sorted((ROOT / "blocks").glob("*/*.yaml")):
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(doc, dict) or "nodes" not in doc:
                continue
            for n in walk(doc["nodes"]):
                if "loop_group" not in n or n["loop_group"].get("fresh_context") is not False:
                    continue
                with self.subTest(block=path.parent.name, loop=n["id"]):
                    self.assertEqual(parallel_before_role(n), [],
                                     f"{path.parent.name} の {n['id']}: 役の前に並んだ層が在り、会話を続ける宣言に反して役が新しい会話で起きる")


if __name__ == "__main__":
    unittest.main()

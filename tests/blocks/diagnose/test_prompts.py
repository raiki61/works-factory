"""判定の指示 md（prompts/diagnose.md）の試験（docs/design/diagnose.md の 9.2）。md が機械の値で組めることと、人に回す問いの推しの印が
機械の拾う字のままであること（承認ノードの推しに効く）だけを見る。印に値が無い・値に印が無いことは workflows/.shared/prompt.py の
emit が全体に照らす。英語の md と古い指示の照らしは、設計書の 9.4 の一覧で審査役が 1 件ずつ行う。"""
import json
import unittest

from tests.blocks import kit
from tests.blocks.diagnose import support
from tests.blocks.diagnose.test_inputs import PORTS

BLOCK = kit.BLOCKS / "diagnose"
PROMPTS = BLOCK / "prompts"


class RenderCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "diagnose")
        support.seeded(self.run)
        self.mod = support.modules()
        import importlib
        self.prompt = importlib.import_module("prompt")

    def test_the_values_the_machine_gives_appear_in_the_prompt(self):
        self.run.script("intake", **{**PORTS, "row_asks": json.dumps([{"item": 1, "unknown": "原因", "cause_quote": "落ちる"}])})
        values, when = self.mod["inputs"].diagnose_values(self.run.artifacts)
        text = self.prompt._compose(BLOCK, "diagnose", values, when)["prompt"]
        self.assertIn(values["inputs_file"], text)
        self.assertIn(values["diff_file"], text)
        self.assertIn("- line 1 (原因)", text)
        self.assertIn("- Policy document: none", text)
        self.assertIn("Recorded policy: none", text)
        self.assertNotIn("Why your previous answer was rejected", text)


class MarkCase(unittest.TestCase):
    def test_fork_recommendation_mark_is_the_one_the_machine_reads(self):
        """人に回す岐路の推しの印は lib/gatemarks.py の PUSH_IN が拾う字のまま（字が崩れると承認ノードの項目が推しを持たない）"""
        support.modules()
        import gatemarks
        raw = (PROMPTS / "diagnose.md").read_text(encoding="utf-8")
        self.assertEqual(gatemarks.PUSH_IN.findall('"推し: <option>——<reason>"'), ["<option>——<reason>\""])
        self.assertIn('"推し: <option>——<reason>"', raw, "推しの印は lib/gatemarks.py の PUSH_IN が拾う字のまま")
        self.assertIn("the mark `推し:` as they are", raw)


if __name__ == "__main__":
    unittest.main()

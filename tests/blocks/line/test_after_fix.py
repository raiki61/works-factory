"""案の直しを差し込むか（blocks/line/scripts/after_fix.py。docs/design/line.md の 4.2）"""
import json
import unittest

from tests.blocks import kit

BLOCK = "line"
INPUTS = {"rounds": "null", "plan": json.dumps({"path": "p.json"}), "fix_plan": json.dumps({"path": "fp.json"}),
          "ripple": "null", "reply": json.dumps({"path": "reply.json"}), "handoffs": json.dumps([{"round": 1, "handoff": None}]), "round": "2"}


class AfterFixCase(unittest.TestCase):
    def test_no_items_no_replan(self):
        got = kit.Run(self, BLOCK).script("after_fix", replan_items="[]", **INPUTS)
        self.assertEqual(got, {"replan": False, "prior": None, "stop_reason": ""})

    def test_items_write_the_prior_of_the_approved_round(self):
        run = kit.Run(self, BLOCK)
        got = run.script("after_fix", replan_items='["1"]', **INPUTS)
        self.assertTrue(got["replan"])
        doc = json.loads((run.artifacts / got["prior"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(doc, {"round": 2, "reply": {"path": "reply.json"}, "fields": {"path": "p.json"}, "fix_plan": {"path": "fp.json"},
                               "ripple": None, "review": None, "record": None, "handoffs": [{"round": 1, "handoff": None}]})

    def test_unreadable_items_stop(self):
        got = kit.Run(self, BLOCK).script("after_fix", replan_items='{"x": 1}', **INPUTS)
        self.assertEqual((got["replan"], got["stop_reason"]), (False, "works:line-script"))


if __name__ == "__main__":
    unittest.main()

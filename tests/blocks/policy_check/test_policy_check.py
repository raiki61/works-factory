"""方針の文だけを入れる入口（blocks/policy-check。docs/design/world.md の 9 節）: policy-in の依頼の行と解き方の組み方と、result の
まとめ（定石と違う行を先頭に）を、script を子のプロセスで回して確かめる"""
import json
import unittest

from tests.blocks import kit

POLICY = "Retry uploads:\n- three times\n* with a fixed one second wait\n1. then give up"


class PolicyInCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "policy-check")

    def test_problem_or_policy_becomes_the_request(self):
        got = self.run.script("policy_in", policy=POLICY, problem="", purpose="p", web="off", lang="")
        self.assertEqual(got["means"], ["three times", "with a fixed one second wait", "then give up"])
        self.assertEqual((got["purpose"], got["web"]), ("p", "off"))
        request = json.loads((self.run.artifacts / got["request"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(request, [{"where": "方針", "text": POLICY}])
        got = self.run.script("policy_in", policy="Just retry.", problem="Uploads fail on a flaky link.", purpose="", web="on", lang="")
        self.assertEqual(got["means"], ["Just retry."], "箇条が無ければ全体を 1 つ")
        request = json.loads((self.run.artifacts / got["request"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(request, [{"where": "依頼", "text": "Uploads fail on a flaky link."}])

    def test_request_reaches_the_world_intake(self):
        """policy-in の pointer を world の入口が port のまま読める（同じ run の pointer）"""
        got = self.run.script("policy_in", policy=POLICY, problem="", purpose="", web="off", lang="")
        intake = self.run.other("world").script("intake", "world__intake", request=json.dumps(got["request"]), purpose="", means=json.dumps(got["means"]),
                              web="off", lang="")
        self.assertEqual(intake, {"due": True, "findings": 1, "reason": ""})
        self.assertTrue((self.run.artifacts / "world" / "intake.json").is_file())


class ResultCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "policy-check")

    def test_differs_rows_come_first(self):
        row = {"finding": 1, "where": "方針", "class_id": "w-1", "problem": "p", "activity": "a", "practice": "backoff",
               "sources": [], "applies": "x", "not_applies": "", "basis": "knowledge",
               "versus": {"proposed": "fixed wait", "verdict": "differs", "challenge": "The request waits a fixed time; use backoff."}}
        (self.run.artifacts / "world").mkdir()
        (self.run.artifacts / "world" / "world.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
        world = {"ok": True, "status": "ok", "reason": "", "rows": json.loads(self.run.pointer("world/world.jsonl")), "classes": 1,
                 "dropped": 0, "report": ["- 類 w-1（依頼の行 1）: backoff"]}
        got = self.run.script("result", "result", world=json.dumps(world))
        self.assertEqual(got["ok"], True)
        self.assertEqual(got["report"], ["- 定石と違う（依頼の行 1）: The request waits a fixed time; use backoff.",
                                         "- 類 w-1（依頼の行 1）: backoff"])
        self.assertEqual(got["world"], world)
        self.assertEqual(got["holes"], [])

    def test_skipped_world_is_reported(self):
        got = self.run.script("result", "result", world="null")
        self.assertEqual((got["ok"], got["world"]), (False, None))
        self.assertIn("走らなかった", got["report"][0])


if __name__ == "__main__":
    unittest.main()

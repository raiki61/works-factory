"""方針の文だけを入れる入口（workflows/policy-check。docs/design/world.md の 9 節・docs/design/plan-review.md の 1.6）: policy-in の依頼の行と
解き方の組み方と、事前審査の block（形 text）へ運ぶ方針の文と、result のまとめ（事前審査の穴と定石と違う行を先頭に・ok は両方の ok）を、
script を子のプロセスで回して確かめる"""
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
        self.assertEqual(got["policy"], POLICY, "事前審査へ運ぶ方針の文は字のまま")
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

    def test_policy_reaches_the_review_intake_as_text(self):
        """policy-in の方針の文と目的を、事前審査の block の入口が方針の文だけの形（text）で読む"""
        got = self.run.script("policy_in", policy=POLICY, problem="", purpose="p", web="off", lang="")
        intake = self.run.other("plan-review").script("intake", "review-run__intake", proposal=got["policy"], purpose=got["purpose"],
                                                      world_rows="null", lang=got["lang"])
        self.assertEqual(intake, {"due": True, "form": "text", "tree": False, "k": 0, "reason": ""})
        doc = json.loads((self.run.artifacts / "review-run" / "intake.json").read_text(encoding="utf-8"))
        self.assertEqual((doc["proposal_text"], doc["purpose"]), (POLICY, "p"))


class ResultCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "policy-check")

    def review(self, faces, ok=True) -> dict:
        """事前審査の block（形 text）の返り: holes は place の review.json の pointer"""
        (self.run.artifacts / "review-run").mkdir(exist_ok=True)
        (self.run.artifacts / "review-run" / "review.json").write_text(json.dumps({"faces": faces, "shrink": [], "reason": "r"}),
                                                                     encoding="utf-8")
        head = "事前審査（方針の文）: 穴 1 件（block 1）・別案 0 件"
        return {"ok": ok, "status": "ok" if ok else "failed", "form": "text", "round": 0, "reason": "",
                "holes": json.loads(self.run.pointer("review-run/review.json")), "blocks": [f["key"] for f in faces], "pass": None,
                "asks": [], "deviations": [], "replan": [], "gave_up": None,
                "report": [head, *(f"- [{f['kind']}] {f['key']}: {f['why']}" for f in faces)]}

    def test_differs_rows_come_first(self):
        row = {"finding": 1, "where": "方針", "class_id": "w-1", "problem": "p", "activity": "a", "practice": "backoff",
               "sources": [], "applies": "x", "not_applies": "", "basis": "knowledge",
               "versus": {"proposed": "fixed wait", "verdict": "differs", "challenge": "The request waits a fixed time; use backoff."}}
        (self.run.artifacts / "world").mkdir()
        (self.run.artifacts / "world" / "world.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
        world = {"ok": True, "status": "ok", "reason": "", "rows": json.loads(self.run.pointer("world/world.jsonl")), "classes": 1,
                 "dropped": 0, "report": ["- 類 w-1（依頼の行 1）: backoff"]}
        face = {"key": "fixed-wait-overloads-server", "kind": "regression", "where": "the policy", "why": "w" * 20,
                "severity": "block", "reach": "breaks_fix"}
        got = self.run.script("result", "result", world=json.dumps(world), review=json.dumps(self.review([face])))
        self.assertEqual(got["ok"], True)
        self.assertEqual(got["report"], ["事前審査（方針の文）: 穴 1 件（block 1）・別案 0 件",
                                         f"- [regression] fixed-wait-overloads-server: {'w' * 20}",
                                         "- 定石と違う（依頼の行 1）: The request waits a fixed time; use backoff.",
                                         "- 類 w-1（依頼の行 1）: backoff"], "事前審査の穴が頭、定石と違う行がその次")
        self.assertEqual(got["world"], world)
        self.assertEqual(got["holes"], [face], "holes は事前審査が受けた返答の faces")
        got = self.run.script("result", "result", world=json.dumps(world), review=json.dumps(self.review([face], ok=False)))
        self.assertEqual(got["ok"], False, "ok は world と review の両方の ok")
        got = self.run.script("result", "result", world=json.dumps(world), review="null")
        self.assertEqual((got["ok"], got["holes"], got["report"][0]), (False, [], "- 事前審査の段が走らなかった"))

    def test_skipped_world_is_reported(self):
        got = self.run.script("result", "result", world="null", review="null")
        self.assertEqual((got["ok"], got["world"]), (False, None))
        self.assertEqual(got["report"], ["- 事前審査の段が走らなかった", "- 世界の解の段が走らなかった"])

    def test_skipped_world_with_review_keeps_the_holes(self):
        """足す: world が回らず review が受けた時も、ok は偽で、holes と事前審査の行は残り、world の走らなかった行が後ろに付く"""
        face = {"key": "fixed-wait-overloads-server", "kind": "regression", "where": "the policy", "why": "w" * 20,
                "severity": "block", "reach": "breaks_fix"}
        review = self.review([face])
        got = self.run.script("result", "result", world="null", review=json.dumps(review))
        self.assertEqual((got["ok"], got["world"], got["holes"]), (False, None, [face]))
        self.assertEqual(got["report"], [*review["report"], "- 世界の解の段が走らなかった"])

    def test_review_report_not_a_list_adds_no_lines(self):
        """足す: review の report が配列でなければ、事前審査の行を足さない（字を 1 字ずつの行にしない）"""
        world = {"ok": True, "status": "ok", "reason": "", "rows": None, "classes": 0, "dropped": 0, "report": ["- 世界の行"]}
        got = self.run.script("result", "result", world=json.dumps(world), review=json.dumps({**self.review([]), "report": "一行"}))
        self.assertEqual(got["report"], ["- 世界の行"])


if __name__ == "__main__":
    unittest.main()

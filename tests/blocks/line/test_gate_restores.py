"""今の line の「事前審査が人に聞く」（lib/boardview.py の ask_human）から新しい形が取りこぼした開き方を戻したことの試験。

1. 計画は通ったのに事前審査の受け付けが諦めた（plan-review の status が gave_up）周: 修正前の承認ノードが諦めた訳の行
   （gatemarks.GIVEN_UP_KIND）で開き、無人の run は needs-human で止まる。報告は往復が進まない止めと人待ちを出す
2. 事前審査が落ちた（status が failed）周: 1 と同じく開く（黙って修正を飛ばさない。閉じた側に倒す）
3. 方針の文書が始めの記録の固めた版から変わった run: 案の直しの承認ノードが方針の変化の行を足して開く。人が前に continue で通した
   同じ文の行は聞き直さない（ほかの行と同じ決まり）
"""
import json
import unittest

from tests.blocks import kit
from tests.blocks.line.test_gates import rounds

BLOCK = "line"


class ReviewFellCase(unittest.TestCase):
    def setUp(self):
        self.g = kit.load(BLOCK, "gates")
        self.gm = __import__("gatemarks")

    def fell(self, status, reason="受け付けが 3 回拒んだ"):
        return rounds(ok=False, done=True, review_status=status, review_reason=reason)

    def test_given_up_review_opens_with_its_reason(self):
        out = self.g.before_fix(self.fell("gave_up"), unattended_run=False, design=False)
        self.assertEqual((out["open"], out["go"]), (True, True))
        self.assertEqual(out["items"], [(self.gm.GIVEN_UP_KIND, self.g.GIVEN_UP_FACES + "受け付けが 3 回拒んだ")])

    def test_failed_review_opens_too(self):
        out = self.g.before_fix(self.fell("failed", "plan-review の intake が落ちた"), unattended_run=False, design=False)
        self.assertTrue(out["open"])
        self.assertEqual(out["items"][0], (self.gm.GIVEN_UP_KIND, self.g.REVIEW_FAILED + "plan-review の intake が落ちた"))

    def test_unattended_run_stops_as_needs_human(self):
        for status in ("gave_up", "failed"):
            with self.subTest(status=status):
                out = self.g.before_fix(self.fell(status), unattended_run=True, design=False)
                self.assertEqual((out["open"], out["go"]), (False, False))
                self.assertEqual(out["stop_reason"], __import__("stopby").NEEDS_HUMAN)

    def test_continued_row_goes_to_the_fix_on_resume(self):
        row = self.g.GIVEN_UP_FACES + "受け付けが 3 回拒んだ"
        out = self.g.before_fix(self.fell("gave_up"), unattended_run=False, design=False,
                                answered=[{"decision": "continue", "text": "", "asked": [row]}])
        self.assertEqual((out["open"], out["go"]), (False, True))

    def test_review_that_passed_or_a_plan_that_failed_does_not_open(self):
        """事前審査が通った周と、計画そのものが通らず事前審査が飛んだ周は、この行を作らない"""
        self.assertEqual(self.g.review_fell_row(rounds()), "")
        self.assertEqual(self.g.review_fell_row(rounds(ok=False, status="gave_up", review_status="")), "")
        out = self.g.before_fix(rounds(ok=False, status="failed", review_status=""), unattended_run=False, design=False)
        self.assertEqual((out["open"], out["go"]), (False, False))


class PlanOutStatusCase(unittest.TestCase):
    """plan-out が事前審査の状態と訳を返す"""

    def setUp(self):
        self.run = kit.Run(self, BLOCK)

    def plan(self):
        ptr = {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "plan/plan-fields.json"}
        return {"ok": True, "status": "ok", "reason": "", "round": 1, "owed": ["u1"], "plan": ptr, "fix_plan": None, "reply": None,
                "handoff": None, "ripple": None, "rejects": [], "gave_up": None}

    def test_given_up_review_is_returned_with_its_reason(self):
        review = {"ok": False, "status": "gave_up", "round": 1, "holes": None, "blocks": [], "pass": None, "asks": [], "deviations": [],
                  "reason": "受け付けが 3 回拒んだ", "gave_up": None}
        out = self.run.script("plan_out", plan=json.dumps(self.plan()), review=json.dumps(review), prior="", unattended="false")
        self.assertEqual((out["done"], out["ok"], out["review_status"], out["review_reason"]), (True, False, "gave_up", "受け付けが 3 回拒んだ"))
        self.assertEqual(out["stop_reason"], "")


class ReportCase(unittest.TestCase):
    """報告: 修正へ進まなかった run は往復が進まない止め（今の outcome._line_stop が諦めた往復を stalled で読んだ形）と、答えの無い
    修正前の問いの人待ち（今の outcome._waits の ask_human）を出す"""

    def setUp(self):
        self.facts = kit.load(BLOCK, "facts")

    def test_fallen_review_halts_and_waits(self):
        stopby = __import__("stopby")
        returns = {"plan": rounds(ok=False, done=True, review_status="gave_up", review_reason="r"), "fix": None}
        self.assertIn({"at": "plan-review", "word": stopby.PLAN_CONVERGE}, self.facts.halt_rows(returns))
        values = {"ask_before_fix": {"deferred": [], "asked": ["事前審査の受け付けが諦めた: r"]}, "answer_before_fix": {"answer": None}}
        self.assertIn({"at": "plan-review", "word": "ask-human"}, self.facts.wait_rows(values, returns)["others"])

    def test_fix_that_ran_is_not_halted(self):
        returns = {"plan": rounds(ok=False, done=True, review_status="failed", review_reason="r"), "fix": {"ok": True}}
        self.assertEqual(self.facts.halt_rows(returns), [])


class ReplanPolicyCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, BLOCK)

    def put(self, rel: str, doc) -> str:
        path = self.run.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return self.run.pointer(rel)

    def changed_record(self) -> str:
        doc = self.run.repo / "policy.md"
        doc.write_text("新しい方針\n", encoding="utf-8")
        return self.put("r1/start.json", {"policy": {"named": str(doc), "path": str(doc), "sha256": "old", "copy": None}})

    def ask(self, record, before_fix="null"):
        old = self.put("plan-fields.json", {"fields": [{"unit_keys": ["u1"]}]})
        new = self.put("replan/plan-fields.json", {"fields": [{"unit_keys": ["u1"]}]})
        replan = {"ok": True, "status": "ok", "reason": "", "plan": json.loads(new), "fix_plan": None, "ripple": None, "round": 1}
        review = {"ok": True, "status": "ok", "reason": "", "round": 1, "holes": None, "blocks": [],
                  "replan": [{"item": 1, "units": ["u1"], "contract_changed": [], "human": [], "widened": None}]}
        return self.run.script("ask_replan", replan=json.dumps(replan), review=json.dumps(review), old_plan=old, items="[1]",
                               conflicts="null", before_fix=before_fix, record=record,
                               ports=json.dumps({"unattended": False, "policy": ""}))

    def test_changed_policy_opens_the_replan_gate(self):
        out = self.ask(self.changed_record())
        self.assertTrue(out["open"], out)
        [row] = out["asked"]
        self.assertTrue(row.startswith("人の方針の文書 "), row)
        self.assertIn("固定した版から変わった", out["text"])

    def test_unchanged_policy_adds_nothing(self):
        out = self.ask(self.put("r1/start.json", {}))
        self.assertEqual((out["open"], out["go"], out["asked"]), (False, True, []))

    def test_row_continued_before_the_fix_is_not_asked_again(self):
        record = self.changed_record()
        row = self.ask(record)["asked"][0]
        out = self.ask(record, before_fix=json.dumps({"decision": "continue", "text": "", "asked": [row]}))
        self.assertEqual((out["open"], out["go"]), (False, True), out)


if __name__ == "__main__":
    unittest.main()

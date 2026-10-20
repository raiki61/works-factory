"""計画の往復の記録と止め（docs/design/line.md の 3 節。node plan-out と owed。src/rounds.py）。

元は今の tests/workflows/test_line.py の PlanOutCase・PlanOutNothingOwedCase・OwedCase。往復の行・止め時の 5 語・上限 20 と YAML の
max_iterations の突き合わせ・上限で止めた行の capped・止まった案を推しで進める時の保留の穴の足し・2 本の prior の形（plan の
plan-prior の形と、plan-review の PRIOR_SHAPE）を見る。往復の記録の行の決まりそのものは test_converge_line.py。
"""
import json
import pathlib
import unittest

import yaml

from tests.blocks import kit

BLOCK = "line"
rounds = kit.load(BLOCK, "rounds")
files = kit.load(BLOCK, "files")
import converge  # noqa: E402
import judgmark  # noqa: E402

U1, U2 = "u1", "u2"
PRIOR_SHAPE_REQUIRED = ("passes",)                   # plan-review の設計書の 1.5 の PRIOR_SHAPE の required
PLAN_PRIOR_REQUIRED = ("round", "reply", "fields")   # plan の plan-prior.schema.json の required


def face(key, units=(U1,), severity="block"):
    return {"key": key, "kind": "regression", "where": f"{key} の場所", "why": f"{key} が穴である理由", "severity": severity,
            "unit_keys": list(units)}


def line_nodes() -> dict:
    doc = yaml.safe_load((kit.BLOCKS / BLOCK / f"works-factory-{BLOCK}.yaml").read_text(encoding="utf-8"))
    out = {}
    for node in doc["nodes"]:
        out[node["id"]] = node
        for inner in (node.get("loop_group") or {}).get("nodes") or []:
            out[inner["id"]] = inner
    return out


class PlanOutCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, BLOCK)

    def put(self, rel, doc):
        path = self.run.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": rel}

    def plan(self, k, **kw):
        return {"ok": True, "status": "ok", "reason": "", "round": k, "owed": [U1], "plan": self.put(f"plan/r{k}/plan-fields.json", {"fields": []}),
                "fix_plan": self.put(f"plan/r{k}/fix-plan.json", {}), "reply": self.put(f"plan/r{k}/reply.json", {"plan": []}),
                "handoff": self.put(f"plan/r{k}/handoff.json", {}), "ripple": self.put(f"plan/r{k}/ripple.json", {}),
                "rejects": [], "gave_up": None, "mode": "plan", "replan": None, "report": [], **kw}

    def review(self, k, faces, *, plan_rows=None, push=None, resolved=(), **kw):
        got = {"pass": k, "review": {"faces": faces}, "answers": [], "resolved": list(resolved), "files": {},
               "rejects": [], **({"plan": plan_rows} if plan_rows is not None else {}), **({"push": push} if push else {})}
        return {"ok": True, "status": "ok", "round": k, "holes": self.put(f"plan-review/r{k}/review.json", {"faces": faces, "shrink": []}),
                "blocks": [f["key"] for f in faces if f["severity"] == "block"], "pass": self.put(f"plan-review/r{k}/pass.json", got),
                "asks": [], "deviations": [], "reason": "", "form": "plan", "replan": [], "gave_up": None, "reads": None, "report": [],
                **kw}

    def out(self, plan, review, prior="", unattended="false"):
        return self.run.script("plan_out", plan=json.dumps(plan, ensure_ascii=False),
                               review=json.dumps(review, ensure_ascii=False) if review is not None else "null",
                               prior=json.dumps(prior) if isinstance(prior, dict) else prior, unattended=unattended)

    def test_clean_pass_proceeds_and_writes_both_priors(self):
        got = self.out(self.plan(1), self.review(1, []))
        self.assertEqual((got["done"], got["ok"], got["stalled"], got["capped"], got["round"], got["stop_reason"]),
                         (True, True, False, False, 1, ""))
        record = json.loads((self.run.artifacts / got["record"]["path"]).read_text(encoding="utf-8"))
        self.assertTrue(all(k in record for k in PRIOR_SHAPE_REQUIRED))
        self.assertEqual((record["outcome"], len(record["passes"])), (converge.CLEAN, 1))
        self.assertEqual(got["record"]["path"], files.PLAN_CONVERGE)
        prior = json.loads((self.run.artifacts / got["plan_prior"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(got["plan_prior"]["path"], files.PLAN_PRIOR.format(k=1))
        self.assertTrue(all(k in prior for k in PLAN_PRIOR_REQUIRED))
        self.assertEqual(prior["record"], record, "plan の prior.record は plan-converge.json と同じ中身")
        self.assertEqual(prior["review"], got["review"])
        self.assertEqual([h["round"] for h in prior["handoffs"]], [1])

    def test_stop_words_and_done(self):
        """止め時は decide の語: AGAIN は続け、PERSISTED は止まる（stalled）。往復の数・block の数で止めない"""
        first = self.out(self.plan(1), self.review(1, [face("key-a1")]))
        self.assertEqual((first["done"], first["ok"], first["stalled"]), (False, False, False))
        second = self.out(self.plan(2), self.review(2, [face("key-b1")]), prior=first["record"])
        self.assertEqual((second["done"], second["stalled"]), (False, False), "中央の新しい block は続く")
        third = self.out(self.plan(3), self.review(3, [face("key-a1")]), prior=second["record"])
        self.assertEqual((third["done"], third["ok"], third["stalled"]), (True, False, True))
        record = json.loads((self.run.artifacts / third["record"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual((record["outcome"], [p["pass"] for p in record["passes"]]), (converge.PERSISTED, [1, 2, 3]))
        prior = json.loads((self.run.artifacts / third["plan_prior"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual([h["round"] for h in prior["handoffs"]], [1, 2, 3], "全部の周の handoff")

    def test_settled_proceeds(self):
        first = self.out(self.plan(1), self.review(1, [face("key-a1")]))
        edge = {**face("key-e1"), converge.REACH: converge.PERIPHERAL}
        got = self.out(self.plan(2), self.review(2, [edge], resolved=["key-a1"]), prior=first["record"])
        self.assertEqual((got["done"], got["ok"]), (True, True))

    def test_cap_matches_the_loop_and_marks_the_stop(self):
        """上限 LIMIT は YAML の plan-rounds の max_iterations と同じ数。上限の周で AGAIN なら capped で止まる（工場の不具合として人に見せる）"""
        self.assertEqual(line_nodes()["plan-rounds"]["loop_group"]["max_iterations"], rounds.LIMIT)
        got = self.out(self.plan(rounds.LIMIT), self.review(rounds.LIMIT, [face("key-z1")]))
        self.assertEqual((got["done"], got["ok"], got["stalled"], got["capped"]), (True, False, True, True))

    def test_plan_not_ok_ends_without_a_prior(self):
        """plan が ok でない周（nothing_owed・held・gave_up・failed）は事前審査が飛び、抜けて status を運ぶ"""
        for status in ("nothing_owed", "held", "gave_up", "failed"):
            with self.subTest(status=status):
                got = self.out(self.plan(1, ok=False, status=status), None)
                self.assertEqual((got["done"], got["ok"], got["status"], got["plan_prior"]), (True, False, status, None))

    def test_review_not_ok_ends(self):
        got = self.out(self.plan(1), self.review(1, [], ok=False, status="gave_up", gave_up=["諦めた"]))
        self.assertEqual((got["done"], got["ok"], got["review"]), (True, False, None))

    def test_unattended_push_adds_the_held_faces(self):
        """止まった案を無人の run が推しで進める時は、保留の項目の前の往復の block（stuck_faces。印 held）を事前審査の返答に足した
        ファイルを review に返す（今の boardview._take:1065-1068）。人の居る run と推しの無い止まりは今の返答のまま"""
        plan_rows = converge.plan_rows([{"unit_keys": [U1]}, {"unit_keys": [U2]}])
        push = {"answer": "continue", "note": "key-a1 と key-b1（項目 1 と 項目 2）は保留のまま進める", "why": "端の穴だけが残った"}

        def walk(unattended):
            r1 = self.out(self.plan(1), self.review(1, [face("key-a1", (U1,)), face("key-b1", (U2,))], plan_rows=plan_rows))
            r2 = self.out(self.plan(2), self.review(2, [face("key-a1", (U1,))], plan_rows=plan_rows), prior=r1["record"])
            return self.out(self.plan(3), self.review(3, [face("key-b1", (U2,))], plan_rows=plan_rows, push=push), prior=r2["record"],
                            unattended=unattended)
        got = walk("true")
        self.assertTrue(got["stalled"])
        self.assertEqual(got["review"]["path"], files.PLAN_REVIEW.format(k=3))
        written = json.loads((self.run.artifacts / got["review"]["path"]).read_text(encoding="utf-8"))
        held = [f for f in written["faces"] if f.get(converge.HELD_MARK)]
        self.assertEqual([f["key"] for f in held], ["key-a1"])
        self.assertEqual(walk("false")["review"]["path"], "plan-review/r3/review.json")

    def test_broken_input_ends_as_not_planned(self):
        got = self.run.script("plan_out", plan="{壊れた", review="null", prior="", unattended="false")
        self.assertEqual((got["done"], got["ok"], got["stop_reason"]), (True, False, "works:line-script"))


class OwedCase(unittest.TestCase):
    """node owed: 計画の 1 回目の周が修正案の役を起こすか（plan の周を開く口と同じ決め）と記録された方針の行"""

    def setUp(self):
        self.run = kit.Run(self, BLOCK)

    def put(self, rel, doc):
        path = self.run.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return json.dumps({"type": "archon_artifact", "run_id": kit.RUN_ID, "path": rel})

    def owed(self, judgment, *, answer="null", decisions="null", dealt=None):
        return self.run.script("owed", judgment=judgment, answer_ties="null", materials="null", world="null", decisions=decisions,
                               answer=answer, ports=json.dumps(dealt or {"request_answers": [], "takes_push": False, "policy": ""}))

    def test_owed_units_open_the_round(self):
        got = self.owed(self.put("judge/judgment.json", {"units": [{"key": U1, "label": "block"}], "questions": []}))
        self.assertEqual((got["owed"], got["why"], got["stop_reason"]), (True, "", ""))

    def test_no_owed_unit_or_unreadable_judgment_does_not(self):
        got = self.owed(self.put("judge/judgment.json", {"units": [{"key": U1, "label": "nit"}], "questions": []}))
        self.assertEqual((got["owed"], got["why"]), (False, judgmark.NOTHING_OWED))
        got = self.owed("null")
        self.assertFalse(got["owed"])
        self.assertIn("判定が読めない", got["why"])

    def test_unanswered_question_withholds_and_answer_returns(self):
        """答えていない fork の出どころは義務から外れ（行き止まり）、依頼の answers が答えれば義務に戻る"""
        q = {"key": "q1", "kind": "fork", "status": "held", "origin": U1, "reason": "a か b か"}
        judgment = self.put("judge/judgment.json", {"units": [{"key": U1, "label": "block"}], "questions": [q]})
        self.assertFalse(self.owed(judgment)["owed"])
        dealt = {"request_answers": [{"question": "q1", "text": "a"}], "takes_push": False, "policy": ""}
        self.assertTrue(self.owed(judgment, dealt=dealt)["owed"])

    def test_recorded_rows_carry_the_start_answer_and_request_answers(self):
        judgment = self.put("judge/judgment.json", {"units": [{"key": U1, "label": "block"}], "questions": []})
        dealt = {"request_answers": [{"question": "q1", "text": "a"}], "takes_push": False, "policy": ""}
        got = self.owed(judgment, answer=json.dumps({"decision": "continue", "text": "テストは消さない"}), dealt=dealt)
        sources = [r["source"] for r in got["recorded"]]
        self.assertIn("answer", sources)
        self.assertIn("gate", sources)
        self.assertIn("テストは消さない", [r["text"] for r in got["recorded"]])

    def test_broken_input_stops(self):
        got = self.run.script("owed", judgment="null", answer_ties="null", materials="null", world="null", decisions="null",
                              answer="null", ports="{壊れた")
        self.assertEqual((got["owed"], got["stop_reason"]), (False, "works:line-script"))


if __name__ == "__main__":
    unittest.main()

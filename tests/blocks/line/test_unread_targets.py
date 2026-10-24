"""承認ノードの script が、pointer の指す先のファイルが無い・読めない時に落ちず、読めなかった物を名指す行で承認ノードを開くことの試験
（docs/design/line.md の 2 節: 読めない計画・修正の控えは聞く側に倒す）。pointer の形の違い（型・ほかの run の id・run directory の
外）は約束の誤りなので、今どおり落ちて止めの語 works:line-script を返す。

対象: ask_before_fix（判定・答えの結び・素材の状態・構造の目の控え・往復の記録）・ask_replan（案の直しの修正案の欄・承認済みの欄・
申し出と裁定の控え）・replan_answer（案の直しの修正案・事前審査の返答。承認ノードの後なので、2 度目の修正の申し送りに訳を書く）・
ask_final（往復の記録・封じた差分）。
"""
import json
import unittest

from tests.blocks import kit
from tests.blocks.line.test_gates import ask_row, rounds

BLOCK = "line"
LINE_SCRIPT = "works:line-script"


def ptr(rel: str, run_id: str = kit.RUN_ID) -> dict:
    return {"type": "archon_artifact", "run_id": run_id, "path": rel}


class LocatedCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, BLOCK)
        self.g = kit.load(BLOCK, "gates")
        ports = __import__("ports")
        self.opened = lambda raw: ports.file(raw, "json(shared:fix-marks.schema.json)")   # 読み手が宣言の form で照らす読み（形は何でもよい）

    def test_missing_target_is_named_and_empty(self):
        unread = []
        with self.run.env():
            self.assertEqual(self.g.located(ptr("judge/judgment.json"), "判定", unread, self.opened), "")
            self.assertEqual(self.g.located(None, "判定", unread, self.opened), "")
            self.assertEqual(self.g.located("null", "判定", unread, self.opened), "")
        self.assertEqual(unread, ["判定 の judge/judgment.json が無い"])

    def test_present_target_is_its_path(self):
        (self.run.artifacts / "a.json").write_text("{}", encoding="utf-8")
        unread = []
        with self.run.env():
            self.assertTrue(self.g.located(ptr("a.json"), "x", unread, self.opened).endswith("a.json"))
            self.assertEqual(self.g.read_located(json.dumps(ptr("a.json")), "x", unread, self.opened), {})
        self.assertEqual(unread, [])

    def test_unreadable_json_is_named(self):
        (self.run.artifacts / "bad.json").write_text("{", encoding="utf-8")
        unread = []
        with self.run.env():
            self.assertIsNone(self.g.read_located(ptr("bad.json"), "判定", unread, self.opened))
        self.assertTrue(unread and "JSON として読めない" in unread[0], unread)

    def test_off_shape_target_is_named_and_empty(self):
        """形に合わない控えも読めない控え（E23）: 落ちず、形の外れを名指して聞く側に倒す"""
        (self.run.artifacts / "odd.json").write_text('{"premise_drift": "yes"}', encoding="utf-8")
        unread = []
        with self.run.env():
            self.assertEqual(self.g.located(ptr("odd.json"), "修正の印", unread, self.opened), "")
        self.assertTrue(unread and "形に合わない" in unread[0] and "premise_drift" in unread[0], unread)

    def test_malformed_pointers_still_raise(self):
        with self.run.env():
            for bad in (ptr("a.json", run_id="other-run"), ptr("../a.json"), {"type": "file", "path": "a.json"}, 3):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    self.g.located(bad, "判定", [], self.opened)


class AskBeforeFixCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, BLOCK)
        self.g = kit.load(BLOCK, "gates")

    def ask(self, judge, *, unattended=False, structure="null"):
        return self.run.script("ask_before_fix", rounds=json.dumps(rounds()), structure=structure, judge=json.dumps(judge),
                               record="null", ports=json.dumps({"unattended": unattended, "design_talk": False, "policy": ""}))

    def test_missing_judgment_opens_with_its_name(self):
        out = self.ask({"judgment": ptr("judge/judgment.json"), "answer_ties": ptr("judge/ties.json"), "materials": None})
        self.assertEqual((out["open"], out["go"], out["stop_reason"]), (True, True, ""), out)
        self.assertEqual(out["asked"], [f"判定 の judge/judgment.json が無い{self.g.UNREAD_TAIL}",
                                        f"答えの結び の judge/ties.json が無い{self.g.UNREAD_TAIL}"])

    def test_broken_structure_state_opens_and_names_the_file(self):
        """壊れた構造の目の控え（state.json）は、落ちて run を止めず、読めなかった控えとして承認ノードを開き、控えの名を理由に出す。
        無人の run なら、その理由つきで止まる。どちらも設計の問いを黙って消さない"""
        path = self.run.artifacts / "structure" / "state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        judge = {"judgment": None, "answer_ties": None, "materials": None}
        out = self.ask(judge, structure=json.dumps(ptr("structure/state.json")))
        self.assertEqual((out["open"], out["go"], out["stop_reason"]), (True, True, ""), out)
        self.assertIn("state.json", out["asked"][0])
        out = self.ask(judge, unattended=True, structure=json.dumps(ptr("structure/state.json")))
        self.assertEqual((out["open"], out["go"]), (False, False), out)

    def test_fallback_keeps_the_reason(self):
        """script が落ちた時の返りは、例外の訳を reason に載せる（壊れた控えでなく約束の誤りの pointer の例）"""
        out = self.ask({"judgment": None, "answer_ties": None, "materials": None},
                       structure=json.dumps({"type": "archon_artifact", "run_id": "other-run", "path": "structure/state.json"}))
        self.assertEqual(out["stop_reason"], LINE_SCRIPT)
        self.assertIn("other-run", out["reason"])

    def test_missing_structure_opens(self):
        out = self.ask({"judgment": None, "answer_ties": None, "materials": None}, structure=json.dumps(ptr("structure/state.json")))
        self.assertTrue(out["open"], out)
        self.assertIn("構造の目の控え の structure/state.json が無い", out["asked"][0])

    def test_unattended_run_stops_as_needs_human(self):
        out = self.ask({"judgment": ptr("judge/judgment.json"), "answer_ties": None, "materials": None}, unattended=True)
        self.assertEqual((out["open"], out["go"], out["stop_reason"]), (False, False, __import__("stopby").NEEDS_HUMAN), out)

    def test_another_runs_pointer_still_falls(self):
        out = self.ask({"judgment": ptr("judge/judgment.json", run_id="other-run"), "answer_ties": None, "materials": None})
        self.assertEqual((out["open"], out["go"], out["stop_reason"]), (False, False, LINE_SCRIPT), out)


class ReplanCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, BLOCK)
        self.g = kit.load(BLOCK, "gates")

    def put(self, rel: str, doc) -> dict:
        path = self.run.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return ptr(rel)

    def test_missing_replanned_fields_open_the_replan_gate(self):
        old = self.put("plan-fields.json", {"round": 1, "fields": [{"unit_keys": ["u1"]}]})
        replan = {"ok": True, "status": "ok", "reason": "", "plan": ptr("replan/plan-fields.json"), "fix_plan": None, "ripple": None,
                  "round": 1}
        review = {"ok": True, "status": "ok", "reason": "", "round": 1, "holes": None, "blocks": [],
                  "replan": [{"item": 1, "units": ["u1"], "contract_changed": [], "human": [], "widened": None}]}
        out = self.run.script("ask_replan", replan=json.dumps(replan), review=json.dumps(review), old_plan=json.dumps(old), items="[1]",
                              conflicts=json.dumps(ptr("fix/conflicts.json")), before_fix="null", record="null",
                              ports=json.dumps({"unattended": False}))
        self.assertEqual((out["open"], out["stop_reason"]), (True, ""), out)
        self.assertIn(f"案の直しの修正案の欄 の replan/plan-fields.json が無い{self.g.UNREAD_TAIL}", out["asked"])
        self.assertIn(f"修正の申し出と裁定の控え の fix/conflicts.json が無い{self.g.UNREAD_TAIL}", out["asked"])

    def test_replan_answer_names_the_missing_fix_plan_in_the_notes(self):
        holes = self.put("replan-review/holes.json", {"faces": [], "shrink": []})
        replan = {"ok": True, "plan": ptr("replan/plan-fields.json"), "fix_plan": ptr("replan/fix-plan.json"), "ripple": None, "owed": ["u1"]}
        review = {"ok": True, "status": "ok", "holes": holes}
        out = self.run.script("replan_answer", gate=json.dumps({"decision": "continue", "text": ""}), go="true", stop_reason="",
                              place="gate-replan", before_fix="null", asked="[]", pushed="null", replan=json.dumps(replan),
                              review=json.dumps(review), items="[1]", first_ripple="null", units_tier="[]")
        self.assertEqual((out["go"], out["stop_reason"]), (True, ""), out)
        self.assertIn("案の直しの修正案 の replan/fix-plan.json が無い", out["fix_notes"])


class AskFinalCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, BLOCK)
        self.final = kit.load(BLOCK, "final")

    def ask(self, *, record=None, seal=None, unattended=False, judged=None, final_gate="protected_only"):
        fix_in = {"answer": None, "passes": [], "structure": None, "record": record, "judgment": None, "units": []}
        fixed = {"no_fix": False, "conflicts": [], "handoffs": [], "mismatched": [], "objection": "", "units": [], "groups": [],
                 "stages": [], "replan_items": [], "refixed": False, "skip_why": ""}
        tests = {"ok": True, "green": True, "red_cause": "", "ran_steps": None, "by": "test_cmd", "suites_line": "1 本", "log": "l",
                 "baseline_line": "b", "reason": "", "fingerprint": {"head": "h", "diff_hash": "d"}}
        return self.run.script("ask_final", fix_in=json.dumps(fix_in), fixed=json.dumps(fixed), judged=json.dumps(judged) if judged else "null", tests=json.dumps(tests),
                               eyes="null", seal=json.dumps(seal) if seal else "null", spec_check="null", parallel_after="null",
                               replan_review="null", replan_answer="null", widened="null", start_answer="null", record="null",
                               final_gate=final_gate, ports=json.dumps({"unattended": unattended}))

    def test_missing_rounds_record_opens_in_every_mode(self):
        out = self.ask(record=ptr("plan-converge.json"))
        self.assertEqual((out["open"], out["stop_reason"]), (True, ""), out)
        self.assertTrue(any(r.startswith(self.final.MISSING_HEAD) and "plan-converge.json" in r for r in out["reasons"]), out["reasons"])

    def test_missing_sealed_diff_opens(self):
        seal = {"mode": "seal", "ok": True, "hash": "abc", "diff": ptr("merge-seal/sealed.diff"), "protected_hits": [],
                "protected_count": 0, "reason": "", "deliver": None, "report": []}
        out = self.ask(seal=seal)
        self.assertTrue(out["open"], out)
        self.assertTrue(any("封じた差分 の merge-seal/sealed.diff が無い" in r for r in out["reasons"]), out["reasons"])

    def test_lost_tie_note_is_shown_but_does_not_force_the_gate(self):
        """読めた控えについての注記（結びの宛て先が今の問いにも単位にも無く、字の一致で当てた）は、読めなかった控えではない:
        承認ノードの材料には出すが、必ず開ける理由に数えない（再審で問いの名が変わっただけの run が必ず止まらない）"""
        for rel, doc in (("judge/judgment.json", {"units": [{"key": "u1", "label": "block"}], "questions": []}),
                         ("judge/ties.json", {"rounds": {"1": [{"answer": "a", "to": "gone-q"}]}})):
            path = self.run.artifacts / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(doc), encoding="utf-8")
        judged = {"units": [], "judgment": ptr("judge/judgment.json"), "answer_ties": ptr("judge/ties.json"), "materials": None,
                  "rejudged": True, "rejudge_verdict": "", "lines": []}
        seal = {"mode": "seal", "ok": True, "hash": "abc", "diff": None, "protected_hits": [], "protected_count": 0, "reason": "",
                "deliver": None, "report": []}
        out = self.ask(judged=judged, seal=seal, final_gate="when_needed")
        self.assertEqual((out["open"], out["go"], out["reasons"]), (False, True, []), out)
        shown = self.ask(judged=judged, seal=seal, final_gate="always")
        self.assertIn("gone-q", shown["text"])

    def test_unattended_run_stops_instead_of_opening(self):
        out = self.ask(record=ptr("plan-converge.json"), unattended=True)
        self.assertEqual((out["open"], out["go"]), (False, False), out)
        self.assertEqual(out["stop_reason"], __import__("stopby").NEEDS_HUMAN)

    def test_another_runs_pointer_still_falls(self):
        out = self.ask(record=ptr("plan-converge.json", run_id="other-run"))
        self.assertEqual(out["stop_reason"], LINE_SCRIPT)


if __name__ == "__main__":
    unittest.main()

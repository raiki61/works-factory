"""判定（再審が走れば再審）を後ろへ渡す judged（workflows/line/src/stages.py の judged。docs/design/line.md の 4.4）。元は今の
test_line.py の AfterFixAndJudgedCase の judged の場面"""
import json
import unittest

from tests.blocks import kit

BLOCK = "line"
FIRST = {"judgment": {"path": "judge/j.json"}, "units": [{"id": "u1"}], "answer_ties": {"path": "t.json"}, "materials": {"path": "m.json"},
         "out_of_purpose": None}


def rejudge(**kw) -> dict:
    return {"ok": True, "status": "ok", "mode": "rejudge", "stop_reason": "", "reason": "", "ready": True, "judgment": {"path": "re/j.json"},
            "units": [{"id": "u2"}], "questions": [], "inputs": None, "brief": None, "materials": None, "out_of_purpose": None,
            "answer_ties": None, "rejudge_verdict": "upheld", "rejudge_exit": None, "rejudge_diff": None, "downgrades": [], "report": [], **kw}


class JudgedCase(unittest.TestCase):
    def setUp(self):
        self.s = kit.load(BLOCK, "stages")

    def test_no_rejudge_passes_the_first(self):
        got = self.s.judged(FIRST, None, due=False, objection="")
        self.assertEqual((got["units"], got["judgment"], got["rejudged"], got["stop_reason"]),
                         (FIRST["units"], FIRST["judgment"], False, ""))

    def test_rejudge_that_did_not_return_stops(self):
        """L-D48: 走るはずが返りが null（返す node が飛んだ）なら止めの語で止める"""
        got = self.s.judged(FIRST, None, due=True, objection="違う")
        self.assertEqual((got["stop_reason"], got["unread"]), ("works:rejudge", self.s.REJUDGE_FELL))
        self.assertEqual(got["carry"], [{"where": self.s.REJUDGE_LEFT_WHERE, "text": "違う"}], "再審されずに残った異議を次の依頼へ")

    def test_rejudge_takes_its_units_and_keeps_the_first_ties(self):
        got = self.s.judged(FIRST, rejudge(), due=True, objection="違う")
        self.assertEqual((got["units"], got["judgment"], got["answer_ties"], got["materials"], got["rejudged"]),
                         ([{"id": "u2"}], {"path": "re/j.json"}, FIRST["answer_ties"], FIRST["materials"], True))
        self.assertTrue(got["unread"].startswith("再審の前後を比べられない"), "出口が無ければ訳を名指す")
        self.assertEqual(got["carry"][0], {"where": self.s.REJUDGE_WHERE, "text": "再審: upheld（異議: 違う）"})

    def test_stopped_rejudge_returns_its_word(self):
        got = self.s.judged(FIRST, rejudge(ok=False, stop_reason="works:rejudge-session"), due=True, objection="")
        self.assertEqual(got["stop_reason"], "works:rejudge-session")
        self.assertEqual(self.s.judged(FIRST, rejudge(ok=False), due=True, objection="")["stop_reason"], "works:rejudge")

    def test_exit_comparisons(self):
        run = kit.Run(self, BLOCK)
        (run.artifacts / "re").mkdir()
        (run.artifacts / "re" / "exit.json").write_text(json.dumps({"new_open_units": ["u3"], "lowered": [], "unnamed_changed": ["u4"],
                                                                    "verdicts": ["overturned"]}))
        ptr = {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "re/exit.json"}
        with run.env():
            got = self.s.judged(FIRST, rejudge(rejudge_exit=ptr), due=True, objection="")
        self.assertEqual((got["new_open_units"], got["unnamed_changed"], got["unread"]), (["u3"], ["u4"], ""))
        self.assertIn("再審の結果（1 往復）: overturned", got["lines"][0])
        self.assertIn({"where": "u3", "text": "u3（再審が直す単位にした——この run では直していない）"}, got["carry"])

    def test_lowered_units_name_an_unreadable_rejudgment(self):
        """下げた単位の今のラベルは再審の judgment から読む。読めない時は「判定に無い」と言わずに、読めないと書く（E23）"""
        run = kit.Run(self, BLOCK)
        (run.artifacts / "re").mkdir()
        (run.artifacts / "re" / "exit.json").write_text(json.dumps({"lowered": ["u1"], "verdicts": ["overturned"]}))
        ptr = {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "re/exit.json"}
        unread = {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "re/j.json"}
        with run.env():
            got = self.s.judged(FIRST, rejudge(rejudge_exit=ptr, judgment=unread), due=True, objection="")
        self.assertIn("u1（再審が block から （再審の判定を読めない） に下げた——人が確かめる）", [c["text"] for c in got["carry"]])
        self.assertFalse([x for x in got["lines"] if "判定に無い" in x], got["lines"])

    def test_units_the_fix_took_are_not_left_open(self):
        """再審が開いた単位のうち、修正の段が受けた単位は「この run では直していない」に数えない（入力 fixed_units）"""
        run = kit.Run(self, BLOCK)
        (run.artifacts / "re").mkdir()
        (run.artifacts / "re" / "exit.json").write_text(json.dumps({"new_open_units": ["u1", "u3"], "verdicts": ["overturned"]}))
        ptr = {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "re/exit.json"}
        got = run.script("judged", fix_in=json.dumps(FIRST), rejudge_due="true", objection="",
                         rejudge=json.dumps(rejudge(rejudge_exit=ptr)), fixed_units=json.dumps([{"unit_id": "u1", "status": "fixed"}]))
        opened = [c["where"] for c in got["carry"] if "直す単位にした" in c["text"]]
        self.assertEqual(opened, ["u3"])
        self.assertEqual(got["new_open_units"], ["u1", "u3"], "出口の比べそのものは字のまま")

    def test_script(self):
        run = kit.Run(self, BLOCK)
        got = run.script("judged", fix_in=json.dumps(FIRST), rejudge_due="false", objection="", rejudge="null", fixed_units="[]")
        self.assertEqual((got["rejudged"], got["stop_reason"]), (False, ""))
        fell = run.script("judged", fix_in=json.dumps(FIRST), rejudge_due="true", objection="", rejudge=json.dumps({"ok": True}), fixed_units="[]")
        self.assertEqual(fell["stop_reason"], "works:line-script", "欄の欠けた前の版の返りは空と読まない")


class StoppedJudgmentWiringCase(unittest.TestCase):
    """judged が止めの語を返した run（再審が止まった・返らなかった）は、最後の試験の関門の when で飛び、待ち方だけで封じ・当て・最後の
    承認ノードまで飛ぶ（L-D48。止まった run で差分を書かない）。待ち方の模型は tests/blocks/line/test_wiring.py の would_run の 1 か所。
    後ろの節の when: は読まず、走りうる節は走ったと見る（それでも封じと当てが飛ぶことを見る）"""

    def test_a_stopped_judgment_reaches_neither_the_seal_nor_the_apply(self):
        from tests.blocks.line.test_wiring import TOP, would_run
        self.assertIn("$judged.output.stop_reason == ''", TOP["test-gate-final"]["when"])
        below = {"test-gate-final"}
        grew = True
        while grew:
            grew = False
            for key, node in TOP.items():
                if key not in below and below & set(node.get("depends_on") or []):
                    below.add(key)
                    grew = True
        state = {"test-gate-final": "skipped"}
        todo = sorted(below - set(state))
        while todo:
            ready = [k for k in todo if all(d in state or d not in below for d in TOP[k].get("depends_on") or [])]
            self.assertTrue(ready, f"待つ先の結末が決まらない節: {todo}")
            for key in ready:
                todo.remove(key)
                waits = {d: state.get(d, "completed") for d in TOP[key].get("depends_on") or []}
                state[key] = "completed" if would_run({**TOP[key], "depends_on": list(waits)}, waits) else "skipped"
        for key in ("merge-seal", "eyes-back-restore", "ask-final", "gate-final", "merge-apply"):
            self.assertEqual(state[key], "skipped", key)
        self.assertEqual(state["collect"], "completed", "報告は止まった run でも走る")


if __name__ == "__main__":
    unittest.main()

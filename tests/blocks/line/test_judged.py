"""判定（再審が走れば再審）を後ろへ渡す judged（workflows/line/src/stages.py の judged。docs/design/line.md の 4.4）。元は今の
tests/workflows/test_line.py の AfterFixAndJudgedCase の judged の場面"""
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
        """L-D48: 走るはずが受け皿の got が null（返す node が落ちた）なら止めの語で止める"""
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


if __name__ == "__main__":
    unittest.main()

"""結末の語の決め方（lib/outcome.py）の検査。決め方の表の 8 行を 1 行ずつ、各行の最小の入力で縛り、行の順と読み方の場面を足す。"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import outcome  # noqa: E402
import report  # noqa: E402
import stopby  # noqa: E402

OK_FACTS = {"start_ok": True, "record_problems": [], "failed": []}
UNIT = {"id": "u1", "paths": ["a"], "summary": "直す"}


def fixed_run(**over) -> dict:
    """直して最後のテストまで通った run の返り（over で段ごとに差し替える）"""
    returns = {
        "test-gate-base": {"mode": "base", "ok": True, "green": False, "red_cause": "introduced"},
        "judge": {"ready": True, "stop_reason": "", "units": [UNIT], "judgment": None},
        "plan": {"ready": True, "depth": []},
        "plan-review": {"pass": True, "stalled": False, "ask_human": False, "questions": []},
        "fix": {"done": True, "units": [{"unit_id": "u1", "status": "fixed", "reason": ""}], "conflicts": None,
                "delta_review": {"rounds": 1, "pass": True}},
        "test-gate-final": {"mode": "final", "ok": True, "green": True, "red_cause": ""},
        "eyes": {"ok": True, "r1": {"status": "pass", "reason": ""}, "r2": None, "r3": None, "r4": None, "premise_check": None,
                 "questions": []},
        "merge-seal": {"mode": "seal", "ok": True}, "merge-apply": {"mode": "apply", "ok": True},
        "rejudge": None, "replan": None, "replan-review": None,
    }
    returns.update(over)
    return returns


def decide(returns=None, gates=None, facts=None):
    return outcome.decide_outcome(fixed_run() if returns is None else returns, gates or {}, OK_FACTS if facts is None else facts)


class TableCase(unittest.TestCase):
    """表の 8 行（元 works/.shared/core/report.py:672-686 の順）"""

    def test_1_request_stop_and_human_stop(self):
        self.assertEqual(decide(gates={"gate-final": {"decision": "stop", "text": "request: 止め札"}}),
                         ("stopped_by_request", "gate-final:stop"))
        self.assertEqual(decide(gates={"gate-before-fix": {"decision": "reject", "text": "やめる"}}),
                         ("stopped_by_human", "gate-before-fix:reject"))
        judge = {"ready": False, "stop_reason": "human:spec", "units": []}
        self.assertEqual(decide(fixed_run(judge=judge)), ("stopped_by_human", "judge:human:spec"))

    def test_2_line_stops(self):
        self.assertEqual(decide(fixed_run(fix={**fixed_run()["fix"], "stop_reason": stopby.DELTA}))[0], "stopped_by_line")
        self.assertEqual(decide(fixed_run(**{"plan-review": {"stalled": True}})),
                         ("stopped_by_line", f"plan-review:{stopby.PLAN_CONVERGE}"))
        self.assertEqual(decide(fixed_run(**{"merge-seal": {"ok": False}})), ("stopped_by_line", "merge-seal:not-ok"))

    def test_3_needs_human(self):
        self.assertEqual(decide(fixed_run(fix={**fixed_run()["fix"], "stop_reason": stopby.REPLAN}))[0], "needs_human")
        eyes = {**fixed_run()["eyes"], "premise_check": {"verdict": "escalate", "reason": "前提が崩れた"}}
        self.assertEqual(decide(fixed_run(eyes=eyes))[0], "needs_human")
        review = {"pass": True, "ask_human": True, "questions": ["どちらに寄せるか"]}
        self.assertEqual(decide(fixed_run(**{"plan-review": review}, fix=None, **{"test-gate-final": None})),
                         ("needs_human", "plan-review:ask-human"))

    def test_4_record_invalid(self):
        self.assertEqual(decide(facts={**OK_FACTS, "start_ok": False}), ("record_invalid", "start:record-invalid"))
        self.assertEqual(decide(facts={**OK_FACTS, "record_problems": ["入力 judge が JSON でない"]})[0], "record_invalid")

    def test_5_interrupted(self):
        self.assertEqual(decide(facts={**OK_FACTS, "failed": ["fix__write"]}), ("interrupted", "fix__write:node-error"))
        self.assertEqual(decide(fixed_run(plan=None))[0], "interrupted")
        self.assertEqual(decide(fixed_run(**{"test-gate-final": None}), facts={**OK_FACTS, "failed": None})[0], "interrupted")
        self.assertEqual(decide(fixed_run(judge=None, rejudge=None), facts={**OK_FACTS, "failed": None}), ("interrupted", "judge:chain-cut"))

    def test_6_no_fix_needed(self):
        self.assertEqual(decide(fixed_run(judge={"ready": False, "stop_reason": "", "units": []}, plan=None, fix=None)),
                         ("no_fix_needed", ""))

    def test_7_residue(self):
        self.assertEqual(decide(fixed_run(**{"test-gate-final": {"ok": False, "green": False, "red_cause": "introduced"}})),
                         ("round_limit", ""))
        eyes = {**fixed_run()["eyes"], "r3": {"status": "redesign-needed", "reason": "崩れる"}}
        self.assertEqual(decide(fixed_run(eyes=eyes))[0], "round_limit")
        eyes = {**fixed_run()["eyes"], "r2": {"status": "unverifiable", "reason": "独立設計が無い"}}
        self.assertEqual(decide(fixed_run(eyes=eyes))[0], "round_limit")
        fix = {**fixed_run()["fix"], "units": [{"unit_id": "u1", "status": "given_up", "reason": "通らない"}]}
        self.assertEqual(decide(fixed_run(fix=fix))[0], "round_limit")
        fix = {**fixed_run()["fix"], "delta_review": {"rounds": 3, "pass": False}}
        self.assertEqual(decide(fixed_run(fix=fix))[0], "round_limit")

    def test_8_fixed(self):
        self.assertEqual(decide(), ("fixed", ""))


class OrderCase(unittest.TestCase):
    def test_request_before_line_stop(self):
        returns = fixed_run(**{"merge-seal": {"ok": False}})
        self.assertEqual(decide(returns, gates={"gate-final": {"decision": "stop", "text": "request: 止め札"}})[0], "stopped_by_request")

    def test_human_stop_before_interrupted(self):
        got = decide(gates={"gate-start": {"decision": "stop", "text": "やめる"}}, facts={**OK_FACTS, "failed": ["plan__write"]})
        self.assertEqual(got[0], "stopped_by_human")

    def test_record_invalid_before_interrupted(self):
        got = decide(facts={"start_ok": False, "record_problems": [], "failed": ["plan__write"]})
        self.assertEqual(got[0], "record_invalid")

    def test_unknown_answer_word_is_a_record_problem(self):
        gates = {"gate-final": {"decision": "maybe", "text": ""}}
        problems = outcome.unknown_answers(gates)
        self.assertEqual(len(problems), 1)
        self.assertIn("'maybe'", problems[0])
        self.assertEqual(decide(gates=gates, facts={**OK_FACTS, "record_problems": problems}), ("record_invalid", "report:record-invalid"))
        for word in ("approve", "continue"):
            with self.subTest(word):
                gates = {"gate-final": {"decision": word, "text": ""}}
                self.assertEqual(outcome.unknown_answers(gates), [])
                self.assertEqual(decide(gates=gates)[0], "fixed")


class ReadingCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)

    def put(self, name: str, doc) -> str:
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def test_skipped_eyes_are_not_left(self):
        eyes = {**fixed_run()["eyes"], "r1": None, "r2": None}
        self.assertEqual(decide(fixed_run(eyes=eyes))[0], "fixed")

    def test_all_returns_none_still_gives_a_word(self):
        got = outcome.decide_outcome({k: None for k in fixed_run()}, {g: None for g in outcome.GATES}, {})
        self.assertIn(got[0], report.OUTCOMES)
        self.assertIn(outcome.decide_outcome({}, {}, OK_FACTS)[0], report.OUTCOMES)

    def test_conflicts_single_list_and_none(self):
        asked = {"unit_key": "u1", "ruling": {"decision": "ask_human"}}
        ruled = {"unit_key": "u2", "ruling": {"decision": "fix_code_as"}}
        waiting = {"unit_key": "u3", "ruling": {"decision": "fix_plan_item"}, "replan": "waiting"}
        one = self.put("fix/conflicts.json", {"items": [asked]})
        quiet = self.put("fix/r1/conflicts.json", {"items": [ruled, waiting]})
        later = self.put("refix/conflicts.json", {"items": [asked]})
        for conflicts, word in ((one, "needs_human"), ([quiet, later], "needs_human"), ([quiet], "fixed"), (None, "fixed")):
            with self.subTest(conflicts=conflicts):
                fix = {**fixed_run()["fix"], "conflicts": conflicts}
                self.assertEqual(decide(fixed_run(fix=fix))[0], word)

    def test_unreadable_conflicts_are_record_problems(self):
        """読めない申し出と裁定のファイルは人に回した申し出を隠すので、訳を record_problems に入れて結果を名乗らせない"""
        broken = self.dir / "fix/broken.json"
        broken.parent.mkdir(parents=True, exist_ok=True)
        broken.write_text("{not json", encoding="utf-8")
        shapes = {"JSON でない": str(broken), "items が無い": self.put("fix/no-items.json", {"rows": []}),
                  "オブジェクトでない": self.put("fix/list.json", []), "無いファイル": str(self.dir / "fix/none.json")}
        for name, path in shapes.items():
            with self.subTest(name):
                returns = fixed_run(fix={**fixed_run()["fix"], "conflicts": path})
                rows, notes = outcome.conflict_rows(returns)
                self.assertEqual((rows, len(notes)), ([], 1))
                self.assertIn(path, notes[0])
                self.assertEqual(decide(returns, facts={**OK_FACTS, "record_problems": notes}), ("record_invalid", "report:record-invalid"))

    def test_unmeasured_materials_only_is_fixed_needs_check(self):
        judgment = self.put("judge/judgment.json", {})
        self.put("judge/materials.json", {"parallel_pr": {"status": "not_run"}, "ci": {"status": "awaiting_human"},
                                          "lint": {"status": "done"}})
        judge = {**fixed_run()["judge"], "judgment": judgment}
        self.assertEqual(decide(fixed_run(judge=judge)), ("fixed_needs_check", ""))
        red = {"ok": False, "green": False, "red_cause": "introduced"}
        self.assertEqual(decide(fixed_run(judge=judge, **{"test-gate-final": red}))[0], "round_limit")

    def test_empty_or_missing_materials_count_zero(self):
        judgment = self.put("judge/judgment.json", {})
        judge = {**fixed_run()["judge"], "judgment": judgment}
        self.assertEqual(decide(fixed_run(judge=judge))[0], "fixed")
        self.put("judge/materials.json", {})
        self.assertEqual(decide(fixed_run(judge=judge))[0], "fixed")

    def test_plan_not_ready(self):
        self.assertEqual(decide(fixed_run(plan={"ready": False})), ("stopped_by_line", "plan:give-up"))
        self.assertEqual(decide(fixed_run(plan={"ready": False, "stop_reason": stopby.FIX})), ("stopped_by_line", f"plan:{stopby.FIX}"))
        judge = {"ready": True, "stop_reason": "", "units": []}
        self.assertEqual(decide(fixed_run(judge=judge, plan={"ready": False}, fix=None))[0], "no_fix_needed")

    def test_later_judge_and_plan_are_read_first(self):
        """再審・案の直しの返りは後の段で先に読む（線と同じ）"""
        self.assertEqual(decide(fixed_run(rejudge={"ready": False, "stop_reason": "", "units": []}))[0], "no_fix_needed")
        self.assertEqual(decide(fixed_run(replan={"ready": False}))[0], "stopped_by_line")

    def test_ok_outcomes(self):
        self.assertEqual(outcome.OK_OUTCOMES, ("fixed", "fixed_needs_check", "no_fix_needed"))
        self.assertTrue(set(outcome.OK_OUTCOMES) <= set(report.OUTCOMES))


class WordsCase(unittest.TestCase):
    def test_outcomes_are_the_original_ten_words(self):
        """返す節の enum と同じ 10 語。字も並びも今の works の report.OUTCOMES のまま"""
        self.assertEqual(report.OUTCOMES, ("fixed", "fixed_needs_check", "no_fix_needed", "round_limit", "stopped_by_request",
                                           "stopped_by_human", "stopped_by_line", "needs_human", "record_invalid", "interrupted"))

    def test_every_outcome_has_plain_words(self):
        """元 works/tests/test_gate_head.py の ReportHeadCase.test_every_outcome_has_plain_words"""
        self.assertEqual(set(report.OUTCOME_WORDS), set(report.OUTCOMES))


if __name__ == "__main__":
    unittest.main()

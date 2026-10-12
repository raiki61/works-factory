"""結末の語の決め方（lib/outcome.py）の検査。決め方の表の 8 行を 1 行ずつ、各行の最小の入力で縛り、行の順と読み方の場面を足す。"""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import conflict  # noqa: E402
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

    def test_nothing_fixed_is_not_fixed(self):
        """判定と計画が ready なのに修正も最後のテストも無い run は直したと名乗らない"""
        returns = fixed_run(fix=None, **{"test-gate-final": None, "eyes": None, "merge-seal": None, "merge-apply": None})
        self.assertEqual(decide(returns, facts={**OK_FACTS, "failed": None}), ("interrupted", "fix:chain-cut"))
        self.assertIn("計画が修正案を出したのに修正の返りが無い", outcome.chain_notes(returns))

    def test_fix_without_final_test_or_seal_is_not_fixed(self):
        self.assertEqual(decide(fixed_run(**{"test-gate-final": None})), ("interrupted", "test-gate-final:chain-cut"))
        self.assertEqual(decide(fixed_run(**{"merge-seal": None, "merge-apply": None})), ("interrupted", "merge-seal:chain-cut"))

    def test_missing_eye_of_a_standard_run_is_left(self):
        """R14（元 report.eye_counts の missing「結果が無い——再実行の要あり」:599-602）: 直した後の深さが標準（線の redepth の
        skip_optional が空。facts の eyes_skip）なのに返りの無い目は、深さで省いた目と分けて残りに数える。軽量で省いた run と、深さの
        返りの届かない run は数えない"""
        eyes = {**fixed_run()["eyes"], "r2": None}
        self.assertEqual(decide(fixed_run(eyes=eyes), facts={**OK_FACTS, "eyes_skip": ""}), ("round_limit", ""))
        self.assertIn({"where": f"{report.EYES_WHERE} R2", "text": "R2 の結果が無い——再実行の要あり（深さは標準で、省いていない）"},
                      outcome.residue(fixed_run(eyes=eyes), {"eyes_skip": ""}))
        self.assertEqual(decide(fixed_run(eyes=eyes), facts={**OK_FACTS, "eyes_skip": "軽量で省いた"}), ("fixed", ""))
        self.assertEqual(decide(fixed_run(eyes=eyes)), ("fixed", ""))

    def test_eyes_not_ok_without_counted_eyes_is_left(self):
        """独立の目のブロックが ok: false で、数えた目（r1〜r4）が全部 null でも、残りに 1 行入れて fixed にしない"""
        eyes = {**fixed_run()["eyes"], "ok": False, "r1": None}
        self.assertEqual(decide(fixed_run(eyes=eyes)), ("round_limit", ""))
        self.assertEqual([r["where"] for r in outcome.residue(fixed_run(eyes=eyes))], [report.EYES_WHERE])
        eyes = {**eyes, "r3": {"status": "redesign-needed", "reason": "崩れる"}}
        self.assertEqual([r["where"] for r in outcome.residue(fixed_run(eyes=eyes))], [f"{report.EYES_WHERE} R3"], "目の行が在れば重ねない")

    def test_seal_without_ok_is_left(self):
        """封じの ok が真でない run は fixed を名乗らない（_proved。ok: false は線の止め _line_stop が先に拾い、訳は報告の
        _stop_lines が出す）。残りの行には重ねない"""
        self.assertEqual(decide(fixed_run(**{"merge-seal": {"mode": "seal"}})), ("round_limit", ""))
        self.assertEqual(outcome.residue(fixed_run(**{"merge-seal": {"mode": "seal"}})), [])


class LineStopCase(unittest.TestCase):
    """R5b・S48: 線の節が返す止めの語（facts の stops。線の collect が集めた {節: 語}）を結末に入れる（元 report._stop_info は線の境の
    節が盤面に書いた止めも読んだ）: 入口の拒みと線の script の例外は stopped_by_line、無人の run の関所の止めは needs_human、人の止め
    human:<関所> は stopped_by_human"""

    def test_line_stop_words_reach_the_outcome(self):
        refused = {"start_ok": False, "record_problems": [], "failed": [], "stops": [("start", stopby.START_REFUSED)]}
        self.assertEqual(decide(fixed_run(judge=None, plan=None, fix=None), facts=refused), ("stopped_by_line", f"start:{stopby.START_REFUSED}"))
        broken = {**OK_FACTS, "stops": [("redepth", stopby.LINE_SCRIPT)]}
        self.assertEqual(decide(fixed_run(**{"test-gate-final": None, "eyes": None, "merge-seal": None, "merge-apply": None}),
                                facts=broken), ("stopped_by_line", f"redepth:{stopby.LINE_SCRIPT}"))
        waiting = {**OK_FACTS, "stops": [("ask-final", stopby.NEEDS_HUMAN)]}
        self.assertEqual(decide(fixed_run(**{"merge-apply": None}), facts=waiting), ("needs_human", f"ask-final:{stopby.NEEDS_HUMAN}"))
        human = {**OK_FACTS, "stops": [("answer-final", "human:gate-final")]}
        self.assertEqual(decide(fixed_run(**{"merge-apply": None}), facts=human), ("stopped_by_human", "answer-final:human:gate-final"))

    def test_line_words_are_the_stopby_words(self):
        self.assertEqual((stopby.START_REFUSED, stopby.NEEDS_HUMAN, stopby.LINE_SCRIPT),
                         ("works:start-refused", "works:needs-human", "works:line-script"))
        self.assertIn(stopby.NEEDS_HUMAN, outcome.WAIT_WORDS)


class ConflictNamesCase(unittest.TestCase):
    def test_conflict_field_names_come_from_conflict(self):
        """S34: 結末と報告は fix の conflicts.json の欄の名と裁定の語を lib/conflict.py から引き、自分の定数に写さない（K20）"""
        import conflict
        import runreport
        for name in ("CONFLICT_ITEMS", "CONFLICT_RULING", "CONFLICT_DECISION", "CONFLICT_REPLAN", "CONFLICT_KIND", "CONFLICT_HEAD",
                     "ASK_HUMAN", "REPLACE_QUERY", "FIX_PLAN_ITEM", "FIX_RULINGS", "RULINGS", "REPLAN_WAITING", "REPLAN_KEPT",
                     "REPLAN_WHY", "PLAN_UNITS", "HELD_WORK_KEPT", "DIV_KINDS", "UNSET"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(outcome, name))
                self.assertFalse(hasattr(runreport, name))
        self.assertEqual((conflict.ITEMS, conflict.RULING, conflict.DECISION), ("items", "ruling", "decision"))


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

    def test_needs_human_before_record_invalid(self):
        """人に回した食い違いは、始めの記録が読めない run でも人待ちの語で返る（元 report.py:672-686 の表の 3 が 4 より先）"""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conflicts = pathlib.Path(tmp.name) / "fix" / "conflicts.json"
        conflicts.parent.mkdir()
        conflicts.write_text(json.dumps({"items": [{"unit_key": "u1", "ruling": {"decision": "ask_human"}}]}), encoding="utf-8")
        returns = fixed_run(fix={**fixed_run()["fix"], "conflicts": str(conflicts)})
        got = decide(returns, facts={"start_ok": False, "record_problems": [], "failed": []})
        self.assertEqual(got, ("needs_human", f"fix:{stopby.CONFLICT}"))

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
        quiet = self.put("fix/r1/conflicts.json", {"items": [ruled]})
        later = self.put("refix/conflicts.json", {"items": [asked]})
        for conflicts, word in ((one, "needs_human"), ([quiet, later], "needs_human"), ([quiet], "fixed"), (None, "fixed")):
            with self.subTest(conflicts=conflicts):
                fix = {**fixed_run()["fix"], "conflicts": conflicts}
                self.assertEqual(decide(fixed_run(fix=fix))[0], word)

    def test_waiting_replan_is_closed_unless_interrupted(self):
        """案の直しを待つ行は、終わった run では諦めた行として人に回し（元 report.build の replan.close_at）、途中で落ちた run では
        締めない"""
        waiting = {"unit_key": "u3", "ruling": {"decision": "fix_plan_item", "text": "案を", "plan_units": ["u3"]}, "replan": "waiting"}
        fix = {**fixed_run()["fix"], "conflicts": self.put("fix/conflicts.json", {"items": [waiting]})}
        self.assertEqual(decide(fixed_run(fix=fix)), ("needs_human", f"fix:{stopby.CONFLICT}"))
        self.assertEqual(outcome.asked_conflicts(fixed_run(fix=fix))[0][conflict.REPLAN_WHY], outcome.CLOSE_WHY)
        self.assertEqual(decide(fixed_run(fix=fix), facts={**OK_FACTS, "failed": ["refix__write"]})[0], "interrupted")
        self.assertEqual(outcome.asked_conflicts(fixed_run(fix=fix), closed=False), [])
        self.assertEqual(outcome.waiting_conflicts(fixed_run(fix=fix)), [waiting])

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

    def test_material_answered_with_command_and_output_is_not_left(self):
        """依頼が命令と出力つきで答えた素材は次の run の残りに数えない（元 report.residue の gatemarks.measured_materials）。
        命令か出力の欠けた答え・2 つの問いに当たる答えは測りの代わりにしない"""
        judgment = self.put("judge/judgment.json", {"questions": [
            {"key": "q1", "origin": "ci", "status": "held"}, {"key": "q2", "origin": "ci", "status": "escalate"}]})
        self.put("judge/materials.json", {"parallel_pr": {"status": "not_run"}, "ci": {"status": "awaiting_human"}})
        returns = fixed_run(judge={**fixed_run()["judge"], "judgment": judgment})
        measured = {"question": "parallel_pr", "text": "重ならない", "command": "gh pr list", "output": "0 件"}
        facts = {**OK_FACTS, "answers": [measured, {"question": "ci", "text": "緑", "command": "make ci", "output": "ok"}]}
        self.assertEqual([r["where"] for r in outcome.residue(returns, facts)], [f"{outcome.MATERIAL_WHERE} ci"])
        self.assertEqual(outcome.measured_materials(returns, facts["answers"]), {"parallel_pr"})
        self.assertEqual(decide(returns, facts=facts), ("fixed_needs_check", ""))
        self.assertEqual(outcome.measured_materials(returns, [{**measured, "output": ""}]), set())
        returns = fixed_run(judge={**fixed_run()["judge"], "judgment": self.put("judge/judgment.json", {})})
        self.put("judge/materials.json", {"parallel_pr": {"status": "not_run"}})
        self.assertEqual(decide(returns, facts={**OK_FACTS, "answers": [measured]}), ("fixed", ""))

    def test_after_rows_are_left(self):
        """直した後の実測が住処の外の知る場所の増えを見たら残りに数える（元 rest_outside_validator の structmark.after_rows）"""
        after = self.put("eyes/structure-after.json", {})
        row = {"where": "考えの住処: x", "text": "増えた"}
        with mock.patch.object(outcome.structmark, "after_rows", return_value=[row]) as got:
            returns = fixed_run(eyes={**fixed_run()["eyes"], "structure_after": after})
            self.assertEqual(outcome.residue(returns), [row])
            self.assertEqual(decide(returns), ("round_limit", ""))
        got.assert_called_with(pathlib.Path(after).parent)

    def test_absorbed_fall_is_left_unless_its_block_returned(self):
        """落ちたが線が受け止めた節は途中で終わった run でなく残り（元 report.absorbed_rows）。返りの在るブロックの中の落ちは
        そのブロックの返りが言うので重ねない"""
        top = {"node": "redepth", "error": "boom\n2 行目"}
        facts = {**OK_FACTS, "absorbed": [top, {"node": "eyes__r2", "error": "落ちた"}]}
        self.assertEqual(decide(facts=facts), ("round_limit", ""))
        rows = outcome.residue(fixed_run(), facts)
        self.assertEqual([r["where"] for r in rows], [f"{report.ABSORBED_WHERE} redepth"])
        self.assertIn("boom", rows[0]["text"])
        self.assertNotIn("2 行目", rows[0]["text"])
        self.assertEqual(decide(fixed_run(eyes=None), facts={**OK_FACTS, "absorbed": [{"node": "eyes__r2", "error": "x"}]})[0],
                         "round_limit")

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

    def test_record_problems_split_must_open_from_notes(self):
        """開けないと結果を名乗れない指し札（fix の conflicts）だけを訳に、ほかの開けなかった指し札は注意に"""
        unopened = [("fix", "conflicts", "指し札の先 a が無い"), ("judge", "world", "指し札の先 b が無い")]
        gates = {"gate-final": {"decision": "maybe", "text": ""}}
        problems, notes = outcome.record_problems({}, gates, unread=["入力 plan が JSON でない"], unopened=unopened)
        self.assertEqual(problems[:2], ["入力 plan が JSON でない", "指し札の先 a が無い"])
        self.assertIn("'maybe'", problems[2])
        self.assertEqual(notes, ["指し札の先 b が無い"])

    def test_conflict_counts_and_asked_units(self):
        rows = [{"unit_key": "u1", "kind": "not_red", "ruling": {"decision": "ask_human", "text": "人に"}},
                {"unit_key": "u2", "kind": "scope_needed", "ruling": {"decision": "fix_plan_item", "text": "案を", "plan_units": ["u2", "u3"]},
                 "replan": "gave_up", "replan_why": "案を直せなかった"},
                {"unit_key": "u4", "ruling": {"decision": "fix_code_as", "text": "こう"}},
                {"unit_key": "u5", "kind": "not_red", "ruling": None}]
        returns = fixed_run(fix={**fixed_run()["fix"], "conflicts": self.put("fix/conflicts.json", {"items": rows})})
        rulings, kinds = outcome.conflict_counts(returns)
        self.assertEqual(rulings, {"parked": 4, "unruled": 1, "fix_test_scope": 0, "fix_code_as": 1, "ask_human": 1, "fix_plan_item": 1})
        self.assertEqual((kinds["not_red"], kinds["scope_needed"], kinds[conflict.UNSET]), (2, 1, 1))
        self.assertEqual([k for k, _ in outcome.asked_units(returns)], ["u1", "u2", "u3"])

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

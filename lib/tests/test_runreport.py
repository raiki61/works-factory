"""機械の報告と持ち越し・書き手の受け付けと AI の報告（lib/runreport.py）の検査。

報告の頭と答えの下書きの場面は、元の works/tests/test_gate_head.py の ReportHeadCase と works/tests/test_gate_drafts.py の
DraftsCase のうち報告の側の物を、盤面と関所の節の代わりにブロックの返りの入力で書き直した（各試験の docstring に元の名）。
"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import carry  # noqa: E402
import gatemarks  # noqa: E402
import outcome  # noqa: E402
import report  # noqa: E402
import report_roles  # noqa: E402
import runreport  # noqa: E402
from lib.tests.test_outcome import fixed_run  # noqa: E402

UNATTENDED = {"run_id": "run-1", "unattended": "true"}
RUN = "run-1"


def rows_of(*rows) -> list:
    """run の記録の見本の行（止めた実行基盤の packages/workflows/src/logger.ts と node-record-serialization.ts の形）"""
    return list(rows)


def start(step, ts):
    return {"type": "node_start", "step": step, "ts": ts, "workflow_id": RUN}


def done(step, ts, cost=None, accounting="node", model=None, kind="node_complete"):
    row = {"type": kind, "step": step, "ts": ts, "workflow_id": RUN, "execution": {"accounting": accounting}}
    if cost is not None:
        row["cost_usd"] = cost
    if model:
        row["execution"]["binding"] = {"model": {"resolved": {"source": "provider", "value": model}}}
    return row


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)
        self.out = self.dir / "report"

    def put(self, rel: str, doc) -> str:
        path = self.dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def build(self, returns=None, gates=None, typed=None, transcript=None, start=None, problems=()):
        returns = fixed_run() if returns is None else returns
        gates = gates or {}
        decided = outcome.decide_outcome(returns, gates, {"start_ok": True, "record_problems": list(problems),
                                                          "failed": (transcript or {}).get("failed", [])})
        got = runreport.build(returns, gates, typed or {}, transcript, *decided, out_dir=self.out, start=start or {"run_id": RUN},
                              problems=problems, run_id=RUN)
        return got, pathlib.Path(got["report"]).read_text(encoding="utf-8"), decided

    @staticmethod
    def section(text: str, heading: str) -> str:
        body = text.split(f"{heading}\n\n", 1)[1]
        return body.split("\n## ", 1)[0]


class BuildCase(Base):
    def test_writes_report_and_only_present_carries(self):
        got, text, decided = self.build()
        self.assertEqual(decided[0], "fixed")
        self.assertTrue(text.startswith(report.TITLE_HEADING.format(run=RUN)))
        self.assertIsNone(got["next_request"])
        self.assertIsNone(got["prior_failures"])
        self.assertEqual(got["facts_file"], got["report"])
        self.assertTrue(got["ai_go"])
        for h in report.HEADINGS:
            self.assertIn(h, text)

        eyes = {**fixed_run()["eyes"], "r2": {"status": "redesign-needed", "reason": "独立設計と食い違う"}}
        fix = {**fixed_run()["fix"], "units": [{"unit_id": "u1", "status": "given_up", "reason": "受け付けが 3 回拒んだ"}]}
        got, _, decided = self.build(fixed_run(eyes=eyes, fix=fix))
        self.assertEqual(decided[0], "round_limit")
        doc = json.loads(pathlib.Path(got["next_request"]).read_text(encoding="utf-8"))
        prior = json.loads(pathlib.Path(got["prior_failures"]).read_text(encoding="utf-8"))
        self.assertEqual(carry.errors(doc, carry.NEXT_SCHEMA), [])
        self.assertEqual(carry.errors(prior, carry.PRIOR_SCHEMA), [])
        self.assertEqual([r["where"] for r in prior if r["where"] == carry.REDESIGN_WHERE], [carry.REDESIGN_WHERE])
        self.assertFalse(any(report._r2_redesign(r) for r in doc["findings"]), "R2 の作り直しの行は前の失敗にだけ載せる")
        self.assertTrue(any("受け付けが 3 回拒んだ" in r["text"] for r in prior))

    def test_record_invalid_has_no_ai(self):
        got = runreport.build({}, {}, {}, None, "record_invalid", "start:record-invalid", out_dir=self.out)
        self.assertFalse(got["ai_go"])

    def test_stopped_by_request_still_writes_report(self):
        """持ち主の決め report-on-stop: 止め札で止めた run も報告を出す"""
        gates = {"gate-final": {"decision": "stop", "text": "request: 止め札"}}
        _, text, decided = self.build(gates=gates)
        self.assertEqual(decided[0], "stopped_by_request")
        self.assertIn(report.OUTCOME_WORDS["stopped_by_request"], text)
        self.assertIn("関所 gate-final: stop（request: 止め札）", text)


class TddCase(Base):
    GROUP_RAN = {"group_id": "g1", "ran": True, "reason": "", "suite": "run-tests", "reused": None,
                 "units": [{"unit_key": "u1", "route": "tdd", "why": "", "tests": ["t::a"], "red": "ok", "green": "ok", "refactor": "none",
                            "gave_up": "", "red_quotes": {"t::a": {"quote": "期待 3 が 6", "why": "分母が違う"}}}]}
    GROUP_OFF = {"group_id": "g2", "ran": False, "reason": "テストの実行ファイルが無い", "suite": "", "reused": None, "units": []}

    def typed(self, *entries):
        return {"by_type": {"tdd-unit": [{"include": inc, "loop": [], "node": f"{inc}__tdd", "path": f"nodes/{inc}.md", "produced_at": "",
                                          "body": body} for inc, body in entries]}, "warnings": []}

    def test_groups_reach_tdd_lines_unchanged(self):
        typed = self.typed(("fix", [self.GROUP_RAN, self.GROUP_OFF]))
        _, text, _ = self.build(typed=typed)
        stages = [(f"{report.TDD_STAGES[0]}（組 g1）", self.GROUP_RAN), (f"{report.TDD_STAGES[0]}（組 g2）", self.GROUP_OFF)]
        for line in report.tdd_lines(stages):
            self.assertIn(line, text)
        self.assertIn("期待 3 が 6", text)
        self.assertIn("分母が違う", text)
        freeze = report.freeze_lines(stages)
        self.assertEqual(len(freeze), 1)
        self.assertIn(freeze[0], self.section(text, report.ENTRY_HEADING), "凍結が効いていない組を入口の節で言う")

    def test_second_fix_stage_is_named_apart(self):
        typed = self.typed(("fix", [self.GROUP_RAN]), ("refix", [self.GROUP_RAN]))
        _, text, _ = self.build(typed=typed)
        self.assertIn(f"{report.TDD_STAGES[1]}（組 g1）", text)

    def test_units_without_artifact(self):
        fix = {**fixed_run()["fix"], "units": [{"unit_id": "u1", "status": "fixed", "reason": "直した"}]}
        _, text, _ = self.build(fixed_run(fix=fix))
        body = self.section(text, report.TDD_HEADING)
        self.assertIn("tdd-unit が一覧に無い", body)
        self.assertIn("u1: fixed（直した）", body)


class TypedCase(Base):
    def test_warnings_each_reach_notes(self):
        typed = {"by_type": {}, "warnings": ["一覧の記録 a が読めない", "一覧の記録 b が読めない"]}
        _, text, _ = self.build(typed=typed)
        notes = self.section(text, runreport.NOTES_HEADING)
        self.assertIn("- 一覧の記録 a が読めない", notes)
        self.assertIn("- 一覧の記録 b が読めない", notes)

    def test_eye_verdict_of_other_shape_is_a_note(self):
        good = {"eye": "r1", "status": "pass", "reason": "小さい"}
        bad = {"eye": "r2", "status": "pass"}
        typed = {"by_type": {"eye-verdict": [{"include": "eyes", "loop": [], "node": "eyes__r1", "path": "nodes/r1.md", "body": good},
                                             {"include": "eyes", "loop": [], "node": "eyes__r2", "path": "nodes/r2.md", "body": bad}]},
                 "warnings": []}
        _, text, _ = self.build(typed=typed)
        self.assertIn("成果物 r1（eyes）: pass（小さい）", text)
        self.assertIn("nodes/r2.md の中身が {eye, status, reason} の形でない", self.section(text, runreport.NOTES_HEADING))

    def test_green_cert_names_red_let_through(self):
        cert = {"mode": "final", "ok": True, "green": False, "red_cause": "inherited"}
        typed = {"by_type": {"green-cert": [{"include": "test-gate-final", "loop": [], "node": "test-gate-final__result",
                                             "path": "nodes/r.md", "body": cert}]}, "warnings": []}
        _, text, _ = self.build(typed=typed)
        self.assertIn("赤のまま通した", self.section(text, runreport.GREEN_HEADING))


class TranscriptCase(Base):
    def test_none_transcript_cost_cannot_be_taken(self):
        _, text, _ = self.build()
        self.assertIn(f"{report.COST_HEADING}\n\n取れない", text)

    def test_rows_give_cost_time_failed_and_retried(self):
        rows = rows_of(
            start("judge__diagnose", "2026-10-12T00:00:00Z"),
            done("judge__diagnose", "2026-10-12T00:03:00Z", cost=0.5, model="sonnet"),
            start("fix__write", "2026-10-12T00:04:00Z"),
            done("fix__write", "2026-10-12T00:05:00Z", cost=0.25, kind="node_error"),
            start("fix__write", "2026-10-12T00:06:00Z"),
            done("fix__write", "2026-10-12T00:10:00Z", cost=0.25),
            done("fix", "2026-10-12T00:10:00Z", accounting="aggregate"),
            {**done("fix", "2026-10-12T00:10:00Z", accounting="aggregate"), "cost_usd": 0.5},
            start("eyes__r1", "2026-10-12T00:11:00Z"),
            done("eyes__r1", "2026-10-12T00:12:00Z", kind="node_error"),
            start("report__facts", "2026-10-12T00:13:00Z"),
            done("report__facts", "2026-10-12T00:13:30Z", kind="node_error"),
            done("test-gate-final__run", "2026-10-12T00:13:00Z"),
        )
        facts = runreport.transcript_facts(rows, exclude_prefix="report__")
        self.assertEqual(facts["failed"], ["eyes__r1"])
        self.assertEqual(facts["retried"], ["fix__write"])
        self.assertEqual(facts["cost"], {"judge__diagnose": 0.5, "fix__write": 0.5})
        self.assertNotIn("fix", facts["cost"], "言い直しの行は数えない")
        self.assertEqual(facts["minutes"]["judge__diagnose"], 3.0)
        self.assertEqual(facts["uncosted"]["test-gate-final__run"], 1)
        self.assertEqual(facts["models"], {"judge__diagnose": ["sonnet"]})
        _, text, decided = self.build(transcript=facts)
        self.assertEqual(decided[0], "interrupted")
        self.assertIn("合計（自分の費用を言う行の和。言い直しの行は数えない）: $1.0000", text)
        self.assertIn(f"{report.INTERRUPTED_HEAD}: 落ちた節 eyes__r1", text)
        self.assertIn(f"{report.RETRIED_HEAD}: fix__write", text)
        self.assertIn("費用の欄が無い行 1 件", text)
        self.assertIn("- judge__diagnose: sonnet", self.section(text, report.MODEL_HEADING))


class DecisionsCase(Base):
    def test_nothing_to_decide_puts_next_items(self):
        """元 ReportHeadCase.test_nothing_to_decide_puts_next_items: 決めることが無い run は 2 行目に次の run に渡す物の件数"""
        p = self.put("judge/out-of-purpose.json", {"rounds": {"1": [{"source": "P1", "why_outside": "目的の外の所見",
                                                                    "found": [{"where": "a.py:1", "text": "x"},
                                                                              {"where": "b.py:2", "text": "y"}]}]}})
        judge = {**fixed_run()["judge"], "out_of_purpose": p}
        _, text, _ = self.build(fixed_run(judge=judge))
        lines = text.splitlines()
        self.assertEqual(lines[2], gatemarks.HAPPENED + report.OUTCOME_WORDS["fixed"] + "（fixed）")
        self.assertEqual(lines[3], "次の run に渡す物: 2 件")
        self.assertEqual(lines[4], gatemarks.PUSH + gatemarks.NO_PUSH)

    def test_decisions_are_counted(self):
        """元 ReportHeadCase.test_decisions_are_counted"""
        review = {"pass": True, "ask_human": True, "questions": ["どちらに寄せるか／推し: 通す（continue）——小さい方（理由: 速い）"]}
        eyes = {**fixed_run()["eyes"], "questions": ["守りを触ってよいか"]}
        _, text, _ = self.build(fixed_run(eyes=eyes, **{"plan-review": review}), gates={"gate-before-fix": {"decision": "approve", "text": ""}})
        second = text.splitlines()[3]
        self.assertTrue(second.startswith(gatemarks.DECIDE + "2 件"), second)
        self.assertIn("小さい方", text.splitlines()[4])

    def test_unreturned_unit_is_counted_as_decision(self):
        """元 ReportHeadCase.test_unreturned_unit_is_counted_as_decision: 関所で答えたが直す義務に戻せなかった単位（fix の not_done）"""
        fix = {**fixed_run()["fix"], "units": [{"unit_id": "u9", "status": "not_done", "reason": "案の直しを待つ"}]}
        _, text, _ = self.build(fixed_run(fix=fix))
        self.assertIn("直す義務に戻せなかった単位 1 件", text.splitlines()[3])
        self.assertIn("u9", self.section(text, report.DECISIONS_HEADING))

    def test_checks_left_are_counted_as_decision(self):
        """元 ReportHeadCase.test_checks_left_are_counted_as_decision"""
        judgment = self.put("judge/judgment.json", {})
        self.put("judge/materials.json", {"parallel_pr": {"status": "not_run"}})
        _, text, decided = self.build(fixed_run(judge={**fixed_run()["judge"], "judgment": judgment}))
        self.assertEqual(decided[0], "fixed_needs_check")
        self.assertTrue(text.splitlines()[2].startswith(gatemarks.HAPPENED + report.OUTCOME_WORDS["fixed_needs_check"]))
        self.assertIn(f"{report.CHECKS_LEFT} 1 件", text.splitlines()[3])
        self.assertNotIn("直しきれず", "\n".join(text.splitlines()[2:5]), "冒頭 3 行は直しきれずと呼ばない")

    def test_gate_passes_follow_decisions(self):
        review = self.put("plan-review/review.json", {})
        self.put("plan-review/gate-passes.json", [{"item": "小さい直し", "why": "自明"}])
        _, text, _ = self.build(fixed_run(**{"plan-review": {**fixed_run()["plan-review"], "review": review}}))
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn("修正前の関所が聞かずに通した行（plan-review）: 1 件", body)
        self.assertIn("小さい直し", body)

    def test_gate_passes_missing_or_broken_is_one_line(self):
        for name, returns in (("返りが無い", fixed_run(**{"plan-review": None})),
                              ("事前審査の指し札が無い", fixed_run()),
                              ("が読めない", fixed_run(**{"plan-review": {"review": str(self.dir / "nowhere" / "review.json")}}))):
            with self.subTest(name):
                _, text, _ = self.build(returns)
                self.assertIn(name, self.section(text, report.DECISIONS_HEADING))
        review = self.put("broken/review.json", {})
        self.put("broken/gate-passes.json", "{壊れた")
        _, text, _ = self.build(fixed_run(**{"plan-review": {"review": review}}))
        self.assertIn("が読めない", self.section(text, report.DECISIONS_HEADING))


class DraftsCase(Base):
    def test_each_stopped_item_gets_a_marked_draft(self):
        """元 DraftsCase.test_each_stopped_item_gets_a_marked_draft: 無人の run で関所が開かなかった問いごとに、下書きの印つきの
        答えの下書き。推しの尾が在れば推しを答えに"""
        review = {"pass": True, "ask_human": True,
                  "questions": ["狭めるか／推し: 通す（continue）——狭めない（理由: 能力を落とさない）", "どの定石に寄せるか"]}
        drafts = runreport.answer_drafts(fixed_run(**{"plan-review": review}), {}, UNATTENDED)
        self.assertEqual(len(drafts), 2, drafts)
        self.assertTrue(all(d["draft"] is True and d["source"] for d in drafts), drafts)
        self.assertEqual(drafts[0]["question"], "狭めるか")
        self.assertIn("狭めない", drafts[0]["text"])
        self.assertEqual(drafts[1]["text"], "")

    def test_world_deviation_drafted_once(self):
        """元 DraftsCase.test_world_deviation_drafted_once: 同じ問いが事前審査と R4 の両方に在っても下書きは 1 行"""
        q = "定石 w-mean から外れてよいか"
        returns = fixed_run(**{"plan-review": {"questions": [q]}}, eyes={**fixed_run()["eyes"], "questions": [q]})
        self.assertEqual(len(runreport.answer_drafts(returns, {}, UNATTENDED)), 1)

    def test_row_with_nothing_still_gets_a_draft_saying_so(self):
        """元 DraftsCase.test_row_with_nothing_still_gets_a_draft_saying_so"""
        drafts = runreport.answer_drafts(fixed_run(**{"plan-review": {"questions": ["どうするか"]}}), {}, UNATTENDED)
        self.assertEqual(drafts[0]["text"], "")
        self.assertIn("書いていない", drafts[0]["note"])

    def test_attended_run_gets_no_gate_item_drafts(self):
        """元 DraftsCase の人の居る run: 関所に人が答えた run は下書きを作らない"""
        returns = fixed_run(**{"plan-review": {"questions": ["どうするか"]}})
        self.assertEqual(runreport.answer_drafts(returns, {"gate-before-fix": {"decision": "approve", "text": ""}},
                                                 {"run_id": RUN}), [])
        self.assertEqual(runreport.answer_drafts(returns, {"gate-before-fix": {"decision": "continue", "text": ""}}, UNATTENDED), [])

    def test_drafts_reach_next_request(self):
        returns = fixed_run(**{"plan-review": {"questions": ["どうするか"]}})
        got, _, _ = self.build(returns, start=UNATTENDED)
        doc = json.loads(pathlib.Path(got["next_request"]).read_text(encoding="utf-8"))
        self.assertEqual(carry.errors(doc, carry.NEXT_SCHEMA), [])
        self.assertEqual([a["question"] for a in doc[carry.ANSWERS]], ["どうするか"])


class GlossaryCase(unittest.TestCase):
    def test_only_terms_in_text(self):
        pack = [{"term": "関所", "definition": "止まる所"}, {"term": "盤面", "definition": "置き場"}]
        sec = runreport.glossary_section("関所で止めた", [{"term": "関所", "definition": "別の定義"}, {"term": "周", "definition": "一巡"}],
                                         pack)
        self.assertIn("- 関所: 止まる所", sec, "同じ語は pack を採る")
        self.assertNotIn("盤面", sec)
        self.assertNotIn("一巡", sec)
        self.assertEqual(runreport.glossary_section("何も無い", [], pack), "")

    def test_pack_terms_come_from_lib(self):
        self.assertTrue(any(t["term"] == "関所" for t in runreport.pack_terms()))


class AcceptCase(Base):
    REPLY = json.dumps({"text": "直した。\n\n## 1. 人が決めること\n\n無い", "terms": []}, ensure_ascii=False)
    PASS = json.dumps({"verdict": "pass", "stops": [], "guessed": [], "decidable": True})
    REDESIGN = json.dumps({"verdict": "redesign-needed", "stops": ["冒頭の 2 行目"], "guessed": [], "decidable": False},
                          ensure_ascii=False)

    def ai(self) -> dict:
        return json.loads((self.out / runreport.AI_FILE).read_text(encoding="utf-8"))

    def test_pass_is_taken(self):
        got = runreport.accept(self.REPLY, self.PASS, out_dir=self.out)
        self.assertEqual(got, {"done": True, "ok": True, "reason": "", "kind": "", "reason_file": ""})
        self.assertTrue(self.ai()["accepted"])
        self.assertEqual(self.ai()["not_passed"], "")

    def test_cold_rejects_twice_then_takes_with_mark(self):
        first = runreport.accept(self.REPLY, self.REDESIGN, out_dir=self.out)
        self.assertEqual((first["done"], first["kind"]), (False, "cold"))
        self.assertIn("冒頭の 2 行目", pathlib.Path(first["reason_file"]).read_text(encoding="utf-8"))
        self.assertFalse(runreport.accept(self.REPLY, self.REDESIGN, out_dir=self.out)["done"])
        third = runreport.accept(self.REPLY, self.REDESIGN, out_dir=self.out)
        self.assertTrue(third["done"] and third["ok"])
        self.assertIn(report_roles.NOT_PASSED, third["reason"])
        self.assertTrue(self.ai()["not_passed"])
        self.assertEqual(self.ai()["rejects"]["report"]["cold"], 2)

    def test_format_and_terms_rejected_first(self):
        bad_cell = json.dumps({"text": "| 項目 |\n|---|\n| 説明の文である。 |"}, ensure_ascii=False)
        self.assertEqual(runreport.accept(bad_cell, self.PASS, out_dir=self.out)["kind"], "format")
        bad_terms = json.dumps({"text": "x", "terms": [{"term": ""}]})
        self.assertEqual(runreport.accept(bad_terms, self.PASS, out_dir=self.out)["kind"], "answer")
        third = runreport.accept("壊れた", self.PASS, out_dir=self.out)
        self.assertTrue(third["done"])
        self.assertFalse(third["ok"])
        self.assertFalse(self.ai()["accepted"], "3 回とも拒めば受け取れなかった訳を残す")


class CollectCase(Base):
    def test_no_ai_file_is_none(self):
        self.assertIsNone(runreport.collect("機械の事実", out_dir=self.out, stamp="run x"))

    def test_taken_reply_becomes_ai_report(self):
        runreport.accept(AcceptCase.REPLY, AcceptCase.PASS, out_dir=self.out)
        path = runreport.collect("- 関所: 開かなかった\n", out_dir=self.out, stamp="works-factory report / run x")
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("works-factory report / run x\n\n直した。"))
        self.assertIn(report_roles.MACHINE_HEADING, text)
        self.assertTrue(text.endswith("- 関所: 開かなかった\n"), "機械の事実は書き換えずに最後に付ける")
        self.assertIn("- 関所:", text.split(report_roles.GLOSSARY_HEADING)[1], "機械の事実に現れる語も定義する")

    def test_not_passed_mark_is_on_top(self):
        for _ in range(report_roles.GIVE_UP_AFTER):
            runreport.accept(AcceptCase.REPLY, AcceptCase.REDESIGN, out_dir=self.out)
        text = runreport.collect("事実", out_dir=self.out, stamp="run x").read_text(encoding="utf-8")
        self.assertTrue(text.split("\n\n")[1].startswith(report_roles.NOT_PASSED))

    def test_given_up_reply_still_reports(self):
        for _ in range(report_roles.GIVE_UP_AFTER):
            runreport.accept("壊れた", AcceptCase.PASS, out_dir=self.out)
        text = runreport.collect("事実", out_dir=self.out, stamp="run x").read_text(encoding="utf-8")
        self.assertIn(report_roles.FAILED_TITLE, text)
        self.assertTrue(text.endswith("事実"))


class ColdBodyCase(unittest.TestCase):
    def test_head_and_glossary_only(self):
        reply = json.dumps({"text": "関所で止めた。\n\n## 1. 人が決めること\n\n- A\n\n## 2. 経緯\n\n長い", "terms": []}, ensure_ascii=False)
        body = runreport.cold_body(reply)
        self.assertIn("関所で止めた", body)
        self.assertNotIn("長い", body)
        self.assertIn(report_roles.GLOSSARY_HEADING, body)

    def test_unreadable_reply_says_so(self):
        self.assertIn("書き手の返答を読めない", runreport.cold_body("壊れた"))


if __name__ == "__main__":
    unittest.main()

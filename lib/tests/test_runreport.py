"""機械の報告と持ち越し・書き手の受け付けと AI の報告（lib/runreport.py）の検査。

報告の頭と答えの下書きの場面は、元の works/tests/test_gate_head.py の ReportHeadCase と works/tests/test_gate_drafts.py の
DraftsCase のうち報告の側の物を、盤面と関所の節の代わりにブロックの返りの入力で書き直した（各試験の docstring に元の名）。
"""
import hashlib
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
import worldmark  # noqa: E402
import outcome  # noqa: E402
import outpurpose  # noqa: E402
import querytest  # noqa: E402
import report  # noqa: E402
import report_roles  # noqa: E402
import runreport  # noqa: E402
import stopby  # noqa: E402
from lib.tests.test_outcome import fixed_run  # noqa: E402
from lib.tests.test_plan_gate import DECIDED, FACE, FORK, FORK_UNIT, NARROW, WORLD_ROW  # noqa: E402

UNATTENDED = {"run_id": "run-1", "unattended": "true"}
UNIT_A, UNIT_B, UNIT_C = ({"id": "a", "paths": ["a.py"], "summary": "狭く直す"}, {"id": "b", "paths": ["b.py"], "summary": "b"},
                          {"id": "c", "paths": ["c.py"], "summary": "c"})
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
        self.assertIn("承認ノード gate-final: stop（request: 止め札）", text)


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

    def test_green_cert_names_suites_and_log(self):
        """元 report.py:1042-1050 の最後のテストの一式の行とログ: test-gate の返りの evidence の先の行から。取れなければ黙らずにその旨"""
        suites = "一式: run-tests（make test）"
        final = self.put("test-gate-final/evidence.md", f"# test-gate（final）\n\n- ok: true\n- 走らせ方: engine・{suites}\n"
                                                        "- ログ: /tmp/x/test.log\n")
        _, text, _ = self.build(fixed_run(**{"test-gate-final": {**fixed_run()["test-gate-final"], "evidence": final}}))
        green = self.section(text, runreport.GREEN_HEADING)
        self.assertIn(f"- 最後のテスト（test-gate-final）の走らせ方: engine・{suites}\n", green)
        self.assertIn("- 最後のテスト（test-gate-final）のログ: /tmp/x/test.log\n", green)
        self.assertIn("- 直す前のテスト（test-gate-base）の走らせ方とログ: 取れない", green)

        fell = self.put("fell/evidence.md", "# test-gate（final）\n\n- ok: false（返す節の中の誤り）\n- 誤り: KeyError: 'by'\n")
        _, text, _ = self.build(fixed_run(**{"test-gate-final": {**fixed_run()["test-gate-final"], "evidence": fell}}))
        green = self.section(text, runreport.GREEN_HEADING)
        self.assertIn("- 最後のテスト（test-gate-final）の走らせ方: 証拠に「走らせ方」の行が無い", green)
        self.assertIn("- 最後のテスト（test-gate-final）のログ: 証拠に「ログ」の行が無い", green)

        _, text, _ = self.build(fixed_run(**{"test-gate-final": {**fixed_run()["test-gate-final"], "evidence": str(self.dir)}}))
        self.assertIn("- 最後のテスト（test-gate-final）の走らせ方とログ: 読めない（", self.section(text, runreport.GREEN_HEADING))

        _, text, _ = self.build(fixed_run(**{"test-gate-base": None, "test-gate-final": None}))
        self.assertNotIn("走らせ方", self.section(text, runreport.GREEN_HEADING))


class TranscriptCase(Base):
    def test_none_transcript_cost_cannot_be_taken(self):
        _, text, _ = self.build()
        self.assertIn(f"{report.COST_HEADING}\n\n- 費用: 取れない", text)

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
            {**done("eyes__r1", "2026-10-12T00:12:00Z", kind="node_error"), "error": "目が落ちた\n詳しい行"},
            start("report__facts", "2026-10-12T00:13:00Z"),
            done("report__facts", "2026-10-12T00:13:30Z", kind="node_error"),
            done("test-gate-final__run", "2026-10-12T00:13:00Z"),
        )
        facts = runreport.transcript_facts(rows, exclude_prefix="report__")
        self.assertEqual(facts["failed"], ["eyes__r1"])
        self.assertEqual(facts["absorbed"], [], "後に始まった節が自分の節だけなら、線は受け止めていない")
        self.assertEqual(facts["retried"], [{"node": "fix__write", "failures": 1, "error": ""}])
        self.assertEqual(facts["cost"], {"judge__diagnose": 0.5, "fix__write": 0.5})
        self.assertNotIn("fix", facts["cost"], "言い直しの行は数えない")
        self.assertEqual(facts["minutes"]["judge__diagnose"], 3.0)
        self.assertEqual(facts["uncosted"]["test-gate-final__run"], 1)
        self.assertEqual(facts["models"], {"judge__diagnose": ["sonnet"]})
        _, text, decided = self.build(transcript=facts)
        self.assertEqual(decided[0], "interrupted")
        self.assertIn("- 費用の合計: $1.0000（途中。", text)
        self.assertIn(f"{report.INTERRUPTED_HEAD}: ノード eyes__r1 が落ちた（誤り: 目が落ちた）", text)
        self.assertIn(f"{report.RETRIED_HEAD}: fix__write（落ちた回 1。最後の誤り: （誤りの文が無い））", text)
        self.assertIn("費用の欄が無い行 1 件", text)
        self.assertIn("- judge__diagnose: sonnet", self.section(text, report.MODEL_HEADING))


    def test_fall_the_line_went_past_is_absorbed_not_interrupted(self):
        """元 report.split_fallen・head_stop: 落ちた後にほかの節が始まった節は受け止めた落ち（止めたかの節に名と誤り、残りに 1 行）で、
        run を途中で終わらせた落ちと分ける。再試行の回と最後の誤りの文も出す"""
        rows = rows_of(
            start("redepth", "2026-10-12T00:00:00Z"),
            {**done("redepth", "2026-10-12T00:01:00Z", kind="node_error"), "error": "深さが読めない\n詳しい行"},
            start("eyes__r1", "2026-10-12T00:02:00Z"),
            done("eyes__r1", "2026-10-12T00:03:00Z"),
            start("fix__write", "2026-10-12T00:04:00Z"),
            {**done("fix__write", "2026-10-12T00:05:00Z", kind="node_error"), "error": "1 回目"},
            {**done("fix__write", "2026-10-12T00:06:00Z", kind="node_error"), "error": "2 回目"},
            done("fix__write", "2026-10-12T00:07:00Z"),
        )
        facts = runreport.transcript_facts(rows)
        self.assertEqual((facts["failed"], facts["absorbed"]), ([], [{"node": "redepth", "error": "深さが読めない\n詳しい行"}]))
        self.assertEqual(facts["retried"], [{"node": "fix__write", "failures": 2, "error": "2 回目"}])
        got = outcome.decide_outcome(fixed_run(), {}, {**{"start_ok": True, "record_problems": []}, "failed": facts["failed"],
                                                       "absorbed": facts["absorbed"]})
        self.assertEqual(got, ("round_limit", ""))
        got = runreport.build(fixed_run(), {}, {}, facts, *got, out_dir=self.out, start={"run_id": RUN}, run_id=RUN)
        text = pathlib.Path(got["report"]).read_text(encoding="utf-8")
        stop = self.section(text, report.STOP_HEADING)
        self.assertIn(f"{report.ABSORBED_HEAD}: redepth（誤り: 深さが読めない）", stop)
        self.assertIn(f"{report.RETRIED_HEAD}: fix__write（落ちた回 2。最後の誤り: 2 回目）", stop)
        self.assertNotIn(report.INTERRUPTED_HEAD, stop)
        self.assertIn(f"{report.ABSORBED_WHERE} redepth: redepth が落ちた", self.section(text, report.DECISIONS_HEADING))


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
        _, text, decided = self.build(fixed_run(fix=fix))
        self.assertEqual(decided[0], "round_limit")
        self.assertEqual(text.splitlines()[3], gatemarks.DECIDE + f"1 件——直す義務に戻せなかった単位 1 件（下の「{report.DECISIONS_HEADING.lstrip('# ')}」）",
                         "round_limit の残りの同じ単位の行を重ねて数えない")
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
        self.assertIn("修正前の承認ノードが聞かずに通した行（plan-review）: 1 件", body)
        self.assertIn("小さい直し", body)

    def test_gate_passes_missing_or_broken_is_one_line(self):
        for name, returns in (("出力が無い", fixed_run(**{"plan-review": None})),
                              ("事前審査のポインタが無い", fixed_run()),
                              ("が読めない", fixed_run(**{"plan-review": {"review": str(self.dir / "nowhere" / "review.json")}}))):
            with self.subTest(name):
                _, text, _ = self.build(returns)
                self.assertIn(name, self.section(text, report.DECISIONS_HEADING))
        review = self.put("broken/review.json", {})
        self.put("broken/gate-passes.json", "{壊れた")
        _, text, _ = self.build(fixed_run(**{"plan-review": {"review": review}}))
        self.assertIn("が読めない", self.section(text, report.DECISIONS_HEADING))


    def test_converge_lines_missing_is_quiet_and_broken_is_one_line(self):
        review = self.put("plan-review/review.json", {})
        self.put("plan-review/gate-passes.json", [])
        _, text, _ = self.build(fixed_run(**{"plan-review": {**fixed_run()["plan-review"], "review": review}}))
        self.assertNotIn("事前審査の壁打ち", text)
        self.put("plan-review/gate.json", "{壊れた")
        _, text, _ = self.build(fixed_run(**{"plan-review": {**fixed_run()["plan-review"], "review": review}}))
        self.assertIn("事前審査の壁打ちの行: 無い（", self.section(text, report.DECISIONS_HEADING))


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
        """元 test_gate_drafts.DraftsCase.test_world_deviation_drafted_once: 決め手の揃った narrows の行が在っても、無人の run で修正前の
        関所が通さなかった同じ世界の解の外れの下書きは 1 行だけ（定石の行は判定の world、外れは計画の欄 structure から）"""
        world = self.put("judge/world.jsonl", json.dumps(WORLD_ROW, ensure_ascii=False))
        plan = self.put("plan/plan-fields.json", {"round": 1, "fields": [{"structure": [
            {"world": "w-mean", "deviation": "呼び手の都合で 0 を返す形に寄せたい、と考えた"}]}]})
        self.put("plan/p2.fix_plan.json", {"plan": [{"unit_keys": ["u1"], "narrows": [{**NARROW, **DECIDED}]}]})
        line = worldmark.gate_line(WORLD_ROW, {"world": "w-mean", "deviation": "呼び手の都合で 0 を返す形に寄せたい、と考えた"})
        review = {"pass": True, "ask_human": True, "questions": [f"修正案 1 の{line}（人に聞く訳: 依頼を出どころにした外れ）"]}
        returns = fixed_run(judge={**fixed_run()["judge"], "world": world}, plan={**fixed_run()["plan"], "plan": plan},
                            **{"plan-review": review}, eyes={**fixed_run()["eyes"], "questions": review["questions"]})
        drafts = runreport.answer_drafts(returns, {}, UNATTENDED)
        self.assertEqual(len(drafts), 1, drafts)
        self.assertIn("w-mean", drafts[0]["question"])
        self.assertIn("呼び手の都合", drafts[0]["note"], "推しの無い外れは、外れの訳と世界の解を材料に置く")

    def test_recommend_of_the_narrow_becomes_the_answer(self):
        """元 gatemarks._gate_draft: 修正案の狭める行の推し（recommend）が答えの下書きになる"""
        plan = self.put("plan/plan-fields.json", {"round": 1, "fields": []})
        rec = {"answer": "continue", "note": "例外にそろえる", "why": "呼び手が既に例外を捕まえている"}
        self.put("plan/p2.fix_plan.json", {"plan": [{"unit_keys": ["u1"], "narrows": [{**NARROW, "recommend": rec}]}]})
        q = f"修正案 1 が狭める能力: {NARROW['what']}——{NARROW['why']}（世界の解: 役が書いていない）"
        returns = fixed_run(plan={**fixed_run()["plan"], "plan": plan}, **{"plan-review": {"ask_human": True, "questions": [q]}})
        drafts = runreport.answer_drafts(returns, {}, UNATTENDED)
        self.assertEqual(drafts[0]["question"], f"修正案 1 が狭める能力: {NARROW['what']}——{NARROW['why']}")
        self.assertTrue(drafts[0]["text"].startswith("continue: 例外にそろえる"))
        self.assertIn("recommend", drafts[0]["source"])

    def test_held_ledger_question_is_drafted_in_attended_run_too(self):
        """元 test_held_ledger_question_gets_its_push_as_draft_keyed_by_the_question と利用者の声 10-09 の C4: 保留のままの台帳の問いは、
        人の居る run でも key を question にした推しの下書きになる。関所で通した問いは下書きにしない"""
        judgment = self.put("judge/judgment.json", {"questions": [FORK, {**FORK, "key": "q-done", "status": "resolved"}]})
        returns = fixed_run(judge={**fixed_run()["judge"], "judgment": judgment})
        drafts = runreport.answer_drafts(returns, {}, {"run_id": RUN})
        self.assertEqual([(d["question"], d["text"]) for d in drafts], [(FORK["key"], "例外——呼び手が既に例外を捕まえている")])
        passed = {"gate-before-fix": {"decision": "continue", "text": ""}}
        self.assertEqual(len(runreport.answer_drafts(returns, passed, {"run_id": RUN})), 1, "関所が聞いていない問いは答えていない")
        returns = fixed_run(judge=returns["judge"], **{"plan-review": {**fixed_run()["plan-review"], "questions": [gatemarks.ask_text(FORK)]}})
        self.assertEqual(runreport.answer_drafts(returns, passed, {"run_id": RUN}), [])
        held = {"gate-before-fix": {"decision": "continue", "text": f"保留: {FORK['key']}"}}
        self.assertEqual(len(runreport.answer_drafts(returns, held, {"run_id": RUN})), 1)
        returns = fixed_run(judge=returns["judge"])
        _, text, _ = self.build(returns)
        self.assertIn("保留にしたままの問い 1 件", text.splitlines()[3])

    def test_unmeasured_material_draft_carries_its_reason(self):
        judgment = self.put("judge/judgment.json", {})
        self.put("judge/materials.json", {"parallel_pr": {"status": "not_run", "reason": "forge が無い"}})
        returns = fixed_run(judge={**fixed_run()["judge"], "judgment": judgment})
        drafts = runreport.answer_drafts(returns, {}, {"run_id": RUN})
        self.assertEqual(drafts[0]["question"], "parallel_pr")
        self.assertIn("forge が無い", drafts[0]["note"])
        answered = {"run_id": RUN, "answers": [{"question": "parallel_pr", "text": "無い", "command": "gh pr list", "output": "[]"}]}
        self.assertEqual(runreport.answer_drafts(returns, {}, answered), [])
        unmeasured = {"run_id": RUN, "answers": [{"question": "parallel_pr", "text": "無いはず"}]}
        self.assertEqual(runreport.answer_drafts(returns, {}, unmeasured), [], "依頼の答えが当たった素材は下書きにしない（命令と出力が無くても）")

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

    def test_no_narrow_and_face_rows_give_their_marks(self):
        """元 gatemarks._gate_draft: 推しの無い修正案の狭める行は狭めない案（no_narrow）を、事前審査の人に回す種類の穴は穴の行の
        決め手を、材料として note に置く"""
        plan = self.put("plan/plan-fields.json", {"round": 1, "fields": []})
        self.put("plan/p2.fix_plan.json", {"plan": [{"unit_keys": ["u1"], "narrows": [{**NARROW, "no_narrow": "例外にそろえて呼び手を直す"}]}]})
        review = self.put("plan-review/review.json", {"faces": [{**FACE, "no_narrow": "上限を変えずに足す"},
                                                               {**FACE, "key": "見た目", "kind": "style"}]})
        narrow = f"修正案 1 が狭める能力: {NARROW['what']}——{NARROW['why']}"
        face = f"事前審査の穴 [regression] {FACE['key']}: {FACE['why']}"
        returns = fixed_run(plan={**fixed_run()["plan"], "plan": plan},
                            **{"plan-review": {"review": review, "questions": [narrow, face, f"事前審査の穴 [style] 見た目: {FACE['why']}"]}})
        drafts = runreport.answer_drafts(returns, {}, UNATTENDED)
        self.assertEqual([d["text"] for d in drafts], ["", "", ""])
        self.assertIn("狭めない案: 例外にそろえて呼び手を直す", drafts[0]["note"])
        self.assertIn(gatemarks.NO_NARROW, drafts[0]["source"])
        self.assertIn("狭めない案: 上限を変えずに足す", drafts[1]["note"])
        self.assertIn("決め手の欄が無い", drafts[2]["source"], "人に回さない種類の穴は事前審査の行に結ばない")

    def test_final_gate_r4_questions_are_drafted_unless_passed(self):
        """最後の関所が通さなかった無人の run は、独立の目 R4 の問いごとに下書き。関所が通した run は作らない"""
        eyes = {**fixed_run()["eyes"], "questions": ["守りを触ってよいか／推し: 通す（continue）——触らない（理由: 守りは別の PR）"]}
        returns = fixed_run(eyes=eyes)
        drafts = runreport.answer_drafts(returns, {}, UNATTENDED)
        self.assertEqual([(d["question"], d["text"]) for d in drafts], [("守りを触ってよいか", "通す（continue）——触らない（理由: 守りは別の PR）")])
        self.assertEqual(runreport.answer_drafts(returns, {"gate-final": {"decision": "approve", "text": ""}}, UNATTENDED), [])

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
        self.assertTrue(any(t["term"] == "承認ノード" for t in runreport.pack_terms()))


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
        path = runreport.collect("- 承認ノード: 開かなかった\n", out_dir=self.out, stamp="works-factory report / run x")
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("works-factory report / run x\n\n直した。"))
        self.assertIn(report_roles.MACHINE_HEADING, text)
        self.assertIn(f"{report_roles.COLD_REJECTS_LINE} 0 回", text)
        self.assertTrue(text.endswith("- 承認ノード: 開かなかった\n"), "機械の事実の行は書き換えずに最後に付ける")
        self.assertIn("- 承認ノード:", text.split(report_roles.GLOSSARY_HEADING)[1], "機械の事実に現れる語も定義する")

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
        self.assertIn(f"report の返答が {report_roles.GIVE_UP_AFTER} 回とも受け付けで拒まれた（最後の拒否: ", text)
        self.assertTrue(text.endswith("事実"))

    def test_decisions_section_is_one_place(self):
        """書き手の頭の「人が決めること」の後ろに機械の事実が付いても、その見出しの節は 1 つ（機械の数えの見出しを言い換え、1 段下げる）"""
        runreport.accept(AcceptCase.REPLY, AcceptCase.PASS, out_dir=self.out)
        got, machine, _ = self.build()
        text = runreport.collect(machine, out_dir=self.out, stamp="run x").read_text(encoding="utf-8")
        heads = [line for line in text.splitlines() if line.startswith("#") and report_roles.DECISIONS_HEAD in line]
        self.assertEqual(heads, ["## 1. 人が決めること"])
        self.assertIn(f"#{runreport.MACHINE_DECISIONS}", text)
        self.assertIn(f"#{report.STOP_HEADING}", text)


class ColdBodyCase(unittest.TestCase):
    def test_head_and_glossary_only(self):
        reply = json.dumps({"text": "承認ノードで止めた。\n\n## 1. 人が決めること\n\n- A\n\n## 2. 経緯\n\n長い", "terms": []}, ensure_ascii=False)
        body = runreport.cold_body(reply)
        self.assertIn("承認ノードで止めた", body)
        self.assertNotIn("長い", body)
        self.assertIn(report_roles.GLOSSARY_HEADING, body)

    def test_unreadable_reply_says_so(self):
        self.assertIn("書き手の返答を読めない", runreport.cold_body("壊れた"))


class CarryCase(Base):
    """次の依頼と前の失敗に運ぶ物（元 report.next_request・prior_failures のうち返りから読める物）"""

    def test_asked_conflicts_parked_groups_and_rejudge_reach_next_request(self):
        rows = [{"unit_key": "u1", "between": ["brief", "判定"], "ruling": {"decision": "ask_human", "text": "人が決める"}},
                {"unit_key": "u2", "between": ["案"], "ruling": {"decision": "fix_plan_item", "text": "案を直す", "plan_units": ["u2"]},
                 "replan": "gave_up", "replan_why": "直せなかった"}]
        fix = {**fixed_run()["fix"], "conflicts": self.put("fix/conflicts.json", {"items": rows}), "objection": "判定が違う",
               "units": [{"unit_id": "u1", "status": "not_done", "reason": "人待ち"}],
               "groups": [{"group_id": "g1", "unit_ids": ["u3"], "returned": True, "reason": ""},
                          {"group_id": "g2", "unit_ids": ["u4"], "returned": False, "reason": "親の木とぶつかった"}]}
        returns = fixed_run(fix=fix, rejudge={**fixed_run()["judge"], "rejudge_verdict": "退ける"})
        got, text, decided = self.build(returns)
        self.assertEqual(decided[0], "needs_human")
        doc = json.loads(pathlib.Path(got["next_request"]).read_text(encoding="utf-8"))
        texts = {r["where"]: r["text"] for r in doc["findings"]}
        self.assertIn("食い違いの申し出を人に回した——直さずに残した。裁定の文: 人が決める。名指し brief, 判定", texts["u1"])
        self.assertIn("案の直し: 直せなかった", texts["u2"])
        self.assertNotIn("修正 u1", texts, "人に回した単位の修正の行は、その単位の行が持つ")
        self.assertIn("親の木とぶつかった", texts["組 g2"])
        self.assertEqual(texts[report.REJUDGE_WHERE], "再審: 退ける（異議: 判定が違う）")
        self.assertIn("修正の段は 1 単位（u3）を受け、1 単位（u4）を止めて持ち越した", text.splitlines()[2])
        self.assertIn("再審の結果: 退ける（異議: 判定が違う）", self.section(text, report.DECISIONS_HEADING))

    def test_objection_without_rejudge_is_carried(self):
        returns = fixed_run(fix={**fixed_run()["fix"], "objection": "判定が違う"})
        self.assertIn({"where": runreport.REJUDGE_LEFT_WHERE, "text": "判定が違う"}, runreport.next_request(returns, []))

    def test_refix_objection_is_left_even_after_a_rejudge(self):
        """2 度目の修正の異議（線の fixed の refix_objection）は再審の後に出るので、再審の結果に関わらず再審されずに残った異議"""
        fix = {**fixed_run()["fix"], "objection": "判定が違う", "refix_objection": "u2 の判定も違う"}
        returns = fixed_run(fix=fix, rejudge={**fixed_run()["judge"], "rejudge_verdict": "退ける"})
        self.assertEqual(runreport.rejudge_lines(returns)[-1], "再審されずに残った異議: u2 の判定も違う")
        self.assertIn({"where": runreport.REJUDGE_LEFT_WHERE, "text": "u2 の判定も違う"}, runreport.next_request(returns, []))
        alone = fixed_run(fix={**fixed_run()["fix"], "refix_objection": "u2 の判定も違う"})
        self.assertEqual(runreport.rejudge_lines(alone), ["再審されずに残った異議: u2 の判定も違う"])

    def test_plan_give_up_is_a_prior_failure(self):
        returns = fixed_run(plan={"ready": False, "stop_reason": "", "depth": []}, fix=None)
        rows = runreport.prior_failures(returns, [])
        self.assertEqual([r["where"] for r in rows], [runreport.PLAN_GAVE_UP_WHERE])


    def test_rejudge_changes_and_opened_units(self):
        """元 report._rejudge_changes・_rejudge_next: 再審で足された・消えた・変わった単位を、異議に名指されたかで分けて並べ、
        再審が足して修正の段が受けていない単位は次の依頼に運ぶ"""
        judge = {**fixed_run()["judge"], "units": [UNIT_A, UNIT_B]}
        rejudge = {**judge, "units": [{**UNIT_A, "summary": "広く直す"}, UNIT_C], "rejudge_verdict": "一部採る"}
        fix = {**fixed_run()["fix"], "objection": "a の範囲が狭い"}
        returns = fixed_run(judge=judge, rejudge=rejudge, fix=fix)
        self.assertEqual(runreport.rejudge_changes(returns), [
            '再審で異議に名指された単位が変わった: a の summary: "狭く直す" → "広く直す"',
            "再審で争点でない単位が消えた: b", "再審で争点でない単位が足された: c"])
        self.assertEqual(runreport.rejudge_opened(returns), ["c"])
        got, text, _ = self.build(returns)
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn("  - 再審が直す単位にした（この run では直していない——次の run に渡す）: c", body)
        self.assertIn("再審で争点でない単位が消えた: b", body)
        doc = json.loads(pathlib.Path(got["next_request"]).read_text(encoding="utf-8"))
        self.assertIn({"where": "c", "text": "c（再審が直す単位にした——この run では直していない）"}, doc["findings"])
        fix = {**fix, "units": [*fix["units"], {"unit_id": "c", "status": "fixed", "reason": ""}]}
        self.assertEqual(runreport.rejudge_opened(fixed_run(judge=judge, rejudge=rejudge, fix=fix)), [], "修正の段が受けた単位は運ばない")
        self.assertEqual(runreport.rejudge_changes(fixed_run(judge=judge)), [])

    def test_rejudge_lowered_block_units_are_shown_and_carried(self):
        """元 rejudge.diff_units の lowered と report.rejudge_lines・_rejudge_next: 再審が block から下げた単位を拒まずに見せ、
        次の依頼に運ぶ。judgment の label・disposition の変化は再審の変化の行にも出る"""
        before = self.put("judge/judgment.json", {"units": [{"key": "a", "label": "block"}, {"key": "b", "label": "block"},
                                                            {"key": "c", "label": "suggest", "disposition": "defer"}]})
        after = self.put("rejudge/judgment.json", {"units": [{"key": "a", "label": "suggest", "disposition": "defer"},
                                                             {"key": "b", "label": "block"},
                                                             {"key": "c", "label": "suggest", "disposition": "do-now"}]})
        judge = {**fixed_run()["judge"], "judgment": before}
        returns = fixed_run(judge=judge, rejudge={**judge, "judgment": after, "rejudge_verdict": "一部採る"})
        self.assertEqual(runreport.rejudge_lowered(returns), [("a", "suggest")])
        self.assertEqual(runreport.rejudge_changes(returns), [
            '再審で争点でない単位が変わった: a の label: "block" → "suggest"',
            '再審で争点でない単位が変わった: a の disposition: null → "defer"',
            '再審で争点でない単位が変わった: c の disposition: "defer" → "do-now"'])
        got, text, _ = self.build(returns)
        self.assertIn("  - 再審が block から suggest に下げた（拒まずに見せる——人が確かめる）: a",
                      self.section(text, report.DECISIONS_HEADING))
        doc = json.loads(pathlib.Path(got["next_request"]).read_text(encoding="utf-8"))
        self.assertIn({"where": "a", "text": "a（再審が block から suggest に下げた——人が確かめる）"}, doc["findings"])
        self.assertEqual(runreport.rejudge_lowered(fixed_run(judge=judge)), [], "再審が無ければ下げた単位も無い")

    def test_unproven_queries_are_listed_from_the_current_judgment(self):
        """元 querytest.unproven_lines: 今の判定の開いた単位（block か do-now の suggest）のうち class_query に例の無い物を、
        例を出せない理由か NO_EXAMPLES つきで並べる。再審が在れば再審の judgment を読む"""
        units = [{"key": "a", "label": "block", "class_query": {"pattern": "x", "examples_unavailable": "生成物なので行が無い"}},
                 {"key": "b", "label": "suggest", "disposition": "do-now", "class_query": {"pattern": "y"}},
                 {"key": "c", "label": "suggest", "disposition": "defer", "class_query": {"pattern": "z"}},
                 {"key": "d", "label": "block", "class_query": {"pattern": "w", "hits": ["w"]}}]
        judgment = self.put("rejudge/judgment.json", {"units": units})
        judge = {**fixed_run()["judge"], "judgment": self.put("judge/judgment.json", {})}
        returns = fixed_run(judge=judge, rejudge={**judge, "judgment": judgment})
        self.assertEqual(runreport.unproven_lines(returns), [
            f"{querytest.UNPROVEN_HEAD}: 2 件", "  - a: 生成物なので行が無い", f"  - b: {querytest.NO_EXAMPLES}"])
        _, text, _ = self.build(returns)
        self.assertIn(f"{querytest.UNPROVEN_HEAD}: 2 件", self.section(text, report.DECISIONS_HEADING))
        self.assertEqual(runreport.unproven_lines(fixed_run(judge=judge)), [])

    def test_waiting_replan_rows_are_carried_only_when_interrupted(self):
        """元 next_request の conflict.waiting の行: 途中で落ちた run は案の直しを待つ行を未完了で運び、終わった run は諦めた行として
        人に回す"""
        rows = [{"unit_key": "u2", "between": ["案"], "ruling": {"decision": "fix_plan_item", "text": "案を直す", "plan_units": ["u2"]},
                 "replan": "waiting"}]
        fix = {**fixed_run()["fix"], "conflicts": self.put("fix/conflicts.json", {"items": rows})}
        cut = runreport.next_request(fixed_run(fix=fix), [], closed=False)
        self.assertEqual(cut, [{"where": "u2", "text": f"u2（{outcome.PENDING_WHY}。裁定の文: 案を直す。名指し 案。{outcome.HELD_WORK_KEPT}）"}])
        closed = runreport.next_request(fixed_run(fix=fix), [])
        self.assertIn(f"案の直し: {outcome.CLOSE_WHY}", closed[0]["text"])
        facts = runreport.transcript_facts([start("fix__write", "2026-10-12T00:00:00Z"),
                                            done("fix__write", "2026-10-12T00:01:00Z", kind="node_error")])
        got, text, decided = self.build(fixed_run(fix=fix), transcript=facts)
        self.assertEqual(decided[0], "interrupted")
        self.assertIn("人に回した食い違いの申し出 0 件", self.section(text, report.DECISIONS_HEADING).replace(": ", " "))
        doc = json.loads(pathlib.Path(got["next_request"]).read_text(encoding="utf-8"))
        self.assertIn(outcome.PENDING_WHY, doc["findings"][-1]["text"])

    def test_line_stop_words_are_prior_failures(self):
        """元 prior_failures の受け付けの最後の拒否の行の代わり: 止めの語で止めた段の語と意味（計画の諦めは計画の行が持つ）"""
        returns = fixed_run(judge={**fixed_run()["judge"], "ready": False, "stop_reason": stopby.PURPOSE})
        rows = runreport.prior_failures(returns, [])
        self.assertEqual(rows, [{"where": f"{runreport.STOPPED_WHERE} judge",
                                 "text": f"{stopby.PURPOSE}（{stopby.REASONS['purpose']}）。受け付けの最後の拒否の本文は返りに無い"}])
        returns = fixed_run(plan={"ready": False, "stop_reason": stopby.FIX, "depth": []}, fix=None)
        self.assertEqual([r["where"] for r in runreport.prior_failures(returns, [])], [runreport.PLAN_GAVE_UP_WHERE])
        returns = fixed_run(fix={**fixed_run()["fix"], "stop_reason": stopby.CONFLICT})
        self.assertEqual(runreport.prior_failures(returns, []), [], "人待ちの語は前の失敗でない")


class LedgerCase(Base):
    """問いの台帳の保留の行と答えた行（元 gatemarks.held_lines・answered_lines）"""

    def returns(self, *questions, units=None, materials=None, review=()):
        judgment = self.put("judge/judgment.json", {"questions": list(questions)})
        if materials is not None:
            self.put("judge/materials.json", materials)
        judge = {**fixed_run()["judge"], "judgment": judgment, "units": units if units is not None else [{"id": FORK_UNIT}]}
        return fixed_run(judge=judge, **{"plan-review": {**fixed_run()["plan-review"], "questions": list(review)}})

    def test_held_line_names_units_left_and_answer_key(self):
        state = runreport.ledger_state(self.returns(FORK), {}, {"run_id": RUN})
        self.assertEqual([line for _, line in state["held"]],
                         [gatemarks._ledger_line(FORK, skip=[FORK_UNIT]) + f'／{gatemarks.ANSWER_KEY_HEAD}: "{FORK["key"]}"'])
        self.assertIn(f"／答えが無いと直さない単位: {FORK_UNIT}", state["held"][0][1])

    def test_answer_key_is_the_material_name_when_it_binds_only_this(self):
        q = {**FORK, "origin": "", "key": "parallel_pr: 重なりを確かめる"}
        state = runreport.ledger_state(self.returns(q, materials={"parallel_pr": {"status": "not_run"}}), {}, {"run_id": RUN})
        self.assertTrue(state["held"][0][1].endswith(f'{gatemarks.ANSWER_KEY_HEAD}: "parallel_pr"'), state["held"][0][1])

    def test_answered_lines_name_where_the_answer_came_from(self):
        other = {**FORK, "key": "q-other", "origin": "x"}
        returns = self.returns(FORK, other, units=[{"id": FORK_UNIT}, {"id": "x"}], review=[gatemarks.ask_text(other)])
        answers = [{"question": FORK["key"], "text": "例外", "command": "pytest -k mean", "output": "1 passed"}]
        state = runreport.ledger_state(returns, {"gate-before-fix": {"decision": "continue", "text": ""}}, {"answers": answers})
        self.assertEqual(state["held"], [])
        self.assertEqual(state["answered"], [
            gatemarks._ledger_line(FORK, "・" + gatemarks.answer_note(answers[0])),
            gatemarks._ledger_line(other, gatemarks.GATE_CONTINUED)])
        self.assertIn("人が手元で実行: `pytest -k mean`", state["answered"][0])

    def test_answer_hitting_two_questions_answers_neither(self):
        twin = {**FORK, "key": "q-twin", "status": "escalate"}
        returns = self.returns(FORK, twin)
        state = runreport.ledger_state(returns, {}, {"answers": [{"question": FORK_UNIT, "text": "例外"}]})
        self.assertEqual(len(state["held"]), 2)

    def test_answers_that_answer_nothing_are_named(self):
        """元 gatemarks.unmatched_answer_lines: 当たる問いが無い・複数に当たる・決着済みの問いに当たった依頼の答えは、答えた扱いに
        せず黙って捨てもしない"""
        done = {**FORK, "key": "q-done", "origin": "z", "status": "resolved"}
        twin = {**FORK, "key": "q-twin", "status": "escalate"}
        answers = [{"question": "q-none", "text": "a"}, {"question": FORK_UNIT, "text": "b"}, {"question": "q-done", "text": "c"}]
        state = runreport.ledger_state(self.returns(FORK, twin, done), {}, {"answers": answers})
        self.assertEqual(state["answered"], [])
        self.assertEqual(state["unmatched"], [
            "依頼の答えに当たる問いが台帳に無い（判定が問いを立てなかったか、字が違う）: q-none——依頼者の答え: a",
            f"依頼の答えが複数の問いに当たった: {FORK_UNIT} → q-empty-mean・q-twin（どれにも答えた扱いにしない。question に問いの key を書く）——依頼者の答え: b",
            "決着済みの問いに当たった答え: q-done → q-done（resolved）（答えは直しに使わない）——依頼者の答え: c"])

    def test_answered_but_unit_gone_is_held(self):
        returns = self.returns(FORK, units=[], review=[gatemarks.ask_text(FORK)])
        state = runreport.ledger_state(returns, {"gate-before-fix": {"decision": "continue", "text": ""}}, {"run_id": RUN})
        self.assertEqual(state["held"], [(None, gatemarks.unreturned_line(FORK["key"], FORK_UNIT))])

    def test_material_answer_lines(self):
        materials = {"ci": {"status": "awaiting_human"}, "lint": {"status": "not_run"}}
        answers = [{"question": "ci", "text": "緑", "command": "make ci", "output": "ok"}, {"question": "lint", "text": "通るはず"}]
        state = runreport.ledger_state(self.returns(materials=materials), {}, {"answers": answers})
        self.assertEqual(state["answered"], [
            f"素材 ci（awaiting_human）: {gatemarks.HAND_CHECKED}。残りに数えない——{gatemarks.answer_note(answers[0])}",
            f"素材 lint（not_run）: command と output が無いので測りの代わりにせず、測れていないまま残りに数える——{gatemarks.answer_note(answers[1])}"])
        got, text, decided = self.build(self.returns(materials=materials), start={"run_id": RUN, "answers": answers})
        self.assertEqual(decided[0], "fixed_needs_check")
        self.assertIn(f"{outcome.MATERIAL_WHERE} lint", self.section(text, report.DECISIONS_HEADING))
        self.assertNotIn(f"{outcome.MATERIAL_WHERE} ci:", self.section(text, report.DECISIONS_HEADING))


class LinesCase(Base):
    """機械の報告の節に取り戻した行（判定・計画・目・封じの返りと、その隣のファイルから）"""

    def judge_with(self, **beside) -> dict:
        judgment = self.put("judge/judgment.json", {})
        for name, doc in beside.items():
            self.put(f"judge/{name}", doc)
        return {**fixed_run()["judge"], "judgment": judgment}

    def test_verify_pr_excluded_and_premise_hypotheses(self):
        verify = {"units": [{"key": "u1", "state": "checked", "verdict": "not_root", "real_root": "b.py", "why": "呼び手の側"}],
                  "synergy": {"state": "checked", "duplicates": [], "order": []}}
        excluded = {"node": "p0.parallel_pr", "excluded": [{"pr": 7, "file": "a.py", "start": 1, "end": 3, "why": "重なる"}]}
        premises = {"constraints": [{"kind": "仮説", "text": "a.py の上限は 10 と見た"}]}
        request = self.put("start/request.json", {"findings": [{"where": "a.py", "text": "上限", "measured": "10 で落ちる"}]})
        judge = self.judge_with(**{"judge-verify.json": verify, "pr-excluded.json": excluded, "premises.json": premises})
        _, text, _ = self.build(fixed_run(judge=judge), start={"run_id": RUN, "request_file": request})
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn("根本でない: u1（本当の根: b.py。呼び手の側）", body)
        self.assertIn("並行 PR #7 と重なるので外した範囲: a.py:1-3（重なる）", body)
        self.assertIn("依頼の実測を測り直せなかった（前提は仮説）: a.py——a.py の上限は 10 と見た", body)

    def test_broken_verify_notes_say_so(self):
        judge = self.judge_with(**{"judge-verify.json": "{壊れた"})
        _, text, _ = self.build(fixed_run(judge=judge))
        self.assertIn("判定の単位の裏取り: 申し送りが読めない", text)

    def test_conflict_counts_line(self):
        rows = [{"unit_key": "u1", "kind": "not_red", "ruling": {"decision": "fix_code_as", "text": "こう"}}]
        fix = {**fixed_run()["fix"], "conflicts": self.put("fix/conflicts.json", {"items": rows})}
        _, text, _ = self.build(fixed_run(fix=fix))
        self.assertIn("- 食い違いの申し出: 1 件（裁定の内訳。括弧は記録の名: テストの直しを許す（fix_test_scope）0・コードをこう直す（fix_code_as）1", text)
        self.assertIn("not_red 1", text)

    def test_inner_words_in_added_lines(self):
        diff = self.put("fix/diff.patch", "diff --git a/x.tf b/x.tf\n--- a/x.tf\n+++ b/x.tf\n@@ -1,1 +1,2 @@\n keep\n+# この単位の作業ツリー\n")
        _, text, _ = self.build(fixed_run(fix={**fixed_run()["fix"], "diff": diff}))
        self.assertIn(f"{report.INNER_WORDS_HEAD}: 1 件", text)
        self.assertIn("x.tf:2（この単位・作業ツリー）", text)
        self.assertEqual(runreport.inner_word_lines(diff, lambda w: True), [], "対象が前から使う語は数えない")

    def test_protected_hits_from_eyes_and_merge_reason(self):
        eyes = {**fixed_run()["eyes"], "protected_hits": ["ci/deploy.yml"]}
        seal = {"mode": "seal", "ok": True, "protected_hits": ["ci/deploy.yml"]}
        apply_ = {"mode": "apply", "ok": False, "reason": "hash が封じた物と違う"}
        _, text, decided = self.build(fixed_run(eyes=eyes, **{"merge-seal": seal, "merge-apply": apply_}))
        self.assertEqual(decided, ("stopped_by_line", "merge-apply:not-ok"))
        self.assertIn("守りのパスに当たった差分 1 件", text.splitlines()[3])
        self.assertIn("merge-apply が ok でない: hash が封じた物と違う", self.section(text, report.STOP_HEADING))

    def test_protected_hits_from_eyes_only(self):
        """封じの返りが当たりを持たない（封じが走らない・欄が無い）run も、独立の目の当たりだけで人が決めることに数える"""
        eyes = {**fixed_run()["eyes"], "protected_hits": ["ci/deploy.yml", "ci/deploy.yml"]}
        _, text, _ = self.build(fixed_run(eyes=eyes))
        self.assertIn("守りのパスに当たった差分 1 件", text.splitlines()[3])
        self.assertIn("ci/deploy.yml", self.section(text, report.DECISIONS_HEADING))

    def test_seal_not_ok_says_why(self):
        seal = {"mode": "seal", "ok": False, "reason": "指紋が今の作業ツリーと違う"}
        _, text, decided = self.build(fixed_run(**{"merge-seal": seal, "merge-apply": None}))
        self.assertEqual(decided, ("stopped_by_line", "merge-seal:not-ok"))
        self.assertIn("merge-seal が ok でない: 指紋が今の作業ツリーと違う", self.section(text, report.STOP_HEADING))
        _, text, _ = self.build(fixed_run(**{"merge-seal": {"mode": "seal", "ok": False}, "merge-apply": None}))
        self.assertIn("merge-seal が ok でない: 訳の記録が無い", self.section(text, report.STOP_HEADING))

    def test_where_lists_sealed_and_applied_diff(self):
        merge = {"merge-seal": {"mode": "seal", "ok": True, "diff": "merge/sealed.diff"},
                 "merge-apply": {"mode": "apply", "ok": True, "diff": "merge/apply.diff"}}
        _, text, _ = self.build(fixed_run(**merge))
        body = self.section(text, report.WHERE_HEADING)
        self.assertIn("- 封じた差分（merge-seal.diff）: merge/sealed.diff", body)
        self.assertIn("- 置いた差分（merge-apply.diff）: merge/apply.diff", body)

    def test_world_rows_keep_mark_and_versus(self):
        world = self.put("judge/world.jsonl", json.dumps({**WORLD_ROW, "basis": "knowledge"}, ensure_ascii=False))
        _, text, _ = self.build(fixed_run(judge={**fixed_run()["judge"], "world": world}))
        body = self.section(text, report.WORLD_HEADING)
        self.assertIn(f"（{worldmark.NOT_WEB}）", body)
        self.assertIn("依頼の解き方「空の並びは 0 を返す」は定石と違う", body)
        self.assertIn("- 類 1", body)

    def test_world_null_says_the_stage_gave_nothing(self):
        """元 worldmark.report_lines の「世界の解の段が落ちた（行なしで進んだ）」: 判定が返ったのに world が null"""
        _, text, _ = self.build(fixed_run(judge={**fixed_run()["judge"], "world": None}))
        self.assertIn("世界の解の行が無い（判定の返りの world が null", self.section(text, report.WORLD_HEADING))
        _, text, _ = self.build(fixed_run(judge=None), )
        self.assertNotIn(report.WORLD_HEADING, text)

    def test_structure_rows_and_after(self):
        design = self.put("plan/design.jsonl", json.dumps({"unit_id": "u1", "verdict": "汚れる", "faces": [], "evidence": [],
                                                           "reason": "責務が割れる"}, ensure_ascii=False))
        state = self.put("plan/structure-state.json", {"status": "ok", "reason": "", "design_file": design, "wall_s": 3})
        after = self.put("eyes/structure-after.json", {"status": "ok", "reason": "", "deviations": [],
                                                       "after": {"changed": ["a.py"], "tables": [], "new_names": []}})
        _, text, _ = self.build(fixed_run(plan={**fixed_run()["plan"], "structure": state},
                                          eyes={**fixed_run()["eyes"], "structure_after": after}))
        body = self.section(text, report.STRUCTURE_HEADING)
        self.assertIn("u1: 汚れる", body)
        self.assertIn("直しの後の実測", body)

    def test_entry_gate_words(self):
        _, text, _ = self.build(start={"run_id": RUN, "final_gate": "when_needed"})
        self.assertIn("- 最後の承認ノード: when_needed", self.section(text, report.ENTRY_HEADING))

    def test_entry_lists_ran_and_skipped_stages_and_baseline(self):
        """入口の節に走った段・飛ばされた段・直す前のテストの色と赤の原因（元 report.py の入口の行）"""
        base = {"mode": "base", "ok": True, "green": False, "red_cause": "inherited"}
        _, text, _ = self.build(fixed_run(**{"test-gate-base": base}))
        body = self.section(text, report.ENTRY_HEADING)
        self.assertIn("- 走った段: test-gate-base・judge・plan・", body)
        self.assertIn("- 飛ばされた・返りの無い段: rejudge・replan・replan-review\n", body)
        self.assertIn("直す前のテスト: 赤", body)
        self.assertIn("赤の原因 inherited", body)

        _, text, _ = self.build(fixed_run(**{"test-gate-base": None}))
        body = self.section(text, report.ENTRY_HEADING)
        self.assertNotIn("直す前のテスト", body)
        self.assertIn("- 飛ばされた・返りの無い段: test-gate-base・rejudge・replan・replan-review", body)

    def test_outside_purpose_rows_and_wrong_name(self):
        """目的の外の所見は節に 1 件ずつ、人が決めることの節に件数と置き場の 1 行（次の run に渡す物の行の前）。名の違う控えは読まない"""
        p = self.put("judge/out-of-purpose.json", {"rounds": {"1": [{"source": "P1", "why_outside": "目的の外の所見",
                                                                    "found": [{"where": "a.py:1", "text": "x"},
                                                                              {"where": "b.py:2", "text": "y"}]}]}})
        _, text, _ = self.build(fixed_run(judge={**fixed_run()["judge"], "out_of_purpose": p}))
        outside = self.section(text, report.OUTSIDE_HEADING)
        self.assertIn(f"{outpurpose.REPORT_HEAD}: 2 件", outside)
        self.assertIn("  - a.py:1（出どころ: P1・", outside)
        lines = self.section(text, report.DECISIONS_HEADING).splitlines()
        count = [i for i, x in enumerate(lines) if x.startswith(f"- {outpurpose.COUNT_HEAD}")]
        carried = [i for i, x in enumerate(lines) if x.startswith("- 次の run に渡す物:")]
        self.assertEqual(len(count), 1, lines)
        self.assertLess(count[0], carried[0])
        for word in ("2 件", carry.NEXT_REQUEST_FILE, report.OUTSIDE_HEADING.removeprefix("## ")):
            self.assertIn(word, lines[count[0]])

        other = self.put("judge/other.json", {})
        _, text, _ = self.build(fixed_run(judge={**fixed_run()["judge"], "out_of_purpose": other}))
        self.assertIn(f"の名が {outpurpose.FILE} でない（読まなかった）", self.section(text, report.OUTSIDE_HEADING))
        self.assertNotIn(outpurpose.COUNT_HEAD, self.section(text, report.DECISIONS_HEADING))

    def test_every_line_is_a_bullet(self):
        """元 build の行の組み方: 節の行は「- 」か、字下げした内訳の行"""
        fix = {**fixed_run()["fix"], "units": [{"unit_id": "u1", "status": "given_up", "reason": "通らない"}]}
        _, text, _ = self.build(fixed_run(fix=fix))
        body = text.split(f"{report.DECISIONS_HEADING}\n\n", 1)[1]
        for line in body.splitlines():
            if line and not line.startswith("#"):
                self.assertTrue(line.startswith(("- ", "  ")), line)


class StampCase(Base):
    def test_stamp_names_workflow_run_and_version(self):
        wf = self.put("works-factory-report.yaml", "name: x\n")
        sha = hashlib.sha256(b"name: x\n").hexdigest()[:12]
        start = {"versions": {"line": "ab" * 32}}
        self.assertEqual(runreport.stamp("run-9", wf, 2, start), f"works-factory-report / run run-9 / 周 2 / グラフの版 {sha} / メイングラフの版 abababababab")
        self.assertEqual(runreport.stamp("", wf, None, start), f"works-factory-report / run — / 周 — / グラフの版 {sha} / メイングラフの版 abababababab")
        self.assertIn("グラフの版 読めない（FileNotFoundError）", runreport.stamp("run-9", self.dir / "none.yaml", None, start))

    def test_stamp_names_line_version(self):
        """元 report_roles.stamp の works のメイングラフの版: 始めの記録の versions.line の頭 12 字。無ければ黙らずにその旨"""
        wf = self.put("works-factory-report.yaml", "name: x\n")
        sha = hashlib.sha256(b"name: x\n").hexdigest()[:12]
        got = runreport.stamp("run-9", wf, 2, {"versions": {"line": "ab" * 32}})
        self.assertEqual(got, f"works-factory-report / run run-9 / 周 2 / グラフの版 {sha} / メイングラフの版 abababababab")
        for start in ({"versions": {}}, {}, {"versions": {"line": ""}}):
            with self.subTest(start=start):
                self.assertTrue(runreport.stamp("run-9", wf, None, start).endswith(" / メイングラフの版 始めの記録に無い（versions.line）"))
        self.assertTrue(runreport.stamp("run-9", wf, None, None).endswith(" / メイングラフの版 読めない（始めの記録が読めない）"))

    def test_pack_terms_raise_when_unreadable(self):
        broken = self.dir / "glossary.json"
        broken.write_text("{壊れた", encoding="utf-8")
        saved = runreport.PACK_TERMS
        runreport.PACK_TERMS = broken
        self.addCleanup(setattr, runreport, "PACK_TERMS", saved)
        with self.assertRaises(ValueError):
            runreport.pack_terms()
        runreport.PACK_TERMS = self.dir / "none.json"
        self.assertEqual(runreport.pack_terms(), [])


if __name__ == "__main__":
    unittest.main()

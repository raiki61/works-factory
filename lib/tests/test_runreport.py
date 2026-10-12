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
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import carry  # noqa: E402
import gatemarks  # noqa: E402
import worldmark  # noqa: E402
import conflict  # noqa: E402
import fixbeside  # noqa: E402
import fixboard  # noqa: E402
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

    def build(self, returns=None, gates=None, typed=None, transcript=None, start=None, problems=(), line=None):
        returns = fixed_run() if returns is None else returns
        gates = gates or {}
        decided = outcome.decide_outcome(returns, gates, {"start_ok": True, "record_problems": list(problems),
                                                          "failed": (transcript or {}).get("failed", []),
                                                          "stops": list(((line or {}).get("stops") or {}).items()),
                                                          "eyes_skip": ((line or {}).get("redepth") or {}).get("skip_optional")})
        got = runreport.build(returns, gates, typed or {}, transcript, *decided, out_dir=self.out, start=start or {"run_id": RUN},
                              problems=problems, run_id=RUN, line=line)
        return got, pathlib.Path(got["report"]).read_text(encoding="utf-8"), decided

    def fix_place(self, name="fix", accept_trace=(), **result) -> str:
        """修正の段の置き場（fix/<name>/）に diff と隣の約束のファイル（fixbeside.write。result は組の子の結果の欄）と、fix の collect が
        いつも置く受け付けの行（accept_trace）・レンズの集め役の事実を置き、diff のパスを返す"""
        folder = self.dir / "fix" / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "fix.diff").write_text("diff --git a/x b/x\n", encoding="utf-8")
        fixbeside.write(folder, [result])
        fixboard.write_json(folder / fixboard.ACCEPT_TRACE_FILE, list(accept_trace))
        fixboard.lens_collector(folder, True, "")
        return str(folder / "fix.diff")

    def with_fix(self, *diffs, **over):
        return fixed_run(fix={**fixed_run()["fix"], "diff": diffs[-1], "diffs": list(diffs)}, **over)

    @staticmethod
    def rejudge_lines(returns):
        return runreport.rejudge_lines(returns, runreport.rejudge_exit(returns))

    @staticmethod
    def next_request(returns, left, closed=True):
        return runreport.next_request(returns, left, closed, beside=runreport.fix_beside(returns),
                                      exit_doc=runreport.rejudge_exit(returns)[0])

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

    def test_build_refuses_off_contract_carries(self):
        """2 つとも照らしてから書く: 次の依頼か前の失敗のどちらかが約束に合わなければ ValueError で、どちらのファイルも置かない。
        次の依頼は前の失敗の行を同じ形で抱えるので、前の失敗だけが合わない場面は PRIOR_SCHEMA の照らしだけを誤らせて作る"""
        eyes = {**fixed_run()["eyes"], "r2": {"status": "redesign-needed", "reason": "独立設計と食い違う"}}
        fix = {**fixed_run()["fix"], "units": [{"unit_id": "u1", "status": "given_up", "reason": "受け付けが 3 回拒んだ"}]}
        real = carry.errors
        only_prior = mock.patch.object(carry, "errors", side_effect=lambda doc, name: ["合わない"] if name == carry.PRIOR_SCHEMA
                                       else real(doc, name))
        off_next = mock.patch.object(runreport, "next_request", return_value=[{"where": 3, "text": "where が字でない"}])
        for word, patch in (("次の依頼", off_next), ("前の失敗", only_prior)):
            with self.subTest(off=word), patch:
                with self.assertRaisesRegex(ValueError, word):
                    self.build(fixed_run(eyes=eyes, fix=fix))
                self.assertFalse((self.out / carry.NEXT_REQUEST_FILE).exists())
                self.assertFalse((self.out / carry.PRIOR_FAILURES_FILE).exists())

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
        """元 report.split_fallen・head_stop: 線が受け止めると宣言した段（optional）の中で落ちた節は受け止めた落ち（止めたかの節に名と
        誤り、残りに 1 行）で、run を途中で終わらせた落ちと分ける。再試行の回と最後の誤りの文も出す"""
        rows = rows_of(
            start("world-judge", "2026-10-12T00:00:00Z"),
            {**done("world-judge", "2026-10-12T00:01:00Z", kind="node_error"), "error": "網が無い\n詳しい行"},
            start("eyes__r1", "2026-10-12T00:02:00Z"),
            done("eyes__r1", "2026-10-12T00:03:00Z"),
            start("fix__write", "2026-10-12T00:04:00Z"),
            {**done("fix__write", "2026-10-12T00:05:00Z", kind="node_error"), "error": "1 回目"},
            {**done("fix__write", "2026-10-12T00:06:00Z", kind="node_error"), "error": "2 回目"},
            done("fix__write", "2026-10-12T00:07:00Z"),
        )
        facts = runreport.transcript_facts(rows, optional=("world-judge", "eyes__"))
        self.assertEqual((facts["failed"], facts["absorbed"]), ([], [{"node": "world-judge", "error": "網が無い\n詳しい行"}]))
        self.assertEqual(facts["retried"], [{"node": "fix__write", "failures": 2, "error": "2 回目"}])
        got = outcome.decide_outcome(fixed_run(), {}, {**{"start_ok": True, "record_problems": []}, "failed": facts["failed"],
                                                       "absorbed": facts["absorbed"]})
        self.assertEqual(got, ("round_limit", ""))
        got = runreport.build(fixed_run(), {}, {}, facts, *got, out_dir=self.out, start={"run_id": RUN}, run_id=RUN)
        text = pathlib.Path(got["report"]).read_text(encoding="utf-8")
        stop = self.section(text, report.STOP_HEADING)
        self.assertIn(f"{report.ABSORBED_HEAD}: world-judge（誤り: 網が無い）", stop)
        self.assertIn(f"{report.RETRIED_HEAD}: fix__write（落ちた回 2。最後の誤り: 2 回目）", stop)
        self.assertNotIn(report.INTERRUPTED_HEAD, stop)
        self.assertIn(f"{report.ABSORBED_WHERE} world-judge: world-judge が落ちた",
                      self.section(text, report.DECISIONS_HEADING))

    def test_fall_outside_declared_optional_stays_interrupted(self):
        """R82（元 works/tests/test_report_head.py::AbsorbedFailureCase.test_fix_lane_fall_still_interrupts_beside_absorbed_eye :149）:
        宣言の無い段の落ちは、後に線の節が始まっても（実行基盤が依存の無い枝を先へ進めただけでも）途中で終わった落ちに数え、宣言した段の
        落ちだけを受け止めた落ちにする。宣言が無い（optional が空）run は落ちを全部途中で終わった落ちに数える"""
        rows = rows_of(
            start("fix__write", "2026-10-12T00:00:00Z"),
            {**done("fix__write", "2026-10-12T00:01:00Z", kind="node_error"), "error": "修正の筋が落ちた"},
            start("eyes__r1", "2026-10-12T00:02:00Z"),
            {**done("eyes__r1", "2026-10-12T00:03:00Z", kind="node_error"), "error": "目が落ちた"},
            start("collect", "2026-10-12T00:04:00Z"),
            done("collect", "2026-10-12T00:05:00Z"),
        )
        facts = runreport.transcript_facts(rows, optional=("eyes__",))
        self.assertEqual(facts["failed"], ["fix__write"])
        self.assertEqual(facts["absorbed"], [{"node": "eyes__r1", "error": "目が落ちた"}])
        got = outcome.decide_outcome(fixed_run(), {}, {"start_ok": True, "record_problems": [], "failed": facts["failed"],
                                                       "absorbed": facts["absorbed"]})
        self.assertEqual(got, ("interrupted", "fix__write:node-error"))
        self.assertEqual(runreport.transcript_facts(rows)["failed"], ["fix__write", "eyes__r1"])


class DecisionsCase(Base):
    def test_residue_count_is_always_shown(self):
        """R20（元 report.always_rows の「残り: N 件」:1588-1591）: 残りの件数の行を結末に依らず人が決めることの節に出す（0 件も）。
        残りが在れば、結果が無い目の注記を添える"""
        _, text, decided = self.build()
        self.assertEqual(decided[0], "fixed")
        self.assertIn(f"- {runreport.RESIDUE_HEAD}: 0 件（", self.section(text, report.DECISIONS_HEADING))
        eyes = {**fixed_run()["eyes"], "r3": {"status": "redesign-needed", "reason": "崩れる"}}
        _, text, _ = self.build(fixed_run(eyes=eyes))
        line = next(x for x in self.section(text, report.DECISIONS_HEADING).splitlines() if x.startswith(f"- {runreport.RESIDUE_HEAD}"))
        self.assertIn(": 1 件（", line)
        self.assertIn(runreport.MISSING_EYE_NOTE, line)

    def test_accepted_breaks_are_counted_as_decision(self):
        """R23・L-W20・F427（元 works/tests/test_report_head.py::HandoffCase :830-867）: 修正役が人に回した物（壊すと分かって通した理由。
        fix の出力の handoffs。線の fixed が 1 回目と 2 度目の修正の分を合わせる）を人が決めることに数え、冒頭 2 行目の件数と節の 1 件 1 行に出す"""
        handoffs = ["u1: 壊すと分かって通した——古い呼び手が壊れる", "u2: 壊すと分かって通した——既定が変わる"]
        returns = self.with_fix(self.fix_place("fix"), self.fix_place("refix-run"))
        _, text, _ = self.build({**returns, "fix": {**returns["fix"], "handoffs": handoffs}})
        self.assertTrue(text.splitlines()[3].startswith(gatemarks.DECIDE + "2 件"), text.splitlines()[3])
        self.assertIn(f"{fixboard.HANDOFF_HEAD} 2 件", text.splitlines()[3])
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn(f"- {fixboard.HANDOFF_HEAD}: 2 件\n  - u1: 壊すと分かって通した——古い呼び手が壊れる\n"
                      "  - u2: 壊すと分かって通した——既定が変わる", body)

    def test_always_rows_name_clean_lens_and_not_run(self):
        """R38・F329（元 works/tests/test_report.py::HeadCase.test_always_rows_show_zero_and_not_run :606）: clean が消したファイル・
        レンズ・仕組みの異常を結末に依らず人が決めることの節に出し、0 件・走らせていない・読めないを分ける"""
        import lens
        diff = self.fix_place("fix")
        folder = pathlib.Path(diff).parent
        fixboard.write_json(folder / "fix-removed.json", {"removed": []})
        lens.write_routes(folder, [{"lens": "silent-failure-hunter", "agent": "a", "go": True}])
        lens.collect(folder, {"silent-failure-hunter": {"findings": []}})
        fixbeside.write(folder, [{}])
        _, text, _ = self.build(self.with_fix(diff))
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn("- clean が消したファイル（fix）: 0 本", body)
        self.assertIn("- レンズの発見: 差分の審査が走っていないので採った・採らなかったは調べていない・形の誤りで捨てた 0 件・落ちたレンズ 0 件（fix）", body)
        self.assertIn(f"- {fixbeside.ANOMALY_LINE}", body)
        (folder / "fix-removed.json").unlink()
        (folder / fixboard.LENSES_FILE).write_text("{", encoding="utf-8")
        _, text, _ = self.build(self.with_fix(diff))
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn("- clean が消したファイル（fix）: 走らせていない", body)
        self.assertIn(f"- 修正の控え: 修正の控え {folder / fixboard.LENSES_FILE} が読めない", body)
        _, text, _ = self.build()
        self.assertIn("- clean が消したファイル: 走らせていない（修正の段が無い run）", self.section(text, report.DECISIONS_HEADING))

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
        review = {"pass": True, "ask_human": True, "questions": [gatemarks.question_row("fork", "どちらに寄せるか／推し: 通す（continue）——小さい方（理由: 速い）")]}
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
        self.assertIn("事前審査の壁打ちの行（plan-review）: 無い（", self.section(text, report.DECISIONS_HEADING))


class DraftsCase(Base):
    def test_each_stopped_item_gets_a_marked_draft(self):
        """元 DraftsCase.test_each_stopped_item_gets_a_marked_draft: 無人の run で関所が開かなかった問いごとに、下書きの印つきの
        答えの下書き。推しの尾が在れば推しを答えに"""
        review = {"pass": True, "ask_human": True,
                  "questions": [gatemarks.question_row("regression", "狭めるか／推し: 通す（continue）——狭めない（理由: 能力を落とさない）"),
                                gatemarks.question_row("world", "どの定石に寄せるか")]}
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
        review = {"pass": True, "ask_human": True, "questions": [gatemarks.question_row("world", f"修正案 1 の{line}（人に聞く訳: 依頼を出どころにした外れ）")]}
        returns = fixed_run(judge={**fixed_run()["judge"], "world": world}, plan={**fixed_run()["plan"], "plan": plan},
                            **{"plan-review": review}, eyes={**fixed_run()["eyes"], "questions": gatemarks.row_texts(review["questions"])})
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
        returns = fixed_run(plan={**fixed_run()["plan"], "plan": plan}, **{"plan-review": {"ask_human": True, "questions": [gatemarks.question_row("regression", q)]}})
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
        passed = {"gate-before-fix": {"decision": "continue", "text": "", "asked": [gatemarks.ask_text(FORK)]}}
        self.assertEqual(runreport.answer_drafts(returns, passed, {"run_id": RUN}), [])
        held = {"gate-before-fix": {"decision": "continue", "text": f"保留: {FORK['key']}", "asked": [gatemarks.ask_text(FORK)]}}
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
        drafts = runreport.answer_drafts(fixed_run(**{"plan-review": {"questions": [gatemarks.question_row("regression", "どうするか")]}}), {}, UNATTENDED)
        self.assertEqual(drafts[0]["text"], "")
        self.assertIn("書いていない", drafts[0]["note"])

    def test_attended_run_gets_no_gate_item_drafts(self):
        """元 DraftsCase の人の居る run: 関所に人が答えた run は下書きを作らない"""
        returns = fixed_run(**{"plan-review": {"questions": [gatemarks.question_row("regression", "どうするか")]}})
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
                            **{"plan-review": {"review": review, "questions": [gatemarks.question_row(k, t) for k, t in (
                                ("regression", narrow), ("regression", face), ("style", f"事前審査の穴 [style] 見た目: {FACE['why']}"))]}})
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
        returns = fixed_run(**{"plan-review": {"questions": [gatemarks.question_row("regression", "どうするか")]}})
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

    def rejudged(self, before, after, objection, verdicts=("退ける",)):
        """判定と再審の返り（judgment の指し札の先）と、判定のブロックの書き手（judge_accept.diff_units・rejudge_collect）が再審の judgment の
        隣に書く rejudge-diff.json・rejudge-exit.json"""
        import judge_accept
        rdir = self.dir / "rejudge"
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / judge_accept.REJUDGE_BEFORE).write_text(json.dumps({"units": before, "objection": objection,
                                                                    "numbered_keys": [u["key"] for u in before]}), encoding="utf-8")
        judge = {**fixed_run()["judge"], "judgment": self.put("judge/judgment.json", {"units": before})}
        rejudge = {**judge, "judgment": self.put("rejudge/judgment.json", {"units": after}), "rejudge_verdict": verdicts[-1]}
        rows = [{"round": 1, "pass": judge_accept.REJUDGE_ROLE, "verdict": v,
                 **judge_accept.diff_units(before, after, objection, [u["key"] for u in before])} for v in verdicts]
        self.put(f"rejudge/{judge_accept.REJUDGE_DIFF}", rows)
        judge_accept.rejudge_collect(rdir)
        return judge, rejudge

    def test_failed_lens_is_carried_as_rerun(self):
        """R39・F329（元 report.lens_next_items）: 修正の diff の隣のレンズの控えで落ちたレンズを、次の依頼の findings に「再実行の要あり」
        で運び、報告の「未確認のレンズ」の節に局所レビューの分の後に並べる"""
        import lens
        diff = self.fix_place("fix")
        folder = pathlib.Path(diff).parent
        lens.write_routes(folder, [{"lens": "silent-failure-hunter", "agent": "a", "go": True}])
        lens.collect(folder, {})
        fixbeside.write(folder, [{}])
        got, text, _ = self.build(self.with_fix(diff))
        doc = json.loads(pathlib.Path(got["next_request"]).read_text(encoding="utf-8"))
        rows = [r for r in doc["findings"] if r["where"] == "レンズ silent-failure-hunter"]
        self.assertEqual(len(rows), 1)
        self.assertIn("再実行の要あり", rows[0]["text"])
        self.assertIn("- silent-failure-hunter: 落ちた（レンズのノードの出口が無い（落ちたか走らなかった））",
                      self.section(text, report.UNSEEN_LENS_HEADING))

    def test_refix_declared_and_second_fixed_holes_are_carried(self):
        """R73・F312（元 report.next_request の手直しの行と branch_rows）: 手直しの返答の handled の declared と 2 回目の fixed を、枝の
        名札つきで次の依頼の findings に載せ、穴の名札と手直しの結果の行を報告の人が決めることの節に出す"""
        diff = self.fix_place("fix")
        folder = pathlib.Path(diff).parent
        doc = {"ties": {"1": [{"key": "穴1", "from": "p3.delta_review", "where": "stats.py", "branches": ["item:1"], "via": ["path"],
                               "held": ""}], "2": "ValueError: 組めない"},
               "handled": {"1": [{"key": "穴1", "handled": "declared", "how": "仕様どおり", "files": ["stats.py"]}],
                           "2": [{"key": "穴2", "handled": "fixed", "how": "分母を直した", "files": ["stats.py"]}]}}
        (folder / fixbeside.DELTA_HOLES_FILE).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        got, text, _ = self.build(self.with_fix(diff))
        findings = json.loads(pathlib.Path(got["next_request"]).read_text(encoding="utf-8"))["findings"]
        self.assertIn({"where": "stats.py", "text": "穴1（手直しが declared で残した穴: 仕様どおり）（枝: 項目 1）"}, findings)
        self.assertIn({"where": "stats.py", "text": "穴2（手直し 2 回目が fixed と言ったが、3 回目の審査は無い——検算が要る: 分母を直した）"},
                      findings)
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn(f"- {fixbeside.branch_head(1)}: 1 件（", body)
        self.assertIn("  - 穴1: 項目 1", body)
        self.assertIn(f"- {fixbeside.branch_head(2)}: 組めない（ValueError: 組めない）", body)
        self.assertIn("  - 穴1: 直さずに残すと申告した（declared）——仕様どおり", body)

    def test_rejudge_passes_and_verdicts_are_listed(self):
        """R76・やる事 2: 再審の行は再審の judgment の隣の rejudge-exit.json（判定のブロックが書く）から、往復の数と答えの並びを出す
        （元 report._settled_rounds・rejudge_lines）。出口が読めない再審は 1 行で名指す"""
        units = [{"key": "a", "label": "block", "disposition": "fix"}]
        judge, rejudge = self.rejudged(units, units, "a は違う", verdicts=("一部採る", "退ける"))
        fix = {**fixed_run()["fix"], "objection": "a は違う"}
        lines = self.rejudge_lines(fixed_run(judge=judge, rejudge=rejudge, fix=fix))
        self.assertEqual(lines[0], "再審の結果（2 往復）: 一部採る・退ける（異議: a は違う）")
        (self.dir / "rejudge" / report.REJUDGE_EXIT).unlink()
        lines = self.rejudge_lines(fixed_run(judge=judge, rejudge=rejudge, fix=fix))
        self.assertTrue(lines[0].startswith(f"再審の記録が読めない（再審の出口 {report.REJUDGE_EXIT} が無い"), lines)

    def test_asked_conflicts_parked_groups_and_rejudge_reach_next_request(self):
        rows = [{"unit_key": "u1", "between": ["brief", "判定"], "ruling": {"decision": "ask_human", "text": "人が決める"}},
                {"unit_key": "u2", "between": ["案"], "ruling": {"decision": "fix_plan_item", "text": "案を直す", "plan_units": ["u2"]},
                 "replan": "gave_up", "replan_why": "直せなかった"}]
        fix = {**fixed_run()["fix"], "conflicts": self.put("fix/conflicts.json", {"items": rows}), "objection": "判定が違う",
               "units": [{"unit_id": "u1", "status": "not_done", "reason": "人待ち"}],
               "groups": [{"group_id": "g1", "unit_ids": ["u3"], "returned": True, "reason": ""},
                          {"group_id": "g2", "unit_ids": ["u4"], "returned": False, "reason": "親の木とぶつかった"}]}
        judge, rejudge = self.rejudged([{"key": "a", "label": "block"}], [{"key": "a", "label": "block"}], "判定が違う")
        returns = fixed_run(fix=fix, judge=judge, rejudge=rejudge)
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
        self.assertIn("再審の結果（1 往復）: 退ける（異議: 判定が違う）", self.section(text, report.DECISIONS_HEADING))

    def test_objection_without_rejudge_is_carried(self):
        returns = fixed_run(fix={**fixed_run()["fix"], "objection": "判定が違う"})
        self.assertIn({"where": runreport.REJUDGE_LEFT_WHERE, "text": "判定が違う"}, self.next_request(returns, []))

    def test_refix_objection_is_rejudged_with_the_first(self):
        """L-D42: 2 度目の修正の異議は、1 回目の異議とつないだ線の fixed の objection で 2 度目の修正の後の再審に渡る（元
        works/darkfactory/darkfactory.yaml:827）。再審の答えが在れば再審されずに残った異議に数えず、再審の無い run は両方が残る"""
        fix = {**fixed_run()["fix"], "objection": "判定が違う\nu2 の判定も違う"}
        returns = fixed_run(fix=fix, rejudge={**fixed_run()["judge"], "rejudge_verdict": "退ける"})
        self.assertEqual([x for x in self.rejudge_lines(returns) if x.startswith("再審されずに残った異議")], [])
        self.assertNotIn(runreport.REJUDGE_LEFT_WHERE, [r["where"] for r in self.next_request(returns, [])])
        alone = self.rejudge_lines(fixed_run(fix=fix))
        self.assertEqual(len(alone), 1)
        self.assertTrue(alone[0].startswith("再審されずに残った異議: 判定が違う") and "u2 の判定も違う" in alone[0], alone)

    def test_plan_give_up_is_a_prior_failure(self):
        returns = fixed_run(plan={"ready": False, "stop_reason": "", "depth": []}, fix=None)
        rows = runreport.prior_failures(returns, [], {})
        self.assertEqual([r["where"] for r in rows], [runreport.PLAN_GAVE_UP_WHERE])


    def test_rejudge_changes_and_opened_units(self):
        """元 report._rejudge_changes・_rejudge_next: 再審で足された・消えた・変わった単位（rejudge-diff.json の changed）を、異議に
        名指されたかで分けて並べ、再審が開いた単位（rejudge-exit.json の new_open_units）で修正の段が受けていない物は次の依頼に運ぶ"""
        before = [{"key": "a", "label": "block", "disposition": "fix"}, {"key": "b", "label": "nit", "disposition": "later"}]
        after = [{"key": "a", "label": "block", "disposition": "later"}, {"key": "c", "label": "block", "disposition": "fix"}]
        judge, rejudge = self.rejudged(before, after, "a の範囲が狭い", verdicts=("一部採る",))
        fix = {**fixed_run()["fix"], "objection": "a の範囲が狭い"}
        returns = fixed_run(judge=judge, rejudge=rejudge, fix=fix)
        self.assertEqual(runreport.rejudge_changes(returns), [
            '再審（rejudge）で異議に名指された単位が変わった: a の disposition: "fix" → "later"',
            "再審（rejudge）で争点でない単位が消えた: b", "再審（rejudge）で争点でない単位が足された: c"])
        self.assertEqual(runreport.rejudge_opened(returns, runreport.rejudge_exit(returns)[0]), ["c"])
        got, text, _ = self.build(returns)
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn("  - 再審が直す単位にした（この run では直していない——次の run に渡す）: c", body)
        self.assertIn("再審（rejudge）で争点でない単位が消えた: b", body)
        doc = json.loads(pathlib.Path(got["next_request"]).read_text(encoding="utf-8"))
        self.assertIn({"where": "c", "text": "c（再審が直す単位にした——この run では直していない）"}, doc["findings"])
        fix = {**fix, "units": [*fix["units"], {"unit_id": "c", "status": "fixed", "reason": ""}]}
        returns = fixed_run(judge=judge, rejudge=rejudge, fix=fix)
        self.assertEqual(runreport.rejudge_opened(returns, runreport.rejudge_exit(returns)[0]), [], "修正の段が受けた単位は運ばない")
        self.assertEqual(runreport.rejudge_changes(fixed_run(judge=judge)), [])

    def test_rejudge_lowered_block_units_are_shown_and_carried(self):
        """元 rejudge.diff_units の lowered と report.rejudge_lines・_rejudge_next: 再審が block から下げた単位（rejudge-exit.json の
        lowered）を今のラベルつきで拒まずに見せ、次の依頼に運ぶ"""
        before = [{"key": "a", "label": "block"}, {"key": "b", "label": "block"}]
        after = [{"key": "a", "label": "suggest", "disposition": "defer"}, {"key": "b", "label": "block"}]
        judge, rejudge = self.rejudged(before, after, "異議", verdicts=("一部採る",))
        returns = fixed_run(judge=judge, rejudge=rejudge)
        self.assertEqual(runreport.rejudge_lowered(returns, runreport.rejudge_exit(returns)[0]), [("a", "suggest")])
        got, text, _ = self.build(returns)
        self.assertIn("  - 再審が block から suggest に下げた（拒まずに見せる——人が確かめる）: a",
                      self.section(text, report.DECISIONS_HEADING))
        doc = json.loads(pathlib.Path(got["next_request"]).read_text(encoding="utf-8"))
        self.assertIn({"where": "a", "text": "a（再審が block から suggest に下げた——人が確かめる）"}, doc["findings"])
        self.assertEqual(runreport.rejudge_lowered(fixed_run(judge=judge), None), [], "再審が無ければ下げた単位も無い")

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
        cut = self.next_request(fixed_run(fix=fix), [], closed=False)
        self.assertEqual(cut, [{"where": "u2", "text": f"u2（{outcome.PENDING_WHY}。裁定の文: 案を直す。名指し 案。{conflict.HELD_WORK_KEPT}）"}])
        closed = self.next_request(fixed_run(fix=fix), [])
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
        rows = runreport.prior_failures(returns, [], {})
        self.assertEqual(rows, [{"where": f"{runreport.STOPPED_WHERE} judge",
                                 "text": f"{stopby.PURPOSE}（{stopby.REASONS['purpose']}）。{runreport.NO_REJECT}"}])
        returns = fixed_run(plan={"ready": False, "stop_reason": stopby.FIX, "depth": []}, fix=None)
        self.assertEqual([r["where"] for r in runreport.prior_failures(returns, [], {})], [runreport.PLAN_GAVE_UP_WHERE])
        returns = fixed_run(fix={**fixed_run()["fix"], "stop_reason": stopby.CONFLICT})
        self.assertEqual(runreport.prior_failures(returns, [], {}), [], "人待ちの語は前の失敗でない")
        line = {"stops": {"ask-final": stopby.LINE_SCRIPT}}
        rows = runreport.prior_failures(fixed_run(), [], runreport.outcome_facts({}, {}, line))
        self.assertEqual([r["where"] for r in rows], [f"{runreport.STOPPED_WHERE} ask-final"],
                         "simplify F6: メイングラフのノードの止めの語も、結末と同じ facts から前の失敗に載る")


    def test_last_reject_text_is_a_prior_failure(self):
        """R78（元 report._accept_last_files・prior_failures :713・:732-749）: 止めの語で止めた段の置き場（返りの指し札と同じフォルダの
        下）の受け付けの最後の拒否の本文（拒否の控え rejects-<役>.json の最後の行か reject-*.md・reject-*.txt の一番新しい物）を、前の失敗の
        行の文に載せる（lib/rolekit.last_reject）"""
        import os
        import rolekit
        judgment = self.put("judge/judgment.json", {})
        self.put("judge/rejects-purpose.json", [{"at": "t1", "reason": "1 回目の拒否"}, {"at": "t2", "reason": "目的の文が\n空同然"}])
        returns = fixed_run(judge={**fixed_run()["judge"], "ready": False, "stop_reason": stopby.PURPOSE, "judgment": judgment})
        rows = runreport.prior_failures(returns, [], {})
        self.assertEqual(rows[0]["text"], f"{stopby.PURPOSE}（{stopby.REASONS['purpose']}）。受け付けの最後の拒否: 目的の文が 空同然")
        later = self.put("judge/r1/reject-3.txt", "計画の欄が足りない")
        os.utime(later, (4_000_000_000, 4_000_000_000))
        self.assertEqual(rolekit.last_reject(pathlib.Path(judgment).parent), "計画の欄が足りない")
        self.assertEqual(rolekit.last_reject(self.dir / "nowhere"), "")


class LedgerCase(Base):
    """問いの台帳の保留の行と答えた行（元 gatemarks.held_lines・answered_lines）"""

    def returns(self, *questions, units=None, materials=None, review=(), judged=None):
        """判定の返りの units は開いた単位だけ。judgment.json の units（judged。無ければ返りの単位を block で）は全部の単位"""
        units = units if units is not None else [{"id": FORK_UNIT}]
        judged = judged if judged is not None else [{"key": u["id"], "label": u.get("label", "block")} for u in units]
        judgment = self.put("judge/judgment.json", {"questions": list(questions), "units": judged})
        if materials is not None:
            self.put("judge/materials.json", materials)
        judge = {**fixed_run()["judge"], "judgment": judgment, "units": units}
        return fixed_run(judge=judge, **{"plan-review": {**fixed_run()["plan-review"],
                                                        "questions": [gatemarks.question_row("fork", q) for q in review]}})

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
        gate = {"decision": "continue", "text": "", "asked": [gatemarks.ask_text(other)]}
        state = runreport.ledger_state(returns, {"gate-before-fix": gate}, {"answers": answers})
        self.assertEqual(state["held"], [])
        self.assertEqual(state["answered"], [
            gatemarks._ledger_line(FORK, "・" + gatemarks.answer_note(answers[0])),
            gatemarks._ledger_line(other, gatemarks.GATE_CONTINUED)])
        self.assertIn("人が手元で実行: `pytest -k mean`", state["answered"][0])

    def test_answered_question_on_a_closed_unit_is_not_held(self):
        """code F1: 答えた問いの出どころが判定に在るが開いていない単位（suggest・defer）でも、修正の段はその単位を直す義務に戻すので
        （gatemarks.returned。fix は judgment.json の全部の単位を読む）、報告も judgment.json の単位で「直す単位に入れられなかった」と
        言わず、最後の関所と同じ held_lines を出す"""
        q = {**FORK, "key": "q1", "origin": "u2", "depends": []}
        returns = self.returns(q, units=[{"id": "u1"}],
                               judged=[{"key": "u1", "label": "block"}, {"key": "u2", "label": "suggest", "disposition": "defer"}])
        state = runreport.ledger_state(returns, {}, {"run_id": RUN, "answers": [{"question": "q1", "text": "直す"}]})
        self.assertEqual(state["held"], [])
        self.assertEqual(len(state["answered"]), 1)

    def test_unread_hold_is_named_in_the_head(self):
        """P238・L-G31: 修正前の関所の答えの文が「保留: q-typo」（台帳の key を拾えない）の時、報告の冒頭に「読めなかった保留」の行が
        在り、問いは答えたものとして扱う（直す義務は変えない）"""
        gate = {"decision": "continue", "text": "保留: q-typo", "asked": [gatemarks.ask_text(FORK)]}
        returns = self.returns(FORK)
        state = runreport.ledger_state(returns, {"gate-before-fix": gate}, {"run_id": RUN})
        self.assertEqual(state["held"], [])
        lines, _ = runreport._decisions(returns, {"gate-before-fix": gate}, {"run_id": RUN}, "fixed", [], closed=True,
                                          beside=runreport.fix_beside(returns), exit_=runreport.rejudge_exit(returns))
        row = next(x for x in lines if "読めなかった保留" in x)
        self.assertIn("「保留: q-typo」", row)
        self.assertIn(FORK["key"], row)

    def test_answer_ties_bind_answers(self):
        """R77: 判定の隣の answer-ties.json の結びで、字の当たらない依頼の答えが問いに当たり（答えた行・保留から外れる）、結びの宛て先が
        今の問いに無ければ字の一致に落ちる。結ばないと判定が名乗った答えは訳つきで並び、判定が単位にしなかった作り直しの行が報告に出る"""
        returns = self.returns(FORK)
        answers = [{"question": "どちらでもよい", "text": "例外"}, {"question": "関係ない", "text": "x"}]
        self.put("judge/answer-ties.json", {"rounds": {"1": [
            {"answer": "どちらでもよい", "to": FORK["key"]}, {"answer": "関係ない", "none": "依頼のこの答えは今の判定のどの問いにも単位にも当たらない"},
            {"redesign": "前の run の作り直しの行", "none": "反証で死んだ。今の判定では成り立たない作り直しの行だった"}]}})
        state = runreport.ledger_state(returns, {}, {"answers": answers})
        self.assertEqual(state["held"], [])
        self.assertEqual(state["answered"], [gatemarks._ledger_line(FORK, "・" + gatemarks.answer_note(answers[0]))])
        self.assertIn("結ばなかった依頼の答え（問いにも単位にも結ばれないと判定が名乗った）: 関係ない", state["unmatched"][0])
        self.assertEqual(state["ties"][0], gatemarks.NO_CARRY_HEAD)
        self.assertIn("前の run の作り直しの行——判定が単位にしなかった訳: 反証で死んだ", state["ties"][-1])
        (self.dir / "judge" / "answer-ties.json").unlink()
        self.assertEqual(len(runreport.ledger_state(returns, {}, {"answers": answers})["held"]), 1, "結びが無い run は字の一致のまま")

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
        gate = {"decision": "continue", "text": "", "asked": [gatemarks.ask_text(FORK)]}
        state = runreport.ledger_state(returns, {"gate-before-fix": gate}, {"run_id": RUN})
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

    def test_answer_ties_reach_the_report(self):
        """J109: 判定の隣の answer-ties.json を報告が読み、どの問いにも当たらなかった答え（結ばない訳つき）と判定が単位にしなかった
        作り直しの行（none の訳）を人が決めることの節に出す"""
        judge = self.judge_with(**{"answer-ties.json": {"rounds": {"1": [
            {"answer": "関係ない", "none": "依頼のこの答えは今の判定のどの問いにも単位にも当たらない"},
            {"redesign": "前の run の作り直しの行", "none": "反証で死んだ。今の判定では成り立たない作り直しの行だった"}]}}})
        _, text, _ = self.build(fixed_run(judge=judge), start={"run_id": RUN, "answers": [{"question": "関係ない", "text": "x"}]})
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn("結ばなかった依頼の答え（問いにも単位にも結ばれないと判定が名乗った）: 関係ない——訳: 依頼のこの答えは", body)
        self.assertIn(gatemarks.NO_CARRY_HEAD, body)
        self.assertIn("前の run の作り直しの行——判定が単位にしなかった訳: 反証で死んだ", body)

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
        self.assertIn("世界の解の行が無い（判定の出力の world が null", self.section(text, report.WORLD_HEADING))
        _, text, _ = self.build(fixed_run(judge=None), )
        self.assertNotIn(report.WORLD_HEADING, text)

    def test_world_state_reason_and_dropped(self):
        """J112・R79（元 worldmark.report_lines :265-277）: 判定の隣の world-state.json の段が落ちた訳（status が ok でない時の reason）と、
        類の数・落とした抜き書きの数を世界の解の節に出す。控えが無い run は前の 1 行のまま"""
        judgment = self.put("judge/judgment.json", {})
        self.put(f"judge/{worldmark.STATE_FILE}", {"status": "failed", "reason": "網が無い（web を引けない）", "world_file": "",
                                                   "classes": 0, "dropped": 0})
        _, text, _ = self.build(fixed_run(judge={**fixed_run()["judge"], "judgment": judgment, "world": None}))
        self.assertIn("- 世界の解の段が落ちた（行なしで進んだ）: 網が無い（web を引けない）", self.section(text, report.WORLD_HEADING))
        world = self.put("judge/world.jsonl", json.dumps({**WORLD_ROW, "basis": "knowledge"}, ensure_ascii=False))
        self.put(f"judge/{worldmark.STATE_FILE}", {"status": "ok", "reason": "", "world_file": world, "classes": 1, "dropped": 3})
        _, text, _ = self.build(fixed_run(judge={**fixed_run()["judge"], "judgment": judgment, "world": world}))
        self.assertIn("- 類 1・落とした抜き書き 3", self.section(text, report.WORLD_HEADING))

    def test_unseen_local_review_lens_is_reported(self):
        """J110（元 diverted.report_lines・report.py:2069）: 判定の隣の local-review-lenses.json の見ていないレンズを、報告の
        「未確認のレンズ」の節に出す。控えが無ければ節に「無い」"""
        import diverted
        judgment = self.put("judge/judgment.json", {})
        self.put(f"judge/{diverted.LENS_FILE}", {"unseen": ["/code-review"]})
        _, text, _ = self.build(fixed_run(judge={**fixed_run()["judge"], "judgment": judgment}))
        self.assertIn("- 局所レビューの /code-review: 所見を受け取れていない（fork の返答が届かなかった）——見ていないのと同じ",
                      self.section(text, report.UNSEEN_LENS_HEADING))
        _, text, _ = self.build()
        self.assertIn("- 無い", self.section(text, report.UNSEEN_LENS_HEADING))

    def test_parallel_pr_drafts_reach_the_head(self):
        """J111・R80（元 report._pr_lines の前半 :1274-1281）: 判定の隣の pr-downgrades.json の並行 PR の担当への申し送りの下書きを、
        人が決めることの節に「投稿していない」と出す（人が担当の PR に渡す）"""
        import prcheck
        judgment = self.put("judge/judgment.json", {})
        self.put(f"judge/{prcheck.DRAFTS}", [{"pr": 12, "files": ["a.py", "b.py"], "note": "a.py の 3 行目を同時に直しています"}])
        _, text, _ = self.build(fixed_run(judge={**fixed_run()["judge"], "judgment": judgment}))
        self.assertIn("- 並行 PR #12 の担当への申し送りの下書き（a.py・b.py。投稿していない）: a.py の 3 行目を同時に直しています",
                      self.section(text, report.DECISIONS_HEADING))

    def test_head_names_declared_downgrades(self):
        """J41（元 prcheck.downgrades・head_downgrades と報告の head_entry）: 並行 PR を投稿しない形と独立設計を 1 度だけ作る形に下げた
        ことを宣言した控え（lib/downgrades.json）を読み、入口の節に「下げている所: N 個」と 1 行ずつ出す"""
        import prcheck
        rows = prcheck.downgrades()
        self.assertEqual([r["node"] for r in rows], ["p0.parallel_pr", "r2.design"])
        _, text, _ = self.build()
        entry = self.section(text, report.ENTRY_HEADING)
        self.assertIn(f"- 下げている所: 2 個\n  - p0.parallel_pr: {rows[0]['what']}（{rows[0]['versus']}）\n", entry)
        bad = self.put("downgrades.json", [{"node": "p0.parallel_pr", "what": ""}])
        with self.assertRaises(ValueError):
            prcheck.downgrades(pathlib.Path(bad))

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
        self.assertIn("- 飛ばされた・出力の無い段: rejudge・replan・replan-review\n", body)
        self.assertIn("直す前のテスト: 赤", body)
        self.assertIn("赤の原因 inherited", body)

        _, text, _ = self.build(fixed_run(**{"test-gate-base": None}))
        body = self.section(text, report.ENTRY_HEADING)
        self.assertNotIn("直す前のテスト", body)
        self.assertIn("- 飛ばされた・出力の無い段: test-gate-base・rejudge・replan・replan-review", body)

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

    def test_line_values_reach_their_sections(self):
        """L-W39・S49〜S51・R5b: 線の値（無人の run で関所に載せなかった問い・聞かずに通した直し・最後の関所を開ける理由・依頼の前の失敗・
        線の節の止めの語）が報告の節に出る"""
        prior = self.put("start/prior-failures-in.json", [{"where": "受け付け 計画", "text": "前の run で計画が通らなかった"}])
        line = {"deferred": ["[fork] u1: どちらに寄せるか"], "widened": ["項目 1: 直した——無人の run なので人に聞かずに範囲を広げた（allowed_paths に足した: b.py）"],
                "final_reasons": ["守りのパスに当たった差分が在る"], "prior_failures": prior,
                "stops": {"ask-final": stopby.NEEDS_HUMAN}}
        fix = {**fixed_run()["fix"], "replan_items": ["1"], "refixed": True}
        _, text, decided = self.build(fixed_run(fix=fix, **{"merge-apply": None}), line=line)
        self.assertEqual(decided, ("needs_human", f"ask-final:{stopby.NEEDS_HUMAN}"))
        decisions = self.section(text, report.DECISIONS_HEADING)
        self.assertIn(f"- {runreport.DEFERRED_HEAD}: 1 件\n  - [fork] u1: どちらに寄せるか\n", decisions)
        self.assertIn("  - 案の項目 1: 直した——無人の run なので人に聞かずに範囲を広げた（allowed_paths に足した: b.py）", decisions)
        self.assertIn(f"- {runreport.FINAL_REASONS_HEAD}: 1 件\n  - 守りのパスに当たった差分が在る\n", decisions)
        entry = self.section(text, report.ENTRY_HEADING)
        self.assertIn(f"- {runreport.PRIOR_IN_HEAD}: 1 件\n  - 受け付け 計画: 前の run で計画が通らなかった\n", entry)
        self.assertIn(f"- メイングラフのノードの止め: ask-final が {stopby.NEEDS_HUMAN}（{stopby.REASONS['needs-human']}）",
                      self.section(text, report.STOP_HEADING))
        self.put("start/prior-failures-in.json", "{壊れた")
        _, text, _ = self.build(line={"prior_failures": prior})
        self.assertIn(f"- {runreport.PRIOR_IN_HEAD}: 読めない（", self.section(text, report.ENTRY_HEADING))

    def test_depth_lines_name_raised_and_skipped(self):
        """L-D13・L-W51・R74: 報告の入口の節の深さの行は、直した後に上げ直した深さ（線の redepth の返り）を元 depth.lines の形で出す
        （単位ごとの数・単位ごとの深さと訳・標準へ上げた信号・run の広さの数え・軽量で省いた物）。上げ直しの返りが無い run は計画の深さと、
        上げ直しが無い訳"""
        redepth = {"depth": [{"unit_id": "u1", "depth": "標準", "why": "触るファイル 1 個 / 標準へ上げた: 再審が走った"}],
                   "skip_optional": "", "raised": ["再審が走った"], "counted": "触るファイル 1 個（起点: 修正の差分）", "stop_reason": ""}
        _, text, _ = self.build(line={"redepth": redepth})
        entry = self.section(text, report.ENTRY_HEADING)
        self.assertIn("- 深さ: 標準（単位ごと: 軽量 0 個・標準 1 個。機械が決めた）\n", entry)
        self.assertIn("  - 標準へ上げた信号: 再審が走った\n", entry)
        self.assertIn("- run の広さの数え: 触るファイル 1 個（起点: 修正の差分）", entry)
        light = {"depth": [{"unit_id": "u1", "depth": "軽量", "why": "触るファイル 1 個"}], "skip_optional": "軽量で省いた",
                 "raised": [], "counted": "", "stop_reason": ""}
        _, text, _ = self.build(line={"redepth": light}, start={"run_id": RUN, "thickness": "軽量"})
        entry = self.section(text, report.ENTRY_HEADING)
        self.assertIn("- 深さ: 軽量（単位ごと: 軽量 1 個・標準 0 個。入力 thickness の名指し 軽量）", entry)
        self.assertIn("- 軽量で省いた: 差分の審査", entry)
        plan = {**fixed_run()["plan"], "depth": [{"unit_id": "u1", "depth": "軽量", "why": "w"}]}
        _, text, _ = self.build(fixed_run(plan=plan))
        entry = self.section(text, report.ENTRY_HEADING)
        self.assertIn("- 深さ: 軽量（単位ごと: 軽量 1 個・標準 0 個。機械が決めた）", entry)
        self.assertIn(runreport.NO_REDEPTH, entry)

    def test_converge_lines_reach_the_report(self):
        """L-D22・P119・R35: 事前審査の壁打ちの往復の行（何往復・抜け方・続いた block と、往復ごとの block・fixed・disputed・suggest に
        下げた key・項目の閉じた/開いた/保留・相乗りの block。converge.lines）を、事前審査の返り review の隣の gate.json の converge から
        人が決めることの節に出す（元 report.head_decisions の converge.lines(b)。計画の往復と案の直しの事前審査の両方）"""
        import converge
        head = converge.LINE_HEAD.format(n=2, word="同じ block が続いた", outcome="persisted", persists="k1", share="",
                                         path="plan-review/pass")
        rounds = [head, converge.LINE_PASS.format(k=1, keys="k1", f=0, d=0, resolved="無い", down="無い"),
                  converge.LINE_ITEMS.format(closed="1", open="2", held="無い", synergy="無い"),
                  converge.LINE_PASS.format(k=2, keys="k1", f=1, d=1, resolved="無い", down="k2")]
        review = self.put("plan-review/review.json", {})
        self.put(f"plan-review/{gatemarks.PLAN_GATE_FILE}", {"items": [], "converge": rounds})
        again = self.put("replan-review/review.json", {})
        self.put(f"replan-review/{gatemarks.PLAN_GATE_FILE}", {"items": [], "converge": ["事前審査の壁打ち: 1 往復・抜け方は block が消えた"]})
        returns = fixed_run(**{"plan-review": {**fixed_run()["plan-review"], "review": review},
                               "replan-review": {**fixed_run()["plan-review"], "review": again}})
        _, text, _ = self.build(returns)
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn("\n".join([f"- {head}", *rounds[1:]]) + "\n", body)
        self.assertIn("- 事前審査の壁打ち: 1 往復・抜け方は block が消えた\n", body)
        self.put(f"plan-review/{gatemarks.PLAN_GATE_FILE}", "{壊れた")
        _, text, _ = self.build(returns)
        self.assertIn("事前審査の壁打ちの行（plan-review）: 無い（", self.section(text, report.DECISIONS_HEADING))

    def test_amended_items_are_listed(self):
        """L-D39・P146・R24: 同じ run で直した案の項目ごとに 1 行（元 replan.lines と report._amend_lines）を見出し AMEND_HEAD の下に
        並べる: 案の直しの関所が聞いた項目を人が通した（人が承認した）・聞かずに通した（手段の欄だけ）・無人の run で範囲を広げた
        （WIDEN_LINE）・2 度目の修正が走らなかった（直さずに諦めた: 申し出の行の replan_why か、関所の止めの一言）・途中で落ちた run（未完了）"""
        import replan
        rows = [{"unit_key": "u3", "between": ["案"], "ruling": {"decision": "fix_plan_item", "text": "案を直す", "plan_units": ["u3"],
                                                              "plan_items": ["3"]}, "plan_items": ["3"], "replan": "gave_up",
                 "replan_why": "直した案が事前審査を通らなかった"}]
        fix = {**fixed_run()["fix"], "replan_items": ["1", "2", "4"], "refixed": True,
               "conflicts": self.put("fix/conflicts.json", {"items": []})}
        gate = {"decision": "continue", "text": "", "asked": ["項目 1: 約束の欄が変わった（allowed_paths）"]}
        widened = ["項目 4: " + replan.widen_text({"allowed_paths": ["b.py"]})]
        _, text, _ = self.build(fixed_run(fix=fix), gates={"gate-replan": gate}, line={"widened": widened})
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn(f"- {replan.AMEND_HEAD}: 3 件\n  - 案の項目 1: 直した——人が承認した\n"
                      "  - 案の項目 2: 直した——聞かずに通した（手段の欄だけ）\n"
                      "  - 案の項目 4: 直した——無人の run なので人に聞かずに範囲を広げた（allowed_paths に足した: b.py）\n", body)
        fix = {**fix, "replan_items": ["3"], "refixed": False, "conflicts": self.put("fix/conflicts.json", {"items": rows})}
        self.assertIn("  - 案の項目 3: 直さずに諦めた: 直した案が事前審査を通らなかった\n",
                      self.section(self.build(fixed_run(fix=fix))[1], report.DECISIONS_HEADING))
        stop = {"decision": "stop", "text": "範囲が違う", "asked": []}
        fix = {**fix, "replan_items": ["5"]}
        self.assertIn("  - 案の項目 5: 直さずに諦めた: 人が承認ノード gate-replan で run を止めた: 範囲が違う\n",
                      self.section(self.build(fixed_run(fix=fix), gates={"gate-replan": stop})[1], report.DECISIONS_HEADING))
        self.assertEqual(replan.amend_lines(["5"], refixed=False, pending=True), [f"案の項目 5: {outcome.PENDING_WHY}"])
        self.assertNotIn(replan.AMEND_HEAD, self.build()[1])

    def test_missing_eye_is_named_apart_from_the_skipped(self):
        """R14: 目の節は、直した後の深さが標準なのに返りの無い目を「結果が無い」と、軽量で省いた目を「深さで省いた」と分けて出し、前の物を
        残りに数える"""
        eyes = {**fixed_run()["eyes"], "r2": None}
        standard = {"depth": [], "skip_optional": "", "raised": [], "counted": "", "stop_reason": ""}
        _, text, _ = self.build(fixed_run(eyes=eyes), line={"redepth": standard})
        self.assertIn("- R2: 結果が無い——再実行の要あり（深さは標準で、省いていない）", self.section(text, runreport.EYES_HEADING))
        self.assertIn(f"- {runreport.RESIDUE_HEAD}: 3 件（", self.section(text, report.DECISIONS_HEADING))
        _, text, _ = self.build(fixed_run(eyes=eyes), line={"redepth": {**standard, "skip_optional": "軽量で省いた"}})
        self.assertIn("- R2: 深さで省いた", self.section(text, runreport.EYES_HEADING))

    def test_design_without_anchor_is_named(self):
        """R36（元 report._design_unanchored :1265）: 独立設計が問いは立たないと返したのに、理由にパス:行の名指しが無ければ 1 行"""
        import design
        p = self.put("plan-review/design.json", {"question_stands": False, "premise_invalid_reason": "前提がそもそも違う"})
        _, text, _ = self.build(fixed_run(**{"plan-review": {**fixed_run()["plan-review"], "design": p}}))
        self.assertIn(f"- 独立設計は問いが立たないと返したが、{design.UNANCHORED}（前提がそもそも違う）", self.section(text, report.DECISIONS_HEADING))
        self.put("plan-review/design.json", {"question_stands": False, "premise_invalid_reason": "stats.py:3 が既に空を扱う"})
        _, text, _ = self.build(fixed_run(**{"plan-review": {**fixed_run()["plan-review"], "design": p}}))
        self.assertNotIn(design.UNANCHORED, text)

    def test_entry_names_thickness_and_features(self):
        """R41（元 report.head_entry :1308-1338・forge_line :1339）: 入口の節に段（thickness）・機能の on でない物（entry.features_part）・
        決めた人（関所の答えの数）と、forge の無い対象では並行 PR の確かめが条件外の 1 行"""
        import entry
        start = {"run_id": RUN, "thickness": "軽量", entry.FEATURES_KEY: ["world"], entry.FEATURES_ON_KEY: []}
        gates = {"gate-start": {"decision": "approve", "text": "", "asked": []}}
        _, text, _ = self.build(start=start, gates=gates)
        body = self.section(text, report.ENTRY_HEADING)
        self.assertIn(f"- 段: 軽量・{entry.features_part(['world'], [])}\n", body)
        self.assertIn("- 決めた人: 承認ノードの答え 1 件\n", body)
        import subprocess
        target = self.dir / "target"
        target.mkdir()
        subprocess.run(["git", "init", "-q", str(target)], check=True)
        got = runreport.build(fixed_run(), {}, {}, None, "fixed", "", out_dir=self.out, start={"run_id": RUN}, run_id=RUN, repo=target)
        self.assertIn(f"- {runreport.FORGE_HEAD}: 無い——並行 PR の確かめは条件外（not_applicable。",
                      self.section(pathlib.Path(got["report"]).read_text(encoding="utf-8"), report.ENTRY_HEADING))

    def test_policy_change_is_named(self):
        """R75（元の書き手の指示書の構成 2 の 3 つ目・process.policy_change）: 事前審査が固めた方針の文書の版（review の隣の
        policy.json）から今の文書が変わったまま終わった run は、入口の節に差分の置き場つきで 1 行（boardview.policy_change）"""
        import boardview
        import policy
        doc = self.dir / "repo" / "POLICY.md"
        doc.parent.mkdir()
        doc.write_text("古い方針\n", encoding="utf-8")
        review = self.put("plan-review/review.json", {})
        self.put(f"plan-review/{boardview.POLICY_FILE}", policy.freeze(self.dir / "plan-review", self.dir / "repo", str(doc)))
        returns = fixed_run(**{"plan-review": {**fixed_run()["plan-review"], "review": review}})
        got = runreport.build(returns, {}, {}, None, "fixed", "", out_dir=self.out, start={"run_id": RUN}, run_id=RUN, repo=self.dir / "repo")
        self.assertNotIn(runreport.POLICY_CHANGED_HEAD, pathlib.Path(got["report"]).read_text(encoding="utf-8"))
        doc.write_text("新しい方針\n", encoding="utf-8")
        got = runreport.build(returns, {}, {}, None, "fixed", "", out_dir=self.out, start={"run_id": RUN}, run_id=RUN, repo=self.dir / "repo")
        entry = self.section(pathlib.Path(got["report"]).read_text(encoding="utf-8"), report.ENTRY_HEADING)
        self.assertIn(f"- {runreport.POLICY_CHANGED_HEAD}: 人の方針の文書 {doc} が固定した版から変わった", entry)
        self.assertIn("（差分 ", entry)

    def test_apply_line_names_bin_apply(self):
        """M37（元 works/dev/lib.sh:633-644・test_use.py::test_show_hides_raw_apply_for_stopped_or_unjudgeable_run）: 差分を置いた run の
        報告に bin/apply <run-id> の行を出し、関所で止めた run には止まりの 1 行（結末の語・止めた所・人の一言）と --allow-stopped の
        要ることを出す。どちらも生の git apply の行を出さない"""
        seal_ok = {"mode": "seal", "ok": True, "diff": self.put("merge/sealed.diff", "")}
        _, text, _ = self.build(fixed_run(**{"merge-seal": seal_ok}))
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn(f"- {runreport.APPLY_HEAD}: bin/apply {RUN}（", body)
        self.assertNotIn("git apply", text)
        stop = {"decision": "stop", "text": "範囲が広すぎる", "asked": []}
        _, text, _ = self.build(fixed_run(**{"merge-seal": seal_ok, "merge-apply": None}), gates={"gate-final": stop})
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn("- 止まった run: 人が承認ノードで止めた（gate-final:stop）で止まった: 「範囲が広すぎる」", body)
        self.assertIn(f"- {runreport.APPLY_HEAD}: bin/apply {RUN} --allow-stopped（", body)
        self.assertNotIn("git apply", text)
        _, text, _ = self.build(fixed_run(**{"merge-seal": None, "merge-apply": None, "eyes": None}))
        self.assertIn(f"- {runreport.APPLY_HEAD}: 無い（差分を封じていない）", self.section(text, report.DECISIONS_HEADING))

    def test_tests_head_lines_and_deleted_files(self):
        """T35・T41・M38（部分 B2 の申し送り。最後の関所と同じ行を報告の冒頭に）: 人が決めることの節に最後のテストの一式の行と修正前のテストの
        行（test-gate の証拠の字のまま）、任せ先の申告の緑なら走らせる語の宣言の仕方、封じた差分が消すファイルを 1 本ずつ出す"""
        import declared_checks
        import seal
        evidence = self.put("test-gate/final/evidence.md", "\n".join([
            "# test-gate（final）", "- ok: true", "- 走らせ方: role_needed・一式: 任せ先の申告", "- ログ: /tmp/ci.log",
            "- 修正前のテスト: 赤（段ごとの終了コード {\"suite\": 1}）——最後のテストの赤は修正前から在りうる"]) + "\n")
        diff = self.put("merge/sealed.diff", "diff --git a/old.py b/old.py\ndeleted file mode 100644\n--- a/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n")
        returns = fixed_run(**{"test-gate-final": {**fixed_run()["test-gate-final"], "evidence": evidence},
                               "merge-seal": {"mode": "seal", "ok": True, "diff": diff}})
        _, text, _ = self.build(returns)
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn("- 最後のテストの一式: role_needed・一式: 任せ先の申告・ログ /tmp/ci.log\n", body)
        self.assertIn("- 修正前のテスト: 赤（段ごとの終了コード {\"suite\": 1}）——最後のテストの赤は修正前から在りうる\n", body)
        self.assertIn(f"- {declared_checks.SELF_REPORTED_NOTE}", body)
        self.assertIn(f"- {seal.DELETED_HEAD}: old.py\n", body)

    def test_every_line_is_a_bullet(self):
        """元 build の行の組み方: 節の行は「- 」か、字下げした内訳の行"""
        fix = {**fixed_run()["fix"], "units": [{"unit_id": "u1", "status": "given_up", "reason": "通らない"}]}
        _, text, _ = self.build(fixed_run(fix=fix))
        body = text.split(f"{report.DECISIONS_HEADING}\n\n", 1)[1]
        for line in body.splitlines():
            if line and not line.startswith("#"):
                self.assertTrue(line.startswith(("- ", "  ")), line)


class FixBesideLinesCase(Base):
    """修正の diff の隣の約束のファイル（lib/fixbeside.py）から報告に出す行"""

    def test_eyes_gate_passes_are_listed(self):
        """E66・E45: 独立の目の返り notes の隣の r4-gate-passes.json（人が通したので R4 の問いから外した行）を報告の「人が通した行」に並べ、
        R2 の行の下に R2 に渡した前提と渡されていないと言われた物を並べる。読めなければ読めないと言う"""
        import eyeverdict
        notes = self.put(f"eyes/{eyeverdict.PREMISE_INPUTS}", {"design": {"given": [], "withheld": []}, "compare": {"given": []},
                                                              "claims": ["上限が渡されていない"]})
        self.put(f"eyes/{eyeverdict.GATE_PASSES}", [{"node": gatemarks.R4_GATE_NODE, "round": 1, "by": gatemarks.PASSED_BY_HUMAN,
                                                     "item": "R4 が BASE から消えたと見た能力: 古い入口",
                                                     "passed_at": {"node": gatemarks.GATE_NODE, "round": 1}}])
        eyes = {**fixed_run()["eyes"], "r2": {"status": "pass", "reason": "同じ"}, "notes": notes}
        _, text, _ = self.build(fixed_run(eyes=eyes))
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn(f"- {runreport.EYE_PASSES_HEAD}: 1 件\n  - ", body)
        self.assertIn("R4 が BASE から消えたと見た能力: 古い入口", body)
        self.assertIn("R2: pass（同じ）\n  - 独立の設計と比べる目が渡されていないと書いた（R2）: 上限が渡されていない",
                      self.section(text, runreport.EYES_HEADING))
        (self.dir / "eyes" / eyeverdict.GATE_PASSES).unlink()
        _, text, _ = self.build(fixed_run(eyes=eyes))
        self.assertIn(f"- {runreport.EYE_PASSES_HEAD}: 読めない", self.section(text, report.DECISIONS_HEADING))

    def test_closure_recount_lines(self):
        """R29・R72（元 querytest.closure_lines・STUCK_HEAD。元 report.py:990-997）: 閉鎖の表で減っていない単位を STUCK_HEAD の下に先に、
        申告と合わない・閉じていない・表に行の無い申告の単位を CLOSURE_HEAD の下に出す"""
        stuck = {"unit_key": "A", "counts": "defects", "total": 3, "after": 3, "claimed": 1, "covered": 1, "bound": True,
                 "how_from": "判定", "closed": False, "discrepancies": [], "out_of_query": []}
        open_ = {**stuck, "unit_key": "B", "total": 3, "after": 1, "discrepancies": ["申告 2 ≠ 数え直し 1"]}
        diff = self.fix_place("fix", closure=[stuck, open_], claimed=["A", "B", "C"])
        _, text, _ = self.build(self.with_fix(diff))
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn(f"- {querytest.STUCK_HEAD}: 1 件\n  - A: 閉じていない（defects・修正前 3・修正後 3", body)
        self.assertIn(f"- {querytest.CLOSURE_HEAD}: 2 件\n  - B: 閉じていない（defects・修正前 3・修正後 1", body)
        self.assertIn("  - C: 閉鎖の表に行が無い", body)

    def test_fix_trace_rows_are_listed(self):
        """R37・F041・F013（元 report.gates_lines・plan_ask_lines）: 修正の受け付けの trace の行（赤緑を確かめずに受けた回と理由・はみ出しを
        相談で認めた／戻した・関所の条件で認めた新しいテスト・守りのテスト・範囲の相談の 1 問 1 答・回さなかった試験）を報告に出す"""
        import conflict as conflictlib
        rows = [{"op": fixbeside.SKIPPED_OP, "why": ["実行器が無い"]}, {"op": fixbeside.SKIPPED_OP, "why": ["実行器が無い"]},
                {"op": fixbeside.OVERFLOW_OP, "agreed": [1], "reverted": [{"paths": ["x.py"], "patch": "p.patch"}], "guards": ["g: 守り"],
                 "gate_tests": ["t（failure）"]},
                {"op": conflictlib.ASKED_OP, "id": 1, "item": 2, "status": "answered", "decision": "allow", "granted_paths": ["x.py"],
                 "reason": "要る"},
                {"op": fixbeside.TESTS_OP, "ci_left": ["tests/test_slow.py"], "final_left": [], "final_far": []}]
        diff = self.fix_place("fix", accept_trace=rows)
        _, text, _ = self.build(self.with_fix(diff))
        body = self.section(text, report.DECISIONS_HEADING)
        for want in ("- 事後の関門の束: 受け付け 2 回が受け入れのテストの赤緑を確かめずに通した（理由: 実行器が無い）",
                     "- はみ出しを相談で認めた: 相談 1", "- 承認ノードの条件の相談で認めた新しいテスト: t（failure）",
                     "- 守りのテストを認めた（今の木で緑だけを確かめた）: g: 守り", "- はみ出しを戻した（", "- 範囲の相談: 1 回（allow 1）",
                     "  - 相談 1（項目 2）: allow（x.py）——要る", "- 修正の受け付けが手元で回さなかった試験（1 件", "  - tests/test_slow.py"):
            self.assertIn(want, body)


class StampCase(Base):
    def test_stamp_names_workflow_run_and_version(self):
        wf = self.put("works-factory-report.yaml", "name: x\n")
        sha = hashlib.sha256(b"name: x\n").hexdigest()[:12]
        start = {"versions": {"works": {"rev": "ab" * 32, "dirty": False}}}
        self.assertEqual(runreport.stamp("run-9", wf, 2, start), f"works-factory-report / run run-9 / 周 2 / グラフの版 {sha} / メイングラフの版 abababababab")
        self.assertEqual(runreport.stamp("", wf, None, start), f"works-factory-report / run — / 周 — / グラフの版 {sha} / メイングラフの版 abababababab")
        self.assertIn("グラフの版 読めない（FileNotFoundError）", runreport.stamp("run-9", self.dir / "none.yaml", None, start))

    def test_stamp_names_line_version(self):
        """元 report_roles.stamp の works のメイングラフの版: 始めの記録の versions の works.rev（versions.LINE_REV）の頭 12 字。
        線の start が書く版の控え（versions.snapshot の返り）をそのまま通して読める（seams F1。書き手と読み手が同じ鍵）。
        無ければ黙らずにその旨"""
        import versions
        wf = self.put("works-factory-report.yaml", "name: x\n")
        sha = hashlib.sha256(b"name: x\n").hexdigest()[:12]
        got = runreport.stamp("run-9", wf, 2, {"versions": {"works": {"rev": "ab" * 32, "dirty": False}}})
        self.assertEqual(got, f"works-factory-report / run run-9 / 周 2 / グラフの版 {sha} / メイングラフの版 abababababab")
        snap = versions.snapshot(pathlib.Path(__file__).resolve().parents[2], {}, run_id="r")
        self.assertTrue(runreport.stamp("r", wf, None, {"versions": snap}).endswith(f" / メイングラフの版 {snap['works']['rev'][:12]}"))
        for start in ({"versions": {}}, {}, {"versions": {"works": {"rev": None}}}):
            with self.subTest(start=start):
                self.assertTrue(runreport.stamp("run-9", wf, None, start).endswith(" / メイングラフの版 始めの記録に無い（versions.works.rev）"))
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

"""機械の報告と持ち越し・書き手の受け付けと AI の報告（lib/runreport.py）の検査。

報告の頭と答えの下書きの場面は、元の works/tests/test_gate_head.py の ReportHeadCase と works/tests/test_gate_drafts.py の
DraftsCase のうち報告の側の物を、盤面と関所の節の代わりにブロックの返りの入力で書き直した（各試験の docstring に元の名）。
"""
import hashlib
import json
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import answer  # noqa: E402
import baseline_red  # noqa: E402
import carry  # noqa: E402
import declared_checks  # noqa: E402
import gatemarks  # noqa: E402
import handoff  # noqa: E402
import green_cert  # noqa: E402
import worldmark  # noqa: E402
import conflict  # noqa: E402
import depth  # noqa: E402
import fixbeside  # noqa: E402
import fixboard  # noqa: E402
import fixture  # noqa: E402
import headdepth  # noqa: E402
import launchgroups  # noqa: E402
import outcome  # noqa: E402
import outpurpose  # noqa: E402
import planfile  # noqa: E402
import querytest  # noqa: E402
import reads  # noqa: E402
import report  # noqa: E402
import userenv  # noqa: E402
import report_roles  # noqa: E402
import rolekit  # noqa: E402
import runreport  # noqa: E402
import stopby  # noqa: E402
import tddloop  # noqa: E402
from lib.tests.test_outcome import STAGES, fixed_run, stage_of  # noqa: E402
from tests.bin.gitkit import git  # noqa: E402
from lib.tests.test_plan_gate import DECIDED, FACE, FORK, FORK_UNIT, NARROW, WORLD_ROW  # noqa: E402
from tests.bin import hermetic  # noqa: E402

UNATTENDED = {"run_id": "run-1", "unattended": "true"}
UNIT_A, UNIT_B, UNIT_C = ({"id": "a", "paths": ["a.py"], "summary": "狭く直す"}, {"id": "b", "paths": ["b.py"], "summary": "b"},
                          {"id": "c", "paths": ["c.py"], "summary": "c"})
RUN = "run-1"


def rows_of(*rows) -> list:
    """run の記録の見本の行（止めた実行基盤の packages/workflows/src/logger.ts と node-record-serialization.ts の形）"""
    return list(rows)


def call(step, name, **raw):
    """道具の呼びの行（止めた実行基盤の logger.ts の logProviderEvent と provider-contract の tool_call の形）"""
    return {"type": "provider_event", "step": step, "workflow_id": RUN, "attemptId": "a-1", "seq": 0,
            "observedAt": "2026-10-13T00:00:00.000Z", "event": {"type": "tool_call", "toolCallId": f"t-{name}", "name": name,
                                                                 "rawInput": raw}}


def start(step, ts):
    return {"type": "node_start", "step": step, "ts": ts, "workflow_id": RUN}


def done(step, ts, cost=None, accounting="node", model=None, kind="node_complete", effort=None):
    row = {"type": kind, "step": step, "ts": ts, "workflow_id": RUN, "execution": {"accounting": accounting}}
    if cost is not None:
        row["cost_usd"] = cost
    if model:
        row["execution"]["binding"] = {"model": {"resolved": {"source": "provider", "value": model}}}
    if effort:
        row["execution"].setdefault("binding", {})["effort"] = effort
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

    def build(self, returns=None, gates=None, typed=None, transcript=None, start=None, problems=(), line=None, user_env=False):
        returns = fixed_run() if returns is None else returns
        gates = gates or {}
        line = {"stages": STAGES, **(line or {})}
        decided = outcome.decide_outcome(returns, gates, {"start_ok": True, "record_problems": list(problems),
                                                          "failed": (transcript or {}).get("failed", []),
                                                          "stops": list((line.get("stops") or {}).items()),
                                                          "eyes_skip": (line.get("redepth") or {}).get("skip_optional"),
                                                          "stages": line["stages"]})
        got = runreport.build(returns, gates, typed or {}, transcript, *decided, out_dir=self.out, start=start or {"run_id": RUN},
                              problems=problems, run_id=RUN, line=line, user_env=user_env)
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
        """修正の段ごとの diff（fix_place の返り）から、段の控えの欄を今の置き場から組んだ fix の返り"""
        return fixed_run(fix={**fixed_run()["fix"], "diff": diffs[-1], "records": [stage_of(d) for d in diffs]}, **over)

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
        got, text, decided = self.build(fixed_run(eyes=eyes, fix=fix))
        self.assertEqual(decided[0], "round_limit")
        named = self.section(text, report.PRIOR_HEADING)
        self.assertIn(carry.NEXT_REQUEST_FILE, named, "書いた next-request.json を名指す（#383 の 10）")
        self.assertIn(carry.PRIOR_FAILURES_FILE, named)
        doc = json.loads(pathlib.Path(got["next_request"]).read_text(encoding="utf-8"))
        prior = json.loads(pathlib.Path(got["prior_failures"]).read_text(encoding="utf-8"))
        self.assertEqual(carry.errors(doc, carry.NEXT_SCHEMA), [])
        self.assertEqual(carry.errors(prior, carry.PRIOR_SCHEMA), [])
        self.assertEqual([r["where"] for r in prior if r["where"] == carry.REDESIGN_WHERE], [carry.REDESIGN_WHERE])
        self.assertFalse(any(report._r2_redesign(r) for r in doc["findings"]), "R2 の作り直しの行は前の失敗にだけ載せる")
        self.assertTrue(any("受け付けが 3 回拒んだ" in r["text"] for r in prior))

    def first_line(self, final=None, **kw) -> str:
        returns = fixed_run(**{"final-tests": {**fixed_run()["final-tests"], **final}}) if final else None
        _, text, _ = self.build(returns, **kw)
        first = text.split("\n\n", 2)[1].splitlines()[0]
        self.assertTrue(first.startswith(gatemarks.HAPPENED), first)
        return first

    def test_pushed_gate_is_named_apart_from_a_human_answer(self):
        """#552: 無人の run が推しで通した承認ノードは、冒頭 1 行目・「人が決めること」・止めた段の行が推しで通したと名指す。
        人の答えでは言わない"""
        rec = {"item": "修正案 1 が狭める能力: 空の列で例外", "answer": "continue", "note": "0 を返す形で通す", "why": "呼び手が前提"}
        pushed = {"decision": "continue", "text": "0 を返す形で通す", "asked": [], "pushed": [rec]}
        _, text, _ = self.build(gates={"before-fix-answer": pushed})
        first = text.split("\n\n", 2)[1].splitlines()[0]
        self.assertIn("無人の run で推しを採って通した承認ノード: gate-before-fix（推し 1 件", first)
        self.assertIn("無人の run で推しを採って通した（承認ノード gate-before-fix）: 修正案 1 が狭める能力: 空の列で例外——通す（continue）: "
                      "0 を返す形で通す（推す理由: 呼び手が前提）", self.section(text, report.DECISIONS_HEADING))
        self.assertIn("承認ノード gate-before-fix: continue（推しで通した: 0 を返す形で通す）", self.section(text, report.STOP_HEADING))
        human = {k: v for k, v in pushed.items() if k != "pushed"}
        _, text, _ = self.build(gates={"before-fix-answer": human})
        self.assertNotIn("推しを採って通した", text)
        self.assertIn("承認ノード gate-before-fix: continue（0 を返す形で通す）", self.section(text, report.STOP_HEADING))

    def test_pushed_run_stopped_at_the_final_gate_quotes_no_push_as_a_human_word(self):
        """#552: 修正の前を推しで通し、最後の承認ノードで無人ゆえに止まった run は、止まりの行に推しの一言を人の一言として引かず、
        決めた人の数に推しを数えない"""
        rec = {"item": "修正案 1 が狭める能力: 空の列で例外", "answer": "continue", "note": "0 を返す形で通す", "why": "呼び手が前提"}
        gates = {"before-fix-answer": {"decision": "continue", "text": "0 を返す形で通す", "asked": [], "pushed": [rec]}}
        seal_ok = {"mode": "seal", "ok": True, "diff": self.put("merge/sealed.diff", "")}
        _, text, decided = self.build(fixed_run(**{"sealed-diff": seal_ok, "applied-diff": None}), gates=gates,
                                      line={"stops": {"ask-final": stopby.HEAD + "needs-human"}})
        stopped = [x for x in self.section(text, report.DECISIONS_HEADING).splitlines() if x.startswith("- 止まった run: ")]
        self.assertEqual(len(stopped), 1, decided)
        self.assertTrue(stopped[0].endswith("「一言なし」"), stopped)
        self.assertIn("- 決めた人: 承認ノードの答え 0 件（ほかに無人の run が推しで通した承認ノード 1 件）\n",
                      self.section(text, report.ENTRY_HEADING))

    def test_report_names_nodes_from_the_stages_table(self):
        table = {**STAGES, "nodes": {**STAGES["nodes"], "final-tests": "x-final", "sealed-diff": "x-seal", "final-answer": "x-gate",
                                     "before-tests": "x-base"}}
        final = {**fixed_run()["final-tests"], "by": "engine", "suites_line": "一式", "log": "/tmp/x/test.log", "baseline_line": "修正前のテスト: 赤",
                 "reason": "", "evidence": str(self.dir / "nowhere.md")}
        sealed = self.put("merge/sealed.diff", "")
        seal = {"mode": "seal", "ok": False, "reason": "hash が食い違う", "diff": sealed}
        gates = {"final-answer": {"decision": "approve", "text": "これで良い", "asked": []}}
        _, text, decided = self.build(fixed_run(**{"final-tests": final, "sealed-diff": seal}), gates=gates, line={"stages": table})
        self.assertEqual(decided, ("stopped_by_line", "x-seal:not-ok"))
        self.assertIn("- 最後のテスト（x-final）の走らせ方: engine・一式\n", self.section(text, runreport.GREEN_HEADING))
        self.assertIn("- 直す前のテスト（x-base）のログ: ", self.section(text, runreport.GREEN_HEADING))
        stop = self.section(text, report.STOP_HEADING)
        self.assertIn("承認ノード x-gate: approve（これで良い）", stop)
        self.assertIn("x-seal が ok でない: hash が食い違う", stop)
        self.assertIn("止めた段と理由の語: x-seal:not-ok", stop)
        self.assertIn("最後の承認ノード x-gate: ", self.section(text, report.MODEL_HEADING))
        entry = self.section(text, report.ENTRY_HEADING)
        self.assertIn("- 走った段: x-base・judge・plan・plan-review・fix・x-final・eyes・x-seal・merge-apply\n", entry)
        self.assertIn("- 飛ばされた・出力の無い段: rejudge・replan・replan-review\n", entry)
        self.assertIn(f"封じた差分（x-seal.diff）: {sealed}", self.section(text, report.WHERE_HEADING))

    def test_final_tests_that_did_not_run_are_named_in_the_head(self):
        """#492: 最後のテストが incomplete の run は、冒頭の 1 行目（起きたこと）が試験は走っていないと言い、利用者の環境で回す道を
        添える。返す節の中の誤り（by が空）は走っていないと言わずに工場の不具合と言う。緑なら言わない"""
        red = {"ok": False, "green": False, "red_cause": "incomplete", "by": "role"}
        first = self.first_line(red)
        self.assertIn(green_cert.NOT_RAN, first)
        self.assertIn(green_cert.RAN_GUIDE, first)
        broke = self.first_line({**red, "by": ""})
        self.assertIn(green_cert.GATE_BROKE, broke)
        self.assertNotIn(green_cert.NOT_RAN, broke)
        green = self.first_line()
        for note in (*green_cert.RAN_NOTES, userenv.NOTE):
            self.assertNotIn(note, green)

    def test_final_tests_partly_started_name_the_steps_in_the_head(self):
        """#514: 宣言の段の一部だけ起こせた最後のテストは、冒頭の 1 行目が起こした段と起こせなかった段を名指し、「走っていない」と言わない"""
        first = self.first_line({"ok": False, "green": False, "red_cause": "incomplete", "by": "engine",
                                 "ran_steps": {"ran": ["unit"], "unran": ["lint"]}})
        self.assertIn(green_cert.PARTLY_RAN, first)
        self.assertIn("unit", first)
        self.assertIn("lint", first)
        self.assertNotIn(green_cert.NOT_RAN, first)

    def test_users_environment_for_target_commands_is_named_in_the_head(self):
        """#492: 対象のコマンドを利用者の HOME・XDG で走らせた run だけ、冒頭の 1 行目が AI の試験のコードが資格に届いたと言う"""
        self.assertIn(userenv.NOTE, self.first_line(user_env=True))
        self.assertNotIn(userenv.NOTE, self.first_line())

    def test_notices_before_the_run_are_in_the_head(self):
        """#678: run を止めずに進めた起こす前の注意の行（線の値 notices）は、冒頭の 3 行の下に 1 行ずつ載り、人に向けた報告の頭
        （machine_head）に入る。無ければ冒頭は今のまま"""
        notices = ["注意（test_cmd）: test_cmd の .venv/bin/x は対象の git が無視するパス", "許しなので止めずに進める"]
        _, text, _ = self.build(line={"notices": notices})
        head = runreport.machine_head(text)
        self.assertTrue(head.split("\n\n")[1].startswith(gatemarks.HAPPENED), head)
        self.assertEqual(head.split("\n\n")[-1].splitlines(), notices)
        _, quiet, _ = self.build()
        self.assertEqual(runreport.machine_head(quiet), head.rsplit("\n\n", 1)[0])

    def test_prior_section_names_only_the_files_written(self):
        """#383 の 10: 前の失敗だけが在る run は next-request.json を書かないので、節はそれを名指さず prior-failures.json を名指す"""
        got, text, _ = self.build(line={"stops": {"ask-final": stopby.LINE_SCRIPT}})
        self.assertIsNone(got["next_request"])
        prior = self.section(text, report.PRIOR_HEADING)
        self.assertNotIn(carry.NEXT_REQUEST_FILE, prior)
        self.assertIn(carry.PRIOR_FAILURES_FILE, prior)
        self.assertEqual(report.prior_lines([], carry.NEXT_REQUEST_FILE), ["0 件"])

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
        gates = {"final-answer": {"decision": "stop", "text": "request: 止め札"}}
        _, text, decided = self.build(gates=gates)
        self.assertEqual(decided[0], "stopped_by_request")
        self.assertIn(report.OUTCOME_WORDS["stopped_by_request"], text)
        self.assertIn("承認ノード gate-final: stop（request: 止め札）", text)

    def test_reads_section_shows_what_u6_can_take(self):
        """「4. 読んだ証拠と包み」が、run の記録の provider_event の道具の呼び（節ごと）と、読んだ証拠の節が書いた reads-*.json の
        欠けを出し、取れない物（Bash で読み書きしたファイル・組の子の run）を名指す（棚卸し R46。docs/design.md の U6）"""
        role = "judge__pr-check-loop.pr-check"
        tfacts = runreport.transcript_facts(rows_of(
            start(role, "2026-10-13T00:00:00Z"), call(role, "Read", file_path="/r/a.py"), call(role, "Read", file_path="/r/a.py"),
            call(role, "Read", file_path="/r/b.py"), call(role, "Bash", command="cat c.py"), done(role, "2026-10-13T00:01:00Z"),
            call("fix__fix", "Edit", file_path="/r/a.py"), call("report__write", "Read", file_path="/r/x.md")),
            exclude_prefix="report__")
        self.assertEqual(tfacts["calls"], {role: {"Read": ["/r/a.py", "/r/b.py"], "Edit": [], "Write": [], "Bash": 1},
                                           "fix__fix": {"Read": [], "Edit": ["/r/a.py"], "Write": [], "Bash": 0}})
        brief = "/art/judge/pr-brief.json"
        log = reads.reads_path(self.dir / "config" / reads.ROOT, self.dir)
        log.parent.mkdir(parents=True)
        log.write_text("", encoding="utf-8")
        (self.dir / "judge").mkdir()
        pr = reads.collect(self.dir / "judge", "pr-check", [brief], log, own=[brief], since="", repo=self.dir)["reads_file"]
        self.put(f"judge/{reads.index_name('pr-check')}", {"pr-check": pr})
        (self.dir / "fix" / "fix").mkdir(parents=True)
        reads.collect(self.dir / "fix" / "fix", "fix", ["/p.md"], self.dir / "none" / "x" / reads.LOG, own=[], since="", repo=self.dir)
        self.put("plan/r1/reads-plan-writer.json", "{")
        reads.guarded(lambda: 1 / 0, owner="plan-review", place=self.dir / "plan-review")
        self.put(f"fix/fix/{reads.index_name('fix')}", {"fix": None, "why": f"{reads.NOT_LAUNCHED}: refix"})
        _, text, _ = self.build(transcript=tfacts)
        got = self.section(text, report.READS_HEADING)
        self.assertIn(f"  - {role}: Read 2 件・Edit 0 件・Write 0 件（ファイル: /r/a.py・/r/b.py）", got)
        self.assertIn("  - fix__fix: Read 0 件・Edit 1 件・Write 0 件（ファイル: /r/a.py）", got)
        self.assertNotIn("report__write", got)
        self.assertIn(f"  - pr-check（judge/reads-pr-check.json）: 渡した 1・読んだ跡の無い 1（{brief}）", got)
        self.assertIn(f"  - fix（fix/fix/reads-fix.json）: 測れない（{reads.NO_ROOT}）", got)
        self.assertIn("  - plan/r1/reads-plan-writer.json: 読めない（", got)
        self.assertNotIn(reads.index_name("pr-check"), got)
        self.assertRegex(got, r"  - plan-review（plan-review/reads-plan-review-failed-[^）]+）: 読んだ証拠のノードが落ちた（ZeroDivisionError: ")
        self.assertIn(f"  - fix/fix/{reads.index_name('fix')}: {reads.NOT_LAUNCHED}: refix", got)
        self.assertIn("取れない（U6）: Bash で読み書きしたファイル", got)
        self.assertIn(f"Bash の呼び 1 回: {role} 1", got)
        self.assertIn("組の子の run", got)
        self.assertNotIn("読んだ証拠を集める口を戻していない", got)

        _, text, _ = self.build(transcript=None)
        got = self.section(text, report.READS_HEADING)
        self.assertIn("  - run の記録が読めない（", got)

    def test_reads_in_the_fixture_copy_are_not_listed_twice(self):
        """固定材料は run の置き場を丸ごと写すので、写しの下の reads-*.json を「4. 読んだ証拠と包み」に元の物と並べて出さない"""
        repo = pathlib.Path(tempfile.mkdtemp(dir=self.dir.parent))
        self.addCleanup(shutil.rmtree, repo)
        git(repo, "init", "-q")
        git(repo, "commit", "-q", "--allow-empty", "-m", "seed")
        (self.dir / "judge" / "judge").mkdir(parents=True)
        reads.collect(self.dir / "judge" / "judge", "judge", ["/p.md"], self.dir / "none" / "x" / reads.LOG, own=[], since="",
                      repo=self.dir)
        fixture.capture(self.dir, repo, run_id="run-1", carried={})
        self.assertTrue((self.dir / fixture.DIR / fixture.COPY / "judge" / "judge" / "reads-judge.json").is_file())
        _, text, _ = self.build(transcript=runreport.transcript_facts(rows_of(), exclude_prefix="report__"))
        got = self.section(text, report.READS_HEADING)
        self.assertEqual(got.count("reads-judge.json"), 1, got)
        self.assertNotIn(fixture.DIR, got)

    def test_unrun_base_is_not_called_red(self):
        """走らせられなかった直す前のテスト（ok false・green false・red_cause incomplete）を「赤」と書かない（棚卸し T68）"""
        base = {"mode": "base", "ok": False, "green": False, "red_cause": green_cert.INCOMPLETE}
        _, text, _ = self.build(fixed_run(**{"before-tests": base}))
        entry = self.section(text, report.ENTRY_HEADING)
        self.assertIn(f"直す前のテスト: 走らせられなかった（incomplete）——{gatemarks.BASELINE_NOT_RUN}", entry)
        self.assertNotIn("直す前のテスト: 赤", entry)

    def test_unrun_base_says_why_it_could_not_run(self):
        """走らせられなかった直す前のテスト（ok false・green false・red_cause environment）の行は、認証しなかった訳（返りの reason。素材が
        not_run の訳と準備の案内）を 1 行にして添え、「赤」と書かない。訳が空なら添えない"""
        why = "素材が not_run——緑を仮定しない（宣言の語を起こせない: suite: 準備が落ちた）。\n準備が要る道具は 宣言に setup を足す"
        base = {"mode": "base", "ok": False, "green": False, "red_cause": green_cert.ENVIRONMENT, "reason": why}
        _, text, _ = self.build(fixed_run(**{"before-tests": base}))
        entry = self.section(text, report.ENTRY_HEADING)
        self.assertIn(f"直す前のテスト: 走らせられなかった（environment）——{gatemarks.BASELINE_NOT_RUN}——"
                      "素材が not_run——緑を仮定しない（宣言の語を起こせない: suite: 準備が落ちた）。 準備が要る道具は 宣言に setup を足す", entry)
        self.assertNotIn("直す前のテスト: 赤", entry)
        bare = {**base, "reason": ""}
        _, text, _ = self.build(fixed_run(**{"before-tests": bare}))
        self.assertIn(f"直す前のテスト: 走らせられなかった（environment）——{gatemarks.BASELINE_NOT_RUN}\n",
                      self.section(text, report.ENTRY_HEADING) + "\n")

    def test_not_applicable_base_is_not_called_unrun(self):
        """素材が not_applicable の直す前のテストは認証され（ok 真）incomplete に畳まれるが、「走らせられなかった」とも「赤」とも書かない"""
        pointed = str(self.dir / "test-gate" / "base" / "baseline.json")
        baseline_red.write_baseline(pointed, suite="", test_cmd="", rev="r", exit=None, cases=[],
                                    material={"status": green_cert.NOT_APPLICABLE, "reason": "検査の宣言が無い"})
        base = {"mode": "base", "ok": True, "green": False, "red_cause": green_cert.INCOMPLETE, "baseline": pointed}
        _, text, _ = self.build(fixed_run(**{"before-tests": base}))
        entry = self.section(text, report.ENTRY_HEADING)
        self.assertIn(f"直す前のテスト: {gatemarks.MATERIAL_WORDS['not_applicable']}（not_applicable）", entry)
        self.assertNotIn("走らせられなかった", entry)

    def test_awaiting_human_base_names_what_could_not_run(self):
        """#495: 一部の系統を走らせられず awaiting_human の直す前のテストは認証され（ok 真）incomplete に畳まれる。「赤」とも
        「走らせられなかった」とも書かず、素材の語と、走らせられなかった系統を名指す reason で言う"""
        pointed = str(self.dir / "test-gate" / "base" / "baseline.json")
        baseline_red.write_baseline(pointed, suite="", test_cmd="", rev="r", exit=None, cases=[],
                                    material={"status": "awaiting_human", "reason": "実機の要る系統は回せない。\nlint は緑"})
        base = {"mode": "base", "ok": True, "green": False, "red_cause": green_cert.INCOMPLETE, "baseline": pointed}
        _, text, _ = self.build(fixed_run(**{"before-tests": base}))
        entry = self.section(text, report.ENTRY_HEADING)
        self.assertIn(f"直す前のテスト: {gatemarks.MATERIAL_WORDS['awaiting_human']}（awaiting_human）——"
                      "実機の要る系統は回せない。 lint は緑", entry)
        self.assertNotIn("直す前のテスト: 赤", entry)


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
        """元 report.py:1042-1050 の最後のテストの一式の行とログ: test-gate の返りの欄 by・suites_line・log から（証拠の文は開かない）。
        取れなければ黙らずにその旨"""
        suites = "一式: run-tests（make test）"
        final = {**fixed_run()["final-tests"], "by": "engine", "suites_line": suites, "log": "/tmp/x/test.log",
                 "baseline_line": "修正前のテスト: 赤", "reason": "", "evidence": str(self.dir / "nowhere.md")}
        _, text, _ = self.build(fixed_run(**{"final-tests": final}))
        green = self.section(text, runreport.GREEN_HEADING)
        self.assertIn(f"- 最後のテスト（test-gate-final）の走らせ方: engine・{suites}\n", green)
        self.assertIn("- 最後のテスト（test-gate-final）のログ: /tmp/x/test.log\n", green)
        self.assertIn("- 最後のテスト（test-gate-final）の修正前のテスト: 赤\n", green)
        self.assertIn(f"- 直す前のテスト（test-gate-base）の走らせ方: {declared_checks.GATE_MISSING}\n", green)
        self.assertIn(f"- 直す前のテスト（test-gate-base）のログ: {declared_checks.GATE_MISSING}\n", green)

        fell = {**final, "by": "", "suites_line": "", "log": "", "baseline_line": "", "reason": "出力ノードの中の誤り"}
        _, text, _ = self.build(fixed_run(**{"final-tests": fell}))
        green = self.section(text, runreport.GREEN_HEADING)
        self.assertIn(f"- 最後のテスト（test-gate-final）の走らせ方: {declared_checks.GATE_MISSING}\n", green)
        self.assertIn(f"- 最後のテスト（test-gate-final）のログ: {declared_checks.GATE_MISSING}\n", green)
        self.assertIn(f"- 最後のテスト（test-gate-final）の修正前のテスト: {declared_checks.GATE_MISSING}\n", green)

        _, text, _ = self.build(fixed_run(**{"before-tests": None, "final-tests": None}))
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

    def test_model_section_lists_groups_node_efforts_and_outcome(self):
        jdir = self.dir / "judge"
        chosen = launchgroups.choices([{"group": "@wf-fix-writers", "model": "opus", "effort": "high", "why": "広い書き換え"},
                                       {"group": "@wf-nothing", "model": "opus", "effort": "high", "why": "x"}])
        record = headdepth.write(jdir, headdepth.record("重厚", "設計の選び", groups=chosen))
        judged = {**fixed_run()["judge"], "judgment": str(jdir / "judgment.json"), "depth_record": str(record)}
        facts = runreport.transcript_facts(rows_of(
            start("judge__diagnose", "2026-10-12T00:00:00Z"),
            done("judge__diagnose", "2026-10-12T00:03:00Z", cost=0.5, model="opus", effort="high"),
            done("fix__write", "2026-10-12T00:05:00Z", cost=0.25, model="sonnet", effort="medium"),
            done("fix__write", "2026-10-12T00:06:00Z", cost=0.25, model="sonnet", effort="high"),
            done("test-gate-final__run", "2026-10-12T00:07:00Z", cost=0.1, model="haiku"),
        ), exclude_prefix="report__")
        self.assertEqual(facts["efforts"], {"judge__diagnose": ["high"], "fix__write": ["medium", "high"]})
        self.assertEqual(runreport.transcript_facts(None)["efforts"], {}, "出来事の行が無い返りも efforts を持つ")
        gates = {"final-answer": {"decision": "approve", "text": "これで良い", "asked": []}}
        eyes = {**fixed_run()["eyes"], "r2": None}
        given_up = {**fixed_run()["fix"], "units": [{"unit_id": "u2", "status": "given_up", "reason": "直せなかった"}]}
        _, text, decided = self.build(fixed_run(judge=judged, eyes=eyes, fix=given_up), gates=gates, transcript=facts,
                                      line={"redepth": {"skip_optional": ""}})
        section = self.section(text, report.MODEL_HEADING)
        self.assertEqual(section.splitlines()[:3], [
            "- @wf-fix-writers: 既定 sonnet・high → 役の選び opus・high（上げ。訳: 広い書き換え）",
            "- @wf-nothing: 表に無い群を既定に戻した（訳: 群 '@wf-nothing' が表に無い）",
            f"- {launchgroups.RECORD_ONLY}"])
        self.assertIn("- judge__diagnose: opus（effort: high）\n", section)
        self.assertIn("- fix__write: sonnet（effort: medium, high）\n", section)
        self.assertIn("- test-gate-final__run: haiku\n", section, "effort の無い行は今の字のまま")
        want = self.section(text, report.DECISIONS_HEADING)
        carried = int(want.split("次の run に渡す物: ")[1].split(" 件")[0])
        outcome_line = next(x for x in section.splitlines() if x.startswith("- 結末: "))
        self.assertIn(f"結末: {report.OUTCOME_WORDS[decided[0]]}（{decided[0]}）", outcome_line)
        self.assertIn(f"最後の承認ノード gate-final: {runreport._gate_line(gates['final-answer'])}", outcome_line)
        self.assertIn(f"次の run に渡す物: {carried} 件", outcome_line)
        self.assertIn("持ち越した失敗: 1 件", outcome_line)
        self.assertIn(runreport.DATA_PLACES, outcome_line)
        for place in ("depth-head.json", "groups", "$LOG_DIR/<run の id>.jsonl", "execution.binding", "result", "outcome", "stop_reason"):
            self.assertIn(place, runreport.DATA_PLACES)
        self.assertNotIn("同じ run の置き場", runreport.DATA_PLACES)
        for skip, said in (("", "結果が無い——再実行の要あり（深さは標準で、省いていない）"), ("軽量で省いた", "深さで省いた")):
            with self.subTest(skip=skip):
                _, text, _ = self.build(fixed_run(judge=judged, eyes=eyes), line={"redepth": {"skip_optional": skip}}, transcript=facts)
                eye_section = self.section(text, runreport.EYES_HEADING).splitlines()
                outcome_line = next(x for x in self.section(text, report.MODEL_HEADING).splitlines() if x.startswith("- 結末: "))
                self.assertIn(f"- R2: {said}", eye_section)
                for name in outcome.EYE_NAMES:
                    word = next(x for x in eye_section if x.startswith(f"- {name.upper()}: ")).removeprefix("- ")
                    self.assertIn(word, outcome_line)
        _, text, _ = self.build(fixed_run(judge=judged, eyes=None), transcript=facts)
        self.assertIn(f"独立の目: {runreport.NO_EYES}", self.section(text, report.MODEL_HEADING))
        self.assertIn(f"- {runreport.NO_EYES}\n", self.section(text, runreport.EYES_HEADING) + "\n")
        _, text, _ = self.build(fixed_run(judge=None), transcript=facts)
        section = self.section(text, report.MODEL_HEADING)
        self.assertEqual(section.splitlines()[:2], [f"- {headdepth.NO_CHOICE}", f"- {launchgroups.RECORD_ONLY}"])
        self.assertNotIn("既定のまま", section)
        self.assertIn("- test-gate-final__run: haiku\n", section)


    @staticmethod
    def until(loop, n, ts, code):
        return {"type": runreport.EXEC_ROW, "step": f"{loop}{runreport.ITERATION_MARK}{n}", runreport.EXEC_LABEL: runreport.UNTIL_ROW,
                runreport.EXIT_CODE: code, "ts": ts, "workflow_id": RUN}

    def cost_section(self, rows):
        facts = runreport.transcript_facts(rows, exclude_prefix="report__")
        _, text, _ = self.build(transcript=facts)
        return facts, self.section(text, report.COST_HEADING)

    def test_until_rows_give_resubmit_count_and_minutes(self):
        rows = rows_of(
            start("judge__world-classes-loop", "2026-10-12T00:00:00Z"),
            self.until("judge__world-classes-loop", 1, "2026-10-12T00:01:00Z", 1),
            self.until("judge__world-classes-loop", 2, "2026-10-12T00:03:00Z", 0),
            self.until("fix__tdd", 1, "2026-10-12T00:04:00Z", 0),
            self.until("report__ask", 1, "2026-10-12T00:05:00Z", 1),
            self.until("report__ask", 2, "2026-10-12T00:06:00Z", 0),
            self.until("fix__kill", 1, "2026-10-12T00:07:00Z", "SIGTERM"),
            self.until("fix__kill", 2, "2026-10-12T00:09:00Z", 0),
            self.until("fix__flag", 1, "2026-10-12T00:10:00Z", True),
            self.until("fix__flag", 2, "2026-10-12T00:11:00Z", 0),
            {**self.until("fix__other", 1, "2026-10-12T00:12:00Z", 1), runreport.EXEC_LABEL: "ほかの呼び"},
        )
        facts, cost = self.cost_section(rows)
        self.assertEqual(facts["resubmits"], {"judge__world-classes-loop": {"count": 1, "minutes": 2.0},
                                              "fix__tdd": {"count": 0, "minutes": 0.0},
                                              "fix__kill": {"count": 0, "minutes": 0.0},
                                              "fix__flag": {"count": 0, "minutes": 0.0}},
                         "exclude_prefix のループ・until でない呼びは数えない。字の exit_code（打ち切り）と bool は回り直しに数えない")
        self.assertIn("judge__world-classes-loop: until が通らず回り直した回 1（受け付けのループでは拒否で出し直した回）・2.0 分", cost)
        self.assertNotIn("fix__tdd: until", cost)
        self.assertNotIn("fix__kill: until", cost)
        self.assertNotIn("report__ask", cost)
        self.assertNotIn("回り直し: 0 回", cost)
        self.assertEqual(cost.splitlines()[-1], f"- {runreport.CHILD_LOOPS}")

    def test_no_failed_until_says_zero_resubmits(self):
        rows = rows_of(
            self.until("judge__world-classes-loop", 1, "2026-10-12T00:01:00Z", 0),
            self.until("fix__tdd", 1, "2026-10-12T00:02:00Z", 0),
        )
        _, cost = self.cost_section(rows)
        self.assertIn("回り直し: 0 回（until の行を読んだループ 2 本）", cost)
        self.assertEqual(cost.splitlines()[-1], f"- {runreport.CHILD_LOOPS}")

        _, cost = self.cost_section(rows_of(start("judge__diagnose", "2026-10-12T00:00:00Z"),
                                            done("judge__diagnose", "2026-10-12T00:03:00Z", cost=0.5)))
        self.assertIn("回り直し: 数えられない（記録にループの until の行が無い）", cost)
        self.assertNotIn("回り直し: 0 回", cost)
        self.assertEqual(cost.splitlines()[-1], f"- {runreport.CHILD_LOOPS}")

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


def fell(step, error, failure_class=None):
    """落ちた節の行。provider の落ちの種は execution.lifecycle.providerFailure（止めた実行基盤の node-execution.ts の形）"""
    row = {**done(step, "2026-10-18T00:01:00Z", kind="node_error"), "error": error}
    lifecycle = {"status": "failed", "error": error}
    if failure_class:
        lifecycle["providerFailure"] = {"class": failure_class, "evidence": "e"}
    row["execution"]["lifecycle"] = lifecycle
    return row


class WriterFellCase(unittest.TestCase):
    """#702: 書き手のループが落ちた訳を run の記録から読み、機械の報告の冒頭に置く。resume で書き直したら外す"""
    QUOTA = "Loop-group node 'write-loop' failed at iteration 1: 'write': usage or credit limit is used up\n詳しい行"
    SAFEGUARDS = "Loop-group node 'write-loop' failed at iteration 1: 'write': API Error: Sonnet 5.5's safeguards flagged this message"
    MACHINE = "# 報告（run run-1）\n\n起きたこと\n当ててよいか\n人が決めること\n\n## 1. 結末\n\n本文\n"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.machine = pathlib.Path(tmp.name) / "report.md"
        self.machine.write_text(self.MACHINE, encoding="utf-8")

    def head(self) -> str:
        return runreport.machine_head(self.machine.read_text(encoding="utf-8"))

    def test_last_row_of_the_loop_decides(self):
        quota = fell("report__write-loop", self.QUOTA, "quota_exhausted")
        self.assertEqual(runreport.writer_fell(rows_of(start("report__write-loop", "t"), quota), "report__write-loop"),
                         {"error": "Loop-group node 'write-loop' failed at iteration 1: 'write': usage or credit limit is used up",
                          "quota": True})
        self.assertEqual(runreport.writer_fell([fell("write-loop", self.SAFEGUARDS)], "write-loop"),
                         {"error": self.SAFEGUARDS, "quota": False})
        again = done("report__write-loop", "2026-10-18T00:09:00Z")
        for rows in ([quota, again], [quota, {"type": "node_skipped", "step": "report__write-loop"}], [], None,
                     [fell("report__write", self.QUOTA, "quota_exhausted")]):
            with self.subTest(rows=rows):
                self.assertIsNone(runreport.writer_fell(rows, "report__write-loop"))

    def test_note_names_the_error_and_resume_only_for_quota(self):
        runreport.note_writer_fell(self.machine, {"error": "API Error: x", "quota": False}, run_id="run-1")
        self.assertTrue(self.head().endswith(runreport.WRITER_FELL.format(error="API Error: x")), self.head())
        self.assertNotIn("resume", self.head())
        self.assertIn("## 1. 結末\n\n本文", self.machine.read_text(encoding="utf-8"))
        runreport.note_writer_fell(self.machine, {"error": "used up", "quota": True}, run_id="run-1")
        lines = [x for x in self.head().splitlines() if x.startswith("AI が書く報告の本文は無い")]
        self.assertEqual(len(lines), 1, "前の周の訳を置き換える")
        self.assertIn("used up", lines[0])
        self.assertIn(answer.resume("run-1"), lines[0])
        self.assertIn("鎖の run を resume する", lines[0])

    def test_rewritten_run_drops_the_note_and_untouched_report_stays(self):
        runreport.note_writer_fell(self.machine, None, run_id="run-1")
        self.assertEqual(self.machine.read_text(encoding="utf-8"), self.MACHINE)
        runreport.note_writer_fell(self.machine, {"error": "used up", "quota": True}, run_id="run-1")
        runreport.note_writer_fell(self.machine, None, run_id="run-1")
        self.assertEqual(self.machine.read_text(encoding="utf-8"), self.MACHINE)


class DecisionsCase(Base):
    def test_stopped_head_says_why_and_what_to_do(self):
        """#383 の 9: R2 が redesign-needed で無人の run が最後の承認ノードの手前で止まった時、冒頭 1 行目に止めた語・開けた理由・
        通さなかった目（R2・状態の語・訳）が、2 行目に人の取る手（差分を当てる行）が出る。節 1 に 0 件の種の行は出ない（元の head3・
        head_decisions は在る種だけを出した）"""
        eyes = {**fixed_run()["eyes"], "r2": {"status": "redesign-needed", "reason": "独立設計と食い違う"}}
        line = {"stops": {"ask-final": stopby.NEEDS_HUMAN}, "final_reasons": ["独立の目が通さなかった（R2: 作り直しが要る）"]}
        seal = {"mode": "seal", "ok": True, "diff": "merge/sealed.diff"}
        _, text, decided = self.build(fixed_run(eyes=eyes, **{"sealed-diff": seal, "applied-diff": None}), line=line)
        self.assertEqual(decided[0], "needs_human")
        head = text.splitlines()[2:5]
        self.assertIn(f"ask-final が {stopby.NEEDS_HUMAN}（{stopby.REASONS['needs-human']}）", head[0])
        self.assertIn("開けた理由: 独立の目が通さなかった（R2: 作り直しが要る）", head[0])
        self.assertIn(f"{gatemarks.eye_named('R2', 'redesign-needed')}——独立設計と食い違う", head[0])
        self.assertEqual(head[1], runreport.APPLY_ASK + "当てない（R2 が redesign-needed を言った run の差分は bin/apply も当てない）")
        decisions = self.section(text, report.DECISIONS_HEADING).splitlines()
        zero = [x for x in decisions if x.endswith(": 0 件")]
        self.assertEqual(zero, ["- 次の run に渡す物: 0 件"], "0 件で残すのは元の head_decisions が常に出した行だけ")
        self.assertTrue(any(x.startswith(f"- {conflict.HEAD}: 0 件") for x in decisions), "申し出の件数の行は元どおり 0 件でも出す")

    def test_stopped_head_says_fix_apart_from_redesign(self):
        """R1 が fix-needed、R2 が redesign-needed で止まった run の冒頭 1 行目は、直しが要る目と作り直しが要る目を別の言い方で並べる
        （直しが要る目を黙って落とさない）。残りの行と結果が無い目の注意に『阻害』の字は無い"""
        eyes = {**fixed_run()["eyes"], "r1": {"status": "fix-needed", "reason": "名前が揃っていない"},
                "r2": {"status": "redesign-needed", "reason": "独立設計と食い違う"}}
        line = {"stops": {"ask-final": stopby.NEEDS_HUMAN}, "final_reasons": []}
        seal = {"mode": "seal", "ok": True, "diff": "merge/sealed.diff"}
        _, text, _ = self.build(fixed_run(eyes=eyes, **{"sealed-diff": seal, "applied-diff": None}), line=line)
        first = text.splitlines()[2]
        fix_said, redesign_said = gatemarks.eye_named("R1", "fix-needed"), gatemarks.eye_named("R2", "redesign-needed")
        self.assertIn(f"{fix_said}——名前が揃っていない", first)
        self.assertIn(f"{redesign_said}——独立設計と食い違う", first)
        self.assertNotEqual(fix_said.split(": ", 1)[1], redesign_said.split(": ", 1)[1])
        self.assertNotIn("阻害", text)

    def test_backed_out_group_is_named_in_head_and_decisions(self):
        """#383 の 8（持ち主の決め clash-goes-to-ruling のそれまでの間）: 当ててから確かめ直しが赤で戻した組は、冒頭 1 行目で名指し、
        人が決めることの節の頭に組ごとの 3 行（組と単位・赤の文・合わせの結果）を置く。当てなかっただけの組は名指さない"""
        groups = [{"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""},
                  {"group_id": "g2", "unit_ids": ["B"], "returned": False, "reason": "意味の食い違い: test_triple が赤",
                   "backed_out": ["b.py", "e.py"]},
                  {"group_id": "g3", "unit_ids": ["C"], "returned": False, "reason": fixboard.NO_RESULT}]
        fix = {**fixed_run()["fix"], "groups": groups,
               "units": [{"unit_id": "B", "group_id": "g2", "status": "not_done", "reason": "組を戻した"}]}
        _, text, _ = self.build(fixed_run(fix=fix))
        head = text.splitlines()[2]
        self.assertIn(f"{runreport.BACKED_OUT_HEAD}: 組 g2", head)
        self.assertNotIn(f"{runreport.BACKED_OUT_HEAD}: 組 g3", head)
        self.assertIn(f"{runreport.BACKED_OUT_HEAD} 1 件", text.splitlines()[4], "#660: 戻した組は冒頭の件数に入る")
        self.assertIn(f"- {runreport.BACKED_OUT_HEAD}: 組 g2（単位 B）。戻したパス b.py・e.py", text.splitlines()[5:])
        body = self.section(text, report.DECISIONS_HEADING).splitlines()
        self.assertEqual(body[:3], [f"- {runreport.BACKED_OUT_HEAD}: 組 g2（単位 B）。戻したパス b.py・e.py",
                                    "  - 赤: 意味の食い違い: test_triple が赤",
                                    "  - 合わせの結果: 合わせ役が直していない。ほかの組は 1 組を当てたまま、外した単位 B は次の run の依頼に回した"])

    def test_backed_out_group_reaches_the_human_report_past_the_cut(self):
        """#660: 戻した組と当たったままの組は 1 組 1 件で人が決めることに数え、書き手の頭が切られても人に向けた報告の冒頭に残る。
        行の上限もその件を数える"""
        groups = [{"group_id": "g1", "unit_ids": ["A"], "returned": False, "reason": "赤", "backed_out": ["a.py"]},
                  {"group_id": "g2", "unit_ids": ["B"], "returned": False, "reason": fixboard.UNRESTORED_HEAD, "unrestored": ["b.py"]}]
        _, machine, _ = self.build(fixed_run(fix={**fixed_run()["fix"], "groups": groups, "units": []}))
        long = "\n".join(["要約。", "", "## 1. 人が決めること", "", *[f"- 行 {i}" for i in range(200)]])
        runreport.accept(json.dumps({"text": long, "terms": []}, ensure_ascii=False), AcceptCase.PASS, out_dir=self.out)
        human = runreport.collect(machine, out_dir=self.out, stamp="run x").read_text(encoding="utf-8").splitlines()
        self.assertTrue(human[4].startswith(runreport.DECIDE_HEAD + "2 件——"), human[4])
        self.assertTrue(human[5].startswith("- 戻せず親の作業ツリーに当たったままの組"), human[5])
        self.assertTrue(human[6].startswith("- 当ててから確かめ直しが赤か落ちて戻した組: 組 g1"), human[6])
        self.assertLessEqual(len(human), runreport.line_budget(2))

    def test_unit_and_premise_items_are_plain_lines(self):
        """#660: 直す義務に戻せなかった単位と前提の検算が人に上げた物は、冒頭の 1 件 1 行で JSON でなく id・判定と訳の 1 文"""
        fix = {**fixed_run()["fix"], "units": [{"unit_id": "u9", "group_id": "g1", "status": fixboard.NOT_DONE, "reason": "赤のまま"}]}
        eyes = {**fixed_run()["eyes"], "premise_check": {"verdict": "escalate", "reason": "仮定が偽"}}
        _, text, _ = self.build(fixed_run(fix=fix, eyes=eyes))
        head = text.split("\n## ", 1)[0].splitlines()
        self.assertIn("- 直す義務に戻せなかった単位: 単位 u9: 赤のまま", head)
        self.assertIn("- 前提の検算が人に上げた物: 検算の判定 escalate: 仮定が偽", head)
        self.assertFalse([x for x in head if "{" in x], head)

    def test_parked_clash_names_its_requests_and_patch(self):
        """#382: 合わせ役が直せず組どうしの合わせの申し出にした組（欄 clash の outcome parked）は、3 行目で申し出の id と控えの差分を
        名指す"""
        groups = [{"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""},
                  {"group_id": "g2", "unit_ids": ["B"], "returned": False, "reason": "意味の食い違い: test_triple が赤",
                   "backed_out": ["b.py", "e.py"], "clash": {"outcome": "parked", "requests": ["c1-1"], "patch": "join/g2.diff"}}]
        fix = {**fixed_run()["fix"], "groups": groups,
               "units": [{"unit_id": "B", "group_id": "g2", "status": "not_done", "reason": "組を戻した"}]}
        _, text, _ = self.build(fixed_run(fix=fix))
        body = self.section(text, report.DECISIONS_HEADING).splitlines()
        self.assertEqual(body[2], "  - 合わせの結果: 合わせ役が直せず、組どうしの合わせの申し出 c1-1 にした（控えの差分 join/g2.diff）。"
                                  "ほかの組は 1 組を当てたまま、外した単位 B は次の run の依頼に回した")

    def test_repaired_clash_is_named_without_parked_groups(self):
        """#382: 止めた組が無くても、合わせ役が直して当てた組（returned で clash の outcome repaired）は冒頭の 1 文で名指す"""
        groups = [{"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""},
                  {"group_id": "g2", "unit_ids": ["B"], "returned": True, "reason": "", "backed_out": ["b.py"],
                   "clash": {"outcome": "repaired", "requests": [], "patch": "join/g2.diff"}}]
        returns = fixed_run(fix={**fixed_run()["fix"], "groups": groups})
        self.assertEqual(runreport.split_line(returns), f"{runreport.REPAIRED_HEAD}: 組 g2")
        self.assertEqual(runreport.backed_out_lines(returns), [], "直して当てた組は戻した組に数えない")

    def test_unrestored_group_is_named_as_still_applied(self):
        """#403: 戻せず親の作業ツリーに当たったままの組は、当てなかった組と分けて冒頭 1 行目で名指し、人が決めることの節の頭に
        当たったままのパスと訳を置く。#406: 確かめ直しが落ちて戻した組は、赤で戻した組と同じく名指す"""
        groups = [{"group_id": "g1", "unit_ids": ["A"], "returned": False, "reason": "当てた後の確かめ直しが落ちた（RuntimeError: x）",
                   "backed_out": ["a.py"]},
                  {"group_id": "g2", "unit_ids": ["B"], "returned": False, "reason": fixboard.UNRESTORED_HEAD + "（OSError: y）",
                   "unrestored": ["b.py"]}]
        fix = {**fixed_run()["fix"], "groups": groups, "units": []}
        _, text, _ = self.build(fixed_run(fix=fix))
        head = text.splitlines()[2]
        self.assertIn(f"{runreport.BACKED_OUT_HEAD}: 組 g1", head)
        self.assertIn(f"{runreport.UNRESTORED_GROUP_HEAD}: 組 g2", head)
        body = self.section(text, report.DECISIONS_HEADING).splitlines()
        self.assertEqual(body[:2], [f"- {runreport.UNRESTORED_GROUP_HEAD}: 組 g2（単位 B）。当たったままのパス b.py",
                                    f"  - 訳: {fixboard.UNRESTORED_HEAD}（OSError: y）"])
        self.assertIn(f"- {runreport.BACKED_OUT_HEAD}: 組 g1（単位 A）。戻したパス a.py", body)

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
        self.assertTrue(text.splitlines()[4].startswith(runreport.DECIDE_HEAD + "2 件"), text.splitlines()[4])
        self.assertIn(f"{fixboard.HANDOFF_HEAD} 2 件", text.splitlines()[4])
        self.assertEqual(text.splitlines()[5:7], [f"- {fixboard.HANDOFF_HEAD}: u1: 壊すと分かって通した——古い呼び手が壊れる",
                                                  f"- {fixboard.HANDOFF_HEAD}: u2: 壊すと分かって通した——既定が変わる"],
                         "人が決める物は冒頭に 1 件 1 行。問いでない物に推しの尾は付けない")
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

    def test_many_removed_files_keep_the_section_short(self):
        """clean が消したファイルが 20,000 本でも、人が決めることの節は本数に依らず短い。件数の行・先頭の数本・上位のフォルダごとの本数
        （根に直に在るファイルは 1 つの区分『（根）』）・全件の置き場（根と scope の両方の fix-removed.json）を出し、全部のパスは並べない"""
        diff = self.fix_place("fix")
        folder = pathlib.Path(diff).parent
        root = [f"r{i}.log" if i % 10 == 0 else f"{('cache', 'dist', 'build', 'tmp')[i % 4]}/a/{i}.bin" for i in range(19990)]
        scoped = [f"gen/{i}.o" for i in range(10)]
        fixboard.write_json(folder / "fix-removed.json", {"removed": root})
        (folder / "sub").mkdir()
        fixboard.write_json(folder / "sub" / "fix-removed.json", {"removed": scoped})
        _, text, _ = self.build(self.with_fix(diff))
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertLessEqual(len(body.splitlines()), 40, body[:2000])
        self.assertLess(len(body), 6000)
        self.assertIn("- clean が消したファイル（fix）: 20000 本", body)
        self.assertIn("  - " + root[0], body)
        self.assertNotIn(root[100], body)
        self.assertIn(f"（全件: {folder / 'fix-removed.json'}、{folder / 'sub' / 'fix-removed.json'}）", body)
        self.assertIn("  - 上位のフォルダごとの本数:", body)
        self.assertIn("    - （根）: 1999 本", body)
        self.assertIn("    - dist: 4998 本", body)
        self.assertNotIn("    - r10.log", body)

    def test_nothing_to_decide_puts_next_items(self):
        """元 ReportHeadCase.test_nothing_to_decide_puts_next_items: 決めることが無い run は 2 行目に次の run に渡す物の件数"""
        p = self.put("judge/out-of-purpose.json", {"rounds": {"1": [{"source": "P1", "why_outside": "目的の外の所見",
                                                                    "found": [{"where": "a.py:1", "text": "x"},
                                                                              {"where": "b.py:2", "text": "y"}]}]}})
        judge = {**fixed_run()["judge"], "out_of_purpose": p}
        _, text, _ = self.build(fixed_run(judge=judge))
        lines = text.splitlines()
        self.assertEqual(lines[2], gatemarks.HAPPENED + report.OUTCOME_WORDS["fixed"] + "（fixed）")
        self.assertEqual(lines[3], runreport.APPLY_ASK + "当てる差分が無い（差分を封じていない）")
        self.assertEqual(lines[4], "次の run に渡す物: 2 件")
        self.assertEqual(lines[5], "", "人が決める物の行は無い")

    def test_decisions_are_counted(self):
        """元 ReportHeadCase.test_decisions_are_counted"""
        review = {"pass": True, "ask_human": True, "questions": [gatemarks.question_row("fork", "どちらに寄せるか／推し: 通す（continue）——小さい方（理由: 速い）")]}
        eyes = {**fixed_run()["eyes"], "questions": ["守りを触ってよいか"]}
        _, text, _ = self.build(fixed_run(eyes=eyes, **{"plan-review": review}), gates={"before-fix-answer": {"decision": "approve", "text": ""}})
        third = text.splitlines()[4]
        self.assertTrue(third.startswith(runreport.DECIDE_HEAD + "2 件"), third)
        self.assertEqual(text.splitlines()[5:7], ["- 修正前の問い: どちらに寄せるか／推し: 通す（continue）——小さい方（理由: 速い）",
                                                  f"- 独立の目 R4 の問い: 守りを触ってよいか——{gatemarks.PUSH}{gatemarks.NO_PUSH}"],
                         "推しは判定の役が書いた物を 1 件ごとに、無ければ書いていないと言う")

    def test_question_answered_at_the_gate_is_not_counted(self):
        """修正前の承認ノードが通す語で答えた問い（答えの asked の行）は人が決めることと冒頭の件数・推しから外し、答えた問いの行に出す。
        関所が開かなかった run（無人の run の plan-review:ask-human）は今どおり数える"""
        text_q = "どちらに寄せるか／推し: 通す（continue）——小さい方（理由: 速い）"
        review = {"pass": True, "ask_human": True, "questions": [gatemarks.question_row("fork", text_q)]}
        eyes = {**fixed_run()["eyes"], "questions": ["守りを触ってよいか"]}
        returns = fixed_run(eyes=eyes, **{"plan-review": review})
        _, text, _ = self.build(returns, gates={"before-fix-answer": {"decision": "approve", "text": "", "asked": [text_q]}})
        head = text.splitlines()
        self.assertTrue(head[4].startswith(runreport.DECIDE_HEAD + "1 件——独立の目 R4 の問い 1 件"), head[4])
        self.assertNotIn("小さい方", "\n".join(head[5:7]))
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertNotIn("- 修正前の問い:", body)   # 0 件の種は出さない（#383 の項目 9）。答えた問いは数えない
        self.assertIn(f"- {gatemarks.ANSWERED_HEAD}（1 件。保留と人が決めることの件数には数えない）:\n  - {text_q}", body)
        for gates in ({}, {"before-fix-answer": {"decision": "stop", "text": "止める", "asked": [text_q]}}):
            with self.subTest(gates=gates):
                _, text, _ = self.build(returns, gates=gates)
                self.assertTrue(text.splitlines()[4].startswith(runreport.DECIDE_HEAD + "2 件——修正前の問い 1 件"), text.splitlines()[4])
                self.assertNotIn(gatemarks.ANSWERED_HEAD, text)

    def test_unreturned_unit_is_counted_as_decision(self):
        """元 ReportHeadCase.test_unreturned_unit_is_counted_as_decision: 関所で答えたが直す義務に戻せなかった単位（fix の not_done）"""
        fix = {**fixed_run()["fix"], "units": [{"unit_id": "u9", "status": "not_done", "reason": "案の直しを待つ"}]}
        _, text, decided = self.build(fixed_run(fix=fix))
        self.assertEqual(decided[0], "round_limit")
        self.assertEqual(text.splitlines()[4], runreport.DECIDE_HEAD + "1 件——直す義務に戻せなかった単位 1 件（1 件ずつ下の行。詳しくは見出しに"
                         f"「{report_roles.DECISIONS_HEAD}」を持つセクション）",
                         "round_limit の残りの同じ単位の行を重ねて数えない")
        self.assertIn("u9", self.section(text, report.DECISIONS_HEADING))

    def test_checks_left_are_counted_as_decision(self):
        """元 ReportHeadCase.test_checks_left_are_counted_as_decision"""
        judgment = self.put("judge/judgment.json", {})
        materials = self.put("judge/materials.json", {"parallel_pr": {"status": "not_run"}})
        _, text, decided = self.build(fixed_run(judge={**fixed_run()["judge"], "judgment": judgment, "materials": materials}))
        self.assertEqual(decided[0], "fixed_needs_check")
        self.assertTrue(text.splitlines()[2].startswith(gatemarks.HAPPENED + report.OUTCOME_WORDS["fixed_needs_check"]))
        self.assertIn(f"{report.CHECKS_LEFT} 1 件", text.splitlines()[4])
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
        world = self.put("judge/world.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in (
            WORLD_ROW, {**WORLD_ROW, "finding": 2, "class_id": "w-empty"})))
        plan = self.put("plan/plan-fields.json", {"round": 1, "fields": [{"structure": [
            {"world": "w-mean", "deviation": "呼び手の都合で 0 を返す形に寄せたい、と考えた"}]}]})
        fix_plan = self.put("plan/p2.fix_plan.json", {"plan": [{"unit_keys": ["u1"], "narrows": [{**NARROW, **DECIDED}]}]})
        line = worldmark.gate_line(WORLD_ROW, {"world": "w-mean", "deviation": "呼び手の都合で 0 を返す形に寄せたい、と考えた"})
        review = {"pass": True, "ask_human": True, "questions": [gatemarks.question_row("world", f"修正案 1 の{line}（人に聞く訳: 依頼を出どころにした外れ）")]}
        returns = fixed_run(judge={**fixed_run()["judge"], "world": world}, plan={**fixed_run()["plan"], "plan": plan, "fix_plan": fix_plan},
                            **{"plan-review": review}, eyes={**fixed_run()["eyes"], "questions": gatemarks.row_texts(review["questions"])})
        drafts = runreport.answer_drafts(returns, {}, UNATTENDED)
        self.assertEqual(len(drafts), 1, drafts)
        self.assertIn("w-mean", drafts[0]["question"])
        self.assertIn("呼び手の都合", drafts[0]["note"], "推しの無い外れは、外れの訳と世界の解を材料に置く")

    def test_recommend_of_the_narrow_becomes_the_answer(self):
        """元 gatemarks._gate_draft: 修正案の狭める行の推し（recommend）が答えの下書きになる"""
        plan = self.put("plan/plan-fields.json", {"round": 1, "fields": []})
        rec = {"answer": "continue", "note": "例外にそろえる", "why": "呼び手が既に例外を捕まえている"}
        fix_plan = self.put("plan/p2.fix_plan.json", {"plan": [{"unit_keys": ["u1"], "narrows": [{**NARROW, "recommend": rec}]}]})
        q = f"修正案 1 が狭める能力: {NARROW['what']}——{NARROW['why']}（世界の解: 役が書いていない）"
        returns = fixed_run(plan={**fixed_run()["plan"], "plan": plan, "fix_plan": fix_plan},
                            **{"plan-review": {"ask_human": True, "questions": [gatemarks.question_row("regression", q)]}})
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
        passed = {"before-fix-answer": {"decision": "continue", "text": ""}}
        self.assertEqual(len(runreport.answer_drafts(returns, passed, {"run_id": RUN})), 1, "関所が聞いていない問いは答えていない")
        passed = {"before-fix-answer": {"decision": "continue", "text": "", "asked": [gatemarks.ask_text(FORK)]}}
        self.assertEqual(runreport.answer_drafts(returns, passed, {"run_id": RUN}), [])
        held = {"before-fix-answer": {"decision": "continue", "text": f"保留: {FORK['key']}", "asked": [gatemarks.ask_text(FORK)]}}
        self.assertEqual(len(runreport.answer_drafts(returns, held, {"run_id": RUN})), 1)
        returns = fixed_run(judge=returns["judge"])
        _, text, _ = self.build(returns)
        self.assertIn("保留にしたままの問い 1 件", text.splitlines()[4])

    def test_unattended_held_question_with_nothing_owed_waits_in_decisions(self):
        """#283: 無人の run で、単位 1 つがその単位を出どころにした推しの無い保留の問い 1 つの答え待ちで、計画が直す義務 0 件で役を
        起こさなかった周は、線の止め（計画の諦め）にならず、問いが報告の冒頭 2 行目と人が決めることに載る（#593: 推しの無い問いは止まる）"""
        judgment = self.put("judge/judgment.json", {"units": [{"key": FORK_UNIT, "label": "block"}],
                                                    "questions": [{**FORK, "reason": "空の列の意味が 2 つに割れる"}]})
        fields = self.put(f"plan/r1/{planfile.planmarks.FIELDS_FILE}", {"round": 1, "fields": []})
        returns = fixed_run(judge={**fixed_run()["judge"], "judgment": judgment}, plan={"ready": False, "plan": fields, "nothing_owed": True},
                            fix=None,
                            eyes=None, **{"plan-review": None, "final-tests": None, "sealed-diff": None, "applied-diff": None})
        _, text, decided = self.build(returns, start=UNATTENDED)
        self.assertEqual(decided, ("round_limit", ""))
        self.assertIn("保留にしたままの問い 1 件", text.splitlines()[4])
        self.assertIn(FORK["key"], self.section(text, report.DECISIONS_HEADING))
        self.assertNotIn(runreport.PLAN_GAVE_UP_WHERE, [r["where"] for r in runreport.prior_failures(returns, [], {})])

    def test_unattended_run_takes_the_held_fork_push_in_the_head(self):
        """#593: 無人の run が推しを答えに採った台帳の問いは、承認ノードの推しと同じく冒頭 1 行目と人が決めることに並び、保留に数えず、
        下書きにもしない。人のいる run は今どおり保留にしたままの問いに数える"""
        judgment = self.put("judge/judgment.json", {"units": [{"key": FORK_UNIT, "label": "block"}], "questions": [FORK]})
        returns = fixed_run(judge={**fixed_run()["judge"], "judgment": judgment})
        _, text, _ = self.build(returns, start=UNATTENDED)
        lines = text.splitlines()
        self.assertIn(f"無人の run で推しを採って答えた台帳の問い: {FORK['key']}（推し 1 件。", lines[2])
        self.assertIn(f"無人の run で推しを採って答えた（{gatemarks.ASK_HEAD} {FORK['key']}）: 推し: 例外——呼び手が既に例外を捕まえている——"
                      f"出どころ・depends の単位 {FORK_UNIT} を直す義務に戻した", self.section(text, report.DECISIONS_HEADING))
        self.assertIn(gatemarks.PUSH_TAKEN, text)
        self.assertNotIn("保留にしたままの問い", text)
        self.assertEqual(runreport.answer_drafts(returns, {}, UNATTENDED), [])
        _, text, _ = self.build(returns)
        self.assertNotIn("無人の run で推しを採って答えた", text)
        self.assertIn("保留にしたままの問い 1 件", text.splitlines()[4])

    def test_unmeasured_material_draft_carries_its_reason(self):
        judgment = self.put("judge/judgment.json", {})
        materials = self.put("judge/materials.json", {"parallel_pr": {"status": "not_run", "reason": "forge が無い"}})
        returns = fixed_run(judge={**fixed_run()["judge"], "judgment": judgment, "materials": materials})
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
        self.assertEqual(runreport.answer_drafts(returns, {"before-fix-answer": {"decision": "approve", "text": ""}},
                                                 {"run_id": RUN}), [])
        self.assertEqual(runreport.answer_drafts(returns, {"before-fix-answer": {"decision": "continue", "text": ""}}, UNATTENDED), [])

    def test_no_narrow_and_face_rows_give_their_marks(self):
        """元 gatemarks._gate_draft: 推しの無い修正案の狭める行は狭めない案（no_narrow）を、事前審査の人に回す種類の穴は穴の行の
        決め手を、材料として note に置く"""
        plan = self.put("plan/plan-fields.json", {"round": 1, "fields": []})
        fix_plan = self.put("plan/p2.fix_plan.json", {"plan": [{"unit_keys": ["u1"], "narrows": [{**NARROW, "no_narrow": "例外にそろえて呼び手を直す"}]}]})
        review = self.put("plan-review/review.json", {"faces": [{**FACE, "no_narrow": "上限を変えずに足す"},
                                                               {**FACE, "key": "見た目", "kind": "style"}]})
        narrow = f"修正案 1 が狭める能力: {NARROW['what']}——{NARROW['why']}"
        face = f"事前審査の穴 [regression] {FACE['key']}: {FACE['why']}"
        returns = fixed_run(plan={**fixed_run()["plan"], "plan": plan, "fix_plan": fix_plan},
                            **{"plan-review": {"review": review, "questions": [gatemarks.question_row(k, t) for k, t in (
                                ("regression", narrow), ("regression", face), ("style", f"事前審査の穴 [style] 見た目: {FACE['why']}"))]}})
        drafts = runreport.answer_drafts(returns, {}, UNATTENDED)
        self.assertEqual([d["text"] for d in drafts], ["", "", ""])
        self.assertIn("狭めない案: 例外にそろえて呼び手を直す", drafts[0]["note"])
        self.assertIn(gatemarks.NO_NARROW, drafts[0]["source"])
        self.assertIn("狭めない案: 上限を変えずに足す", drafts[1]["note"])
        self.assertIn("決め手の欄が無い", drafts[2]["source"], "人に回さない種類の穴は事前審査の行に結ばない")

    def test_final_gate_r4_questions_are_drafted_even_when_passed(self):
        """独立の目 R4 の問いごとに下書き。関所の continue は問いに答えないので、人の居る run でも関所が通した run でも作る（元
        skills/works/SKILL.md 119 行「問いは報告の冒頭と次の run の依頼の下書きに載り、結末は needs_human」。#505）"""
        eyes = {**fixed_run()["eyes"], "questions": ["守りを触ってよいか／推し: 通す（continue）——触らない（理由: 守りは別の PR）"]}
        returns = fixed_run(eyes=eyes)
        drafts = runreport.answer_drafts(returns, {}, UNATTENDED)
        self.assertEqual([(d["question"], d["text"]) for d in drafts], [("守りを触ってよいか", "通す（continue）——触らない（理由: 守りは別の PR）")])
        for start in (UNATTENDED, {"run_id": RUN}):
            with self.subTest(start=start):
                self.assertEqual(runreport.answer_drafts(returns, {"final-answer": {"decision": "continue", "text": ""}}, start), drafts)

    def test_drafts_reach_next_request(self):
        returns = fixed_run(**{"plan-review": {"questions": [gatemarks.question_row("regression", "どうするか")]}})
        got, _, _ = self.build(returns, start=UNATTENDED)
        doc = json.loads(pathlib.Path(got["next_request"]).read_text(encoding="utf-8"))
        self.assertEqual(carry.errors(doc, carry.NEXT_SCHEMA), [])
        self.assertEqual([a["question"] for a in doc[carry.ANSWERS]], ["どうするか"])

    def test_spec_changed_reaches_head_and_next_request(self):
        """#510: 承認の後に受け入れ条件のテストが変わった問いは、結末を人待ちにし、冒頭（止めの語の意味と人が決めることの件数）と
        次の依頼の下書き（答えの空の行）に載る"""
        q = "承認の後に受け入れ条件のテストが変わった（spec_changed）: t.txt（sha256 aaaaaaaaaaaa → 消えた）——承認し直すか"
        got, text, decided = self.build(line={"spec_changed": [q], "spec_unchecked": False,
                                              "stops": {"spec-check": stopby.SPEC_CHANGED}})
        self.assertEqual(decided, ("needs_human", f"spec-check:{stopby.SPEC_CHANGED}"))
        head = "\n".join(text.splitlines()[2:6])
        self.assertIn(stopby.REASONS["spec-changed"], head)
        self.assertIn(f"{gatemarks.SPEC_CHANGED_HEAD} 1 件", head)
        doc = json.loads(pathlib.Path(got["next_request"]).read_text(encoding="utf-8"))
        self.assertEqual(carry.errors(doc, carry.NEXT_SCHEMA), [])
        self.assertEqual([(a["question"], a["text"], a["draft"]) for a in doc[carry.ANSWERS]], [(q, "", True)])
        self.assertTrue(doc[carry.ANSWERS][0]["source"].startswith(gatemarks.SPEC_CHANGED_LABEL))
        self.assertEqual(doc[carry.ANSWERS][0]["note"], gatemarks.spec_words(False).note)

    def test_spec_unchecked_says_could_not_check(self):
        """#550: 照らせなかった時は、結末と止めは変わった時と同じで、冒頭の見出しと下書きの source と注 note が「照らせなかった」と言い、
        注は変更を確かめろとは言わない"""
        q = "照らしが落ちた——承認済みの受け入れ条件のテストが変わったかを確かめられない（ValueError: x）"
        got, text, decided = self.build(line={"spec_changed": [q], "spec_unchecked": True,
                                              "stops": {"spec-check": stopby.SPEC_CHANGED}})
        self.assertEqual(decided, ("needs_human", f"spec-check:{stopby.SPEC_CHANGED}"))
        head = "\n".join(text.splitlines()[2:6])
        self.assertIn(f"{gatemarks.SPEC_UNCHECKED_HEAD} 1 件", head)
        self.assertNotIn(gatemarks.SPEC_CHANGED_HEAD, text)
        doc = json.loads(pathlib.Path(got["next_request"]).read_text(encoding="utf-8"))
        self.assertEqual(carry.errors(doc, carry.NEXT_SCHEMA), [])
        self.assertEqual([(a["question"], a["draft"]) for a in doc[carry.ANSWERS]], [(q, True)])
        self.assertTrue(doc[carry.ANSWERS][0]["source"].startswith(gatemarks.SPEC_UNCHECKED))
        self.assertEqual(doc[carry.ANSWERS][0]["note"], gatemarks.spec_words(True).note)
        self.assertNotIn("変更を確かめ", doc[carry.ANSWERS][0]["note"])

    def test_spec_unchecked_unknown_says_could_not_check(self):
        """判らない（線の値に spec_unchecked が無い）時は、照らせなかった側に倒す: 冒頭の見出し・下書きの source・注が「照らせなかった」と言う"""
        q = "照らしが落ちた——承認済みの受け入れ条件のテストが変わったかを確かめられない（ValueError: x）"
        got, text, _ = self.build(line={"spec_changed": [q], "stops": {"spec-check": stopby.SPEC_CHANGED}})
        head = "\n".join(text.splitlines()[2:5])
        self.assertIn(f"{gatemarks.SPEC_UNCHECKED_HEAD} 1 件", head)
        self.assertNotIn(gatemarks.SPEC_CHANGED_HEAD, text)
        doc = json.loads(pathlib.Path(got["next_request"]).read_text(encoding="utf-8"))
        self.assertTrue(doc[carry.ANSWERS][0]["source"].startswith(gatemarks.SPEC_UNCHECKED))
        self.assertEqual(doc[carry.ANSWERS][0]["note"], gatemarks.spec_words(True).note)
        self.assertNotIn("変更を確かめ", doc[carry.ANSWERS][0]["note"])


class GlossaryCase(unittest.TestCase):
    def test_only_terms_in_text(self):
        """語の定義の節は書き手の terms のうち本文に現れる語だけ（語の表の語は言い換えるので定義しない）"""
        sec = runreport.glossary_section("寄せて止めた", [{"term": "寄せ", "definition": "合わせること"}, {"term": "周", "definition": "一巡"}])
        self.assertIn("- 寄せ: 合わせること", sec)
        self.assertNotIn("一巡", sec)
        self.assertEqual(runreport.glossary_section("何も無い", []), "")

    def test_pack_terms_come_from_lib(self):
        """語の表は lib/glossary.json の記録の名と人に向けた言い方の対。言い方の字に表の語が混じらない（言い換えた文に内側の語が残らない）"""
        pack = runreport.pack_terms()
        self.assertTrue(any(t["term"] == "承認ノード" for t in pack))
        self.assertTrue(all(set(t) == {"term", "plain"} for t in pack))
        for t in pack:
            with self.subTest(t["term"]):
                self.assertEqual([u["term"] for u in pack if u["term"] in t["plain"]], [])

    def test_plain_words_swap_outside_code(self):
        """長い語から当て、`…` とコードの囲みの中は識別子とパスなので置き換えない。置き換えた語ごとに回数を返す"""
        pack = [{"term": "単位", "plain": "項目"}, {"term": "根本の単位", "plain": "直す項目"}]
        text, counts = runreport.plain_words("根本の単位と単位。`単位` は鍵\n```\n単位\n```\n単位", pack)
        self.assertEqual(text, "直す項目と項目。`単位` は鍵\n```\n単位\n```\n項目")
        self.assertEqual(counts, {"根本の単位": 1, "単位": 2})

    def test_plain_words_skip_katakana_words_that_only_contain_a_term(self):
        """片仮名の語は、長い片仮名語の一部（パイプライン・サブノード）なら置き換えない"""
        pack = [{"term": "ライン", "plain": "処理の段の組み合わせ"}, {"term": "ノード", "plain": "処理の段"}]
        text, counts = runreport.plain_words("パイプラインとライン。サブノードとノード", pack)
        self.assertEqual(text, "パイプラインと処理の段の組み合わせ。サブノードと処理の段")
        self.assertEqual(counts, {"ライン": 1, "ノード": 1})

    def test_plain_words_skip_compounds_that_only_contain_a_one_kanji_term(self):
        """#660: 漢字 1 字の語（周・柵）は、前後が漢字でない時だけ置き換え、熟語の一部（周囲・周知・一周・周辺）は残す"""
        text, counts = runreport.plain_words("前の周に戻り、周ごとに柵の印を見た。周囲と周知、一周、周辺")
        self.assertEqual(text, "前の判定から確かめまでの一巡に戻り、判定から確かめまでの一巡ごとに決まりを確かめる試験の印を見た。"
                               "周囲と周知、一周、周辺")
        self.assertEqual(counts, {"周": 2, "柵": 1})
        self.assertEqual(runreport.plain_words("周りを見た。3 周目")[0], "周りを見た。3 周目")

    def test_plain_words_keep_any_question_key_on_a_ledger_line(self):
        """#660: 問いの key は判定の役が書く自由な 1 行なので、空白・全角括弧・「（…・…）」を含んでも、key の後ろの印
        （kind・status と答えの印）が何であっても、key だけを字のまま残し、行の残りは言い換える"""
        noted = "・" + gatemarks.answer_note({"text": "柵で", "command": "ls", "output": "柵"})
        for key, kind, status, mark in (("parallel_pr: 単位の柵", "fork", "held", ""),
                                        ("柵（住処）", "fork", "held", ""),
                                        ("柵（住処・素材）", "fork", "held", ""),
                                        ("柵の住処（周）", "fork", "held", noted),
                                        ("ci（柵）", "awaiting", "held", ""),
                                        ("柵（周・住処）", "rule", "escalate", "")):
            with self.subTest(key=key):
                q = {"key": key, "kind": kind, "status": status, "reason": "柵が要る"}
                text = runreport.plain_words(gatemarks._ledger_line(q, mark))[0]
                self.assertIn(f" {key}（{kind}・{status}", text)
                self.assertNotIn(gatemarks.ASK_HEAD, text)
                self.assertNotIn("柵が要る", text)

    def test_plain_wording_keeps_the_meaning(self):
        """#660: 守りのパスは対象のリポジトリが守ると宣言したファイルも含み、承認ノードは無人の run では機械が通すので、言い方が
        工場の内輪や人の確認に寄らない。周・ノードも言い換える（定義の節を持たない語を人に向けた報告に字のまま残さない）"""
        text = runreport.plain_words("守りのパスに当たった差分。無人の run が推しで通した承認ノード。周 2 のノード")[0]
        self.assertIn("対象のリポジトリ", text)
        self.assertNotIn("工場自身", text)
        self.assertNotIn("人の確認", text)
        self.assertEqual([t["term"] for t in runreport.pack_terms() if t["term"] in text], [])


class AcceptCase(Base):
    REPLY = json.dumps({"text": "直した。\n\n## 1. 人が決めること\n\n無い", "terms": []}, ensure_ascii=False)
    PASS = json.dumps({"verdict": "pass", "stops": [], "guessed": [], "decidable": True})
    REDESIGN = json.dumps({"verdict": "redesign-needed", "stops": ["冒頭の 2 行目"], "guessed": [], "decidable": False},
                          ensure_ascii=False)

    def ai(self) -> dict:
        return json.loads((self.out / runreport.AI_FILE).read_text(encoding="utf-8"))

    def test_pass_is_taken(self):
        got = runreport.accept(self.REPLY, self.PASS, out_dir=self.out)
        self.assertEqual(got, {"done": True, "ok": True, "reason": "", "kind": "", "reason_file": "", "prev_file": ""})
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

    def test_head_notes_are_the_machines_not_the_writers(self):
        """#492・#514（#660 で形を変えた）: 冒頭の 1 行目は機械が組むので、試験が走っていない・段の一部しか走らせられていない・
        利用者の資格に届く環境で走らせたの句を書き手の頭に求めて拒まない。句は機械の冒頭のまま人に向けた報告の頭に載る"""
        self.out.mkdir(parents=True)
        partly = green_cert.ran_note(green=False, red_cause="incomplete", by="engine", steps={"ran": ["unit"], "unran": ["e2e"]})
        for note in (green_cert.NOT_RAN, partly, userenv.NOTE):
            with self.subTest(note=note):
                machine = f"# 報告\n\n起きたこと: 赤。{note}\n\n## 1. 人が決めること\n\n- 無い\n"
                (self.out / report.REPORT_FILE).write_text(machine, encoding="utf-8")
                (self.out / runreport.AI_FILE).unlink(missing_ok=True)
                self.assertTrue(runreport.accept(self.REPLY, self.PASS, out_dir=self.out)["ok"])
                head = runreport.collect(machine, out_dir=self.out, stamp="run x").read_text(encoding="utf-8").splitlines()[2]
                self.assertIn(runreport.plain_words(note)[0], head)

    def test_format_and_terms_rejected_first(self):
        bad_cell = json.dumps({"text": "| 項目 |\n|---|\n| 説明の文である。 |"}, ensure_ascii=False)
        self.assertEqual(runreport.accept(bad_cell, self.PASS, out_dir=self.out)["kind"], "format")
        bad_terms = json.dumps({"text": "x", "terms": [{"term": ""}]})
        self.assertEqual(runreport.accept(bad_terms, self.PASS, out_dir=self.out)["kind"], "answer")
        third = runreport.accept("壊れた", self.PASS, out_dir=self.out)
        self.assertTrue(third["done"])
        self.assertFalse(third["ok"])
        self.assertFalse(self.ai()["accepted"], "3 回とも拒めば受け取れなかった訳を残す")


    def kept_answer(self, out=None) -> dict:
        return json.loads(rolekit.candidate_path(out or self.out, runreport.REPORT_NODE).read_text(encoding="utf-8"))

    def kept_note(self, n: int, out=None) -> dict:
        return json.loads(handoff.path_of((out or self.out) / runreport.NOTE_ROUND.format(n=n)).read_text(encoding="utf-8"))

    @staticmethod
    def with_handoff(text: str, tag: str) -> str:
        return json.dumps({"text": text, "terms": [], "handoff": {
            "read": [{"path": f"{tag}.py", "lines": "1", "why": f"{tag}を読んだ"}], "kept": [f"{tag}の訳"],
            "set_aside": [{"option": f"{tag}の脇に置いた案", "why": f"{tag}の置いた訳"}], "open": [f"{tag}の迷い"]}},
                          ensure_ascii=False)

    def test_rejected_reply_is_kept_for_the_next_round(self):
        """拒んだ回の返答の本文 text・terms は rolekit の前の答えの控え candidate-report.json に残り、prev_file がそれを指す。handoff は
        その周のフォルダ report/r<n>/ の handoff.json に置かれ、自前の控えのファイルは作らず、どの控えにも欄 handoffs が無い。handoff は
        初見の読み手に貼る本文に入らない。handoff の無い返答の回は本文だけ新しくなり、その周のフォルダは作らない。受け取った回の prev_file は空"""
        terms = [{"term": "語", "definition": "定義"}]
        first = json.dumps({**json.loads(self.with_handoff("一回目の本文。\n\n## 1. 人が決めること\n\n無い", "a")), "terms": terms},
                           ensure_ascii=False)
        got = runreport.accept(first, self.REDESIGN, out_dir=self.out)
        self.assertEqual((got["done"], got["ok"]), (False, False))
        candidate = rolekit.candidate_path(self.out, runreport.REPORT_NODE)
        self.assertEqual(candidate.name, "candidate-report.json")
        self.assertEqual(got["prev_file"], str(candidate))
        self.assertEqual(self.kept_answer(), {"text": json.loads(first)["text"], "terms": terms})
        self.assertEqual(self.kept_note(1), json.loads(first)["handoff"], "メモは前もって作っていない report/r1/ に置かれる")
        self.assertEqual(sorted(p.name for p in self.out.iterdir()),
                         ["candidate-report.json", "r1", "rejects-report.json", "rejects-report.md"], "自前の控えのファイルは作らない")
        self.assertNotIn("a.py", runreport.cold_body(first, out_dir=self.out))
        self.assertNotIn("handoff", json.loads((self.out / "rejects-report.json").read_text(encoding="utf-8"))[-1])
        second = runreport.accept(self.REPLY, self.REDESIGN, out_dir=self.out)
        self.assertEqual(second["prev_file"], got["prev_file"])
        self.assertEqual(self.kept_answer(), {"text": json.loads(self.REPLY)["text"], "terms": []})
        self.assertFalse((self.out / runreport.NOTE_ROUND.format(n=2)).exists(), "メモの無い回は周のフォルダを作らない")
        self.assertEqual(self.kept_note(1), json.loads(first)["handoff"], "前の周のメモは変わらない")
        taken = runreport.accept(self.REPLY, self.PASS, out_dir=self.out)
        self.assertEqual((taken["ok"], taken["prev_file"]), (True, ""))
        for path in self.out.rglob("*.json"):
            self.assertNotIn("handoffs", path.read_text(encoding="utf-8"), path.name)
        # 本文が文字列でない・空白だけの回は拒否をそのまま返し、前の答えの控えもメモも書かない（前の回の控えを上書きしない）
        for n, text in enumerate(("  \n", 3, None)):
            with self.subTest(text=text):
                out = self.out / f"blank-{n}"
                runreport.accept(first, self.REDESIGN, out_dir=out)
                before = self.kept_answer(out)
                reply = json.dumps({"text": text, "terms": [], "handoff": json.loads(self.with_handoff("x", "z"))["handoff"]})
                got = runreport.accept(reply, self.PASS, out_dir=out)
                self.assertEqual((got["ok"], got["kind"], got["done"]), (False, "answer", False))
                self.assertEqual(self.kept_answer(out), before)
                self.assertFalse((out / runreport.NOTE_ROUND.format(n=2)).exists())
                self.assertEqual(self.kept_note(1, out), json.loads(first)["handoff"])
                # メモを置かなかった周は、次の周の節で「書かなかった」と断らず、置かれていないと名指す
                part = runreport.handoff_part(out)
                line = next(x for x in part.splitlines() if x.startswith("- r2"))
                self.assertIn(handoff.NONE, line)
                self.assertIn("置かれていない", handoff.NONE)
                self.assertIn("受け付けがメモを置かなかった", handoff.NONE)

    def test_second_rejection_keeps_the_first_handoff(self):
        """2 回拒んだ時、メモは並びに積まれず周ごとのファイルに 1 つずつ残る。前の答えの控えの本文は 2 回目"""
        first = self.with_handoff("一回目の本文", "a")
        second = self.with_handoff("二回目の本文", "b")
        runreport.accept(first, self.REDESIGN, out_dir=self.out)
        runreport.accept(second, self.REDESIGN, out_dir=self.out)
        self.assertEqual(self.kept_answer()["text"], "二回目の本文")
        self.assertEqual(self.kept_note(1), json.loads(first)["handoff"])
        self.assertEqual(self.kept_note(2), json.loads(second)["handoff"])
        # 書き手の指示書に差し込む字は、頼みと、今の周の前までの周ごとのメモ（古い順）。控えが読めない時は頼みだけ
        part = runreport.handoff_part(self.out)
        self.assertTrue(part.startswith(handoff.ASK))
        self.assertIn(handoff.USE, part)
        self.assertLess(part.index(str(handoff.path_of(self.out / "r1"))), part.index(str(handoff.path_of(self.out / "r2"))))
        self.assertNotIn("r3", part, "今の周の前までだけ")
        rolekit.rejects_path(self.out, runreport.REPORT_NODE).write_text("{壊れた", encoding="utf-8")
        self.assertEqual(runreport.handoff_part(self.out), handoff.ASK)

    def test_unreadable_previous_answer_stops_without_overwrite(self):
        """前の周のメモ report/r1/handoff.json が壊れていれば、上書きも次の周のメモ・前の答えの控えも書かず、1 回目で諦める"""
        for n, broken in enumerate(("{壊れた", "null", "[]")):
            with self.subTest(broken=broken):
                out = self.out / f"broken-{n}"
                prev = handoff.path_of(out / runreport.NOTE_ROUND.format(n=1))
                prev.parent.mkdir(parents=True)
                prev.write_text(broken, encoding="utf-8")
                rolekit.rejects_path(out, runreport.REPORT_NODE).write_text(
                    json.dumps([{"at": "x", "reason": "前", "kind": "cold"}]), encoding="utf-8")
                got = runreport.accept(self.with_handoff("本文", "a"), self.REDESIGN, out_dir=out)
                self.assertEqual(prev.read_text(encoding="utf-8"), broken, "上書きしない")
                self.assertFalse((out / runreport.NOTE_ROUND.format(n=2)).exists())
                self.assertFalse(rolekit.candidate_path(out, runreport.REPORT_NODE).exists())
                self.assertEqual((got["done"], got["ok"], got["prev_file"]), (True, False, ""))
                rows = json.loads(rolekit.rejects_path(out, runreport.REPORT_NODE).read_text(encoding="utf-8"))
                self.assertEqual(len(rows), 2)
                self.assertIs(rows[-1]["give_up"], True)
                self.assertIn("前の周の引き継ぎのメモ", rows[-1]["reason"])
                self.assertIn(str(prev), rows[-1]["reason"])
                ai = json.loads((out / runreport.AI_FILE).read_text(encoding="utf-8"))
                self.assertIs(ai["accepted"], False)
                self.assertEqual(ai["reason"], rolekit.gave_up_text(runreport.REPORT_NODE, 2, rows[-1]["reason"], at_once=True))
                self.assertIn("前の周の引き継ぎのメモ", ai["reason"])
                self.assertIn("前の周の引き継ぎのメモ", pathlib.Path(got["reason_file"]).read_text(encoding="utf-8"))

    def test_unwritable_candidate_gives_up_at_once(self):
        """前の答えの控え（candidate-report.json）に書けない時は、1 回目の拒否で諦めの行（give_up: true）を積む。AI_FILE には
        accepted: False と『前の答えの控え』を含む訳が残る。メモは置かない"""
        self.out.mkdir(parents=True)
        rolekit.candidate_path(self.out, runreport.REPORT_NODE).mkdir()
        got = runreport.accept(self.with_handoff("本文", "a"), self.REDESIGN, out_dir=self.out)
        self.assertEqual((got["done"], got["ok"], got["prev_file"]), (True, False, ""))
        rows = json.loads(rolekit.rejects_path(self.out, runreport.REPORT_NODE).read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 1)
        self.assertIs(rows[-1]["give_up"], True)
        self.assertIn("前の答えの控え", rows[-1]["reason"])
        ai = json.loads((self.out / runreport.AI_FILE).read_text(encoding="utf-8"))
        self.assertIs(ai["accepted"], False)
        self.assertIn("前の答えの控え", ai["reason"])
        self.assertFalse((self.out / runreport.NOTE_ROUND.format(n=1)).exists())
        # メモの控えに書けない時も同じく 1 回目で諦める（前の周のメモを次の周へ渡せない）
        blocked = self.out / "note-blocked"
        folder = blocked / runreport.NOTE_ROUND.format(n=1)
        folder.mkdir(parents=True)
        handoff.path_of(folder).with_name("handoff.json.tmp").mkdir()
        got = runreport.accept(self.with_handoff("本文", "a"), self.REDESIGN, out_dir=blocked)
        self.assertEqual((got["done"], got["ok"], got["prev_file"]), (True, False, ""))
        rows = json.loads(rolekit.rejects_path(blocked, runreport.REPORT_NODE).read_text(encoding="utf-8"))
        self.assertIs(rows[-1]["give_up"], True)
        self.assertIn(f"前の周の引き継ぎのメモ {handoff.path_of(folder)} に書けない", rows[-1]["reason"])
        self.assertNotIn("前の答えの控え", rows[-1]["reason"])


class ReportGiveUpCase(Base):
    """書き手の返答を諦めた 1 行の文は rolekit.gave_up_text の 1 か所が持つ"""

    def test_give_up_text_is_rolekit_text(self):
        bad_terms = json.dumps({"text": "x", "terms": [{"term": ""}]})
        for _ in range(rolekit.GIVE_UP_AFTER):
            runreport.accept(bad_terms, AcceptCase.PASS, out_dir=self.out)
        rows = rolekit.reject_rows(self.out, runreport.REPORT_NODE)
        self.assertIn("\n", rows[-1]["reason"], "拒否の文が複数の行でも諦めの文は 1 行")
        ai = json.loads((self.out / runreport.AI_FILE).read_text(encoding="utf-8"))
        self.assertEqual(ai["reason"], rolekit.gave_up_text(runreport.REPORT_NODE, len(rows), rows[-1]["reason"]))

    def test_rejects_live_in_the_rolekit_ledger_with_kind(self):
        """報告の書き手の拒否は rolekit の rejects-report.json に kind つきで積む（format・answer の順）。前の版の控え
        report-rejects.json と reject-<n>.md は作らない。reason_file は rejects-report.md で、それまでの拒否を全部持つ。
        読めない返答・空の返答・本文の無い返答も kind answer で積み、返りは {done, ok, reason, kind, reason_file, prev_file} の 6 欄"""
        bad_cell = json.dumps({"text": "| 項目 |\n|---|\n| 説明の文である。 |"}, ensure_ascii=False)
        bad_terms = json.dumps({"text": "x", "terms": [{"term": ""}]})
        first = runreport.accept(bad_cell, AcceptCase.PASS, out_dir=self.out)
        second = runreport.accept(bad_terms, AcceptCase.PASS, out_dir=self.out)
        self.assertEqual([(first["kind"], first["done"]), (second["kind"], second["done"])], [("format", False), ("answer", False)])
        rows = rolekit.reject_rows(self.out, runreport.REPORT_NODE)
        self.assertEqual([r["kind"] for r in rows], ["format", "answer"])
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), sorted(["rejects-report.json", "rejects-report.md", "candidate-report.json"]),
                         "メモの無い返答なので周のフォルダ r<n>/ は作られない")
        self.assertEqual(second["reason_file"], str(self.out / "rejects-report.md"))
        text = pathlib.Path(second["reason_file"]).read_text(encoding="utf-8")
        self.assertLess(text.index(first["reason"]), text.index(second["reason"]), "それまでの拒否を古い順に全部持つ")
        self.assertEqual(report_roles.count_rejects([{**r, "node": runreport.REPORT_NODE} for r in rows])[runreport.REPORT_NODE],
                         {"cold": 0, "format": 1, "answer": 1, "unknown": 0})
        # 読めない返答・空の返答・本文の無い返答は、口の既定の拒否でなく kind answer の行で積み、返りも同じ 6 欄
        for n, raw in enumerate(("壊れた", "", json.dumps({"terms": []})), 1):
            with self.subTest(raw=raw):
                out = self.out / f"unreadable-{n}"
                got = runreport.accept(raw, AcceptCase.PASS, out_dir=out)
                self.assertEqual(set(got), {"done", "ok", "reason", "kind", "reason_file", "prev_file"})
                self.assertEqual(got["prev_file"], "")
                self.assertFalse(rolekit.candidate_path(out, runreport.REPORT_NODE).exists())
                self.assertEqual(sorted(p.name for p in out.iterdir()), ["rejects-report.json", "rejects-report.md"])
                self.assertEqual((got["ok"], got["kind"]), (False, "answer"))
                self.assertEqual(got["reason_file"], str(out / "rejects-report.md"))
                self.assertEqual([r["kind"] for r in rolekit.reject_rows(out, runreport.REPORT_NODE)], ["answer"])
                self.assertEqual(report_roles.count_rejects(
                    [{**r, "node": runreport.REPORT_NODE} for r in rolekit.reject_rows(out, runreport.REPORT_NODE)]
                )[runreport.REPORT_NODE]["answer"], 1, "answer が unknown に化けない")

    def test_unusable_ledger_still_leaves_the_unaccepted_reason(self):
        """報告の控え rejects-report.json が読めない時、accept は落ちずに done 真・ok 偽を返し、AI_FILE に accepted: False と
        『拒否の控えが扱えない』を含む reason を書く。collect は None を返さず、受け取れなかった訳を報告に載せる。reason_file は空"""
        self.out.mkdir(parents=True)
        (self.out / "rejects-report.json").mkdir()
        for raw in (AcceptCase.REPLY, "壊れた"):
            with self.subTest(raw=raw[:3]):
                (self.out / runreport.AI_FILE).unlink(missing_ok=True)
                cold = AcceptCase.REDESIGN if raw == AcceptCase.REPLY else AcceptCase.PASS
                got = runreport.accept(raw, cold, out_dir=self.out)
                self.assertEqual((got["done"], got["ok"], got["reason_file"]), (True, False, ""))
                self.assertIn("拒否の控えが扱えない", got["reason"])
                ai = json.loads((self.out / runreport.AI_FILE).read_text(encoding="utf-8"))
                self.assertFalse(ai["accepted"])
                self.assertIn("拒否の控えが扱えない", ai["reason"])
                self.assertEqual(ai["rejects"], report_roles.count_rejects([]), "控えが読めない時は空として数える")
                path = runreport.collect("事実", out_dir=self.out, stamp="run x")
                self.assertIsNotNone(path)
                self.assertIn("拒否の控えが扱えない", path.read_text(encoding="utf-8"))
        # 通る返答は控えを読まずに受け取れる（数えは空）
        (self.out / runreport.AI_FILE).unlink()
        ok = runreport.accept(AcceptCase.REPLY, AcceptCase.PASS, out_dir=self.out)
        self.assertEqual((ok["done"], ok["ok"]), (True, True))
        self.assertTrue(json.loads((self.out / runreport.AI_FILE).read_text(encoding="utf-8"))["accepted"])


class CollectCase(Base):
    def human(self) -> str:
        return (self.out / runreport.AI_REPORT_FILE).read_text(encoding="utf-8")

    def detail(self) -> str:
        return (self.out / runreport.DETAIL_FILE).read_text(encoding="utf-8")

    def test_no_ai_file_is_none(self):
        self.assertIsNone(runreport.collect("機械の事実", out_dir=self.out, stamp="run x"))
        self.assertFalse((self.out / runreport.DETAIL_FILE).exists())

    def test_taken_reply_becomes_ai_report(self):
        """#660: 人に向けた報告は機械の冒頭・書き手の頭・語の定義・詳細のファイルを指す 1 行と来歴。書き手の頭の後ろの本文と機械の
        事実は詳細のファイルにだけ在り、機械の事実の行は書き換えずに最後に付ける"""
        reply = json.dumps({"text": "直した。\n\n## 1. 人が決めること\n\n- 寄せるか\n\n## 2. 経緯\n\n長い経緯",
                            "terms": [{"term": "寄せ", "definition": "合わせること"}]}, ensure_ascii=False)
        runreport.accept(reply, AcceptCase.PASS, out_dir=self.out)
        machine = "# 報告（run x）\n\n起きたこと: 直した\n\n## 1. 人が決めること\n\n- 承認ノード: 開かなかった\n"
        path = runreport.collect(machine, out_dir=self.out, stamp="works-factory report / run x")
        self.assertEqual(path, self.out / runreport.AI_REPORT_FILE)
        human = self.human()
        self.assertTrue(human.startswith("# 報告（run x）\n\n起きたこと: 直した\n\n直した。\n\n## 1. 人が決めること"), human)
        self.assertIn("- 寄せ: 合わせること", human.split(report_roles.GLOSSARY_HEADING)[1])
        self.assertTrue(human.endswith(runreport.POINTER_LINE.format(file=runreport.DETAIL_FILE) + "\nworks-factory report / run x\n"))
        self.assertNotIn("長い経緯", human)
        self.assertNotIn(report_roles.MACHINE_HEADING, human)
        detail = self.detail()
        self.assertIn(f"{runreport.RAW_HEADING}\n\n{json.loads(reply)['text']}\n", detail)
        self.assertIn(report_roles.MACHINE_HEADING, detail)
        self.assertIn(f"{report_roles.COLD_REJECTS_LINE} 0 回", detail)
        self.assertTrue(detail.endswith("- 承認ノード: 開かなかった\n"), "機械の事実の行は書き換えずに最後に付ける")

    def test_sample_run_human_report_shape(self):
        """#660 の受け入れ（見本の run）: 人が決める物が 3 件の run の人に向けた報告は、冒頭に起きたこと・差分を当ててよいか・
        人が決めることの 3 行と 1 件 1 行の 3 行が並び、語の表の内側の語が無く、行は line_budget(3) までに収まる"""
        review = {"pass": True, "ask_human": True,
                  "questions": [gatemarks.question_row("fork", "どちらに寄せるか／推し: 通す（continue）——小さい方（理由: 速い）")]}
        eyes = {**fixed_run()["eyes"], "questions": ["守りのパスを触ってよいか"], "protected_hits": ["ci/deploy.yml"]}
        seal = {"mode": "seal", "ok": True, "diff": self.put("merge/sealed.diff", "")}
        _, machine, _ = self.build(fixed_run(eyes=eyes, **{"plan-review": review, "sealed-diff": seal}),
                                   gates={"before-fix-answer": {"decision": "approve", "text": ""}})
        parts = ["レンズ 2 本の指摘を直し、根本の単位 1 つを残した。", "", "## 1. 人が決めること", ""]
        for n in range(3):
            parts += [f"### {n + 1}. 問い {n + 1}", "- 何を決めるか: x", "- 背景: 単位 a の柵", "- 選択肢: A か B", "- 推し: A",
                      "- 決めないと: 止まる", ""]
        parts += ["## 2. 入口と依頼", "", *[f"- 経緯 {i}" for i in range(400)]]
        runreport.accept(json.dumps({"text": "\n".join(parts), "terms": []}, ensure_ascii=False), AcceptCase.PASS, out_dir=self.out)
        lines = runreport.collect(machine, out_dir=self.out, stamp="run x").read_text(encoding="utf-8").splitlines()
        self.assertTrue(lines[2].startswith(gatemarks.HAPPENED), lines[2])
        self.assertEqual(lines[3], runreport.APPLY_ASK + f"人が決めること 3 件を決めてから当てる（bin/apply {RUN}）")
        self.assertTrue(lines[4].startswith(runreport.DECIDE_HEAD + "3 件——"), lines[4])
        self.assertEqual(len([x for x in lines[5:8] if x.startswith("- ")]), 3, lines[5:8])
        self.assertEqual(lines[8], "")
        text = "\n".join(lines)
        self.assertEqual([t["term"] for t in runreport.pack_terms() if t["term"] in text], [])
        self.assertLessEqual(len(lines), runreport.line_budget(3))
        self.assertNotIn("経緯 0", text)

    def test_inner_words_are_swapped_only_in_the_human_report(self):
        """#660: 人に向けた報告は語の表の語を言い換え、詳細のファイルが書き手の字のままの本文と、言い換えた語と回数の 1 行を持つ"""
        reply = json.dumps({"text": "レンズが根本の単位を見た。`fix__lens` は名", "terms": []}, ensure_ascii=False)
        runreport.accept(reply, AcceptCase.PASS, out_dir=self.out)
        human = runreport.collect("# 報告\n\n起きたこと: 承認ノードで止めた\n", out_dir=self.out, stamp="run x").read_text(encoding="utf-8")
        for t in runreport.pack_terms():
            self.assertNotIn(t["term"], human.replace("`fix__lens`", ""))
        self.assertIn("観点ごとの見直しが直す項目を見た。`fix__lens` は名", human)
        detail = self.detail()
        self.assertIn("レンズが根本の単位を見た。", detail)
        self.assertIn(f"- {runreport.SWAPPED_HEAD}: 承認ノード→先へ進めるかを決める所 1 回・レンズ→観点ごとの見直し 1 回・根本の単位→直す項目 1 回",
                      detail)

    def test_human_report_is_cut_to_the_line_budget(self):
        """#660: 書き手の頭が長くても、人に向けた報告は line_budget（人が決める物の件数）の行に収まり、切った残りの行数と置き場を
        1 行で言う。切った所がコードの囲みの中なら閉じる。全文は詳細のファイルに在る"""
        long = "\n".join(["要約。", "", "## 1. 人が決めること", "", "```", *[f"行 {i}" for i in range(200)], "```"])
        runreport.accept(json.dumps({"text": long, "terms": []}, ensure_ascii=False), AcceptCase.PASS, out_dir=self.out)
        machine = "# 報告\n\n起きたこと: 赤\n差分を当ててよいか: 無い\n人が決めること: 2 件\n- a: x\n- b: y\n"
        human = runreport.collect(machine, out_dir=self.out, stamp="run x").read_text(encoding="utf-8")
        self.assertLessEqual(len(human.splitlines()), runreport.line_budget(2), human)
        [cut] = [x for x in human.splitlines() if runreport.DETAIL_FILE in x and "行は" in x]
        self.assertRegex(cut, r"ここから先 \d+ 行は")
        body = human.split(cut)[0]
        self.assertEqual(sum(1 for x in body.splitlines() if x.startswith("```")) % 2, 0, "コードの囲みを閉じる")
        self.assertIn("行 199", self.detail())

    def test_cut_right_after_an_opening_fence_opens_no_new_fence(self):
        """#660: 切って落ちた行が囲みの開く印なら、閉じる印を足さない（足すと新しい囲みが開き、切った訳の 1 行がコードに入る）"""
        cut = runreport._cut("a\nb\nc\n```\nx\ny\n```\nz", 5)
        self.assertEqual(cut.splitlines()[:3], ["a", "b", "c"])
        self.assertEqual(runreport._fences(cut.splitlines()), [])

    def test_definitions_are_kept_and_follow_the_shown_head(self):
        """#660: 書き手の頭が長くても語の定義は切られず、切った後に見えている頭に現れる語だけを並べる"""
        text = "\n".join(["寄せて直した。", "", "## 1. 人が決めること", "", *[f"- 行 {i}" for i in range(200)], "- 畳みの話"])
        terms = [{"term": "寄せ", "definition": "合わせること"}, {"term": "畳み", "definition": "後ろへ送ること"}]
        runreport.accept(json.dumps({"text": text, "terms": terms}, ensure_ascii=False), AcceptCase.PASS, out_dir=self.out)
        human = runreport.collect("# 報告\n\n起きたこと: 赤\n", out_dir=self.out, stamp="run x").read_text(encoding="utf-8")
        self.assertLessEqual(len(human.splitlines()), runreport.line_budget(0), human)
        self.assertNotIn("畳みの話", human)
        defined = human.split(report_roles.GLOSSARY_HEADING)[1]
        self.assertIn("- 寄せ: 合わせること", defined)
        self.assertNotIn("畳み", defined)

    def test_not_passed_is_said_at_the_head(self):
        """#660（#495 の形を変えた）: 初見の読み手が 3 回とも通さず受け取った報告は、人に向けた報告の冒頭（機械の冒頭の直後）でそれを
        1 行で言い、出し直しの命令は書かない。詳細のファイルは拒みの数の行の尾に同じ事実を持つ"""
        for _ in range(rolekit.GIVE_UP_AFTER):
            runreport.accept(AcceptCase.REPLY, AcceptCase.REDESIGN, out_dir=self.out)
        human = runreport.collect("# 報告\n\n起きたこと: 赤\n", out_dir=self.out, stamp="run x").read_text(encoding="utf-8")
        said = runreport.plain_words(report_roles.NOT_PASSED)[0]
        self.assertEqual(human.splitlines()[3].split("（")[0], said, human)
        self.assertIn("止まった所: 冒頭の 2 行目", human.splitlines()[3])
        self.assertEqual(human.count(said), 1)
        self.assertNotIn("出し直せ", human)
        [line] = [ln for ln in self.detail().splitlines() if report_roles.NOT_PASSED in ln]
        self.assertTrue(line.startswith(f"{report_roles.COLD_REJECTS_LINE} 2 回。{report_roles.NOT_PASSED}"), line)

    def test_words_only_on_the_not_passed_line_are_defined(self):
        """通らなかった事実の行にだけ在る語（判定を読めなかった事実の「初見の読み手」）も、人に向けた報告では言い換えて出る"""
        for _ in range(rolekit.GIVE_UP_AFTER):
            runreport.accept(AcceptCase.REPLY, "壊れた", out_dir=self.out)
        human = runreport.collect("事実", out_dir=self.out, stamp="run x").read_text(encoding="utf-8")
        self.assertIn(runreport.plain_words(runreport.COLD_UNREADABLE)[0], human)
        self.assertNotIn("初見の読み手", human)

    def test_not_passed_line_keeps_guesses_and_unreadable_verdict(self):
        """通らなかった事実の行は、止まった所だけでなく推測で埋めた所と、判定を読めなかった事実も落とさない"""
        guessed = json.dumps({"verdict": "redesign-needed", "stops": [], "guessed": ["語 X を推測"]}, ensure_ascii=False)
        for cold, want in ((guessed, "推測で埋めた所: 語 X を推測"), ("壊れた", runreport.COLD_UNREADABLE)):
            with self.subTest(want=want):
                out = self.out / want
                for _ in range(rolekit.GIVE_UP_AFTER):
                    runreport.accept(AcceptCase.REPLY, cold, out_dir=out)
                runreport.collect("事実", out_dir=out, stamp="run x")
                [line] = [ln for ln in (out / runreport.DETAIL_FILE).read_text(encoding="utf-8").splitlines()
                          if report_roles.NOT_PASSED in ln]
                self.assertIn(want, line)

    def test_given_up_reply_still_reports(self):
        for _ in range(rolekit.GIVE_UP_AFTER):
            runreport.accept("壊れた", AcceptCase.PASS, out_dir=self.out)
        human = runreport.collect("# 報告\n\n起きたこと: 赤\n\n## 1. 人が決めること\n\n事実", out_dir=self.out,
                                  stamp="run x").read_text(encoding="utf-8")
        self.assertTrue(human.startswith("# 報告\n\n起きたこと: 赤\n\n"), human)
        self.assertIn(report_roles.FAILED_TITLE, human)
        self.assertIn(f"report の返答が {rolekit.GIVE_UP_AFTER} 回とも受け付けで拒まれた（最後の拒否: ", human)
        self.assertTrue(self.detail().endswith("事実"))

    def test_decisions_section_is_one_place(self):
        """書き手の頭の「人が決めること」の後ろに機械の事実が付いても、詳細のファイルの見出しの節は 1 つ（機械の数えの見出しを言い換え、
        1 段下げる）。人に向けた報告は機械の事実の節を持たない"""
        runreport.accept(AcceptCase.REPLY, AcceptCase.PASS, out_dir=self.out)
        got, machine, _ = self.build()
        human = runreport.collect(machine, out_dir=self.out, stamp="run x").read_text(encoding="utf-8")
        for text in (human, self.detail()):
            heads = [line for line in text.splitlines() if line.startswith("#") and report_roles.DECISIONS_HEAD in line]
            self.assertEqual(heads, ["## 1. 人が決めること"])
        self.assertIn(f"#{runreport.MACHINE_DECISIONS}", self.detail())
        self.assertIn(f"#{report.STOP_HEADING}", self.detail())
        self.assertNotIn(report.STOP_HEADING, human)


class ColdBodyCase(Base):
    def test_head_and_glossary_only(self):
        """初見の読み手に貼る本文は人に向けた報告の頭と同じ: 機械の冒頭・書き手の頭・語の定義を、語の表で言い換えた物"""
        self.out.mkdir(parents=True)
        (self.out / report.REPORT_FILE).write_text("# 報告\n\n起きたこと: 赤\n\n## 1. 人が決めること\n\n- 機械の行\n", encoding="utf-8")
        reply = json.dumps({"text": "承認ノードで止めた。\n\n## 1. 人が決めること\n\n- A\n\n## 2. 経緯\n\n長い",
                            "terms": [{"term": "A", "definition": "決める物"}]}, ensure_ascii=False)
        body = runreport.cold_body(reply, out_dir=self.out)
        self.assertTrue(body.startswith("# 報告\n\n起きたこと: 赤\n\n先へ進めるかを決める所で止めた。"), body)
        self.assertNotIn("長い", body)
        self.assertNotIn("機械の行", body)
        self.assertIn(report_roles.GLOSSARY_HEADING, body)

    def test_unreadable_reply_says_so(self):
        self.assertIn("書き手の返答を読めない", runreport.cold_body("壊れた", out_dir=self.out))
        reply = json.dumps({"text": "本文"}, ensure_ascii=False)
        self.assertIn("機械の報告の冒頭を読めない", runreport.cold_body(reply, out_dir=self.out))


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
        rejudge = {**judge, "judgment": self.put("rejudge/judgment.json", {"units": after}), "rejudge_verdict": verdicts[-1],
                   "rejudge_exit": str(rdir / judge_accept.PORTS["rejudge_exit"]), "rejudge_diff": str(rdir / judge_accept.REJUDGE_DIFF)}
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

    def test_asked_query_hits_fixed_unit_keeps_its_fix_in_the_next_request(self):
        """query_hits_fixed の単位は直してから申し出たので、次の依頼の行は直しが差分に在ると言い、直さずに残したと言わない（#355）"""
        rows = [{"unit_key": "u1", "between": ["判定:58", "stats.py:14"], "kind": conflict.QUERY_HITS_FIXED, "which_is_right": "query",
                 "ruling": {"decision": "ask_human", "text": "置き換える問いを書けない"}}]
        fix = {**fixed_run()["fix"], "conflicts": self.put("fix/conflicts.json", {"items": rows})}
        got, _, _ = self.build(fixed_run(fix=fix))
        doc = json.loads(pathlib.Path(got["next_request"]).read_text(encoding="utf-8"))
        text = {r["where"]: r["text"] for r in doc["findings"]}["u1"]
        self.assertIn(conflict.FIX_IN_DIFF, text)
        self.assertNotIn(conflict.UNFIXED_LEFT, text)

    def test_mixed_asked_unit_does_not_claim_its_fix_in_the_diff(self):
        """#368: 1 単位に query_hits_fixed と unnamed_test_broke の人に回した行が混ざる時、次の依頼の行は関所の行と同じく
        conflict.fix_place の 1 つの在りか（直さずに残した）を言い、先頭の行の種類で「差分に在る」と言わない"""
        ask = {"decision": "ask_human", "text": "人が決める"}
        rows = [{"unit_key": "u1", "between": ["判定:58", "stats.py:14"], "kind": conflict.QUERY_HITS_FIXED, "which_is_right": "query",
                 "ruling": ask},
                {"unit_key": "u1", "between": ["test_stats.py:3"], "kind": conflict.UNNAMED_TEST_BROKE, "which_is_right": "request",
                 "ruling": ask}]
        fix = {**fixed_run()["fix"], "conflicts": self.put("fix/conflicts.json", {"items": rows})}
        got, _, _ = self.build(fixed_run(fix=fix))
        doc = json.loads(pathlib.Path(got["next_request"]).read_text(encoding="utf-8"))
        text = {r["where"]: r["text"] for r in doc["findings"]}["u1"]
        self.assertIn(conflict.UNFIXED_LEFT, text)
        self.assertNotIn(conflict.FIX_IN_DIFF, text)

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
        self.assertNotIn("人に回した食い違いの申し出", self.section(text, report.DECISIONS_HEADING))
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

    def test_plan_last_reject_is_the_returned_rejects(self):
        """計画と案の直しの受け付けの最後の拒否は、返りの欄 rejects の最後の行（周のフォルダの拒否の控えを探さない）"""
        rows = [{"at": "t1", "reason": "1 回目"}, {"at": "t2", "reason": "網羅が\n足りない"}]
        self.assertEqual(runreport._last_reject(fixed_run(replan={"ready": False, "rejects": rows}), "replan"),
                         "受け付けの最後の拒否: 網羅が 足りない")
        self.assertEqual(runreport._last_reject(fixed_run(plan={"ready": False, "rejects": []}), "plan"), runreport.NO_REJECT)

    def test_replan_gave_up_reads_the_returned_rows(self):
        """案の直しを終えられなかった項目の行は、案の直しと、その事前審査の返りの欄 gave_up から読む（置き場の控えを開かない）"""
        rows = [{"item": 2, "why": "修正案の役の直しが 3 回とも拒まれた: 網羅", "ruling": "案を直す"}]
        review = [{"item": 3, "why": "事前審査の役の返答が 3 回とも拒まれた: 形", "ruling": "裁定なし"}]
        returns = fixed_run(replan={"ready": False, "gave_up": rows}, **{"replan-review-result": {"gave_up": review}})
        self.assertEqual(runreport.replan_gave_up(returns), [
            {"where": runreport.REPLAN_GAVE_UP_WHERE.format(item=2), "text": "修正案の役の直しが 3 回とも拒まれた: 網羅。裁定の文: 案を直す"},
            {"where": runreport.REPLAN_GAVE_UP_WHERE.format(item=3), "text": "事前審査の役の返答が 3 回とも拒まれた: 形。裁定の文: 裁定なし"}])
        self.assertEqual(runreport.replan_gave_up(fixed_run(replan={"ready": False, "gave_up": None})), [])


class LedgerCase(Base):
    """問いの台帳の保留の行と答えた行（元 gatemarks.held_lines・answered_lines）"""

    def returns(self, *questions, units=None, materials=None, review=(), judged=None):
        """判定の返りの units は開いた単位だけ。judgment.json の units（judged。無ければ返りの単位を block で）は全部の単位"""
        units = units if units is not None else [{"id": FORK_UNIT}]
        judged = judged if judged is not None else [{"key": u["id"], "label": u.get("label", "block")} for u in units]
        judgment = self.put("judge/judgment.json", {"questions": list(questions), "units": judged})
        mats = self.put("judge/materials.json", materials) if materials is not None else None
        judge = {**fixed_run()["judge"], "judgment": judgment, "units": units, "materials": mats,
                 "answer_ties": str(self.dir / "judge" / "answer-ties.json")}
        return fixed_run(judge=judge, **{"plan-review": {**fixed_run()["plan-review"],
                                                        "questions": [gatemarks.question_row("fork", q) for q in review]}})

    def test_held_line_names_units_left_and_answer_key(self):
        state = runreport.ledger_state(self.returns(FORK), {}, {"run_id": RUN})
        self.assertEqual([line for _, line in state["held"]],
                         [gatemarks._ledger_line(FORK, skip=[FORK_UNIT]) + f'／{gatemarks.ANSWER_KEY_HEAD}: "{FORK["key"]}"'])
        self.assertIn(f"／答えが無いと直さない単位: {FORK_UNIT}", state["held"][0][1])

    def test_answer_key_with_inner_words_survives_the_human_report(self):
        """#660: 問いの key に語の表の語が混じっても、人に向けた報告の 1 件 1 行の問いの key と答えの鍵は字のまま（人が次の run の
        answers に写す字が問いに当たる）。key の外の語は言い換える"""
        q = {**FORK, "key": "柵の住処"}
        _, machine, _ = self.build(self.returns(q))
        runreport.accept(AcceptCase.REPLY, AcceptCase.PASS, out_dir=self.out)
        human = runreport.collect(machine, out_dir=self.out, stamp="run x").read_text(encoding="utf-8")
        [held] = [x for x in human.splitlines() if x.startswith("- 保留にしたままの問い: ")]
        self.assertIn(f"／{gatemarks.ANSWER_KEY_HEAD}: {json.dumps(q['key'], ensure_ascii=False)}", held)
        self.assertIn(" 柵の住処（", held)
        self.assertNotIn("問いの台帳", held)

    def test_answer_key_with_a_space_and_inner_words_survives_the_human_report(self):
        """#660: 空白を含む問いの key（素材の名と問いの文）も、行の頭で語の表の語を言い換えない"""
        q = {**FORK, "key": "parallel_pr: 単位の柵"}
        _, machine, _ = self.build(self.returns(q))
        runreport.accept(AcceptCase.REPLY, AcceptCase.PASS, out_dir=self.out)
        human = runreport.collect(machine, out_dir=self.out, stamp="run x").read_text(encoding="utf-8")
        [held] = [x for x in human.splitlines() if x.startswith("- 保留にしたままの問い: ")]
        self.assertIn(" parallel_pr: 単位の柵（", held)
        self.assertNotIn("問いの台帳", held)

    def test_held_lines_warn_to_read_the_measuring_command_first(self):
        """#505: 保留の行の下の答え方は、測り方の命令が対象を読んだ役の書いた物なので、打つ前に読み読み取りだけの時だけ打てと言う
        （元 works の skills/works/SKILL.md 117 行）"""
        _, text, _ = self.build(self.returns(FORK))
        self.assertIn(gatemarks.ANSWER_HOW, text)
        self.assertIn("打つ前に読み、読み取りだけの時だけ打つ", gatemarks.ANSWER_HOW)

    def test_answer_key_is_the_material_name_when_it_binds_only_this(self):
        q = {**FORK, "origin": "", "key": "parallel_pr: 重なりを確かめる"}
        state = runreport.ledger_state(self.returns(q, materials={"parallel_pr": {"status": "not_run"}}), {}, {"run_id": RUN})
        self.assertTrue(state["held"][0][1].endswith(f'{gatemarks.ANSWER_KEY_HEAD}: "parallel_pr"'), state["held"][0][1])

    def test_answered_lines_name_where_the_answer_came_from(self):
        other = {**FORK, "key": "q-other", "origin": "x"}
        returns = self.returns(FORK, other, units=[{"id": FORK_UNIT}, {"id": "x"}], review=[gatemarks.ask_text(other)])
        answers = [{"question": FORK["key"], "text": "例外", "command": "pytest -k mean", "output": "1 passed"}]
        gate = {"decision": "continue", "text": "", "asked": [gatemarks.ask_text(other)]}
        state = runreport.ledger_state(returns, {"before-fix-answer": gate}, {"answers": answers})
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

    def test_question_held_at_the_gate_stays_a_decision(self):
        """通す語の答えでも一言が「保留: <key>」と名指した事前審査の問いは答えていないので、修正前の問いに数え、答えた問いの行に出さない"""
        returns = self.returns(FORK, review=[gatemarks.ask_text(FORK)])
        for decision in ("continue", "approve"):
            with self.subTest(decision=decision):
                gate = {"decision": decision, "text": f"保留: {FORK['key']}", "asked": [gatemarks.ask_text(FORK)]}
                _, text, _ = self.build(returns, gates={"before-fix-answer": gate})
                self.assertIn("修正前の問い 1 件", text.splitlines()[4])
                body = self.section(text, report.DECISIONS_HEADING)
                self.assertIn("- 修正前の問い: 1 件\n", body)
                self.assertNotIn(gatemarks.ANSWERED_HEAD, body)

    def test_ledger_question_answered_at_the_gate_is_listed_once(self):
        """通す語の答えが asked に載せた台帳の問いは、答えた問いの行に台帳の 1 行だけで出し、事前審査の行として重ねない"""
        returns = self.returns(FORK, review=[gatemarks.ask_text(FORK)])
        gate = {"decision": "approve", "text": "", "asked": [gatemarks.ask_text(FORK)]}
        _, text, _ = self.build(returns, gates={"before-fix-answer": gate})
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertNotIn("- 修正前の問い:", body)   # 0 件の種は出さない（#383 の項目 9）。答えた問いは数えない
        self.assertEqual(body.count(gatemarks.ANSWERED_HEAD), 1, body)
        self.assertEqual(body.count(f"{gatemarks._prefix(FORK)}"), 1, body)
        self.assertIn(f"- {gatemarks.ANSWERED_HEAD}（1 件。", body)

    def test_unread_hold_is_named_in_the_head(self):
        """P238・L-G31: 修正前の関所の答えの文が「保留: q-typo」（台帳の key を拾えない）の時、報告の冒頭に「読めなかった保留」の行が
        在り、問いは答えたものとして扱う（直す義務は変えない）"""
        gate = {"decision": "continue", "text": "保留: q-typo", "asked": [gatemarks.ask_text(FORK)]}
        returns = self.returns(FORK)
        state = runreport.ledger_state(returns, {"before-fix-answer": gate}, {"run_id": RUN})
        self.assertEqual(state["held"], [])
        lines, _ = runreport._decisions(returns, {"before-fix-answer": gate}, {"run_id": RUN}, "fixed", [], closed=True,
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
        state = runreport.ledger_state(returns, {"before-fix-answer": gate}, {"run_id": RUN})
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
        """判定の返り（judgment と、置いた隣のファイルを指す出力の欄。欄の名は judge_accept の表から引く）"""
        import judge_accept
        field = {name: key for key, name in {**judge_accept.PORTS, **judge_accept.FIRST_PORTS}.items()}
        judgment = self.put("judge/judgment.json", {})
        return {**fixed_run()["judge"], "judgment": judgment,
                **{field[name]: self.put(f"judge/{name}", doc) for name, doc in beside.items()}}

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
        _, text, decided = self.build(fixed_run(eyes=eyes, **{"sealed-diff": seal, "applied-diff": apply_}))
        self.assertEqual(decided, ("stopped_by_line", "merge-apply:not-ok"))
        self.assertIn("守りのパスに当たった差分 1 件", text.splitlines()[4])
        self.assertIn("merge-apply が ok でない: hash が封じた物と違う", self.section(text, report.STOP_HEADING))

    def test_protected_hits_from_eyes_only(self):
        """封じの返りが当たりを持たない（封じが走らない・欄が無い）run も、独立の目の当たりだけで人が決めることに数える"""
        eyes = {**fixed_run()["eyes"], "protected_hits": ["ci/deploy.yml", "ci/deploy.yml"]}
        _, text, _ = self.build(fixed_run(eyes=eyes))
        self.assertIn("守りのパスに当たった差分 1 件", text.splitlines()[4])
        self.assertIn("ci/deploy.yml", self.section(text, report.DECISIONS_HEADING))

    def test_seal_not_ok_says_why(self):
        seal = {"mode": "seal", "ok": False, "reason": "指紋が今の作業ツリーと違う"}
        _, text, decided = self.build(fixed_run(**{"sealed-diff": seal, "applied-diff": None}))
        self.assertEqual(decided, ("stopped_by_line", "merge-seal:not-ok"))
        self.assertIn("merge-seal が ok でない: 指紋が今の作業ツリーと違う", self.section(text, report.STOP_HEADING))
        _, text, _ = self.build(fixed_run(**{"sealed-diff": {"mode": "seal", "ok": False}, "applied-diff": None}))
        self.assertIn("merge-seal が ok でない: 訳の記録が無い", self.section(text, report.STOP_HEADING))

    def test_where_lists_sealed_and_applied_diff(self):
        merge = {"sealed-diff": {"mode": "seal", "ok": True, "diff": "merge/sealed.diff"},
                 "applied-diff": {"mode": "apply", "ok": True, "diff": "merge/apply.diff"}}
        _, text, _ = self.build(fixed_run(**merge))
        body = self.section(text, report.WHERE_HEADING)
        self.assertIn("- 封じた差分（merge-seal.diff）: merge/sealed.diff", body)
        self.assertIn("- 置いた差分（merge-apply.diff）: merge/apply.diff", body)

    def test_world_rows_keep_mark_and_versus(self):
        row = {**WORLD_ROW, "basis": "knowledge"}
        world = self.put("judge/world.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in (
            row, {**row, "finding": 2, "class_id": "w-empty"})))
        _, text, _ = self.build(fixed_run(judge={**fixed_run()["judge"], "world": world}))
        body = self.section(text, report.WORLD_HEADING)
        self.assertIn(f"（{worldmark.NOT_WEB}）", body)
        self.assertIn("依頼の解き方「空の並びは 0 を返す」は定石と違う", body)
        self.assertIn("類 w-empty（依頼の行 2）", body)
        self.assertIn("- 類 2", body)

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
        state = self.put("judge/world-state.json", {"status": "failed", "reason": "網が無い（web を引けない）", "world_file": "",
                                                    "classes": 0, "dropped": 0})
        _, text, _ = self.build(fixed_run(judge={**fixed_run()["judge"], "judgment": judgment, "world": None, "world_state": state}))
        self.assertIn("- 世界の解の段が落ちた（行なしで進んだ）: 網が無い（web を引けない）", self.section(text, report.WORLD_HEADING))
        world = self.put("judge/world.jsonl", json.dumps({**WORLD_ROW, "basis": "knowledge"}, ensure_ascii=False))
        self.put("judge/world-state.json", {"status": "ok", "reason": "", "world_file": world, "classes": 1, "dropped": 3})
        _, text, _ = self.build(fixed_run(judge={**fixed_run()["judge"], "judgment": judgment, "world": world, "world_state": state}))
        self.assertIn("- 類 1・落とした抜き書き 3", self.section(text, report.WORLD_HEADING))

    def test_unseen_local_review_lens_is_reported(self):
        """J110（元 diverted.report_lines・report.py:2069）: 判定の隣の local-review-lenses.json の見ていないレンズを、報告の
        「未確認のレンズ」の節に出す。控えが無ければ節に「無い」"""
        judge = self.judge_with(**{"local-review-lenses.json": {"unseen": ["/code-review"]}})
        _, text, _ = self.build(fixed_run(judge=judge))
        self.assertIn("- 局所レビューの /code-review: 所見を受け取れていない（fork の返答が届かなかった）——見ていないのと同じ",
                      self.section(text, report.UNSEEN_LENS_HEADING))
        _, text, _ = self.build()
        self.assertIn("- 無い", self.section(text, report.UNSEEN_LENS_HEADING))

    def test_parallel_pr_drafts_reach_the_head(self):
        """J111・R80（元 report._pr_lines の前半 :1274-1281）: 判定の隣の pr-downgrades.json の並行 PR の担当への申し送りの下書きを、
        人が決めることの節に「投稿していない」と出す（人が担当の PR に渡す）"""
        judge = self.judge_with(**{"pr-downgrades.json": [{"pr": 12, "files": ["a.py", "b.py"], "note": "a.py の 3 行目を同時に直しています"}]})
        _, text, _ = self.build(fixed_run(judge=judge))
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

    def test_structure_time_adds_the_stage_b_seconds(self):
        """#227: 構造の実測と目で増えた時間は、段 A と目の秒（計画の structure-state.json）に直しの後の実測（段 B）の秒
        （structure-after.json の after.timing）を足す（元 works/blk-structure/scripts/collect.py:83）"""
        design = self.put("plan/design.jsonl", "")
        state = self.put("plan/structure-state.json", {"status": "ok", "reason": "", "design_file": design, "wall_s": 3})
        after = self.put("eyes/structure-after.json", {"status": "ok", "reason": "", "deviations": [],
                                                       "after": {"changed": [], "tables": [], "new_names": [],
                                                                 "timing": {"wall_s": 1.5}}})
        _, text, _ = self.build(fixed_run(plan={**fixed_run()["plan"], "structure": state},
                                          eyes={**fixed_run()["eyes"], "structure_after": after}))
        self.assertIn("- 構造の実測と目で増えた時間: 4.5 秒\n", self.section(text, report.STRUCTURE_HEADING))

    def test_entry_gate_words(self):
        _, text, _ = self.build(start={"run_id": RUN, "final_gate": "when_needed"})
        self.assertIn("- 最後の承認ノード: when_needed", self.section(text, report.ENTRY_HEADING))

    def test_entry_fixture_lines(self):
        """#509: 固定材料から始めた run は写しの元の run を、写した run は次の run に渡すフォルダか写せなかった訳を入口の節に並べる"""
        _, text, _ = self.build(start={"run_id": RUN, "fixture": {"source_run": "run-0"},
                                       "fixture_captured": {"dir": "/x/fix-fixture", "error": ""}})
        body = self.section(text, report.ENTRY_HEADING)
        self.assertIn("- 固定材料から: run run-0 の修正の前の写し（", body)
        self.assertIn("- 固定材料: /x/fix-fixture（次の run の入力 fix_fixture に渡すと、", body)
        _, text, _ = self.build(start={"run_id": RUN, "fixture_captured": {"dir": "", "error": "OSError: 書けない"}})
        self.assertIn("- 固定材料を写せなかった: OSError: 書けない", self.section(text, report.ENTRY_HEADING))

    def test_entry_lists_ran_and_skipped_stages_and_baseline(self):
        """入口の節に走った段・飛ばされた段・直す前のテストの色と赤の原因（元 report.py の入口の行）"""
        base = {"mode": "base", "ok": True, "green": False, "red_cause": "inherited"}
        _, text, _ = self.build(fixed_run(**{"before-tests": base}))
        body = self.section(text, report.ENTRY_HEADING)
        self.assertIn("- 走った段: test-gate-base・judge・plan・", body)
        self.assertIn("- 飛ばされた・出力の無い段: rejudge・replan・replan-review\n", body)
        self.assertIn("直す前のテスト: 赤", body)
        self.assertIn("赤の原因 inherited", body)

        _, text, _ = self.build(fixed_run(**{"before-tests": None}))
        body = self.section(text, report.ENTRY_HEADING)
        self.assertNotIn("直す前のテスト", body)
        self.assertIn("- 飛ばされた・出力の無い段: test-gate-base・rejudge・replan・replan-review", body)

    def test_outside_purpose_rows_and_wrong_name(self):
        """目的の外の所見は節に 1 件ずつ、人が決めることの節に件数と置き場の 1 行（次の run に渡す物の行のすぐ後ろ。元 works/.shared/core/
        report.py:1019-1022 の順）。名の違う控えは読まない"""
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
        self.assertEqual(count[0], carried[0] + 1)
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
        _, text, decided = self.build(fixed_run(fix=fix, **{"applied-diff": None}), line=line)
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
        light_head = fixed_run(judge={**fixed_run()["judge"], "depth": "軽量", "depth_why": "入力 thickness の名指し（軽量）"})
        _, text, _ = self.build(light_head, line={"redepth": light}, start={"run_id": RUN, "thickness": "軽量"})
        entry = self.section(text, report.ENTRY_HEADING)
        self.assertIn("- 深さ: 軽量（単位ごと: 軽量 1 個・標準 0 個。入力 thickness の名指し 軽量）", entry)
        self.assertIn("- 軽量で省いた: 差分の審査", entry)
        _, text, _ = self.build(line={"redepth": {**light, "skip_optional": ""}})
        entry = self.section(text, report.ENTRY_HEADING)
        self.assertNotIn("軽量で省いた", entry)
        self.assertIn("- 単位はどれも軽量だが、run の頭の深さが 標準 なので省かない", entry)
        plan = {**fixed_run()["plan"], "depth": [{"unit_id": "u1", "depth": "軽量", "why": "w"}]}
        _, text, _ = self.build(fixed_run(plan=plan))
        entry = self.section(text, report.ENTRY_HEADING)
        self.assertIn("- 深さ: 軽量（単位ごと: 軽量 1 個・標準 0 個。機械が決めた）", entry)
        self.assertIn(runreport.NO_REDEPTH, entry)

    def test_test_cmd_skip_counts_from_the_loop_record(self):
        """PR #597: test_cmd の省きは TDD の輪の記録（tdd-unit の単位の test_cmd が light）から数える。記録が無い run は頭と単位が
        軽量でも省いたと言わず、輪の後に標準へ上げた単位も、輪が省いた事実を報告に残す"""
        light_head = fixed_run(judge={**fixed_run()["judge"], "depth": "軽量", "depth_why": "入力 thickness の名指し（軽量）"})
        light = {"depth": [{"unit_id": "u1", "depth": "軽量", "why": "触るファイル 1 個"}], "skip_optional": "軽量で省いた",
                 "raised": [], "counted": "", "stop_reason": ""}
        _, text, _ = self.build(light_head, line={"redepth": light})
        entry = self.section(text, report.ENTRY_HEADING)
        self.assertIn("- 軽量で省いた: 差分の審査", entry)
        self.assertNotIn("test_cmd の走らせ直し", entry)
        unit = {"unit_key": "u1", "route": "tdd", "why": "", "tests": ["t::a"], "red": "ok", "green": "ok", "refactor": "none",
                "gave_up": "", "test_cmd": tddloop.CMD_LIGHT}
        typed = {"by_type": {"tdd-unit": [{"include": "fix", "loop": [], "node": "fix__tdd", "path": "nodes/fix.md", "produced_at": "",
                                           "body": [{"group_id": "g1", "ran": True, "reason": "", "suite": "run-tests",
                                                     "reused": None, "units": [unit]}]}]}, "warnings": []}
        raised = {**light, "depth": [{"unit_id": "u1", "depth": "標準", "why": "触るファイル 1 個 / 標準へ上げた: 再審が走った"}],
                  "skip_optional": "", "raised": ["再審が走った"]}
        _, text, _ = self.build(light_head, typed=typed, line={"redepth": raised})
        self.assertIn(f"- 軽量の単位 1 個で省いた: {depth.UNIT_OMIT}", self.section(text, report.ENTRY_HEADING))

    def test_head_depth_line_names_the_depth_and_the_skipped_nodes(self):
        """issue #441: 入口の節に run の頭の深さと根拠・段の省く物・足す物を 1 行で出す。判定の返りが無い run は出さない"""
        judge = {**fixed_run()["judge"], "depth": "軽量", "depth_why": "原因と直す行が名指されている"}
        plan = {**fixed_run()["plan"], "depth_why": "計画の単位 1 個がすべて軽量"}   # 計画の往復の欄は読まない
        _, text, _ = self.build(fixed_run(judge=judge, plan=plan))
        self.assertIn("- run の頭の深さ: 軽量（根拠: 原因と直す行が名指されている）／省く物（単位がどれも軽量の時）: "
                      f"{'・'.join(depth.OMITS)}／足した物: 無い\n",
                      self.section(text, report.ENTRY_HEADING))
        _, text, _ = self.build(fixed_run(judge={**judge, "depth": "標準", "depth_why": "試験のコマンドが無い"}))
        self.assertIn("- run の頭の深さ: 標準（根拠: 試験のコマンドが無い）／省く物: 無い／足した物: 無い\n", self.section(text, report.ENTRY_HEADING))
        _, text, _ = self.build(fixed_run(judge=None))
        self.assertNotIn("run の頭の深さ", text)

    def test_head_depth_line_names_what_the_tier_added(self):
        """判定の depth が重厚の run の入口の節に、段の名・根拠と「足した物: judge_verify・review_tree」が出る。features_off で切った
        機能には名指しで切ったと添える"""
        judge = {**fixed_run()["judge"], "depth": "重厚", "depth_why": "公開の約束を変える"}
        _, text, _ = self.build(fixed_run(judge=judge))
        self.assertIn("- run の頭の深さ: 重厚（根拠: 公開の約束を変える）／省く物: 無い／足した物: judge_verify・review_tree\n",
                      self.section(text, report.ENTRY_HEADING))
        start = {"run_id": RUN, "features_off": ["judge_verify"], "features_on": []}
        _, text, _ = self.build(fixed_run(judge=judge), start=start)
        self.assertIn("／足した物: judge_verify（名指しで切った）・review_tree\n", self.section(text, report.ENTRY_HEADING))

    def test_heavy_entry_line_says_the_added_features_on(self):
        """判定の depth が重厚で features を名指していない run の入口の「段: …・機能: …」の行に、judge_verify off と review_tree auto が
        出ない。標準の run は今の既定のまま。名指しで切った機能は off のまま"""
        heavy = {**fixed_run()["judge"], "depth": "重厚", "depth_why": "公開の約束を変える"}
        start = {"run_id": RUN, "features_off": [], "features_on": []}
        _, text, _ = self.build(fixed_run(judge=heavy), start=start)
        entry = self.section(text, report.ENTRY_HEADING)
        self.assertIn("- 段: 自動（機械が単位ごとに決めた）・機能: 全部 on\n", entry)
        self.assertNotIn("judge_verify off", entry)
        self.assertNotIn("review_tree auto", entry)
        _, text, _ = self.build(fixed_run(judge={**heavy, "depth": "標準"}), start=start)
        self.assertIn("- 段: 自動（機械が単位ごとに決めた）・機能: judge_verify off・review_tree auto\n", self.section(text, report.ENTRY_HEADING))
        _, text, _ = self.build(fixed_run(judge=heavy), start={**start, "features_off": ["judge_verify"]})
        self.assertIn("・機能: judge_verify off\n", self.section(text, report.ENTRY_HEADING))

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
                               "replan-review-result": {**fixed_run()["plan-review"], "review": again}})
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
        _, text, _ = self.build(fixed_run(fix=fix), gates={"replan-answer": gate}, line={"widened": widened})
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
                      self.section(self.build(fixed_run(fix=fix), gates={"replan-answer": stop})[1], report.DECISIONS_HEADING))
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
        gates = {"start-answer": {"decision": "approve", "text": "", "asked": []}}
        _, text, _ = self.build(start=start, gates=gates)
        body = self.section(text, report.ENTRY_HEADING)
        self.assertIn(f"- 段: 軽量・{entry.features_part(['world'], [])}\n", body)
        self.assertIn("- 決めた人: 承認ノードの答え 1 件\n", body)
        import subprocess
        target = self.dir / "target"
        target.mkdir()
        subprocess.run(["git", "init", "-q", str(target)], check=True, env=hermetic.child_env())
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
        _, text, _ = self.build(fixed_run(**{"sealed-diff": seal_ok}))
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn(f"- {runreport.APPLY_HEAD}: bin/apply {RUN}（", body)
        self.assertNotIn("git apply", text)
        stop = {"decision": "stop", "text": "範囲が広すぎる", "asked": []}
        _, text, _ = self.build(fixed_run(**{"sealed-diff": seal_ok, "applied-diff": None}), gates={"final-answer": stop})
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn("- 止まった run: 人が承認ノードで止めた（gate-final:stop）で止まった: 「範囲が広すぎる」", body)
        self.assertIn(f"- {runreport.APPLY_HEAD}: bin/apply {RUN} --allow-stopped（", body)
        self.assertNotIn("git apply", text)
        _, text, _ = self.build(fixed_run(**{"sealed-diff": None, "applied-diff": None, "eyes": None}))
        self.assertIn(f"- {runreport.APPLY_HEAD}: 無い（差分を封じていない）", self.section(text, report.DECISIONS_HEADING))

    def test_head_says_whether_to_apply(self):
        """#660: 冒頭の 2 行目は差分を当ててよいかを、bin/apply の打ち方（apply_said が _apply_lines と同じ道で決める）と結末・人が決める
        物の件数で言う"""
        seal_ok = {"mode": "seal", "ok": True, "diff": self.put("merge/sealed.diff", "")}
        cases = ((fixed_run(**{"sealed-diff": seal_ok}), {}, f"当ててよい（bin/apply {RUN}）"),
                 (fixed_run(**{"sealed-diff": seal_ok, "applied-diff": None}), {"final-answer": {"decision": "stop", "text": "x"}},
                  f"差分を置かずに止まった run。止めた訳を確かめてから当てる（bin/apply {RUN} --allow-stopped）"),
                 (fixed_run(**{"sealed-diff": None, "applied-diff": None}), {}, "当てる差分が無い（差分を封じていない）"))
        for returns, gates, said in cases:
            with self.subTest(said=said):
                _, text, _ = self.build(returns, gates=gates)
                self.assertEqual(text.splitlines()[3], runreport.APPLY_ASK + said)
        self.assertEqual(runreport.apply_said(fixed_run(**{"sealed-diff": seal_ok}), "round_limit", RUN, 0),
                         f"確かめてから当てる（結末が「{report.OUTCOME_WORDS['round_limit']}」。bin/apply {RUN}）")

    def test_tests_head_lines_and_deleted_files(self):
        """T35・T41・M38（部分 B2 の申し送り。最後の関所と同じ行を報告の冒頭に）: 人が決めることの節に最後のテストの一式の行と修正前のテストの
        行（test-gate の返りの欄のまま）、任せ先の申告の緑なら走らせる語の宣言の仕方、封じた差分が消すファイルを SHOWN 件までは 1 本ずつ、
        超える分は件数と封じた差分のパスで出す"""
        import declared_checks
        import seal
        final = {**fixed_run()["final-tests"], "by": "role_needed", "suites_line": "一式: 任せ先の申告", "log": "/tmp/ci.log",
                 "baseline_line": "修正前のテスト: 赤（段ごとの終了コード {\"suite\": 1}）——最後のテストの赤は修正前から在りうる", "reason": ""}
        diff = self.put("merge/sealed.diff", "diff --git a/old.py b/old.py\ndeleted file mode 100644\n--- a/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n")
        returns = fixed_run(**{"final-tests": final,
                               "sealed-diff": {"mode": "seal", "ok": True, "diff": diff}})
        _, text, _ = self.build(returns)
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertIn("- 最後のテストの一式: role_needed・一式: 任せ先の申告・ログ /tmp/ci.log\n", body)
        self.assertIn("- 修正前のテスト: 赤（段ごとの終了コード {\"suite\": 1}）——最後のテストの赤は修正前から在りうる\n", body)
        self.assertIn(f"- {declared_checks.SELF_REPORTED_NOTE}", body)
        self.assertIn(f"- {seal.DELETED_HEAD}: old.py\n", body)

    def test_many_deleted_files_stay_short(self):
        """封じた差分が 20,000 本を消しても、人が決めることの節は本数に依らず短い。先頭の数本と、残りの件数と封じた差分の実のパス
        （merge-seal の diff）の 1 行を出し、全部のパスは並べない"""
        import seal
        names = [f"gen/{i}.o" for i in range(20000)]
        diff = self.put("merge/sealed.diff", "".join(f"diff --git a/{n} b/{n}\ndeleted file mode 100644\n--- a/{n}\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n"
                                                      for n in names))
        _, text, _ = self.build(fixed_run(**{"sealed-diff": {"mode": "seal", "ok": True, "diff": diff}}))
        body = self.section(text, report.DECISIONS_HEADING)
        self.assertLessEqual(len(body.splitlines()), 40, body[:2000])
        self.assertLess(len(body), 6000)
        self.assertIn(f"- {seal.DELETED_HEAD}: {names[0]}\n", body)
        self.assertNotIn(names[100], body)
        self.assertIn(f"- {seal.DELETED_HEAD}: ほか 19995 件（全件: {diff}）\n", body)

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

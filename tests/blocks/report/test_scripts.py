"""報告の block を、script を子のプロセスで回して確かめる（docs/design/report.md の 2.9 と 8 節）。

始めの記録の無い使い捨ての run directory で、port の値だけを渡し、facts → write_prep → 台本の返答 → cold_prep → 台本の判定 → write_accept →
finish と回す。写す元は tests/workflows/test_report.py の FactsCase・AcceptScriptCase・RejectScriptCase・ColdPrepScriptCase・CollectScriptCase・
WriterRunCase（#702 の筋書き。書き手が使用枠の切れで落ち、別のトークンの resume で書き直す。block を include する小さな graph の形のまま）。
"""
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

from tests import archon
from tests.blocks import kit
from tests.blocks.report import base
from tests.blocks.report.base import INCLUDE, LOOP, SECTIONS, Flow

M = base.src()
import handoff  # noqa: E402  lib/

REQUEST_STOP = json.dumps({**base.READY, "gates": [{"at": "final-answer", "decision": "stop", "text": "request: 止め札"}]})


class FactsCase(Flow):
    def test_empty_inputs_are_record_invalid_and_exit_zero(self):
        got = self.run.script("facts", f"{INCLUDE}facts", sections="", facts="", lang="")
        self.assertEqual((got["outcome"], got["ok"], got["ai_go"]), ("record_invalid", False, False))
        self.assertEqual(got["stop_reason"], "start:record-invalid")
        text = self.machine()
        self.assertIn("結果を名乗れない訳: 入力 sections: json の入力が空", text)
        self.assertIn("起きたこと: 記録が検証器を通らない（結果を名乗れない）（record_invalid）", text)
        self.assertEqual(base.read(self.place / "facts.json")["ai_go"], False)

    def test_no_facts_is_record_invalid_from_the_start(self):
        got = self.facts(facts="{}")
        self.assertEqual((got["outcome"], got["stop_reason"], got["ai_go"]), ("record_invalid", "start:record-invalid", False))
        self.assertIn("人が決めること: 1 件——記録が通らないこと 1 件", self.machine())

    def test_broken_inputs_are_named_and_do_not_fall(self):
        got = self.facts(sections="[壊れた", facts='{"nope": 1}')
        self.assertEqual(got["outcome"], "record_invalid")
        text = self.machine()
        self.assertIn("結果を名乗れない訳: 入力 sections:", text)
        self.assertIn("結果を名乗れない訳: 入力 facts: 入力が facts.schema.json の形に合わない", text)
        got = self.facts(sections="[壊れた")
        self.assertEqual((got["outcome"], got["stop_reason"]), ("record_invalid", "report:record-invalid"), "始めの記録が読めて入力だけ壊れた時")

    def test_facts_json_and_return(self):
        got = self.facts(lang=" 日本語 ")
        self.assertEqual((got["outcome"], got["ok"], got["stop_reason"], got["ai_go"]), ("fixed", True, "", True))
        self.assertEqual(got["machine"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "report/report.md"})
        self.assertEqual((got["next_request"], got["prior_failures"]), (None, None))
        doc = base.read(self.place / "facts.json")
        self.assertEqual(doc, {"outcome": "fixed", "stop_reason": "", "ok": True, "ai_go": True, "stamp": got["stamp"], "lang": "日本語",
                               "run_id": kit.RUN_ID, "decisions": 0})
        self.assertIn("works-factory-report / run run-test / 周 — / グラフの版 ", got["stamp"])

    def test_request_stop_with_a_dry_run_environment(self):
        got = self.facts(facts=REQUEST_STOP)
        self.assertEqual((got["outcome"], got["stop_reason"], got["ai_go"]), ("stopped_by_request", "final-answer:stop", True))
        self.assertIn("run の記録の置き場（LOG_DIR）か run の id（WORKFLOW_ID）が届いていない", self.machine())

    def test_carried_rows_reach_their_files_and_pointers(self):
        carry = {"findings": [{"where": "stats.py:4", "text": "mean が違う"}], "prior": [{"where": "受け付け 計画", "text": "拒まれた"}],
                 "drafts": [], "constraints": []}
        got = self.facts(facts=json.dumps({**base.READY, "carry": carry}))
        self.assertEqual(got["next_request"]["path"], "report/next-request.json")
        self.assertEqual(got["prior_failures"]["path"], "report/prior-failures.json")
        self.assertEqual(base.read(self.place / "prior-failures.json"), carry["prior"])

    def test_run_record_failure_is_read_from_the_log(self):
        self.log({"type": "node_start", "step": "fix__tdd", "ts": "2026-10-12T00:00:00Z"},
                 {"type": "node_error", "step": "fix__tdd", "ts": "2026-10-12T00:01:00Z", "error": "boom", "execution": {}},
                 {"type": "node_error", "step": "report__facts", "ts": "2026-10-12T00:01:00Z", "error": "自分", "execution": {}})
        got = self.facts()
        self.assertEqual((got["outcome"], got["stop_reason"]), ("interrupted", "fix__tdd:node-error"))
        self.assertIn("run が途中で終わった: ノード fix__tdd が落ちた（誤り: boom）", self.machine())
        self.assertNotIn("report__facts", self.machine().split("## 2. 止めたか")[1].split("## 3.")[0])

    def test_fallen_child_run_names_its_own_cause(self):
        """fan_out の子の run が落ちると、親の記録の誤りは「子 N (run 先頭 8 字) が落ちた」と子の失敗の総括だけを言い、AI の provider の
        429 のような落ちた訳は子の run の記録（同じ置き場の <子の run の id>.jsonl）にだけ在る。報告は子の記録を読んで訳を載せる"""
        child = "abcd1234-0000-4000-8000-000000000000"
        self.log({"type": "node_error", "step": "fix__groups-par", "ts": "2026-10-12T00:01:00Z", "execution": {},
                  "error": "fan_out node 'groups-par' (join: all_success): child 1 (run abcd1234) failed: DAG workflow 'works-factory-fix' "
                           "failed: node tdd failed. 3 downstream nodes were skipped."})
        log_dir = pathlib.Path(self.run.extra["LOG_DIR"])
        rows = [{"type": "node_start", "step": "tdd", "ts": "2026-10-12T00:00:00Z"},
                {"type": "node_error", "step": "tdd", "ts": "2026-10-12T00:00:30Z",
                 "error": "429 rate_limit_error: concurrent request limit reached\nraw detail", "execution": {}}]
        (log_dir / f"{child}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        self.facts()
        self.assertIn("子の run abcd1234 のノード tdd が落ちた（誤り: 429 rate_limit_error: concurrent request limit reached）", self.machine())

    def test_child_run_record_without_a_fall_or_with_broken_json_is_said(self):
        """子の記録が読めても落ちた node が無い・記録の JSON が壊れている時も、黙らずに子の run を名指して言う"""
        self.log({"type": "node_error", "step": "fix__groups-par", "ts": "2026-10-12T00:01:00Z", "execution": {},
                  "error": "fan_out node 'groups-par' (join: all_success): child 0 (run aaaa1111) failed: x; child 1 (run bbbb2222) failed: y"})
        log_dir = pathlib.Path(self.run.extra["LOG_DIR"])
        (log_dir / "aaaa1111-0000.jsonl").write_text(json.dumps({"type": "node_start", "step": "tdd", "ts": "t"}) + "\n", encoding="utf-8")
        (log_dir / "bbbb2222-0000.jsonl").write_bytes(b'{"type": "node_error", "step": \xff\xfe broken\n')
        self.facts()
        body = self.machine()
        self.assertIn("子の run aaaa1111 の記録に落ちたノードが無い", body)
        self.assertIn("子の run bbbb2222 の記録 bbbb2222-0000.jsonl が読めない", body)

    def test_child_run_without_a_record_is_said_not_dropped(self):
        self.log({"type": "node_error", "step": "fix__groups-par", "ts": "2026-10-12T00:01:00Z", "execution": {},
                  "error": "fan_out node 'groups-par' (join: all_success): child 0 (run 99999999) failed: x"})
        self.facts()
        self.assertIn("子の run 99999999 の記録が読めない", self.machine())

    def test_optional_stage_fall_is_absorbed(self):
        self.log({"type": "node_error", "step": "eyes__r1", "ts": "2026-10-12T00:01:00Z", "error": "目が落ちた", "execution": {}})
        got = self.facts(facts=json.dumps({**base.READY, "optional": ["eyes__"]}))
        self.assertEqual(got["outcome"], "round_limit")
        self.assertIn("受け止めた落ち eyes__r1: eyes__r1 が落ちた（誤り: 目が落ちた）", self.machine())

    def test_unexpected_error_still_returns(self):
        """約束の Schema に合わない前の失敗の行は ValueError。落ちずに、訳を載せた別の名の機械の報告を指す record_invalid を返す"""
        bad = json.dumps({**base.READY, "carry": {"prior": [{"where": "w"}]}})
        got = self.facts(facts=bad)
        self.assertEqual((got["outcome"], got["ok"], got["ai_go"]), ("record_invalid", False, False))
        self.assertTrue(got["stop_reason"].startswith("report:ValueError: "), got["stop_reason"])
        self.assertEqual(got["machine"]["path"], "report/report-unwritten.md")
        self.assertIn("前の失敗が約束の Schema に合わない", (self.place / "report-unwritten.md").read_text(encoding="utf-8"))
        self.assertFalse((self.place / "report.md").exists())
        self.assertEqual(base.read(self.place / "facts.json")["outcome"], "record_invalid")

    def test_without_the_libraries_still_returns(self):
        """lib/ を読めない時は標準ライブラリだけで訳だけのファイルを書いて指す"""
        with tempfile.TemporaryDirectory() as empty:
            self.run.extra = {"WORKS_FACTORY_ROOT": empty}
            got = self.facts()
        self.assertEqual((got["outcome"], got["ai_go"]), ("record_invalid", False))
        self.assertEqual(got["machine"]["path"], "report/report-facts-unwritten.md")
        self.assertIn("報告を組めなかった:", (self.place / "report-facts-unwritten.md").read_text(encoding="utf-8"))


class AcceptCase(Flow):
    def test_cold_redesign_three_times(self):
        self.facts()
        for n in (1, 2):
            got = self.accept(cold=base.BAD_COLD)
            self.assertEqual((got["done"], got["ok"], got["kind"]), (False, False, "cold"), n)
            self.assertTrue(got["prev_file"].endswith("candidate-report.json"))
        got = self.accept(cold=base.BAD_COLD)
        self.assertEqual((got["done"], got["ok"], got["kind"], got["prev_file"]), (True, True, "", ""))
        ai = base.read(self.place / "ai.json")
        self.assertTrue(ai["accepted"])
        self.assertIn("何の話か分からない", ai["not_passed"])
        self.assertEqual(ai["rejects"]["report"]["cold"], 2)
        fin = self.finish()
        human = (self.place / "report-ai.md").read_text(encoding="utf-8")
        self.assertIn("止まった所: 何の話か分からない", [x for x in human.splitlines() if "上限の 3 回目で受け取った" in x][0])
        self.assertEqual(fin["human"]["path"], "report/report-ai.md")

    def test_cells_and_terms_rejected_first_time(self):
        self.facts()
        got = self.accept(json.dumps({"text": "| 項目 |\n|---|\n| 説明の文である。 |", "handoff": base.NOTE}, ensure_ascii=False))
        self.assertEqual((got["done"], got["kind"]), (False, "format"))
        got = self.accept(json.dumps({"text": "x", "terms": [{"term": ""}], "handoff": base.NOTE}))
        self.assertEqual(got["kind"], "answer")

    def test_acceptance_never_falls(self):
        got = self.run.script("write_accept", LOOP + "write-accept", reply="", cold="")
        self.assertEqual((got["done"], got["ok"], got["kind"]), (False, False, "answer"))

    def test_unexpected_error_in_accept_fails_the_node(self):
        """思わぬ誤り（拒否の読み物に書けない）は捕まえない: node が落ち、ai.json は無く、finish が書き手のノードの落ちを頭に置く"""
        self.facts()
        (self.place / "rejects-report.md").mkdir()
        err = self.run.failing("write_accept", LOOP + "write-accept", reply=base.default_reply(), cold=json.dumps(base.BAD_COLD))
        self.assertIn("rejects-report.md", err)
        self.assertFalse((self.place / "ai.json").exists())


class FinishCase(Flow):
    def test_without_ai_file_returns_machine_report(self):
        self.facts()
        got = self.finish()
        self.assertEqual((got["ok"], got["outcome"], got["stop_reason"]), (True, "fixed", ""))
        self.assertEqual((got["human"], got["detail"]), (None, None))
        self.assertEqual(got["machine"]["path"], "report/report.md")
        self.assertEqual(got["report"], ["結末: 直して、最後のテストまで通った（fixed）", "人に向けた報告: 無い（書き手の返答が無い）",
                                         "機械の報告: report/report.md"])
        self.assertFalse((self.place / "report-detail.md").exists())

    def test_record_invalid_says_the_writer_was_not_started(self):
        self.facts(facts="{}")
        got = self.finish()
        self.assertEqual((got["ok"], got["outcome"], got["human"]), (False, "record_invalid", None))
        self.assertIn("人に向けた報告: 無い（結果を名乗れない（結末 record_invalid）ので書き手を起こしていない）", got["report"])

    def test_with_ai_file_returns_the_human_report_and_detail(self):
        self.facts()
        self.accept()
        got = self.finish()
        self.assertEqual((got["human"]["path"], got["detail"]["path"]), ("report/report-ai.md", "report/report-detail.md"))
        self.assertEqual(got["report"][1:], ["人に向けた報告: report/report-ai.md", "機械の報告: report/report.md"])
        human = (self.place / "report-ai.md").read_text(encoding="utf-8")
        self.assertTrue(human.rstrip().splitlines()[-1].startswith("works-factory-report / run run-test / "))
        self.assertIn("同じフォルダの report-detail.md", human)

    def test_carried_pointers_are_passed_through(self):
        carry = {"findings": [{"where": "w", "text": "t"}], "prior": [{"where": "w", "text": "t"}], "drafts": [], "constraints": []}
        self.facts(facts=json.dumps({**base.READY, "carry": carry}))
        got = self.finish()
        self.assertEqual((got["next_request"]["path"], got["prior_failures"]["path"]), ("report/next-request.json", "report/prior-failures.json"))

    def test_fallen_writer_is_named_in_the_head_until_resume_rewrites_it(self):
        self.facts()
        fell = {"type": "node_error", "step": "report__write-loop", "ts": "t", "error": "Loop-group node failed: usage or credit limit is used up",
                "execution": {"lifecycle": {"providerFailure": {"class": "quota_exhausted"}}}}
        self.log(fell)
        got = self.finish()
        self.assertIsNone(got["human"])
        head = M.writer.machine_head(self.machine())
        self.assertIn("AI が書く報告の本文は無い。書き手のノードが落ちた（Loop-group node failed: usage or credit limit is used up）", head)
        self.assertIn("別のアカウントで run を resume すれば", head)
        self.assertIn("人に向けた報告: 無い（書き手のノードが落ちた（Loop-group node failed: usage or credit limit is used up））", got["report"])
        self.log(fell, {"type": "node_complete", "step": "report__write-loop", "ts": "t2", "execution": {}})
        self.prep()
        self.assertNotIn("AI が書く報告の本文は無い", self.machine())
        self.assertNotIn("AI が書く報告の本文は無い", self.finish() and self.machine())

    def test_fallen_finish_keeps_the_facts_report(self):
        self.facts()
        (self.place / "facts.json").write_text("{壊れた", encoding="utf-8")
        got = self.finish()
        self.assertEqual((got["outcome"], got["ok"], got["human"]), ("record_invalid", False, None))
        self.assertTrue(got["stop_reason"].startswith("report:ValueError: facts.json が無いか読めない"), got["stop_reason"])
        self.assertEqual(got["machine"]["path"], "report/report.md", "facts の機械の報告が在ればそれを指す")

    def test_fallen_finish_without_any_report_writes_its_own_file(self):
        got = self.finish()
        self.assertEqual((got["outcome"], got["machine"]["path"]), ("record_invalid", "report/report-finish-unwritten.md"))
        self.assertIn("報告を組めなかった:", (self.place / "report-finish-unwritten.md").read_text(encoding="utf-8"))

    def test_without_the_libraries_still_returns(self):
        self.facts()
        with tempfile.TemporaryDirectory() as empty:
            self.run.extra = {"WORKS_FACTORY_ROOT": empty}
            got = self.finish()
        self.assertEqual((got["outcome"], got["ok"]), ("record_invalid", False))
        self.assertEqual(got["machine"]["path"], "report/report-finish-unwritten.md")


# 書き手と初見の読み手の役が起こす Claude Code の代わり（Archon の claude provider が話す stream-json の最小の形）。認証のトークンが
# SPENT の時だけ、書き手は使用枠の切れ（SDK の billing_error。Archon は quota_exhausted と読む）で落ちる。ほかは型に合う答えを返す
FAKE_CLAUDE = """import json, os, sys
if sys.argv[1:2] == ["plugin"]:
    print("[]")
    sys.exit(0)
def say(doc):
    print(json.dumps(doc, ensure_ascii=False), flush=True)
schema = {}
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("type") == "control_request":
        schema = msg["request"].get("jsonSchema") or {}
        say({"type": "control_response", "response": {"subtype": "success", "request_id": msg["request_id"], "response": {}}})
    elif msg.get("type") == "user":
        break
session = "fake-session"
say({"type": "system", "subtype": "init", "session_id": session, "model": "sonnet", "tools": [], "plugins": [], "mcp_servers": []})
cold = "verdict" in schema.get("properties", {})
if not cold and os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") == "SPENT":
    words = "Claude AI usage limit reached"
    say({"type": "assistant", "session_id": session, "error": "billing_error",
         "message": {"model": "<synthetic>", "role": "assistant", "content": [{"type": "text", "text": words}]}})
    say({"type": "result", "subtype": "success", "is_error": True, "session_id": session, "result": words,
         "terminal_reason": "api_error", "num_turns": 1})
    sys.exit(1)
answer = ({"verdict": "pass", "stops": [], "guessed": [], "decidable": True} if cold else
          {"text": "依頼で止めた。\\n直した物は無い。\\n次の run に渡す物は無い。", "terms": [],
           "handoff": {"read": [], "kept": [], "set_aside": [], "open": []}})
say({"type": "result", "subtype": "success", "is_error": False, "session_id": session, "num_turns": 1, "total_cost_usd": 0,
     "result": json.dumps(answer, ensure_ascii=False), "structured_output": answer})
"""
SPENT = "SPENT"
# graph の写し: report を include し、後ろに報告を読む node を置く（書き手のループの node の id は include の頭つき）
REPORT_LINE = """name: works-factory-report-line
description: report を include した graph の写し
nodes:
  - id: report
    include: works-factory-report
    with:
      sections: '[{"title": "直した所", "lines": ["単位 u1: 直した"]}]'
      facts: '{"start_ok": true, "proved": true, "gates": [{"at": "final-answer", "decision": "stop", "text": "request: 止め札"}]}'
  - id: after
    bash: echo after
    depends_on: [report]
    trigger_rule: all_done
    mutates_checkout: false
"""


class WriterRunCase(unittest.TestCase):
    """#702 の筋書き: 止めた Archon で報告の block を include した graph を本物の run（dry-run でない）で回し、書き手の役を偽の Claude Code に
    替える。書き手が通る筋は人に向けた報告が載る。使用枠の切れで落ちる筋は run が failed で終わり、機械の報告の冒頭に訳と resume の道が載り、
    別のアカウント（別のトークン）で resume すると書き手のループと出口と後ろが走り直して本文が載る"""

    def setUp(self):
        if shutil.which("uv") is None:
            self.skipTest("uv が無い")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.fake = pathlib.Path(tmp.name) / "claude"
        self.fake.write_text(f"#!{sys.executable}\n{FAKE_CLAUDE}", encoding="utf-8")
        self.fake.chmod(0o755)
        self.flows = pathlib.Path(tmp.name) / "flows"
        shutil.copytree(base.BLOCK, self.flows / "report", ignore=shutil.ignore_patterns("__pycache__"))
        (self.flows / "report-line").mkdir()
        (self.flows / "report-line" / "works-factory-report-line.yaml").write_text(REPORT_LINE, encoding="utf-8")

    def tree(self):
        return archon.tree(["report", "report-line"], workflows=self.flows, shared=kit.SHARED)

    def drive(self, tree, *args, token):
        return archon.archon(tree, "workflow", *args, "--cwd", str(tree), CLAUDE_BIN_PATH=str(self.fake), CLAUDE_CODE_OAUTH_TOKEN=token)

    def run_line(self, tree, token) -> tuple[dict, list]:
        done = self.drive(tree, "run", "works-factory-report-line", "--no-worktree", token=token)
        return self.state(tree, f"{done.stdout}{done.stderr}")

    def state(self, tree, said="") -> tuple[dict, list]:
        runs = json.loads(archon.archon(tree, "workflow", "runs", "--json", "--cwd", str(tree)).stdout)["runs"]
        self.assertEqual(len(runs), 1, said)
        return runs[0], [(e["event_type"], e["step_name"]) for e in self.events(tree, runs[0]["id"]) if e["event_type"].startswith("node_")]

    def events(self, tree, run_id) -> list:
        return json.loads(archon.archon(tree, "workflow", "get", run_id, "--json", "--verbose", "--events", "--cwd", str(tree)).stdout)["events"]

    def written(self, tree, run_id) -> dict:
        """run の置き場の report/ のファイルの名 → 中身"""
        return {p.name: p.read_text(encoding="utf-8") for p in (tree.parent / "archon-home").rglob(f"runs/{run_id}/report/*.md")}

    def test_writer_passes_and_the_human_report_is_written(self):
        with self.tree() as tree:
            run, events = self.run_line(tree, "FRESH")
            files = self.written(tree, run["id"])
        self.assertEqual(run["status"], "completed", events)
        self.assertIn(("node_completed", "report__write-loop"), events)
        self.assertIn("report-ai.md", files)
        self.assertNotIn("AI が書く報告の本文は無い", files["report.md"])

    def test_quota_fall_fails_the_run_and_resume_with_another_account_writes_the_body(self):
        with self.tree() as tree:
            run, first = self.run_line(tree, SPENT)
            fallen = self.written(tree, run["id"])
            resumed = self.drive(tree, "resume", run["id"], token="FRESH")
            again, both = self.state(tree, f"{resumed.stdout}{resumed.stderr}")
            files = self.written(tree, run["id"])
            prepped = [e["data"]["node_output"] for e in self.events(tree, run["id"])
                       if (e["event_type"], e["step_name"]) == ("node_completed", "report__write-loop.cold-prep")]
        self.assertEqual(run["status"], "failed", first)
        self.assertIn(("node_failed", "report__write-loop"), first)
        self.assertIn(("node_completed", "report__finish"), first, "出口は書き手が落ちても走る")
        self.assertNotIn("report-ai.md", fallen)
        head = M.writer.machine_head(fallen["report.md"])
        self.assertIn("AI が書く報告の本文は無い。書き手のノードが落ちた（Loop-group node 'report__write-loop' failed", head)
        self.assertIn(f"{run['id']}", head)
        self.assertIn("resume", head)
        self.assertEqual(again["status"], "completed", f"{resumed.stdout}{resumed.stderr}")
        later = both[len(first):]
        for ran in ("report__write-loop", "report__finish", "after"):
            self.assertIn(("node_completed", ran), later)
        self.assertNotIn(("node_completed", "report__facts"), later, "facts は走り直さない")
        self.assertEqual(len(prepped), 1, both)
        self.assertNotIn("AI が書く報告の本文は無い", prepped[0], "初見の読み手に貼る本文に前の run の訳を残さない")
        self.assertIn("report-ai.md", files)
        for name in ("report.md", "report-ai.md"):
            self.assertNotIn("AI が書く報告の本文は無い", files[name], name)


if __name__ == "__main__":
    unittest.main()

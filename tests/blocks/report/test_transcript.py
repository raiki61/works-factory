"""run の記録の読み（workflows/report/src/transcript.py）。写す元は lib/tests/test_runreport.py の TranscriptCase・WriterFellCase と
tests/workflows/test_report.py の RealRunCase（止めた Archon で本物の run を回し、run の記録の行を読む）"""
import json
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

from tests import archon
from tests.blocks import kit
from tests.blocks.report import base

M = base.src()
RUN = "run-test"


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


def call(step, name, **raw):
    return {"type": "provider_event", "step": step, "workflow_id": RUN, "event": {"type": "tool_call", "toolCallId": f"t-{name}", "name": name,
                                                                                  "rawInput": raw}}


def until(loop, n, ts, code):
    return {"type": "exec_output", "step": f"{loop}-iteration-{n}", "content": "<until_bash>", "exit_code": code, "ts": ts, "workflow_id": RUN}


def fell(step, error, failure_class=None):
    row = {**done(step, "2026-10-18T00:01:00Z", kind="node_error"), "error": error}
    lifecycle = {"status": "failed", "error": error}
    if failure_class:
        lifecycle["providerFailure"] = {"class": failure_class, "evidence": "e"}
    row["execution"]["lifecycle"] = lifecycle
    return row


class FactsCase(unittest.TestCase):
    def test_rows_give_cost_time_failed_and_retried(self):
        rows = [start("judge__diagnose", "2026-10-12T00:00:00Z"), done("judge__diagnose", "2026-10-12T00:03:00Z", cost=0.5, model="sonnet"),
                start("fix__write", "2026-10-12T00:04:00Z"), done("fix__write", "2026-10-12T00:05:00Z", cost=0.25, kind="node_error"),
                start("fix__write", "2026-10-12T00:06:00Z"), done("fix__write", "2026-10-12T00:10:00Z", cost=0.25),
                {**done("fix", "2026-10-12T00:10:00Z", accounting="aggregate"), "cost_usd": 0.5},
                start("eyes__r1", "2026-10-12T00:11:00Z"),
                {**done("eyes__r1", "2026-10-12T00:12:00Z", kind="node_error"), "error": "目が落ちた\n詳しい行"},
                start("report__facts", "2026-10-12T00:13:00Z"), done("report__facts", "2026-10-12T00:13:30Z", kind="node_error"),
                done("test-gate-final__run", "2026-10-12T00:13:00Z")]
        got = M.transcript.facts(rows, exclude_prefix="report__")
        self.assertEqual(got["failed"], ["eyes__r1"])
        self.assertEqual(got["absorbed"], [])
        self.assertEqual(got["retried"], [{"node": "fix__write", "failures": 1, "error": ""}])
        self.assertEqual(got["cost"], {"judge__diagnose": 0.5, "fix__write": 0.5})
        self.assertNotIn("fix", got["cost"], "言い直しの行は数えない")
        self.assertEqual(got["minutes"]["judge__diagnose"], 3.0)
        self.assertEqual(got["uncosted"]["test-gate-final__run"], 1)
        self.assertEqual(got["models"], {"judge__diagnose": ["sonnet"]})
        self.assertNotIn("report__facts", got["errors"], "自分の block の落ちは数えない")

    def test_unreadable_record_has_every_field(self):
        got = M.transcript.facts(None)
        self.assertFalse(got["ok"])
        self.assertEqual(set(got), set(M.transcript.facts([])))

    def test_declared_fall_is_absorbed_and_the_rest_is_failed(self):
        rows = [start("fix__write", "2026-10-12T00:00:00Z"), {**done("fix__write", "2026-10-12T00:01:00Z", kind="node_error"), "error": "修正の筋が落ちた"},
                start("eyes__r1", "2026-10-12T00:02:00Z"), {**done("eyes__r1", "2026-10-12T00:03:00Z", kind="node_error"), "error": "目が落ちた"},
                start("collect", "2026-10-12T00:04:00Z"), done("collect", "2026-10-12T00:05:00Z")]
        got = M.transcript.facts(rows, optional=("eyes__",))
        self.assertEqual(got["failed"], ["fix__write"])
        self.assertEqual(got["absorbed"], [{"node": "eyes__r1", "error": "目が落ちた"}])
        self.assertEqual(M.transcript.facts(rows)["failed"], ["fix__write", "eyes__r1"], "宣言が無ければ落ちを全部途中で終わった落ちに数える")
        exact = M.transcript.facts(rows, optional=("fix__write",))
        self.assertEqual(exact["absorbed"], [{"node": "fix__write", "error": "修正の筋が落ちた"}])
        near = M.transcript.facts([{**done("fix__lens-collect", "t", kind="node_error"), "step": "fix__lens-collect"}], optional=("fix__lens",))
        self.assertEqual(near["failed"], ["fix__lens-collect"], "区切りの無い頭は別の node まで受け止めない")

    def test_models_and_efforts(self):
        rows = [done("fix__write", "t", cost=0.1, model="sonnet", effort="medium"), done("fix__write", "t", cost=0.1, model="sonnet", effort="high"),
                done("fix__write", "t", cost=0.1, model="opus")]
        got = M.transcript.facts(rows)
        self.assertEqual((got["models"], got["efforts"]), ({"fix__write": ["sonnet", "opus"]}, {"fix__write": ["medium", "high"]}))
        self.assertEqual(M.transcript.node_model_lines(got), ["fix__write: sonnet, opus（run の途中で替わった）（effort: medium, high）"])
        self.assertEqual(M.transcript.node_model_lines(M.transcript.facts(None)), ["run の記録が読めない"])
        self.assertEqual(M.transcript.node_model_lines(M.transcript.facts([])), ["記録に模型の欄が無い"])

    def test_until_rows_give_resubmit_count_and_minutes(self):
        rows = [until("judge__loop", 1, "2026-10-12T00:01:00Z", 1), until("judge__loop", 2, "2026-10-12T00:03:00Z", 0),
                until("fix__tdd", 1, "2026-10-12T00:04:00Z", 0),
                until("report__ask", 1, "2026-10-12T00:05:00Z", 1), until("report__ask", 2, "2026-10-12T00:06:00Z", 0),
                until("fix__kill", 1, "2026-10-12T00:07:00Z", "SIGTERM"), until("fix__kill", 2, "2026-10-12T00:09:00Z", 0),
                until("fix__flag", 1, "2026-10-12T00:10:00Z", True), until("fix__flag", 2, "2026-10-12T00:11:00Z", 0),
                {**until("fix__other", 1, "2026-10-12T00:12:00Z", 1), "content": "ほかの呼び"}]
        got = M.transcript.facts(rows, exclude_prefix="report__")
        self.assertEqual(got["resubmits"], {"judge__loop": {"count": 1, "minutes": 2.0}, "fix__tdd": {"count": 0, "minutes": 0.0},
                                            "fix__kill": {"count": 0, "minutes": 0.0}, "fix__flag": {"count": 0, "minutes": 0.0}})
        lines = M.transcript.resubmit_rows(got)
        self.assertEqual(lines[0], "judge__loop: until が通らず回り直した回 1（受け付けのループでは拒否で出し直した回）・2.0 分")
        self.assertEqual(lines[-1], M.transcript.CHILD_LOOPS)
        self.assertEqual(M.transcript.resubmit_rows(M.transcript.facts([until("a__l", 1, "t", 0)]))[0], "回り直し: 0 回（until の行を読んだループ 1 本）")
        self.assertEqual(M.transcript.resubmit_rows(M.transcript.facts([]))[0], "回り直し: 数えられない（記録にループの until の行が無い）")

    def test_cost_section(self):
        rows = [start("a", "2026-10-12T00:00:00Z"), done("a", "2026-10-12T00:03:00Z", cost=0.5), done("b", "2026-10-12T00:03:00Z")]
        lines = M.transcript.head_cost(M.transcript.facts(rows), "")
        self.assertIn("費用の合計: $0.5000", lines[0])
        self.assertEqual(lines[1], "a: $0.5000・3.0 分")
        self.assertEqual(lines[2], "b: 費用の記録なし・費用の欄が無い行 1 件（AI ノードでないノードか、提供元が費用を返さなかった）・時間を測れない")
        self.assertEqual(M.transcript.head_cost(M.transcript.facts(None), ""), ["費用: 取れない（run の記録が読めない）"])
        self.assertEqual(M.transcript.head_cost(M.transcript.facts(None), "訳 W"), ["費用: 取れない（訳 W）"])


class CallsCase(unittest.TestCase):
    def test_calls_per_node_and_lines(self):
        rows = [call("fix__a", "Read", file_path="/repo/x.py"), call("fix__a", "Read", file_path="/repo/x.py"), call("fix__a", "Edit", file_path="/repo/y.py"),
                call("fix__a", "Bash", command="ls"), call("fix__b", "Bash", command="ls"), call("fix__b", "Grep", pattern="x"),
                call("report__write", "Read", file_path="/repo/report.md")]
        got = M.transcript.facts(rows, exclude_prefix="report__")
        self.assertEqual(got["calls"], {"fix__a": {"Read": ["/repo/x.py"], "Edit": ["/repo/y.py"], "Write": [], "Bash": 1},
                                        "fix__b": {"Read": [], "Edit": [], "Write": [], "Bash": 1}})
        lines = M.transcript.calls_lines(got, "", "/repo")
        self.assertEqual(lines[1], "  - fix__a: Read 1 件・Edit 1 件・Write 0 件（ファイル: x.py・y.py）")
        self.assertEqual(lines[2], "  - fix__b: Read 0 件・Edit 0 件・Write 0 件")
        self.assertTrue(lines[-2].endswith("。Bash の呼び 2 回: fix__a 1・fix__b 1"), lines[-2])
        self.assertEqual(lines[-1], M.transcript.CHILD_RUNS)

    def test_more_than_three_files_are_counted(self):
        rows = [call("a", "Read", file_path=f"/r/{n}.py") for n in range(5)]
        line = M.transcript.calls_lines(M.transcript.facts(rows), "", "/r")[1]
        self.assertIn("（ファイル: 0.py・1.py・2.py ほか 2 件）", line)

    def test_unreadable_record_and_no_calls_are_said(self):
        self.assertIn("  - run の記録が読めない（訳 W）", M.transcript.calls_lines(M.transcript.facts(None), "訳 W", None))
        self.assertIn("  - 道具を呼んだノードが run の記録に無い", M.transcript.calls_lines(M.transcript.facts([]), "", None))
        self.assertIn("Bash の呼びは run の記録が読めないので数えられない", M.transcript.calls_lines(M.transcript.facts(None), "", None)[-2])

    def test_no_block_name_in_the_child_lines(self):
        for line in (M.transcript.CHILD_RUNS, M.transcript.CHILD_LOOPS):
            self.assertNotIn("fix", line)


class WriterFellCase(unittest.TestCase):
    """#702: 書き手のループが落ちた訳を run の記録から読む"""
    QUOTA = "Loop-group node 'write-loop' failed at iteration 1: 'write': usage or credit limit is used up\n詳しい行"
    SAFEGUARDS = "Loop-group node 'write-loop' failed at iteration 1: 'write': API Error: Sonnet 5.5's safeguards flagged this message"
    MACHINE = "# 報告（run run-1）\n\n起きたこと\n当ててよいか\n人が決めること\n\n## 1. 結末\n\n本文\n"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.machine = pathlib.Path(tmp.name) / "report.md"
        self.machine.write_text(self.MACHINE, encoding="utf-8")

    def head(self) -> str:
        return M.writer.machine_head(self.machine.read_text(encoding="utf-8"))

    def test_last_row_of_the_loop_decides(self):
        quota = fell("report__write-loop", self.QUOTA, "quota_exhausted")
        self.assertEqual(M.transcript.writer_fell([start("report__write-loop", "t"), quota], "report__write-loop"),
                         {"error": "Loop-group node 'write-loop' failed at iteration 1: 'write': usage or credit limit is used up", "quota": True})
        self.assertEqual(M.transcript.writer_fell([fell("write-loop", self.SAFEGUARDS)], "write-loop"), {"error": self.SAFEGUARDS, "quota": False})
        again = done("report__write-loop", "2026-10-18T00:09:00Z")
        for rows in ([quota, again], [quota, {"type": "node_skipped", "step": "report__write-loop"}], [], None,
                     [fell("report__write", self.QUOTA, "quota_exhausted")]):
            with self.subTest(rows=rows):
                self.assertIsNone(M.transcript.writer_fell(rows, "report__write-loop"))

    def test_note_names_the_error_and_resume_only_for_quota(self):
        M.writer.note_writer_fell(self.machine, {"error": "API Error: x", "quota": False}, run_id="run-1")
        self.assertTrue(self.head().endswith(M.writer.WRITER_FELL.format(error="API Error: x")), self.head())
        self.assertNotIn("resume", self.head())
        self.assertIn("## 1. 結末\n\n本文", self.machine.read_text(encoding="utf-8"))
        M.writer.note_writer_fell(self.machine, {"error": "used up", "quota": True}, run_id="run-1")
        lines = [x for x in self.head().splitlines() if x.startswith("AI が書く報告の本文は無い")]
        self.assertEqual(len(lines), 1, "前の周の訳を置き換える")
        self.assertIn("used up", lines[0])
        self.assertIn("run-1", lines[0])
        self.assertIn("鎖の run を resume する", lines[0])

    def test_rewritten_run_drops_the_note_and_untouched_report_stays(self):
        M.writer.note_writer_fell(self.machine, None, run_id="run-1")
        self.assertEqual(self.machine.read_text(encoding="utf-8"), self.MACHINE)
        M.writer.note_writer_fell(self.machine, {"error": "used up", "quota": True}, run_id="run-1")
        M.writer.note_writer_fell(self.machine, None, run_id="run-1")
        self.assertEqual(self.machine.read_text(encoding="utf-8"), self.MACHINE)


class ReadCase(unittest.TestCase):
    def test_read_and_own_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / f"{RUN}.jsonl").write_text('{"step": "a"}\nこわれた行\n{"step": "b"}\n', encoding="utf-8")
            with mock.patch.dict("os.environ", {"LOG_DIR": tmp, "WORKFLOW_ID": RUN}):
                self.assertEqual(M.transcript.read(), ([{"step": "a"}, {"step": "b"}], ""))
            with mock.patch.dict("os.environ", {"LOG_DIR": tmp, "WORKFLOW_ID": "other"}):
                rows, why = M.transcript.read()
                self.assertIsNone(rows)
                self.assertIn("読めない", why)
        with mock.patch.dict("os.environ", {"LOG_DIR": "", "WORKFLOW_ID": RUN}):
            self.assertEqual(M.transcript.read()[0], None)
        for path, want in (("report__finish", "report__"), ("outer__report__facts", "outer__report__"), ("facts", ""),
                           ("report__write-loop.write-prep", "report__"), ("outer__report__write-loop.write-prep", "outer__report__")):
            with self.subTest(path), mock.patch.dict("os.environ", {"ARCHON_NODE_EXECUTION": json.dumps({"path": path})}):
                self.assertEqual(M.transcript.own_prefix(), want)
        with mock.patch.dict("os.environ", {"ARCHON_NODE_EXECUTION": "{こわれた"}):
            self.assertEqual(M.transcript.own_prefix(), "")


PROBE_HEAD = '# /// script\n# requires-python = ">=3.12"\n# dependencies = []\n# ///\n'
PROBE = {
    "works-factory-probe.yaml": """name: works-factory-probe
description: report の読み手に本物の run の記録を渡す試し
nodes:
  - id: make
    script: make
    runtime: uv
  - id: boom
    script: boom
    runtime: uv
    depends_on: [make]
  - id: read
    script: read
    runtime: uv
    depends_on: [boom]
    trigger_rule: all_done
""",
    "scripts/make.py": PROBE_HEAD + 'import json\nprint(json.dumps({"a": 1}))\n',
    "scripts/boom.py": PROBE_HEAD + 'import sys\nsys.exit("boom")\n',
    "scripts/read.py": PROBE_HEAD + """import json, os
out = os.environ["ARTIFACTS_DIR"]
keys = ("LOG_DIR", "WORKFLOW_ID", "ARCHON_NODE_EXECUTION")
with open(os.path.join(out, "env.json"), "w", encoding="utf-8") as f:
    json.dump({k: os.environ.get(k, "") for k in keys}, f)
print("{}")
""",
}


class RealRunCase(unittest.TestCase):
    """止めた Archon で本物の run（dry-run でない）を 1 回回し、実行基盤が書いた run の記録を、手で組んだ見本でなく本物の出力のまま読ませる
    （欄の名が変われば赤）"""

    def test_readers_read_a_real_run(self):
        if shutil.which("uv") is None:
            self.skipTest("uv が無い")
        with tempfile.TemporaryDirectory() as tmp:
            flows = pathlib.Path(tmp)
            for rel, text in PROBE.items():
                (flows / "probe" / rel).parent.mkdir(parents=True, exist_ok=True)
                (flows / "probe" / rel).write_text(text, encoding="utf-8")
            with archon.tree(["probe"], workflows=flows, shared=kit.SHARED) as tree:
                done_run = archon.archon(tree, "workflow", "run", "works-factory-probe", "--no-worktree", "--cwd", str(tree))
                found = sorted((tree.parent / "archon-home").rglob("env.json"))
                self.assertEqual(len(found), 1, f"{done_run.stdout}{done_run.stderr}")
                env = json.loads(found[0].read_text(encoding="utf-8"))
                with mock.patch.dict("os.environ", {"LOG_DIR": env["LOG_DIR"], "WORKFLOW_ID": env["WORKFLOW_ID"]}):
                    rows, why = M.transcript.read()
                self.assertEqual(why, "")
                got = M.transcript.facts(rows, optional=("boom",))
                self.assertTrue(got["ok"])
                self.assertEqual(got["failed"], [])
                self.assertEqual([a["node"] for a in got["absorbed"]], ["boom"])
                self.assertEqual(M.transcript.facts(rows)["failed"], ["boom"], "受け止めると宣言していない段の落ち")
                self.assertIn("boom", got["errors"]["boom"])
                self.assertLessEqual({"make", "boom", "read"}, set(got["minutes"]))


if __name__ == "__main__":
    unittest.main()

"""run の記録の読み（workflows/report/src/transcript.py）。写す元は test_runreport.py の TranscriptCase・WriterFellCase と
tests/workflows の test_report.py の RealRunCase（止めた Archon で本物の run を回し、run の記録の行を読む）"""
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


class WriterFellCase(unittest.TestCase):
    """#702: 書き手のループが落ちた訳を run の記録から読む"""
    QUOTA = "Loop-group node 'write-loop' failed at iteration 1: 'write': usage or credit limit is used up\n詳しい行"
    SAFEGUARDS = "Loop-group node 'write-loop' failed at iteration 1: 'write': API Error: Sonnet 5.5's safeguards flagged this message"
    MACHINE = "# 報告（run run-1）\n\n起きたこと\n当ててよいか\n人が決めること\n\n## 1. 結末\n\n本文\n\n## 注意（読めなかった物）\n\n- 無い\n"

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

    def notes(self) -> str:
        return self.machine.read_text(encoding="utf-8").split("## 注意（読めなかった物）\n\n", 1)[1]

    def test_note_names_the_error_and_resume_only_for_quota(self):
        H = M.head
        M.writer.note_writer_fell(self.machine, {"error": "API Error: x", "quota": False}, run_id="run-1")
        self.assertTrue(self.head().endswith(H.render(H.Line.WRITER_FELL_OTHER)), self.head())
        self.assertNotIn("resume の命令", self.head(), "使用枠の切れでない落ちには resume の命令を付けない")
        self.assertNotIn("API Error: x", self.head(), "誤りの文の全文は頭に置かない")
        self.assertEqual(self.notes(), "- 書き手の段が落ちた誤り: API Error: x\n", "誤りの文は注意の節に 1 行")
        self.assertIn("## 1. 結末\n\n本文", self.machine.read_text(encoding="utf-8"))
        M.writer.note_writer_fell(self.machine, {"error": "used up", "quota": True}, run_id="run-1")
        quota = H.render(H.Line.WRITER_FELL_QUOTA, H.QuotaSlot(H.Command(M.writer.answer.resume("run-1"))))
        fell = [x for x in self.head().splitlines() if H.parse(x) and H.parse(x).kind in (H.Line.WRITER_FELL_OTHER, H.Line.WRITER_FELL_QUOTA)]
        self.assertEqual(fell, [quota], "前の周の行を置き換える")
        self.assertIn("run-1", quota)
        self.assertIn("別のアカウントで run を resume すれば", quota)
        self.assertNotIn("used up", self.head())
        self.assertEqual(self.notes(), "- 書き手の段が落ちた誤り: used up\n", "前の周の誤りの行を置き換える")

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

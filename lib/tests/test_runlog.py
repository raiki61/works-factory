"""run の記録の読み（lib/runlog.py。integration.md の 4.5-2）。写す元は tests/blocks/report/test_transcript.py の読みの部分
（report の block と chain の script が同じ口を使う）。報告の行の組み立ての試験は report の block の側に残る。"""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import runlog  # noqa: E402

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


def spend(step, tokens, kind="node_complete", accounting="node"):
    """Archon の本物の行の形（execution.spend.tokens が {source: provider, value} か {source: unavailable, reason}。費用の欄は unavailable）の
    済んだ行。tokens が None なら spend の欄が無い行"""
    row = done(step, "2026-10-12T00:00:00Z", kind=kind, accounting=accounting)
    if tokens is not None:
        got = {"source": "provider", "value": tokens} if isinstance(tokens, dict) else tokens
        row["execution"]["spend"] = {"tokens": got, "costUsd": {"source": "unavailable", "reason": "not_applicable"}}
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
        got = runlog.facts(rows, exclude_prefix="report__")
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
        got = runlog.facts(None)
        self.assertFalse(got["ok"])
        self.assertEqual(set(got), set(runlog.facts([])))

    def test_declared_fall_is_absorbed_and_the_rest_is_failed(self):
        rows = [start("fix__write", "2026-10-12T00:00:00Z"), {**done("fix__write", "2026-10-12T00:01:00Z", kind="node_error"), "error": "修正の筋が落ちた"},
                start("eyes__r1", "2026-10-12T00:02:00Z"), {**done("eyes__r1", "2026-10-12T00:03:00Z", kind="node_error"), "error": "目が落ちた"},
                start("collect", "2026-10-12T00:04:00Z"), done("collect", "2026-10-12T00:05:00Z")]
        got = runlog.facts(rows, optional=("eyes__",))
        self.assertEqual(got["failed"], ["fix__write"])
        self.assertEqual(got["absorbed"], [{"node": "eyes__r1", "error": "目が落ちた"}])
        self.assertEqual(runlog.facts(rows)["failed"], ["fix__write", "eyes__r1"], "宣言が無ければ落ちを全部途中で終わった落ちに数える")
        exact = runlog.facts(rows, optional=("fix__write",))
        self.assertEqual(exact["absorbed"], [{"node": "fix__write", "error": "修正の筋が落ちた"}])
        near = runlog.facts([{**done("fix__lens-collect", "t", kind="node_error"), "step": "fix__lens-collect"}], optional=("fix__lens",))
        self.assertEqual(near["failed"], ["fix__lens-collect"], "区切りの無い頭は別の node まで受け止めない")

    def test_models_and_efforts(self):
        rows = [done("fix__write", "t", cost=0.1, model="sonnet", effort="medium"), done("fix__write", "t", cost=0.1, model="sonnet", effort="high"),
                done("fix__write", "t", cost=0.1, model="opus")]
        got = runlog.facts(rows)
        self.assertEqual((got["models"], got["efforts"]), ({"fix__write": ["sonnet", "opus"]}, {"fix__write": ["medium", "high"]}))

    def test_until_rows_give_resubmit_count_and_minutes(self):
        rows = [until("judge__loop", 1, "2026-10-12T00:01:00Z", 1), until("judge__loop", 2, "2026-10-12T00:03:00Z", 0),
                until("fix__tdd", 1, "2026-10-12T00:04:00Z", 0),
                until("report__ask", 1, "2026-10-12T00:05:00Z", 1), until("report__ask", 2, "2026-10-12T00:06:00Z", 0),
                until("fix__kill", 1, "2026-10-12T00:07:00Z", "SIGTERM"), until("fix__kill", 2, "2026-10-12T00:09:00Z", 0),
                until("fix__flag", 1, "2026-10-12T00:10:00Z", True), until("fix__flag", 2, "2026-10-12T00:11:00Z", 0),
                {**until("fix__other", 1, "2026-10-12T00:12:00Z", 1), "content": "ほかの呼び"}]
        got = runlog.facts(rows, exclude_prefix="report__")
        self.assertEqual(got["resubmits"], {"judge__loop": {"count": 1, "minutes": 2.0}, "fix__tdd": {"count": 0, "minutes": 0.0},
                                            "fix__kill": {"count": 0, "minutes": 0.0}, "fix__flag": {"count": 0, "minutes": 0.0}})


    def test_spend_tokens_are_summed_per_node_without_double_counting(self):
        full = {"input": 1000, "output": 200, "cacheRead": 700, "cacheWrite": 100}
        rows = [spend("a", full, kind="node_error"), spend("a", {"input": 500, "output": 50, "cacheRead": 300, "cacheWrite": 0}),
                spend("loop", full, accounting="aggregate"),
                spend("script", {"source": "unavailable", "reason": "not_applicable"}), spend("bare", None),
                spend("flag", {"source": "provider", "value": {"input": True, "output": 1}}),
                spend("nocr", {"input": 100, "output": 10, "cacheWrite": 20}),
                spend("partial", {"input": 300, "output": 30, "cacheRead": 100, "cacheWrite": 50, "cachePartial": True}),
                spend("mix", {"input": 100, "output": 10, "cacheWrite": 20}), spend("mix", full)]
        got = runlog.facts(rows)
        self.assertEqual(got["tokens"]["a"], {"input": 1500, "output": 250, "cacheRead": 1000, "cacheWrite": 100, "uncached": 400},
                         "input は cacheRead・cacheWrite を含む総量なので足し直さず、キャッシュ外は input − cacheRead − cacheWrite")
        self.assertNotIn("loop", got["tokens"], "言い直しの行（aggregate）は数えない")
        self.assertNotIn("loop", got["untokened"])
        self.assertEqual(got["untokened"], {"script": 1, "bare": 1, "flag": 1})
        self.assertEqual(got["tokens"]["nocr"], {"input": 100, "output": 10, "cacheRead": 0, "cacheWrite": 20, "cacheUnknown": 1},
                         "cacheRead の欠けた行はキャッシュ外を出さず、内訳が不明な起動に数える")
        self.assertEqual(got["tokens"]["partial"], {"input": 300, "output": 30, "cacheRead": 100, "cacheWrite": 50, "cacheUnknown": 1},
                         "cachePartial の行は cacheRead・cacheWrite が数でも内訳が不明な起動に数える")
        self.assertEqual(got["tokens"]["mix"], {"input": 1100, "output": 210, "cacheRead": 700, "cacheWrite": 120, "cacheUnknown": 1},
                         "後の行が全部知れていても、不明な起動が一度在ればキャッシュ外を出さない")
        self.assertEqual({k: sorted(v) for k, v in {"tokens": got["tokens"], "untokened": got["untokened"]}.items()},
                         {"tokens": ["a", "mix", "nocr", "partial"], "untokened": ["bare", "flag", "script"]})
        self.assertEqual(sorted(runlog.facts(None)["tokens"]) + sorted(runlog.facts(None)["untokened"]), [])

    def test_measurement_takes_only_numeric_provider_value(self):
        def cost(entry):
            return runlog.measurement({"costUsd": entry}, "costUsd", runlog.number)

        self.assertEqual(cost({"source": "provider", "value": 0.5}), (0.5, None))
        self.assertEqual(cost({"source": "provider", "value": 0}), (0, None), "0 は知れた値")
        self.assertEqual(cost({"source": "unavailable", "reason": "not_applicable"}), (None, "not_applicable"))
        for entry in ({"source": "provider", "value": "0.5"}, {"source": "provider", "value": True}, {"source": "provider"},
                      {"source": "estimate", "value": 1}, "0.5"):
            with self.subTest(entry=entry):
                value, why = cost(entry)
                self.assertIsNone(value)
                self.assertTrue(why, "値が無い訳を残す")
        self.assertEqual(runlog.measurement({}, "costUsd", runlog.number), (None, "spend.costUsd が無い"))
        self.assertEqual(runlog.measurement(None, "costUsd", runlog.number), (None, "spend.costUsd が無い"))
        value = {"input": 10, "output": 2, "cacheRead": 4, "extra": "x"}
        self.assertEqual(runlog.measurement({"tokens": {"source": "provider", "value": value}}, "tokens", runlog.tokens),
                         ({"input": 10, "output": 2, "cacheRead": 4}, None), "dict を受ける accept なら tokens の dict が返る")
        self.assertEqual(runlog.measurement({"tokens": {"source": "provider", "value": value}}, "tokens", dict),
                         (value, None))
        for bad in ({"output": 2}, {"input": 10}, {"input": "10", "output": 2}, [], None):
            with self.subTest(tokens=bad):
                self.assertIsNone(runlog.measurement({"tokens": {"source": "provider", "value": bad}}, "tokens", runlog.tokens)[0])
        self.assertEqual(runlog.number(True), None)
        self.assertEqual((runlog.number(3), runlog.number(1.5), runlog.number("1")), (3, 1.5, None))


class CallsCase(unittest.TestCase):
    def test_calls_per_node(self):
        rows = [call("fix__a", "Read", file_path="/repo/x.py"), call("fix__a", "Read", file_path="/repo/x.py"), call("fix__a", "Edit", file_path="/repo/y.py"),
                call("fix__a", "Bash", command="ls"), call("fix__b", "Bash", command="ls"), call("fix__b", "Grep", pattern="x"),
                call("report__write", "Read", file_path="/repo/report.md")]
        got = runlog.facts(rows, exclude_prefix="report__")
        self.assertEqual(got["calls"], {"fix__a": {"Read": ["/repo/x.py"], "Edit": ["/repo/y.py"], "Write": [], "Bash": 1},
                                        "fix__b": {"Read": [], "Edit": [], "Write": [], "Bash": 1}})

class ReadCase(unittest.TestCase):
    def test_read_and_own_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / f"{RUN}.jsonl").write_text('{"step": "a"}\nこわれた行\n{"step": "b"}\n', encoding="utf-8")
            with mock.patch.dict("os.environ", {"LOG_DIR": tmp, "WORKFLOW_ID": RUN}):
                self.assertEqual(runlog.read(), ([{"step": "a"}, {"step": "b"}], ""))
            with mock.patch.dict("os.environ", {"LOG_DIR": tmp, "WORKFLOW_ID": "other"}):
                rows, why = runlog.read()
                self.assertIsNone(rows)
                self.assertIn("読めない", why)
        with mock.patch.dict("os.environ", {"LOG_DIR": "", "WORKFLOW_ID": RUN}):
            self.assertEqual(runlog.read()[0], None)
        for path, want in (("report__finish", "report__"), ("outer__report__facts", "outer__report__"), ("facts", ""),
                           ("report__write-loop.write-prep", "report__"), ("outer__report__write-loop.write-prep", "outer__report__")):
            with self.subTest(path), mock.patch.dict("os.environ", {"ARCHON_NODE_EXECUTION": json.dumps({"path": path})}):
                self.assertEqual(runlog.own_prefix(), want)
        with mock.patch.dict("os.environ", {"ARCHON_NODE_EXECUTION": "{こわれた"}):
            self.assertEqual(runlog.own_prefix(), "")


if __name__ == "__main__":
    unittest.main()

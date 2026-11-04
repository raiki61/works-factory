"""span の木の OTLP での送り（viewer/src/otlp.py）と、入口 viewer/runtrace.py が SDK に利用者の OTEL_ の名を読ませないこと
（viewer/AGENTS.md の E25 の 2・docs/design/viewer.md の 8.1）。

- 送り: sendto の答えの URL へ、span の数と親子と時刻（ミリ秒）と id のまま protobuf で届く。圧縮しない
- 入口を子で起こす: 子の env に OTEL_EXPORTER_OTLP_HEADERS と OTEL_EXPORTER_OTLP_COMPRESSION=gzip を置いても、受け口に届いた頼みに
  その headers が無く、本文が圧縮されていない（入口が OTEL_ の名を SDK の前に外している）。送り先は引数 --endpoint で渡す（env の
  OTEL_EXPORTER_OTLP_ENDPOINT で名指すと sendto は決めどおり env の headers を付けるので、外した印にならない）
- 手元へは proxy を通さない: 子の env の HTTP_PROXY・HTTPS_PROXY・ALL_PROXY に届かない番地を置き、NO_PROXY・no_proxy を空にしても
  届く（NO_PROXY を空にするのは、CI の runner や利用者の shell の NO_PROXY が 127.0.0.1 を外していると、守りが外れても届くため）

extra trace（OpenTelemetry の SDK と OTLP/HTTP の exporter）が無ければ名前つきで見送る。見送りの条件は SDK の import の 1 つだけ。
CI の job trace は旗 WORKS_FACTORY_TRACE_REQUIRED（hermetic.TRACE_REQUIRED_ENV）を立て、見送る所を赤にする。
受け口は試験の中で 127.0.0.1 に立てる標準ライブラリの HTTP の口で、外の網には出ない。run の家は WORKS_FACTORY_HOME（E24）で一時の
フォルダへ向け、利用者の本物の run の家を読まない。
"""
import gzip
import json
import os
import sqlite3
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tests.bin import hermetic

ROOT = Path(__file__).resolve().parents[2]
try:
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
    from viewer.src import otlp
except ImportError as missing:
    SDK_MISSING = f"extra trace（OpenTelemetry の SDK）が無い: {missing}"
else:
    SDK_MISSING = ""

from bin._lib import isolate, launcher  # noqa: E402
from viewer.src import runread, sendto, trace  # noqa: E402

UNREACHABLE = "http://127.0.0.1:9"


def setUpModule():
    if SDK_MISSING:
        if os.environ.get(hermetic.TRACE_REQUIRED_ENV):
            raise AssertionError(SDK_MISSING)
        raise unittest.SkipTest(SDK_MISSING)


class Sink:
    """127.0.0.1 の受け口。届いた頼み（path・headers・本文）を持つ"""

    def __init__(self, case: unittest.TestCase):
        got = self.got = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                got.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
                self.send_response(200)
                self.send_header("Content-Type", "application/x-protobuf")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        case.addCleanup(self.server.server_close)
        case.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1/traces"

    def spans(self) -> list:
        out = []
        for request in self.got:
            message = ExportTraceServiceRequest()
            message.ParseFromString(request["body"])
            out += [span for resource in message.resource_spans for scope in resource.scope_spans for span in scope.spans]
        return out


def built() -> dict:
    run = {"id": "f" * 16, "parent": None, "name": "works-factory-line", "start": "2026-11-04T00:16:00.125Z",
           "end": "2026-11-04T01:25:00.000Z", "attributes": {trace.KIND: "AGENT", trace.COST: 1.5, trace.RUN_ID: "r1"}}
    node = {"id": "e" * 16, "parent": run["id"], "name": "review-tree", "start": "2026-11-04T00:17:00.001Z",
            "end": "2026-11-04T00:20:00.000Z", "attributes": {trace.KIND: "LLM", trace.PROMPT: 12}}
    return {"trace_id": "a" * 32, "spans": [run, node], "unread": {}}


class SendTest(unittest.TestCase):
    def test_the_spans_arrive_as_they_were_built(self):
        sink = Sink(self)
        sent = otlp.send(built(), sendto.decide(sink.url, {}, False))
        self.assertEqual(sent, 2)
        self.assertEqual([r["path"] for r in sink.got], ["/v1/traces"])
        self.assertNotIn("content-encoding", sink.got[0]["headers"])
        spans = {span.name: span for span in sink.spans()}
        run, node = spans["works-factory-line"], spans["review-tree"]
        self.assertEqual(run.trace_id.hex(), "a" * 32)
        self.assertEqual(node.span_id.hex(), "e" * 16)
        self.assertEqual(node.parent_span_id.hex(), run.span_id.hex())
        self.assertEqual(run.parent_span_id, b"")
        self.assertEqual(run.start_time_unix_nano, int(runread.when("2026-11-04T00:16:00.125Z").timestamp() * 1000) * 1_000_000)
        attrs = {a.key: a.value for a in run.attributes}
        self.assertEqual(attrs[trace.COST].double_value, 1.5)
        self.assertEqual(attrs[trace.KIND].string_value, "AGENT")

    def test_env_headers_are_sent(self):
        sink = Sink(self)
        otlp.send(built(), sendto.decide(None, {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": sink.url,
                                                "OTEL_EXPORTER_OTLP_HEADERS": "authorization=Bearer%20k"}, False))
        self.assertEqual(sink.got[0]["headers"]["authorization"], "Bearer k")


class EntryTest(unittest.TestCase):
    """入口を子で起こし、小さな run の記録を手元の受け口へ送らせる"""

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.home, self.rid = self.tmp / "home", "run-trace-1"
        db = self.home / isolate.DIRS["ARCHON_HOME"] / runread.DB_FILE
        db.parent.mkdir(parents=True)
        con = sqlite3.connect(db)
        con.execute(f"create table {runread.RUN_TABLE} ({', '.join(runread.RUN_COLUMNS)})")
        con.execute(f"create table {runread.EVENT_TABLE} ({', '.join(runread.EVENT_COLUMNS)})")
        con.execute(f"insert into {runread.RUN_TABLE} (id, workflow_name, status, parent_run_id, started_at, output_root, metadata) "
                    "values (?, 'g', 'completed', null, '2026-11-04 01:00:00', ?, '{}')", (self.rid, str(self.home)))
        con.commit()
        con.close()
        node = {"step": "a", runread.EXECUTION: {"path": "a", "invocation": {"id": "a"}, "node": {"kind": "script"}}}
        log = self.home / runread.LOGS / f"{self.rid}.jsonl"
        log.parent.mkdir()
        log.write_text("\n".join(json.dumps({**node, "type": kind, "ts": ts}) for kind, ts in
                                 (("node_start", "2026-11-04T01:00:00.000Z"), ("node_complete", "2026-11-04T01:00:02.500Z"))),
                       encoding="utf-8")
        self.target = self.tmp / "target"
        self.target.mkdir()

    def run_entry(self, endpoint: str, **env) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(ROOT / "viewer" / "runtrace.py"), "--target", str(self.target), "--run", self.rid,
                               "--endpoint", endpoint], capture_output=True, text=True, cwd=ROOT, timeout=120,
                              env=hermetic.child_env(**{launcher.HOME_ENV: str(self.home), **env}))

    def test_the_entry_sends_the_run_without_the_users_otel_settings_or_proxy(self):
        sink = Sink(self)
        done = self.run_entry(sink.url, OTEL_EXPORTER_OTLP_HEADERS="x-leak=secret", OTEL_EXPORTER_OTLP_COMPRESSION="gzip",
                              HTTP_PROXY=UNREACHABLE, HTTPS_PROXY=UNREACHABLE, ALL_PROXY=UNREACHABLE, http_proxy=UNREACHABLE,
                              https_proxy=UNREACHABLE, all_proxy=UNREACHABLE, NO_PROXY="", no_proxy="")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(sink.got, done.stderr)
        for request in sink.got:
            self.assertNotIn("x-leak", request["headers"])
            self.assertNotIn("content-encoding", request["headers"])
            self.assertFalse(request["body"].startswith(gzip.compress(b"")[:2]))
        spans = sink.spans()
        names = sorted(span.name for span in spans)
        self.assertEqual(names, ["a", "g"])
        root = next(span for span in spans if span.name == "g")
        attrs = {a.key: a.value.string_value for a in root.attributes}
        self.assertEqual(attrs[trace.RUN_ID], self.rid)


if __name__ == "__main__":
    unittest.main()

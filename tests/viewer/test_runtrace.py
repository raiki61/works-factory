"""入口 viewer/runtrace.py は、送り先の決め（src/sendto.py）を通ってから OpenTelemetry の SDK を読む（viewer/AGENTS.md の E25 の 2・
docs/design/viewer.md の 8.1 の入口の順）。

- 送り先が無い時と、手元でない送り先で --remote が無い時は、run を読まずに sendto の拒む訳の 1 行を出し、終了の値 2 で止まる
- 止まった時の sys.modules に opentelemetry と viewer.src.otlp が無い（拒む道は SDK の無い環境でも走り切る）
- 対象のフォルダが無くても同じ訳で止まる（run を読む前に決める。読む方が先なら「対象のフォルダが無い」で止まる）
- 時刻の無い span（時刻が 1 つも読めない下請け・時刻の読めない往復。trace.build は始めも終わりも None で返す）は、送る前に一番近い
  時刻の在る祖先の始めと終わりで埋め、印 works_factory.time_from_ancestor を付け、埋めた数を返す。読めなかった物には足さない
  （時刻の読めない往復は会話の読みが数え済みで、足すと二重になる）。落とすと子の span が親を失う

入口は子のプロセスで、小さな包み（python3 -c）が runpy.run_path で走らせ、SystemExit の後に終了の値と sys.modules の名を 1 行で出す。
子で起こすのは、extra の在る手元で test_otlp.py が同じプロセスで先に import した物を拾わないため。SDK は要らない。
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from tests.bin import hermetic
from viewer import runtrace
from viewer.src import trace
from viewer.src import sendto

ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "viewer" / "runtrace.py"
WRAP = """
import json, runpy, sys
entry, args = sys.argv[1], sys.argv[2:]
sys.argv = [entry, *args]
code = 0
try:
    runpy.run_path(entry, run_name="__main__")
except SystemExit as stop:
    code = stop.code
print(json.dumps({"code": code, "modules": sorted(m for m in sys.modules if m.split(".")[0] == "opentelemetry" or m.endswith("otlp"))}))
"""


class EntryOrderTest(unittest.TestCase):
    def run_entry(self, *args: str, **env) -> tuple[dict, str]:
        done = subprocess.run([sys.executable, "-c", WRAP, str(ENTRY), *args], capture_output=True, text=True, cwd=ROOT,
                              env=hermetic.child_env(**env), timeout=120)
        lines = done.stdout.strip().splitlines()
        self.assertTrue(lines, done.stderr)
        return json.loads(lines[-1]), done.stderr

    def expect_refusal(self, endpoint, env, remote, *args: str, **child):
        with self.assertRaises(sendto.Refused) as caught:
            sendto.decide(endpoint, env, remote)
        got, err = self.run_entry(*args, **child)
        self.assertEqual(got["code"], 2, err)
        self.assertEqual(err.strip().splitlines(), [f"runtrace: {caught.exception}"])
        self.assertEqual(got["modules"], [])

    def test_no_endpoint_stops_before_the_sdk(self):
        self.expect_refusal(None, {}, False, "--target", str(ROOT / "no-such-target"))

    def test_a_far_endpoint_without_remote_stops_before_the_sdk(self):
        far = "http://collector.example.com:4318"
        self.expect_refusal(None, {"OTEL_EXPORTER_OTLP_ENDPOINT": far}, False, "--target", str(ROOT / "no-such-target"),
                            OTEL_EXPORTER_OTLP_ENDPOINT=far)


class TimelessTest(unittest.TestCase):
    def test_timeless_spans_take_the_nearest_timed_ancestor(self):
        def span(ident, parent, start=None, end=None):
            return {"id": ident, "parent": parent, "name": ident, "start": start, "end": end, "attributes": {}}

        built = {"trace_id": "t", "unread": {"x": 1}, "spans": [
            span("run", None, "2026-11-04T01:00:00.000Z", "2026-11-04T02:00:00.000Z"),
            span("tool", "run", "2026-11-04T01:10:00.000Z", "2026-11-04T01:10:01.000Z"),
            span("turn", "agent", "2026-11-04T01:12:00.000Z", "2026-11-04T01:13:00.000Z"),
            span("agent", "tool"), span("lost", "agent")]}
        self.assertEqual(runtrace.timed(built), 2)
        got = {s["id"]: s for s in built["spans"]}
        for ident in ("agent", "lost"):
            self.assertEqual((got[ident]["start"], got[ident]["end"]), ("2026-11-04T01:10:00.000Z", "2026-11-04T01:10:01.000Z"))
            self.assertIs(got[ident]["attributes"][trace.TIME_FROM_ANCESTOR], True)
        self.assertEqual(got["turn"]["start"], "2026-11-04T01:12:00.000Z")
        self.assertNotIn(trace.TIME_FROM_ANCESTOR, got["turn"]["attributes"])
        self.assertEqual(built["unread"], {"x": 1})


if __name__ == "__main__":
    unittest.main()

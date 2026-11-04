"""入口 viewer/runtrace.py は、送り先の決め（src/sendto.py）を通ってから OpenTelemetry の SDK を読む（viewer/AGENTS.md の E25 の 2・
docs/design/viewer.md の 8.1 の入口の順）。

- 送り先が無い時と、手元でない送り先で --remote が無い時は、run を読まずに sendto の拒む訳の 1 行を出し、終了の値 2 で止まる
- 止まった時の sys.modules に opentelemetry と viewer.src.otlp が無い（拒む道は SDK の無い環境でも走り切る）
- 対象のフォルダが無くても同じ訳で止まる（run を読む前に決める。読む方が先なら「対象のフォルダが無い」で止まる）

入口は子のプロセスで、小さな包み（python3 -c）が runpy.run_path で走らせ、SystemExit の後に終了の値と sys.modules の名を 1 行で出す。
子で起こすのは、extra の在る手元で test_otlp.py が同じプロセスで先に import した物を拾わないため。SDK は要らない。
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from tests.bin import hermetic
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


if __name__ == "__main__":
    unittest.main()

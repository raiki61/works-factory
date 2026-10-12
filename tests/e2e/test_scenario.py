"""筋書き harness/runtime.scenario.json の形の試験。止めた Archon の archon-verify-runtime が読める形か、人の読む要約
harness/END-TO-END.md の節が主張と同じ順か、線を起こす命令が段 1 の計画の文書と同じ 1 つの形で、切り離さずに前で打つ形か。"""
import json
import pathlib
import re
import subprocess
import sys
import unittest

from tests import archon
from tests.bin import hermetic

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "harness" / "runtime.scenario.json"
END_TO_END = ROOT / "harness" / "END-TO-END.md"
PLAN = ROOT / "docs" / "plans" / "2026-10-13-stage1-walking-skeleton.md"
READ_SCENARIO = pathlib.Path(".archon", "workflows", "sdlc", "verify-runtime", "scripts", "read-scenario.py")
ASSERTIONS = ["request-to-report", "every-block-ran", "capabilities-evidenced", "changed-diff-refused",
              "sealed-diff-fixes-seed"]
LAUNCH = re.compile(r"`(WORKS_FACTORY_HOME=<家> \./bin/works-factory workflow run works-factory-line [^`]*)`")


class ScenarioCase(unittest.TestCase):
    def test_verify_runtime_reads_the_scenario(self):
        done = subprocess.run([sys.executable, str(archon.source() / READ_SCENARIO)], capture_output=True, text=True,
                              encoding="utf-8", env=hermetic.child_env(INPUTS_SCENARIO=str(SCENARIO)), timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["assertion_ids"], ASSERTIONS)

    def test_end_to_end_sections_follow_the_assertions(self):
        heads = re.findall(r"^## `([a-z0-9-]+)`", END_TO_END.read_text(encoding="utf-8"), re.M)
        ids = [a["id"] for a in json.loads(SCENARIO.read_text(encoding="utf-8"))["assertions"]]
        self.assertEqual(heads, ids)

    def test_plan_and_scenario_launch_the_line_the_same_way_in_the_foreground(self):
        """線は interactive: true なので、止めた Archon は切り離した新しい起こし（workflow run --detach）を拒む（#187）"""
        plan = LAUNCH.findall(PLAN.read_text(encoding="utf-8"))
        scenario = LAUNCH.findall(SCENARIO.read_text(encoding="utf-8"))
        self.assertEqual(len(plan), 1, plan)
        self.assertEqual(scenario, plan)
        self.assertNotIn("--detach", plan[0])
        self.assertNotIn("--json", plan[0])


if __name__ == "__main__":
    unittest.main()

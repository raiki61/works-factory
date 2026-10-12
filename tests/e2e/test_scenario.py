"""筋書き harness/runtime.scenario.json の形の試験。止めた Archon の archon-verify-runtime が読める形か、人の読む要約
harness/END-TO-END.md の節が主張と同じ順か、殻の命令が段 1 の計画の文書と同じ 1 つの形か（線は切り離さずに前で起こし、関所の答えは
切り離す）、every-block-ran が名指す節が線とブロックの YAML に在るか。"""
import json
import pathlib
import re
import subprocess
import sys
import unittest

from tests import archon
from tests.bin import hermetic, stepnames

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "harness" / "runtime.scenario.json"
END_TO_END = ROOT / "harness" / "END-TO-END.md"
PLAN = ROOT / "docs" / "plans" / "2026-10-13-stage1-walking-skeleton.md"
READ_SCENARIO = pathlib.Path(".archon", "workflows", "sdlc", "verify-runtime", "scripts", "read-scenario.py")
ASSERTIONS = ["request-to-report", "every-block-ran", "capabilities-evidenced", "changed-diff-refused",
              "sealed-diff-fixes-seed"]
COMMAND = re.compile(r"`(WORKS_FACTORY_HOME=<家> \./bin/works-factory workflow (\S+) [^`]*)`")
# 計画の文書と筋書きが同じ字で持つ命令の動詞（起こす・待つ・関所に答える）
SHARED_VERBS = ("run", "wait", "respond")


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

    def test_plan_and_scenario_drive_the_line_with_the_same_commands(self):
        """線は interactive: true なので、止めた Archon は切り離した新しい起こし（workflow run --detach）を拒む（#187）。関所の答えは
        続きなので切り離せ、切り離さないと答えた後の run の続きが道具の 1 回の呼び出しの中で走る"""
        plan = commands(PLAN.read_text(encoding="utf-8"))
        scenario = commands(SCENARIO.read_text(encoding="utf-8"))
        self.assertEqual(sorted(plan), sorted(SHARED_VERBS), plan)
        self.assertEqual(scenario, plan)
        (launch,) = plan["run"]
        self.assertIn(" works-factory-line ", launch)
        self.assertNotIn("--detach", launch)
        self.assertNotIn("--json", launch)
        for respond in plan["respond"]:
            self.assertIn("--detach", respond)

    def test_every_block_ran_names_the_nodes_the_workflows_have(self):
        includes = {n["id"] for n in stepnames.walk(stepnames.nodes("works-factory-line")) if "include" in n}
        roles = {f"eyes__{n['id']}" for n in stepnames.nodes("works-factory-eyes")
                 if "command" in n and re.match(r"r\d-", n["id"])}
        child = stepnames.step_names("works-factory-fix")
        scenario = {a["id"]: a["description"] for a in json.loads(SCENARIO.read_text(encoding="utf-8"))["assertions"]}
        plan = next(line for line in PLAN.read_text(encoding="utf-8").splitlines() if line.startswith("  2. `every-block-ran`"))
        for name, text in (("scenario", scenario["every-block-ran"]), ("plan", plan.replace("`", ""))):
            with self.subTest(text=name):
                listed = named(r"線の include の id は ([^。]+)。", text) + named(r"案の直しの道の include（([^）]+)）", text)
                listed += named(r"直す物の無い周の include（([^）]+)）", text)
                self.assertEqual(sorted(listed), sorted(includes))
                self.assertEqual(set(named(r"eyes の R1〜R4 の役の節（([^）]+)）", text)), roles)
                fixers = named(r"修正の役の節（([^）]+)）", text)
                self.assertTrue(fixers)
                self.assertLessEqual(set(fixers), child)


def commands(text: str) -> dict[str, list[str]]:
    """text の中の殻の命令（`` で囲んだ物）のうち SHARED_VERBS の物を、動詞ごとに出た順で"""
    found = {}
    for command, verb in COMMAND.findall(text):
        if verb in SHARED_VERBS:
            found.setdefault(verb, []).append(command)
    return found


def named(pattern: str, text: str) -> list[str]:
    """text で pattern の最初の組に当たった「・」区切りの並び（当たらなければ空）"""
    found = re.search(pattern, text)
    return found.group(1).split("・") if found else []


if __name__ == "__main__":
    unittest.main()

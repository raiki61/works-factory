"""筋書き tests/e2e/scenario.json の形の試験。人の読む要約 tests/e2e/scenario.md の節が主張と同じ順か、殻の命令が
段 1 の計画の文書と同じ 1 つの形か（線は切り離さずに前で起こし、関所の答えは切り離す）、every-block-ran が名指す節が線と
ブロックの YAML に在るか。"""
import json
import pathlib
import re
import unittest

from tests.bin import stepnames

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "tests" / "e2e" / "scenario.json"
SUMMARY = ROOT / "tests" / "e2e" / "scenario.md"
PLAN = ROOT / "docs" / "plans" / "2026-10-13-stage1-walking-skeleton.md"
COMMAND = re.compile(r"`(WORKS_FACTORY_HOME=<家> \./bin/works-factory workflow (\S+) [^`]*)`")
# 計画の文書と筋書きが同じ字で持つ命令の動詞（起こす・待つ・関所に答える）
SHARED_VERBS = ("run", "wait", "respond")


class ScenarioCase(unittest.TestCase):
    def test_summary_sections_follow_the_assertions(self):
        heads = re.findall(r"^## `([a-z0-9-]+)`", SUMMARY.read_text(encoding="utf-8"), re.M)
        ids = [a["id"] for a in json.loads(SCENARIO.read_text(encoding="utf-8"))["assertions"]]
        self.assertEqual(heads, ids)

    def test_plan_and_scenario_drive_the_line_with_the_same_commands(self):
        """d97d00ef の Archon は interactive の線の切り離した新しい起こし（workflow run --detach）を拒んだ（#187）。355f1867 で
        切り離して起こす形はまだ実測していないので、線は前で起こす。関所の答えは続きなので切り離せ、切り離さないと答えた後の
        run の続きが道具の 1 回の呼び出しの中で走る"""
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
        eyes = {n["id"]: n for n in stepnames.walk(stepnames.nodes("works-factory-eyes"))}
        roles = {f"eyes__{step}" for step in stepnames.step_names("works-factory-eyes")
                 if "command" in eyes[step.rsplit(".", 1)[-1]] and re.match(r"r\d-", step.rsplit(".", 1)[-1])}
        child = stepnames.step_names("works-factory-fix")
        scenario = {a["id"]: a["description"] for a in json.loads(SCENARIO.read_text(encoding="utf-8"))["assertions"]}
        plan = next(line for line in PLAN.read_text(encoding="utf-8").splitlines() if line.startswith("  2. `every-block-ran`"))
        for name, text in (("scenario", scenario["every-block-ran"]), ("plan", plan.replace("`", ""))):
            with self.subTest(text=name):
                listed = named(r"線の include の id は ([^。]+)。", text) + named(r"案の直しの道の include（([^）]+)）", text)
                listed += named(r"条件で回る include（([^。）]+)。", text)
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

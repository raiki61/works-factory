"""run の中の確かめの命令と全部の試験の命令を、役が取り違えないように書いてある（tests/AGENTS.md。持ち主の決め full-suite-in-ci）。

run の中の役は決まりの文書から確かめの全体の命令を探す。そこに書いた run の中の命令は harness/harness.config.json の unit と
同じ字で、全部の試験の命令は tests/AGENTS.md の CI の行にだけ在る。読み方そのものは人が見る。
"""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
RULES = ROOT / "tests" / "AGENTS.md"
FULL = "python3 -m unittest discover"
# 役が確かめの命令を探す決まりの文書（AGENTS.md は全部の階層）
GUIDES = ("README.md", "engineering.md", "MISSION.md", "pyproject.toml")


def unit_command() -> str:
    return json.loads((ROOT / "harness" / "harness.config.json").read_text(encoding="utf-8"))["unit"]


def full_suite_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if FULL in line]


class TestCommandsTest(unittest.TestCase):
    def test_rules_name_the_unit_command_first(self):
        text = RULES.read_text(encoding="utf-8")
        self.assertIn(f"`{unit_command()}`", text)
        self.assertLess(text.index(unit_command()), text.index(FULL))

    def test_full_suite_is_written_only_as_the_ci_command(self):
        lines = full_suite_lines(RULES.read_text(encoding="utf-8"))
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("CI が回す物", lines[0])
        self.assertIn("回さない", lines[0])

    def test_no_other_guide_names_the_full_suite(self):
        guides = [p for p in ROOT.rglob("AGENTS.md") if p != RULES and ".git" not in p.parts]
        guides += [ROOT / name for name in GUIDES if (ROOT / name).exists()]
        found = {p.relative_to(ROOT).as_posix(): full_suite_lines(p.read_text(encoding="utf-8")) for p in guides}
        self.assertEqual({path: lines for path, lines in found.items() if lines}, {})


if __name__ == "__main__":
    unittest.main()

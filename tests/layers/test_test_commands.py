"""run の中の確かめの命令と全部の試験の命令を、役が取り違えないように書いてある（tests/AGENTS.md。持ち主の決め full-suite-in-ci）。

run の中の役は決まりの文書から確かめの全体の命令を探す。そこに書いた run の中の命令は UNIT が先に在り、
全部の試験の命令は tests/AGENTS.md の CI の行にだけ在る。読み方そのものは人が見る。
"""
import pathlib
import unittest

from tests.layers.test_words import guides

ROOT = pathlib.Path(__file__).resolve().parents[2]
RULES = ROOT / "tests" / "AGENTS.md"
UNIT = "uv run --isolated python3 tests/changed.py"
FULL = "python3 -m unittest discover"


def full_suite_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if FULL in line]


class TestCommandsTest(unittest.TestCase):
    def test_rules_name_the_unit_command_first(self):
        text = RULES.read_text(encoding="utf-8")
        self.assertIn(f"`{UNIT}`", text)
        self.assertLess(text.index(UNIT), text.index(FULL))

    def test_full_suite_is_written_only_as_the_ci_command(self):
        lines = full_suite_lines(RULES.read_text(encoding="utf-8"))
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("CI が回す物", lines[0])
        self.assertIn("回さない", lines[0])

    def test_no_other_guide_names_the_full_suite(self):
        read = [p for p in guides(ROOT) if p != RULES] + [ROOT / "pyproject.toml"]
        found = {p.relative_to(ROOT).as_posix(): full_suite_lines(p.read_text(encoding="utf-8")) for p in read}
        self.assertEqual({path: lines for path, lines in found.items() if lines}, {})


if __name__ == "__main__":
    unittest.main()

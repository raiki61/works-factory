"""run の中の確かめの命令と全部の試験の命令を、役が取り違えないように書いてある（`tests/AGENTS.md`。持ち主の決め `full-suite-in-ci`）。

- `tests/AGENTS.md` に run の中の命令 `uv run --isolated python3 tests/changed.py`（試験の中の定数 `UNIT`）が、全部の試験の命令より先に在る。
- 全部の試験の命令（`python3 -m unittest discover`）は `tests/AGENTS.md` の CI の行にだけ在り、その行は「CI が回す物」と「回さない」を持つ。ほかの決まりの文書（全部の階層の `AGENTS.md`・根の `README.md`・`MISSION.md`・`engineering.md`）と `pyproject.toml` には無い。
- どちらが run の中の命令と読めるか（読み方そのもの）は人が見る。
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

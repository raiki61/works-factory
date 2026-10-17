"""借りたスキルの座（lib/seat.py）の試験。元 works の tests/test_sp_skills.py のうち座と下請けの所を、置き場の写しで回す。
"""
import pathlib
import sys
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import seat  # noqa: E402

IMPL = {"[task name]": "直す義務の単位 1 件", "[BRIEF_FILE]": "/p/brief.md",
        "[Scene-setting: where this fits, dependencies, architectural context]": seat.SCENE, "[directory]": "/repo",
        "[REPORT_FILE]": seat.NO_REPORT_FILE}
REVIEW = {"[BRIEF_FILE]": "/p/brief.md", "[GLOBAL_CONSTRAINTS]": seat.NONE, "[REPORT_FILE]": seat.G1_REPORT,
          "[BASE_SHA]": "abc123", "[HEAD_SHA]": seat.G1_HEAD_SHA, "[DIFF_FILE]": "/p/g1-1.patch"}


class SeatCase(unittest.TestCase):
    def test_fill_names_missing_holes(self):
        self.assertIn("task-reviewer-prompt.md", seat.section("review", REVIEW))
        with self.assertRaises(ValueError):
            seat.fill("implementer", {k: v for k, v in IMPL.items() if k != "[directory]"})

    def test_sections_of_each_seat(self):
        overlay = (seat.spseam.BORROW_DIR / seat.spseam.OVERLAY_FILE).read_text(encoding="utf-8").strip()
        for node in seat.SKILL_NODES:
            text = seat.section(node)
            self.assertIn(seat.SKILL_LEAD.split("`")[0], text, node)
            self.assertTrue(text.rstrip().endswith(overlay), node)
        fix = seat.section("fix", IMPL)
        self.assertIn(seat.DIVERGENCE_HINT, fix)
        review = seat.section("review", REVIEW)
        self.assertIn(str(seat.WORDS_HEAD), review)
        self.assertIn(seat.WINS_OF["review"], review)
        self.assertEqual(seat.section("review2", REVIEW), "")
        with self.assertRaises(ValueError):
            seat.section("fix")

    def test_g1_files_carry_the_works_rules_and_the_query_rule(self):
        text = seat.g1_prompt("task-review", REVIEW)
        self.assertNotIn(f"abc123..{seat.G1_HEAD_SHA}", text, "作業ツリーとの差分に直す")
        self.assertIn(str(seat.G1_SUB_HEAD), text)
        self.assertIn(seat.query_rule(), text)
        section = seat.g1_section([{"item": 1, "impl_file": "/p/i.md", "review_file": "/p/r.md", "base": "abc123",
                                    "patch": "/p/g1 1.patch"}])
        self.assertIn(str(seat.G1_HEAD), section)
        self.assertIn("'/p/g1 1.patch'", section)

    def test_copy_that_differs_from_the_pin_is_named(self):
        with mock.patch.object(seat.spseam, "_sha", return_value="0" * 64):
            with self.assertRaises(ValueError) as e:
                seat.section("tdd")
        self.assertIn("固定", str(e.exception))


if __name__ == "__main__":
    unittest.main()

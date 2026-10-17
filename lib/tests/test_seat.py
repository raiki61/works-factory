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
        for node in seat.SKILL_NODES:
            text = seat.section(node)
            self.assertIn(seat.SKILL_LEAD.split("`")[0], text, node)
            self.assertTrue(text.rstrip().endswith(seat.overlay_body(seat.OVERLAY_KINDS[node]).strip()), node)
        fix = seat.section("fix", IMPL)
        self.assertIn(seat.DIVERGENCE_HINT, fix)
        review = seat.section("review", REVIEW)
        self.assertIn(str(seat.WORDS_HEAD), review)
        self.assertIn(seat.WINS_OF["review"], review)
        self.assertEqual(seat.section("review2", REVIEW), "")
        with self.assertRaises(ValueError):
            seat.section("fix")

    def test_each_role_gets_only_its_declared_kinds(self):
        """読み替えは、役が宣言した種類の節と共通の文だけを載せる（局所レビューの役に修正・手直し・審査の役の節は載らない）"""
        full = (seat.spseam.BORROW_DIR / seat.spseam.OVERLAY_FILE).read_text(encoding="utf-8")
        heads = {line.removeprefix("### ") for line in full.splitlines() if line.startswith("### ")}
        self.assertEqual({k for h in heads for k in h.split("・")}, set(seat.KINDS), "種類の見出しは KINDS の名だけで、どの種類も使う")
        self.assertLessEqual(set(seat.SEATS), set(seat.OVERLAY_KINDS), "座の載る役はどれも種類を宣言する")
        for node, kinds in seat.OVERLAY_KINDS.items():
            with self.subTest(node=node):
                text = seat.overlay_body(kinds)
                got = {line.removeprefix("### ") for line in text.splitlines() if line.startswith("### ")}
                self.assertEqual(got, {h for h in heads if set(h.split("・")) & set(kinds)})
                self.assertIn("## COMMIT ", text, "共通の文は載る")
        local = seat.overlay_body(seat.OVERLAY_KINDS["local-review"])
        for other in (seat.FIX, seat.TDD, seat.REFIX, seat.REVIEW):
            self.assertNotIn(other, local)
        self.assertNotIn("## 義務の単位の行き先", local, "種類の節が全部落ちた決まりは見出しごと落ちる")
        self.assertTrue(seat.skill_overlay("fix").endswith(seat.overlay_body((seat.FIX,))))

    def test_unknown_kind_heading_is_named(self):
        with mock.patch.object(pathlib.Path, "read_text", return_value="# t\n\n## A x\n\n### 知らない役\n\n文\n"):
            with self.assertRaises(ValueError) as e:
                seat.overlay_body((seat.FIX,))
        self.assertIn("知らない役", str(e.exception))

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

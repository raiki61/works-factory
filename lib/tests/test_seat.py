"""借りたスキルの座（lib/seat.py）の試験。元 works の tests/test_sp_skills.py のうち座の所を、置き場の写しで回す（座の文と下請けの
指示の組み立ては fix・delta-review の md へ移った。integration.md 4.3-13）。
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
        "[Scene-setting: where this fits, dependencies, architectural context]": "works の修正の段", "[directory]": "/repo",
        "[REPORT_FILE]": "ファイルに書かない"}
REVIEW = {"[BRIEF_FILE]": "/p/brief.md", "[GLOBAL_CONSTRAINTS]": seat.NONE, "[REPORT_FILE]": "実装役の最後のメッセージ",
          "[BASE_SHA]": "abc123", "[HEAD_SHA]": "作業ツリー", "[DIFF_FILE]": "/p/g1-1.patch"}


class SeatCase(unittest.TestCase):
    def test_fill_names_missing_holes(self):
        self.assertIn("/p/g1-1.patch", seat.fill("task-review", REVIEW))
        self.assertIn("/repo", seat.fill("implementer", IMPL))
        with self.assertRaises(ValueError):
            seat.fill("implementer", {k: v for k, v in IMPL.items() if k != "[directory]"})

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

    def test_copy_that_differs_from_the_pin_is_named(self):
        with mock.patch.object(seat.spseam, "_sha", return_value="0" * 64):
            with self.assertRaises(ValueError) as e:
                seat.pinned()
        self.assertIn("固定", str(e.exception))


if __name__ == "__main__":
    unittest.main()

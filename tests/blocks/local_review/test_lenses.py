"""レンズの宣言と照らし blocks/local-review/src/lenses.py（写す元 lib/tests/test_diverted.py。README の 9.5 で local-review へ移す物）"""
import unittest

from tests.blocks import kit

ITEM2 = {"where": "deploy/values.yaml:174", "text": "常設環境に漏れる"}
LOST = "起こしたが fork 実行の結果が本文なし（Skill execution completed のみ）で、所見を受け取れなかった。"


class LensesCase(unittest.TestCase):
    def setUp(self):
        self.lenses = kit.load("local-review", "lenses")
        self.skills = self.lenses.skills()

    def reply(self, code_review_items=(), failed=LOST, status="clean"):
        rows = [{"skill": e["skill"], "items": [], "invoked": True, "failed": "起こしたが所見なし（差分を見た）"} for e in self.skills]
        rows[0].update(items=list(code_review_items), failed=failed)
        material = {"status": status, "checked": "差分を見た"} if status == "clean" else \
            {"status": status, "count": 3, "detail": "code-reviewer が 3 件"}
        return {"material": material, "simplify_carried": False, "findings": rows}

    def test_empty_fork_lens_row_is_marked_unseen_not_nothing_found(self):
        for failed in (LOST, "起こしたが所見なし（スキルは結果本文を返さずに完了）"):
            with self.subTest(failed):
                out, notes = self.lenses.mark_unseen(self.reply(failed=failed), self.skills)
                row = out["findings"][0]
                self.assertTrue(row["failed"].startswith(self.lenses.UNSEEN_TAG), row)
                self.assertIn(failed, row["failed"], "役の文は残す")
                self.assertEqual(notes, {"unseen": ["/code-review"]})
                self.assertEqual(self.lenses.unseen(out), ["/code-review"])
                self.assertIn(self.lenses.UNSEEN_TAG, out["material"]["checked"])
        given = self.reply()
        self.lenses.mark_unseen(given, self.skills)
        self.assertEqual(given, self.reply(), "受けた返答は書き換えない（写しを返す）")

    def test_rows_with_items_and_inline_lenses_are_left_alone(self):
        out, notes = self.lenses.mark_unseen(self.reply(code_review_items=[ITEM2], failed=""), self.skills)
        self.assertEqual(out["findings"][0]["items"], [ITEM2], "役が受け取った本文を差し替えない")
        self.assertEqual(out["findings"][2]["failed"], "起こしたが所見なし（差分を見た）", "/simplify は fork しない（0 件は 0 件）")
        self.assertEqual((notes, self.lenses.unseen(out)), ({"unseen": []}, []))

    def test_not_invoked_row_is_not_marked(self):
        r = self.reply()
        r["findings"][0]["invoked"] = False
        out, notes = self.lenses.mark_unseen(r, self.skills)
        self.assertEqual(out["findings"][0]["failed"], LOST)
        self.assertEqual(notes, {"unseen": []})

    def test_report_lines(self):
        self.assertEqual(self.lenses.unseen_lines(["/code-review"]),
                         ["局所レビューの /code-review: 所見を受け取れていない（fork の返答が届かなかった）——見ていないのと同じ"])
        self.assertEqual(self.lenses.unseen_lines([]), [])

    def test_declaration_and_condition(self):
        self.assertEqual([e["skill"] for e in self.lenses.LENSES],
                         ["/code-review", "pr-review-toolkit:code-reviewer", "/simplify", "/security-review",
                          "pr-review-toolkit:silent-failure-hunter", "pr-review-toolkit:type-design-analyzer",
                          "pr-review-toolkit:pr-test-analyzer"])
        self.assertEqual(list(self.lenses.LENSES), [
            {"skill": "/code-review", "args": "high", "required": True},
            {"skill": "pr-review-toolkit:code-reviewer", "required": True},
            {"skill": "/simplify", "required": True},
            {"skill": "/security-review", "required": False, "applies_cond": "security_surface_touched"},
            {"skill": "pr-review-toolkit:silent-failure-hunter", "required": True},
            {"skill": "pr-review-toolkit:type-design-analyzer", "required": True},
            {"skill": "pr-review-toolkit:pr-test-analyzer", "required": True}])
        self.assertFalse(any("note" in e for e in self.skills))
        sec = self.skills[3]
        self.assertEqual((sec["applies"], sec["applies_why"]), (True, self.lenses.SECURITY_WHY))
        self.assertEqual([e for e in self.skills if "applies" in e], [sec], "条件を持つのは /security-review だけ")
        with self.assertRaises(ValueError):
            self.lenses.applies("no_such_cond")
        self.assertEqual(self.lenses.LENS_FILE, "lenses.json")


if __name__ == "__main__":
    unittest.main()

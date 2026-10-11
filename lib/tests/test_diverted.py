"""局所レビューの fork のレンズ（/code-review）の所見が届かなかった空の行を「見ていない」と書く口（.shared/core/diverted.py）と、
局所レビューの受け付け（blk-material の take）がそれを盤面と報告に渡す振る舞いの検査（FAST: 一時の置き場のファイルだけ。git・盤面の
再生を使わない）。

実測（2026-10-08、利用者の run f57a5374 ほか 6 つの works の家）: 組み込みの skill code-review は fork（下請けの会話）で走り、
返答の道具 StructuredOutput を継いだ fork は所見をそこに書いて終わった。Skill の結果は『Skill execution completed』だけになり、
局所レビューの役は /code-review の行を items 空で返していた（run f57a5374 では 10 件の所見が消えた）。今は旗 text-reply で
fork に返答の道具が無いが、空の行は「所見なし」でなく「見ていない」と書く。0.2.46 の拾い戻し（record-output.py のフックと
diverted.recover）は 2026-10-09 の掃除で外した。
"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import diverted  # noqa: E402

LENSES = [{"skill": "/code-review", "required": True}, {"skill": "pr-review-toolkit:code-reviewer", "required": True},
          {"skill": "/simplify", "required": True},
          {"skill": "/security-review", "required": False, "applies_cond": "security_surface_touched"}]
ITEM2 = {"where": "deploy/values.yaml:174", "text": "常設環境に漏れる"}
LOST = "起こしたが fork 実行の結果が本文なし（Skill execution completed のみ）で、所見を受け取れなかった。"


def reply(code_review_items=(), failed=LOST, status="clean"):
    rows = [{"skill": e["skill"], "items": [], "invoked": True, "failed": "起こしたが所見なし（差分を見た）"} for e in LENSES]
    rows[0].update(items=list(code_review_items), failed=failed)
    material_ = {"status": status, "checked": "差分を見た"} if status == "clean" else \
        {"status": status, "count": 3, "detail": "code-reviewer が 3 件"}
    return {"material": material_, "simplify_carried": False, "findings": rows}


class UnseenCase(unittest.TestCase):
    def test_empty_fork_lens_row_is_marked_unseen_not_nothing_found(self):
        for failed in (LOST, "起こしたが所見なし（スキルは結果本文を返さずに完了）"):
            with self.subTest(failed):
                out, notes = diverted.mark_unseen(reply(failed=failed), LENSES)
                row = out["findings"][0]
                self.assertTrue(row["failed"].startswith(diverted.UNSEEN_TAG), row)
                self.assertIn(failed, row["failed"], "役の文は残す")
                self.assertEqual(notes, {"unseen": ["/code-review"]})
                self.assertIn(diverted.UNSEEN_TAG, out["material"]["checked"])
        given = reply()
        diverted.mark_unseen(given, LENSES)
        self.assertEqual(given, reply(), "受けた返答は書き換えない（写しを返す）")

    def test_rows_with_items_and_inline_lenses_are_left_alone(self):
        out, notes = diverted.mark_unseen(reply(code_review_items=[ITEM2], failed=""), LENSES)
        self.assertEqual(out["findings"][0]["items"], [ITEM2], "役が受け取った本文を差し替えない")
        self.assertEqual(out["findings"][2]["failed"], "起こしたが所見なし（差分を見た）", "/simplify は fork しない（0 件は 0 件）")
        self.assertEqual(notes, {"unseen": []})

    def test_not_invoked_row_is_not_marked(self):
        r = reply()
        r["findings"][0]["invoked"] = False
        out, notes = diverted.mark_unseen(r, LENSES)
        self.assertEqual(out["findings"][0]["failed"], LOST)
        self.assertEqual(notes, {"unseen": []})


if __name__ == "__main__":
    unittest.main()

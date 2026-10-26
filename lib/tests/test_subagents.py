"""下請け（書き手が項目ごとに起こす実装役と審査役）の値の関数（lib/subagents.py）の試験。docs/plans/2026-10-24-fix-weapons.md の 11.6 の D2 の
縛る試験のうち「項目ごとに 2 つのファイル・審査役の型の <base>..<head> の直し・brief の無い run の残りの単位の項目」の、値の関数の側。
ファイルを place に書いて md を組む本体は tests/blocks/shared/test_writerblock.py。lib は実行環境を知らない（E3）ので、md を組んだ字は引数で渡す。
"""
import pathlib
import sys
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import planbrief  # noqa: E402
import seat  # noqa: E402
import subagents  # noqa: E402

A, B = "stats.py:4 mean", "bounds.py:2 clamp"
TEXTS = {"scene": "SCENE", "impl_report": "IMPL-REPORT", "report": "REPORT", "head_sha": "WORKTREE"}


def sub(**kw) -> dict:
    """slots の subagents の形（.shared/schemas/writer-slots.schema.json）。既定は brief の無い run で、単位 A が 1 つ"""
    return {"owed": [A], "briefs": [], "all_items": [], "seat_brief_rows": "", "judgment_file": "/p/judgment.json", "policy_path": "",
            "base_rev": "abc123", "check_cmd": "", "directory": "/repo", **kw}


def rest(key: str) -> str:
    return f"REST {key}"


class ItemsCase(unittest.TestCase):
    def test_a_run_without_briefs_has_one_item_per_owed_unit_numbered_from_one(self):
        """brief の無い run は、直す義務の単位ごとに判定のファイルを brief にした 1 単位 1 項目（題は呼び手が組んだ字）"""
        got = subagents.items(sub(owed=[A, B]), rest)
        self.assertEqual(got, [(1, "/p/judgment.json", f"REST {A}"), (2, "/p/judgment.json", f"REST {B}")])

    def test_the_items_of_the_plan_come_first_and_the_units_the_plan_leaves_out_follow_after_the_last_item(self):
        """案の項目は brief の行ごとに 1 つ（題は項目の番号と、今直す単位）。案のどの項目にも無い単位は、凍結した項目の最大の次から振る"""
        briefs = [{"item": 1, "file": "/b/brief-1.md", "unit_keys": [A]}]
        got = subagents.items(sub(owed=[A, B], briefs=briefs, all_items=[1, 3]), rest)
        self.assertEqual(got[0], (1, "/b/brief-1.md", f"修正案の項目 1（直す義務の単位 {A}）"))
        self.assertEqual(got[1], (4, "/p/judgment.json", f"REST {B}"), "最大の項目 3 の次")

    def test_a_unit_of_the_item_that_is_not_owed_now_is_marked(self):
        """項目の単位のうち今の注文に無い物は『今は直すな』と添える（P1。1 つの項目の単位が 2 つの型に分かれる時の守り）"""
        briefs = [{"item": 2, "file": "/b/brief-2.md", "unit_keys": [A, B]}]
        [(_, _, task)] = subagents.items(sub(owed=[A], briefs=briefs, all_items=[2]), rest)
        self.assertEqual(task, f"修正案の項目 2（直す義務の単位 {planbrief.unit_note([A, B], [A])}）")
        self.assertIn(f"{planbrief.NOT_NOW}: {B}", task)


class EntriesCase(unittest.TestCase):
    def entries(self, place="/place", **kw):
        return subagents.entries(place, sub(**kw), rest_title=rest, **TEXTS)

    def test_each_item_has_two_files_and_a_patch_file_in_the_place(self):
        [one] = self.entries("/place")
        self.assertEqual((one["item"], one["impl_file"], one["review_file"], one["patch"], one["base"]),
                         (1, "/place/g1-impl-1.md", "/place/g1-review-1.md", "/place/g1-1.patch", "abc123"))

    def test_the_implementer_template_is_the_borrowed_one_with_the_holes_filled(self):
        """実装役の型の穴: その項目の brief・題・報告のファイル（呼び手の字）・場面（呼び手の字）・作業ツリーの根"""
        [one] = self.entries(judgment_file="/p/judgment.json", directory="/repo")
        text = one["impl_template"]
        for want in ("/p/judgment.json", f"REST {A}", "IMPL-REPORT", "SCENE", "/repo"):
            self.assertIn(want, text)
        self.assertFalse(text.endswith("\n"), "呼び手が md に入れる字は前後の改行を外してある")

    def test_the_reviewer_template_reads_the_diff_against_the_base_and_not_a_commit_range(self):
        """審査役の型の `<base>..<head>` は `<base>` に直す（works は commit しないので、commit の範囲は空になる）。差分のファイルと
        修正前の版・[HEAD_SHA] の字は型の穴に入る"""
        [one] = self.entries()
        raw = seat.fill("task-review", {"[BRIEF_FILE]": "/p/judgment.json", "[GLOBAL_CONSTRAINTS]": seat.NONE, "[REPORT_FILE]": "REPORT",
                                        "[BASE_SHA]": "abc123", "[HEAD_SHA]": "WORKTREE", "[DIFF_FILE]": "/place/g1-1.patch"}).rstrip("\n")
        self.assertIn("abc123..WORKTREE", raw, "借りた型の元の字には範囲が在る（直す前提の確かめ）")
        text = one["review_template"]
        self.assertNotIn("abc123..WORKTREE", text)
        self.assertIn("/place/g1-1.patch", text)
        self.assertEqual(text, raw.replace("abc123..WORKTREE", "abc123"))

    def test_the_policy_document_is_the_constraint_of_the_reviewer_or_none(self):
        self.assertIn(seat.NONE, self.entries(policy_path="")[0]["review_template"])
        text = self.entries(policy_path="/p/policy.md")[0]["review_template"]
        self.assertIn("/p/policy.md", text)

    def test_every_item_gets_its_own_files(self):
        briefs = [{"item": 1, "file": "/b/brief-1.md", "unit_keys": [A]}]
        got = self.entries(owed=[A, B], briefs=briefs, all_items=[1])
        self.assertEqual([(e["item"], e["impl_file"], e["patch"]) for e in got],
                         [(1, "/place/g1-impl-1.md", "/place/g1-1.patch"), (2, "/place/g1-impl-2.md", "/place/g1-2.patch")])
        self.assertIn("/b/brief-1.md", got[0]["impl_template"])
        self.assertIn(B, got[1]["impl_template"])

    def test_a_borrowed_copy_that_does_not_match_the_pin_stops(self):
        """借りた写しが固定と合わなければ ValueError（seat.fill が照らす）。黙って別の字の型で下請けを起こさない"""
        with mock.patch.object(seat.spseam, "pin_problems", return_value=["字が違う"]):
            with self.assertRaisesRegex(ValueError, "固定"):
                self.entries()


class RowCase(unittest.TestCase):
    def test_a_row_names_the_two_files_and_the_command_that_writes_the_diff(self):
        [one] = subagents.entries("/place", sub(), rest_title=rest, **TEXTS)
        row = subagents.row(one)
        self.assertTrue(row.startswith("項目 1: 実装役 /place/g1-impl-1.md・審査役 /place/g1-review-1.md・差分のコマンド `"))
        self.assertIn(subagents.diff_cmd("abc123", "/place/g1-1.patch"), row)

    def test_the_diff_command_quotes_the_patch_path_and_diffs_the_tree_against_the_base(self):
        cmd = subagents.diff_cmd("abc123", "/a b/g1-1.patch")
        self.assertIn("p='/a b/g1-1.patch'", cmd)
        self.assertIn("diff abc123 > \"$p\"", cmd)
        self.assertIn("ls-files --others --exclude-standard", cmd, "未追跡の新しいファイルも差分に入る")
        self.assertTrue(cmd.endswith('echo "$p"'))


if __name__ == "__main__":
    unittest.main()

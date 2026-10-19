"""独立の目の族の共通の部品（lib/eyekit.py）の試験（docs/design/r1.md の 8 節）。

今の lib/tests/test_eyeverdict.py の CollectCase の R1 の 3 本・FellTextCase の ran の無い 1 本・test_off_contract_status_is_named・
HumanPassedCase の行の形の半分と、tests/workflows/test_eyes.py の ScriptCase の差分と頭の場面（test_empty_diff_points_at_the_reason・
test_untaken_diff_is_unmeasured_not_zero・test_prep_diff_leaves_out_the_runtime_copy の名の試験・test_r1_head_carries_*・
test_prep_carries_the_recorded_policy_section）を、関数を直に呼ぶ形で写した。各試験の docstring に元の試験の名を書く。
"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import answer  # noqa: E402
import eyekit  # noqa: E402
import gatemarks  # noqa: E402
import policy  # noqa: E402
import seal  # noqa: E402
import structmark  # noqa: E402
from tests.bin import hermetic  # noqa: E402
from tests.bin.gitkit import git  # noqa: E402

AFTER = {"changed": ["a.txt"], "tables": [], "new_names": [{"name": "x", "sites": 2}], "dup_blocks_added": 2}
DEVIATION = {"item": 2, "row": "u2", "deviation": "入口を 2 つ残す（呼び手が別のリポジトリに在る）"}


class _Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = hermetic.tmpdir(self)


class DiffCase(_Tmp):
    def repo(self) -> pathlib.Path:
        repo = self.tmp / "repo"
        repo.mkdir()
        git(repo, "init", "-q")
        (repo / "a.txt").write_text("a\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "base")
        return repo

    def test_diff_from_the_base_includes_untracked_and_leaves_out_the_skipped_copy(self):
        """test_prep_takes_the_diff_from_the_entry_base・test_prep_diff_leaves_out_the_runtime_copy の名の試験"""
        repo = self.repo()
        base = git(repo, "rev-parse", "HEAD")
        (repo / "a.txt").write_text("b\n", encoding="utf-8")
        (repo / "new.txt").write_text("n\n", encoding="utf-8")
        (repo / "copy" / "workflows").mkdir(parents=True)
        (repo / "copy" / "workflows" / "x.yaml").write_text("name: x\n", encoding="utf-8")
        got = eyekit.take_diff(self.tmp / "place", repo, base, ("copy/",), "run.diff", "run-diff-none.txt")
        self.assertEqual(pathlib.Path(got["file"]), self.tmp / "place" / "run.diff")
        self.assertIn("-a\n+b\n", got["text"])
        self.assertNotIn("copy/", got["text"])
        self.assertEqual((got["changed"], got["why"], got["base"], got["repo"]), (["a.txt", "new.txt"], "", base, str(repo)))
        self.assertEqual(got["lines"], len(got["text"].splitlines()))
        self.assertEqual(eyekit.diff_values(got), {"diff_file": got["file"], "changed_files": "a.txt、new.txt", "base": base,
                                                   "repo": str(repo)})

    def test_empty_diff_points_at_the_reason(self):
        """test_empty_diff_points_at_the_reason: 空の差分は空の字でなく訳を書いたファイルを指す。空の base は HEAD"""
        repo = self.repo()
        got = eyekit.take_diff(self.tmp / "place", repo, "", (), "run.diff", "run-diff-none.txt")
        self.assertEqual((got["text"], got["why"], got["lines"], got["changed"], got["base"]), ("", "", 0, [], "HEAD"))
        self.assertEqual(pathlib.Path(got["file"]).name, "run-diff-none.txt")
        self.assertIn("HEAD", pathlib.Path(got["file"]).read_text(encoding="utf-8"))

    def test_untaken_diff_is_named_not_empty(self):
        """test_untaken_diff_is_unmeasured_not_zero: 引けない base は訳を残し、変更ファイルの値はその訳"""
        repo = self.repo()
        got = eyekit.take_diff(self.tmp / "place", repo, "no-such-rev", (), "run.diff", "run-diff-none.txt")
        self.assertTrue(got["why"].startswith("累積差分が取れない"), got["why"])
        self.assertIn(got["why"], pathlib.Path(got["file"]).read_text(encoding="utf-8"))
        self.assertEqual(eyekit.diff_values(got)["changed_files"], got["why"])


class MapsCase(_Tmp):
    def test_found_maps_are_listed_and_the_rest_counted(self):
        repo = self.tmp / "repo"
        repo.mkdir()
        git(repo, "init", "-q")
        names = ["docs/concepts.md", *(f"p{n}/docs/concepts.md" for n in range(6))]
        for name in names:
            (repo / name).parent.mkdir(parents=True, exist_ok=True)
            (repo / name).write_text("# map\n", encoding="utf-8")
        git(repo, "add", "-A")
        values, found = eyekit.maps(repo)
        self.assertTrue(found)
        rows = values["concept_maps"].splitlines()
        self.assertEqual(rows[0], "- docs/concepts.md")
        self.assertEqual(rows[-1], eyekit.MORE_MAPS.format(n=2))
        self.assertEqual(values["map_tail"], "")

    def test_no_map_and_an_unreadable_tree(self):
        repo = self.tmp / "repo"
        repo.mkdir()
        git(repo, "init", "-q")
        self.assertEqual(eyekit.maps(repo), ({"concept_maps": "", "map_tail": ""}, False))
        values, found = eyekit.maps(self.tmp / "not-a-repo")
        self.assertFalse(found)
        self.assertTrue(values["map_tail"].startswith(" (the tree could not be read: "), values["map_tail"])


class AfterCase(_Tmp):
    def test_no_after_file_says_so(self):
        """test_r1_head_carries_after_counts の控えが無い半分"""
        self.assertEqual(eyekit.after_section(None, {}), eyekit.NO_AFTER)
        self.assertEqual(eyekit.after_section(self.tmp / structmark.AFTER_FILE, {}), eyekit.NO_AFTER)
        self.assertEqual(eyekit.after_section(self.tmp / "other.json", {}), eyekit.AFTER_MISNAMED.format(path=self.tmp / "other.json"))
        self.assertIn("structure-after.json でない", eyekit.AFTER_MISNAMED)

    def test_counts_only_without_deviations(self):
        """test_r1_head_carries_after_counts: 外れの訳の無い run は数の 1 文だけ（事前審査の行も載せない）"""
        path = structmark.write_after(self.tmp, status="ok", reason="", after=AFTER, deviations=[])
        got = eyekit.after_section(path, {"round": 2, "verdict": "accepted"})
        self.assertEqual(got, structmark.after_counts(self.tmp))
        self.assertIn("増えた写しの塊 2 個", got)

    def test_deviations_carry_the_review_line(self):
        """test_r1_head_carries_plan_deviations_and_the_plan_review_verdict を port review の値で"""
        path = structmark.write_after(self.tmp, status="ok", reason="", after=AFTER, deviations=[DEVIATION])
        got = eyekit.after_section(path, {"round": 2, "verdict": "accepted", "blocks": [], "why": ""})
        line = "  - 修正案の項目 2・設計の行 u2から外れる——入口を 2 つ残す（呼び手が別のリポジトリに在る）"
        self.assertEqual(got, f"{structmark.after_counts(self.tmp)}\n{line}\n{eyekit.REVIEW_ACCEPTED.format(k=2)}")
        self.assertNotIn("新しい名 x", got)

    def test_review_line_has_a_line_for_every_verdict(self):
        cases = [
            ({"round": 3, "verdict": "accepted"}, eyekit.REVIEW_ACCEPTED.format(k=3)),
            ({"round": 3, "verdict": "blocked", "blocks": [{"key": "f1", "why": "入口は 1 つで足りる"}, {"key": "f2", "why": "名が長い"}]},
             eyekit.REVIEW_BLOCKED.format(k=3, n=2, faces="f1: 入口は 1 つで足りる; f2: 名が長い")),
            ({"round": 3, "verdict": "gave_up", "why": "3 回拒んだ"}, eyekit.REVIEW_GAVE_UP.format(k=3, why="3 回拒んだ")),
            ({"round": 3, "verdict": "held", "why": "held"}, eyekit.REVIEW_HELD.format(k=3, outcome="held")),
            ({"round": 3, "verdict": "design"}, eyekit.REVIEW_UNREAD.format(why=eyekit.REVIEW_NO_PLAN)),
            ({"round": 3, "verdict": "unread", "why": "往復の案が別の周"}, eyekit.REVIEW_UNREAD.format(why="往復の案が別の周")),
            ({}, eyekit.REVIEW_UNREAD.format(why=eyekit.REVIEW_NOT_GIVEN)),
            ({"round": 3, "verdict": "maybe", "why": "x"}, eyekit.REVIEW_UNREAD.format(why="結論の語が約束の外（'maybe'）")),
        ]
        for review, want in cases:
            with self.subTest(review.get("verdict")):
                self.assertEqual(eyekit.review_line(review), want)


class ReviewMdCase(_Tmp):
    def test_repo_review_md_says_when_the_target_has_none(self):
        """test_prep_pastes_the_premises_and_names_the_target_review_md の REVIEW.md の半分（r3 と r4 のまとめた形が使う）"""
        got = eyekit.review_md_values(self.tmp)
        self.assertEqual(got, {"review_md": eyekit.review_md(self.tmp)[0], "repo_review_md": eyekit.NO_REPO_REVIEW_MD})
        (self.tmp / "REVIEW.md").write_text("# 観点\n", encoding="utf-8")
        self.assertEqual(pathlib.Path(eyekit.review_md_values(self.tmp)["repo_review_md"]), (self.tmp / "REVIEW.md").resolve())
        self.assertTrue(pathlib.Path(eyekit.review_md_values(self.tmp)["review_md"]).is_file())


class HumanItemsCase(unittest.TestCase):
    def test_rows_keep_the_record_shape_and_the_push_mark(self):
        """HumanPassedCase の行の形の半分（元 eyeverdict.human_items）"""
        got = eyekit.human_items({"start": {"decision": "continue", "text": " 入口は 1 つに絞る "},
                                  "before_fix": {"decision": "continue", "text": "", answer.PUSHED: True}})
        self.assertEqual(got, [
            {"round": 1, "node": gatemarks.START_GATE_NODE, "answer": "continue", "note": "入口は 1 つに絞る"},
            {"round": 1, "node": gatemarks.GATE_NODE, "answer": "continue", "note": None, answer.PUSHED: True}])
        self.assertEqual(eyekit.human_items({}), [])
        self.assertEqual(eyekit.human_items({"start": None, "before_fix": None}), [])


class PolicyCase(_Tmp):
    def test_body_is_pasted_up_to_the_cap(self):
        doc = self.tmp / "policy.md"
        doc.write_text("方針の第 1 項\n", encoding="utf-8")
        self.assertEqual(eyekit.policy_body(doc), "方針の第 1 項\n")
        self.assertEqual(eyekit.policy_body(None), "")
        self.assertEqual(eyekit.policy_body(self.tmp / "gone.md"), "")
        doc.write_bytes(b"a" * (policy.PASTE_CAP + 10))
        got = eyekit.policy_body(doc)
        self.assertLessEqual(len(got.encode("utf-8")), policy.PASTE_CAP)
        self.assertIn(str(doc), got)

    def test_recorded_rows_keep_the_names(self):
        """test_prep_carries_the_recorded_policy_section・test_prep_keeps_the_recorded_rows_for_the_verdict の作り直し"""
        doc = self.tmp / "policy.md"
        doc.write_text("1\n2\n", encoding="utf-8")
        items = eyekit.human_items({"before_fix": {"decision": "continue", "text": "古い入口は消してよい"}})
        rows = eyekit.recorded_rows(doc, [{"question": "入口は 1 つか", "text": "はい"}], items, ["問い q1: 推しを採る"], None)
        self.assertEqual([r["source"] for r in rows], ["doc", "answer", "gate", "push"])
        text, none = eyekit.recorded_rows_text(rows)
        self.assertFalse(none)
        for r in rows:
            self.assertIn(f"`{r['name']}", text)
        self.assertIn("(lines 1-2;", text)
        self.assertEqual(policy.hits(rows, f"ぶつかる: {rows[2]['name']}"), [rows[2]["name"]])

    def test_no_nameable_row_is_recorded_none(self):
        text, none = eyekit.recorded_rows_text(eyekit.recorded_rows(None, [], [], [], None))
        self.assertTrue(none)
        self.assertIn("- Policy document: none", text)
        self.assertIn("- People's answers at the approval nodes: none", text)


class VerdictCase(_Tmp):
    REASON = "冗長な写しが在る"

    def r1(self, status, **extra):
        return {"status": status, "reason": self.REASON, "deletions": [], "ledger_audit": [], "increments": [], **extra}

    def test_status_values_follow_the_eye(self):
        self.assertEqual(eyekit.status_values("r1"), {"st_pass": "pass", "st_redesign": "redesign-needed",
                                                      "st_unverifiable": "unverifiable", "st_fix": "fix-needed"})
        self.assertNotIn("st_fix", eyekit.status_values("r3"))

    def test_read_reply_names_why(self):
        self.assertEqual(eyekit.read_reply(self.tmp, "r1-minimality"), (None, eyekit.NO_FILE))
        (self.tmp / "x.json").write_text("{", encoding="utf-8")
        self.assertIn("読めない", eyekit.read_reply(self.tmp, "x")[1])
        (self.tmp / "x.json").write_text("[]", encoding="utf-8")
        self.assertIn("object でない", eyekit.read_reply(self.tmp, "x")[1])
        (self.tmp / "x.json").write_text('{"status": "pass"}', encoding="utf-8")
        self.assertEqual(eyekit.read_reply(self.tmp, "x"), ({"status": "pass"}, ""))

    def test_missing_reply_is_unverifiable_and_named(self):
        """test_missing_eye_file_is_unverifiable_and_named と FellTextCase の ran の無い形"""
        row, took = eyekit.verdict_row("r1", None, eyekit.NO_FILE)
        self.assertFalse(took)
        self.assertEqual(row, {"status": "unverifiable", "reason": "R1 の筋が落ちた（r1: 出力のファイルが無い。ノードが落ちた）"})
        self.assertNotIn("を回した", row["reason"])

    def test_off_contract_status_is_named(self):
        """test_off_contract_status_is_named: R3 の fix-needed も約束の外"""
        for eye, status in (("r3", "ok"), ("r3", seal.FIX_NEEDED), ("r1", "ok")):
            with self.subTest(eye=eye, status=status):
                row, took = eyekit.verdict_row(eye, {"status": status, "reason": "整合"})
                self.assertFalse(took)
                self.assertEqual(row["status"], "unverifiable")
                self.assertTrue(row["reason"].startswith(eyekit.LANE[eye] + " "), row["reason"])
                self.assertIn("約束の外", row["reason"])

    def test_r1_redesign_without_points_falls_to_fix_needed(self):
        for label, points in (("欄が無い", {}), ("空の配列", {"redesign_points": []})):
            with self.subTest(label):
                self.assertEqual(eyekit.verdict_row("r1", self.r1(seal.REDESIGN, **points)),
                                 ({"status": seal.FIX_NEEDED, "reason": eyekit.UNNAMED_REDESIGN + self.REASON}, True))
        self.assertEqual(eyekit.verdict_row("r3", {"status": seal.REDESIGN, "reason": "筋が合わない"}),
                         ({"status": seal.REDESIGN, "reason": "筋が合わない"}, True))

    def test_r1_malformed_points_are_unverifiable_not_unnamed(self):
        for status in (seal.REDESIGN, seal.FIX_NEEDED, seal.PASSED):
            for label, points in (("空白だけ", ["", "  "]), ("配列でない", "設計の点"), ("項が文字列でない", [3, None]), ("オブジェクト", {"a": 1})):
                with self.subTest(status=status, label=label):
                    self.assertEqual(eyekit.verdict_row("r1", self.r1(status, redesign_points=points))[0],
                                     {"status": seal.UNVERIFIABLE, "reason": eyekit.BROKEN_POINTS + self.REASON})
        self.assertEqual(eyekit.verdict_row("r1", self.r1(seal.REDESIGN, redesign_points=["  ", "返りの型を作り替える", 3]))[0],
                         {"status": seal.REDESIGN, "reason": self.REASON + "（組み直す設計の点: 返りの型を作り替える）"})

    def test_r1_points_make_redesign_whatever_the_eye_wrote(self):
        points = ["返りの型を作り替える", "他の消費者が読む契約を替える"]
        tail = "（組み直す設計の点: 返りの型を作り替える／他の消費者が読む契約を替える）"
        for status in (seal.FIX_NEEDED, seal.PASSED):
            with self.subTest(status):
                self.assertEqual(eyekit.verdict_row("r1", self.r1(status, redesign_points=[*points, ""]))[0],
                                 {"status": seal.REDESIGN, "reason": eyekit.RAISED_BY_POINTS + self.REASON + tail})
        self.assertEqual(eyekit.verdict_row("r1", self.r1(seal.REDESIGN, redesign_points=points))[0],
                         {"status": seal.REDESIGN, "reason": self.REASON + tail})
        self.assertEqual(eyekit.verdict_row("r1", self.r1(seal.UNVERIFIABLE, redesign_points=points))[0],
                         {"status": seal.UNVERIFIABLE, "reason": self.REASON})
        self.assertEqual(eyekit.verdict_row("r1", self.r1(seal.FIX_NEEDED))[0], {"status": seal.FIX_NEEDED, "reason": self.REASON})
        self.assertEqual(eyekit.verdict_row("r3", {"status": seal.PASSED, "reason": "整合", "redesign_points": points})[0],
                         {"status": seal.PASSED, "reason": "整合"})

    def test_headline_is_the_report_row_shape(self):
        self.assertEqual(eyekit.headline("R1", {"status": "pass", "reason": "最小\n で ある"}), "R1: pass（最小 で ある）")
        self.assertEqual(eyekit.headline("R1", {"status": "pass", "reason": ""}), "R1: pass（理由なし）")

    def test_constants_are_the_eyeverdict_words(self):
        """写した定数は今の eyeverdict の字のまま（組み込みで eyeverdict を消すまで、2 か所が同じ字を言う）"""
        import eyeverdict
        for name in ("FELL_MARK", "NO_FILE", "UNNAMED_REDESIGN", "RAISED_BY_POINTS", "BROKEN_POINTS", "NO_AFTER", "REVIEW_ACCEPTED",
                     "REVIEW_BLOCKED", "REVIEW_GAVE_UP", "REVIEW_HELD", "REVIEW_NO_PLAN", "REVIEW_UNREAD", "LANE"):
            with self.subTest(name):
                self.assertEqual(getattr(eyekit, name), getattr(eyeverdict, name))


if __name__ == "__main__":
    unittest.main()

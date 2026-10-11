"""書き込みの出どころの突き合わせ（lib/writes.py。元 .shared/core/writes.py）の検査。

- 突き合わせ: 記録も申告も無い変更（追跡中・未追跡・消した物）を拒む。記録の後に中身が変わった物も拒む。理由つきの申告は通し、
  記録に残す（後ろの受け付けが同じ申告を求めない）。除くパスの頭の下を数えないことは test_fix_seams。記録の無い run は知らせつきで通す
"""
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from tests.bin.gitkit import committed_copy, git  # noqa: E402
import leftovers  # noqa: E402
import writes  # noqa: E402

SEED = LIB.parent / "tests" / "e2e" / "target-seed"   # 元は test_blk_fix_tdd の SEED（ROOT / "dev" / "target-seed"）
WHY = "整形の道具で 40 ファイルを一度に書き換えた"


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def record(log, path, tool="Edit"):
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"tool_name": tool, "path": os.path.realpath(str(path)), "file_sha": sha(path)}) + "\n")


class RepoCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        self.rev = committed_copy(self.repo, SEED)
        self.log = self.tmp / "writes.jsonl"
        self.log.write_text("", encoding="utf-8")

    def check(self, reply=None, **kw):
        return writes.check(reply or {}, self.repo, writes.changed(self.repo, self.rev), self.log, **kw)


class TestChangedFrom(RepoCase):
    """writes.changed_from: HEAD・index と違う木（修正役の並べの枝の項目の頭。tddloop.snapshot＝leftovers.snapshot）からの変更。前の項目が作った
    新しいファイル（index に無い）は、中身が同じなら変更でない"""

    def test_changes_from_a_snapshot_tree(self):
        (self.repo / "stats.py").write_text("前の項目\n", encoding="utf-8")
        (self.repo / "NOTES.md").write_text("前の項目の記録\n", encoding="utf-8")
        (self.repo / "GONE.md").write_text("前の項目が作り、後で消す\n", encoding="utf-8")
        head = leftovers.snapshot(self.repo)
        self.assertEqual(writes.changed_from(self.repo, head), [], "頭の木のままなら変更は無い")
        self.assertEqual(writes.changed_from(self.repo, self.rev), writes.changed(self.repo, self.rev), "commit からは changed と同じ")
        (self.repo / "test_stats.py").write_text("後の項目\n", encoding="utf-8")
        (self.repo / "NEW.md").write_text("後の項目の記録\n", encoding="utf-8")
        (self.repo / "GONE.md").unlink()
        self.assertEqual(writes.changed_from(self.repo, head), ["GONE.md", "NEW.md", "test_stats.py"])
        tracked = subprocess.run(["git", "ls-files"], cwd=self.repo, capture_output=True, text=True, encoding="utf-8",
                                 check=True).stdout.split()
        self.assertNotIn("NOTES.md", tracked, "本物の index は触らない")

    def test_changed_from_frozen_revision_ignores_untracked_files_written_before(self):
        """版 rev（写しの核が版を固めた review_rev。作業ツリーの未追跡のファイルも入る）に在る未追跡のファイルは、中身が同じなら
        rev からの変更でない（仕様の段の書き手が版を固める前に書いた受け入れ条件のテストを、修正役の変更と数えない。線に仕様の段を
        配線して本物のスクリプトで回して見つけた）。中身を変えれば変更で、rev に無い新しいファイルは今どおり変更"""
        (self.repo / "test_spec_accept.py").write_text("仕様の書き手が書いた\n", encoding="utf-8")
        frozen = leftovers.snapshot(self.repo)
        self.assertEqual(writes.changed(self.repo, frozen), [])
        (self.repo / "stats.py").write_text("修正\n", encoding="utf-8")
        (self.repo / "NEW.md").write_text("修正役の記録\n", encoding="utf-8")
        self.assertEqual(writes.changed(self.repo, frozen), ["NEW.md", "stats.py"])
        (self.repo / "test_spec_accept.py").write_text("弱めた\n", encoding="utf-8")
        self.assertIn("test_spec_accept.py", writes.changed(self.repo, frozen))

    def test_untouched_files_are_not_changed_without_auto_refresh(self):
        """利用者の git 設定 diff.autoRefreshIndex=false でも、触っていないファイルを変わったと数えない（一時の index に stat が無い）"""
        (self.repo / "NOTES.md").write_text("前の項目の記録\n", encoding="utf-8")
        head = leftovers.snapshot(self.repo)
        (self.repo / "stats.py").write_text("後の項目\n", encoding="utf-8")
        env = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "diff.autoRefreshIndex", "GIT_CONFIG_VALUE_0": "false"}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(writes.changed_from(self.repo, head), ["stats.py"])


class TestProvenance(RepoCase):
    def test_bash_write_without_record_is_rejected(self):
        (self.repo / "stats.py").write_text("changed\n", encoding="utf-8")
        got = self.check({"changes": []})
        self.assertEqual(len(got["problems"]), 1)
        self.assertIn("stats.py", got["problems"][0])
        self.assertIn("bash_writes", got["problems"][0])
        self.assertEqual(got["reply"], {"changes": []})

    def test_edit_with_matching_record_passes(self):
        (self.repo / "stats.py").write_text("changed\n", encoding="utf-8")
        record(self.log, self.repo / "stats.py")
        self.assertEqual(self.check()["problems"], [])

    def test_carry_moves_a_unit_record_only_for_same_content(self):
        """単位の worktree で Edit が書いた中身と同じ中身の run の作業ツリーのファイルだけ、記録を写す（依頼 243 の並べ）。
        中身が違う・元に記録が無い物は写さず、受け付けは今どおり拒む"""
        unit = self.tmp / "unit"
        unit.mkdir()
        for name, text in (("stats.py", "changed\n"), ("other.py", "unit side\n"), ("bare.py", "no record\n")):
            (unit / name).write_text(text, encoding="utf-8")
        record(self.log, unit / "stats.py")
        record(self.log, unit / "other.py")
        (self.repo / "stats.py").write_text("changed\n", encoding="utf-8")
        (self.repo / "other.py").write_text("merged with another\n", encoding="utf-8")
        (self.repo / "bare.py").write_text("no record\n", encoding="utf-8")
        got = writes.carry(self.log, [(unit / n, self.repo / n) for n in ("stats.py", "other.py", "bare.py")])
        self.assertEqual(got, [str((self.repo / "stats.py").resolve())])
        problems = self.check()["problems"]
        self.assertEqual(len(problems), 1)
        self.assertNotIn("stats.py", problems[0])
        self.assertIn("other.py", problems[0])
        self.assertIn("bare.py", problems[0])

    def test_carry_merged_records_a_machine_merge_of_recorded_units(self):
        """TDD の輪の並べで機械が 2 つの単位の中身を合わせたファイル（依頼 243 の並べの 3 段目）: どちらの中身にも記録が在れば
        合わせた中身に 1 行を足し、受け付けが通る。片方に記録が無ければ足さない"""
        u1, u2 = self.tmp / "u1", self.tmp / "u2"
        for d, text in ((u1, "a\nB\n"), (u2, "A\nb\n")):
            d.mkdir()
            (d / "stats.py").write_text(text, encoding="utf-8")
        (self.repo / "stats.py").write_text("A\nB\n", encoding="utf-8")
        record(self.log, u1 / "stats.py")
        self.assertFalse(writes.carry_merged(self.log, self.repo / "stats.py", [u1 / "stats.py", u2 / "stats.py"]))
        self.assertTrue(self.check()["problems"])
        record(self.log, u2 / "stats.py")
        self.assertTrue(writes.carry_merged(self.log, self.repo / "stats.py", [u1 / "stats.py", u2 / "stats.py"]))
        self.assertEqual(self.check()["problems"], [])
        row = json.loads(self.log.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual((row["tool_name"], row["from"]), (writes.CARRY_TOOL, [str((u1 / "stats.py").resolve()),
                                                                                 str((u2 / "stats.py").resolve())]))

    def test_overwritten_after_record_is_rejected(self):
        p = self.repo / "stats.py"
        p.write_text("by edit\n", encoding="utf-8")
        record(self.log, p)
        p.write_text("by bash\n", encoding="utf-8")
        self.assertTrue(self.check()["problems"])

    def test_restored_to_recorded_content_passes(self):
        """輪が単位の頭に戻した中身（前に編集の道具が書いた中身）は、最後の記録でなくても通す"""
        p = self.repo / "stats.py"
        p.write_text("first\n", encoding="utf-8")
        record(self.log, p)
        p.write_text("second\n", encoding="utf-8")
        record(self.log, p)
        p.write_text("first\n", encoding="utf-8")
        self.assertEqual(self.check()["problems"], [])

    def test_untracked_and_deleted_without_record_are_rejected(self):
        (self.repo / "new.py").write_text("n\n", encoding="utf-8")
        (self.repo / "stats.py").unlink()
        got = self.check()
        for name in ("new.py", "stats.py"):
            self.assertIn(name, got["problems"][0])
        self.assertEqual(got["left"], ["new.py", "stats.py"])

    def test_declared_bash_write_with_reason_passes_and_is_kept(self):
        (self.repo / "stats.py").write_text("formatted\n", encoding="utf-8")
        (self.repo / "test_stats.py").unlink()
        got = self.check({"x": 1, "bash_writes": [{"path": "stats.py", "why": WHY}, {"path": "./test_stats.py", "why": WHY}]})
        self.assertEqual((got["problems"], got["reply"]), ([], {"x": 1}))
        self.assertEqual(self.check()["problems"], [], "通った申告は記録に残り、後ろの受け付けが同じ申告を求めない")
        (self.repo / "stats.py").write_text("again\n", encoding="utf-8")
        self.assertTrue(self.check()["problems"], "申告の後に中身が変われば記録が無いのと同じ")

    def test_declaration_without_reason_is_rejected(self):
        (self.repo / "stats.py").write_text("x\n", encoding="utf-8")
        for bad in ([{"path": "stats.py", "why": "短い"}], [{"path": "/abs/stats.py", "why": WHY}], [{"why": WHY}], "stats.py"):
            with self.subTest(bad):
                self.assertTrue(self.check({"bash_writes": bad})["problems"])

    def test_symlink_needs_a_declaration(self):
        """Bash で作った symlink は、指し先の中身に記録が在っても通さない（編集の道具は symlink を作れない）"""
        p = self.repo / "stats.py"
        p.write_text("by edit\n", encoding="utf-8")
        record(self.log, p)
        os.symlink(p, self.repo / "link.py")
        self.assertEqual(self.check()["left"], ["link.py"])
        self.assertEqual(self.check({"bash_writes": [{"path": "link.py", "why": WHY}]})["problems"], [])

    def test_no_change_passes(self):
        got = self.check()
        self.assertEqual((got["problems"], got["note"], got["left"]), ([], "", []))

    def test_not_strict_keeps_the_change_for_the_report(self):
        (self.repo / "stats.py").write_text("x\n", encoding="utf-8")
        got = self.check(strict=False)
        self.assertEqual((got["problems"], got["left"]), ([], ["stats.py"]))


class TestNoRecordRun(RepoCase):
    def test_run_without_sink_passes_with_note(self):
        """包みの無い run（記録のファイルが無い）は拒否の理由にせず今どおり通し、知らせを返す（盤面の trace から報告に 1 行）"""
        (self.repo / "stats.py").write_text("changed\n", encoding="utf-8")
        self.log.unlink()
        got = self.check()
        self.assertEqual((got["problems"], got["note"]), ([], writes.NO_RECORD))
        self.assertIn("書き込みの記録が無い run", got["note"])


if __name__ == "__main__":
    unittest.main()

"""並行 PR の block を、script を子のプロセスで回して確かめる（docs/design/parallel-pr.md の 7 節）。

始めの記録の無い使い捨ての run directory と、remote を GitHub の URL にした git のリポジトリで、port の値だけを渡し、
scan → prep → 台本の返答 → take → read_proof → finish と回す。gh は PATH の頭に置いた偽の gh（読むだけ）で返す。
筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import hashlib
import json
import os
import stat
import unittest
from unittest import mock

from tests.bin import hermetic
from tests.bin.gitkit import git
from tests.blocks import kit

NAME = "parallel-pr"
SOURCE = "def mean(xs):\n    return sum(xs)\n"
LOOP = "pr-check-loop"
GITHUB = "git@github.com:o/r.git"
FAKE_GH = """#!/bin/sh
case "$1 $2" in
  "pr list") echo '[{"number": 7, "headRefName": "x", "headRefOid": "theirs"}, {"number": 9, "headRefName": "y", "headRefOid": "other"}]' ;;
  "pr view") case "$3" in 7) echo '{"files": [{"path": "stats.py"}]}' ;; *) echo '{"files": [{"path": "other.py"}]}' ;; esac ;;
esac
"""
OK_REPLY = {
    "material": {"status": "found", "count": 1, "detail": "PR #7 が stats.py の mean を同じく書き換えている"},
    "repo": "o/r", "listed": 2, "truncated": False,
    "conflicts": [{"pr": "7", "files": ["stats.py"], "handed_over": False, "note": "PR #7 の担当へ: どちらを先に入れるか決めてください"}],
    "excluded": [{"pr": "7", "file": "stats.py", "start": 1, "end": 2, "why": "mean の同じ行を書き換える"}],
}


class FlowCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, NAME)
        (self.run.repo / "stats.py").write_text(SOURCE, encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")
        git(self.run.repo, "remote", "add", "origin", GITHUB)
        self.bin = hermetic.tmpdir(self) / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        gh.write_text(FAKE_GH, encoding="utf-8")
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        patch = mock.patch.dict(os.environ, PATH=os.pathsep.join([str(self.bin), os.environ.get("PATH", "")]))
        patch.start()
        self.addCleanup(patch.stop)

    def scan(self, **inputs):
        return self.run.script("scan", "scan", **{"base": "", "request": "[]", "changed": "[]", "lang": "", **inputs})

    def prep(self):
        return self.run.script("prep", f"{LOOP}.pr-check-prep")

    def take(self, reply):
        return self.run.script("take", f"{LOOP}.pr-check-accept", reply=json.dumps(reply, ensure_ascii=False))

    def finish(self):
        return self.run.script("finish", "finish")

    def read(self, name):
        return json.loads((self.run.artifacts / name).read_text(encoding="utf-8"))

    def test_no_crossing_is_decided_by_the_machine(self):
        """交差なし → scan が役を起こさず、出口が clean。外す hunk は空の控えで置く"""
        got = self.scan(changed='["unrelated.py"]')
        self.assertEqual(got["go_role"], False, got)
        self.assertIn("機械が決めた: clean", got["reason"])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["stop_reason"]), (True, "clean", ""))
        self.assertEqual(self.read(fin["excluded"]["path"]), {"node": "p0.parallel_pr", "head": git(self.run.repo, "rev-parse", "HEAD"),
                                                                "excluded": []})
        self.assertEqual((fin["drafts"], fin["reads"]), (None, None))
        self.assertEqual(fin["material"]["status"], "clean")
        self.assertTrue(fin["report"][0].startswith("並行 PR: clean（"), fin["report"])
        self.assertEqual(len(fin["downgrades"]), 1)

    def test_crossing_runs_the_role_and_keeps_the_drafts(self):
        """交差あり → 役へ → 指示に渡し物の絶対パス → 台本の返答を受ける → 下書きと中身の印つきの外す hunk"""
        got = self.scan(changed='["stats.py"]')
        self.assertEqual(got["go_role"], True, got)
        self.assertIn("交差", got["reason"])
        brief = self.run.artifacts / "pr-brief.json"
        self.assertEqual(json.loads(brief.read_text(encoding="utf-8"))["changed_files"], ["stats.py"])
        self.assertIn(str(brief), self.prep()["prompt"])
        self.assertEqual(self.take(OK_REPLY), {"ok": True, "done": True, "reason": ""})
        reads = self.run.script("read_proof", "pr-check-reads")
        self.assertEqual((reads["ok"], reads["reason"]), (True, ""), reads)
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["stop_reason"]), (True, "found", ""))
        self.assertEqual(self.read(fin["drafts"]["path"]), [{"pr": "7", "files": ["stats.py"], "note": OK_REPLY["conflicts"][0]["note"]}])
        hunk = self.read(fin["excluded"]["path"])["excluded"][0]
        self.assertEqual((hunk["text"], hunk["sha256"]), (SOURCE, hashlib.sha256(SOURCE.encode("utf-8")).hexdigest()))
        self.assertEqual(fin["reads"]["path"], "reads-pr-check.json")
        self.assertIn("並行 PR #7 の担当への申し送りの下書き（stats.py。投稿していない）: ", "\n".join(fin["report"]))

    def test_role_that_changes_the_working_tree_is_refused(self):
        self.scan(changed='["stats.py"]')
        (self.run.repo / "stats.py").write_text("changed\n", encoding="utf-8")
        got = self.take(OK_REPLY)
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertIn("作業ツリーを変えた", got["reason"])
        self.assertFalse((self.run.artifacts / "pr-excluded.json").exists())
        self.assertTrue(self.prep()["prompt"])

    def test_local_remote_is_not_applicable_and_wakes_no_role(self):
        git(self.run.repo, "remote", "set-url", "origin", str(self.run.repo.parent / "elsewhere"))
        got = self.scan(changed='["stats.py"]')
        self.assertEqual(got["go_role"], False)
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (True, "not_applicable"))
        self.assertTrue(fin["material"]["reason"].startswith("no_forge: local_path"), fin["material"])

    def test_request_wheres_name_the_changed_files_when_nothing_else_does(self):
        """changed が空で base も空なら、依頼の where が名指す追跡中のファイルが変更ファイル"""
        request = json.dumps([{"where": "stats.py:2", "text": "mean が数で割っていない"}], ensure_ascii=False)
        self.assertEqual(self.scan(request=request)["go_role"], True)
        brief = self.read("pr-brief.json")
        self.assertEqual((brief["changed_files"], brief["request_wheres"]), (["stats.py"], ["stats.py:2"]))

    def test_unreadable_port_does_not_crash_and_the_exit_says_failed(self):
        got = self.scan(changed="not json")
        self.assertEqual(got["go_role"], False)
        self.assertIn("入力が読めない", got["reason"])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["stop_reason"]), (True, "failed", ""))
        self.assertEqual(fin["material"]["status"], "not_run")
        self.assertIn("入力が読めない", fin["material"]["reason"])

    def test_exit_without_any_record_says_not_run(self):
        """scan も役も回っていない place → failed と not_run の素材（無言の空を作らない）。ok は真のまま"""
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["stop_reason"]), (True, "failed", ""))
        self.assertEqual(fin["material"]["status"], "not_run")
        self.assertIn("走らなかった", fin["material"]["reason"])
        self.assertEqual((fin["excluded"], fin["drafts"], fin["reads"]), (None, None, None))

    def test_third_rejection_gives_up_with_works_pr(self):
        """役が 3 回とも拒まれたら、輪は 3 回目で抜け、出口が failed と stop_reason works:pr を返す"""
        self.scan(changed='["stats.py"]')
        handed = {**OK_REPLY, "conflicts": [{**OK_REPLY["conflicts"][0], "handed_over": True}]}
        for n in (1, 2, 3):
            got = self.take(handed)
            self.assertEqual((got["ok"], got["done"]), (False, n == 3), n)
            if n < 3:
                self.assertIn("1 回目の拒否", self.prep()["prompt"])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["stop_reason"]), (False, "failed", "works:pr"))
        self.assertEqual(fin["material"]["status"], "not_run")
        self.assertEqual(fin["material"]["reason"], fin["reason"])

    def test_new_run_in_the_same_place_clears_the_old_files_by_name(self):
        self.scan(changed='["stats.py"]')
        self.take(OK_REPLY)
        (self.run.artifacts / "keep.txt").write_text("x", encoding="utf-8")
        self.scan(changed='["unrelated.py"]')
        self.assertFalse((self.run.artifacts / "pr-downgrades.json").exists())
        self.assertFalse((self.run.artifacts / "rejects-pr-check.json").exists())
        self.assertTrue((self.run.artifacts / "keep.txt").is_file(), "ほかの名は消さない")

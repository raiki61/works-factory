"""並行 PR の block を、script を子のプロセスで回して確かめる（docs/design/parallel-pr.md の 7 節）。

始めの記録の無い使い捨ての run directory と、remote を GitHub の URL にした git のリポジトリで、port の値だけを渡し、
scan → prep → 台本の返答 → take → read_proof → finish と回す。gh は PATH の頭に置いた偽の gh（読むだけ）で返す。
筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import hashlib
import json
import os
import pathlib
import stat
import subprocess
import sys
import unittest
from unittest import mock

import yaml

from tests.bin import hermetic
from tests.bin.gitkit import git
from tests.blocks import kit

NAME = "parallel-pr"
RECORDER = kit.ROOT / "bin" / "_lib" / "record-read.py"
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


class FlowBase(unittest.TestCase):
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


class FlowCase(FlowBase):
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
        """同じ place の前の run が素材の控えを残していても、読めない port の run の出口はそれを読まない"""
        self.scan(changed='["stats.py"]')
        self.take(OK_REPLY)
        got = self.scan(changed="not json")
        self.assertEqual(got["go_role"], False)
        self.assertIn("入力 changed が読めない", got["reason"])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["stop_reason"]), (False, "failed", "works:pr"))   # 素材の控えが無い
        self.assertEqual(fin["material"]["status"], "not_run")
        self.assertIn("入力 changed が読めない", fin["material"]["reason"])

    def test_exit_without_any_record_stops_with_works_pr(self):
        """scan も役も回っていない place（役が再試行の後に落ちた・scan が全部落ちた）→ failed と not_run の素材に、止める語 works:pr。
        元の工場では役の輪が落ちると判定が止まった（再開できる止め）"""
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["stop_reason"]), (False, "failed", "works:pr"))
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


class ReadsCase(FlowBase):
    """読んだ証拠の node pr-check-reads（元 tests/workflows/test_judge.py の ReadsTest の写し）"""

    def setUp(self):
        super().setUp()
        self.config = hermetic.tmpdir(self) / "claude"
        self.scan(changed='["stats.py"]')
        self.brief = self.run.artifacts / "pr-brief.json"
        at = self.brief.stat().st_mtime - 60
        os.utime(self.brief, (at, at))

    def read_proof(self) -> dict:
        """read_proof を、隔離した設定の置き場（CLAUDE_CONFIG_DIR）を渡して子のプロセスで回す（kit.Run.script は INPUTS_ しか渡さない）"""
        done = subprocess.run([sys.executable, str(kit.BLOCKS / NAME / "scripts" / "read_proof.py")], cwd=self.run.repo, text=True,
                              encoding="utf-8", capture_output=True,
                              env=hermetic.child_env(**self.run.environ(), CLAUDE_CONFIG_DIR=str(self.config)))
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def hook(self, path):
        event = {"session_id": "s-1", "tool_name": "Read", "tool_input": {"file_path": str(path)}, "tool_use_id": "toolu_Read",
                 "cwd": str(self.run.repo), "hook_event_name": "PostToolUse"}
        done = subprocess.run([sys.executable, str(RECORDER), str(self.config / "works-reads")], input=json.dumps(event), text=True,
                              encoding="utf-8", capture_output=True, cwd=str(self.run.repo),
                              env=hermetic.child_env(PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_pr_check_must_read_its_brief(self):
        """渡し物を読んでいなければ missing に入り、出口の報告に 1 行出る。読めば空になり、索引に読んだ行が残る"""
        (self.config / "works-reads").mkdir(parents=True)
        self.hook(self.run.repo / "stats.py")
        out = self.read_proof()
        self.assertIs(out["ok"], True, out)
        self.assertEqual(out["missing"], [str(self.brief)])
        self.assertIn(f"並行 PR の役が渡し物を読んだ記録が無い（{self.brief}）", self.finish()["report"])
        self.hook(self.brief)
        out = self.read_proof()
        self.assertEqual(out["missing"], [], out)
        index = pathlib.Path(out["index_file"])
        self.assertEqual(index.parent, self.run.artifacts)
        doc = json.loads(pathlib.Path(json.loads(index.read_text(encoding="utf-8"))["pr-check"]).read_text(encoding="utf-8"))
        self.assertEqual([row["path"] for row in doc["rows"]], [str(self.brief)])
        self.assertTrue(all("読んだ記録が無い" not in line for line in self.finish()["report"]))

    def test_pr_check_reads_without_record_root_does_not_fail(self):
        """記録の根が無い（フックを置いていない起動）時も落ちず、読んでいないとも言わない"""
        out = self.read_proof()
        self.assertEqual((out["ok"], out["missing"]), (True, []), out)
        self.assertEqual(self.read("reads-pr-check.json")["sources"], {"hook": "none", "why": "記録の根が無い（読んだ証拠のフックを置いていない起動）"})

    def test_proof_failure_is_reported_and_cleaned_by_the_next_run(self):
        """集める node が落ちた回（渡し物が消えた）: ok 偽で返り、時刻つきの落ちた記録が残り、出口の報告に 1 行出る。
        次の scan はその記録を型の名で引いて消す（積もらない）"""
        self.brief.unlink()
        out = self.read_proof()
        self.assertIs(out["ok"], False, out)
        self.assertTrue(out["reason"])
        self.assertEqual(len(list(self.run.artifacts.glob("reads-pr-check-failed-*.json"))), 1)
        self.assertTrue(any(line.startswith("並行 PR: 読んだ証拠を集められなかった（") for line in self.finish()["report"]))
        self.scan(changed='["unrelated.py"]')
        self.assertEqual(list(self.run.artifacts.glob("reads-pr-check-failed-*.json")), [])


class WiringCase(unittest.TestCase):
    """YAML の配線と、役の返答の形（元 tests/workflows/test_judge.py の同名の試験の写し）"""

    def setUp(self):
        doc = yaml.safe_load((kit.BLOCKS / NAME / "works-factory-parallel-pr.yaml").read_text(encoding="utf-8"))
        self.nodes = {}
        for node in doc["nodes"]:
            self.nodes[node["id"]] = node
            for inner in (node.get("loop_group") or {}).get("nodes", []):
                self.nodes[inner["id"]] = inner

    def rejected(self, reply):
        kit.load(NAME, "files")   # lib/graphloops を sys.path に足す
        from engine.schema import validate_schema
        return validate_schema(reply, self.nodes["pr-check"]["output_format"])

    def test_pr_check_reads_runs_after_the_role_on_the_roles_rounds(self):
        """役の輪の後に走り（先に走ると読む前の記録で欠けと言う）、輪が落ちた回も走り、役を起こした回だけ走る"""
        node, role = self.nodes["pr-check-reads"], self.nodes[LOOP]
        self.assertIn(LOOP, node["depends_on"])
        self.assertEqual(node["trigger_rule"], "one_success")
        self.assertEqual(node["when"], role["when"])

    def test_pr_check_reply_outside_the_type_is_rejected(self):
        """excluded が無い・行の番号が 1 より小さい返答を、output_format が拒む"""
        self.assertEqual(self.rejected(OK_REPLY), [])
        self.assertTrue(self.rejected({k: v for k, v in OK_REPLY.items() if k != "excluded"}))
        self.assertTrue(self.rejected(dict(OK_REPLY, excluded=[dict(OK_REPLY["excluded"][0], start=0)])))


if __name__ == "__main__":
    unittest.main()

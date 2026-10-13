"""読んだ証拠（lib/reads.py）の検査。元の works/tests/test_reads.py の CollectTest・WebTest・NamesTest の場合を、出どころを
フックの記録だけにして写す（行は試験が記録の形で書く。フックを実物で起こすのは tests/bin/test_record_read.py）。
足した場合: 差し込みの始まりの時刻 since より前の行と、役だけに渡した材料を読んでいない session の行を数えない・記録が無い・
読めない時の名指し。
"""
import hashlib
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import reads  # noqa: E402

SINCE = "2026-10-12T10:00:00"
BEFORE = "2026-10-12T09:59:59"


class Case(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name).resolve()
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.place = self.tmp / "place"
        self.place.mkdir()
        self.log = reads.reads_path(self.tmp / reads.ROOT, self.repo)
        self.doc = self.repo / "brief.md"
        self.doc.write_text("材料\n", encoding="utf-8")

    def write(self, *rows):
        self.log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log, "a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def read_row(self, path, ts=SINCE, session="s", **more):
        raw = pathlib.Path(path).read_bytes()
        return {"ts": ts, "session_id": session, "agent_id": None, "path": str(pathlib.Path(path).resolve()),
                "file_sha": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "partial": False, "partial_why": None,
                "tool_use_id": "toolu_r", **more}

    def call(self, tool, value, ts=SINCE, session="s"):
        return {"ts": ts, "session_id": session, "agent_id": None, "tool_use_id": "toolu_c", "tool_name": tool, "input": value}

    def collect(self, must, **kw):
        got = reads.collect(self.place, "plan-writer", must, self.log, own=kw.pop("own", [str(self.doc)]),
                            since=kw.pop("since", SINCE), repo=self.repo, **kw)
        return got, json.loads(pathlib.Path(got["reads_file"]).read_text(encoding="utf-8"))


class CollectTest(Case):
    def test_states_from_hook(self):
        other = self.repo / "policy.md"
        other.write_text("方針\n", encoding="utf-8")
        partial = self.repo / "big.md"
        partial.write_text("大きい\n", encoding="utf-8")
        self.write(self.read_row(self.doc), self.read_row(partial, partial=True, partial_why="range"))
        got, doc = self.collect([str(self.doc), str(other), str(partial)])
        self.assertEqual([r["hook"] for r in doc["rows"]], ["read", "absent", "partial"])
        self.assertEqual(got["missing"], [str(other)])
        self.assertEqual(got["sources"], {"hook": "recorded", "why": ""})
        self.assertTrue(got["ok"])

    def test_stale_when_file_changed(self):
        self.write(self.read_row(self.doc))
        self.doc.write_text("書き換えた\n", encoding="utf-8")
        _, doc = self.collect([str(self.doc)])
        self.assertEqual(doc["rows"][0]["hook"], "stale")

    def test_rows_before_since_are_not_counted(self):
        """記録は作業の場ごとに混ざるので、差し込みの始まりより前の行（前の役・前の往復の読み）は数えない"""
        self.write(self.read_row(self.doc, ts=BEFORE))
        got, doc = self.collect([str(self.doc)])
        self.assertEqual((doc["rows"][0]["hook"], got["missing"]), ("absent", [str(self.doc)]))
        got, _ = self.collect([str(self.doc)], since=BEFORE)
        self.assertEqual(got["missing"], [])

    def test_relative_must_resolves_against_repo(self):
        self.write(self.read_row(self.doc))
        _, doc = self.collect(["brief.md"], own=["brief.md"])
        self.assertEqual(doc["rows"], [{"path": "brief.md", "hook": "read"}])

    def test_other_sessions_rows_are_not_the_roles(self):
        """同じ作業の場で並んで走る別の役（線の判定のやり直しなど）の読み・web・Agent を、役 role の物に数えない。役の session は
        役だけに渡した材料 own を読んだ session"""
        policy = self.repo / "policy.md"
        policy.write_text("方針\n", encoding="utf-8")
        self.write(self.read_row(policy, session="S-judge"), self.call("WebFetch", "https://judge.example/", session="S-judge"),
                   self.call("Agent", "general-purpose", session="S-judge"),
                   self.read_row(self.doc), self.call("WebSearch", "mean 空の列"))
        got, doc = self.collect([str(self.doc), str(policy)])
        self.assertEqual([r["hook"] for r in doc["rows"]], ["read", "absent"])
        self.assertEqual(got["missing"], [str(policy)])
        self.assertEqual(doc["web"], {"fetches": [], "searches": ["mean 空の列"]})
        self.assertEqual(reads.tool_count(got["records"], "Agent"), 0)

    def test_role_that_read_none_of_its_own_material_has_no_rows(self):
        self.write(self.read_row(self.doc, session="S-judge"), self.call("WebFetch", "https://judge.example/", session="S-judge"))
        got, doc = self.collect([str(self.doc)], own=[])
        self.assertEqual((got["missing"], got["records"]), ([str(self.doc)], []))
        self.assertEqual(doc["web"], {"fetches": [], "searches": []})

    def test_missing_record_file_is_named_none(self):
        self.log.parent.mkdir(parents=True)
        got, doc = self.collect([str(self.doc)])
        self.assertEqual(got["sources"]["hook"], "none")
        self.assertIn(str(self.log), got["sources"]["why"])
        self.assertEqual((got["missing"], doc["rows"][0]["hook"]), ([], None))

    def test_missing_root_and_missing_config_are_named_apart(self):
        """記録が無い訳を取り違えない（K15）: 設定の置き場が渡っていない起動と、渡ったが記録の根が無い（フックを置いていない）起動"""
        got, _ = self.collect([str(self.doc)])
        self.assertEqual((got["sources"]["hook"], got["sources"]["why"]), ("none", reads.NO_ROOT))
        got = reads.collect(self.place, "plan-writer", [str(self.doc)], None, own=[], since=SINCE, repo=self.repo)
        self.assertEqual(got["sources"]["why"], reads.NO_CONFIG)

    def test_log_here_follows_the_config_dir(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.tmp)}):
            self.assertEqual(reads.log_here(), reads.reads_path(self.tmp / reads.ROOT, pathlib.Path.cwd()))
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(reads.log_here())

    def test_unreadable_record_is_named_unreadable(self):
        """読めない記録を「読んでいない」と取り違えない（元の EVENTS_VERIFIED の扱い）"""
        self.log.parent.mkdir(parents=True)
        self.log.mkdir()
        got, doc = self.collect([str(self.doc)])
        self.assertEqual(got["sources"]["hook"], "unreadable")
        self.assertEqual((got["missing"], doc["web"]), ([], None))

    def test_replan_names_the_evidence_file(self):
        got, doc = self.collect([str(self.doc)], replan=True)
        self.assertEqual(pathlib.Path(got["reads_file"]).name, "reads-replan-plan-writer.json")
        self.assertEqual(doc["role"], "replan-plan-writer")

    def test_collect_records_web_of_the_role(self):
        self.write(self.read_row(self.doc), self.call("WebFetch", "https://example.org/a", ts=BEFORE),
                   self.call("WebFetch", "https://example.org/b"), self.call("WebFetch", "https://example.org/b"),
                   self.call("WebSearch", "mean 空の列"))
        _, doc = self.collect([])
        self.assertEqual(doc["web"], {"fetches": ["https://example.org/b"], "searches": ["mean 空の列"]})


class ReadEvidenceTest(Case):
    def test_reads_back_what_collect_wrote(self):
        other = self.repo / "other.md"
        other.write_text("x\n", encoding="utf-8")
        self.write(self.read_row(self.doc))
        got, _ = self.collect([str(self.doc), str(other)])
        doc, why = reads.read_evidence(got["reads_file"])
        self.assertEqual(why, "")
        self.assertEqual((doc["role"], doc["missing"], doc["sources"]["hook"]), ("plan-writer", [str(other)], reads.RECORDED))
        self.assertEqual([r["path"] for r in doc["rows"]], [str(self.doc), str(other)])

    def test_unreadable_and_misshapen_files_say_why(self):
        bad = self.place / "reads-x.json"
        bad.write_text("{", encoding="utf-8")
        self.assertTrue(reads.read_evidence(bad)[1].startswith("JSONDecodeError: "))
        bad.write_text('{"role": "x", "rows": []}', encoding="utf-8")
        self.assertEqual(reads.read_evidence(bad), (None, reads.SHAPE_WRONG))
        self.assertTrue(reads.read_evidence(self.place / "none.json")[1].startswith("FileNotFoundError: "))


class GuardedTest(unittest.TestCase):
    """#371: 読んだ証拠のノードの中で誤りが起きた時も、報告が「役を起こしていない」と取り違えない記録を置き場に残す"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.place = pathlib.Path(tmp.name) / "place"

    def test_passes_the_collected_return_through(self):
        got = reads.guarded(lambda: {"ok": True, "missing": ["a"], "index_file": "i"}, owner="fix", place=self.place)
        self.assertEqual(got, {"ok": True, "missing": ["a"], "index_file": "i", "reason": ""})
        self.assertFalse(self.place.exists())

    def test_failure_writes_a_failed_evidence(self):
        def broken():
            raise KeyError("k\n2")
        got = reads.guarded(broken, owner="plan-review", place=self.place)
        self.assertEqual(got, {"ok": False, "missing": [], "index_file": "", "reason": "KeyError: 'k\\n2'"})
        [path] = self.place.glob(reads.EVIDENCE_GLOB)
        self.assertFalse(reads.is_index(path.name))
        doc, why = reads.read_evidence(path)
        self.assertEqual(why, "")
        self.assertEqual((doc["role"], doc["sources"]), ("plan-review", {"hook": reads.FAILED, "why": got["reason"]}))

    def test_failure_names_do_not_overwrite_each_other_or_the_role_evidence(self):
        self.assertNotEqual(reads.failure_name("plan-review", 0), reads.failure_name("plan-review", 60))
        self.assertNotEqual(reads.failure_name("fix", 0), reads.evidence_name("fix"))
        self.assertTrue(reads.failure_name("fix", 0).startswith(reads.evidence_name("fix").removesuffix(".json")))


class ToolTest(unittest.TestCase):
    ROWS = [{"tool_name": "Agent", "input": "general-purpose"}, {"tool_name": "Agent", "input": "general-purpose"},
            {"tool_name": "WebSearch", "input": "q"}, {"path": "/x", "file_sha": "a"}]

    def test_tool_count_and_inputs(self):
        self.assertEqual(reads.tool_count(self.ROWS, "Agent"), 2)
        self.assertEqual(reads.tool_inputs(self.ROWS, "Agent"), ["general-purpose", "general-purpose"])
        self.assertEqual(reads.tool_count(self.ROWS, "WebFetch"), 0)

    def test_web_fetches_and_searches(self):
        self.assertEqual(reads.web_searches(self.ROWS), ["q"])
        self.assertEqual(reads.web_fetches(self.ROWS), [])
        self.assertEqual(reads.web_fetches(None), [])


class NamesTest(unittest.TestCase):
    def test_evidence_and_index_names(self):
        """元 NamesTest: 役ごとの証拠と索引の名は別で、どちらも EVIDENCE_GLOB に当たる"""
        self.assertEqual(reads.evidence_name("plan-review"), "reads-plan-review.json")
        self.assertEqual(reads.index_name("plan-review"), "reads-plan-review-block.json")
        self.assertNotEqual(reads.index_name("plan-review"), reads.evidence_name("plan-review"))
        self.assertTrue(reads.is_index(reads.index_name("plan")))
        self.assertFalse(reads.is_index(reads.evidence_name("plan-writer")))
        for name in (reads.index_name("plan"), reads.evidence_name("plan-writer")):
            self.assertTrue(pathlib.PurePath(name).match(reads.EVIDENCE_GLOB))

    def test_reads_path_is_per_cwd(self):
        root = pathlib.Path("/r")
        self.assertEqual(reads.reads_path(root, "/a").name, reads.LOG)
        self.assertNotEqual(reads.reads_path(root, "/a").parent, reads.reads_path(root, "/b").parent)


if __name__ == "__main__":
    unittest.main()

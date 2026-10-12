"""読んだ証拠（lib/reads.py）の検査。元の works/tests/test_reads.py の CollectTest・WebTest・NamesTest の場合を、出どころを
フックの記録だけにして写す（行は試験が記録の形で書く。フックを実物で起こすのは tests/bin/test_record_read.py）。
足した場合: 差し込みの始まりの時刻 since より前の行を数えない・記録が無い・読めない時の名指し。
"""
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

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

    def read_row(self, path, ts=SINCE, **more):
        raw = pathlib.Path(path).read_bytes()
        return {"ts": ts, "session_id": "s", "agent_id": None, "path": str(pathlib.Path(path).resolve()),
                "file_sha": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "partial": False, "partial_why": None,
                "tool_use_id": "toolu_r", **more}

    def call(self, tool, value, ts=SINCE):
        return {"ts": ts, "session_id": "s", "agent_id": None, "tool_use_id": "toolu_c", "tool_name": tool, "input": value}

    def collect(self, must, **kw):
        got = reads.collect(self.place, "plan-writer", must, self.log, since=kw.pop("since", SINCE), repo=self.repo, **kw)
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
        _, doc = self.collect(["brief.md"])
        self.assertEqual(doc["rows"], [{"path": "brief.md", "hook": "read"}])

    def test_missing_record_is_named_none(self):
        got, doc = self.collect([str(self.doc)])
        self.assertEqual(got["sources"]["hook"], "none")
        self.assertIn(str(self.log), got["sources"]["why"])
        self.assertEqual((got["missing"], doc["rows"][0]["hook"]), ([], None))

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
        self.write(self.call("WebFetch", "https://example.org/a", ts=BEFORE), self.call("WebFetch", "https://example.org/b"),
                   self.call("WebFetch", "https://example.org/b"), self.call("WebSearch", "mean 空の列"))
        _, doc = self.collect([])
        self.assertEqual(doc["web"], {"fetches": ["https://example.org/b"], "searches": ["mean 空の列"]})


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

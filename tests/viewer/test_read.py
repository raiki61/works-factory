"""見る道具の読む部品の後始末と数え（viewer/src/runread.py・viewer/src/session.py。docs/design/viewer.md の 5 章と 6 章）。

- DB は読むだけで開き、読み終えたら閉じる（接続の close が呼ばれたかを見る。開いたままの接続に ResourceWarning を出すのは
  Python 3.13 からなので、警告では版によって照らせない）
- 始めの時刻が同じ秒の run は、後に作った run を新しいとする。Archon の SQLite は時刻を秒までしか持たず（datetime('now')）、承認で
  再開した run の始めを今に書き直す（packages/core/src/db/workflow-run-resume.ts）ので、再開の直後に起こした run と秒が並ぶ
- 一覧の並びと一番新しい run は、出来事の最初の時刻で決める（起き直した run が、後に始めた run より上に来ない）
- 子の run のかかった秒も、run の行の値でなく、その子と孫の出来事の最初の始めと最後の終わりから出す
- 壊れた時刻（読めない ts）の出来事が在っても、選んだ run は落ちず、その時刻だけを数えない
- 会話の記録の行は、読む型・読まない型（訳つき）・知らない型に分け、知らない型だけを読めなかった物に数える（帯の数が本当に読めなかった
  物を指す）。読まない型のうち字を別の型から読む物は、その代わりの型が記録に無い会話では知らない型と同じく数える。Claude Code の記録の形は工場が止めていないので、読まない型の表が本物の記録に合うかは人が見る
- 往復の印は、usage を持つ行を待たず、その往復の最初の行で置く（usage の無い返事が混じっても往復の数がずれず、どの返事にも usage が
  無くても返事と道具の呼び出しが並びから消えない。usage は後の行で埋める）

試験は一時のフォルダに小さな DB と記録を作る。
"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from viewer.src import runread, session


class ReadCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def test_db_is_closed_after_reading(self):
        db = self.tmp / runread.DB_FILE
        con = sqlite3.connect(db)
        con.execute(f"create table {runread.RUN_TABLE} ({', '.join(runread.RUN_COLUMNS)})")
        con.execute(f"create table {runread.EVENT_TABLE} ({', '.join(runread.EVENT_COLUMNS)})")
        con.execute(f"insert into {runread.RUN_TABLE} (id, parent_run_id, started_at) values ('run-1', null, '2026-10-28')")
        con.commit()
        con.close()
        opened, real = [], sqlite3.connect

        class Probe:
            """本物の接続に渡し、close が呼ばれたかを持つ（sqlite3 の接続の close は差し替えられない）"""
            def __init__(self, *args, **kwargs):
                self.con, self.closed = real(*args, **kwargs), False
                opened.append(self)

            def __getattr__(self, name):
                return getattr(self.con, name)

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return self.con.__exit__(*exc)

            def close(self):
                self.closed = True
                self.con.close()

        with mock.patch.object(runread.sqlite3, "connect", Probe):
            self.assertEqual(runread.pick(db), "run-1")
        self.assertTrue(opened)
        self.assertEqual([p.closed for p in opened], [True] * len(opened))
        for p in opened:
            p.con.close()

    def test_later_run_is_newer_within_the_same_second(self):
        db = self.tmp / runread.DB_FILE
        con = sqlite3.connect(db)
        con.execute(f"create table {runread.RUN_TABLE} ({', '.join(runread.RUN_COLUMNS)})")
        con.execute(f"create table {runread.EVENT_TABLE} ({', '.join(runread.EVENT_COLUMNS)})")
        for rid in ("zz-resumed", "aa-later"):
            con.execute(f"insert into {runread.RUN_TABLE} (id, parent_run_id, started_at) values (?, null, '2026-10-28 12:00:00')", (rid,))
        con.commit()
        con.close()
        self.assertEqual((runread.pick(db), [r["id"] for r in runread.runs(db)]), ("aa-later", ["aa-later", "zz-resumed"]))

    def test_span_runs_from_the_first_event_to_the_last(self):
        db, rid = self.tmp / runread.DB_FILE, "run-resumed"
        con = sqlite3.connect(db)
        con.execute(f"create table {runread.RUN_TABLE} ({', '.join(runread.RUN_COLUMNS)})")
        con.execute(f"create table {runread.EVENT_TABLE} ({', '.join(runread.EVENT_COLUMNS)})")
        # 承認の答えで起き直した run は、DB の行の始めが起き直した時刻に書き換わる
        con.execute(f"insert into {runread.RUN_TABLE} (id, workflow_name, status, parent_run_id, started_at, completed_at, output_root, metadata) "
                    "values (?, 'g', 'completed', null, '2026-10-25 02:31:34', '2026-10-25 02:34:41', ?, '{}')", (rid, str(self.tmp)))
        for kind, at in (("workflow_started", "2026-10-25 01:50:54"), ("node_started", "2026-10-25 01:50:54"),
                         ("workflow_started", "2026-10-25 02:31:34"), ("workflow_completed", "2026-10-25 02:34:41")):
            con.execute(f"insert into {runread.EVENT_TABLE} (workflow_run_id, event_type, data, created_at) values (?, ?, '{{}}', ?)", (rid, kind, at))
        con.commit()
        con.close()
        log = self.tmp / runread.LOGS / f"{rid}.jsonl"
        log.parent.mkdir()
        node = lambda kind, ts, path: {"type": kind, "ts": ts, "step": path, runread.EXECUTION: {"path": path, "invocation": {"id": path}}}
        log.write_text("\n".join(json.dumps(row) for row in (
            node("node_start", "2026-10-25T01:50:54.377Z", "a"), node("node_complete", "2026-10-25T01:50:55.000Z", "a"),
            node("node_start", "2026-10-25T02:34:40.000Z", "b"), node("node_complete", "2026-10-25T02:34:41.278Z", "b"))) + "\n", encoding="utf-8")
        got = runread.run(db, rid)
        self.assertEqual((got["started"], got["seconds"]), ("2026-10-25T01:50:54.377Z", 2626.9))
        listed = runread.runs(db)[0]
        self.assertEqual((listed["started"], listed["seconds"]), ("2026-10-25 01:50:54", 2627.0))

    def _db(self, runs: list[tuple], events: list[tuple]) -> Path:
        """runs は (id, parent, started, completed, metadata)、events は (run, created_at)"""
        db = self.tmp / runread.DB_FILE
        con = sqlite3.connect(db)
        con.execute(f"create table {runread.RUN_TABLE} ({', '.join(runread.RUN_COLUMNS)})")
        con.execute(f"create table {runread.EVENT_TABLE} ({', '.join(runread.EVENT_COLUMNS)})")
        for rid, parent, started, completed, metadata in runs:
            con.execute(f"insert into {runread.RUN_TABLE} (id, workflow_name, status, parent_run_id, started_at, completed_at, output_root, metadata) "
                        "values (?, 'g', 'completed', ?, ?, ?, ?, ?)", (rid, parent, started, completed, str(self.tmp), metadata))
        for rid, at in events:
            con.execute(f"insert into {runread.EVENT_TABLE} (workflow_run_id, event_type, data, created_at) values (?, 'node_started', '{{}}', ?)", (rid, at))
        con.commit()
        con.close()
        return db

    def _log(self, rid: str, rows: list) -> None:
        log = self.tmp / runread.LOGS / f"{rid}.jsonl"
        log.parent.mkdir(exist_ok=True)
        log.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    @staticmethod
    def _node(kind, ts, path):
        return {"type": kind, "ts": ts, "step": path, runread.EXECUTION: {"path": path, "invocation": {"id": path}}}

    def test_resumed_run_sorts_by_its_first_event(self):
        db = self._db([("resumed", None, "2026-10-28 13:00:00", None, "{}"), ("later", None, "2026-10-28 12:00:00", None, "{}")],
                      [("resumed", "2026-10-28 10:00:00"), ("resumed", "2026-10-28 13:00:00"), ("later", "2026-10-28 12:00:00")])
        self.assertEqual((runread.pick(db), [r["id"] for r in runread.runs(db)]), ("later", ["later", "resumed"]))

    def test_child_span_runs_from_its_events(self):
        db = self._db([("top", None, "2026-10-25 01:00:00", "2026-10-25 02:00:00", "{}"),
                       ("kid", "top", "2026-10-25 01:55:00", "2026-10-25 01:56:00", json.dumps({runread.PARENT_NODE: "w"})),
                       ("grand", "kid", "2026-10-25 01:55:30", "2026-10-25 01:56:00", json.dumps({runread.PARENT_NODE: "x"}))], [])
        self._log("top", [self._node("node_start", "2026-10-25T01:00:00.000Z", "w"), self._node("node_complete", "2026-10-25T02:00:00.000Z", "w")])
        self._log("kid", [self._node("node_start", "2026-10-25T01:10:00.000Z", "a"), self._node("node_complete", "2026-10-25T01:20:00.000Z", "a")])
        self._log("grand", [self._node("node_start", "2026-10-25T01:15:00.000Z", "b"), self._node("node_complete", "2026-10-25T01:30:00.500Z", "b")])
        kids = {c["id"]: (c["started"], c["seconds"]) for c in runread.run(db, "top")["children"]}
        self.assertEqual(kids, {"kid": ("2026-10-25T01:10:00.000Z", 1200.5), "grand": ("2026-10-25T01:15:00.000Z", 900.5)})

    def test_broken_time_is_not_counted(self):
        db = self._db([("top", None, "2026-10-25 01:00:00", "2026-10-25 02:00:00", "{}")], [])
        self._log("top", [self._node("node_start", "2026-10-25T01:00:00.000Z", "a"), self._node("node_complete", "not a time", "a"),
                          self._node("node_start", "2026-10-25T01:00:10.000Z", "b"), self._node("node_complete", "2026-10-25T01:00:20.000Z", "b")])
        got = runread.run(db, "top")
        self.assertEqual((got["started"], got["seconds"]), ("2026-10-25T01:00:00.000Z", 20.0))

    def test_children_keep_their_run_and_outputs_their_whole_digest(self):
        """同じノードから起こした子の run 2 つ（fan_out）は出来事の道が同じなので、繰り返しの確かめの行も run の id で分かる。
        切った出力は、切る前の字の hash（digest）を持つ（頭の 20,000 字が同じで後ろの違う出力を同じと数えない）"""
        db = self.tmp / runread.DB_FILE
        con = sqlite3.connect(db)
        con.execute(f"create table {runread.RUN_TABLE} ({', '.join(runread.RUN_COLUMNS)})")
        con.execute(f"create table {runread.EVENT_TABLE} ({', '.join(runread.EVENT_COLUMNS)})")
        con.execute(f"insert into {runread.RUN_TABLE} (id, workflow_name, status, parent_run_id, started_at, output_root, metadata) "
                    "values ('top', 'g', 'completed', null, '2026-10-25 01:00:00', ?, '{}')", (str(self.tmp),))
        for child in ("c1", "c2"):
            con.execute(f"insert into {runread.RUN_TABLE} (id, workflow_name, status, parent_run_id, started_at, output_root, metadata) "
                        "values (?, 'k', 'completed', 'top', '2026-10-25 01:00:01', ?, ?)",
                        (child, str(self.tmp), json.dumps({runread.PARENT_NODE: "fan"})))
            con.execute(f"insert into {runread.EVENT_TABLE} (workflow_run_id, event_type, data, created_at) values (?, ?, ?, '')",
                        (child, runread.OUTPUT_EVENT, json.dumps({"invocation": {"id": f"{child}-a"},
                                                                   runread.NODE_OUTPUT: "x" * runread.CLIP + child})))
        con.commit()
        con.close()
        (self.tmp / runread.LOGS).mkdir()
        (self.tmp / runread.LOGS / "top.jsonl").write_text("", encoding="utf-8")
        for child in ("c1", "c2"):
            node = lambda kind: {"type": kind, "ts": "2026-10-25T01:00:02.000Z", "step": "a",
                                 runread.EXECUTION: {"path": "a", "invocation": {"id": f"{child}-a"}}}
            check = {"type": runread.EXEC_ROW, "step": f"rounds{runread.ITERATION_MARK}1", runread.runlog.EXIT_CODE: 1,
                     "ts": "2026-10-25T01:00:03.000Z"}
            (self.tmp / runread.LOGS / f"{child}.jsonl").write_text(
                "\n".join(json.dumps(row) for row in (node("node_start"), node("node_complete"), check)) + "\n", encoding="utf-8")
        got = runread.run(db, "top")
        self.assertEqual([(row["run"], row["node"]) for row in got["checks"]], [("c1", ["fan"]), ("c2", ["fan"])])
        a1, a2 = sorted(got["events"], key=lambda e: e["run"])
        self.assertEqual((a1["tokens"], a1["output"]), (a2["tokens"], a2["output"]))
        self.assertNotEqual(a1["digest"], a2["digest"])

    def test_only_unknown_session_types_are_unread(self):
        path = self.tmp / "s.jsonl"
        known = next(kind for kind in session.UNREAD_TYPES if kind not in session.READ_FROM)
        rows = [{"type": "user", "message": {"content": "hello"}}, {"type": known}, {"type": "no-such-type"}]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\nnot json\n", encoding="utf-8")
        got = session.read(path, lambda text: text)
        self.assertEqual(got["unread"], {"知らない型 no-such-type": 1, "JSON でない行": 1})
        self.assertFalse(set(session.UNREAD_TYPES) & set(session.READ_TYPES))

    def test_unread_types_count_when_their_substitute_is_missing(self):
        path = self.tmp / "s.jsonl"
        rows = [{"type": "attachment"}, {"type": "api-request"}, {"type": "attachment"}]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        got = session.read(path, lambda text: text)
        self.assertEqual(got["unread"], {f"字を読む代わりの型が記録に無い {kind}": n for kind, n in (("attachment", 2), ("api-request", 1))})
        rows.append({"type": session.BLOB, "message": {"content": []}})
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        self.assertEqual(session.read(path, lambda text: text)["unread"], {"字を読む代わりの型が記録に無い api-request": 1})
        rows.append({"type": session.SHAPE, "shape": {}})
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        self.assertEqual(session.read(path, lambda text: text)["unread"], {})
        self.assertLessEqual(set(session.READ_FROM), set(session.UNREAD_TYPES))

    def test_flow_marks_each_turn_once_by_its_number(self):
        path = self.tmp / "s.jsonl"
        usage = lambda out: {"input_tokens": 2, "cache_read_input_tokens": 10, "cache_creation_input_tokens": 5, "output_tokens": out}
        say = lambda ident, out, part: {"type": "assistant", "message": {"id": ident, "usage": usage(out), "content": [part]}}
        rows = [{"type": "user", "message": {"content": "go"}},
                say("m1", 1, {"type": "text", "text": "a"}), say("m1", 50, {"type": "tool_use", "id": "t1", "name": "Read", "input": {}}),
                {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "body"}]}},
                say("m2", 7, {"type": "text", "text": "b"})]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        got = session.read(path, lambda text: text)
        self.assertEqual([row[0] for row in got["seq"]], ["user", "turn", "say", "call", "result", "turn", "say"])
        self.assertEqual([row[1] for row in got["seq"] if row[0] == "turn"], [0, 1])
        self.assertEqual([turn["usage"]["out"] for turn in got["turns"]], [50, 7])

    def test_flow_marks_turns_without_usage(self):
        path = self.tmp / "s.jsonl"
        say = lambda ident, part, **more: {"type": "assistant", "message": {"id": ident, "content": [part], **more}}
        rows = [{"type": "user", "message": {"content": "go"}},
                say("m1", {"type": "tool_use", "id": "t1", "name": "Read", "input": {}}),
                {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "body"}]}},
                say("m2", {"type": "text", "text": "a"}), say("m2", {"type": "text", "text": "b"}, usage={"output_tokens": 4})]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        got = session.read(path, lambda text: text)
        self.assertEqual([row[0] for row in got["seq"]], ["user", "turn", "call", "result", "turn", "say", "say"])
        self.assertEqual([row[1] for row in got["seq"] if row[0] == "turn"], [0, 1])
        self.assertEqual([turn["usage"].get("out") for turn in got["turns"]], [None, 4])

    def test_turns_keep_their_first_time_and_calls_their_whole_input(self):
        """往復の時刻は往復の最初の行の時刻（cache の保ち時間を越えた往復を出す。無駄の手がかり）。道具の呼び出しは切る前の入力の字の
        番号を持ち、会話は作業の場所 cwd を持つ（読み直しの数えが、切った入力でなく全文のパスを読む）"""
        path = self.tmp / "s.jsonl"
        long = {"file_path": "/w/a.md", "note": "x" * 1000}
        say = lambda ident, ts, part: {"type": "assistant", "timestamp": ts, "cwd": "/w", "message": {"id": ident, "content": [part]}}
        rows = [say("m1", "2026-10-25T01:00:00.000Z", {"type": "tool_use", "id": "t1", "name": "Read", "input": long}),
                say("m1", "2026-10-25T01:00:09.000Z", {"type": "text", "text": "a"}),
                say("m2", "2026-10-25T01:07:00.000Z", {"type": "text", "text": "b"})]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        texts = {}
        got = session.read(path, lambda text: texts.setdefault(str(len(texts)), text) and next(k for k, v in texts.items() if v == text))
        self.assertEqual([turn["at"] for turn in got["turns"]], ["2026-10-25T01:00:00.000Z", "2026-10-25T01:07:00.000Z"])
        self.assertEqual(json.loads(texts[got["turns"][0]["calls"][0]["text"]]), long)
        self.assertEqual(got["cwd"], "/w")


if __name__ == "__main__":
    unittest.main()

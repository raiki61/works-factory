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
- run の一覧の行の結末 outcome は、line の返すノード result の出力（DB の node_completed。JSON の字でも値でも）の結末の語。result の
  出力を持たない run（ほかの graph・result まで走っていない run）と、出力に結末の語が無い run は空
- run の費用は metadata の total_cost_usd で、空の run（一覧の行と選んだ run の両方）は DB のノードの終わりの出来事（落ちたノードも）のうち
  accounting が node の物の和（後から書く費用の出来事も）で代える。子の run の費用は、親の子の run を起こすノード（workflow）の行が accounting を
  node にして子の総額を載せる（metadata の total_cost_usd と同じ）。子の run の行は別の run なので親の和に足さない（足すと二重）。どちらも無い run は空
- 起き直した run のログが書く「前に済んだので飛ばした」行（node_skipped の content が prior_success）は、飛んだノードに数えない
  （その道が済んだことは前の起動の出来事で見える）
- 終わった run（状態が completed・failed・cancelled）の終わりは DB の終わりの出来事の時刻で、一覧と選んだ run のかかった秒が合う
  （終わりの出来事をログに書かずに終わった run でも）。終わりの無い待ちと走り中のまま止まったノードはその時刻で閉じ、印 cut を付ける。
  走り中の run は最後の出来事まで。DB の終わりは秒までなので、ログの最後の終わりの方が遅ければそちらを run の終わりにする
- 出来事の時刻の欄は、DB の時刻で閉じた物も含めて全部ログの形（T と Z）
- run の費用の代わりの和は Archon の nodeCostScope の数え方: accounting の無い古い行は aggregate が true でなければ自前、
  compose_fan_out の instance の行が正でその中の行（道の頭が instance の道）は外す、費用の欄を持つ行が無ければ空。走り中の run は
  metadata の古い total_cost_usd でなく代わりの和。答え待ちの run は待ちに入る時に Archon が書いた total_cost_usd
- 落ちの訳は状態が failed の run だけに出す（落ちた後に起き直して終わった run に古い訳を残さない）
- 読めない時刻の行（字でない時刻も）は、その時刻を数えずに進み、読めなかった物に数える（段の集計と無駄の手がかりを落とさない）
- 会話の id の頭が 2 つ以上の記録に当たれば、黙って選ばずに読めなかった物に数える
- DB のパスに URI の特別な字（? # %）が在っても、そのパスの DB を開く
- 続けた会話（sessionOrigin が resumed）は、ノードの出来事の始めより前の往復（前の会話から写して持つ物）に copied を付ける
- 往復の印は、usage を持つ行を待たず、その往復の最初の行で置く（usage の無い返事が混じっても往復の数がずれず、どの返事にも usage が
  無くても返事と道具の呼び出しが並びから消えない。usage は後の行で埋める）

試験は一時のフォルダに小さな DB と記録を作る。
"""
import json
import re
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
        self.assertEqual((got["started"], got["seconds"]), ("2026-10-25T01:50:54.377Z", 2626.9))   # 終わりは DB の workflow_completed（秒まで）とログの最後の終わりの遅い方
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

    def test_listed_run_carries_the_outcome_of_its_result(self):
        db = self._db([(rid, None, f"2026-10-28 1{n}:00:00", None, "{}") for n, rid in enumerate(("done", "text", "none", "odd"))], [])
        con = sqlite3.connect(db)
        for rid, output in (("done", {runread.RESULT_OUTCOME: "stopped_by_human", "stop_reason": "gate-design:stop"}),
                            ("text", json.dumps({runread.RESULT_OUTCOME: "fixed"})), ("odd", {"ok": False})):
            con.execute(f"insert into {runread.EVENT_TABLE} (workflow_run_id, event_type, step_name, data, created_at) values (?, ?, ?, ?, '')",
                        (rid, runread.OUTPUT_EVENT, runread.RESULT_NODE, json.dumps({"invocation": {"id": rid}, runread.NODE_OUTPUT: output})))
        con.execute(f"insert into {runread.EVENT_TABLE} (workflow_run_id, event_type, step_name, data, created_at) values (?, ?, ?, ?, '')",
                    ("none", runread.OUTPUT_EVENT, "report", json.dumps({"invocation": {"id": "x"}, runread.NODE_OUTPUT: {runread.RESULT_OUTCOME: "fixed"}})))
        con.commit()
        con.close()
        self.assertEqual({r["id"]: r["outcome"] for r in runread.runs(db)}, {"done": "stopped_by_human", "text": "fixed", "none": "", "odd": ""})

    def test_empty_total_cost_falls_back_to_the_calls(self):
        db = self._db([("paid", None, "2026-10-28 13:00:00", None, json.dumps({runread.TOTAL_COST: 9.5})),
                       ("blank", None, "2026-10-28 12:00:00", None, "{}"),
                       ("kid", "blank", "2026-10-28 12:00:01", None, json.dumps({runread.PARENT_NODE: "w"})),
                       ("none", None, "2026-10-28 11:00:00", None, "{}")], [])
        con = sqlite3.connect(db)
        # 子の run を起こすノード w の行（accounting が node）が子の総額 0.125 を載せる。子 kid の行は別の run で、親の和に足さない。
        # 繰り返しの束ね行（accounting が aggregate）は中のノードの言い直しなので足さない
        own, loop = runread.runlog.OWN_SPEND, "aggregate"
        for rid, kind, step, accounting, cost in (("paid", runread.OUTPUT_EVENT, "a", own, 1.0), ("blank", runread.OUTPUT_EVENT, "a", own, 0.25),
                                                  ("blank", runread.NODE_FAILED_EVENT, "a", own, 0.5),
                                                  ("blank", runread.DEFERRED_EVENT, "a", own, 0.0625),
                                                  ("blank", runread.OUTPUT_EVENT, "w", own, 0.125), ("blank", runread.OUTPUT_EVENT, "l", loop, 2.0),
                                                  ("kid", runread.OUTPUT_EVENT, "a", own, 0.125)):
            con.execute(f"insert into {runread.EVENT_TABLE} (workflow_run_id, event_type, step_name, data, created_at) values (?, ?, ?, ?, '')",
                        (rid, kind, step, json.dumps({runread.ACCOUNTING: accounting, runread.NODE_COST: cost})))
        con.commit()
        con.close()
        (self.tmp / runread.LOGS).mkdir()
        (self.tmp / runread.LOGS / "blank.jsonl").write_text("", encoding="utf-8")
        self.assertEqual({r["id"]: r["cost"] for r in runread.runs(db)}, {"paid": 9.5, "blank": 0.9375, "none": None})
        self.assertEqual(runread.run(db, "blank")["cost"], 0.9375)

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


    def test_prior_success_rows_are_not_skips(self):
        db = self._db([("top", None, "2026-10-25 01:00:00", None, "{}")], [])
        self._log("top", [{"type": "node_skipped", "ts": "2026-10-25T01:00:00.000Z", "step": "a", "content": runread.PRIOR_SUCCESS},
                          {**self._node("node_skipped", "2026-10-25T01:00:01.000Z", "b"), "cause": "when"}])
        self.assertEqual([(s["tokens"], s["cause"]) for s in runread.run(db, "top")["skipped"]], [(["b"], "when")])

    def _status(self, db: Path, rid: str, status: str) -> None:
        con = sqlite3.connect(db)
        con.execute(f"update {runread.RUN_TABLE} set status = ? where id = ?", (status, rid))
        con.commit()
        con.close()

    def _event(self, db: Path, rid: str, kind: str, at: str = "", step: str = "", data: dict | None = None) -> None:
        con = sqlite3.connect(db)
        con.execute(f"insert into {runread.EVENT_TABLE} (workflow_run_id, event_type, step_name, data, created_at) values (?, ?, ?, ?, ?)",
                    (rid, kind, step, json.dumps(data or {}), at))
        con.commit()
        con.close()

    def test_a_finished_run_ends_at_its_end_event(self):
        """ログが待ちの始めで切れた run（待ちのまま止めた）は、DB の終わりの出来事で終わり、一覧と選んだ run の秒が合う。
        終わりの無い待ちはその時刻で閉じる。走り中の run は最後の出来事まで"""
        db = self._db([("top", None, "2026-10-25 01:00:00", None, "{}"), ("live", None, "2026-10-25 00:00:00", None, "{}")],
                      [("top", "2026-10-25 01:00:00"), ("live", "2026-10-25 00:00:00")])
        self._status(db, "top", "cancelled")
        self._status(db, "live", "running")
        self._event(db, "top", "workflow_cancelled", "2026-10-25 01:10:00")
        self._event(db, "live", "workflow_failed", "2026-10-25 00:00:30")   # 落ちた後に起き直して走っている
        gate = {**self._node("node_suspended", "2026-10-25T01:00:05.000Z", "gate"),
                runread.EXECUTION: {"path": "gate", "invocation": {"id": "gate"}, "node": {"kind": runread.WAIT_NODE}}}
        self._log("top", [self._node("node_start", "2026-10-25T01:00:00.000Z", "a"), self._node("node_complete", "2026-10-25T01:00:05.000Z", "a"),
                          {**gate, "type": "node_start"}, gate, self._node("node_start", "2026-10-25T01:09:00.000Z", "b")])
        self._log("live", [self._node("node_start", "2026-10-25T00:00:00.000Z", "a"), self._node("node_complete", "2026-10-25T00:00:40.000Z", "a")])
        got, listed = runread.run(db, "top"), {r["id"]: r for r in runread.runs(db)}
        self.assertEqual((got["seconds"], listed["top"]["seconds"]), (600.0, 600.0))
        by_path = {e["path"]: e for e in got["events"]}
        self.assertEqual({path: (runread.length(e), e.get("cut", False)) for path, e in by_path.items()},
                         {"a": (5.0, False), "gate": (595.0, True), "b": (60.0, True)})
        self.assertEqual(runread.run(db, "live")["seconds"], 40.0)

    def test_a_run_ends_no_earlier_than_its_last_node(self):
        """DB の終わりの出来事は秒まで（切り捨て）なので、ログの最後の終わりより前になりうる。run の終わりは遅い方"""
        db = self._db([("top", None, "2026-10-25 01:00:00", None, "{}")], [("top", "2026-10-25 01:00:00")])
        self._event(db, "top", "workflow_completed", "2026-10-25 01:00:09")
        self._log("top", [self._node("node_start", "2026-10-25T01:00:00.000Z", "a"), self._node("node_complete", "2026-10-25T01:00:09.800Z", "a")])
        self.assertEqual(runread.run(db, "top")["seconds"], 9.8)

    def test_event_times_are_log_times(self):
        """出来事・飛び・確かめの行の時刻の欄は、DB の時刻で閉じた物も含めて全部ログの形（T と Z）。雛形は Date.parse で読み、
        再生の歩を字で並べるので、T も Z も無い DB の書き方が混じると時差の分ずれる"""
        db = self._db([("top", None, "2026-10-25 01:00:00", None, "{}"),
                       ("kid", "top", "2026-10-25 01:00:01", None, json.dumps({runread.PARENT_NODE: "call"}))], [])
        self._status(db, "top", "cancelled")
        self._status(db, "kid", "cancelled")
        for rid in ("top", "kid"):
            self._event(db, rid, "workflow_cancelled", "2026-10-25 01:10:00")
        gate = {**self._node("node_suspended", "2026-10-25T01:00:05.000Z", "gate"),
                runread.EXECUTION: {"path": "gate", "invocation": {"id": "gate"}, "node": {"kind": runread.WAIT_NODE}}}
        self._log("top", [{**gate, "type": "node_start"}, gate, {**self._node("node_skipped", "2026-10-25T01:00:06.000Z", "s"), "cause": "when"},
                          {"type": runread.EXEC_ROW, "ts": "2026-10-25T01:00:07.000Z", "step": "until-iteration-1"}])
        self._log("kid", [self._node("node_start", "2026-10-25T01:00:02.000Z", "k")])
        got = runread.run(db, "top")
        times = [(row.get(name), name) for part in ("events", "skipped", "checks") for row in got[part]
                 for name in ("start", "end", "time", "at") if name in row]
        self.assertEqual(len(times), 6)
        self.assertEqual([t for t in times if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z", t[0] or "")], [])

    def test_failure_text_only_on_a_failed_run(self):
        db = self._db([("again", None, "2026-10-25 01:00:00", None, "{}"), ("down", None, "2026-10-25 00:00:00", None, "{}")], [])
        self._status(db, "down", "failed")
        for rid in ("again", "down"):
            self._event(db, rid, runread.FAILED_EVENT, "2026-10-25 01:00:00", data={"error": "boom"})
        self.assertEqual({r["id"]: r["error"] for r in runread.runs(db)}, {"again": "", "down": "boom"})

    def test_spent_follows_the_archon_cost_scope(self):
        """古い行（accounting が無い）は aggregate が true でなければ自前。compose_fan_out の instance の行が正で、中の行は外す。
        費用の欄を持つ行が無い run（bash だけの run）は空。走り中の run は metadata の古い合計でなく代わりの和。答え待ちの run は
        Archon が待ちに入る時に書いた metadata の合計（persistRunUsage）"""
        db = self._db([("old", None, "2026-10-25 04:00:00", None, "{}"), ("fan", None, "2026-10-25 03:00:00", None, "{}"),
                       ("bash", None, "2026-10-25 02:00:00", None, "{}"),
                       ("live", None, "2026-10-25 01:00:00", None, json.dumps({runread.TOTAL_COST: 1.0})),
                       ("wait", None, "2026-10-25 00:00:00", None, json.dumps({runread.TOTAL_COST: 2.0}))], [])
        self._status(db, "live", "running")
        self._status(db, "wait", runread.PAUSED)
        for rid, step, data in (("old", "a", {runread.NODE_COST: 0.5}), ("old", "l", {runread.NODE_COST: 2.0, runread.AGGREGATE: True}),
                                ("fan", "i", {runread.NODE_COST: 0.75, "type": runread.INSTANCE, runread.ACCOUNTING: "instance"}),
                                ("fan", "i__x", {runread.NODE_COST: 0.5, runread.ACCOUNTING: "node"}),
                                ("fan", "b", {runread.NODE_COST: 0.125, runread.ACCOUNTING: "node"}),
                                ("bash", "s", {runread.ACCOUNTING: "node"}),
                                ("live", "a", {runread.NODE_COST: 1.0, runread.ACCOUNTING: "node"}),
                                ("live", "b", {runread.NODE_COST: 0.5, runread.ACCOUNTING: "node"}),
                                ("wait", "a", {runread.NODE_COST: 0.5, runread.ACCOUNTING: "node"})):
            self._event(db, rid, runread.OUTPUT_EVENT, step=step, data=data)
        self.assertEqual({r["id"]: r["cost"] for r in runread.runs(db)}, {"old": 0.5, "fan": 0.875, "bash": None, "live": 1.5,
                                                                         "wait": 2.0})
        self._log("live", [])
        self.assertEqual(runread.run(db, "live")["cost"], 1.5)

    def test_broken_time_is_listed_as_unread(self):
        db = self._db([("top", None, "2026-10-25 01:00:00", None, "{}")], [])
        self._log("top", [self._node("node_start", "2026-10-25T01:00:00.000Z", "a"), self._node("node_complete", "not a time", "a"),
                          self._node("node_start", 123, "b")])
        got = runread.run(db, "top")
        self.assertEqual(([e["end"] for e in got["events"]], got["unread"]), ([None, None], {"読めない時刻の行": 2}))
        self.assertEqual((runread.try_when(123), runread.seconds(123, "2026-10-25 01:00:00")), (None, None))

    def test_db_path_with_uri_marks_opens_that_file(self):
        folder = self.tmp / "a?b#c%41"
        folder.mkdir()
        db = folder / runread.DB_FILE
        con = sqlite3.connect(db)
        con.execute(f"create table {runread.RUN_TABLE} ({', '.join(runread.RUN_COLUMNS)})")
        con.execute(f"create table {runread.EVENT_TABLE} ({', '.join(runread.EVENT_COLUMNS)})")
        con.execute(f"insert into {runread.RUN_TABLE} (id, parent_run_id, started_at) values ('only', null, '2026-10-28 12:00:00')")
        con.commit()
        con.close()
        self.assertEqual(runread.pick(db), "only")

    def test_ambiguous_session_head_is_unread(self):
        projects = self.tmp / "projects"
        for folder in ("p1", "p2"):
            (projects / folder).mkdir(parents=True)
            (projects / folder / "abcd1234-0000.jsonl").write_text("", encoding="utf-8")
        (projects / "p1" / "ffff0000-1111.jsonl").write_text("", encoding="utf-8")
        run = {"events": [{"session": "abcd1234", "start": None}, {"session": "ffff0000", "start": None}], "unread": {}}
        got = session.collect(run, projects, lambda text: text)
        self.assertEqual((list(got), run["unread"]), (["ffff0000"], {"会話の id の頭が 2 つ以上の記録に当たる": 1}))

    def test_resumed_session_marks_turns_before_its_node(self):
        """続けた会話は前の会話の往復を写して持つ。ノードの出来事の始めより前の往復に copied を付ける（読み直さず数えから外す）。
        新しく始めた会話は付けない。読めない時刻は読めなかった物に数える"""
        projects = self.tmp / "projects"
        (projects / "p").mkdir(parents=True)
        say = lambda ident, ts: {"type": "assistant", "timestamp": ts, "message": {"id": ident, "content": [{"type": "text", "text": ident}]}}
        rows = [say("m1", "2026-10-25T01:00:00.000Z"), say("m2", "2026-10-25T02:00:01.000Z"), say("m3", "not a time")]
        for name in ("aaaa0000", "bbbb0000"):
            (projects / "p" / f"{name}.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        run = {"events": [{"session": "aaaa0000", "start": "2026-10-25T02:00:00.000Z", "origin": runread.RESUMED},
                          {"session": "bbbb0000", "start": "2026-10-25T02:00:00.000Z", "origin": "fresh"}], "unread": {}}
        got = session.collect(run, projects, lambda text: text)
        self.assertEqual([t.get("copied", False) for t in got["aaaa0000"]["turns"]], [True, False, False])
        self.assertEqual([t.get("copied", False) for t in got["bbbb0000"]["turns"]], [False, False, False])
        self.assertEqual(got["aaaa0000"]["unread"], {"読めない時刻": 1})


if __name__ == "__main__":
    unittest.main()

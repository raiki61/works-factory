"""見る道具の読む部品の後始末と数え（viewer/src/runread.py・viewer/src/session.py。docs/design/viewer.md の 5 章と 6 章）。

- DB は読むだけで開き、読み終えたら閉じる（接続の close が呼ばれたかを見る。開いたままの接続に ResourceWarning を出すのは
  Python 3.13 からなので、警告では版によって照らせない）
- 始めの時刻が同じ秒の run は、後に作った run を新しいとする。Archon の SQLite は時刻を秒までしか持たず（datetime('now')）、承認で
  再開した run の始めを今に書き直す（packages/core/src/db/workflow-run-resume.ts）ので、再開の直後に起こした run と秒が並ぶ
- 会話の記録の行は、読む型・読まない型（訳つき）・知らない型に分け、知らない型だけを読めなかった物に数える（帯の数が本当に読めなかった
  物を指す）。読まない型のうち字を別の型から読む物は、その代わりの型が記録に無い会話では知らない型と同じく数える。Claude Code の記録の形は工場が止めていないので、読まない型の表が本物の記録に合うかは人が見る

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


if __name__ == "__main__":
    unittest.main()

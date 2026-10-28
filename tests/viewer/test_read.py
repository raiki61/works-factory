"""見る道具の読む部品の後始末と数え（viewer/src/runread.py・viewer/src/session.py。docs/design/viewer.md の 5 章と 6 章）。

- DB は読むだけで開き、読み終えたら閉じる（開いたまま残すと ResourceWarning が出る）
- 始めの時刻が同じ秒の run は、後に作った run を新しいとする。Archon の SQLite は時刻を秒までしか持たず（datetime('now')）、承認で
  再開した run の始めを今に書き直す（packages/core/src/db/workflow-run-resume.ts）ので、再開の直後に起こした run と秒が並ぶ
- 会話の記録の行は、読む型・読まない型（訳つき）・知らない型に分け、知らない型だけを読めなかった物に数える（帯の数が本当に読めなかった
  物を指す）。Claude Code の記録の形は工場が止めていないので、読まない型の表が本物の記録に合うかは人が見る

試験は一時のフォルダに小さな DB と記録を作る。
"""
import gc
import json
import sqlite3
import tempfile
import unittest
import warnings
from pathlib import Path

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
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always", ResourceWarning)
            self.assertEqual(runread.pick(db), "run-1")
            gc.collect()
        self.assertEqual([str(w.message) for w in seen if issubclass(w.category, ResourceWarning)], [])

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
        known = next(iter(session.UNREAD_TYPES))
        rows = [{"type": "user", "message": {"content": "hello"}}, {"type": known}, {"type": "no-such-type"}]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\nnot json\n", encoding="utf-8")
        got = session.read(path, lambda text: text)
        self.assertEqual(got["unread"], {"知らない型 no-such-type": 1, "JSON でない行": 1})
        self.assertFalse(set(session.UNREAD_TYPES) & set(session.READ_TYPES))


if __name__ == "__main__":
    unittest.main()

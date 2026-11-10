"""run を 1 枚の HTML にする入口（viewer/runpage.py と viewer/src/page.py。viewer/AGENTS.md の E25 の 2・3、docs/design/viewer.md の照らしの 11）。

書き込みと秘密の値と外への読みを守る物だけを照らす（持ち主の決め tests-guard-writes）。見た目と形は縛らない（E25 の 4）。

- ページは 1 枚で完結する: 雛形と埋める物（viewer/page/ の全部）に、別のファイルや網から読む形（`<script src`・`import(`・`fetch(`）が無い
- Archon の DB は読むだけで開く: 読みの口 runread.connect の上では書けず、入口が小さな run をページにした後も DB の中身が 1 字も変わらない
- 秘密の値を出さない: run の metadata の run_config に置いた値が、ページに出ない
- ページに埋めたデータの逃がし: ノードの出力に `</script>` と `<!--` を含む run でも、データの script の中身は記録の字で閉じず、
  JSON として読み戻せる

run の家は WORKS_FACTORY_HOME（E24）で一時のフォルダへ向け、利用者の本物の run の家を読まない。
"""
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path

from bin._lib import isolate, launcher
from tests.bin import hermetic
from viewer.src import page, runread, stages

ROOT = Path(__file__).resolve().parents[2]
OUTSIDE = (re.compile(r"<script\b[^>]*\bsrc\b", re.I), re.compile(r"\bimport\s*\("), re.compile(r"\bfetch\s*\("))
DATA = re.compile(r'<script type="application/json" id="data">(.*?)</script>', re.S)
TRICKY = '{"ok": true, "note": "</script><!-- <script>x</script> </SCRIPT"}'
SECRET = "run-config-secret-7c1f"


class PageCase(unittest.TestCase):
    def test_the_page_reads_no_other_file(self):
        found = {f.name: [p.pattern for p in OUTSIDE if p.search(f.read_text(encoding="utf-8"))] for f in sorted(page.ASSETS.iterdir())}
        self.assertIn(page.TEMPLATE.name, found)
        self.assertEqual({name: hits for name, hits in found.items() if hits}, {})


class EntryCase(unittest.TestCase):
    """入口を子で起こし、一時の run の家の小さな line の run をページにする"""

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.home, self.rid = self.tmp / "home", "run-page-1"
        self.target = self.tmp / "target"
        self.target.mkdir()
        self.db = self.home / isolate.DIRS["ARCHON_HOME"] / runread.DB_FILE
        self._record()

    def _record(self) -> None:
        self.db.parent.mkdir(parents=True)
        first = stages.TABLE["stages"][0]["nodes"][0]
        meta = {runread.INPUTS: {"request": "x"}, runread.NODE_COUNTS: {"completed": 1}, "run_config": {"token": SECRET}}
        con = sqlite3.connect(self.db)
        con.execute(f"create table {runread.RUN_TABLE} ({', '.join(runread.RUN_COLUMNS)})")
        con.execute(f"create table {runread.EVENT_TABLE} ({', '.join(runread.EVENT_COLUMNS)})")
        con.execute(f"insert into {runread.RUN_TABLE} (id, workflow_name, status, parent_run_id, started_at, output_root, metadata) "
                    "values (?, 'works-factory-line', 'completed', null, '2026-11-04 01:00:00', ?, ?)",
                    (self.rid, str(self.home), json.dumps(meta)))
        con.execute(f"insert into {runread.EVENT_TABLE} (workflow_run_id, event_type, step_name, data, event_order, created_at) "
                    "values (?, ?, ?, ?, 0, '2026-11-04 01:00:02')",
                    (self.rid, runread.OUTPUT_EVENT, first, json.dumps({"invocation": {"id": first}, runread.NODE_OUTPUT: TRICKY})))
        con.commit()
        con.close()
        node = {"step": first, runread.EXECUTION: {"path": first, "invocation": {"id": first}, "node": {"kind": "script"}}}
        log = self.home / runread.LOGS / f"{self.rid}.jsonl"
        log.parent.mkdir()
        log.write_text("\n".join(json.dumps({**node, "type": kind, "ts": ts}) for kind, ts in
                                 (("node_start", "2026-11-04T01:00:00.000Z"), ("node_complete", "2026-11-04T01:00:02.500Z"))),
                       encoding="utf-8")

    def _entry(self) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(ROOT / "viewer" / "runpage.py"), "--target", str(self.target), "--run", self.rid],
                              capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=120,
                              env=hermetic.child_env(**{launcher.HOME_ENV: str(self.home)}))

    def _digest(self) -> str:
        return hashlib.sha256(self.db.read_bytes()).hexdigest()

    def test_the_db_is_opened_only_to_read(self):
        with runread.connect(self.db) as con:
            with self.assertRaises(sqlite3.OperationalError):
                con.execute("create table written (x)")
        before = self._digest()
        done = self._entry()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self._digest(), before)

    def test_run_config_stays_out_of_the_page(self):
        done = self._entry()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn(SECRET, done.stdout)
        self.assertNotIn(SECRET, done.stderr)

    def test_the_embedded_data_cannot_close_its_script(self):
        done = self._entry()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.lower().count("</script"), page.TEMPLATE.read_text(encoding="utf-8").lower().count("</script"))
        data = json.loads(DATA.search(done.stdout)[1])
        outputs = [e["output"] for o in data["objs"].values() for e in o["events"] if e.get("output")]
        self.assertIn(TRICKY, outputs)


if __name__ == "__main__":
    unittest.main()

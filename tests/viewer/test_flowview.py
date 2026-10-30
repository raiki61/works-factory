"""見る道具の入口（viewer/flowview.py）の止まり方と終了の値（viewer/AGENTS.md の E25 の 2・docs/design/viewer.md の 6.6）。

- --ja-import は、置き場が無い時と拒んだ訳が在る時に 0 でない値で終わる（取り込めた訳は取り込む）
- --ja-import と --ja-prune はページを書かない（出力の名を添えても）
- --ja-batches の置き場が工場の clone の下なら、何も書かずに止まる
- 出力の HTML が無ければ止まる
- 飛んだノードに図の当たる所（at）を付けても、飛んだ時刻（time）は残る。前は時刻も at の名で持っていて、当てる時に上書きされて
  再生の帯から飛んだノードが消えていた（#906 のレビュー）
- 記録と会話の字に片割れのサロゲート（JSON の \\ud83d だけ）が在っても、ページを落ちずに書く（字は置き換える）

試験は一時のフォルダに木と控えと置き場を組み（tests/viewer/test_ja.py の Base）、利用者の環境の置き場を一時のフォルダへ向ける。
飛んだノードは一時のフォルダに小さな DB と記録を作り、今の木の図に当てる。
"""
import contextlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.viewer.test_ja import HEAD, OTHER, Base
from bin._lib import isolate
from viewer import flowview
from viewer.src import ja, runread


class FlowviewCase(Base):
    def setUp(self):
        super().setUp()
        patch = mock.patch.dict(os.environ, self.env)
        patch.start()
        self.addCleanup(patch.stop)
        self.out = self.tmp / "out" / "page.html"

    def main(self, *argv: str) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            try:
                code = flowview.main(list(argv))
            except SystemExit as stop:
                code = stop.code
        return code, err.getvalue()

    def test_import_from_a_missing_folder_fails(self):
        code, err = self.main("--ja-import", str(self.tmp / "nowhere"), str(self.out))
        self.assertNotEqual(code, 0)
        self.assertIn("nowhere", err)
        self.assertFalse(self.repo.exists())
        self.assertFalse(self.out.exists())

    def test_import_with_a_refused_translation_fails_but_keeps_the_good_ones(self):
        folder = self.tmp / "b"
        ja.export({ja.key(HEAD): HEAD, ja.key(OTHER): OTHER}, folder)
        (folder / "batch-0.ja.txt").write_text(f"%%% {ja.key(HEAD)}\n{{file}} を読む。\n%%% {ja.key(OTHER)}\n{{lost}} 会話から来た。\n",
                                               encoding="utf-8")
        code, err = self.main("--ja-import", str(folder))
        self.assertNotEqual(code, 0)
        self.assertIn(ja.key(OTHER), err)
        self.assertEqual(list(ja._load(self.repo)), [ja.key(HEAD)])

    def test_prune_writes_no_page(self):
        code, _ = self.main("--ja-prune", str(self.out))
        self.assertEqual(code, 0)
        self.assertFalse(self.out.exists())

    def test_batches_in_the_clone_are_refused(self):
        inside = flowview.ROOT / "viewer-batches-must-not-be-written"
        code, err = self.main("--ja-batches", str(inside), str(self.out))
        self.assertEqual(code, 2)
        self.assertIn("clone", err)
        self.assertFalse(inside.exists())
        self.assertFalse(self.out.exists())

    def test_page_needs_an_output(self):
        code, err = self.main()
        self.assertEqual(code, 2)
        self.assertIn("出力の HTML", err)

    def test_a_lone_surrogate_does_not_stop_the_page(self):
        home, rid = self.tmp / "home", "run-odd"
        db = home / isolate.DIRS["ARCHON_HOME"] / runread.DB_FILE
        db.parent.mkdir(parents=True)
        con = sqlite3.connect(db)
        con.execute(f"create table {runread.RUN_TABLE} ({', '.join(runread.RUN_COLUMNS)})")
        con.execute(f"create table {runread.EVENT_TABLE} ({', '.join(runread.EVENT_COLUMNS)})")
        con.execute(f"insert into {runread.RUN_TABLE} (id, workflow_name, status, parent_run_id, started_at, output_root, metadata) "
                    "values (?, 'g', 'failed', null, '2026-10-25 01:00:00', ?, '{}')", (rid, str(home)))
        con.commit()
        con.close()
        node = {"step": "a", runread.EXECUTION: {"path": "a", "invocation": {"id": "a"}, "binding": {"sessionPreview": "sess"}}}
        log = home / runread.LOGS / f"{rid}.jsonl"
        log.parent.mkdir()
        log.write_text("\n".join(json.dumps({**node, "type": kind, "ts": ts, "error": "ab\ud83d"})
                                 for kind, ts in (("node_start", "2026-10-25T01:00:00.000Z"), ("node_error", "2026-10-25T01:00:01.000Z"))),
                       encoding="utf-8")
        talk = home / isolate.DIRS["CLAUDE_CONFIG_DIR"] / "projects" / "x" / "sess.jsonl"
        talk.parent.mkdir(parents=True)
        talk.write_text(json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t", "content": "ab\ud83d"}]}}),
                        encoding="utf-8")
        with mock.patch.object(flowview.launcher, "target_root", lambda target, here: Path(target)), \
                mock.patch.object(flowview.launcher, "run_home", lambda user, root: home):
            code, err = self.main("--target", str(self.tmp), "--run", rid, str(self.out))
        self.assertEqual(code, 0, err)
        self.assertIn(runread.REPLACEMENT, self.out.read_text(encoding="utf-8"))

class PlaceCase(unittest.TestCase):
    def test_a_skipped_node_keeps_its_time_after_it_is_placed(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root, rid, ts = Path(tmp.name), "run-skip", "2026-10-25T01:50:54.377Z"
        graphs = flowview.tree_shape()["graphs"]
        node = graphs["line"]["items"][0]["id"]
        con = sqlite3.connect(root / runread.DB_FILE)
        con.execute(f"create table {runread.RUN_TABLE} ({', '.join(runread.RUN_COLUMNS)})")
        con.execute(f"create table {runread.EVENT_TABLE} ({', '.join(runread.EVENT_COLUMNS)})")
        con.execute(f"insert into {runread.RUN_TABLE} (id, workflow_name, status, parent_run_id, started_at, output_root, metadata) "
                    "values (?, ?, 'completed', null, '2026-10-25 01:50:54', ?, '{}')", (rid, graphs["line"]["name"], str(root)))
        con.commit()
        con.close()
        log = root / runread.LOGS / f"{rid}.jsonl"
        log.parent.mkdir()
        log.write_text(json.dumps({"type": "node_skipped", "ts": ts, "step": node, runread.EXECUTION: {"path": node}}) + "\n",
                       encoding="utf-8")
        run = runread.run(root / runread.DB_FILE, rid)
        self.assertEqual(flowview.unmatched(graphs, run), [])
        self.assertEqual([(s["time"], s["at"]["node"]) for s in run["skipped"]], [(ts, node)])


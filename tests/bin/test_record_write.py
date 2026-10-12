"""書き込みの記録のフック（bin/_lib/record-write.py）と、その置き場の決め方（lib/writelog.log_path）の検査。

元は今の works の works/tests/test_writes.py の TestHook（同じ名の試験）。フックの設定は包み（adapter.hook_settings）でなく
隔離した設定の settings.json（toolset.recorder_row）に置き、置き場は根の下の作業の場ごと（CLAUDE_PROJECT_DIR、無ければ入力の cwd）。
- 設定: PostToolUse:Edit|Write|NotebookEdit に record-write.py を根つきで足す
- 記録器: Edit・Write・NotebookEdit で 1 行（書いた後の sha）、ほかの道具・根の無い起動は 1 バイトも書かない
- 下請け（Agent の子）の書き込みも同じ記録に載り、突き合わせ（lib/writes.py）を申告なしに通る
"""
import hashlib
import json
import os
import pathlib
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CORE = ROOT / "bin" / "_lib"
RECORDER = CORE / "record-write.py"
SEED = ROOT / "tests" / "e2e" / "target-seed"
sys.dont_write_bytecode = True
sys.path.insert(0, str(CORE))
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))

import toolset  # noqa: E402
import writelog  # noqa: E402
import writes  # noqa: E402
from tests.bin import hermetic  # noqa: E402
from tests.bin.gitkit import committed_copy  # noqa: E402


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


class TestHook(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(os.path.realpath(tmp.name))
        self.root = self.tmp / "works-writes"
        self.work = self.tmp / "work"
        self.work.mkdir()

    def run_recorder(self, event, *, root=None, project=None):
        env = hermetic.child_env(PYTHONDONTWRITEBYTECODE="1")
        if project is not None:
            env["CLAUDE_PROJECT_DIR"] = str(project)
        return subprocess.run([sys.executable, str(RECORDER), str(self.root if root is None else root)],
                              input=event if isinstance(event, str) else json.dumps(event), text=True, encoding="utf-8",
                              capture_output=True, env=env)

    def rows(self, cwd=None):
        log = writelog.log_path(self.root, cwd or self.work)
        return [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines()]

    def test_hook_settings_record_edit_and_write(self):
        row = toolset.recorder_row(self.tmp / "cfg")
        self.assertEqual(row["matcher"], "Edit|Write|NotebookEdit")
        self.assertEqual(row["hooks"], [{"type": "command", "command": shlex.join(
            (sys.executable, str(RECORDER), str(self.tmp / "cfg" / writelog.ROOT)))}])

    def test_recorder_writes_path_and_sha_after_write(self):
        self.root.mkdir()
        f = self.work / "a.py"
        f.write_text("x = 1\n", encoding="utf-8")
        for tool in ("Edit", "Write"):
            r = self.run_recorder({"tool_name": tool, "tool_input": {"file_path": str(f)}, "session_id": "s",
                                   "tool_use_id": "toolu_1", "cwd": str(self.work)})
            self.assertEqual(r.returncode, 0, r.stderr)
        self.run_recorder({"tool_name": "NotebookEdit", "tool_input": {"notebook_path": str(f)}, "cwd": str(self.work)})
        rows = self.rows()
        self.assertEqual([r["tool_name"] for r in rows], ["Edit", "Write", "NotebookEdit"])
        self.assertEqual({r["path"] for r in rows}, {os.path.realpath(str(f))})
        self.assertEqual({r["file_sha"] for r in rows}, {sha(f)})

    def test_subagent_write_lands_in_the_same_record(self):
        """修正の形 g1 の下請け（修正役が Agent で起こす子）の Edit・Write も、修正役と同じ記録に載り、突き合わせを通る（強み 5:
        書き込みの出どころ）。Claude Code は設定の PostToolUse のフックを subagent の道具の呼び出しでも起こし、入力に agent_id を
        載せる。子の cwd が別でも、置き場は起動の作業の場（CLAUDE_PROJECT_DIR）で決まる"""
        repo = self.tmp / "repo"
        rev = committed_copy(repo, SEED)
        self.root.mkdir()
        parent, child = repo / "stats.py", repo / "test_stats.py"
        parent.write_text("by the fix role\n", encoding="utf-8")
        child.write_text("by the subagent\n", encoding="utf-8")
        for path, agent in ((parent, None), (child, "a6562aad50ab27481")):
            ev = {"tool_name": "Edit" if agent is None else "Write", "tool_input": {"file_path": str(path)},
                  "session_id": "s-1", "tool_use_id": "toolu_1", "cwd": str(repo if agent is None else self.tmp)}
            if agent:
                ev.update(agent_id=agent, agent_type="general-purpose")
            self.assertEqual(self.run_recorder(ev, project=repo).returncode, 0)
        rows = self.rows(repo)
        self.assertEqual([(r["path"], r["agent_id"]) for r in rows],
                         [(os.path.realpath(str(parent)), None), (os.path.realpath(str(child)), "a6562aad50ab27481")])
        got = writes.check({"changes": []}, repo, writes.changed(repo, rev), writelog.log_path(self.root, repo))
        self.assertEqual((got["problems"], got["note"]), ([], ""), "申告なしに、記録だけで通る")

    def test_recorder_writes_nothing_without_sink_or_for_other_tools(self):
        f = self.work / "a.py"
        f.write_text("x\n", encoding="utf-8")
        ev = {"tool_name": "Write", "tool_input": {"file_path": str(f)}, "cwd": str(self.work)}
        self.assertEqual(self.run_recorder(ev).returncode, 0)
        self.assertFalse(self.root.exists())
        self.root.mkdir()
        for ev in ({"tool_name": "Read", "tool_input": {"file_path": str(f)}, "cwd": str(self.work)},
                   {"tool_name": "Bash", "cwd": str(self.work)}, "not json",
                   {"tool_name": "Write", "tool_input": {"file_path": str(f)}}):   # 作業の場が分からない
            self.assertEqual(self.run_recorder(ev).returncode, 0)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_log_path_is_the_one_lib_rule(self):
        """フックが書いた所 == lib の log_path(根, 作業の場)。作業の場は実パスで比べる（symlink の綴りでも同じ所）"""
        self.root.mkdir()
        link = self.tmp / "link"
        link.symlink_to(self.work)
        f = self.work / "a.py"
        f.write_text("x\n", encoding="utf-8")
        self.run_recorder({"tool_name": "Write", "tool_input": {"file_path": str(f)}, "cwd": str(link)})
        self.assertEqual([p for p in self.root.rglob("*") if p.is_file()], [writelog.log_path(self.root, self.work)])
        self.assertEqual(writelog.log_path(self.root, link), writelog.log_path(self.root, self.work))
        self.assertNotEqual(writelog.log_path(self.root, self.tmp), writelog.log_path(self.root, self.work))


if __name__ == "__main__":
    unittest.main()

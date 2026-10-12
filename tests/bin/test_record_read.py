"""読んだ証拠のフック（bin/_lib/record-read.py）と、その置き場の決め方（lib/reads.reads_path）の検査。

元は今の works の works/tests/test_adapter.py の test_read_hook_records_file_and_sha・test_recorder_writes_nothing_without_sink・
test_record_read_copy_differs_only_in_sink（同じ名の試験）。置き場は包みの置き場（adapter.reads_dir）でなく、コマンドの 1 つ目の
引数の根の下の作業の場ごと（CLAUDE_PROJECT_DIR、無ければ入力の cwd）。
- 記録器: Read で 1 行（path・sha・部分読みか）。Agent・WebFetch・WebSearch は path の無い行（入力の 1 欄だけ）、ほかの道具と
  根の無い起動は 1 バイトも書かない
- 写し: 元の record-read.py と違うのは書く先を決める boards() と、Read の外の道具の行（other_tool と main の頭の分かれ）と、
  READ_CAP の一致を見る所の名指しだけ。READ_CAP は読む側（engine.util）と同じ値
"""
import ast
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
RECORDER = ROOT / "bin" / "_lib" / "record-read.py"
sys.dont_write_bytecode = True
for p in (ROOT / "lib", ROOT / "lib" / "graphloops"):
    if str(p) not in sys.path:
        sys.path.append(str(p))

import reads  # noqa: E402
from engine import util  # noqa: E402
from tests.bin import hermetic  # noqa: E402

# 元: raiki61/claude-plugins の 2aa7c66cf7abe1fe09699ac2942d107123214168 の works/.shared/core/record-read.py の sha256
# （boards() と、Read の外の道具の行を除いた残りの字の）
ORIGINAL_OUTSIDE_SHA256 = "04fde608ff0d3729267a23bbe32742867af7067214072e4f7ee9915dc03c5970"


class TestHook(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(os.path.realpath(tmp.name))
        self.root = self.tmp / reads.ROOT
        self.root.mkdir()
        self.work = self.tmp / "work"
        self.work.mkdir()
        self.doc = self.work / "doc.md"
        self.doc.write_text("読む文書\n", encoding="utf-8")

    def run_recorder(self, event, *, root=None, project=None):
        env = hermetic.child_env(PYTHONDONTWRITEBYTECODE="1")
        env.pop("CLAUDE_PROJECT_DIR", None)
        if project is not None:
            env["CLAUDE_PROJECT_DIR"] = str(project)
        args = [] if root == "" else [str(self.root if root is None else root)]
        return subprocess.run([sys.executable, str(RECORDER), *args], input=json.dumps(event), text=True, encoding="utf-8",
                              capture_output=True, env=env, cwd=str(self.work))

    def event(self, tool="Read", **tool_input):
        return {"session_id": "s-1", "tool_name": tool, "tool_input": tool_input or {"file_path": str(self.doc)},
                "tool_use_id": "toolu_x", "cwd": str(self.work), "hook_event_name": "PostToolUse"}

    def rows(self, cwd=None):
        log = reads.reads_path(self.root, cwd or self.work)
        return [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines()]

    def test_read_hook_records_file_and_sha(self):
        h = self.run_recorder(self.event())
        self.assertEqual(h.returncode, 0, h.stderr)
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["path"], str(self.doc.resolve()))
        self.assertEqual(rows[0]["file_sha"], hashlib.sha256(self.doc.read_bytes()).hexdigest())
        self.assertEqual((rows[0]["session_id"], rows[0]["tool_use_id"], rows[0]["partial"]), ("s-1", "toolu_x", False))
        log = reads.reads_path(self.root, self.work)
        self.assertEqual(util.hook_evidence(log.parent, str(self.doc))[0], "read")
        self.doc.write_text("書き換えた\n", encoding="utf-8")
        self.assertEqual(util.hook_evidence(log.parent, str(self.doc))[0], "stale")

    def test_partial_read_is_marked(self):
        self.run_recorder(self.event(file_path=str(self.doc), offset=1))
        self.assertEqual([(r["partial"], r["partial_why"]) for r in self.rows()], [(True, "range")])

    def test_web_and_agent_calls_have_no_path(self):
        for tool, given in (("WebFetch", {"url": "https://example.org/a", "prompt": "要点"}),
                            ("WebSearch", {"query": "statistics mean 空の列"}),
                            ("Agent", {"subagent_type": "general-purpose", "prompt": "項目 1 を見よ"})):
            self.assertEqual(self.run_recorder(self.event(tool, **given)).returncode, 0)
        rows = self.rows()
        self.assertEqual([(r["tool_name"], r["input"]) for r in rows],
                         [("WebFetch", "https://example.org/a"), ("WebSearch", "statistics mean 空の列"),
                          ("Agent", "general-purpose")])
        self.assertTrue(all("path" not in r and r["tool_use_id"] == "toolu_x" for r in rows))

    def test_other_tools_write_nothing(self):
        for tool in ("Grep", "Edit", "Bash"):
            self.run_recorder(self.event(tool, file_path=str(self.doc)))
        self.assertFalse(reads.reads_path(self.root, self.work).exists())

    def test_recorder_writes_nothing_without_sink(self):
        for root in ("", self.tmp / "missing-dir"):
            h = self.run_recorder(self.event(), root=root)
            self.assertEqual(h.returncode, 0, h.stderr)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_reads_path_is_the_one_lib_rule(self):
        """書く先は CLAUDE_PROJECT_DIR（無ければ入力の cwd）の lib/reads.reads_path。読む側（plan-reads・review-reads）も同じ口で引く"""
        project = self.tmp / "project"
        project.mkdir()
        self.run_recorder(self.event(), project=project)
        self.assertEqual(len(self.rows(project)), 1)
        self.assertFalse(reads.reads_path(self.root, self.work).exists())
        self.assertEqual(reads.reads_path(self.root, project).parent.parent, self.root)

    def test_record_read_copy_differs_only_in_sink(self):
        """record-read.py は今の works の record-read.py の写しで、書く先を決める boards() と Read の外の道具の行だけを替えた"""
        self.assertEqual(hashlib.sha256(outside_changes(RECORDER.read_text(encoding="utf-8")).encode("utf-8")).hexdigest(),
                         ORIGINAL_OUTSIDE_SHA256)

    def test_read_cap_is_the_engine_one(self):
        """記録器の上限が読む側と違えば、間の大きさの文書は sha の無い行になり「読んだ」が partial に化ける"""
        tree = ast.parse(RECORDER.read_text(encoding="utf-8"))
        caps = [n.value for n in tree.body if isinstance(n, ast.Assign) and [ast.unparse(t) for t in n.targets] == ["READ_CAP"]]
        self.assertEqual([ast.literal_eval(v) for v in caps], [util.READ_CAP])


def outside_changes(text: str) -> str:
    """boards() の本体・other_tool・import の足し・main の頭の分かれ・記録の名と時刻の形の字・READ_CAP の一致を見る所の名を、元の字に
    戻して外し、頭の説明の文（今の works の置き場の言葉を直した。bin/AGENTS.md の E15）も外した残り"""
    head, rest = text.split("\ndef boards(", 1)
    text = head + rest[rest.index("\nREAD_CAP = "):]
    text = text.replace('\nsys.dont_write_bytecode = True\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "lib"))'
                        "\nimport reads  # noqa: E402\n", "")
    head, rest = text.split("\ndef other_tool(", 1)
    text = head + rest[rest.index("\ndef main():"):]
    text = text.replace('    if not isinstance(d, dict):\n        return 0\n    if d.get("tool_name") in reads.WEB_INPUTS:\n'
                        '        return other_tool(d)\n    if d.get("tool_name") != "Read":\n',
                        '    if not isinstance(d, dict) or d.get("tool_name") != "Read":\n')
    text = text.replace("time.strftime(reads.TS_FORMAT)", 'time.strftime("%Y-%m-%dT%H:%M:%S")')
    text = text.replace('open(b / reads.LOG, "a"', 'open(b / "reads.jsonl", "a"')
    text = text.replace("一致は tests/bin/test_record_read.py が見る", "一致は simulate.py の腕が見る")
    return text.split('"""', 2)[2]


if __name__ == "__main__":
    unittest.main()

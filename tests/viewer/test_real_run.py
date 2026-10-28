"""見る道具が本物の run を読める（docs/design/viewer.md の照らしの 3。持ち主の決め light-in-loop で、Archon を起こすので CI だけで回る）。

止めた Archon で小さな graph（include で葉の block を取り込み、1 つのノードが落ちる）を 1 回回し、見る道具の入口の build で読む。
手書きの DB や記録の見本は作らない（見本は Archon の形から外れても緑のままになる。docs/design/test-double-fidelity.md の型）。

- 読めなかった行（知らない型の行・ノードに当たらない道具の出来事）が 0、記録の無い run が 0
- 図は run の写しから作り、図に当たらないノードが 0
- run の一覧に、その run が終わりの状態で 1 行在る
- 落ちたノードの誤りの字が出来事に在る
"""
import pathlib
import shutil
import tempfile
import unittest

from tests import archon
from tests.blocks import kit
from viewer import flowview

HEAD = '# /// script\n# requires-python = ">=3.12"\n# dependencies = []\n# ///\n'
PREFIX = flowview.PACK["name_prefix"]
FLOWS = {
    f"seen/{PREFIX}seen.yaml": f"""name: {PREFIX}seen
description: 見る道具に本物の run の記録を渡す試し
nodes:
  - id: make
    script: make
    runtime: uv
  - id: leaf
    include: {PREFIX}seen-leaf
    depends_on: [make]
  - id: boom
    script: boom
    runtime: uv
    depends_on: [leaf]
""",
    "seen/scripts/make.py": HEAD + 'import json\nprint(json.dumps({"a": 1}))\n',
    "seen/scripts/boom.py": HEAD + 'import sys\nsys.exit("boom")\n',
    f"seen-leaf/{PREFIX}seen-leaf.yaml": f"""name: {PREFIX}seen-leaf
description: 取り込まれる葉
nodes:
  - id: rounds
    loop_group:
      max_iterations: 1
      until_bash: "true"
      nodes:
        - id: step
          script: step
          runtime: uv
""",
    "seen-leaf/scripts/step.py": HEAD + 'print("{}")\n',
}


class RealRunCase(unittest.TestCase):
    def test_viewer_reads_a_real_run(self):
        if shutil.which("uv") is None:
            self.skipTest("uv が無い")
        with tempfile.TemporaryDirectory() as tmp:
            flows = pathlib.Path(tmp)
            for rel, text in FLOWS.items():
                (flows / rel).parent.mkdir(parents=True, exist_ok=True)
                (flows / rel).write_text(text, encoding="utf-8")
            with archon.tree(["seen", "seen-leaf"], workflows=flows, shared=kit.SHARED) as tree:
                done = archon.archon(tree, "workflow", "run", f"{PREFIX}seen", "--no-worktree", "--cwd", str(tree))
                # 家は archon.archon が木の横に置く archon-home（isolate.DIRS の名）。殻と同じく WORKS_FACTORY_HOME で向ける
                data = flowview.build(str(tree), "", {"WORKS_FACTORY_HOME": str(tree.parent), "HOME": str(tree.parent)}, tree)
        run = data["run"]
        self.assertIsNotNone(run, f"{done.stdout}{done.stderr}")
        self.assertEqual((run["unread"], run["missing_logs"]), ({}, []))
        self.assertEqual((data["shape_from"], data["unmatched"]), ("run-copy", []))
        self.assertEqual([(r["id"], r["status"]) for r in data["runs"]], [(run["id"], "failed")])
        at = {e["at"]["graph"] + "/" + e["at"]["node"] for e in run["events"]}
        self.assertLessEqual({"seen/make", "seen-leaf/rounds/step", "seen/boom"}, at)
        self.assertIn("boom", next(e for e in run["events"] if e["tokens"] == ["boom"])["error"])


if __name__ == "__main__":
    unittest.main()

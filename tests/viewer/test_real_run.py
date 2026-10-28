"""見る道具が本物の run を読める（docs/design/viewer.md の照らしの 3。持ち主の決め light-in-loop で、Archon を起こすので CI だけで回る）。

止めた Archon で小さな graph（include で葉の block を取り込み、1 つのノードが落ちる）を 1 回回し、見る道具の入口の build で読む。
手書きの DB や記録の見本は作らない（見本は Archon の形から外れても緑のままになる。docs/design/test-double-fidelity.md の型）。

- 読めなかった行（知らない型の行・ノードに当たらない道具の出来事）が 0、記録の無い run が 0
- 図は run の写しから作り、図に当たらないノードが 0
- run の一覧に、その run が終わりの状態で 1 行在る
- 落ちたノードの誤りの字が出来事に在る
- 承認ノードで止まった run は待ちと答える命令を出し、答えが入って次へ進む前の間（Archon は答えを run の metadata の wait に書くだけで、
  状態は paused のまま node_completed も書かない。Archon の runAttention はこの間を待ちに数えない）と、待ちのまま止めた後（Archon は
  node_completed を書かず、run を cancelled にする）は、どちらも出さない。答えだけを入れた間は、Archon の CLI がすぐ次へ進めて残らないので、
  Archon の答えを書く口（packages/core/src/db/workflow-run-waits.ts の answerAttentionWait）を bun で直に呼んで作る
- 答えた承認ノード（wait: attention）は、出来事の出力に答え（decision と添えた字 text）を持ち、その run のログに gate_decision の行が無い
  （runread の UNREAD_ROWS の gate_decision の訳。読まない型の行は数えずに飛ばすので、unread が空でも行が無いことは言えない）

待ちの消し方は、名の照らし（tests/viewer/test_archon_names.py）では捕まらない。名が源に在っても、どの状態と欄の組で待ちが終わるかは
Archon の振る舞いの意味の話なので、本物の run で照らす。
"""
import json
import pathlib
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

from tests import archon
from tests.blocks import kit
from viewer import flowview
from viewer.src import runread

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
    f"seen-gate/{PREFIX}seen-gate.yaml": f"""name: {PREFIX}seen-gate
description: 承認ノードで止まり、待ちのまま止められる試し
nodes:
  - id: ask
    wait:
      attention: 進めるか
      form: select
      options: [{{id: approve}}]
  - id: after
    script: step
    runtime: uv
    depends_on: [ask]
""",
    "seen-gate/scripts/step.py": HEAD + 'print("{}")\n',
}
# 答えだけを書き、次へ進めない（Archon の answerRun が store.answerAttentionWait に渡す形）
ANSWER_ONLY = """import { answerAttentionWait } from '%s';
const [id, pauseId] = process.argv.slice(2);
const done = await answerAttentionWait(id, { pauseId, answer: { decision: 'approve', text: 'よし' }, answeredVia: 'cli',
  answeredAt: new Date().toISOString() });
console.log(JSON.stringify(done));
process.exit(done.answered ? 0 : 1);
"""


def answer_only(tree: pathlib.Path, run_id: str) -> subprocess.CompletedProcess:
    """止まっている run の承認ノードに、Archon の口で答えだけを書く（次へ進む前の間を残す）"""
    db = tree.parent / "archon-home" / runread.DB_FILE
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as con:
        meta = json.loads(con.execute(f"select metadata from {runread.RUN_TABLE} where id = ?", (run_id,)).fetchone()[0])
    script = tree.parent / "answer-only.ts"
    script.write_text(ANSWER_ONLY % (archon.source() / "packages/core/src/db/workflow-run-waits.ts"), encoding="utf-8")
    head, env = archon.command(tree)
    return subprocess.run([head[0], str(script), run_id, meta["wait"]["pauseId"]], cwd=tree, env=env, capture_output=True, text=True,
                          encoding="utf-8")


def rows(tree: pathlib.Path, run_id: str) -> list[str]:
    """run のログの行の型"""
    with sqlite3.connect(f"file:{tree.parent / 'archon-home' / runread.DB_FILE}?mode=ro", uri=True) as con:
        root = con.execute(f"select output_root from {runread.RUN_TABLE} where id = ?", (run_id,)).fetchone()[0]
    log = pathlib.Path(root) / runread.LOGS / f"{run_id}.jsonl"
    return [json.loads(line).get("type") for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


class RealRunCase(unittest.TestCase):
    def test_viewer_reads_a_real_run(self):
        if shutil.which("uv") is None:
            self.skipTest("uv が無い")
        with tempfile.TemporaryDirectory() as tmp:
            flows = pathlib.Path(tmp)
            for rel, text in FLOWS.items():
                (flows / rel).parent.mkdir(parents=True, exist_ok=True)
                (flows / rel).write_text(text, encoding="utf-8")
            with archon.tree(["seen", "seen-leaf", "seen-gate"], workflows=flows, shared=kit.SHARED) as tree:
                # 家は archon.archon が木の横に置く archon-home（isolate.DIRS の名）。殻と同じく WORKS_FACTORY_HOME で向ける
                user = {"WORKS_FACTORY_HOME": str(tree.parent), "HOME": str(tree.parent)}
                gate = archon.archon(tree, "workflow", "run", f"{PREFIX}seen-gate", "--no-worktree", "--cwd", str(tree))
                paused = flowview.build(str(tree), "", user, tree)
                answering = answer_only(tree, paused["run"]["id"]) if paused["run"] else None
                answered_only = flowview.build(str(tree), paused["run"]["id"] if paused["run"] else "", user, tree)
                abandoned = archon.archon(tree, "workflow", "abandon", paused["run"]["id"], "--cwd", str(tree)) if paused["run"] else None
                stopped = flowview.build(str(tree), paused["run"]["id"] if paused["run"] else "", user, tree)
                archon.archon(tree, "workflow", "run", f"{PREFIX}seen-gate", "--no-worktree", "--cwd", str(tree))
                again = flowview.build(str(tree), "", user, tree)
                approved = archon.archon(tree, "workflow", "approve", again["run"]["id"], "よし", "--cwd", str(tree))
                answered = flowview.build(str(tree), again["run"]["id"], user, tree)
                answered_rows = rows(tree, again["run"]["id"])
                done = archon.archon(tree, "workflow", "run", f"{PREFIX}seen", "--no-worktree", "--cwd", str(tree))
                data = flowview.build(str(tree), "", user, tree)
        self.assertIsNotNone(paused["run"], f"{gate.stdout}{gate.stderr}")
        self.assertEqual((paused["run"]["status"], paused["run"]["waiting"], paused["runs"][0]["waiting"]), ("paused", ["ask"], ["ask"]))
        self.assertIn(f"respond {paused['run']['id']}", paused["run"]["answer"])
        self.assertEqual(answering.returncode, 0, f"{answering.stdout}{answering.stderr}")
        self.assertEqual((answered_only["run"]["status"], answered_only["run"]["waiting"], answered_only["run"]["answer"],
                          answered_only["runs"][0]["waiting"]), ("paused", [], "", []))
        self.assertEqual(stopped["run"]["status"], "cancelled", f"{abandoned.stdout}{abandoned.stderr}")
        self.assertEqual((stopped["run"]["waiting"], stopped["run"]["answer"], stopped["runs"][0]["waiting"]), ([], "", []))
        self.assertEqual(answered["run"]["status"], "completed", f"{approved.stdout}{approved.stderr}")
        self.assertEqual((answered["run"]["unread"], answered["run"]["waiting"], answered["run"]["answer"]), ({}, [], ""))
        gate = next(e for e in answered["run"]["events"] if e["tokens"] == ["ask"])
        self.assertEqual(json.loads(gate["output"]), {"decision": "approve", "text": "よし"})
        self.assertIn("node_complete", answered_rows)
        self.assertNotIn("gate_decision", answered_rows)
        run = data["run"]
        self.assertIsNotNone(run, f"{done.stdout}{done.stderr}")
        self.assertEqual((run["unread"], run["missing_logs"]), ({}, []))
        self.assertEqual((data["shape_from"], data["unmatched"]), ("run-copy", []))
        self.assertEqual([(r["id"], r["status"]) for r in data["runs"]], [(run["id"], "failed"), (again["run"]["id"], "completed"), (paused["run"]["id"], "cancelled")])
        at = {e["at"]["graph"] + "/" + e["at"]["node"] for e in run["events"]}
        self.assertLessEqual({"seen/make", "seen-leaf/rounds/step", "seen/boom"}, at)
        self.assertIn("boom", next(e for e in run["events"] if e["tokens"] == ["boom"])["error"])


if __name__ == "__main__":
    unittest.main()

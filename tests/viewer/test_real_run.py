"""見る道具の読む部品が本物の run を読める（docs/design/viewer.md の照らしの 3。持ち主の決め light-in-loop で、Archon を起こすので CI だけで回る）。

止めた Archon で小さな graph（include で葉の block を取り込み、1 つのノードが落ちる）を 1 回回し、見る道具の読む部品（src/runread.py）と
入口 runtrace.py の read で読む。手書きの DB や記録の見本は作らない（見本は Archon の形から外れても緑のままになる。
docs/design/test-double-fidelity.md の型）。

- 読めなかった行（知らない型の行）が 0
- 作りは run の写しから読む（runread.copy が指す写しの中の pack の置き場が、本物の Archon の置き方と合う）
- include の中のノードの出来事が、外の graph から入る道（通った include のノード）の token を持つ
- 落ちたノードの誤りの字が出来事に在る
- 名指さずに開いた一番新しい run が、落ちた状態で読める
- 答えた承認ノード（wait: attention）は、出来事の出力に答え（decision と添えた字 text）を持ち、その run のログに gate_decision の行が無い
  （runread の UNREAD_ROWS の gate_decision の訳。読まない型の行は数えずに飛ばすので、unread が空でも行が無いことは言えない）
"""
import json
import pathlib
import shutil
import tempfile
import unittest

from tests import archon
from tests.blocks import kit
from viewer import runtrace
from viewer.src import runread

HEAD = '# /// script\n# requires-python = ">=3.12"\n# dependencies = []\n# ///\n'
PREFIX = runtrace.PACK["name_prefix"]
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
  - id: talk
    script: talk
    runtime: uv
    depends_on: [rounds]
""",
    "seen-leaf/scripts/step.py": HEAD + 'print("{}")\n',
    # 指示を組む prep と同じ口（prompt.emit）で、include の中の place に指示を書く
    "seen-leaf/scripts/talk.py": HEAD + """import json, sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared")]
import prompt
print(json.dumps(prompt.emit("talk", {"name": "x{y}"}, {"web": True}, prompt.round_of("talk"))))
""",
    "seen-leaf/prompts/talk.md": "Say hello to {name} and describe what this factory makes today.\n<!-- if web -->\nOn\n<!-- end web -->\n{shared:lang-default}\n",
    f"seen-gate/{PREFIX}seen-gate.yaml": f"""name: {PREFIX}seen-gate
description: 承認ノードで止まり、答えを受けて進む試し
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
def read(tree: pathlib.Path, wanted: str, user: dict) -> dict:
    """選んだ run（wanted が空なら一番新しい親の run）の読み。全部の読み（作り・会話・段）は runtrace.read"""
    return runtrace.read(str(tree), wanted, user, tree)


def rows(tree: pathlib.Path, run_id: str) -> list[str]:
    """run のログの行の型"""
    with runread.connect(tree.parent / 'archon-home' / runread.DB_FILE) as con:
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
                again = read(tree, "", user)
                approved = archon.archon(tree, "workflow", "approve", again["run"]["id"], "よし", "--cwd", str(tree))
                answered = read(tree, again["run"]["id"], user)
                answered_rows = rows(tree, again["run"]["id"])
                done = archon.archon(tree, "workflow", "run", f"{PREFIX}seen", "--no-worktree", "--cwd", str(tree))
                data = read(tree, "", user)
        self.assertIsNotNone(again["run"], f"{gate.stdout}{gate.stderr}")
        self.assertEqual(answered["run"]["status"], "completed", f"{approved.stdout}{approved.stderr}")
        self.assertEqual(answered["run"]["unread"], {})
        gate = next(e for e in answered["run"]["events"] if e["tokens"] == ["ask"])
        self.assertEqual(json.loads(gate["output"]), {"decision": "approve", "text": "よし"})
        self.assertIn("node_complete", answered_rows)
        self.assertNotIn("gate_decision", answered_rows)
        run = data["run"]
        self.assertIsNotNone(run, f"{done.stdout}{done.stderr}")
        self.assertEqual(run["unread"], {})
        # 作りは run の写しから読む（runread.copy の写しの中の pack の置き場のパスが本物の Archon と合う）
        self.assertEqual(data["shape_from"], "run-copy")
        self.assertEqual(run["status"], "failed")
        paths = {"/".join(e["tokens"]) for e in run["events"]}
        self.assertLessEqual({"make", "leaf/rounds/step", "leaf/talk", "boom"}, paths)
        self.assertIn("boom", next(e for e in run["events"] if e["tokens"] == ["boom"])["error"])


if __name__ == "__main__":
    unittest.main()

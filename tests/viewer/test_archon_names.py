"""見る道具の Archon の記録の読み（viewer/src/runread.py）が読む名が、止めた Archon（factory/pack.json の版）の源に在る
（docs/design/viewer.md の照らしの 2）。源の字を読むだけなので手元の確かめでも回る（源が無ければ tests/archon.py の absent。CI は赤）。

- ログの行の型と道具の出来事の型は、源の型の和と runread の読む型・読まない型の和がちょうど同じ（源に型が足されても消されても赤）
- run の状態は源の enum とちょうど同じ（生きている状態と答えを待つ状態はその中）
- DB の表の欄は、源の CREATE TABLE のその表の欄に在る
- 置き場の名と、DB の出来事・metadata の名は、源のその名を書くファイルに字として在る

行の中の欄（execution.path など）は、本物の run の照らし（tests/viewer/test_real_run.py）が読めたことで照らす。
"""
import re
import unittest

from tests import archon
from viewer.src import runread

LOGGER = "packages/workflows/src/logger.ts"
SETUP = "packages/workflows/src/schemas/worktree-setup.ts"
EVENTS = "packages/provider-contract/src/events.ts"
RUN_SCHEMA = "packages/workflows/src/schemas/workflow-run.ts"
SQLITE = "packages/core/src/db/adapters/sqlite.ts"
# 名 → それを字として書く源のファイル
WRITTEN = {
    f"'{runread.DB_FILE}'": "packages/core/src/db/connection.ts",
    **{f"'{name}'": "packages/paths/src/archon-paths.ts"
       for name in (runread.LOGS, runread.SOURCE, runread.ARTIFACTS, runread.RUNS_DIR, runread.WORKFLOW_FOLDER)},
    f"PROJECT_SCOPE_DIR = '{runread.PROJECT_SCOPE}'": "packages/workflows/src/workflow-source.ts",
    **{f"type: '{name}'": "packages/workflows/src/event-emitter.ts"
       for name in (runread.OUTPUT_EVENT, runread.FAILED_EVENT, runread.NODE_FAILED_EVENT, runread.SUSPENDED_EVENT)},
    **{f"{name}:": "packages/workflows/src/node-record-serialization.ts" for name in (runread.NODE_COST, runread.ACCOUNTING)},
    f"{runread.NODE_OUTPUT}": "packages/workflows/src/node-record-serialization.ts",
    f"{runread.PARENT_NODE}": "packages/workflows/src/dag-executor.ts",
    f"{runread.TOTAL_COST}:": "packages/workflows/src/dag-executor.ts",
    f"{runread.ATTEMPT_ID}:": "packages/workflows/src/schemas/provider-event.ts",
    **{f"kind: z.literal('{kind}')": "packages/workflows/src/schemas/dag-node.ts"
       for kind in (*runread.AI_KINDS, runread.WAIT_NODE, *runread.GROUP_KINDS)},
    **{name: RUN_SCHEMA for name in (f"metadata?.{runread.WAIT}", f"kind: z.literal('{runread.WAIT_KIND}')", f"{runread.WAIT_ANSWER}: attentionAnswerSchema",
                                     f"wait.owner === '{runread.WAIT_LOOP_OWNER}' ? `${{wait.nodeId}}.${{wait.bodyWaitId}}` : wait.nodeId")},
}


def literals(text: str) -> set[str]:
    return set(re.findall(r"'([a-z_-]+)'", text))


class ArchonNamesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = archon.source()

    def read(self, rel: str) -> str:
        return (self.source / rel).read_text(encoding="utf-8")

    def test_row_types_are_the_sources(self):
        union = re.search(r"export interface WorkflowEvent\b.*?\n  type:\n(.*?)\n  workflow_id:", self.read(LOGGER), re.S)[1]
        setup = re.search(r"WORKTREE_SETUP_EVENT_TYPES = \[(.*?)\]", self.read(SETUP), re.S)[1]
        self.assertIn("WorktreeSetupEvent['type']", union)
        self.assertEqual(literals(union.replace("WorktreeSetupEvent['type']", "")) | literals(setup),
                         set(runread.READ_ROWS) | set(runread.UNREAD_ROWS))

    def test_provider_event_types_are_the_sources(self):
        text = self.read(EVENTS)
        names = re.search(r"providerEventSchema = z\.discriminatedUnion\('type', \[(.*?)\]\)", text, re.S)[1]
        types = {re.search(rf"export const {name} = .*?type: z\.literal\('([a-z_]+)'\)", text, re.S)[1]
                 for name in re.findall(r"\w+", names)}
        self.assertEqual(types, set(runread.READ_EVENTS) | set(runread.UNREAD_EVENTS))

    def test_statuses_are_the_sources(self):
        found = re.search(r"workflowRunStatusSchema = z\.enum\(\[(.*?)\]\)", self.read(RUN_SCHEMA), re.S)[1]
        self.assertEqual(literals(found), set(runread.STATUSES))
        self.assertLessEqual({*runread.LIVE, runread.PAUSED, runread.FAILED}, set(runread.STATUSES))

    def test_table_columns_are_in_the_source(self):
        text = self.read(SQLITE)
        for table, columns in ((runread.RUN_TABLE, runread.RUN_COLUMNS), (runread.EVENT_TABLE, runread.EVENT_COLUMNS)):
            with self.subTest(table=table):
                body = re.search(rf"CREATE TABLE IF NOT EXISTS {table} \((.*?)\n\s*\);", text, re.S)[1]
                have = {line.split()[0] for line in body.splitlines() if line.strip()}
                self.assertLessEqual(set(columns), have)

    def test_written_names_are_in_the_source(self):
        for name, rel in WRITTEN.items():
            with self.subTest(name=name):
                self.assertIn(name, self.read(rel))


if __name__ == "__main__":
    unittest.main()

"""K6 周ごとの値（$LOOP_PREV）を本物の役で確かめる（docs/plans/2026-10-13-stage1-walking-skeleton.md の手順 6）。

筋書き（archon workflow test）は前の周の出力を渡さない（止めた Archon の dry-run.ts 795・1053-1058 行）ので、
tests/e2e/loop-prev/ の使い捨ての工程を、止めた Archon を bun で直に起こして回す。殻 bin/works-factory は
--workflow-source を拒み workflows/ だけを渡すので通さない。役を起こす（費用がかかる）ので、環境変数 WORKS_FACTORY_REAL_RUN=1 の
時だけ走り、無ければ名前つきで見送る。CI は立てないので見送る。認証は利用者の環境のまま（Claude Code のログインか ANTHROPIC_API_KEY）。
"""
import json
import os
import pathlib
import unittest

from tests import archon

E2E = pathlib.Path(__file__).resolve().parent
WORKFLOW = "works-factory-loop-prev"
REAL_RUN_ENV = "WORKS_FACTORY_REAL_RUN"


def body_outputs(events: list[dict], node: str) -> list[dict]:
    """輪の本体の節 node の周ごとの返り（周の順）"""
    done = [e for e in events if e["event_type"] == "node_completed" and e["step_name"] == f"rounds.{node}"]
    return [e["data"]["structured_output"] for e in sorted(done, key=lambda e: e["event_order"])]


class LoopPrevRealCase(unittest.TestCase):
    def setUp(self):
        if os.environ.get(REAL_RUN_ENV) != "1":
            self.skipTest(f"本物の役を起こす試験: {REAL_RUN_ENV}=1 の時だけ走る")

    def test_reason_changes_by_round(self):
        with archon.tree(["loop-prev"], workflows=E2E) as root:
            run = archon.archon(root, "workflow", "run", WORKFLOW, "--no-worktree")
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            listed = archon.archon(root, "workflow", "runs", "--json")
            runs = json.loads(listed.stdout)["runs"]
            self.assertEqual(len(runs), 1, listed.stdout)
            got = archon.archon(root, "workflow", "get", runs[0]["id"], "--json", "--verbose", "--events")
            detail = json.loads(got.stdout)
        print(json.dumps({"run": runs[0]["id"], "status": detail["status"],
                          **{n: body_outputs(detail["events"], n) for n in ("prev-reason", "echo", "round-check")}},
                         ensure_ascii=False, indent=1))
        self.assertEqual(detail["status"], "completed")
        heads, echoes, checks = (body_outputs(detail["events"], n) for n in ("prev-reason", "echo", "round-check"))
        self.assertEqual(len(heads), 2)
        self.assertEqual(heads[0]["reason"], "")
        self.assertTrue(checks[0]["reason"])
        self.assertEqual(heads[1]["reason"], checks[0]["reason"])
        self.assertEqual(echoes[1]["heard"], checks[0]["reason"])
        self.assertTrue(checks[1]["done"])


if __name__ == "__main__":
    unittest.main()

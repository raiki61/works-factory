"""K6 周ごとの値（$LOOP_PREV）を本物の Archon で確かめる（docs/plans/2026-10-13-stage1-walking-skeleton.md の手順 6）。

筋書き（archon workflow test）は前の周の出力を渡さない（止めた Archon の dry-run.ts 795・1053-1058 行）ので、
tests/e2e/loop-prev/ の使い捨ての工程を、止めた Archon を bun で直に起こして回す。殻 bin/works-factory は
--workflow-source を拒み workflows/ だけを渡すので通さない。
- LoopPrevScriptedCase: 役の節 echo を script（scripts/echo_back.py）に差し替えた写しを回す。AI も認証も要らないので CI でも走る。
- LoopPrevRealCase: 本物の役で回す。役を起こす（費用がかかる）ので、環境変数 WORKS_FACTORY_REAL_RUN=1 の時だけ走り、無ければ
  名前つきで見送る。CI は立てないので見送る。認証は利用者の環境のまま（Claude Code のログインか ANTHROPIC_API_KEY）。
"""
import json
import pathlib
import unittest

import yaml

from tests import archon
from tests.bin import hermetic
from tests.bin.gitkit import git
from tests.layers.test_archon_validate import validate

E2E = pathlib.Path(__file__).resolve().parent
FOLDER = "loop-prev"
WORKFLOW = "works-factory-loop-prev"
REAL_RUN_ENV = "WORKS_FACTORY_REAL_RUN"
NODES = ("prev-reason", "echo", "round-check")


def body_outputs(events: list[dict], node: str) -> list[dict]:
    """輪の本体の節 node の周ごとの返り（周の順）"""
    done = [e for e in events if e["event_type"] == "node_completed" and e["step_name"] == f"rounds.{node}"]
    return [e["data"]["structured_output"] for e in sorted(done, key=lambda e: e["event_order"])]


def script_the_role(root: pathlib.Path) -> None:
    """木の工程の役の節 echo を、同じ id・同じ返りの形の script の節 echo_back に替えて commit する"""
    path = root / ".archon" / "workflows" / archon.PACK["ours"]["pack"] / FOLDER / f"{WORKFLOW}.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    body = doc["nodes"][0]["loop_group"]["nodes"]
    at = next(i for i, node in enumerate(body) if node["id"] == "echo")
    role = body[at]
    body[at] = {"id": "echo", "script": "echo_back", "runtime": "uv", "mutates_checkout": False,
                "depends_on": role["depends_on"], "with": {"heard": "$prev-reason.output.reason"},
                "output_format": role["output_format"]}
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    git(root, "commit", "-q", "-am", "script the role")


class LoopPrevValidateCase(unittest.TestCase):
    """本物の回しは CI で見送るので、工程の形の崩れ（名前の script の解決・節の結び）は CI でも validate で捕まえる"""

    def test_workflow_has_no_errors_or_warnings(self):
        with archon.tree([FOLDER], workflows=E2E) as root:
            self.assertEqual(validate(root), {WORKFLOW: []})


class RoundsCase(unittest.TestCase):
    """工程を 1 度回し、周ごとの返りを印字してから、$LOOP_PREV が 1 周目の受け付けの理由を 2 周目の頭へ運んだかを照らす。
    印字を照らしより先に置くのは、赤の時に周ごとの返りを見るため"""

    def passed(self) -> dict:
        """Archon へ名指しで渡す名（親の環境は継がない）。AI も認証も要らない回しは何も渡さない"""
        return {}

    def assert_reason_changes_by_round(self, root: pathlib.Path):
        passed = self.passed()
        run = archon.archon(root, "workflow", "run", WORKFLOW, "--no-worktree", **passed)
        listed = archon.archon(root, "workflow", "runs", "--json", **passed)
        runs = json.loads(listed.stdout)["runs"]
        self.assertEqual(len(runs), 1, listed.stdout + run.stdout + run.stderr)
        got = archon.archon(root, "workflow", "get", runs[0]["id"], "--json", "--verbose", "--events", **passed)
        detail = json.loads(got.stdout)
        outputs = {node: body_outputs(detail["events"], node) for node in NODES}
        print(json.dumps({"run": runs[0]["id"], "status": detail["status"], **outputs}, ensure_ascii=False, indent=1))
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(detail["status"], "completed")
        heads, echoes, checks = (outputs[node] for node in NODES)
        self.assertEqual(len(heads), 2)
        self.assertEqual(heads[0]["reason"], "")
        self.assertTrue(checks[0]["reason"])
        self.assertEqual(heads[1]["reason"], checks[0]["reason"])
        self.assertEqual(echoes[1]["heard"], checks[0]["reason"])
        self.assertTrue(checks[1]["done"])


class LoopPrevScriptedCase(RoundsCase):
    def test_reason_changes_by_round(self):
        with archon.tree([FOLDER], workflows=E2E) as root:
            script_the_role(root)
            self.assert_reason_changes_by_round(root)


class LoopPrevRealCase(RoundsCase):
    def setUp(self):
        if hermetic.inherited(REAL_RUN_ENV).get(REAL_RUN_ENV) != "1":
            self.skipTest(f"本物の役を起こす試験: {REAL_RUN_ENV}=1 の時だけ走る")

    def passed(self) -> dict:
        """本物の役は利用者の認証で動く（Claude Code のログイン・ANTHROPIC_API_KEY・CLAUDE_CONFIG_DIR・ANTHROPIC_BASE_URL）ので、
        試験を回し始めた時の ANTHROPIC_・CLAUDE_ の頭の名を名指しで返す（試験を回す口が過程の環境から外した後も引ける）"""
        return hermetic.inherited("ANTHROPIC_", "CLAUDE_")

    def test_reason_changes_by_round(self):
        with archon.tree([FOLDER], workflows=E2E) as root:
            self.assert_reason_changes_by_round(root)


if __name__ == "__main__":
    unittest.main()

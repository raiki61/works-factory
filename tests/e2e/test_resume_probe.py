"""段 1b の U1・P1 の使い捨ての工程（tests/e2e/resume-probe/・owner-lost-probe/。AI の役は無い）を止めた Archon で照らす。

段 1b の実測の run は使い捨ての家と一緒に消えて読み戻せないので、U1（resume の後の run の id。docs/design.md）はこの試験が
CI で回し直す。P1（docs/polyfills.md）は持ち主のプロセスを止めるので手で回し、ここでは工程の形だけを validate で照らす。
"""
import json
import pathlib
import unittest

from tests import archon
from tests.layers.test_archon_validate import validate

E2E = pathlib.Path(__file__).resolve().parent
WORKFLOW = "works-factory-resume-probe"
PROBES = {"resume-probe": WORKFLOW, "owner-lost-probe": "works-factory-owner-lost-probe"}


class ProbesValidateCase(unittest.TestCase):
    def test_probes_have_no_errors_or_warnings(self):
        with archon.tree(PROBES, workflows=E2E) as root:
            self.assertEqual(validate(root), {name: [] for name in PROBES.values()})


class ResumeKeepsRunIdCase(unittest.TestCase):
    def test_resume_after_approve_continues_the_same_run(self):
        with archon.tree(["resume-probe"], workflows=E2E) as root:
            paused = archon.archon(root, "workflow", "run", WORKFLOW, "--no-worktree")
            self.assertEqual(paused.returncode, 0, paused.stdout + paused.stderr)
            [run] = json.loads(archon.archon(root, "workflow", "runs", "--json").stdout)["runs"]
            self.assertEqual(run["status"], "paused")
            approved = archon.archon(root, "workflow", "approve", run["id"], "--json")
            self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)
            resumed = archon.archon(root, "workflow", "resume", run["id"])
            self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
            runs = json.loads(archon.archon(root, "workflow", "runs", "--json").stdout)["runs"]
            detail = json.loads(archon.archon(root, "workflow", "get", run["id"], "--json", "--verbose", "--events").stdout)
        self.assertEqual([(r["id"], r["status"]) for r in runs], [(run["id"], "completed")])
        steps = [(e["event_type"], e["step_name"]) for e in detail["events"]]
        self.assertEqual(steps.count(("workflow_started", None)), 2, steps)
        self.assertIn(("node_skipped_prior_success", "first"), steps)
        self.assertIn(("node_completed", "after"), steps)
        self.assertEqual({e["workflow_run_id"] for e in detail["events"]}, {run["id"]})


if __name__ == "__main__":
    unittest.main()

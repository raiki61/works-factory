"""線の後始末の部品 bin/_lib/childsweep.py の試験。Archon は起こさず、起こす口 run に偽を差して、起こした引数と環境を照らす。"""
import json
import pathlib
import subprocess
import tempfile
import unittest

from bin._lib import childsweep, place

RUN = "1a2b3c4d-0000-4000-8000-000000000001"
OTHER = "9f8e7d6c-0000-4000-8000-000000000002"
CHECKOUT = "/runs/checkout"
OURS = f"archon/task-{RUN[:8]}-fix-groups-par-a1b2c3d4-child-"


def row(run_id: str, status: str = "completed", parent: str | None = None, **metadata) -> dict:
    return {"id": run_id, "status": status, "parent_run_id": parent, "metadata": metadata}


def child(n: int, status: str = "completed", branch: str | None = None, as_text: bool = False) -> dict:
    metadata = {"parent_node_id": "fix__groups-par", "branch_name": branch or f"{OURS}{n}"}
    found = row(f"child-{n}", status, RUN, **metadata)
    if as_text:
        found["metadata"] = json.dumps(metadata)
    return found


class FakeArchon:
    """起こした引数・環境・cwd を記録し、workflow runs には listing を、complete には枝ごとの出力を返す"""

    def __init__(self, listing, completes: dict[str, tuple[str, str]] | None = None):
        self.listing = listing
        self.completes = completes or {}
        self.calls: list[dict] = []

    def __call__(self, argv, **kwargs):
        self.calls.append({"argv": argv, **kwargs})
        command = argv[3:-2]
        if command[:2] == ["workflow", "runs"]:
            stdout = self.listing if isinstance(self.listing, str) else json.dumps(self.listing) + "\n"
            return subprocess.CompletedProcess(argv, 0, stdout, "")
        branch = command[-1]
        stdout, stderr = self.completes.get(branch, (f"\n  Completed: {branch}\n", ""))
        return subprocess.CompletedProcess(argv, 0, stdout, stderr)

    def completed(self) -> list[str]:
        return [c["argv"][-3] for c in self.calls if c["argv"][3] == "complete"]


class ChildSweepTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.source = self.tmp / "archon"
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        self.bun = bin_dir / "bun"
        self.bun.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.bun.chmod(0o755)
        self.env = {"PATH": str(bin_dir), place.SOURCE_ENV: str(self.source), "ARTIFACTS_DIR": str(self.tmp)}

    def sweep(self, archon: FakeArchon, env: dict | None = None) -> dict:
        return childsweep.sweep(RUN, CHECKOUT, self.env if env is None else env, run=archon)

    def test_selects_only_this_runs_children(self):
        archon = FakeArchon({"runs": [
            child(0),
            child(1, branch="feature/y"),
            row("child-seq", parent=RUN, parent_node_id="fix__groups-seq"),
            row("other-child", parent=OTHER, branch_name=f"archon/task-{OTHER[:8]}-fix-groups-par-x-child-0"),
            row("human", branch_name="feature/x"),
            row(RUN, "running"),
        ]})
        got = self.sweep(archon)
        self.assertEqual(archon.completed(), [f"{OURS}0"])
        self.assertEqual(got["cleaned"], [{"branch": f"{OURS}0", "run_id": "child-0", "node": "fix__groups-par"}])
        self.assertEqual([left["branch"] for left in got["left"]], ["feature/y"])
        self.assertIn("この run の子の形でない", got["left"][0]["reason"])
        self.assertEqual(got["error"], "")

    def test_run_without_children_removes_nothing(self):
        archon = FakeArchon({"runs": [row(RUN, "running"), row("human", branch_name="feature/x")]})
        self.assertEqual(self.sweep(archon), {"cleaned": [], "left": [], "error": ""})
        self.assertEqual(archon.completed(), [])

    def test_metadata_stored_as_text_is_read(self):
        archon = FakeArchon({"runs": [child(0, as_text=True), row(RUN, "running")]})
        self.assertEqual([c["branch"] for c in self.sweep(archon)["cleaned"]], [f"{OURS}0"])

    def test_list_after_log_lines_is_read(self):
        listing = {"runs": [child(0), row(RUN, "running")]}
        archon = FakeArchon('{"level":40,"msg":"warn"}\n' + json.dumps(listing, indent=2) + "\n")
        self.assertEqual([c["branch"] for c in self.sweep(archon)["cleaned"]], [f"{OURS}0"])

    def test_reports_what_could_not_be_removed(self):
        archon = FakeArchon({"runs": [child(0, "failed"), child(1, "paused"), child(2), child(3), child(4),
                                      row(RUN, "running")]}, {
            f"{OURS}2": ("", f"  Blocked: {OURS}2\n    ✗ uncommitted changes in worktree\n"),
            f"{OURS}3": ("", f"  Failed: {OURS}3 — Worktree creation identity changed\n"),
        })
        got = self.sweep(archon)
        self.assertEqual(archon.completed(), [f"{OURS}2", f"{OURS}3", f"{OURS}4"])
        self.assertEqual([c["branch"] for c in got["cleaned"]], [f"{OURS}4"])
        reasons = {left["branch"]: left["reason"] for left in got["left"]}
        self.assertEqual(list(reasons), [f"{OURS}0", f"{OURS}1", f"{OURS}2", f"{OURS}3"])
        self.assertIn("failed", reasons[f"{OURS}0"])
        self.assertIn("paused", reasons[f"{OURS}1"])
        self.assertIn("uncommitted changes in worktree", reasons[f"{OURS}2"])
        self.assertIn("Worktree creation identity changed", reasons[f"{OURS}3"])

    def test_keeps_children_that_have_not_completed(self):
        archon = FakeArchon({"runs": [child(0, "running"), child(1, "pending"), child(2, "cancelled"), child(3),
                                      row(RUN, "running")]})
        got = self.sweep(archon)
        self.assertEqual(archon.completed(), [f"{OURS}3"])
        reasons = {left["branch"]: left["reason"] for left in got["left"]}
        self.assertEqual(list(reasons), [f"{OURS}0", f"{OURS}1", f"{OURS}2"])
        for n, status in enumerate(("running", "pending", "cancelled")):
            self.assertIn(status, reasons[f"{OURS}{n}"])

    def test_branch_left_behind_after_the_worktree_is_reported(self):
        warning = f"Unexpected error deleting branch '{OURS}0': Command failed: git branch -D"
        archon = FakeArchon({"runs": [child(0), child(1), row(RUN, "running")]}, {
            f"{OURS}0": (f"\n  Completed: {OURS}0\n", f"  Warning: {warning}\n"),
            f"{OURS}1": (f"\n  Completed: {OURS}1\n", '{"level":30,"msg":"isolation.complete"}\n'),
        })
        got = self.sweep(archon)
        self.assertEqual([c["branch"] for c in got["cleaned"]], [f"{OURS}1"])
        self.assertEqual([left["branch"] for left in got["left"]], [f"{OURS}0"])
        self.assertIn(warning, got["left"][0]["reason"])

    def test_silent_complete_is_left_with_a_reason(self):
        archon = FakeArchon({"runs": [child(0), row(RUN, "running")]}, {f"{OURS}0": ("", "")})
        got = self.sweep(archon)
        self.assertEqual(got["cleaned"], [])
        self.assertTrue(got["left"][0]["reason"])

    def test_list_without_this_run_removes_nothing(self):
        archon = FakeArchon({"runs": [child(0)]})
        got = self.sweep(archon)
        self.assertEqual(archon.completed(), [])
        self.assertEqual((got["cleaned"], got["left"]), ([], []))
        self.assertIn(str(childsweep.LIST_LIMIT), got["error"])

    def test_unreadable_list_removes_nothing(self):
        refused = '{\n  "ok": false,\n  "error": "Error: Not in a git repository."\n}\n'
        for listing in ("not json\n", refused, {"ok": False, "error": "db locked"}, {"runs": "x"}):
            with self.subTest(listing=listing):
                archon = FakeArchon(listing)
                got = self.sweep(archon)
                self.assertEqual(archon.completed(), [])
                self.assertEqual((got["cleaned"], got["left"]), ([], []))
                self.assertTrue(got["error"])

    def test_runs_the_pinned_archon_without_prompts(self):
        archon = FakeArchon({"runs": [child(0), row(RUN, "running")]})
        self.sweep(archon)
        head = [str(self.bun), f"--config={self.source / 'bunfig.toml'}", str(self.source / place.ENTRY)]
        listing, complete = archon.calls
        self.assertEqual(listing["argv"], [*head, "workflow", "runs", "--json", "--all", "--limit",
                                           str(childsweep.LIST_LIMIT), "--cwd", CHECKOUT])
        self.assertEqual(complete["argv"], [*head, "complete", "--force", f"{OURS}0", "--cwd", CHECKOUT])
        for call in archon.calls:
            self.assertEqual(call["env"]["GIT_TERMINAL_PROMPT"], "0")
            self.assertEqual(call["env"]["GIT_SSH_COMMAND"], "ssh -o BatchMode=yes")
            self.assertEqual(call["cwd"], str(self.tmp))

    def test_own_ssh_command_is_kept(self):
        archon = FakeArchon({"runs": [row(RUN, "running")]})
        self.sweep(archon, {**self.env, "GIT_SSH_COMMAND": "ssh -i key"})
        self.assertEqual(archon.calls[0]["env"]["GIT_SSH_COMMAND"], "ssh -i key")

    def test_without_source_runs_nothing(self):
        env = {k: v for k, v in self.env.items() if k != place.SOURCE_ENV}
        archon = FakeArchon({"runs": []})
        got = self.sweep(archon, env)
        self.assertEqual(archon.calls, [])
        self.assertIn(place.SOURCE_ENV, got["error"])

    def test_without_bun_runs_nothing(self):
        archon = FakeArchon({"runs": []})
        got = self.sweep(archon, {**self.env, "PATH": str(self.tmp / "empty")})
        self.assertEqual(archon.calls, [])
        self.assertIn("bun", got["error"])


if __name__ == "__main__":
    unittest.main()

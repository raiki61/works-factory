"""殻の workflow cancel（bin/_lib/runstop.py。docs/polyfills.md の P13）を、止めた Archon と偽の claude で照らす（#706）。

使い捨ての工程 works-factory-stop-probe（tests/bin/stop-probe/）は、親の run の AI のノード・子の run の AI のノード・bash のノードを
並べて走らせる。偽の claude（CLAUDE_BIN_PATH）は、本物の Claude Code が道具で起こすプロセスの代わりに、自分と同じグループの子と
別のセッションの子を起こして眠る。止めた Archon の cancel だけでは、provider のプロセス（持ち主が detached で起こす）とその下が
親が 1 になって残る（P13 の実測）。源か bun が無ければ見送る。
"""
import contextlib
import io
import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from bin._lib import runstop
from tests import archon
from tests.bin.gitkit import git

import tree_run  # noqa: E402  （bin._lib.runstop が lib/ を sys.path に足した後に読む）

HERE = pathlib.Path(__file__).resolve().parent
PROBE = "works-factory-stop-probe"
POLL = 0.2
STUB = """#!{python}
import json, os, signal, subprocess, sys
if sys.argv[1:3] == ["plugin", "list"]:
    print("[]")
    sys.exit(0)
pause = [sys.executable, "-c", "import signal; signal.pause()"]
near = subprocess.Popen(pause)
away = subprocess.Popen(pause, start_new_session=True)
with open({log!r}, "a") as f:
    f.write(json.dumps({{"pid": os.getpid(), "ppid": os.getppid(), "cwd": os.getcwd(), "kids": [near.pid, away.pid]}}) + "\\n")
signal.pause()
"""


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    rows, _ = tree_run.ps_all()
    return rows is None or pid not in rows or not rows[pid].stat.startswith("Z")


class CancelStopsTheRunTreeTest(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(archon.tree(["stop-probe", "stop-kid"], workflows=HERE))
        tmp = pathlib.Path(self.enterContext(tempfile.TemporaryDirectory()))
        git(tmp, "init", "-q", "--bare", str(tmp / "origin.git"))   # 作業ツリーは remote の在る木でだけ切れる
        git(self.root, "remote", "add", "origin", str(tmp / "origin.git"))
        git(self.root, "push", "-q", "-u", "origin", "HEAD")
        self.log, self.shells = tmp / "claude.jsonl", tmp / "shells.txt"
        stub = tmp / "claude"
        stub.write_text(STUB.format(python=sys.executable, log=str(self.log)), encoding="utf-8")
        stub.chmod(0o755)
        self.head, self.env = archon.command(self.root, CLAUDE_BIN_PATH=str(stub), STOP_PROBE_SHELLS=str(self.shells))
        self.seen: dict[int, float] = {}
        self.addCleanup(self.reap)

    def reap(self):
        """試験が見たプロセスのうち、同じ開始時刻で生きている物を番号で止める（止め損ねた試験が後に残さない）"""
        rows, _ = tree_run.ps_all()
        for pid, started in self.seen.items():
            if rows and pid in rows and abs(rows[pid].started - started) <= tree_run.REUSE_SLACK:
                with contextlib.suppress(OSError):
                    os.kill(pid, signal.SIGKILL)

    def archon(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([*self.head, *args, "--cwd", str(self.root)], cwd=self.root, env=self.env, capture_output=True,
                              text=True, encoding="utf-8")

    def get(self, run_id: str) -> dict:
        done = self.archon("workflow", "get", run_id, "--json")
        return runstop.childsweep.last_json(done.stdout)

    def detach(self) -> str:
        done = self.archon("workflow", "run", PROBE, "--detach", "--json")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return runstop.childsweep.last_json(done.stdout)["runId"]

    def foreground(self) -> tuple[subprocess.Popen, str]:
        known = {r["id"] for r in self.runs()}
        owner = subprocess.Popen([*self.head, "workflow", "run", PROBE, "--cwd", str(self.root)], cwd=self.root, env=self.env,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: owner.poll() is not None or (owner.kill(), owner.wait()))
        while not (fresh := [r["id"] for r in self.runs() if r["id"] not in known and not r.get("parent_run_id")]):
            self.assertIsNone(owner.poll(), "前で起こした run が run を作る前に抜けた")
            time.sleep(POLL)
        return owner, fresh[0]

    def runs(self) -> list[dict]:
        return runstop.childsweep.last_json(self.archon("workflow", "runs", "--json", "--all").stdout)["runs"]

    def tree(self, run_id: str) -> dict:
        """run が親と子の run の AI のノードと bash のノードを走らせるまで待ち、種類ごとの番号の一覧 {owner・hosts（provider）・claude・
        kids（claude の子）・shell} を返す。run が pending か running の外になれば赤。見た番号は待つ間も片付けの控えに足していく"""
        while True:
            run = self.get(run_id)
            self.assertIn(run.get("status"), ("pending", "running"), json.dumps(run, ensure_ascii=False)[:2000])
            found = self.processes(run, run_id)
            rows, _ = tree_run.ps_all()
            self.seen.update({pid: rows[pid].started for pids in found.values() for pid in pids if rows and pid in rows})
            if run["status"] == "running" and all(found.values()) and len(found["claude"]) == 2:
                return found
            time.sleep(POLL)

    def processes(self, run: dict, run_id: str) -> dict:
        work = os.path.realpath(run.get("working_path") or "/nonexistent")
        stubs = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []
        mine = [s for s in stubs if os.path.realpath(s["cwd"]) == work][:1] + [s for s in stubs if f"task-{run_id[:8]}-" in s["cwd"]][:1]
        shells = [line.split(" ", 1) for line in self.shells.read_text(encoding="utf-8").splitlines()] if self.shells.exists() else []
        owner = runstop.childsweep.run_metadata(run.get("metadata")).get(runstop.OWNER_KEY, {}).get("pid")
        return {"owner": [owner] if owner else [], "hosts": [s["ppid"] for s in mine], "claude": [s["pid"] for s in mine],
                "kids": [k for s in mine for k in s["kids"]], "shell": [int(pid) for pid, cwd in shells if os.path.realpath(cwd) == work]}

    def cancel(self, run_id: str) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = runstop.cancel(self.head, ["workflow", "cancel", run_id, "--json"], self.env, str(self.root))
        return code, err.getvalue()

    def assertGone(self, found: dict, *kinds: str):
        left = {kind: [pid for pid in found[kind] if alive(pid)] for kind in kinds}
        self.assertEqual(left, {kind: [] for kind in kinds})

    def test_cancel_leaves_no_ai_process_of_the_run_or_its_child_run(self):
        run_id = self.detach()
        found = self.tree(run_id)
        code, err = self.cancel(run_id)
        self.assertEqual(code, 0, err)
        self.assertGone(found, "owner", "hosts", "claude", "kids", "shell")
        self.assertIn(f"run {run_id} のプロセス", err)
        self.assertNotIn("残ったプロセス", err)
        self.assertEqual(self.get(run_id)["status"], "cancelled")

    def test_cancel_leaves_a_parallel_run_alone(self):
        stopped, other = self.detach(), self.detach()
        found, untouched = self.tree(stopped), self.tree(other)
        code, err = self.cancel(stopped)
        self.assertEqual(code, 0, err)
        self.assertGone(found, "owner", "hosts", "claude", "kids", "shell")
        self.assertEqual({kind: [pid for pid in pids if not alive(pid)] for kind, pids in untouched.items()},
                         {kind: [] for kind in untouched})
        self.assertEqual(self.get(other)["status"], "running")
        code, err = self.cancel(other)
        self.assertEqual(code, 0, err)
        self.assertGone(untouched, "owner", "hosts", "claude", "kids", "shell")

    def test_cancel_of_a_foreground_run_stops_its_owner_too(self):
        """前で起こした run は Archon の cancel が拒む（終了の値は Archon の物）が、殻が持ち主ごと止め、run は failed になる"""
        owner, run_id = self.foreground()
        found = self.tree(run_id)
        self.assertEqual(found["owner"], [owner.pid])
        code, err = self.cancel(run_id)
        self.assertEqual(code, 1, err)
        self.assertIn("持ち主も止めた", err)
        owner.wait()
        self.assertGone(found, "hosts", "claude", "kids", "shell")
        self.assertEqual(self.get(run_id)["status"], "failed")

    def test_orphans_left_in_the_group_of_a_vanished_owner_are_stopped(self):
        """持ち主が先に消えた run（P1 の kill -9）は、持ち主のグループに残った bash のノードを止める。provider は自分のセッションに
        居て番号のつながりが無いので拾わない（抜け道。試験は見たプロセスを番号で片付ける）"""
        run_id = self.detach()
        found = self.tree(run_id)
        os.kill(found["owner"][0], signal.SIGKILL)
        while alive(found["owner"][0]):
            time.sleep(POLL)
        self.assertTrue(all(alive(pid) for pid in found["shell"]))
        code, err = self.cancel(run_id)
        self.assertEqual(code, 1, err)   # Archon は持ち主が答えないので拒む（abandon を勧める）
        self.assertGone(found, "shell")
        self.assertIn(f"run {run_id} のプロセス", err)


if __name__ == "__main__":
    unittest.main()

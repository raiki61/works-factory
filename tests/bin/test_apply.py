"""封じた差分を対象に当てる口 bin/apply（bin/_lib/apply.py）の試験。

workflow get の答えは偽の関数で渡す（計画 docs/plans/2026-10-13-stage1-walking-skeleton.md の「bin/apply」の約束の形の JSON。
線の返す節 result の値が terminal_record.returns.value）。対象と差分は使い捨ての git リポジトリで作る。
殻を通す道だけは、tests/bin/fakelaunch.py の木で bin/apply を子のプロセスとして走らせ、偽の bun が受けた引数を照らす。
"""
import contextlib
import hashlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from bin._lib import apply
from tests.bin import fakelaunch, hermetic
from tests.bin.gitkit import git

RUN = "0123456789abcdef0123456789abcdef"
SHORT = RUN[:8]
FIXED = "def mean(xs):\n    return sum(xs) / len(xs)\n"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pointer(path: str, run_id: str = RUN) -> dict:
    return {"type": "archon_artifact", "run_id": run_id, "path": path}


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.target = self.tmp / "target"
        self.target.mkdir()
        (self.target / "stats.py").write_text("def mean(xs):\n    return sum(xs) / (len(xs) - 1)\n", encoding="utf-8")
        (self.target / "old.txt").write_text("gone\n", encoding="utf-8")
        git(self.target, "init", "-q")
        git(self.target, "add", "-A")
        git(self.target, "commit", "-q", "-m", "seed")
        self.root = self.tmp / "artifacts"
        self.diff = self.make_diff(lambda: (self.target / "stats.py").write_text(FIXED, encoding="utf-8"))
        self.place("merge/sealed.diff", self.diff)
        self.place("merge/apply.diff", self.diff)
        self.calls = []

    def make_diff(self, change) -> bytes:
        change()
        git(self.target, "add", "-A")
        data = subprocess.run(["git", "-C", str(self.target), "diff", "--cached", "--binary"], capture_output=True,
                              check=True).stdout
        git(self.target, "reset", "-q", "--hard")
        return data

    def place(self, rel: str, data: bytes) -> pathlib.Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def value(self, **over) -> dict:
        h = sha(self.diff)
        value = {"outcome": "fixed",
                 "apply": {"ok": True, "hash": h, "diff": pointer("merge/apply.diff"), "reason": ""},
                 "sealed": {"ok": True, "hash": h, "diff": pointer("merge/sealed.diff")},
                 "r2_status": None, "report": None}
        value.update(over)
        return value

    def record(self, value=None, *, returns=None, run_id=RUN) -> dict:
        return {"run": {"id": run_id}, "terminal_record": {
            "run_id": run_id, "status": "completed", "outcome": "success", "error": None, "first_failed_node": None,
            "nodes": [],
            "returns": returns or {"availability": "available", "node_id": "result",
                                   "value": self.value() if value is None else value},
            "artifacts": {"root": str(self.root), "files": [], "limitations": []}}}

    def run_apply(self, got, *args, rc=0, run=RUN):
        """bin/_lib/apply.main を偽の get で回す。(終了の値, 標準出力, 標準エラー)"""
        def get(run_id, target):
            self.calls.append((run_id, target))
            stdout = got if isinstance(got, str) else json.dumps(got)
            return subprocess.CompletedProcess([], rc, stdout, "")

        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = apply.main([run, "--cwd", str(self.target), *args], here=self.tmp, get=get)
        return code, out.getvalue(), err.getvalue()

    def status(self) -> str:
        return git(self.target, "status", "--porcelain")

    def assert_refused(self, done, code=1, *words):
        rc, out, err = done
        self.assertEqual(rc, code, out + err)
        self.assertEqual(self.status(), "", "対象が変わった")
        for word in words:
            self.assertIn(word, err)
        return err

    def assert_applied(self, done):
        rc, out, err = done
        self.assertEqual(rc, 0, out + err)
        self.assertEqual((self.target / "stats.py").read_text(encoding="utf-8"), FIXED)
        git(self.target, "apply", "-R", "--check", str(self.root / "merge/sealed.diff"))
        self.assertEqual(git(self.target, "rev-list", "--count", "HEAD"), "1", "commit した")
        return out

    def test_apply_applies_sealed_diff(self):
        out = self.assert_applied(self.run_apply(self.record()))
        self.assertIn("stats.py", out)
        self.assertIn("commit はしていない", out)
        self.assertEqual(self.calls, [(RUN, self.target)])

    def test_apply_refuses_changed_diff(self):
        changed = self.diff.replace(b"len(xs)\n", b"len(xs) \n")
        self.place("merge/apply.diff", changed)
        err = self.assert_refused(self.run_apply(self.record()), 1, "封じた hash と合わない")
        self.assertIn(sha(self.diff), err)
        self.assertIn(sha(changed), err)

    def test_apply_refuses_apply_hash_not_sealed(self):
        other = "0" * 64
        for sealed in ({"ok": True, "hash": other, "diff": pointer("merge/sealed.diff")}, None):
            with self.subTest(sealed=sealed):
                self.assert_refused(self.run_apply(self.record(self.value(sealed=sealed))), 1, "封じた hash と合わない")

    def test_apply_refuses_when_nothing_placed(self):
        failed = {"ok": False, "hash": sha(self.diff), "diff": pointer("merge/refused.diff"), "reason": "r"}
        for value in (self.value(apply=None, sealed=None, outcome="stopped_by_line"), self.value(apply=failed)):
            with self.subTest(value=value):
                self.assert_refused(self.run_apply(self.record(value)), 1, "置いた差分が無い", value["outcome"])
        with self.subTest("封じていない差分は --allow-stopped でも当てない"):
            value = self.value(apply=None, sealed=None, outcome="stopped_by_line")
            self.assert_refused(self.run_apply(self.record(value), "--allow-stopped"), 1, "置いた差分が無い")

    def test_apply_stopped_run_needs_flag(self):
        value = self.value(apply=None, outcome="stopped_by_human")
        self.assert_refused(self.run_apply(self.record(value)), 1, "--allow-stopped", "stopped_by_human")
        self.assert_applied(self.run_apply(self.record(value), "--allow-stopped"))

    def test_apply_stopped_run_refuses_redesign(self):
        value = self.value(apply=None, outcome="stopped_by_human", r2_status="redesign-needed")
        self.assert_refused(self.run_apply(self.record(value), "--allow-stopped"), 1, "redesign-needed")

    def test_apply_refuses_unreadable_run(self):
        cases = {
            "終わっていない": ({"run": {"id": RUN}, "terminal_record": None}, 0),
            "unavailable": (self.record(returns={"availability": "unavailable", "node_id": None,
                                                 "reason": "node_not_completed"}), 0),
            "truncated": (self.record(returns={"availability": "truncated", "node_id": "result", "spill_path": None,
                                               "original_bytes": 9}), 0),
            "get が落ちた": (self.record(), 1),
            "JSON でない": ("not json", 0),
        }
        for name, (got, rc) in cases.items():
            with self.subTest(name):
                err = self.assert_refused(self.run_apply(got, rc=rc), 2)
                self.assertEqual(len(err.strip().splitlines()), 1, err)

    def test_apply_refuses_pointer_outside_root(self):
        outside = self.place("../outside.diff", self.diff)
        link = self.root / "merge" / "link.diff"
        link.symlink_to(outside)
        for name, ptr in (("..", pointer("../outside.diff")), ("絶対パス", pointer(str(outside))),
                          ("symlink", pointer("merge/link.diff")), ("無いファイル", pointer("merge/none.diff")),
                          ("フォルダ", pointer("merge")), ("別の run", pointer("merge/apply.diff", run_id="other")),
                          ("指し札でない", "merge/apply.diff")):
            with self.subTest(name):
                value = self.value()
                value["apply"]["diff"] = ptr
                self.assert_refused(self.run_apply(self.record(value)), 1)

    def test_apply_accepts_short_run_id(self):
        self.assert_applied(self.run_apply(self.record(), run=SHORT))
        self.assertEqual(self.calls, [(SHORT, self.target)])

    def test_apply_refuses_delete_unless_allowed(self):
        git(self.target, "reset", "-q", "--hard")
        gone = self.make_diff(lambda: (self.target / "old.txt").unlink())
        self.place("merge/apply.diff", gone)
        self.place("merge/sealed.diff", gone)
        value = self.value(apply={"ok": True, "hash": sha(gone), "diff": pointer("merge/apply.diff"), "reason": ""},
                           sealed={"ok": True, "hash": sha(gone), "diff": pointer("merge/sealed.diff")})
        self.assert_refused(self.run_apply(self.record(value)), 1, "old.txt", "--allow-delete")
        rc, out, err = self.run_apply(self.record(value), "--allow-delete")
        self.assertEqual(rc, 0, out + err)
        self.assertFalse((self.target / "old.txt").exists())

    def test_apply_refuses_when_check_fails(self):
        (self.target / "stats.py").write_text("def mean(xs):\n    return 0\n", encoding="utf-8")
        before = self.status()
        rc, out, err = self.run_apply(self.record())
        self.assertEqual(rc, 1, out + err)
        self.assertEqual(self.status(), before)
        self.assertEqual((self.target / "stats.py").read_text(encoding="utf-8"), "def mean(xs):\n    return 0\n")


class BinApplyTest(unittest.TestCase):
    """bin/apply を子のプロセスで走らせる。get は殻 bin/works-factory を通り、偽の bun が答える。
    殻は工程を回さない命令でも認証つきで Archon を起こす（bin/_lib/auth_launch.py の exec）ので、偽の API キーを渡す"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="works-apply-")
        cls.tree = fakelaunch.build(pathlib.Path(os.path.realpath(cls._tmp.name)))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.target = self.tmp / "target"
        (self.target / "sub").mkdir(parents=True)
        git(self.target, "init", "-q")
        fake = self.tmp / "fake-bin"
        fakelaunch.put(fake / "bun", fakelaunch.FAKE_BUN)
        self.bun_log = self.tmp / "bun.json"
        self.env = hermetic.child_env(HOME=str(self.tmp / "user-home"), PATH=f"{fake}{os.pathsep}{self.tree.tools}",
                                      XDG_CACHE_HOME=str(self.tree.cache_home), FAKE_BUN_LOG=str(self.bun_log),
                                      ANTHROPIC_API_KEY="sk-ant-api03-fake-for-apply")
        for name in ("XDG_STATE_HOME", "GH_CONFIG_DIR"):
            self.env.pop(name, None)

    def bin_apply(self, *args, cwd):
        return subprocess.run([sys.executable, str(self.tree.repo / "bin" / "apply"), *args], env=self.env, cwd=cwd,
                              capture_output=True, text=True, encoding="utf-8", timeout=120)

    def test_bin_apply_asks_launcher_for_get(self):
        homes = []
        for cwd, args in ((self.target / "sub", ()), (self.tmp, ("--cwd", str(self.target / "sub")))):
            with self.subTest(cwd=cwd):
                done = self.bin_apply(RUN, *args, cwd=cwd)
                self.assertEqual(done.returncode, 2, done.stderr)
                got = json.loads(self.bun_log.read_text(encoding="utf-8"))
                self.assertEqual(got["argv"][3:], ["workflow", "get", RUN, "--json", "--cwd", str(self.target)])
                homes.append(got["env"]["HOME"])
        self.assertEqual(homes[0], homes[1])

    def test_bin_apply_old_python_stops_before_loading_parts(self):
        pretend = ("import runpy, sys; sys.version_info = (3, 9, 6, 'final', 0); "
                   f"runpy.run_path({str(self.tree.repo / 'bin' / 'apply')!r}, run_name='__main__')")
        done = subprocess.run([sys.executable, "-c", pretend, RUN], env=self.env, cwd=self.target,
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertEqual(done.stderr.strip(), "apply: Python 3.12 以上が要る")
        self.assertFalse(self.bun_log.exists())


if __name__ == "__main__":
    unittest.main()

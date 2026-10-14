"""封じた差分を対象に当てる口 bin/apply（bin/_lib/apply.py）の試験。

workflow get の答えは偽の関数で渡す（計画 docs/plans/2026-10-13-stage1-walking-skeleton.md の「bin/apply」の約束の形の JSON。
線の返す節 result の値が terminal_record.returns.value）。対象と差分は使い捨ての git リポジトリで作る。
殻を通す道だけは、tests/bin/fakelaunch.py の木で bin/apply を子のプロセスとして走らせ、偽の bun が受けた引数を照らす。
"""
import ast
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
from unittest import mock

import yaml

from bin._lib import apply
from graphloops.engine.schema import validate_schema  # lib/ は bin._lib.apply が sys.path に置く
from tests.bin import fakelaunch, hermetic
from tests.bin.gitkit import git
from tests.workflows.test_chain import ROUND_FILES, chain, run_final, run_result, three_rounds

ROOT = pathlib.Path(__file__).resolve().parents[2]
MERGE = ROOT / "workflows" / "merge" / "works-factory-merge.yaml"

RUN = "0123456789abcdef0123456789abcdef"
SHORT = RUN[:8]
BASE = "fedcba9876543210fedcba9876543210fedcba98"
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
        self.worktree = self.tmp / "run-worktree"
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
        """workflow get --json の答え: run の記録の欄（止めた Archon の workflowGetCommand が run を広げて出す）と terminal_record"""
        return {"id": run_id, "status": "completed", "working_path": str(self.worktree),
                "checkout_baseline": {"kind": "git", "commit": BASE, "tree": "0" * 40, "worktree": {"status": "clean"}},
                "terminal_record": {
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
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        for word in words:
            self.assertIn(word, err)
        return err

    def by_hand(self) -> str:
        """封じる前に止まった run の作業ツリーの差分を、確かめずに当てる道"""
        return f"git -C {self.worktree} diff {BASE} | git -C {self.target} apply"

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
        refused = {"ok": False, "hash": sha(self.diff), "diff": pointer("merge/refused.diff")}
        for name, sealed in (("封じる前に止まった", None), ("merge-seal が拒んだ", refused)):
            with self.subTest(f"{name}差分は --allow-stopped でも当てず、作業ツリーから当てる道を言う"):
                value = self.value(apply=None, sealed=sealed, outcome="stopped_by_line")
                self.assert_refused(self.run_apply(self.record(value), "--allow-stopped"), 1, "置いた差分が無い",
                                    self.by_hand())
        with self.subTest("R2 が作り直しと言った run には当てる道を言わない"):
            value = self.value(apply=None, sealed=None, outcome="stopped_by_line", r2_status="redesign-needed")
            err = self.assert_refused(self.run_apply(self.record(value), "--allow-stopped"), 1, "置いた差分が無い")
            self.assertNotIn(str(self.worktree), err)
            self.assertNotIn("git -C", err)

    def test_apply_stopped_run_needs_flag(self):
        value = self.value(apply=None, outcome="stopped_by_human", stop_reason="human:gate-final",
                           final_answer={"decision": "stop", "text": "まだ早い。\n境界の試験が無い"})
        self.assert_refused(self.run_apply(self.record(value)), 1, "--allow-stopped", "stopped_by_human",
                            "human:gate-final", "まだ早い。 境界の試験が無い")
        rc, out, err = self.run_apply(self.record(value), "--allow-stopped")
        self.assert_applied((rc, out, err))
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        for word in ("stopped_by_human", "human:gate-final", "まだ早い。 境界の試験が無い", "--allow-stopped が在るので当てた"):
            self.assertIn(word, err)

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
                self.assert_refused(self.run_apply(got, rc=rc), 2)
        unknown = {"unavailable": cases["unavailable"][0], "truncated": cases["truncated"][0],
                   "object でない": self.record(returns={"availability": "available", "node_id": "result", "value": "x"})}
        for name, got in unknown.items():
            with self.subTest(f"{name}: 置き場の差分を確かめずに当てる道を言う"):
                place = self.root / "merge" / "apply.diff"
                self.assert_refused(self.run_apply(got), 2, str(place), f"git -C {self.target} apply {place}")
        (self.root / "merge" / "apply.diff").unlink()
        with self.subTest("置いた差分が無ければ封じた差分を名指す"):
            place = self.root / "merge" / "sealed.diff"
            self.assert_refused(self.run_apply(cases["unavailable"][0]), 2, f"git -C {self.target} apply {place}")
        (self.root / "merge" / "sealed.diff").unlink()
        with self.subTest("周の鎖の親の run なら最後の差分を名指す"):
            place = self.place(chain.FINAL, self.diff)
            self.assert_refused(self.run_apply(cases["unavailable"][0]), 2, f"git -C {self.target} apply {place}")
        place.unlink()
        with self.subTest("置き場に差分が無ければ道を言わない"):
            err = self.assert_refused(self.run_apply(cases["unavailable"][0]), 2)
            self.assertNotIn("git -C", err)

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

    def test_apply_refuses_when_readback_fails(self):
        real = apply.git_apply

        def readback_fails(target, data, *flags):
            if flags == ("-R", "--check"):
                return subprocess.CompletedProcess([], 1, "", "patch does not apply")
            return real(target, data, *flags)

        with mock.patch.object(apply, "git_apply", readback_fails):
            rc, out, err = self.run_apply(self.record())
        self.assertEqual(rc, 1, out + err)
        self.assertIn("当てたが読み戻せない", err)
        self.assertEqual(out, "")

    def test_apply_ignores_whitespace_setting_and_names_files_plainly(self):
        git(self.target, "config", "apply.whitespace", "error")
        git(self.target, "config", "core.quotePath", "true")
        diff = self.make_diff(lambda: (self.target / "日本.txt").write_text("x \n", encoding="utf-8"))
        self.place("merge/apply.diff", diff)
        self.place("merge/sealed.diff", diff)
        value = self.value(apply={"ok": True, "hash": sha(diff), "diff": pointer("merge/apply.diff"), "reason": ""},
                           sealed={"ok": True, "hash": sha(diff), "diff": pointer("merge/sealed.diff")})
        rc, out, err = self.run_apply(self.record(value))
        self.assertEqual(rc, 0, out + err)
        self.assertIn("日本.txt", out.splitlines()[0])
        self.assertEqual((self.target / "日本.txt").read_bytes(), b"x \n")

    def test_apply_reads_the_merge_returns(self):
        """result の apply・sealed は merge の返りの欄を写した物（計画「線の返りに足す欄」）。試験の形が merge の output_format に合う"""
        returns = yaml.safe_load(MERGE.read_text(encoding="utf-8"))["nodes"][0]["output_format"]["properties"]
        self.assertEqual(returns["diff"]["properties"]["type"]["enum"], [apply.POINTER_TYPE])
        self.assertLessEqual({apply.APPLY_DIFF, apply.SEALED_DIFF}, set(returns["diff"]["properties"]["path"]["enum"]))
        for name, member in ((n, self.value()[n]) for n in ("apply", "sealed")):
            with self.subTest(name):
                shape = {"type": "object", "properties": {k: returns[k] for k in member}, "required": list(member)}
                self.assertEqual(validate_schema(member, shape), [])

    def test_apply_sets_no_deadline(self):
        for part in (ROOT / "bin" / "apply", ROOT / "bin" / "_lib" / "apply.py"):
            with self.subTest(part.name):
                tree = ast.parse(part.read_text(encoding="utf-8"))
                self.assertEqual([n.lineno for n in ast.walk(tree) if isinstance(n, ast.keyword) and n.arg == "timeout"],
                                 [])

    def test_apply_refuses_when_check_fails(self):
        (self.target / "stats.py").write_text("def mean(xs):\n    return 0\n", encoding="utf-8")
        before = self.status()
        rc, out, err = self.run_apply(self.record())
        self.assertEqual(rc, 1, out + err)
        self.assertIn("手元の変更", err)
        self.assertEqual(self.status(), before)
        self.assertEqual((self.target / "stats.py").read_text(encoding="utf-8"), "def mean(xs):\n    return 0\n")

    def test_every_refusal_is_one_line_and_leaves_target(self):
        def dirty():
            (self.target / "stats.py").write_text("def mean(xs):\n    return 0\n", encoding="utf-8")

        def unreadable():
            (self.root / "merge" / "apply.diff").chmod(0)

        def changed():
            self.place("merge/apply.diff", self.diff + b"\n")

        stopped = self.value(apply=None, outcome="stopped_by_human", final_answer={"decision": "stop", "text": "a\nb"})
        cases = {"手元の変更とぶつかる": (dirty, self.record()),
                 "差分のファイルが読めない": (unreadable, self.record()),
                 "封じた hash と合わない": (changed, self.record()),
                 "止まった run": (None, self.record(stopped)),
                 "封じる前に止まった run": (None, self.record(self.value(apply=None, sealed=None))),
                 "読めない run": (None, self.record(returns={"availability": "unavailable", "node_id": None}))}
        for name, (spoil, got) in cases.items():
            with self.subTest(name):
                if spoil:
                    spoil()
                before = {p: p.read_bytes() for p in self.target.iterdir() if p.is_file()}
                status = self.status()
                rc, out, err = self.run_apply(got)
                self.assertNotEqual(rc, 0, out + err)
                self.assertEqual(out, "")
                self.assertEqual(len(err.strip().splitlines()), 1, err)
                self.assertEqual(self.status(), status)
                self.assertEqual({p: p.read_bytes() for p in self.target.iterdir() if p.is_file()}, before)
                git(self.target, "checkout", "-q", "--", ".")
                (self.root / "merge" / "apply.diff").chmod(0o644)
                self.place("merge/apply.diff", self.diff)

    def test_apply_ignores_env_allowances(self):
        """今の works の許しの環境変数（WORKS_USE_ALLOW_DELETE・WORKS_USE_ALLOW_STOPPED）は効かない。許しは 1 回の打ち方の旗だけ"""
        gone = self.make_diff(lambda: (self.target / "old.txt").unlink())
        self.place("merge/apply.diff", gone)
        self.place("merge/sealed.diff", gone)
        deletes = self.value(apply={"ok": True, "hash": sha(gone), "diff": pointer("merge/apply.diff"), "reason": ""},
                             sealed={"ok": True, "hash": sha(gone), "diff": pointer("merge/sealed.diff")})
        stopped = self.value(apply=None, sealed=deletes["sealed"], outcome="stopped_by_human")
        with mock.patch.dict(os.environ, {"WORKS_USE_ALLOW_DELETE": "1", "WORKS_USE_ALLOW_STOPPED": "1"}):
            self.assert_refused(self.run_apply(self.record(deletes)), 1, "--allow-delete")
            self.assert_refused(self.run_apply(self.record(stopped)), 1, "--allow-stopped")

    def test_apply_does_not_need_the_run_worktree(self):
        """当てる物は置き場の封じた差分だけで、run の作業ツリーを読まない（作業ツリーが片付いた後でも当たる）"""
        self.assertFalse(self.worktree.exists())
        self.assert_applied(self.run_apply(self.record()))


class ChainApplyTest(unittest.TestCase):
    """周の鎖の親の run の出力（final-diff と result を本当に走らせた物）から、bin/apply が最後の差分を選んで当てる"""

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.target = self.tmp / "target"
        self.target.mkdir()
        (self.target / "seed.txt").write_text("seed\n", encoding="utf-8")
        git(self.target, "init", "-q")
        git(self.target, "add", "-A")
        git(self.target, "commit", "-q", "-m", "seed")
        self.work = self.tmp / "run-worktree"
        git(self.tmp, "clone", "-q", str(self.target), str(self.work))
        self.root = self.tmp / "artifacts"
        self.root.mkdir()

    def parent_run(self, **rounds) -> dict:
        return self.record(*three_rounds(self.work, **rounds))

    def record(self, start, made) -> dict:
        final = run_final(self.work, self.root, RUN, start, *made)
        value = run_result(start, final, *made, artifacts=self.root, run_id=RUN)
        return {"id": RUN, "status": "completed", "working_path": str(self.work),
                "checkout_baseline": {"kind": "git", "commit": start["origin"]},
                "terminal_record": {"run_id": RUN, "status": "completed", "outcome": "success",
                                    "returns": {"availability": "available", "node_id": "result", "value": value},
                                    "artifacts": {"root": str(self.root), "files": [], "limitations": []}}}

    def run_apply(self, record, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = apply.main([RUN, "--cwd", str(self.target), *args], here=self.tmp,
                              get=lambda run_id, target: subprocess.CompletedProcess([], 0, json.dumps(record), ""))
        return code, out.getvalue(), err.getvalue()

    def present(self) -> list:
        return [name for name in ROUND_FILES if (self.target / name).exists()]

    def test_last_diff_is_applied_without_the_halted_round(self):
        code, out, err = self.run_apply(self.parent_run())
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.present(), ["one.txt", "two.txt"])
        self.assertIn("one.txt two.txt", out)

    def test_round_whose_child_did_not_place_needs_allow_stopped(self):
        record = self.parent_run(halted_last=False, placed=())
        code, _, err = self.run_apply(record)
        self.assertEqual((code, self.present()), (1, []), err)
        self.assertIn("--allow-stopped", err)
        code, out, err = self.run_apply(record, "--allow-stopped")
        self.assertEqual((code, self.present()), (0, list(ROUND_FILES)), out + err)

    def test_earlier_round_that_did_not_place_needs_allow_stopped(self):
        code, _, err = self.run_apply(self.parent_run(placed=(2,)))
        self.assertEqual((code, self.present()), (1, []), err)
        self.assertIn("--allow-stopped", err)
        self.assertIn("周 1", err)

    def test_redesign_is_refused_even_with_allow_stopped(self):
        code, _, err = self.run_apply(self.parent_run(placed=(2,), r2={1: "redesign-needed"}), "--allow-stopped")
        self.assertEqual((code, self.present()), (1, []), err)
        self.assertIn("redesign-needed", err)

    def test_nothing_to_take_names_why(self):
        start, made = three_rounds(self.work)
        halted = [{**d, "rows": [{**r, "kind": chain.KIND_HALTED} for r in d["rows"]]} for d in made]
        code, _, err = self.run_apply(self.record(start, halted))
        self.assertEqual((code, self.present()), (1, []), err)
        self.assertIn("採れる周が無い", err)


KEY = "sk-ant-api03-fake-for-apply"


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
                                      ANTHROPIC_API_KEY=KEY)
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
                self.assertNotIn(KEY, done.stdout + done.stderr)
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

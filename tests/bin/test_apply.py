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
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

from bin._lib import apply
from graphloops.engine.schema import validate_schema  # lib/ は bin._lib.apply が sys.path に置く
from tests.bin import fakelaunch, hermetic
from tests.bin.stepnames import step_names
from tests.archon import WORKFLOWS
from tests.bin.gitkit import git
from tests.workflows.test_chain import ROUND_FILES, chain, run_final, run_result, three_rounds

ROOT = pathlib.Path(__file__).resolve().parents[2]
MERGE = WORKFLOWS / "merge" / "works-factory-merge.yaml"
LINE = WORKFLOWS / "line" / "works-factory-line.yaml"
CHAIN = WORKFLOWS / "chain" / "works-factory-chain.yaml"
# 周の鎖は承認のノードを持たない（最後の承認は周の子 run の中）ので、人の一言 final_answer を鎖の result は運ばない。
# stopped_why は無い一言を言わないだけで、ほかの読む欄は鎖も線と同じに要る
CHAIN_OMITS = {"final_answer"}

RUN = "0123456789abcdef0123456789abcdef"
SHORT = RUN[:8]
BASE = "fedcba9876543210fedcba9876543210fedcba98"
FIXED = "def mean(xs):\n    return sum(xs) / len(xs)\n"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pointer(path: str, run_id: str = RUN) -> dict:
    return {"type": "archon_artifact", "run_id": run_id, "path": path}


def value_keys(node: ast.AST) -> list[ast.Constant]:
    """value.get("欄") と value["欄"] の欄の名"""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
        holder, keys = node.func.value, node.args[:1]
    elif isinstance(node, ast.Subscript):
        holder, keys = node.value, [node.slice]
    else:
        return []
    if not (isinstance(holder, ast.Name) and holder.id == "value"):
        return []
    return [k for k in keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]


class TargetCase(unittest.TestCase):
    """使い捨ての対象と run の置き場（封じた差分と置いた差分）と、偽の get で回す bin/apply"""

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
                              check=True, env=hermetic.child_env()).stdout
        git(self.target, "reset", "-q", "--hard")
        return data

    def place(self, rel: str, data: bytes) -> pathlib.Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def run_apply(self, got, *args, rc=0, run=RUN, events=None):
        """bin/_lib/apply.main を偽の get で回す。出来事の列を求める get には events（無ければ got）を答える。(終了の値, 標準出力, 標準エラー)"""
        def get(run_id, target, *flags):
            self.calls.append((run_id, target, *flags))
            answer = events if flags and events is not None else got
            stdout = answer if isinstance(answer, str) else json.dumps(answer)
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

    def assert_applied(self, done):
        rc, out, err = done
        self.assertEqual(rc, 0, out + err)
        self.assertEqual((self.target / "stats.py").read_text(encoding="utf-8"), FIXED)
        git(self.target, "apply", "-R", "--check", str(self.root / "merge/sealed.diff"))
        self.assertEqual(git(self.target, "rev-list", "--count", "HEAD"), "1", "commit した")
        return out


class ApplyTest(TargetCase):
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

    def by_hand(self) -> str:
        """封じる前に止まった run の作業ツリーの差分を、確かめずに当てる道"""
        return shlex.join(["sh", "-c", apply.BY_HAND, "sh", str(self.worktree), BASE, str(self.target)])

    def test_apply_applies_sealed_diff(self):
        out = self.assert_applied(self.run_apply(self.record()))
        self.assertIn("stats.py", out)
        self.assertIn("commit はしていない", out)
        self.assertEqual(self.calls, [(RUN, self.target)])

    def test_apply_notes_pending_reapproval(self):
        """#550: 承認し直すかの問いを残した run は、断らずに当て、標準エラーにそう 1 行で知らせる。止めの語が別の待ち
        （fix の衝突が先に立った）でも、照らせなかった（止めの語は works:line-script）でも、問いの数で知らせる"""
        for stop in ("spec-check:works:spec-changed", "fix:works:conflict", "spec-check:works:line-script"):
            with self.subTest(stop=stop):
                git(self.target, "reset", "-q", "--hard")
                value = self.value(outcome="needs_human", stop_reason=stop, spec_questions=2)
                rc, out, err = self.run_apply(self.record(value))
                self.assert_applied((rc, out, err))
                self.assertEqual(len(err.strip().splitlines()), 1, err)
                for word in ("承認し直す", "2 件", "needs_human", stop):
                    self.assertIn(word, err)

    def test_apply_other_waits_say_nothing(self):
        value = self.value(outcome="needs_human", stop_reason="ask-final:works:needs-human", spec_questions=0)
        rc, out, err = self.run_apply(self.record(value))
        self.assert_applied((rc, out, err))
        self.assertEqual(err, "")

    def test_apply_fixed_run_says_nothing(self):
        rc, out, err = self.run_apply(self.record())
        self.assert_applied((rc, out, err))
        self.assertEqual(err, "")

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

    def test_by_hand_carries_new_files(self):
        """封じる前に止まった run の拒む行の命令を打つと、修正の段が index 無しで当てた変更（追跡外のまま残る新しいファイル・
        バイナリ・消したファイル）も対象に当たり、run の作業ツリーの本物の index は動かない"""
        git(self.tmp, "clone", "-q", str(self.target), str(self.worktree))
        base = git(self.worktree, "rev-parse", "HEAD")
        (self.worktree / "stats.py").write_text(FIXED, encoding="utf-8")
        (self.worktree / "new.txt").write_text("new\n", encoding="utf-8")
        (self.worktree / "blob.bin").write_bytes(bytes(range(256)))
        (self.worktree / "old.txt").unlink()
        before = git(self.worktree, "status", "--porcelain")
        record = self.record(self.value(apply=None, sealed=None, outcome="stopped_by_line"))
        record["checkout_baseline"]["commit"] = base
        err = self.assert_refused(self.run_apply(record), 1, "置いた差分が無い")
        command = err.strip().split("当てるなら ", 1)[1]
        subprocess.run(command, shell=True, check=True, capture_output=True, env=hermetic.child_env())
        self.assertEqual((self.target / "stats.py").read_text(encoding="utf-8"), FIXED)
        self.assertEqual((self.target / "new.txt").read_text(encoding="utf-8"), "new\n")
        self.assertEqual((self.target / "blob.bin").read_bytes(), bytes(range(256)))
        self.assertFalse((self.target / "old.txt").exists())
        self.assertEqual(git(self.worktree, "status", "--porcelain"), before, "run の作業ツリーの index が動いた")

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
        link = self.root / "link" / "apply.diff"
        link.parent.mkdir()
        link.symlink_to(outside)
        (self.root / "folder" / "apply.diff").mkdir(parents=True)
        for name, ptr, said in (("..", pointer("../apply.diff"), "外"), ("絶対パス", pointer(str(self.root / "merge/apply.diff")), "相対"),
                                ("symlink", pointer("link/apply.diff"), "外"), ("無いファイル", pointer("none/apply.diff"), "普通のファイル"),
                                ("フォルダ", pointer("folder/apply.diff"), "普通のファイル"),
                                ("別の run", pointer("merge/apply.diff", run_id="other"), "別の run"),
                                ("先の名が違う", pointer("merge/sealed.diff"), "名が apply.diff でない"),
                                ("指し札でない", "merge/apply.diff", "読めない")):
            with self.subTest(name):
                value = self.value()
                value["apply"]["diff"] = ptr
                self.assert_refused(self.run_apply(self.record(value)), 1, said)

    def test_apply_reads_the_place_of_any_include(self):
        """place は include の道で決まる（merge-seal/sealed.diff・merge-apply/apply.diff）。決まったパスでなく名の末尾で照らす（README 11.3 の 7）"""
        self.place("merge-apply/apply.diff", self.diff)
        self.place("merge-seal/sealed.diff", self.diff)
        value = self.value(apply={"ok": True, "hash": sha(self.diff), "diff": pointer("merge-apply/apply.diff"), "reason": ""},
                           sealed={"ok": True, "hash": sha(self.diff), "diff": pointer("merge-seal/sealed.diff")})
        self.assert_applied(self.run_apply(self.record(value)))

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
        nodes = yaml.safe_load(MERGE.read_text(encoding="utf-8"))["nodes"]
        returns = next((n for n in nodes if n["id"] == "merge"), nodes[0])["output_format"]["properties"]
        self.assertEqual(returns["diff"]["properties"]["type"]["enum"], [apply.POINTER_TYPE])
        path = returns["diff"]["properties"]["path"]
        for name in (apply.APPLY_DIFF, apply.SEALED_DIFF):
            with self.subTest(name):
                if "pattern" in path:   # place は include の道で決まるので、名の末尾の形で縛る（docs/design/merge.md の 1.3）
                    self.assertRegex(f"merge-apply/{name}", path["pattern"])
                else:
                    self.assertTrue(any(pathlib.PurePosixPath(p).name == name for p in path["enum"]))
        for name, member in ((n, self.value()[n]) for n in ("apply", "sealed")):
            with self.subTest(name):
                shape = {"type": "object", "properties": {k: returns[k] for k in member}, "required": list(member)}
                self.assertEqual(validate_schema(member, shape), [])

    def test_apply_reads_only_line_returns(self):
        """bin/_lib/apply.py が value から読む欄は、どれも線の result の output_format が要る欄として持つ（名を変えると知らせが黙って消える）。
        spec_questions は respec_note が数えられる整数で来る。周の鎖の result も同じ口で読むので、CHAIN_OMITS のほかは同じ欄を同じ形で持つ"""
        tree = ast.parse((ROOT / "bin" / "_lib" / "apply.py").read_text(encoding="utf-8"))
        read = {key.value for node in ast.walk(tree) for key in value_keys(node)}
        self.assertIn("spec_questions", read)
        for graph in (LINE, CHAIN):
            with self.subTest(graph.name):
                result = next(n for n in yaml.safe_load(graph.read_text(encoding="utf-8"))["nodes"] if n["id"] == "result")
                returns = result["output_format"]
                self.assertLessEqual(read - (CHAIN_OMITS if graph == CHAIN else set()), set(returns["required"]))
                self.assertIn("spec_questions", returns["required"])
                self.assertEqual(validate_schema(self.value(spec_questions=2)["spec_questions"],
                                                 returns["properties"]["spec_questions"]), [])
                self.assertNotEqual(validate_schema("2", returns["properties"]["spec_questions"]), [])

    def test_apply_sets_no_deadline(self):
        for part in (ROOT / "bin" / "apply", ROOT / "bin" / "_lib" / "apply.py"):
            with self.subTest(part.name):
                tree = ast.parse(part.read_text(encoding="utf-8"))
                self.assertEqual([n.lineno for n in ast.walk(tree) if isinstance(n, ast.keyword) and n.arg == "timeout"],
                                 [])

    def test_refused_run_with_pending_reapproval_says_only_the_refusal(self):
        """#565: 知らせは当てた後に出す。断った時は断りの 1 行だけで、当てていない差分に「当てた」と言わない"""
        (self.target / "stats.py").write_text("def mean(xs):\n    return 0\n", encoding="utf-8")
        before = self.status()
        rc, out, err = self.run_apply(self.record(self.value(outcome="needs_human", stop_reason="spec-check:works:spec-changed",
                                                             spec_questions=2)))
        self.assertEqual((rc, out), (1, ""), err)
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertIn("手元の変更", err)
        self.assertNotIn("承認し直す", err)
        self.assertEqual(self.status(), before)

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


class FailedAfterSealTest(TargetCase):
    """#665: 封じた後のノードが落ちてメイングラフの出力が読めない run は、--allow-failed が在れば封じのノードの出力から照らして当てる"""

    def failed_run(self, seal_state="completed", eyes_state="completed", answer=None) -> dict:
        """最後の問いを組むノード ask-final が落ち、result が走らなかった run の workflow get --json の答え。
        seal_state が None なら封じのノードの無い run。answer を渡すと、最後の承認ノードの答え answer-final が済んだ後に report が落ちた run"""
        nodes = [*([{"node_id": apply.SEAL_STEP, "state": seal_state}] if seal_state else []),
                 {"node_id": apply.EYES_STEP, "state": eyes_state}, {"node_id": "ask-final", "state": "completed" if answer else "failed"},
                 {"node_id": "result", "state": "skipped"}]
        failed = "ask-final"
        if answer:
            nodes += [{"node_id": apply.ANSWER_STEP, "state": "completed"}, {"node_id": "report__report", "state": "failed"}]
            failed = "report__report"
        return {"id": RUN, "status": "failed", "working_path": str(self.worktree),
                "terminal_record": {
                    "run_id": RUN, "status": "failed", "outcome": None, "error": f"{failed} failed",
                    "first_failed_node": failed, "nodes": nodes,
                    "returns": {"availability": "unavailable", "node_id": "result", "reason": "node_not_completed"},
                    "artifacts": {"root": str(self.root), "files": [], "limitations": []}}}

    def events(self, seal=None, r2=None, *, seal_data=None, answer=None) -> dict:
        """出来事の列つきの答え。封じのノードの受け皿の出力は素の出力（JSON の字）で、独立の目の受け皿と承認ノードの答えの出力は型つきの出力で持つ"""
        sealed = {"mode": "seal", "ok": True, "hash": sha(self.diff), "diff": pointer("merge/sealed.diff"),
                  "protected_hits": [], "reason": ""} if seal is None else seal
        verdict = {"ok": True, "r1": None, "r2": r2, "r3": None, "r4": None, "questions": [], "premise_check": None,
                   "structure_after": None, "protected_hits": [], "notes": None}
        events = [
            {"event_type": "node_started", "step_name": apply.SEAL_STEP, "data": {}},
            {"event_type": "node_completed", "step_name": apply.SEAL_STEP,
             "data": seal_data if seal_data is not None else {"node_output": json.dumps({"got": sealed, "stop_reason": ""})}},
            {"event_type": "node_completed", "step_name": apply.EYES_STEP,
             "data": json.dumps({"node_output": "", "structured_output": {"got": verdict, "stop_reason": ""}})},
        ]
        if answer:
            events += [{"event_type": "node_completed", "step_name": apply.ANSWER_STEP, "data": {"structured_output": answer}},
                       {"event_type": "node_failed", "step_name": "report__report", "data": {"error": "boom"}}]
        else:
            events.append({"event_type": "node_failed", "step_name": "ask-final", "data": {"error": "output too large"}})
        return {**self.failed_run(answer=answer), "events": events}

    def test_applies_sealed_diff_with_flag(self):
        rc, out, err = self.run_apply(self.failed_run(), "--allow-failed", events=self.events())
        self.assert_applied((rc, out, err))
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        for word in ("ask-final", "人が見るはずだった物", "--allow-failed"):
            self.assertIn(word, err)
        self.assertEqual(self.calls, [(RUN, self.target), (RUN, self.target, *apply.EVENTS_FLAGS)])

    def test_needs_flag(self):
        err = self.assert_refused(self.run_apply(self.failed_run(), events=self.events()), 1, "--allow-failed", "ask-final",
                                  "人が見るはずだった物")
        self.assertNotIn("git -C", err)

    def test_approved_run_whose_report_failed_says_the_human_approved(self):
        go = {"go": True, "answer": {"decision": "approve", "text": "", "asked": []}, "stop_reason": ""}
        rc, out, err = self.run_apply(self.failed_run(answer=go), "--allow-failed", events=self.events(answer=go))
        self.assert_applied((rc, out, err))
        self.assertIn("人は承認した", err)
        self.assertNotIn("人が見るはずだった物", err)

    def assert_go_not_by_a_human(self, go: dict, said: str):
        rc, out, err = self.run_apply(self.failed_run(answer=go), "--allow-failed", events=self.events(answer=go))
        self.assert_applied((rc, out, err))
        self.assertIn(said, err)
        self.assertNotIn("人は承認した", err)

    def test_gate_skipped_by_policy_does_not_say_the_human_approved(self):
        """最後の承認ノードが方針で開かなかった run（answer が null）は、人の承認と言わない"""
        self.assert_go_not_by_a_human({"go": True, "answer": None, "stop_reason": ""}, "機械が通した")

    def test_unattended_push_does_not_say_the_human_approved(self):
        """無人の run が推しで通した run（答えに欄 pushed）は、人の承認と言わない"""
        self.assert_go_not_by_a_human({"go": True, "answer": {"decision": "approve", "text": "", "asked": [], "pushed": ["ask-final"]},
                                       "stop_reason": ""}, "推しで通した")

    def test_run_stopped_at_the_final_gate_whose_report_failed_needs_allow_stopped(self):
        """最後の承認ノードで人が止めた後に report が落ちた run は、--allow-failed だけでは当てない（止めた run の許しを迂回させない）"""
        stop = {"go": False, "answer": {"decision": "stop", "text": "当てない", "asked": []}, "stop_reason": "human:gate-final"}
        run, events = self.failed_run(answer=stop), self.events(answer=stop)
        self.assert_refused(self.run_apply(run, "--allow-failed", events=events), 1, "--allow-stopped", "human:gate-final",
                            "人の一言「当てない」")
        rc, out, err = self.run_apply(run, "--allow-failed", "--allow-stopped", events=events)
        self.assert_applied((rc, out, err))
        for word in ("report__report", "human:gate-final", "--allow-stopped"):
            self.assertIn(word, err)

    def test_unreadable_answer_is_refused(self):
        go = {"go": True, "answer": None, "stop_reason": ""}
        events = self.events(answer=go)
        events["events"] = [e for e in events["events"] if e["step_name"] != apply.ANSWER_STEP]
        self.assert_refused(self.run_apply(self.failed_run(answer=go), "--allow-failed", "--allow-stopped", events=events), 2,
                            apply.ANSWER_STEP, "git -C")

    def test_seal_not_completed_is_refused_as_before(self):
        """封じのノードが済んでいない run は、旗が在っても今どおり拒み、置き場の差分を確かめずに当てる道を言う"""
        place = self.root / "merge" / "apply.diff"
        for state in ("failed", "skipped", "pending"):
            with self.subTest(state=state):
                self.assert_refused(self.run_apply(self.failed_run(seal_state=state), "--allow-failed", events=self.events()),
                                    2, apply.SEAL_STEP, "済んでいない", f"git -C {self.target} apply {place}")
        with self.subTest("封じのノードが無い"):
            self.assert_refused(self.run_apply(self.failed_run(seal_state=None), "--allow-failed", events=self.events()),
                                2, f"この run には封じのノード {apply.SEAL_STEP} が無い", f"git -C {self.target} apply {place}")

    def test_unreadable_seal_output_is_refused(self):
        whole = json.dumps({"got": {"mode": "seal", "ok": True, "hash": sha(self.diff), "diff": pointer("merge/sealed.diff"),
                                    "protected_hits": [], "reason": ""}, "stop_reason": ""})
        cases = {"切り詰めた": {"node_output": whole, "node_output_truncated": True},
                 "JSON でない": {"node_output": "not json"},
                 "出力が無い": {},
                 "受け皿の形でない": {"node_output": json.dumps({"mode": "seal", "ok": True, "hash": sha(self.diff)})},
                 "seal の形でない": {"node_output": json.dumps({"got": {"mode": "apply", "ok": True, "hash": sha(self.diff)}})}}
        for name, data in cases.items():
            with self.subTest(name):
                self.assert_refused(self.run_apply(self.failed_run(), "--allow-failed", events=self.events(seal_data=data)),
                                    2, "出力が読めない", "git -C")
        for name, answer in {"出来事の列が無い": self.failed_run(), "答えが JSON でない": "not json"}.items():
            with self.subTest(name):
                self.assert_refused(self.run_apply(self.failed_run(), "--allow-failed", events=answer), 2, "events", "git -C")
        with self.subTest("封じていない"):
            refused = {"mode": "seal", "ok": False, "hash": "", "diff": None, "protected_hits": [], "reason": "指紋が違う"}
            self.assert_refused(self.run_apply(self.failed_run(), "--allow-failed", events=self.events(seal=refused)), 1,
                                "封じていない", "指紋が違う")
        with self.subTest("独立の目が済んでいない"):
            self.assert_refused(self.run_apply(self.failed_run(eyes_state="failed"), "--allow-failed", events=self.events()),
                                2, apply.EYES_STEP, "R2")

    def test_structured_output_is_read_before_the_truncation_mark(self):
        """Archon の terminal-record.ts と同じく、型つきの出力が在れば切り詰めの印を見ない"""
        got = {"got": {"mode": "seal", "ok": True, "hash": sha(self.diff), "diff": pointer("merge/sealed.diff"),
                       "protected_hits": [], "reason": ""}, "stop_reason": ""}
        data = {"node_output": "{", "node_output_truncated": True, "structured_output": got}
        self.assert_applied(self.run_apply(self.failed_run(), "--allow-failed", events=self.events(seal_data=data)))

    def test_redesign_is_refused_even_with_flag(self):
        events = self.events(r2={"status": "redesign-needed", "reason": "設計を組み直す"})
        err = self.assert_refused(self.run_apply(self.failed_run(), "--allow-failed", events=events), 1, "redesign-needed")
        self.assertNotIn("git -C", err)

    def test_changed_sealed_file_is_refused(self):
        self.place("merge/sealed.diff", self.diff + b"\n")
        self.assert_refused(self.run_apply(self.failed_run(), "--allow-failed", events=self.events()), 1, "封じた hash と合わない")

    def test_steps_are_the_line_seal_and_eyes_receivers_and_the_final_answer(self):
        """SEAL_STEP は mode: seal で merge を include するノードの受け皿、EYES_STEP は merge-apply に r2 を渡すノードの受け皿で、
        どちらも読む欄を names に宣言する。ANSWER_STEP は merge-apply に人の答えを渡すノード。どれもメイングラフの run の記録に出るノードの id"""
        nodes = yaml.safe_load(LINE.read_text(encoding="utf-8"))["nodes"]
        by_id = {n["id"]: n for n in nodes}
        (sealer,) = [n for n in nodes if n.get("include") == "works-factory-merge" and n["with"]["mode"] == "seal"]
        (applier,) = [n for n in nodes if n.get("include") == "works-factory-merge" and n["with"]["mode"] == "apply"]
        eyes_id = applier["with"]["r2"].removeprefix("$").removesuffix(".output.r2")
        for step, source, names in ((apply.SEAL_STEP, sealer["id"], {"mode", "ok", "hash", "diff", "reason"}),
                                    (apply.EYES_STEP, eyes_id, {"r2"})):
            with self.subTest(step):
                self.assertEqual(by_id[step]["script"], "returned")
                self.assertEqual(by_id[step]["with"]["got"], f"${source}.output")
                self.assertLessEqual(names, set(by_id[step]["with"]["names"].split()))
        self.assertEqual(applier["with"]["answer"], f"${apply.ANSWER_STEP}.output.answer")
        self.assertLessEqual({"go", "answer", "stop_reason"}, set(by_id[apply.ANSWER_STEP]["output_format"]["properties"]))
        self.assertLessEqual({apply.SEAL_STEP, apply.EYES_STEP, apply.ANSWER_STEP}, step_names("works-factory-line"))


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

    def test_kept_round_with_spec_questions_notes_reapproval(self):
        """#563: 採る周に承認し直すかの問いが残る鎖の run は、メイングラフと同じく当てて 1 行で知らせる"""
        code, out, err = self.run_apply(self.parent_run(spec={2: 2}))
        self.assertEqual((code, self.present()), (0, ["one.txt", "two.txt"]), out + err)
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        for word in ("承認し直す", "2 件"):
            self.assertIn(word, err)

    def test_questions_of_the_halted_round_that_is_not_taken_say_nothing(self):
        code, out, err = self.run_apply(self.parent_run(spec={3: 4}))
        self.assertEqual((code, self.present()), (0, ["one.txt", "two.txt"]), out + err)
        self.assertEqual(err, "")

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

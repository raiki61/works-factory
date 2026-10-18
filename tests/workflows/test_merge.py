"""ブロック merge（workflows/merge/）の YAML の形・script の通し・筋書きの試験。

- YAML の形は PyYAML で読み、Archon を起こさない（返りの約束の欄・入力・照らし・commit・PR の子の run・読み戻し・返す節の 5 つの節）
- script は subprocess で、一時の git の木を cwd に、Archon が script の節に渡す環境（WORKFLOW_ID・ARTIFACTS_DIR・INPUTS_*）を偽の run で作って走らせる。
  照らしの節はどの走りでも作業ツリーの `git status --porcelain` が前後で同じ（E6・E7）。commit の節は run の作業ツリー（worktree）の
  枝にだけ積み、origin へは何も送らない
- 筋書き（fixtures/）は tests/archon.py の使い捨ての木で `workflow test` に回し、返す節の渡し方を dry-run の trace で照らす。Archon の源が無ければ見送る
"""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

from tests import archon
from tests.bin import hermetic
from tests.bin.gitkit import commit_absent, git
from tests.e2e.test_line_scenarios import dry_run_traces

ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import entry  # noqa: E402
import green_cert  # noqa: E402
import listcut  # noqa: E402
from graphloops.engine.schema import validate_schema  # noqa: E402
import protect  # noqa: E402
import seal  # noqa: E402
import tree_run  # noqa: E402
import userenv  # noqa: E402

BLOCK = ROOT / "workflows" / "merge"
YAML = BLOCK / "works-factory-merge.yaml"
SCRIPTS = BLOCK / "scripts"
SCRIPT = SCRIPTS / "merge.py"
NAME = "works-factory-merge"
RUN = "run-merge"
INPUTS = ("mode", "start", "base_rev", "fingerprint", "green_ok", "eyes_ok", "sealed_hash", "answer", "r2", "deliver", "request", "items",
          "user_env_dir")
PLACE_INPUTS = ("mode", "start", "base_rev", "fingerprint", "green_ok", "eyes_ok", "sealed_hash", "answer", "r2", "deliver")
RETURNS = ("mode", "ok", "hash", "diff", "protected_hits", "protected_count", "reason", "deliver", "optional")
PLACE_RETURNS = ("mode", "ok", "hash", "diff", "protected_hits", "protected_count", "reason", "base_rev", "deliver")
PROTECTED_FILE = "merge/protected-all.json"
PASS = json.dumps({"decision": "continue", "text": ""})
URL = "https://github.com/o/r.git"
SCENARIOS = ("apply", "apply-refused", "empty-diff", "pr", "pr-child-failed", "pr-same-branch", "seal")


def load() -> dict:
    return yaml.safe_load(YAML.read_text(encoding="utf-8"))


def nodes() -> dict:
    return {n["id"]: n for n in load()["nodes"]}


def output_format(node: str = "place") -> dict:
    return nodes()[node]["output_format"]


def run_node(script: str, env: dict, cwd: pathlib.Path, node: str) -> dict:
    """merge の script を Archon と同じく子のプロセスで走らせ、終了の値 0 と返りが節の output_format に合うことを確かめて返す"""
    done = subprocess.run([sys.executable, str(SCRIPTS / f"{script}.py")], cwd=cwd,
                          env=hermetic.child_env(PYTHONDONTWRITEBYTECODE="1", WORKFLOW_ID=RUN, **env),
                          capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise AssertionError(f"{script} が終了の値 {done.returncode}: {done.stderr}")
    got = json.loads(done.stdout)
    errors = validate_schema(got, output_format(node))
    if errors:
        raise AssertionError(f"{script} の返りが output_format に合わない: {errors}: {got}")
    return got


class ShapeTest(unittest.TestCase):
    def setUp(self):
        self.doc = load()
        self.nodes = nodes()
        self.node = self.nodes["place"]

    def test_header(self):
        self.assertEqual(self.doc["name"], NAME)
        self.assertEqual(self.doc["returns"], "merge")
        self.assertEqual(self.doc["outcome_field"], "ok")
        self.assertNotIn("interactive", self.doc)

    def test_nodes_are_place_the_pr_path_and_the_return(self):
        self.assertEqual(list(self.nodes), ["place", "pr-commit", "pr-open", "pr-read", "merge"])
        for node, script in (("place", "merge"), ("pr-commit", "pr_commit"), ("pr-read", "pr_read"), ("merge", "handed")):
            self.assertEqual((self.nodes[node]["script"], self.nodes[node]["runtime"]), (script, "uv"), node)
        for node in ("place", "pr-read", "merge"):
            self.assertIs(self.nodes[node]["mutates_checkout"], False, node)
        self.assertNotIn("mutates_checkout", self.nodes["pr-commit"], "commit の節は HEAD と index を変える")
        for node in self.nodes.values():
            self.assertNotIn("timeout", node)
        self.assertFalse(any("approval" in n or "wait" in n for n in self.doc["nodes"]))

    def test_pr_path_runs_only_after_the_check_for_the_word_pr(self):
        """出口の語 pr で照らしが通った時だけ commit し、commit が進めた時だけ PR を作る子の run を起こす（既定の空の語は対象に書かない）"""
        commit, opened, read = self.nodes["pr-commit"], self.nodes["pr-open"], self.nodes["pr-read"]
        self.assertEqual(commit["when"], f"$place.output.ok == true && $place.output.deliver == '{entry.DELIVER_PR}'"
                                         " && $place.output.mode != 'seal'")
        self.assertEqual(commit["with"], {"mode": "$place.output.mode", "base_rev": "$place.output.base_rev",
                                          "sealed_hash": "$place.output.hash", "request": "$INPUTS.request", "items": "$INPUTS.items",
                                          "user_env_dir": "$INPUTS.user_env_dir"})
        self.assertEqual((opened["workflow"], opened["when"]), ("archon-pr", "$pr-commit.output.go == true"))
        self.assertEqual(opened["with"], {"branch": "$pr-commit.output.branch"}, "push の先の枝は commit の節が積んだ枝（AI に決めさせない）")
        self.assertNotIn("input", opened)
        self.assertEqual(read["depends_on"], ["pr-open"])
        self.assertEqual(read["with"], {"got": "$pr-open.output", "head": "$pr-commit.output.head", "branch": "$pr-commit.output.branch",
                                        "base_branch": "$pr-commit.output.base", "repo": "$pr-commit.output.repo"})
        self.assertNotIn("trigger_rule", read, "子の run が落ちたら読み戻しの節は飛ぶ（返す節が落ちない）")
        handed = self.nodes["merge"]
        self.assertEqual(handed["trigger_rule"], "all_done")
        self.assertEqual(handed["with"]["commit"], {"from": "$pr-commit.output", "if_skipped": None})
        self.assertEqual(handed["with"]["read"], {"from": "$pr-read.output", "if_skipped": None})
        self.assertEqual(json.loads(handed["with"]["optional"]), [{"node": "pr-open", "bare": False}])

    def test_inputs_are_the_contract(self):
        inputs = self.doc["inputs"]
        self.assertEqual(sorted(inputs), sorted(INPUTS))
        self.assertIs(inputs["mode"].get("required"), True)
        for name in set(INPUTS) - {"mode"}:
            self.assertEqual(inputs[name].get("default"), "", name)
        self.assertEqual(self.node["with"], {name: f"$INPUTS.{name}" for name in PLACE_INPUTS})

    def test_output_format_is_the_contract(self):
        for node, names in (("merge", RETURNS), ("place", PLACE_RETURNS)):
            with self.subTest(node=node):
                fmt = self.nodes[node]["output_format"]
                self.assertEqual(sorted(fmt["properties"]), sorted(names))
                self.assertEqual(sorted(fmt["required"]), sorted(names))
                self.assertIs(fmt["additionalProperties"], False)
                props = fmt["properties"]
                self.assertEqual(props["mode"]["enum"], ["seal", "apply", "check"])
                self.assertEqual(props["ok"]["type"], "boolean")
                self.assertIn("null", props["diff"]["type"])
                self.assertIn("null", props["protected_hits"]["type"])
                self.assertEqual(props["protected_count"]["type"], ["integer", "null"])
                self.assertEqual(sorted(props["diff"]["properties"]["path"]["enum"]),
                                 sorted(["merge/sealed.diff", "merge/apply.diff", "merge/refused.diff"]))
        self.assertEqual(self.nodes["merge"]["output_format"]["properties"]["deliver"]["properties"]["act"]["enum"],
                         ["placed", "none", "pr", "stopped", "unconfirmed"])


class ScriptCase(unittest.TestCase):
    """一時の git の木（1 本の commit の後に 1 ファイルを書き換えた物）と、偽の run の置き場"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        (self.repo / "a.txt").write_text("one\n", encoding="utf-8")
        git(self.repo, "add", "a.txt")
        git(self.repo, "commit", "-q", "-m", "seed")
        self.base = git(self.repo, "rev-parse", "HEAD")
        (self.repo / "a.txt").write_text("two\n", encoding="utf-8")
        self.artifacts = self.tmp / "artifacts"
        self.artifacts.mkdir()
        self.start = self.place("start.json", json.dumps({"base_rev": self.base}))

    def place(self, rel: str, text: str) -> str:
        path = self.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return json.dumps({"type": "archon_artifact", "run_id": RUN, "path": rel})

    def fingerprint(self) -> str:
        return json.dumps(green_cert.fingerprint(self.repo))

    def run_script(self, cwd=None, root=ROOT, **inputs) -> dict:
        """script を走らせ、終了の値 0・返りが output_format に合う・作業ツリーが前後で同じことを確かめて返りを返す"""
        cwd = self.repo if cwd is None else cwd
        env = hermetic.child_env(WORKFLOW_ID=RUN, ARTIFACTS_DIR=str(self.artifacts), WORKS_FACTORY_ROOT=str(root),
                                 PYTHONDONTWRITEBYTECODE="1", **{f"INPUTS_{name.upper()}": inputs.get(name, "") for name in PLACE_INPUTS})
        status = self.status(cwd)
        done = subprocess.run([sys.executable, str(SCRIPT)], cwd=cwd, env=env, capture_output=True, text=True,
                              encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.status(cwd), status, "作業ツリーを変えた")
        got = json.loads(done.stdout)
        self.assertEqual(validate_schema(got, output_format()), [], got)
        return got

    @staticmethod
    def status(cwd):
        done = subprocess.run(["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True, env=hermetic.child_env())
        return done.stdout if done.returncode == 0 else None

    def seal(self, **over) -> dict:
        inputs = {"mode": "seal", "start": self.start, "fingerprint": self.fingerprint(),
                  "green_ok": "true", "eyes_ok": "true", "sealed_hash": "null", "answer": "null", "r2": "null"}
        return self.run_script(**{**inputs, **over})

    def apply(self, sealed_hash: str, **over) -> dict:
        inputs = {"mode": "apply", "start": self.start, "fingerprint": self.fingerprint(),
                  "green_ok": "true", "eyes_ok": "true", "sealed_hash": sealed_hash, "answer": PASS, "r2": "null"}
        return self.run_script(**{**inputs, **over})

    def artifact(self, rel: str) -> pathlib.Path:
        return self.artifacts / rel

    def touch_protected(self, *marks: str) -> str:
        """一覧の glob の無い行のファイルを書く。marks があれば先にそれを commit して base_rev にし、git update-index の印 marks を付けてから書き換える"""
        rule = next(r for r in protect.rules(protect.load()) if not any(c in r["glob"] for c in "*?["))
        path = self.repo / rule["glob"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if marks:
            path.write_text("x\n", encoding="utf-8")
            git(self.repo, "add", rule["glob"])
            git(self.repo, "commit", "-q", "-m", "protected")
            self.base = git(self.repo, "rev-parse", "HEAD")
            self.start = self.place("start.json", json.dumps({"base_rev": self.base}))
            for mark in marks:
                git(self.repo, "update-index", mark, rule["glob"])
        path.write_text("y\n", encoding="utf-8")
        return rule["glob"]


class SealTest(ScriptCase):
    def test_seal_hashes_the_written_diff(self):
        got = self.seal()
        self.assertEqual((got["mode"], got["ok"], got["reason"]), ("seal", True, ""))
        self.assertEqual(got["diff"], {"type": "archon_artifact", "run_id": RUN, "path": "merge/sealed.diff"})
        written = self.artifact("merge/sealed.diff").read_bytes()
        self.assertEqual(got["hash"], hashlib.sha256(written).hexdigest())
        self.assertEqual(written, green_cert.diff_bytes(self.repo, self.base))
        self.assertEqual((got["protected_hits"], got["protected_count"]), ([], 0))

    def test_changed_fingerprint_refuses_but_writes(self):
        moved = json.dumps({**green_cert.fingerprint(self.repo), "diff_hash": "0" * 64})
        got = self.seal(fingerprint=moved)
        self.assertIs(got["ok"], False)
        self.assertIn("緑の認証の指紋が今の木と違う", got["reason"])
        self.assertTrue(self.artifact("merge/sealed.diff").is_file())

    def test_protected_hit_is_named(self):
        glob = self.touch_protected()
        got = self.seal()
        self.assertEqual(len(got["protected_hits"]), 1, got)
        self.assertTrue(got["protected_hits"][0].startswith(glob))

    def test_many_protected_hits_keep_the_return_short(self):
        """守りのファイルに当たった物が何本でも、返りの protected_hits は先頭 SHOWN 行と残りの 1 行だけで、全件の数は
        protected_count、全件は置き場の merge/protected-all.json に残る（20,000 本の時の最後の承認ノードの文は test_line が見る）"""
        many = listcut.SHOWN * 40
        (self.repo / ".works-protected.json").write_text(
            json.dumps({"rules": [{"id": "gen", "glob": "gen/**", "why": "生成物"}]}), encoding="utf-8")
        git(self.repo, "add", ".works-protected.json")
        self.base = commit_absent(self.repo, [f"gen/{i}.o" for i in range(many)])
        self.start = self.place("start.json", json.dumps({"base_rev": self.base}))
        got = self.seal(fingerprint=self.fingerprint())
        whole = json.loads(self.artifact(PROTECTED_FILE).read_text(encoding="utf-8"))["protected_hits"]
        self.assertEqual((got["protected_count"], len(whole)), (many, many))
        self.assertEqual(got["protected_hits"][:listcut.SHOWN], whole[:listcut.SHOWN])
        self.assertEqual(got["protected_hits"][listcut.SHOWN:], [
            f"{protect.LIST}（protected_hits）の" + listcut.REST.format(n=many - listcut.SHOWN)
            + f"（全件: {self.artifact(PROTECTED_FILE)}）"])

    def test_index_marks_do_not_hide_a_protected_hit(self):
        for mark in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(mark=mark):
                self.setUp()
                glob = self.touch_protected(mark)
                got = self.seal()
                self.assertEqual(len(got["protected_hits"]), 1, got)
                self.assertTrue(got["protected_hits"][0].startswith(f"{glob}（+1 −1）"), got)
                refused = self.apply(got["hash"], answer="null")
                self.assertIs(refused["ok"], False, refused)
                self.assertIn("守りのパス", refused["reason"])
                self.assertFalse(self.artifact("merge/apply.diff").exists())

    def test_broken_manifest_is_an_unknown_hit_and_blocks_apply_without_answer(self):
        root = self.tmp / "root"
        shutil.copytree(LIB, root / "lib", ignore=shutil.ignore_patterns("__pycache__"))
        (root / "lib" / "protected.json").write_text("{", encoding="utf-8")
        sealed = self.seal(root=root)
        self.assertEqual(len(sealed["protected_hits"]), 1)
        self.assertTrue(sealed["protected_hits"][0].startswith(seal.unknown_row("")))
        got = self.apply(sealed["hash"], root=root, answer="null")
        self.assertIs(got["ok"], False)
        self.assertIn("守りのパスを確かめられない", got["reason"])
        self.assertFalse(self.artifact("merge/apply.diff").exists())

    def test_uncountable_diff_is_an_unknown_hit(self):
        """seal.diff_files が ValueError を投げる（PATH の頭の偽の git が git apply だけを落とす）と、守りの当たりは
        確かめられなかった 1 行になり、答え無しの apply はそれで拒む"""
        fake = self.tmp / "bin"
        fake.mkdir()
        (fake / "git").write_text(f'#!/bin/sh\n[ "$1" = apply ] && {{ echo "偽の git" >&2; exit 1; }}\n'
                                  f'exec "{shutil.which("git")}" "$@"\n', encoding="utf-8")
        (fake / "git").chmod(0o755)
        with mock.patch.dict(os.environ, {"PATH": f"{fake}{os.pathsep}{os.environ['PATH']}"}):
            sealed = self.seal()
            self.assertEqual(len(sealed["protected_hits"]), 1, sealed)
            self.assertTrue(sealed["protected_hits"][0].startswith(seal.unknown_row("")), sealed)
            self.assertIn("偽の git", sealed["protected_hits"][0])
            got = self.apply(sealed["hash"], answer="null")
        self.assertIs(got["ok"], False)
        self.assertIn("守りのパスを確かめられない", got["reason"])
        self.assertFalse(self.artifact("merge/apply.diff").exists())

    def test_sealed_diff_has_no_runtime_folder(self):
        copy = self.repo / ".archon" / "workflows" / "works-factory" / "x.yaml"
        copy.parent.mkdir(parents=True)
        copy.write_text("RUNTIME = 1\n", encoding="utf-8")
        got = self.seal()
        written = self.artifact("merge/sealed.diff").read_bytes()
        self.assertNotIn(b".archon/", written)
        self.assertIn(b"a.txt", written)
        applied = self.apply(got["hash"])
        self.assertIs(applied["ok"], True, applied)
        self.assertEqual(self.artifact("merge/apply.diff").read_bytes(), written)

    def test_empty_diff_is_null(self):
        (self.repo / "a.txt").write_text("one\n", encoding="utf-8")
        got = self.seal()
        self.assertEqual((got["ok"], got["hash"], got["diff"]), (False, "", None))
        self.assertIn("差分が空", got["reason"])


class ApplyTest(ScriptCase):
    def setUp(self):
        super().setUp()
        self.sealed = self.seal()["hash"]

    def test_same_tree_applies_the_sealed_diff(self):
        got = self.apply(self.sealed)
        self.assertEqual((got["mode"], got["ok"], got["reason"], got["protected_hits"]), ("apply", True, "", None))
        self.assertEqual(got["diff"]["path"], "merge/apply.diff")
        self.assertEqual(got["hash"], self.sealed)
        self.assertEqual(hashlib.sha256(self.artifact("merge/apply.diff").read_bytes()).hexdigest(), self.sealed)

    def test_tree_changed_after_seal_refuses(self):
        (self.repo / "a.txt").write_text("three\n", encoding="utf-8")
        got = self.apply(self.sealed)
        self.assertIs(got["ok"], False)
        self.assertIn("封じた差分と今の差分が違う", got["reason"])
        self.assertFalse(self.artifact("merge/apply.diff").exists())
        self.assertEqual(got["diff"]["path"], "merge/refused.diff")
        refused = self.artifact("merge/refused.diff").read_bytes()
        self.assertTrue(refused)
        self.assertEqual(got["hash"], hashlib.sha256(refused).hexdigest())

    def test_refused_retry_removes_the_earlier_apply(self):
        self.assertIs(self.apply(self.sealed)["ok"], True)
        (self.repo / "a.txt").write_text("three\n", encoding="utf-8")
        self.assertIs(self.apply(self.sealed)["ok"], False)
        self.assertFalse(self.artifact("merge/apply.diff").exists())

    def assertRefused(self, got, words):
        self.assertIs(got["ok"], False)
        self.assertIn(words, got["reason"])
        self.assertFalse(self.artifact("merge/apply.diff").exists())

    def test_stop_answer_refuses(self):
        self.assertRefused(self.apply(self.sealed, answer=json.dumps({"decision": "stop", "text": ""})),
                           "最後の承認ノードで stop と答えた")

    def test_no_answer_and_red_refuses(self):
        self.assertRefused(self.apply(self.sealed, answer="null", green_ok="false"), "人の通しの答えが無いのに")

    def test_no_answer_and_clean_run_applies_only_when_every_check_passed(self):
        moved = json.dumps({**green_cert.fingerprint(self.repo), "diff_hash": "0" * 64})
        for over, words in (({}, ""), ({"eyes_ok": "false"}, "目が通していない"), ({"fingerprint": moved}, "指紋")):
            with self.subTest(over=over):
                shutil.rmtree(self.artifact("merge"))
                got = self.apply(self.sealed, answer="null", **over)
                self.assertEqual(got["ok"], not words, got)
                self.assertIn(words, got["reason"])
                self.assertEqual(self.artifact("merge/apply.diff").exists(), not words)

    def test_no_answer_and_protected_hit_refuses(self):
        self.touch_protected()
        sealed = self.seal(fingerprint=self.fingerprint())["hash"]
        self.assertRefused(self.apply(sealed, answer="", fingerprint=self.fingerprint()), "守りのパス")

    def test_apply_refuses_target_protected_hit_without_answer(self):
        (self.repo / ".works-protected.json").write_text(
            json.dumps({"rules": [{"id": "core", "glob": "a.txt", "why": "対象の芯"}]}), encoding="utf-8")
        git(self.repo, "add", ".works-protected.json")
        git(self.repo, "commit", "-q", "-m", "declare")
        self.base = git(self.repo, "rev-parse", "HEAD")
        self.start = self.place("start.json", json.dumps({"base_rev": self.base}))
        (self.repo / ".works-protected.json").unlink()
        sealed = self.seal(fingerprint=self.fingerprint())
        self.assertEqual([h.split("（")[0] for h in sealed["protected_hits"]], [".works-protected.json", "a.txt"], sealed)
        self.assertRefused(self.apply(sealed["hash"], answer="", fingerprint=self.fingerprint()), "守りのパス")
        self.assertIs(self.apply(sealed["hash"], fingerprint=self.fingerprint())["ok"], True)

    def test_unverifiable_r2_with_approve_applies(self):
        got = self.apply(self.sealed, eyes_ok="false", answer=json.dumps({"decision": "approve", "text": ""}),
                         r2=json.dumps({"status": "unverifiable", "reason": "比べの節が落ちた"}))
        self.assertIs(got["ok"], True, got)

    def test_redesign_r2_with_continue_refuses(self):
        self.assertRefused(self.apply(self.sealed, r2=json.dumps({"status": "redesign-needed", "reason": "別の設計"})),
                           "R2 が作り直しと言った")


class CheckTest(ScriptCase):
    """check は封じた hash を入力 base_rev からの今の差分と照らすだけで置く（関所の答え・緑・目は読まない）"""

    def check(self, sealed_hash: str, **over) -> dict:
        return self.run_script(**{"mode": "check", "base_rev": self.base, "sealed_hash": sealed_hash, "deliver": "pr", **over})

    def test_same_diff_is_placed_with_the_root_and_the_word(self):
        sealed = seal.digest(green_cert.diff_bytes(self.repo, self.base))
        got = self.check(sealed)
        self.assertEqual((got["mode"], got["ok"], got["hash"], got["reason"]), ("check", True, sealed, ""))
        self.assertEqual((got["base_rev"], got["deliver"], got["diff"]["path"]), (self.base, "pr", "merge/apply.diff"))
        self.assertEqual((got["protected_hits"], got["protected_count"]), (None, None))

    def test_other_diff_is_refused(self):
        got = self.check("0" * 64)
        self.assertIs(got["ok"], False)
        self.assertIn("封じた差分と今の差分が違う", got["reason"])
        self.assertFalse(self.artifact("merge/apply.diff").exists())
        self.assertEqual(got["diff"]["path"], "merge/refused.diff")

    def test_missing_root_is_refused(self):
        got = self.check("0" * 64, base_rev="")
        self.assertEqual((got["ok"], got["diff"]), (False, None))
        self.assertIn("base_rev", got["reason"])


class PrCommitTest(unittest.TestCase):
    """出口の語 pr の commit の節: run の作業ツリー（worktree）の枝にだけ、照らした差分を修正案の項目ごとの commit で積む（分けられなければ 1 つ）。origin へは送らない"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.origin = self.tmp / "origin.git"
        git(self.tmp, "init", "-q", "--bare", "-b", "main", str(self.origin))
        self.main = self.tmp / "main"
        git(self.tmp, "clone", "-q", str(self.origin), str(self.main))
        (self.main / "a.txt").write_text("one\n", encoding="utf-8")
        git(self.main, "add", "a.txt")
        git(self.main, "commit", "-q", "-m", "seed")
        git(self.main, "push", "-q", "origin", "main")
        self.base = git(self.main, "rev-parse", "HEAD")
        self.run_tree = self.tmp / "run"
        git(self.main, "worktree", "add", "-q", "-b", "archon/task-run", str(self.run_tree))
        # commit の節は repo を remote.origin.url の字から決め、git は insteadOf で置き換えた先（ローカルの origin）を読む
        git(self.main, "config", "remote.origin.url", URL)
        git(self.main, "config", f"url.{self.origin}.insteadOf", URL)
        (self.run_tree / "a.txt").write_text("two\n", encoding="utf-8")
        (self.run_tree / "new.txt").write_text("new\n", encoding="utf-8")
        copy = self.run_tree / ".archon" / "workflows" / "x.yaml"
        copy.parent.mkdir(parents=True)
        copy.write_text("RUNTIME = 1\n", encoding="utf-8")
        self.sealed = seal.digest(green_cert.diff_bytes(self.run_tree, self.base, skip=(".archon/",)))
        self.artifacts = self.tmp / "artifacts"
        self.artifacts.mkdir()

    def commit(self, cwd=None, env=None, **over) -> dict:
        inputs = {"mode": "apply", "base_rev": self.base, "sealed_hash": self.sealed, "request": "", **over}
        env = {"ARTIFACTS_DIR": str(self.artifacts), **(env or {}), **{f"INPUTS_{k.upper()}": v for k, v in inputs.items()}}
        return run_node("pr_commit", env, self.run_tree if cwd is None else cwd, "pr-commit")

    def remote_heads(self) -> str:
        return git(self.origin, "for-each-ref", "--format=%(refname)")

    def assertStopped(self, got, words: str):
        self.assertIs(got["go"], False, got)
        self.assertIn(words, got["reason"])
        self.assertIsNone(got["repo"])

    def test_checked_diff_is_one_commit_on_the_run_branch_without_the_runtime_copy(self):
        got = self.commit()
        self.assertEqual((got["go"], got["branch"], got["base"], got["repo"], got["reason"]),
                         (True, "archon/task-run", "main", {"host": "github.com", "path": "o/r"}, ""), got)
        self.assertEqual(got["head"], git(self.run_tree, "rev-parse", "HEAD"))
        self.assertEqual(git(self.run_tree, "rev-list", "--count", f"{self.base}..HEAD"), "1")
        self.assertEqual(git(self.run_tree, "diff", "--name-only", self.base, "HEAD").split(), ["a.txt", "new.txt"])
        subject, body = git(self.run_tree, "log", "-1", "--format=%s"), git(self.run_tree, "log", "-1", "--format=%b")
        self.assertIn(RUN, subject)
        for words in (self.sealed, f"run: {RUN}", f"workflow get {RUN}", "対象の既定の枝 main", "merge の apply"):
            self.assertIn(words, body)
        self.assertEqual(git(self.main, "rev-parse", "main"), self.base, "利用者の枝は動かさない")
        self.assertEqual(self.remote_heads(), "refs/heads/main", "commit の節は push しない")

    ADD = "読み口 read_rows を lib に足し、行の形を 1 か所で決める"
    USE = "呼び手を読み口 read_rows に寄せ、写しの読みを消す"

    def record(self, claims) -> str:
        """項目 1 が項目 2 に依存する修正の段の記録（番号の順と依存の順が逆）"""
        return json.dumps({"items": [{"item": 1, "unit_keys": ["u1"], "approach": self.USE, "after": [2]},
                                     {"item": 2, "unit_keys": ["u2"], "approach": self.ADD, "after": []}],
                           "claims": [{"unit_key": k, "files": f} for k, f in claims], "unread": []}, ensure_ascii=False)

    def test_two_items_are_two_commits_in_dependency_order(self):
        """#569: 項目ごとに 1 つの commit。並びは依存の位相順（項目 2 が先）、題と本文は項目から作り、最後の commit に対を書く"""
        got = self.commit(items=self.record([("u1", ["a.txt"]), ("u2", ["new.txt"])]))
        self.assertIs(got["go"], True, got)
        heads = git(self.run_tree, "rev-list", "--reverse", f"{self.base}..HEAD").split()
        self.assertEqual(len(heads), 2)
        self.assertEqual([c["item"] for c in got["commits"]], [2, 1])
        self.assertEqual([c["head"] for c in got["commits"]], heads)
        self.assertEqual((got["head"], got["split"]), (heads[-1], ""))
        self.assertEqual([git(self.run_tree, "diff-tree", "--no-commit-id", "--name-only", "-r", h).split() for h in heads],
                         [["new.txt"], ["a.txt"]])
        subjects = [git(self.run_tree, "log", "-1", "--format=%s", h) for h in heads]
        self.assertTrue(subjects[0].startswith("項目 2: 読み口 read_rows を lib に足し"), subjects)
        self.assertTrue(subjects[1].startswith("項目 1: 呼び手を読み口"), subjects)
        first, last = (git(self.run_tree, "log", "-1", "--format=%b", h) for h in heads)
        self.assertIn(self.ADD, first)
        self.assertNotIn(self.sealed, first, "照らしの要約は最後の commit だけ")
        self.assertIn("項目 2 に依存する", last)
        for words in (self.sealed, f"run: {RUN}", "対象の既定の枝 main", f"- 項目 2: {heads[0]}", "- 項目 1: この commit",
                      "各 commit の時点で試験が通るかは確かめていない"):
            self.assertIn(words, last)
        self.assertEqual(seal.digest(green_cert.diff_between(self.run_tree, self.base, heads[-1], skip=(".archon/",))), self.sealed)
        self.assertEqual(git(self.run_tree, "status", "--porcelain", "--", ".", ":(exclude).archon"), "")

    def test_paths_no_single_item_owns_fall_back_to_one_commit_with_the_reason(self):
        for claims, words in (([("u1", ["a.txt", "new.txt"]), ("u2", ["new.txt"])], "複数の項目か項目の外の単位が触った: new.txt"),
                              ([("u1", ["a.txt"])], "どの項目も申告していない: new.txt"),
                              ([("u1", ["a.txt"]), ("u9", ["new.txt"])], "項目の外の単位")):
            with self.subTest(words=words):
                git(self.run_tree, "reset", "-q", self.base)
                got = self.commit(items=self.record(claims))
                self.assertEqual((got["go"], got["commits"]), (True, []), got)
                self.assertIn(words, got["split"])
                self.assertEqual(git(self.run_tree, "rev-list", "--count", f"{self.base}..HEAD"), "1")
                self.assertIn(f"1 つの commit にまとめた訳: {got['split']}", git(self.run_tree, "log", "-1", "--format=%b"))

    def test_run_without_the_item_record_is_one_commit(self):
        got = self.commit()
        self.assertEqual((got["go"], got["commits"]), (True, []))
        self.assertIn("修正案の項目の記録が無い", got["split"])

    def test_stacked_tree_is_checked_against_the_sealed_hash_as_a_whole(self):
        """項目の commit を積み終えた木の差分を封じた hash と照らす（hooks が途中の commit の中身を変えれば push しない）"""
        self.hook("git diff --cached --name-only | grep -q new.txt && { echo more >> new.txt; git add new.txt; }\nexit 0\n")
        got = self.commit(items=self.record([("u1", ["a.txt"]), ("u2", ["new.txt"])]))
        self.assertStopped(got, "差分が封じた差分と違う")

    def hook(self, script: str) -> None:
        hook = self.tmp / "hooks" / "pre-commit"
        hook.parent.mkdir()
        hook.write_text("#!/bin/sh\n" + script, encoding="utf-8")
        hook.chmod(0o755)
        git(self.main, "config", "core.hooksPath", str(hook.parent))

    def test_failing_hook_on_a_later_item_is_restacked_as_one_commit_with_the_reason(self):
        """項目ごとの commit の途中で hooks が落ちても、最後の木で hooks が通れば 1 つの commit に積み直して進む"""
        self.hook("staged=$(git diff --cached --name-only)\necho \"$staged\" | grep -q new.txt && exit 0\n"
                  "echo \"$staged\" | grep -q a.txt && { echo 'a だけの誤り' >&2; exit 1; }\nexit 0\n")
        got = self.commit(items=self.record([("u1", ["a.txt"]), ("u2", ["new.txt"])]))
        self.assertEqual((got["go"], got["commits"]), (True, []), got)
        self.assertIn("項目ごとの 2 本目で hooks が落ちた: ", got["split"])
        self.assertIn("a だけの誤り", got["split"])
        self.assertEqual(git(self.run_tree, "rev-list", "--count", f"{self.base}..HEAD"), "1", "途中まで積んだ commit は残さない")
        self.assertEqual(got["head"], git(self.run_tree, "rev-parse", "HEAD"))
        self.assertIn(f"1 つの commit にまとめた訳: {got['split']}", git(self.run_tree, "log", "-1", "--format=%b"))
        self.assertEqual(seal.digest(green_cert.diff_between(self.run_tree, self.base, got["head"], skip=(".archon/",))), self.sealed)

    def test_hook_failing_on_the_restacked_commit_too_leaves_no_commit(self):
        self.hook("git diff --cached --name-only | grep -q a.txt && { echo 'a の誤り' >&2; exit 1; }\nexit 0\n")
        got = self.commit(items=self.record([("u1", ["a.txt"]), ("u2", ["new.txt"])]))
        self.assertStopped(got, "a の誤り")
        self.assertEqual(git(self.run_tree, "rev-parse", "HEAD"), self.base, "積み始める前の HEAD に戻す")
        self.assertEqual(seal.digest(green_cert.diff_bytes(self.run_tree, self.base, skip=(".archon/",))), self.sealed,
                         "作業ツリーの変更は残す")

    def test_branch_named_like_the_default_branch_is_not_committed_nor_pushed(self):
        """run の枝の名が対象の既定の枝と同じ時は、積まず・PR を作る子の run へ進めない（既定の枝へは push しない）"""
        same = self.tmp / "same"
        git(self.main, "branch", "-q", "-m", "main", "local-seed")
        git(self.main, "worktree", "add", "-q", "-b", "main", str(same), self.base)
        (same / "a.txt").write_text("two\n", encoding="utf-8")
        got = self.commit(cwd=same, sealed_hash=seal.digest(green_cert.diff_bytes(same, self.base)))
        self.assertStopped(got, "run の枝 main が対象の既定の枝と同じ名")
        self.assertEqual(git(same, "rev-parse", "HEAD"), self.base, "積まない")
        self.assertEqual(git(self.origin, "rev-parse", "main"), self.base, "origin の既定の枝は動かない")

    def test_other_diff_is_not_committed(self):
        got = self.commit(sealed_hash="0" * 64)
        self.assertStopped(got, "封じた差分と今の差分が違う")
        self.assertEqual(git(self.run_tree, "rev-parse", "HEAD"), self.base)

    def test_unreadable_default_branch_stops(self):
        git(self.run_tree, "remote", "remove", "origin")
        got = self.commit()
        self.assertStopped(got, "既定の枝を読めない")
        self.assertEqual(git(self.run_tree, "rev-parse", "HEAD"), self.base)

    def test_main_tree_and_detached_head_are_refused(self):
        (self.main / "a.txt").write_text("two\n", encoding="utf-8")
        self.assertStopped(self.commit(cwd=self.main), "本体の作業ツリーでは commit しない")
        git(self.run_tree, "checkout", "-q", "--detach")
        self.assertStopped(self.commit(), "切り離された HEAD")

    def test_issue_named_by_the_request_is_a_non_closing_reference_in_the_commit(self):
        request = self.tmp / "request.json"
        request.write_text(json.dumps({"findings": [{"where": "a.txt", "text": "x"}], "issue": [555]}), encoding="utf-8")
        self.assertIs(self.commit(request=str(request))["go"], True)
        self.assertIn("Refs #555", git(self.run_tree, "log", "-1", "--format=%b").splitlines())

    def test_failing_commit_hook_stops_without_a_commit(self):
        """対象の commit の hooks は飛ばさない。落ちれば積まずに止め、hooks の言葉を訳に載せる"""
        self.hook("echo 'lint の誤り' >&2\nexit 1\n")
        got = self.commit()
        self.assertStopped(got, "hooks")
        self.assertIn("lint の誤り", got["reason"])
        self.assertEqual(git(self.run_tree, "rev-parse", "HEAD"), self.base)

    def test_commit_hook_sees_the_read_only_gh_first(self):
        """hooks は対象のコマンドなので、起動の殻が渡した読むだけの gh の置き場が PATH の頭に在る"""
        seen = self.tmp / "path.txt"
        self.hook(f"printf '%s' \"$PATH\" > '{seen}'\n")
        read_gh = self.tmp / "read-gh"
        self.assertIs(self.commit(env={userenv.READ_GH_ENV: str(read_gh)})["go"], True)
        entries = [p for p in seen.read_text(encoding="utf-8").split(os.pathsep) if p != git(self.tmp, "--exec-path")]
        self.assertEqual(entries[0], str(read_gh), "git が頭に足す自分の置き場の後ろは読むだけの gh の置き場")

    def shell_env(self, ran_dir) -> dict:
        """起動の殻を通った run の節の環境: 控えた利用者の HOME・入力 user_env_dir・読むだけの gh の置き場・uv の足した物"""
        self.user_home = self.tmp / "user-home"
        self.read_gh = self.tmp / "read-gh"
        return {userenv.RECORD: userenv.record({"HOME": str(self.user_home)}), "INPUTS_USER_ENV_DIR": str(ran_dir),
                userenv.READ_GH_ENV: str(self.read_gh), "UV_RUN_RECURSION_DEPTH": "1",
                "PATH": os.pathsep.join([os.path.dirname(sys.executable), os.environ["PATH"]])}

    def test_commit_hook_runs_in_the_target_command_env(self):
        """hooks は対象のコマンドの環境で走る: 利用者の HOME・uv の足した物の無い PATH の頭に読むだけの gh・MARK 無し。印は置き場に残る"""
        seen = self.tmp / "env.txt"
        self.hook(f"env > '{seen}'\n")
        ran_dir = self.tmp / "ran"
        self.assertIs(self.commit(env=self.shell_env(ran_dir))["go"], True)
        hooked = dict(line.split("=", 1) for line in seen.read_text(encoding="utf-8").splitlines() if "=" in line)
        self.assertEqual(hooked["HOME"], str(self.user_home))
        entries = [p for p in hooked["PATH"].split(os.pathsep) if p != git(self.tmp, "--exec-path")]
        self.assertEqual(entries[0], str(self.read_gh), "git が頭に足す自分の置き場の後ろは読むだけの gh の置き場で、この python の bin はその先に無い")
        self.assertNotIn(userenv.MARK, hooked)
        self.assertNotIn("UV_RUN_RECURSION_DEPTH", hooked)
        self.assertIs(userenv.ran(ran_dir), True)

    def test_item_commits_and_the_restacked_commit_run_the_hooks_in_the_target_command_env(self):
        """#758 の項目ごとの各 commit と、途中で落ちて 1 つに積み直す commit も、hooks は利用者の HOME で走り、印が残る"""
        homes = self.tmp / "homes.txt"
        self.hook(f"echo \"$HOME\" >> '{homes}'\n"
                  "staged=$(git diff --cached --name-only)\necho \"$staged\" | grep -q new.txt && exit 0\n"
                  "[ -e \"$FAIL_ON_A\" ] && echo \"$staged\" | grep -q a.txt && exit 1\nexit 0\n")
        for fail, count in ((False, "2"), (True, "1")):
            with self.subTest(restacked=fail):
                git(self.run_tree, "reset", "-q", self.base)
                homes.unlink(missing_ok=True)
                ran_dir = self.tmp / f"ran-{fail}"
                flag = self.tmp / "fail-on-a"
                env = {**self.shell_env(ran_dir), "FAIL_ON_A": str(flag if fail else self.tmp / "absent")}
                flag.touch()
                got = self.commit(env=env, items=self.record([("u1", ["a.txt"]), ("u2", ["new.txt"])]))
                self.assertIs(got["go"], True, got)
                self.assertEqual(git(self.run_tree, "rev-list", "--count", f"{self.base}..HEAD"), count)
                self.assertEqual(set(homes.read_text(encoding="utf-8").split()), {str(self.user_home)})
                self.assertIs(userenv.ran(ran_dir), True)

    def test_failing_hook_in_the_target_command_env_stops_with_the_mark_kept(self):
        """利用者の環境で hooks が落ちて積まずに止まっても、hooks は走ったので印は残る（1 つの commit・積み直しの commit の両方）"""
        self.hook("git diff --cached --name-only | grep -q a.txt && { echo 'a の誤り' >&2; exit 1; }\nexit 0\n")
        for items in ("", self.record([("u1", ["a.txt"]), ("u2", ["new.txt"])])):
            with self.subTest(items=bool(items)):
                ran_dir = self.tmp / f"ran-{bool(items)}"
                got = self.commit(env=self.shell_env(ran_dir), items=items)
                self.assertStopped(got, "a の誤り")
                self.assertEqual(git(self.run_tree, "rev-parse", "HEAD"), self.base, "積み始める前の HEAD に戻す")
                self.assertIs(userenv.ran(ran_dir), True)

    def assertStoppedBeforeTheHooks(self, ran_dir, words: str):
        hooked = self.tmp / "hooked"
        self.hook(f"touch '{hooked}'\n")
        self.assertStopped(self.commit(env=self.shell_env(ran_dir)), words)
        self.assertEqual(git(self.run_tree, "rev-parse", "HEAD"), self.base)
        self.assertFalse(hooked.exists(), "利用者の環境で hooks を走らせない")

    def test_mark_folder_that_is_a_file_stops_without_a_commit(self):
        """印の置き場がフォルダでなくファイルなら、置き場を作る所（outside_env）で止まり、積まない"""
        as_file = self.tmp / "ran"
        as_file.write_text("", encoding="utf-8")
        self.assertStoppedBeforeTheHooks(as_file, str(as_file))

    @unittest.skipIf(os.geteuid() == 0, "root は書けないフォルダの中も書ける")
    def test_mark_that_cannot_be_placed_stops_without_a_commit(self):
        """印を置けなければ（書けない置き場）、訳に tree_run.MARK_FAILED を載せて積まずに止まる"""
        read_only = self.tmp / "ran"
        read_only.mkdir()
        read_only.chmod(0o500)
        self.assertStoppedBeforeTheHooks(read_only, tree_run.MARK_FAILED)

    def test_record_without_the_user_env_dir_stops_without_a_commit(self):
        """控えが在るのに印の置き場の入力が空なら、利用者の環境に戻さず・隔離のまま積まずに止まる"""
        got = self.commit(env=self.shell_env(""))
        self.assertStopped(got, userenv.RAN_DIR_ENV)
        self.assertEqual(git(self.run_tree, "rev-parse", "HEAD"), self.base)

    def test_mark_stays_only_when_a_commit_ran_the_hooks(self):
        """印は、commit を積んでフックを走らせた時だけ残る。封じた差分が既に枝の commit に在って積まない回は、印を置かない"""
        ran_dir = self.tmp / "ran"
        git(self.run_tree, "add", "-A", "--", ".", ":(exclude).archon")
        git(self.run_tree, "commit", "-q", "-m", "round")
        got = self.commit(env=self.shell_env(ran_dir))
        self.assertIs(got["go"], True, got)
        self.assertIs(userenv.ran(ran_dir), False, "積まなかった回に印は残らない")
        (self.run_tree / "a.txt").write_text("three\n", encoding="utf-8")
        sealed = seal.digest(green_cert.diff_bytes(self.run_tree, self.base, skip=(".archon/",)))
        got = self.commit(env=self.shell_env(ran_dir), sealed_hash=sealed)
        self.assertIs(got["go"], True, got)
        self.assertEqual(git(self.run_tree, "rev-list", "--count", f"{self.base}..HEAD"), "2")
        self.assertIs(userenv.ran(ran_dir), True, "積んでフックを走らせた回は印が残る")

    def test_origin_without_a_forge_repo_stops(self):
        git(self.main, "config", "remote.origin.url", str(self.origin))
        self.assertStopped(self.commit(), "PR を出す repo")
        self.assertEqual(git(self.run_tree, "rev-parse", "HEAD"), self.base)

    def test_seal_is_not_committed(self):
        self.assertStopped(self.commit(mode="seal"), "照らしの形")
        self.assertEqual(git(self.run_tree, "rev-parse", "HEAD"), self.base)

    def test_already_committed_diff_goes_without_a_new_commit(self):
        git(self.run_tree, "add", "-A", "--", ".", ":(exclude).archon")
        git(self.run_tree, "commit", "-q", "-m", "round")
        head = git(self.run_tree, "rev-parse", "HEAD")
        got = self.commit()
        self.assertEqual((got["go"], got["head"]), (True, head), got)

    def test_lib_missing_is_a_stop_not_a_failure(self):
        nowhere = self.tmp / "no-lib"
        nowhere.mkdir()
        env = {"WORKS_FACTORY_ROOT": str(nowhere), "INPUTS_BASE_REV": self.base, "INPUTS_SEALED_HASH": self.sealed}
        self.assertIs(run_node("pr_commit", env, self.run_tree, "pr-commit")["go"], False)


class PrReadTest(unittest.TestCase):
    HEAD = "c" * 40
    REPO = {"host": "github.com", "path": "o/r"}
    RECORD = {"schemaVersion": 1, "number": 7, "url": "https://github.com/o/r/pull/7", "state": "open", "head_revision": HEAD,
              "is_draft": True, "head": "archon/task-run", "base": "main", "repo": REPO, "head_repo": REPO}

    def read(self, got) -> dict:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = {"INPUTS_GOT": json.dumps(got), "INPUTS_HEAD": self.HEAD, "INPUTS_BRANCH": "archon/task-run", "INPUTS_BASE_BRANCH": "main",
               "INPUTS_REPO": json.dumps(self.REPO)}
        return run_node("pr_read", env, pathlib.Path(tmp.name), "pr-read")

    def test_open_pr_at_the_committed_head_is_made(self):
        self.assertEqual(self.read(self.RECORD), {"ok": True, "number": 7, "url": self.RECORD["url"], "is_draft": True, "reason": ""})
        self.assertIs(self.read({**self.RECORD, "repo": {"host": "GitHub.com", "path": "O/R"}})["ok"], True, "repo の名は大小を区別しない")

    def test_pr_other_than_the_committed_one_is_not_made(self):
        """開いていて、repo・head の repo・head の枝・base の枝・head の版が積んだ物と全部同じ時だけ作ったと言う"""
        fork = {"host": "github.com", "path": "someone/r"}
        for over, words in (({"head_revision": "d" * 40}, "積んだ commit"), ({"state": "closed"}, "開いていない"),
                            ({"url": ""}, "在りかが無い"), ({"head": "other"}, "積んだ枝"), ({"base": "dev"}, "既定の枝"),
                            ({"repo": fork}, "repo"), ({"head_repo": fork}, "head_repo"), ({"head_repo": None}, "head_repo")):
            with self.subTest(over=over):
                got = self.read({**self.RECORD, **over})
                self.assertIs(got["ok"], False)
                self.assertIn(words, got["reason"])

    def test_unreadable_record_is_not_made(self):
        self.assertIs(self.read("x")["ok"], False)

    def test_import_fallback_keeps_its_own_name(self):
        """境の口の import が落ちた時の控えの名と、読めない時の返りを組む関数の名は別（同じ名だと関数が控えを上書きする）"""
        script = (SCRIPTS / "pr_read.py").read_text(encoding="utf-8")
        self.assertIn("boundary, unread = None, error", script)
        self.assertNotIn("def unread(", script)


class HandedTest(unittest.TestCase):
    """返す節: 照らしの返りに渡し方 deliver を足す。既定の空の語は置くだけで、PR の節の返りを読まない"""
    PLACE = {"mode": "apply", "ok": True, "hash": "a" * 64, "diff": {"type": "archon_artifact", "run_id": RUN, "path": "merge/apply.diff"},
             "protected_hits": None, "protected_count": None, "reason": "", "base_rev": "b" * 40, "deliver": ""}
    STACKED = {"commits": [{"item": 1, "subject": "項目 1: 足す", "head": "e" * 40}, {"item": 2, "subject": "項目 2: 使う", "head": "c" * 40}],
               "split": ""}
    COMMIT = {"go": True, "head": "c" * 40, "branch": "archon/task-run", "base": "main", "repo": {"host": "github.com", "path": "o/r"},
              **STACKED, "reason": ""}

    def handed(self, place, commit=None, read=None) -> dict:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = {"INPUTS_MODE": place.get("mode", "") if isinstance(place, dict) else "", "INPUTS_PLACE": json.dumps(place),
               "INPUTS_COMMIT": json.dumps(commit), "INPUTS_READ": json.dumps(read),
               "INPUTS_OPTIONAL": '[{"node": "pr-open", "bare": false}]'}
        return run_node("handed", env, pathlib.Path(tmp.name), "merge")

    def test_default_word_places_only(self):
        got = self.handed(self.PLACE)
        self.assertEqual({k: got[k] for k in RETURNS if k not in ("deliver", "optional")},
                         {k: self.PLACE[k] for k in RETURNS if k not in ("deliver", "optional")})
        self.assertEqual(got["deliver"], {"act": "placed", "pr": None, "reason": ""})
        self.assertEqual(self.handed({**self.PLACE, "ok": False, "reason": "違う"})["deliver"]["act"], "none")
        self.assertEqual(got["optional"], [{"node": "pr-open", "bare": False}])

    def test_seal_has_no_delivery(self):
        self.assertIsNone(self.handed({**self.PLACE, "mode": "seal"})["deliver"])

    def test_pr_word_names_the_pr_or_why_it_stopped_or_was_unconfirmed(self):
        place = {**self.PLACE, "deliver": "pr"}
        made = {"ok": True, "number": 7, "url": "https://github.com/o/r/pull/7", "is_draft": True, "reason": ""}
        self.assertEqual(self.handed(place, self.COMMIT, made)["deliver"],
                         {"act": "pr", "pr": {"number": 7, "url": made["url"], "is_draft": True}, "reason": "", **self.STACKED})
        for args, act, words in (((None, None), "stopped", "commit のノードの出力が無い"),
                                 (({**self.COMMIT, "go": False, "reason": "同じ名"}, None), "stopped", "同じ名"),
                                 ((self.COMMIT, None), "unconfirmed", "PR を作る子の run が落ちたか返らなかった"),
                                 ((self.COMMIT, {**made, "ok": False, "reason": "開いていない"}), "unconfirmed", "開いていない")):
            with self.subTest(words=words):
                got = self.handed(place, *args)["deliver"]
                self.assertEqual((got["act"], got["pr"]), (act, None))
                self.assertIn(words, got["reason"])
                if act == "unconfirmed":
                    self.assertEqual(got["commits"], self.STACKED["commits"], "積んだ commit は確かめられない時も報告に渡す")
        refused = self.handed({**place, "ok": False, "reason": "封じた差分と今の差分が違う"})["deliver"]
        self.assertEqual(refused["act"], "stopped")
        self.assertIn("差分を置かなかった", refused["reason"])

    def test_unreadable_place_is_not_ok(self):
        got = self.handed("x")
        self.assertIs(got["ok"], False)


class NeverFailsTest(ScriptCase):
    """返す節は落ちない: 壊れた入力でも終了の値 0 で、output_format に合う ok: false と理由を返す"""

    def assertBroken(self, got, mode):
        self.assertEqual(got["mode"], mode)
        self.assertEqual((got["ok"], got["hash"], got["diff"], got["protected_hits"]), (False, "", None, None))
        self.assertTrue(got["reason"])

    def test_unknown_mode(self):
        got = self.seal(mode="merge")
        self.assertBroken(got, "seal")
        self.assertIn("merge", got["reason"])
        self.assertFalse(self.artifact("merge/sealed.diff").exists())

    def test_empty_mode(self):
        self.assertBroken(self.seal(mode=""), "seal")

    def test_unknown_deliver_word(self):
        got = self.apply("0" * 64, deliver="merge")
        self.assertBroken(got, "apply")
        self.assertIn("deliver", got["reason"])

    def test_start_not_json(self):
        self.assertBroken(self.seal(start="{"), "seal")

    def test_start_of_another_run(self):
        other = json.dumps({"type": "archon_artifact", "run_id": "run-other", "path": "start.json"})
        self.assertBroken(self.seal(start=other), "seal")

    def test_start_record_without_base_rev(self):
        self.assertBroken(self.seal(start=self.place("start.json", json.dumps({"run_id": RUN}))), "seal")

    def test_answer_not_json(self):
        self.assertBroken(self.apply("0" * 64, answer="{"), "apply")

    def test_r2_not_json(self):
        self.assertBroken(self.apply("0" * 64, r2="{"), "apply")

    def test_lib_missing(self):
        nowhere = self.tmp / "no-lib"
        nowhere.mkdir()
        self.assertBroken(self.seal(root=nowhere), "seal")

    def test_checkout_not_git(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        self.assertBroken(self.seal(cwd=plain), "seal")


class FixturesTest(unittest.TestCase):
    """筋書きの合否（workflow test）と、返す節の渡し方（dry-run の trace）。Archon の源か bun が無ければ見送る"""

    @classmethod
    def setUpClass(cls):
        with archon.tree(["merge"]) as tree:
            cls.done = archon.archon(tree, "workflow", "test", NAME)
        cls.traces = dry_run_traces("merge", NAME, ["merge"], SCENARIOS)

    def deliver(self, scenario: str):
        return json.loads(self.traces[scenario]["merge"]["output"])["deliver"]

    def test_fixtures_pass_in_archon(self):
        fixtures = sorted(p.name.removesuffix(".stubs.yaml") for p in (BLOCK / "fixtures").glob("*.stubs.yaml"))
        self.assertEqual(fixtures, sorted(SCENARIOS))
        self.assertEqual(self.done.returncode, 0, self.done.stdout + self.done.stderr)
        for name in fixtures:
            self.assertIn(f"merge/fixtures/{name}.stubs.yaml", self.done.stdout)
        self.assertIn(f"{len(fixtures)} passed, 0 failed", self.done.stdout)

    def test_default_word_places_without_the_pr_path(self):
        for scenario in ("apply", "seal", "empty-diff"):
            with self.subTest(scenario=scenario):
                trace = self.traces[scenario]
                self.assertTrue(all(trace.get(n, {}).get("state", "skipped") == "skipped" for n in ("pr-commit", "pr-open", "pr-read")),
                                trace)
        self.assertEqual(self.deliver("apply"), {"act": "placed", "pr": None, "reason": ""})
        self.assertIsNone(self.deliver("seal"))

    def test_pr_word_makes_the_pr_and_names_it(self):
        got = self.deliver("pr")
        self.assertEqual({k: got[k] for k in ("act", "pr", "reason", "split")},
                         {"act": "pr", "pr": {"number": 7, "url": "https://github.com/owner/repo/pull/7", "is_draft": True}, "reason": "",
                          "split": ""})
        self.assertEqual([c["item"] for c in got["commits"]], [1, 2])

    def test_pr_word_stops_without_the_child_on_the_default_branch_name(self):
        self.assertEqual(self.traces["pr-same-branch"].get("pr-open", {}).get("state", "skipped"), "skipped")
        got = self.deliver("pr-same-branch")
        self.assertEqual(got["act"], "stopped")
        self.assertIn("既定の枝と同じ名", got["reason"])

    def test_failed_child_is_unconfirmed_not_a_failed_return(self):
        got = self.deliver("pr-child-failed")
        self.assertEqual(got["act"], "unconfirmed")
        self.assertIn("PR を作る子の run が落ちた", got["reason"])
        self.assertEqual(self.deliver("apply-refused")["act"], "stopped")


if __name__ == "__main__":
    unittest.main()

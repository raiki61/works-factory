"""ブロック merge（workflows/merge/）の YAML の形・script の通し・筋書きの試験。

- YAML の形は PyYAML で読み、Archon を起こさない（返りの約束の 6 欄・入力の 9 つ・節 1 つ・作業ツリーを変えない）
- script は subprocess で、一時の git の木を cwd に、Archon が script の節に渡す環境（WORKFLOW_ID・ARTIFACTS_DIR・INPUTS_*）を偽の run で作って走らせる。
  どの走りでも作業ツリーの `git status --porcelain` が前後で同じ（E6・E7）
- 筋書き（fixtures/）は tests/archon.py の使い捨ての木で `workflow test` に回す。Archon の源が無ければ見送る
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
from tests.bin.gitkit import git

ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import green_cert  # noqa: E402
from graphloops.engine.schema import validate_schema  # noqa: E402
import protect  # noqa: E402
import seal  # noqa: E402

BLOCK = ROOT / "workflows" / "merge"
YAML = BLOCK / "works-factory-merge.yaml"
SCRIPT = BLOCK / "scripts" / "merge.py"
NAME = "works-factory-merge"
RUN = "run-merge"
INPUTS = ("mode", "start", "fingerprint", "green_ok", "eyes_ok", "sealed_hash", "answer", "r2")
RETURNS = ("mode", "ok", "hash", "diff", "protected_hits", "reason")
PASS = json.dumps({"decision": "continue", "text": ""})


def load() -> dict:
    return yaml.safe_load(YAML.read_text(encoding="utf-8"))


def output_format() -> dict:
    return load()["nodes"][0]["output_format"]


class ShapeTest(unittest.TestCase):
    def setUp(self):
        self.doc = load()
        self.node = self.doc["nodes"][0]

    def test_header(self):
        self.assertEqual(self.doc["name"], NAME)
        self.assertEqual(self.doc["returns"], "merge")
        self.assertEqual(self.doc["outcome_field"], "ok")
        self.assertNotIn("interactive", self.doc)

    def test_one_script_node(self):
        self.assertEqual([n["id"] for n in self.doc["nodes"]], ["merge"])
        self.assertEqual(self.node["script"], "merge")
        self.assertEqual(self.node["runtime"], "uv")
        self.assertIs(self.node["mutates_checkout"], False)
        self.assertNotIn("timeout", self.node)
        self.assertFalse(any("approval" in n or "wait" in n for n in self.doc["nodes"]))

    def test_inputs_are_the_contract(self):
        inputs = self.doc["inputs"]
        self.assertEqual(sorted(inputs), sorted(INPUTS))
        for name in ("mode", "start"):
            self.assertIs(inputs[name].get("required"), True, name)
        for name in set(INPUTS) - {"mode", "start"}:
            self.assertEqual(inputs[name].get("default"), "", name)
        self.assertEqual(self.node["with"], {name: f"$INPUTS.{name}" for name in INPUTS})

    def test_output_format_is_the_contract(self):
        fmt = self.node["output_format"]
        self.assertEqual(sorted(fmt["properties"]), sorted(RETURNS))
        self.assertEqual(sorted(fmt["required"]), sorted(RETURNS))
        self.assertIs(fmt["additionalProperties"], False)
        props = fmt["properties"]
        self.assertEqual(props["mode"]["enum"], ["seal", "apply"])
        self.assertEqual(props["ok"]["type"], "boolean")
        self.assertIn("null", props["diff"]["type"])
        self.assertIn("null", props["protected_hits"]["type"])
        self.assertEqual(sorted(props["diff"]["properties"]["path"]["enum"]),
                         sorted(["merge/sealed.diff", "merge/apply.diff", "merge/refused.diff"]))


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
                                 PYTHONDONTWRITEBYTECODE="1", **{f"INPUTS_{name.upper()}": inputs.get(name, "") for name in INPUTS})
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
        self.assertEqual(got["protected_hits"], [])

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
    def test_fixtures_pass_in_archon(self):
        fixtures = sorted(p.name for p in (BLOCK / "fixtures").glob("*.stubs.yaml"))
        self.assertEqual(fixtures, ["apply-refused.stubs.yaml", "apply.stubs.yaml", "empty-diff.stubs.yaml",
                                    "seal.stubs.yaml"])
        with archon.tree(["merge"]) as tree:
            done = archon.archon(tree, "workflow", "test", NAME)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        for name in fixtures:
            self.assertIn(f"merge/fixtures/{name}", done.stdout)
        self.assertIn(f"{len(fixtures)} passed, 0 failed", done.stdout)



if __name__ == "__main__":
    unittest.main()

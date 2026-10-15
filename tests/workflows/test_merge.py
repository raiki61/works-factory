"""ブロック merge（workflows/merge/）の YAML の形・script の通し・筋書きの試験。

- YAML の形は PyYAML で読み、Archon を起こさない（返りの約束の 7 欄・入力の 11 個・節 1 つ・作業ツリーを変えない）
- script は subprocess で、一時の git の木を cwd に、Archon が script の節に渡す環境（WORKFLOW_ID・ARTIFACTS_DIR・INPUTS_*）を偽の run で作って走らせる。
  どの走りでも作業ツリーの `git status --porcelain` が前後で同じ（E6・E7）
- DeliverTest は出口 deliver: pr（lib/deliver.py）を、偽の gh（PATH の頭の読むだけの口の後ろ）と裸の git の remote で縛る
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
INPUTS = ("mode", "start", "fingerprint", "green_ok", "eyes_ok", "sealed_hash", "answer", "r2", "deliver", "placed", "base_rev")
RETURNS = ("mode", "ok", "hash", "diff", "protected_hits", "reason", "delivered")
NO_DEADLINE = 1728000000
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
        self.assertEqual(self.node["timeout"], NO_DEADLINE)
        self.assertFalse(any("approval" in n for n in self.doc["nodes"]))

    def test_inputs_are_the_contract(self):
        inputs = self.doc["inputs"]
        self.assertEqual(sorted(inputs), sorted(INPUTS))
        self.assertIs(inputs["mode"].get("required"), True)
        for name in set(INPUTS) - {"mode"}:
            self.assertNotIn("required", inputs[name], name)
            self.assertEqual(inputs[name].get("default"), "", name)
        self.assertEqual(self.node["with"], {name: f"$INPUTS.{name}" for name in INPUTS})

    def test_output_format_is_the_contract(self):
        fmt = self.node["output_format"]
        self.assertEqual(sorted(fmt["properties"]), sorted(RETURNS))
        self.assertEqual(sorted(fmt["required"]), sorted(RETURNS))
        self.assertIs(fmt["additionalProperties"], False)
        props = fmt["properties"]
        self.assertEqual(props["mode"]["enum"], ["seal", "apply", "handoff"])
        self.assertEqual(sorted(props["delivered"]["type"]), ["null", "object"])
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
        env = {k: v for k, v in os.environ.items() if not k.startswith("INPUTS_")}
        env.update({"WORKFLOW_ID": RUN, "ARTIFACTS_DIR": str(self.artifacts), "WORKS_FACTORY_ROOT": str(root),
                    "PYTHONDONTWRITEBYTECODE": "1"})
        env.update({f"INPUTS_{name.upper()}": inputs.get(name, "") for name in INPUTS})
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
        done = subprocess.run(["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True)
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

    def test_lib_missing_with_a_delivery_asked_still_returns(self):
        """pr を頼んだ run でも、lib を読めずに落ちた時は delivered を組む口が無いので null のまま返す（訳は reason）"""
        nowhere = self.tmp / "no-lib"
        nowhere.mkdir()
        got = self.apply("0" * 64, deliver="pr", root=nowhere)
        self.assertBroken(got, "apply")
        self.assertIsNone(got["delivered"])

    def test_checkout_not_git(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        self.assertBroken(self.seal(cwd=plain), "seal")

    def test_handoff_failure_keeps_the_handoff_mode(self):
        """mode_of は seal・apply・handoff の 3 つを返し、知らない字だけ seal にする。handoff の入力が壊れて落ちた時も handoff のまま"""
        got = self.run_script(mode="handoff", placed="{", base_rev=self.base, deliver="pr")
        self.assertBroken(got, "handoff")
        self.assertFalse(self.artifact("merge/apply.diff").exists())

    def test_failure_with_a_delivery_asked_names_why_nothing_was_delivered(self):
        """pr を頼んだ run が例外で落ちたら、delivered は null でなく {ok: false, reason}（null は何も頼まれていない印）"""
        for name, got in (("handoff", self.run_script(mode="handoff", placed="{", base_rev=self.base, deliver="pr")),
                          ("apply", self.apply("0" * 64, answer="{", deliver="pr"))):
            with self.subTest(name):
                self.assertFalse(got["ok"])
                self.assertFalse(got["delivered"]["ok"])
                self.assertEqual((got["delivered"]["branch"], got["delivered"]["commit"], got["delivered"]["url"]), ("", "", ""))
                self.assertIn(got["reason"], got["delivered"]["reason"])

    def test_failure_without_a_delivery_asked_keeps_delivered_null(self):
        for name, got in (("handoff", self.run_script(mode="handoff", placed="{", base_rev=self.base, deliver="")),
                          ("apply", self.apply("0" * 64, answer="{")),
                          ("seal", self.seal(start="{", deliver="pr"))):
            with self.subTest(name):
                self.assertIsNone(got["delivered"])


FAKE_GH = '''#!PYTHON
"""偽の gh: 呼びを控えに書き、api の答え・pr list・pr create・pr view を裸の remote の枝と状態のファイルから組む。api に -R が来れば exit 1"""
import json
import os
import re
import subprocess
import sys

state = json.load(open(os.environ["FAKE_GH_STATE"]))
args = sys.argv[1:]
with open(state["calls"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")


def out(value):
    print(json.dumps(value))
    sys.exit(0)


def fail(message, code=1):
    print(message, file=sys.stderr)
    sys.exit(code)


def ref(branch):
    done = subprocess.run(["git", "--git-dir", state["bare"], "rev-parse", "--verify", "-q", "refs/heads/" + branch],
                          capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else None


def prs():
    try:
        return json.load(open(state["prs"]))
    except OSError:
        return []


def option(name):
    return args[args.index(name) + 1] if name in args else None


if args[:1] == ["api"]:
    if "-R" in args or "--repo" in args:
        fail("gh api に -R は無い（--hostname と明示のパスで打つ）")
    if "--hostname" not in args or any(a in args for a in ("-X", "--method", "-f", "-F", "--input")):
        fail("api は --hostname と明示のパスの GET だけ")
    match = re.fullmatch(r"repos/([^/]+)/([^/]+)(?:/(.*))?", args[-1])
    if not match:
        fail("明示のパスでない")
    rest = match.group(3) or ""
    if rest == "":
        out({"default_branch": state["default"], "permissions": {"push": state["push"]}})
    if rest.startswith("branches/"):
        branch = rest[len("branches/"):]
        if state["protected"] or ref(branch):
            out({"name": branch, "protected": state["protected"]})
        fail("gh: Not Found (HTTP 404)")
    if rest.startswith("rules/branches/"):
        out(state["rules"])
    if rest.startswith("compare/"):
        if state["compare"] == "404":
            fail("gh: Not Found (HTTP 404)")
        out({"status": state["compare"]})
    if rest.startswith("git/ref/heads/"):
        branch = rest[len("git/ref/heads/"):]
        sha = state["ref_sha"] or ref(branch)
        if sha is None:
            fail("gh: Not Found (HTTP 404)")
        out({"ref": "refs/heads/" + branch, "object": {"sha": sha, "type": "commit"}})
    fail("知らないパス: " + rest)
if args[:2] == ["pr", "list"]:
    out([p for p in prs() if p["headRefName"] == option("--head") and p["state"] == "OPEN"])
if args[:2] == ["pr", "create"]:
    number = len(prs()) + 1
    head = option("--head")
    made = {"number": number, "url": "https://github.com/acme/widgets/pull/%d" % number, "state": "OPEN", "headRefName": head,
            "headRefOid": state["pr_head"] or ref(head), "baseRefName": option("-B"), "title": option("--title"),
            "body": option("--body")}
    json.dump([*prs(), made], open(state["prs"], "w"))
    print(made["url"])
    sys.exit(0)
if args[:2] == ["pr", "view"]:
    found = [p for p in prs() if str(p["number"]) == args[2]]
    if not found:
        fail("no pull requests found")
    out({**found[0], "headRefOid": state["view_head"] or found[0]["headRefOid"]})
fail("知らない呼び: " + " ".join(args), 2)
'''
BARE_URL = "https://github.com/acme/widgets.git"


class DeliverTest(ScriptCase):
    """deliver: pr（lib/deliver.py）。対象の origin は github.com の https URL で、push の先だけ url.<裸>.pushInsteadOf で裸の remote へ向ける
    （insteadOf だと git remote get-url が書き換えた先のパスを返し、forge の判定が GitHub でなくなる）。PATH の頭に読むだけの口 gh・works-gh
    （exit 2）、その後ろに偽の gh。git push は本物の git で送る。対象の木には作業ツリーへファイルを書く pre-push フックを置く"""

    BRANCH = f"works-factory/run-{RUN}"

    def setUp(self):
        super().setUp()
        self.bare = self.tmp / "remote.git"
        git(self.tmp, "init", "-q", "--bare", str(self.bare))
        git(self.repo, "remote", "add", "origin", BARE_URL)
        git(self.repo, "config", f"url.{self.bare}.pushInsteadOf", BARE_URL)
        git(self.repo, "push", "-q", "origin", f"{self.base}:refs/heads/main")
        self.marker = self.repo / "hook-ran.txt"
        hook = self.repo / ".git" / "hooks" / "pre-push"
        hook.write_text(f'#!/bin/sh\necho ran > "{self.marker}"\nexit 1\n', encoding="utf-8")
        hook.chmod(0o755)
        shim, fake = self.tmp / "shim", self.tmp / "fake"
        for folder in (shim, fake):
            folder.mkdir()
        self.shim_calls = self.tmp / "shim-calls"
        for name in ("gh", "works-gh"):
            (shim / name).write_text(f'#!/bin/sh\necho "$0" >> "{self.shim_calls}"\nexit 2\n', encoding="utf-8")
            (shim / name).chmod(0o755)
        (fake / "gh").write_text(FAKE_GH.replace("PYTHON", sys.executable), encoding="utf-8")
        (fake / "gh").chmod(0o755)
        self.state_file = self.tmp / "gh-state.json"
        self.state = {"bare": str(self.bare), "calls": str(self.tmp / "gh-calls.jsonl"), "prs": str(self.tmp / "gh-prs.json"),
                      "default": "main", "push": True, "protected": False, "rules": [], "compare": "behind", "ref_sha": None,
                      "pr_head": None, "view_head": None}
        self.gh()
        patch = mock.patch.dict(os.environ, {"PATH": os.pathsep.join([str(shim), str(fake), os.environ["PATH"]]),
                                             "FAKE_GH_STATE": str(self.state_file)})
        patch.start()
        self.addCleanup(patch.stop)
        self.sealed = self.seal()["hash"]

    def gh(self, **over):
        self.state.update(over)
        self.state_file.write_text(json.dumps(self.state), encoding="utf-8")

    def calls(self) -> list:
        path = pathlib.Path(self.state["calls"])
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def made(self, *verb) -> list:
        return [c for c in self.calls() if c[:len(verb)] == list(verb)]

    def remote_branch(self, name=None):
        done = subprocess.run(["git", "--git-dir", str(self.bare), "rev-parse", "--verify", "-q", f"refs/heads/{name or self.BRANCH}"],
                              capture_output=True, text=True)
        return done.stdout.strip() or None

    def remote_refs(self) -> str:
        return git(self.bare, "for-each-ref", "--format=%(refname) %(objectname)")

    def target_state(self) -> tuple:
        """対象の .git のうち、出口が書いてはならない物（枝・HEAD・設定）"""
        git_dir = self.repo / ".git"
        return (git(self.repo, "for-each-ref", "--format=%(refname) %(objectname)"), (git_dir / "HEAD").read_bytes(),
                (git_dir / "config").read_bytes())

    def apply_pr(self, **over) -> dict:
        return self.apply(self.sealed, **{"deliver": "pr", **over})

    def final_diff(self, **over) -> dict:
        """鎖の final-diff の apply の見本 {ok, hash, diff, reason}（差分は元の基から今の作業ツリーまで）"""
        data = green_cert.diff_bytes(self.repo, self.base)
        pointer = json.loads(self.place("chain/final.diff", data.decode("utf-8")))
        return {"ok": True, "hash": hashlib.sha256(data).hexdigest(), "diff": pointer, "reason": "", **over}

    def run_chain_handoff(self, placed=None, r2="pass", **over) -> dict:
        inputs = {"mode": "handoff", "placed": json.dumps(self.final_diff() if placed is None else placed), "base_rev": self.base,
                  "r2": r2, "deliver": "pr"}
        return self.run_script(**{**inputs, **over})

    def assertNothingWritten(self, delivered, words):
        self.assertIsNotNone(delivered)
        self.assertIs(delivered["ok"], False, delivered)
        self.assertIn(words, delivered["reason"])
        self.assertIsNone(self.remote_branch(), "押す先の枝を書いた")
        self.assertEqual(self.made("pr", "create"), [])

    def test_pr_pushes_the_sealed_diff_to_the_run_branch_and_reads_back(self):
        before, refs = self.target_state(), self.remote_refs()
        self.assertIsNone(self.remote_branch(), "1 度目の提出の前は押す先の枝が無い（branches/<b> は 404）")
        got = self.apply_pr()
        self.assertEqual((got["mode"], got["ok"], got["reason"]), ("apply", True, ""))
        delivered = got["delivered"]
        commit = self.remote_branch()
        self.assertEqual(delivered, {"ok": True, "branch": self.BRANCH, "commit": commit,
                                     "url": "https://github.com/acme/widgets/pull/1", "reason": ""})
        self.assertEqual(git(self.bare, "rev-parse", f"{commit}^"), self.base, "押した commit の親は元の基")
        self.assertEqual(git(self.bare, "diff", "--name-only", self.base, commit), "a.txt", "封じた差分だけを載せる")
        self.assertEqual(git(self.bare, "show", f"{commit}:a.txt"), "two")
        self.assertEqual(git(self.bare, "log", "-1", "--format=%an <%ae>|%cn", commit), "works-factory <works-factory@localhost>|works-factory")
        self.assertEqual(self.remote_refs().splitlines(), sorted([*refs.splitlines(), f"refs/heads/{self.BRANCH} {commit}"]))
        self.assertEqual(self.target_state(), before, "対象の .git の枝・HEAD・設定を書いた")
        self.assertNotEqual(subprocess.run(["git", "-C", str(self.repo), "cat-file", "-e", f"{commit}^{{commit}}"],
                                           capture_output=True).returncode, 0, "commit を対象の objects に書いた")
        self.assertFalse(self.marker.exists(), "対象の pre-push フックを走らせた")
        self.assertFalse(self.shim_calls.exists(), "読むだけの口を通った")
        for call in self.calls():
            if call[0] == "api":
                self.assertEqual(call[1:3], ["--hostname", "github.com"], call)
                self.assertNotIn("-R", call)
            else:
                self.assertEqual(call[call.index("-R") + 1], "github.com/acme/widgets", call)
        self.assertIn(["api", "--hostname", "github.com", f"repos/acme/widgets/compare/main...{self.base}"], self.calls())
        self.assertIn(["api", "--hostname", "github.com", f"repos/acme/widgets/rules/branches/{self.BRANCH}"], self.calls(),
                      "無い枝の 404 は守りなしと読み、規則の照らしへ進む")
        create = self.made("pr", "create")[0]
        self.assertEqual((create[create.index("-B") + 1], create[create.index("--head") + 1]), ("main", self.BRANCH))
        self.assertEqual(create[create.index("--title") + 1], f"works-factory: run {RUN}")
        body = create[create.index("--body") + 1]
        self.assertIn(RUN, body)
        self.assertIn("pre-push", body, "対象のフックを走らせない訳を本文に書く")
        self.assertEqual([c[:2] for c in self.calls() if c[:2] in (["pr", "merge"], ["pr", "close"])], [])

    def test_handoff_with_a_wrong_hash_writes_nothing(self):
        got = self.run_chain_handoff(self.final_diff(hash="0" * 64))
        self.assertEqual((got["mode"], got["ok"]), ("handoff", False))
        self.assertIn("食い違", got["reason"])
        self.assertFalse(self.artifact("merge/apply.diff").exists())
        self.assertNothingWritten(got["delivered"], "食い違")
        self.assertEqual(self.made("api") + self.made("pr"), [], "出口は呼ばれない")

    def test_handoff_places_the_sealed_diff_and_delivers(self):
        data = green_cert.diff_bytes(self.repo, self.base)
        for r2 in ("pass", "null"):
            with self.subTest(r2=r2):
                shutil.rmtree(self.artifact("merge"), ignore_errors=True)
                git(self.bare, "update-ref", "-d", f"refs/heads/{self.BRANCH}")
                self.gh()
                pathlib.Path(self.state["prs"]).unlink(missing_ok=True)
                got = self.run_chain_handoff(r2=r2)
                self.assertEqual((got["mode"], got["ok"], got["reason"], got["protected_hits"]), ("handoff", True, "", None), got)
                self.assertEqual(got["diff"]["path"], "merge/apply.diff")
                self.assertEqual(got["hash"], hashlib.sha256(data).hexdigest())
                self.assertEqual(self.artifact("merge/apply.diff").read_bytes(), data)
                delivered = got["delivered"]
                self.assertIs(delivered["ok"], True, delivered)
                self.assertEqual(delivered["commit"], self.remote_branch())
                self.assertEqual(git(self.bare, "rev-parse", f"{delivered['commit']}^"), self.base)
        got = self.run_chain_handoff(deliver="")
        self.assertEqual((got["ok"], got["delivered"]), (True, None))

    def test_handoff_without_base_rev_names_why_nothing_was_delivered(self):
        """base_rev が無い例外で落ちても、pr を頼んだ run の delivered は null でなく {ok: false, reason}。何も書かない"""
        got = self.run_chain_handoff(base_rev="")
        self.assertEqual((got["mode"], got["ok"]), ("handoff", False))
        self.assertIn("base_rev", got["reason"])
        self.assertNothingWritten(got["delivered"], "base_rev")
        self.assertEqual(self.made("api") + self.made("pr"), [])

    def test_handoff_refuses_redesign_and_unplaced_inside_merge(self):
        cases = (("redesign-needed", self.final_diff(), "R2 が作り直しと言った"),
                 ("pass", self.final_diff(ok=False, reason="最後の差分に入る周の子の run が差分を置かなかった: 周 2"),
                  "最後の差分に入る周の子の run が差分を置かなかった"),
                 ("pass", None, "placed が無い"))
        for r2, placed, words in cases:
            with self.subTest(r2=r2, placed=placed and placed["ok"]):
                got = self.run_script(mode="handoff", placed=json.dumps(placed), base_rev=self.base, r2=r2, deliver="pr")
                self.assertEqual((got["mode"], got["ok"], got["diff"]), ("handoff", False, None))
                self.assertIn(words, got["reason"])
                self.assertFalse(self.artifact("merge/apply.diff").exists())
                self.assertNothingWritten(got["delivered"], words)
                self.assertEqual(self.made("api") + self.made("pr"), [])

    def test_protected_branch_is_refused(self):
        for over, words in (({"protected": True}, "守られている"),
                            ({"rules": [{"type": "pull_request", "ruleset_id": 3}]}, "規則")):
            with self.subTest(over=over):
                self.gh(**{"protected": False, "rules": [], **over})
                got = self.apply_pr()
                self.assertIs(got["ok"], True, "置いた意味の ok は変えない")
                self.assertNothingWritten(got["delivered"], words)
                self.assertEqual(self.made("pr", "create"), [])

    def test_unreachable_base_is_refused_without_fetch(self):
        for status in ("diverged", "ahead", "404"):
            with self.subTest(status=status):
                self.gh(compare=status)
                got = self.apply_pr()
                self.assertIs(got["ok"], True)
                self.assertNothingWritten(got["delivered"], "届かない")
                self.assertFalse((self.repo / ".git" / "FETCH_HEAD").exists(), "fetch で FETCH_HEAD を書いた")
        self.gh(compare="identical")
        self.assertIs(self.apply_pr()["delivered"]["ok"], True, "基が既定の枝の先と同じなら届いている")

    def test_open_pr_is_read_back_not_recreated(self):
        first = self.apply_pr()["delivered"]
        second = self.apply_pr()["delivered"]
        self.assertIs(first["ok"], True, first)
        self.assertEqual(second, first, "走り直しても同じ commit・同じ PR")
        self.assertEqual(len(self.made("pr", "create")), 1)
        self.assertGreaterEqual(len(self.made("pr", "list")), 2)
        # 読み戻しは push した commit と照らす。remote の枝の先か PR の head が違えば、delivered.ok は偽で食い違いを名指す（置いた意味の ok は変わらない）
        wrong = "0" * 40
        for over, words in (({"ref_sha": wrong}, "remote の枝"), ({"view_head": wrong}, "PR の head")):
            with self.subTest(readback=over):
                git(self.bare, "update-ref", "-d", f"refs/heads/{self.BRANCH}")
                pathlib.Path(self.state["prs"]).unlink(missing_ok=True)
                self.gh(**{"ref_sha": None, "view_head": None, **over})
                got = self.apply_pr()
                self.assertIs(got["ok"], True)
                self.assertIs(got["delivered"]["ok"], False, got["delivered"])
                self.assertIn(words, got["delivered"]["reason"])
                self.assertIn(wrong, got["delivered"]["reason"])
        # 同じ名の枝が別の commit で remote に在る時、--force なしの push が拒まれ、上書きせず delivered.ok は偽
        self.gh(ref_sha=None, view_head=None)
        git(self.bare, "update-ref", "-d", f"refs/heads/{self.BRANCH}")
        pathlib.Path(self.state["prs"]).unlink(missing_ok=True)
        tree = subprocess.run(["git", "-C", str(self.repo), "mktree"], input="", capture_output=True, text=True,
                              check=True).stdout.strip()
        other = git(self.repo, "commit-tree", tree, "-m", "別の枝")
        git(self.repo, "push", "-q", "origin", f"{other}:refs/heads/{self.BRANCH}")
        creates = len(self.made("pr", "create"))
        got = self.apply_pr()
        self.assertIs(got["ok"], True)
        self.assertIs(got["delivered"]["ok"], False, got["delivered"])
        self.assertIn("push", got["delivered"]["reason"])
        self.assertEqual(self.remote_branch(), other, "別の commit の枝を上書きした")
        self.assertEqual(len(self.made("pr", "create")), creates, "押せなかった枝の PR を作った")
        self.assertFalse(self.marker.exists())

    def test_empty_word_writes_nothing(self):
        refs = self.remote_refs()
        got = self.apply_pr(deliver="")
        self.assertIn("delivered", got)
        self.assertEqual((got["ok"], got["delivered"]), (True, None))
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.remote_refs(), refs)
        shutil.rmtree(self.artifact("merge"))
        got = self.apply_pr(deliver="push")
        self.assertIs(got["ok"], False)
        self.assertIn("push", got["reason"])
        self.assertFalse(self.artifact("merge/apply.diff").exists())
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.remote_refs(), refs)
        # 置かなかった apply（最後の承認ノードが止めた）は提出もしない
        got = self.apply_pr(answer=json.dumps({"decision": "stop", "text": ""}))
        self.assertIs(got["ok"], False)
        self.assertNothingWritten(got["delivered"], "最後の承認ノードで stop と答えた")
        self.assertEqual(self.calls(), [])


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

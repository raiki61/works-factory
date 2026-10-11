"""独立の目のブロック（workflows/eyes/）の YAML の形・筋書き・script の起こしの試験。

- YAML の形: PyYAML で読むだけ（Archon を起こさない）
- 筋書き: tests/archon.py の使い捨ての木で `archon workflow test` を回す（Archon の源が無ければ見送る）
- script の起こし: scripts/*.py を一時の ARTIFACTS_DIR・WORKFLOW_ID・INPUTS_* で子のプロセスとして走らせる（Archon を起こさない）。
  目の返りのファイルを読む verdict の振る舞い（落ちた目・問いの外し）は、筋書きの dry-run では script が空の置き場で走るので、ここで見る
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests import archon
from tests.bin.gitkit import git

ROOT = pathlib.Path(__file__).resolve().parents[2]
BLOCK = ROOT / "workflows" / "eyes"
DOC = yaml.safe_load((BLOCK / "works-factory-eyes.yaml").read_text(encoding="utf-8"))
NODES = {n["id"]: n for n in DOC["nodes"]}
ROLES = {i: n for i, n in NODES.items() if "command" in n}
EYE_NODES = ("r1-minimality", "r2-compare", "premise-check", "r3-coherence", "r4-scope")
VERDICT_NODES = {f"{n}-verdict": eye for n, eye in zip(EYE_NODES, ("r1", "r2", "premise-check", "r3", "r4"))}
sys.path.append(str(ROOT / "lib"))
import eyeverdict  # noqa: E402

RETURN_FIELDS = ["ok", "r1", "r2", "r3", "r4", "questions", "premise_check", "structure_after", "protected_hits"]
RUN_ID = "run-eyes-test"
PROTECTED_UNKNOWN = "?: 守りのファイルを確かめられなかった"

# 役の返りの型の正本: 今の works（raiki61/claude-plugins の 2aa7c66cf7abe1fe09699ac2942d107123214168）の
# works/.shared/core/graphloops/graphs/review-loop.json の各節の schema を字のまま写した物（graph はリポジトリに入れない）
_STATUS3 = {"type": "string", "enum": ["pass", "redesign-needed", "unverifiable"]}
_REASON = {"type": "string", "minLength": 1}
_WHERE_TEXT = {"where": {"type": "string"}, "text": {"type": "string"}}
GRAPH_SCHEMAS = {
    "r1-comments": {  # r1.comment_candidates
        "type": "object", "required": ["candidates", "kept"], "additionalProperties": False,
        "properties": {
            "candidates": {"type": "array", "items": {
                "type": "object", "required": ["where", "comment", "same_content_at", "reason"], "additionalProperties": False,
                "properties": {"where": {"type": "string"}, "comment": {"type": "string"},
                               "same_content_at": {"type": "string"}, "reason": {"type": "string"}}}},
            "kept": {"type": "array", "items": {
                "type": "object", "required": ["where", "fact"], "additionalProperties": False,
                "properties": {"where": {"type": "string"}, "fact": {"type": "string"}}}}}},
    "r1-minimality": {  # r1.minimality
        "type": "object", "required": ["status", "reason", "deletions", "ledger_audit", "increments"],
        "additionalProperties": False,
        "properties": {
            "status": _STATUS3, "reason": _REASON,
            "deletions": {"type": "array", "items": {
                "type": "object", "required": ["where", "why"], "additionalProperties": False,
                "properties": {
                    "where": {"type": "string", "minLength": 1, "note": (
                        "照合される側（p2.diagnose.carried_r1[].where）は minLength を持つのに、正本のこちらが持たないと、"
                        "空文字が schema を通ったうえで数える口から黙って落ち、次の周の judge はその候補について 1 行も"
                        "書かなくてよくなる（実測 2026-09-16・静的）")},
                    "why": {"type": "string"}}}},
            "ledger_audit": {"type": "array", "items": {"type": "string"}},
            "increments": {"type": "array", "items": {"type": "string"}},
            "candidates_note": {"type": "string"}}},
    "r2-compare": {  # r2.compare
        "type": "object", "required": ["status", "reason", "differences"], "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": ["pass", "redesign-needed"]}, "reason": _REASON,
            "differences": {"type": "array", "items": {
                "type": "object", "required": ["kind", "text"], "additionalProperties": False,
                "properties": {"kind": {"type": "string", "enum": ["構造", "表現"]}, "text": {"type": "string"}}}}}},
    "premise-check": {  # stop.premise_check
        "type": "object", "required": ["key", "assumption", "assumption_false", "evidence", "verdict", "reason"],
        "additionalProperties": False,
        "properties": {
            "key": {"type": "string", "minLength": 1}, "assumption": {"type": "string"},
            "assumption_false": {"type": "boolean"}, "evidence": {"type": "string"},
            "verdict": {"type": "string", "enum": ["resolved", "escalate"]}, "reason": _REASON,
            "resolution": {"type": "string"}, "facts_to_add": {"type": "array", "items": {"type": "string"}}}},
    "r3-coherence": {  # r3.coherence
        "type": "object", "required": ["status", "reason"], "properties": {"status": _STATUS3, "reason": _REASON}},
    "r4-scope": {  # r4.hidden_scope
        "type": "object", "required": ["status", "reason", "capability_inventory", "policy_conflicts", "surfaced"],
        "additionalProperties": False,
        "properties": {
            "status": _STATUS3, "reason": _REASON,
            "capability_inventory": {
                "type": "object", "required": ["fired"], "additionalProperties": False,
                "properties": {"fired": {"type": "boolean"}, "lost": {"type": "array", "items": {"type": "string"}},
                               "note": {"type": "string"}}},
            "policy_conflicts": {"type": "array", "items": {"type": "string", "minLength": 1}},
            "surfaced": {"type": "array", "items": {
                "type": "object", "required": ["where", "text"], "additionalProperties": False,
                "properties": {**_WHERE_TEXT, "mechanism": {"type": "string"}, "measured": {"type": "string"},
                               "false_positive_if": {"type": "string"}}}}}},
}
SEEN_UNSEEN = ("seen", "unseen")   # concepthome.R3_HEAD と r3・r4 の指示書が求める、graph の schema に足した欄


def depends(node) -> set:
    return set(node.get("depends_on") or [])


def prep_reads(text: str) -> set:
    return set(re.findall(r"\$prep\.output\.([A-Za-z0-9_]+)", text))


def conforms(value, schema, where="$") -> list:
    """試験に要る分だけの JSON Schema の照らし（type・enum・required・properties・additionalProperties・items）"""
    kinds = schema.get("type")
    kinds = [kinds] if isinstance(kinds, str) else kinds or []
    py = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None), "integer": int}
    if kinds and not any(isinstance(value, py[k]) and not (k == "integer" and isinstance(value, bool)) for k in kinds):
        return [f"{where}: {kinds} でない（{value!r}）"]
    if "enum" in schema and value not in schema["enum"]:
        return [f"{where}: {value!r} が {schema['enum']} に無い"]
    out = []
    if isinstance(value, dict):
        out += [f"{where}: {k} が無い" for k in schema.get("required", []) if k not in value]
        if schema.get("additionalProperties") is False:
            out += [f"{where}: {k} は無い欄" for k in value if k not in schema.get("properties", {})]
        for k, sub in schema.get("properties", {}).items():
            if k in value:
                out += conforms(value[k], sub, f"{where}.{k}")
    if isinstance(value, list) and "items" in schema:
        for i, v in enumerate(value):
            out += conforms(v, schema["items"], f"{where}[{i}]")
    return out


class ShapeCase(unittest.TestCase):
    def test_every_role_node_is_read_only(self):
        for nid, node in NODES.items():
            with self.subTest(nid):
                self.assertIs(node.get("mutates_checkout"), False)
                if "command" in node:
                    self.assertEqual(node.get("context"), "fresh")

    def test_no_eye_has_shell_or_writer_tools(self):
        for nid, node in ROLES.items():
            with self.subTest(nid):
                self.assertFalse({"Bash", "Write", "Edit", "NotebookEdit"} & set(node["allowed_tools"]))
        self.assertEqual(ROLES["r2-compare"]["allowed_tools"], ["Read"])

    def test_r2_compare_gets_no_forbidden_input(self):
        """持ち主の決め independent-verdict: 比較役には目的・独立設計・後で分かった前提・累積差分だけが届く"""
        self.assertNotIn("with", NODES["r2-compare"])
        text = (BLOCK / "commands" / "r2-compare.md").read_text(encoding="utf-8")
        self.assertEqual(prep_reads(text), {"purpose_text", "design_text", "premises_text", "diff_file", "diff_lines", "changed_files"})
        self.assertEqual(re.findall(r"\$([A-Za-z0-9_-]+)\.output", text), ["prep"] * len(re.findall(r"\$prep\.output", text)))
        self.assertNotIn("$INPUTS", text)
        self.assertNotIn("$ARTIFACTS_DIR", text)

    def test_r4_waits_for_r1_and_r2_lanes(self):
        node = NODES["r4-scope"]
        self.assertLessEqual({"r1-minimality", "r2-compare", "premise-check"}, depends(node))
        self.assertEqual(node.get("trigger_rule"), "all_done")

    def test_r1_minimality_runs_without_the_comment_candidates(self):
        node = NODES["r1-minimality"]
        self.assertEqual(node.get("trigger_rule"), "all_done")
        self.assertIn("r1-comments-save", depends(node))
        self.assertNotIn("with", node)

    def test_barrier_before_verdict(self):
        barrier = NODES["eyes-complete"]
        self.assertEqual(barrier.get("bash"), "true")
        self.assertEqual(barrier.get("trigger_rule"), "all_done")
        self.assertEqual(depends(barrier), {*ROLES, "r1-comments-save", *VERDICT_NODES})
        verdict = NODES["verdict"]
        self.assertEqual(depends(verdict), {"eyes-complete", "prep", "structure-after", "protected"})
        self.assertEqual(verdict.get("trigger_rule"), "all_done")
        self.assertNotIn("with", verdict)

    def test_eye_verdict_typed(self):
        typed = {i: n for i, n in NODES.items() if "output_type" in n}
        self.assertEqual(list(typed), list(VERDICT_NODES))
        for nid, node in typed.items():
            with self.subTest(nid):
                self.assertEqual(node["output_type"], "eye-verdict")
                fmt = node["output_format"]
                self.assertEqual(set(fmt["properties"]), {"eye", "status", "reason"})
                self.assertEqual(set(fmt["required"]), {"eye", "status", "reason"})
                self.assertEqual(node["with"]["eye"], VERDICT_NODES[nid])
                eye_node = nid.removesuffix("-verdict")
                self.assertEqual(depends(node), {eye_node})
                self.assertEqual(node["with"]["out"], f"${eye_node}.output")
        self.assertFalse(any("output_type" in n for n in ROLES.values()))

    def test_frozen_read_in_commands(self):
        for path in sorted((BLOCK / "commands").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path.name):
                self.assertNotRegex(text, r"git -C|git show|git grep")
        for name in ("r1-comments", "r1-minimality", "r3-coherence", "r4-scope"):
            with self.subTest(name):
                self.assertIn("Read・Grep・Glob で cwd のファイルをそのまま読め",
                              (BLOCK / "commands" / f"{name}.md").read_text(encoding="utf-8"))

    def test_commands_read_only_declared_prep_fields(self):
        declared = set(NODES["prep"]["output_format"]["properties"])
        for nid, node in ROLES.items():
            with self.subTest(nid):
                text = (BLOCK / "commands" / f"{node['command']}.md").read_text(encoding="utf-8")
                self.assertLessEqual(prep_reads(text), declared)
                self.assertIn("prep", depends(node))

    def test_role_schemas_match_graph(self):
        for nid, want in GRAPH_SCHEMAS.items():
            got = json.loads(json.dumps(ROLES[nid]["output_format"]))
            with self.subTest(nid):
                if nid in ("r3-coherence", "r4-scope"):
                    for key in SEEN_UNSEEN:
                        self.assertEqual(got["properties"].pop(key), {"type": "array", "items": {"type": "string"}})
                        got["required"].remove(key)
                if nid == "r4-scope":
                    self.assertEqual(got.pop("if"), {"properties": {"capability_inventory": {"properties": {"fired": {"const": True}}}}})
                    self.assertEqual(got.pop("then"), {"properties": {"capability_inventory": {"required": ["fired", "lost"]}}})
                self.assertEqual(got, want)

    def test_returns_contract(self):
        self.assertEqual((DOC["returns"], DOC["outcome_field"]), ("verdict", "ok"))
        fmt = NODES["verdict"]["output_format"]
        self.assertEqual(fmt["required"], RETURN_FIELDS)
        self.assertEqual(list(fmt["properties"]), RETURN_FIELDS)
        self.assertIs(fmt["additionalProperties"], False)

    def test_eye_names_and_status_words_match_eyeverdict(self):
        """eyeverdict は目のファイル名と判定の語を YAML の output_format と同じ物として読む"""
        eye_fmt = NODES["r1-minimality-verdict"]["output_format"]["properties"]
        verdict_fmt = NODES["verdict"]["output_format"]["properties"]
        names = {*eyeverdict.EYES, eyeverdict.PREMISE}
        self.assertEqual({n["with"]["eye"] for n in NODES.values() if n.get("output_type") == "eye-verdict"}, names)
        self.assertEqual(set(eye_fmt["eye"]["enum"]), names)
        self.assertEqual(verdict_fmt["r1"]["properties"]["status"]["enum"], list(eyeverdict.STATUSES))
        self.assertEqual(verdict_fmt["premise_check"]["properties"]["verdict"]["enum"], list(eyeverdict.VERDICTS))
        self.assertEqual(eye_fmt["status"]["enum"], [*eyeverdict.STATUSES, *eyeverdict.VERDICTS])

    def test_retry_gives_three_tries(self):
        for nid, node in ROLES.items():
            with self.subTest(nid):
                self.assertEqual(node.get("retry"), {"max_attempts": 2, "on_error": "all"})

    def test_role_settings_copied(self):
        for nid, node in ROLES.items():
            with self.subTest(nid):
                self.assertEqual(node.get("settingSources"), ["user"])
                self.assertEqual(node.get("sandbox"), {"enabled": True, "allowUnsandboxedCommands": False})
                self.assertEqual(node.get("context"), "fresh")

    def test_no_workflow_level_composed_keys(self):
        self.assertFalse({"interactive", "worktree", "container", "evidence_policy", "mutates_checkout"} & set(DOC))


class FixtureCase(unittest.TestCase):
    # 筋書きごとの仕事の結末（返す節の差し替えの ok）。run の終わり（outcome）はどれも completed
    AUTHORED = {"pass": "succeeded", "redesign": "failed", "premise": "failed", "all-light": "succeeded", "protected-hit": "succeeded"}

    def test_fixtures_pass_in_archon(self):
        with archon.tree(["eyes"]) as tree:
            done = archon.archon(tree, "workflow", "test", DOC["name"], "--json")
        try:
            report = json.loads(done.stdout)
        except json.JSONDecodeError as error:
            raise AssertionError(f"workflow test の返りが読めない（{error}）: {done.stdout}{done.stderr}") from None
        got = {pathlib.PurePosixPath(r["fixture"]).name.removesuffix(".stubs.yaml"): r for r in report["results"]}
        self.assertEqual(sorted(got), sorted(self.AUTHORED), done.stdout)
        for name, result in got.items():
            with self.subTest(name):
                self.assertTrue(result["pass"], result)
                self.assertEqual((result["outcome"], result["authoredOutcome"]), ("completed", self.AUTHORED[name]))


class ScriptCase(unittest.TestCase):
    """scripts/*.py を Archon と同じ環境変数で走らせる"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.artifacts = self.tmp / "artifacts"
        self.artifacts.mkdir()
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        (self.repo / "a.txt").write_text("a\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        self.base = git(self.repo, "rev-parse", "HEAD").strip()
        self.inputs = {name: "null" for name in DOC["inputs"]}

    def pointer(self, rel: str, doc) -> str:
        path = self.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": rel})

    def eye_file(self, name: str, doc) -> None:
        path = self.artifacts / "eyes" / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def run_script(self, name: str, *, with_=None, artifacts=None, cwd=None) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.startswith("INPUTS_")}
        env.update({"ARTIFACTS_DIR": str(artifacts or self.artifacts), "WORKFLOW_ID": RUN_ID, "WORKS_FACTORY_ROOT": str(ROOT)})
        env.update({f"INPUTS_{k.upper()}": v for k, v in {**self.inputs, **(with_ or {})}.items()})
        done = subprocess.run([sys.executable, str(BLOCK / "scripts" / f"{name}.py")], cwd=cwd or self.repo, env=env,
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(done.stdout.strip().splitlines()[-1])
        self.assertEqual(conforms(got, NODES[{"save_reply": "r1-comments-save", "eye_verdict": "r1-minimality-verdict"}
                                              .get(name, name.replace("_", "-"))]["output_format"]), [])
        return got

    def start(self, **more) -> None:
        self.inputs["start"] = self.pointer("start/start.json", {"run_id": RUN_ID, "base_rev": self.base, **more})

    def prep_file(self, **more) -> None:
        self.eye_file("prep", {"run_eyes": True, "compare_due": True, "premise_due": False, **more})

    def design(self, doc) -> None:
        self.inputs["design"] = self.pointer("plan-review/design.json", doc)

    def passing_eyes(self, r4_lost=(), policy=()):
        self.eye_file("r1", {"status": "pass", "reason": "最小"})
        self.eye_file("r2", {"status": "pass", "reason": "同じ構造", "differences": []})
        self.eye_file("r3", {"status": "pass", "reason": "整合", "seen": [], "unseen": []})
        self.eye_file("r4", {"status": "pass", "reason": "なし", "seen": [], "unseen": [], "surfaced": [],
                             "capability_inventory": {"fired": bool(r4_lost), "lost": list(r4_lost)},
                             "policy_conflicts": list(policy)})
        self.eye_file("protected", {"hits": [], "lines": [], "broken": ""})

    def test_verdict_names_fallen_eye(self):
        self.prep_file()
        self.design({"question_stands": True, "reason": "立つ", "design": "設計"})
        self.passing_eyes()
        (self.artifacts / "eyes" / "r1.json").unlink()
        got = self.run_script("verdict")
        self.assertEqual(got["r1"]["status"], "unverifiable")
        self.assertIn("R1 の筋が落ちた", got["r1"]["reason"])
        self.assertFalse(got["ok"])

    def test_verdict_drops_passed_questions(self):
        self.prep_file()
        self.design({"question_stands": True, "reason": "立つ", "design": "設計"})
        self.passing_eyes(r4_lost=("古い入口——使う人がいない", "別の能力"), policy=("方針の第 1 項",))
        self.inputs["answers"] = json.dumps({"decision": "continue", "text": ""})
        self.inputs["plan_questions"] = json.dumps(["修正案 1 が狭める能力: 古い入口——使う人がいない"], ensure_ascii=False)
        got = self.run_script("verdict")
        self.assertEqual(got["questions"], ["R4 が BASE から消えたと見た能力: 別の能力", "R4 が見た人の方針とのぶつかり: 方針の第 1 項"])

    def test_verdict_carries_protected_hits(self):
        self.prep_file()
        self.design({"question_stands": True, "reason": "立つ", "design": "設計"})
        self.passing_eyes()
        self.eye_file("protected", {"hits": ["pack.json"], "lines": ["pack.json（+1 −0）"], "broken": ""})
        got = self.run_script("verdict")
        self.assertEqual(got["protected_hits"], ["pack.json"])
        self.assertTrue(got["ok"])

    def test_verdict_points_at_the_structure_measured_after_the_fix(self):
        self.prep_file()
        self.design({"question_stands": True, "reason": "立つ", "design": "設計"})
        self.passing_eyes()
        self.eye_file("structure-after", {"counts": {}})
        got = self.run_script("verdict")
        self.assertEqual(got["structure_after"], {"type": "archon_artifact", "run_id": RUN_ID, "path": "eyes/structure-after.json"})
        (self.artifacts / "eyes" / "structure-after.json").unlink()
        self.assertIsNone(self.run_script("verdict")["structure_after"])

    def test_verdict_without_prep_keeps_a_clean_protected_check_empty(self):
        self.eye_file("protected", {"hits": [], "lines": [], "broken": ""})
        got = self.run_script("verdict")
        self.assertEqual(got["protected_hits"], [])
        self.assertEqual(got["r1"]["status"], "unverifiable")
        self.assertFalse(got["ok"])

    def test_protected_broken_is_a_hit(self):
        self.start(base_rev="0" * 40)
        got = self.run_script("protected")
        self.assertTrue(got["hits"][0].startswith(PROTECTED_UNKNOWN), got)
        self.assertTrue(got["broken"])
        self.prep_file()
        self.design({"question_stands": True, "reason": "立つ", "design": "設計"})
        self.passing_eyes()
        (self.artifacts / "eyes" / "protected.json").unlink()
        self.run_script("protected")
        verdict = self.run_script("verdict")
        self.assertFalse(verdict["ok"])
        self.assertEqual(verdict["protected_hits"], got["hits"])

    def test_protected_names_touched_guarded_paths(self):
        self.start()
        (self.repo / "lib").mkdir()
        (self.repo / "lib" / "protect.py").write_text("足した\n", encoding="utf-8")
        got = self.run_script("protected")
        self.assertEqual((got["hits"], got["broken"]), (["lib/protect.py"], ""))
        self.assertTrue(json.loads((self.artifacts / "eyes" / "protected.json").read_text(encoding="utf-8"))["lines"])

    def test_verdict_never_fails(self):
        for label, setup, artifacts in (
                ("壊れた入力", lambda: self.inputs.update(design="{", answers="[", plan_questions="{"), None),
                ("目のファイルが JSON でない", lambda: (self.prep_file(), self.eye_file("r1", "{")), None),
                ("置き場が無い", lambda: None, self.tmp / "nowhere")):
            with self.subTest(label):
                setup()
                got = self.run_script("verdict", artifacts=artifacts)
                self.assertFalse(got["ok"])

    def test_eye_verdict_writes_file_and_returns_row(self):
        out = {"key": "k", "assumption": "a", "assumption_false": False, "evidence": "e", "verdict": "escalate", "reason": "実測で反証できない"}
        got = self.run_script("eye_verdict", with_={"eye": "premise-check", "out": json.dumps(out, ensure_ascii=False)})
        self.assertEqual(got, {"eye": "premise-check", "status": "escalate", "reason": "実測で反証できない"})
        self.assertEqual(json.loads((self.artifacts / "eyes" / "premise-check.json").read_text(encoding="utf-8")), out)

    def test_save_reply_writes_the_reply(self):
        reply = {"candidates": [], "kept": [{"where": "a.py:1", "fact": "なぜこの値か"}]}
        got = self.run_script("save_reply", with_={"name": "r1-comments", "out": json.dumps(reply, ensure_ascii=False)})
        self.assertEqual(got, {"saved": True})
        self.assertEqual(json.loads((self.artifacts / "eyes" / "r1-comments.json").read_text(encoding="utf-8")), reply)

    def prep_inputs(self, depth=None):
        self.start(policy_md="")
        self.inputs.update(
            purpose=self.pointer("judge/purpose.json", {"purpose_text": "古い入口を消す"}),
            judgment=self.pointer("judge/judgment.json", {"units": [], "questions": []}),
            units=json.dumps([{"id": "u1", "paths": ["a.txt"], "summary": "入口"}], ensure_ascii=False),
            plan=self.pointer("plan/plan-fields.json", {"round": 1, "fields": []}),
            ripple=self.pointer("plan/ripple.json", {"rows": []}),
            diff=self.pointer("fix/diff.patch", "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-a\n+b\n"),
            changed=json.dumps({"premise_drift": False}),
            fix_units=json.dumps([{"unit_id": "u1", "group_id": "g1", "status": "fixed", "reason": "直した"}], ensure_ascii=False),
            green_ok="true",
            depth=json.dumps(depth or [{"unit_id": "u1", "depth": "標準", "why": ["測りで見つけた"]}], ensure_ascii=False))
        self.design({"question_stands": True, "reason": "立つ", "design": "設計の本文"})

    def test_prep_resolves_diff_pointer(self):
        self.prep_inputs()
        got = self.run_script("prep")
        self.assertEqual(got["diff_file"], str(self.artifacts / "fix" / "diff.patch"))
        self.assertEqual((got["run_eyes"], got["compare_due"], got["premise_due"]), (True, True, False))
        self.assertEqual(got["diff_lines"], 6)
        self.assertEqual(json.loads((self.artifacts / "eyes" / "prep.json").read_text(encoding="utf-8")), got)

    def test_prep_names_the_file_r1_comments_save_writes(self):
        self.prep_inputs()
        self.assertEqual(pathlib.Path(self.run_script("prep")["candidates_file"]).name,
                         NODES["r1-comments-save"]["with"]["name"] + ".json")

    def test_prep_all_light_turns_eyes_off(self):
        self.prep_inputs(depth=[{"unit_id": "u1", "depth": "軽量", "why": ["何も見つけなかった"]}])
        self.assertIs(self.run_script("prep")["run_eyes"], False)

    def test_structure_after_never_fails_the_line(self):
        self.inputs["plan"] = self.pointer("plan/plan-fields.json", {"round": 1, "fields": []})
        got = self.run_script("structure_after")
        self.assertEqual(got["status"], "failed")
        self.assertTrue(got["reason"])
        self.start()
        got = self.run_script("structure_after")
        self.assertEqual(got["after"]["path"], "eyes/structure-after.json")
        self.assertTrue((self.artifacts / "eyes" / "structure-after.json").is_file())


if __name__ == "__main__":
    unittest.main()

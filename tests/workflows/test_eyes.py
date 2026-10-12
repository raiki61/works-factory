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
import concepthome  # noqa: E402
import eyeverdict  # noqa: E402
import seal  # noqa: E402

RETURN_FIELDS = ["ok", "r1", "r2", "r3", "r4", "questions", "premise_check", "structure_after", "protected_hits", "notes"]
RUN_ID = "run-eyes-test"
# pr-review-toolkit:comment-analyzer の定義の本文（anthropics/claude-plugins-official の ce721c1f1d5da2c281588818e072ae01a05d2e73 の
# plugins/pr-review-toolkit/agents/comment-analyzer.md。Apache-2.0。今の works の run が読んだ物と同じ版）の sha256
COMMENT_ANALYZER_SHA256 = "4a9c1f2eb8234a4b9231983e75739663d512e1aed242388964a165a719b84698"
COMMENT_ANALYZER_FRONT = """---
name: comment-analyzer
description: Use this agent when you need to analyze code comments for accuracy, completeness, and long-term maintainability. This includes (1) after generating large documentation comments or docstrings, (2) before finalizing a pull request that adds or modifies comments, (3) when reviewing existing comments for potential technical debt or comment rot, and (4) when you need to verify that comments accurately reflect the code they describe. See "When to invoke" in the agent body for worked scenarios.
model: inherit
color: green
---

"""

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
        self.assertEqual(prep_reads(text), {"purpose_text", "design_text", "premises_text", "diff_file", "diff_lines", "changed_files",
                                            "lang_line"})
        self.assertEqual(re.findall(r"\$([A-Za-z0-9_-]+)\.output", text), ["prep"] * len(re.findall(r"\$prep\.output", text)))
        self.assertNotIn("$INPUTS", text)
        self.assertNotIn("$ARTIFACTS_DIR", text)

    def test_r2_compare_runs_without_the_default_system_prompt(self):
        """元の旗 isolated: 比較役だけ、既定の claude_code の system prompt（cwd と git status の写しを持つ）を替える"""
        self.assertTrue(ROLES["r2-compare"].get("systemPrompt", "").strip())
        self.assertEqual([i for i, n in ROLES.items() if "systemPrompt" in n], ["r2-compare"])
        self.assertNotIn("$", ROLES["r2-compare"]["systemPrompt"])

    def test_r1_comments_carries_the_comment_analyzer_definition_verbatim(self):
        import hashlib
        text = (BLOCK / "commands" / "r1-comments.md").read_text(encoding="utf-8")
        head = "## お前の役の定義（pr-review-toolkit:comment-analyzer）\n\n"
        body = text[text.index(head) + len(head):text.index("\n\n---\n\n", text.index(head))]
        self.assertEqual(hashlib.sha256((COMMENT_ANALYZER_FRONT + body + "\n").encode("utf-8")).hexdigest(), COMMENT_ANALYZER_SHA256)

    def test_every_command_binds_the_language_and_returns_json(self):
        for path in sorted((BLOCK / "commands").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path.name):
                self.assertTrue(text.rstrip().endswith("$prep.output.lang_line\n\n返すのは、この節の返りの型（JSON Schema）に合う JSON だけ。"))

    def test_r3_names_the_target_repo_review_md(self):
        self.assertIn("（対象リポジトリ側: $prep.output.repo_review_md）",
                      (BLOCK / "commands" / "r3-coherence.md").read_text(encoding="utf-8"))

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

    def test_restored_command_sentences_stay(self):
        """元の指示書から戻した文と差し込み。消すと前提の検算・R4・R1/R3 の頭が元の読みを落とす"""
        check = (BLOCK / "commands" / "premise-check.md").read_text(encoding="utf-8")
        self.assertIn("実測を制約に足して R2 を回し直すのは次の run で", check)
        self.assertLessEqual({"design_reply", "constraints_text"}, prep_reads(check))
        self.assertIn("前の周と同じ能力なら同じ文で書け", (BLOCK / "commands" / "r4-scope.md").read_text(encoding="utf-8"))

    def test_concept_map_is_pasted_after_the_concept_head(self):
        """concepthome の R1_HEAD・R3_HEAD は『考えの住処の地図』の節を「機械がこの節の後ろに貼った」と読ませる"""
        for name, field, head in (("r1-minimality", "r1_head", concepthome.R1_HEAD), ("r3-coherence", "r3_head", concepthome.R3_HEAD)):
            with self.subTest(name):
                self.assertIn("機械がこの節の後ろに貼った", head)
                text = (BLOCK / "commands" / f"{name}.md").read_text(encoding="utf-8")
                self.assertLess(text.index(f"$prep.output.{field}"), text.index("$prep.output.concept_map"))

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
        self.assertEqual(verdict_fmt["r1"]["properties"]["status"]["enum"], list(seal.STATUSES))
        self.assertEqual(verdict_fmt["premise_check"]["properties"]["verdict"]["enum"], list(eyeverdict.VERDICTS))
        self.assertEqual(eye_fmt["status"]["enum"], [*seal.STATUSES, *eyeverdict.VERDICTS])

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
        self.assertEqual(got["r1"]["status"], seal.UNVERIFIABLE)
        self.assertIn("R1 の筋が落ちた", got["r1"]["reason"])
        self.assertFalse(got["ok"])

    def test_verdict_drops_passed_questions(self):
        self.prep_file()
        self.design({"question_stands": True, "reason": "立つ", "design": "設計"})
        self.passing_eyes(r4_lost=("古い入口——使う人がいない", "別の能力"), policy=("方針の第 1 項",))
        self.inputs["answers"] = json.dumps({"decision": "continue", "text": ""})
        self.inputs["plan_questions"] = json.dumps([{"kind": "regression", "text": "修正案 1 が狭める能力: 古い入口——使う人がいない"}],
                                                   ensure_ascii=False)
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
        self.assertTrue(got["hits"][0].startswith(seal.UNKNOWN_HEAD), got)
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

    def test_protected_hits_include_target_rules(self):
        (self.repo / ".works-protected.json").write_text(
            json.dumps({"rules": [{"id": "core", "glob": "core/*.txt", "why": "対象の芯"}]}), encoding="utf-8")
        git(self.repo, "add", ".works-protected.json")
        git(self.repo, "commit", "-q", "-m", "declare")
        self.base = git(self.repo, "rev-parse", "HEAD").strip()
        self.start()
        (self.repo / ".works-protected.json").unlink()
        (self.repo / "core").mkdir()
        (self.repo / "core" / "a.txt").write_text("足した\n", encoding="utf-8")
        got = self.run_script("protected")
        self.assertEqual((got["hits"], got["broken"]), ([".works-protected.json", "core/a.txt"], ""))

    def test_verdict_never_fails(self):
        for label, setup, artifacts in (
                ("壊れた入力", lambda: self.inputs.update(design="{", answers="[", plan_questions="{"), None),
                ("目のファイルが JSON でない", lambda: (self.prep_file(), self.eye_file("r1", "{")), None),
                ("置き場が無い", lambda: None, self.tmp / "nowhere")):
            with self.subTest(label):
                setup()
                got = self.run_script("verdict", artifacts=artifacts)
                self.assertFalse(got["ok"])

    def test_verdict_never_fails_when_lib_cannot_be_read(self):
        env_root = self.tmp / "no-root"
        env = {k: v for k, v in os.environ.items() if not k.startswith("INPUTS_")}
        env.update({"ARTIFACTS_DIR": str(self.artifacts), "WORKFLOW_ID": RUN_ID, "WORKS_FACTORY_ROOT": str(env_root)})
        done = subprocess.run([sys.executable, str(BLOCK / "scripts" / "verdict.py")], cwd=self.repo, env=env,
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(done.stdout.strip().splitlines()[-1])
        self.assertEqual(conforms(got, NODES["verdict"]["output_format"]), [])
        self.assertFalse(got["ok"])
        self.assertEqual(got["r1"]["status"], seal.UNVERIFIABLE)   # lib を読めない時の約束の形（fallen）は語を写すしかない
        self.assertIn("出口が落ちた", got["r1"]["reason"])
        self.assertTrue(got["protected_hits"])

    def test_verdict_returns_strict_json(self):
        """Archon は JSON.parse で読むので、NaN が混じった返りは出さず落ちた返りにする（boundary.returns と同じ allow_nan=False）"""
        self.prep_file()
        self.design({"question_stands": True, "reason": "立つ", "design": "設計"})
        self.passing_eyes()
        (self.artifacts / "eyes" / "protected.json").write_text('{"hits": [NaN], "lines": [], "broken": ""}', encoding="utf-8")
        got = self.run_script("verdict")
        self.assertFalse(got["ok"])
        self.assertIn("JSON に書けない", got["r1"]["reason"])

    def test_verdict_writes_the_notes_for_the_final_gate(self):
        self.prep_file()
        self.design({"question_stands": True, "reason": "立つ", "design": "設計"})
        (self.artifacts / "plan-review" / eyeverdict.DESIGN_PREMISES).write_text(
            json.dumps({"given": [], "withheld": [], "seen": {"count": 0}}), encoding="utf-8")
        self.passing_eyes(r4_lost=("古い入口——使う人がいない",))
        self.eye_file("r2", {"status": "pass", "reason": "人の答えが渡されていない", "differences": []})
        self.eye_file(eyeverdict.R2_PREMISES.removesuffix(".json"), {"node": "r2.compare", "given": [{"kind": "human_answer", "what": "修正前の関所: continue"}]})
        self.inputs["answers"] = json.dumps({"decision": "continue", "text": ""})
        self.inputs["plan_questions"] = json.dumps([{"kind": "regression", "text": "修正案 1 が狭める能力: 古い入口——使う人がいない"}],
                                                   ensure_ascii=False)
        got = self.run_script("verdict")
        self.assertEqual(got["questions"], [])
        notes = json.loads((self.artifacts / "eyes" / eyeverdict.PREMISE_INPUTS).read_text(encoding="utf-8"))
        self.assertEqual(notes["design"], {"given": [], "withheld": [], "seen": {"count": 0}})
        self.assertEqual(notes["claims"], ["人の答えが渡されていない"])
        self.assertEqual([c["kind"] for c in notes["compare"]["claims_given"]], ["human_answer"])
        passes = json.loads((self.artifacts / "eyes" / eyeverdict.GATE_PASSES).read_text(encoding="utf-8"))
        self.assertEqual([p["by"] for p in passes], ["human"])

    def test_premise_facts_reach_the_report(self):
        """E37: 前提の検算が仮定を偽（resolved）と示したら、返り notes の隣の premise-check.json の問いの key と実測 facts_to_add を、
        最後の関所と報告が読み（問いは held のまま残すと言い、実測を並べる）、報告は実測を次の依頼の constraints（{text, measured_how,
        kind: 実測}。carry.parts が読む）に運ぶ。次の run の判定は前提の実測の制約に足し（judge_accept.with_carried）、目の支度は
        運ばれた制約の在る run では深さで目を省かない"""
        import carry
        import judge_accept
        import runreport
        self.prep_file(premise_due=True, compare_due=False)
        self.design({"question_stands": False, "premise_invalid_reason": "上限が無いと仮定した", "design": ""})
        self.passing_eyes()
        self.eye_file("premise-check", {"key": "上限を呼び手ごとに持つか", "assumption": "上限が無い", "assumption_false": True,
                                        "evidence": "config.py:3", "verdict": "resolved", "reason": "上限は在る",
                                        "resolution": "config.py:3 に上限 10", "facts_to_add": ["上限は config.py:3 の 10"]})
        got = self.run_script("verdict")
        self.assertEqual(got["notes"], {"type": "archon_artifact", "run_id": RUN_ID, "path": f"eyes/{eyeverdict.PREMISE_INPUTS}"})
        folder = self.artifacts / "eyes"
        self.assertEqual(eyeverdict.premise_fact_lines(folder),
                         ["仮定は偽と検算した——問い「上限を呼び手ごとに持つか」は保留（held）のまま残す（次の run の判定が回し直した R2 を見て決める）"
                          ": config.py:3 に上限 10", "次の run の制約に足す実測: 上限は config.py:3 の 10"])
        out = self.tmp / "report"
        eyes = {**{k: got[k] for k in got}, "notes": str(folder / eyeverdict.PREMISE_INPUTS)}
        built = runreport.build({"eyes": eyes}, {}, {}, None, "needs_human", "", out_dir=out, run_id="run-9")
        text = pathlib.Path(built["report"]).read_text(encoding="utf-8")
        self.assertIn("  - 次の run の制約に足す実測: 上限は config.py:3 の 10", text)
        doc = json.loads(pathlib.Path(built["next_request"]).read_text(encoding="utf-8"))
        rows = [{"text": "上限は config.py:3 の 10", "measured_how": carry.CARRIED_HOW.format(run="run-9"), "kind": carry.MEASURED}]
        self.assertEqual(doc["constraints"], rows)
        self.assertEqual(carry.parts({"findings": [], "constraints": rows})["constraints"], rows)
        self.assertFalse([r for r in doc["findings"] + doc["prior_failures"] if "上限は config.py:3 の 10" in r["text"]],
                         "直す穴にも前の失敗にも混ぜない")
        jdir = self.tmp / "judge"
        jdir.mkdir()
        (jdir / judge_accept.CARRIED_FILE).write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        merged = judge_accept.with_carried({"constraints": [{"text": "a", "measured_how": "m", "kind": "仮説"}]}, jdir)
        self.assertEqual([c["text"] for c in merged["constraints"]], ["a", "上限は config.py:3 の 10"])

    def test_carried_constraints_keep_the_eyes(self):
        """E37（R2 を省かない）: 前の run が運んだ実測が判定の制約に在る run は、深さが目を省く軽量の単位でも run_eyes を真にする
        （元 review-loop.py:3755 の r2_refire_forced）"""
        import carry
        import depth
        self.start()
        self.inputs.update({"judgment": self.pointer("judge/judgment.json", {"units": []}),
                            "purpose": self.pointer("judge/purpose.json", {"purpose_text": "目的"}),
                            "diff": self.pointer("fix/fix.diff", ""), "answers": "null", "start_answers": "null",
                            "changed": json.dumps({}), "x_scalars": "{}", "units": "[]", "fix_units": "[]",
                            "depth": json.dumps([{"unit_id": "u1", "depth": depth.LIGHT, "why": ""}], ensure_ascii=False)})
        self.design({"question_stands": True, "reason": "立つ", "design": "設計"})
        got = self.run_script("prep")
        self.assertFalse(got["run_eyes"], "軽量の単位だけなら目を省く")
        self.pointer("judge/premises.json", {"constraints": [
            {"text": "上限は 10", "measured_how": carry.CARRIED_HOW.format(run="run-0"), "kind": carry.MEASURED}]})
        self.assertTrue(self.run_script("prep")["run_eyes"])

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

    def test_policy_path_is_frozen_copy(self):
        """独立の目に渡す方針のパスは始めの記録の固めた版の写し（policy_md の生の文書ではない）"""
        self.prep_inputs()
        self.start(policy_md=str(self.repo / "POLICY.md"),
                   policy={"named": "POLICY.md", "path": str(self.repo / "POLICY.md"), "sha256": "a" * 64,
                           "copy": "/run/policy/frozen.md"})
        self.assertEqual(self.run_script("prep")["policy_path"], "/run/policy/frozen.md")

    def test_prep_pastes_the_premises_and_names_the_target_review_md(self):
        self.prep_inputs()
        (self.repo / "REVIEW.md").write_text("# 観点\n", encoding="utf-8")
        request = self.tmp / "request.md"
        request.write_text("`docs/d.md` の 2 節のとおりに入口を直す", encoding="utf-8")
        self.start(policy_md="", request_file=str(request), lang="English")
        self.inputs["answers"] = json.dumps({"decision": "continue", "text": "古い入口は消してよい"}, ensure_ascii=False)
        self.inputs["start_answers"] = json.dumps({"decision": "continue", "text": "入口は 1 つに絞る"}, ensure_ascii=False)
        (self.artifacts / "plan-review" / eyeverdict.DESIGN_PREMISES).write_text(
            json.dumps({"given": [], "withheld": [], "seen": {"count": 1, "last_round": 1}}), encoding="utf-8")
        self.inputs["changed"] = json.dumps({"premise_drift": True, "premise_drift_note": "入口は 2 つあった"}, ensure_ascii=False)
        self.inputs["x_scalars"] = json.dumps({"x_endpoints": 2})
        got = self.run_script("prep")
        self.assertEqual(pathlib.Path(got["repo_review_md"]).resolve(), (self.repo / "REVIEW.md").resolve())
        for want in ("古い入口は消してよい", "入口は 2 つあった", "### 対象のリポジトリの地図", "### 依頼が名指した設計書の節",
                     "依頼が名指したが引けなかった: docs/d.md 2 節"):
            self.assertIn(want, got["premises_text"])
        self.assertIn("English", got["lang_line"])
        self.assertIn("x_endpoints 2", got["scalars"])
        self.assertEqual(json.loads(got["design_reply"])["design"], "設計の本文")
        ledger = json.loads((self.artifacts / "eyes" / eyeverdict.R2_PREMISES).read_text(encoding="utf-8"))
        self.assertEqual(len([g for g in ledger["given"] if g["kind"] == "human_answer"]), 2)
        self.assertEqual(len(ledger["after_design"]), 1)
        self.assertIn("古い入口は消してよい", ledger["after_design"][0])
        (self.repo / "REVIEW.md").unlink()
        self.assertIn("無い", self.run_script("prep")["repo_review_md"])

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

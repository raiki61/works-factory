"""判定のブロック（workflows/judge/）の YAML の形・筋書き・script の振る舞いの試験（計画 docs/plans/2026-10-12-blocks/judge.md の「試験」）。

- YAML の形: PyYAML で読み、Archon を起こさない。返す節の約束（docs/design.md の「judge の返り」）・関所・輪・役の節の設定の表
- 筋書き: tests/archon.py の使い捨ての木で `archon workflow test` と `archon validate workflows` を回す。源か bun が無ければ見送る
- script の振る舞い: scripts/<名>.py を子のプロセスで走らせる（Archon が渡す INPUTS_<名>・ARTIFACTS_DIR・WORKFLOW_ID と、
  boundary.lib_root() が届く WORKS_FACTORY_ROOT を置く。作業ツリーは tests/e2e/target-seed/ の写し）
"""
import json
import os
import pathlib
import shlex
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests import archon
from tests.bin.gitkit import committed_copy, git

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "lib"))
import judge_accept as ja  # noqa: E402
import rolekit  # noqa: E402

BLOCK = ROOT / "workflows" / "judge"
YAML_FILE = BLOCK / "works-factory-judge.yaml"
SCRIPTS = BLOCK / "scripts"
COMMANDS = BLOCK / "commands"
SEED = ROOT / "tests" / "e2e" / "target-seed"
NAME = "works-factory-judge"
NO_DEADLINE = 1728000000
RUN_ID = "run-judge"

# 返す節の欄（docs/design.md の「ブロックの返りの約束」の judge の返り）
RETURNS = ("ready", "stop_reason", "units", "judgment", "purpose", "world", "spec", "out_of_purpose", "rejudge_verdict")
INPUTS = {"start": "null", "baseline": "null", "objection": "", "prior_failures": "null"}
RUN_OWNED = ("worktree", "container", "evidence_policy", "mutates_checkout")
MATERIALS = tuple(ja.MATERIAL_ROLES)
PUBLIC = ("premises.json", "judge-verify.json", "pr-excluded.json", "materials.json")

# 役の節の設定（今の works の旧 YAML の値。works/blk-*/blk-*.yaml と darkfactory/darkfactory.yaml の 174〜400 行・866 行）
BASE = {"enabled": True, "allowUnsandboxedCommands": False}
CLOSED = {**BASE, "failIfUnavailable": True, "excludedCommands": ["works-gh:*"], "network": {"allowedDomains": []}}
DELEGATE = {**BASE, "failIfUnavailable": True, "enableWeakerNetworkIsolation": True,
            "network": {"allowedDomains": ["*"], "allowLocalBinding": True}, "filesystem": {"allowWrite": ["/"]}}
READ = ["Read", "Grep", "Glob"]
WEB = ["WebSearch", "WebFetch"]
INVESTIGATE = [*READ, "Bash", *WEB]
WRITE_TESTS = [*READ, "Edit", "Write", "Bash", *WEB]
# 節の id → (model, effort, allowed_tools, sandbox, mutates_checkout が false か, context)
ROLES = {
    "spec": ("opus", "medium", WRITE_TESTS, BASE, False, None),
    "spec-review": ("opus", "high", [*READ, *WEB], BASE, True, None),
    "spec-revise": ("opus", "medium", WRITE_TESTS, BASE, False, None),
    "pr-check": ("sonnet", "medium", INVESTIGATE, CLOSED, False, None),
    "premises": ("sonnet", "medium", INVESTIGATE, BASE, False, None),
    "purpose": ("sonnet", "medium", [*READ, *WEB], BASE, True, None),
    "world-classes": ("opus", "high", [], BASE, True, None),
    "world-judge": ("sonnet", "medium", WEB, BASE, True, None),
    "prior-decisions": ("sonnet", "medium", INVESTIGATE, CLOSED, False, None),
    "purpose-review": ("sonnet", "medium", READ, BASE, True, None),
    "local-review": ("sonnet", "medium", [*INVESTIGATE, "Skill", "Agent"], CLOSED, False, None),
    "consistency-bypass": ("sonnet", "medium", READ, BASE, True, None),
    "hygiene": ("sonnet", "medium", [], BASE, True, None),
    "external-standards": ("sonnet", "medium", INVESTIGATE, CLOSED, False, None),
    "procedure-trace": ("sonnet", "medium", INVESTIGATE, CLOSED, False, None),
    "gate-efficacy": ("sonnet", "medium", INVESTIGATE, DELEGATE, False, None),
    "test-double-fidelity": ("sonnet", "medium", INVESTIGATE, DELEGATE, False, None),
    "main-path-observation": ("sonnet", "medium", INVESTIGATE, DELEGATE, False, None),
    "provenance": ("sonnet", "medium", INVESTIGATE, DELEGATE, False, None),
    "diagnose": ("opus", "high", [*READ, *WEB], BASE, True, None),
    "judge-verify": ("opus", "high", [*READ, *WEB, "Agent", "Write"], BASE, True, "fresh"),
    "rejudge": ("opus", "high", [*READ, *WEB], BASE, True, "fresh"),
}
# 輪の id → 受け付けの節と fresh_context（旧 YAML: 仕様の 3 つの輪と再審の輪は true、ほかは false）
FRESH = {"spec-loop", "spec-review-loop", "spec-revise-loop", "rejudge-loop"}
# 観点の正本（REVIEW.md）を読む役の指示書（元が {{inputs.review_md}} で読ませていた物）
REVIEW_READERS = ("diagnose", "material-local-review", "material-consistency-bypass", "material-hygiene",
                  "material-external-standards", "material-procedure-trace")


def load() -> dict:
    return yaml.safe_load(YAML_FILE.read_text(encoding="utf-8"))


def walk(nodes):
    for node in nodes:
        yield node
        if "loop_group" in node:
            yield from walk(node["loop_group"]["nodes"])


def nodes() -> dict:
    return {n["id"]: n for n in walk(load()["nodes"])}


def loops() -> dict:
    return {n["id"]: n for n in walk(load()["nodes"]) if "loop_group" in n}


class ReturnsShapeTest(unittest.TestCase):
    def test_verdict_returns_exactly_the_contract(self):
        doc, by = load(), nodes()
        self.assertEqual((doc["returns"], doc["outcome_field"]), ("verdict", "ready"))
        fmt = by["verdict"]["output_format"]
        self.assertEqual(sorted(fmt["properties"]), sorted(RETURNS))
        self.assertEqual(sorted(fmt["required"]), sorted(RETURNS))
        self.assertIs(fmt["additionalProperties"], False)
        self.assertEqual(fmt["properties"]["ready"], {"type": "boolean"})
        self.assertEqual(fmt["properties"]["stop_reason"], {"type": "string"})
        self.assertEqual(by["verdict"]["trigger_rule"], "all_done")
        self.assertNotIn("output_type", by["verdict"])

    def test_inputs_are_the_contract_and_prior_failures(self):
        inputs = load()["inputs"]
        self.assertEqual({k: v["default"] for k, v in inputs.items()}, INPUTS)

    def test_head_keeps_only_the_gate_declaration(self):
        """include で差し込まれるブロックは run の持ち物（worktree ほか）を書かない（workflows/AGENTS.md の E16）。
        interactive: true だけは書く: 止めた Archon の validate は、工程の頭に無いまま approval: の節を持つ工程に警告を出し
        （loader.ts の validateWorkflowClassPlacement の猶予）、include した線の validate はこの鍵に何も言わない"""
        doc = load()
        self.assertEqual([k for k in RUN_OWNED if k in doc], [])
        self.assertIs(doc["interactive"], True)


class GateTest(unittest.TestCase):
    def test_spec_gate_is_an_approval_with_the_four_words(self):
        by = nodes()
        gate = by["spec-gate"]
        self.assertEqual([d["id"] for d in gate["approval"]["decisions"]], ["approve", "continue", "stop", "reject"])
        self.assertEqual(gate["approval"]["message"], "$spec-ask.output.message")
        self.assertEqual(gate["idle_timeout"], NO_DEADLINE)
        self.assertEqual(by["spec-freeze"]["with"]["answer"], {"from": "$spec-gate.output", "if_skipped": None})


class LoopTest(unittest.TestCase):
    def test_every_loop_retries_three_times_until_its_accept_is_done(self):
        for lid, loop in loops().items():
            with self.subTest(loop=lid):
                body = loop["loop_group"]
                accept = body["nodes"][-1]["id"]
                self.assertTrue(accept.endswith("-accept"), accept)
                self.assertEqual(body["max_iterations"], 3)
                self.assertEqual(body["until_bash"], f'done=${accept}.output.done; test "$done" = true')
                self.assertEqual(loop["timeout"], NO_DEADLINE)
                self.assertIs(body["fresh_context"], lid in FRESH)

    def test_roles_receive_the_reject_reason_through_with(self):
        """拒否の理由は役の節の with: に $LOOP_PREV で結び、指示書は $INPUTS.reject_reason で受け、rolekit.with_reject の見出しと
        文で出す（1 周目の $LOOP_PREV は空の字）"""
        lead = rolekit.with_reject("", "").split("\n\n")[1].removesuffix(":")
        for loop in loops().values():
            body = loop["loop_group"]["nodes"]
            for role in (n for n in body if "command" in n):
                with self.subTest(role=role["id"]):
                    self.assertEqual(role["with"], {"reject_reason": f"$LOOP_PREV.{body[-1]['id']}.output.reason"})
                    text = (COMMANDS / f"{role['command']}.md").read_text(encoding="utf-8")
                    self.assertNotIn("$LOOP_PREV", text)
                    section = text.partition(f"{rolekit.REJECT_HEADING}\n\n")[2]
                    self.assertTrue(section.startswith(lead), section[:80])
                    self.assertIn("```text\n$INPUTS.reject_reason\n```", section)

    def test_materials_are_eleven_loops_one_per_command(self):
        material_loops = sorted(lid.removesuffix("-loop") for lid in loops() if lid.removesuffix("-loop") in MATERIALS)
        self.assertEqual(material_loops, sorted(MATERIALS))
        commands = sorted(p.stem.removeprefix("material-") for p in COMMANDS.glob("material-*.md"))
        self.assertEqual(commands, sorted(MATERIALS))
        by = nodes()
        for name in MATERIALS:
            with self.subTest(material=name):
                self.assertEqual(by[name]["command"], f"material-{name}")
                self.assertEqual(by[f"{name}-loop"]["when"], f"$material-route.output.{ja.route_key(name)} == true")

    def test_role_names_are_the_libs(self):
        """役の名の持ち主は lib（MATERIAL_ROLES・SPEC_ROLES）。YAML の route の欄と with: の role がそれに合う"""
        by = nodes()
        route = by["material-route"]["output_format"]
        keys = {ja.route_key(r) for r in ja.MATERIAL_ROLES} | {"reason"}
        self.assertEqual((set(route["required"]), set(route["properties"])), (keys, keys))
        for script, table in (("material_prep", ja.MATERIAL_ROLES), ("material_accept", ja.MATERIAL_ROLES),
                              ("spec_accept", ja.SPEC_ROLES)):
            with self.subTest(script=script):
                roles = [n["with"]["role"] for n in by.values() if n.get("script") == script]
                self.assertEqual(sorted(roles), sorted(table))


class RoleSettingsTest(unittest.TestCase):
    def test_roles_keep_the_old_settings(self):
        by = nodes()
        roles = {nid for nid, n in by.items() if "command" in n or "prompt" in n}
        self.assertEqual(sorted(roles), sorted(ROLES))
        for nid, (model, effort, tools, sandbox, read_only, context) in ROLES.items():
            n = by[nid]
            with self.subTest(role=nid):
                self.assertEqual((n["model"], n["effort"]), (model, effort))
                self.assertEqual(n["settingSources"], ["user"])
                self.assertEqual(n["allowed_tools"], tools)
                self.assertEqual(n["sandbox"], sandbox)
                self.assertEqual(n.get("context"), context)
                self.assertEqual(n.get("mutates_checkout"), False if read_only else None)
                self.assertEqual(n["idle_timeout"], NO_DEADLINE)
                self.assertTrue((COMMANDS / f"{n['command']}.md").is_file(), n["command"])

    def test_purpose_role_does_not_see_the_prior_run(self):
        """目的の役に前の run の判断（前の失敗の行・前の判定）を見せない（持ち主の決め premises-purpose の当て方）"""
        role = nodes()["purpose"]
        text = (COMMANDS / "purpose.md").read_text(encoding="utf-8") + json.dumps(role.get("with", {}), ensure_ascii=False)
        for word in ("prior_failures", "prior-failures", "judgment", "PRIOR"):
            self.assertNotIn(word, text)

    def test_viewpoint_readers_read_review_md(self):
        for name in REVIEW_READERS:
            with self.subTest(command=name):
                self.assertIn(".output.review_md", (COMMANDS / f"{name}.md").read_text(encoding="utf-8"))


class FixtureTest(unittest.TestCase):
    """筋書き（fixtures/）を Archon の workflow test で回す。配線だけを見る（振る舞いは下の子のプロセスの試験）"""

    @classmethod
    def setUpClass(cls):
        try:
            with archon.tree(["judge"]) as tree:
                done = archon.archon(tree, "workflow", "test", NAME, "--json")
                checked = archon.archon(tree, "validate", "workflows", "--json", "--cwd", str(tree))
        except unittest.SkipTest as skip:
            cls.skipped = str(skip)
            return
        cls.skipped = ""
        text = done.stdout
        cls.results = {pathlib.PurePosixPath(r["fixture"]).name.removesuffix(".stubs.yaml"): r
                       for r in json.JSONDecoder().raw_decode(text[text.index("{"):])[0]["results"]}
        validated = json.loads(checked.stdout)["results"]
        cls.issues = {r["workflowName"]: r["issues"] for r in validated}

    def check(self, name):
        if self.skipped:
            self.skipTest(self.skipped)
        result = self.results[name]
        self.assertTrue(result["pass"], result)
        self.assertEqual((result["missingStubs"], result["unusedStubs"]), ([], []), result)

    def test_validate_has_no_issue(self):
        if self.skipped:
            self.skipTest(self.skipped)
        self.assertEqual(self.issues.get(NAME), [])

    def test_every_fixture_has_a_test(self):
        if self.skipped:
            self.skipTest(self.skipped)
        self.assertEqual(sorted(self.results), sorted(name.removeprefix("test_fixture_").replace("_", "-")
                                                      for name in dir(self) if name.startswith("test_fixture_")))

    def test_fixture_pass(self):
        self.check("pass")

    def test_fixture_bad_request(self):
        self.check("bad-request")

    def test_fixture_judge_gave_up(self):
        self.check("judge-gave-up")

    def test_fixture_no_open_units(self):
        self.check("no-open-units")

    def test_fixture_spec_on(self):
        self.check("spec-on")

    def test_fixture_world_offline(self):
        self.check("world-offline")

    def test_fixture_material_peer_stop(self):
        self.check("material-peer-stop")

    def test_fixture_rejudge(self):
        self.check("rejudge")


# ---------------------------------------------------------------- script の振る舞い（子のプロセス）
KEY = "stats.py mean: 分母が len(xs) - 1"
REQUEST = [{"where": "stats.py", "text": "mean([1, 2, 3]) が 2 でなく 3 を返す。test_mean_of_three が赤"}]


def empty_reply(**over) -> dict:
    """開いた単位の無い判定役の返答（judge_output の規則の全部を空で通る形）"""
    return {"units": [], "questions": [], "framing": "依頼の行は 1 つの根に当たる", "one_shot": "直す物は無い",
            "materials_missing": [], "carried_r1": [], "one_shot_closes": [], "precedents": [], **over}


def open_reply(**over) -> dict:
    """開いた単位 1 つ（KEY）の判定役の返答（judge_output の規則を通る形）"""
    unit = {"key": KEY, "label": "block", "disposition": "do-now",
            "reason": f"事実: {KEY}。反証: 意図の取り違えを当たったが、関数名とテストが逆を期待する",
            "origin_analysis": "写し間違いの形", "why_chain": ["テストが境界の値を試していない"],
            "class_query": {"how": {"patterns": ["(len(xs) - 1)"], "fixed": True, "paths": ["stats.py"], "count": "lines"},
                            "counts": "defects", "total": 1}}
    precedent = {"key": KEY, "problem": "数列の算術平均を求める", "source": "Python の statistics.mean の文書の節",
                 "verdict": "adopt", "reason": "分母はデータ点の数 len(xs)"}
    return empty_reply(units=[unit], framing="依頼の行は stats.py の mean の分母の取り違え", one_shot="mean の分母を len(xs) に直す",
                       one_shot_closes=[KEY], precedents=[precedent], **over)


class Run:
    """1 run の置き場と作業ツリー。script を子のプロセスで走らせる"""

    def __init__(self, case: unittest.TestCase, request=REQUEST, **start):
        tmp = tempfile.TemporaryDirectory()
        case.addCleanup(tmp.cleanup)
        base = pathlib.Path(tmp.name)
        self.repo = base / "repo"
        self.head = committed_copy(self.repo, SEED)
        self.artifacts = base / "artifacts"
        self.artifacts.mkdir()
        (self.artifacts / "entry").mkdir()
        request_file = ""
        if request is not None:
            request_file = str(base / "request.json")
            pathlib.Path(request_file).write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        record = {"run_id": RUN_ID, "base_rev": self.head, "test_cmd": "", "adapter": "", "final_gate": "always", "thickness": "",
                  "request_file": request_file, "features_cut": ["judge_verify"], "answers": [], "gates": "",
                  "input": {"base": {"rev": self.head, "from": "head", "name": "", "label": "HEAD"}, "head_rev": self.head,
                            "diff": {"empty": True, "files": 0, "stat": ""}, "requests": len(request or []),
                            "request_file": request_file, "pr": None, "spec": False}}
        record.update(start)
        (self.artifacts / "entry" / "start.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        self.start = json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": "entry/start.json"})
        self.case = case

    @property
    def judge(self) -> pathlib.Path:
        return self.artifacts / "judge"

    def run(self, script: str, *, objection: str = "", start=None, launcher=(sys.executable,), **inputs) -> subprocess.CompletedProcess:
        env = {k: v for k, v in os.environ.items() if not k.startswith("INPUTS_")}
        env.update({"ARTIFACTS_DIR": str(self.artifacts), "WORKFLOW_ID": RUN_ID, "WORKS_FACTORY_ROOT": str(ROOT),
                    "PYTHONDONTWRITEBYTECODE": "1", "INPUTS_START": self.start if start is None else start,
                    "INPUTS_BASELINE": "null", "INPUTS_OBJECTION": objection, "INPUTS_PRIOR_FAILURES": "null"})
        env.update({f"INPUTS_{k.upper()}": v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for k, v in inputs.items()})
        return subprocess.run([*launcher, str(SCRIPTS / f"{script}.py")], cwd=self.repo, env=env,
                              capture_output=True, text=True, encoding="utf-8")

    def returned(self, script: str, **kw) -> dict:
        done = self.run(script, **kw)
        self.case.assertEqual(done.returncode, 0, f"{script}: {done.stdout}{done.stderr}")
        lines = [line for line in done.stdout.splitlines() if line.strip()]
        self.case.assertEqual(len(lines), 1, f"{script} の標準出力は JSON 1 行: {done.stdout}")
        return json.loads(lines[0])

    def resolve(self, ptr) -> pathlib.Path:
        self.case.assertEqual((ptr["type"], ptr["run_id"]), ("archon_artifact", RUN_ID))
        return self.artifacts / ptr["path"]


def verdict_shape(case: unittest.TestCase, out: dict) -> None:
    """返す節の返りが output_format に合う（欄がちょうど在り、型が合う）"""
    fmt = nodes()["verdict"]["output_format"]
    case.assertEqual(sorted(out), sorted(fmt["required"]))
    case.assertIsInstance(out["ready"], bool)
    case.assertIsInstance(out["stop_reason"], str)
    case.assertIsInstance(out["units"], list)
    for unit in out["units"]:
        case.assertEqual(sorted(unit), ["id", "paths", "summary"])
    case.assertIn(out["rejudge_verdict"], (None, "採る", "退ける", "一部採る"))


JSON_TYPES = {"boolean": bool, "string": str, "array": list, "object": dict, "null": type(None), "integer": int}


def node_inputs(node: dict) -> dict:
    """節の with: を子のプロセスの入力にする。上流の出力を指す値は空の字、指図（from/if_skipped）は if_skipped の値"""
    inputs = {}
    for key, value in node.get("with", {}).items():
        if isinstance(value, dict):
            inputs[key] = json.dumps(value.get("if_skipped"))
        elif isinstance(value, str) and value.startswith("$"):
            inputs[key] = ""
        else:
            inputs[key] = value
    return inputs


def write_purpose(r: Run) -> None:
    (r.judge / "purpose.json").write_text(json.dumps({"purpose_text": "平均が正しい値を返す", "source": "①PR 説明",
                                                      "known_weaknesses": [], "source_files": []}, ensure_ascii=False), encoding="utf-8")


class ScriptReturnsTest(unittest.TestCase):
    def test_every_script_node_prints_one_line_of_its_output_format(self):
        """output_format を持つ script の節は、それに合う JSON を 1 行出す（出さないと Archon は節を落とし、輪の中なら輪ごと落ちる）。
        YAML の並びで 1 つの置き場に走らせ、上流の出力は空の字で渡す。世界の解の段からは、輪が回る形（止めの控えが無く目的の文が在る）の
        新しい置き場で走らせる"""
        r = Run(self)
        for nid, node in nodes().items():
            if "script" not in node or "output_format" not in node:
                continue
            if nid == "world-intake":
                r = Run(self)
                r.returned("intake")
                write_purpose(r)
            with self.subTest(node=nid):
                fmt = node["output_format"]
                out = r.returned(node["script"], **node_inputs(node))
                self.assertEqual(sorted(set(fmt["required"]) - set(out)), [], out)
                self.assertEqual(sorted(set(out) - set(fmt["properties"])), [], out)
                for key, value in out.items():
                    kinds = fmt["properties"][key].get("type")
                    if kinds is not None:
                        kinds = [kinds] if isinstance(kinds, str) else kinds
                        self.assertIsInstance(value, tuple(JSON_TYPES[k] for k in kinds), key)


class UvLaunchTest(unittest.TestCase):
    def test_read_only_script_leaves_a_python_project_untouched(self):
        """Archon は runtime: uv の節を作業ツリーで `uv run <script>` で起こす。対象が pyproject.toml を持つと、宣言（# /// script）の
        無い script は uv が対象の環境（.venv・uv.lock）を作業ツリーに作り、mutates_checkout: false の節が落ちる"""
        r = Run(self)
        (r.repo / "pyproject.toml").write_text('[project]\nname = "target"\nversion = "0"\n', encoding="utf-8")
        git(r.repo, "add", "pyproject.toml")
        git(r.repo, "commit", "-q", "-m", "pyproject")
        done = r.run("intake", launcher=("uv", "run", "--quiet"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(git(r.repo, "status", "--porcelain", "--ignored"), "")
        for script in SCRIPTS.glob("*.py"):
            with self.subTest(script=script.name):
                self.assertTrue(script.read_text(encoding="utf-8").startswith("# /// script\n"))


class StopPathFilesMixin:
    def assert_pointers_filled(self, r: Run, out: dict):
        """指し札の先と公開の隣のファイルが在り、空でない（Archon は節の終わりに先が在って空でないかを照らす）"""
        verdict_shape(self, out)
        for field in ("judgment", "purpose", "world", "spec", "out_of_purpose"):
            if out[field] is None:
                continue
            path = r.resolve(out[field])
            self.assertTrue(path.is_file() and path.stat().st_size > 0, f"{field}: {path}")
        folder = r.resolve(out["judgment"]).parent
        for name in PUBLIC:
            path = folder / name
            self.assertTrue(path.is_file() and path.stat().st_size > 0, name)
            json.loads(path.read_text(encoding="utf-8"))
        judgment = json.loads(r.resolve(out["judgment"]).read_text(encoding="utf-8"))
        for key in ("units", "questions", "framing", "one_shot", "materials_missing", "carried_r1", "one_shot_closes", "precedents"):
            self.assertIn(key, judgment)
        purpose = json.loads(r.resolve(out["purpose"]).read_text(encoding="utf-8"))
        self.assertEqual(sorted(purpose), ["known_weaknesses", "purpose_text", "source", "source_files"])


class AcceptLoopTest(unittest.TestCase):
    def test_diagnose_accept_gives_up_on_the_third_reject(self):
        """受け付けが拒めば 3 回まで出し直す: 1・2 回目は done: false、3 回目は done: true で、拒否の控えに 3 行。
        標準出力の done を until_bash の字に入れて走らせると、3 回目だけ終了の値 0"""
        r = Run(self)
        self.assertTrue(r.returned("intake")["go"])
        bad = empty_reply(units=[{"key": KEY, "label": "bogus"}])
        until = nodes()["diagnose-loop"]["loop_group"]["until_bash"]
        exits = []
        for n in (1, 2, 3):
            out = r.returned("diagnose_accept", reply=bad)
            self.assertEqual((out["ok"], out["done"]), (False, n == 3), out)
            self.assertTrue(out["reason"])
            script = until.replace("$diagnose-accept.output.done", shlex.quote(json.dumps(out["done"])))
            exits.append(subprocess.run(["sh", "-c", script]).returncode)
        self.assertEqual([e == 0 for e in exits], [False, False, True])
        self.assertEqual(len(json.loads((r.judge / "rejects-diagnose.json").read_text(encoding="utf-8"))), 3)

    def test_accepted_judgment_is_written_with_its_public_neighbours(self):
        r = Run(self)
        r.returned("intake")
        out = r.returned("diagnose_accept", reply=empty_reply())
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        judgment = json.loads((r.judge / "judgment.json").read_text(encoding="utf-8"))
        self.assertEqual(judgment["units"], [])
        returned = r.returned("verdict")
        self.assertEqual(r.resolve(returned["judgment"]), r.judge / "judgment.json")
        for name in PUBLIC:
            self.assertTrue((r.judge / name).is_file(), name)

    def test_judge_that_changed_the_tree_is_refused(self):
        r = Run(self)
        r.returned("intake")
        (r.repo / "stats.py").write_text("changed\n", encoding="utf-8")
        out = r.returned("diagnose_accept", reply=empty_reply())
        self.assertFalse(out["ok"], out)


SPEC = {"requirements": [{"key": "R1", "text": "mean は要素の数で割る"}],
        "acceptance": [{"key": "A1", "requirement": "R1", "file": "test_spec_mean.txt", "name": "test_mean_divides_by_count",
                        "run": "grep -q test_mean_divides_by_count test_spec_mean.txt"}],
        "out_of_scope": []}
SPEC_TEST_FILE = "test_mean_divides_by_count\n# Given 1, 2, 3 の並び\n# When mean を呼ぶ\n# Then 2 を返す\n"


REVIEW = {"faces": [], "faces_none": "要件と受け入れ条件の抜け・曖昧さ・範囲の外を見たが無かった",
          "reason": "要件 R1 は受け入れ条件 A1 が試し、範囲の外の物は無い"}


def spec_run(case: unittest.TestCase) -> Run:
    """仕様の段を選んだ run で、仕様を書き・審査し、関所に見せる所まで"""
    r = Run(case)
    record = json.loads((r.artifacts / "entry" / "start.json").read_text(encoding="utf-8"))
    record["input"]["spec"] = True
    (r.artifacts / "entry" / "start.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    case.assertTrue(r.returned("intake")["spec"])
    (r.repo / "test_spec_mean.txt").write_text(SPEC_TEST_FILE, encoding="utf-8")
    case.assertTrue(r.returned("spec_accept", role="write", reply=SPEC)["ok"])
    review = r.returned("spec_accept", role="review", reply=REVIEW)
    case.assertEqual((review["ok"], review["revise"]), (True, False), review)
    case.assertTrue(r.returned("spec_ask")["ask"])
    return r


class SpecFreezeTest(unittest.TestCase):
    spec_run = spec_run

    def test_stop_word_is_a_human_stop(self):
        r = self.spec_run()
        out = r.returned("spec_freeze", answer={"decision": "stop", "text": "要らない"})
        self.assertFalse(out["go"])
        self.assertEqual(r.returned("verdict")["stop_reason"], "human:spec-gate")

    def test_request_flag_is_a_request_stop(self):
        r = self.spec_run()
        out = r.returned("spec_freeze", answer={"decision": "reject", "text": "request: 札"})
        self.assertFalse(out["go"])
        self.assertEqual(r.returned("verdict")["stop_reason"], "request:spec-gate")

    def test_approval_freezes_hashes_and_exit_codes(self):
        r = self.spec_run()
        out = r.returned("spec_freeze", answer={"decision": "approve", "text": ""})
        self.assertTrue(out["go"], out)
        spec = json.loads((r.judge / "spec.json").read_text(encoding="utf-8"))
        row = spec["acceptance"][0]
        self.assertRegex(row["sha256"], "^[0-9a-f]{64}$")
        self.assertEqual(row["exit_at_approval"], 0)


class StopPathTest(StopPathFilesMixin, unittest.TestCase):
    def test_bad_request_stops_before_any_role_and_still_fills_pointers(self):
        r = Run(self, request=[{"where": "stats.py"}])
        out = r.returned("intake")
        self.assertFalse(out["go"])
        returned = r.returned("verdict")
        self.assertFalse(returned["ready"])
        self.assertEqual(returned["stop_reason"], "works:request")
        self.assert_pointers_filled(r, returned)

    def test_gave_up_judgment_still_fills_pointers(self):
        r = Run(self)
        r.returned("intake")
        for _ in range(3):
            r.returned("diagnose_accept", reply=empty_reply(units=[{"key": KEY, "label": "bogus"}]))
        returned = r.returned("verdict")
        self.assertEqual((returned["ready"], returned["stop_reason"]), (False, "works:judge"))
        self.assert_pointers_filled(r, returned)

    def test_spec_stop_still_fills_pointers(self):
        r = spec_run(self)
        r.returned("spec_freeze", answer={"decision": "stop", "text": ""})
        returned = r.returned("verdict")
        self.assertEqual(returned["stop_reason"], "human:spec-gate")
        self.assert_pointers_filled(r, returned)

    def test_no_open_units_is_not_a_stop(self):
        r = Run(self)
        r.returned("intake")
        premises_and_purpose(r)
        r.returned("diagnose_accept", reply=empty_reply())
        returned = r.returned("verdict")
        self.assertEqual((returned["ready"], returned["stop_reason"], returned["units"]), (False, "", []))
        self.assert_pointers_filled(r, returned)


class RejudgeTest(unittest.TestCase):
    OBJECTION = "単位 1 は clamp の欠陥と同じ根で、分けると二度直す"

    def test_rejudge_without_a_first_judgment_stops(self):
        r = Run(self)
        out = r.returned("intake", objection=self.OBJECTION)
        self.assertEqual((out["go"], out["mode"]), (True, "rejudge"))
        prep = r.returned("rejudge_prep", objection=self.OBJECTION)
        self.assertFalse(prep["go"])
        returned = r.returned("verdict", objection=self.OBJECTION)
        self.assertEqual(returned["stop_reason"], "works:rejudge-session")

    def test_rejudge_with_a_first_judgment_writes_its_brief(self):
        r = Run(self)
        r.returned("intake")
        r.returned("diagnose_accept", reply=empty_reply())
        r.returned("verdict")
        prep = r.returned("rejudge_prep", objection=self.OBJECTION)
        self.assertTrue(prep["go"], prep)
        self.assertEqual(pathlib.Path(prep["brief_file"]), r.artifacts / "rejudge" / "brief.md")
        self.assertIn(self.OBJECTION, (r.artifacts / "rejudge" / "brief.md").read_text(encoding="utf-8"))


def premises_and_purpose(r: Run) -> None:
    """前提と目的の段が受け付けた控えを置く（判定の前の段が通った姿）"""
    (r.judge / "premises.json").write_text(json.dumps({"constraints": []}), encoding="utf-8")
    write_purpose(r)


HYGIENE = {"role": "hygiene", "materials": {"hygiene": {"status": "found", "count": 1, "detail": "1 件"}},
           "reply": {"findings": [{"where": "test_stats.py", "text": "使わない import が残る"}]}}
OUTSIDE = [{"source": "衛生", "where": "test_stats.py", "why_outside": "凍結した目的の外の衛生の所見"}]


class JudgedVerdictTest(StopPathFilesMixin, unittest.TestCase):
    def judged(self) -> Run:
        r = Run(self)
        r.returned("intake")
        premises_and_purpose(r)
        (r.judge / "material-hygiene.json").write_text(json.dumps(HYGIENE, ensure_ascii=False), encoding="utf-8")
        out = r.returned("diagnose_accept", reply=open_reply(out_of_purpose=OUTSIDE))
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        return r

    def test_open_unit_is_ready_with_its_out_of_purpose_rows(self):
        r = self.judged()
        out = r.returned("verdict")
        self.assertEqual((out["ready"], out["stop_reason"]), (True, ""), out)
        self.assertEqual([u["id"] for u in out["units"]], [KEY])
        self.assertEqual(out["units"][0]["paths"], ["stats.py"])
        self.assertEqual(out["units"][0]["summary"], open_reply()["units"][0]["reason"])
        self.assertIsNone(out["rejudge_verdict"])
        self.assertEqual(r.resolve(out["out_of_purpose"]), r.judge / "out-of-purpose.json")
        carried = json.loads((r.judge / "out-of-purpose.json").read_text(encoding="utf-8"))
        self.assertEqual(carried["rounds"]["1"][0]["found"][0]["from"], "p1.hygiene")
        self.assert_pointers_filled(r, out)

    def test_missing_premises_or_purpose_stops_even_with_an_accepted_judgment(self):
        """前提・目的の段が落ちた run（控えを書く前に終わる）は、受けた判定が在っても ready にしない"""
        for name, word in (("premises.json", "works:premises"), ("purpose.json", "works:purpose")):
            with self.subTest(missing=name):
                r = self.judged()
                (r.judge / name).unlink()
                out = r.returned("verdict")
                self.assertEqual((out["ready"], out["stop_reason"], out["units"]), (False, word, []), out)
                self.assert_pointers_filled(r, out)

    def test_purpose_prep_failure_writes_a_stop(self):
        r = Run(self)
        r.returned("intake")
        (r.judge / "premises.json").write_text(json.dumps({"constraints": []}), encoding="utf-8")
        (r.judge / "start.json").write_text("{broken", encoding="utf-8")
        self.assertFalse(r.returned("purpose_prep")["go"])
        self.assertEqual(json.loads((r.judge / "stop.json").read_text(encoding="utf-8"))["stop_reason"], "works:purpose")


class RejudgedVerdictTest(unittest.TestCase):
    OBJECTION = f"{KEY} は分母でなく呼び手の渡す並びの誤り"
    UNITS = [{"key": KEY, "label": "block", "reason": "異議を当たったが、呼び手の並びは正しく、分母の取り違えが残る"}]

    def test_rejudge_returns_its_own_units_and_keeps_the_first_judgment(self):
        r = Run(self)
        r.returned("intake")
        premises_and_purpose(r)
        self.assertTrue(r.returned("diagnose_accept", reply=open_reply())["ok"])
        self.assertTrue(r.returned("verdict")["ready"])
        first = (r.judge / "judgment.json").read_bytes()
        self.assertTrue(r.returned("rejudge_prep", objection=self.OBJECTION)["go"])
        reply = {"verdict": "退ける", "new_facts": "test_stats.py の呼び手を読み、並び [1, 2, 3] を渡していることを確かめた",
                 "units": self.UNITS, "reason": "異議は呼び手の誤りと言うが、呼び手は正しい"}
        out = r.returned("rejudge_accept", reply=reply)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        returned = r.returned("verdict", objection=self.OBJECTION)
        verdict_shape(self, returned)
        self.assertEqual(r.resolve(returned["judgment"]), r.artifacts / "rejudge" / "judgment.json")
        self.assertEqual((returned["ready"], returned["stop_reason"], returned["rejudge_verdict"]), (True, "", "退ける"), returned)
        self.assertEqual([(u["id"], u["summary"]) for u in returned["units"]], [(KEY, self.UNITS[0]["reason"])])
        self.assertEqual((r.judge / "judgment.json").read_bytes(), first, "再審は 1 回目の判定を上書きしない")
        self.assertEqual(json.loads((r.artifacts / "rejudge" / "premises.json").read_text(encoding="utf-8")),
                         json.loads((r.judge / "premises.json").read_text(encoding="utf-8")))


class MaterialGiveUpTest(unittest.TestCase):
    def test_diagnose_prep_builds_the_brief_from_the_remaining_materials(self):
        """素材の 1 本の受け付けが諦めても、支度は残りの素材のファイルで材料を組む（諦めた素材が在るので判定役は起こさない）"""
        r = Run(self)
        r.returned("intake")
        write_purpose(r)
        r.returned("material_route")
        for _ in range(3):
            out = r.returned("material_accept", role="provenance", reply={"not": "a provenance reply"})
            self.assertFalse(out["ok"])
        self.assertTrue(out["done"])
        prep = r.returned("diagnose_prep")
        self.assertFalse(prep["go"])
        self.assertTrue((r.judge / "diagnose-brief.md").is_file())
        self.assertEqual(r.returned("verdict")["stop_reason"], "works:material")


class VerdictNeverFailsTest(unittest.TestCase):
    """返す節は落ちない: 壊れた入力でも終了の値 0 で、output_format に合う ready: false と訳を返す（線は落ちた返す節の先へ進めない）"""

    def test_broken_inputs(self):
        cases = {
            "start が JSON でない": dict(start="{not json"),
            "指し札の先が無い": dict(start=json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": "nowhere/start.json"})),
            "judge が空": {},
        }
        for what, kw in cases.items():
            with self.subTest(case=what):
                r = Run(self)
                (r.artifacts / "judge").mkdir(exist_ok=True)
                out = r.returned("verdict", **kw)
                verdict_shape(self, out)
                self.assertFalse(out["ready"])
                self.assertTrue(out["stop_reason"])

    def test_broken_judgment_file(self):
        r = Run(self)
        r.returned("intake")
        (r.judge / "judgment.json").write_text("{broken", encoding="utf-8")
        out = r.returned("verdict")
        verdict_shape(self, out)
        self.assertFalse(out["ready"])
        self.assertTrue(out["stop_reason"])


if __name__ == "__main__":
    unittest.main()

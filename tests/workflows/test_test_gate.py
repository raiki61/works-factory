"""ブロック test-gate（workflows/test-gate/）の YAML の形と、script を子のプロセスで走らせる振る舞いと、筋書きを Archon で回す試験。

- YAML: 工程の名・入力・返す節・返す節の output_format（docs/design.md の「test-gate の返り」の欄ちょうど）・任せ先の CI の役の節の形
  （今の works の blk-ci.yaml の値）・輪の上限と受け付けの諦める回数・script の INPUTS_<名> と with: の鍵・読むだけの節
- script（今の works の test_blk_tests_delta.py の TestTestsModes・test_blk_ci.py の ScriptCase と同じ形。Archon が渡す環境
  INPUTS_*・ARTIFACTS_DIR・WORKFLOW_ID を与え、tests/e2e/target-seed/ の写しを対象にする）: 止められた run・JUnit の報告の後始末・
  任せ先の受け付けの拒みと諦め・返す節の赤の原因と認証・壊れた入力でも落ちない返す節
- 筋書き: tests/archon.py の使い捨ての木で `archon workflow test` を fixtures/ の全部に走らせる（Archon の源が無ければ見送る）
"""
import json
import os
import pathlib
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest

import yaml

from tests import archon
from tests.bin.gitkit import committed_copy, git

ROOT = pathlib.Path(__file__).resolve().parents[2]
BLOCK = ROOT / "workflows" / "test-gate"
SCRIPTS = BLOCK / "scripts"
SEED = ROOT / "tests" / "e2e" / "target-seed"
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))

import baseline_red  # noqa: E402
import declared_checks  # noqa: E402
import green_cert  # noqa: E402
import rolekit  # noqa: E402
from engine.schema import validate_schema  # noqa: E402  （declared_checks が lib/graphloops を sys.path に足す）

DEADLINE = 1728000000
RUN_ID = "run-1"
PY = sys.executable
RESULT_FIELDS = ["mode", "ok", "green", "red_cause", "baseline", "fingerprint", "evidence"]
RED_CAUSES = ["introduced", "inherited", "environment", "interaction", "incomplete", ""]
WAIT = 30   # 子のプロセスを待つ上限（秒）。試験の枠で、script の中には期限を置かない


def workflow() -> dict:
    return yaml.safe_load((BLOCK / "works-factory-test-gate.yaml").read_text(encoding="utf-8"))


def walk(nodes):
    for n in nodes:
        yield n
        yield from walk((n.get("loop_group") or {}).get("nodes") or [])


def node(nid: str) -> dict:
    return next(n for n in walk(workflow()["nodes"]) if n["id"] == nid)


def script_inputs(name: str) -> set:
    return set(re.findall(r"INPUTS_[A-Z_]+", (SCRIPTS / f"{name}.py").read_text(encoding="utf-8")))


def schema_problems(value, schema) -> list:
    """返す節の output_format に照らした違い。engine.schema の型検査は anyOf を読まないので、欄の anyOf だけここで分ける"""
    if not isinstance(value, dict):
        return [f"object でない: {value!r}"]
    probs = [f"欄 {k} が無い" for k in schema["required"] if k not in value]
    probs += [f"知らない欄 {k}" for k in value if k not in schema["properties"]]
    for k, sub in schema["properties"].items():
        if k not in value:
            continue
        branches = sub.get("anyOf") or [sub]
        if all(validate_schema(value[k], b, f"$.{k}") for b in branches):
            probs.append(f"欄 {k} が形に合わない: {value[k]!r}")
    return probs


class YamlCase(unittest.TestCase):
    def setUp(self):
        self.y = workflow()

    def test_name_inputs_and_return(self):
        self.assertEqual(self.y["name"], "works-factory-test-gate")
        self.assertEqual(set(self.y["inputs"]), {"mode", "start", "baseline"})
        self.assertTrue(self.y["inputs"]["mode"]["required"])
        self.assertTrue(self.y["inputs"]["start"]["required"])
        self.assertEqual(self.y["inputs"]["baseline"]["default"], "")
        self.assertEqual((self.y["returns"], self.y["outcome_field"]), ("result", "ok"))

    def test_result_output_format_is_the_contract(self):
        result = node("result")
        fmt = result["output_format"]
        self.assertEqual(sorted(fmt["properties"]), sorted(RESULT_FIELDS))
        self.assertEqual(sorted(fmt["required"]), sorted(RESULT_FIELDS))
        self.assertIs(fmt["additionalProperties"], False)
        self.assertEqual(fmt["properties"]["mode"]["enum"], ["base", "final"])
        self.assertEqual(fmt["properties"]["red_cause"]["enum"], RED_CAUSES)
        self.assertEqual(fmt["properties"]["ok"]["type"], "boolean")
        self.assertEqual(result["output_type"], "green-cert")
        self.assertEqual((result["trigger_rule"], result["depends_on"]), ("all_done", ["run", "ci-loop"]))
        self.assertEqual(set(result["with"]), {"mode", "start", "baseline"})
        self.assertTrue(all(v.startswith("$INPUTS.") for v in result["with"].values()),
                        "落ちうる節の返り（$run.output など）を束ねない")

    def test_role_node_reads_only(self):
        ci = node("ci")
        self.assertIs(ci["mutates_checkout"], False)
        self.assertEqual(ci["allowed_tools"], ["Read", "Grep", "Glob", "Bash", "WebSearch", "WebFetch"])
        self.assertFalse({"Edit", "Write"} & set(ci["allowed_tools"]))
        self.assertEqual((ci["model"], ci["effort"]), ("sonnet", "medium"))   # 今の works の stage-models.json の blk-ci/ci（light）
        self.assertEqual(ci["command"], "ci")
        self.assertTrue((BLOCK / "commands" / "ci.md").is_file())

    def test_role_node_matches_works_blk_ci(self):
        """今の works の blk-ci.yaml の役の節の settingSources・sandbox・context と同じ値"""
        ci = node("ci")
        self.assertEqual(ci["settingSources"], ["user"])
        self.assertEqual(ci["context"], "fresh")
        self.assertEqual(ci["sandbox"], {"enabled": True, "allowUnsandboxedCommands": False, "failIfUnavailable": True,
                                         "enableWeakerNetworkIsolation": True,
                                         "network": {"allowedDomains": ["*"], "allowLocalBinding": True},
                                         "filesystem": {"allowWrite": ["/"]}})
        self.assertEqual(ci["output_format"]["properties"]["material"], declared_checks.MATERIAL_SCHEMA)

    def test_loop_matches_give_up(self):
        loop = node("ci-loop")
        self.assertEqual(loop["when"], "$run.output.by == 'role_needed'")
        self.assertIs(loop["loop_group"]["fresh_context"], True)
        self.assertIn("$ci-accept.output.done", loop["loop_group"]["until_bash"])
        self.assertEqual(loop["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER)

    def test_prep_takes_previous_reject(self):
        self.assertEqual(node("ci-prep")["with"]["reject"], "$LOOP_PREV.ci-accept.output.reason")

    def test_script_inputs_match_with(self):
        for n in walk(self.y["nodes"]):
            if "script" not in n:
                continue
            with self.subTest(n["id"]):
                self.assertEqual(script_inputs(n["script"]), {f"INPUTS_{k.upper()}" for k in n["with"]})
                self.assertEqual((n["runtime"], n["timeout"]), ("uv", DEADLINE))

    def test_readonly_nodes(self):
        for nid in ("ci-prep", "ci", "ci-accept", "result"):
            with self.subTest(nid):
                self.assertIs(node(nid)["mutates_checkout"], False)

    def test_scripts_write_nothing_outward(self):
        for path in sorted(SCRIPTS.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path.name):
                for word in (r"\bgh\b", r"git\W+push", r"git\W+merge"):
                    self.assertIsNone(re.search(word, text), word)


class ScriptCase(unittest.TestCase):
    """script を子のプロセスで走らせる。対象は種の写し self.repo、run の置き場は self.artifacts"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        self.head = committed_copy(self.repo, SEED)
        self.artifacts = self.tmp / "artifacts"
        self.write_start()

    def write_start(self, **over):
        rec = {"base_rev": self.head, "test_cmd": "", "tdd_suite": "", **over}
        path = self.artifacts / "start" / "record.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec), encoding="utf-8")
        self.start = json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": "start/record.json"})

    def env(self, inputs: dict) -> dict:
        return {**os.environ, "WORKFLOW_ID": RUN_ID, "ARTIFACTS_DIR": str(self.artifacts), "WORKS_FACTORY_ROOT": str(ROOT),
                "PYTHONDONTWRITEBYTECODE": "1", **{f"INPUTS_{k.upper()}": v for k, v in inputs.items()}}

    def script(self, name: str, **inputs) -> tuple:
        """(終了コード, 返りの dict か None, 標準エラー)。返りは JSON 1 行だけ"""
        done = subprocess.run([PY, str(SCRIPTS / f"{name}.py")], cwd=self.repo, env=self.env(inputs), capture_output=True,
                              text=True, encoding="utf-8", timeout=WAIT * 4)
        if done.returncode:
            self.assertEqual(done.stdout, "")
            return done.returncode, None, done.stderr
        self.assertEqual(done.stdout.count("\n"), 1, done.stdout)
        return 0, json.loads(done.stdout), done.stderr

    def ok(self, name: str, **inputs) -> dict:
        rc, out, err = self.script(name, **inputs)
        self.assertEqual(rc, 0, err)
        return out

    def decl(self, steps, commit=True):
        (self.repo / declared_checks.DECL_NAME).write_text(json.dumps({"suite": steps}), encoding="utf-8")
        if commit:
            git(self.repo, "add", "-A")
            git(self.repo, "commit", "-qm", "decl")
            self.head = git(self.repo, "rev-parse", "HEAD")
            self.write_start()

    def pointed(self, ptr: dict) -> pathlib.Path:
        self.assertEqual((ptr["type"], ptr["run_id"]), ("archon_artifact", RUN_ID))
        return self.artifacts / ptr["path"]


class RunScriptCase(ScriptCase):
    def test_stopped_run_exits_without_output(self):
        """元 test_blk_tests_delta.py の test_stopped_run_exits_without_output: 止められたら孫まで木ごと止め、返りを出さずに 128+信号"""
        pidfile = self.tmp / "grandchild.pid"
        body = ("import subprocess, sys, time; p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']); "
                f"open({str(pidfile)!r}, 'w').write(str(p.pid)); time.sleep(120)")
        self.decl([{"name": "suite", "argv": [PY, "-c", body]}])
        proc = subprocess.Popen([PY, str(SCRIPTS / "run.py")], cwd=self.repo, env=self.env({"mode": "final", "start": self.start}),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        end = time.monotonic() + WAIT
        while not (pidfile.is_file() and pidfile.read_text()) and time.monotonic() < end:
            time.sleep(0.1)
        grandchild = int(pidfile.read_text())
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=WAIT)
        self.assertEqual((proc.returncode, out), (128 + signal.SIGTERM, ""), err)
        self.assertIn("止められた", err)
        end = time.monotonic() + WAIT
        while time.monotonic() < end:
            try:
                os.kill(grandchild, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            os.kill(grandchild, signal.SIGKILL)
            self.fail("孫が止まっていない")

    def test_run_leaves_no_new_junit_report_in_the_tree(self):
        """走らせる前に無かった JUnit の報告は対象の木に残らず run の置き場に写り、作業ツリーの指紋が走らせたことでは変わらない"""
        report = "<testsuite><testcase classname='m' name='a'/></testsuite>"
        body = f"import os; os.makedirs('out', exist_ok=True); open('out/r.xml', 'w').write({report!r})"
        self.decl([{"name": "suite", "argv": [PY, "-c", body], "junit": "out/r.xml"}])
        before = green_cert.fingerprint(self.repo)
        out = self.ok("run", mode="base", start=self.start)
        self.assertFalse((self.repo / "out" / "r.xml").exists())
        self.assertEqual((self.artifacts / "test-gate" / "base" / "junit" / "suite.xml").read_text(encoding="utf-8"), report)
        self.assertEqual((out["fingerprint_before"], out["fingerprint_after"]), (before, before))
        self.assertEqual(green_cert.fingerprint(self.repo), before)
        self.assertEqual((out["by"], out["material"]["status"], out["junit_steps"]), ("engine", "clean", ["suite"]))
        self.assertEqual(sorted(out), sorted(node("run")["output_format"]["required"]))

    def test_scope_declaration_without_review_declaration_stops(self):
        """範囲の宣言だけが在れば走らせずに 1 で止め、理由を標準エラーに出す"""
        (self.repo / ".works-checks.json").write_text('{"far": {"paths_ignore": ["works/"]}}', encoding="utf-8")
        rc, out, err = self.script("run", mode="base", start=self.start)
        self.assertEqual((rc, out), (1, None))
        self.assertIn(".works-checks.json", err)


class CiRoleCase(ScriptCase):
    """任せ先の CI の役の支度と受け付け（元 test_blk_ci.py の ScriptCase）"""
    GOOD = json.dumps({"material": {"status": "found", "count": 1, "detail": "1 件落ちた"}})
    BAD = json.dumps({"material": {"status": "not_run", "reason": "走らせなかった"}})   # base では awaiting_human を求める

    def prep(self, reject=""):
        out = self.ok("ci_prep", mode="base", start=self.start, reject=reject)
        top = pathlib.Path(out["copy_dir"]).parent
        self.addCleanup(lambda: top.exists() and __import__("shutil").rmtree(top, ignore_errors=True))
        return out

    def test_prep_copies_tree_and_passes_reject(self):
        (self.repo / "new.txt").write_text("未追跡\n", encoding="utf-8")
        out = self.prep(reject="前の理由")
        self.assertEqual((out["mode"], out["reject"], out["attempt"], out["root"]), ("base", "前の理由", 1, str(self.repo.resolve())))
        self.assertEqual((pathlib.Path(out["copy_dir"]) / "new.txt").read_text(encoding="utf-8"), "未追跡\n")
        self.assertTrue(pathlib.Path(out["tmp_dir"]).is_dir())

    def test_gives_up_after_three_rejections(self):
        """元 test_gives_up_after_three_rejections: 3 回目の拒否で done・give_up（輪を max_iterations で落とさない）。写しを消す"""
        rounds = []
        for _ in range(3):
            p = self.prep()
            rounds.append((p["attempt"], self.ok("ci_accept", mode="base", reply=self.BAD)))
        self.assertEqual([a for a, _ in rounds], [1, 2, 3])
        self.assertEqual([(r["ok"], r["done"], r["give_up"]) for _, r in rounds],
                         [(False, False, False), (False, False, False), (False, True, True)])
        self.assertIn("awaiting_human", rounds[-1][1]["reason"])
        self.assertFalse(pathlib.Path(p["copy_dir"]).exists())
        self.assertFalse((self.artifacts / "test-gate" / "base" / "ci-material.json").exists())

    def test_tree_change_rejected(self):
        """元 test_tree_change_rejected: 役を起こした後に未追跡のファイル・git が無視するパスが増えたら拒む。元に戻せば通る"""
        (self.repo / ".git" / "info" / "exclude").write_text("build/\n", encoding="utf-8")
        self.prep()

        def untracked():
            (self.repo / "new.txt").write_text("x\n", encoding="utf-8")
            return lambda: (self.repo / "new.txt").unlink()

        def ignored():
            (self.repo / "build").mkdir()
            (self.repo / "build" / "out.o").write_text("x\n", encoding="utf-8")
            return lambda: __import__("shutil").rmtree(self.repo / "build")

        for change, word in ((untracked, "new.txt"), (ignored, "build/")):
            with self.subTest(word):
                undo = change()
                got = self.ok("ci_accept", mode="base", reply=self.GOOD)
                self.assertEqual((got["ok"], got["done"]), (False, False))
                self.assertIn("作業ツリーを変えた", got["reason"])
                self.assertIn(word, got["reason"])
                undo()
        got = self.ok("ci_accept", mode="base", reply=self.GOOD)
        self.assertEqual((got["ok"], got["done"], got["give_up"]), (True, True, False))
        saved = json.loads((self.artifacts / "test-gate" / "base" / "ci-material.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, json.loads(self.GOOD))

    def test_branch_switch_rejected(self):
        """元 test_branch_switch_rejected"""
        self.prep()
        git(self.repo, "checkout", "-q", "--detach", "HEAD")
        got = self.ok("ci_accept", mode="base", reply=self.GOOD)
        self.assertFalse(got["ok"])
        self.assertIn("ref", got["reason"])


class ResultScriptCase(ScriptCase):
    """返す節: 赤の原因と認証と、落ちないこと"""
    # 段は報告 out/r.xml に m.a（通る）と m.b（落ちる）を書く。対象の木に broken.flag が在れば m.c（落ちる）も書く。fixed.flag が
    # 在れば m.b も通る
    STEP_BODY = ("import os, sys; os.makedirs('out', exist_ok=True); b = 'passed' if os.path.exists('fixed.flag') else 'failure'; "
                 "c = os.path.exists('broken.flag'); "
                 "rows = ['<testcase classname=\"m\" name=\"a\"/>'] + "
                 "(['<testcase classname=\"m\" name=\"b\"><failure/></testcase>'] if b == 'failure' else ['<testcase classname=\"m\" name=\"b\"/>']) + "
                 "(['<testcase classname=\"m\" name=\"c\"><failure/></testcase>'] if c else []); "
                 "open('out/r.xml', 'w').write('<testsuite>' + ''.join(rows) + '</testsuite>'); "
                 "sys.exit(1 if b == 'failure' or c else 0)")

    def setUp(self):
        super().setUp()
        self.output_format = node("result")["output_format"]

    def result(self, mode, **inputs) -> dict:
        out = self.ok("result", mode=mode, **{"start": self.start, "baseline": "", **inputs})
        self.assertEqual(schema_problems(out, self.output_format), [], out)
        self.assertTrue(self.pointed(out["evidence"]).is_file())
        return out

    def base(self) -> str:
        self.decl([{"name": "suite", "argv": [PY, "-c", self.STEP_BODY], "junit": "out/r.xml"}])
        self.ok("run", mode="base", start=self.start)
        out = self.result("base")
        self.assertEqual((out["mode"], out["ok"], out["green"], out["fingerprint"]), ("base", True, False, None))
        doc = baseline_red.read_baseline(self.pointed(out["baseline"]))
        self.assertEqual((doc["rev"], doc["exit"], doc["junit_steps"], doc["exit_codes"]), (self.head, 1, ["suite"], {"suite": 1}))
        self.assertEqual(baseline_red.outcomes(doc["cases"]), {"m::a": "passed", "m::b": "failure"})
        return json.dumps(out["baseline"])

    def final(self, baseline: str) -> dict:
        self.ok("run", mode="final", start=self.start)
        return self.result("final", baseline=baseline)

    def test_final_inherited_red_is_not_certified(self):
        out = self.final(self.base())
        self.assertEqual((out["ok"], out["green"], out["red_cause"]), (False, False, "inherited"))
        self.assertIn("inherited", self.pointed(out["evidence"]).read_text(encoding="utf-8"))
        self.assertEqual(out["fingerprint"], green_cert.fingerprint(self.repo))

    def test_final_introduced_red_is_not_certified(self):
        baseline = self.base()
        (self.repo / "broken.flag").write_text("x\n", encoding="utf-8")
        out = self.final(baseline)
        self.assertEqual((out["ok"], out["red_cause"]), (False, "introduced"))
        self.assertIn("m::c", self.pointed(out["evidence"]).read_text(encoding="utf-8"))

    def test_final_green_is_certified_with_fingerprint_and_tree_change_voids_it(self):
        baseline = self.base()
        (self.repo / "fixed.flag").write_text("x\n", encoding="utf-8")
        self.ok("run", mode="final", start=self.start)
        out = self.result("final", baseline=baseline)
        self.assertEqual((out["ok"], out["green"], out["red_cause"]), (True, True, ""))
        self.assertTrue(green_cert.matches(out["fingerprint"], self.repo))
        (self.repo / "later.txt").write_text("x\n", encoding="utf-8")
        out = self.result("final", baseline=baseline)
        self.assertEqual((out["ok"], out["green"]), (False, True))
        self.assertIn("指紋が before と違う", self.pointed(out["evidence"]).read_text(encoding="utf-8"))

    def test_tdd_suite_cases_go_into_the_baseline(self):
        """始めの記録の tdd_suite は一式を 1 回走らせ、その 1 件ごとの結末と終了コードを元の結末に置く（suite は実行ファイルのパス）"""
        suite = self.tmp / "suite.py"
        suite.write_text("import sys\nopen(sys.argv[1], 'w').write(\"<testsuite><testcase classname='s' name='x'>"
                         "<failure/></testcase></testsuite>\")\nsys.exit(1)\n", encoding="utf-8")
        self.write_start(tdd_suite=str(suite), test_cmd="true")
        self.ok("run", mode="base", start=self.start)
        out = self.result("base")
        doc = baseline_red.read_baseline(self.pointed(out["baseline"]))
        self.assertEqual((doc["suite"], doc["test_cmd"], doc["exit"]), (str(suite), "true", 1))
        self.assertEqual(baseline_red.outcomes(doc["cases"]), {"s::x": "failure"})

    def test_base_that_cannot_run_is_not_ok(self):
        """宣言も test_cmd も無い base: 任せ先の役が走らせられず awaiting_human を返した・素材を渡さなかった、どちらも緑を仮定しない"""
        self.assertEqual(self.ok("run", mode="base", start=self.start)["by"], "role_needed")
        out = self.result("base")
        self.assertEqual((out["ok"], out["green"], out["red_cause"]), (False, False, "incomplete"))
        gate = self.artifacts / "test-gate" / "base"
        (gate / "ci-material.json").write_text(json.dumps({"material": {"status": "awaiting_human", "reason": "実機が要る"}}),
                                               encoding="utf-8")
        out = self.result("base")
        self.assertEqual((out["ok"], out["green"], out["red_cause"]), (False, False, "incomplete"))

    def test_final_not_run_is_incomplete(self):
        self.ok("run", mode="final", start=self.start)
        gate = self.artifacts / "test-gate" / "final"
        (gate / "ci-material.json").write_text(json.dumps({"material": {"status": "not_run", "reason": "依存が入らない"}}),
                                               encoding="utf-8")
        out = self.result("final")
        self.assertEqual((out["ok"], out["red_cause"]), (False, "incomplete"))

    def test_broken_inputs_return_incomplete_without_failing(self):
        """返す節は落ちない: 壊れた入力でも終了の値 0 で、output_format に合う ok: false・red_cause: incomplete を 1 つ出す"""
        self.decl([{"name": "suite", "argv": [PY, "-c", "print('ok')"]}])
        self.ok("run", mode="final", start=self.start)
        broken = self.artifacts / "broken.json"
        broken.write_text('{"suite": ""}', encoding="utf-8")
        other_run = json.dumps({"type": "archon_artifact", "run_id": "other-run", "path": "start/record.json"})
        cases = {
            "INPUTS_START が JSON でない": {"start": "{"},
            "ほかの run の指し札": {"start": other_run},
            "INPUTS_BASELINE の先が無い": {"baseline": json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": "nope.json"})},
            "壊れた元の結末のファイル": {"baseline": json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": "broken.json"})},
            "形が違う": {"mode": "middle"},
        }
        for why, inputs in cases.items():
            with self.subTest(why):
                mode = inputs.pop("mode", "final")
                out = self.result(mode, **inputs)
                self.assertEqual((out["ok"], out["green"], out["red_cause"], out["baseline"], out["fingerprint"]),
                                 (False, False, "incomplete", None, None))
        (self.artifacts / "test-gate" / "final" / "run.json").unlink()
        out = self.result("final")
        self.assertEqual((out["ok"], out["red_cause"]), (False, "incomplete"))
        self.assertIn("run.json", self.pointed(out["evidence"]).read_text(encoding="utf-8"))


class FixtureCase(unittest.TestCase):
    """筋書き（fixtures/）を止めた Archon の `workflow test` で回す。base と final の形が 1 つの返す節で返る"""
    AUTHORED = {"base-engine": "succeeded", "base-role": "failed", "final-green": "succeeded", "final-red": "failed"}

    def test_fixtures_pass_in_archon(self):
        with archon.tree(["test-gate"]) as tree:
            done = archon.archon(tree, "workflow", "test", "works-factory-test-gate", "--json", "--cwd", str(tree))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        got = json.loads(done.stdout)
        self.assertEqual((got["failed"], got["errors"]), (0, []))
        authored = {pathlib.Path(r["fixture"]).name.removesuffix(".stubs.yaml"): r["authoredOutcome"] for r in got["results"]}
        self.assertEqual(authored, self.AUTHORED)
        self.assertTrue(all(r["pass"] for r in got["results"]))


if __name__ == "__main__":
    unittest.main()

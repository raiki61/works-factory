"""試験の関門の block（workflows/test-gate/）の YAML の形と、script を子のプロセスで走らせる振る舞いの試験（docs/design/test-gate.md の 12 節）。

- YAML: block の名・入力（port 12 個）・返す node の output_format（今の 15 欄に suite・suite_note・related・report を足した 18 欄）・
  TDD の実行器の書き手の node の形・script の INPUTS_<名> と with: の鍵（INPUTS_ を読むのは intake.py だけ）・読むだけの node
- script（始めの記録の無い使い捨ての run directory と、tests/e2e/target-seed/ の写しの git のリポジトリで、port の値だけを渡す）:
  止められた run・JUnit の報告の後始末・返す node の赤の原因と認証・壊れた入力でも落ちない返す node・TDD の実行器の輪・
  走らせ方が決まらない道の関わる試験だけの走らせ方（RelatedCase）・出力の欄 suite・suite_note・related・report
- 筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py
"""
import datetime
import hashlib
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import yaml

from bin._lib import isolate, launcher
from tests.bin import hermetic
from tests.bin.gitkit import committed_copy, git
from tests.blocks import kit
from tests.layers import scan

ROOT = pathlib.Path(__file__).resolve().parents[3]
BLOCK = kit.BLOCKS / "test-gate"
SCRIPTS = BLOCK / "scripts"
SEED = ROOT / "tests" / "e2e" / "target-seed"
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))

import baseline_red  # noqa: E402
import declared_checks  # noqa: E402
import gatemarks  # noqa: E402
import green_cert  # noqa: E402
import launchgroups  # noqa: E402
import suitewrite  # noqa: E402
import tree_run  # noqa: E402
import userenv  # noqa: E402
from engine.schema import validate_schema  # noqa: E402  （declared_checks が lib/graphloops を sys.path に足す）

RUN_ID = "run-1"
PY = sys.executable
WAIT = 30   # 子のプロセスを待つ上限（秒）。試験の枠で、script の中には期限を置かない
PORTS = ("mode", "test_cmd", "tdd_suite", "base", "entry_base", "request", "request_scope", "baseline", "reuse_dir", "reuse_key", "user_env_dir", "lang")


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
    """返す node の output_format に照らした違い。engine.schema の型検査は anyOf を読まないので、欄の anyOf だけここで分ける"""
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
        self.assertEqual(set(self.y["inputs"]), set(PORTS))
        self.assertTrue(self.y["inputs"]["mode"]["required"])
        self.assertEqual({k for k, v in self.y["inputs"].items() if "default" in v}, set(PORTS) - {"mode"})
        self.assertEqual({k: v["default"] for k, v in self.y["inputs"].items() if "default" in v and k != "request_scope" and k != "request"},
                         {k: "" for k in set(PORTS) - {"mode", "request", "request_scope"}})
        self.assertEqual((self.y["inputs"]["request"]["default"], self.y["inputs"]["request_scope"]["default"]), ("[]", "false"))
        self.assertEqual((self.y["returns"], self.y["outcome_field"]), ("result", "ok"))
        self.assertEqual([n["id"] for n in walk(self.y["nodes"])],
                         ["intake", "run", "suite-loop", "suite-prep", "suite-write", "suite-place", "suite-try", "result"])

    def test_intake_gates_the_run(self):
        self.assertEqual((node("run")["depends_on"], node("run")["when"]), (["intake"], "$intake.output.ok == true"))
        self.assertEqual(sorted(node("intake")["output_format"]["required"]), ["ok", "reason"])

    def test_result_output_format_is_the_contract(self):
        result = node("result")
        fmt = result["output_format"]
        self.assertEqual(sorted(fmt["required"]), sorted(set(fmt["properties"]) - {"optional"}))
        self.assertEqual(len(fmt["required"]), 18)
        self.assertTrue({"suite", "suite_note", "related", "report"} <= set(fmt["required"]))
        self.assertEqual(fmt["properties"]["report"], {"type": "array", "items": {"type": "string"}})
        self.assertIs(fmt["additionalProperties"], False)
        self.assertEqual(fmt["properties"]["mode"]["enum"], ["base", "final"])
        self.assertEqual(fmt["properties"]["red_cause"]["enum"], list(green_cert.RED_CAUSES))
        compared = next(b for b in fmt["properties"]["test_outcomes"]["anyOf"] if b["type"] == "object")
        for side in ("base", "final"):
            self.assertEqual(compared["properties"]["rows"]["items"]["properties"][side]["enum"], [*baseline_red.OUTCOMES, ""])
        self.assertEqual(fmt["properties"]["ok"]["type"], "boolean")
        self.assertEqual(result["output_type"], "green-cert")
        self.assertEqual((result["trigger_rule"], result["depends_on"]), ("all_done", ["run", "suite-loop"]))
        self.assertEqual(set(result["with"]), {"optional"})

    def test_runner_writer_is_a_read_only_role_and_its_fall_is_declared(self):
        """#516: TDD の実行器の書き手は読むだけの役の起こし方（軽い群・道具・砂場の 1 組）で起き、書き手と輪が落ちても線が先へ進める
        （返す node の宣言 optional。落ちれば実行器の無い run の道を通る）。役の砂場は run の作業ツリーを含む Archon の家ごと書き込みを塞ぎ
        （相対のパス '.' は cwd でなく設定の一時ファイルのフォルダに解かれ、作業ツリーを塞がない。実測 2026-10-13）、読むだけの node の印
        mutates_checkout: false も外さない"""
        writer = node("suite-write")
        self.assertEqual(writer["allowed_tools"], ["Read", "Grep", "Glob", "Bash", "WebSearch", "WebFetch"])
        self.assertFalse({"Edit", "Write"} & set(writer["allowed_tools"]))
        self.assertEqual(launchgroups.default_of(writer["model"]), ("sonnet", "medium"))
        self.assertEqual(writer["settingSources"], ["user"])
        self.assertNotIn("context", writer)
        self.assertEqual(writer["sandbox"], {"enabled": True, "allowUnsandboxedCommands": False, "failIfUnavailable": True,
                                             "enableWeakerNetworkIsolation": True,
                                             "network": {"allowedDomains": ["*"], "allowLocalBinding": True},
                                             "filesystem": {"allowWrite": ["/"], "denyWrite": [scan.NO_TREE_WRITE]}})
        self.assertIs(writer["mutates_checkout"], False)
        self.assertEqual((writer["idle_timeout"], writer["retry"]), (1728000000, {"max_attempts": 2, "on_error": "all"}))
        self.assertEqual((writer["prompt"], writer["when"]), ("$suite-prep.output.prompt", "$suite-prep.output.write == true"))
        self.assertTrue((BLOCK / "prompts" / "suite-write.md").is_file())
        self.assertEqual(json.loads(node("result")["with"]["optional"]),
                         [{"node": "suite-loop", "bare": False}, {"node": "suite-write", "bare": True}])

    def test_runner_loop_rewrites_only_after_a_kept_runner_fails(self):
        """#516: 輪は修正前のテストの後に、用意が要る時（run の返り suite_owed）だけ回る。2 周目は取り置きが照らしを通らなかった時の
        書き直しだけ。照らしの 1 回（suite-try）は書き手が飛んでも落ちても走る"""
        loop = node("suite-loop")
        self.assertEqual((loop["when"], loop["depends_on"]), ("$run.output.suite_owed == true", ["run"]))
        self.assertEqual(loop["loop_group"]["max_iterations"], 2)
        self.assertIn("$suite-try.output.done", loop["loop_group"]["until_bash"])
        self.assertEqual([n["id"] for n in loop["loop_group"]["nodes"]], ["suite-prep", "suite-write", "suite-place", "suite-try"])
        self.assertEqual(node("suite-try")["trigger_rule"], "all_done")
        self.assertNotIn("suite_owed", node("run")["output_format"]["required"])

    def test_run_material_is_the_material_schema_or_null(self):
        material = node("run")["output_format"]["properties"]["material"]
        self.assertEqual(material["type"], ["object", "null"])
        self.assertEqual({**material, "type": "object"}, declared_checks.MATERIAL_SCHEMA)

    def test_script_inputs_match_with(self):
        """INPUTS_ を読むのは intake.py だけ（port の 12 個）。ほかの script は with: に結んだ鍵だけを読む"""
        self.assertEqual(script_inputs("intake"), {f"INPUTS_{k.upper()}" for k in PORTS})
        for n in walk(self.y["nodes"]):
            if "script" not in n or n["script"] == "intake":
                continue
            with self.subTest(n["id"]):
                self.assertEqual(script_inputs(n["script"]), {f"INPUTS_{k.upper()}" for k in n.get("with") or {}})
        for n in walk(self.y["nodes"]):
            if "script" in n:
                self.assertEqual((n["runtime"], n.get("timeout")), ("uv", None))
            self.assertNotIn("$INPUTS", json.dumps(n.get("with") or {}), "port は intake だけが読む")

    def test_readonly_nodes(self):
        for nid in ("intake", "suite-prep", "suite-write", "suite-place", "suite-try", "result"):
            with self.subTest(nid):
                self.assertIs(node(nid)["mutates_checkout"], False)

    def test_scripts_write_nothing_outward(self):
        for path in sorted(SCRIPTS.glob("*.py")) + sorted((BLOCK / "src").glob("*.py")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path.name):
                for word in (r"\bgh\b", r"git\W+push", r"git\W+merge"):
                    self.assertIsNone(re.search(word, text), word)

    def test_file_names_match_lib(self):
        files = kit.load("test-gate", "files")
        self.assertEqual(files.RUN, declared_checks.RUN_FILE)
        self.assertEqual(files.MODES, declared_checks.MODES)


class EvidenceRowsCase(unittest.TestCase):
    """証拠の文の行の頭（走らせ方・ログ）の持ち主は src/certify.py の RUN_ROW・LOG_ROW だけ（持ち主の決め evidence-prefix-one-home）。
    試験と通しの照らしはここから引く"""
    # 同じ字の頭を持つ別の文（最後の承認ノードの文の行。ask_final.tests_lines）を照らす試験
    FINAL_GATE_TESTS = {"tests/workflows/test_gate_head.py", "tests/workflows/test_line.py"}

    def test_tests_draw_the_prefixes_from_certify(self):
        certify = kit.load("test-gate", "certify")
        for path in sorted((ROOT / "tests").rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            text = path.read_text(encoding="utf-8")
            prefixes = (certify.RUN_ROW,) if rel in self.FINAL_GATE_TESTS else (certify.RUN_ROW, certify.LOG_ROW)
            with self.subTest(rel):
                self.assertEqual([p for p in prefixes if p in text], [])

    def test_e2e_evidence_rows_start_with_the_prefixes(self):
        certify = kit.load("test-gate", "certify")
        rows = json.loads((ROOT / "tests" / "e2e" / "evidence.json").read_text(encoding="utf-8"))
        heads = [p.removeprefix("- ") for p in (certify.RUN_ROW, certify.LOG_ROW)]
        texts = [r["text"] for r in rows if str(r.get("where", "")).endswith("/evidence.md")
                 and str(r.get("where")).startswith(("parent/test-gate-base/", "parent/test-gate-final/")) and any(h in str(r.get("text")) for h in heads)]
        self.assertTrue(texts)
        for text in texts:
            with self.subTest(text):
                self.assertTrue(text.startswith((certify.RUN_ROW, certify.LOG_ROW)), text)


class ScriptCase(unittest.TestCase):
    """script を子のプロセスで走らせる。対象は種の写し self.repo、run の置き場は self.artifacts。形ごとの place は include の道
    test-gate-<mode>（line が include する時の道。ARCHON_NODE_EXECUTION の path）で分ける"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        self.head = committed_copy(self.repo, SEED)
        self.artifacts = self.tmp / "artifacts"
        self.artifacts.mkdir()
        self.declared = {}   # 包みの宣言（launcher.FENCE_RECORDS_ENV）。空なら起動の殻を通らない run
        self.user_home = None   # 在れば起動の殻の隔離を通った run（as_user）
        self.given = {}   # port の値（write_start が書き換える）
        self.fresh = set()   # port を読み直した（intake を回した）形

    def write_start(self, **over):
        """port の値を書き換える（次に script を回す形から intake を回し直す）"""
        self.given.update(over)
        self.fresh.clear()

    def place(self, mode: str) -> pathlib.Path:
        return self.artifacts / f"test-gate-{mode}"

    def port_env(self, mode: str) -> dict:
        ports = {"mode": mode, "reuse_dir": str(self.artifacts / "test-reuse"), "user_env_dir": str(self.artifacts), **self.given}
        return {f"INPUTS_{k.upper()}": str(v) for k, v in ports.items()}

    def env(self, mode: str, name: str, inputs: dict, with_ports: bool = False, include: bool = True) -> dict:
        execution = {"ARCHON_NODE_EXECUTION": json.dumps({"runId": RUN_ID, "path": f"test-gate-{mode}__{name}"})} if include else {}
        env = hermetic.child_env(**{**self.declared, "WORKFLOW_ID": RUN_ID, "ARTIFACTS_DIR": str(self.artifacts),
                                    **execution, "WORKS_FACTORY_ROOT": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1",
                                    **(self.port_env(mode) if with_ports else {}),
                                    **{f"INPUTS_{k.upper()}": v for k, v in inputs.items()}})
        if self.user_home is None:
            return env
        user = {k: v for k, v in env.items() if k not in userenv.NAMES}
        return isolate.isolate({**user, "HOME": str(self.user_home)}, self.tmp / "run-home")

    def as_user(self) -> pathlib.Path:
        """起動の殻の隔離を通った run にし、HOME の下の全体の設定（.config/homecfg/ok）が在る時だけ通る小さな道具を返す。
        利用者の HOME は self.tmp/user（XDG_* は無し）。道具は設定が無ければ config missing と出して 3 で抜ける"""
        self.user_home = self.tmp / "user"
        tool = self.tmp / "bin" / "homecfg"
        tool.parent.mkdir()
        tool.write_text('#!/bin/sh\n[ -f "${XDG_CONFIG_HOME:-$HOME/.config}/homecfg/ok" ] && exit 0\n'
                        'echo config missing >&2\nexit 3\n', encoding="utf-8")
        tool.chmod(0o755)
        return tool

    def script(self, name: str, mode: str = "base", **inputs) -> tuple:
        """(終了コード, 返りの dict か None, 標準エラー)。返りは JSON 1 行だけ。intake 以外は、その形の port をまだ読んでいなければ先に
        intake を回す（port の値は write_start で変える）"""
        if name != "intake" and mode not in self.fresh:
            self.intake(mode)
        return self.run_script(name, mode, inputs, with_ports=name == "intake")

    def run_script(self, name: str, mode: str, inputs: dict, with_ports: bool = False, include: bool = True) -> tuple:
        done = subprocess.run([PY, str(SCRIPTS / f"{name}.py")], cwd=self.repo, env=self.env(mode, name, inputs, with_ports, include),
                              capture_output=True, text=True, encoding="utf-8", timeout=WAIT * 4)
        if done.returncode:
            self.assertEqual(done.stdout, "")
            return done.returncode, None, done.stderr
        self.assertEqual(done.stdout.count("\n"), 1, done.stdout)
        return 0, json.loads(done.stdout), done.stderr

    def intake(self, mode: str) -> dict:
        rc, out, err = self.run_script("intake", mode, {}, with_ports=True)
        self.assertEqual(rc, 0, err)
        self.fresh.add(mode)
        return out

    def ok(self, name: str, mode: str = "base", **inputs) -> dict:
        rc, out, err = self.script(name, mode, **inputs)
        self.assertEqual(rc, 0, err)
        return out

    def decl(self, steps, commit=True, setup=None):
        (self.repo / declared_checks.DECL_NAME).write_text(json.dumps({"suite": steps, **({"setup": setup} if setup else {})}),
                                                           encoding="utf-8")
        if commit:
            git(self.repo, "add", "-A")
            git(self.repo, "commit", "-qm", "decl")
            self.head = git(self.repo, "rev-parse", "HEAD")
            self.write_start()

    def pointed(self, ptr: dict) -> pathlib.Path:
        self.assertEqual((ptr["type"], ptr["run_id"]), ("archon_artifact", RUN_ID))
        return self.artifacts / ptr["path"]


class IntakeCase(ScriptCase):
    def test_reads_every_port_into_intake_json(self):
        request = self.tmp / "request.json"
        request.write_text(json.dumps({"findings": [{"where": "stats.py:4", "text": "x"}]}), encoding="utf-8")
        baseline = self.tmp / "base.json"
        baseline.write_text("{}", encoding="utf-8")
        self.write_start(test_cmd=" make test ", tdd_suite=" run.sh ", base=self.head, entry_base=" origin/main ", request=str(request), request_scope="true",
                         baseline=str(baseline), reuse_key="k", lang="Japanese")
        self.assertEqual(self.intake("final"), {"ok": True, "reason": ""})
        doc = json.loads((self.place("final") / "intake.json").read_text(encoding="utf-8"))
        self.assertEqual(doc, {"mode": "final", "test_cmd": " make test ", "tdd_suite": "run.sh", "base": self.head,
                               "entry_base": "origin/main", "request": [{"where": "stats.py:4", "text": "x"}], "request_scope": True, "baseline": str(baseline),
                               "reuse_dir": str(self.artifacts / "test-reuse"), "reuse_key": "k", "user_env_dir": str(self.artifacts),
                               "lang": "Japanese"})
        state = json.loads((self.place("final") / "suite-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state, {"test_cmd": " make test ", "tdd_suite": "run.sh"})
        self.assertEqual(self.intake("base"), {"ok": True, "reason": ""})
        base = json.loads((self.place("base") / "intake.json").read_text(encoding="utf-8"))
        self.assertEqual(base["baseline"], "", "base では渡されても baseline を読まない")

    def test_defaults_are_empty(self):
        self.assertEqual(self.intake("base"), {"ok": True, "reason": ""})
        doc = json.loads((self.place("base") / "intake.json").read_text(encoding="utf-8"))
        self.assertEqual((doc["test_cmd"], doc["tdd_suite"], doc["base"], doc["entry_base"], doc["request"], doc["request_scope"],
                          doc["baseline"], doc["lang"]), ("", "", "", "", [], False, "", ""))

    def test_mode_outside_the_words_is_not_ok(self):
        self.write_start(mode="middle")
        out = self.intake("middle")
        self.assertEqual((out["ok"], out["reason"]), (False, "mode は base・final のどれか: middle"))

    def test_unreadable_port_names_the_port(self):
        for port, value, word in (("request_scope", "maybe", "port request_scope"),
                                  ("baseline", str(self.tmp / "none.json"), "port baseline")):
            with self.subTest(port):
                self.write_start(**{port: value})
                out = self.intake("final")
                self.assertFalse(out["ok"])
                self.assertIn(word, out["reason"])
                self.given.pop(port)
        with self.subTest("request"):
            self.write_start(request="{", request_scope="true")
            out = self.intake("base")
            self.assertFalse(out["ok"])
            self.assertIn("port request", out["reason"])
            self.given.pop("request"), self.given.pop("request_scope")

    def test_unreadable_request_is_empty_where_scope_does_not_read_it(self):
        """依頼の行を読むのは request_scope が真の base だけ。ほかで読めない依頼は関門を落とさず [] にする"""
        for mode, scope in (("final", "true"), ("base", "")):
            with self.subTest(mode=mode, scope=scope):
                self.write_start(request="{", **({"request_scope": scope} if scope else {}))
                self.assertTrue(self.intake(mode)["ok"])
                self.assertEqual(json.loads((self.place(mode) / "intake.json").read_text(encoding="utf-8"))["request"], [])
                self.given.pop("request"), self.given.pop("request_scope", None)

    def test_deletes_only_its_own_files_and_keeps_earlier_logs(self):
        """単独の run の place は run directory の根。消すのはこの block の名の在るファイルだけで、前の走りのログは残す"""
        other = self.artifacts / "other-block.json"
        other.write_text("{}", encoding="utf-8")
        (self.artifacts / "junit").mkdir()
        (self.artifacts / "junit" / "1.xml").write_text("x", encoding="utf-8")
        (self.artifacts / "logs" / "a1").mkdir(parents=True)
        (self.artifacts / "logs" / "a1" / "1.out").write_text("old", encoding="utf-8")
        (self.artifacts / "suite-write-prompt-1.md").write_text("old", encoding="utf-8")
        for k in range(3):
            (self.artifacts / f"keep-{k}.txt").write_text("x", encoding="utf-8")
        rc, out, err = self.run_script("intake", "base", {}, with_ports=True, include=False)
        self.assertEqual((rc, out), (0, {"ok": True, "reason": ""}), err)
        self.assertTrue(other.is_file() and all((self.artifacts / f"keep-{k}.txt").is_file() for k in range(3)))
        self.assertTrue((self.artifacts / "logs" / "a1" / "1.out").is_file())
        self.assertFalse((self.artifacts / "junit").exists() or (self.artifacts / "suite-write-prompt-1.md").exists())
        self.assertTrue((self.artifacts / "intake.json").is_file())


class RunScriptCase(ScriptCase):
    def test_stopped_run_exits_without_output(self):
        """止められたら孫まで木ごと止め、返りを出さずに 128+信号"""
        pidfile = self.tmp / "grandchild.pid"
        body = ("import subprocess, sys, time; p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']); "
                "open('r.xml', 'w').write('<testsuite/>'); "
                f"open({str(pidfile)!r}, 'w').write(str(p.pid)); time.sleep(120)")
        self.decl([{"name": "suite", "argv": [PY, "-c", body], "junit": "r.xml"}])
        before = green_cert.fingerprint(self.repo)
        self.intake("final")
        proc = subprocess.Popen([PY, str(SCRIPTS / "run.py")], cwd=self.repo, env=self.env("final", "run", {}),
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
        self.assertFalse((self.repo / "r.xml").exists(), "止められた段が書いた JUnit の報告が対象の木に残った")
        self.assertEqual(green_cert.fingerprint(self.repo), before)
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
        out = self.ok("run", "final")
        self.assertFalse((self.repo / "out" / "r.xml").exists())
        self.assertEqual((self.place("final") / "junit" / "1.xml").read_text(encoding="utf-8"), report)
        self.assertEqual((out["fingerprint_before"], out["fingerprint_after"]), (before, before))
        self.assertEqual(green_cert.fingerprint(self.repo), before)
        self.assertEqual((out["by"], out["material"]["status"], out["junit_steps"]), ("engine", "clean", ["suite"]))
        self.assertEqual(sorted(out), sorted(node("run")["output_format"]["properties"]))

    def test_target_command_reads_the_users_global_config_without_a_switch(self):
        """起動の殻が HOME・XDG を隔離した run でも、対象のコマンドは旗を置かずに利用者の HOME の下の全体の設定を読める
        （殻の隔離を通した run は、いつも隔離の前の HOME・XDG の控えを持つ）"""
        tool = self.as_user()
        (self.user_home / ".config" / "homecfg").mkdir(parents=True)
        (self.user_home / ".config" / "homecfg" / "ok").write_text("", encoding="utf-8")
        self.decl([{"name": "suite", "argv": [str(tool)]}])
        out = self.ok("run", "final")
        self.assertEqual([r["exit"] for r in out["runs"]], [0])

    def test_users_env_marker_only_when_a_target_command_ran(self):
        """#504: 殻の隔離を通した run で対象のコマンドを起こした時だけ、メイングラフの run の置き場に印（userenv.RAN_FILE）が残る。
        CI の役だけに任せた run（走らせる物が無い。role_needed）には残らない"""
        tool = self.as_user()
        self.write_start(test_cmd=str(tool))
        self.ok("run", "final")
        self.assertTrue(userenv.ran(self.artifacts))
        (self.artifacts / userenv.RAN_FILE).unlink()
        self.write_start(user_env_dir=" ")   # 空の置き場
        rc, out, err = self.script("run", "final")
        self.assertEqual((rc, out), (1, None), "#681: 印の置き場の入力が無ければ自分の置き場へ黙って倒さず、戻さずに止める")
        self.assertIn(userenv.RAN_DIR_ENV, err)
        self.assertFalse(userenv.ran(self.artifacts))
        self.write_start(test_cmd="", user_env_dir=str(self.artifacts))
        self.assertEqual(self.ok("run", "final")["by"], declared_checks.ROLE_NEEDED)
        self.assertFalse(userenv.ran(self.artifacts))

    def scoped(self):
        """種に far・near の宣言と、far が works/ を見ない範囲の宣言を commit する"""
        (self.repo / ".works-checks.json").write_text('{"far": {"paths_ignore": ["works/"]}}', encoding="utf-8")
        self.decl([{"name": "far", "argv": [PY, "-c", "print('far')"]}, {"name": "near", "argv": [PY, "-c", "print('near')"]}])

    def test_archon_workspace_is_not_a_change(self):
        """Archon が作業ツリーに置く .archon/ の下は範囲と照らす変更に数えない"""
        self.scoped()
        (self.repo / "works").mkdir()
        (self.repo / "works" / "a.py").write_text("x\n", encoding="utf-8")
        (self.repo / ".archon").mkdir()
        (self.repo / ".archon" / "x.yaml").write_text("x: 1\n", encoding="utf-8")
        self.write_start(base=self.head)
        out = self.ok("run", "final")
        self.assertEqual(out["skipped_steps"], [{"name": "far", "paths_ignore": ["works/"]}])

    def test_final_does_not_read_request_where_as_change(self):
        """最後のテストは依頼の where を範囲と照らす変更に足さない（変更の無い final は絞らない）。直す前は段を走らせないので照らさない
        （持ち主の決め base-selfcheck-only）"""
        (self.repo / "works").mkdir()
        (self.repo / "works" / "a.py").write_text("x\n", encoding="utf-8")
        self.scoped()
        request = self.tmp / "request.json"
        request.write_text(json.dumps({"findings": [{"where": "works/a.py:1", "text": "x"}]}), encoding="utf-8")
        self.write_start(request=str(request), request_scope="true")
        self.assertEqual(self.ok("run", "final")["skipped_steps"], [])
        self.assertEqual(self.ok("run", "base")["runs"], [])

    def test_rerun_keeps_earlier_logs(self):
        """同じ run で同じ形を呼び直しても前の走りのログを上書きしない（空いた番号の置き場 logs/a<k>/）。前の回の素材・拒否・記録は
        intake が消す（今回の物として読まない）"""
        self.decl([{"name": "suite", "argv": [PY, "-c", "print('ran')"]}])
        gate = self.place("final")
        first = self.ok("run", "final")
        for name in ("baseline.json", "evidence.md"):
            (gate / name).write_text("{}", encoding="utf-8")
        self.intake("final")
        second = self.ok("run", "final")
        self.assertEqual((gate / "logs" / "a1" / "1.out").read_text(encoding="utf-8"), "ran\n")
        self.assertEqual((gate / "logs" / "a2" / "1.out").read_text(encoding="utf-8"), "ran\n")
        self.assertEqual((pathlib.Path(first["log"]).parent.name, pathlib.Path(second["log"]).parent.name), ("a1", "a2"))
        self.assertFalse((gate / "baseline.json").exists())
        self.assertFalse((gate / "evidence.md").exists())

    def test_scope_declaration_without_review_declaration_stops(self):
        """範囲の宣言だけが在れば走らせずに 1 で止め、理由を標準エラーに出す"""
        (self.repo / ".works-checks.json").write_text('{"far": {"paths_ignore": ["works/"]}}', encoding="utf-8")
        rc, out, err = self.script("run", "base")
        self.assertEqual((rc, out), (1, None))
        self.assertIn(".works-checks.json", err)

    def test_declared_step_with_the_factory_step_name_stops(self):
        """#531: 宣言の段の名が工場の段の名（declared_checks.TEST_CMD_STEP）なら、判定の AI より前の修正前のテストで、何も走らせずに
        1 行の訳で 1 で止める"""
        ran = self.tmp / "ran"
        self.decl([{"name": declared_checks.TEST_CMD_STEP, "argv": [PY, "-c", f"open({str(ran)!r}, 'w')"]}])
        rc, out, err = self.script("run", "base")
        self.assertEqual((rc, out), (1, None))
        self.assertEqual(err.count("\n"), 1, err)
        self.assertIn(declared_checks.TEST_CMD_STEP, err)
        self.assertFalse(ran.exists())


class ResultScriptCase(ScriptCase):
    """返す node: 赤の原因と認証と、落ちないこと"""
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
        out = self.ok("result", mode, **inputs)
        self.assertEqual(schema_problems(out, self.output_format), [], out)
        self.assertTrue(self.pointed(out["evidence"]).is_file())
        return out

    def base(self) -> str:
        """base を通し、base の出力の baseline のファイルのパス（final の port baseline）を返す。直す前は段を走らせない（持ち主の決め
        base-selfcheck-only）ので、元の結末に 1 件ごとの結末は無く、final の赤は修正前の版（port base）で段を走らせ直して分ける"""
        self.decl([{"name": "suite", "argv": [PY, "-c", self.STEP_BODY], "junit": "out/r.xml"}])
        self.write_start(base=self.head)
        self.ok("run", "base")
        out = self.result("base")
        self.assertEqual((out["mode"], out["ok"], out["green"], out["fingerprint"]), ("base", True, False, None))
        doc = baseline_red.read_baseline(self.pointed(out["baseline"]))
        self.assertEqual((doc["rev"], doc["exit"], doc["junit_steps"], doc["exit_codes"], doc["cases"]), (self.head, None, [], {}, []))
        self.assertEqual(doc["material"]["status"], "not_applicable")
        self.baseline_path = str(self.pointed(out["baseline"]))
        return self.baseline_path

    def final(self, baseline: str) -> dict:
        self.write_start(baseline=baseline)
        self.ok("run", "final")
        return self.result("final")

    def test_final_inherited_red_is_not_certified(self):
        out = self.final(self.base())
        self.assertEqual((out["ok"], out["green"], out["red_cause"]), (False, False, "inherited"))
        self.assertIn("inherited", self.pointed(out["evidence"]).read_text(encoding="utf-8"))
        self.assertEqual(out["fingerprint"], green_cert.fingerprint(self.repo))

    def test_returned_values_are_the_evidence_rows(self):
        """走らせ方・ログ・修正前のテスト・認証しなかった訳は、返りの欄（1 行）と同じ回の証拠の文の行が同じ値（報告と最後の関所は
        返りの欄を読む）。base は修正前のテストの欄が空で、証拠にその行が無い"""
        certify = kit.load("test-gate", "certify")
        baseline = self.base()
        for out in (self.result("base"), self.final(baseline)):
            with self.subTest(out["mode"]):
                rows = self.pointed(out["evidence"]).read_text(encoding="utf-8").splitlines()
                self.assertEqual(out["by"], "engine")
                self.assertFalse([r for r in rows if r.startswith("- 包み:")])
                self.assertIn(f"{certify.RUN_ROW}engine・{out['suites_line']}", rows)
                self.assertIn(f"{certify.LOG_ROW}{declared_checks.gate_values(out)['log']}", rows)
                self.assertTrue((out["log"] or out["mode"] == "base") and "\n" not in out["suites_line"] + out["log"] + out["baseline_line"], out)
                self.assertIn(f"- ok: {str(out['ok']).lower()}" + (f"（{out['reason']}）" if out["reason"] else ""), rows)
                if out["mode"] == "final":
                    self.assertTrue(out["baseline_line"].startswith(f"{declared_checks.BASELINE_HEAD}: {gatemarks.MATERIAL_WORDS['not_applicable']}"), out)
                    self.assertIn(f"- {out['baseline_line']}", rows)
                else:
                    self.assertEqual(out["baseline_line"], "")
                    self.assertFalse([r for r in rows if declared_checks.BASELINE_HEAD in r])

    def test_final_evidence_names_the_tests_before_the_fix(self):
        """final の証拠は修正前のテストの行を出す: 直す前は試験を回さなかった（持ち主の決め base-selfcheck-only）ことと、元の結末に無い
        赤を修正前の版で走らせ直した行。元の結末が無い final は記録が無いと書く"""
        text = self.pointed(self.final(self.base())["evidence"]).read_text(encoding="utf-8")
        line = next(l for l in text.splitlines() if "修正前のテスト" in l)
        self.assertIn(f"修正前のテスト: {gatemarks.MATERIAL_WORDS['not_applicable']}", line)
        self.assertIn("直す前の版では全部の試験を回さない", line)
        self.assertIn("- 修正前の版で走らせ直した: ", text)
        self.write_start(baseline="")
        self.intake("final")
        self.ok("run", "final")
        text = self.pointed(self.result("final")["evidence"]).read_text(encoding="utf-8")
        self.assertIn("修正前のテスト: 記録が無い", text)

    def test_final_introduced_red_is_not_certified(self):
        baseline = self.base()
        (self.repo / "broken.flag").write_text("x\n", encoding="utf-8")
        out = self.final(baseline)
        self.assertEqual((out["ok"], out["red_cause"]), (False, "introduced"))
        self.assertIn("m::c", self.pointed(out["evidence"]).read_text(encoding="utf-8"))

    def test_final_green_is_certified_with_fingerprint_and_tree_change_voids_it(self):
        baseline = self.base()
        (self.repo / "fixed.flag").write_text("x\n", encoding="utf-8")
        self.write_start(baseline=baseline)
        self.ok("run", "final")
        out = self.result("final")
        self.assertEqual((out["ok"], out["green"], out["red_cause"]), (True, True, ""))
        self.assertTrue(green_cert.matches(out["fingerprint"], self.repo))
        (self.repo / "later.txt").write_text("x\n", encoding="utf-8")
        out = self.result("final")
        self.assertEqual((out["ok"], out["green"]), (False, True))
        self.assertIn("指紋が before と違う", self.pointed(out["evidence"]).read_text(encoding="utf-8"))

    def test_tdd_suite_cases_go_into_the_baseline(self):
        """port の tdd_suite は一式を 1 回走らせ、その 1 件ごとの結末と終了コードを元の結末に置く（suite は実行ファイルのパス）"""
        suite = self.tmp / "suite.py"
        suite.write_text("import sys\nopen(sys.argv[1], 'w').write(\"<testsuite><testcase classname='s' name='x'>"
                         "<failure/></testcase></testsuite>\")\nsys.exit(1)\n", encoding="utf-8")
        self.write_start(tdd_suite=str(suite), test_cmd="true")
        self.ok("run", "base")
        out = self.result("base")
        doc = baseline_red.read_baseline(self.pointed(out["baseline"]))
        self.assertEqual((doc["suite"], doc["test_cmd"], doc["exit"]), (str(suite), "true", 1))
        self.assertEqual(baseline_red.outcomes(doc["cases"]), {"s::x": "failure"})
        self.assertTrue(doc["how"][0].startswith(f"作業ツリーの根: `{self.repo.resolve()}`"), doc["how"])
        self.assertTrue(any(r.startswith("test_cmd: `true`") for r in doc["how"]), doc["how"])
        self.assertEqual((out["suite"], out["suite_note"]), (str(suite), ""))

    def test_final_returns_every_test_with_its_base_and_final_outcome(self):
        """final はテストごとの元の結末と今の結末を test_outcomes で返す（独立の目の比較役が読む）。base は null、
        元の結末が無い final は rows を空にして比べない訳を書く"""
        suite = self.tmp / "suite.py"
        suite.write_text("import os, sys\nok = os.path.exists('fixed.flag')\nopen(sys.argv[1], 'w').write("
                         "\"<testsuite><testcase classname='s' name='y'/>\" + (\"<testcase classname='s' name='x'/>\" if ok else \"<testcase classname='s' name='x'><failure message='0 != 10'/>"
                         "</testcase>\") + \"</testsuite>\")\nsys.exit(0 if ok else 1)\n", encoding="utf-8")
        self.write_start(tdd_suite=str(suite), test_cmd="true")
        self.ok("run", "base")
        base = self.result("base")
        self.assertIsNone(base["test_outcomes"])
        (self.repo / "fixed.flag").write_text("x\n", encoding="utf-8")
        self.write_start(baseline=str(self.pointed(base["baseline"])))
        self.ok("run", "final")
        self.assertEqual(self.result("final")["test_outcomes"],
                         {"rows": [{"key": "s::y", "base": "passed", "final": "passed", "fail_message": ""},
                                   {"key": "s::x", "base": "failure", "final": "passed", "fail_message": "0 != 10"}], "unmeasured": ""})
        self.write_start(baseline="")
        self.ok("run", "final")
        self.assertEqual(self.result("final")["test_outcomes"],
                         {"rows": [], "unmeasured": "base の実測（baseline）が無い（実行器の無い run か、base のテストが走っていない）"})

    def test_test_outcomes_are_not_compared_when_either_side_has_no_per_test_results(self):
        """1 件ごとの結末を取っていない側が在れば、rows を空にして比べない訳を書く（「無い」と読ませない）。直す前は自己点検の
        実行器が無ければ 1 件ごとの結末を取らず、最後のテストに元の結末に無い赤も無ければ修正前の版で走らせ直さない"""
        suite = self.tmp / "suite.py"
        suite.write_text("import sys\nopen(sys.argv[1], 'w').write(\"<testsuite><testcase classname='s' name='x'/></testsuite>\")\n",
                         encoding="utf-8")
        self.write_start(tdd_suite=str(suite), base=self.head)
        self.ok("run", "base")
        tallied = str(self.pointed(self.result("base")["baseline"]))
        self.decl([{"name": "suite", "argv": [PY, "-c", "pass"]}])
        self.write_start(tdd_suite="")
        self.assertEqual(self.final(tallied)["test_outcomes"],
                         {"rows": [], "unmeasured": "最後のテストは 1 件ごとの結末を取っていない"})
        untallied = self.base()
        (self.repo / "fixed.flag").write_text("x\n", encoding="utf-8")
        self.assertEqual(self.final(untallied)["test_outcomes"],
                         {"rows": [], "unmeasured": "base のテストは 1 件ごとの結末を取っていない"})

    def test_bare_name_tdd_suite_runs_from_the_target_root(self):
        """#340: 種の tdd_suite のようにファイル名だけ（junit-suite.sh）の実行器は、PATH でなく対象の根から起こす（TDD の輪の
        tddloop.exe_path と同じ解き方）。base も final も"""
        suite = self.repo / "bare-suite.sh"
        suite.write_text("#!/bin/sh\nprintf '%s' \"<testsuite><testcase classname='s' name='x'/></testsuite>\" > \"$1\"\n",
                         encoding="utf-8")
        suite.chmod(0o755)
        self.write_start(tdd_suite=suite.name, test_cmd="true")
        for mode in declared_checks.MODES:
            with self.subTest(mode):
                self.ok("run", mode)
                run = json.loads((self.place(mode) / "run.json").read_text(encoding="utf-8"))
                ran, cases = (run["selfcheck"]["ran"], run["selfcheck"]["cases"]) if mode == "base" else (run["suite"], run["cases"])
                self.assertEqual({k: ran[k] for k in ("exe", "exit", "problems")}, {"exe": suite.name, "exit": 0, "problems": []})
                self.assertEqual(baseline_red.outcomes(cases), {"s::x": "passed"})

    def test_final_not_run_is_incomplete(self):
        self.ok("run", "final")
        out = self.result("final")
        self.assertEqual((out["ok"], out["red_cause"]), (False, "incomplete"))

    def test_command_that_fails_before_its_tests_is_named_not_ran(self):
        """#492: JUnit の報告を宣言した段が試験に入る前に落ちた（利用者の設定が無い）final は incomplete で、冒頭の句は「走っていない」"""
        tool = self.as_user()
        self.decl([{"name": "suite", "argv": [str(tool)], "junit": "out/r.xml"}])
        self.ok("run", "final")
        out = self.result("final")
        self.assertEqual((out["ok"], out["green"], out["red_cause"]), (False, False, "incomplete"))
        self.assertTrue(green_cert.ran_note(green=out["green"], red_cause=out["red_cause"], by=out["by"]).startswith(green_cert.NOT_RAN))

    def test_shell_command_failing_alike_before_and_after_is_not_named_not_ran(self):
        """#504: shell の test_cmd だけの対象で、時刻を出さない試験が直す前と後で同じログの赤でも、試験に入ったかの証拠が無いだけで
        「走っていない」とは言わない（原因の無い赤。冒頭の句は「確かめられていない」）"""
        tool = self.as_user()
        self.write_start(test_cmd=f"{tool} && echo tests")
        self.ok("run", "base")
        base = self.result("base")
        self.assertEqual((base["by"], base["red_cause"]), (declared_checks.ROLE, green_cert.INCOMPLETE), "直す前は試験を走らせない")
        self.write_start(baseline=str(self.pointed(base["baseline"])))
        self.ok("run", "final")
        out = self.result("final")
        self.assertEqual((out["green"], out["red_cause"]), (False, ""))
        note = green_cert.ran_note(green=out["green"], red_cause=out["red_cause"], by=out["by"])
        self.assertTrue(note.startswith(green_cert.UNVERIFIED_RUN), note)
        self.assertNotIn(green_cert.NOT_RAN, note)

    def test_shell_command_that_cannot_start_is_named_not_ran(self):
        """#504: test_cmd のコマンドが起きない（試験に入れなかった証拠）final は incomplete で、冒頭の句は「走っていない」。
        起動の殻の隔離を通した run でも、起きなかったコマンドは利用者の HOME・XDG で走らせた印（userenv.RAN_FILE）を残さない"""
        self.write_start(test_cmd=str(self.tmp / "no-such-tool"))
        for through_shell in (False, True):
            with self.subTest(through_shell=through_shell):
                if through_shell:
                    self.as_user()
                self.ok("run", "final")
                out = self.result("final")
                self.assertEqual((out["green"], out["red_cause"]), (False, green_cert.INCOMPLETE))
                self.assertEqual(out["ran_steps"]["ran"], [])
                note = green_cert.ran_note(green=out["green"], red_cause=out["red_cause"], by=out["by"], steps=out["ran_steps"])
                self.assertTrue(note.startswith(green_cert.NOT_RAN), note)
                self.assertFalse(userenv.ran(self.artifacts))
                self.fresh.clear()

    def stopped_base(self):
        """base を run と result の node まで通し、(run の返り, result の返り) を返す。直す前の基準を測れず止めた形（ok も green も偽）かを照らす"""
        run = self.ok("run", "base")
        out = self.result("base")
        self.assertEqual((out["ok"], out["green"]), (False, False), out)
        return run, out

    def unrun_final(self):
        """試験の道具を起こせない対象の (base の返り, final の run の返り, final の result の返り, final の証拠の文)。直す前は試験を
        走らせない（持ち主の決め base-selfcheck-only）ので base は止まらず、最後のテストが走らせられなかったと言い、認証しない"""
        self.ok("run", "base")
        base = self.result("base")
        self.assertIs(base["ok"], True, base)
        run = self.ok("run", "final")
        out = self.result("final")
        self.assertEqual((out["ok"], out["green"]), (False, False), out)
        return base, run, out, self.pointed(out["evidence"]).read_text(encoding="utf-8")

    def note(self, out) -> str:
        """最後のテストの冒頭の句（green_cert.ran_note。走っていない句には準備の案 RAN_GUIDE が付く）"""
        return green_cert.ran_note(green=out["green"], red_cause=out["red_cause"], by=out["by"], steps=out["ran_steps"])

    def test_declared_steps_that_all_fail_to_start_are_named_at_the_final(self):
        """宣言の段が全部起こせない（無いコマンド）対象は、最後のテストの素材が not_run で environment。証拠の素材の訳に起こせない
        誤りの文が載り、冒頭の句に準備の案（SETUP_HINT）が付く"""
        self.decl([{"name": "a", "argv": [str(self.tmp / "no-such-tool")]}, {"name": "b", "argv": [str(self.tmp / "no-such-tool-b")]}])
        _, run, out, text = self.unrun_final()
        self.assertEqual((run["by"], run["material"]["status"]), ("engine", "not_run"))
        self.assertEqual(out["red_cause"], green_cert.ENVIRONMENT)
        for said in ("宣言の語を起こせない", "no-such-tool"):
            self.assertIn(said, text)
        self.assertIn(declared_checks.declared.SETUP_HINT, self.note(out))

    def test_place_trusting_tool_runs_at_the_final_once_setup_trusts_the_place(self):
        """場所ごとに信頼する道具（利用者の HOME の下の信頼の一覧に cwd の実パスが在る時だけ試験の報告を書いて 0 で抜ける）は、準備を
        宣言しなければ試験に入る前に 3 で落ち、最後のテストは not_run で認証しない。証拠に道具の誤りの文と準備の案が載る。
        宣言の setup が一覧に cwd を書けば、殻の隔離を通した最後のテストの段が 0 で走る"""
        self.as_user()
        tool = self.tmp / "bin" / "trusting"
        tool.write_text('#!/bin/sh\nif grep -qxF "$(pwd -P)" "$HOME/.config/trust/list" 2>/dev/null; then\n'
                        "  mkdir -p out && echo '<testsuite><testcase classname=\"m\" name=\"a\"/></testsuite>' > out/r.xml && exit 0\n"
                        'fi\necho "untrusted: $(pwd -P)" >&2\nexit 3\n', encoding="utf-8")
        tool.chmod(0o755)
        trust = [PY, "-c", "import os, pathlib; p = pathlib.Path(os.environ['HOME'], '.config', 'trust', 'list'); "
                           "p.parent.mkdir(parents=True, exist_ok=True); open(p, 'a').write(os.path.realpath(os.getcwd()) + chr(10))"]
        step = {"name": "suite", "argv": [str(tool)], "junit": "out/r.xml"}
        self.decl([step])
        _, run, out, text = self.unrun_final()
        self.assertEqual(([r["exit"] for r in run["runs"]], run["material"]["status"]), ([3], "not_run"))
        self.assertIn("untrusted: ", text)
        self.assertIn(declared_checks.declared.SETUP_HINT, self.note(out))
        self.decl([step], setup=[trust])
        run = self.ok("run", "final")
        self.assertEqual(([r["exit"] for r in run["runs"]], run["material"]["status"]), ([0], "clean"))

    def test_a_test_cmd_that_cannot_start_is_named_at_the_final(self):
        """宣言が無く test_cmd を起こせない（無いコマンド）対象は、最後のテストの by が role・素材が not_run で認証しない"""
        self.write_start(test_cmd=str(self.tmp / "no-such-tool"))
        base, run, out, text = self.unrun_final()
        self.assertEqual((run["by"], run["material"]["status"]), (declared_checks.ROLE, "not_run"))
        self.assertIn(declared_checks.declared.SETUP_HINT, self.note(out))

    def test_junit_steps_that_ran_no_tests_name_the_tools_error_at_the_final(self):
        """JUnit を宣言した唯一の段が、試験に入る前に道具の誤り（config missing）で落ちた対象は、最後のテストの素材が not_run。証拠に
        道具が出した誤りの文が載る"""
        tool = self.as_user()
        self.decl([{"name": "suite", "argv": [str(tool)], "junit": "out/r.xml"}])
        _, run, out, text = self.unrun_final()
        self.assertEqual(run["material"]["status"], "not_run")
        self.assertIn("config missing", text)

    def test_failing_setup_stops_the_base_with_its_error(self):
        """suite の横に宣言した setup が非 0 で終わる（標準エラーに『準備が落ちた』）base は、試験を走らせない base でも準備だけは走らせて
        止まる（ok が false）。suite の段は起こされず、reason に setup の誤りの文と準備の案が載り、実行器を用意しない"""
        ran = self.tmp / "suite-ran"
        self.decl([{"name": "suite", "argv": [PY, "-c", f"open({str(ran)!r}, 'w')"]}],
                  setup=[[PY, "-c", "import sys; print('準備が落ちた', file=sys.stderr); sys.exit(4)"]])
        run, out = self.stopped_base()
        self.assertIs(run["suite_owed"], False)
        self.assertFalse(ran.exists())
        self.assertIn(tree_run.SETUP_FAILED, out["reason"])
        self.assertIn("準備が落ちた", out["reason"])
        self.assertIn(declared_checks.declared.SETUP_HINT, out["reason"])

    def test_partly_startable_steps_are_named_not_not_ran(self):
        """#514: 宣言の段の一部だけ起こせた final は、判定はそのまま（赤で認証しない）で、冒頭の句は起こした段と起こせなかった段を
        名指し、「走っていない」と言わない"""
        self.decl([{"name": "started", "argv": [PY, "-c", "pass"]}, {"name": "missing", "argv": [str(self.tmp / "no-such-tool")]}])
        self.ok("run", "final")
        out = self.result("final")
        self.assertEqual((out["ok"], out["green"]), (False, False))
        self.assertIn(out["red_cause"], (green_cert.ENVIRONMENT, green_cert.INCOMPLETE))
        self.assertEqual(out["ran_steps"], {"ran": ["started"], "unran": ["missing"]})
        note = green_cert.ran_note(green=out["green"], red_cause=out["red_cause"], by=out["by"], steps=out["ran_steps"])
        self.assertTrue(note.startswith(green_cert.PARTLY_RAN), note)
        self.assertNotIn(green_cert.NOT_RAN, note)

    def test_gate_script_failure_is_not_named_not_ran(self):
        """#492 R1: 返す node の中の誤りの返り（failed）は、試験の関門の句（GATE_BROKE）で、「走っていない」と言わない"""
        certify = kit.load("test-gate", "certify")
        self.intake("final")
        with mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(self.artifacts), "WORKFLOW_ID": RUN_ID}):
            out = certify.failed(self.place("final"), ValueError("壊れた元の結末"))
        self.assertEqual(out["ran_steps"], {"ran": [], "unran": []})
        self.assertEqual(green_cert.ran_note(green=out["green"], red_cause=out["red_cause"], by=out["by"]), green_cert.GATE_BROKE)

    def test_suite_without_cases_leaves_no_baseline_exit(self):
        """tdd_suite が JUnit を書かずに落ちた base は元の結末の exit を残さない。final はそれを「元の結末が無い」と読み、今の赤を
        今回入れた物に数えない"""
        suite = self.tmp / "suite.py"
        suite.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
        self.write_start(tdd_suite=str(suite), test_cmd="false")
        self.ok("run", "base")
        out = self.result("base")
        self.assertIsNone(baseline_red.read_baseline(self.pointed(out["baseline"]))["exit"])
        suite.write_text("import sys\nopen(sys.argv[1], 'w').write(\"<testsuite><testcase classname='s' name='x'>"
                         "<failure/></testcase></testsuite>\")\nsys.exit(1)\n", encoding="utf-8")
        out = self.final(str(self.pointed(out["baseline"])))
        self.assertEqual((out["ok"], out["red_cause"]), (False, ""))

    def test_shell_test_cmd_names_how_it_was_launched(self):
        """宣言が無く test_cmd だけを走らせた回の証拠は、test_cmd の起こし方（shell）を書く"""
        self.write_start(test_cmd="echo a | cat")
        self.assertEqual(self.ok("run", "final")["by"], "role")
        out = self.result("final")
        self.assertIn("走らせた: test_cmd（shell）", self.pointed(out["evidence"]).read_text(encoding="utf-8"))

    def test_fell_back_reason_is_in_the_evidence(self):
        """engine の結果を任せ先へ落とした回の証拠は、落とした訳（run.json の fell_back）を書く"""
        self.write_start(test_cmd=f"{PY} -c pass")
        self.ok("run", "base")
        run_json = self.place("base") / "run.json"
        run = json.loads(run_json.read_text(encoding="utf-8"))
        run_json.write_text(json.dumps({**run, "fell_back": "engine が組んだ素材が素材の欄の決まりに外れた: 訳 X"}), encoding="utf-8")
        text = self.pointed(self.result("base")["evidence"]).read_text(encoding="utf-8")
        self.assertIn("- engine の結果を任せ先へ落とした訳: engine が組んだ素材が素材の欄の決まりに外れた: 訳 X", text)

    def test_broken_inputs_return_incomplete_without_failing(self):
        """返す node は落ちない: 壊れた入力でも終了の値 0 で、output_format に合う ok: false・red_cause: incomplete を 1 つ出す。
        port が読めなかった回の intake（intake.json に failed）も、読めなかった訳を証拠に名指して返す"""
        self.decl([{"name": "suite", "argv": [PY, "-c", "print('ok')"]}])
        self.ok("run", "final")
        place = self.place("final")
        intake = place / "intake.json"
        good = intake.read_text(encoding="utf-8")
        cases = {
            "intake.json が JSON でない": "{",
            "port が読めなかった回": json.dumps({"failed": "port baseline が読めない: x", "mode": "final"}),
            "元の結末のファイルが壊れている": json.dumps({**json.loads(good), "baseline": str(self.tmp / "broken.json")}),
            "baseline の先が無い": json.dumps({**json.loads(good), "baseline": str(self.tmp / "nope.json")}),
            "mode が形の外": json.dumps({**json.loads(good), "mode": "middle"}),
        }
        (self.tmp / "broken.json").write_text('{"suite": ""}', encoding="utf-8")
        for why, text in cases.items():
            with self.subTest(why):
                intake.write_text(text, encoding="utf-8")
                out = self.result("final")
                self.assertEqual((out["mode"], out["ok"], out["green"], out["red_cause"], out["baseline"], out["fingerprint"]),
                                 ("final", False, False, "incomplete", None, None))
                self.assertEqual((out["by"], out["reason"]), ("", "出力ノードの中の誤り"))
                self.assertEqual(out["report"], [f"試験の関門（final）: 出力ノードの中の誤り（工場の不具合）——{out['evidence']['path']}"])
        intake.write_text(good, encoding="utf-8")
        (place / "run.json").unlink()
        out = self.result("final")
        self.assertEqual((out["ok"], out["red_cause"]), (False, "incomplete"))
        self.assertIn("run.json", self.pointed(out["evidence"]).read_text(encoding="utf-8"))

    def test_broken_intake_in_base_names_the_base_mode(self):
        self.write_start(request="{", request_scope="true")
        out = self.intake("base")
        self.assertFalse(out["ok"])
        failed = self.ok("result", "base")
        self.assertEqual((failed["mode"], failed["ok"], failed["red_cause"], failed["suite"]), ("base", False, "incomplete", ""))
        self.assertIn("port request", self.pointed(failed["evidence"]).read_text(encoding="utf-8"))

    def test_lib_that_cannot_be_imported_returns_incomplete_without_failing(self):
        """lib の import が落ちても、返す node は終了の値 0 で約束の形の偽の結末と、誤りを名指した証拠を返す"""
        self.intake("base")
        nowhere = self.tmp / "no-root"
        done = subprocess.run([PY, str(SCRIPTS / "result.py")], cwd=self.repo, timeout=WAIT,
                              env={**self.env("base", "result", {"optional": ""}), "WORKS_FACTORY_ROOT": str(nowhere)},
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        self.assertEqual(schema_problems(out, self.output_format), [], out)
        self.assertEqual((out["mode"], out["ok"], out["green"], out["red_cause"]), ("base", False, False, "incomplete"))
        self.assertEqual((out["by"], out["suites_line"], out["log"], out["baseline_line"]), ("", "", "", ""))
        self.assertIn(f"- ok: false（{out['reason']}）", self.pointed(out["evidence"]).read_text(encoding="utf-8"))
        self.assertIn("ModuleNotFoundError", self.pointed(out["evidence"]).read_text(encoding="utf-8"))

    def test_report_lines(self):
        """報告の行（10 節）: base と final と、出力 node の中の誤り"""
        baseline = self.base()
        base = self.result("base")
        word = gatemarks.MATERIAL_WORDS["not_applicable"]
        self.assertEqual(base["report"][0], f"直す前のテスト: {word}（not_applicable）")
        self.assertTrue(base["report"][1].startswith("直す前のテストの走らせ方: engine・直す前は自己点検だけ"), base["report"])
        self.assertTrue(base["report"][2].startswith("直す前のテストのログ: "), base["report"])
        self.assertEqual(base["report"][3], "試験の関門（base）: 緑でない・ok True・赤の原因 incomplete")
        self.assertEqual(len(base["report"]), 4)
        out = self.final(baseline)
        self.assertTrue(out["report"][0].startswith("最後のテストの走らせ方: engine・"), out["report"])
        self.assertTrue(out["report"][2].startswith(f"最後のテストの修正前のテスト: {word}"), out["report"])
        self.assertTrue(out["report"][3].startswith("最後のテストの一式: engine・"), out["report"])
        self.assertEqual(out["report"][-1], "試験の関門（final）: 緑でない・ok False・赤の原因 inherited")
        (self.repo / "fixed.flag").write_text("x\n", encoding="utf-8")
        self.assertEqual(self.final(baseline)["report"][-1], "試験の関門（final）: 緑・ok True")

    def test_report_names_a_red_that_was_passed(self):
        """ok が真で原因が inherited・environment の赤は、赤のまま通したと言う"""
        report = kit.load("test-gate", "report")
        line = report._green_line("base", {"green": False, "ok": True, "red_cause": "environment"})
        self.assertEqual(line, "試験の関門（base）: 緑でない・ok True・赤の原因 environment——赤のまま通した（environment の赤。直しが起こした赤でないと認証が見た）")


class SuiteLoopCase(ScriptCase):
    """#516: tdd_suite を省いた run の base で TDD の実行器を用意する輪の script（suite-prep → 書き手の返り → suite-place → suite-try）。
    取り置きの根（起動の殻が渡す launcher.SUITE_KEEP_ENV。ports.suite_keep）は一時の置き場に向ける。test_cmd は赤（false）にする:
    緑の test_cmd と赤の実行器は、直す前の自己点検が起動スクリプトの壊れと読んで止める（#836。SelfCheckCase）"""
    CMD = "false"
    # 名 test_x が failure（赤）、test_y が通る JUnit XML を第 1 引数に書いて 1 で抜ける実行器
    RED = ("#!/bin/sh\nprintf '%s' \"<testsuite><testcase classname='test_a.TestA' name='test_x'><failure message='0 != 10'/>"
           "</testcase><testcase classname='test_a.TestA' name='test_y'/></testsuite>\" > \"$1\"\nexit 1\n")
    EMPTY = "#!/bin/sh\nprintf '%s' '<testsuite/>' > \"$1\"\n"

    def setUp(self):
        super().setUp()
        self.declared = {launcher.SUITE_KEEP_ENV: str(self.tmp / "suites")}
        self.write_start(test_cmd=f" {self.CMD} ")

    def kept(self) -> pathlib.Path:
        return self.tmp / "suites" / hashlib.sha256(self.CMD.encode("utf-8")).hexdigest()

    def put_kept(self, body: str) -> None:
        self.kept().parent.mkdir(parents=True)
        self.kept().write_text(body, encoding="utf-8")

    def state(self) -> dict:
        return json.loads((self.place("base") / "suite-state.json").read_text(encoding="utf-8"))

    def run_doc(self) -> dict:
        return json.loads((self.place("base") / declared_checks.RUN_FILE).read_text(encoding="utf-8"))

    def round(self, body=None) -> tuple:
        """輪の 1 周（prep が書くと言えば、書き手の返りとして body を置く。None は書き手が落ちた周）。(prep の返り, try の返り)"""
        prep = self.ok("suite_prep", "base")
        if prep["write"] and body is not None:
            self.ok("suite_place", "base", reply=json.dumps({"made": True, "body": body, "why": ""}))
        return prep, self.ok("suite_try", "base")

    def test_run_owes_a_runner_only_in_the_base_without_tdd_suite(self):
        self.assertIs(self.ok("run", "base")["suite_owed"], True)
        self.assertIs(self.ok("run", "final")["suite_owed"], False)
        self.write_start(test_cmd=self.CMD, tdd_suite="run-tests.sh")
        self.assertIs(self.ok("run", "base")["suite_owed"], False)

    def test_written_runner_feeds_the_red_green_check(self):
        """keep-essence 1（赤緑の機械の判定）は tdd_suite を省いた run でも効く: 書いた実行器を 1 回走らせた結末が照らしを通れば
        実行器の控えの tdd_suite に結び、元の結末に 1 件ごとの結末が載り、出力の suite が実行器の絶対パスで、修正の段の TDD の輪が
        その実行器で名指しの赤を判じる。照らしを通った実行器は test_cmd の字で取り置く"""
        tddloop = kit.load("fix", "tdd")   # keep-essence 1 の継ぎ目: 修正の段の TDD の輪（integration.md 4.3-3）
        self.assertEqual(tddloop.start(self.tmp / "fix", self.repo, "", "[]")["reason"], tddloop.NO_SUITE)
        self.ok("run", "base")
        prep, tried = self.round(self.RED)
        self.assertTrue(prep["write"])
        self.assertEqual(tried, {"done": True, "ok": True, "why": ""})
        suite = self.state()["tdd_suite"]
        self.assertTrue(pathlib.Path(suite).is_absolute())
        self.assertEqual(self.kept().read_text(encoding="utf-8"), self.RED)
        self.assertEqual((self.run_doc()["selfcheck"]["ran"]["exe"], self.run_doc()["selfcheck"]["ran"]["count"]), (suite, 2))
        out = self.ok("result", "base")
        doc = baseline_red.read_baseline(self.pointed(out["baseline"]))
        self.assertEqual((doc["suite"], doc["exit"]), (suite, 1))
        self.assertEqual(baseline_red.outcomes(doc["cases"]), {"test_a.TestA::test_x": "failure", "test_a.TestA::test_y": "passed"})
        self.assertEqual(out["suite"], suite)
        self.assertIn(suitewrite.WROTE, out["suite_note"])
        self.assertEqual(out["report"][-1], suitewrite.head_note(self.state()))
        self.assertTrue(tddloop.start(self.tmp / "fix", self.repo, suite, "[]")["go"])
        work = self.tmp / "tdd"
        work.mkdir()
        cases, code, why = tddloop.run_suite(suite, self.repo, work, "red")
        self.assertEqual(why, [])
        self.assertEqual(tddloop.red_check(["test_a.py::TestA::test_x"], cases, code, {}), ([], []))
        probs, _ = tddloop.red_check(["test_a.py::TestA::test_y"], cases, code, {})
        self.assertTrue(any("もう通る" in p for p in probs), probs)

    def test_kept_runner_is_used_without_the_writer(self):
        self.put_kept(self.RED)
        self.ok("run", "base")
        prep, tried = self.round()
        self.assertEqual((prep["write"], prep["prompt"], tried["ok"]), (False, "", True))
        self.assertTrue(self.state()["tdd_suite"])
        self.assertEqual(self.state()[suitewrite.KEY]["from"], suitewrite.FROM_KEEP)
        out = self.ok("result", "base")
        self.assertEqual(out["suite"], self.state()["tdd_suite"])
        self.assertIn(suitewrite.USED, out["suite_note"])

    def test_kept_runner_that_fails_the_check_is_dropped_and_rewritten(self):
        """取り置きが照らしを通らなければ捨てて 2 周目で書き直し、書き直した物が通った時だけ取り置き直す。捨てた取り置きのログは残す"""
        self.put_kept(self.EMPTY)
        self.ok("run", "base")
        prep, tried = self.round()
        self.assertEqual((prep["write"], tried), (False, {"done": False, "ok": False, "why": suitewrite.NO_CASES}))
        self.assertFalse(self.kept().exists())
        prep, tried = self.round(self.RED)
        self.assertEqual((prep["write"], tried["ok"]), (True, True))
        self.assertEqual(self.kept().read_text(encoding="utf-8"), self.RED)
        self.assertEqual(self.state()[suitewrite.KEY]["dropped"], suitewrite.NO_CASES)
        gate = self.place("base")
        self.assertTrue((gate / "suite-suite.log").is_file() and (gate / "suite-suite-again.log").is_file())

    def test_runner_without_cases_is_not_bound_and_the_base_has_no_suite(self):
        """照らしが落ちた実行器は結ばず取り置かず、元の結末は実行器の無い run と同じ形（suite が空・1 件ごとの結末を取らない）"""
        self.ok("run", "base")
        _, tried = self.round(self.EMPTY)
        self.assertEqual(tried, {"done": True, "ok": False, "why": suitewrite.NO_CASES})
        self.assertEqual(self.state()["tdd_suite"], "")
        self.assertFalse(self.kept().exists())
        self.assertIsNone(self.run_doc()["suite"])
        out = self.ok("result", "base")
        self.assertTrue(out["ok"])
        self.assertEqual(baseline_red.read_baseline(self.pointed(out["baseline"]))["suite"], "")
        self.assertEqual(out["suite"], "")
        self.assertTrue(out["suite_note"].startswith(suitewrite.NOT_MADE))
        self.assertIn(out["suite_note"], out["report"])

    def test_fallen_writer_leaves_the_not_made_mark(self):
        self.ok("run", "base")
        _, tried = self.round()
        self.assertEqual(tried, {"done": True, "ok": False, "why": suitewrite.NO_REPLY})
        self.assertIn(suitewrite.NO_REPLY, self.ok("result", "base")["suite_note"])

    def test_final_returns_the_port_suite_as_it_is(self):
        self.write_start(tdd_suite="run-tests.sh")
        self.ok("run", "final")
        out = self.ok("result", "final")
        self.assertEqual((out["suite"], out["suite_note"]), ("run-tests.sh", ""))

    def test_given_suite_is_returned_by_the_base_too(self):
        suite = self.tmp / "suite.py"
        suite.write_text("import sys\nopen(sys.argv[1], 'w').write(\"<testsuite><testcase classname='s' name='x'/></testsuite>\")\n",
                         encoding="utf-8")
        self.write_start(tdd_suite=str(suite))
        self.assertIs(self.ok("run", "base")["suite_owed"], False)
        out = self.ok("result", "base")
        self.assertEqual((out["suite"], out["suite_note"]), (str(suite), ""))


class RelatedCase(ScriptCase):
    """持ち主の決め related-tests-only（docs/design/test-gate.md の 14 節）: test_cmd も宣言も無い対象（by role_needed）では、
    TDD の実行器に変更に関わる試験のファイルだけを渡す。test_cmd の道と宣言の道は絞らない"""
    # 第 1 引数の書き先の隣に、環境の合図と後ろの引数を控え、対象の根に fail.flag が在れば 1 件が failure の JUnit XML を書く実行器
    RUNNER = ("#!/bin/sh\nout=$1\nshift\nprintf '%s\\n' \"only=${TDD_SUITE_ONLY:-}\" \"$@\" > \"$(dirname \"$out\")/runner-args.txt\"\n"
              "if [ -f fail.flag ]; then body=\"<failure message='x'/>\"; code=1; else body=''; code=0; fi\n"
              "printf '%s' \"<testsuite><testcase classname='test_stats.TestStats' name='test_mean_of_three'>$body</testcase></testsuite>\" "
              "> \"$out\"\nexit $code\n")

    def setUp(self):
        super().setUp()
        self.runner = self.tmp / "runner.sh"
        self.runner.write_text(self.RUNNER, encoding="utf-8")
        self.runner.chmod(0o755)
        self.write_start(base=self.head, tdd_suite=str(self.runner))

    def touch(self, rel: str = "stats.py") -> None:
        with open(self.repo / rel, "a", encoding="utf-8") as f:
            f.write("\n# touched\n")

    def args(self, mode: str) -> list:
        path = self.place(mode) / "runner-args.txt"
        return path.read_text(encoding="utf-8").splitlines() if path.is_file() else None

    def run_doc(self, mode: str) -> dict:
        return json.loads((self.place(mode) / declared_checks.RUN_FILE).read_text(encoding="utf-8"))

    def test_the_given_runner_gets_only_the_related_test_files(self):
        self.touch()
        out = self.ok("run", "final")
        self.assertEqual(out["by"], declared_checks.ROLE_NEEDED)
        self.assertEqual(self.args("final"), ["only=1", str((self.repo / "test_stats.py").resolve())])
        got = self.run_doc("final")
        self.assertEqual(got["related"]["files"], ["test_stats.py"])
        self.assertTrue(got["related"]["applied"] and not got["related"]["whole"])
        self.assertEqual(got["related"]["ran"], "related")
        self.assertEqual(got["suite"]["exit"], 0)

    def test_the_base_picks_from_the_entry_base_when_it_is_given(self):
        """入口の差分は修正前の版に入っているので、base でも入口の差分の根から触った所が起点になり、final の選びが base の選びを含む"""
        self.touch()
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "entry diff")
        head = git(self.repo, "rev-parse", "HEAD")
        self.write_start(base=head, entry_base=self.head)
        self.ok("run", "base")
        self.assertEqual(self.run_doc("base")["selfcheck"]["plan"], {"how": "related", "files": ["test_stats.py"]})
        self.write_start(entry_base="")
        self.ok("run", "base")
        self.assertEqual(self.run_doc("base")["selfcheck"]["plan"]["how"], "sample", "入口の差分の根が無ければ修正前の版からで、何も触っていない")

    def test_a_change_no_test_depends_on_runs_no_test(self):
        (self.repo / "NOTES.md").write_text("notes\n", encoding="utf-8")
        self.ok("run", "final")
        self.assertIsNone(self.args("final"), "走らせる試験が無いのに実行器を起こした")
        got = self.run_doc("final")
        self.assertEqual((got["suite"], got["related"]["files"], got["related"]["ran"]), (None, [], "none"))

    def test_something_unreadable_near_the_change_runs_the_whole_runner_as_before(self):
        self.touch()
        (self.repo / "widget.js").write_text("export function widget() { return 1 }\n", encoding="utf-8")
        self.ok("run", "final")
        self.assertEqual(self.args("final"), ["only="])
        got = self.run_doc("final")
        self.assertTrue(got["related"]["whole"] and got["related"]["reasons"])
        self.assertEqual(got["related"]["ran"], "whole")

    def test_a_given_test_command_is_the_users_way_and_the_runner_runs_whole(self):
        self.touch()
        self.write_start(test_cmd="true")
        self.assertEqual(self.ok("run", "final")["by"], declared_checks.ROLE)
        self.assertEqual(self.args("final"), ["only="])
        self.assertFalse(self.run_doc("final")["related"]["applied"])

    def test_a_declaration_is_the_users_way_and_the_runner_runs_whole(self):
        self.touch()
        self.decl([{"name": "suite", "argv": [PY, "-c", "print('1 passed')"]}])
        self.write_start(base=self.head, tdd_suite=str(self.runner))
        self.assertEqual(self.ok("run", "final")["by"], declared_checks.ENGINE)
        self.assertEqual(self.args("final"), ["only="])
        self.assertFalse(self.run_doc("final")["related"]["applied"])

    def test_the_writers_runner_is_checked_on_the_related_tests(self):
        """実行器を用意する輪の照らしの回（suite-try）も、関わる試験だけ。書き手の返りは SuiteLoopCase と同じ"""
        self.write_start(tdd_suite="")
        self.touch()
        self.assertIs(self.ok("run", "base")["suite_owed"], True)
        prep = self.ok("suite_prep", "base")
        self.assertTrue(prep["write"])
        self.ok("suite_place", "base", reply=json.dumps({"made": True, "body": self.RUNNER, "why": ""}))
        self.assertEqual(self.ok("suite_try", "base"), {"done": True, "ok": True, "why": ""})
        self.assertEqual(self.args("base"), ["only=1", str((self.repo / "test_stats.py").resolve())])
        self.assertEqual(self.run_doc("base")["selfcheck"]["plan"], {"how": "related", "files": ["test_stats.py"]})

    def test_the_writers_runner_with_nothing_related_is_checked_on_one_sample(self):
        """関わる試験が無くても、直す前は一式を走らせない（持ち主の決め base-selfcheck-only）。実行器が JUnit XML を書く事は、見本の
        試験のファイル 1 つで確かめる"""
        self.write_start(tdd_suite="")
        self.ok("run", "base")
        self.ok("suite_prep", "base")
        self.ok("suite_place", "base", reply=json.dumps({"made": True, "body": self.RUNNER, "why": ""}))
        self.assertEqual(self.ok("suite_try", "base"), {"done": True, "ok": True, "why": ""})
        self.assertEqual(self.args("base"), ["only=1", str((self.repo / "test_stats.py").resolve())])
        self.assertEqual(self.run_doc("base")["selfcheck"]["plan"]["how"], "sample")

    def base_and_final(self, base_fails=False, final_fails=False) -> dict:
        self.touch()
        if base_fails:
            (self.repo / "fail.flag").write_text("", encoding="utf-8")
        self.ok("run", "base")
        base = self.ok("result", "base")
        (self.repo / "fail.flag").unlink(missing_ok=True)
        if final_fails:
            (self.repo / "fail.flag").write_text("", encoding="utf-8")
        self.write_start(baseline=str(self.pointed(base["baseline"])))
        self.ok("run", "final")
        return self.ok("result", "final")

    def test_a_green_from_the_related_run_is_machine_measured_but_not_certified(self):
        out = self.base_and_final()
        self.assertEqual((out["by"], out["green"], out["ok"], out["red_cause"]), (declared_checks.ROLE_NEEDED, True, False, ""))
        self.assertEqual(out["reason"], green_cert.RUNNER_HELD)
        self.assertEqual(out["ran_steps"], {"ran": ["関わる試験の実行器"], "unran": []})
        self.assertEqual(out["related"]["files"], ["test_stats.py"])
        self.assertIn(declared_checks.SELF_REPORTED_NOTE, out["report"])

    def test_a_red_that_was_already_red_is_inherited(self):
        out = self.base_and_final(base_fails=True, final_fails=True)
        self.assertEqual((out["green"], out["ok"], out["red_cause"]), (False, False, green_cert.INHERITED), "赤は原因が何でも認証しない")

    def test_a_red_the_fix_made_is_introduced_and_not_certified(self):
        out = self.base_and_final(final_fails=True)
        self.assertEqual((out["green"], out["ok"], out["red_cause"]), (False, False, green_cert.INTRODUCED))
        self.assertEqual([r["key"] for r in out["test_outcomes"]["rows"]], ["test_stats.TestStats::test_mean_of_three"])

    def test_a_red_outside_the_narrow_base_is_not_called_introduced(self):
        """修正前の確かめが関わる試験だけ（1 件）で、最後の確かめが全部の試験（選べなかった）の時、修正前の結果に無い試験の赤は、直しが
        起こした赤とも元からの赤とも言わない（比べる事実が無い。合格と確定しないのは同じ）"""
        self.touch()
        self.ok("run", "base")
        base = self.ok("result", "base")
        other = self.tmp / "other-runner.sh"
        other.write_text("#!/bin/sh\nprintf '%s' \"<testsuite><testcase classname='test_stats.TestStats' name='test_mean_of_three'/>"
                         "<testcase classname='test_far.TestFar' name='test_far'><failure message='x'/></testcase></testsuite>\" > \"$1\"\nexit 1\n",
                         encoding="utf-8")
        other.chmod(0o755)
        (self.repo / "widget.js").write_text("export function widget() { return 1 }\n", encoding="utf-8")
        # 修正前の版（port base）が無いので走らせ直せない（走らせ直す道は SelfCheckCase）
        self.write_start(baseline=str(self.pointed(base["baseline"])), tdd_suite=str(other), base="")
        self.ok("run", "final")
        out = self.ok("result", "final")
        self.assertTrue(out["related"]["whole"])
        self.assertEqual((out["ok"], out["red_cause"]), (False, ""))

    def test_nothing_related_in_the_final_is_not_a_green(self):
        self.write_start(tdd_suite=str(self.runner))
        self.ok("run", "base")
        base = self.ok("result", "base")
        self.write_start(baseline=str(self.pointed(base["baseline"])))
        self.ok("run", "final")
        out = self.ok("result", "final")
        self.assertEqual((out["green"], out["ok"], out["red_cause"]), (False, False, green_cert.INCOMPLETE))
        self.assertTrue(out["related"]["applied"] and out["related"]["files"] == [])

    def test_a_base_without_a_runner_goes_on_as_awaiting_a_person(self):
        """任せ先の CI の役を外した後の base: 実行器が作れなかった (3) の道は、試験を走らせず、緑を仮定せずに鎖を止めない"""
        self.write_start(tdd_suite="")
        self.touch()
        self.ok("run", "base")
        self.ok("suite_prep", "base")
        self.ok("suite_try", "base")
        out = self.ok("result", "base")
        self.assertEqual((out["ok"], out["green"], out["red_cause"]), (True, False, green_cert.INCOMPLETE))
        doc = baseline_red.read_baseline(self.pointed(out["baseline"]))
        self.assertEqual(doc["material"]["status"], "awaiting_human")
        self.assertTrue(doc["material"]["reason"])
        self.assertFalse((self.place("base") / "ci-material.json").exists())

    def test_a_final_without_a_runner_is_not_run(self):
        self.write_start(tdd_suite="")
        self.touch()
        self.ok("run", "final")
        out = self.ok("result", "final")
        self.assertEqual((out["ok"], out["green"], out["red_cause"]), (False, False, green_cert.INCOMPLETE))
        self.assertEqual(out["ran_steps"], {"ran": [], "unran": ["関わる試験の実行器"]})


class SelfCheckCase(ScriptCase):
    """#828・#836（持ち主の決め base-selfcheck-only。docs/design/test-gate.md の 15 節）: 直す前は全部の試験を回さず、TDD の実行器を
    小さな試験の組で 1 回走らせる自己点検だけをする。工場が用意した実行器が赤で、test_cmd の単体が緑なら、壊れているのは起動スクリプト
    なので、判定を起こす前に止める。最後のテストの赤で元の結末に無い物は、修正前の版で同じ走らせ方を 1 回して、元から赤か直しが壊したかを分ける"""
    # 第 1 引数の書き先の隣に合図と後ろの引数を書き足し、対象の根に red.flag が在れば 1 件を failure にして 1 で抜ける。合図 ONLY が
    # 無い回（一式）だけ test_far も書き、対象の根に far.flag が在ればそれを failure にする
    RUNNER = ("#!/bin/sh\nout=$1\nshift\nprintf '%s\\n' \"only=${TDD_SUITE_ONLY:-}\" \"$@\" >> \"$(dirname \"$out\")/selfcheck-args.txt\"\n"
              "code=0; body=''; far=''\n"
              "if [ -f red.flag ]; then body=\"<failure message='No module named yaml'/>\"; code=1; fi\n"
              "if [ -z \"${TDD_SUITE_ONLY:-}\" ]; then fb=''; if [ -f far.flag ]; then fb=\"<failure message='far'/>\"; code=1; fi\n"
              "  far=\"<testcase classname='test_far.TestFar' name='test_far'>$fb</testcase>\"; fi\n"
              "printf '%s' \"<testsuite><testcase classname='test_stats.TestStats' name='test_mean_of_three'>$body</testcase>$far</testsuite>\" "
              "> \"$out\"\nexit $code\n")

    def setUp(self):
        super().setUp()
        self.runner = self.tmp / "runner.sh"
        self.runner.write_text(self.RUNNER, encoding="utf-8")
        self.runner.chmod(0o755)
        self.declared = {launcher.SUITE_KEEP_ENV: str(self.tmp / "suites")}
        self.write_start(base=self.head)

    def calls(self, mode: str = "base") -> list:
        path = self.place(mode) / "selfcheck-args.txt"
        return path.read_text(encoding="utf-8").splitlines() if path.is_file() else []

    def run_doc(self, mode: str = "base") -> dict:
        return json.loads((self.place(mode) / declared_checks.RUN_FILE).read_text(encoding="utf-8"))

    def kept(self, cmd: str) -> pathlib.Path:
        return self.tmp / "suites" / hashlib.sha256(cmd.encode("utf-8")).hexdigest()

    def written(self, body: str = "") -> dict:
        """輪の 1 周で書き手が body（既定は self.RUNNER）を返し、照らしを通す。suite-try の返り"""
        self.assertTrue(self.ok("suite_prep", "base")["write"])
        self.ok("suite_place", "base", reply=json.dumps({"made": True, "body": body or self.RUNNER, "why": ""}))
        return self.ok("suite_try", "base")

    def test_the_base_runs_neither_the_declared_steps_nor_the_test_cmd(self):
        """#828: 直す前の版で全部の試験（宣言の段と test_cmd）を回さない。最後のテストは今までどおり走らせる"""
        steps, cmd = self.tmp / "steps-ran", self.tmp / "cmd-ran"
        self.decl([{"name": "suite", "argv": [PY, "-c", f"open({str(steps)!r}, 'a').write('1')"]}])
        self.write_start(base=self.head, test_cmd=f"{PY} -c \"open({str(cmd)!r}, 'a').write('1')\"")
        run = self.ok("run", "base")
        out = self.ok("result", "base")
        self.assertFalse(steps.exists() or cmd.exists(), "直す前に宣言の段か test_cmd を走らせた")
        self.assertEqual((run["by"], run["runs"]), (declared_checks.ENGINE, []))
        self.assertEqual((out["ok"], out["green"]), (True, False))
        doc = baseline_red.read_baseline(self.pointed(out["baseline"]))
        self.assertEqual((doc["material"]["status"], doc["cases"], doc["exit"]), ("not_applicable", [], None))
        self.assertIn("自己点検だけ", out["suites_line"])
        self.intake("final")
        self.ok("run", "final")
        self.assertTrue(steps.exists() and cmd.exists(), "最後のテストは宣言の段と test_cmd を走らせる")

    def test_the_given_runner_is_self_checked_on_one_sample_test_file(self):
        """#828: 人が渡した実行器も、直す前は小さな組だけ（関わる試験が無ければ見本の試験のファイル 1 つ）を合図つきで 1 回走らせる"""
        self.write_start(base=self.head, tdd_suite=str(self.runner))
        self.ok("run", "base")
        self.assertEqual(self.calls(), ["only=1", str((self.repo / "test_stats.py").resolve())])
        self.assertEqual(self.run_doc()["selfcheck"]["plan"], {"how": "sample", "files": ["test_stats.py"]})
        out = self.ok("result", "base")
        doc = baseline_red.read_baseline(self.pointed(out["baseline"]))
        self.assertEqual((doc["material"]["status"], doc["exit"], doc["narrow"]), ("clean", 0, True))
        self.assertEqual(baseline_red.outcomes(doc["cases"]), {"test_stats.TestStats::test_mean_of_three": "passed"})

    def test_a_runner_red_while_the_test_cmd_alone_is_green_stops_before_the_judge(self):
        """#836: 工場の書いた実行器の自己点検が赤で、test_cmd の単体が緑で、実行器の一式でも赤なら、壊れているのは起動スクリプト。
        base の ok を偽にして判定の前で止め、訳とログのパスを報告の行の頭と reason に置く。実行器は結ばず、取り置きからも捨てる"""
        (self.repo / "red.flag").write_text("", encoding="utf-8")
        self.write_start(base=self.head, test_cmd="true")
        self.ok("run", "base")
        self.assertEqual(self.written(), {"done": True, "ok": True, "why": ""})
        check = self.run_doc()["selfcheck"]
        self.assertEqual((check["broken"], check["test_cmd"]["status"]), (True, "clean"))
        self.assertFalse(self.kept("true").exists(), "壊れた起動スクリプトが取り置きに残った")
        out = self.ok("result", "base")
        self.assertEqual((out["ok"], out["green"], out["suite"]), (False, False, ""))
        self.assertEqual(check["whole"]["exit"], 1)
        log = str(self.place("base") / "suite-suite-whole.log")
        for text in (out["reason"], out["report"][0]):
            self.assertIn("起動スクリプトが壊れている", text)
            self.assertIn(log, text)
            self.assertIn(check["test_cmd"]["log"], text)
        self.assertTrue(out["report"][0].startswith("直す前の自己点検: "))
        self.assertTrue(out["suite_note"].startswith(suitewrite.NOT_MADE))

    def test_a_red_only_in_the_small_set_is_not_called_broken(self):
        """#836: 組で赤・test_cmd の単体で緑でも、実行器の一式が緑なら、組が test_cmd の外の赤を拾っただけで起動スクリプトは壊れて
        いない。止めない"""
        body = ("#!/bin/sh\nout=$1\nshift\nif [ -n \"${TDD_SUITE_ONLY:-}\" ]; then b=\"<failure message='x'/>\"; c=1; else b=''; c=0; fi\n"
                "printf '%s' \"<testsuite><testcase classname='test_stats.TestStats' name='test_mean_of_three'>$b</testcase></testsuite>\" "
                "> \"$out\"\nexit $c\n")
        self.write_start(base=self.head, test_cmd="true")
        self.ok("run", "base")
        self.written(body)
        check = self.run_doc()["selfcheck"]
        self.assertEqual((check["test_cmd"]["status"], check["whole"]["exit"], check["broken"]), ("clean", 0, False))
        self.assertIs(self.ok("result", "base")["ok"], True)

    def test_a_runner_red_with_the_test_cmd_alone_red_goes_on(self):
        """#836: test_cmd の単体も赤なら試験そのものの赤で、この確かめでは止めない（実行器も結んだまま）"""
        (self.repo / "red.flag").write_text("", encoding="utf-8")
        self.write_start(base=self.head, test_cmd="false")
        self.ok("run", "base")
        self.written()
        check = self.run_doc()["selfcheck"]
        self.assertEqual((check["broken"], check["test_cmd"]["status"]), (False, "found"))
        out = self.ok("result", "base")
        self.assertEqual(out["ok"], True)
        self.assertTrue(out["suite"])
        self.assertTrue(self.kept("false").exists())

    def test_a_green_runner_does_not_run_the_test_cmd(self):
        """#836: 自己点検が緑なら test_cmd を単体で走らせない（直す前に全部の試験を回さない）"""
        cmd = self.tmp / "cmd-ran"
        self.write_start(base=self.head, test_cmd=f"{PY} -c \"open({str(cmd)!r}, 'a').write('1')\"")
        self.ok("run", "base")
        self.written()
        self.assertIsNone(self.run_doc()["selfcheck"]["test_cmd"])
        self.assertFalse(cmd.exists())
        self.assertIs(self.ok("result", "base")["ok"], True)

    def test_a_given_runner_red_does_not_stop_on_the_mismatch(self):
        """人が渡した実行器は人の選びなので、食い違いでは止めない（test_cmd も走らせない）"""
        (self.repo / "red.flag").write_text("", encoding="utf-8")
        self.write_start(base=self.head, test_cmd="true", tdd_suite=str(self.runner))
        self.ok("run", "base")
        out = self.ok("result", "base")
        self.assertEqual((out["ok"], self.run_doc()["selfcheck"]["test_cmd"]), (True, None))

    FLAGS_CMD = "test ! -f far.flag -a ! -f red.flag"   # 実行器と同じ旗で赤になる test_cmd（最後のテストの素材は test_cmd の結果）

    def base_then_final(self) -> dict:
        self.write_start(base=self.head, test_cmd=self.FLAGS_CMD, tdd_suite=str(self.runner))
        self.ok("run", "base")
        base = self.ok("result", "base")
        self.write_start(base=self.head, test_cmd=self.FLAGS_CMD, tdd_suite=str(self.runner), baseline=str(self.pointed(base["baseline"])))
        self.ok("run", "final")
        return self.ok("result", "final")

    def test_a_red_outside_the_base_that_the_fix_made_is_introduced(self):
        """#828: 直す前の結末に無い試験が最後に赤なら、同じ走らせ方を修正前の版で 1 回走らせ、そこで通れば直しが起こした赤"""
        (self.repo / "far.flag").write_text("", encoding="utf-8")   # 追跡していない: 修正前の版の写しには無い
        out = self.base_then_final()
        self.assertEqual((out["ok"], out["green"], out["red_cause"]), (False, False, green_cert.INTRODUCED))
        rows = {r["key"]: (r["base"], r["final"]) for r in out["test_outcomes"]["rows"]}
        self.assertEqual(rows["test_far.TestFar::test_far"], ("passed", "failure"))
        self.assertEqual(self.run_doc("final")["base_rerun"]["rev"], self.head)

    def test_a_red_outside_the_base_that_was_already_red_is_inherited(self):
        """#828: 修正前の版でも同じ試験が赤なら、元から赤（認証はしない）"""
        (self.repo / "far.flag").write_text("", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "far is red before the fix")
        self.head = git(self.repo, "rev-parse", "HEAD")
        out = self.base_then_final()
        self.assertEqual((out["ok"], out["green"], out["red_cause"]), (False, False, green_cert.INHERITED))
        rows = {r["key"]: (r["base"], r["final"]) for r in out["test_outcomes"]["rows"]}
        self.assertEqual(rows["test_far.TestFar::test_far"], ("failure", "failure"))

    def test_a_red_already_in_the_base_is_not_run_again(self):
        """直す前の自己点検の結末に在る赤は、修正前の版で走らせ直さない"""
        (self.repo / "red.flag").write_text("", encoding="utf-8")
        out = self.base_then_final()
        self.assertEqual(out["red_cause"], green_cert.INHERITED)
        self.assertNotIn("base_rerun", self.run_doc("final"))


class PromptCase(ScriptCase):
    """TDD の実行器の書き手の指示（prompts/suite-write.md）に prep が入れる値と、段落の選び（docs/design/test-gate.md の 4.3）"""
    def write_prompt(self, **ports) -> str:
        self.write_start(**ports)
        self.ok("run", "base")
        return self.ok("suite_prep", "base")["prompt"]

    def test_suite_write_prompt_without_test_cmd_or_declaration(self):
        text = self.write_prompt()
        self.assertIn(f"The target root: {self.repo.resolve()}", text)
        self.assertIn(f"has no run declaration `{declared_checks.DECL_NAME}`", text)
        self.assertNotIn("has the run declaration", text)
        self.assertIn("None (the person did not give one).", text)
        self.assertIn(f"`{baseline_red.ONLY_ENV}=1`", text)
        self.assertEqual((self.place("base") / "suite-write-prompt-1.md").read_text(encoding="utf-8"), text)

    def test_suite_write_prompt_with_a_declaration_and_a_test_cmd_that_holds_backticks(self):
        self.decl([{"name": "suite", "argv": [PY, "-c", "pass"]}])
        cmd = "make test ARGS='`x`' ```"
        text = self.write_prompt(test_cmd=cmd)
        self.assertIn(f"has the run declaration `{declared_checks.DECL_NAME}`", text)
        self.assertIn(f"````text\n{cmd}\n````", text)
        self.assertNotIn("None (the person did not give one).", text)

    def test_suite_write_lang(self):
        self.assertIn("in Japanese.", self.write_prompt(lang="Japanese"))


if __name__ == "__main__":
    unittest.main()

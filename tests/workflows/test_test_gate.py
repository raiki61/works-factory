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

    def test_ci_command_keeps_the_rules(self):
        """元 test_blk_ci.py の test_command_is_thin_and_prompts_keep_the_rules: 役の指示書が今の works の決まりを持つ——走らせられなければ
        緑を仮定しない（base は awaiting_human・final は not_run）・走ったかは試験の件数で決める・終わるまで待つ・系統ごとの終了コード・
        自己申告・本物の作業ツリーを変えない"""
        text = (BLOCK / "commands" / "ci.md").read_text(encoding="utf-8")
        for phrase in ("緑を仮定するな", "awaiting_human", "not_run", "試験の件数", "で決めよ", "終わるまで待て", "系統ごとの終了コード",
                       "自己申告", "本物の作業ツリーのファイルを書く・消す"):
            with self.subTest(phrase):
                self.assertIn(phrase, text)

    def test_role_node_matches_works_blk_ci(self):
        """今の works の blk-ci.yaml の役の節の settingSources・sandbox・context と同じ値"""
        ci = node("ci")
        self.assertEqual(ci["settingSources"], ["user"])
        self.assertEqual(ci["context"], "fresh")
        self.assertEqual(ci["sandbox"], {"enabled": True, "allowUnsandboxedCommands": False, "failIfUnavailable": True,
                                         "enableWeakerNetworkIsolation": True,
                                         "network": {"allowedDomains": ["*"], "allowLocalBinding": True},
                                         "filesystem": {"allowWrite": ["/"], "denyWrite": ["."]}})
        self.assertEqual(ci["output_format"]["properties"]["material"], declared_checks.MATERIAL_SCHEMA)

    def test_role_cannot_write_the_checkout(self):
        """元 ci_role.fence の書き込みの守り: 役の砂場は run の作業ツリー（役の cwd。砂場は相対のパスを cwd から読む）への書き込みを塞ぎ、
        写しの置き場（一時の置き場の直下）は書けるまま。読むだけの節の印 mutates_checkout: false も外さない"""
        ci = node("ci")
        self.assertEqual(ci["sandbox"]["filesystem"], {"allowWrite": ["/"], "denyWrite": ["."]})
        self.assertIs(ci["mutates_checkout"], False)

    def test_run_material_is_the_material_schema_or_null(self):
        material = node("run")["output_format"]["properties"]["material"]
        self.assertEqual(material["type"], ["object", "null"])
        self.assertEqual({**material, "type": "object"}, declared_checks.MATERIAL_SCHEMA)

    def test_loop_matches_give_up(self):
        loop = node("ci-loop")
        self.assertEqual(loop["when"], "$run.output.by == 'role_needed'")
        self.assertIs(loop["loop_group"]["fresh_context"], True)
        self.assertIn("$ci-accept.output.done", loop["loop_group"]["until_bash"])
        self.assertEqual(loop["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER)

    def test_loop_does_not_paste_previous_reject_by_loop_prev(self):
        """前の回の拒否の文は $LOOP_PREV で with: に貼らない（元の裁定 R44）: Archon は with: の値を $LOOP_PREV で置き換えた後に
        もう 1 度 $<節>.output.<欄> を置き換えるので、拒否の文に節の参照の字が在ると輪が落ちる。ci-prep が拒否の控えから読む"""
        for n in node("ci-loop")["loop_group"]["nodes"]:
            with self.subTest(n["id"]):
                self.assertNotIn("$LOOP_PREV", json.dumps(n.get("with") or {}))

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
                "open('r.xml', 'w').write('<testsuite/>'); "
                f"open({str(pidfile)!r}, 'w').write(str(p.pid)); time.sleep(120)")
        self.decl([{"name": "suite", "argv": [PY, "-c", body], "junit": "r.xml"}])
        before = green_cert.fingerprint(self.repo)
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
        out = self.ok("run", mode="base", start=self.start)
        self.assertFalse((self.repo / "out" / "r.xml").exists())
        self.assertEqual((self.artifacts / "test-gate" / "base" / "junit" / "1.xml").read_text(encoding="utf-8"), report)
        self.assertEqual((out["fingerprint_before"], out["fingerprint_after"]), (before, before))
        self.assertEqual(green_cert.fingerprint(self.repo), before)
        self.assertEqual((out["by"], out["material"]["status"], out["junit_steps"]), ("engine", "clean", ["suite"]))
        self.assertEqual(sorted(out), sorted(node("run")["output_format"]["required"]))

    def scoped(self):
        """種に far・near の宣言と、far が works/ を見ない範囲の宣言を commit する"""
        (self.repo / ".works-checks.json").write_text('{"far": {"paths_ignore": ["works/"]}}', encoding="utf-8")
        self.decl([{"name": "far", "argv": [PY, "-c", "print('far')"]}, {"name": "near", "argv": [PY, "-c", "print('near')"]}])

    def test_archon_workspace_is_not_a_change(self):
        """元 test_blk_tests_delta.py の test_final_does_not_count_archon_workspace_as_change: Archon が作業ツリーに置く .archon/ の下は
        範囲と照らす変更に数えない"""
        self.scoped()
        (self.repo / "works").mkdir()
        (self.repo / "works" / "a.py").write_text("x\n", encoding="utf-8")
        (self.repo / ".archon").mkdir()
        (self.repo / ".archon" / "x.yaml").write_text("x: 1\n", encoding="utf-8")
        out = self.ok("run", mode="base", start=self.start)
        self.assertEqual(out["skipped_steps"], [{"name": "far", "paths_ignore": ["works/"]}])

    def test_base_reads_request_where_as_change(self):
        """元 entry.scope_changed の _pr_files: 判定から入る run（入口の差分が空）の base は、依頼の where が名指す追跡中のパスも
        変更に足す。where が全部 far の見ない所なら base で far を回さない。final は where を足さない（変更の無い final は絞らない）"""
        (self.repo / "works").mkdir()
        (self.repo / "works" / "a.py").write_text("x\n", encoding="utf-8")
        self.scoped()
        request = self.tmp / "request.json"
        request.write_text(json.dumps({"findings": [{"where": "works/a.py:1", "text": "x"}]}), encoding="utf-8")
        self.write_start(request_file=str(request), input={"diff": {"empty": True}})
        self.assertEqual(self.ok("run", mode="base", start=self.start)["skipped_steps"],
                         [{"name": "far", "paths_ignore": ["works/"]}])
        self.assertEqual(self.ok("run", mode="final", start=self.start)["skipped_steps"], [])
        self.write_start(request_file=str(request), input={"diff": {"empty": False}})
        self.assertEqual(self.ok("run", mode="base", start=self.start)["skipped_steps"], [])

    def test_rerun_keeps_earlier_logs(self):
        """元 test_board_engine_run.py の test_rerun_keeps_earlier_logs: 同じ run で同じ形を呼び直しても前の走りのログを上書きしない
        （空いた番号の置き場 logs/a<k>/）。前の回の素材・拒否・記録は消す（今回の物として読まない）"""
        self.decl([{"name": "suite", "argv": [PY, "-c", "print('ran')"]}])
        gate = self.artifacts / "test-gate" / "base"
        first = self.ok("run", mode="base", start=self.start)
        for name in ("ci-material.json", "rejects-ci.json"):
            (gate / name).write_text("{}", encoding="utf-8")
        second = self.ok("run", mode="base", start=self.start)
        self.assertEqual((gate / "logs" / "a1" / "1.out").read_text(encoding="utf-8"), "ran\n")
        self.assertEqual((gate / "logs" / "a2" / "1.out").read_text(encoding="utf-8"), "ran\n")
        self.assertEqual((pathlib.Path(first["log"]).parent.name, pathlib.Path(second["log"]).parent.name), ("a1", "a2"))
        self.assertFalse((gate / "ci-material.json").exists())
        self.assertFalse((gate / "rejects-ci.json").exists())

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
        """ci_prep を回す。reject が在れば、前の回の受け付けが拒んだ控え（ci_accept が積む物）に先に積む"""
        if reject:
            gate = self.artifacts / "test-gate" / "base"
            gate.mkdir(parents=True, exist_ok=True)
            rolekit.with_done(gate, declared_checks.CI_ROLE, {"ok": False, "reason": reject})
        out = self.ok("ci_prep", mode="base", start=self.start)
        top = pathlib.Path(out["copy_dir"]).parent
        self.addCleanup(lambda: top.exists() and __import__("shutil").rmtree(top, ignore_errors=True))
        return out

    def test_prep_copies_tree_and_passes_reject(self):
        (self.repo / "new.txt").write_text("未追跡\n", encoding="utf-8")
        out = self.prep(reject="前の理由")
        self.assertEqual((out["mode"], out["reject"], out["attempt"], out["root"]), ("base", "前の理由", 2, str(self.repo.resolve())))
        self.assertEqual((pathlib.Path(out["copy_dir"]) / "new.txt").read_text(encoding="utf-8"), "未追跡\n")
        self.assertTrue(pathlib.Path(out["tmp_dir"]).is_dir())

    def test_reject_with_a_reference_reaches_the_prompt_verbatim(self):
        """前の回の拒否の文は、節の参照の字（$ci.output.material・$INPUTS.mode）を含んでも字のまま次の回の reject に載る。
        1 回目は reject が空"""
        first = self.prep()
        self.assertEqual((first["reject"], first["attempt"]), ("", 1))
        reason = "欄を直せ: $ci.output.material と $INPUTS.mode"
        again = self.prep(reject=reason)
        self.assertEqual((again["reject"], again["attempt"]), (reason, 2))

    def test_unreadable_reply_is_a_reject(self):
        """元 test_blk_ci.py の test_unreadable_reply_is_a_reject: 読めない返答（JSON でない・オブジェクトでない）は受け付けの拒否として
        数え、理由を次の回へ渡す"""
        for raw, word in (("not json", "JSON"), ("[1]", "オブジェクトでない")):
            with self.subTest(raw):
                self.prep()
                got = self.ok("ci_accept", mode="base", reply=raw)
                self.assertEqual((got["ok"], got["done"]), (False, False))
                self.assertIn(word, got["reason"])
                self.assertIn(word, self.prep()["reject"])
                rolekit.rejects_path(self.artifacts / "test-gate" / "base", declared_checks.CI_ROLE).unlink()

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

    def test_retry_keeps_the_first_snapshot(self):
        """出し直しの回の ci-prep は役を起こす前の姿を置き換えない: 1 回目の役が変えた作業ツリーは 2 回目も拒む"""
        self.prep()
        (self.repo / "new.txt").write_text("x\n", encoding="utf-8")
        self.assertFalse(self.ok("ci_accept", mode="base", reply=self.GOOD)["ok"])
        self.prep()
        got = self.ok("ci_accept", mode="base", reply=self.GOOD)
        self.assertFalse(got["ok"])
        self.assertIn("new.txt", got["reason"])

    def test_status_guarded_leaves_index_only_change_to_the_status_check(self):
        """with: の status_guarded が真の受け付けは、Archon の状態の照らし（git status の行の違い）が見る index だけの変化では
        拒まない。印が無ければ今どおり全部の欄を比べて拒む"""
        with open(self.repo / "stats.py", "a", encoding="utf-8") as f:
            f.write("# 前から在った変更\n")
        self.prep()
        git(self.repo, "add", "stats.py")
        got = self.ok("ci_accept", mode="base", reply=self.GOOD)
        self.assertFalse(got["ok"])
        self.assertIn("git status --porcelain", got["reason"])
        got = self.ok("ci_accept", mode="base", reply=self.GOOD, status_guarded="true")
        self.assertEqual((got["ok"], got["done"]), (True, True), got)

    def test_status_guarded_still_sees_rewrite_of_dirty_file(self):
        """status_guarded でも、git status の行が同じままの既に変わっていたファイルの書き換えは拒む（照らしが見ない所）"""
        with open(self.repo / "stats.py", "a", encoding="utf-8") as f:
            f.write("# 前から在った変更\n")
        self.prep()
        with open(self.repo / "stats.py", "a", encoding="utf-8") as f:
            f.write("# 役が書いた\n")
        got = self.ok("ci_accept", mode="base", reply=self.GOOD, status_guarded="true")
        self.assertFalse(got["ok"])
        self.assertIn("中身が変わった", got["reason"])

    def test_done_removes_only_its_own_copy_folder(self):
        """終わった時に消すのは一時の置き場の直下の写しの頭のフォルダだけ（symlink は辿らない）。役が書ける snapshot の top が
        別の所を指しても消さない"""
        top = pathlib.Path(self.prep()["copy_dir"]).parent
        elsewhere = self.tmp / top.name                                   # 写しと同じ名で、一時の置き場の直下でない
        elsewhere.mkdir()
        (elsewhere / "keep.txt").write_text("x\n", encoding="utf-8")
        link = pathlib.Path(tempfile.gettempdir()) / f"{top.name}-link"  # 一時の置き場の直下の、写しを指す symlink
        link.symlink_to(top)
        self.addCleanup(link.unlink)
        snap_path = self.artifacts / "test-gate" / "base" / "ci-snapshot.json"
        for pointed, kept in ((elsewhere, elsewhere / "keep.txt"), (link, top / "work")):
            with self.subTest(str(pointed)):
                snap = json.loads(snap_path.read_text(encoding="utf-8"))
                snap_path.write_text(json.dumps({**snap, "top": str(pointed)}), encoding="utf-8")
                self.assertTrue(self.ok("ci_accept", mode="base", reply=self.GOOD)["done"])
                self.assertTrue(kept.exists())

    def test_rejected_reply_leaves_no_material_the_role_wrote(self):
        """拒んだ回は、役が run の置き場に自分で置いた ci-material.json を消す（返す節が受け付けていない素材を読まない）"""
        self.prep()
        material = self.artifacts / "test-gate" / "base" / "ci-material.json"
        material.write_text(json.dumps({"material": {"status": "clean", "checked": "x"}}), encoding="utf-8")
        self.assertFalse(self.ok("ci_accept", mode="base", reply=self.BAD)["ok"])
        self.assertFalse(material.exists())

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

    def test_final_evidence_names_the_tests_before_the_fix(self):
        """final の証拠は修正前のテストの行（元 entry.baseline_line）を出す: 修正前は赤で、段ごとの終了コードと、最後の赤は修正前から
        在りうること。元の結末が無い final は記録が無いと書く"""
        text = self.pointed(self.final(self.base())["evidence"]).read_text(encoding="utf-8")
        line = next(l for l in text.splitlines() if "修正前のテスト" in l)
        self.assertIn("修正前のテスト: 赤", line)
        self.assertIn('{"suite": 1}', line)
        self.assertIn("最後のテストの赤は修正前から在りうる", line)
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

    def test_suite_without_cases_leaves_no_baseline_exit(self):
        """tdd_suite が JUnit を書かずに落ちた base は元の結末の exit を残さない。final はそれを「元の結末が無い」と読み、今の赤を
        今回入れた物に数えない"""
        suite = self.tmp / "suite.py"
        suite.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
        self.write_start(tdd_suite=str(suite), test_cmd="false")
        self.ok("run", mode="base", start=self.start)
        out = self.result("base")
        self.assertIsNone(baseline_red.read_baseline(self.pointed(out["baseline"]))["exit"])
        suite.write_text("import sys\nopen(sys.argv[1], 'w').write(\"<testsuite><testcase classname='s' name='x'>"
                         "<failure/></testcase></testsuite>\")\nsys.exit(1)\n", encoding="utf-8")
        out = self.final(json.dumps(out["baseline"]))
        self.assertEqual((out["ok"], out["red_cause"]), (False, ""))

    def test_role_clean_material_written_by_ci_accept_is_read(self):
        """任せ先の役の素材は ci-accept が書いた所から result が読む: 受け付けた clean の base は ok"""
        self.assertEqual(self.ok("run", mode="base", start=self.start)["by"], "role_needed")
        prep = self.ok("ci_prep", mode="base", start=self.start)
        self.addCleanup(__import__("shutil").rmtree, pathlib.Path(prep["copy_dir"]).parent, True)
        clean = json.dumps({"material": {"status": "clean", "checked": "make test: exit 0"}})
        self.assertTrue(self.ok("ci_accept", mode="base", reply=clean)["ok"])
        out = self.result("base")
        self.assertEqual((out["ok"], out["green"], out["red_cause"]), (True, True, ""))

    def test_final_role_green_is_self_reported_and_not_certified(self):
        """final で任せ先の役が書いた緑は、機械が走らせていない自己申告として認証しない（元 run_tests.run_final の role_needed・
        review-loop.py の ci_unverified）"""
        self.assertEqual(self.ok("run", mode="final", start=self.start)["by"], "role_needed")
        gate = self.artifacts / "test-gate" / "final"
        (gate / "ci-material.json").write_text(json.dumps({"material": {"status": "clean", "checked": "make test: exit 0"}}),
                                               encoding="utf-8")
        out = self.result("final")
        self.assertEqual((out["ok"], out["green"], out["red_cause"]), (False, True, ""))
        self.assertIn(green_cert.SELF_REPORTED, self.pointed(out["evidence"]).read_text(encoding="utf-8"))

    def test_copy_left_by_a_fallen_role_is_removed(self):
        """役の節が落ちて ci-accept が回らなくても、返す節が ci-snapshot.json の写しの置き場を消す"""
        self.ok("run", mode="final", start=self.start)
        top = pathlib.Path(self.ok("ci_prep", mode="final", start=self.start)["copy_dir"]).parent
        self.addCleanup(__import__("shutil").rmtree, top, True)
        self.result("final")
        self.assertFalse(top.exists())

    def test_rerun_in_the_same_run_does_not_read_the_earlier_material(self):
        """同じ run で同じ形をもう 1 度差し込んだ時、前の回の任せ先の素材で今の木を認証しない"""
        self.ok("run", mode="final", start=self.start)
        gate = self.artifacts / "test-gate" / "final"
        (gate / "ci-material.json").write_text(json.dumps({"material": {"status": "clean", "checked": "x"}}), encoding="utf-8")
        (self.repo / "later.txt").write_text("x\n", encoding="utf-8")
        self.ok("run", mode="final", start=self.start)
        out = self.result("final")
        self.assertEqual((out["ok"], out["green"], out["red_cause"]), (False, False, "incomplete"))

    def test_shell_test_cmd_names_how_it_was_launched(self):
        """宣言が無く test_cmd だけを走らせた回の証拠は、test_cmd の起こし方（shell）を書く"""
        self.write_start(test_cmd="echo a | cat")
        self.assertEqual(self.ok("run", mode="base", start=self.start)["by"], "role")
        out = self.result("base")
        self.assertIn("走らせた: test_cmd（shell）", self.pointed(out["evidence"]).read_text(encoding="utf-8"))

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

    def test_lib_that_cannot_be_imported_returns_incomplete_without_failing(self):
        """lib の import が落ちても、返す節は終了の値 0 で約束の形の偽の結末と、誤りを名指した証拠を返す"""
        nowhere = self.tmp / "no-root"
        done = subprocess.run([PY, str(SCRIPTS / "result.py")], cwd=self.repo, timeout=WAIT,
                              env={**self.env({"mode": "base", "start": self.start, "baseline": ""}), "WORKS_FACTORY_ROOT": str(nowhere)},
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        self.assertEqual(schema_problems(out, self.output_format), [], out)
        self.assertEqual((out["mode"], out["ok"], out["green"], out["red_cause"]), ("base", False, False, "incomplete"))
        self.assertIn("ModuleNotFoundError", self.pointed(out["evidence"]).read_text(encoding="utf-8"))


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

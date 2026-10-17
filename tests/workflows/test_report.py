"""報告のブロック（workflows/report/）の試験。書き手のループのサブグラフ（workflows/report-write/）は test_report_write.py。

- YAML の形: PyYAML で読み、Archon を起こさない（返す節の約束の欄・入力・書き手のループの fan_out の形）
- 部品と script: scripts/facts.py の一覧の読みを一時の一覧で回し、facts.py・write_out.py・collect.py を子のプロセスで走らせる
  （一時の ARTIFACTS_DIR と環境変数。Archon を起こさない）
- 筋書き: tests/archon.py の使い捨ての木で fixtures/ を archon workflow test で回す。Archon の源か bun が無ければ名前つきで見送る
- 本物の run: 同じ使い捨ての木で試しの工程を 1 回だけ本当に回し（dry-run でない）、実行基盤が書いた run の記録と型つきの
  成果物の一覧を読む部品に読ませる。報告のブロックも本物で回し、書き手の役が落ちても run が completed で終わり、機械の報告に
  AI の本文が無い訳が載ることを見る（#702）
"""
import ast
import importlib.util
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
from tests.workflows import test_plan_review as plan_review

ROOT = pathlib.Path(__file__).resolve().parents[2]
BLOCK = ROOT / "workflows" / "report"
SCRIPTS = BLOCK / "scripts"
WRITE_BLOCK = ROOT / "workflows" / "report-write"
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
if str(LIB / "graphloops") not in sys.path:
    sys.path.append(str(LIB / "graphloops"))

import converge  # noqa: E402
import declared_checks  # noqa: E402
import gatemarks  # noqa: E402
import outcome  # noqa: E402
import report  # noqa: E402
import report_roles  # noqa: E402
import runreport  # noqa: E402
import userenv  # noqa: E402
from engine.schema import validate_schema  # noqa: E402
from lib.tests.test_outcome import fixed_run  # noqa: E402

WORKFLOW = yaml.safe_load((BLOCK / "works-factory-report.yaml").read_text(encoding="utf-8"))
NODES = {n["id"]: n for n in WORKFLOW["nodes"]}
INPUTS = ("start", "test-gate-base", "judge", "rejudge", "plan", "plan-review", "replan", "replan-review", "fix", "test-gate-final",
          "eyes", "merge-seal", "merge-apply", "gate-start", "gate-before-fix", "gate-replan", "gate-final", "stops", "prior-failures",
          "deferred", "widened", "final-reasons", "spec-changed", "spec-unchecked", "redepth", "optional", "notices")
RETURN_FIELDS = {"outcome", "stop_reason", "report", "report_ai", "next_request", "prior_failures", "ok"}
TOP_KEYS_DROPPED_ON_INCLUDE = ("interactive", "worktree", "container", "evidence_policy", "mutates_checkout")
RUN = "run-test"

def load_script(name: str, scripts: pathlib.Path = SCRIPTS):
    spec = importlib.util.spec_from_file_location(f"{scripts.parent.name}_block_{name}", scripts / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


def env_reads(script: str) -> dict:
    """script の頭の、入力の名 → 読む環境変数の名（RETURNS・GATES・LINE の dict と START の os.environ.get の字）"""
    reads = {}
    for node in ast.parse((SCRIPTS / f"{script}.py").read_text(encoding="utf-8")).body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
            continue
        name, value = node.targets[0].id, node.value
        pairs = (zip(value.keys, value.values) if isinstance(value, ast.Dict) and name in ("RETURNS", "GATES", "LINE")
                 else [(ast.Constant("start"), value)] if name == "START" else [])
        for key, call in pairs:
            reads[key.value] = call.args[0].value
    return reads


if str(ROOT / "workflows" / ".shared") not in sys.path:
    sys.path.append(str(ROOT / "workflows" / ".shared"))
facts_script = load_script("facts")


class ShapeCase(unittest.TestCase):
    def test_name_and_returns(self):
        self.assertEqual(WORKFLOW["name"], "works-factory-report")
        self.assertEqual(WORKFLOW["returns"], "report")
        self.assertEqual(WORKFLOW["outcome_field"], "ok")

    def test_return_fields_are_the_contract(self):
        schema = NODES["report"]["output_format"]
        self.assertEqual(set(schema["properties"]), RETURN_FIELDS)
        self.assertEqual(set(schema["required"]), RETURN_FIELDS)
        self.assertIs(schema["additionalProperties"], False)
        self.assertEqual(tuple(schema["properties"]["outcome"]["enum"]), report.OUTCOMES)
        self.assertEqual(schema["properties"][WORKFLOW["outcome_field"]]["type"], "boolean")

    def test_inputs_are_the_contract(self):
        self.assertEqual(tuple(WORKFLOW["inputs"]), INPUTS)
        self.assertTrue(all(v == {"default": ""} for v in WORKFLOW["inputs"].values()))

    def test_facts_reads_every_input_by_its_own_name(self):
        """facts の読む入力が YAML の inputs と同じで、どれも自分の名の環境変数から読む。outcome の関所の並びは inputs の gate-*"""
        reads = env_reads("facts")
        self.assertEqual(reads, {name: f"INPUTS_{name.upper().replace('-', '_')}" for name in WORKFLOW["inputs"]})
        self.assertEqual(outcome.GATES, tuple(name for name in WORKFLOW["inputs"] if name.startswith("gate-")))

    def test_no_top_keys_dropped_on_include(self):
        for key in TOP_KEYS_DROPPED_ON_INCLUDE:
            self.assertNotIn(key, WORKFLOW)

    def test_every_node_leaves_the_checkout_alone(self):
        for nid, node in NODES.items():
            if "include" in node:
                continue
            with self.subTest(nid):
                self.assertIs(node.get("mutates_checkout"), False)

    def test_writer_loop_runs_as_one_item_fan_out_that_absorbs_its_fall(self):
        """#702: 書き手のループは別のサブグラフを 1 つの項目の fan_out（join: all_done）で回す。直に include した節が落ちると run は
        failed で終わるが、fan_out の中の落ちは出力の配列の印になる。項目は機械の事実のファイルで、ほかの入力は facts の出力"""
        write = NODES["write"]
        self.assertEqual(write["include"], "works-factory-report-write")
        self.assertEqual(write["fan_out"], {"items": '["$facts.output.facts_file"]', "as": "facts_file", "max_parallel": 1,
                                            "join": "all_done"})
        self.assertEqual(write["when"], "$facts.output.ai_go == 'true'")
        self.assertEqual(write["with"], {name: f"$facts.output.{name}" for name in ("outcome", "stop_reason", "lang_line")})
        inner = yaml.safe_load((WRITE_BLOCK / "works-factory-report-write.yaml").read_text(encoding="utf-8"))
        self.assertEqual(set(inner["inputs"]), {write["fan_out"]["as"], *write["with"]})
        relay = NODES["write-out"]
        self.assertEqual((relay["depends_on"], relay["with"], relay.get("trigger_rule")), (["write"], {"got": "$write.output"}, None))

    def test_return_node_runs_whatever_came_before(self):
        self.assertEqual(NODES["report"]["trigger_rule"], "all_done")
        self.assertEqual(NODES["report"]["depends_on"], ["facts", "write-out"])
        self.assertEqual(NODES["report"]["with"]["write"], {"from": "$write-out.output", "if_skipped": None})



class TypedCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)

    def entry(self, node, path, body, loop=None, run=RUN):
        (self.dir / path).parent.mkdir(parents=True, exist_ok=True)
        (self.dir / path).write_text(json.dumps(body), encoding="utf-8")
        row = {"nodeId": node, "outputType": "x", "path": path, "runId": run, "producedAt": "2026-10-12T00:00:00.000Z", "size": 1}
        if loop:
            row["loopGroupPath"] = [{"groupId": g, "iteration": i} for g, i in loop]
        return row

    def listing(self, by_type, errors=(), run=RUN):
        path = self.dir / "listing.json"
        path.write_text(json.dumps({"runId": run, "artifactsByType": by_type, "errors": list(errors)}), encoding="utf-8")
        return str(path)

    def read(self, listing, execution=""):
        return facts_script.listing(listing, str(self.dir), RUN, execution)

    def test_groups_by_include_and_loop_keep_rounds_and_drop_others(self):
        rows = [self.entry("fix__tdd", "nodes/a.md", [{"group_id": "g1"}], loop=[("fix__loop", 1)]),
                self.entry("fix__tdd", "nodes/b.md", [{"group_id": "g1"}], loop=[("fix__loop", 2)]),
                self.entry("refix__tdd", "nodes/c.md", [{"group_id": "g2"}]),
                self.entry("fix__tdd", "nodes/d.md", [], run="other-run"),
                self.entry("report__x", "nodes/e.md", {})]
        got = self.read(self.listing({"tdd-unit": rows}), json.dumps({"path": "report__facts"}))
        units = got["by_type"]["tdd-unit"]
        self.assertEqual([(u["include"], u["loop"]) for u in units],
                         [("fix", [("fix__loop", 1)]), ("fix", [("fix__loop", 2)]), ("refix", [])])
        self.assertEqual(units[0]["body"], [{"group_id": "g1"}])
        self.assertEqual(got["warnings"], [])

    def test_nested_include_drops_only_its_own_rows(self):
        """入れ子の include の節の id は outer__inner__node（Archon の include-expander の名前空間）"""
        rows = [self.entry("outer__fix__tdd", "nodes/a.md", {}), self.entry("outer__report__x", "nodes/b.md", {})]
        got = self.read(self.listing({"k": rows}), json.dumps({"path": "outer__report__facts"}))
        self.assertEqual([u["node"] for u in got["by_type"]["k"]], ["outer__fix__tdd"])

    def test_own_prefix_is_the_full_namespace(self):
        self.assertEqual(facts_script.own_prefix(json.dumps({"path": "outer__report__facts"})), "outer__report__")
        self.assertEqual(facts_script.own_prefix(json.dumps({"path": "report__facts"})), "report__")
        self.assertEqual(facts_script.own_prefix(json.dumps({"path": "facts"})), "")

    def test_errors_each_become_a_warning(self):
        errors = [{"path": "nodes/x.meta.json", "kind": "invalid_metadata"}, {"path": "nodes", "kind": "unreadable_directory", "code": "EACCES"}]
        got = self.read(self.listing({}, errors))
        self.assertEqual(len(got["warnings"]), 2)
        self.assertIn("invalid_metadata", got["warnings"][0])
        self.assertIn("EACCES", got["warnings"][1])

    def test_named_limits_without_raising(self):
        cases = {"": "TYPED_ARTIFACTS_FILE が空", str(self.dir / "none.json"): "読めない"}
        bad = self.dir / "bad.json"
        bad.write_text("{壊れた", encoding="utf-8")
        cases[str(bad)] = "読めない"
        cases[self.listing("配列でない")] = "artifactsByType がオブジェクトでない"
        cases[self.listing({"tdd-unit": {"a": 1}})] = "配列でない"
        for listing, word in cases.items():
            with self.subTest(listing=listing):
                got = self.read(listing)
                self.assertEqual(len(got["warnings"]), 1, got)
                self.assertIn(word, got["warnings"][0])

    def test_unreadable_content_is_named(self):
        row = self.entry("eyes__r1", "nodes/r1.md", {})
        (self.dir / "nodes/r1.md").write_text("JSON でない", encoding="utf-8")
        got = self.read(self.listing({"eye-verdict": [row]}))
        self.assertIsNone(got["by_type"]["eye-verdict"][0]["body"])
        self.assertIn("nodes/r1.md", got["warnings"][0])


class Run(unittest.TestCase):
    """script を子のプロセスで走らせる（一時の run の置き場と、Archon が渡すのと同じ名の環境変数）"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)
        self.artifacts = self.dir / "artifacts"
        self.artifacts.mkdir()

    def run_script(self, name: str, scripts: pathlib.Path = SCRIPTS, **env) -> tuple[int, dict]:
        base = hermetic.child_env(**{"ARTIFACTS_DIR": str(self.artifacts), "WORKFLOW_ID": RUN, "TYPED_ARTIFACTS_FILE": "", "LOG_DIR": "",
                                     "WORKS_FACTORY_ROOT": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1", **env})
        done = subprocess.run([sys.executable, str(scripts / f"{name}.py")], env=base, capture_output=True, text=True,
                              encoding="utf-8")
        lines = [line for line in done.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, f"JSON 1 つを出す: {done.stdout}{done.stderr}")
        return done.returncode, json.loads(lines[0])

    def pointer(self, rel: str, doc) -> str:
        path = self.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return json.dumps({"type": "archon_artifact", "run_id": RUN, "path": rel})


class FactsCase(Run):
    def test_empty_inputs_are_record_invalid_and_exit_zero(self):
        code, out = self.run_script("facts")
        self.assertEqual(code, 0)
        self.assertEqual(out["outcome"], "record_invalid")
        self.assertIs(out["ai_go"], False)
        text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
        self.assertIn("始めの記録（入力 start）が届いていない", text)
        self.assertTrue(out["stamp"].endswith(" / メイングラフの版 読めない（始めの記録が読めない）"), out["stamp"])
        self.assertIn("TYPED_ARTIFACTS_FILE が空", text)
        self.assertIn("LOG_DIR", text)

    def test_users_env_sentence_only_with_the_marker(self):
        """#504: 起動の殻を通った run（いつも控えが在る）でも、対象のコマンドを利用者の HOME・XDG に戻して起こした印（メイングラフの run の
        置き場の userenv.RAN_FILE）が無ければ、報告の冒頭は利用者の環境で走らせたと言わない（対象のコマンドの前に止まった run）"""
        opted = {userenv.RECORD: userenv.record({"HOME": "/u"})}
        text = (self.artifacts / self.run_script("facts", **opted)[1]["facts_file"]).read_text(encoding="utf-8")
        self.assertNotIn(userenv.NOTE, text)
        (self.artifacts / userenv.RAN_FILE).touch()
        text = (self.artifacts / self.run_script("facts", **opted)[1]["facts_file"]).read_text(encoding="utf-8")
        self.assertIn(userenv.NOTE, text)

    def test_fallen_report_says_users_env_with_the_marker(self):
        """#504: 思わぬ誤りで落ちた報告も、印（userenv.RAN_FILE）が在れば冒頭で利用者の環境で走らせたと言う（起動の 1 行が冒頭を指す）"""
        with mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(self.artifacts), "WORKFLOW_ID": RUN, "INPUTS_OUT_DIR": ""}):
            for marked in (False, True):
                with self.subTest(marked=marked):
                    if marked:
                        (self.artifacts / userenv.RAN_FILE).touch()
                    out = facts_script.fallen(RuntimeError("壊れた"))
                    text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
                    self.assertEqual(userenv.NOTE in text, marked)

    def test_broken_inputs_and_missing_pointer_do_not_fall(self):
        code, out = self.run_script("facts", INPUTS_START=json.dumps({"type": "archon_artifact", "run_id": RUN, "path": "start/none.json"}),
                                    INPUTS_JUDGE="{壊れた", INPUTS_PLAN="[1, 2]", INPUTS_FIX="null", INPUTS_GATE_FINAL="",
                                    WORKFLOW_ID=RUN, LOG_DIR=str(self.dir))
        self.assertEqual(code, 0)
        self.assertEqual(out["outcome"], "record_invalid")
        text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
        self.assertIn("入力 judge が JSON でない", text)
        self.assertIn("入力 plan が JSON のオブジェクトでない", text)
        self.assertIn("始めの記録を開けない", text)
        self.assertTrue(out["stamp"].endswith(" / メイングラフの版 読めない（始めの記録が読めない）"), out["stamp"])
        self.assertIn(f"run の記録 {self.dir / RUN}.jsonl が読めない", text)

    def test_unexpected_error_still_returns(self):
        """思わぬ誤り（ここでは run の置き場がファイル）でも 0 で終わり、record_invalid と誤りの 1 行を返す"""
        blocker = self.dir / "file"
        blocker.write_text("", encoding="utf-8")
        code, out = self.run_script("facts", ARTIFACTS_DIR=str(blocker))
        self.assertEqual(code, 0)
        self.assertEqual(out["outcome"], "record_invalid")
        self.assertTrue(out["stop_reason"].startswith("report:報告の事実を組めなかった"))

    def test_lang_line_reaches_the_writer(self):
        """L-E37: 始めの記録の lang が、報告の書き手の役の文の頭に言語の 1 行（rolekit.lang_line。判定・計画・修正・独立の目と同じ口）
        として届く。始めの記録が読めない・思わぬ誤りの時も既定の言語の 1 行を返す"""
        import rolekit
        start = self.pointer("start/start.json", {"run_id": RUN, "lang": "English"})
        code, out = self.run_script("facts", INPUTS_START=start)
        self.assertEqual((code, out["lang_line"]), (0, rolekit.lang_line({"lang": "English"})))
        self.assertIn("English", out["lang_line"])
        self.assertEqual(self.run_script("facts")[1]["lang_line"], rolekit.lang_line({}))
        blocker = self.dir / "file"
        blocker.write_text("", encoding="utf-8")
        self.assertEqual(self.run_script("facts", ARTIFACTS_DIR=str(blocker))[1]["lang_line"], rolekit.lang_line({}))
        first = (WRITE_BLOCK / "commands" / "report.md").read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(first, "$INPUTS.lang_line")
        self.assertIn("lang_line", WORKFLOW["nodes"][0]["output_format"]["required"])
        self.assertEqual(NODES["write"]["with"]["lang_line"], "$facts.output.lang_line")

    def test_request_stop_with_dry_run_environment(self):
        start = self.pointer("start/start.json", {"run_id": RUN})
        code, out = self.run_script("facts", INPUTS_START=start, INPUTS_GATE_FINAL='{"decision":"stop","text":"request: 止め札"}',
                                    WORKFLOW_ID="dry-run")
        self.assertEqual(code, 0)
        self.assertEqual((out["outcome"], out["stop_reason"], out["ok"]), ("stopped_by_request", "gate-final:stop", False))

    def test_unknown_answer_word_is_record_invalid_with_its_reason(self):
        start = self.pointer("start/start.json", {"run_id": RUN})
        code, out = self.run_script("facts", INPUTS_START=start, INPUTS_GATE_FINAL='{"decision":"maybe","text":""}')
        self.assertEqual(code, 0)
        self.assertEqual((out["outcome"], out["stop_reason"], out["ok"]), ("record_invalid", "report:record-invalid", False))
        text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
        self.assertIn("結果を名乗れない訳: 承認ノード gate-final の知らない答えの語 'maybe'", text)

    def test_unreadable_or_missing_conflicts_are_record_invalid(self):
        """人に回した申し出が読めない run は結果を名乗らない（読めなければ人に聞いた申し出が無いと数えて fixed に落ちる）"""
        start = self.pointer("start/start.json", {"run_id": RUN})
        broken = self.pointer("fix/conflicts.json", {})
        (self.artifacts / "fix/conflicts.json").write_text("{not json", encoding="utf-8")
        missing = json.dumps({"type": "archon_artifact", "run_id": RUN, "path": "fix/none.json"})
        for name, conflicts, word in (("JSON でない", broken, "申し出と裁定のファイル"), ("先が無い", missing, "ポインタの先")):
            with self.subTest(name):
                fix = json.dumps({"done": True, "units": [], "conflicts": json.loads(conflicts)})
                code, out = self.run_script("facts", INPUTS_START=start, INPUTS_FIX=fix)
                self.assertEqual(code, 0)
                self.assertEqual((out["outcome"], out["stop_reason"]), ("record_invalid", "report:record-invalid"))
                text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
                self.assertIn(f"結果を名乗れない訳: {word}", text)

    def test_stamp_carries_the_plan_round_and_measured_answer_reaches_outcome(self):
        """来歴の行の周は計画（案の直しが在ればそちら）の round、メイングラフの版は始めの記録の versions.works.rev。依頼が命令と出力つきで答えた素材は残りに数えない（始めの記録の
        answers が結末の決め方に届く）"""
        start = self.pointer("start/start.json", {"run_id": RUN, "versions": {"works": {"rev": "c" * 64, "dirty": False}}, "answers": [
            {"question": "ci", "text": "緑", "command": "make ci", "output": "ok"}]})
        judgment = self.pointer("judge/judgment.json", {})
        self.pointer("judge/materials.json", {"ci": {"status": "awaiting_human"}})
        judge = {"ready": True, "stop_reason": "", "units": [{"id": "u1"}], "judgment": json.loads(judgment)}
        env = {"INPUTS_START": start, "INPUTS_JUDGE": json.dumps(judge), "INPUTS_PLAN": '{"ready": true, "round": 1}',
               "INPUTS_REPLAN": '{"ready": true, "round": 2}', "INPUTS_FIX": json.dumps({"done": True, "units": []}),
               "INPUTS_TEST_GATE_FINAL": '{"ok": true, "green": true}', "INPUTS_MERGE_SEAL": '{"ok": true}'}
        code, out = self.run_script("facts", **env)
        self.assertEqual(code, 0)
        self.assertEqual(out["outcome"], "fixed", (self.artifacts / out["facts_file"]).read_text(encoding="utf-8"))
        self.assertRegex(out["stamp"], rf"^works-factory-report / run {RUN} / 周 2 / グラフの版 [0-9a-f]{{12}} / メイングラフの版 cccccccccccc$")

    def test_evidence_rows_stay_one_line_each(self):
        """役の素材の reason の改行は返りの欄と証拠の行を切らず、次の行の頭にも化けない: 修正前のテストの行は reason の終わりまで
        届き、ログの行は本物の置き場のまま。報告は証拠の文を開かずに返りの欄から同じ行を出す"""
        result = load_script("result", ROOT / "workflows" / "test-gate" / "scripts")
        run = {"by": "engine", "log": "/tmp/test.log", "junit_steps": [], "junit_unran": [], "suite": None,
               "fingerprint_before": None, "fingerprint_after": None}
        log, how = result.LOG_ROW, result.RUN_ROW
        base_line = declared_checks.baseline_line({"material": {"status": "not_run", "reason": f"見た物:\n{log}ci/output.txt"}})
        out = {"ok": False, "green": False, "red_cause": "incomplete", **result.gate_fields(run, "一式", base_line, f"訳:\n{log}偽")}
        rows = result.evidence("final", out, run, None, f"落ちた:\n{how}偽").splitlines()
        self.assertEqual([r for r in rows if r.startswith((log, how))], [f"{how}engine・一式", f"{log}/tmp/test.log"])
        self.assertIn(f"- ok: false（訳: {log}偽）", rows)
        returns = {"test-gate-final": out}
        got = runreport._evidence_lines(returns)
        self.assertIn("最後のテスト（test-gate-final）のログ: /tmp/test.log", got)
        self.assertIn("最後のテスト（test-gate-final）の走らせ方: engine・一式", got)
        base = next(x for x in got if x.startswith("最後のテスト（test-gate-final）の修正前のテスト: "))
        self.assertIn(f"見た物: {log}ci/output.txt", base)
        self.assertIn(gatemarks.BASELINE_NOT_RUN, base)
        self.assertIn(f"- {base.removeprefix('最後のテスト（test-gate-final）の')}", rows)
        self.assertIn("最後のテストの一式: engine・一式・ログ /tmp/test.log", runreport._tests_head_lines(returns))

    def final_returned(self, **fields) -> str:
        """test-gate（final）の返りの JSON。証拠の指し札の先のファイルは置かない（報告は返りの欄だけを読む）"""
        return json.dumps({"mode": "final", "ok": True, "green": True, "red_cause": "", "baseline": None, "fingerprint": None,
                           "evidence": {"type": "archon_artifact", "run_id": RUN, "path": "test-gate/final/evidence.md"},
                           "by": "engine", "suites_line": "", "log": "", "baseline_line": "", "reason": "", **fields})

    def green_section(self, final: str) -> str:
        code, out = self.run_script("facts", INPUTS_START=self.pointer("start/start.json", {"run_id": RUN}), INPUTS_TEST_GATE_FINAL=final)
        self.assertEqual(code, 0)
        return (self.artifacts / out["facts_file"]).read_text(encoding="utf-8").split(f"{runreport.GREEN_HEADING}\n\n", 1)[1]

    def test_green_cert_section_reads_the_test_gate_evidence(self):
        """test-gate の返りの走らせ方とログの欄が、証拠の文を開かずに緑の認証の節に届く。ログの無い回は「無い」"""
        suites, log = "一式: run-tests（make test）", str(self.dir / "test.log")
        green = self.green_section(self.final_returned(suites_line=suites, log=log))
        self.assertIn(f"- 最後のテスト（test-gate-final）の走らせ方: engine・{suites}\n", green)
        self.assertIn(f"- 最後のテスト（test-gate-final）のログ: {log}\n", green)
        green = self.green_section(self.final_returned(suites_line=suites))
        self.assertIn(f"- 最後のテスト（test-gate-final）のログ: 無い\n", green)

    def test_green_cert_section_carries_the_baseline_line(self):
        """T35: 最後のテストの返りの修正前のテストの欄（declared_checks.baseline_line）が、緑の認証の節に字のまま届く"""
        base = "修正前のテスト: 緑（元の結末（入力 baseline）の status clean）——最後のテストの赤は修正の後に出た赤でありうる"
        green = self.green_section(self.final_returned(suites_line="一式", baseline_line=base))
        self.assertIn(f"- 最後のテスト（test-gate-final）の{base}\n", green)

    def test_line_values_reach_the_outcome_and_the_report(self):
        """R5b・S48〜S51・S53: 線の collect が渡す線の値が、facts の結末と機械の報告に届く（入力 stops の止めの語が結末に、deferred・
        widened・final-reasons・prior-failures・redepth が報告の節に）。JSON でない線の値は結果を名乗らせない"""
        start = self.pointer("start/start.json", {"run_id": RUN})
        prior = self.pointer("start/prior-failures-in.json", [{"where": "受け付け 計画", "text": "前の run の拒否"}])
        redepth = {"depth": [{"unit_id": "u1", "depth": "標準", "why": "w"}], "skip_optional": "", "raised": ["再審が走った"],
                   "counted": "", "stop_reason": ""}
        code, out = self.run_script("facts", INPUTS_START=start, INPUTS_STOPS=json.dumps({"ask-final": "works:needs-human"}),
                                    INPUTS_DEFERRED='["[fork] q1"]', INPUTS_WIDENED='["項目 1: 直した——広げた"]',
                                    INPUTS_FINAL_REASONS='["守りのパスに当たった"]', INPUTS_PRIOR_FAILURES=prior,
                                    INPUTS_REDEPTH=json.dumps(redepth), INPUTS_OPTIONAL='["eyes__"]',
                                    INPUTS_FIX=json.dumps({"done": True, "units": [], "replan_items": ["1"], "refixed": True}))
        self.assertEqual(code, 0)
        self.assertEqual((out["outcome"], out["stop_reason"]), ("needs_human", "ask-final:works:needs-human"))
        text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
        for line in (f"- {runreport.DEFERRED_HEAD}: 1 件\n  - [fork] q1", "  - 案の項目 1: 直した——広げた",
                     f"- {runreport.FINAL_REASONS_HEAD}: 1 件\n  - 守りのパスに当たった", f"- {runreport.PRIOR_IN_HEAD}: 1 件\n  - 受け付け 計画: 前の run の拒否",
                     "  - 標準へ上げた信号: 再審が走った", "- メイングラフのノードの止め: ask-final が works:needs-human"):
            with self.subTest(line=line):
                self.assertIn(line, text)
        code, out = self.run_script("facts", INPUTS_START=start, INPUTS_STOPS=json.dumps({"start": "works:start-refused"}))
        self.assertEqual((out["outcome"], out["stop_reason"]), ("stopped_by_line", "start:works:start-refused"))
        code, out = self.run_script("facts", INPUTS_START=start, INPUTS_DEFERRED="{壊れた")
        self.assertEqual(out["outcome"], "record_invalid")
        self.assertIn("入力 deferred が JSON でない", (self.artifacts / out["facts_file"]).read_text(encoding="utf-8"))

    def test_missing_eye_of_a_standard_run_is_not_fixed(self):
        """R14: 直した後の深さが標準（入力 redepth の skip_optional が空）なのに返りの無い目は、結末を fixed にしない（深さで省いた run は数えない）"""
        start = self.pointer("start/start.json", {"run_id": RUN})
        env = {"INPUTS_START": start, "INPUTS_JUDGE": json.dumps({"ready": True, "stop_reason": "", "units": [{"id": "u1"}]}),
               "INPUTS_PLAN": '{"ready": true, "round": 1}', "INPUTS_FIX": json.dumps({"done": True, "units": []}),
               "INPUTS_TEST_GATE_FINAL": '{"ok": true, "green": true}', "INPUTS_MERGE_SEAL": '{"ok": true}',
               "INPUTS_EYES": json.dumps({"ok": True, "r1": {"status": "pass", "reason": ""}, "r2": None, "r3": None, "r4": None})}
        standard = {"depth": [], "skip_optional": "", "raised": [], "counted": "", "stop_reason": ""}
        self.assertEqual(self.run_script("facts", **env, INPUTS_REDEPTH=json.dumps(standard))[1]["outcome"], "round_limit")
        light = {**standard, "skip_optional": "軽量で省いた"}
        self.assertEqual(self.run_script("facts", **env, INPUTS_REDEPTH=json.dumps(light))[1]["outcome"], "fixed")

    def test_returns_with_pointers_reach_the_report(self):
        judgment = self.pointer("judge/judgment.json", {})
        judge = json.dumps({"ready": True, "stop_reason": "", "units": [{"id": "u1"}], "judgment": json.loads(judgment)})
        code, out = self.run_script("facts", INPUTS_START=self.pointer("start/start.json", {"run_id": RUN}), INPUTS_JUDGE=judge)
        self.assertEqual(code, 0)
        self.assertEqual(out["outcome"], "interrupted", "計画の返りが無い")
        text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
        self.assertIn(str(self.artifacts / "judge" / "judgment.json"), text)


class ReplanGiveUpCase(Run):
    """案の直しを終えられなかった項目（計画の役の諦め・事前審査の諦め）は、項目ごとに諦めの訳と裁定の文（字のまま）を前の失敗の行
    （報告と次の run に渡す prior-failures.json）に載せる（元 tests/test_replan.py の test_gave_up_paths_reach_ask_human_verbatim）"""

    def test_gave_up_replan_names_ruling_text_and_reason(self):
        import planblk
        ruling = "RULING-7310 項目 1 の allowed_paths に request_ok.json を足せ"
        why = planblk.PLAN_GAVE_UP_WHY.format(reason="plan の受け付けが 3 回とも拒んだ: 一字も変えずに写す")
        plan = self.pointer("plan/r2/plan-fields.json", {"round": 2, "fields": []})
        self.pointer(f"plan/r2/{planblk.REPLAN_GAVE_UP_FILE}", [{"item": 1, "why": why, "ruling": ruling}])
        judgment = self.pointer("judge/judgment.json", {})
        judge = {"ready": True, "stop_reason": "", "units": [{"id": "u1"}], "judgment": json.loads(judgment)}
        replan = {"ready": False, "round": 2, "plan": json.loads(plan)}
        code, out = self.run_script("facts", INPUTS_START=self.pointer("start/start.json", {"run_id": RUN}),
                                    INPUTS_JUDGE=json.dumps(judge), INPUTS_PLAN='{"ready": true, "round": 1}',
                                    INPUTS_REPLAN=json.dumps(replan))
        self.assertEqual(code, 0)
        rows = json.loads((self.artifacts / out["prior_failures"]["path"]).read_text(encoding="utf-8"))
        hit = [r for r in rows if r["where"] == runreport.REPLAN_GAVE_UP_WHERE.format(item=1)]
        self.assertEqual(len(hit), 1, rows)
        self.assertIn(f"裁定の文: {ruling}", hit[0]["text"])
        self.assertIn(why, hit[0]["text"])
        text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
        self.assertIn(ruling, text)


class OutDirCase(unittest.TestCase):
    def test_scripts_draw_the_report_folder_from_lib(self):
        """#372: 報告の置き場の名の持ち主は runreport.OUT_DIR だけ。script は名を字で持たない（名を代入する・パスに足す・
        「名/」で始まる字）"""
        name = runreport.OUT_DIR
        for path in sorted([*SCRIPTS.glob("*.py"), *(WRITE_BLOCK / "scripts").glob("*.py")]):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            found = [n.lineno for n in ast.walk(tree)
                     if (isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and n.value.value == name)
                     or (isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)
                         and any(isinstance(x, ast.Constant) and x.value == name for x in (n.left, n.right)))
                     or (isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith(f"{name}/"))]
            with self.subTest(path.name):
                self.assertEqual(found, [])


REPLY = json.dumps({"text": "直した。\n\n## 1. 人が決めること\n\n無い", "terms": []}, ensure_ascii=False)
PASS = json.dumps({"verdict": "pass", "stops": [], "guessed": [], "decidable": True})
FELL = "Loop-group node 'report__write__x__write-loop' failed at iteration 1: 'write': API Error: Sonnet 5.5's safeguards flagged this message\n二行目"


class WriteOutScriptCase(Run):
    """中継 write-out: 書き手のループの fan_out の出力の配列を、答えのポインタか AI の本文が無い訳にする。落ちない"""
    SCHEMA = NODES["write-out"]["output_format"]

    def relay(self, got) -> dict:
        code, out = self.run_script("write_out", INPUTS_GOT=got if isinstance(got, str) else json.dumps(got, ensure_ascii=False))
        self.assertEqual(code, 0)
        self.assertEqual(validate_schema(out, self.SCHEMA), [], out)
        return out

    def test_fallen_item_becomes_its_error(self):
        out = self.relay([{"archon_failed": True, "error": FELL, "status": "failed"}])
        self.assertEqual(out, {"ai": None, "fell": FELL})

    def test_answer_item_becomes_its_pointer(self):
        ai = {"type": "archon_artifact", "run_id": RUN, "path": f"{runreport.OUT_DIR}/{runreport.AI_FILE}"}
        self.assertEqual(self.relay([{"ok": True, "ai": ai}]), {"ai": ai, "fell": ""})
        self.assertEqual(self.relay([{"ok": False, "ai": None}]), {"ai": None, "fell": load_script("write_out").NO_ANSWER})

    def test_unreadable_output_still_returns_its_reason(self):
        for name, got in (("項目が 2 つ", [{"ok": False, "ai": None}] * 2), ("配列でない", {"ok": True}), ("JSON でない", "{壊れた")):
            with self.subTest(name):
                out = self.relay(got)
                self.assertIsNone(out["ai"])
                self.assertTrue(out["fell"].startswith("書き手のループの出力を読めない（"), out["fell"])


class CollectScriptCase(Run):
    SCHEMA = NODES["report"]["output_format"]

    def facts(self) -> dict:
        code, out = self.run_script("facts", INPUTS_START=self.pointer("start/start.json", {"run_id": RUN}),
                                    INPUTS_GATE_FINAL='{"decision":"stop","text":"止める"}')
        self.assertEqual(code, 0)
        return out

    def collect(self, facts: str, **env) -> dict:
        code, out = self.run_script("collect", INPUTS_FACTS=facts, **env)
        self.assertEqual(code, 0)
        self.assertEqual(validate_schema(out, self.SCHEMA), [], out)
        return out

    def answer(self) -> str:
        """書き手のループが受け取った答えを置き、中継 write-out の出力（答えのポインタ）を返す"""
        runreport.accept(REPLY, PASS, out_dir=self.artifacts / runreport.OUT_DIR)
        ai = {"type": "archon_artifact", "run_id": RUN, "path": f"{runreport.OUT_DIR}/{runreport.AI_FILE}"}
        return json.dumps({"ai": ai, "fell": ""})

    def test_without_writer_returns_machine_report(self):
        """書き手のループが飛ばされた（中継の出力が null）run は機械の報告を返す。置き場に答えのファイルが在っても、ポインタで
        受けていなければ読まない"""
        facts = self.facts()
        machine = (self.artifacts / facts["report"]["path"]).read_text(encoding="utf-8")
        runreport.accept(REPLY, PASS, out_dir=self.artifacts / runreport.OUT_DIR)
        for write in ("", "null"):
            with self.subTest(write=write):
                out = self.collect(json.dumps(facts), INPUTS_WRITE=write)
                self.assertEqual((out["outcome"], out["ok"]), ("stopped_by_human", False))
                self.assertIsNone(out["report_ai"])
                self.assertEqual(out["report"], facts["report"])
                self.assertEqual((self.artifacts / facts["report"]["path"]).read_text(encoding="utf-8"), machine)

    def test_writer_fell_returns_machine_report_with_the_reason_in_its_head(self):
        """#702: 書き手のループが落ちた run は、結末と ok を facts のまま、機械の報告を報告として返し、その冒頭に AI の本文が無い訳
        （落ちた誤りの文の 1 行目）が載る"""
        facts = self.facts()
        out = self.collect(json.dumps(facts), INPUTS_WRITE=json.dumps({"ai": None, "fell": FELL}, ensure_ascii=False))
        self.assertEqual((out["outcome"], out["ok"], out["stop_reason"]), (facts["outcome"], facts["ok"], facts["stop_reason"]))
        self.assertIsNone(out["report_ai"])
        self.assertEqual(out["report"], facts["report"])
        text = (self.artifacts / out["report"]["path"]).read_text(encoding="utf-8")
        line = runreport.WRITER_FELL.format(error=FELL.splitlines()[0])
        self.assertIn(line, runreport.machine_head(text))
        self.assertNotIn("二行目", text)
        self.assertTrue(text.startswith(f"# 報告（run {RUN}）\n\n{gatemarks.HAPPENED}"), text)

    def test_with_ai_file_returns_ai_report(self):
        """人に向けた報告は機械の冒頭で始まり来歴で終わり、来歴で始まる詳細のファイルが機械の事実を持つ（#660）"""
        facts = self.facts()
        out = self.collect(json.dumps(facts), INPUTS_WRITE=self.answer())
        self.assertEqual(out["report_ai"]["path"], f"{runreport.OUT_DIR}/{runreport.AI_REPORT_FILE}")
        text = (self.artifacts / out["report_ai"]["path"]).read_text(encoding="utf-8")
        self.assertTrue(text.startswith(f"# 報告（run {RUN}）\n\n{gatemarks.HAPPENED}"), text)
        self.assertRegex(text.splitlines()[-1], rf"^works-factory-report / run {RUN} / 周 — / グラフの版 ")
        self.assertNotIn(report_roles.MACHINE_HEADING, text)
        detail = (self.artifacts / runreport.OUT_DIR / runreport.DETAIL_FILE).read_text(encoding="utf-8")
        self.assertTrue(detail.startswith(f"works-factory-report / run {RUN} / 周 — / グラフの版 "))
        self.assertIn(report_roles.MACHINE_HEADING, detail)

    def test_ok_is_passed_through_from_facts(self):
        facts = self.facts()
        for ok in (True, False):
            with self.subTest(ok=ok):
                self.assertIs(self.collect(json.dumps({**facts, "ok": ok}))["ok"], ok)

    def test_broken_inputs_are_record_invalid(self):
        good = self.facts()
        cases = {"空": "", "JSON でない": "{壊れた", "欄が欠けた": json.dumps({"report": good["report"]}),
                 "指し札の先が無い": json.dumps({**good, "report": {"type": "archon_artifact", "run_id": RUN, "path": f"{runreport.OUT_DIR}/none.md"}})}
        for name, facts in cases.items():
            with self.subTest(name):
                out = self.collect(facts)
                self.assertEqual((out["outcome"], out["ok"]), ("record_invalid", False))
                self.assertTrue(out["stop_reason"].startswith("report:報告を組めなかった（"))

    def test_fallen_keeps_facts_report_and_carries(self):
        """facts の機械の報告と持ち越しの指し札が在れば、それを指して返る（facts の report.md を上書きしない）"""
        good = self.facts()
        machine = (self.artifacts / good["report"]["path"]).read_text(encoding="utf-8")
        carried = json.loads(self.pointer(f"{runreport.OUT_DIR}/next-request.json", {"findings": []}))
        broken = {**{k: v for k, v in good.items() if k != "stop_reason"}, "next_request": carried}
        out = self.collect(json.dumps(broken))
        self.assertEqual(out["outcome"], "record_invalid")
        self.assertEqual((out["report"], out["next_request"]), (good["report"], carried))
        self.assertEqual((self.artifacts / good["report"]["path"]).read_text(encoding="utf-8"), machine)

    def test_fallen_without_facts_report_writes_another_name(self):
        good = self.facts()
        machine = (self.artifacts / good["report"]["path"]).read_text(encoding="utf-8")
        out = self.collect("{壊れた")
        self.assertEqual(out["report"]["path"], f"{runreport.OUT_DIR}/{runreport.UNWRITTEN}")
        text = (self.artifacts / out["report"]["path"]).read_text(encoding="utf-8")
        self.assertIn("報告を組めなかった", text)
        self.assertNotIn(userenv.NOTE, text)
        self.assertEqual((self.artifacts / good["report"]["path"]).read_text(encoding="utf-8"), machine)
        (self.artifacts / userenv.RAN_FILE).touch()   # #504: 利用者の HOME・XDG で走らせた run は、落ちた報告の冒頭も言う
        self.assertIn(userenv.NOTE, (self.artifacts / self.collect("{壊れた")["report"]["path"]).read_text(encoding="utf-8"))

    def test_without_lib_still_returns(self):
        """lib/ を読めない（入口が渡した根に lib/ が無い）時も、返す節と facts は訳だけのファイルを指して 0 で返る"""
        empty = self.dir / "empty-root"
        empty.mkdir()
        code, out = self.run_script("facts", WORKS_FACTORY_ROOT=str(empty))
        self.assertEqual((code, out["outcome"], out["facts_file"]), (0, "record_invalid", facts_script.LIBLESS))
        self.assertIn("ModuleNotFoundError", (self.artifacts / out["facts_file"]).read_text(encoding="utf-8"))
        out = self.collect("", WORKS_FACTORY_ROOT=str(empty))
        self.assertEqual((out["outcome"], out["report"]["path"]), ("record_invalid", load_script("collect").LIBLESS))

    def test_unwritable_place_is_record_invalid(self):
        good = self.facts()
        blocker = self.dir / "file"
        blocker.write_text("", encoding="utf-8")
        out = self.collect(json.dumps({**good, "report": None}), ARTIFACTS_DIR=str(blocker))
        self.assertEqual(out["outcome"], "record_invalid")


class ConvergeLinesCase(unittest.TestCase):
    """事前審査の往復の報告の行（棚卸しの P119。元 works/tests/test_report.py の test_head_lists_converge_lines）"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(os.path.realpath(tmp.name))

    def test_head_carries_plan_converge_lines(self):
        """plan-review の返りの review の隣の gate.json の converge の行（1 回目に出た割合の句を含む頭の行）が、報告の冒頭の決めの節に
        載る。事前審査のブロックの script を本当に回して返りを作る"""
        r = plan_review.Run(self.dir / "plan-review")
        r.start(features_off=["review_tree"])
        got = r.pass_(plan_review.review(plan_review.MEAN_BLOCK))
        lines = converge.lines(r.view())
        self.assertIn("1 回目の block 1 件", lines[0])
        returns = fixed_run(**{"plan-review": {**got, "review": str(r.pointed(got["review"]))}})
        decided = outcome.decide_outcome(returns, {}, {"start_ok": True, "record_problems": [], "failed": []})
        built = runreport.build(returns, {}, {}, None, *decided, out_dir=self.dir / runreport.OUT_DIR, start={"run_id": RUN}, run_id=RUN)
        text = pathlib.Path(built["report"]).read_text(encoding="utf-8")
        body = text.split(f"{report.DECISIONS_HEADING}\n\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn(f"- {lines[0]}\n", body)
        for line in lines[1:]:
            self.assertIn(f"{line}\n", body)


class FixtureCase(unittest.TestCase):
    """筋書きを止めた Archon の workflow test で回し、同じ木の validate に誤りも警告も無いことを見る"""

    def test_fixtures_pass_and_validate_is_clean(self):
        with archon.tree(["report", "report-write"]) as tree:
            done = archon.archon(tree, "workflow", "test", "works-factory-report", "--json", "--cwd", str(tree))
            try:
                got = json.loads(done.stdout)
            except json.JSONDecodeError:
                self.fail(f"workflow test の返りが読めない: {done.stdout}{done.stderr}")
            names = sorted(pathlib.Path(r["fixture"]).name for r in got["results"])
            self.assertEqual(names, sorted(p.name for p in (BLOCK / "fixtures").glob("*.stubs.yaml")))
            self.assertEqual([r for r in got["results"] if not r["pass"]], [], done.stdout)
            self.assertEqual(got["errors"], [])
            checked = archon.archon(tree, "validate", "workflows", "--json", "--cwd", str(tree))
            issues = {r["workflowName"]: r["issues"] for r in json.loads(checked.stdout)["results"]}
            self.assertEqual(issues.get("works-factory-report"), [])

    def test_all_empty_and_request_stop_reach_their_words(self):
        """exec-code の筋書きの返す節の出力（dry-run の trace）が、それぞれの結末を返す"""
        for name, word in (("start-missing", "record_invalid"), ("stopped-by-request", "stopped_by_request")):
            with self.subTest(name), archon.tree(["report", "report-write"]) as tree:
                fixture = yaml.safe_load((BLOCK / "fixtures" / f"{name}.stubs.yaml").read_text(encoding="utf-8"))
                stubs = tree.parent / "stubs.yaml"
                stubs.write_text(yaml.safe_dump({k: v for k, v in fixture.items() if k not in ("fixture", "exec-code")},
                                                allow_unicode=True), encoding="utf-8")
                args = [arg for k, v in (fixture["fixture"].get("inputs") or {}).items() for arg in ("--input", f"{k}={v}")]
                done = archon.archon(tree, "workflow", "run", "works-factory-report", "--dry-run", "--exec-code", "--stubs", str(stubs),
                                     "--json", *args, "--cwd", str(tree))
                trace = {n["nodeId"]: n for n in json.JSONDecoder().raw_decode(done.stdout)[0]["trace"]}
                self.assertEqual(json.loads(trace["report"]["output"])["outcome"], word, done.stdout)



# 書き手の役が起こす Claude Code の代わり。提供元の安全の判定が依頼を止めた時と同じ誤りの文を出して落ちる（#702 の run の形）
FAKE_CLAUDE = "#!/bin/sh\necho \"API Error: Sonnet 5.5's safeguards flagged this message\" >&2\nexit 1\n"
SAFEGUARDS = "API Error: Sonnet 5.5's safeguards flagged this message"


class WriterFallRunCase(unittest.TestCase):
    """#702 の受け入れ: 止めた Archon で報告のブロックを本物の run（dry-run でない）で回し、書き手の役が落ちても run は completed で
    終わり、機械の報告が報告として残って、その冒頭に AI の本文が無い訳（落ちた誤りの文の 1 行目）が載る"""

    def test_fallen_writer_leaves_a_completed_run_and_the_machine_report(self):
        if shutil.which("uv") is None:
            self.skipTest("uv が無い")
        with tempfile.TemporaryDirectory() as tmp:
            fake = pathlib.Path(tmp) / "claude"
            fake.write_text(FAKE_CLAUDE, encoding="utf-8")
            fake.chmod(0o755)
            with archon.tree(["report", "report-write"]) as tree:
                done = archon.archon(tree, "workflow", "run", "works-factory-report", "--no-worktree",
                                     "--input", 'gate-final={"decision":"stop","text":"request: 止め札"}', "--cwd", str(tree),
                                     CLAUDE_BIN_PATH=str(fake))
                said = f"{done.stdout}{done.stderr}"
                returned = json.loads(next((x for x in done.stdout.splitlines() if x.startswith('{"outcome"')), "null"))
                self.assertIsNotNone(returned, said)
                self.assertIn(SAFEGUARDS, said, "書き手の役が本当に落ちた")
                run_id = returned["report"]["run_id"]
                got = json.loads(archon.archon(tree, "workflow", "get", run_id, "--json", "--cwd", str(tree)).stdout)
                self.assertEqual(got["status"], "completed", said)
                self.assertEqual((returned["outcome"], returned["report_ai"]), ("stopped_by_request", None))
                found = sorted((tree.parent / "archon-home").rglob(f"runs/{run_id}/{returned['report']['path']}"))
                self.assertEqual(len(found), 1, said)
                head = runreport.machine_head(found[0].read_text(encoding="utf-8"))
                fell = [x for x in head.splitlines() if x.startswith(runreport.WRITER_FELL.partition("{error}")[0])]
                self.assertEqual(len(fell), 1, head)
                self.assertIn(SAFEGUARDS, fell[0])


PROBE_HEAD = '# /// script\n# requires-python = ">=3.12"\n# dependencies = []\n# ///\n'
PROBE = {
    "works-factory-probe.yaml": """name: works-factory-probe
description: report の読み手に本物の run の記録と一覧を渡す試し
nodes:
  - id: make
    script: make
    runtime: uv
    output_type: probe-kind
  - id: boom
    script: boom
    runtime: uv
    depends_on: [make]
  - id: read
    script: read
    runtime: uv
    depends_on: [boom]
    trigger_rule: all_done
""",
    "scripts/make.py": PROBE_HEAD + 'import json\nprint(json.dumps({"a": 1}))\n',
    "scripts/boom.py": PROBE_HEAD + 'import sys\nsys.exit("boom")\n',
    "scripts/read.py": PROBE_HEAD + """import json, os, shutil
out = os.environ["ARTIFACTS_DIR"]
shutil.copy(os.environ["TYPED_ARTIFACTS_FILE"], os.path.join(out, "listing-copy.json"))
keys = ("LOG_DIR", "WORKFLOW_ID", "ARCHON_NODE_EXECUTION")
with open(os.path.join(out, "env.json"), "w", encoding="utf-8") as f:
    json.dump({k: os.environ.get(k, "") for k in keys}, f)
print("{}")
""",
}


class RealRunCase(unittest.TestCase):
    """止めた Archon で本物の run（dry-run でない）を 1 回回し、実行基盤が書いた run の記録と型つきの成果物の一覧を、
    手で組んだ見本でなく本物の出力のまま runreport.transcript_facts と facts.listing に読ませる（欄の名が変われば赤）"""

    def test_readers_read_a_real_run(self):
        if shutil.which("uv") is None:
            self.skipTest("uv が無い")
        with tempfile.TemporaryDirectory() as tmp:
            flows = pathlib.Path(tmp)
            for rel, text in PROBE.items():
                (flows / "probe" / rel).parent.mkdir(parents=True, exist_ok=True)
                (flows / "probe" / rel).write_text(text, encoding="utf-8")
            with archon.tree(["probe"], workflows=flows) as tree:
                done = archon.archon(tree, "workflow", "run", "works-factory-probe", "--no-worktree", "--cwd", str(tree))
                found = sorted((tree.parent / "archon-home").rglob("env.json"))
                self.assertEqual(len(found), 1, f"{done.stdout}{done.stderr}")
                artifacts = found[0].parent
                env = json.loads(found[0].read_text(encoding="utf-8"))
                lines = (pathlib.Path(env["LOG_DIR"]) / f"{env['WORKFLOW_ID']}.jsonl").read_text(encoding="utf-8").splitlines()
                rows = [json.loads(x) for x in lines if x.strip()]
                facts = runreport.transcript_facts(rows, optional=("boom",))
                self.assertTrue(facts["ok"])
                self.assertEqual(facts["failed"], [])
                self.assertEqual([a["node"] for a in facts["absorbed"]], ["boom"])
                self.assertEqual(runreport.transcript_facts(rows)["failed"], ["boom"], "受け止めると宣言していない段の落ち")
                self.assertIn("boom", facts["errors"]["boom"])
                self.assertLessEqual({"make", "boom", "read"}, set(facts["minutes"]))
                got = facts_script.listing(str(artifacts / "listing-copy.json"), str(artifacts), env["WORKFLOW_ID"],
                                    env["ARCHON_NODE_EXECUTION"])
                self.assertEqual(got["warnings"], [])
                self.assertEqual([(r["node"], r["body"]) for r in got["by_type"]["probe-kind"]], [("make", {"a": 1})])
                self.assertEqual(facts_script.own_prefix(env["ARCHON_NODE_EXECUTION"]), "")


if __name__ == "__main__":
    unittest.main()

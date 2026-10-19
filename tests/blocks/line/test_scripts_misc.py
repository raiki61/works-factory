"""line の小さな script（docs/design/line.md の 1.5）の振る舞い: testcmd（頭の止め）・gate_answer（承認ノードの答え）・returned（受け皿）・
relay（返し）・result（line の返す node）・sweep_children（後始末）。

元は今の tests/workflows/test_line.py の GateAnswerCase・ReturnedCase・SweepChildrenCase・CollectAndResultCase の result の部分と
tests/workflows/test_testcmd_head.py の TestCmdNodeTest（README 9.5）。script は子のプロセスで回すか（kit.Run.script。port の値だけを
INPUTS_<名> で渡す）、名で読んで関数を直に呼ぶ。testcmd が run を cancel する Archon の dry-run の場面は line の筋書きが持つ。
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.bin import hermetic
from tests.bin.gitkit import committed_copy, git
from tests.blocks import kit
from tests.blocks.line.test_start import LINE, ROOT, SEED, script

testcmd = script("testcmd")
result = script("result")
sweep_children = script("sweep_children")
testcmd_check = kit.load("line", "testcmd_check")
guard = kit.load("line", "guard")

import answer  # noqa: E402  （kit.load が共通の口を読み、lib/ を sys.path に足した後に読む）
RUN = kit.RUN_ID


def ptr(path: str) -> dict:
    return {"type": "archon_artifact", "run_id": RUN, "path": path}


class LineScriptWordCase(unittest.TestCase):
    def test_the_stop_word_is_the_lib_word(self):
        import stopby
        self.assertEqual((guard.LINE_SCRIPT, result.LINE_SCRIPT), (stopby.LINE_SCRIPT,) * 2)


class TestCmdNodeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name).resolve()
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, SEED)
        self.run_tree = self.worktree("run-tree")
        (self.tmp / "artifacts").mkdir()
        env = mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(self.tmp / "artifacts"), "WORKFLOW_ID": RUN})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(testcmd.ALLOW_ENV, None)

    def worktree(self, name: str) -> pathlib.Path:
        tree = self.tmp / name
        git(self.repo, "worktree", "add", "-q", "--detach", str(tree))
        return tree

    def test_the_allow_name_is_the_src_name(self):
        self.assertEqual(testcmd.ALLOW_ENV, testcmd_check.ALLOW_ENV)

    def test_command_running_the_checkout_stops_with_the_lines(self):
        got = testcmd.check(f"cd {self.repo} && make test", self.run_tree)
        self.assertTrue(got["stop"], got)
        lines = got["reason"].splitlines()
        self.assertTrue(lines[0].startswith(f"{testcmd.STOP_HEAD}test_cmd の {self.repo} は対象の手元"), lines)
        self.assertIn(f"test_cmd が対象の手元（{self.repo}）を走らせる形なので、AI を起こす前に run を止めた", lines[-1])
        self.assertIn(f"{testcmd.ALLOW_ENV}=1", lines[-1])

    def test_the_run_tree_itself_is_not_a_checkout(self):
        self.assertTrue(testcmd.check(f"{self.repo}/stats.py", self.run_tree)["stop"])
        self.assertEqual(testcmd.check(f"{self.run_tree}/stats.py", self.run_tree), {"stop": False, "reason": ""})

    def test_a_linked_worktree_of_the_user_is_a_checkout_too(self):
        mine = self.worktree("mine")
        got = testcmd.check(f"cd {mine} && make test", self.run_tree)
        self.assertTrue(got["stop"], got)
        self.assertTrue(got["reason"].startswith(f"{testcmd.STOP_HEAD}test_cmd の {mine} は対象の手元"), got)
        self.assertIn(f"対象の手元（{mine}）を走らせる形", got["reason"])

    def test_a_relative_word_the_tree_lacks_goes_on_with_a_notice(self):
        (self.repo / "sub" / ".venv" / "bin").mkdir(parents=True)
        (self.repo / "sub" / ".venv" / "bin" / "run-tests").write_text("#!/bin/sh\n")
        with open(self.repo / ".gitignore", "a", encoding="utf-8") as f:
            f.write(".venv\n")
        got = testcmd.check("cd sub && .venv/bin/run-tests", self.run_tree)
        self.assertFalse(got["stop"], got)
        lines = got["reason"].splitlines()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(f"{testcmd.ALLOWED_HEAD}test_cmd の .venv/bin/run-tests（cd の後の "
                                            "sub/.venv/bin/run-tests） は対象の git が無視するパス"), lines)

    def test_allowed_or_quiet_commands_go_on(self):
        for cmd in ("", "  ", "make test", "cd sub && uv run pytest"):
            with self.subTest(cmd):
                self.assertEqual(testcmd.check(cmd, self.run_tree), {"stop": False, "reason": ""})
        with mock.patch.dict(os.environ, {testcmd.ALLOW_ENV: "1"}):
            got = testcmd.check(f"cd {self.repo} && make test", self.run_tree)
        self.assertFalse(got["stop"], got)
        self.assertTrue(got["reason"].startswith(testcmd.ALLOWED_HEAD), got)

    def test_a_check_that_fails_stops_unless_allowed(self):
        got = testcmd.fallback("OSError: 落ちた")
        self.assertTrue(got["stop"])
        self.assertIn("OSError: 落ちた", got["reason"])
        with mock.patch.dict(os.environ, {testcmd.ALLOW_ENV: "1"}):
            self.assertFalse(testcmd.fallback("OSError: 落ちた")["stop"])


class ScriptRun(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "line")


class GateAnswerCase(ScriptRun):
    def take(self, gate, go="true", stop="", place="gate-final", final="false") -> dict:
        return self.run.script("gate_answer", gate=gate, go=go, stop_reason=stop, place=place, final=final)

    def test_skipped_gate_passes_the_decision_before_it(self):
        self.assertEqual(self.take("null"), {"go": True, "answer": None, "stop_reason": ""})
        self.assertEqual(self.take("", go="false", stop="works:needs-human"), {"go": False, "answer": None, "stop_reason": "works:needs-human"})
        self.assertFalse((self.run.artifacts / answer.ANSWERS).exists())

    def test_go_words_continue_and_are_recorded(self):
        for word in answer.GO_WORDS:
            with self.subTest(word=word):
                got = self.take(json.dumps({"decision": word, "text": "a.py だけ"}), place="gate-start")
                self.assertEqual(got, {"go": True, "answer": {"decision": word, "text": "a.py だけ", "asked": []}, "stop_reason": ""})
                kept = json.loads((self.run.artifacts / "gates" / "gate-start.json").read_text(encoding="utf-8"))
                self.assertEqual(kept, got["answer"])

    def test_stop_and_unknown_words_stop_with_the_gate_named(self):
        """L-G03: 通す語でない答え（stop・reject・知らない語）は止めと読む"""
        for word in ("stop", answer.REJECT, "maybe"):
            with self.subTest(word=word):
                got = self.take(json.dumps({"decision": word, "text": "やめる"}))
                self.assertEqual((got["go"], got["stop_reason"]), (False, "human:gate-final"))

    def test_empty_stop_note_gets_the_default_reason(self):
        """L-G07: stop・reject の一言が空なら既定の文。最後の承認ノードは with: の final で見分ける"""
        self.assertEqual(self.take(json.dumps({"decision": "stop", "text": " "}), final="true")["answer"]["text"], answer.FINAL_STOP_NOTE)
        self.assertEqual(self.take(json.dumps({"decision": "stop", "text": ""}), place="gate-start")["answer"]["text"], answer.STOP_NOTE)
        self.assertEqual(self.take(json.dumps({"decision": "continue", "text": ""}))["answer"]["text"], "")

    def test_a_plain_word_is_a_decision(self):
        """承認ノードの出力が JSON でない字（選び肢の語だけ）でも答えの語と読む"""
        self.assertEqual(self.take("approve")["answer"], {"decision": "approve", "text": "", "asked": []})

    def test_unreadable_inputs_fall_to_the_line_script_word(self):
        self.assertEqual(self.take("null", go="yes"), {"go": False, "answer": None, "stop_reason": guard.LINE_SCRIPT})


class ReturnedCase(ScriptRun):
    def test_whole_output_gives_the_declared_fields(self):
        """受け皿は got（受ける node の返りまるごと）の names で宣言した欄だけを、型を保ったまま got にする。optional は無くてよい"""
        whole = {"mode": "seal", "ok": True, "hash": "123", "diff": None, "protected_hits": [], "reason": "", "extra": 1}
        got = self.run.script("returned", got=json.dumps(whole), names="mode ok hash diff protected_hits reason")
        self.assertEqual(got, {"got": {**{k: v for k, v in whole.items() if k != "extra"}, "optional": None}, "why": ""})

    def test_missing_declared_field_is_a_null_got_with_the_why(self):
        """宣言した欄が無い返り（前の版の block の返り）は空と読まず、got: null と訳（integration.md の 4.3-12）"""
        got = self.run.script("returned", got=json.dumps({"ok": True}), names="ok hash")
        self.assertIsNone(got["got"])
        self.assertIn("hash", got["why"])

    def test_unreadable_got_is_a_null_got(self):
        for case, inputs in {"無い": {"names": "ok"}, "null": {"got": "null", "names": "ok"}, "配列": {"got": "[]", "names": "ok"},
                             "names が無い": {"got": "{}"}}.items():
            with self.subTest(case):
                got = self.run.script("returned", **inputs)
                self.assertIsNone(got["got"])
                self.assertTrue(got["why"])


class RelayCase(ScriptRun):
    def test_named_fields_are_relayed(self):
        whole = {"ok": True, "design": ptr("d.json"), "reason": "", "premises": None, "extra": 1}
        got = self.run.script("relay", got=json.dumps(whole), field="design reason premises")
        self.assertEqual(got, {"design": ptr("d.json"), "reason": "", "premises": None, "stop_reason": ""})

    def test_skipped_got_is_null_fields(self):
        """飛ばされた作り手（`{from, if_skipped: null}` の null・宣言した null の欄の空の字）は各欄 null で、止めない"""
        for raw in ("null", ""):
            with self.subTest(raw=raw):
                self.assertEqual(self.run.script("relay", got=raw, field="structure"), {"structure": None, "stop_reason": ""})

    def test_missing_field_stops(self):
        """作り手の返りに名指した欄が無い（前の版の返り）なら止めの語で後ろへ進めない"""
        self.assertEqual(self.run.script("relay", got=json.dumps({"ok": True}), field="rows"),
                         {"rows": None, "stop_reason": guard.LINE_SCRIPT})


class ResultCase(unittest.TestCase):
    REPORT = {"ok": True, "outcome": "fixed", "stop_reason": "", "machine": ptr("report.md"), "human": ptr("report-ai.md"),
              "next_request": None, "prior_failures": ptr("prior-failures.json")}

    def result(self, report=None, **kw) -> dict:
        given = {"merge_apply": None, "merge_seal": None, "eyes": None, "spec_check": None, "answer_final": None, "children": None, **kw}
        return result.result(report, **given)

    def test_report_names_are_kept(self):
        """report の返りの machine・human を今の名 report・report_ai で写す（bin/apply・chain・通しの試験が今の名で読む）"""
        got = self.result(dict(self.REPORT))
        self.assertEqual((got["fixed"], got["ok"], got["outcome"]), (True, True, "fixed"))
        self.assertEqual((got["report"], got["report_ai"], got["prior_failures"]), (ptr("report.md"), ptr("report-ai.md"),
                                                                                   ptr("prior-failures.json")))
        self.assertTrue(self.result({**self.REPORT, "outcome": "fixed_needs_check", "ok": True})["fixed"])
        self.assertFalse(self.result({**self.REPORT, "outcome": "no_fix_needed"})["fixed"])

    def test_absent_report_is_not_fixed(self):
        got = self.result(None)
        self.assertEqual((got["fixed"], got["ok"], got["outcome"], got["report"]), (False, False, "", None))

    def test_line_fields_come_from_the_receivers(self):
        apply = {"mode": "apply", "ok": True, "hash": "h", "diff": ptr("d"), "reason": "", "protected_hits": []}
        seal = {"mode": "seal", "ok": True, "hash": "h", "diff": ptr("d"), "reason": ""}
        eyes = {"ok": True, "r2": {"status": "pass", "reason": ""}}
        final = {"decision": "approve", "text": "", "asked": []}
        swept = {"cleaned": [{"branch": "b0", "run_id": "c0", "node": "fix__groups-par"}], "left": [], "error": ""}
        got = self.result(dict(self.REPORT), merge_apply=apply, merge_seal=seal, eyes=eyes, spec_check={"questions": ["a", "b"]},
                          answer_final=final, children=swept)
        self.assertEqual(got["apply"], {"ok": True, "hash": "h", "diff": ptr("d"), "reason": ""})
        self.assertEqual(got["sealed"], {"ok": True, "hash": "h", "diff": ptr("d")})
        self.assertEqual((got["r2_status"], got["final_answer"], got["spec_questions"], got["children"]), ("pass", final, 2, swept))
        bare = self.result(dict(self.REPORT))
        self.assertEqual((bare["apply"], bare["sealed"], bare["r2_status"], bare["final_answer"], bare["spec_questions"], bare["children"]),
                         (None, None, None, None, 0, None))

    def test_script_reads_every_input(self):
        run = kit.Run(self, "line")
        got = run.script("result", report=json.dumps(self.REPORT), merge_apply="null", merge_seal="", eyes="null", spec_check="null",
                         answer_final="null", children="null")
        self.assertEqual((got["fixed"], got["outcome"], got["children"]), (True, "fixed", None))
        broken = run.script("result", report=json.dumps({"ok": True}))
        self.assertEqual((broken["fixed"], broken["stop_reason"]), (False, guard.LINE_SCRIPT),
                         "report の返りの欄が欠けた（前の版の返り）なら fallback")

    def test_result_does_not_fall_without_the_shared_port(self):
        """共通の口を読めない時も標準ライブラリだけで fallback の返りを書く"""
        with tempfile.TemporaryDirectory() as tmp:
            copied = pathlib.Path(tmp) / "line"
            shutil.copytree(LINE, copied, ignore=shutil.ignore_patterns("__pycache__"))
            done = subprocess.run([sys.executable, str(copied / "scripts" / "result.py")], cwd=tmp, env=hermetic.child_env(),
                                  capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), result.fallback(""))


class SweepChildrenCase(unittest.TestCase):
    """line の後始末の node sweep-children: 落ちずに {cleaned, left, error} を返す。選びと Archon の起こし方は埋め childsweep の試験"""

    def test_failure_is_returned_not_raised(self):
        with mock.patch.object(sweep_children.ports, "returns") as returns, mock.patch("sys.stderr"), \
                mock.patch.object(sweep_children, "sweep", side_effect=OSError("壊れた")):
            sweep_children.main()
        returns.assert_called_once_with({"cleaned": [], "left": [], "error": "OSError: 壊れた"})

    def run_node(self, extra: dict) -> dict:
        """node の script を、Archon と同じく pack の写し（line と共通の口）から、リポジトリの根を WORKS_FACTORY_ROOT で渡して
        本当に走らせる。Archon は偽の bun（一覧に WORKFLOW_ID の run だけを出す）で、子の run は無い"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            copied = tmp / "blocks"
            for folder in ("line", ".shared"):
                shutil.copytree(kit.BLOCKS / folder, copied / folder, ignore=shutil.ignore_patterns("__pycache__"))
            (tmp / "bin").mkdir()
            bun = tmp / "bin" / "bun"
            listing = json.dumps({"runs": [{"id": RUN, "status": "running", "parent_run_id": None, "metadata": {}}]})
            bun.write_text(f"#!/bin/sh\ncat <<'EOF'\n{listing}\nEOF\n", encoding="utf-8")
            bun.chmod(0o755)
            env = hermetic.child_env(
                PATH=f"{tmp / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}", WORKFLOW_ID=RUN, ARTIFACTS_DIR=str(tmp),
                WORKS_FACTORY_ROOT=str(ROOT), **{k: v.replace("<tmp>", str(tmp)) for k, v in extra.items()})
            done = subprocess.run([sys.executable, str(copied / "line/scripts/sweep_children.py")], cwd=tmp, env=env,
                                  capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_run_without_children_does_not_fail(self):
        childsweep = sweep_children.ports.polyfill("childsweep")
        self.assertEqual(self.run_node({childsweep.CLI_ENV: json.dumps(["<tmp>/bin/bun"])}), {"cleaned": [], "left": [], "error": ""})

    def test_run_outside_the_launcher_does_not_fail(self):
        got = self.run_node({})
        self.assertEqual((got["cleaned"], got["left"]), ([], []))
        self.assertIn(sweep_children.ports.polyfill("childsweep").CLI_ENV, got["error"])


if __name__ == "__main__":
    unittest.main()

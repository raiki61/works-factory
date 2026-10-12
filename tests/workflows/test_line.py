"""線の script（workflows/line/scripts/）の決めを、関数を直に呼んで照らす。

筋書き（tests/e2e/test_line_scenarios.py）は関所の答えを stub で差し、往復を 1 周で終えるので、関所の答えの読み・往復の抜け方・
入口の拒み・返りの合わせ方はここで照らす。種の git は gitkit の型の写し。
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

import yaml

from tests.bin.gitkit import committed_copy, git
from tests.bin.linescripts import SCRIPTS, load
from tests.workflows.test_gate_head import final_got

linekit = load("linekit")
start = load("start")
gate_answer = load("gate_answer")
before_fix_answer = load("before_fix_answer")
replan_answer = load("replan_answer")
ask_before_fix = load("ask_before_fix")
ask_replan = load("ask_replan")
ask_final = load("ask_final")
plan_out = load("plan_out")
after_fix = load("after_fix")
judged = load("judged")
fixed = load("fixed")
redepth = load("redepth")
returned = load("returned")
collect = load("collect")
result = load("result")

import answer  # noqa: E402  （線の script が lib/ を sys.path に足した後に読む）
import boardview  # noqa: E402
import conflict  # noqa: E402
import fixboard  # noqa: E402
import gatemarks  # noqa: E402
import judge_accept  # noqa: E402
import policy  # noqa: E402
import startrec  # noqa: E402
import stopby  # noqa: E402

SEED = SCRIPTS.parents[2] / "tests" / "e2e" / "target-seed"
RUN = "run-1"
LINE = yaml.safe_load((SCRIPTS.parent / "works-factory-line.yaml").read_text(encoding="utf-8"))
BLOCKS = ("judge", "plan", "plan-review", "fix", "test-gate", "eyes", "report", "merge")


def block_doc(include: str) -> dict:
    """差し込むブロックの YAML（include の名の works-factory- の後ろがフォルダ）"""
    return yaml.safe_load((SCRIPTS.parents[1] / include.removeprefix("works-factory-") / f"{include}.yaml").read_text(encoding="utf-8"))


def line_nodes(nodes=None) -> dict:
    """線の節（loop_group の中の節も）を id ごとに"""
    got = {}
    for node in LINE["nodes"] if nodes is None else nodes:
        got[node["id"]] = node
        got.update(line_nodes(node["loop_group"]["nodes"]) if "loop_group" in node else {})
    return got


class Artifacts(unittest.TestCase):
    """run の置き場（ARTIFACTS_DIR）と run の id（WORKFLOW_ID）を一時の物にする"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.artifacts = self.tmp / "artifacts"
        self.artifacts.mkdir()
        env = mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(self.artifacts), "WORKFLOW_ID": RUN})
        env.start()
        self.addCleanup(env.stop)


def raw(**kw) -> dict:
    got = {key: "" for key in ("request", "base", "pr", "spec", "test_cmd", "tdd_suite", "final_gate", "unattended", "design_only",
                               "thickness", "features_off", "features_on", "policy_md", "fix_fixture", "lang")}
    got.update(kw)
    return got


class StartCase(Artifacts):
    def setUp(self):
        super().setUp()
        self.repo = self.tmp / "repo"
        self.fork = committed_copy(self.repo, SEED)
        git(self.repo, "branch", "base")
        with (self.repo / "stats.py").open("a", encoding="utf-8") as f:
            f.write("\n# 変更\n")
        git(self.repo, "commit", "-q", "-am", "change")

    def start(self, **kw):
        return start.start(raw(**kw), self.repo, self.artifacts, RUN)

    def record(self, got):
        self.assertEqual(got["record"]["run_id"], RUN)
        return json.loads((self.artifacts / got["record"]["path"]).read_text(encoding="utf-8"))

    def test_request_builds_the_entry_shape_and_the_record(self):
        got = self.start(request="request_ok.json", final_gate="when_needed", features_off="tdd_lanes")
        self.assertTrue(got["ok"], got)
        self.assertEqual((got["ask"], got["unattended"], got["design_only"], got["final_gate"]), (True, False, False, "when_needed"))
        doc = self.record(got)
        head = git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(doc["input"]["base"], {"rev": head, "from": "head", "name": "", "label": "HEAD"})
        self.assertEqual((doc["input"]["requests"], doc["input"]["diff"]["empty"]), (2, True))
        self.assertEqual(doc["input"]["request_file"], str((self.repo / "request_ok.json").resolve()),
                         "相対の依頼は対象の根から読み、絶対パスで残す（L-E06）")
        self.assertEqual(doc["features_off"], ["tdd_lanes"])
        self.assertEqual(doc["features"]["tdd_lanes"], "off")
        self.assertEqual(doc["final_gate"], "when_needed")
        self.assertIn("archon", doc["versions"])
        self.assertTrue(got["gate_text"].startswith("起きたこと: "), got["gate_text"])

    def test_base_alone_is_a_change_entry(self):
        got = self.start(base="base")
        self.assertTrue(got["ok"], got)
        doc = self.record(got)
        self.assertEqual(doc["input"]["base"], {"rev": self.fork, "from": "base", "name": "base", "label": "base base"},
                         "差分の根は base と HEAD の merge-base、label は「base <名>」（L-E09）")
        self.assertGreaterEqual(doc["input"]["diff"]["files"], 1)
        self.assertEqual(doc["base_rev"], git(self.repo, "rev-parse", "HEAD"),
                         "base_rev は修正の前の HEAD（今の works の entry.py 1203 行。merge と test-gate が差分の起点に読む）")

    def test_request_file_is_on_the_top_of_the_record(self):
        """issue #89: 始めの記録の上の欄 request_file は input.request_file と同じ絶対パス（今の works の entry.py 605 行）。
        依頼の無い入口では両方 \"\""""
        doc = self.record(self.start(request="request_ok.json"))
        self.assertEqual(doc["request_file"], str((self.repo / "request_ok.json").resolve()))
        self.assertEqual(doc["request_file"], doc["input"]["request_file"])
        doc = self.record(self.start(base="base"))
        self.assertEqual((doc["request_file"], doc["input"]["request_file"]), ("", ""))

    def test_blocks_read_the_request_file_from_the_line_record(self):
        """issue #89: 線の始めの記録を fix の prep・事前審査の open と同じ口（startrec.adopt）で置き場の r1/start.json に字のまま写すと、
        上の欄だけを読む fix の読み手（conflict.request_file・fixboard.fix_values）が依頼のファイルを返す"""
        got = self.start(request="request_ok.json")
        place = self.tmp / "fix"
        self.assertEqual(startrec.adopt(place, self.artifacts / got["record"]["path"]), self.record(got))
        self.assertEqual(startrec.path(place).read_bytes(), (self.artifacts / got["record"]["path"]).read_bytes())
        want = str((self.repo / "request_ok.json").resolve())
        self.assertEqual(conflict.request_file(place), want)
        self.assertEqual(fixboard.fix_values(place, [], start=startrec.read(place))["request_file"], want)

    def test_unattended_does_not_open_the_start_gate(self):
        got = self.start(request="request_ok.json", unattended="true")
        self.assertEqual((got["ok"], got["ask"], got["unattended"]), (True, False, True))

    def test_prior_failures_of_the_request_are_placed(self):
        (self.repo / "next.json").write_text(json.dumps({"findings": [{"where": "a", "text": "b"}],
                                                         "prior_failures": [{"where": "判定", "text": "拒まれた"}]}),
                                             encoding="utf-8")
        got = self.start(request="next.json")
        self.assertEqual(got["prior_failures"]["path"], "prior-failures-in.json")
        self.assertEqual(json.loads((self.artifacts / "prior-failures-in.json").read_text(encoding="utf-8")),
                         [{"where": "判定", "text": "拒まれた"}])

    def bad_findings(self) -> pathlib.Path:
        """依頼の型に合わない依頼のファイル（text の無い行）。対象の木の外に置く（木を汚すと差分が空でなくなる）"""
        path = self.tmp / "bad_findings.json"
        path.write_text(json.dumps([{"where": "stats.py"}]), encoding="utf-8")
        return path

    def test_policy_md_is_recorded_as_an_absolute_path(self):
        (self.repo / "policy.md").write_text("方針\n", encoding="utf-8")
        got = self.start(request="request_ok.json", policy_md="policy.md")
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.record(got)["policy_md"], str(self.repo / "policy.md"))

    def test_record_carries_the_policy_frozen_at_the_start(self):
        """始めの記録の欄 policy は run の始めに固めた版 {named, path, sha256, copy}（写しは run の置き場の中）。名指しも既定の置き場の
        文書も無ければ path は空・sha256 と copy は null"""
        (self.tmp / "policy.md").write_text("方針\n", encoding="utf-8")
        frozen = self.record(self.start(request="request_ok.json", policy_md=str(self.tmp / "policy.md")))["policy"]
        self.assertEqual((frozen["named"], frozen["path"]), (str(self.tmp / "policy.md"),) * 2)
        self.assertTrue(pathlib.Path(frozen["copy"]).is_relative_to(self.artifacts))
        self.assertEqual(pathlib.Path(frozen["copy"]).read_text(encoding="utf-8"), "方針\n")
        self.assertEqual(self.record(self.start(request="request_ok.json"))["policy"],
                         {"named": "", "path": "", "sha256": None, "copy": None})

    def test_refusals_stop_before_any_role(self):
        for kw, words in (({}, "直す物も審査する物も無い"),
                          ({"request": "request_ok.json", "base": "base", "pr": "1"}, "両方"),
                          ({"request": "request_ok.json", "spec": "on", "unattended": "true"}, "組めない"),
                          ({"request": "request_ok.json", "thickness": "重厚"}, "足す工程がまだ無い"),
                          ({"request": "request_ok.json", "thickness": "xx"}, "知らない値"),
                          ({"request": "request_ok.json", "features_off": "nope"}, "nope"),
                          ({"request": "request_ok.json", "features_off": "judge_verify", "features_on": "judge_verify"}, "両方"),
                          ({"request": "no-such.json"}, "no-such.json"),
                          ({"request": "request_ok.json", "design_only": "yes"}, "design_only"),
                          ({"request": "request_ok.json", "policy_md": "no-such.md"}, "no-such.md"),
                          ({"request": "request_ok.json", "fix_fixture": "fx"}, "fix_fixture"),
                          ({"request": str(self.bad_findings())}, "findings は")):
            with self.subTest(kw=kw):
                got = self.start(**kw)
                self.assertEqual((got["ok"], got["stop_reason"], got["ask"]), (False, linekit.START_REFUSED, False), got)
                self.assertIn(words, got["reason"])
                doc = self.record(got)
                self.assertEqual(doc["refused"], got["reason"])
                self.assertEqual(doc["inputs"], raw(**kw), "拒む run でも設定の写しを残す（L-E46）")
                self.assertIn("unknown", doc["versions"], "拒む run でも版の控えを残す（L-E46）")

    def outside(self, name: str, text: str) -> pathlib.Path:
        """対象の木の外に置く依頼のファイル（木を汚すと差分が空でなくなる）"""
        path = self.tmp / name
        path.write_text(text, encoding="utf-8")
        return path

    def refused(self, **kw) -> str:
        got = self.start(**kw)
        self.assertEqual((got["ok"], got["stop_reason"]), (False, linekit.START_REFUSED), got)
        return got["reason"]

    def test_request_refusals_name_the_cause(self):
        """L-E02: 依頼が読めない・JSON として読めない・形が違うを別の文で拒む（元 works/.shared/core/entry.py 620-632 行）"""
        self.assertIn("読めない", self.refused(request="no-such.json"))
        self.assertNotIn("JSON", self.refused(request="no-such.json"))
        self.assertIn("JSON として読めない", self.refused(request=str(self.outside("broken.json", "{findings"))))
        bad = json.dumps({"findings": [{"where": "a", "text": "b"}], "answers": "x"})
        reason = self.refused(request=str(self.outside("bad_answers.json", bad)))
        self.assertIn("の形", reason)
        self.assertNotIn("読めない", reason)

    def test_request_answers_reach_the_record(self):
        """L-E03: 依頼の answers は始めの記録の answers（元 works/tests/test_entry.py の test_request_answers_reach_start_doc）"""
        rows = [{"question": "q1", "text": "a を選ぶ"}]
        path = self.outside("answers.json", json.dumps({"findings": [{"where": "a", "text": "b"}], "answers": rows}))
        self.assertEqual(self.record(self.start(request=str(path)))["answers"], rows)

    def test_bad_answers_or_prior_shape_refused(self):
        """L-E04・L-D51: answers・prior_failures の形の違う依頼は AI の前で拒む（元 test_entry.py の
        test_request_answers_bad_shape_refused・test_request_prior_failures_bad_shape_refused）"""
        for key, bad in (("answers", [{"text": "問いの無い答え"}]), ("answers", "x"), ("prior_failures", [{"where": "w"}]),
                         ("prior_failures", [{"where": "w", "text": "t", "extra": 1}])):
            with self.subTest(key=key, bad=bad):
                path = self.outside("shape.json", json.dumps({"findings": [{"where": "a", "text": "b"}], key: bad}))
                self.assertIn(key, self.refused(request=str(path)))

    def test_bad_base_or_pr_refused(self):
        """L-E10: 引けない base・番号でない pr を名を言って拒む"""
        self.assertIn("no-such-branch", self.refused(base="no-such-branch"))
        self.assertIn("引けない", self.refused(base="no-such-branch"))
        self.assertIn("番号でない", self.refused(pr="x"))

    def pr_reads(self, **pr) -> dict:
        doc = {"baseRefOid": self.fork, "headRefOid": git(self.repo, "rev-parse", "HEAD"), "title": "題 T", "body": "本文X",
               "status": "ok"}
        doc.update(pr)
        return {"version": 1, "pr": {"7": doc}, "issue": {}}

    def start_with_gh(self, reads, **kw):
        """run の中の gh の読み出しを reads に差して start を回す（呼ばれた回数を返す）"""
        import ghreads
        calls = []

        def read_named(repo, prs, issues):
            calls.append((prs, issues))
            return reads
        with mock.patch.object(ghreads, "read_named", read_named):
            return self.start(**kw), calls

    def test_named_pr_is_read_once_and_placed(self):
        """L-E11: 名指した PR は run の中で 1 度だけ読み、置き場の根の github.json に 0600 で置く。2 度目（再開）は読み直さない"""
        import ghreads
        got, calls = self.start_with_gh(self.pr_reads(), pr="7")
        self.assertTrue(got["ok"], got)
        self.assertEqual(calls, [([7], [])])
        placed = self.artifacts / ghreads.BOARD_FILE
        self.assertEqual(placed.stat().st_mode & 0o777, 0o600)
        again, calls = self.start_with_gh(self.pr_reads(title="別の題"), pr="7")
        self.assertEqual(calls, [])
        self.assertEqual(self.record(again)["input"]["pr"]["title"], "題 T")

    def test_pr_base_is_the_github_base_oid(self):
        """L-E12: PR の差分の根は GitHub の baseRefOid と HEAD の merge-base、label は「PR #N「題」」（元 works/tests/test_entry_inputs.py の
        test_pr_uses_github_base_oid_and_carries_description）"""
        got, _ = self.start_with_gh(self.pr_reads(), pr="7")
        doc = self.record(got)
        self.assertEqual(doc["input"]["base"], {"rev": self.fork, "from": "pr", "name": "7", "label": "PR #7「題 T」"})

    def test_pr_refused_when_head_differs_or_base_missing(self):
        """L-E13: PR の head が対象の HEAD と違えば止め、PR の base の版が無ければ fetch してからと言って止める"""
        import ghreads
        got, _ = self.start_with_gh(self.pr_reads(headRefOid=self.fork), pr="7")
        self.assertIn("head", got["reason"])
        self.assertIn("違う", got["reason"])
        (self.artifacts / ghreads.BOARD_FILE).unlink()
        got, _ = self.start_with_gh(self.pr_reads(baseRefOid="f" * 40), pr="7")
        self.assertIn("fetch してから", got["reason"])
        self.assertFalse(got["ok"])

    def test_no_auth_launch_refuses_named_pr_without_gh(self):
        """L-E15: 認証の要らない起動（殻が立てる WORKS_FACTORY_NO_AUTH=1）で PR を名指せば、gh を呼ばずに認証を使う起動で回すと止める"""
        with mock.patch.dict(os.environ, {"WORKS_FACTORY_NO_AUTH": "1"}):
            got, calls = self.start_with_gh(self.pr_reads(), pr="7")
        self.assertEqual(calls, [])
        self.assertFalse(got["ok"])
        self.assertIn("認証を使う起動", got["reason"])

    def test_request_text_carries_request_and_pr(self):
        """L-E16: 依頼と PR の両方なら見出しつき、片方ならその文（元 works/tests/test_entry_inputs.py の同名）。L-E17: PR の題と本文は
        始めの記録の input.pr に載る（目的の役の材料が読む）"""
        req = self.outside("req.json", json.dumps([{"where": "stats.py", "text": "依頼の穴"}], ensure_ascii=False))
        doc = self.record(self.start_with_gh(self.pr_reads(), pr="7", request=str(req))[0])
        self.assertIn("## 依頼", doc["request_text"])
        self.assertIn("依頼の穴", doc["request_text"])
        self.assertIn("## PR #7 の題と本文", doc["request_text"])
        self.assertIn("本文X", doc["request_text"])
        self.assertEqual(doc["input"]["pr"], {"number": "7", "title": "題 T", "body": "本文X"})
        doc = self.record(self.start_with_gh(self.pr_reads(), pr="7")[0])
        self.assertEqual(doc["request_text"], "題 T\n\n本文X")
        doc = self.record(self.start(request=str(req)))
        self.assertEqual(doc["request_text"], req.read_text(encoding="utf-8"))

    def test_every_entry_has_the_same_shape(self):
        """L-E19: 依頼・base・PR のどの入口でも input の鍵が同じ（元 works/tests/test_entry_inputs.py の test_build_input_from_each_entry）"""
        keys = {"base", "head_rev", "diff", "requests", "request_file", "pr", "spec"}
        for name, got in (("依頼", self.start(request="request_ok.json")), ("base", self.start(base="base")),
                          ("PR", self.start_with_gh(self.pr_reads(), pr="7")[0])):
            with self.subTest(entry=name):
                doc = self.record(got)
                self.assertEqual(set(doc["input"]), keys)
                self.assertEqual(set(doc["input"]["base"]), {"rev", "from", "name", "label"})

    def test_record_is_where_lib_readers_look(self):
        """L-E24: start が書いた記録を lib の読み手の口（startrec.read）がそのまま読む（置き場が 2 つに割れない）"""
        got = self.start(request="request_ok.json", features_off="world")
        self.assertEqual(startrec.read(self.artifacts), self.record(got))
        self.assertEqual(self.artifacts / got["record"]["path"], startrec.path(self.artifacts))

    def test_spec_word_checked(self):
        """L-E27: spec は空か on。on は input.spec を真に（元 works/tests/test_entry_inputs.py の SpecInputCase.test_spec_word_checked）"""
        self.assertIn("spec", self.refused(request="request_ok.json", spec="yes"))
        self.assertTrue(self.record(self.start(request="request_ok.json", spec="on"))["input"]["spec"])
        self.assertFalse(self.record(self.start(request="request_ok.json"))["input"]["spec"])

    def test_spec_refused_without_request_text(self):
        """L-E29: spec=on なのに依頼の文（依頼も PR の題と本文も）が無ければ止める（元 SpecInputCase の同名）"""
        self.assertIn("依頼の文", self.refused(base="base", spec="on"))

    def test_features_cut_is_recorded(self):
        """L-E33: 機能の切り替えは始めの記録の features_cut に載り、ブロックはそこを読む"""
        self.assertIn("world", self.record(self.start(request="request_ok.json", features_off="world"))["features_cut"])

    def test_test_cmd_and_tdd_suite_are_recorded(self):
        """L-E38: test_cmd・tdd_suite を始めの記録に置く（test-gate と fix が読む）"""
        doc = self.record(self.start(request="request_ok.json", test_cmd="make test", tdd_suite="./junit-suite.sh"))
        self.assertEqual((doc["test_cmd"], doc["tdd_suite"]), ("make test", "./junit-suite.sh"))

    def test_unknown_versions_say_why(self):
        """L-E45: 分からない版の値は null にし、unknown に理由を書く（元 works/.shared/core/versions.py 59-117 行）"""
        bare = self.tmp / "bare-bin"   # git だけを置いた PATH（claude が無い）
        bare.mkdir()
        (bare / "git").symlink_to(shutil.which("git"))
        with mock.patch.dict(os.environ, {"PATH": str(bare)}), \
                mock.patch.object(start.boundary, "lib_root", return_value=self.tmp / "nowhere" / "lib"):
            doc = self.record(self.start(request="request_ok.json"))["versions"]
        for key in ("archon", "claude_code"):
            with self.subTest(key=key):
                self.assertIsNone(doc[key])
                self.assertTrue(doc["unknown"][key])
        self.assertTrue(doc["python"])
        self.assertTrue(doc["platform"])

    def test_start_gate_text_names_entry_features_and_answers(self):
        """L-E48・L-G09: 起動の関所の文は冒頭 3 行・入口の文・機能・最後の関所の開き方・答え方の 2 行を持ち、AI の前に見せる"""
        got = self.start(request="request_ok.json", final_gate="when_needed", features_off="world")
        text = got["gate_text"]
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith("起きたこと: "))
        self.assertIn("入口: 差分なし（HEAD）・依頼 2 件", text)
        self.assertIn("機能: ", text)
        self.assertIn("world off", text)
        self.assertIn("最後の関所: when_needed", text)
        self.assertIn(answer.line(RUN, "continue", "<一言>"), text)
        self.assertIn(answer.line(RUN, "stop", "<理由>"), text)
        self.assertEqual(line_nodes()["gate-start"]["approval"]["message"], "$start.output.gate_text")
        self.assertEqual(line_nodes()["gate-start"]["depends_on"], ["start"])

    def test_gate_text_has_the_depth_word(self):
        """L-E49: 頭の行に段（thickness と（既定））・機能・最後の関所・修正前のテストの任せ先の注を並べる（元 entry.py 1213-1219 行）"""
        text = self.start(request="request_ok.json")["gate_text"]
        self.assertIn("段: 自動（既定）", text)
        self.assertIn("修正前のテスト: 宣言も test_cmd も無い", text)
        text = self.start(request="request_ok.json", thickness="軽量", test_cmd="make test")["gate_text"]
        self.assertIn("段: 軽量", text)
        self.assertNotIn("（既定）", text)
        self.assertNotIn("修正前のテスト:", text)


class PolicyPassedCase(Artifacts):
    """修正前の関所で人が方針の文書の変化（版 A→B）を通したら、answer-before-fix が始めの記録の欄 policy を事前審査が固め直した版 B に
    書き直し、始めの記録を読む fix・eyes・judge の再審が B を読む。止めた答えでは書き直さない"""

    def setUp(self):
        super().setUp()
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, SEED)
        self.doc = self.tmp / "policy.md"
        self.doc.write_text("- 版 A\n", encoding="utf-8")
        self.pointer = start.start(raw(request="request_ok.json", policy_md=str(self.doc)), self.repo, self.artifacts, RUN)["record"]
        self.folder = self.artifacts / boardview.FOLDER
        self.folder.mkdir()
        (self.folder / boardview.POLICY_FILE).write_text(json.dumps(self.record()["policy"]), encoding="utf-8")
        self.doc.write_text("- 版 B\n", encoding="utf-8")
        self.change = boardview.policy_change(self.folder, self.repo)
        self.row = boardview.change_row(self.change)
        boardview._note_asked(self.folder, [(boardview.POLICY_CHANGED, self.row)], self.change)

    def record(self) -> dict:
        return json.loads((self.artifacts / self.pointer["path"]).read_text(encoding="utf-8"))

    def answer(self, decision: str) -> dict:
        return before_fix_answer.answer(json.dumps(self.pointer), self.artifacts, go_raw="true", stop_raw="", place="gate-before-fix",
                                        gate_raw=json.dumps({"decision": decision, "text": "B で進める"}, ensure_ascii=False),
                                        asked_raw=json.dumps([self.row], ensure_ascii=False))

    def test_continue_past_a_policy_change_rewrites_the_record_with_the_refrozen_version(self):
        self.assertTrue(self.answer("continue")["go"])
        rec = self.record()
        self.assertEqual((rec["policy"]["sha256"], rec["policy"]["copy"]), (self.change["to"], self.change["to_copy"]))
        self.assertEqual(policy.frozen_copy(rec), self.change["to_copy"], "fix の役と eyes の prep が読む写し")
        self.assertIn("版 B", fixboard.policy_brief(rec)["paste"])
        self.assertIn("版 B", judge_accept.policy_text(rec), "judge の再審が貼る本文")
        self.answer("continue")
        self.assertEqual(self.record(), rec, "同じ答えをもう 1 度受けても版は変わらない")

    def test_stop_keeps_the_version_of_the_start(self):
        frozen = self.record()["policy"]
        self.assertFalse(self.answer("stop")["go"])
        self.assertEqual(self.record()["policy"], frozen)
        self.assertFalse((self.folder / boardview.GATE_ANSWERS_FILE).exists(), "止めた答えは事前審査の控えにも積まない")

    def test_line_passes_the_start_record(self):
        self.assertEqual(line_nodes()["answer-before-fix"]["with"]["start"], "$start.output.record")


class ReplanAnswerCase(Artifacts):
    def test_refix_answers_carry_the_before_fix_conditions_and_the_replan_note(self):
        """元 replan._notes: 2 度目の修正には修正前の関所の条件と案の直しの関所の一言の両方が届く"""
        got = replan_answer.fix_answers({"decision": "continue", "text": "範囲は stats.py だけ", "asked": ["問い q1（"]},
                                        {"decision": "approve", "text": "項目 1 は\n util.py も"})
        self.assertEqual(got, {"decision": "approve", "text": f"{replan_answer.FIX_NOTES_HEAD}\n\n範囲は stats.py だけ\n\n"
                                                                f"{replan_answer.NOTE_HEAD}\n\n項目 1 は util.py も\n",
                               "asked": ["問い q1（"]})
        self.assertEqual(replan_answer.fix_answers({"decision": "continue", "text": ""}, None),
                         {"decision": "continue", "text": "", "asked": []})
        self.assertEqual(replan_answer.fix_answers(None, {"decision": "continue", "text": "x"})["text"], f"{replan_answer.NOTE_HEAD}\n\nx\n")
        self.assertIsNone(replan_answer.fix_answers(None, None))

    def test_answer_is_the_gate_answer_with_the_fix_answers(self):
        got = replan_answer.answer(json.dumps({"decision": "continue", "text": "x"}), "true", "", "null", "gate-replan", self.artifacts)
        self.assertEqual(got, {"go": True, "answer": {"decision": "continue", "text": "x"}, "stop_reason": "",
                               "fix_answers": {"decision": "continue", "text": f"{replan_answer.NOTE_HEAD}\n\nx\n", "asked": []}})


class FixGateAnswersCase(Artifacts):
    """fix・refix-run に渡す修正前の関所の答えは、関所で見せた問いの行 asked を持ち、fix の置き場の読み（fixboard.gate_asks）が
    人の通した問いの単位を直す義務に戻す（asked が無いと、答えた問いの単位が外されたまま直されない）"""

    FORK = {"key": "q1", "kind": "fork", "status": "held", "origin": "u1", "options": ["a", "b"], "reason": "割れる"}

    def gate_asks(self, name, answers):
        place = self.tmp / name
        place.mkdir()
        (place / fixboard.JUDGMENT_FILE).write_text(json.dumps({"units": [{"key": "u1"}], "questions": [self.FORK]}), encoding="utf-8")
        (place / fixboard.ANSWERS_FILE).write_text(json.dumps(answers, ensure_ascii=False), encoding="utf-8")
        return fixboard.gate_asks(place)

    def test_before_fix_answer_returns_the_asked_unit(self):
        asked = json.dumps([gatemarks.ask_text(self.FORK)], ensure_ascii=False)
        before_fix = before_fix_answer.answer(**self.before_fix_inputs(asked), artifacts=self.artifacts)["answer"]
        replan = gate_answer.answer(json.dumps({"decision": "approve", "text": "直した案でよい"}), "true", "", "gate-replan",
                                    self.artifacts)["answer"]
        for name, answers in (("fix", before_fix), ("refix-run", replan_answer.fix_answers(before_fix, replan)),
                              ("refix-run の関所なし", replan_answer.fix_answers(before_fix, None))):
            with self.subTest(include=name):
                self.assertEqual(self.gate_asks(name, answers), ({}, {"u1"}))

    def before_fix_inputs(self, asked) -> dict:
        """answer-before-fix の script が環境から読む引数"""
        env = {"INPUTS_GATE": json.dumps({"decision": "approve", "text": "q1 は a"}), "INPUTS_GO": "true", "INPUTS_STOP_REASON": "",
               "INPUTS_PLACE": "gate-before-fix", "INPUTS_ASKED": asked}
        with mock.patch.dict(os.environ, env):
            return before_fix_answer.from_env()

    def test_line_passes_the_shown_questions(self):
        self.assertEqual(line_nodes()["answer-before-fix"]["with"]["asked"], "$plan-rounds.output.questions")


class GateAnswerCase(Artifacts):
    def test_skipped_gate_passes_the_decision_before_it(self):
        self.assertEqual(gate_answer.answer("null", "true", "", "gate-final", self.artifacts),
                         {"go": True, "answer": None, "stop_reason": ""})
        self.assertEqual(gate_answer.answer(None, "false", linekit.NEEDS_HUMAN, "gate-final", self.artifacts),
                         {"go": False, "answer": None, "stop_reason": linekit.NEEDS_HUMAN})
        self.assertFalse((self.artifacts / gate_answer.ANSWERS).exists())

    def test_go_words_continue_and_are_recorded(self):
        for word in linekit.GO_WORDS:
            with self.subTest(word=word):
                got = gate_answer.answer(json.dumps({"decision": word, "text": "a.py だけ"}), "true", "", "gate-before-fix",
                                         self.artifacts)
                self.assertEqual(got, {"go": True, "answer": {"decision": word, "text": "a.py だけ"}, "stop_reason": ""})
                kept = json.loads((self.artifacts / "gates" / "gate-before-fix.json").read_text(encoding="utf-8"))
                self.assertEqual(kept, got["answer"])

    def test_stop_word_stops_with_the_gate_named(self):
        got = gate_answer.answer(json.dumps({"decision": "stop", "text": "やめる"}), "true", "", "gate-final", self.artifacts)
        self.assertEqual((got["go"], got["stop_reason"]), (False, "human:gate-final"))
        self.assertEqual(json.loads((self.artifacts / "gates" / "gate-final.json").read_text(encoding="utf-8"))["decision"], "stop")

    def test_reject_stops_like_stop(self):
        got = gate_answer.answer(json.dumps({"decision": linekit.REJECT, "text": ""}), "true", "", "gate-replan", self.artifacts)
        self.assertEqual((got["go"], got["stop_reason"]), (False, "human:gate-replan"))

    def test_unknown_word_stops(self):
        """L-G03: 通す語でない答え（知らない語も）は通さず、止めと読む（元 line_edge.py 191-203 行 _gate_words は知らない語を落とした）"""
        got = gate_answer.answer(json.dumps({"decision": "maybe", "text": ""}), "true", "", "gate-before-fix", self.artifacts)
        self.assertEqual((got["go"], got["stop_reason"]), (False, "human:gate-before-fix"))

    def test_empty_stop_note_gets_the_default_reason(self):
        """L-G07: stop・reject の一言が空なら既定の文を止めの理由にする（元 line_edge.py 98・104 行の GATE_STOP_NOTE・
        FINAL_GATE_STOP_NOTE）。一言が在れば字のまま。通す答えの空の一言は空のまま"""
        for place, word, want in (("gate-final", "stop", gate_answer.FINAL_STOP_NOTE), ("gate-before-fix", "reject", gate_answer.STOP_NOTE),
                                  ("gate-start", "stop", gate_answer.STOP_NOTE)):
            with self.subTest(place=place, word=word):
                got = gate_answer.answer(json.dumps({"decision": word, "text": " "}), "true", "", place, self.artifacts)
                self.assertEqual(got["answer"]["text"], want)
                self.assertEqual(json.loads((self.artifacts / "gates" / f"{place}.json").read_text(encoding="utf-8"))["text"], want)
        self.assertEqual((gate_answer.STOP_NOTE, gate_answer.FINAL_STOP_NOTE), ("関所で止めた", "最後の関所で止めた"))
        got = gate_answer.answer(json.dumps({"decision": "stop", "text": "範囲が違う"}), "true", "", "gate-final", self.artifacts)
        self.assertEqual(got["answer"]["text"], "範囲が違う")
        got = gate_answer.answer(json.dumps({"decision": "continue", "text": ""}), "true", "", "gate-final", self.artifacts)
        self.assertEqual(got["answer"]["text"], "")

    def test_dry_run_approval_reads_as_approve(self):
        got = gate_answer.answer(linekit.DRY_RUN_APPROVED, "true", "", "gate-start", self.artifacts)
        self.assertEqual(got, {"go": True, "answer": {"decision": "approve", "text": ""}, "stop_reason": ""})


def planned(**kw) -> dict:
    got = {"ready": True, "pass": True, "stalled": False, "round": 1, "ask_human": False,
           "gate_axes": {key: {"ok": True, "note": ""} for key in ask_before_fix.AXES}, "questions": []}
    got.update(kw)
    return got


class AskBeforeFixCase(unittest.TestCase):
    def ask(self, plan, unattended=False, design_only=False):
        return ask_before_fix.ask(plan, unattended=unattended, design_only=design_only, run_id=RUN)

    def test_no_plan_goes_nowhere(self):
        self.assertEqual(self.ask(planned(ready=False)), {"open": False, "go": False, "stop_reason": "", "text": "", "deferred": []})

    def test_clean_plan_goes_to_fix_without_the_gate(self):
        self.assertEqual(self.ask(planned()), {"open": False, "go": True, "stop_reason": "", "text": "", "deferred": []})

    def test_reasons_that_open_the_gate(self):
        failing = {**planned()["gate_axes"], "clean": {"ok": False, "note": "名前が合わない"}}
        for plan, words in ((planned(gate_axes=failing), "汚くない（clean）の軸が通らない: 名前が合わない"),
                            (planned(questions=["0 を返すか"]), "0 を返すか"),
                            (planned(ask_human=True), "直す前の関所"),
                            (planned(**{"pass": False, "stalled": True}), gatemarks.STUCK_ITEM),
                            (planned(**{"pass": False, "round": 3}), ask_before_fix.UNSETTLED_ITEM)):
            with self.subTest(words=words):
                got = self.ask(plan)
                self.assertEqual((got["open"], got["go"]), (True, True))
                self.assertIn(words, got["text"])

    def test_design_only_always_opens(self):
        got = self.ask(planned(), design_only=True)
        self.assertTrue(got["open"])
        self.assertIn("設計だけの run", got["text"])

    def test_unattended_moves_questions_to_the_report(self):
        got = self.ask(planned(questions=["0 を返すか"], ask_human=True), unattended=True)
        self.assertEqual(got, {"open": False, "go": True, "stop_reason": "", "text": "", "deferred": ["0 を返すか"]})

    def test_unattended_stops_where_the_gate_would_open(self):
        got = self.ask(planned(**{"pass": False, "stalled": True}), unattended=True)
        self.assertEqual((got["open"], got["go"], got["stop_reason"]), (False, False, linekit.NEEDS_HUMAN))


class AskReplanCase(Artifacts):
    ITEM = {"unit_keys": ["u1"], "narrows": [], "removes": [], "allowed_paths": ["stats.py"], "out_of_scope": [], "rewrite_tests": [],
            "tests": [{"id": "t1", "behavior": "空の列で例外"}]}

    def plan(self, name, item):
        (self.artifacts / name).write_text(json.dumps({"round": 1, "fields": [item]}), encoding="utf-8")
        return {"type": "archon_artifact", "run_id": RUN, "path": name}

    def ask(self, new_item, *, ask_human=False, unattended=False, old=None):
        return ask_replan.ask(old or self.plan("old.json", self.ITEM), self.plan("new.json", new_item), ["1"],
                              ask_human=ask_human, questions=[], unattended=unattended, run_id=RUN)

    def test_same_contract_passes_without_asking(self):
        got = self.ask({**self.ITEM, "approach": "別の手段"})
        self.assertEqual((got["open"], got["go"]), (False, True))

    def test_changed_contract_asks(self):
        got = self.ask({**self.ITEM, "out_of_scope": ["cli.py"]})
        self.assertTrue(got["open"])
        self.assertIn("out_of_scope", got["text"])

    def test_unreadable_plan_asks(self):
        got = self.ask(self.ITEM, old={"type": "archon_artifact", "run_id": "another", "path": "old.json"})
        self.assertTrue(got["open"])
        self.assertIn("読めない", got["text"])

    def test_unattended_passes_widening_only_and_records_it(self):
        got = self.ask({**self.ITEM, "allowed_paths": ["stats.py", "util.py"]}, unattended=True)
        self.assertEqual((got["open"], got["go"]), (False, True))
        self.assertIn("util.py", got["widened"][0])

    def test_unattended_stops_on_a_contract_change(self):
        got = self.ask({**self.ITEM, "out_of_scope": ["cli.py"]}, unattended=True)
        self.assertEqual((got["open"], got["go"], got["stop_reason"]), (False, False, linekit.NEEDS_HUMAN))

    def test_review_asking_human_asks(self):
        self.assertTrue(self.ask(self.ITEM, ask_human=True)["open"])


class AskFinalCase(unittest.TestCase):
    def got(self, **kw):
        return final_got(**kw)

    def ask(self, got, mode="", unattended=False):
        return ask_final.ask(got, mode=mode, unattended=unattended, run_id=RUN)

    def test_always_is_the_default(self):
        got = self.ask(self.got())
        self.assertEqual((got["open"], got["go"], got["reasons"]), (True, True, []))

    def test_protected_hits_and_conflicts_open_in_every_mode(self):
        for mode in ("when_needed", "protected_only"):
            for got in (self.got(protected_hits=["tests/x.py"]), self.got(conflicts=[{"path": "fix/conflicts.json"}])):
                with self.subTest(mode=mode, got=got["protected_hits"] or got["conflicts"]):
                    self.assertTrue(self.ask(got, mode)["open"])

    def test_protected_only_ignores_other_reasons(self):
        self.assertFalse(self.ask(self.got(green=False), "protected_only")["open"])

    def test_unattended_stops_instead_of_opening(self):
        got = self.ask(self.got(), unattended=True)
        self.assertEqual((got["open"], got["go"], got["stop_reason"]), (False, False, linekit.NEEDS_HUMAN))
        self.assertTrue(self.ask(self.got(), "when_needed", unattended=True)["go"])

    def test_unattended_protected_hit_stops(self):
        """守りのパスに当たった無人の run は、protected_only でも関所を開かずに人待ちで止め、merge-apply が飛ぶ（飛んだ関所が go を渡すのは GateAnswerCase）"""
        got = self.ask(self.got(protected_hits=["lib/seal.py（+1 −0）: 規則 seal（lib/seal.py）——封印"]), "protected_only",
                       unattended=True)
        self.assertEqual((got["open"], got["go"], got["stop_reason"]), (False, False, linekit.NEEDS_HUMAN))
        nodes = line_nodes()
        self.assertEqual(nodes["gate-final"]["when"], "$ask-final.output.open == true")
        self.assertEqual(nodes["merge-apply"]["when"], "$answer-final.output.go == true")

    def test_unsealed_is_a_reason(self):
        got = self.got(sealed=False, seal_reason="緑の認証の指紋が今の木と違う")
        self.assertEqual(ask_final.final_needs(got), ["差分を封じられなかった（緑の認証の指紋が今の木と違う）"])
        self.assertTrue(self.ask(got, "when_needed")["open"])

    def test_objection_left_after_the_rejudge_is_a_reason(self):
        self.assertIn("止めずに残った異議が在る", ask_final.final_needs(self.got(objection="異議", rejudge_verdict="退ける")))
        self.assertEqual(ask_final.final_needs(self.got(objection="異議", rejudge_verdict="採る")), [])
        self.assertIn("止めずに残った異議が在る",
                      ask_final.final_needs(self.got(objection="異議", rejudge_verdict="採る", refix_objection="2 度目の異議")))


class AskFinalReadsCase(Artifacts):
    """最後の関所が指し札の先から読む物: 判定の保留の問い（judgment.json）と直した後の実測（structure-after.json）"""

    def place(self, rel, doc):
        path = self.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return {"type": "archon_artifact", "run_id": RUN, "path": rel}

    def judgment(self, questions, units=("u1",)):
        return self.place("judge/judgment.json", {"units": [{"key": k} for k in units], "questions": questions})

    def held(self, questions, *, answers=(), before_fix=None, asked=(), units=("u1",)):
        start_ptr = self.place("start.json", {"answers": list(answers)})
        held, unread = ask_final.held_questions(self.judgment(questions, units), start_ptr, before_fix, list(asked))
        self.assertEqual(unread, "")
        return held

    FORK = {"key": "q1", "kind": "fork", "status": "held", "origin": "u1", "options": ["a", "b"], "reason": "割れる"}

    def test_held_questions_are_every_asking_question_not_answered(self):
        """元 gatemarks.held_lines: 人に聞く状態（held・escalate）の問いは kind を問わず並べ、答えた（answered）問いは並べない"""
        other = {**self.FORK, "key": "q3", "kind": "field", "status": "held"}
        got = self.held([self.FORK, {**self.FORK, "key": "q2", "status": "answered"}, other,
                         {**self.FORK, "key": "q4", "kind": "awaiting", "status": "escalate"}])
        self.assertEqual([q.split("（")[0] for q in got], [f"{gatemarks.ASK_HEAD} {k}" for k in ("q1", "q3", "q4")])
        self.assertIn(f"／{gatemarks.ANSWER_KEY_HEAD}: \"q1\"", got[0])
        self.assertIn("答えが無いと直さない単位: u1", got[0])

    def test_before_fix_answer_answers_only_the_questions_it_was_asked(self):
        q2 = {**self.FORK, "key": "q2", "origin": "u2"}
        passed = {"decision": "continue", "text": "a を選ぶ"}
        got = self.held([self.FORK, q2], before_fix=passed, asked=[gatemarks.ask_text(self.FORK)], units=("u1", "u2"))
        self.assertEqual([q.split("（")[0] for q in got], [f"{gatemarks.ASK_HEAD} q2"])

    def test_hold_names_keep_each_question_held(self):
        """一言の「保留: <key>」で名指した問いは、関所に載せて continue で通しても保留のまま（問いごと）"""
        q2 = {**self.FORK, "key": "q2", "origin": "u2"}
        asked = [gatemarks.ask_text(self.FORK), gatemarks.ask_text(q2)]
        got = self.held([self.FORK, q2], before_fix={"decision": "approve", "text": "q1 は a。保留: q2"}, asked=asked,
                        units=("u1", "u2"))
        self.assertEqual([q.split("（")[0] for q in got], [f"{gatemarks.ASK_HEAD} q2"])

    def test_stopped_or_absent_gate_answers_nothing(self):
        for before_fix in (None, {"decision": "stop", "text": "やめる"}):
            with self.subTest(before_fix=before_fix):
                self.assertEqual(len(self.held([self.FORK], before_fix=before_fix, asked=[gatemarks.ask_text(self.FORK)])), 1)

    def test_request_answers_answer_by_key_or_origin(self):
        self.assertEqual(self.held([self.FORK], answers=[{"question": "q1", "text": "a"}]), [])
        self.assertEqual(self.held([self.FORK], answers=[{"question": "u1", "text": "a"}]), [])
        both = [self.FORK, {**self.FORK, "key": "q2"}]
        self.assertEqual(len(self.held(both, answers=[{"question": "u1", "text": "a"}])), 2, "2 つの問いに当たる答えはどれにも答えない")

    def test_answered_unit_missing_from_the_judgment_is_said(self):
        got = self.held([self.FORK], answers=[{"question": "q1", "text": "a"}], units=())
        self.assertEqual(got, ["関所で答えたが直す単位に入れられなかった: q1・u1（理由: 今の周の判定に無い）"])

    def test_unreadable_judgment_is_said(self):
        held, unread = ask_final.held_questions({"type": "archon_artifact", "run_id": "another", "path": "x.json"}, None, None, [])
        self.assertEqual(held, [])
        self.assertIn("判定の問いの控えか始めの記録を読めない", unread)
        self.assertEqual(ask_final.held_questions(None, None, None, []), ([], ""))

    def test_fence_rows_come_from_the_structure_after(self):
        rise = {"concept": "止め", "what": "語", "path": "a.py", "before": 1, "after": 2}
        ptr = self.place("eyes/structure-after.json", {"status": "ok", "reason": "", "deviations": [],
                                                       "after": {"tables": ["t"], "fence_up": [rise]}})
        rows, unread = ask_final.fenced_rows(ptr)
        self.assertEqual(([row["where"] for row in rows], unread), (["a.py"], ""))
        self.assertEqual(ask_final.fenced_rows(None), ([], ""))

    def test_unreadable_structure_after_is_said(self):
        rows, unread = ask_final.fenced_rows({"type": "archon_artifact", "run_id": "another", "path": "eyes/structure-after.json"})
        self.assertEqual(rows, [])
        self.assertIn("指し札を読めない", unread)
        rows, unread = ask_final.fenced_rows(self.place("eyes/structure-after.json", {"status": "?"}))
        self.assertEqual(rows, [])
        self.assertIn("控え structure-after.json を読めない", unread)

    def test_unread_is_shown_in_the_gate_text(self):
        text = ask_final.final_text(final_got(unread=["読めない訳"]), [], RUN)
        self.assertIn("- 読めない訳", text)


class PlanOutCase(unittest.TestCase):
    def got(self, **kw):
        base = {key: None for key in plan_out.PLAN + plan_out.REVIEW}
        base.update({"ready": True, "round": 1, "pass": False, "stalled": False})
        base.update(kw)
        return plan_out.plan_out(base)

    def test_done_rules(self):
        self.assertFalse(self.got()["done"])
        for kw in ({"ready": False}, {"pass": True}, {"stalled": True}, {"round": 3}):
            with self.subTest(kw=kw):
                self.assertTrue(self.got(**kw)["done"])

    def test_every_field_is_returned(self):
        self.assertEqual(set(self.got()), set(plan_out.PLAN + plan_out.REVIEW) | {"done", "stop_reason"})


class AfterFixAndJudgedCase(Artifacts):
    def test_after_fix_counts(self):
        self.assertEqual(after_fix.decide([], ""), {"replan": False, "rejudge": False, "stop_reason": ""})
        self.assertEqual(after_fix.decide(["1"], " 異議 "), {"replan": True, "rejudge": True, "stop_reason": ""})

    def judgment(self, rel, units):
        (self.artifacts / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.artifacts / rel).write_text(json.dumps({"units": units, "questions": []}), encoding="utf-8")
        return {"type": "archon_artifact", "run_id": RUN, "path": rel}

    def returned(self, ptr, verdict=None):
        return {"units": [{"id": "x"}], "judgment": ptr, "purpose": "p", "world": None, "rejudge_verdict": verdict}

    def test_judged_without_the_rejudge_is_the_judge(self):
        judge = self.returned(self.judgment("judge/judgment.json", []))
        got = judged.judged(judge, None, "")
        self.assertEqual((got["judgment"], got["rejudged"], got["new_open_units"], got["lowered"], got["unnamed_changed"]),
                         (judge["judgment"], False, [], [], []))

    def test_judged_compares_the_two_judgments_like_the_original(self):
        """元 rejudge.collect と diff_units の意味: 開いた単位は再審の後に開いた物、下げた単位は block から下げた物、
        名指していない変化は異議の文が key も番号も名指さない変わった単位"""
        before = [{"key": "a", "label": "block", "disposition": "fix"}, {"key": "b", "label": "suggest", "disposition": "later"},
                  {"key": "c", "label": "block", "disposition": "fix"}, {"key": "d", "label": "nit", "disposition": "later"}]
        after = [{"key": "a", "label": "suggest", "disposition": "later"}, {"key": "b", "label": "suggest", "disposition": "do-now"},
                 {"key": "c", "label": "block", "disposition": "fix"}, {"key": "d", "label": "nit", "disposition": "drop"},
                 {"key": "e", "label": "block", "disposition": "fix"}]
        judge = self.returned(self.judgment("judge/judgment.json", before))
        again = self.returned(self.judgment("rejudge/judgment.json", after), "一部採る")
        got = judged.judged(judge, again, "a は直さなくてよい。no 2 も")
        self.assertEqual((got["judgment"], got["rejudged"], got["rejudge_verdict"]), (again["judgment"], True, "一部採る"))
        self.assertEqual(got["new_open_units"], ["b", "e"])
        self.assertEqual(got["lowered"], ["a"])
        self.assertEqual(got["unnamed_changed"], ["d", "e"])
        self.assertEqual(got["unread"], "")

    def test_rejudge_stop_holds_the_line(self):
        """L-D48: 再審が止まった run（3 回拒まれた・支度ができない）は、judged が再審の止めの理由を返し、fixed が試験の関門（final）・
        独立の目・merge へ進めない（元 works/.shared/core/rejudge.py 546-558 行）。止まらない再審と、再審の無い run は止めない"""
        judge = self.returned(self.judgment("judge/judgment.json", []))
        stopped = {**self.returned(judge["judgment"]), "units": []}
        got = judged.judged(judge, stopped, "異議", "works:rejudge")
        self.assertEqual(got["stop_reason"], "works:rejudge")
        fix = FixedCase.fix(FixedCase())
        self.assertEqual((lambda f: (f["done"], f["go"]))(fixed.fixed(fix, None, replan=False, stops=("", got["stop_reason"]))),
                         (False, False))
        self.assertEqual(judged.judged(judge, self.returned(judge["judgment"], "採る"), "異議", "")["stop_reason"], "")
        self.assertEqual(judged.judged(judge, None, "", "works:rejudge")["stop_reason"], "", "再審が走らなければ止めの理由は無い")
        nodes = line_nodes()
        self.assertEqual(nodes["judged"]["with"]["rejudge_stop_reason"], {"from": "$rejudge-run.output.stop_reason", "if_skipped": None})
        self.assertEqual(nodes["fixed"]["with"]["stop_judged"], "$judged.output.stop_reason")
        self.assertIn("$fixed.output.go == true", nodes["test-gate-final"]["when"])

    def test_unreadable_judgments_are_said(self):
        judge = self.returned({"type": "archon_artifact", "run_id": "another", "path": "judge/judgment.json"})
        got = judged.judged(judge, self.returned(judge["judgment"]), "")
        self.assertEqual((got["new_open_units"], got["lowered"], got["unnamed_changed"], got["stop_reason"]), ([], [], [], ""))
        self.assertIn("比べられない", got["unread"])


class FixedCase(unittest.TestCase):
    def fix(self, **kw):
        got = {"done": True, "units": [{"unit_id": "u1", "status": "given_up"}], "groups": [{"group_id": "g1"}],
               "conflicts": {"path": "fix/conflicts.json"}, "replan_items": ["1"], "objection": "", "diff": {"path": "fix/diff"},
               "allowed_test_changes": ["tests/a.py"], "changed": {"path_changed": False}, "delta_review": {"rounds": 1, "pass": True}}
        got.update(kw)
        return got

    def test_first_fix_alone(self):
        got = fixed.fixed(self.fix(), None, replan=False, stops=("", ""))
        self.assertEqual((got["conflicts"], got["refixed"], got["diff"]), ([{"path": "fix/conflicts.json"}], False, {"path": "fix/diff"}))
        self.assertTrue(got["done"])

    def test_replan_without_the_second_fix_is_not_done(self):
        """案の直しの関所の stop・無人の止め・案ができなかった時に、1 回目の修正の差分を試験の関門から先へ進めない"""
        self.assertFalse(fixed.fixed(self.fix(), None, replan=True, stops=("", ""))["done"])

    def test_a_line_script_stop_before_is_not_done(self):
        for stops in ((linekit.LINE_SCRIPT, ""), ("", linekit.LINE_SCRIPT)):
            with self.subTest(stops=stops):
                self.assertFalse(fixed.fixed(self.fix(), None, replan=False, stops=stops)["done"])

    def test_review_not_passed_still_goes_to_the_final_test(self):
        """今の works の最後のテスト p4.ci は手直しの段（p3.delta_fix・p3.delta_fix2）が済むのを待つだけで、差分の審査が通ったかを
        待たない。審査が回って通らなかった run も最後のテスト・独立の目・最後の関所へ進め（go）、done は偽のまま報告の残りに載る。
        審査が回らなかった（変更の確かめが通らなかった）run と、線の止めは進めない"""
        failed = self.fix(done=False, delta_review={"rounds": 2, "pass": False})
        got = fixed.fixed(failed, None, replan=False, stops=("", ""))
        self.assertEqual((got["done"], got["go"]), (False, True))
        self.assertTrue(fixed.fixed(self.fix(), None, replan=False, stops=("", ""))["go"])
        for fix, replan, stops in ((self.fix(done=False, delta_review={"rounds": 0, "pass": False}), False, ("", "")),
                                   (failed, True, ("", "")), (failed, False, (linekit.LINE_SCRIPT, ""))):
            with self.subTest(review=fix["delta_review"], replan=replan, stops=stops):
                self.assertFalse(fixed.fixed(fix, None, replan=replan, stops=stops)["go"])

    def test_final_test_waits_on_go(self):
        self.assertIn("$fixed.output.go == true", line_nodes()["test-gate-final"]["when"])

    def test_refix_is_merged_without_losing_the_first(self):
        refix = self.fix(units=[{"unit_id": "u1", "status": "fixed"}, {"unit_id": "u2", "status": "fixed"}], groups=[{"group_id": "g2"}],
                         conflicts=None, replan_items=[], diff={"path": "refix/diff"}, allowed_test_changes=["tests/b.py"])
        got = fixed.fixed(self.fix(), refix, replan=True, stops=("", ""))
        self.assertTrue(got["done"])
        self.assertEqual(got["units"], [{"unit_id": "u1", "status": "fixed"}, {"unit_id": "u2", "status": "fixed"}])
        self.assertEqual(got["groups"], [{"group_id": "g1"}, {"group_id": "g2"}])
        self.assertEqual(got["conflicts"], [{"path": "fix/conflicts.json"}])
        self.assertEqual(got["allowed_test_changes"], ["tests/a.py", "tests/b.py"])
        self.assertEqual((got["diff"], got["replan_items"], got["refixed"]), ({"path": "refix/diff"}, ["1"], True))

    def test_eyes_get_the_replanned_plan(self):
        """L-W56: 独立の目が照らす修正案と波及は、案の直しの後（2 度目の修正が走った run）は案の直しの物に差し替えた承認済みの物
        （元 works/darkfactory/lib/line_edge.py 1058-1064 行）。2 度目の修正が走らなければ計画の往復の物"""
        again = {"ready": True, "plan": {"path": "replan/plan-fields.json"}, "ripple": {"path": "replan/ripple.json"}, "depth": []}
        plans = {"plan": {"path": "plan/plan-fields.json"}, "ripple": {"path": "plan/ripple.json"}, "replanned": again}
        got = fixed.fixed(self.fix(), self.fix(), replan=True, stops=("", ""), plans=plans)
        self.assertEqual((got["plan"], got["ripple"]), (again["plan"], again["ripple"]))
        got = fixed.fixed(self.fix(), None, replan=True, stops=("", ""), plans=plans)
        self.assertEqual((got["plan"], got["ripple"]), (plans["plan"], plans["ripple"]))
        nodes = line_nodes()
        self.assertEqual({k: nodes["eyes"]["with"][k] for k in ("plan", "ripple")},
                         {"plan": "$fixed.output.plan", "ripple": "$fixed.output.ripple"})
        self.assertEqual({k: nodes["fixed"]["with"][k] for k in (*fixed.PLANS, "replanned")},
                         {"plan": "$plan-rounds.output.plan", "ripple": "$plan-rounds.output.ripple",
                          "replanned": {"from": "$replan-out.output.got", "if_skipped": None}})
        self.assertIn("replan-out", nodes["fixed"]["depends_on"])

    def test_refix_objection_is_kept_beside_the_first(self):
        """再審が受けるのは 1 回目の異議。2 度目の修正の異議は捨てず、再審されずに残った異議として refix_objection で運ぶ"""
        got = fixed.fixed(self.fix(objection="u1 は誤り"), self.fix(objection="u2 も誤り"), replan=True, stops=("", ""))
        self.assertEqual((got["objection"], got["refix_objection"]), ("u1 は誤り", "u2 も誤り"))
        self.assertEqual(fixed.fixed(self.fix(), None, replan=False, stops=("", ""))["refix_objection"], "")


class RedepthCase(unittest.TestCase):
    LIGHT = [{"unit_id": "u1", "depth": "軽量", "why": "配線だけ"}]

    def redepth(self, *, units=(), conflicts=(), questions=(), answer=None, replanned=False, rejudged=False, replanned_depth=None):
        return redepth.redepth(self.LIGHT, replanned_depth, list(units), list(conflicts), list(questions), answer,
                               replanned=replanned, rejudged=rejudged)

    def test_quiet_run_stays_light_and_names_what_it_skips(self):
        got = self.redepth(units=[{"unit_id": "u1", "status": "fixed"}])
        self.assertEqual(got["depth"][0]["depth"], "軽量")
        self.assertTrue(got["skip_optional"])

    def test_signals_raise_to_standard(self):
        for kw in ({"units": [{"unit_id": "u1", "status": "given_up"}]}, {"conflicts": [{"path": "c"}]}, {"questions": ["q"]},
                   {"replanned": True}, {"rejudged": True}):
            with self.subTest(kw=kw):
                got = self.redepth(**kw)
                self.assertEqual((got["depth"][0]["depth"], got["skip_optional"]), ("標準", ""))

    def test_answered_questions_do_not_raise(self):
        self.assertEqual(self.redepth(questions=["q"], answer={"decision": "approve", "text": ""})["depth"][0]["depth"], "軽量")

    def test_replanned_depth_wins(self):
        got = self.redepth(replanned_depth=[{"unit_id": "u9", "depth": "標準", "why": "直した案"}], replanned=True)
        self.assertEqual([row["unit_id"] for row in got["depth"]], ["u9"])


class ReturnedCase(unittest.TestCase):
    def test_fields_are_gathered_and_strings_stay_strings(self):
        env = {"ok": "true", "hash": "123", "mode": "seal", "diff": "null", "protected_hits": "[]", "reason": ""}
        self.assertEqual(returned.returned("merge", env.get),
                         {"got": {"mode": "seal", "ok": True, "hash": "123", "diff": None, "protected_hits": [], "reason": ""},
                          "stop_reason": ""})


class CollectAndResultCase(unittest.TestCase):
    def line(self, **kw):
        got = {"start": "null", "fixed": None,
               "gates": {"gate_start": "null", "gate_before_fix": "null", "gate_replan": "null", "gate_final": "null"}}
        got.update(kw)
        return got

    def test_fields_are_the_inputs_report_declares(self):
        declared = yaml.safe_load((SCRIPTS.parents[1] / "report" / "works-factory-report.yaml").read_text(encoding="utf-8"))["inputs"]
        got = collect.collect({}, self.line())
        self.assertEqual(set(got), {name.replace("-", "_") for name in declared})
        self.assertEqual(collect.fallback("x").keys(), got.keys())

    def test_skipped_receiver_is_null(self):
        seal = {"got": {"mode": "seal", "ok": True, "hash": "123"}, "stop_reason": ""}
        got = collect.collect({"judge": "null", "merge_seal": json.dumps(seal), "plan_rounds": None}, self.line())
        self.assertIsNone(got["judge"])
        self.assertEqual(got["merge_seal"], seal["got"])
        self.assertEqual((got["plan"], got["plan_review"], got["fix"]), (None, None, None))

    def test_plan_rounds_are_split_into_plan_and_review(self):
        rounds = {key: None for key in returned.SHAPES["plan_rounds"]}
        rounds.update({"ready": False, "round": 1, "stop_reason": ""})
        got = collect.collect({"plan_rounds": json.dumps({"got": rounds, "stop_reason": ""})}, self.line())
        self.assertEqual(got["plan"], {key: rounds[key] for key in plan_out.PLAN})
        self.assertIsNone(got["plan_review"])

    def test_fix_is_the_first_and_second_fix_merged(self):
        """report の入力 fix は 1 回目と 2 度目の修正を合わせた物（申し出 conflicts は段ごとの指し札の配列）。合わせる節 fixed が
        飛ばされた（2 度目の修正の中が落ちた）時は 1 回目の返り。修正が走らなければ null"""
        first = {"got": {"done": True, "conflicts": "c1"}, "stop_reason": ""}
        merged = {"done": True, "conflicts": ["c1", "c2"], "refixed": True, "stop_reason": ""}
        got = collect.collect({"fix": json.dumps(first)}, self.line(fixed=json.dumps(merged)))
        self.assertEqual(got["fix"], merged)
        self.assertEqual(collect.collect({"fix": json.dumps(first)}, self.line())["fix"], first["got"])
        self.assertIsNone(collect.collect({"fix": "null"}, self.line(fixed=json.dumps(merged)))["fix"])

    def test_gate_answers_and_the_start_pass_through(self):
        stop = {"decision": "stop", "text": "範囲が違う"}
        ptr = {"type": "archon_artifact", "run_id": "r", "path": "start.json"}
        gates = {"gate_start": "null", "gate_before_fix": "null", "gate_replan": "null", "gate_final": json.dumps(stop)}
        got = collect.collect({}, self.line(start=json.dumps(ptr), gates=gates))
        self.assertEqual((got["start"], got["gate_final"], got["gate_start"]), (ptr, stop, None))

    def test_result_carries_what_apply_reads(self):
        """線の返りの欄 apply・sealed・r2_status・final_answer（bin/apply と段 1 が読む）は collect が集めた返りから組み、飛ばされた段は
        null。result は merge・eyes・関所の返りを直に読まず collect を通す"""
        seal = {"mode": "seal", "ok": True, "hash": "h", "diff": {"path": "merge/sealed.diff"}, "protected_hits": [], "reason": ""}
        put = {**seal, "mode": "apply", "diff": {"path": "merge/apply.diff"}}
        eyes = {"ok": True, "r2": {"status": "pass", "reason": ""}}
        answer = {"decision": "stop", "text": "やめる"}
        got = result.result({"outcome": "fixed"}, {"merge_apply": put, "merge_seal": seal, "eyes": eyes, "gate_final": answer})
        self.assertEqual(got["apply"], {"ok": True, "hash": "h", "diff": {"path": "merge/apply.diff"}, "reason": ""})
        self.assertEqual(got["sealed"], {"ok": True, "hash": "h", "diff": {"path": "merge/sealed.diff"}})
        self.assertEqual((got["r2_status"], got["final_answer"]), ("pass", answer))
        got = result.result({"outcome": ""}, {"merge_apply": None, "merge_seal": None, "eyes": {"ok": True, "r2": None}, "gate_final": None})
        self.assertEqual((got["apply"], got["sealed"], got["r2_status"], got["final_answer"]), (None, None, None, None))
        with_ = line_nodes()["result"]["with"]
        for key in ("merge_apply", "merge_seal", "eyes", "gate_final"):
            with self.subTest(key=key):
                self.assertEqual(with_[key], {"from": f"$collect.output.{key}", "if_skipped": None})
        self.assertFalse([v for v in with_.values() if "$merge-" in json.dumps(v) or "$eyes" in json.dumps(v)])

    def test_result_fixed(self):
        for outcome, want in (("fixed", True), ("fixed_needs_check", True), ("no_fix_needed", False), ("", False)):
            with self.subTest(outcome=outcome):
                self.assertEqual(result.result({"outcome": outcome})["fixed"], want)


class LinekitCase(unittest.TestCase):
    def test_script_failure_is_returned_not_raised(self):
        def boom():
            raise ValueError("壊れた\n入力")

        with mock.patch.object(linekit.boundary, "returns") as returns, mock.patch("sys.stderr"):
            linekit.run(boom, lambda reason: {"stop_reason": linekit.LINE_SCRIPT, "reason": reason})
        returns.assert_called_once_with({"stop_reason": linekit.LINE_SCRIPT, "reason": "ValueError: 壊れた 入力"})

    def test_line_stop_words_are_what_stopby_declares(self):
        for word, meaning in linekit.DECLARED.items():
            with self.subTest(word=word):
                self.assertEqual(stopby.declare(word.removeprefix(stopby.HEAD), meaning), word)

    def test_skipped_values(self):
        self.assertEqual((linekit.value("null"), linekit.text("null"), linekit.flag("true"), linekit.items("[1]")), (None, "", True, [1]))
        self.assertEqual((linekit.value("abc"), linekit.text("abc"), linekit.items("null")), ("abc", "abc", []))


TYPES = {"boolean": bool, "string": str, "array": list, "object": dict, "integer": int, "null": type(None)}


def script_nodes() -> dict:
    return {key: node for key, node in line_nodes().items() if "script" in node}


class FallbackCase(unittest.TestCase):
    """線の script の例外の返り fallback が、節の output_format に合い（合わなければ Archon が節を落とし、報告が届かない）、
    止めの理由 works:line-script を持ち（collect は始めの記録を null にし）、関所を通さないこと"""

    def test_every_fallback_fits_its_node_and_stops(self):
        for key, node in script_nodes().items():
            with self.subTest(node=key):
                got = load(node["script"]).fallback("boom")
                shape = node["output_format"]
                self.assertLessEqual(set(shape["required"]), set(got))
                for field, rule in shape["properties"].items():
                    kinds = rule.get("type")
                    if kinds is not None:
                        self.assertIsInstance(got[field], tuple(TYPES[k] for k in ([kinds] if isinstance(kinds, str) else kinds)), field)
                if key == "collect":   # report に止めの理由の入力が無い。始めの記録が届かないので report が結果を名乗らない
                    self.assertIsNone(got["start"])
                else:
                    self.assertEqual(got["stop_reason"], linekit.LINE_SCRIPT)
                self.assertIsNot(got.get("go"), True)
                if key != "plan-out":   # plan-out の done は往復を抜けるか（例外の時は抜ける）で、修正へ進むかではない
                    self.assertIsNot(got.get("done"), True)


class BrokenLibCase(unittest.TestCase):
    """lib/ が読めなくても、線の script は節として落ちず、fallback の返り（止めの理由 works:line-script）を返す。
    lib/ を import する script を、空の lib/ を指す WORKS_FACTORY_ROOT で本当に走らせる"""

    def test_lib_import_failure_is_returned_not_raised(self):
        guarded = [node for node in script_nodes().values() if "guarded_imports" in (SCRIPTS / f"{node['script']}.py").read_text()]
        self.assertGreaterEqual(len(guarded), 5)
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "lib").mkdir()
            env = {**os.environ, "WORKS_FACTORY_ROOT": tmp, "WORKFLOW_ID": RUN, "ARTIFACTS_DIR": tmp, "INPUTS_PLACE": "gate"}
            for node in guarded:
                with self.subTest(script=node["script"]):
                    done = subprocess.run([sys.executable, str(SCRIPTS / f"{node['script']}.py")], cwd=tmp, env=env,
                                          capture_output=True, text=True)
                    self.assertEqual(done.returncode, 0, done.stderr)
                    self.assertEqual(json.loads(done.stdout)["stop_reason"], linekit.LINE_SCRIPT)
                    self.assertIn("ModuleNotFoundError", done.stderr)


class GateDecisionsCase(unittest.TestCase):
    """人の関所は 4 つで、どれも関所の文が見せる答えの語（lib/answer.py の VERBS）と approve・reject を受け、受ける語は通す語
    （linekit.GO_WORDS）か止める語（VERBS のうち通す語でない物と reject。gate_answer は通す語でない答えを止めと読む）だけ。
    reject が decisions に無いと、Archon はその答えを run の取り消しとして扱い、報告が出ない"""

    def test_gates_take_the_words_their_text_prints(self):
        gates = {key: node for key, node in line_nodes().items() if "approval" in node}
        self.assertEqual(set(gates), {"gate-start", "gate-before-fix", "gate-replan", "gate-final"})
        stop_words = set(answer.VERBS) - set(linekit.GO_WORDS)
        self.assertEqual(stop_words, {"stop"})
        for key, node in gates.items():
            with self.subTest(gate=key):
                self.assertEqual({d["id"] for d in node["approval"]["decisions"]},
                                 set(linekit.GO_WORDS) | set(answer.VERBS) | {linekit.REJECT})


class Recorded(dict):
    """読まれた環境変数の名を控える os.environ の代わり"""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.read = set()

    def get(self, key, default=None):
        self.read.add(key)
        return super().get(key, default)


class LineWiringCase(unittest.TestCase):
    """返しの節の with: の鍵と、その script が読む INPUTS_<名> が同じ（片方だけ欄を足すと、欄が黙って報告から落ちる）"""

    READERS = {
        "plan-out": lambda: plan_out.from_env(),
        "judged": lambda: judged.from_env(),
        "fixed": lambda: fixed.from_env(),
        "collect": lambda: (collect.received_of_env(), collect.line_of_env()),
        "ask-final": lambda: ask_final.from_env(),
        "answer-before-fix": lambda: before_fix_answer.from_env(),
        "result": lambda: (result.from_env(), result.line_of_env()),
    }

    def test_with_keys_are_what_the_script_reads(self):
        nodes = line_nodes()
        readers = {**self.READERS, **{key: returned.from_env for key, node in nodes.items() if node.get("script") == "returned"}}
        for key, read in readers.items():
            with self.subTest(node=key):
                env = Recorded(WORKFLOW_ID=RUN)
                if nodes[key].get("script") == "returned":
                    env["INPUTS_BLOCK"] = nodes[key]["with"]["block"]
                with mock.patch.object(os, "environ", env):
                    read()
                self.assertEqual(env.read, {f"INPUTS_{name.upper()}" for name in nodes[key]["with"]})

    def test_every_include_and_the_plan_rounds_have_a_receiver_that_collect_reads(self):
        """ブロックの返す節が落ちても報告が出るように、collect は返りを受け皿 <id>-out からだけ読む。2 度目の修正 refix-run は、
        1 回目と合わせた節 fixed を通して読む（fixed は refix-run が落ちると飛ばされ、collect は 1 回目の返りに戻る）"""
        nodes = line_nodes()
        inside = {node["id"] for node in nodes["plan-rounds"]["loop_group"]["nodes"]}
        received = [key for key, node in nodes.items() if "include" in node and key not in ("report", "refix-run") and key not in inside]
        self.assertEqual(nodes["collect"]["with"]["fixed"], {"from": "$fixed.output", "if_skipped": None})
        self.assertIn("refix-run", nodes["fixed"]["depends_on"])
        self.assertEqual(nodes["fixed"]["trigger_rule"], "none_failed_min_one_success")
        received.append("plan-rounds")
        reads = {v["from"] for v in nodes["collect"]["with"].values() if isinstance(v, dict)}
        for key in received:
            with self.subTest(node=key):
                receiver = nodes.get(f"{key}-out")
                self.assertIsNotNone(receiver)
                self.assertEqual((receiver["script"], receiver["depends_on"], receiver.get("trigger_rule")), ("returned", [key], None))
                self.assertIn(f"{key}-out", nodes["collect"]["depends_on"])
                self.assertIn(f"${key}-out.output", reads)
                self.assertFalse(any(f"${key}.output" in v for v in reads), "collect がブロックの返りを直に読む")

    def test_line_includes_the_eight_blocks(self):
        """線が差し込むのは 8 つのブロックで、どれも workflows/ に在る（無ければ block_doc が落ちて赤）"""
        includes = {node["include"] for node in line_nodes().values() if "include" in node}
        self.assertEqual(includes, {f"works-factory-{name}" for name in BLOCKS})
        for name in sorted(includes):
            with self.subTest(block=name):
                self.assertIn("inputs", block_doc(name))

    def test_blocks_get_the_start_answers_and_prior_failures(self):
        """ブロックが宣言する、線の頭が決める入力は渡す（既定値 null のまま黙って落ちない）"""
        from_the_start = {"prior_failures": "$start.output.prior_failures", "start_answers": "$answer-start.output.answer"}
        for key, node in line_nodes().items():
            if "include" not in node:
                continue
            for name in from_the_start.keys() & block_doc(node["include"])["inputs"].keys():
                with self.subTest(node=key, input=name):
                    self.assertEqual(node["with"].get(name), from_the_start[name])

    UNPASSED = {
        "plan-review-run": {"conflicts", "gate_answers"},   # 計画の往復は修正の前。申し出も修正前の関所の答えもまだ無い
        "fix": {"only_items", "mode", "group", "from_tree", "out_dir"},   # docs/design.md の「約束に無い入力（線は渡さない）」
        "refix-run": {"mode", "group", "from_tree", "out_dir"},
        "merge-seal": {"answer", "r2", "sealed_hash"},   # apply の時だけ
        "eyes": {"x_scalars"},   # issue #110
    }

    def test_includes_pass_every_declared_input_but_the_named(self):
        """ブロックへの with: の鍵はそのブロックの inputs: の宣言の中に在り、宣言する入力は UNPASSED に名指した物のほかは全部渡す
        （既定値のまま黙って落ちない。約束の「← $…」の入力は宣言の中に在る）。名指した物に required は無い。report には宣言の全部を
        渡す（報告は全部の段の返りと関所の答えを読む）"""
        for key, node in line_nodes().items():
            if "include" not in node:
                continue
            declared = block_doc(node["include"])["inputs"]
            passed = set(node.get("with") or {})
            with self.subTest(node=key):
                self.assertLessEqual(passed, set(declared))
                self.assertEqual(set(declared) - passed, self.UNPASSED.get(key, set()))
                self.assertFalse([name for name in self.UNPASSED.get(key, ()) if declared[name].get("required")])

    def test_fix_and_refix_get_their_plan_and_gate_answers(self):
        """筋書きはブロックの script に include の入力を渡さない（docs/design.md の U3）ので、修正の段に届く物はここで照らす: 1 回目は計画の往復の
        案と修正前の関所の答え、2 度目は案の直しの案と両方の関所を合わせた答え、直すのは 1 回目が返した計画の項目だけ"""
        nodes = line_nodes()
        self.assertEqual({k: nodes["fix"]["with"][k] for k in ("plan", "ripple", "depth", "answers")},
                         {"plan": "$plan-rounds.output.plan", "ripple": "$plan-rounds.output.ripple",
                          "depth": "$plan-rounds.output.depth", "answers": "$answer-before-fix.output.answer"})
        self.assertNotIn("only_items", nodes["fix"]["with"])
        self.assertEqual({k: nodes["refix-run"]["with"][k] for k in ("plan", "ripple", "depth", "answers", "only_items")},
                         {"plan": "$replan.output.plan", "ripple": "$replan.output.ripple", "depth": "$replan.output.depth",
                          "answers": "$answer-replan.output.fix_answers", "only_items": "$fix.output.replan_items"})

    def test_replan_gets_ruling_and_conflicts(self):
        """L-D24: 案の直しの役に、裁かれた項目（ruling）と申し出・裁定の文（conflicts）を渡す（元 works/.shared/core/replan.py:116
        REPLAN_ASK・:387 _section）"""
        got = line_nodes()["replan"]["with"]
        self.assertEqual((got["ruling"], got["conflicts"]), ("$fix.output.replan_items", "$fix.output.conflicts"))

    def test_replan_review_gets_the_conflicts(self):
        """L-D25・P139: 案の直しの事前審査に申し出と裁定の行（fix の conflicts.json の指し札）を渡す（元 replan.py:593 _gate_section）。
        事前審査は項目ごとの申し出と裁定の文を材料に貼る（boardview.open_pass の conflicts）"""
        got = line_nodes()["replan-review"]["with"]
        self.assertEqual((got["conflicts"], got["ruling"]), ("$fix.output.conflicts", "$fix.output.replan_items"))

    def test_replan_review_gets_the_before_fix_answer(self):
        """L-D26・L-G29・P244: 事前審査の 2 度目の差し込みに修正前の関所の答え {decision, text, asked} を渡し、人が continue で通した行
        （狭め・穴・世界の解の外れ・構造の設計の問い・方針の変化）を聞き直さない（元 review-loop.py:4134 human_gate_answered）"""
        self.assertEqual(line_nodes()["replan-review"]["with"]["gate_answers"], "$answer-before-fix.output.answer")

    def test_plan_review_gets_conflicts_and_gate_answers(self):
        """P152・L-W45: 事前審査の差し込みのうち、修正の後に走る replan-review には申し出と関所の答えの両方が届き、修正前の関所より前に
        走る往復の中の plan-review-run には渡さない（まだ無い。UNPASSED に訳つき）"""
        nodes = line_nodes()
        self.assertLessEqual({"conflicts", "gate_answers"}, set(nodes["replan-review"]["with"]))
        self.assertFalse({"conflicts", "gate_answers"} & set(nodes["plan-review-run"]["with"]))
        self.assertEqual(self.UNPASSED["plan-review-run"], {"conflicts", "gate_answers"})
        self.assertNotIn("replan-review", self.UNPASSED)

    def test_include_ids_are_not_loop_body_ids(self):
        """展開した後の節の id が重ならない: Archon は差し込んだブロックの頭の段の節にだけ `<include の id>__` を付け、輪の中の節の id は
        そのまま残す。線の差し込みの名（頭の段と線の輪の中）は、輪の中の `$<名>.output` までブロックの返す節へ書き換わる
        （include-expander.ts の renameIncludeRef）ので、線と差し込む全ブロック（入れ子も）の輪の中の節の名と重なると、ブロックの
        輪の中の節が線の節を読む"""
        def body_ids(nodes, inside=False):
            got = set()
            for node in nodes:
                if "include" in node:
                    got |= body_ids(block_doc(node["include"])["nodes"])
                elif inside:
                    got.add(node["id"])
                if "loop_group" in node:
                    got |= body_ids(node["loop_group"]["nodes"], inside=True)
            return got

        includes = {key for key, node in line_nodes().items() if "include" in node}
        self.assertEqual(len(includes), 14)
        self.assertEqual(includes & body_ids(LINE["nodes"]), set())

    def test_report_reruns_on_resume(self):
        """L-W60: 報告はいつも走る。collect・report・result は前の段が落ちても飛ばされても走り（all_done）、Archon の resume でも collect と
        result は回し直す（always_run。元 works/darkfactory/darkfactory.yaml 1314-1322 行・works/tests/test_line_wiring.py の
        ReportAfterFailureCase.test_report_reruns_on_resume）。report は include で、Archon は include の always_run を捨てる
        （止めた Archon の packages/workflows/src/schemas/dag-node.ts 1085-1091 行・1911-1914 行）ので、回し直した collect の返りが
        変わった時に Archon が report の中の節の控えを捨てて回し直す（dag-executor.ts 9716-9727 行の getStaleCachedDependencies）。
        resume で本当に回し直されるかは筋書きで確かめられない（段 1 の本物の run で見る）"""
        nodes = line_nodes()
        for key in ("collect", "report", "result"):
            with self.subTest(node=key):
                self.assertEqual(nodes[key]["trigger_rule"], "all_done")
        for key in ("collect", "result"):
            with self.subTest(node=key):
                self.assertIs(nodes[key].get("always_run"), True)
        self.assertNotIn("always_run", nodes["report"], "include の always_run は Archon が捨てる（効くと読み違えない）")
        self.assertEqual(nodes["report"]["depends_on"], ["collect"])

    def test_start_is_not_always_run(self):
        """L-E34: 呼び直し（resume）で機能・test_cmd・入口の形・base_rev を替えない。Archon の再開は済んだ節を飛ばすので、start に
        always_run を付けない（止めた Archon の packages/workflows/src/dag-executor.ts 9664-9666 行の priorCompletedNodes）"""
        self.assertNotIn("always_run", line_nodes()["start"])

    def test_round_limit_is_the_loop_limit(self):
        self.assertEqual(line_nodes()["plan-rounds"]["loop_group"]["max_iterations"], plan_out.ROUND_LIMIT)


if __name__ == "__main__":
    unittest.main()

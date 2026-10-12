"""線の script（workflows/line/scripts/）の決めを、関数を直に呼んで照らす。

筋書き（tests/e2e/test_line_scenarios.py）は関所の答えを stub で差し、往復を 1 周で終えるので、関所の答えの読み・往復の抜け方・
入口の拒み・返りの合わせ方はここで照らす。種の git は gitkit の型の写し。
"""
import ast
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import re
import runpy
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

import answer  # noqa: E402  （線の script が lib/ と境の口の置き場を sys.path に足した後に読む）
import boardview  # noqa: E402
import boundary  # noqa: E402
import conflict  # noqa: E402
import converge  # noqa: E402
import fixboard  # noqa: E402
import gatemarks  # noqa: E402
import judge_accept  # noqa: E402
import planfile  # noqa: E402
import policy  # noqa: E402
import startrec  # noqa: E402
import stopby  # noqa: E402

SEED = SCRIPTS.parents[2] / "tests" / "e2e" / "target-seed"
RUN = "run-1"
LINE = yaml.safe_load((SCRIPTS.parent / "works-factory-line.yaml").read_text(encoding="utf-8"))
BLOCKS = ("judge", "plan", "plan-review", "fix", "test-gate", "eyes", "report", "merge")
ROUND_LIMIT = 20


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


ROOT = SCRIPTS.parents[2]
DESIGN = ROOT / "docs" / "design.md"
CONTRACT_HEAD = "## ブロックの返りの約束"


def contract_section(text: str) -> str:
    """docs/design.md の「ブロックの返りの約束」の節（次の ## の前まで）。無ければ落ちる"""
    start = text.index(CONTRACT_HEAD)
    end = text.find("\n## ", start + len(CONTRACT_HEAD))
    return text[start:] if end < 0 else text[start:end]


def contract_inputs(text: str) -> dict:
    """約束の節の「### <ブロック> の返り」ごとの、「入力（`with:`）:」の箇条の下の段の箇条が名指す入力の名の集まり。
    「←」の在る行は各「←」の直前の `名`（`a`・`b` ← の並びも）、無い行（`mode` の行・report の行）は行の中の `名` の全部（約束の外の
    名は呼び手が宣言と交わして落とす）。同じ節の上の段の箇条（fix の「`refix-run` の時」「約束に無い入力」）は約束の入力に数えない"""
    got = {}
    for block, body in re.findall(r"^### (\S+) の返り\n(.*?)(?=^### |\Z)", contract_section(text), re.M | re.S):
        lines = body.splitlines()
        head = next((i for i, line in enumerate(lines) if line.startswith("- 入力（`with:`）")), None)
        if head is None:
            continue
        names = set()
        for line in lines[head + 1:]:
            if not line.startswith("  - "):
                break
            names |= set(re.findall(r"`([\w-]+)`(?=(?:・`[\w-]+`)*\s*←)" if "←" in line else r"`([\w-]+)`", line))
        got[block] = names
    return got


def neighbour_files(text: str) -> tuple:
    """約束の節が名指す隣のファイル（ほかのブロックが名で開く控え）の名の集まりと、そのうち「中身が無い run では書かれないことが
    ある」と名指した物の集まり。隣のファイルは「ただし次の隣のファイルは約束の一部」から始まる箇条の `*.json`・`*.jsonl` のうち、
    「`欄`（`ファイル`）」の形で欄の指し札の先を名指す物（judgment.json ほか）を除いた物"""
    item = next(line for line in contract_section(text).splitlines() if "隣のファイルは約束の一部" in line)
    body = item[item.index("隣のファイルは約束の一部"):]
    names = {m.group(2) for m in re.finditer(r"(`（)?`([\w.-]+\.jsonl?)`", body) if not m.group(1)}
    optional = body[body.index("次の 4 つは"):body.index("この 4 つは")]
    return names, set(re.findall(r"`([\w.-]+\.jsonl?)`", optional))


def block_scripts(block: str) -> list:
    return sorted((SCRIPTS.parents[1] / block / "scripts").glob("*.py"))


def imported_files(paths) -> set:
    """paths の script と、そこから import で辿れる lib/*.py と同じ script の置き場の *.py（推移で全部）"""
    lib = ROOT / "lib"
    seen, todo = set(), list(paths)
    while todo:
        path = todo.pop()
        if path in seen:
            continue
        seen.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module] if isinstance(node, ast.ImportFrom) and node.module and not node.level else []
            for name in names:
                for where in (lib / f"{name.split('.')[0]}.py", path.parent / f"{name.split('.')[0]}.py"):
                    if where.is_file():
                        todo.append(where)
    return seen


def literals(path: pathlib.Path) -> set:
    """ファイルの中の字の定数の全部"""
    return {n.value for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def named_files(path: pathlib.Path) -> set:
    """ファイルが名で持つ字: 字の定数と、import した lib のモジュールの字の定数を <別名>.<名> で引いた値（持ち主の定数で開く読み手）"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    aliases = {a.asname or a.name: a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    found = literals(path)
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in aliases:
            module = aliases[n.value.id]
            if (ROOT / "lib" / f"{module}.py").is_file() and isinstance(value := getattr(importlib.import_module(module), n.attr, None), str):
                found.add(value)
    return found


def load_file(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        self.assertEqual(doc["features_off"], ["tdd_lanes"])
        self.assertEqual(doc["features"]["tdd_lanes"], "off")
        self.assertEqual(doc["final_gate"], "when_needed")
        self.assertIn("archon", doc["versions"])
        self.assertTrue(got["gate_text"].startswith("起きたこと: "), got["gate_text"])

    def test_base_alone_is_a_change_entry(self):
        got = self.start(base="base")
        self.assertTrue(got["ok"], got)
        doc = self.record(got)
        self.assertEqual(doc["input"]["base"]["rev"], self.fork)
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
        """issue #89: 線の始めの記録を fix の prep と同じ重ね方で置き場の r1/start.json に写すと、上の欄だけを読む fix の読み手
        （conflict.request_file・fixboard.fix_values）が依頼のファイルを返す"""
        doc = self.record(self.start(request="request_ok.json"))
        place = self.tmp / "fix"
        defaults = {"tdd_suite": "", "test_cmd": "", "policy_md": "", "request_file": "", "features_cut": []}   # fix の prep の START_DEFAULTS
        fixboard.write_json(startrec.path(place), {**defaults, **{k: v for k, v in doc.items() if v is not None}})
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
                          ({"request": "request_ok.json", "thickness": "重厚"}, "重厚"),
                          ({"request": "request_ok.json", "features_off": "nope"}, "nope"),
                          ({"request": "request_ok.json", "features_off": "judge_verify", "features_on": "judge_verify"}, "両方"),
                          ({"request": "no-such.json"}, "no-such.json"),
                          ({"request": "request_ok.json", "design_only": "yes"}, "design_only"),
                          ({"request": "request_ok.json", "policy_md": "no-such.md"}, "no-such.md"),
                          ({"request": "request_ok.json", "fix_fixture": "fx"}, "fix_fixture"),
                          ({"request": str(self.bad_findings())}, "findings は")):
            with self.subTest(kw=kw):
                got = self.start(**kw)
                self.assertEqual((got["ok"], got["stop_reason"], got["ask"]), (False, stopby.START_REFUSED, False), got)
                self.assertIn(words, got["reason"])
                self.assertEqual(self.record(got)["refused"], got["reason"])


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
        return before_fix_answer.take(start_raw=json.dumps(self.pointer), artifacts=self.artifacts, go_raw="true", stop_raw="",
                                      place="gate-before-fix",
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
        got = replan_answer.take(json.dumps({"decision": "continue", "text": "x"}), "true", "", "null", "gate-replan", self.artifacts)
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
        before_fix = before_fix_answer.take(**self.before_fix_inputs(asked), artifacts=self.artifacts)["answer"]
        replan = gate_answer.take(json.dumps({"decision": "approve", "text": "直した案でよい"}), "true", "", "gate-replan",
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
        self.assertEqual(gate_answer.take("null", "true", "", "gate-final", self.artifacts),
                         {"go": True, "answer": None, "stop_reason": ""})
        self.assertEqual(gate_answer.take(None, "false", stopby.NEEDS_HUMAN, "gate-final", self.artifacts),
                         {"go": False, "answer": None, "stop_reason": stopby.NEEDS_HUMAN})
        self.assertFalse((self.artifacts / answer.ANSWERS).exists())

    def test_go_words_continue_and_are_recorded(self):
        for word in answer.GO_WORDS:
            with self.subTest(word=word):
                got = gate_answer.take(json.dumps({"decision": word, "text": "a.py だけ"}), "true", "", "gate-before-fix",
                                         self.artifacts)
                self.assertEqual(got, {"go": True, "answer": {"decision": word, "text": "a.py だけ"}, "stop_reason": ""})
                kept = json.loads((self.artifacts / "gates" / "gate-before-fix.json").read_text(encoding="utf-8"))
                self.assertEqual(kept, got["answer"])

    def test_stop_word_stops_with_the_gate_named(self):
        got = gate_answer.take(json.dumps({"decision": "stop", "text": "やめる"}), "true", "", "gate-final", self.artifacts)
        self.assertEqual((got["go"], got["stop_reason"]), (False, "human:gate-final"))
        self.assertEqual(json.loads((self.artifacts / "gates" / "gate-final.json").read_text(encoding="utf-8"))["decision"], "stop")

    def test_reject_stops_like_stop(self):
        got = gate_answer.take(json.dumps({"decision": answer.REJECT, "text": ""}), "true", "", "gate-replan", self.artifacts)
        self.assertEqual((got["go"], got["stop_reason"]), (False, "human:gate-replan"))

    def test_dry_run_approval_reads_as_approve(self):
        got = gate_answer.take(answer.DRY_RUN_APPROVED, "true", "", "gate-start", self.artifacts)
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
                            (planned(**{"pass": False, "stalled": True, "round": ROUND_LIMIT, "ask_human": True,
                                        "questions": [f"{gatemarks.STUCK_ITEM}。理由: " + converge.CAP_WHY.format(
                                            n=ROUND_LIMIT, counts="1 往復目 2 → 20 往復目 1")]}),
                             "仕組みの異常として止めた")):
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
        self.assertEqual((got["open"], got["go"], got["stop_reason"]), (False, False, stopby.NEEDS_HUMAN))


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
        self.assertEqual((got["open"], got["go"], got["stop_reason"]), (False, False, stopby.NEEDS_HUMAN))

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
        self.assertEqual((got["open"], got["go"], got["stop_reason"]), (False, False, stopby.NEEDS_HUMAN))
        self.assertTrue(self.ask(self.got(), "when_needed", unattended=True)["go"])

    def test_unattended_protected_hit_stops(self):
        """守りのパスに当たった無人の run は、protected_only でも関所を開かずに人待ちで止め、merge-apply が飛ぶ（飛んだ関所が go を渡すのは GateAnswerCase）"""
        got = self.ask(self.got(protected_hits=["lib/seal.py（+1 −0）: 規則 seal（lib/seal.py）——封印"]), "protected_only",
                       unattended=True)
        self.assertEqual((got["open"], got["go"], got["stop_reason"]), (False, False, stopby.NEEDS_HUMAN))
        nodes = line_nodes()
        self.assertEqual(nodes["gate-final"]["when"], "$ask-final.output.open == true")
        self.assertEqual(nodes["merge-apply"]["when"], "$answer-final.output.go == true")

    def test_escalated_premise_check_opens_the_final_gate(self):
        """前提の検算が escalate なら、ほかの阻害に依らず最後の関所で人に聞く（元 review-loop.json:5189 stop.premise_check の does）"""
        eyes = final_got()["eyes"]
        got = self.got(eyes={**eyes, "premise_check": {"verdict": "escalate", "reason": "実測で反証できない"}})
        self.assertEqual(ask_final.final_needs(got), ["前提の検算が人に上げた"])
        self.assertTrue(self.ask(got, "when_needed")["open"])
        self.assertEqual(ask_final.final_needs(self.got(eyes={**eyes, "premise_check": {"verdict": "resolved", "reason": "偽と示した"}})), [])

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
        return plan_out.plan_out(base, ROUND_LIMIT)

    def test_done_rules(self):
        self.assertFalse(self.got()["done"])
        for kw in ({"ready": False}, {"pass": True}, {"stalled": True}, {"round": ROUND_LIMIT}):
            with self.subTest(kw=kw):
                self.assertTrue(self.got(**kw)["done"])
        self.assertFalse(self.got(round=3)["done"], "往復は数でなく開いた block の減り方で止まる（converge.decide）")

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
        for stops in ((stopby.LINE_SCRIPT, ""), ("", stopby.LINE_SCRIPT)):
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
                                   (failed, True, ("", "")), (failed, False, (stopby.LINE_SCRIPT, ""))):
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
        env = {"INPUTS_GOT_OK": "true", "INPUTS_GOT_HASH": "123", "INPUTS_GOT_MODE": "seal", "INPUTS_GOT_DIFF": "null",
               "INPUTS_GOT_PROTECTED_HITS": "[]", "INPUTS_GOT_REASON": ""}
        self.assertEqual(returned.returned(env),
                         {"got": {"mode": "seal", "ok": True, "hash": "123", "diff": None, "protected_hits": [], "reason": ""},
                          "stop_reason": ""})

    def test_line_inputs_are_not_fields(self):
        """Archon は線の inputs: も INPUTS_<名> で渡す。受け皿は got_ の付いた with: の鍵だけを欄にする"""
        env = {f"INPUTS_{name.upper()}": "x" for name in LINE["inputs"]} | {"INPUTS_GOT_OK": "true"}
        self.assertEqual(returned.returned(env)["got"], {"ok": True})


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
        got = collect.collect({"judge": "null", "merge_seal": json.dumps(seal), "plan": "null", "plan_review": "null"}, self.line())
        self.assertIsNone(got["judge"])
        self.assertEqual(got["merge_seal"], seal["got"])
        self.assertEqual((got["plan"], got["plan_review"], got["fix"]), (None, None, None))

    def test_plan_rounds_without_a_review_have_no_plan_review(self):
        """plan-review が飛ばされた周で抜けた往復は、plan-review の欄が全部 null の受け皿を null に倒す"""
        plan = {key: None for key in plan_out.PLAN} | {"ready": False, "round": 1}
        review = {key: None for key in plan_out.REVIEW}
        got = collect.collect({"plan": json.dumps({"got": plan, "stop_reason": ""}),
                               "plan_review": json.dumps({"got": review, "stop_reason": ""})}, self.line())
        self.assertEqual(got["plan"], plan)
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

    def test_result_fixed(self):
        for outcome, want in (("fixed", True), ("fixed_needs_check", True), ("no_fix_needed", False), ("", False)):
            with self.subTest(outcome=outcome):
                self.assertEqual(result.result({"outcome": outcome})["fixed"], want)


class BoundaryRunCase(unittest.TestCase):
    def test_script_failure_is_returned_not_raised(self):
        def boom():
            raise ValueError("壊れた\n入力")

        with mock.patch.object(boundary, "returns") as returns, mock.patch("sys.stderr"):
            boundary.run(boom, lambda reason: {"stop_reason": stopby.LINE_SCRIPT, "reason": reason})
        returns.assert_called_once_with({"stop_reason": stopby.LINE_SCRIPT, "reason": "ValueError: 壊れた 入力"})

    def test_skipped_values(self):
        self.assertEqual((boundary.value("null"), boundary.text("null"), boundary.flag("true"), boundary.items("[1]")),
                         (None, "", True, [1]))
        self.assertEqual((boundary.value("abc"), boundary.text("abc"), boundary.items("null")), ("abc", "abc", []))


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
                    self.assertEqual(got["stop_reason"], stopby.LINE_SCRIPT)
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
                    self.assertEqual(json.loads(done.stdout)["stop_reason"], stopby.LINE_SCRIPT)
                    self.assertIn("ModuleNotFoundError", done.stderr)


class GateDecisionsCase(unittest.TestCase):
    """人の関所は 4 つで、どれも関所の文が見せる答えの語（lib/answer.py の VERBS）と approve・reject を受け、受ける語は通す語
    （answer.GO_WORDS）か止める語（VERBS のうち通す語でない物と reject。gate_answer は通す語でない答えを止めと読む）だけ。
    reject が decisions に無いと、Archon はその答えを run の取り消しとして扱い、報告が出ない"""

    def test_gates_take_the_words_their_text_prints(self):
        gates = {key: node for key, node in line_nodes().items() if "approval" in node}
        self.assertEqual(set(gates), {"gate-start", "gate-before-fix", "gate-replan", "gate-final"})
        stop_words = set(answer.VERBS) - set(answer.GO_WORDS)
        self.assertEqual(stop_words, {"stop"})
        for key, node in gates.items():
            with self.subTest(gate=key):
                self.assertEqual({d["id"] for d in node["approval"]["decisions"]},
                                 set(answer.GO_WORDS) | set(answer.VERBS) | {answer.REJECT})


class Recorded(dict):
    """読まれた環境変数の名を控える os.environ の代わり"""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.read = set()

    def get(self, key, default=None):
        self.read.add(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self.read.add(key)
        return super().__getitem__(key)


class LineWiringCase(unittest.TestCase):
    """返しの節の with: の鍵と、その script が読む INPUTS_<名> が同じ（片方だけ欄を足すと、欄が黙って報告から落ちる）"""

    def test_with_keys_are_what_the_script_reads(self):
        """with: を持つ線の script の節の全部（受け皿 returned は下の 2 本）を、with: の鍵の全部を "null" にして走らせ、読んだ
        INPUTS_<名> を控える"""
        nodes = {key: node for key, node in line_nodes().items()
                 if "script" in node and node.get("with") and node["script"] != "returned"}
        self.assertIn("ask-before-fix", nodes)
        for key, node in nodes.items():
            with self.subTest(node=key), tempfile.TemporaryDirectory() as tmp:
                env = Recorded(WORKFLOW_ID=RUN, ARTIFACTS_DIR=tmp, **{f"INPUTS_{name.upper()}": "null" for name in node["with"]})
                with mock.patch.object(os, "environ", env), contextlib.redirect_stdout(io.StringIO()):
                    runpy.run_path(str(SCRIPTS / f"{node['script']}.py"), run_name="__main__")
                self.assertEqual({name for name in env.read if name.startswith("INPUTS_")},
                                 {f"INPUTS_{name.upper()}" for name in node["with"]})

    def test_receivers_return_every_with_key_and_nothing_else(self):
        """受け皿（returned）は with: の鍵 got_<欄> の全部を欄にし、Archon が同じく INPUTS_<名> で渡す線の inputs: は欄にしない"""
        run_inputs = {f"INPUTS_{name.upper()}": "x" for name in LINE["inputs"]}
        for key, node in line_nodes().items():
            if node.get("script") != "returned":
                continue
            with self.subTest(node=key):
                self.assertTrue(all(name.startswith("got_") for name in node["with"]), node["with"])
                env = run_inputs | {f"INPUTS_{name.upper()}": "null" for name in node["with"]}
                self.assertEqual(set(returned.returned(env)["got"]), {name.removeprefix("got_") for name in node["with"]})

    def test_receivers_take_every_field_of_what_they_receive(self):
        """受け皿の got_<欄> は受ける節の同じ欄を指し、欄の組はブロックの返す節の output_format（計画の往復は plan_out の
        PLAN・REVIEW）と同じ（受け皿の鍵を消すか向け違えると、その欄が黙って報告から落ちる）"""
        nodes = line_nodes()
        rounds = {"plan-rounds-out": plan_out.PLAN, "plan-rounds-review-out": plan_out.REVIEW}
        for key, node in nodes.items():
            if node.get("script") != "returned":
                continue
            with self.subTest(node=key):
                dep = node["depends_on"][0]
                fields = {name.removeprefix("got_") for name in node["with"]}
                self.assertEqual(node["with"], {f"got_{name}": f"${dep}.output.{name}" for name in fields})
                if key in rounds:
                    self.assertEqual(fields, set(rounds[key]))
                    continue
                doc = block_doc(nodes[dep]["include"])
                returns = next(n for n in doc["nodes"] if n["id"] == doc["returns"])
                self.assertEqual(fields, set(returns["output_format"]["properties"]))

    def test_every_include_and_the_plan_rounds_have_a_receiver_that_collect_reads(self):
        """ブロックの返す節が落ちても報告が出るように、collect は返りを受け皿 <id>-out からだけ読む。2 度目の修正 refix-run は、
        1 回目と合わせた節 fixed を通して読む（fixed は refix-run が落ちると飛ばされ、collect は 1 回目の返りに戻る）。計画の往復は
        plan の欄と plan-review の欄を別の受け皿で受ける"""
        nodes = line_nodes()
        inside = {node["id"] for node in nodes["plan-rounds"]["loop_group"]["nodes"]}
        received = {key: (f"{key}-out",) for key, node in nodes.items()
                    if "include" in node and key not in ("report", "refix-run") and key not in inside}
        self.assertEqual(nodes["collect"]["with"]["fixed"], {"from": "$fixed.output", "if_skipped": None})
        self.assertIn("refix-run", nodes["fixed"]["depends_on"])
        self.assertEqual(nodes["fixed"]["trigger_rule"], "none_failed_min_one_success")
        received["plan-rounds"] = ("plan-rounds-out", "plan-rounds-review-out")
        reads = {v["from"] for v in nodes["collect"]["with"].values() if isinstance(v, dict)}
        for key, receivers in received.items():
            for name in receivers:
                with self.subTest(node=key, receiver=name):
                    receiver = nodes.get(name)
                    self.assertIsNotNone(receiver)
                    self.assertEqual((receiver["script"], receiver["depends_on"], receiver.get("trigger_rule")), ("returned", [key], None))
                    self.assertIn(name, nodes["collect"]["depends_on"])
                    self.assertIn(f"${name}.output", reads)
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

    APPLY_ONLY = "apply だけの入力（merge は seal と apply の 2 つの形で、seal には渡さない）"
    GROUP_ONLY = "組の子の run だけの入力（fix が組ごとの並べのために自分を子の run として起こす時に渡す）"
    UNPASSED = {
        ("merge-seal", "answer"): APPLY_ONLY,
        ("merge-seal", "r2"): APPLY_ONLY,
        ("merge-seal", "sealed_hash"): APPLY_ONLY,
        ("fix", "mode"): GROUP_ONLY,
        ("fix", "group"): GROUP_ONLY,
        ("fix", "from_tree"): GROUP_ONLY,
        ("fix", "out_dir"): GROUP_ONLY,
        ("refix-run", "mode"): GROUP_ONLY,
        ("refix-run", "group"): GROUP_ONLY,
        ("refix-run", "from_tree"): GROUP_ONLY,
        ("refix-run", "out_dir"): GROUP_ONLY,
        ("fix", "only_items"): "1 回目は全部の項目（refix-run だけが 1 回目の replan_items を渡す）",
        ("plan-review-run", "conflicts"): "修正の前なので申し出が無い",
        ("plan-review-run", "gate_answers"): "修正前の関所より前に走る",
        ("replan-review", "round_limit"): "案の直しの事前審査は往復の輪の外で、輪の上限が無い",
        ("eyes", "x_scalars"): "部分 D1 で配線する。D1 で表から消す",
    }

    def test_every_declared_block_input_is_wired_or_listed(self):
        """行 L-W67: 線が差し込む各ブロックの inputs: の全部が、線の with: に在るか、渡さない訳を名指した表 UNPASSED に在る
        （既定値つきの入力が黙って未配線で残らない）。with: の鍵は宣言の中に在り、表の行は宣言に在って with: に無く、required でない。
        元 works/tests/test_line_inputs.py::InputNamesCase.test_block_inputs_are_all_referenced（:129）"""
        nodes = line_nodes()
        includes = {key for key, node in nodes.items() if "include" in node}
        self.assertLessEqual({key for key, _ in self.UNPASSED}, includes, "表の行の include の id が線に無い")
        for key in sorted(includes):
            node = nodes[key]
            declared = block_doc(node["include"])["inputs"]
            passed = set(node.get("with") or {})
            listed = {name for include, name in self.UNPASSED if include == key}
            with self.subTest(node=key):
                self.assertLessEqual(passed, set(declared), "with: の鍵がブロックの宣言に無い")
                self.assertEqual(listed - set(declared), set(), "表の行の入力がブロックの宣言に無い")
                self.assertEqual(listed & passed, set(), "with: で渡す入力が表にも在る（配線したら表の行を消す）")
                self.assertEqual(set(declared) - passed - listed, set(), "宣言した入力が with: にも表にも無い")
                self.assertFalse([name for name in listed if declared[name].get("required")], "表の行の入力が required")

    def test_block_inputs_outside_the_contract_have_defaults(self):
        """落とし穴 K11: ブロックの入力のうち docs/design.md の「ブロックの返りの約束」の入力（「入力（`with:`）:」の箇条）の外の物は
        既定値を持つ（既定値の無い入力は include する全部の工程の読み込みを落とす。Archon の include-expander.ts 576-580 行）"""
        contract = contract_inputs(DESIGN.read_text(encoding="utf-8"))
        self.assertEqual(set(contract), set(BLOCKS), "約束の節からブロックごとの入力の箇条を読めない")
        for block in BLOCKS:
            declared = block_doc(f"works-factory-{block}")["inputs"]
            agreed = contract[block] & set(declared)
            with self.subTest(block=block):
                self.assertTrue(agreed, f"約束の節の {block} の入力の名がブロックの宣言に 1 つも当たらない（読み方が崩れた）")
                self.assertEqual(sorted(name for name in set(declared) - agreed if "default" not in (declared[name] or {})), [],
                                 "約束の外の入力に既定値が無い")

    def test_line_inputs_are_what_start_reads(self):
        """行 L-E54: 線の inputs: の名と、始めの節 start が読む INPUTS_<名>（Archon は工程の入力を INPUTS_<大文字> で渡す）が同じ。
        元 works/tests/test_line_inputs.py（TA16）"""
        env = Recorded()
        with mock.patch.object(os, "environ", env):
            got = start.raw_inputs()
        self.assertEqual(env.read, {f"INPUTS_{name.upper()}" for name in LINE["inputs"]})
        self.assertEqual(set(got), set(LINE["inputs"]))

    # 隣のファイル（docs/design.md の約束の節）: 名 → ((書き手のブロック, 隣に置く返りの欄), 読み手の lib か script)
    NEIGHBOURS = {
        "premises.json": (("judge", "judgment"), "lib/boardview.py"),
        "judge-verify.json": (("judge", "judgment"), "lib/planfile.py"),
        "pr-excluded.json": (("judge", "judgment"), "lib/planfile.py"),
        "materials.json": (("judge", "judgment"), "lib/boardview.py"),
        "purpose-review.json": (("judge", "judgment"), "lib/boardview.py"),
        "answer-ties.json": (("judge", "judgment"), "lib/gatemarks.py"),
        "local-review-lenses.json": (("judge", "judgment"), "lib/runreport.py"),
        "pr-downgrades.json": (("judge", "judgment"), "lib/runreport.py"),
        "world-state.json": (("judge", "judgment"), "lib/worldmark.py"),
        "p2.fix_plan.json": (("plan", "plan"), "lib/fixboard.py"),
        "design.jsonl": (("plan", "structure"), "lib/boardview.py"),
        "gate-passes.json": (("plan-review", "review"), "lib/eyeverdict.py"),
        "design-premises.json": (("plan-review", "design"), "lib/eyeverdict.py"),
    }
    # 書き手の返す節を空の置き場で走らせる時の入力（ブロックの YAML がその節に渡す with: と、Archon がブロックの入力を渡す INPUTS_*）
    RETURN_INPUTS = {
        "judge": {"INPUTS_OBJECTION": ""},
        "plan": {"INPUTS_DIR": "plan/r1", "INPUTS_START": "", "INPUTS_JUDGMENT": ""},
        "plan-review": {},
    }
    # 今の木で照らしが通らない所（named: 書き手の script と lib が名を持つ・stop: lib の在る返す節が空の置き場でも書く・bare: lib も
    # 境の口も無い返す節が書く・read: 読み手が名を開く）。表に無い新しい穴と、通るようになったのに残る行は赤
    UNPROVEN = {
        **{(name, "bare"): "区分の issue で外す（judge の返す節 verdict.py の lib の無い道 fallen は judgment.json・purpose.json だけを書く）"
           for name in ("premises.json", "judge-verify.json", "pr-excluded.json", "materials.json", "purpose-review.json")},
        **{("p2.fix_plan.json", check): "区分の issue で外す（plan の返す節の止めの道と lib の無い道が修正案の役の返答の写しを置かない）"
           for check in ("stop", "bare")},
        **{("design-premises.json", check): "区分の issue で外す（plan-review の返す節の止めの道と lib の無い道が独立設計の控えを置かない）"
           for check in ("stop", "bare")},
        ("answer-ties.json", "read"): "区分の issue で外す（ほかのブロックが判定の隣のこの名を開かない。部分 B1 の S58・部分 C の S31）",
        ("local-review-lenses.json", "read"): "区分の issue で外す（report が開かない。部分 C の S41）",
        ("pr-downgrades.json", "read"): "区分の issue で外す（report が開かない。部分 C の S41）",
    }

    def written_beside(self, block: str, field: str, bare: bool) -> set:
        """書き手のブロックの返す節を空の置き場で走らせ、返りの欄 field の指し札の先と同じフォルダに在るファイルの名。bare なら返す節を
        境の口も lib も無い一時のフォルダに単独で写して走らせる（lib の無い道）"""
        doc = block_doc(f"works-factory-{block}")
        script = next(n["script"] for n in doc["nodes"] if n["id"] == doc["returns"])
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            artifacts = tmp / "artifacts"
            artifacts.mkdir()
            path = SCRIPTS.parents[1] / block / "scripts" / f"{script}.py"
            if bare:
                alone = tmp / "alone" / "scripts"
                alone.mkdir(parents=True)
                path = pathlib.Path(shutil.copy(path, alone))
            env = {k: v for k, v in os.environ.items() if not k.startswith(("INPUTS_", "WORKS_FACTORY_ROOT", "PYTHONPATH"))}
            env.update({"ARTIFACTS_DIR": str(artifacts), "WORKFLOW_ID": RUN, "PYTHONDONTWRITEBYTECODE": "1", **self.RETURN_INPUTS[block]})
            done = subprocess.run([sys.executable, str(path)], cwd=tmp, env=env, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            ptr = json.loads(done.stdout.strip().splitlines()[-1])[field]
            folder = (artifacts / ptr["path"]).parent
            return {p.name for p in folder.iterdir()} if folder.is_dir() else set()

    def test_every_contract_neighbour_file_has_a_writer_and_a_reader(self):
        """落とし穴 K12: docs/design.md の隣のファイルの一覧と表 NEIGHBOURS が同じで、各行で、書き手のブロックの script か lib が
        その名を字の定数で持ち（named）、書き手の返す節が止めの道（空の置き場で lib の在る道。stop）と lib の無い道（bare）でも返りの
        欄の指し札の隣にそのファイルを置き、読み手（書き手でないブロックの script か、そこから import で辿れる lib）がその名を字か持ち主の定数で開く（read）。
        約束が「書かれないことがある」と名指した 4 つは stop・bare を問わない。通らない照らしは UNPROVEN に名指して許す"""
        names, optional = neighbour_files(DESIGN.read_text(encoding="utf-8"))
        self.assertEqual(set(self.NEIGHBOURS), names, "表と docs/design.md の隣のファイルの一覧が違う")
        self.assertEqual(len(optional), 4, "約束の「次の 4 つは」の名を読めない")
        reach = {block: imported_files(block_scripts(block)) for block in (*BLOCKS, "line")}
        beside = {}
        for (block, field) in {writer for writer, _ in self.NEIGHBOURS.values()}:
            for bare in (False, True):
                beside[block, field, bare] = self.written_beside(block, field, bare)
        found = set()
        for name, ((block, field), reader) in sorted(self.NEIGHBOURS.items()):
            reader_path = ROOT / reader
            checks = {
                "named": any(name in literals(p) for p in reach[block]),
                "stop": name in optional or name in beside[block, field, False],
                "bare": name in optional or name in beside[block, field, True],
                "read": reader_path.is_file() and name in named_files(reader_path)
                        and any(reader_path in files for other, files in reach.items() if other != block),
            }
            found |= {(name, check) for check, ok in checks.items() if not ok}
        self.assertEqual(sorted(found - set(self.UNPROVEN)), [], "照らしの通らない隣のファイル（直すか、訳を書いて UNPROVEN に足す）")
        self.assertEqual(sorted(set(self.UNPROVEN) - found), [], "通るようになった照らしが UNPROVEN に残っている（表から消す）")

    # 2 度差し込むが置き場を分けないブロック: plan-review は案の直しの差し込みが前の差し込みの承認済みの項目を読む（boardview.view の
    # 「同じ run の往復と案の直しを同じ周に積む」）ので置き場 plan-review/ を共にし、差し込みの形は with: の ruling で分ける
    SHARED_PLACE = {"works-factory-plan-review": "ruling"}

    def test_twice_included_blocks_use_their_own_place(self):
        """落とし穴 K14: 線が 2 度差し込むブロック（YAML から数える）の全部で、置き場を決める関数に 2 つの include の id か形（with: の
        値）を渡すと違う置き場が返る（2 度目が 1 度目の置き場の物を今回の物として拾わない）。関数: judge は lib/judge_accept.verdict
        （異議の有無で judge/・rejudge/）、plan は lib/planfile.open_round（周ごとの plan/r<k>/）、fix は workflows/fix/scripts/fixio.place
        （include の名ごとの fix/<id>/）、test-gate は workflows/test-gate/scripts/result.rel（形ごとの test-gate/<mode>/）、merge は
        workflows/merge/scripts/merge.py の返す節（形ごとのファイル。フォルダ merge/ は同じ）。表 SHARED_PLACE のブロックは置き場を
        共にし、2 つの include が形の with: の値で分かれる"""
        nodes = line_nodes()
        twice = {}
        for key, node in nodes.items():
            if "include" in node:
                twice.setdefault(node["include"], []).append(key)
        twice = {block: keys for block, keys in twice.items() if len(keys) > 1}
        places = {"works-factory-judge": self.judge_places, "works-factory-plan": self.plan_places,
                  "works-factory-fix": self.fix_places, "works-factory-test-gate": self.gate_places,
                  "works-factory-merge": self.merge_places}
        self.assertEqual(set(twice), set(places) | set(self.SHARED_PLACE), "2 度差し込むブロックの置き場の照らし")
        for block, keys in twice.items():
            with self.subTest(block=block, includes=keys):
                if block in self.SHARED_PLACE:
                    form = self.SHARED_PLACE[block]
                    self.assertNotEqual(*[nodes[key]["with"][form] for key in keys])
                    continue
                self.assertNotEqual(*places[block]([nodes[key] for key in keys], keys))

    def judge_places(self, includes, keys) -> list:
        self.assertEqual([node["with"]["objection"] for node in includes], ["", "$fix.output.objection"])
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            return [pathlib.PurePosixPath(judge_accept.verdict(tmp / "judge", tmp / "rejudge", tmp, objection,
                                                               lambda rel: {"path": rel})["judgment"]["path"]).parent
                    for objection in ("", "u1 は直さなくてよい")]

    def plan_places(self, includes, keys) -> list:
        self.assertEqual([node["with"]["ruling"] for node in includes], [[], "$fix.output.replan_items"])
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            return [planfile.open_round(tmp / "plan", ruling=ruling, judgment=None, review=None, units=[], repo=tmp, why="試験")["dir"]
                    for ruling in ([], ["1"])]

    def fix_places(self, includes, keys) -> list:
        fixio = load_file("fix_fixio", SCRIPTS.parents[1] / "fix" / "scripts" / "fixio.py")
        with tempfile.TemporaryDirectory() as tmp:
            places = []
            for include in keys:
                env = {"ARTIFACTS_DIR": tmp, "ARCHON_NODE_EXECUTION": json.dumps({"path": f"{include}__fix-prep"})}
                with mock.patch.dict(os.environ, env):
                    places.append(fixio.place())
            return places

    def gate_places(self, includes, keys) -> list:
        gate = load_file("test_gate_result", SCRIPTS.parents[1] / "test-gate" / "scripts" / "result.py")
        return [pathlib.PurePosixPath(gate.rel(node["with"]["mode"], "run.json")).parent for node in includes]

    def merge_places(self, includes, keys) -> list:
        """merge の返す節を一時の git の木で形ごとに走らせ（seal の次に apply）、返りの diff の指し札の置き場を並べる"""
        modes = [node["with"]["mode"] for node in includes]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            repo, artifacts = tmp / "repo", tmp / "artifacts"
            repo.mkdir()
            artifacts.mkdir()
            git(repo, "init", "-q")
            (repo / "a.txt").write_text("one\n", encoding="utf-8")
            git(repo, "add", "a.txt")
            git(repo, "commit", "-q", "-m", "seed")
            (artifacts / "start.json").write_text(json.dumps({"base_rev": git(repo, "rev-parse", "HEAD")}), encoding="utf-8")
            (repo / "a.txt").write_text("two\n", encoding="utf-8")
            got, sealed = [], "null"
            for mode in modes:
                env = {k: v for k, v in os.environ.items() if not k.startswith("INPUTS_")}
                env.update({"WORKFLOW_ID": RUN, "ARTIFACTS_DIR": str(artifacts), "WORKS_FACTORY_ROOT": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"})
                env.update({f"INPUTS_{name.upper()}": "null" for name in block_doc("works-factory-merge")["inputs"]})
                env.update({"INPUTS_MODE": mode, "INPUTS_START": json.dumps({"type": "archon_artifact", "run_id": RUN, "path": "start.json"}),
                            "INPUTS_SEALED_HASH": sealed})
                done = subprocess.run([sys.executable, str(SCRIPTS.parents[1] / "merge" / "scripts" / "merge.py")], cwd=repo, env=env,
                                      capture_output=True, text=True)
                out = json.loads(done.stdout)
                self.assertIsNotNone(out["diff"], out)
                sealed = out["hash"]
                got.append(out["diff"]["path"])
            return got

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

    def test_round_limit_is_the_loop_limit(self):
        """往復の輪の上限は線の 1 つの数: max_iterations と、plan-out と事前審査（上限の周を知る）に with: で渡す round_limit"""
        nodes = line_nodes()
        self.assertEqual({nodes[key]["with"]["round_limit"] for key in ("plan-out", "plan-review-run")},
                         {nodes["plan-rounds"]["loop_group"]["max_iterations"]})



DF = "works/darkfactory/darkfactory.yaml"   # 今の works の線（pack.json の works.commit 2aa7c66c の版）
EDGE = "works/darkfactory/lib/line_edge.py"   # その境の節
PRIOR = "$start.output.prior_failures"
START_ANSWER = "$answer-start.output.answer"


class HandoffCase(unittest.TestCase):
    """今の works の線が段から段へ渡した値（元の線の各節の入力と境の節が盤面から渡した物）を、今の線の with: が同じ源から渡すか。
    元の線は判定・案・深さを境の節（h-*）が盤面から読んで渡したので、表の 1 行は「元の受け手の節 → 今の include か節の id と入力 →
    今の源の $…」。元に在って今の線に無い受け渡しは MISSING に閉じる部分の名を訳に書いて置き、今の線に無いことを照らす（配線した
    部分がその行を MISSING から HANDOFFS へ移す）。行 L-W05・L-W11・L-W12・L-W43・L-W50・L-W58"""

    HANDOFFS = [
        # L-W05 判定の単位と判定を後ろの段へ運ぶ。元は h-plan が判定の出口を盤面に控え（DF:409 judged）、どの境の節も
        # judgment_file・open_units をその控えから返した（EDGE:224 _carried・:1163）
        ("planning（DF:481-489。盤面の判定を読む）", "plan", "units", "$judge.output.units"),
        ("planning（DF:481-489）", "plan", "judgment", "$judge.output.judgment"),
        ("planning の事前審査（DF:481-489。blk-plan の中）", "plan-review-run", "units", "$judge.output.units"),
        ("planning の事前審査（DF:481-489）", "plan-review-run", "judgment", "$judge.output.judgment"),
        ("fixing（DF:629 open_units ← h-fix）", "fix", "units", "$judge.output.units"),
        ("fixing（DF:628 judgment_file ← h-fix）", "fix", "judgment", "$judge.output.judgment"),
        ("replanning（DF:687-696。盤面の判定を読む）", "replan", "units", "$judge.output.units"),
        ("replanning（DF:687-696）", "replan", "judgment", "$judge.output.judgment"),
        ("replanning の事前審査（DF:687-696。blk-plan の中）", "replan-review", "units", "$judge.output.units"),
        ("replanning の事前審査（DF:687-696）", "replan-review", "judgment", "$judge.output.judgment"),
        ("refitting（DF:810 open_units ← h-refit）", "refix-run", "units", "$judge.output.units"),
        ("refitting（DF:809 judgment_file ← h-refit）", "refix-run", "judgment", "$judge.output.judgment"),
        # L-W11 修正案と波及の一覧と深さを修正へ渡す（EDGE:1217-1226・:163 _ripple_file）
        ("fixing（DF:630 plan_file ← h-fix）", "fix", "plan", "$plan-rounds.output.plan"),
        ("fixing（DF:637 ripple_file ← h-fix）", "fix", "ripple", "$plan-rounds.output.ripple"),
        ("fixing（DF:636 unit_depths ← h-depth）", "fix", "depth", "$plan-rounds.output.depth"),
        ("refitting（DF:811 plan_file ← h-refit。差し替えた承認済みの案）", "refix-run", "plan", "$replan.output.plan"),
        ("refitting（DF:817 ripple_file ← h-refit。EDGE:169 refit_ripple_file の作り直した一覧）", "refix-run", "ripple", "$replan.output.ripple"),
        ("refitting（DF:803-821 は unit_depths を持たず盤面の深さのまま。今は直した案の深さを渡す）", "refix-run", "depth", "$replan.output.depth"),
        # L-W12 計画の往復。事前審査の返答を次の周の plan に渡す（元 works/blk-plan の輪と works/.shared/core/converge.py）
        ("planning の往復（DF:481-489。blk-plan の中の輪）", "plan", "review", "$LOOP_PREV.plan-out.output.review"),
        # L-W43 再審の後は独立の目と最後の関所が再審の判定を読む（元は盤面の判定の差し替え。EDGE:1043-1053 rejudge_edge）
        ("eyeing（DF:1195-1202。盤面の判定を読む）", "eyes", "units", "$judged.output.units"),
        ("eyeing（DF:1195-1202）", "eyes", "judgment", "$judged.output.judgment"),
        ("eyeing（DF:1195-1202）", "eyes", "purpose", "$judged.output.purpose"),
        ("eyeing（DF:1195-1202）", "eyes", "world", "$judged.output.world"),
        ("h-final（DF:1204-1215。EDGE:560 _final_text の保留の問い）", "ask-final", "judgment", "$judged.output.judgment"),
        # L-W50 単位ごとの深さを修正へ渡し、修正の後の信号で上げ直して独立の目が省くかを決める（fix.depth は L-W11 の行）
        ("eyeing（DF:1201 skip_optional ← h-redepth.skip）", "eyes", "depth", "$redepth.output.depth"),
        ("h-redepth（DF:885 replanned ← h-replan.go）", "redepth", "replan_depth", {"from": "$replan.output.depth", "if_skipped": None}),
        ("h-redepth（DF:885 replanned ← h-replan.go）", "redepth", "replanned", "$after-fix.output.replan"),
        ("h-redepth（DF:886 rejudged ← h-rejudge.go）", "redepth", "rejudged", "$after-fix.output.rejudge"),
        # L-W58 前の失敗は判定と修正案にだけ（元 works/tests/test_line_a.py:503 test_prior_failures_reach_judge_and_plan_only）
        ("judging（test_line_a.py:503。盤面の prior-failures-in.json）", "judge", "prior_failures", PRIOR),
        ("rejudging（DF:866-873。同じ盤面）", "rejudge-run", "prior_failures", PRIOR),
        ("planning（test_line_a.py:503。修正案の役の指示書）", "plan", "prior_failures", PRIOR),
        ("replanning（DF:687-696。同じ盤面）", "replan", "prior_failures", PRIOR),
        # L-W58 始めの関所の答え（元は入口のブロック DF:98-119 の起動の関所の答えを盤面の人の答えにし、独立設計と前提の検算が読む。
        # EDGE:529 _r2_inputs の after_design）
        ("planning の独立設計（DF:481-489）", "plan-review-run", "answers", START_ANSWER),
        ("replanning の事前審査（DF:687-696）", "replan-review", "answers", START_ANSWER),
        ("eyeing の前提の検算（DF:1195-1202）", "eyes", "start_answers", START_ANSWER),
    ]
    # 元に在って今の線に無い受け渡し: (元の受け手と元の在り処, 今の id, 今なら読むはずの源の字, 閉じる部分)
    MISSING = [
        ("refitting が 1 回目の申し出と裁定を見る（works/.shared/core/conflict.py:411-414 second_pass・works/blk-fix/lib/fixgates.py:103）",
         "refix-run", "$fix.output.conflicts", "部分 D1（S01）"),
        ("差分の審査役の材料 out.p2.plan_review（works/.shared/core/graphloops/graphs/review-loop.json:4163・"
         "works/blk-delta/commands/delta-review.md:8）", "fix", "$plan-rounds.output.review", "部分 D1（S02）"),
        ("独立の目の x_scalars（盤面の修正役の返答。S09）", "eyes", ".output.x_scalars", "部分 D1（S09）"),
        ("h-final の breaks.accepted（EDGE:814-815 _final_needs・:719-723 _handoff_text・:868。works/.shared/core/report.py:304-314）",
         "ask-final", ".output.breaks", "部分 D2（S03）"),
        ("report の depth ← h-redepth（DF:1330）", "collect", "$redepth.output", "部分 C（S30・S53）"),
        ("report の前の失敗（DF:1307-1308 の prior-failures.json。盤面の prior-failures-in.json）", "collect", PRIOR, "部分 C（S49）"),
    ]

    def test_handoff_table(self):
        nodes = line_nodes()
        for origin, key, name, want in self.HANDOFFS:
            with self.subTest(origin=origin, node=key, input=name):
                self.assertIn(key, nodes)
                self.assertEqual((nodes[key].get("with") or {}).get(name), want)
        for origin, key, source, part in self.MISSING:
            with self.subTest(origin=origin, node=key, closes=part):
                values = json.dumps(nodes[key].get("with") or {}, ensure_ascii=False)
                self.assertNotIn(source, values, f"{part} が配線した。行を MISSING から HANDOFFS へ移す")

    def test_prior_failures_reach_judge_and_plan_only(self):
        """元 works/tests/test_line_a.py:503 の「判定と修正案の役にだけ」: 前の失敗を渡す差し込みは HANDOFFS の 4 つだけ"""
        given = {key for key, node in line_nodes().items() if "include" in node and PRIOR in (node.get("with") or {}).values()}
        self.assertEqual(given, {key for _, key, name, want in self.HANDOFFS if name == "prior_failures"})


if __name__ == "__main__":
    unittest.main()

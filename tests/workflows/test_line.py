"""線の script（workflows/line/scripts/）の決めを、関数を直に呼んで照らす。

筋書き（tests/e2e/test_line_scenarios.py）は関所の答えを stub で差し、往復を 1 周で終えるので、関所の答えの読み・往復の抜け方・
入口の拒み・返りの合わせ方はここで照らす。種の git は gitkit の型の写し。
"""
import ast
import collections
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

from bin._lib.place import shared
from tests.bin import hermetic
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
spec_check = load("spec_check")
returned = load("returned")
collect = load("collect")
result = load("result")
sweep_children = load("sweep_children")
fix_in = load("fix_in")

import answer  # noqa: E402  （線の script が lib/ と境の口の置き場を sys.path に足した後に読む）
import boardview  # noqa: E402
import boundary  # noqa: E402
import childsweep  # noqa: E402
import conceptfence  # noqa: E402
import conflict  # noqa: E402
import consult  # noqa: E402
import converge  # noqa: E402
import entry  # noqa: E402
import entryshape  # noqa: E402
import fixbeside  # noqa: E402
import fixboard  # noqa: E402
import fixture  # noqa: E402
import gatemarks  # noqa: E402
import gatepolicy  # noqa: E402
import latedepth  # noqa: E402
import green_cert  # noqa: E402
import judge_accept  # noqa: E402
import outcome  # noqa: E402
import planfile  # noqa: E402
import policy  # noqa: E402
import protect  # noqa: E402
import querytest  # noqa: E402
import replan  # noqa: E402
import runreport  # noqa: E402
import seal  # noqa: E402
import startrec  # noqa: E402
import stopby  # noqa: E402
import structmark  # noqa: E402

SEED = SCRIPTS.parents[2] / "tests" / "e2e" / "target-seed"
RUN = "run-1"
LINE = yaml.safe_load((SCRIPTS.parent / "works-factory-line.yaml").read_text(encoding="utf-8"))
BLOCKS = ("judge", "plan", "plan-review", "fix", "test-gate", "eyes", "report", "merge")
ROUND_LIMIT = 20


def load_block_script(block: str, name: str):
    """ブロックの script を試験から読む（書き手の関数の字を線の読み手と結ぶため）"""
    folder = SCRIPTS.parents[1] / block / "scripts"
    spec = importlib.util.spec_from_file_location(f"{block.replace('-', '_')}_block_{name}", folder / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def block_doc(include: str) -> dict:
    """差し込むブロックの YAML（include の名の works-factory- の後ろがフォルダ）"""
    return yaml.safe_load((SCRIPTS.parents[1] / include.removeprefix("works-factory-") / f"{include}.yaml").read_text(encoding="utf-8"))


def record_steps(block: str = "line", prefix: str = "") -> set:
    """線を回した時の run の記録の step に出うる節の id の全部。Archon は include の中の節に「include の節の id__」を前に付け、
    ループの中の節は素の id のまま記録する（include-expander.ts の inlineInclude・node-record-serialization.ts の step）"""
    doc = yaml.safe_load((SCRIPTS.parents[1] / block / f"works-factory-{block}.yaml").read_text(encoding="utf-8"))
    got = set()

    def walk(nodes, head):
        for node in nodes:
            got.add(head + node["id"])
            if "include" in node:
                got.update(record_steps(node["include"].removeprefix("works-factory-"), head + node["id"] + "__"))
            if "loop_group" in node:
                walk(node["loop_group"]["nodes"], "")
    walk(doc["nodes"], prefix)
    return got


def line_nodes(nodes=None) -> dict:
    """線の節（loop_group の中の節も）を id ごとに"""
    got = {}
    for node in LINE["nodes"] if nodes is None else nodes:
        got[node["id"]] = node
        got.update(line_nodes(node["loop_group"]["nodes"]) if "loop_group" in node else {})
    return got


RETURNING = {"test_gate_base": "test-gate", "judge": "judge", "rejudge": "judge", "plan": "plan", "replan": "plan",
             "fix": "fix"}   # collect の欄 → その返りを返すブロック


def block_optional(block: str) -> list:
    doc = block_doc(f"works-factory-{block}")
    return json.loads(next(n for n in doc["nodes"] if n["id"] == doc["returns"])["with"]["optional"])


def received_with_declarations() -> dict:
    """受け皿が collect へ運ぶ got の形（collect の欄 → 返りの欄）。各ブロックの返す節の宣言を optional に載せる"""
    return {field: {"ready": True, "optional": block_optional(block)} for field, block in RETURNING.items()}


def declared_by_blocks() -> list:
    """メイングラフ自身の宣言に、各ブロックの宣言を collect.absorbed で重ねた、受け止める段の並び（collect が report へ渡す物）"""
    return collect.absorbed(received_with_declarations(), json.loads(line_nodes()["collect"]["with"]["optional"]))


ROOT = SCRIPTS.parents[2]
DESIGN = ROOT / "docs" / "design.md"
CONTRACT_HEAD = "## サブグラフの出力の約束"


def contract_section(text: str) -> str:
    """docs/design.md の「サブグラフの出力の約束」の節（次の ## の前まで）。無ければ落ちる"""
    start = text.index(CONTRACT_HEAD)
    end = text.find("\n## ", start + len(CONTRACT_HEAD))
    return text[start:] if end < 0 else text[start:end]


def contract_inputs(text: str) -> dict:
    """約束の節の「### <サブグラフ> の出力」ごとの、「入力（`with:`）:」の箇条の下の段の箇条が名指す入力の名の集まり。
    「←」の在る行は各「←」の直前の `名`（`a`・`b` ← の並びも）、無い行（`mode` の行・report の行）は行の中の `名` の全部（約束の外の
    名は呼び手が宣言と交わして落とす）。同じ節の上の段の箇条（fix の「`refix-run` の時」「約束に無い入力」）は約束の入力に数えない"""
    got = {}
    for block, body in re.findall(r"^### (\S+) の出力\n(.*?)(?=^### |\Z)", contract_section(text), re.M | re.S):
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
                               "thickness", "features_off", "features_on", "policy_md", "fix_fixture", "lang", "deliver")}
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

    def test_start_returns_the_shared_places(self):
        """#681: 始めのノードはメイングラフの run の共有の置き場（試験の結果の控え tree_run.reuse_dir と、利用者の HOME・XDG に戻して
        起こした印の置き場＝run の置き場）を出力の欄で返す。拒んだ run の控えの置き場は空（後ろの節は飛ぶ）"""
        import tree_run
        got = self.start(request="request_ok.json")
        self.assertEqual((got["reuse_dir"], got["user_env_dir"]), (str(tree_run.reuse_dir(self.artifacts)), str(self.artifacts)))
        refused = self.start()
        self.assertFalse(refused["ok"])
        self.assertEqual((refused["reuse_dir"], refused["user_env_dir"]), ("", str(self.artifacts)))

    def test_base_alone_is_a_change_entry(self):
        got = self.start(base="base")
        self.assertTrue(got["ok"], got)
        doc = self.record(got)
        self.assertEqual(doc["input"]["base"], {"rev": self.fork, "from": "base", "name": "base", "label": "base base"},
                         "差分の根は base と HEAD の merge-base、label は「base <名>」（L-E09）")
        self.assertGreaterEqual(doc["input"]["diff"]["files"], 1)
        self.assertEqual(doc["base_rev"], git(self.repo, "rev-parse", "HEAD"),
                         "base_rev は修正の前の HEAD（今の works の entry.py 1203 行。merge と test-gate が差分の起点に読む）")
        self.assertEqual(doc["review_rev"], doc["base_rev"], "review_rev は役の材料の読む版。差分の根 input.base.rev とは別に持つ")

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
        startrec.request_file で読む fix の読み手（conflict.request_file・fixboard.fix_values）が依頼のファイルを返す"""
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
                          ({"request": "request_ok.json", "thickness": "xx"}, "知らない値"),
                          ({"request": "request_ok.json", "features_off": "nope"}, "nope"),
                          ({"request": "request_ok.json", "deliver": "merge"}, "deliver='merge' は知らない語"),
                          ({"request": "request_ok.json", "features_off": "judge_verify", "features_on": "judge_verify"}, "両方"),
                          ({"request": "no-such.json"}, "no-such.json"),
                          ({"request": "request_ok.json", "design_only": "yes"}, "design_only"),
                          ({"request": "request_ok.json", "policy_md": "no-such.md"}, "no-such.md"),
                          ({"request": "request_ok.json", "fix_fixture": "fx"}, "固定材料のフォルダ fx が無い"),
                          ({"request": "request_ok.json", "spec": "on", "fix_fixture": str(self.tmp)}, "固定材料（fix_fixture）と組めない"),
                          ({"request": str(self.bad_findings())}, "findings は")):
            with self.subTest(kw=kw):
                got = self.start(**kw)
                self.assertEqual((got["ok"], got["stop_reason"], got["ask"]), (False, stopby.START_REFUSED, False), got)
                self.assertIn(words, got["reason"])
                doc = self.record(got)
                self.assertEqual(doc["refused"], got["reason"])
                self.assertEqual(doc["inputs"], raw(**kw), "拒む run でも設定の写しを残す（L-E46）")
                self.assertIn("unknown", doc["versions"], "拒む run でも版の控えを残す（L-E46）")

    def test_fixture_starts_the_run_from_the_copy(self):
        """#509（元 works/.shared/core/entry.py の _start_from_fixture）: 写した run の置き場の固定材料を名指した start は、写しを今の
        run の置き場に取り込み、始めの記録を写しの物に今の run の id・入力・版の控えと固定材料の印を足して書き、運ぶ値のポインタを返す"""
        first = self.start(request="request_ok.json", final_gate="when_needed")
        carried = {"judge": {"judgment": {"type": "archon_artifact", "run_id": RUN, "path": "judge/judgment.json"}}}
        fixture.capture(self.artifacts, self.repo, run_id=RUN, carried=carried)
        place = self.tmp / "artifacts-2"
        with mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(place), "WORKFLOW_ID": "run-2"}):
            kw = {"request": "request_ok.json", "final_gate": "when_needed", "fix_fixture": str(self.artifacts / fixture.DIR),
                  "features_off": "tdd_lanes"}
            got = start.start(raw(**kw), self.repo, place, "run-2")
        self.assertEqual((got["ok"], got["from_fixture"], got["ask"], got["final_gate"]), (True, True, True, "when_needed"), got)
        self.assertEqual(got["fixture"], {"type": "archon_artifact", "run_id": "run-2", "path": fixture.CARRIED})
        self.assertEqual(json.loads((place / fixture.CARRIED).read_text(encoding="utf-8"))["judge"]["judgment"]["run_id"], "run-2")
        doc = json.loads((place / got["record"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual((doc["run_id"], doc["inputs"], doc[fixture.KEY]["source_run"]), ("run-2", raw(**kw), RUN))
        self.assertEqual(doc["input"], self.record(first)["input"])
        self.assertIn("archon", doc["versions"])
        self.assertIn(f"- 固定材料から: run {RUN} の修正の前の写し", got["gate_text"])
        self.assertNotIn("tdd_lanes", self.record(first)[entry.FEATURES_CUT_KEY])
        self.assertEqual((doc[entry.FEATURES_KEY], doc[entry.FEATURES_CUT_KEY]),
                         (["tdd_lanes"], entry.features_cut(["tdd_lanes"], doc[entry.FEATURES_ON_KEY])),
                         "機能の切り替えは写しの物でなく今の run の物（修正の段だけを替えて比べる）")

    def test_fixture_run_points_at_its_own_request_file(self):
        """依頼は今の値にする欄なので、同じ中身の別のファイルで起こした固定材料の run の始めの記録は、写した run の依頼のファイルでなく
        今の依頼のファイルを指す（修正役の指示に出る道も今の物）"""
        self.start(request="request_ok.json")
        fixture.capture(self.artifacts, self.repo, run_id=RUN, carried={})
        again = self.tmp / "request-again.json"
        shutil.copyfile(self.repo / "request_ok.json", again)
        place = self.tmp / "artifacts-2"
        with mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(place), "WORKFLOW_ID": "run-2"}):
            got = start.start(raw(request=str(again), fix_fixture=str(self.artifacts / fixture.DIR)), self.repo, place, "run-2")
        self.assertTrue(got["ok"], got)
        doc = json.loads((place / got["record"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual((doc["request_file"], doc["input"]["request_file"]), (str(again.resolve()), str(again.resolve())))

    def test_fixture_that_does_not_match_is_refused_before_any_role(self):
        self.start(request="request_ok.json")
        fixture.capture(self.artifacts, self.repo, run_id=RUN, carried={})
        place = self.tmp / "artifacts-2"
        with mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(place), "WORKFLOW_ID": "run-2"}):
            got = start.start(raw(request="request_ok.json", test_cmd="make other", fix_fixture=str(self.artifacts / fixture.DIR)),
                              self.repo, place, "run-2")
        self.assertEqual((got["ok"], got["stop_reason"], got["from_fixture"]), (False, stopby.START_REFUSED, False), got)
        self.assertTrue(got["reason"].startswith("固定材料を取り込まない: "), got["reason"])
        self.assertIn("test_cmd", got["reason"])
        self.assertFalse((place / fixture.CARRIED).exists())

    def outside(self, name: str, text: str) -> pathlib.Path:
        """対象の木の外に置く依頼のファイル（木を汚すと差分が空でなくなる）"""
        path = self.tmp / name
        path.write_text(text, encoding="utf-8")
        return path

    def refused(self, **kw) -> str:
        got = self.start(**kw)
        self.assertEqual((got["ok"], got["stop_reason"]), (False, stopby.START_REFUSED), got)
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

    def test_request_without_findings_is_taken(self):
        """#505: findings を省いた依頼（answers・pr だけ）は空の findings として受け、差分の在る base で始まる（元 works の
        skills/works/SKILL.md 57 行「findings を省くと空の配列」）。差分も依頼の行も無ければ今までどおり空の入力として拒む"""
        rows = [{"question": "q1", "text": "a を選ぶ"}]
        path = self.outside("answers_only.json", json.dumps({"answers": rows}))
        got = self.start(request=str(path), base="base")
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.record(got)["answers"], rows)
        self.assertIn(entryshape.EMPTY_REFUSED, self.refused(request=str(path)))

    def test_omitted_tdd_suite_says_how_the_runner_is_prepared(self):
        """#505・#516: tdd_suite を省いた run は、承認ノードの文が TDD の実行器を取り置きから使うか AI が書き、照らしが通らなければ
        ループを飛ばす事を言う（元 works の dev/use.sh 1086-1089 行）。名指した tdd_suite は始めの記録にそのまま載り、文は言わない"""
        import suitewrite
        got = self.start(base="base", test_cmd="make test")
        self.assertEqual(self.record(got)["tdd_suite"], "")
        self.assertIn(suitewrite.GATE_NOTE, got["gate_text"])
        got = self.start(base="base", test_cmd="make test", tdd_suite="run-tests.sh")
        self.assertEqual(self.record(got)["tdd_suite"], "run-tests.sh")
        self.assertNotIn(suitewrite.GATE_NOTE, got["gate_text"])

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

    def test_spec_on_reaches_the_output(self):
        """#550: spec=on は始めの出力 spec で spec-check に渡る（拒んだ・落ちた返りは偽）"""
        self.assertIs(self.start(request="request_ok.json", spec="on")["spec"], True)
        self.assertIs(self.start(request="request_ok.json")["spec"], False)
        self.assertIs(self.start(base="base", spec="on")["spec"], False)
        self.assertIs(start.fallback("落ちた")["spec"], False)

    def test_spec_refused_without_request_text(self):
        """L-E29: spec=on なのに依頼の文（依頼も PR の題と本文も）が無ければ止める（元 SpecInputCase の同名）"""
        self.assertIn("依頼の文", self.refused(base="base", spec="on"))

    def test_spec_refused_without_findings_or_pr_text(self):
        """#526: findings を省いた依頼（answers だけ・名指す PR の並びだけ）は #505 から受けるが、spec=on では仕様の書き手が読む
        物が無いので AI を起こす前に止める。名指した PR の題と本文が在れば足りる"""
        answers_only = self.outside("answers_only.json", json.dumps({"answers": [{"question": "q1", "text": "a"}]}))
        got = self.start(request=str(answers_only), base="base", spec="on")
        self.assertEqual((got["ok"], got["stop_reason"], got["ask"]), (False, stopby.START_REFUSED, False), got)
        self.assertIn("依頼の文", got["reason"])
        self.assertIn("refused", self.record(got))
        pr_only = self.outside("pr_only.json", json.dumps({"pr": [7]}))
        got, _ = self.start_with_gh(self.pr_reads(), request=str(pr_only), base="base", spec="on")
        self.assertEqual((got["ok"], got["stop_reason"]), (False, stopby.START_REFUSED), got)
        self.assertIn("依頼の文", got["reason"])
        got, _ = self.start_with_gh(self.pr_reads(), pr="7", spec="on")
        self.assertTrue(got["ok"], got)

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
        self.assertIn("最後の承認ノード: when_needed", text)
        self.assertIn(answer.line(RUN, "continue", "<一言>"), text)
        self.assertIn(answer.line(RUN, "stop", "<理由>"), text)
        self.assertEqual(line_nodes()["gate-start"]["wait"]["attention"], "$start.output.gate_text")
        self.assertEqual(line_nodes()["gate-start"]["depends_on"], ["start"])

    def test_start_gate_text_names_the_deliver_word(self):
        """#751: 始めの承認ノードの頭の行に出口の語（deliver）を、段・機能・最後の承認ノードの開き方と同じ形で 1 行出す"""
        rows = {"": "- 出口（deliver）: 空（既定）——差分を run の置き場に置くだけで、対象の repo に何も書かない",
                "pr": "- 出口（deliver）: pr——最後の承認ノードを通ると、報告の前に run の枝へ commit を積んで push し、"
                      "対象の既定の枝へ向けた PR を作る（merge はしない）"}
        for word, row in rows.items():
            with self.subTest(deliver=word):
                lines = self.start(request="request_ok.json", deliver=word)["gate_text"].splitlines()
                self.assertIn(row, lines)
                self.assertEqual(lines.index(row), lines.index("- 最後の承認ノード: always") + 1)

    def test_heavy_thickness_is_taken(self):
        got = self.start(request="request_ok.json", thickness="重厚")
        self.assertTrue(got["ok"], got)
        doc = self.record(got)
        self.assertEqual(doc["thickness"], "重厚")
        self.assertNotIn("judge_verify", doc[entry.FEATURES_CUT_KEY])
        self.assertEqual(doc["features"]["judge_verify"], "on")
        self.assertEqual(doc["features"]["review_tree"], "on")
        self.assertIn("段: 重厚", got["gate_text"])
        self.assertNotIn("judge_verify off", got["gate_text"])
        self.assertNotIn("review_tree auto", got["gate_text"])
        plain = self.start(request="request_ok.json")
        self.assertIn("judge_verify", self.record(plain)[entry.FEATURES_CUT_KEY])
        self.assertIn("judge_verify off", plain["gate_text"])

    def test_heavy_with_a_named_off_is_refused(self):
        """issue #561 の求め 4: 名指した重厚が足す機能を features_off で切ると、入口がぶつかった機能を名指して止める。重厚の足さない
        機能を切るのと、自動・軽量・標準と切りの組は受ける"""
        for off in ("judge_verify", "review_tree", "tdd_lanes, review_tree"):
            with self.subTest(off=off):
                reason = self.refused(request="request_ok.json", thickness="重厚", features_off=off)
                self.assertIn("thickness=重厚", reason)
                self.assertIn("review_tree" if "review_tree" in off else "judge_verify", reason)
                self.assertNotIn("tdd_lanes", reason)
        self.assertTrue(self.start(request="request_ok.json", thickness="重厚", features_off="tdd_lanes")["ok"])
        for thickness in ("", "自動", "軽量", "標準"):
            with self.subTest(thickness=thickness):
                self.assertTrue(self.start(request="request_ok.json", thickness=thickness, features_off="judge_verify")["ok"])

    def test_gate_text_has_the_depth_word(self):
        """L-E49: 頭の行に段（thickness と（既定））・機能・最後の関所・修正前のテストの任せ先の注を並べる（元 entry.py 1213-1219 行）"""
        text = self.start(request="request_ok.json")["gate_text"]
        self.assertIn("段: 自動（既定）", text)
        self.assertIn("修正前のテスト: 宣言も test_cmd も無い", text)
        text = self.start(request="request_ok.json", thickness="軽量", test_cmd="make test")["gate_text"]
        self.assertIn("- 段: 軽量\n", text)
        self.assertNotIn("修正前のテスト:", text)


class FixInCase(Artifacts):
    """#509: 修正の段へ運ぶ値の中継 fix-in。通常の run は受け皿から組み、修正に入る時だけ固定材料を写す。固定材料の run は運ぶ値を
    そのまま平らにし、写さない"""

    BASE = {"baseline": {"type": "archon_artifact", "run_id": RUN, "path": "test-gate-base/baseline.json"}, "ok": True}
    JUDGE = {"units": [{"id": "u1"}], "judgment": {"path": "judge/judgment.json"}, "purpose": None, "world": None, "spec": None,
             "rejudge_verdict": "", "depth": "軽量", **dict.fromkeys(judge_accept.PORTS), **dict.fromkeys(judge_accept.FIRST_PORTS),
             "materials": {"path": "judge/materials.json"}}
    PLAN = {"plan": {"path": "plan/plan-fields.json"}, "ripple": {"path": "plan/ripple.json"}, "depth": [], "structure": None,
            "fix_plan": {"path": "plan/p2.fix_plan.json"}, "rejects": [], "nothing_owed": False, "gave_up": None}
    REVIEW = {"review": {"path": "plan-review/review.json"}, "gate_passes": {"path": "plan-review/gate-passes.json"},
              "gate": {"path": "plan-review/gate.json"}, "design": {"path": "plan-review/design.json"},
              "design_premises": {"path": "plan-review/design-premises.json"}, "questions": []}
    ANSWER = {"decision": "continue", "text": "q1 は a", "asked": []}

    def setUp(self):
        super().setUp()
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, SEED)

    def env(self, **kw) -> dict:
        got = {f"INPUTS_{name.upper()}": "null" for name in line_nodes()["fix-in"]["with"]}
        got.update({"INPUTS_TEST_GATE_BASE": json.dumps({"got": self.BASE, "stop_reason": ""}),
                    "INPUTS_JUDGE": json.dumps({"got": self.JUDGE, "stop_reason": ""}),
                    "INPUTS_PLAN": json.dumps({"got": self.PLAN, "stop_reason": ""}),
                    "INPUTS_PLAN_REVIEW": json.dumps({"got": self.REVIEW, "stop_reason": ""}),
                    "INPUTS_BEFORE_FIX_ANSWER": json.dumps(self.ANSWER), "INPUTS_DEFERRED": json.dumps([{"key": "q9"}]),
                    "INPUTS_START_GO": "true", "INPUTS_FIXTURE": ""})
        got.update({f"INPUTS_{k.upper()}": v for k, v in kw.items()})
        return got

    def run_in(self, **kw) -> dict:
        return fix_in.fix_in(self.env(**kw), self.artifacts, self.repo, RUN)

    def test_live_run_flattens_the_receivers_and_captures_once_it_goes(self):
        got = self.run_in(before_fix_go="true")
        self.assertEqual((got["go"], got["received"]), (True, None))
        self.assertEqual((got["baseline"], got["units"], got["plan"], got["review"], got["answer"], got["deferred"], got["head_depth"]),
                         (self.BASE["baseline"], self.JUDGE["units"], self.PLAN["plan"], self.REVIEW["review"], self.ANSWER,
                          [{"key": "q9"}], "軽量"))
        man = json.loads((self.artifacts / fixture.DIR / fixture.MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual(man["carried"], {"test_gate_base": self.BASE, "judge": self.JUDGE, "plan": self.PLAN,
                                          "plan_review": self.REVIEW, "gate_before_fix": self.ANSWER, "deferred": [{"key": "q9"}]})

    def test_live_run_that_does_not_go_does_not_capture(self):
        got = self.run_in(before_fix_go="false")
        self.assertIs(got["go"], False)
        self.assertFalse((self.artifacts / fixture.DIR).exists())

    def test_fixture_run_carries_the_copy_and_goes_on_the_start_gate(self):
        received = {"test_gate_base": self.BASE, "judge": self.JUDGE, "plan": self.PLAN, "plan_review": self.REVIEW,
                    "gate_before_fix": self.ANSWER, "deferred": []}
        (self.artifacts / fixture.CARRIED).write_text(json.dumps(received), encoding="utf-8")
        pointer = json.dumps({"type": "archon_artifact", "run_id": RUN, "path": fixture.CARRIED})
        got = self.run_in(fixture=pointer, start_go="true", before_fix_go="null", test_gate_base="null", judge="null")
        self.assertEqual((got["go"], got["received"]), (True, received))
        self.assertEqual((got["units"], got["judgment"], got["answer"], got["head_depth"]),
                         (self.JUDGE["units"], self.JUDGE["judgment"], self.ANSWER, "軽量"), "写した run の頭の深さを運ぶ（標準に倒さない）")
        self.assertFalse((self.artifacts / fixture.DIR).exists(), "固定材料から始めた run は写さない")
        self.assertIs(self.run_in(fixture=pointer, start_go="false")["go"], False)

    def test_judge_return_of_the_prior_version_stops(self):
        """この版より前に走った判定の返り（出力の欄の鍵が無い）を修正前の承認からの resume で受けた fix-in は止める（欄を読んで
        KeyError で落ちない・写さない）。先の無い欄の null は止めない"""
        prior = {key: value for key, value in self.JUDGE.items() if key != "depth_record"}
        with self.assertRaisesRegex(ValueError, judge_accept.PRIOR_VERSION):
            self.run_in(before_fix_go="true", judge=json.dumps({"got": prior, "stop_reason": ""}))
        self.assertFalse((self.artifacts / fixture.DIR).exists())
        self.assertIsNone(self.run_in(before_fix_go="false")["depth_record"])

    def test_plan_return_of_the_prior_version_stops(self):
        """#681: この版より前に走った計画の返り（出力の欄 fix_plan ほかの鍵が無い）を resume で受けた fix-in は止める（修正案の返答の
        無い修正を黙って走らせない・写さない）"""
        prior = {key: value for key, value in self.PLAN.items() if key not in planfile.PORTS}
        with self.assertRaisesRegex(ValueError, planfile.PRIOR_VERSION):
            self.run_in(before_fix_go="true", plan=json.dumps({"got": prior, "stop_reason": ""}))
        self.assertFalse((self.artifacts / fixture.DIR).exists())
        self.assertEqual(self.run_in(before_fix_go="false")["fix_plan"], self.PLAN["fix_plan"])

    def test_returns_and_fallback_are_the_output_format(self):
        required = line_nodes()["fix-in"]["output_format"]["required"]
        self.assertEqual(sorted(self.run_in(before_fix_go="false")), sorted(required))
        self.assertEqual(sorted(fix_in.fallback("x")), sorted(required))
        self.assertEqual(fix_in.fallback("x")["stop_reason"], boundary.LINE_SCRIPT)

    def test_received_names_are_the_collect_fields(self):
        self.assertLessEqual(set(fix_in.received_live({})), set(line_nodes()["collect"]["output_format"]["required"]))

    def test_flat_reads_fields_the_receivers_give(self):
        """fix-in の平らな欄は受け皿の got に在る欄を読む（名がずれた欄は落ちる。黙って null にしない）"""
        got = carried_shape(LINE_TEXT, FIX_IN_TEXT)["got"]
        for name, (part, key) in fix_in.FLAT.items():
            with self.subTest(name=name):
                self.assertIn(key, got[part])
        with self.assertRaises(KeyError):
            fix_in.flat({"judge": {"units": []}})

    def test_flat_keys_do_not_overlap_and_depth_is_the_plan_depth(self):
        """修正の段へ渡す depth は計画の depth。FLAT の辞書の表示の鍵（字の鍵と、全部の内包の名の並び）が重ならないので、辞書の
        表示の後勝ちは結果に効かず、並びに依らない"""
        flat_dict = next(n.value for n in ast.walk(ast.parse(FIX_IN_TEXT)) if isinstance(n, ast.Assign) and
                         any(isinstance(t, ast.Name) and t.id == "FLAT" for t in n.targets))
        shown, literal = [], {}
        for key, value in zip(flat_dict.keys, flat_dict.values):
            if key is None:
                # 数えられる形は「字の並びを回し、鍵が生成の名そのものの内包」だけ。名の ** や並びが字でない内包は数え損ねるので赤にする
                self.assertIsInstance(value, ast.DictComp, "FLAT の ** は内包だけ（名の ** は鍵を数えられない）")
                self.assertEqual(len(value.generators), 1)
                target = value.generators[0].target
                self.assertTrue(isinstance(value.key, ast.Name) and isinstance(target, ast.Name) and value.key.id == target.id,
                                "内包の鍵は生成の名そのもの")
                shown += list(ast.literal_eval(value.generators[0].iter))
            else:
                shown.append(ast.literal_eval(key))
                literal[ast.literal_eval(key)] = ast.literal_eval(value)
        self.assertEqual([k for k, n in collections.Counter(shown).items() if n > 1], [], "FLAT の辞書の表示の鍵が重なる")
        self.assertEqual(literal.get("depth"), ("plan", "depth"), "depth は字の 1 行で計画の depth を引く")
        self.assertEqual(fix_in.FLAT["depth"], ("plan", "depth"))
        self.assertEqual(fix_in.FLAT["head_depth"], ("judge", "depth"))
        got = fix_in.flat({"judge": {**self.JUDGE, "depth": "軽量"}, "plan": {**self.PLAN, "depth": []}})
        self.assertEqual((got["depth"], got["head_depth"]), ([], "軽量"), "返りの depth は計画の depth、head_depth は判定の depth")


LINE_REL = "workflows/line/works-factory-line.yaml"
FIX_IN_REL = "workflows/line/scripts/fix_in.py"
FIXTURE_REL = "lib/fixture.py"
LINE_TEXT = (ROOT / LINE_REL).read_text(encoding="utf-8")
FIX_IN_TEXT = (ROOT / FIX_IN_REL).read_text(encoding="utf-8")


def carried_shape(line_text: str, fix_in_text: str) -> dict:
    """固定材料の運ぶ値の形: fix_in.received_live の鍵と、fix-in が受け皿（script returned）から受ける入力ごとの got の欄（受け皿の
    with: の names）"""
    nodes = line_nodes(yaml.safe_load(line_text)["nodes"])
    live = next(n for n in ast.walk(ast.parse(fix_in_text)) if isinstance(n, ast.FunctionDef) and n.name == "received_live")
    got = {}
    for name, source in nodes["fix-in"]["with"].items():
        node = nodes.get((source.get("from") if isinstance(source, dict) else source).removeprefix("$").removesuffix(".output"))
        if node is not None and node.get("script") == "returned":
            got[name] = sorted(node["with"]["names"].split())
    return {"received": sorted(k.value for r in ast.walk(live) if isinstance(r, ast.Return) for k in r.value.keys), "got": got}


def fixture_format(fixture_text: str):
    return next(n.value.value for n in ast.parse(fixture_text).body
                if isinstance(n, ast.Assign) and [t.id for t in n.targets if isinstance(t, ast.Name)] == ["FORMAT"])


def text_at(rev: str, rel: str) -> str | None:
    """版 rev のファイル rel の字（無ければ None）"""
    got = subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:{rel}"], capture_output=True, text=True, encoding="utf-8", env=hermetic.child_env())
    return got.stdout if got.returncode == 0 else None


class CarriedShapeCase(unittest.TestCase):
    """運ぶ値の形を変える差分は lib/fixture.py の FORMAT も変える（前の形の固定材料を取り込まない）。比べる相手は HEAD と
    origin/main の分かれ目（main にまだ固定材料が無ければ比べない）。分かれ目を引けなければ見送らずに赤（CI は全履歴を取る）"""

    def test_format_moves_with_the_carried_shape(self):
        fork = conceptfence.fork_ref(ROOT)
        if fork is None:
            self.fail(f"HEAD と {conceptfence.MAIN_REF} の分かれ目を引けない（手元では git fetch origin main）")
        old = {rel: text_at(fork, rel) for rel in (LINE_REL, FIX_IN_REL, FIXTURE_REL)}
        if None in old.values():
            return
        if carried_shape(old[LINE_REL], old[FIX_IN_REL]) != carried_shape(LINE_TEXT, FIX_IN_TEXT):
            self.assertNotEqual(fixture.FORMAT, fixture_format(old[FIXTURE_REL]),
                                f"運ぶ値の形が分かれ目 {fork[:12]} と違うのに lib/fixture.py の FORMAT が同じ")

    def test_shape_and_format_read_the_texts(self):
        renamed = LINE_TEXT.replace(" judgment purpose ", " judgment purposex ", 1)
        self.assertNotEqual(carried_shape(renamed, FIX_IN_TEXT), carried_shape(LINE_TEXT, FIX_IN_TEXT))
        self.assertEqual(fixture_format((ROOT / FIXTURE_REL).read_text(encoding="utf-8")), fixture.FORMAT)


class FixInWiringCase(unittest.TestCase):
    """#509: 修正から後ろのノードは直す前のテスト・判定・計画・修正前の承認の答えを fix-in からだけ読み（固定材料の run で飛んだ
    ノードを直に結ぶと落ちる）、固定材料の run は直す前のテストから飛ぶ"""

    SKIPPED = ("$judge.output", "$plan-rounds.output", "$test-gate-base.output", "$answer-before-fix.output",
               "$ask-before-fix.output", "$test-gate-base-out.output", "$judge-out.output", "$plan-rounds-out.output",
               "$plan-rounds-review-out.output")

    @staticmethod
    def after(nodes: dict) -> list:
        """fix-in の後ろのノード（depends_on をたどる）。飛んだノードも待つ all_done のノード（collect から後ろ）は写しの値で埋めるので除く"""
        down = {"fix-in"}
        while grown := {i for i, n in nodes.items() if i not in down and down & set(n.get("depends_on") or [])}:
            down |= grown
        return sorted(i for i in down - {"fix-in"} if nodes[i].get("trigger_rule") != "all_done")

    def test_nodes_after_fix_read_only_the_relay(self):
        nodes = line_nodes()
        self.assertIn("spec-check", self.after(nodes))
        for node in self.after(nodes):
            text = json.dumps({k: nodes[node].get(k) for k in ("with", "when")}, ensure_ascii=False)
            for source in self.SKIPPED:
                with self.subTest(node=node, source=source):
                    self.assertNotIn(source, text)

    def test_fixture_run_skips_from_the_base_tests(self):
        nodes = line_nodes()
        self.assertEqual(nodes["test-gate-base"]["when"], "$answer-start.output.go == true && $start.output.from_fixture == false")
        self.assertEqual((nodes["fix"]["depends_on"], nodes["fix"]["when"]), (["fix-in"], "$fix-in.output.go == true"))
        self.assertIn("answer-start", nodes["fix-in"]["depends_on"])
        self.assertEqual(nodes["fix-in"]["trigger_rule"], "none_failed_min_one_success")
        self.assertEqual(nodes["collect"]["with"]["fix_in"], {"from": "$fix-in.output", "if_skipped": None})


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

    def test_refix_answers_keep_the_push_origin(self):
        """推しで通した関所の答え（欄 answer.PUSHED）を含む 2 度目の修正の answers は、採った推しを合わせて持つ。本文の見出しは答えた
        者を名乗らない（推しの印は読み手が answer.said で 1 度だけ付ける）"""
        rec = {"item": "x", "answer": "continue", "note": "n", "why": "y"}
        before = {"decision": "continue", "text": "n", "asked": ["x"], answer.PUSHED: [rec]}
        got = replan_answer.fix_answers(before, {"decision": "continue", "text": "m", answer.PUSHED: [rec]})
        self.assertEqual(got["text"], f"{replan_answer.FIX_NOTES_HEAD}\n\nn\n\n{replan_answer.NOTE_HEAD}\n\nm\n")
        self.assertEqual(got[answer.PUSHED], [rec, rec])
        self.assertEqual(gatemarks.gate_items(got)[0][answer.PUSHED], [rec, rec])
        self.assertNotIn(answer.PUSHED, replan_answer.fix_answers({"decision": "continue", "text": "人"}, None))

    def test_answer_is_the_gate_answer_with_the_fix_answers(self):
        got = replan_answer.take(json.dumps({"decision": "continue", "text": "x"}), "true", "", "null", "gate-replan", self.artifacts)
        notes = got.pop("fix_notes")
        self.assertIsNone(got.pop("fix_ripple"), "波及の一覧のポインタが無ければ null")
        self.assertEqual(got, {"go": True, "answer": {"decision": "continue", "text": "x", "asked": []}, "stop_reason": "",
                               "fix_answers": {"decision": "continue", "text": f"{replan_answer.NOTE_HEAD}\n\nx\n", "asked": []}})
        self.assertTrue(notes.startswith(replan.NO_REVIEW_WHY.split("{")[0]), "事前審査の返りが無ければ訳を 1 行")

    def test_refix_ripple_falls_back_to_the_first_list(self):
        """L-W17: 2 度目の修正に渡す波及の一覧は、案の直しが作り直した一覧。作り直せなかった（作れなかった訳 error を持つ・読めない）
        時だけ 1 回目の案の一覧（元 works/darkfactory/lib/line_edge.py:169 の refit_ripple_file）。止める答えでは渡さない"""
        ptr = lambda rel: {"type": "archon_artifact", "run_id": RUN, "path": rel}
        (self.artifacts / "replan").mkdir()
        gate = json.dumps({"decision": "continue", "text": ""})
        for doc, want in (({"items": [{"path": "stats.py"}]}, "replan/ripple.json"),
                          ({"items": [], "error": "案が無い"}, "plan/ripple.json"), (None, "plan/ripple.json")):
            with self.subTest(doc=doc):
                path = self.artifacts / "replan" / "ripple.json"
                path.unlink(missing_ok=True)
                if doc is not None:
                    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
                got = replan_answer.take(gate, "true", "", "null", "gate-replan", self.artifacts, None, None, None, "[]",
                                           json.dumps(ptr("replan/ripple.json")), json.dumps(ptr("plan/ripple.json")))
                self.assertEqual(got["fix_ripple"], ptr(want))
        stopped = replan_answer.take(json.dumps({"decision": "stop", "text": ""}), "true", "", "null", "gate-replan",
                                       self.artifacts, None, None, None, "[]", json.dumps(ptr("replan/ripple.json")),
                                       json.dumps(ptr("plan/ripple.json")))
        self.assertIsNone(stopped["fix_ripple"])
        self.assertEqual({k: line_nodes()["answer-replan"]["with"][k] for k in ("ripple", "first_ripple")},
                         {"ripple": "$replan.output.ripple", "first_ripple": "$fix-in.output.ripple"})

    def test_refix_answers_carry_the_non_human_faces_of_taken_items(self):
        """P144・L-D35・L-W17: 2 度目の修正に、採った項目ごとの事前審査の穴のうち人に聞く種類でない物を見出しつきで渡す（元
        works/.shared/core/replan.py:688-693 の _notes の 3 つ目）。人に聞く種類（regression・policy）は関所が聞くので渡さず、人の答え
        fix_answers には混ぜない。止める答えでは渡さない。項目の単位は入力 fix_plan（案の直しの修正案の役の返答）の先から引く"""
        (self.artifacts / "replan").mkdir()
        (self.artifacts / "replan" / "reply-of-the-replan.json").write_text(json.dumps(
            {"plan": [{"unit_keys": ["u1", "u2"]}, {"unit_keys": ["u3"]}]}), encoding="utf-8")
        (self.artifacts / "replan-review").mkdir()
        faces = [{"key": "穴-分母", "kind": "contract_drift", "where": "stats.py", "why": "空の列で割れる", "unit_keys": ["u2"]},
                 {"key": "穴-後退", "kind": "regression", "where": "stats.py", "why": "前の呼び手が壊れる", "unit_keys": ["u1"]},
                 {"key": "穴-ほかの項目", "kind": "entrance", "where": "bounds.py", "why": "入口が増える", "unit_keys": ["u3"]}]
        (self.artifacts / "replan-review" / "review.json").write_text(json.dumps({"faces": faces}, ensure_ascii=False), encoding="utf-8")
        ptr = lambda rel: json.dumps({"type": "archon_artifact", "run_id": RUN, "path": rel})
        got = replan_answer.take(json.dumps({"decision": "continue", "text": "x"}), "true", "", "null", "gate-replan", self.artifacts,
                                   None, ptr("replan-review/review.json"), ptr("replan/reply-of-the-replan.json"), '["1"]')
        self.assertEqual(got["fix_notes"], f"{replan.FACES_HEAD.format(item='1', units='u1、u2')}\n\n"
                                           "- [contract_drift] 穴-分母（stats.py）: 空の列で割れる\n")
        self.assertNotIn("穴-分母", got["fix_answers"]["text"])
        stopped = replan_answer.take(json.dumps({"decision": "stop", "text": "x"}), "true", "", "null", "gate-replan", self.artifacts,
                                       None, ptr("replan-review/review.json"), ptr("replan/reply-of-the-replan.json"), '["1"]')
        self.assertEqual(stopped["fix_notes"], "")
        nodes = line_nodes()
        self.assertEqual(nodes["refix-run"]["with"]["notes"], "$answer-replan.output.fix_notes")
        self.assertEqual({k: nodes["answer-replan"]["with"][k] for k in ("review", "fix_plan", "items")},
                         {"review": {"from": "$replan-review.output.review", "if_skipped": None}, "fix_plan": "$replan.output.fix_plan",
                          "items": "$fix.output.replan_items"})


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
        self.assertEqual(line_nodes()["answer-before-fix"]["with"]["asked"], "$ask-before-fix.output.asked")


class FixWiringCase(FixGateAnswersCase):
    """修正前の関所の答えが fix に届く道（ask-before-fix の asked → answer-before-fix の答え → fix の answers → 置き場の answers.json）"""

    Q2 = {**FixGateAnswersCase.FORK, "key": "q2", "origin": "u2"}

    def place_with(self, answers) -> pathlib.Path:
        place = self.tmp / "fix-place"
        place.mkdir(exist_ok=True)
        (place / fixboard.JUDGMENT_FILE).write_text(json.dumps({"units": [{"key": "u1", "label": "defer"}, {"key": "u2", "label": "block"}],
                                                                "questions": [self.FORK, self.Q2]}), encoding="utf-8")
        (place / fixboard.ANSWERS_FILE).write_text(json.dumps(answers, ensure_ascii=False), encoding="utf-8")
        return place

    def shown_and_answered(self, decision="continue", text="q1 は a"):
        rows = [gatemarks.question_row("fork", gatemarks.ask_text(self.FORK))]
        shown = ask_before_fix.ask(planned(questions=rows, ask_human=True), unattended=False, design_only=False, run_id=RUN)
        return before_fix_answer.take(**self.before_fix_inputs(json.dumps(shown["asked"], ensure_ascii=False)),
                                        artifacts=self.artifacts)["answer"] if decision == "continue" else None

    def test_gate_before_fix_answer_carries_asked(self):
        """F225: 関所の continue を問いへの答えに数えるには、答えに人が見た関所の行 asked が要る。線は answer-before-fix の答えを
        そのまま fix の answers に渡し、fix の置き場の読み（gatemarks.gate_items）がその asked を human_items の行に持つ"""
        answer = self.shown_and_answered()
        self.assertEqual(line_nodes()["fix"]["with"]["answers"], "$fix-in.output.answer")
        items = gatemarks.gate_items(answer)
        self.assertEqual([h["asked"] for h in items], [[gatemarks.ask_text(self.FORK)]])

    def test_fix_gets_returned_and_withheld_units(self):
        """L-G32・L-G33: 関所で答えた問いの出どころ（開いていない defer の単位でも）は直す義務に戻り、修正役に「答えで直す義務に戻った
        単位」の行（returned_lines）が届く。関所に載らなかった・答えていない問いの出どころは直す義務から外れ（withheld）、外れた訳を名指す"""
        place = self.place_with(self.shown_and_answered())
        withheld, back = fixboard.gate_asks(place)
        self.assertEqual((set(withheld), back), ({"u2"}, {"u1"}))
        self.assertEqual(fixboard.group_owed(place), ["u1"])
        notes = pathlib.Path(fixboard.write_notes(place)).read_text(encoding="utf-8")
        self.assertIn("q1 は a", notes)
        self.assertIn(f"承認ノードで答えた{gatemarks.ASK_HEAD} q1 の出どころ・depends は直す義務に戻った", notes)
        owed, excused = fixboard.fix_duty(place, set(fixboard.group_owed(place)))
        self.assertEqual((owed, set(excused)), ({"u1"}, {"u2"}))
        self.assertIn("答え待ちの問い q2", excused["u2"])

    def test_fix_notes_name_a_pushed_answer_as_a_push(self):
        """無人の run が推しで通した修正前の承認ノードの一言は、修正役の notes_file に頭 PUSHED_NOTE つきで届く（人の答えと名乗らない）。
        人の答えの一言は頭を持たない"""
        note = "空の列は 0 を返す形で通す"
        pushed = {"decision": "continue", "text": note, "asked": [],
                  answer.PUSHED: [{"item": "1", "answer": "continue", "note": note, "why": "既存の呼び手が 0 を待つ"}]}
        read = lambda got: pathlib.Path(fixboard.write_notes(self.place_with(got))).read_text(encoding="utf-8")
        self.assertEqual(read(pushed), f"{answer.PUSHED_NOTE}\n{note}")
        self.assertEqual(read({key: v for key, v in pushed.items() if key != answer.PUSHED}), note)

    def test_refix_notes_mark_a_pushed_answer_once_and_keep_the_headings(self):
        """#562: 2 度目の修正の answers（replan_answer.fix_answers の見出しつきの本文）を推しで通した時も、修正役の notes_file と相談の
        条件には推しの印が 1 度だけ付き、見出しの行は行の頭から始まる（印を見出しの前に繋げて Markdown の見出しを崩さない）"""
        rec = {"item": "1", "answer": "continue", "note": "n", "why": "y"}
        got = replan_answer.fix_answers({"decision": "continue", "text": "空の列は 0 を返す", "asked": [], answer.PUSHED: [rec]},
                                        {"decision": "continue", "text": "項目 1 も", answer.PUSHED: [rec]})
        notes = pathlib.Path(fixboard.write_notes(self.place_with(got))).read_text(encoding="utf-8")
        said = consult.gate_notes(None, gatemarks.gate_items(got))
        for text in (notes, said):
            with self.subTest(text=text):
                self.assertTrue(text.startswith(f"{answer.PUSHED_NOTE}\n{replan_answer.FIX_NOTES_HEAD}\n"), text)
                self.assertEqual(text.count(answer.PUSHED_NOTE), 1)
                self.assertIn(f"\n{replan_answer.NOTE_HEAD}\n", text)


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
                self.assertEqual(got, {"go": True, "answer": {"decision": word, "text": "a.py だけ", "asked": []}, "stop_reason": ""})
                kept = json.loads((self.artifacts / "gates" / "gate-before-fix.json").read_text(encoding="utf-8"))
                self.assertEqual(kept, got["answer"])

    def test_stop_word_stops_with_the_gate_named(self):
        got = gate_answer.take(json.dumps({"decision": "stop", "text": "やめる"}), "true", "", "gate-final", self.artifacts)
        self.assertEqual((got["go"], got["stop_reason"]), (False, "human:gate-final"))
        self.assertEqual(json.loads((self.artifacts / "gates" / "gate-final.json").read_text(encoding="utf-8"))["decision"], "stop")

    def test_reject_stops_like_stop(self):
        got = gate_answer.take(json.dumps({"decision": answer.REJECT, "text": ""}), "true", "", "gate-replan", self.artifacts)
        self.assertEqual((got["go"], got["stop_reason"]), (False, "human:gate-replan"))

    def test_unknown_word_stops(self):
        """L-G03: 通す語でない答え（知らない語も）は通さず、止めと読む（元 line_edge.py 191-203 行 _gate_words は知らない語を落とした）"""
        got = gate_answer.take(json.dumps({"decision": "maybe", "text": ""}), "true", "", "gate-before-fix", self.artifacts)
        self.assertEqual((got["go"], got["stop_reason"]), (False, "human:gate-before-fix"))

    def test_empty_stop_note_gets_the_default_reason(self):
        """L-G07: stop・reject の一言が空なら既定の文を止めの理由にする（元 line_edge.py 98・104 行の GATE_STOP_NOTE・
        FINAL_GATE_STOP_NOTE）。一言が在れば字のまま。通す答えの空の一言は空のまま"""
        for place, word, want, final in (("gate-final", "stop", answer.FINAL_STOP_NOTE, True),
                                         ("gate-before-fix", "reject", answer.STOP_NOTE, False),
                                         ("gate-start", "stop", answer.STOP_NOTE, False)):
            with self.subTest(place=place, word=word):
                got = gate_answer.take(json.dumps({"decision": word, "text": " "}), "true", "", place, self.artifacts,
                                       **({"final": True} if final else {}))
                self.assertEqual(got["answer"]["text"], want)
                self.assertEqual(json.loads((self.artifacts / "gates" / f"{place}.json").read_text(encoding="utf-8"))["text"], want)
        self.assertEqual((answer.STOP_NOTE, answer.FINAL_STOP_NOTE), ("承認ノードで止めた", "最後の承認ノードで止めた"))
        nodes = line_nodes()
        self.assertEqual([nodes[n]["with"]["final"] for n in ("answer-start", "answer-final")], ["false", "true"])
        with mock.patch.dict(os.environ, {"INPUTS_FINAL": "true"}):
            self.assertIs(gate_answer.from_env()["final"], True)
        with mock.patch.dict(os.environ, {"INPUTS_FINAL": "false"}):
            self.assertIs(gate_answer.from_env()["final"], False)
        got = gate_answer.take(json.dumps({"decision": "stop", "text": "範囲が違う"}), "true", "", "gate-final", self.artifacts)
        self.assertEqual(got["answer"]["text"], "範囲が違う")
        got = gate_answer.take(json.dumps({"decision": "continue", "text": ""}), "true", "", "gate-final", self.artifacts)
        self.assertEqual(got["answer"]["text"], "")

    def test_answer_carries_asked(self):
        """L-W14・S46: どの関所の答えも {decision, text, asked} の 1 つの形。asked は関所が人に見せた項目の行で、項目を持たない関所は []。
        一言は字のまま答えに残り、gates/<関所>.json にも同じ形で書く"""
        for place in ("gate-start", "gate-replan", "gate-final"):
            with self.subTest(place=place):
                got = gate_answer.take(json.dumps({"decision": "continue", "text": "範囲は\n a.py だけ"}), "true", "", place,
                                         self.artifacts)["answer"]
                self.assertEqual(got, {"decision": "continue", "text": "範囲は\n a.py だけ", "asked": []})
        rows = ["汚くない（clean）の軸が通らない: 名前", gatemarks.ask_text(FixGateAnswersCase.FORK)]
        got = answer.taken({"decision": "approve", "text": "q1 は a"}, go=True, stop_reason="", place="gate-before-fix",
                           folder=self.artifacts, asked=rows)["answer"]
        self.assertEqual(got, {"decision": "approve", "text": "q1 は a", "asked": rows})
        self.assertEqual(json.loads((self.artifacts / "gates" / "gate-before-fix.json").read_text(encoding="utf-8")), got)

    def test_before_fix_answer_carries_the_asked_items(self):
        """P241: answer-before-fix の答えは、ask-before-fix が関所に載せた項目の文を asked に持つ（線の with: が ask-before-fix の asked を
        渡す）。無いと fix の置き場の読み（gatemarks._asked_in）が偽になり、continue を受けても問いの出どころが直す義務に戻らない"""
        shown = ask_before_fix.ask(planned(questions=[gatemarks.question_row("fork", gatemarks.ask_text(FixGateAnswersCase.FORK))],
                                           ask_human=True), unattended=False, design_only=False, run_id=RUN)
        env = {"INPUTS_GATE": json.dumps({"decision": "continue", "text": ""}), "INPUTS_GO": "true", "INPUTS_STOP_REASON": "",
               "INPUTS_PLACE": "gate-before-fix", "INPUTS_ASKED": json.dumps(shown["asked"], ensure_ascii=False)}
        with mock.patch.dict(os.environ, env):
            got = before_fix_answer.take(**before_fix_answer.from_env(), artifacts=self.artifacts)
        self.assertEqual(got["answer"]["asked"], [gatemarks.ask_text(FixGateAnswersCase.FORK)])
        self.assertEqual(line_nodes()["answer-before-fix"]["with"]["asked"], "$ask-before-fix.output.asked")



def pushed_row(word: str, note: str) -> str:
    """推しの尾つきの狭めの行（gatemarks._push の形）"""
    rec = {"answer": word, "note": f"{note} で通す", "why": "呼び手が 0 を前提に書かれている"}
    return gatemarks._item(f"修正案 1 が狭める能力: {note}", {gatemarks.RECOMMEND: rec}, ("決め手の欄が揃わない",))


def planned(**kw) -> dict:
    got = {"ready": True, "pass": True, "stalled": False, "round": 1, "ask_human": False,
           "gate_axes": {key: {"ok": True, "note": ""} for key in ask_before_fix.AXES}, "questions": []}
    got.update(kw)
    return got


class UnattendedPolicyCallCase(unittest.TestCase):
    def test_gate_scripts_leave_the_unattended_choice_to_the_policy(self):
        """#653: 修正前と案の直しの承認ノードの script は、無人の run の進むか止まるかを gatepolicy.passage に渡すだけで、止めの語を
        自分で組まない（分かれ道の写しを持たない）"""
        for name in ("ask_before_fix", "ask_replan"):
            with self.subTest(name=name):
                text = (SCRIPTS / f"{name}.py").read_text(encoding="utf-8")
                self.assertIn("gatepolicy.passage(", text)
                self.assertNotIn("NEEDS_HUMAN", text)


class AskBeforeFixCase(unittest.TestCase):
    def ask(self, plan, unattended=False, design_only=False):
        return ask_before_fix.ask(plan, unattended=unattended, design_only=design_only, run_id=RUN)

    def test_no_plan_goes_nowhere(self):
        self.assertEqual(self.ask(planned(ready=False)), {"open": False, "go": False, "stop_reason": "", "text": "", "deferred": [],
                                                           "asked": [], "pushed": None})

    def test_clean_plan_goes_to_fix_without_the_gate(self):
        self.assertEqual(self.ask(planned()), {"open": False, "go": True, "stop_reason": "", "text": "", "deferred": [], "asked": [],
                                               "pushed": None})

    def test_reasons_that_open_the_gate(self):
        failing = {**planned()["gate_axes"], "clean": {"ok": False, "note": "名前が合わない"}}
        for plan, words in ((planned(gate_axes=failing), "汚くない（clean）の軸が通らない: 名前が合わない"),
                            (planned(questions=[gatemarks.question_row("fork", "0 を返すか")]), "0 を返すか"),
                            (planned(ask_human=True), "直す前の承認ノード"),
                            (planned(**{"pass": False, "stalled": True}), gatemarks.STUCK_ITEM),
                            (planned(**{"pass": False, "stalled": True, "round": ROUND_LIMIT, "ask_human": True,
                                        "questions": [f"{gatemarks.STUCK_ITEM}。理由: " + converge.CAP_WHY.format(
                                            n=ROUND_LIMIT, counts="1 往復目 2 → 20 往復目 1")]}),
                             "工場の不具合として止めた")):
            with self.subTest(words=words):
                got = self.ask(plan)
                self.assertEqual((got["open"], got["go"]), (True, True))
                self.assertIn(words, got["text"])

    def test_design_only_always_opens(self):
        got = self.ask(planned(), design_only=True)
        self.assertTrue(got["open"])
        self.assertIn("設計だけの run", got["text"])

    def test_unattended_moves_questions_to_the_report(self):
        got = self.ask(planned(questions=[gatemarks.question_row("fork", "0 を返すか")], ask_human=True), unattended=True)
        self.assertEqual(got, {"open": False, "go": True, "stop_reason": "", "text": "", "deferred": ["0 を返すか"], "asked": [],
                               "pushed": None})

    def test_unattended_stops_where_the_gate_would_open(self):
        got = self.ask(planned(**{"pass": False, "stalled": True}), unattended=True)
        self.assertEqual((got["open"], got["go"], got["stop_reason"]), (False, False, stopby.NEEDS_HUMAN))

    def test_unattended_design_only_stops(self):
        """L-G27: 無人で設計だけの run は、関所で止まって報告へ進む（開かず・修正へ進まず・needs-human）"""
        got = self.ask(planned(), unattended=True, design_only=True)
        self.assertEqual((got["open"], got["go"], got["stop_reason"], got["pushed"]), (False, False, stopby.NEEDS_HUMAN, None))

    def test_unattended_takes_the_push_when_every_item_pushes_continue(self):
        """#552: 無人の run は、関所に載る項目の全部が通す推しを持てば推しで修正へ進み（開かない）、採った推しを pushed で返す。
        台帳の問いは今どおり deferred に回り、推しの判定に入らない"""
        rows = [pushed_row("continue", "a"), pushed_row("continue", "b")]
        fork = gatemarks.question_row("fork", "0 を返すか")
        got = self.ask(planned(questions=[fork, *[gatemarks.question_row("regression", r) for r in rows]], ask_human=True),
                       unattended=True)
        self.assertEqual((got["open"], got["go"], got["stop_reason"], got["deferred"], got["asked"]),
                         (False, True, "", ["0 を返すか"], rows))
        self.assertEqual(got["pushed"], gatepolicy.passage(rows, gatemarks.row_push).pushed)
        self.assertEqual(got["pushed"]["text"], "a で通す；b で通す")

    def test_unattended_stops_when_a_push_stops_or_is_missing(self):
        """#552: 推しが止める・推しの無い項目が 1 つでも混じれば、今どおり止める（needs-human・pushed は null）"""
        for rows in ([pushed_row("continue", "a"), pushed_row("stop", "b")],
                     [pushed_row("continue", "a"), "修正案 2 が狭める能力: y（人に聞く訳: 決め手の欄が揃わない）"]):
            with self.subTest(rows=rows):
                got = self.ask(planned(questions=[gatemarks.question_row("regression", r) for r in rows]), unattended=True)
                self.assertEqual((got["open"], got["go"], got["stop_reason"], got["pushed"]), (False, False, stopby.NEEDS_HUMAN, None))

    def test_attended_run_opens_the_gate_even_with_pushes(self):
        """#552: 人のいる run は推しが揃っていても今どおり関所を開いて人を待つ"""
        got = self.ask(planned(questions=[gatemarks.question_row("regression", pushed_row("continue", "a"))]))
        self.assertEqual((got["open"], got["pushed"]), (True, None))

    def test_pushed_answer_is_recorded_as_the_gate_answer(self):
        """#552: answer-before-fix は推しで進んだ答えを関所の答えとして gates/gate-before-fix.json に残し、欄 pushed で人の答えと
        読み分ける（線の with: が ask-before-fix の pushed を渡す）"""
        rows = [pushed_row("continue", "a")]
        shown = self.ask(planned(questions=[gatemarks.question_row("regression", r) for r in rows]), unattended=True)
        with tempfile.TemporaryDirectory() as tmp:
            got = before_fix_answer.take("null", "true", "", "gate-before-fix", json.dumps(shown["asked"], ensure_ascii=False), "null",
                                         pathlib.Path(tmp), json.dumps(shown["pushed"], ensure_ascii=False))
            kept = json.loads((pathlib.Path(tmp) / answer.ANSWERS / "gate-before-fix.json").read_text(encoding="utf-8"))
        self.assertEqual((got["go"], got["stop_reason"]), (True, ""))
        self.assertEqual(got["answer"], {"decision": "continue", "text": "a で通す", "asked": rows,
                                         answer.PUSHED: shown["pushed"][answer.PUSHED]})
        self.assertEqual(kept, got["answer"])
        self.assertEqual(line_nodes()["answer-before-fix"]["with"]["pushed"], "$ask-before-fix.output.pushed")

    def test_unattended_stops_on_policy_change_rows(self):
        """L-G40・L-G38・P236: 無人の run は台帳の問い（fork・escalate）だけなら関所を開かず報告へ回して修正へ進み、聞くはずだった
        ほかの項目（方針の文書の変化・事前審査の諦め・狭め・事前審査の穴・世界の解の外れ）が在れば見落とさずに止まる"""
        fork = gatemarks.question_row("fork", "0 を返すか")
        for kind in ("policy_changed", gatemarks.GIVEN_UP_KIND, "regression", "policy", gatemarks.WORLD_KIND):
            with self.subTest(kind=kind):
                got = self.ask(planned(questions=[fork, gatemarks.question_row(kind, "人が決める行")], ask_human=True), unattended=True)
                self.assertEqual((got["open"], got["go"], got["stop_reason"], got["deferred"]),
                                 (False, False, stopby.NEEDS_HUMAN, ["0 を返すか"]))
        got = self.ask(planned(questions=[fork, gatemarks.question_row("escalate", "人でないと決められない")], ask_human=True),
                       unattended=True)
        self.assertEqual((got["open"], got["go"], got["deferred"]), (False, True, ["0 を返すか", "人でないと決められない"]))

    def test_kinds_come_from_the_gate_record(self):
        """P250: 関所の文の冒頭の種類と台帳の問いへの答え方（ASK_GATE_HEAD）は、事前審査が返した項目の種類から決まる（方針の変化の行
        だけなら台帳の問いと名乗らない）。関所に載せた項目の文は asked で返る"""
        changed = gatemarks.question_row("policy_changed", "人の方針の文書が固定した版から変わった")
        got = self.ask(planned(questions=[changed], ask_human=True))
        head = got["text"].splitlines()[0]
        self.assertIn(f"{gatemarks.KIND_WORDS['policy_changed']}（policy_changed）", head)
        self.assertNotIn(gatemarks.KIND_WORDS["fork"], head)
        self.assertNotIn(gatemarks.ASK_GATE_HEAD, got["text"])
        self.assertEqual(got["asked"], [changed["text"]])
        got = self.ask(planned(questions=[changed, gatemarks.question_row("fork", "0 を返すか")], ask_human=True))
        self.assertIn(gatemarks.ASK_GATE_HEAD, got["text"])
        self.assertEqual(got["asked"], [changed["text"], "0 を返すか"])


    def test_item_kinds_are_kept(self):
        """L-G21: 関所の項目の種類を平易な名で頭に並べる（狭めの行の頭が「今ある能力を減らす・狭める変更（regression）」）。台帳の
        答え方（ASK_GATE_HEAD）は台帳の問いが在る時だけ"""
        got = self.ask(planned(questions=[gatemarks.question_row("regression", "修正案 1 が狭める能力: x")], ask_human=True))
        head = got["text"].splitlines()[0]
        self.assertIn(f"{gatemarks.KIND_WORDS['regression']}（regression）", head)
        self.assertNotIn(gatemarks.KIND_WORDS["fork"], head)
        self.assertNotIn(gatemarks.ASK_GATE_HEAD, got["text"])

    def test_question_is_quoted_with_the_note(self):
        """L-G23: 問いの文は記録のまま引用し（> の行）、読み替えの行（QUOTE_NOTE）を添える"""
        text = self.ask(planned(questions=[gatemarks.question_row("regression", "修正案 1 が狭める能力: x")]))["text"]
        self.assertIn(f"> {ask_before_fix.QUESTION}\n{gatemarks.QUOTE_NOTE}", text)

    def test_stalled_has_one_row_with_the_reason(self):
        """L-D19: 壁打ちが止まった案は必ず開け、行は 1 つで、尾に止まった理由（事前審査の design_item の行のまま）"""
        stuck = gatemarks.STUCK_ITEM + "。理由: 3 往復続いた block の key: k1（往復 3）"
        got = self.ask(planned(**{"pass": False, "stalled": True}, questions=[gatemarks.question_row(gatemarks.DESIGN_ONLY_KIND, stuck)]))
        self.assertTrue(got["open"])
        self.assertEqual(got["asked"], [stuck])
        self.assertEqual(got["text"].count(gatemarks.STUCK_ITEM), 1)

    def test_plan_review_rows_are_not_repeated(self):
        """P249: 関所に載る行は 1 件 1 行で重ならない: 設計だけの行と止まりの行は事前審査の 1 行、決め手の揃わない行の訳は項目の尾に
        1 度（軸の行を足し直さない）。項目の無い時だけ軸の訳が行になる"""
        both = gatemarks.DESIGN_ONLY_ITEM + "。理由: x"
        narrow = "修正案 1 が狭める能力: x（人に聞く訳: 決め手の欄が揃わない（decided_by が無いか、undecided_because が在る））"
        failing = {**planned()["gate_axes"], "obvious": {"ok": False, "note": "修正案 1 が狭める能力: x: 決め手の欄が揃わない"}}
        got = self.ask(planned(**{"pass": False, "stalled": True}, gate_axes=failing,
                               questions=[gatemarks.question_row("regression", narrow),
                                          gatemarks.question_row(gatemarks.DESIGN_ONLY_KIND, both)]), design_only=True)
        self.assertEqual(got["asked"], [narrow, both])
        self.assertEqual(self.ask(planned(gate_axes=failing))["asked"], ["自明（obvious）の軸が通らない: 修正案 1 が狭める能力: x: 決め手の欄が揃わない"])


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
        self.assertEqual(got["widened"], ["項目 1: 直した——無人の run なので人に聞かずに範囲を広げた（allowed_paths に足した: util.py）"])

    def test_asked_items_reach_the_gate_answer(self):
        """P146・L-D39: 案の直しの関所に見せた項目の行（asked）を answer-replan が答えの asked にし、報告と最後の関所は項目ごとに人が
        承認したか聞かずに通したかを読む（lib/replan.amend_lines。元 replan.lines の行の ask）"""
        got = self.ask({**self.ITEM, "out_of_scope": ["cli.py"]})
        self.assertEqual(got["asked"], ["項目 1: 約束の欄が変わった（out_of_scope）"])
        self.assertEqual(self.ask({**self.ITEM, "approach": "別の手段"})["asked"], [])
        answered = replan_answer.take('{"decision": "continue", "text": "よい"}', "true", "", "null", "gate-replan", self.artifacts,
                                        json.dumps(got["asked"], ensure_ascii=False))
        self.assertEqual(answered["answer"]["asked"], got["asked"])
        self.assertEqual(replan.amend_lines(["1"], refixed=True, answer=answered["answer"]), ["案の項目 1: 直した——人が承認した"])
        nodes = line_nodes()
        self.assertEqual(nodes["answer-replan"]["with"]["asked"], "$ask-replan.output.asked")
        self.assertEqual({k: nodes["ask-final"]["with"][k] for k in ("replan_answer", "widened")},
                         {"replan_answer": {"from": "$answer-replan.output.answer", "if_skipped": None},
                          "widened": {"from": "$ask-replan.output.widened", "if_skipped": None}})

    def test_gate_text_shows_claim_ruling_and_both_items(self):
        """L-G44・L-D31: 案の直しの関所の文は聞く項目ごとに、約束の欄の変化・その項目を誤りとした申し出の文と裁定の文（字のまま）・
        前の項目と直した項目の JSON を見せる（元 replan._gate_section）"""
        rows = [{"id": "c1", "unit_key": "u1", "between": ["stats.py:3", "t.py:2"], "why_both_cannot_hold": "案の範囲では直らない",
                 "which_is_right": "request", "ruling": {"decision": conflict.REPLAN, "text": "項目 1 の範囲が誤り。cli.py も要る",
                                                         "limits": [], conflict.PLAN_ITEMS: [1]}},
                {"id": "c2", "unit_key": "u9", "between": ["x.py:1", "y.py:2"], "why_both_cannot_hold": "別の項目",
                 "which_is_right": "code", "ruling": {"decision": conflict.REPLAN, "text": "項目 2 の誤り", "limits": [], conflict.PLAN_ITEMS: [2]}}]
        (self.artifacts / "fix").mkdir()
        (self.artifacts / "fix" / conflict.FILE).write_text(json.dumps({"items": rows}, ensure_ascii=False), encoding="utf-8")
        ptr = {"type": "archon_artifact", "run_id": RUN, "path": f"fix/{conflict.FILE}"}
        new = {**self.ITEM, "out_of_scope": ["cli.py"]}
        got = ask_replan.ask(self.plan("old.json", self.ITEM), self.plan("new.json", new), ["1"], ask_human=False, questions=[],
                             unattended=False, run_id=RUN, conflicts=ptr)
        text = got["text"]
        for want in ("## 人に聞く直した項目 1（単位 u1）", "- 約束の欄の変化: out_of_scope", "- 申し出の文（c1・単位 u1）: 案の範囲では直らない",
                     "- 裁定の文（c1）: 項目 1 の範囲が誤り。cli.py も要る", replan.OLD_HEAD, ask_replan.NEW_HEAD,
                     json.dumps(self.ITEM, ensure_ascii=False, indent=1), json.dumps(new, ensure_ascii=False, indent=1)):
            self.assertIn(want, text)
        self.assertNotIn("c2", text)
        self.assertEqual(line_nodes()["ask-replan"]["with"]["conflicts"], "$fix.output.conflicts")

    def test_unattended_stops_on_a_contract_change(self):
        got = self.ask({**self.ITEM, "out_of_scope": ["cli.py"]}, unattended=True)
        self.assertEqual((got["open"], got["go"], got["stop_reason"], got["pushed"]), (False, False, stopby.NEEDS_HUMAN, None))

    def test_unattended_takes_the_push_of_the_review_questions(self):
        """#552: 無人の run は、聞く行が事前審査の問いだけで全部が通す推しを持てば推しで 2 度目の修正へ進み、answer-replan が答えとして
        残す。約束の欄が変わった項目の行は推しを持たないので、混じれば今どおり止まる"""
        q = gatemarks.question_row("regression", pushed_row("continue", "a"))
        got = ask_replan.ask(self.plan("old.json", self.ITEM), self.plan("new.json", self.ITEM), ["1"], ask_human=True, questions=[q],
                             unattended=True, run_id=RUN)
        self.assertEqual((got["open"], got["go"], got["stop_reason"], got["asked"]), (False, True, "", [f"事前審査の問い: {q['text']}"]))
        self.assertEqual(got["pushed"]["text"], "a で通す")
        answered = replan_answer.take("null", "true", "", "null", "gate-replan", self.artifacts,
                                      json.dumps(got["asked"], ensure_ascii=False), pushed_raw=json.dumps(got["pushed"], ensure_ascii=False))
        self.assertEqual((answered["go"], answered["answer"]["text"], answered["answer"][answer.PUSHED]),
                         (True, "a で通す", got["pushed"][answer.PUSHED]))
        self.assertEqual(line_nodes()["answer-replan"]["with"]["pushed"], "$ask-replan.output.pushed")
        changed = ask_replan.ask(self.plan("old.json", self.ITEM), self.plan("new.json", {**self.ITEM, "out_of_scope": ["cli.py"]}), ["1"],
                                 ask_human=True, questions=[q], unattended=True, run_id=RUN)
        self.assertEqual((changed["go"], changed["stop_reason"], changed["pushed"]), (False, stopby.NEEDS_HUMAN, None))

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
        self.assertIn("承認ノードはいつも開く設定", got["text"].splitlines()[0])

    def test_protected_hits_and_conflicts_open_in_every_mode(self):
        for mode in ("when_needed", "protected_only"):
            for got in (self.got(protected_hits=["tests/x.py"]), self.got(asked=["u1: 人に回した"]),
                        self.got(conflicts_unread=["fix/conflicts.json: 読めない"]), self.got(allowed_tests=[{"path": "tests/t.py", "permit": "plan-1", "source": "plan"}])):
                with self.subTest(mode=mode, got=got["protected_hits"] or got["asked"] or got["conflicts_unread"] or got["allowed_tests"]):
                    self.assertTrue(self.ask(got, mode)["open"])

    def test_protected_only_ignores_other_reasons(self):
        self.assertFalse(self.ask(self.got(green=False), "protected_only")["open"])

    def test_spec_changed_opens_in_every_mode(self):
        """#510: 承認の後に受け入れ条件のテストが変わった問いは開き方に依らず開き、1 行目に名指し、この関所の答えが問いに答えないと言う"""
        q = "承認の後に受け入れ条件のテストが変わった（spec_changed）: test_spec_accept.txt（sha256 aaaaaaaaaaaa → bbbbbbbbbbbb）——承認し直すか"
        for mode in ("", "when_needed", "protected_only"):
            with self.subTest(mode=mode):
                got = self.ask(self.got(spec_changed=[q]), mode)
                self.assertIs(got["open"], True)
                self.assertIn(gatemarks.KIND_WORDS[gatemarks.SPEC_CHANGED_KIND], got["text"].splitlines()[0])
                self.assertIn(q, got["text"])
                self.assertIn("この承認ノードの答えはこの問いに答えない", got["text"])
                self.assertIn(ask_final.SPEC_APPLIES.strip(), got["text"], "#550: 承認すると差分が当たると言う")
        self.assertNotIn(ask_final.SPEC_APPLIES.strip(), self.ask(self.got())["text"], "問いの無い run の文は増やさない")

    def test_spec_unchecked_says_could_not_check(self):
        """#550: 照らせなかった（unchecked）時は、1 行目と節の頭が「変わった」でなく「照らせなかった」と言う。開くのは同じ"""
        q = "照らしが落ちた——承認済みの受け入れ条件のテストが変わったかを確かめられない（ValueError: x）"
        for mode in ("", "when_needed", "protected_only"):
            with self.subTest(mode=mode):
                got = self.ask(self.got(spec_changed=[q], spec_unchecked=True), mode)
                self.assertIs(got["open"], True)
                first = got["text"].splitlines()[0]
                self.assertIn(gatemarks.SPEC_UNCHECKED, first)
                self.assertNotIn(gatemarks.KIND_WORDS[gatemarks.SPEC_CHANGED_KIND], first)
                self.assertIn(gatemarks.SPEC_UNCHECKED_HEAD, got["text"])
                self.assertNotIn(gatemarks.SPEC_CHANGED_HEAD, got["text"])
                self.assertIn(ask_final.SPEC_APPLIES.strip(), got["text"])

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
        self.assertEqual(nodes["merge-apply"]["when"], "$answer-final.output.go == true && $fixed.output.no_fix == false")

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
                      ask_final.final_needs(self.got(objection="異議\n2 度目の異議", rejudge_verdict="一部採る")),
                      "2 度目の修正の異議も同じ再審を受け、採られなければ残る")


    def test_allowed_test_changes_open_in_every_mode(self):
        """M30: 承認済みの案と裁定が書き換えを許したテストを触った run も、守りのパスと同じに開き方に依らず開き、1 行目と最初の節で
        名指す。無人の run なら開かずに止める（merge-apply は飛ぶ）"""
        got = self.got(allowed_tests=[{"path": "tests/test_mean.py", "permit": "ruled-test-c1-1", "source": "ruling"}])
        for mode in ("when_needed", "protected_only", "always"):
            with self.subTest(mode=mode):
                out = self.ask(got, mode)
                self.assertTrue(out["open"])
                self.assertIn(f"{ask_final.ALLOWED_TESTS_HEAD}（1 件。人の確かめが要る）", out["text"].splitlines()[0])
                self.assertTrue(out["text"].splitlines()[4].startswith("## " + ask_final.ALLOWED_TESTS_HEAD))
        self.assertEqual(self.ask(got, "protected_only", unattended=True)["stop_reason"], stopby.NEEDS_HUMAN)

    def test_accepted_breaks_open_and_are_listed(self):
        """L-W20・F427: 修正役が人に回した物（壊すと分かって通した理由）が在れば開ける理由にし（元 _final_needs の handoffs）、
        1 行目に件数、節 HANDOFF_HEAD に 1 件 1 行で並べる。開き方 when_needed で開き、無ければ開かない"""
        rows = ["u1: 壊すと分かって通した——古い呼び手の戻り値が変わる"]
        out = self.ask(self.got(handoffs=rows), "when_needed")
        self.assertTrue(out["open"])
        self.assertIn(f"{ask_final.HANDOFF_REASON}（1 件）", out["text"].splitlines()[0])
        self.assertIn(f"## {fixboard.HANDOFF_HEAD}（1 件。通すのは人の continue だけ）\n\n- {rows[0]}", out["text"])
        self.assertFalse(self.ask(self.got(), "when_needed")["open"])

    def test_recount_mismatch_is_a_reason(self):
        """L-W21・F428: 直したという申告と機械の数え直しが合わない単位（closure_lines の mismatched_only）が在れば開ける理由にし、
        減っていない単位（STUCK_HEAD）と閉鎖の数え直しの節（CLOSURE_HEAD）を並べる"""
        got = self.got(mismatched=["A: 閉じていない（defects・修正前 3・修正後 3）"], stuck=["A: 閉じていない（defects）"],
                       closure=["C: 閉鎖の表に行が無い"])
        out = self.ask(got, "when_needed")
        self.assertTrue(out["open"])
        self.assertIn(f"{ask_final.MISMATCH_REASON}（1 件）", out["text"].splitlines()[0])
        self.assertIn(f"## {querytest.STUCK_HEAD}（1 件）", out["text"])
        self.assertIn(f"## {querytest.CLOSURE_HEAD}（1 件）\n\n- C: 閉鎖の表に行が無い", out["text"])
        self.assertFalse(self.ask(self.got(stuck=["A"], closure=["C"]), "when_needed")["open"], "閉じていないだけは見せるだけ")

    def test_open_and_first_line_come_from_one_list(self):
        """L-G48: 開くかと 1 行目の開けた理由は同じ 1 つの列（ask_final.needs）。開き方に依らず開く理由は列の印 must だけで決まる"""
        cases = (self.got(protected_hits=["tests/x.py"]), self.got(asked=["u1: 人に回した"]), self.got(green=False),
                 self.got(conflicts_unread=["fix/conflicts.json: 読めない"]), self.got(allowed_tests=[{"path": "tests/t.py", "permit": "plan-1", "source": "plan"}]),
                 self.got(questions=["q"]), self.got(sealed=False))
        for got in cases:
            rows = ask_final.needs(got)
            with self.subTest(rows=rows):
                out = self.ask(got, "protected_only")
                self.assertEqual(out["open"], any(must for _, must in rows))
                self.assertEqual(out["reasons"], [phrase for phrase, _ in rows])
                opened = self.ask(got, "when_needed")
                self.assertIn("開けた理由: " + "・".join(opened["reasons"]), opened["text"].splitlines()[0])

    def test_settled_rejudge_lines_are_shown(self):
        """L-W30: 決着した再審の結果（runreport.rejudge_lines）を並べ、再審が無ければ「再審: 無い」"""
        rows = ["再審の結果（1 往復）: 退ける（異議: 異議）", "  - 再審が直す単位にした（この run では直していない——次の run に渡す）: u2"]
        text = ask_final.final_text(self.got(rejudge=rows), [], RUN)
        self.assertIn("- 再審で決着した結果:\n  - 再審の結果（1 往復）: 退ける（異議: 異議）\n    - 再審が直す単位にした", text)
        self.assertIn("- 再審: 無い", ask_final.final_text(self.got(), [], RUN))
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"ARTIFACTS_DIR": tmp, "WORKFLOW_ID": RUN}):
            (pathlib.Path(tmp) / "rejudge").mkdir()
            (pathlib.Path(tmp) / "rejudge" / "judgment.json").write_text('{"units": []}', encoding="utf-8")
            (pathlib.Path(tmp) / "rejudge" / judge_accept.REJUDGE_EXIT).write_text(json.dumps(
                {"verdicts": ["退ける"], "objection": "異議", "new_open_units": ["u2"], "lowered": []}), encoding="utf-8")
            ptr = {"type": "archon_artifact", "run_id": RUN, "path": "rejudge/judgment.json"}
            exit_ = {"type": "archon_artifact", "run_id": RUN, "path": f"rejudge/{judge_accept.REJUDGE_EXIT}"}
            returns = ask_final.judged_returns({"units": [{"id": "u1"}, {"id": "u2"}], "first_units": [{"id": "u1"}], "judgment": ptr,
                                                "first_judgment": None, "rejudge_exit": exit_, "rejudged": True,
                                                "rejudge_verdict": "退ける", "objection": "異議",
                                                "fix_units": [{"unit_id": "u1"}], "groups": []})
            self.assertEqual(ask_final.rejudge_rows(returns), rows)

    def test_questions_say_the_answer_does_not_answer_them(self):
        """L-W35: 人に聞いている問いを記録のまま引き（> の行）、「この関所の答えはこの問いに答えない」と添える"""
        text = ask_final.final_text(self.got(questions=["範囲の外の cli.py を変えてよいか\n（R4）"]), [], RUN)
        self.assertIn("  > 範囲の外の cli.py を変えてよいか\n  > （R4）", text)
        self.assertIn("この承認ノードの答えはこの問いに答えない", text)
        self.assertNotIn("- 問い: ", text)

    def test_final_text_sections_match_the_original(self):
        """L-W34: 例で試していない単位・同じ run で直した案の項目（AMEND_HEAD）・持ち越した単位（split_line）・取り込むと消える
        ファイル・残りの件数（独立の目が通さなかった目と結果が無い目）と、clean・レンズ・仕組みの異常の行（修正の diff の隣の控え。fixbeside.always_rows）を並べる"""
        got = self.got(unproven=["u1: 例が無い"], amend=["案の項目 1: 直した——人が承認した"],
                       split="修正の段は 1 単位（u1）を受け、1 単位（u2）を止めて持ち越した", deleted=["old.py"],
                       always=["clean が消したファイル（fix）: 0 本", fixbeside.ANOMALY_LINE],
                       eyes={**self.got()["eyes"], "r3": {"status": "redesign-needed", "reason": ""}, "r4": None})
        text = ask_final.final_text(got, [], RUN)
        for want in (f"## {querytest.UNPROVEN_HEAD}（1 件）", "- u1: 例が無い", f"## {replan.AMEND_HEAD}（1 件）", "- 案の項目 1: 直した",
                     f"- {seal.DELETED_HEAD}: old.py", "独立の目が通さなかった目 1 件（R3: 作り直しが要る）・結果が無い目 1 件（R4）",
                     "- clean が消したファイル（fix）: 0 本", f"- {fixbeside.ANOMALY_LINE}"):
            self.assertIn(want, text)
        self.assertIn("1 単位（u2）を止めて持ち越した", text.splitlines()[0])
        self.assertEqual(replan.amend_lines(["1"], refixed=False), [f"案の項目 1: 直さずに諦めた: {replan.NOT_RUN_WHY}"])
        approved = {"decision": "continue", "text": "", "asked": ["項目 2: 約束の欄が変わった（allowed_paths）"]}
        self.assertEqual(replan.amend_lines(["2", "3"], refixed=True, answer=approved),
                         ["案の項目 2: 直した——人が承認した", "案の項目 3: 直した——聞かずに通した（手段の欄だけ）"])


class AskFinalDeliverCase(unittest.TestCase):
    """#751: 出口の語 pr の run の最後の承認ノードの文は、承認すると積んで push し PR を作る事と、push 先と向け先の枝を出す"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        origin = self.tmp / "origin.git"
        git(self.tmp, "init", "-q", "--bare", "-b", "main", str(origin))
        self.main = self.tmp / "main"
        git(self.tmp, "clone", "-q", str(origin), str(self.main))
        git(self.main, "commit", "-q", "--allow-empty", "-m", "seed")
        git(self.main, "push", "-q", "origin", "main")
        self.run_tree = self.tmp / "run"
        git(self.main, "worktree", "add", "-q", "-b", "archon/task-run", str(self.run_tree))

    def text(self, deliver: str, tree: pathlib.Path) -> str:
        with contextlib.chdir(tree):
            got = final_got(pr_branches=ask_final.pr_branches({"inputs": {"deliver": deliver}}))
        return ask_final.final_text(got, [], RUN)

    def test_pr_run_names_the_push_and_target_branches(self):
        lines = self.text("pr", self.run_tree).splitlines()
        row = ("- 承認すると（出口 deliver=pr）: 報告の前に run の枝 archon/task-run へ commit を積んで push し、main へ向けた PR を"
               "作る（merge はしない）。止めれば対象の repo に何も書かない")
        self.assertIn(row, lines)
        self.assertLess(lines.index(row), lines.index("答え方（人が決める承認ノード。依頼者に聞いて、その言葉で答える）:"))

    def test_pr_run_that_would_stop_before_the_commit_says_why(self):
        text = self.text("pr", self.main)
        self.assertIn("- 承認すると（出口 deliver=pr）: run の枝へ commit を積んで push し PR を作るはずだが、今の作業ツリーでは積む前に"
                      "止まる（本体の作業ツリーでは commit しない", text)
        self.assertIn("。止めれば対象の repo に何も書かない", text)

    def test_placing_run_says_nothing_of_a_pr(self):
        self.assertIsNone(ask_final.pr_branches({"inputs": {"deliver": ""}}))
        self.assertIsNone(ask_final.pr_branches(None))
        self.assertNotIn("出口 deliver", self.text("", self.run_tree))


class AskFinalReadsCase(Artifacts):
    """最後の関所が指し札の先から読む物: 判定の保留の問い（judgment.json）と直した後の実測（structure-after.json）"""

    def place(self, rel, doc):
        path = self.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return {"type": "archon_artifact", "run_id": RUN, "path": rel}

    def judgment(self, questions, units=("u1",)):
        return self.place("judge/judgment.json", {"units": [{"key": k} for k in units], "questions": questions})

    def stage(self, diff: dict) -> dict:
        """diff のポインタの置き場から、fix の返す節が組む段の控えの欄（fixbeside.returned）を今の置き場で組んだ段"""
        folder = (self.artifacts / diff["path"]).parent
        got = fixbeside.returned(folder, lambda path: boundary.pointer(path.relative_to(self.artifacts).as_posix()))
        return fixbeside.stage({"diff": diff, **got})

    def held(self, questions, *, answers=(), before_fix=None, asked=(), units=("u1",), ties=None, materials=None, notes=()):
        start_ptr = self.place("start.json", {"answers": list(answers)})
        before_fix = {**before_fix, "asked": list(asked)} if isinstance(before_fix, dict) else before_fix
        mats = None if materials is None else self.place("judge/materials.json", materials)
        tied = None if ties is None else self.place("judge-first/answer-ties.json", {"rounds": {"1": ties}})
        b, unread = ask_final.ledger(self.judgment(questions, units), ask_final.start_doc(start_ptr)[0], before_fix, tied, mats)
        self.assertEqual(unread, list(notes))
        return gatemarks.held_lines(b)

    FORK = {"key": "q1", "kind": "fork", "status": "held", "origin": "u1", "options": ["a", "b"], "reason": "割れる"}

    @staticmethod
    def null_env(**kw) -> dict:
        """ask-final の with: の鍵の全部を "null"（飛ばされた節）にした環境に、kw の入力を JSON の字（字はそのまま）で重ねた物"""
        env = {f"INPUTS_{name.upper()}": "null" for name in line_nodes()["ask-final"]["with"]}
        env.update({f"INPUTS_{key.upper()}": value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                    for key, value in kw.items()})
        return env

    def test_replan_stop_line_names_the_gate_the_line_gives(self):
        """案の直しの承認で止めた答えの行は、承認ノードの名を線の with: の replan_gate から受けて描く（lib は名を持たない）。ask-final の
        replan_gate は answer-replan の place と同じ字"""
        nodes = line_nodes()
        self.assertEqual(nodes["ask-final"]["with"].get("replan_gate"), nodes["answer-replan"]["with"]["place"])
        stop = {"decision": "stop", "text": "範囲が違う", "asked": []}
        env = self.null_env(replan_items=["5"], refixed=False, replan_answer=stop, replan_gate=nodes["answer-replan"]["with"]["place"])
        with mock.patch.dict(os.environ, env):
            got = ask_final.got_of_env()
        self.assertEqual(got["amend"], ["案の項目 5: 直さずに諦めた: 人が承認ノード gate-replan で run を止めた: 範囲が違う"])
        with mock.patch.dict(os.environ, {**env, "INPUTS_REPLAN_GATE": "null"}):
            self.assertEqual(ask_final.got_of_env()["amend"],
                             ["案の項目 5: 直さずに諦めた: 人が承認ノードで run を止めた: 範囲が違う"])

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
        """L-G34: 依頼の answers は key か出どころの字の一致で 1 つの問いだけに当たる時に答えに数える（gatemarks.binds の 1 つの式）。
        判定の結び（1 回目の判定の出力の欄 answer_ties。再審の後も 1 回目の物を指し、線は judged から渡す）と測れていない素材の名（今の判定の出力の欄 materials）
        も読み、結びの宛て先が今の（再審の）問いに無ければ字の一致に落として 1 行添える"""
        self.assertEqual(self.held([self.FORK], answers=[{"question": "q1", "text": "a"}]), [])
        self.assertEqual(self.held([self.FORK], answers=[{"question": "u1", "text": "a"}]), [])
        both = [self.FORK, {**self.FORK, "key": "q2"}]
        self.assertEqual(len(self.held(both, answers=[{"question": "u1", "text": "a"}])), 2, "2 つの問いに当たる答えはどれにも答えない")
        loose = [{"question": "どちらでもよい", "text": "a"}]
        self.assertEqual(len(self.held([self.FORK], answers=loose)), 1)
        self.assertEqual(self.held([self.FORK], answers=loose, ties=[{"answer": "どちらでもよい", "to": "q1"}]), [])
        lost = "判定の結びの宛て先 q-gone が今の問いにも単位にも無い（字の一致で当てた）: 依頼の答え どちらでもよい"
        self.assertEqual(len(self.held([self.FORK], answers=loose, ties=[{"answer": "どちらでもよい", "to": "q-gone"}], notes=[lost])), 1)
        field = {**self.FORK, "key": "parallel_pr: 重なり", "kind": "field", "status": "escalate", "origin": ""}
        self.assertEqual(self.held([field], answers=[{"question": "parallel_pr", "text": "a"}],
                                   materials={"parallel_pr": {"status": "not_run"}}), [])
        for node in ("ask-final", "eyes", "redepth"):   # 目は無人の run が採った推しを同じ台帳の読みで R4 の記録された方針に足す
            self.assertEqual(line_nodes()[node]["with"]["answer_ties"], "$judged.output.answer_ties", node)
            self.assertEqual(line_nodes()[node]["with"]["materials"], "$judged.output.materials", node)

    def test_answered_unit_missing_from_the_judgment_is_said(self):
        got = self.held([self.FORK], answers=[{"question": "q1", "text": "a"}], units=())
        self.assertEqual(got, [gatemarks.unreturned_line("q1", "u1")])

    def test_unreadable_judgment_is_said(self):
        b, unread = ask_final.ledger({"type": "archon_artifact", "run_id": "another", "path": "x.json"}, None, None)
        self.assertIsNone(b)
        self.assertIn("判定の問いの控えか始めの記録を読めない", unread[0])
        self.assertEqual(ask_final.ledger(None, None, None), (None, []))

    def test_fence_rows_come_from_the_structure_after(self):
        rise = {"concept": "止め", "what": "語", "path": "a.py", "before": 1, "after": 2}
        ptr = self.place("eyes/structure-after.json", {"status": "ok", "reason": "", "deviations": [],
                                                       "after": {"tables": ["t"], "fence_up": [rise]}})
        rows, _, unread = ask_final.after_rows(ptr)
        self.assertEqual(([row["where"] for row in rows], unread), (["a.py"], ""))
        self.assertEqual(ask_final.after_rows(None), ([], [ask_final.NO_AFTER], ""))

    def test_unreadable_structure_after_is_said(self):
        rows, _, unread = ask_final.after_rows({"type": "archon_artifact", "run_id": "another", "path": "eyes/structure-after.json"})
        self.assertEqual(rows, [])
        self.assertIn("ポインタを読めない", unread)
        rows, _, unread = ask_final.after_rows(self.place("eyes/structure-after.json", {"status": "?"}))
        self.assertEqual(rows, [])
        self.assertIn("控え structure-after.json を読めない", unread)

    def test_null_structure_after_is_said(self):
        """L-W54: 直した後の構造の実測が無い（eyes の structure_after が null。実測の節が落ちた）時は、線を止めずに、そう言う 1 行を
        関所の文に出す。実測の一部が落ちた（status: failed）時は数の 1 文に理由を添える"""
        fenced, after, unread = ask_final.after_rows(None)
        self.assertEqual((fenced, after, unread), ([], [ask_final.NO_AFTER], ""))
        self.assertIn(f"- {ask_final.NO_AFTER}", ask_final.final_text(final_got(after=after), [], RUN))
        ptr = self.place("eyes/structure-after.json", {"status": "failed", "reason": "版が引けない", "deviations": [], "after": {}})
        self.assertIn("（実測の一部が落ちた: 版が引けない）", ask_final.after_rows(ptr)[1][0])

    def test_final_gate_shows_the_after_counts(self):
        """E73: 直した後の実測の数の 1 文（structmark.after_counts）・増えた所・新しい名を最後の関所に並べ、柵の増えは開ける理由にする"""
        rise = {"concept": "止め", "what": "語", "path": "a.py", "before": 1, "after": 2}
        ptr = self.place("eyes/structure-after.json", {"status": "ok", "reason": "", "deviations": [],
                                                       "after": {"tables": ["t"], "fence_up": [rise], "changed": ["a.py"],
                                                                 "new_names": [{"name": "n", "sites": 1}]}})
        fenced, after, _ = ask_final.after_rows(ptr)
        got = final_got(fenced=fenced, after=after)
        text = ask_final.final_text(got, ask_final.final_needs(got), RUN)
        self.assertIn("- 直しの後の実測（直しの前の版と今の作業ツリーの差分。機械が測った）: 変わったファイル 1 本", text)
        self.assertIn("  - 新しい名 n（現れる所 1 か所）", text)
        self.assertIn("考えの住処の柵の数が増えた（1 件", text.splitlines()[0])

    def test_failed_structure_is_marked(self):
        """L-W09: 計画の構造の目が落ちた周（計画の返り structure の先の structure-state.json が status: failed）は、計画を止めずに
        進め、最後の関所に「構造のブロック: 構造の目の行なしで計画した（理由: …）」を出す"""
        ptr = self.place("plan/structure/structure-state.json", {"status": "failed", "reason": "構造の目の役が落ちた",
                                                                  "design_file": "", "wall_s": 0})
        missing = ask_final.structure_missing(ptr)
        self.assertEqual(missing, "構造の目の行なしで計画した（理由: 構造の目の役が落ちた）")
        self.assertIn(f"- 構造のサブグラフ: {missing}", ask_final.final_text(final_got(structure_missing=missing), [], RUN))
        ok = self.place("plan/structure/structure-state.json", {"status": "ok", "reason": "", "design_file": "", "wall_s": 0})
        self.assertEqual(ask_final.structure_missing(ok), "")
        self.assertEqual(line_nodes()["ask-final"]["with"]["structure"], {"from": "$fix-in.output.structure", "if_skipped": None})

    def test_failed_structure_reaches_the_gate_text_from_the_with_keys(self):
        """L-W09: 計画の構造の目が落ちた周は、ノード ask-final が with: の structure（$plan-rounds.output.structure）の先を読み、開いた
        最後の承認ノードの文に「構造のブロック: …」の行が届く（with: の鍵を読むかだけでなく、文まで）"""
        ptr = self.place("plan/structure/structure-state.json", {"status": "failed", "reason": "構造の目の役が落ちた",
                                                                  "design_file": "", "wall_s": 0})
        env = self.null_env(structure=ptr, final_gate="always", unattended="false", tests={"ok": True, "green": True}, seal={"ok": True})
        with mock.patch.dict(os.environ, env):
            out = ask_final.ask(**ask_final.from_env())
        self.assertTrue(out["open"], out)
        self.assertIn("- 構造のサブグラフ: 構造の目の行なしで計画した（理由: 構造の目の役が落ちた）", out["text"])

    def test_partly_started_steps_reach_the_gate_text_from_the_with_keys(self):
        """#514: 最後の関所は with: の tests（$test-gate-final.output のまるごと）の ran_steps を JSON の形で読み、起こした段と起こせなかった段を
        名指し、走っていないと言わない（with: の鍵を読むかだけでなく、文まで）"""
        tests = {"ran_steps": {"ran": ["unit"], "unran": ["lint"]}, "red_cause": "incomplete", "by": "engine", "ok": False, "green": False}
        env = self.null_env(final_gate="always", unattended="false", tests=tests, seal={"ok": True})
        with mock.patch.dict(os.environ, env):
            out = ask_final.ask(**ask_final.from_env())
        self.assertIn(green_cert.PARTLY_RAN, out["text"])
        self.assertIn("unit", out["text"])
        self.assertIn("lint", out["text"])
        self.assertNotIn(green_cert.NOT_RAN, out["text"])

    def test_fix_beside_files_reach_the_final_gate(self):
        """F013・F041・F312・F329・L-W20・L-W21（S03・S28・S29）: 最後の関所は修正の段ごとの返りの控えの欄（fixed の records。
        1 回目と 2 度目の修正の両方）を読み、申告と合わない単位・回さなかった試験・確かめずに受けた回・穴の名札と手直しの結果・
        clean とレンズを並べる。修正役が人に回した物は fixed の handoffs から並べる。無い控えは欄の名で訳にする"""
        import fixboard
        diffs = []
        for name in ("fix", "refix-run"):
            diffs.append(self.place(f"fix/{name}/fix.diff", {}))
            folder = self.artifacts / "fix" / name
            fixbeside.write(folder, [{"closure": [{"unit_key": f"u-{name}", "closed": False, "discrepancies": ["合わない"]}]}])
            fixboard.write_json(folder / fixboard.ACCEPT_TRACE_FILE, [
                {"op": fixbeside.TESTS_OP, "ci_left": [f"t_{name}.py"], "final_left": [], "final_far": [], "pass": "first", "attempt": 1},
                {"op": fixbeside.SKIPPED_OP, "why": ["実行器が無い"]}])
            fixboard.write_json(folder / fixboard.ALLOWED_TESTS_FILE, [])
            fixboard.write_json(folder / "fix-removed.json", {"removed": ["build/x.o"]})
        fixboard.lens_collector(self.artifacts / "fix" / "fix", True, "")
        fixboard.write_json(self.artifacts / "fix" / "fix" / fixbeside.DELTA_HOLES_FILE, {
            "ties": {"1": [{"key": "穴1", "branches": ["item:1"], "via": ["path"], "held": ""}]},
            "handled": {"1": [{"key": "穴1", "handled": "fixed", "how": "直した"}]}})
        got = ask_final.fix_beside([self.stage(d) for d in diffs])
        self.assertIn("  - 穴1: 項目 1", got["branch_rows"])
        self.assertEqual([x.split("（")[0] for x in got["closure"]], ["u-fix: 閉じていない", "u-refix-run: 閉じていない"])
        self.assertIn("  - t_refix-run.py", got["tests_left"])
        self.assertEqual(got["gates"], ["事後の関門の束: 受け付け 2 回が受け入れのテストの赤緑を確かめずに通した（理由: 実行器が無い）"])
        self.assertIn("clean が消したファイル（refix-run）: 1 本", got["always"])
        self.assertEqual(got["always"][-1], fixbeside.ANOMALY_LINE)
        self.assertEqual(got["beside_unread"], ["修正の控え lenses が無い"])
        self.assertEqual(line_nodes()["ask-final"]["with"]["fix_records"], "$fixed.output.records")
        self.assertEqual(line_nodes()["ask-final"]["with"]["handoffs"], "$fixed.output.handoffs")
        handoffs = ["u-fix: 壊すと分かって通した——古い呼び手が壊れる"]
        text = ask_final.final_text(final_got(handoffs=handoffs, **got), [], RUN)
        for want in ("- 修正の受け付けが手元で回さなかった試験（2 件", "- 事後の関門の束: 受け付け 2 回", "- clean が消したファイル（fix）: 1 本",
                     "  - build/x.o", "u-fix: 壊すと分かって通した——古い呼び手が壊れる", f"- {fixbeside.branch_head(1)}: 1 件（",
                     "  - 穴1: 直した（fixed）——直した", f"## {ask_final.BESIDE_UNREAD}（1 件"):
            self.assertIn(want, text)

    def test_many_removed_files_keep_the_answer_lines(self):
        """clean が消したファイルが 20,000 本でも、最後の承認ノードの文は本数に依らず短く、末尾の答え方の行まで在る。件数の行と
        全件の置き場（fix-removed.json のパス）を出し、全部のパスは並べない"""
        import fixboard
        diff = self.place("fix/fix/fix.diff", {})
        folder = self.artifacts / "fix" / "fix"
        fixbeside.write(folder, [{}])
        names = [f"cache/a/{i}.bin" if i % 2 else f"dist/b/{i}.o" for i in range(20000)]
        fixboard.write_json(folder / "fix-removed.json", {"removed": names})
        got = ask_final.fix_beside([self.stage(diff)])
        text = ask_final.final_text(final_got(**got), [], RUN)
        lines = text.splitlines()
        self.assertLessEqual(len(lines), 120, text[:3000])
        self.assertIn("- clean が消したファイル（fix）: 20000 本", lines)
        self.assertIn("  - " + names[0], lines)
        self.assertNotIn("  - " + names[100], lines)
        self.assertIn(f"（全件: {folder / 'fix-removed.json'}）", text)
        self.assertIn("  - 上位のフォルダごとの本数:", lines)
        self.assertIn("    - cache: 10000 本", lines)
        self.assertIn(f"- 報告へ進める: {answer.line(RUN, 'continue', '<一言>')}（一言は {ask_final.RECORD} に残る）", lines)
        self.assertIn(f"- 止める: {answer.line(RUN, 'stop', '<理由>')}（報告は出る）", lines)

    def test_unreadable_fix_beside_opens_the_gate(self):
        """errors F1: 修正の段の控えを読めない時は、人に回した物と数え直しの食い違いを数えられないので、開き方に依らず関所を開け、
        無人の run は開かずに止める（黙って merge-apply へ進めない）"""
        got = final_got(beside_unread=["修正の控え x/closure.json を組めなかった（e）"])
        self.assertIn((f"{ask_final.BESIDE_UNREAD}（1 件。人に回した物・数え直しの食い違いを数えられない）", True), ask_final.needs(got))
        self.assertTrue(ask_final.ask(got, mode="when_needed", unattended=False, run_id=RUN)["open"])
        self.assertEqual(ask_final.ask(got, mode="when_needed", unattended=True, run_id=RUN)["stop_reason"], stopby.NEEDS_HUMAN)

    def test_final_gate_lists_the_r2_premise_inputs(self):
        """E45・E66・E37（S12）: 独立の目の返り notes（premise-inputs.json）の先から、R2 の行の下に「渡されていない」と書いた文・
        そのうち渡していた物（claims_given）・2 つの役に渡した前提と渡していない物・独立設計の後の答え（元 line_edge._r2_inputs）を、
        修正前の関所で通した行に返り r4_passes の先の「人が通したので R4 で聞き直さなかった行」を、前提の検算の行の下に返り
        premise_reply の先の偽と分かった仮定の問いと次の run の制約に足す実測を並べる。notes が null なら控えが無いと言う"""
        import eyeverdict
        notes = self.place(f"eyes/{eyeverdict.PREMISE_INPUTS}", {
            "design": {"given": [{"kind": "制約", "what": "上限 10"}], "withheld": [{"kind": "人の答え", "what": "x", "why": "後に来た"}]},
            "compare": {"given": [], "claims_given": [{"claim": "上限", "kind": "制約", "what": "上限 10"}], "after_design": ["continue"]},
            "claims": ["上限が渡されていない"]})
        passes = self.place("eyes/r4-gate-passes.json", [{"node": gatemarks.R4_GATE_NODE, "round": 1, "by": gatemarks.PASSED_BY_HUMAN,
                                                          "item": "R4 が BASE から消えたと見た能力: 古い入口",
                                                          "passed_at": {"node": gatemarks.GATE_NODE, "round": 1}}])
        premise = self.place("eyes/premise-check.json", {"key": "上限を持つか", "verdict": "resolved", "reason": "在る", "resolution": "10",
                                                         "facts_to_add": ["上限は 10"]})
        got = ask_final.eye_notes({"notes": notes, "r4_passes": passes, "premise_reply": premise})
        self.assertEqual(got["notes_unread"], [])
        self.assertEqual(len(got["eye_passes"]), 1)
        eyes = {**final_got()["eyes"], "premise_check": {"verdict": "resolved", "reason": "在る"}}
        text = ask_final.final_text(final_got(r2_inputs=got["r2_inputs"], premise_facts=got["premise_facts"], eyes=eyes,
                                              passes=got["eye_passes"]), [], RUN)
        for want in ("    - 独立の設計と比べる目が渡されていないと書いた（R2）: 上限が渡されていない",
                     "    - 独立の設計と比べる目が渡されていないと書いたが、渡していた（R2）: 上限 ← 制約: 上限 10",
                     "    - 独立設計の後に来た人の答え（独立の設計と差分を比べる役にだけ渡った）: continue",
                     "    - 独立の設計を作る役に渡した前提の入力（design）: 制約: 上限 10", "    - run に在ったが渡していない: 人の答え: x（後に来た）",
                     "    - 次の run の制約に足す実測: 上限は 10", "R4 が BASE から消えたと見た能力: 古い入口"):
            self.assertIn(want, text)
        self.assertLess(text.index("（R2）: 上限が渡されていない"), text.index("R3"))
        self.assertEqual(ask_final.eye_notes(dict.fromkeys(("notes", "r4_passes", "premise_reply")))["r2_inputs"],
                         ["独立の設計と比べる目に渡した入力の控えが無い（独立の目の出力 notes が null）"])
        self.assertEqual(line_nodes()["ask-final"]["with"]["eyes"], {"from": "$eyes.output", "if_skipped": None})
        self.assertEqual(line_nodes()["eyes-out"]["with"]["got"], "$eyes.output")
        self.assertLessEqual({"notes", "r4_passes", "premise_reply"}, set(ask_final.EYES))
        unread = ask_final.eye_notes({"notes": notes, "r4_passes": None, "premise_reply": None})["notes_unread"]
        self.assertTrue(unread and "ポインタを読めない" in unread[0], unread)

    def test_allowed_tests_come_from_beside_both_diffs(self):
        """許したテストの変更は fix と refix-run の段の欄 allowed_tests の先を読み、許しの id と出どころつきで並べる（重ねない）。
        開き方に依らず関所を開ける"""
        row = {"path": "tests/test_a.py", "permit": "plan-1", "source": "plan"}
        fix = self.place("fix/fix/fix.diff", "")
        self.place("fix/fix/allowed-tests.json", [row])
        refix = self.place("fix/refix/fix.diff", "")
        self.place("fix/refix/allowed-tests.json", [row, {"path": "tests/test_b.py", "permit": "r-2", "source": "ruling"}])
        rows = ask_final.fix_beside([self.stage(fix), self.stage(refix)])["allowed_tests"]
        self.assertEqual([r["path"] for r in rows], ["tests/test_a.py", "tests/test_b.py"])
        self.assertEqual(ask_final.fix_beside([self.stage(fix)])["allowed_tests"], [row])
        got = final_got(allowed_tests=rows)
        text = ask_final.final_text(got, ask_final.final_needs(got), RUN)
        self.assertIn(f"## {ask_final.ALLOWED_TESTS_HEAD}（2 件", text)
        self.assertIn("- tests/test_b.py（許し r-2・ruling）", text)
        self.assertTrue(any(must for _, must in ask_final.needs(got)))

    def test_unreadable_allowed_tests_is_said(self):
        """collect は落ちた道でも [] を置くので、欄が null・先が形の違う許したテストの変更の訳は読めなかった訳を返す（黙って空にしない）"""
        diff = self.place("fix/fix/fix.diff", "")
        got = ask_final.fix_beside([self.stage(diff)])
        self.assertEqual(got["allowed_tests"], [])
        self.assertIn("修正の控え allowed_tests が無い", got["beside_unread"])
        self.place("fix/fix/allowed-tests.json", {"path": "x"})
        self.assertTrue(any("行の配列でない" in x for x in ask_final.fix_beside([self.stage(diff)])["beside_unread"]))

    def test_fix_beside_reads_the_stage_ports_not_the_diff_folder(self):
        """#681: 最後の承認ノードは段の欄のポインタの先を読み、diff の隣を名で開かない（欄が別の置き場を指せばそちらを読む）"""
        diff = self.place("fix/fix/fix.diff", "")
        self.place("fix/fix/allowed-tests.json", [{"path": "tests/beside.py", "permit": "p", "source": "plan"}])
        moved = self.place("elsewhere/allowed.json", [{"path": "tests/ported.py", "permit": "p", "source": "plan"}])
        got = ask_final.fix_beside([{**self.stage(diff), "allowed_tests": moved}])
        self.assertEqual([r["path"] for r in got["allowed_tests"]], ["tests/ported.py"])

    def test_unresolvable_stage_port_is_named_by_its_field(self):
        """#681: 戻せないポインタ（ほかの run の物）の欄と dict でない段は、欄の名と訳で読めなかった行にする（黙って空にしない）"""
        diff = self.place("fix/fix/fix.diff", "")
        other = {**self.stage(diff), "closure": {"type": "archon_artifact", "run_id": "other", "path": "fix/fix/closure.json"}}
        got = ask_final.fix_beside([other, "壊れた段"])
        self.assertTrue(any(x.startswith("修正の控え closure のポインタを読めない（") for x in got["beside_unread"]), got["beside_unread"])
        self.assertIn("修正の段の出力が dict でない", got["beside_unread"])

    def test_unread_is_shown_in_the_gate_text(self):
        text = ask_final.final_text(final_got(unread=["読めない訳"]), [], RUN)
        self.assertIn("- 読めない訳", text)


    def conflicts(self, rel, *decisions):
        """conflicts.json（conflict の形 {items}）に、裁定 decisions の行を 1 つずつ置いた指し札"""
        rows = [{"id": f"c{i}", "unit_key": f"u{i}", "between": ["stats.py:3", "test_stats.py:2"], "why_both_cannot_hold": "両方は立たない",
                 "which_is_right": "unknown", "kind": "needs_context",
                 "ruling": {"decision": d, "text": f"裁定の文 {i}（{d}）", "limits": []}} for i, d in enumerate(decisions, 1)]
        return self.place(f"{rel}/{conflict.FILE}", {"items": rows})

    def test_only_asked_conflict_rows_open_and_are_named(self):
        """L-W24: 申し出は人に回した行（ask_human と案の直しを諦めた行）だけを数え、文は conflict.human_lines の行（1 回目と 2 度目の
        修正の控えの両方）。直す裁定だけの控えは数えない。読めない控えは黙って 0 にせず訳を返す"""
        first = self.conflicts("fix/fix", "fix_code_as", "ask_human")
        second = self.conflicts("fix/refix-run", "fix_test_scope")
        rows, unread = ask_final.asked_conflicts([first, second])
        self.assertEqual((len(rows), unread), (1, []))
        self.assertTrue(rows[0].startswith("u2: 裁定の文 2（ask_human）（名指し stats.py:3, test_stats.py:2・種類 needs_context・"), rows[0])
        self.assertEqual(ask_final.asked_conflicts([second]), ([], []))
        gone = {"type": "archon_artifact", "run_id": RUN, "path": "fix/gone/conflicts.json"}
        rows, unread = ask_final.asked_conflicts([gone])
        self.assertEqual(rows, [])
        self.assertIn("fix/gone/conflicts.json", unread[0])

    def test_unread_hold_is_shown(self):
        """L-G31・P238: 台帳の key を拾えない「保留」（打ち間違いの key）は答えた扱いのまま、最後の関所の文に「読めなかった保留」として
        一言の断片と、答えたものとして推しで直す問いの key を並べる"""
        judgment = self.judgment([self.FORK])
        start = self.place("start.json", {"answers": []})
        b, _ = ask_final.ledger(judgment, ask_final.start_doc(start)[0], {"decision": "continue", "text": "保留: q-typo",
                                                                          "asked": [gatemarks.ask_text(self.FORK)]})
        rows = ask_final.ledger_rows(b)
        self.assertEqual(rows["held"], [])
        text = ask_final.final_text(final_got(**rows), [], RUN)
        line = next(x for x in text.splitlines() if "読めなかった保留" in x)
        self.assertIn("「保留: q-typo」", line)
        self.assertIn("答えたものとして推しで直す問い: q1", line)

    def test_final_text_lists_new_names_and_deviations(self):
        """L-W31: 直した後の実測（数・柵の増え・新しい名・修正案の外れの訳。structmark.after_lines）を並べる"""
        rise = {"concept": "止め", "what": "語", "path": "a.py", "before": 1, "after": 2}
        ptr = self.place("eyes/structure-after.json", {"status": "ok", "reason": "", "deviations": [{"item": 1, "answer": "外れた", "why": "訳"}],
                                                       "after": {"tables": ["t"], "fence_up": [rise], "new_names": [{"name": "mean_or_zero", "sites": 2}]}})
        fenced, after, unread = ask_final.after_rows(ptr)
        text = ask_final.final_text(final_got(fenced=fenced, after=after), [], RUN)
        self.assertEqual(unread, "")
        self.assertIn("  - 新しい名 mean_or_zero（現れる所 2 か所）", text)
        self.assertIn("を知る場所が a.py で増えた", text)
        self.assertIn("  - 修正案の", text)

    def test_passed_items_and_converge_rounds_are_listed(self):
        """L-W32: 修正前の関所で通した項目（gatemarks.pass_lines。事前審査の返り gate_passes の先）と事前審査の往復（返り gate の先の
        converge）を最後の関所の文に並べる。案の直しの事前審査の物も足す"""
        row = {"node": gatemarks.GATE_NODE, "round": 1, "by": gatemarks.PASSED_BY, "item": "修正案 1 が狭める能力: x", "decided_by": "docs/adr.md:3"}
        review = (self.place("plan-review/pass-1/review.json", {}), self.place("plan-review/pass-1/gate-passes.json", [row]),
                  self.place("plan-review/pass-1/gate.json", {"items": [], "converge": ["壁打ち: 2 往復で clean", "  - 往復 1: …"]}))
        passes, rounds, unread = ask_final.review_rows((review, (None, None, None)))
        self.assertEqual((passes, rounds, unread), ([gatemarks.pass_lines([row])[0]], ["壁打ち: 2 往復で clean", "  - 往復 1: …"], []))
        text = ask_final.final_text(final_got(passes=passes, converge=rounds), [], RUN)
        self.assertIn(f"  - {gatemarks.named(gatemarks.GATE_NODE)}（周 1）で決め手が在るので聞かずに通した: 修正案 1 が狭める能力: x", text)
        self.assertIn("- 壁打ち: 2 往復で clean\n  - 往復 1: …", text)
        gone = {"type": "archon_artifact", "run_id": RUN, "path": "gone/gate-passes.json"}
        _, _, unread = ask_final.review_rows((({**gone, "path": "gone/review.json"}, gone, {**gone, "path": "gone/gate.json"}),))
        self.assertIn("事前審査の隣の控え（通した行・往復）を読めない", unread[0])

    def test_review_fields_missing_from_a_review_that_ran_is_said(self):
        """事前審査が走った（出力の欄 review が在る）のに欄 gate_passes・gate がどちらも無い（欄の無い版の run を再開した時）は、黙って
        飛ばさず読めなかった訳の 1 行にする。計画の往復の物も案の直しの事前審査の物も同じ。review も null（飛ばされた）なら黙って飛ばす"""
        ran = self.place("plan-review/pass-1/review.json", {})
        for env in (self.null_env(review=ran), self.null_env(replan_review=ran)):
            with mock.patch.dict(os.environ, env):
                got = ask_final.got_of_env()
            self.assertIn(ask_final.REVIEW_FIELDS_MISSING, got["unread"])
            self.assertIn(ask_final.REVIEW_FIELDS_MISSING, ask_final.final_text(got, [], RUN))
        self.assertEqual(ask_final.review_rows(((ran, None, None), (None, None, None))), ([], [], [ask_final.REVIEW_FIELDS_MISSING]))

    def test_skipped_review_is_not_said_missing(self):
        """直す物の無い周（no-fix）と直す義務が 0 件の周（nothing_owed）は、判定が在っても計画の出力の ready が偽で事前審査が飛ぶので、
        事前審査の出力の欄はどれも null で来る。欄の無い版の行を出さない"""
        judgment = self.place("judge/judgment.json", {})
        with mock.patch.dict(os.environ, self.null_env(first_judgment=judgment, judgment=judgment)):
            got = ask_final.got_of_env()
        self.assertNotIn(ask_final.REVIEW_FIELDS_MISSING, got["unread"])
        self.assertNotIn(ask_final.REVIEW_FIELDS_MISSING, ask_final.final_text(got, [], RUN))
        self.assertEqual(ask_final.review_rows(((None, None, None),)), ([], [], []))

    def test_final_gate_lists_gate_passes(self):
        """P255: 事前審査の返り gate_passes の先に 1 行在る時、最後の関所の文にその行が在る（元 works/tests/test_plan_gate.py:397・
        :515・:575 の final_text の断言の、決め手で通した行の分）"""
        row = {"node": gatemarks.GATE_NODE, "round": 1, "by": gatemarks.PASSED_BY, "item": "決め手で通した行", "decided_by": "x.md:1"}
        passes, _, _ = ask_final.review_rows(((self.place("plan-review/pass-1/review.json", {}),
                                                self.place("plan-review/pass-1/gate-passes.json", [row]),
                                                self.place("plan-review/pass-1/gate.json", {"items": [], "converge": []})),))
        self.assertIn("決め手で通した行（決め手: x.md:1）", ask_final.final_text(final_got(passes=passes), [], RUN))

    def test_final_text_lists_suites_baseline_and_left_tests(self):
        """L-W28・T35: 最後のテストの返りの欄（with: の tests＝試験の関門の返りまるごとの by・suites_line・log・baseline_line・reason）から、
        一式・修正前のテスト・ログ・認証しなかった訳を字のまま出し、作業ツリーと並べる（証拠の文は開かない）。関門が返さなかった
        （飛ばされた節の null）時はその旨と「取れない」。返す節の中の誤り（by の空の字）は返らなかった形と分ける。手元で回さなかった
        試験（ci_left・final_left・final_far）は修正の返りに控えが無い（F013。部分 D2）"""
        self.assertEqual(line_nodes()["ask-final"]["with"]["tests"], {"from": "$test-gate-final.output", "if_skipped": None})
        returned = {"by": "role_needed", "suites_line": "一式 X", "log": "test-gate/final/logs/checks.log",
                    "baseline_line": "修正前のテスト: 緑（元の結末）", "reason": "任せ先の自己申告の緑"}
        with mock.patch.dict(os.environ, self.null_env(tests=returned)):
            got = ask_final.got_of_env()["tests"]
        text = ask_final.final_text(final_got(tests=got, tests_ok=False), [], RUN)
        for want in ("- テストの一式: role_needed・一式 X", "- 修正前のテスト: 緑（元の結末）", "- ログ: test-gate/final/logs/checks.log",
                     "- 走れなかった・認証しなかった理由: 任せ先の自己申告の緑", "- run の作業ツリー: /tmp/tree"):
            self.assertIn(want, text)
        with mock.patch.dict(os.environ, self.null_env(tests="null")):
            got = ask_final.got_of_env()["tests"]
        missing = ask_final.declared_checks.GATE_MISSING
        self.assertEqual((got["suites"], got["log"], got["baseline"], got["reason"]), (missing, missing, f"修正前のテスト: {missing}", ""))
        self.assertIn(f"- {got['unread']}", ask_final.final_text(final_got(tests=got, tests_ok=False), [], RUN))
        self.assertTrue(got["unread"])
        with mock.patch.dict(os.environ, self.null_env(tests={k: "" for k in returned})):
            self.assertEqual(ask_final.got_of_env()["tests"]["unread"], "")

    def test_final_tests_read_the_whole_gate_output(self):
        """最後のテストの欄は INPUTS_TESTS（試験の関門の返りまるごと）から読む。by が空の字なら返った形（unread は空）、tests が null なら
        『試験の関門が返さなかった』の unread。ok・green・red_cause・ran_steps も同じ値から読む"""
        gate = {"mode": "final", "ok": True, "green": True, "red_cause": "", "ran_steps": {"ran": ["unit"], "unran": []}, "baseline": None,
                "fingerprint": "f", "test_outcomes": None, "evidence": None, "by": "", "suites_line": "", "log": "", "baseline_line": "",
                "reason": ""}
        with mock.patch.dict(os.environ, self.null_env(tests=gate)):
            got = ask_final.got_of_env()
        self.assertEqual((got["tests"]["unread"], got["tests"]["by"]), ("", ""))
        self.assertEqual((got["tests_ok"], got["green"], got["red_cause"], got["ran_steps"]), (True, True, "", gate["ran_steps"]))
        with mock.patch.dict(os.environ, self.null_env(tests="null")):
            got = ask_final.got_of_env()
        self.assertIn("試験の関門が返さなかった", got["tests"]["unread"])
        self.assertEqual((got["tests_ok"], got["green"], got["red_cause"], got["ran_steps"]), (False, False, "", None))

    def test_skipped_seal_falls_to_the_script_defaults(self):
        """封じの節が飛んだ（seal が null）時、最後の関所は sealed を真、seal_reason と hash を空の字、protected_hits を空の並びとして
        読む（YAML の if_skipped にあった既定と同じ）。封じる差分も無い"""
        with mock.patch.dict(os.environ, self.null_env()):
            got = ask_final.got_of_env()
        self.assertEqual((got["sealed"], got["seal_reason"], got["hash"], got["protected_hits"], got["deleted"]), (True, "", "", [], []))
        self.assertEqual(ask_final.SEAL_SKIPPED, {"ok": True, "reason": "", "hash": "", "protected_hits": [], "protected_count": 0, "diff": None})
        self.assertEqual(set(ask_final.SEAL_SKIPPED), set(ask_final.SEAL))

    def test_skipped_whole_outputs_stop_on_undeclared_names(self):
        """飛ばされた封じの既定も、宣言の外の名を .get で引くと黙って None にならず KeyError で止まる"""
        with self.assertRaises(KeyError):
            ask_final.SEAL_SKIPPED.get("fingerprint")

    def test_seal_without_hits_still_names_why_it_did_not_seal(self):
        """走った封じが protected_hits: null（merge の差分が空・中の誤りの返り）を返しても、最後の関所は落ちない。protected_hits を [] と
        読み、sealed 偽と封じなかった理由を出す"""
        seal = {"ok": False, "reason": "封じる差分が空", "hash": "", "protected_hits": None, "diff": None}
        with mock.patch.dict(os.environ, self.null_env(seal=seal)):
            got = ask_final.got_of_env()
        self.assertEqual((got["sealed"], got["seal_reason"], got["protected_hits"]), (False, "封じる差分が空", []))
        self.assertIn("差分を封じられなかった（封じる差分が空）", ask_final.final_needs(got))

    def test_seal_without_count_counts_the_hit_rows(self):
        """前の版の merge-seal の返り（protected_count が無い）を resume で受けても、件数は 0 件でなく当たった行の数で言う"""
        seal = {"ok": True, "reason": "", "hash": "h", "protected_hits": ["ci/a.yml（+1 −0）", "ci/b.yml（+1 −0）"], "diff": None}
        with mock.patch.dict(os.environ, self.null_env(seal=seal)):
            got = ask_final.got_of_env()
        self.assertEqual(got["protected_count"], 2)
        self.assertIn(f"{ask_final.PROTECTED_HEAD}（2 件。人の確かめが要る）", ask_final.final_needs(got))

    def test_deleted_files_named(self):
        """M38: 封じた差分の中で消えるファイルを、当てる前に SHOWN 件までは 1 本ずつ名指し（「取り込むと消えるファイル: <パス>」）、
        超える分は件数と封じた差分のパスで指す"""
        diff = ("diff --git a/old.py b/old.py\ndeleted file mode 100644\nindex 1..0\n--- a/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n"
                "diff --git a/keep.py b/keep.py\nindex 1..2 100644\n--- a/keep.py\n+++ b/keep.py\n@@ -1 +1 @@\n-a\n+b\n")
        ptr = self.place("merge/sealed.diff", {})
        (self.artifacts / "merge/sealed.diff").write_text(diff, encoding="utf-8")
        self.assertEqual(ask_final.deleted_files(ptr), (["old.py"], ""))
        self.assertIn(f"- {seal.DELETED_HEAD}: old.py", ask_final.final_text(final_got(deleted=["old.py"]), [], RUN))
        self.assertIn("封じた差分を読めない", ask_final.deleted_files({"type": "archon_artifact", "run_id": "x", "path": "d"})[1])

    def test_many_deleted_files_are_cut(self):
        """封じた差分が 20,000 本を消しても、最後の承認ノードの文は本数に依らず短く、末尾の答え方の行まで在る。with: の鍵（封じの返りまるごとの
        diff の指し札）から文まで本物で通し、先頭 SHOWN 件と、残りの件数と封じた差分の実のパスの 1 行だけを出す"""
        names = [f"gen/{i}.o" for i in range(20000)]
        ptr = self.place("merge/sealed.diff", {})
        (self.artifacts / "merge/sealed.diff").write_text(
            "".join(f"diff --git a/{n} b/{n}\ndeleted file mode 100644\n--- a/{n}\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n" for n in names), encoding="utf-8")
        env = self.null_env(final_gate="always", unattended="false", tests={"ok": True, "green": True}, seal={"ok": True, "diff": ptr})
        with mock.patch.dict(os.environ, env):
            out = ask_final.ask(**ask_final.from_env())
        text, lines = out["text"], out["text"].splitlines()
        self.assertTrue(out["open"], out)
        self.assertLessEqual(len(lines), 120, text[:3000])
        self.assertIn(f"- {seal.DELETED_HEAD}: {names[0]}", lines)
        self.assertNotIn(f"- {seal.DELETED_HEAD}: {names[100]}", lines)
        self.assertIn(f"- {seal.DELETED_HEAD}: ほか 19995 件（全件: {boundary.resolve(ptr)}）", lines)
        self.assertIn(f"- 報告へ進める: {answer.line(RUN, 'continue', '<一言>')}（一言は {ask_final.RECORD} に残る）", lines)
        self.assertIn(f"- 止める: {answer.line(RUN, 'stop', '<理由>')}（報告は出る）", lines)

    def test_many_protected_hits_are_cut(self):
        """守りのファイルに当たった物が 20,000 本でも、最後の承認ノードの文は本数に依らず短く、末尾の答え方の行まで在る。封じの返り
        （merge が protect.shown で切った行と全件の数 protected_count）から文まで通し、件数は全件の数で言う"""
        rows = protect.lines([{"path": f"gen/{i}.o", "id": "target:gen", "glob": "gen/**", "why": "生成物", "added": 0, "deleted": 1}
                              for i in range(20000)])
        whole = self.artifacts / "merge" / "protected-all.json"
        seal_out = {"ok": True, "protected_hits": protect.shown(rows, "protected_hits", whole), "protected_count": len(rows)}
        env = self.null_env(final_gate="always", unattended="false", tests={"ok": True, "green": True}, seal=seal_out)
        with mock.patch.dict(os.environ, env):
            out = ask_final.ask(**ask_final.from_env())
        text, lines = out["text"], out["text"].splitlines()
        self.assertTrue(out["open"], out)
        self.assertLessEqual(len(lines), 120, text[:3000])
        self.assertIn(f"{ask_final.PROTECTED_HEAD}（20000 件。人の確かめが要る）", lines[0])
        self.assertTrue(any(x.startswith(f"## {ask_final.PROTECTED_HEAD}（20000 件。") for x in lines), text[:3000])
        self.assertIn(f"- {rows[0]}", lines)
        self.assertNotIn(f"- {rows[100]}", lines)
        self.assertIn(f"- {protect.LIST}（protected_hits）のほか 19995 件（全件: {whole}）", lines)
        self.assertIn(f"- 報告へ進める: {answer.line(RUN, 'continue', '<一言>')}（一言は {ask_final.RECORD} に残る）", lines)
        self.assertIn(f"- 止める: {answer.line(RUN, 'stop', '<理由>')}（報告は出る）", lines)

    def test_many_new_names_are_cut(self):
        """直した後の実測の新しい名と知る場所の増えが 20,000 件ずつでも、最後の承認ノードの文は件数に依らず短く、末尾の答え方の行まで在る。
        各一覧は先頭 SHOWN 件と、どの一覧の残りかと残りの件数と structure-after.json のパスの 1 行だけで、全件の数の行（after_counts）は残る"""
        rises = [{"concept": "止め", "what": "語", "path": f"m{i}.py", "before": 1, "after": 2} for i in range(20000)]
        names = [{"name": f"name_{i}", "sites": 2} for i in range(20000)]
        ptr = self.place("eyes/structure-after.json", {"status": "ok", "reason": "", "deviations": [],
                                                       "after": {"tables": ["t"], "fence_up": rises, "new_names": names}})
        fenced, after, unread = ask_final.after_rows(ptr)
        text = ask_final.final_text(final_got(fenced=fenced, after=after), [], RUN)
        lines = text.splitlines()
        where = f"（全件: {ask_final.path_of(ptr)}）"
        self.assertEqual(unread, "")
        self.assertLessEqual(len(lines), 120, text[:3000])
        self.assertTrue(any("新しい名 20000 個" in x and "知る場所の増え 20000 件" in x for x in lines), text[:3000])
        self.assertIn("  - 新しい名 name_0（現れる所 2 か所）", lines)
        self.assertNotIn("  - 新しい名 name_100（現れる所 2 か所）", lines)
        self.assertIn(f"  - {structmark.FENCE_UP_LIST}のほか 19995 件{where}", lines)
        self.assertIn(f"  - {structmark.NEW_NAMES_LIST}のほか 19995 件{where}", lines)
        self.assertNotIn("m100.py", text)
        self.assertIn(f"- 報告へ進める: {answer.line(RUN, 'continue', '<一言>')}（一言は {ask_final.RECORD} に残る）", lines)
        self.assertIn(f"- 止める: {answer.line(RUN, 'stop', '<理由>')}（報告は出る）", lines)

    def test_gate_text_is_kept_in_the_artifacts(self):
        """L-W37: 開いた関所の文の控えを run の置き場の gates/final-gate.md に残し、文はそのパスを名指す"""
        out = ask_final.keep(ask_final.ask(final_got(), mode="", unattended=False, run_id=RUN), self.artifacts)
        self.assertEqual((self.artifacts / ask_final.FINAL_GATE_FILE).read_text(encoding="utf-8"), out["text"])
        self.assertIn(f"この文の控え: run の置き場の {ask_final.FINAL_GATE_FILE}", out["text"])
        shut = ask_final.keep(ask_final.ask(final_got(), mode="when_needed", unattended=False, run_id=RUN), self.tmp / "none")
        self.assertFalse((self.tmp / "none").exists())
        self.assertFalse(shut["open"])


class FinalGateCase(Artifacts):
    """最後の人の関所に、人に回した食い違いの申し出（ask_human と案の直しを諦めた fix_plan_item）だけを 1 行ずつ並べ、それが在る時
    だけ開ける（F426）"""
    place, conflicts = AskFinalReadsCase.place, AskFinalReadsCase.conflicts

    def test_final_gate_lists_asked_lines_not_pointers(self):
        for mode in ("when_needed", "protected_only"):
            with self.subTest(mode=mode):
                rows, unread = ask_final.asked_conflicts([self.conflicts("fix/fix", "fix_code_as", "fix_test_scope")])
                fixed_only = ask_final.ask(final_got(asked=rows, conflicts_unread=unread), mode=mode, unattended=False, run_id=RUN)
                self.assertFalse(fixed_only["open"], fixed_only)
                rows, unread = ask_final.asked_conflicts([self.conflicts("fix/fix", "fix_code_as", "ask_human")])
                asked = ask_final.ask(final_got(asked=rows, conflicts_unread=unread), mode=mode, unattended=False, run_id=RUN)
                self.assertTrue(asked["open"])
                self.assertIn(f"- {rows[0]}", asked["text"])
                self.assertNotIn("conflicts.json", asked["text"])

    def test_refix_replan_rows_reach_the_final_gate(self):
        """L-W48: 2 度目の修正の段で新しく fix_plan_item と裁いた行は、段を抜ける時に諦めた行になり（fix の返す節 collect の replan.close。
        tests/workflows/test_fix.py の test_refix_place_reads_the_first_pass_rulings）、fixed が運ぶ 2 度目の控えから最後の関所の申し出に
        1 行で並ぶ（元 works/darkfactory/lib/line_edge.py:1159-1160）。1 回目の段の案を直した行は並べず、2 度数えない"""
        first, second = self.artifacts / "fix" / "fix", self.artifacts / "fix" / "refix-run"
        first.mkdir(parents=True)
        second.mkdir(parents=True)
        body = {"between": ["stats.py:9", "test_stats.py:8"], "why_both_cannot_hold": "案の項目が判定と食い違う",
                "which_is_right": "request", "kind": "brief_vs_judgment", "round": 1, "source": "fix", "status": "ruled"}
        (first / conflict.FILE).write_text(json.dumps({"items": [
            {**body, "id": "c1-1", "unit_key": "u1", "replan": "waiting",
             "ruling": {"decision": "fix_plan_item", "text": "項目 1 が誤り", "limits": [], "plan_items": [1], "by": "ruler"}}]},
            ensure_ascii=False), encoding="utf-8")
        conflict.adopt_prior(second, first, ["1"])
        new = conflict.park(second, [{**{k: body[k] for k in conflict.FIELDS if k != "unit_key"}, "unit_key": "u2"}], source=conflict.FIX_SOURCE)
        conflict.apply_rulings(second, {new[0]: {"decision": "fix_plan_item", "text": "項目 2 も誤り", "limits": [],
                                                 "plan_items": [2]}}, by="ruler")
        replan.close(second, replan.CLOSE_WHY)
        ptr = lambda rel: {"type": "archon_artifact", "run_id": RUN, "path": rel}
        got = fixed.fixed(FixedCase.fix(FixedCase()), FixedCase.fix(FixedCase(), conflicts=ptr("fix/refix-run/conflicts.json")),
                          replan=True, stops=("",))
        rows, unread = ask_final.asked_conflicts(got["conflicts"])
        self.assertEqual(unread, [])
        self.assertEqual(len(rows), 1, rows)
        self.assertTrue(rows[0].startswith("u2: 項目 2 も誤り"), rows)
        self.assertIn(replan.CLOSE_WHY, rows[0])
        opened = ask_final.ask(final_got(asked=rows), mode="when_needed", unattended=False, run_id=RUN)
        self.assertTrue(opened["open"])
        self.assertIn(f"- {rows[0]}", opened["text"])


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
        self.assertFalse(self.got(round=3)["done"], "往復は数でなく中央の穴の有無で止まる（converge.decide）")

    def test_every_field_is_returned(self):
        self.assertEqual(set(self.got()), set(plan_out.PLAN + plan_out.REVIEW) | {"nothing_owed", "done", "stop_reason"})


class PlanOutNothingOwedCase(Artifacts):
    def test_nothing_owed_is_the_plan_field(self):
        """#291・#681: 直す義務 0 件の周かは plan の出力の欄 nothing_owed をそのまま読む（周のフォルダの round.json を開かない。
        lib/outcome.py の plan_nothing_owed も同じ欄）。計画ができた周は欄が真でも偽"""
        got = {key: None for key in plan_out.PLAN + plan_out.REVIEW}
        self.assertTrue(plan_out.plan_out({**got, "ready": False, "nothing_owed": True}, ROUND_LIMIT)["nothing_owed"])
        self.assertFalse(plan_out.plan_out({**got, "ready": False, "nothing_owed": False}, ROUND_LIMIT)["nothing_owed"])
        self.assertFalse(plan_out.plan_out({**got, "ready": True, "round": 1, "nothing_owed": True}, ROUND_LIMIT)["nothing_owed"])

    def read_from_env(self, nothing_owed: str) -> dict:
        env = {f"INPUTS_{key.upper()}": "null" for key in plan_out.PLAN + plan_out.REVIEW}
        env.update({"INPUTS_READY": "false", "INPUTS_NOTHING_OWED": nothing_owed, "INPUTS_ROUND_LIMIT": str(ROUND_LIMIT)})
        with mock.patch.dict(os.environ, env):
            return plan_out.plan_out(*plan_out.from_env())

    def test_the_node_reads_the_field_from_its_input(self):
        """本番の節の口（from_env）が入力 nothing_owed（$plan.output.nothing_owed）を読む"""
        self.assertTrue(self.read_from_env("true")["nothing_owed"])
        self.assertFalse(self.read_from_env("false")["nothing_owed"])
        self.assertEqual(line_nodes()["plan-rounds"]["loop_group"]["nodes"][2]["with"]["nothing_owed"], "$plan.output.nothing_owed")


class SpecCheckNodeCase(Artifacts):
    def test_no_spec_no_question(self):
        self.assertEqual(spec_check.check("null", False), {"questions": [], "stop_reason": "", "unchecked": False})

    def test_spec_on_without_pointer_asks(self):
        """#550: spec=on なのに判定が指しを返さなければ、黙って通さずに問い、照らせなかったと言う"""
        self.assertEqual(spec_check.check("null", True),
                         {"questions": [spec_check.NO_POINTER], "stop_reason": stopby.SPEC_CHANGED, "unchecked": True})

    def test_unreadable_spec_is_unchecked(self):
        """#550: 指した J/spec.json を読めない時は問い 1 行と人待ちの止め（今のまま）で、照らせなかったと言う"""
        ptr = json.dumps({"type": "archon_artifact", "run_id": RUN, "path": "judge/spec.json"})
        with contextlib.chdir(self.tmp):
            got = spec_check.check(ptr, True)
        self.assertEqual((len(got["questions"]), got["stop_reason"], got["unchecked"]), (1, stopby.SPEC_CHANGED, True), got)
        self.assertIn("読めない", got["questions"][0])

    def test_changed_spec_waits(self):
        (self.tmp / "test_accept.txt").write_text("変えた\n", encoding="utf-8")
        (self.artifacts / "judge").mkdir()
        spec = {"acceptance": [{"key": "A1", "file": "test_accept.txt", "sha256": "a" * 64}]}
        (self.artifacts / "judge" / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
        ptr = json.dumps({"type": "archon_artifact", "run_id": RUN, "path": "judge/spec.json"})
        with contextlib.chdir(self.tmp):
            got = spec_check.check(ptr, True)
        self.assertEqual(got["stop_reason"], stopby.SPEC_CHANGED)
        self.assertIs(got["unchecked"], False)
        self.assertEqual(len(got["questions"]), 1, got)
        self.assertIn("test_accept.txt", got["questions"][0])

    def test_crash_is_a_question_not_silence(self):
        """照らしが落ちた返りの 0 件は、最後の承認ノードに「変わっていない」と読まれて問わずに通る。落ちたら問いを 1 行返す"""
        ptr = json.dumps({"type": "archon_artifact", "run_id": "another-run", "path": "judge/spec.json"})
        env = hermetic.child_env(ARTIFACTS_DIR=str(self.artifacts), WORKFLOW_ID=RUN, INPUTS_SPEC=ptr)
        done = subprocess.run([sys.executable, str(SCRIPTS / "spec_check.py")], cwd=self.tmp, env=env, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(done.stdout)
        self.assertEqual(got["stop_reason"], stopby.LINE_SCRIPT)
        self.assertEqual(len(got["questions"]), 1, got)
        self.assertIn("確かめられない", got["questions"][0])
        self.assertIs(got["unchecked"], True)

    def test_check_reads_the_judge_spec(self):
        """仕様の段の J/spec.json の指し札が fix-in を通って照らしに届き、照らしの問いが最後の承認ノードと collect に届く"""
        nodes = line_nodes()
        self.assertEqual(nodes["spec-check"]["with"]["spec"], {"from": "$fix-in.output.spec", "if_skipped": None})
        self.assertEqual(nodes["spec-check"]["with"]["spec_on"], "$start.output.spec")
        self.assertEqual(nodes["spec-check"]["depends_on"], ["fixed"])
        for key, skipped, unchecked in (("ask-final", [], False), ("collect", None, None)):
            with self.subTest(node=key):
                self.assertEqual(nodes[key]["with"]["spec_changed"], {"from": "$spec-check.output.questions", "if_skipped": skipped})
                self.assertEqual(nodes[key]["with"]["spec_unchecked"], {"from": "$spec-check.output.unchecked", "if_skipped": unchecked})
        self.assertEqual(nodes["report"]["with"]["spec-unchecked"], "$collect.output.spec_unchecked")


class AfterFixAndJudgedCase(Artifacts):
    def test_after_fix_counts(self):
        self.assertEqual(after_fix.decide([]), {"replan": False, "stop_reason": ""})
        self.assertEqual(after_fix.decide(["1"]), {"replan": True, "stop_reason": ""})

    def judgment(self, rel, units):
        (self.artifacts / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.artifacts / rel).write_text(json.dumps({"units": units, "questions": []}), encoding="utf-8")
        return {"type": "archon_artifact", "run_id": RUN, "path": rel}

    def returned(self, ptr, verdict=None, exit_=None):
        return {"units": [{"id": "x"}], "judgment": ptr, "purpose": "p", "world": None, "rejudge_verdict": verdict, "rejudge_exit": exit_}

    EXIT = {"type": "archon_artifact", "run_id": RUN, "path": f"rejudge/{judge_accept.REJUDGE_EXIT}"}

    def test_judged_without_the_rejudge_is_the_judge(self):
        judge = self.returned(self.judgment("judge/judgment.json", []))
        got = judged.judged(judge, None, "")
        self.assertEqual((got["judgment"], got["rejudged"], got["new_open_units"], got["lowered"], got["unnamed_changed"]),
                         (judge["judgment"], False, [], [], []))

    def rejudged(self, before, after, objection, verdicts=("一部採る",)):
        """判定のブロックの書き手（judge_accept.diff_units・rejudge_collect）が再審の置き場に書く judgment.json・rejudge-diff.json・
        rejudge-exit.json（再審の返りの欄 rejudge_exit が指す）"""
        rdir = self.artifacts / "rejudge"
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / judge_accept.REJUDGE_BEFORE).write_text(json.dumps({"units": before, "objection": objection,
                                                                    "numbered_keys": [u["key"] for u in before]}), encoding="utf-8")
        ptr = self.judgment("rejudge/judgment.json", after)
        rows = [{"round": 1, "pass": judge_accept.REJUDGE_ROLE, "verdict": v,
                 **judge_accept.diff_units(before, after, objection, [u["key"] for u in before])} for v in verdicts]
        (rdir / judge_accept.REJUDGE_DIFF).write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        judge_accept.rejudge_collect(rdir)
        return ptr

    def test_judged_reads_the_rejudge_exit(self):
        """L-W42・やる事 2: 再審の前後の比べ（後に開いた単位・block から下げた単位・異議が名指さずに変わった単位）は判定のブロックが
        再審の置き場に書き、再審の返りの欄 rejudge_exit が指す出口だけが数え（元 rejudge.collect と diff_units）、judged はそれを読んで
        返し、出口のポインタも欄 rejudge_exit で返す（数えを 2 か所に持たない。K20）"""
        before = [{"key": "a", "label": "block", "disposition": "fix"}, {"key": "b", "label": "suggest", "disposition": "later"},
                  {"key": "c", "label": "block", "disposition": "fix"}, {"key": "d", "label": "nit", "disposition": "later"}]
        after = [{"key": "a", "label": "suggest", "disposition": "later"}, {"key": "b", "label": "suggest", "disposition": "do-now"},
                 {"key": "c", "label": "block", "disposition": "fix"}, {"key": "d", "label": "nit", "disposition": "drop"},
                 {"key": "e", "label": "block", "disposition": "fix"}]
        judge = self.returned(self.judgment("judge/judgment.json", before))
        again = self.returned(self.rejudged(before, after, "a は直さなくてよい。no 2 も"), "一部採る", self.EXIT)
        got = judged.judged(judge, again, "a は直さなくてよい。no 2 も")
        self.assertEqual((got["judgment"], got["rejudged"], got["rejudge_verdict"], got["rejudge_exit"]),
                         (again["judgment"], True, "一部採る", self.EXIT))
        self.assertEqual(got["new_open_units"], ["b", "e"])
        self.assertEqual(got["lowered"], ["a"])
        self.assertEqual(got["unnamed_changed"], ["d", "e"])
        self.assertEqual(got["unread"], "")
        exit_doc = json.loads((self.artifacts / "rejudge" / judge_accept.REJUDGE_EXIT).read_text(encoding="utf-8"))
        exit_doc.update({"new_open_units": ["z"], "lowered": [], "unnamed_changed": []})
        (self.artifacts / "rejudge" / judge_accept.REJUDGE_EXIT).write_text(json.dumps(exit_doc), encoding="utf-8")
        self.assertEqual(judged.judged(judge, again, "")["new_open_units"], ["z"], "judged は自分で数えず出口を読む")
        self.assertFalse(hasattr(judged, "unit_changes"))

    def test_rejudge_stop_holds_the_line(self):
        """L-D48: 再審が止まった run（3 回拒まれた・支度ができない）は、judged が再審の止めの理由を返し、fixed が試験の関門（final）・
        独立の目・merge へ進めない（元 works/.shared/core/rejudge.py 546-558 行）。止まらない再審と、再審の無い run は止めない"""
        judge = self.returned(self.judgment("judge/judgment.json", []))
        stopped = {**self.returned(judge["judgment"]), "units": []}
        got = judged.judged(judge, stopped, "異議", "works:rejudge")
        self.assertEqual(got["stop_reason"], "works:rejudge")
        self.assertEqual(judged.judged(judge, self.returned(judge["judgment"], "採る"), "異議", "")["stop_reason"], "")
        self.assertEqual(judged.judged(judge, None, "", "works:rejudge")["stop_reason"], "", "再審が走らなければ止めの理由は無い")
        nodes = line_nodes()
        self.assertEqual(nodes["judged"]["with"]["rejudge"], {"from": "$rejudge-run.output", "if_skipped": None})
        # 再審は 2 度目の修正の後（L-D42）なので、judged の止めは fixed でなく試験の関門（final）の when が読む。独立の目・merge はその後ろ
        self.assertIn("$judged.output.stop_reason == ''", nodes["test-gate-final"]["when"])
        self.assertIn("$fixed.output.go == true", nodes["test-gate-final"]["when"])
        self.assertEqual(nodes["redepth"]["depends_on"], ["judged"])

    def test_judged_reads_the_whole_rejudge_output(self):
        """judged は INPUTS_REJUDGE（再審の返りまるごと）から、再審の単位と止めの理由 stop_reason を読む。judge_ の欄（fix-in の欄つきの
        参照）はどの欄も値に戻す。再審の節が飛んだ（null）時は再審なし"""
        judge = self.returned(self.judgment("judge/judgment.json", []), "採る")
        again = {**self.returned(self.judgment("rejudge/judgment.json", []), "一部採る"), "units": [],
                 "ready": False, "stop_reason": "works:rejudge", "depth": [], "depth_why": ""}
        env = {f"INPUTS_JUDGE_{key.upper()}": value if isinstance(value, str) else json.dumps(value) for key, value in judge.items()}
        with mock.patch.dict(os.environ, {**env, "INPUTS_REJUDGE": json.dumps(again), "INPUTS_OBJECTION": "異議"}, clear=True):
            took = judged.judged(*judged.from_env())
        self.assertEqual((took["rejudged"], took["stop_reason"], took["units"], took["rejudge_verdict"]), (True, "works:rejudge", [], "一部採る"))
        with mock.patch.dict(os.environ, {**env, "INPUTS_REJUDGE": "null", "INPUTS_OBJECTION": ""}, clear=True):
            took = judged.judged(*judged.from_env())
        self.assertEqual((took["rejudged"], took["stop_reason"], took["rejudge_verdict"]), (False, "", "採る"))
        self.assertEqual(judged.REJUDGE, (*judged.FIELDS, "stop_reason", "rejudge_exit"))

    def test_judged_passes_the_first_only_ports_of_the_rejudge(self):
        """1 回目の判定でしか書かない控え（decisions・answer_ties。judge_accept.FIRST_PORTS）は再審の返りも 1 回目の物を指すので、
        judged はそれを運ぶ（再審の後に目の記録された方針が null にならない）"""
        first = {"decisions": f"judge/{judge_accept.FIRST_PORTS['decisions']}",
                 "answer_ties": f"judge/{judge_accept.FIRST_PORTS['answer_ties']}"}
        judge = {**self.returned(self.judgment("judge/judgment.json", [])), **first}
        again = {**self.returned(self.judgment("rejudge/judgment.json", []), "採る"), **first}
        got = judged.judged(judge, again, "異議")
        self.assertEqual({key: got[key] for key in first}, first)
        self.assertEqual(line_nodes()["judged"]["with"]["judge_answer_ties"], "$fix-in.output.answer_ties")

    def test_unreadable_judgments_are_said(self):
        judge = self.returned({"type": "archon_artifact", "run_id": "another", "path": "judge/judgment.json"})
        got = judged.judged(judge, self.returned(judge["judgment"], exit_={**self.EXIT, "run_id": "another"}), "")
        self.assertEqual((got["new_open_units"], got["lowered"], got["unnamed_changed"], got["stop_reason"]), ([], [], [], ""))
        self.assertIn("比べられない", got["unread"])
        judge = self.returned(self.judgment("judge/judgment.json", []))
        got = judged.judged(judge, self.returned(self.judgment("rejudge/judgment.json", [])), "")
        self.assertIn("再審の出口が無い", got["unread"])


class FixedCase(unittest.TestCase):
    def fix(self, **kw):
        got = {"done": True, "units": [{"unit_id": "u1", "status": "given_up"}], "groups": [{"group_id": "g1"}],
               "conflicts": {"path": "fix/conflicts.json"}, "replan_items": ["1"], "objection": "", "diff": {"path": "fix/diff"},
               "allowed_test_changes": ["tests/a.py"], "changed": {"path_changed": False}, "delta_review": {"rounds": 1, "pass": True},
               **{field: {"path": f"fix/{name}"} for field, name in fixbeside.PORTS.items()}, "removed": [{"path": "fix/fix-removed.json"}],
               "tdd_refused": {"refused": [], "unread": []}}
        got.update(kw)
        return got

    def test_first_fix_alone(self):
        got = fixed.fixed(self.fix(), None, replan=False, stops=("", ""))
        self.assertEqual((got["conflicts"], got["refixed"], got["diff"]), ([{"path": "fix/conflicts.json"}], False, {"path": "fix/diff"}))
        self.assertTrue(got["done"])

    def test_no_fix_round_goes_on_with_the_design(self):
        """L-W07: 直す物が無い周（fix が走らず、独立設計だけを作る差し込み design-only が走った）は、fixed が直す物の無い形
        （no_fix・go・差分も申し出も無い）と独立設計の指し札を返し、最後のテスト・独立の目へ進める。普段の周は計画の往復の設計と
        修正前の問い・答えをそのまま渡す"""
        design, premises = {"path": "plan-review/design.json"}, {"path": "plan-review/design-premises.json"}
        plans = {"plan": None, "ripple": None, "replanned": None, "design": None, "design_premises": None, "no_fix_design": design,
                 "no_fix_design_premises": premises, "plan_questions": None, "answer": None}
        got = fixed.fixed({key: None for key in fixed.FIELDS}, None, replan=False, stops=("",), plans=plans)
        self.assertEqual((got["no_fix"], got["go"], got["done"], got["design"], got["design_premises"], got["diff"], got["records"],
                          got["units"], got["conflicts"], got["rejudge"], got["plan_questions"], got["answer"]),
                         (True, True, True, design, premises, None, [], [], [], False, [], None))
        normal = fixed.fixed(self.fix(), None, replan=False, stops=("",),
                             plans={"design": {"path": "pr/design.json"}, "design_premises": {"path": "pr/design-premises.json"},
                                    "plan_questions": [{"kind": "fork", "text": "q"}], "answer": {"decision": "continue"}})
        self.assertEqual((normal["no_fix"], normal["design"], normal["design_premises"], normal["plan_questions"], normal["answer"]),
                         (False, {"path": "pr/design.json"}, {"path": "pr/design-premises.json"}, [{"kind": "fork", "text": "q"}],
                          {"decision": "continue"}))

    def test_records_line_up_the_stage_ports(self):
        """部分 D2・#681: fixed は段ごとの diff と控えの欄の並び records（1 回目・2 度目の順。fixbeside.stage）を返し、最後の
        承認ノード・深さの上げ直し・独立の目・報告が段ごとに読む。2 度目が走らなければ 1 回目だけ。控えの欄の無い返り（この版より前に
        走った修正の返り）は止める"""
        first = fixed.fixed(self.fix(), None, replan=False, stops=("", ""))
        self.assertEqual(first["records"], [fixbeside.stage(self.fix())])
        self.assertEqual(set(first["records"][0]), {"diff", *fixbeside.PORTS, *fixbeside.FROM})
        second = self.fix(diff={"path": "refix/diff"}, closure={"path": "refix/closure.json"})
        both = fixed.fixed(self.fix(), second, replan=True, stops=("", ""))
        self.assertEqual(both["diff"], {"path": "refix/diff"})
        self.assertEqual([(r["diff"], r["closure"]) for r in both["records"]],
                         [({"path": "fix/diff"}, {"path": "fix/closure.json"}), ({"path": "refix/diff"}, {"path": "refix/closure.json"})])
        for prior in ({k: v for k, v in self.fix().items() if k != "tdd_refused"}, {**self.fix(), "tdd_refused": None}):
            with self.subTest(prior=sorted(prior)), self.assertRaisesRegex(ValueError, fixbeside.PRIOR_VERSION):
                fixed.fixed(self.fix(), prior, replan=True, stops=("", ""))

    def test_replan_without_the_second_fix_is_not_done(self):
        """案の直しの関所の stop・無人の止め・案ができなかった時に、1 回目の修正の差分を試験の関門から先へ進めない"""
        self.assertFalse(fixed.fixed(self.fix(), None, replan=True, stops=("", ""))["done"])

    def test_a_line_script_stop_before_is_not_done(self):
        for stops in ((stopby.LINE_SCRIPT, ""), ("", stopby.LINE_SCRIPT)):
            with self.subTest(stops=stops):
                self.assertFalse(fixed.fixed(self.fix(), None, replan=False, stops=stops)["done"])

    def test_a_fix_stop_holds_and_is_returned(self):
        """#403: fix か 2 度目の修正が止めの語（戻せず当たったままの組の stopby.UNRESTORED）を返したら、試験の関門から先へ進めず
        （held）、その語を stop_reason で報告へ届ける"""
        for first, second in ((self.fix(stop_reason=stopby.UNRESTORED), None),
                              (self.fix(), self.fix(stop_reason=stopby.UNRESTORED))):
            with self.subTest(refix=second is not None):
                got = fixed.fixed(first, second, replan=second is not None, stops=("",))
                self.assertEqual((got["done"], got["go"], got["rejudge"], got["stop_reason"]), (False, False, False, stopby.UNRESTORED))
        self.assertEqual(fixed.fixed(self.fix(stop_reason=""), None, replan=False, stops=("",))["stop_reason"], "")

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

    def test_declared_plan_blocks_reach_the_eyes(self):
        """issue #662: 修正役が直さずに残すと答えた事前審査の block の行は、1 回目と 2 度目の修正の分を重ねずに合わせ、独立の目の
        入力 plan_declared へ渡す"""
        row = "stale-docstring-left: 古い docstring が残る（直す側の答え: 範囲の外なので残す）"
        got = fixed.fixed(self.fix(plan_declared=[row]), self.fix(plan_declared=[row, "b: x（直す側の答え: y）"]), replan=True,
                          stops=("", ""))
        self.assertEqual(got["plan_declared"], [row, "b: x（直す側の答え: y）"])
        self.assertEqual(line_nodes()["eyes"]["with"]["plan_declared"], "$fixed.output.plan_declared")

    def test_eyes_get_the_final_test_outcomes_and_every_fix_diff(self):
        """issue #384: R2 の比較役の実測は最後のテストの関門の比べ（base の関門の欄は常に null）と、修正の段ごとの diff"""
        self.assertEqual({k: line_nodes()["eyes"]["with"][k] for k in ("test_outcomes", "records")},
                         {"test_outcomes": "$test-gate-final.output.test_outcomes", "records": "$fixed.output.records"})

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
                         {"plan": {"from": "$fix-in.output.plan", "if_skipped": None},
                          "ripple": {"from": "$fix-in.output.ripple", "if_skipped": None},
                          "replanned": {"from": "$replan-out.output.got", "if_skipped": None}})
        self.assertIn("replan-out", nodes["fixed"]["depends_on"])

    def test_refix_objection_is_kept(self):
        """L-D42: 再審は 2 度目の修正の後に 1 度だけ走り、1 回目と 2 度目の修正役の異議の両方を受ける（元 works/darkfactory/darkfactory.yaml:827
        の h-rejudge は refit の後）。異議の文は最後の関所と報告にも同じ objection で届く。止めた run（held）は再審しない"""
        got = fixed.fixed(self.fix(objection="u1 は誤り"), self.fix(objection="u2 も誤り"), replan=True, stops=("",))
        self.assertEqual((got["objection"], got["rejudge"]), ("u1 は誤り\nu2 も誤り", True))
        alone = fixed.fixed(self.fix(), self.fix(objection="u2 も誤り"), replan=True, stops=("",))
        self.assertEqual((alone["objection"], alone["rejudge"]), ("u2 も誤り", True))
        self.assertFalse(fixed.fixed(self.fix(), None, replan=False, stops=("",))["rejudge"])
        self.assertFalse(fixed.fixed(self.fix(objection="u1 は誤り"), None, replan=True, stops=("",))["rejudge"], "held は再審しない")
        nodes = line_nodes()
        self.assertEqual((nodes["rejudge-run"]["depends_on"], nodes["rejudge-run"]["when"], nodes["rejudge-run"]["with"]["objection"]),
                         (["fixed"], "$fixed.output.rejudge == true", "$fixed.output.objection"))
        self.assertIn("fixed", nodes["judged"]["depends_on"])
        self.assertEqual((nodes["judged"]["with"]["objection"], nodes["ask-final"]["with"]["objection"]),
                         ("$fixed.output.objection", "$fixed.output.objection"))
        self.assertNotIn("judged", nodes["fixed"]["depends_on"])

    def test_second_ruling_in_refix_is_not_dropped(self):
        """L-D38: 2 度目の修正の控え（1 回目の段の行を写して持つ）を 1 つの指し札で運び、2 度目の段の申し出を捨てず、1 回目の行を
        2 度数えない。2 度目の修正が控えを返さなければ 1 回目の物"""
        got = fixed.fixed(self.fix(), self.fix(conflicts={"path": "fix/refix-run/conflicts.json"}), replan=True, stops=("",))
        self.assertEqual(got["conflicts"], [{"path": "fix/refix-run/conflicts.json"}])
        self.assertEqual(fixed.fixed(self.fix(), self.fix(conflicts=None), replan=True, stops=("",))["conflicts"],
                         [{"path": "fix/conflicts.json"}])

    def test_eyes_gets_the_fix_x_scalars(self):
        """E17・L-W57: 修正役が足した x_ の規模の数値は fix の返り x_scalars から fixed（2 度目の値を優先して名ごとに合わせる）を通って
        独立の目に届く"""
        got = fixed.fixed(self.fix(x_scalars={"x_a": 1, "x_b": 2}), self.fix(x_scalars={"x_b": 5}), replan=True, stops=("",))
        self.assertEqual(got["x_scalars"], {"x_a": 1, "x_b": 5})
        self.assertEqual(fixed.fixed(self.fix(x_scalars={"x_a": 1}), None, replan=False, stops=("",))["x_scalars"], {"x_a": 1})
        nodes = line_nodes()
        self.assertEqual(nodes["eyes"]["with"]["x_scalars"], "$fixed.output.x_scalars")
        self.assertEqual(nodes["fixed"]["with"]["refix"], {"from": "$refix-run.output", "if_skipped": None})
        self.assertIn("x_scalars", fixed.FIELDS)
        self.assertIn("x_scalars", block_doc("works-factory-fix")["nodes"][-1]["output_format"]["required"])

    def test_fields_are_every_field_fix_returns_and_fixed_takes_them_all(self):
        """fixed.FIELDS は fix の返す節の output_format の欄の組と同じで、fixed は 1 回目（fix）と 2 度目（refix-run）の出力をまるごとで
        受け、読む欄は口 picked に渡す FIELDS（片側だけ変えると欄が黙って落ちる。stop_reason は refix-run から fixed を通ってだけ
        報告に届く）"""
        doc = block_doc("works-factory-fix")
        returns = next(n for n in doc["nodes"] if n["id"] == doc["returns"])
        self.assertEqual(set(fixed.FIELDS), set(returns["output_format"]["properties"]) - {"optional"})
        self.assertIn("optional", returns["output_format"]["properties"], "宣言の欄は返す節が持つ（fixed は運ばない）")
        self.assertNotIn("optional", returns["output_format"]["required"])
        took = line_nodes()["fixed"]["with"]
        self.assertEqual({key: took[key] for key in ("fix", "refix")},
                         {"fix": {"from": "$fix.output", "if_skipped": None}, "refix": {"from": "$refix-run.output", "if_skipped": None}})
        self.assertFalse([key for key in took if key.startswith(("fix_", "refix_"))], "欄ごとの書き写しは残さない")

    def test_whole_outputs_of_both_passes_are_read(self):
        """fixed は INPUTS_FIX・INPUTS_REFIX（返りまるごと）を読む。refix が null なら 2 度目は走らなかったと見分け、fix も refix も
        null なら直す物の無い周の形に倒す。fix だけ null で refix が在っても落ちない"""
        first = self.fix(stop_reason="")
        second = self.fix(units=[{"unit_id": "u2", "status": "fixed"}], diff={"path": "refix/diff"}, stop_reason="")
        base = {"INPUTS_REPLAN": "false", "INPUTS_STOP_AFTER_FIX": ""}

        def run(**inputs):
            env = {**base, **{f"INPUTS_{k.upper()}": json.dumps(v) for k, v in inputs.items()}}
            with mock.patch.dict(os.environ, env, clear=True):
                return fixed.fixed(**fixed.from_env())

        got = run(fix=first, refix=None)
        self.assertEqual((got["done"], got["refixed"], got["no_fix"], got["units"]), (True, False, False, first["units"]))
        both = run(fix=first, refix=second)
        self.assertEqual((both["done"], both["refixed"], both["no_fix"], both["diff"]), (True, True, False, {"path": "refix/diff"}))
        self.assertEqual([u["unit_id"] for u in both["units"]], ["u1", "u2"])
        self.assertTrue(run(fix=None, refix=None)["no_fix"])
        self.assertEqual(run(fix=None, refix=second)["refixed"], True)
        with mock.patch.dict(os.environ, {**base, "INPUTS_FIX": json.dumps(first), "INPUTS_REFIX": "null"}, clear=True):
            took = fixed.from_env()
        self.assertEqual((set(took["fix"]), took["refix"]), (set(fixed.FIELDS), None))
        with self.assertRaises(KeyError):
            took["fix"]["typo"]
        with self.assertRaises(KeyError):
            took["fix"].get("typo")
        with mock.patch.dict(os.environ, {**base, "INPUTS_FIX": "null", "INPUTS_REFIX": "null"}, clear=True):
            skipped = fixed.from_env()["fix"]
        self.assertEqual(skipped, dict.fromkeys(fixed.FIELDS))
        with self.assertRaises(KeyError, msg="飛ばされた fix の既定も宣言の外の名で止まる"):
            skipped.get("typo")


class RedepthCase(Artifacts):
    LIGHT = [{"unit_id": "u1", "depth": "軽量", "why": "配線だけ"}]

    def redepth(self, *, units=(), conflicts=(), signals=(), replanned=False, rejudged=False, replanned_depth=None, counted="",
                head="軽量"):
        return redepth.redepth(self.LIGHT, replanned_depth, list(units), list(conflicts), list(signals), replanned=replanned,
                               rejudged=rejudged, head=head, counted=counted)

    def put(self, rel, doc):
        (self.artifacts / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.artifacts / rel).write_text(doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return {"type": "archon_artifact", "run_id": RUN, "path": rel}

    def test_quiet_run_stays_light_and_names_what_it_skips(self):
        got = self.redepth(units=[{"unit_id": "u1", "status": "fixed"}])
        self.assertEqual(got["depth"][0]["depth"], "軽量")
        self.assertTrue(got["skip_optional"])

    def test_standard_or_heavy_head_omits_nothing(self):
        """issue #561: 単位がどれも軽量のままでも、run の頭の深さが標準・重厚・不明なら省く理由の文は空（目と差分の審査を回す）"""
        for head in ("標準", "重厚", "", "null"):
            with self.subTest(head=head):
                got = self.redepth(units=[{"unit_id": "u1", "status": "fixed"}], head=head)
                self.assertEqual((got["depth"][0]["depth"], got["skip_optional"]), ("軽量", ""))

    def test_signals_raise_to_standard(self):
        for kw in ({"units": [{"unit_id": "u1", "status": "given_up"}]}, {"conflicts": [{"path": "c"}]},
                   {"signals": ["答えていない問い q1"]}, {"replanned": True}, {"rejudged": True}):
            with self.subTest(kw=kw):
                got = self.redepth(**kw)
                self.assertEqual((got["depth"][0]["depth"], got["skip_optional"]), ("標準", ""))

    def test_question_not_in_the_answer_still_raises(self):
        """L-D08: 上げる信号「答えていない問い」は問いの台帳の問いごと（元 depth.signals の gatemarks.pending。判定の役が人に聞くと保留に
        した問いも含む）。修正前の関所の答えが聞いた問いと依頼の answers が答えた問いは数えず、関所の答えが 1 つ在っても聞いていない問い・
        「保留: <key>」と名指した問いは上げる。台帳が読めない時は上げる側に倒す"""
        questions = [{"key": "q1", "kind": "fork", "status": "held", "origin": "u1", "reason": "a か b か"},
                     {"key": "q2", "kind": "fork", "status": "held", "origin": "u2", "reason": "c か d か"},
                     {"key": "q3", "kind": "fork", "status": "held", "origin": "u3", "reason": "e か f か"}]
        judgment = self.put("judge/judgment.json", {"units": [], "questions": questions})
        start = self.put("r1/start.json", {"answers": [{"question": "q3", "text": "e"}]})
        answer = {"decision": "continue", "text": "", "asked": [gatemarks.ask_text(questions[0])]}
        self.assertEqual(redepth.pending_signals(judgment, start, answer, None, None), ["答えていない問い q2"])
        held = {**answer, "text": "保留: q1", "asked": [gatemarks.ask_text(q) for q in questions[:2]]}
        self.assertEqual(redepth.pending_signals(judgment, start, held, None, None), ["答えていない問い q1"])
        self.assertEqual(redepth.pending_signals(judgment, start, None, None, None), ["答えていない問い q1", "答えていない問い q2"])
        broken = self.put("judge/broken.json", "{壊れた")
        self.assertTrue(redepth.pending_signals(broken, start, None, None, None)[0].startswith("問いの台帳が読めない"))
        self.assertEqual(redepth.pending_signals(None, start, None, None, None), [])
        got = self.redepth(signals=redepth.pending_signals(judgment, start, answer, None, None))
        self.assertEqual(got["depth"][0]["depth"], "標準")
        self.assertIn("答えていない問い q2", got["raised"])

    def test_unattended_run_does_not_raise_for_a_taken_push(self):
        """#593: 無人の run が判定の推しを答えに採った fork・held は答えた問い（始めの記録から ledger_at が読む）なので上げない。
        人のいる run では同じ問いが答えていない問いのまま上げる"""
        pushed = {"key": "q1", "kind": "fork", "status": "held", "origin": "u1", "options": ["a", "b"], "reason": "a か b か。推し: a——速い"}
        judgment = self.put("judge/judgment.json", {"units": [{"key": "u1", "label": "block"}], "questions": [pushed]})
        for record, want in (({"unattended": "true"}, []), ({}, ["答えていない問い q1"])):
            with self.subTest(record=record):
                start = self.put("r1/start.json", record)
                self.assertEqual(redepth.pending_signals(judgment, start, None, None, None), want)

    def test_wide_run_raises_to_standard(self):
        """L-D10: run 全体の広さ（計画の allowed_paths と修正の実際の差分のファイルの和集合・受け入れと書き換えのテストの本数。
        depth.run_wide）が単位ごとの上限を超えれば、軽量の名指しでも全部の単位を標準へ上げ、数えた数と起点を counted に残す
        （元 depth.raise_ :302-313）"""
        plan = self.put("plan/plan-fields.json", {"fields": [{"unit_keys": ["u1"], "allowed_paths": ["a.py"], "tests": [], "rewrite_tests": []}]})
        diff = "".join(f"diff --git a/w{n}.py b/w{n}.py\n--- a/w{n}.py\n+++ b/w{n}.py\n@@ -1 +1 @@\n-x\n+y\n" for n in range(4))
        ptr = self.put("fix/diff.patch", diff)
        stage = fixbeside.stage({"diff": ptr, **dict.fromkeys(fixbeside.PORTS), "removed": [], "tdd_refused": {"refused": [], "unread": []}})
        signals, counted = redepth.fix_signals(plan, ptr, [stage], None, ["u1"])
        self.assertEqual(signals, ["run 全体で触るファイル 5 個（3 個まで）"])
        self.assertTrue(counted.startswith("触るファイル 5 個（起点: 修正の差分 fix/diff.patch）／"), counted)
        got = self.redepth(signals=signals, counted=counted)
        self.assertEqual((got["depth"][0]["depth"], got["counted"]), ("標準", counted))
        signals, counted = redepth.fix_signals(plan, None, [], None, ["u1"])
        self.assertEqual(signals, [])
        self.assertTrue(counted.startswith(f"触るファイル 1 個（起点: {latedepth.PLAN_ORIGIN}"), counted)

    def test_the_node_joins_the_question_and_width_signals(self):
        """L-D08・L-D10: ノード redepth は with: の判定・始めの記録・修正前の承認ノードの答え・結びの判定から答えていない問いの信号を、
        計画と修正の差分から run の広さの信号を組み、どちらも上げる理由に載せ、数えた数を counted に返す（from_env で信号を合わせる所を
        外すと、片方の信号が上げる理由から落ちて赤）"""
        questions = [{"key": "q1", "kind": "fork", "status": "held", "origin": "u1", "reason": "a か b か"}]
        judgment = self.put("judge/judgment.json", {"units": [], "questions": questions})
        start = self.put("r1/start.json", {"answers": []})
        plan = self.put("plan/plan-fields.json", {"fields": [{"unit_keys": ["u1"], "allowed_paths": ["a.py"], "tests": [], "rewrite_tests": []}]})
        diff = self.put("fix/diff.patch", "".join(f"diff --git a/w{n}.py b/w{n}.py\n--- a/w{n}.py\n+++ b/w{n}.py\n@@ -1 +1 @@\n-x\n+y\n"
                                                for n in range(4)))
        env = {"INPUTS_DEPTH": json.dumps(self.LIGHT, ensure_ascii=False), "INPUTS_REPLAN_DEPTH": "null", "INPUTS_UNITS": "[]",
               "INPUTS_CONFLICTS": "[]", "INPUTS_PLAN": json.dumps(plan), "INPUTS_DIFF": json.dumps(diff),
               "INPUTS_JUDGMENT": json.dumps(judgment), "INPUTS_START": json.dumps(start), "INPUTS_ANSWER": "null",
               "INPUTS_ANSWER_TIES": "null", "INPUTS_MATERIALS": "null", "INPUTS_DEPTH_RECORD": "null",
               "INPUTS_REPLANNED": "false", "INPUTS_REJUDGED": "false", "INPUTS_HEAD_DEPTH": "軽量",
               "INPUTS_RECORDS": json.dumps([fixbeside.stage({"diff": diff, **dict.fromkeys(fixbeside.PORTS), "removed": [],
                                                              "tdd_refused": {"refused": [], "unread": []}})])}
        self.assertLessEqual({k.removeprefix("INPUTS_").lower() for k in env}, set(line_nodes()["redepth"]["with"]))
        with mock.patch.dict(os.environ, env):
            got = redepth.compute()
        self.assertEqual(got["depth"][0]["depth"], "標準")
        self.assertIn("答えていない問い q1", got["raised"])
        self.assertIn("run 全体で触るファイル 5 個（3 個まで）", got["raised"])
        self.assertTrue(got["counted"].startswith("触るファイル 5 個（起点: 修正の差分 fix/diff.patch）"), got["counted"])
        self.assertIn("修正の後の信号の控えが無い", got["counted"])

    def test_fix_and_line_read_missing_and_broken_records_alike(self):
        """#654: 修正のブロックの中の上げ直し（fixboard.redepth）と線の redepth は、同じ置き場の修正の後の信号の控えを
        latedepth.signals の 1 つの決まりで読む。範囲の相談の行を運ぶ控え（fix では戻せた組の子の結果、線では欄 accept_trace の先）が
        無ければどちらも上げずに counted に訳を添え、在るのに読めなければどちらも上げる側へ倒す。TDD の輪の状態も同じ。片方の控えだけが
        崩れた時は、その控えを読む側だけが同じ決まりで動く（子の結果は fix だけが読む。置き場の受け付けの行は fix も
        fixboard.accept_trace_rows で読むので、壊れれば両方が上げる。無いのは fix には行が 0 の置き場で、線には null の欄）"""
        import tddloop
        place = self.artifacts / "fix"
        diff = self.put("fix/diff.patch", "")
        result = place / "groups" / "g1" / fixboard.RESULT_FILE
        env = {"INPUTS_DEPTH": json.dumps(self.LIGHT, ensure_ascii=False), "INPUTS_REPLAN_DEPTH": "null", "INPUTS_UNITS": "[]",
               "INPUTS_CONFLICTS": "[]", "INPUTS_PLAN": "null", "INPUTS_DIFF": json.dumps(diff), "INPUTS_JUDGMENT": "null",
               "INPUTS_START": "null", "INPUTS_ANSWER": "null", "INPUTS_ANSWER_TIES": "null", "INPUTS_MATERIALS": "null",
               "INPUTS_DEPTH_RECORD": "null", "INPUTS_REPLANNED": "false", "INPUTS_REJUDGED": "false", "INPUTS_HEAD_DEPTH": "軽量",
               "INPUTS_PLAN_DECLARED": "[]"}

        def outcome(*, result_doc, trace, state):
            """(fix の (上げたか, 無い訳を添えたか), 線の同じ組)。None の控えは置かない"""
            shutil.rmtree(place, ignore_errors=True)
            fixboard.write_json(place / fixboard.DEPTH_FILE, self.LIGHT)
            fixboard.write_json(place / fixboard.HEAD_DEPTH_FILE, "軽量")
            fixboard.write_json(place / fixboard.GROUPS_FILE, {"groups": [{"group_id": "g1"}], "out_dir": str(place / "groups")})
            fixboard.write_json(place / fixboard.JOIN_FILE, {"groups": [{"group_id": "g1", "returned": True}], "units": []})
            self.put("fix/diff.patch", "")
            for rel, doc in ((result.relative_to(self.artifacts).as_posix(), result_doc), ("fix/accept-trace.json", trace),
                             (f"fix/tdd-1/{tddloop.STATE}", state)):
                if doc is not None:
                    self.put(rel, doc)
            skip = fixboard.redepth(place, place)
            counted = fixboard.read_json(place / fixboard.DEPTH_RAISED_FILE)["counted"]
            got = fixbeside.returned(place, lambda path: boundary.pointer(path.relative_to(self.artifacts).as_posix()))
            with mock.patch.dict(os.environ, {**env, "INPUTS_RECORDS": json.dumps([fixbeside.stage({"diff": diff, **got})])}):
                line = redepth.compute()
            no_record = latedepth.NO_LATE_RECORD.split("（")[0]
            return ((skip == "", no_record in counted),
                    (line["depth"][0]["depth"] == "標準", no_record in line["counted"]))

        passed = {"calls": [{"n": 1, "phase": "fix", "unit_key": "u1", "ok": True}]}
        whole, kept, noted, raised = {"group_id": "g1"}, (False, False), (False, True), (True, False)
        for case, kw, want in (("揃った控え", {"result_doc": whole, "trace": [], "state": passed}, (kept, kept)),
                               ("輪の状態が無い", {"result_doc": whole, "trace": [], "state": None}, (kept, kept)),
                               ("相談の行の控えが無い", {"result_doc": None, "trace": None, "state": passed}, (noted, noted)),
                               ("相談の行の控えが壊れた", {"result_doc": "{壊れた", "trace": "{壊れた", "state": passed}, (raised, raised)),
                               ("子の結果だけが無い", {"result_doc": None, "trace": [], "state": passed}, (noted, kept)),
                               ("欄 accept_trace の先だけが無い", {"result_doc": whole, "trace": None, "state": passed}, (kept, noted)),
                               ("子の結果だけが壊れた", {"result_doc": "{壊れた", "trace": [], "state": passed}, (raised, kept)),
                               ("欄 accept_trace の先だけが壊れた", {"result_doc": whole, "trace": "{壊れた", "state": passed}, (raised, raised)),
                               ("輪の状態が壊れた", {"result_doc": whole, "trace": [], "state": "{壊れた"}, (raised, raised))):
            with self.subTest(case):
                self.assertEqual(outcome(**kw), want)

    def test_late_signals_come_from_the_stage_ports(self):
        """修正の後の 3 つの事実: diff の触るファイルが 1 回目の判定の頭の深さの控え（入力 depth_record）の where の外（テストのファイルを除く）・最後の
        修正の段の欄 tdd_refused（返す節が TDD の輪の状態 tdd-<k>/state.json の拒まれた call から組む）・同じ段の欄 accept_trace の先の範囲の相談の行。
        それぞれ上げる理由になり、ノード redepth が軽量の単位を標準へ上げる。欄 accept_trace が null の時は上げずに counted に訳を添え、輪の状態が無い時は
        拒否を数えず、在るのに読めない・{error} の時だけ上げる。diff が null なら何も足さない。段は返す節が fixbeside.returned で組む形（#681。
        diff の隣を名で開かない）"""
        import conflict
        import consult
        import headdepth
        import tddloop

        def patch(*names):
            return "".join(f"diff --git a/{n} b/{n}\n--- a/{n}\n+++ b/{n}\n@@ -1 +1 @@\n-x\n+y\n" for n in names)
        record = headdepth.record("軽量", "易しい", items=[{"item": 1, "unknown": "無し", "where": "stats.py:9", "cause_quote": "分母が違う",
                                                           "code_quote": "return"}])
        judgment = self.put("judge/judgment.json", {"units": [], "questions": []})
        depth_record = self.put("judge/depth-head.json", record)
        plan = self.put("plan/plan-fields.json", {"fields": [{"unit_keys": ["u1"], "allowed_paths": ["stats.py"], "tests": [], "rewrite_tests": []}]})
        diff = self.put("fix/diff.patch", patch("stats.py"))
        tdd_name, trace_name = f"fix/tdd-1/{tddloop.STATE}", "fix/accept-trace.json"
        refused = {"calls": [{"n": 1, "phase": "test", "unit_key": "u1", "ok": False}, {"n": 2, "phase": "route", "unit_key": "", "ok": False}]}
        passed = {"calls": [{"n": 1, "phase": "runner", "unit_key": "u1", "ok": False}, {"n": 2, "phase": "fix", "unit_key": "u1", "ok": True}]}
        asked = {"op": conflict.ASKED_OP, "item": 1, "unit_keys": ["u1"], "origin": None}
        gate = {"op": conflict.ASKED_OP, "item": 1, "unit_keys": ["u1"], "origin": consult.ORIGIN_GATE}

        def records():
            """fix の返す節が今の置き場から組む段（fixbeside.returned）の並び"""
            got = fixbeside.returned(self.artifacts / "fix", lambda path: boundary.pointer(path.relative_to(self.artifacts).as_posix()))
            return [fixbeside.stage({"diff": diff, **got})]

        def signals(*names):
            if names:
                self.put("fix/diff.patch", patch(*names))   # 同じ指し札のまま差分の中身を替える
            got, counted = redepth.fix_signals(plan, diff, records(), depth_record, ["u1"])
            return got, counted.split("／")[1:]
        no_trace = latedepth.NO_LATE_RECORD.format(name="accept-trace.json")
        self.assertEqual(signals(), ([], [no_trace]), "受け付けの行が無い時は上げずに訳を添え、輪の状態が無い時は拒否を数えない")
        self.put(tdd_name, passed)
        self.put(trace_name, [gate, {"op": "fix_tests_selected", "note": "x"}])
        self.assertEqual(signals(), ([], []), "拒否も相談も引用の外も無い")
        self.put(tdd_name, refused)
        got, notes = signals()
        self.assertEqual(notes, [])
        self.assertEqual(len(got), 1)
        self.assertIn("TDD のループで修正役が拒まれた", got[0])
        self.assertIn("u1", got[0])
        self.assertIn(tddloop.ROUTE_REFUSED, got[0])
        self.put(tdd_name, passed)
        self.put(trace_name, [gate, asked])
        got, _ = signals()
        self.assertEqual([("範囲の相談" in w, "u1" in w) for w in got], [(True, True)])
        self.put(trace_name, [])
        got, _ = signals("stats.py", "tests/test_stats.py", "other.py")
        self.assertEqual(len(got), 1)
        self.assertIn("引用した where の外に出た", got[0])
        self.assertIn("other.py", got[0])
        self.assertNotIn("test_stats.py", got[0], "テストのファイルだけが外なら外の信号は出ない")
        self.assertEqual(signals("stats.py", "tests/test_stats.py"), ([], []))
        self.put("judge/depth-head.json", headdepth.record("標準", "割れる"))
        self.assertEqual(signals("stats.py", "other.py"), ([], []), "where の無い頭の深さの控えは外を持たない")
        self.put("judge/depth-head.json", record)
        self.put(tdd_name, "{壊れた")
        got, notes = signals("stats.py")
        self.assertEqual((len(got), notes), (1, []))
        self.assertIn("修正の後の信号の控えが読めない", got[0])
        self.put(tdd_name, {"error": "組めなかった"})
        self.assertIn("組めなかった", signals()[0][0])
        got, counted = redepth.fix_signals(plan, None, [], depth_record, ["u1"])
        self.assertEqual((got, counted.split("／")[1:]), ([], []), "diff が null なら修正の段の信号も訳も足さない")
        env = {"INPUTS_DEPTH": json.dumps(self.LIGHT, ensure_ascii=False), "INPUTS_REPLAN_DEPTH": "null", "INPUTS_UNITS": "[]",
               "INPUTS_CONFLICTS": "[]", "INPUTS_PLAN": json.dumps(plan), "INPUTS_DIFF": json.dumps(diff),
               "INPUTS_JUDGMENT": json.dumps(judgment), "INPUTS_START": "null", "INPUTS_ANSWER": "null",
               "INPUTS_ANSWER_TIES": "null", "INPUTS_MATERIALS": "null", "INPUTS_DEPTH_RECORD": json.dumps(depth_record),
               "INPUTS_REPLANNED": "false", "INPUTS_REJUDGED": "false", "INPUTS_HEAD_DEPTH": "軽量"}

        def run(names, tdd, trace):
            self.put("fix/diff.patch", patch(*names))
            self.put(tdd_name, tdd)
            self.put(trace_name, trace)
            with mock.patch.dict(os.environ, {**env, "INPUTS_RECORDS": json.dumps(records(), ensure_ascii=False)}):
                return redepth.compute()
        quiet = run(["stats.py"], passed, [])
        self.assertEqual((quiet["depth"][0]["depth"], bool(quiet["skip_optional"])), ("軽量", True))
        self.assertNotIn("控えが無い", quiet["counted"])
        for why, args in (("TDD のループで修正役が拒まれた", (["stats.py"], refused, [])),
                          ("修正役が範囲の相談をした", (["stats.py"], passed, [asked])),
                          ("引用した where の外に出た", (["stats.py", "other.py"], passed, []))):
            with self.subTest(why=why):
                got = run(*args)
                self.assertEqual((got["depth"][0]["depth"], got["skip_optional"]), ("標準", ""))
                self.assertTrue(any(why in r for r in got["raised"]), got["raised"])
        (self.artifacts / tdd_name).unlink()
        (self.artifacts / trace_name).unlink()
        self.put("fix/diff.patch", patch("stats.py"))
        with mock.patch.dict(os.environ, {**env, "INPUTS_RECORDS": json.dumps(records(), ensure_ascii=False)}):
            got = redepth.compute()
        self.assertEqual((got["depth"][0]["depth"], bool(got["skip_optional"])), ("軽量", True), "控えが無ければ今どおり軽量のまま省く")
        self.assertIn(no_trace, got["counted"])

    def test_declared_plan_block_raises_a_light_run(self):
        """issue #662: 修正役が直さずに残すと答えた事前審査の block（入力 plan_declared）が在れば、頭も単位も軽量の run も標準へ上げ、
        目の R1〜R4 を省かない（省くと、その block を読む R4 が走らず誰にも届かない）。無ければ軽量のまま省く"""
        plan = self.put("plan/plan-fields.json", {"fields": [{"unit_keys": ["u1"], "allowed_paths": ["a.py"], "tests": [], "rewrite_tests": []}]})
        env = {"INPUTS_DEPTH": json.dumps(self.LIGHT, ensure_ascii=False), "INPUTS_REPLAN_DEPTH": "null", "INPUTS_UNITS": "[]",
               "INPUTS_CONFLICTS": "[]", "INPUTS_PLAN": json.dumps(plan), "INPUTS_DIFF": "null", "INPUTS_JUDGMENT": "null",
               "INPUTS_START": "null", "INPUTS_ANSWER": "null", "INPUTS_ANSWER_TIES": "null", "INPUTS_MATERIALS": "null",
               "INPUTS_DEPTH_RECORD": "null", "INPUTS_REPLANNED": "false", "INPUTS_REJUDGED": "false", "INPUTS_HEAD_DEPTH": "軽量",
               "INPUTS_PLAN_DECLARED": "[]"}
        self.assertLessEqual({k.removeprefix("INPUTS_").lower() for k in env}, set(line_nodes()["redepth"]["with"]))
        with mock.patch.dict(os.environ, env):
            quiet = redepth.compute()
        self.assertEqual((quiet["depth"][0]["depth"], bool(quiet["skip_optional"])), ("軽量", True))
        line = "b1: 古い説明文が残る（直す側の答え: 別の issue で直す）"
        with mock.patch.dict(os.environ, {**env, "INPUTS_PLAN_DECLARED": json.dumps([line], ensure_ascii=False)}):
            got = redepth.compute()
        self.assertEqual((got["depth"][0]["depth"], got["skip_optional"]), ("標準", ""))
        self.assertTrue(any("直さずに残すと答えた事前審査の block が在る" in r and "b1" in r for r in got["raised"]), got["raised"])

    def test_replanned_depth_merges_by_unit(self):
        """L-D15: 案の直しの後の深さは、1 回目の単位の行を残して直した案の単位の行で単位ごとに置き換える（元 depth.raise_ は全部の単位の
        控えを残して上げた）"""
        got = self.redepth(replanned_depth=[{"unit_id": "u9", "depth": "標準", "why": "直した案"}], replanned=True)
        self.assertEqual([row["unit_id"] for row in got["depth"]], ["u1", "u9"])
        got = self.redepth(replanned_depth=[{"unit_id": "u1", "depth": "標準", "why": "直した案"}])
        self.assertEqual([(row["unit_id"], row["depth"]) for row in got["depth"]], [("u1", "標準")])

    def test_line_passes_what_the_signals_read(self):
        """L-D08・L-D10: redepth は判定の問いの台帳（判定と始めの記録と修正前の関所の答えと今の判定の結びと素材の状態）と、
        1 回目の判定の頭の深さの控えと、修正の計画と差分と、修正役が直さずに残した事前審査の block の行を受ける"""
        with_ = line_nodes()["redepth"]["with"]
        keys = ("judgment", "start", "answer", "answer_ties", "materials", "depth_record", "plan", "diff", "records", "head_depth",
                "plan_declared")
        self.assertEqual({k: with_[k] for k in keys},
                         {"judgment": "$judged.output.judgment", "start": "$start.output.record", "head_depth": "$fix-in.output.head_depth",
                          "answer": {"from": "$fix-in.output.answer", "if_skipped": None},
                          "answer_ties": "$judged.output.answer_ties", "materials": "$judged.output.materials",
                          "depth_record": "$fix-in.output.depth_record",
                          "plan": "$fixed.output.plan", "diff": "$fixed.output.diff", "records": "$fixed.output.records",
                          "plan_declared": "$fixed.output.plan_declared"})
        self.assertIn("counted", line_nodes()["redepth"]["output_format"]["required"])


class ReturnedCase(unittest.TestCase):
    def returned(self, env: dict) -> dict:
        with mock.patch.dict(os.environ, env, clear=True):
            return returned.returned()

    def test_whole_output_gives_the_declared_fields(self):
        """受け皿は INPUTS_GOT（受ける節の返りまるごと）の、INPUTS_NAMES（with: の names）で宣言した欄だけを、型を保ったまま got にする
        （hash "123" は字、reason "" は字、diff null は None。返りに無い宣言の名は None、宣言の外の欄は運ばない）"""
        whole = {"mode": "seal", "ok": True, "hash": "123", "diff": None, "protected_hits": [], "reason": "", "extra": 1}
        got = self.returned({"INPUTS_GOT": json.dumps(whole), "INPUTS_NAMES": "mode ok hash diff protected_hits reason missing"})
        self.assertEqual(got, {"got": {**{k: v for k, v in whole.items() if k != "extra"}, "missing": None}, "stop_reason": ""})
        self.assertEqual((got["got"]["hash"], got["got"]["reason"], got["got"]["diff"]), ("123", "", None))

    def test_fields_outside_the_declaration_stop_the_script(self):
        """returned の got は宣言した名だけを持ち、.get・globals・getattr・locals で読み直しても、宣言の外の欄は KeyError になる"""
        env = {"INPUTS_GOT": json.dumps({"ok": True, "stall": True}), "INPUTS_NAMES": "ok"}
        reads = {
            "返りの欄を .get": 'returned()["got"].get("stall")',
            "globals": 'globals()["returned"]()["got"].get("stall")',
            "getattr": 'getattr(sys.modules[__name__], "returned")()["got"]["stall"]',
            "locals": '(lambda whole: locals()["whole"].get("stall"))(returned()["got"])',
        }
        for name, read in reads.items():
            with self.subTest(name), mock.patch.dict(os.environ, env), self.assertRaises(KeyError):
                eval(read, {**vars(returned), "sys": sys})

    def test_unreadable_got_is_a_fallback_not_an_empty_got(self):
        """受ける返りが読めない（INPUTS_GOT が無い・空・null・object でない・運ぶ欄の名 names が無い）時は、空の got の成功にせず
        例外にして、boundary.run が fallback（got が None、stop_reason が works:line-script）に落とす"""
        line_inputs = {f"INPUTS_{name.upper()}": "x" for name in LINE["inputs"]}
        for case, env in {"無い": {}, "空": {"INPUTS_GOT": ""}, "null": {"INPUTS_GOT": "null"}, "字": {"INPUTS_GOT": "abc"},
                          "配列": {"INPUTS_GOT": "[]"}, "names が無い": {"INPUTS_GOT": "{}"}, "線の入力だけ": line_inputs,
                          "欄ごとの入力だけ": {"INPUTS_GOT_OK": "true"}}.items():
            with self.subTest(case):
                with self.assertRaises(ValueError):
                    self.returned(env)
        self.assertEqual(returned.fallback("x"), {"got": None, "stop_reason": "works:line-script"})


class CollectAndResultCase(unittest.TestCase):
    def line(self, **kw):
        got = {"start": "null", "fixed": None,
               "gates": {"gate_start": "null", "gate_before_fix": "null", "gate_replan": "null", "gate_final": "null"}}
        got.update(kw)
        return got

    def test_fields_are_the_inputs_report_declares(self):
        """collect の欄と report のポートの結びは名の一致でなく、線の report の with: が持つ: with: の鍵の集まりは report の inputs、
        with: の値 $collect.output.<欄> の欄の集まりは collect の欄（段の表 stages を含む）。fallback の鍵も同じ"""
        declared = yaml.safe_load((SCRIPTS.parents[1] / "report" / "works-factory-report.yaml").read_text(encoding="utf-8"))["inputs"]
        wired = line_nodes()["report"]["with"]
        self.assertEqual(set(wired), set(declared))
        fields = {re.fullmatch(r"\$collect\.output\.(\w+)", value)[1] for value in wired.values()}
        got = collect.collect({}, self.line())
        self.assertEqual(fields, set(got))
        self.assertEqual(collect.fallback("x").keys(), got.keys())

    def test_stages_table_reaches_report(self):
        """段の表 STAGES（役の名 → 線の節の id と返りの続き）は collect と fallback の出力の欄 stages になり、collect の節の出力の宣言と
        report の with: が運ぶ。表の nodes の値と、続きの行が引く id（outcome.node_of で描く物）は線の節の id に在る"""
        stages = collect.STAGES
        self.assertEqual(collect.collect({}, self.line())["stages"], stages)
        self.assertEqual(collect.fallback("x")["stages"], stages)
        nodes = line_nodes()
        shape = nodes["collect"]["output_format"]
        self.assertIn("stages", shape["properties"])
        self.assertIn("stages", shape["required"])
        self.assertEqual(nodes["report"]["with"]["stages"], "$collect.output.stages")
        self.assertLessEqual(set(stages["nodes"].values()), set(nodes))
        drawn = {outcome.node_of(stages, role) for row in stages["links"] for role in (row["before"], row["after"], row.get("needs")) if role}
        self.assertLessEqual(drawn, set(nodes))
        self.assertTrue(all(set(row) <= {"before", "flag", "after", "text", "held", "needs"} for row in stages["links"]))

    def test_lists_are_the_lists_report_reads(self):
        """collect が並びに倒す入力（LISTS と、字を行に割る TEXT_LINES）は、report の facts が並びと読む入力（無ければ黙って [] に
        なる）と、collect の節が配列と申告する欄と同じ"""
        from tests.workflows.test_report import facts_script
        lists = {*collect.LISTS, *collect.TEXT_LINES}
        self.assertEqual(lists, {name.replace("-", "_") for name in facts_script.LISTS})
        shape = line_nodes()["collect"]["output_format"]["properties"]
        self.assertEqual({key for key, rule in shape.items() if rule.get("type") == "array"}, lists)

    def test_skipped_receiver_is_null(self):
        seal = {"got": {"mode": "seal", "ok": True, "hash": "123"}, "stop_reason": ""}
        got = collect.collect({"judge": "null", "merge_seal": json.dumps(seal), "plan": "null", "plan_review": "null"}, self.line())
        self.assertIsNone(got["judge"])
        self.assertEqual(got["merge_seal"], seal["got"])
        self.assertEqual((got["plan"], got["plan_review"], got["fix"]), (None, None, None))

    def test_plan_rounds_without_a_review_have_no_plan_review(self):
        """plan-review が飛ばされた周で抜けた往復は、plan-review の欄が全部 null の受け皿を null に倒す"""
        plan = {key: None for key in plan_out.PLAN} | {"ready": False, "round": 1, "rejects": [], "nothing_owed": False}
        review = {key: None for key in plan_out.REVIEW}
        got = collect.collect({"plan": json.dumps({"got": plan, "stop_reason": ""}),
                               "plan_review": json.dumps({"got": review, "stop_reason": ""})}, self.line())
        self.assertNotIn("optional", got["plan"], "宣言の欄は report への欄から外れる")
        self.assertEqual(got["plan"], {key: value for key, value in plan.items() if key != "optional"})
        self.assertIsNone(got["plan_review"])

    def test_fixture_run_fills_the_skipped_stages_from_the_copy(self):
        """#509: 固定材料の run は直す前のテスト・判定・計画・修正前の承認が飛ぶので、その欄を fix-in が運んだ写しの値で埋める
        （報告の結末の決めは判定と計画の出力が無いと途中で終わった run と読む）。ほかの run の値は替えない"""
        received = {"test_gate_base": {"ok": True}, "judge": {"ready": True}, "plan": {"ready": True}, "plan_review": {"pass": True},
                    "gate_before_fix": {"decision": "continue"}, "deferred": [{"key": "q9"}]}
        relay = json.dumps({"received": received})
        got = collect.collect({"judge": "null", "plan": "null"}, self.line(fix_in=relay))
        self.assertEqual({name: got[name] for name in received}, received)
        judge = {"ready": False, **dict.fromkeys((*judge_accept.PORTS, *judge_accept.FIRST_PORTS))}
        live = json.dumps({"got": judge, "stop_reason": ""})
        got = collect.collect({"judge": live}, self.line(fix_in=json.dumps({"received": None})))
        self.assertEqual((got["judge"], got["plan"], got["deferred"]), (judge, None, []))

    def test_judge_return_of_the_prior_version_stops(self):
        """この版より前に走った判定・再審の返りを resume で受けた（出力の欄の鍵が無い）集めは、欄を空と読んで結末を作らず止める。
        先の無い欄の null は今の判定の返りなので止めない"""
        current = {"ready": True, **dict.fromkeys((*judge_accept.PORTS, *judge_accept.FIRST_PORTS))}
        for name in ("judge", "rejudge"):
            with self.subTest(name=name):
                prior = {key: value for key, value in current.items() if key != "depth_record"}
                with self.assertRaisesRegex(ValueError, judge_accept.PRIOR_VERSION):
                    collect.collect({name: json.dumps({"got": prior, "stop_reason": ""})}, self.line())
                got = collect.collect({name: json.dumps({"got": current, "stop_reason": ""})}, self.line())
                self.assertEqual(got[name], current)

    def test_plan_and_fix_returns_of_the_prior_version_stop(self):
        """#681: この版より前に走った計画・案の直し・修正の返り（控えの欄の鍵が無い）と、段の並び records の無い fixed の出力を resume で
        受けた集めは、欄を空と読んで結末を作らず止める（修正案の返答や修正の控えを「無い」と読まない）"""
        plan = {"ready": True, "fix_plan": None, "rejects": [], "nothing_owed": False, "gave_up": None}
        for name in ("plan", "replan"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, planfile.PRIOR_VERSION):
                    collect.collect({name: json.dumps({"got": {"ready": True}, "stop_reason": ""})}, self.line())
                for field in ("rejects", "nothing_owed"):
                    with self.assertRaisesRegex(ValueError, planfile.PRIOR_VERSION):
                        collect.collect({name: json.dumps({"got": {**plan, field: None}, "stop_reason": ""})}, self.line())
                self.assertEqual(collect.collect({name: json.dumps({"got": plan, "stop_reason": ""})}, self.line())[name], plan)
        fell = {key: plan_out.fallback("x")[key] for key in plan_out.PLAN if key != "optional"}
        self.assertEqual(collect.collect({"plan": json.dumps({"got": fell, "stop_reason": ""})}, self.line())["plan"], fell)
        fix = {"done": True, **FixedCase.fix(FixedCase())}
        with self.assertRaisesRegex(ValueError, fixbeside.PRIOR_VERSION):
            collect.collect({"fix": json.dumps({"got": {**fix, "tdd_refused": None}, "stop_reason": ""})}, self.line())
        with self.assertRaisesRegex(ValueError, fixbeside.PRIOR_VERSION):
            collect.collect({"fix": json.dumps({"got": fix, "stop_reason": ""})}, self.line(fixed=json.dumps({"done": True, "diffs": []})))

    def test_fallback_keeps_the_user_env_dir(self):
        """集めが落ちた時（前の版の返りの照らしで止まる道と、境の口を読めない道）も、利用者の環境で起こした印の置き場は報告に届く"""
        env = {"INPUTS_USER_ENV_DIR": "/art/user-env", "INPUTS_PLAN": json.dumps({"got": {"ready": True}, "stop_reason": ""})}
        unread = mock.patch.multiple(collect, boundary=None, unread=ImportError("x"))
        for case, patched in (("照らしで止まる", contextlib.nullcontext()), ("境の口を読めない", unread)):
            with self.subTest(case), patched, mock.patch.dict(os.environ, env), contextlib.redirect_stdout(io.StringIO()) as out, \
                    contextlib.redirect_stderr(io.StringIO()):
                collect.main()
            got = json.loads(out.getvalue())
            self.assertEqual((got["stops"], got["user_env_dir"]), ({"collect": collect.LINE_SCRIPT}, "/art/user-env"))

    def test_no_fix_design_is_the_plan_review(self):
        """L-W07: 直す物が無い周（計画の往復が飛んだ）は、report の plan-review の欄に design-only の受け皿の返りを置く"""
        only = {"pass": True, "design": {"path": "plan-review/design.json"}}
        got = collect.collect({"design_only": json.dumps({"got": only, "stop_reason": ""})}, self.line())
        self.assertEqual((got["plan"], got["plan_review"]), (None, only))
        self.assertEqual(line_nodes()["collect"]["with"]["design_only"], {"from": "$design-only-out.output", "if_skipped": None})

    def test_fix_is_the_first_and_second_fix_merged(self):
        """report の入力 fix は 1 回目と 2 度目の修正を合わせた物（申し出 conflicts は段ごとの指し札の配列）。合わせる節 fixed が
        飛ばされた（2 度目の修正の中が落ちた）時は 1 回目の返り。修正が走らなければ null"""
        first = {"got": {**FixedCase.fix(FixedCase()), "conflicts": "c1"}, "stop_reason": ""}
        merged = {"done": True, "conflicts": ["c1", "c2"], "records": [], "refixed": True, "stop_reason": ""}
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

    def test_line_stop_reasons_reach_report(self):
        """R5b・S48: 線の script の節（受け皿・collect・result と、往復の中の節の外）が返す止めの語は、collect が全部
        {from: $<節>.output.stop_reason, if_skipped: null} で受け、report の入力 stops に {節: 語} で渡す（空の語と飛ばされた節は載せない）。
        元は線の境の節が盤面の state.stop に書き、どの節の止めも結末が読んだ（works/.shared/core/report.py:328 _stop_info）"""
        nodes = line_nodes()
        inside = {node["id"] for node in nodes["plan-rounds"]["loop_group"]["nodes"]}
        stopping = {key for key, node in script_nodes().items() if "stop_reason" in node["output_format"]["properties"]
                    and node["script"] not in ("returned", "collect", "result") and key not in inside}
        self.assertLessEqual({"start", "ask-before-fix", "ask-replan", "ask-final", "judged", "fixed", "redepth", "after-fix"}, stopping)
        with_ = nodes["collect"]["with"]
        self.assertEqual({k for k in with_ if k.startswith("stop_")}, {f"stop_{k.replace('-', '_')}" for k in stopping})
        self.assertEqual(set(collect.STOPS), stopping)
        for key in sorted(stopping):
            with self.subTest(node=key):
                self.assertEqual(with_[f"stop_{key.replace('-', '_')}"], {"from": f"${key}.output.stop_reason", "if_skipped": None})
                self.assertIn(key, nodes["collect"]["depends_on"])
        got = collect.collect({}, self.line(stops={"start": "", "ask-final": "works:needs-human", "redepth": "null"}))
        self.assertEqual(got["stops"], {"ask-final": "works:needs-human"})
        self.assertEqual(nodes["report"]["with"]["stops"], "$collect.output.stops")

    def test_deferred_widened_reasons_reach_report(self):
        """L-W39・S49〜S51・S53: 無人の run で関所に載せなかった問い（ask-before-fix の deferred）・聞かずに通した範囲を広げるだけの直し
        （ask-replan の widened）・最後の関所を開ける理由（ask-final の reasons）・依頼の前の失敗の指し札（start の prior_failures）・
        直した後の深さの上げ直し（redepth の返り）を、collect が受けて report の入力に渡す。飛ばされた節は空の並びか null"""
        with_ = line_nodes()["collect"]["with"]
        self.assertEqual({k: with_[k] for k in ("deferred", "widened", "final_reasons", "prior_failures", "redepth")}, {
            "deferred": {"from": "$ask-before-fix.output.deferred", "if_skipped": None},
            "widened": {"from": "$ask-replan.output.widened", "if_skipped": None},
            "final_reasons": {"from": "$ask-final.output.reasons", "if_skipped": None},
            "prior_failures": {"from": "$start.output.prior_failures", "if_skipped": None},
            "redepth": {"from": "$redepth.output", "if_skipped": None}})
        ptr = {"type": "archon_artifact", "run_id": "r", "path": "start/prior-failures-in.json"}
        depth = {"depth": [{"unit_id": "u1", "depth": "標準", "why": "w"}], "skip_optional": "", "raised": ["再審が走った"], "stop_reason": ""}
        got = collect.collect({}, self.line(deferred=json.dumps(["[fork] q1"]), widened=json.dumps(["項目 1: 直した——…"]),
                                            final_reasons=json.dumps(["申し出を人に回した"]), prior_failures=json.dumps(ptr),
                                            redepth=json.dumps(depth)))
        self.assertEqual((got["deferred"], got["widened"], got["final_reasons"], got["prior_failures"], got["redepth"]),
                         (["[fork] q1"], ["項目 1: 直した——…"], ["申し出を人に回した"], ptr, depth))
        got = collect.collect({}, self.line())
        self.assertEqual((got["deferred"], got["widened"], got["final_reasons"], got["prior_failures"], got["redepth"]),
                         ([], [], [], None, None))
        report_with = line_nodes()["report"]["with"]
        for key in ("deferred", "widened", "final-reasons", "prior-failures", "redepth"):
            with self.subTest(input=key):
                self.assertEqual(report_with[key], f"$collect.output.{key.replace('-', '_')}")

    def test_notices_of_the_head_reach_report_by_the_line_only(self):
        """#678: 頭のノードが run を止めずに進めた注意の行（reason）を、collect が入力のポートで受けて行の並びにし、report の入力に
        渡す。どのノードから来るかはメイングラフの YAML だけが書き、報告のブロックは頭のノードの名を知らない"""
        nodes = line_nodes()
        self.assertEqual(nodes["collect"]["with"]["notices"], {"from": "$testcmd.output.reason", "if_skipped": None})
        self.assertIn("testcmd", nodes["collect"]["depends_on"])
        self.assertEqual(nodes["report"]["with"]["notices"], "$collect.output.notices")
        got = collect.collect({}, self.line(notices="注意（test_cmd）: a\nWORKS_FACTORY_ALLOW_TESTCMD=1 なので止めずに進める"))
        self.assertEqual(got["notices"], ["注意（test_cmd）: a", "WORKS_FACTORY_ALLOW_TESTCMD=1 なので止めずに進める"])
        for skipped in (None, "", "null"):
            with self.subTest(skipped=skipped):
                self.assertEqual(collect.collect({}, self.line(notices=skipped))["notices"], [])
        block = SCRIPTS.parents[1] / "report"
        for path in [block / "works-factory-report.yaml", *sorted((block / "scripts").glob("*.py"))]:
            with self.subTest(path=path.name):
                self.assertNotIn("testcmd", path.read_text(encoding="utf-8"))

    def test_absorbed_stages_are_declared_by_each_block(self):
        """R82: 受け止める段（落ちても線が先へ進めてよい段。元は線の YAML の節の description の [optional]）の宣言の置き場は、ブロック
        （judge・plan・fix）が返す節の with: の optional と、メイングラフの collect の with: の optional（include 丸ごとの宣言だけ）。
        collect が include の id の頭を付けて合わせた並びが report の入力 optional に届く。元の宣言は世界の解・構造の実測・レンズ・
        直した後の構造・独立の目（works/darkfactory/darkfactory.yaml 347・445・946・1124・1196 行）"""
        own = json.loads(line_nodes()["collect"]["with"]["optional"])
        self.assertEqual(own, ["eyes__"])
        self.assertEqual(collect.collect({}, self.line(optional=json.dumps(own)))["optional"], own)
        declared = declared_by_blocks()
        for stage in ("judge__world-", "plan__structure-", "fix__lens", "eyes__", "judge__head-depth-", "head-depth",
                      "test-gate-base__suite-loop", "suite-write"):
            with self.subTest(stage=stage):
                self.assertIn(stage, declared)
        self.assertEqual(line_nodes()["report"]["with"]["optional"], "$collect.output.optional")

    def test_optional_is_built_from_each_blocks_declaration(self):
        before = ["judge__world-", "rejudge-run__world-", "world-classes", "world-classes-", "world-judge", "world-judge-",
                  "plan__structure-", "replan__structure-", "structure-eye", "structure-eye-", "fix__lens", "fix__lens-reply",
                  "refix-run__lens", "refix-run__lens-reply", "eyes__", "judge__head-depth-", "head-depth", "head-depth-",
                  "test-gate-base__suite-loop", "suite-write"]
        own = line_nodes()["collect"]["with"]["optional"]
        self.assertEqual(json.loads(own), ["eyes__"])
        self.assertTrue(all(head.endswith(childsweep.INCLUDE_SEP) for head in json.loads(own)), "メイングラフの宣言に中の節の名が在る")
        ports = {**dict.fromkeys(judge_accept.PORTS), **dict.fromkeys(judge_accept.FIRST_PORTS)}
        plan_ports = {"fix_plan": None, "rejects": [], "nothing_owed": False, "gave_up": None}
        fix_ports = {**dict.fromkeys(fixbeside.PORTS), "removed": [], "tdd_refused": {"refused": [], "unread": []}}
        block_ports = {"test_gate_base": {}, "judge": ports, "rejudge": ports, "plan": plan_ports, "replan": plan_ports, "fix": fix_ports}
        returned = {field: {"ready": True, "units": [], **block_ports[field]} for field in RETURNING}
        receipts = {field: json.dumps({"got": {**returned[field], "optional": block_optional(block)}, "stop_reason": ""})
                    for field, block in RETURNING.items()}
        got = collect.collect(receipts, self.line(optional=own))
        self.assertEqual(sorted(got["optional"]), sorted(set(before) | {"rejudge-run__head-depth-"}))
        self.assertEqual(len(got["optional"]), len(set(got["optional"])), "重ねない")
        self.assertEqual(got["optional"], declared_by_blocks())
        for field in RETURNING:
            with self.subTest(field=field):
                self.assertEqual(got[field], returned[field], "report へ渡す欄に optional を載せない")
        judge = {n["id"]: n for n in block_doc("works-factory-judge")["nodes"]}
        self.assertIn("$intake.output.mode == 'judge'", judge["head-depth-prep"]["when"])
        # 固定材料の run: 飛んだ judge の欄を fix-in の写しで埋める。写しに optional が載っていても外し、宣言としては読まない
        copy = json.dumps({"received": {"judge": {"ready": True, "optional": [{"node": "carried-", "bare": False}]}}})
        got = collect.collect({"judge": "null"}, self.line(optional=own, fix_in=copy))
        self.assertEqual((got["judge"], got["optional"]), ({"ready": True}, ["eyes__"]))
        # 宣言の届かないブロック: 受け皿が null・返りに optional が無い・読めない行は、そのブロックの宣言を無い物と読む
        mixed = {"judge": json.dumps({"got": {"ready": True, **ports, "optional": None}, "stop_reason": ""}), "rejudge": "null",
                 "plan": json.dumps({"got": {"ready": True, **plan_ports, "optional": [{"node": 5, "bare": False}, "x", {"bare": True}]},
                                     "stop_reason": ""}),
                 "fix": json.dumps({"got": {"done": True, **fix_ports, "optional": [{"node": "lens", "bare": False}]}, "stop_reason": ""})}
        self.assertEqual(collect.collect(mixed, self.line(optional=own))["optional"], ["eyes__", "fix__lens", "refix-run__lens"])
        # 届かない宣言の先の落ちは、受け止めた落ち(absorbed)でなく途中で終わった落ち(failed)に数え、報告は節そのものを名指す
        fell = [r for i, step in enumerate(("judge__world-intake", "fix__lens")) for r in (
            {"step": step, "type": "node_start", "ts": f"2026-10-14T00:{i:02d}:00Z"},
            {"step": step, "type": "node_error", "ts": f"2026-10-14T00:{i:02d}:30Z", "error": "落ちた"})]
        unreached = collect.collect({"fix": "null", "judge": "null"}, self.line(optional=own))["optional"]
        facts = runreport.transcript_facts(fell, optional=unreached)
        self.assertEqual((facts["failed"], facts["absorbed"]), (["judge__world-intake", "fix__lens"], []))
        facts = runreport.transcript_facts(fell, optional=declared_by_blocks())
        self.assertEqual((facts["failed"], [a["node"] for a in facts["absorbed"]]), ([], ["judge__world-intake", "fix__lens"]))

    def test_stopping_stages_beside_an_absorbed_one_are_not_absorbed(self):
        """#599: 宣言はレンズの節とその中継だけを受け止め、名の頭が同じ止める段（支度 lens-prep・集め役 lens-collect）の落ちは
        途中で終わった落ちに数える（止まった run の報告がレンズを受け止めた落ちに載せ、止めたかの節を誤らない）。世界の解の段は
        ループの中の節（記録の step では素の id）まで受け止める"""
        declared = declared_by_blocks()
        fell = ["fix__lens", "fix__lens-reply", "refix-run__lens", "fix__lens-prep", "fix__lens-collect", "refix-run__lens-collect",
                "world-judge-accept", "eyes__r1"]
        rows = [r for i, s in enumerate(fell) for r in (
            {"step": s, "type": "node_start", "ts": f"2026-10-14T00:{i:02d}:00Z"},
            {"step": s, "type": "node_error", "ts": f"2026-10-14T00:{i:02d}:30Z", "error": "落ちた"})]
        facts = runreport.transcript_facts(rows, optional=declared)
        self.assertEqual(facts["failed"], ["fix__lens-prep", "fix__lens-collect", "refix-run__lens-collect"])
        self.assertEqual([a["node"] for a in facts["absorbed"]],
                         ["fix__lens", "fix__lens-reply", "refix-run__lens", "world-judge-accept", "eyes__r1"])

    def test_declared_range_moved_only_off_the_lens_prep_and_collect(self):
        """#599: 宣言を区切りつきの頭か名そのものに改めた時、受け止める範囲から外れたのは止める段のレンズの支度と集め役だけで、
        ループの中の節（記録の step では素の id）を含むほかの節の受け止めは前の宣言（区切りの無い頭の一致）と変わらない"""
        before = ["judge__world", "rejudge-run__world", "world-classes", "world-judge", "plan__structure", "replan__structure",
                  "structure-eye", "fix__lens", "refix-run__lens", "eyes__", "judge__head-depth", "head-depth"]
        declared = declared_by_blocks()
        steps = record_steps()
        self.assertIn("world-judge-accept", steps)
        moved = {s for s in steps if any(s.startswith(head) for head in before) != runreport._declared(s, declared)}
        late = {"rejudge-run__head-depth-prep", "rejudge-run__head-depth-loop"}
        suite = {"test-gate-base__suite-loop", "suite-write"}   # #516: 前の宣言に無い TDD の実行器の輪と書き手（落ちれば実行器の無い run の道）
        self.assertEqual(moved, {"fix__lens-prep", "fix__lens-collect", "refix-run__lens-prep", "refix-run__lens-collect"} | late | suite)
        # judge の宣言は judge と rejudge-run の両方に当たるので、再審の頭の深さの 2 節も数に入る。この 2 節は再審では走らない:
        # head-depth-prep は when が mode == 'judge' で飛び、head-depth-loop はその後ろで飛ぶ（落ちが無いので受け止めも変わらない）
        judge = {n["id"]: n for n in block_doc("works-factory-judge")["nodes"]}
        self.assertIn("$intake.output.mode == 'judge'", judge["head-depth-prep"]["when"])
        self.assertEqual(judge["head-depth-loop"]["depends_on"], ["head-depth-prep"])
        self.assertEqual({s for s in moved if "head-depth" in s}, late)

    def test_head_depth_fall_is_absorbed(self):
        """頭の深さの役が落ちても判定は標準で進む（judge_accept.head_depth）ので、報告は run を途中で終わった物と数えない"""
        rows = [{"step": "judge__head-depth-loop", "type": "node_start", "ts": "2026-10-14T00:00:00Z"},
                {"step": "judge__head-depth-loop", "type": "node_error", "ts": "2026-10-14T00:01:00Z", "error": "役が落ちた"},
                {"step": "judge__verdict", "type": "node_start", "ts": "2026-10-14T00:02:00Z"},
                {"step": "judge__verdict", "type": "node_complete", "ts": "2026-10-14T00:03:00Z"}]
        facts = runreport.transcript_facts(rows, optional=declared_by_blocks())
        self.assertEqual((facts["failed"], facts["absorbed"]), ([], [{"node": "judge__head-depth-loop", "error": "役が落ちた"}]))

    def test_result_carries_what_apply_reads(self):
        """線の返りの欄 apply・sealed・r2_status・final_answer・spec_questions（bin/apply と段 1 が読む）は collect が集めた返りから組み、飛ばされた段は
        null。result は merge・eyes・関所の返りを直に読まず collect を通す"""
        seal = {"mode": "seal", "ok": True, "hash": "h", "diff": {"path": "merge/sealed.diff"}, "protected_hits": [], "reason": ""}
        put = {**seal, "mode": "apply", "diff": {"path": "merge/apply.diff"}}
        eyes = {"ok": True, "r2": {"status": "pass", "reason": ""}}
        answer = {"decision": "stop", "text": "やめる"}
        got = result.result({"outcome": "fixed"}, {"merge_apply": put, "merge_seal": seal, "eyes": eyes, "gate_final": answer,
                                                   "spec_changed": [{"name": "t"}, {"name": "u"}]}, None)
        self.assertEqual(got["apply"], {"ok": True, "hash": "h", "diff": {"path": "merge/apply.diff"}, "reason": ""})
        self.assertEqual(got["sealed"], {"ok": True, "hash": "h", "diff": {"path": "merge/sealed.diff"}})
        self.assertEqual((got["r2_status"], got["final_answer"], got["spec_questions"]), ("pass", answer, 2))
        got = result.result({"outcome": ""}, {"merge_apply": None, "merge_seal": None, "eyes": {"ok": True, "r2": None}, "gate_final": None,
                                              "spec_changed": None}, None)
        self.assertEqual((got["apply"], got["sealed"], got["r2_status"], got["final_answer"], got["spec_questions"]),
                         (None, None, None, None, 0))
        with_ = line_nodes()["result"]["with"]
        for key in ("merge_apply", "merge_seal", "eyes", "gate_final", "spec_changed"):
            with self.subTest(key=key):
                self.assertEqual(with_[key], {"from": f"$collect.output.{key}", "if_skipped": None})
        self.assertFalse([v for v in with_.values() if "$merge-" in json.dumps(v) or "$eyes" in json.dumps(v)])

    def test_result_fixed(self):
        for outcome, want in (("fixed", True), ("fixed_needs_check", True), ("no_fix_needed", False), ("", False)):
            with self.subTest(outcome=outcome):
                self.assertEqual(result.result({"outcome": outcome}, {}, None)["fixed"], want)


class SweepChildrenCase(unittest.TestCase):
    """線の後始末の節 sweep-children（issue #113）: 報告の後・線の返す節の前に在り、落ちずに {cleaned, left, error} を返し、
    result がそれを線の返りの欄 children に載せる。選びと Archon の起こし方は tests/shared/test_childsweep.py"""

    def test_runs_after_the_report_and_feeds_only_the_result(self):
        nodes = line_nodes()
        node = nodes["sweep-children"]
        self.assertEqual((node["script"], node["depends_on"], node["trigger_rule"]), ("sweep_children", ["report"], "all_done"))
        self.assertIs(node["mutates_checkout"], False)
        self.assertEqual({key for key, other in nodes.items() if "sweep-children" in other.get("depends_on", [])}, {"result"})
        self.assertIn("sweep-children", nodes["result"]["depends_on"])
        self.assertEqual(nodes["result"]["with"]["children"], {"from": "$sweep-children.output", "if_skipped": None})
        top = {node["id"]: node for node in LINE["nodes"]}
        ends = {key for key in top if not any(key in other.get("depends_on", []) for other in top.values())}
        self.assertEqual({key for key in ends if "cancel" not in top[key]}, {"result"})   # cancel のノードは run をそこで終える

    def test_result_carries_the_sweep(self):
        swept = {"cleaned": [{"branch": "b0", "run_id": "c0", "node": "fix__groups-par"}],
                 "left": [{"branch": "b1", "run_id": "c1", "node": "fix__groups-par", "reason": "子の run が failed"}], "error": ""}
        self.assertEqual(result.result({"outcome": "fixed"}, {}, swept)["children"], swept)
        self.assertIsNone(result.result({"outcome": "fixed"}, {}, None)["children"])

    def test_failure_is_returned_not_raised(self):
        with mock.patch.object(boundary, "returns") as returns, mock.patch("sys.stderr"), \
                mock.patch.object(sweep_children, "sweep", side_effect=OSError("壊れた")):
            sweep_children.main()
        returns.assert_called_once_with({"cleaned": [], "left": [], "error": "OSError: 壊れた"})

    def run_node(self, extra: dict) -> dict:
        """節の script を、Archon と同じく工程のフォルダの写し（線と境の口）から、リポジトリの根を WORKS_FACTORY_ROOT で渡して
        本当に走らせる。Archon は偽の bun（一覧に WORKFLOW_ID の run だけを出す）で、子の run は無い"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            copied = tmp / "workflows"
            for folder in ("line", ".shared"):
                shutil.copytree(SCRIPTS.parents[1] / folder, copied / folder)
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
        head = {shared("childsweep").CLI_ENV: json.dumps(["<tmp>/bin/bun"])}
        self.assertEqual(self.run_node(head), {"cleaned": [], "left": [], "error": ""})

    def test_run_outside_the_launcher_does_not_fail(self):
        got = self.run_node({})
        self.assertEqual((got["cleaned"], got["left"]), ([], []))
        self.assertIn(shared("childsweep").CLI_ENV, got["error"])


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
                elif key == "sweep-children":   # 報告の後の後始末。止める段が無く、訳は error に書く
                    self.assertEqual(got["error"], "boom")
                elif key == "testcmd":   # 頭のノードは止めの理由でなく、cancel のノードが読む stop と reason で止める
                    self.assertIs(got["stop"], True)
                    self.assertIn("boom", got["reason"])
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
            env = hermetic.child_env(WORKS_FACTORY_ROOT=tmp, WORKFLOW_ID=RUN, ARTIFACTS_DIR=tmp, INPUTS_PLACE="gate")
            for node in guarded:
                with self.subTest(script=node["script"]):
                    done = subprocess.run([sys.executable, str(SCRIPTS / f"{node['script']}.py")], cwd=tmp, env=env,
                                          capture_output=True, text=True)
                    self.assertEqual(done.returncode, 0, done.stderr)
                    got = json.loads(done.stdout)
                    if node["script"] == "testcmd":   # 頭のノードは cancel のノードが読む stop で止める
                        self.assertIs(got["stop"], True)
                    else:
                        self.assertEqual(got["stops"]["collect"] if node["script"] == "collect" else got["stop_reason"], stopby.LINE_SCRIPT)
                    self.assertIn("ModuleNotFoundError", done.stderr)


class GateDecisionsCase(unittest.TestCase):
    """人の関所は 4 つで、どれも関所の文が見せる答えの語（lib/answer.py の VERBS）と approve・reject を受け、受ける語は通す語
    （answer.GO_WORDS）か止める語（VERBS のうち通す語でない物と reject。gate_answer は通す語でない答えを止めと読む）だけ。
    reject が decisions に無いと、Archon はその答えを run の取り消しとして扱い、報告が出ない"""

    def test_gates_take_the_words_their_text_prints(self):
        gates = {key: node for key, node in line_nodes().items() if "attention" in node.get("wait", {})}
        self.assertEqual(set(gates), {"gate-start", "gate-before-fix", "gate-replan", "gate-final"})
        stop_words = set(answer.VERBS) - set(answer.GO_WORDS)
        self.assertEqual(stop_words, {"stop"})
        for key, node in gates.items():
            with self.subTest(gate=key):
                self.assertEqual(node["wait"]["form"], "select")
                self.assertEqual({d["id"] for d in node["wait"]["options"]},
                                 set(answer.GO_WORDS) | set(answer.VERBS) | {answer.REJECT})


NO_FIX_WHEN = ("$judge.output.ready == false && $judge.output.stop_reason == '' "
               "|| $judge.output.ready == true && $plan-rounds.output.nothing_owed == true")


class NoFixWiringCase(unittest.TestCase):
    def test_no_fix_round_closes_the_round(self):
        """L-W07（元 line_edge.plan_edge 1107-1119）: 判定が直す単位を出さず止めてもいない周は、plan-review を形 design で差し込み
        （design-only。修正案は null）、fixed がそれを受けて最後のテスト・独立の目（設計は fixed の design）へ進める。差分が無いので
        封じず当てない（merge-seal・merge-apply の when）。最後の関所は封じの節が飛んでも開ける。飛びうる節は {from, if_skipped}"""
        nodes = line_nodes()
        only = nodes["design-only"]
        self.assertEqual((only["include"], only["when"], only["with"]["mode"], only["with"]["plan"]),
                         ("works-factory-plan-review", NO_FIX_WHEN, "design", "null"))
        self.assertIn("design-only", nodes["fixed"]["depends_on"])
        for key in ("fix", "refix", "plan", "ripple", "replan", "stop_after_fix", "design", "design_premises", "no_fix_design",
                    "no_fix_design_premises", "plan_questions", "answer"):
            self.assertIsInstance(nodes["fixed"]["with"][key], dict, key)
        self.assertEqual({key: nodes["fixed"]["with"][key] for key in ("fix", "refix")},
                         {"fix": {"from": "$fix.output", "if_skipped": None}, "refix": {"from": "$refix-run.output", "if_skipped": None}})
        self.assertEqual(nodes["eyes"]["with"]["design"], "$fixed.output.design")
        self.assertEqual(nodes["eyes"]["with"]["design_premises"], "$fixed.output.design_premises")
        self.assertEqual(nodes["eyes"]["with"]["plan_questions"], "$fixed.output.plan_questions")
        self.assertEqual(nodes["eyes"]["with"]["answers"], "$fixed.output.answer")
        self.assertIn("$fixed.output.no_fix == false", nodes["merge-seal"]["when"])
        self.assertIn("$fixed.output.no_fix == false", nodes["merge-apply"]["when"])
        self.assertEqual((nodes["ask-final"]["depends_on"], nodes["ask-final"]["trigger_rule"]),
                         (["eyes", "merge-seal"], "none_failed_min_one_success"))
        for key in ("seal", "review", "review_passes", "review_gate", "replan_review", "structure", "before_fix_answer"):
            self.assertIsInstance(nodes["ask-final"]["with"][key], dict, key)
        self.assertEqual(nodes["ask-final"]["with"]["seal"], {"from": "$merge-seal.output", "if_skipped": None})
        for key in ("depth", "answer", "replanned"):
            self.assertIsInstance(nodes["redepth"]["with"][key], dict, key)

    def test_nothing_owed_round_takes_the_no_fix_tail(self):
        """#291（元 line_edge.plan_edge 1109-1114 の空の修正）: 計画の直す義務が 0 件の周も design-only から最後のテスト・独立の目へ
        進む。判定が ready でない周は plan-rounds が飛ぶので、その欄を読む句は判定が ready の句の後（評価は偽の句で止まる）"""
        nodes = line_nodes()
        only = nodes["design-only"]
        self.assertEqual((only["depends_on"], only["trigger_rule"]), (["judge", "plan-rounds"], "none_failed_min_one_success"))
        self.assertTrue(only["when"].startswith("$judge.output.ready == false && $judge.output.stop_reason == '' || "))
        self.assertIn("$judge.output.ready == true && $plan-rounds.output.nothing_owed == true", only["when"])
        self.assertIn("nothing_owed", nodes["plan-out"]["output_format"]["required"])


class SharedPlacesWiringCase(unittest.TestCase):
    """#681: メイングラフの run の共有の置き場は、始めのノードの出力の欄から入力でブロックへ配線する（ブロックは自分の置き場の形から
    辿らない）。最後のテストは控えを引かないので印の置き場だけ。report へは collect を通す"""

    def test_shared_places_are_wired_from_start(self):
        nodes = line_nodes()
        both = {"reuse_dir": "$start.output.reuse_dir", "user_env_dir": "$start.output.user_env_dir"}
        for key in ("test-gate-base", "fix", "refix-run"):
            with self.subTest(node=key):
                self.assertEqual({k: nodes[key]["with"][k] for k in both}, both)
        for key in ("test-gate-final", "judge", "rejudge-run"):
            with self.subTest(node=key):
                self.assertEqual(nodes[key]["with"]["user_env_dir"], both["user_env_dir"])
        self.assertNotIn("reuse_dir", nodes["test-gate-final"]["with"])
        self.assertEqual(nodes["collect"]["with"]["user_env_dir"], {"from": "$start.output.user_env_dir", "if_skipped": None})
        self.assertEqual(nodes["report"]["with"]["user-env-dir"], "$collect.output.user_env_dir")
        group = {k: v for node in block_doc("works-factory-fix")["nodes"] if node["id"] in ("groups-par", "groups-seq")
                 for k, v in node["with"].items() if k in both}
        self.assertEqual(group, {"reuse_dir": "$INPUTS.reuse_dir", "user_env_dir": "$INPUTS.user_env_dir"})

    def test_plan_ports_are_wired_to_their_readers(self):
        """#681: 計画の出力の欄（修正案の役の返答 fix_plan・拒否の行 rejects・直す義務 0 件の周 nothing_owed・諦めの行 gave_up）を、
        事前審査・修正・案の直しの答えの返し・往復の終わりの返し・受け皿が受ける（隣の控えを名で開かない）"""
        nodes = line_nodes()
        loop = {n["id"]: n for n in nodes["plan-rounds"]["loop_group"]["nodes"]}
        self.assertEqual({k: loop["plan-review-run"]["with"][k] for k in ("fix_plan", "plan_rejects")},
                         {"fix_plan": "$plan.output.fix_plan", "plan_rejects": "$plan.output.rejects"})
        self.assertEqual({k: nodes["replan-review"]["with"][k] for k in ("fix_plan", "plan_rejects")},
                         {"fix_plan": "$replan.output.fix_plan", "plan_rejects": "$replan.output.rejects"})
        self.assertEqual({k: loop["plan-out"]["with"][k] for k in ("fix_plan", "rejects", "nothing_owed", "gave_up")},
                         {k: f"$plan.output.{k}" for k in ("fix_plan", "rejects", "nothing_owed", "gave_up")})
        self.assertEqual((nodes["fix"]["with"]["fix_plan"], nodes["refix-run"]["with"]["fix_plan"], nodes["answer-replan"]["with"]["fix_plan"]),
                         ("$fix-in.output.fix_plan", "$replan.output.fix_plan", "$replan.output.fix_plan"))
        self.assertEqual(fix_in.FLAT["fix_plan"], ("plan", "fix_plan"))
        for key in ("plan-rounds-out", "replan-out"):
            with self.subTest(receiver=key):
                self.assertLessEqual({*planfile.PORTS, *planfile.FROM}, set(nodes[key]["with"]["names"].split()))
        for key in ("replan-review-out", "design-only-out"):
            with self.subTest(receiver=key):
                self.assertIn("gave_up", nodes[key]["with"]["names"].split())


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
        """with: を持つ線の script の節の全部を、with: の鍵の全部を "null" にして走らせ、
        読んだ INPUTS_<名> を控える"""
        nodes = {key: node for key, node in line_nodes().items()
                 if "script" in node and node.get("with")}
        self.assertIn("judge-out", nodes)
        self.assertIn("ask-before-fix", nodes)
        for key, node in nodes.items():
            with self.subTest(node=key), tempfile.TemporaryDirectory() as tmp:
                env = Recorded(WORKFLOW_ID=RUN, ARTIFACTS_DIR=tmp, **{f"INPUTS_{name.upper()}": "null" for name in node["with"]})
                with mock.patch.object(os, "environ", env), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    runpy.run_path(str(SCRIPTS / f"{node['script']}.py"), run_name="__main__")
                self.assertEqual({name for name in env.read if name.startswith("INPUTS_")},
                                 {f"INPUTS_{name.upper()}" for name in node["with"]})

    def test_receivers_return_every_with_key_and_nothing_else(self):
        """受け皿（returned）の with: は、ちょうど {got, names}（返りまるごとと、運ぶ欄の名）で、got は names の欄だけを持つ。Archon が
        同じく INPUTS_<名> で渡す線の inputs: は欄にしない"""
        run_inputs = {f"INPUTS_{name.upper()}": "x" for name in LINE["inputs"]}
        for key, node in line_nodes().items():
            if node.get("script") != "returned":
                continue
            with self.subTest(node=key):
                self.assertEqual(set(node["with"]), {"got", "names"})
                env = run_inputs | {"INPUTS_GOT": json.dumps({"a": 1}), "INPUTS_NAMES": node["with"]["names"]}
                with mock.patch.dict(os.environ, env):
                    self.assertEqual(list(returned.returned()["got"]), node["with"]["names"].split())

    ROUNDS = {"plan-rounds-out": plan_out.PLAN, "plan-rounds-review-out": plan_out.REVIEW}

    def test_receiver_body_is_written_once(self):
        """受け皿の本体（script・runtime・timeout・output_format）は YAML の字に 1 度だけ在り、ほかの受け皿はアンカーで受ける"""
        self.assertEqual(len(re.findall(r"^\s*script: returned\s*$", LINE_TEXT, re.M)), 1)
        self.assertEqual(sum(node.get("script") == "returned" for node in line_nodes().values()), 13)

    def test_receivers_take_every_field_of_what_they_receive(self):
        """受け皿は、受ける節の出力をまるごとの got: $<dep>.output で受け、運ぶ欄の names の組はブロックの返す節の output_format の
        欄と同じ。計画の往復の 2 本の names の組は plan_out の PLAN と REVIEW と同じ（names の名を消すか受け皿の鍵を向け違えると、その欄が
        黙って報告から落ちる）"""
        nodes = line_nodes()
        for key, node in nodes.items():
            if node.get("script") != "returned":
                continue
            with self.subTest(node=key):
                dep = node["depends_on"][0]
                self.assertEqual(node["with"]["got"], f"${dep}.output")
                if key in self.ROUNDS:
                    self.assertEqual(node["with"]["names"].split(), list(self.ROUNDS[key]))
                    continue
                self.assertIn("include", nodes[dep])
                doc = block_doc(nodes[dep]["include"])
                returns = next(n for n in doc["nodes"] if n["id"] == doc["returns"])
                self.assertEqual(sorted(node["with"]["names"].split()), sorted(returns["output_format"]["properties"]))

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
                    self.assertEqual(receiver["script"], "returned")
                    self.assertEqual((receiver["depends_on"], receiver.get("trigger_rule")), ([key], None))
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
    CHECK_ONLY = "check だけの入力（差分の根の版。線の seal と apply は始めの記録の base_rev を読む）"
    GROUP_ONLY = "組の子の run だけの入力（fix が組ごとの並べのために自分を子の run として起こす時に渡す）"
    UNPASSED = {
        ("merge-seal", "answer"): APPLY_ONLY,
        ("merge-seal", "r2"): APPLY_ONLY,
        ("merge-seal", "sealed_hash"): APPLY_ONLY,
        ("merge-seal", "deliver"): APPLY_ONLY,
        ("merge-seal", "request"): APPLY_ONLY,
        ("merge-seal", "base_rev"): CHECK_ONLY,
        ("merge-apply", "base_rev"): CHECK_ONLY,
        ("fix", "mode"): GROUP_ONLY,
        ("fix", "group"): GROUP_ONLY,
        ("fix", "from_tree"): GROUP_ONLY,
        ("fix", "out_dir"): GROUP_ONLY,
        ("refix-run", "mode"): GROUP_ONLY,
        ("refix-run", "group"): GROUP_ONLY,
        ("refix-run", "from_tree"): GROUP_ONLY,
        ("refix-run", "out_dir"): GROUP_ONLY,
        ("fix", "only_items"): "1 回目は全部の項目（refix-run だけが 1 回目の replan_items を渡す）",
        ("fix", "prior_conflicts"): "1 回目の段は前の段の申し出が無い（refix-run だけが 1 回目の conflicts を渡す）",
        ("fix", "notes"): "機械の申し送りは案の直しの後の 2 度目の修正だけ（refix-run だけが answer-replan の fix_notes を渡す）",
        ("plan-review-run", "conflicts"): "修正の前なので申し出が無い",
        ("plan-review-run", "gate_answers"): "修正前の承認ノードより前に走る",
        ("plan-review-run", "mode"): "計画の往復の事前審査は形が空（既定）",
        ("replan-review", "round_limit"): "案の直しの事前審査は往復のループの外で、ループの上限が無い",
        ("replan-review", "mode"): "案の直しの事前審査は形が空（既定）。形 design は直す物が無い周の design-only だけ",
        ("replan-review", "head_depth"): "形 replan は事前審査を木にしない（boardview.open_pass の tree は形 review だけ）",
        ("design-only", "head_depth"): "形 design は事前審査を回さず木を決めない",
        ("design-only", "ruling"): "直す物が無い周は修正案を読まない形 design（裁定が無い）",
        ("design-only", "conflicts"): "直す物が無い周は修正の段が無いので申し出が無い",
        ("design-only", "gate_answers"): "直す物が無い周は修正前の承認ノードが無い",
        ("design-only", "round_limit"): "形 design は往復のループの外で、ループの上限が無い",
        ("design-only", "fix_plan"): "形 design は修正案を読まない（boardview.open_design）",
        ("design-only", "plan_rejects"): "形 design は修正案を読まないので計画の周の拒否も無い",
        ("test-gate-final", "reuse_dir"): "最後のテストは試験の結果の控えを引かない（test-gate の run は base だけ引く）",
        **{("design-only", name): "形 design は修正案を読まず事前審査を回さないので、素材の状態・並行 PR の外した範囲・依頼の解き方の控えを使わない"
           for name in ("materials", "pr_excluded", "purpose_means")},
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
        """落とし穴 K11: ブロックの入力のうち docs/design.md の「サブグラフの出力の約束」の入力（「入力（`with:`）:」の箇条）の外の物は
        既定値を持つ（既定値の無い入力は include する全部の工程の読み込みを落とす。Archon の include-expander.ts の resolveIncludeInputs）"""
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

    # 2 度差し込むが置き場を分けないブロック: plan-review は案の直しの差し込みが前の差し込みの承認済みの項目を読む（boardview.view の
    # 「同じ run の往復と案の直しを同じ周に積む」）ので置き場 plan-review/ を共にし、差し込みの形は with: の ruling で分ける
    SHARED_PLACE = {"works-factory-plan-review": ("ruling", "mode")}

    def test_twice_included_blocks_use_their_own_place(self):
        """落とし穴 K14: 線が 2 度差し込むブロック（YAML から数える）の全部で、置き場を決める関数に 2 つの include の id か形（with: の
        値）を渡すと違う置き場が返る（2 度目が 1 度目の置き場の物を今回の物として拾わない）。関数: judge は lib/judge_accept.verdict
        （異議の有無で judge/・rejudge/）、plan は lib/planfile.open_round（周ごとの plan/r<k>/）、fix は workflows/.shared/boundary.place("fix")
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
                    forms = [json.dumps([nodes[key]["with"].get(f) for f in self.SHARED_PLACE[block]]) for key in keys]
                    self.assertEqual(len(set(forms)), len(keys), forms)
                    continue
                self.assertNotEqual(*places[block]([nodes[key] for key in keys], keys))

    def judge_places(self, includes, keys) -> list:
        self.assertEqual([node["with"]["objection"] for node in includes], ["", "$fixed.output.objection"])
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
        boundary = load_file("boundary", SCRIPTS.parents[1] / ".shared" / "boundary.py")
        with tempfile.TemporaryDirectory() as tmp:
            places = []
            for include in keys:
                env = {"ARTIFACTS_DIR": tmp, "ARCHON_NODE_EXECUTION": json.dumps({"path": f"{include}__fix-prep"})}
                with mock.patch.dict(os.environ, env):
                    places.append(boundary.place("fix"))
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
                env = {"WORKFLOW_ID": RUN, "ARTIFACTS_DIR": str(artifacts), "WORKS_FACTORY_ROOT": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
                env.update({f"INPUTS_{name.upper()}": "null" for name in block_doc("works-factory-merge")["inputs"]})
                env.update({"INPUTS_MODE": mode, "INPUTS_START": json.dumps({"type": "archon_artifact", "run_id": RUN, "path": "start.json"}),
                            "INPUTS_SEALED_HASH": sealed})
                env = hermetic.child_env(**env)
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
                         {"plan": "$fix-in.output.plan", "ripple": "$fix-in.output.ripple",
                          "depth": "$fix-in.output.depth", "answers": "$fix-in.output.answer"})
        self.assertNotIn("only_items", nodes["fix"]["with"])
        self.assertEqual({k: nodes["refix-run"]["with"][k] for k in ("plan", "ripple", "depth", "answers", "only_items")},
                         {"plan": "$replan.output.plan", "ripple": "$answer-replan.output.fix_ripple", "depth": "$replan.output.depth",
                          "answers": "$answer-replan.output.fix_answers", "only_items": "$fix.output.replan_items"})

    def test_refix_gets_only_the_ruled_items(self):
        """L-D36: 2 度目の修正の直す義務は、案を直して戻った項目だけ（only_items ← 1 回目の replan_items。fix は項目の単位だけを直す:
        tests/workflows/test_fix.py の test_prep_only_items_keeps_their_units）。1 回目の修正には渡さない"""
        nodes = line_nodes()
        self.assertEqual(nodes["refix-run"]["with"]["only_items"], "$fix.output.replan_items")
        self.assertNotIn("only_items", nodes["fix"]["with"])
        self.assertEqual(nodes["refix-run"]["when"], "$answer-replan.output.go == true")

    def test_second_round_plan_gets_the_review(self):
        """L-D17: 計画の往復の 2 周目の plan は、前の周の事前審査の返り review（plan-out が plan-review-run から受け直した物）を
        $LOOP_PREV で受けて案を直す（元 converge.revise_section :538）。筋書きは輪を 1 周で終え前の周の値を渡さない（docs/design.md の U3。
        止めた Archon の packages/workflows/src/dry-run.ts の executeCodeNode の `loopPrevOutput: ''`・simulateLoopGroup）ので、2 周目の値は段 1 の本物の run で見る。ブロックの側は
        tests/workflows/test_plan.py の CollectCase.test_rounds_count_and_second_round_gets_review"""
        nodes = line_nodes()
        self.assertEqual(nodes["plan"]["with"]["review"], "$LOOP_PREV.plan-out.output.review")
        self.assertEqual(nodes["plan-out"]["with"]["review"], {"from": "$plan-review-run.output.review", "if_skipped": None})

    def test_eyes_get_the_raised_depth(self):
        """L-D11: 独立の目は直した後に上げ直した深さ（redepth の返り）を受け、全部の単位が軽量のままなら削除候補と R1〜R4 を省く（目の
        ブロックの prep が depth.skip_reason で決める。tests/workflows/test_eyes.py の test_prep_all_light_turns_eyes_off）。筋書きは
        include の入力を目の script に渡さない（docs/design.md の U3）ので、深さで目が省かれる道はここと目のブロックの試験で照らす"""
        self.assertEqual(line_nodes()["eyes"]["with"]["depth"], "$redepth.output.depth")
        self.assertEqual(line_nodes()["eyes"]["depends_on"], ["test-gate-final"])
        self.assertIn("redepth", json.dumps(line_nodes()["test-gate-final"]))

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
        self.assertEqual(line_nodes()["replan-review"]["with"]["gate_answers"], "$fix-in.output.answer")

    def test_plan_review_gets_conflicts_and_gate_answers(self):
        """P152・L-W45: 事前審査の差し込みのうち、修正の後に走る replan-review には申し出と関所の答えの両方が届き、修正前の関所より前に
        走る往復の中の plan-review-run には渡さない（まだ無い。UNPASSED に訳つき）"""
        nodes = line_nodes()
        self.assertLessEqual({"conflicts", "gate_answers"}, set(nodes["replan-review"]["with"]))
        self.assertFalse({"conflicts", "gate_answers"} & set(nodes["plan-review-run"]["with"]))
        self.assertEqual({name for key, name in self.UNPASSED if key == "plan-review-run"}, {"conflicts", "gate_answers", "mode"})
        self.assertEqual({name for key, name in self.UNPASSED if key == "replan-review"},
                         {"mode", "round_limit", "head_depth"},
                         "申し出と関所の答えは渡す（mode は直す物が無い周の design-only だけ）")
        self.assertEqual(nodes["plan-review-run"]["with"]["head_depth"], "$judge.output.depth")
        self.assertNotIn("head_depth", nodes["replan-review"]["with"])
        self.assertNotIn("head_depth", nodes["design-only"]["with"])
        self.assertNotIn("plan-review-due", nodes)
        self.assertNotIn("plan-review-due", nodes["plan-review-run"]["depends_on"])
        self.assertNotIn("depth_skip", json.dumps(nodes))
        self.assertNotIn("review_skipped", json.dumps(nodes))
        self.assertEqual(nodes["judge-out"]["with"]["got"], "$judge.output")

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
        self.assertEqual(len(includes), 15)
        self.assertEqual(includes & body_ids(LINE["nodes"]), set())

    def test_report_reruns_on_resume(self):
        """L-W60: 報告はいつも走る。collect・report・result は前の段が落ちても飛ばされても走り（all_done）、Archon の resume でも collect と
        result は回し直す（always_run。元 works/darkfactory/darkfactory.yaml 1314-1322 行・works/tests/test_line_wiring.py の
        ReportAfterFailureCase.test_report_reruns_on_resume）。report は include で、Archon は include の always_run を捨てる
        （止めた Archon の packages/workflows/src/schemas/dag-node.ts の INCLUDE_NODE_IGNORED_FIELDS と、dagNodeSchema の transform の include の枝）ので、回し直した collect の返りが
        変わった時に Archon が report の中の節の控えを捨てて回し直す（dag-executor.ts の getStaleCachedDependencies）。
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
        always_run を付けない（止めた Archon の packages/workflows/src/dag-executor.ts の priorCompletedNodes）"""
        self.assertNotIn("always_run", line_nodes()["start"])

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
        ("fixing（DF:629 open_units ← h-fix）", "fix", "units", "$fix-in.output.units"),
        ("fixing（DF:628 judgment_file ← h-fix）", "fix", "judgment", "$fix-in.output.judgment"),
        ("replanning（DF:687-696。盤面の判定を読む）", "replan", "units", "$fix-in.output.units"),
        ("replanning（DF:687-696）", "replan", "judgment", "$fix-in.output.judgment"),
        ("replanning の事前審査（DF:687-696。blk-plan の中）", "replan-review", "units", "$fix-in.output.units"),
        ("replanning の事前審査（DF:687-696）", "replan-review", "judgment", "$fix-in.output.judgment"),
        ("refitting（DF:810 open_units ← h-refit）", "refix-run", "units", "$fix-in.output.units"),
        ("refitting（DF:809 judgment_file ← h-refit）", "refix-run", "judgment", "$fix-in.output.judgment"),
        # L-W11 修正案と波及の一覧と深さを修正へ渡す（EDGE:1217-1226・:163 _ripple_file）
        ("fixing（DF:630 plan_file ← h-fix）", "fix", "plan", "$fix-in.output.plan"),
        ("fixing（DF:637 ripple_file ← h-fix）", "fix", "ripple", "$fix-in.output.ripple"),
        ("fixing（DF:636 unit_depths ← h-depth）", "fix", "depth", "$fix-in.output.depth"),
        ("refitting（DF:811 plan_file ← h-refit。差し替えた承認済みの案）", "refix-run", "plan", "$replan.output.plan"),
        ("refitting（DF:817 ripple_file ← h-refit。EDGE:169 refit_ripple_file の作り直した一覧）", "refix-run", "ripple",
         "$answer-replan.output.fix_ripple"),
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
        ("h-redepth（DF:885 replanned ← h-replan.go）", "redepth", "replanned", {"from": "$after-fix.output.replan", "if_skipped": None}),
        ("h-redepth（DF:886 rejudged ← h-rejudge.go。再審は 2 度目の修正の後で、fixed が決める）", "redepth", "rejudged",
         "$fixed.output.rejudge"),
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
        # 部分 C・D1・D2 が配線した受け渡し（前は MISSING に在った）
        ("refitting が 1 回目の申し出と裁定を見る（works/.shared/core/conflict.py:411-414 second_pass・works/blk-fix/lib/fixgates.py:103。S01）",
         "refix-run", "prior_conflicts", "$fix.output.conflicts"),
        ("差分の審査役の材料 out.p2.plan_review（works/.shared/core/graphloops/graphs/review-loop.json:4163・"
         "works/blk-delta/commands/delta-review.md:8。S02）", "fix", "plan_review", "$fix-in.output.review"),
        ("同じく 2 度目の修正の差分の審査（S02）", "refix-run", "plan_review", "$replan-review.output.review"),
        ("独立の目の x_scalars（盤面の修正役の返答。S09）", "eyes", "x_scalars", "$fixed.output.x_scalars"),
        ("h-final の breaks.accepted（EDGE:814-815 _final_needs・:719-723 _handoff_text・:868。works/.shared/core/report.py:304-314。S03）",
         "ask-final", "handoffs", "$fixed.output.handoffs"),
        ("report の depth ← h-redepth（DF:1330。S30・S53）", "collect", "redepth", {"from": "$redepth.output", "if_skipped": None}),
        ("report の前の失敗（DF:1307-1308 の prior-failures.json。盤面の prior-failures-in.json。S49）", "collect", "prior_failures",
         {"from": PRIOR, "if_skipped": None}),
    ]
    # 元に在って今の線に無い受け渡し: (元の受け手と元の在り処, 今の id, 今なら読むはずの源の字, 閉じる部分)。今は無い
    MISSING = []

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
        self.assertEqual(given, {key for _, key, name, want in self.HANDOFFS if name == "prior_failures" and want == PRIOR})


if __name__ == "__main__":
    unittest.main()

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
plan_review_due = load("plan_review_due")
after_fix = load("after_fix")
judged = load("judged")
fixed = load("fixed")
redepth = load("redepth")
returned = load("returned")
collect = load("collect")
result = load("result")
sweep_children = load("sweep_children")

import answer  # noqa: E402  （線の script が lib/ と境の口の置き場を sys.path に足した後に読む）
import boardview  # noqa: E402
import boundary  # noqa: E402
import conflict  # noqa: E402
import converge  # noqa: E402
import fixbeside  # noqa: E402
import fixboard  # noqa: E402
import gatemarks  # noqa: E402
import judge_accept  # noqa: E402
import planfile  # noqa: E402
import policy  # noqa: E402
import querytest  # noqa: E402
import replan  # noqa: E402
import seal  # noqa: E402
import startrec  # noqa: E402
import stopby  # noqa: E402

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


def line_nodes(nodes=None) -> dict:
    """線の節（loop_group の中の節も）を id ごとに"""
    got = {}
    for node in LINE["nodes"] if nodes is None else nodes:
        got[node["id"]] = node
        got.update(line_nodes(node["loop_group"]["nodes"]) if "loop_group" in node else {})
    return got


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
                          ({"request": "request_ok.json", "thickness": "重厚"}, "足すノードがまだ無い"),
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
                self.assertEqual((got["ok"], got["stop_reason"], got["ask"]), (False, stopby.START_REFUSED, False), got)
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
        self.assertIn("最後の承認ノード: when_needed", text)
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
                         {"ripple": "$replan.output.ripple", "first_ripple": "$plan-rounds.output.ripple"})

    def test_refix_answers_carry_the_non_human_faces_of_taken_items(self):
        """P144・L-D35・L-W17: 2 度目の修正に、採った項目ごとの事前審査の穴のうち人に聞く種類でない物を見出しつきで渡す（元
        works/.shared/core/replan.py:688-693 の _notes の 3 つ目）。人に聞く種類（regression・policy）は関所が聞くので渡さず、人の答え
        fix_answers には混ぜない。止める答えでは渡さない"""
        (self.artifacts / "replan").mkdir()
        (self.artifacts / "replan" / "p2.fix_plan.json").write_text(json.dumps(
            {"plan": [{"unit_keys": ["u1", "u2"]}, {"unit_keys": ["u3"]}]}), encoding="utf-8")
        (self.artifacts / "replan-review").mkdir()
        faces = [{"key": "穴-分母", "kind": "contract_drift", "where": "stats.py", "why": "空の列で割れる", "unit_keys": ["u2"]},
                 {"key": "穴-後退", "kind": "regression", "where": "stats.py", "why": "前の呼び手が壊れる", "unit_keys": ["u1"]},
                 {"key": "穴-ほかの項目", "kind": "entrance", "where": "bounds.py", "why": "入口が増える", "unit_keys": ["u3"]}]
        (self.artifacts / "replan-review" / "review.json").write_text(json.dumps({"faces": faces}, ensure_ascii=False), encoding="utf-8")
        ptr = lambda rel: json.dumps({"type": "archon_artifact", "run_id": RUN, "path": rel})
        got = replan_answer.take(json.dumps({"decision": "continue", "text": "x"}), "true", "", "null", "gate-replan", self.artifacts,
                                   None, ptr("replan-review/review.json"), ptr("replan/plan-fields.json"), '["1"]')
        self.assertEqual(got["fix_notes"], f"{replan.FACES_HEAD.format(item='1', units='u1、u2')}\n\n"
                                           "- [contract_drift] 穴-分母（stats.py）: 空の列で割れる\n")
        self.assertNotIn("穴-分母", got["fix_answers"]["text"])
        stopped = replan_answer.take(json.dumps({"decision": "stop", "text": "x"}), "true", "", "null", "gate-replan", self.artifacts,
                                       None, ptr("replan-review/review.json"), ptr("replan/plan-fields.json"), '["1"]')
        self.assertEqual(stopped["fix_notes"], "")
        nodes = line_nodes()
        self.assertEqual(nodes["refix-run"]["with"]["notes"], "$answer-replan.output.fix_notes")
        self.assertEqual({k: nodes["answer-replan"]["with"][k] for k in ("review", "plan", "items")},
                         {"review": {"from": "$replan-review.output.review", "if_skipped": None}, "plan": "$replan.output.plan",
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
        self.assertEqual(line_nodes()["fix"]["with"]["answers"], "$answer-before-fix.output.answer")
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
        for place, word, want in (("gate-final", "stop", answer.FINAL_STOP_NOTE), ("gate-before-fix", "reject", answer.STOP_NOTE),
                                  ("gate-start", "stop", answer.STOP_NOTE)):
            with self.subTest(place=place, word=word):
                got = gate_answer.take(json.dumps({"decision": word, "text": " "}), "true", "", place, self.artifacts)
                self.assertEqual(got["answer"]["text"], want)
                self.assertEqual(json.loads((self.artifacts / "gates" / f"{place}.json").read_text(encoding="utf-8"))["text"], want)
        self.assertEqual((answer.STOP_NOTE, answer.FINAL_STOP_NOTE), ("承認ノードで止めた", "最後の承認ノードで止めた"))
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

    def test_dry_run_approval_reads_as_approve(self):
        got = gate_answer.take(answer.DRY_RUN_APPROVED, "true", "", "gate-start", self.artifacts)
        self.assertEqual(got, {"go": True, "answer": {"decision": "approve", "text": "", "asked": []}, "stop_reason": ""})


def planned(**kw) -> dict:
    got = {"ready": True, "pass": True, "stalled": False, "round": 1, "ask_human": False,
           "gate_axes": {key: {"ok": True, "note": ""} for key in ask_before_fix.AXES}, "questions": []}
    got.update(kw)
    return got


class AskBeforeFixCase(unittest.TestCase):
    def ask(self, plan, unattended=False, design_only=False):
        return ask_before_fix.ask(plan, unattended=unattended, design_only=design_only, run_id=RUN)

    def test_no_plan_goes_nowhere(self):
        self.assertEqual(self.ask(planned(ready=False)), {"open": False, "go": False, "stop_reason": "", "text": "", "deferred": [],
                                                           "asked": []})

    def test_clean_plan_goes_to_fix_without_the_gate(self):
        self.assertEqual(self.ask(planned()), {"open": False, "go": True, "stop_reason": "", "text": "", "deferred": [], "asked": []})

    def test_reasons_that_open_the_gate(self):
        failing = {**planned()["gate_axes"], "clean": {"ok": False, "note": "名前が合わない"}}
        for plan, words in ((planned(gate_axes=failing), "汚くない（clean）の軸が通らない: 名前が合わない"),
                            (planned(questions=[gatemarks.question_row("fork", "0 を返すか")]), "0 を返すか"),
                            (planned(ask_human=True), "直す前の承認ノード"),
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
        got = self.ask(planned(questions=[gatemarks.question_row("fork", "0 を返すか")], ask_human=True), unattended=True)
        self.assertEqual(got, {"open": False, "go": True, "stop_reason": "", "text": "", "deferred": ["0 を返すか"], "asked": []})

    def test_unattended_stops_where_the_gate_would_open(self):
        got = self.ask(planned(**{"pass": False, "stalled": True}), unattended=True)
        self.assertEqual((got["open"], got["go"], got["stop_reason"]), (False, False, stopby.NEEDS_HUMAN))

    def test_unattended_design_only_stops(self):
        """L-G27: 無人で設計だけの run は、関所で止まって報告へ進む（開かず・修正へ進まず・needs-human）"""
        got = self.ask(planned(), unattended=True, design_only=True)
        self.assertEqual((got["open"], got["go"], got["stop_reason"]), (False, False, stopby.NEEDS_HUMAN))

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
        self.assertIn("承認ノードはいつも開く設定", got["text"].splitlines()[0])

    def test_protected_hits_and_conflicts_open_in_every_mode(self):
        for mode in ("when_needed", "protected_only"):
            for got in (self.got(protected_hits=["tests/x.py"]), self.got(asked=["u1: 人に回した"]),
                        self.got(conflicts_unread=["fix/conflicts.json: 読めない"]), self.got(allowed_tests=[{"path": "tests/t.py", "permit": "plan-1", "source": "plan"}])):
                with self.subTest(mode=mode, got=got["protected_hits"] or got["asked"] or got["conflicts_unread"] or got["allowed_tests"]):
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
            returns = ask_final.judged_returns({"units": [{"id": "u1"}, {"id": "u2"}], "first_units": [{"id": "u1"}], "judgment": ptr,
                                                "ties_judgment": None, "rejudged": True, "rejudge_verdict": "退ける", "objection": "異議",
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
        ファイル・残りの件数（目の阻害と結果が無い目）と、clean・レンズ・仕組みの異常の行（修正の diff の隣の控え。fixbeside.always_rows）を並べる"""
        got = self.got(unproven=["u1: 例が無い"], amend=["案の項目 1: 直した——人が承認した"],
                       split="修正の段は 1 単位（u1）を受け、1 単位（u2）を止めて持ち越した", deleted=["old.py"],
                       always=["clean が消したファイル（fix）: 0 本", fixbeside.ANOMALY_LINE],
                       eyes={**self.got()["eyes"], "r3": {"status": "redesign-needed", "reason": ""}, "r4": None})
        text = ask_final.final_text(got, [], RUN)
        for want in (f"## {querytest.UNPROVEN_HEAD}（1 件）", "- u1: 例が無い", f"## {replan.AMEND_HEAD}（1 件）", "- 案の項目 1: 直した",
                     f"- {seal.DELETED_HEAD}: old.py", "独立の目の阻害 1 件（R3）・結果が無い目 1 件（R4）",
                     "- clean が消したファイル（fix）: 0 本", f"- {fixbeside.ANOMALY_LINE}"):
            self.assertIn(want, text)
        self.assertIn("1 単位（u2）を止めて持ち越した", text.splitlines()[0])
        self.assertEqual(replan.amend_lines(["1"], refixed=False), [f"案の項目 1: 直さずに諦めた: {replan.NOT_RUN_WHY}"])
        approved = {"decision": "continue", "text": "", "asked": ["項目 2: 約束の欄が変わった（allowed_paths）"]}
        self.assertEqual(replan.amend_lines(["2", "3"], refixed=True, answer=approved),
                         ["案の項目 2: 直した——人が承認した", "案の項目 3: 直した——聞かずに通した（手段の欄だけ）"])


class AskFinalReadsCase(Artifacts):
    """最後の関所が指し札の先から読む物: 判定の保留の問い（judgment.json）と直した後の実測（structure-after.json）"""

    def place(self, rel, doc):
        path = self.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return {"type": "archon_artifact", "run_id": RUN, "path": rel}

    def judgment(self, questions, units=("u1",)):
        return self.place("judge/judgment.json", {"units": [{"key": k} for k in units], "questions": questions})

    def held(self, questions, *, answers=(), before_fix=None, asked=(), units=("u1",), ties=None, materials=None, notes=()):
        start_ptr = self.place("start.json", {"answers": list(answers)})
        before_fix = {**before_fix, "asked": list(asked)} if isinstance(before_fix, dict) else before_fix
        if materials is not None:
            self.place(f"judge/{gatemarks.MATERIALS_FILE}", materials)
        first = None if ties is None else self.place("judge-first/judgment.json", {})
        if ties is not None:
            self.place(f"judge-first/{gatemarks.BESIDE[0]}", {"rounds": {"1": ties}})
        b, unread = ask_final.ledger(self.judgment(questions, units), ask_final.start_doc(start_ptr)[0], before_fix, first)
        self.assertEqual(unread, list(notes))
        return gatemarks.held_lines(b)

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
        """L-G34: 依頼の answers は key か出どころの字の一致で 1 つの問いだけに当たる時に答えに数える（gatemarks.binds の 1 つの式）。
        判定の結び（1 回目の判定の隣の answer-ties.json。線は ties_judgment で渡す）と測れていない素材の名（判定の隣の materials.json）
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
        self.assertEqual(line_nodes()["ask-final"]["with"]["ties_judgment"], "$judge.output.judgment")

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
        self.assertEqual(line_nodes()["ask-final"]["with"]["structure"], {"from": "$plan-rounds.output.structure", "if_skipped": None})

    def test_failed_structure_reaches_the_gate_text_from_the_with_keys(self):
        """L-W09: 計画の構造の目が落ちた周は、ノード ask-final が with: の structure（$plan-rounds.output.structure）の先を読み、開いた
        最後の承認ノードの文に「構造のブロック: …」の行が届く（with: の鍵を読むかだけでなく、文まで）"""
        ptr = self.place("plan/structure/structure-state.json", {"status": "failed", "reason": "構造の目の役が落ちた",
                                                                  "design_file": "", "wall_s": 0})
        env = {f"INPUTS_{name.upper()}": "null" for name in line_nodes()["ask-final"]["with"]}
        env.update({"INPUTS_STRUCTURE": json.dumps(ptr), "INPUTS_FINAL_GATE": "always", "INPUTS_UNATTENDED": "false",
                    "INPUTS_TESTS_OK": "true", "INPUTS_GREEN": "true", "INPUTS_SEALED": "true"})
        with mock.patch.dict(os.environ, env):
            out = ask_final.ask(**ask_final.from_env())
        self.assertTrue(out["open"], out)
        self.assertIn("- 構造のサブグラフ: 構造の目の行なしで計画した（理由: 構造の目の役が落ちた）", out["text"])

    def test_fix_beside_files_reach_the_final_gate(self):
        """F013・F041・F312・F329・L-W20・L-W21（S03・S28・S29）: 最後の関所は修正の段ごとの diff の隣の控え（fixed の diffs。
        1 回目と 2 度目の修正の両方）を読み、申告と合わない単位・回さなかった試験・確かめずに受けた回・穴の名札と手直しの結果・
        clean とレンズを並べる。修正役が人に回した物は fixed の handoffs から並べる。読めないファイルは訳にする"""
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
        got = ask_final.fix_beside(diffs)
        self.assertIn("  - 穴1: 項目 1", got["branch_rows"])
        self.assertEqual([x.split("（")[0] for x in got["closure"]], ["u-fix: 閉じていない", "u-refix-run: 閉じていない"])
        self.assertIn("  - t_refix-run.py", got["tests_left"])
        self.assertEqual(got["gates"], ["事後の関門の束: 受け付け 2 回が受け入れのテストの赤緑を確かめずに通した（理由: 実行器が無い）"])
        self.assertIn("clean が消したファイル（refix-run）: 1 本", got["always"])
        self.assertEqual(got["always"][-1], fixbeside.ANOMALY_LINE)
        self.assertEqual(len(got["beside_unread"]), 1)
        self.assertIn(fixboard.LENSES_FILE, got["beside_unread"][0])
        self.assertEqual(line_nodes()["ask-final"]["with"]["fix_diffs"], "$fixed.output.diffs")
        self.assertEqual(line_nodes()["ask-final"]["with"]["handoffs"], "$fixed.output.handoffs")
        handoffs = ["u-fix: 壊すと分かって通した——古い呼び手が壊れる"]
        text = ask_final.final_text(final_got(handoffs=handoffs, **got), [], RUN)
        for want in ("- 修正の受け付けが手元で回さなかった試験（2 件", "- 事後の関門の束: 受け付け 2 回", "- clean が消したファイル（fix）: 1 本",
                     "  - build/x.o", "u-fix: 壊すと分かって通した——古い呼び手が壊れる", f"- {fixbeside.branch_head(1)}: 1 件（",
                     "  - 穴1: 直した（fixed）——直した", f"## {ask_final.BESIDE_UNREAD}（1 件"):
            self.assertIn(want, text)

    def test_unreadable_fix_beside_opens_the_gate(self):
        """errors F1: 修正の段の控えを読めない時は、人に回した物と数え直しの食い違いを数えられないので、開き方に依らず関所を開け、
        無人の run は開かずに止める（黙って merge-apply へ進めない）"""
        got = final_got(beside_unread=["修正の控え x/closure.json を組めなかった（e）"])
        self.assertIn((f"{ask_final.BESIDE_UNREAD}（1 件。人に回した物・数え直しの食い違いを数えられない）", True), ask_final.needs(got))
        self.assertTrue(ask_final.ask(got, mode="when_needed", unattended=False, run_id=RUN)["open"])
        self.assertEqual(ask_final.ask(got, mode="when_needed", unattended=True, run_id=RUN)["stop_reason"], stopby.NEEDS_HUMAN)

    def test_final_gate_lists_the_r2_premise_inputs(self):
        """E45・E66・E37（S12）: 独立の目の返り notes（premise-inputs.json）の隣から、R2 の行の下に「渡されていない」と書いた文・
        そのうち渡していた物（claims_given）・2 つの役に渡した前提と渡していない物・独立設計の後の答え（元 line_edge._r2_inputs）を、
        修正前の関所で通した行に「人が通したので R4 で聞き直さなかった行」（r4-gate-passes.json）を、前提の検算の行の下に偽と分かった
        仮定の問いと次の run の制約に足す実測（premise-check.json）を並べる。notes が null なら控えが無いと言う"""
        import eyeverdict
        notes = self.place(f"eyes/{eyeverdict.PREMISE_INPUTS}", {
            "design": {"given": [{"kind": "制約", "what": "上限 10"}], "withheld": [{"kind": "人の答え", "what": "x", "why": "後に来た"}]},
            "compare": {"given": [], "claims_given": [{"claim": "上限", "kind": "制約", "what": "上限 10"}], "after_design": ["continue"]},
            "claims": ["上限が渡されていない"]})
        self.place(f"eyes/{eyeverdict.GATE_PASSES}", [{"node": gatemarks.R4_GATE_NODE, "round": 1, "by": gatemarks.PASSED_BY_HUMAN,
                                                       "item": "R4 が BASE から消えたと見た能力: 古い入口",
                                                       "passed_at": {"node": gatemarks.GATE_NODE, "round": 1}}])
        self.place("eyes/premise-check.json", {"key": "上限を持つか", "verdict": "resolved", "reason": "在る", "resolution": "10",
                                               "facts_to_add": ["上限は 10"]})
        got = ask_final.eye_notes(notes)
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
        self.assertEqual(ask_final.eye_notes(None)["r2_inputs"],
                         ["独立の設計と比べる目に渡した入力の控えが無い（独立の目の出力 notes が null）"])
        self.assertEqual(line_nodes()["ask-final"]["with"]["eye_notes"], "$eyes.output.notes")
        self.assertEqual(line_nodes()["eyes-out"]["with"]["got_notes"], "$eyes.output.notes")

    def test_allowed_tests_come_from_beside_both_diffs(self):
        """許したテストの変更は fix と refix-run の差分の隣の allowed-tests.json を読み、許しの id と出どころつきで並べる（重ねない）。
        開き方に依らず関所を開ける"""
        row = {"path": "tests/test_a.py", "permit": "plan-1", "source": "plan"}
        fix = self.place("fix/fix/fix.diff", "")
        self.place("fix/fix/allowed-tests.json", [row])
        refix = self.place("fix/refix/fix.diff", "")
        self.place("fix/refix/allowed-tests.json", [row, {"path": "tests/test_b.py", "permit": "r-2", "source": "ruling"}])
        rows = ask_final.fix_beside([fix, refix])["allowed_tests"]
        self.assertEqual([r["path"] for r in rows], ["tests/test_a.py", "tests/test_b.py"])
        self.assertEqual(ask_final.fix_beside([fix])["allowed_tests"], [row])
        got = final_got(allowed_tests=rows)
        text = ask_final.final_text(got, ask_final.final_needs(got), RUN)
        self.assertIn(f"## {ask_final.ALLOWED_TESTS_HEAD}（2 件", text)
        self.assertIn("- tests/test_b.py（許し r-2・ruling）", text)
        self.assertTrue(any(must for _, must in ask_final.needs(got)))

    def test_unreadable_allowed_tests_is_said(self):
        """collect は落ちた道でも [] を置くので、無い・形の違う allowed-tests.json は読めなかった訳を返す（黙って空にしない）"""
        got = ask_final.fix_beside([self.place("fix/fix/fix.diff", "")])
        self.assertEqual(got["allowed_tests"], [])
        self.assertTrue(any("allowed-tests.json を読めない" in x for x in got["beside_unread"]), got["beside_unread"])
        self.place("fix/fix/allowed-tests.json", {"path": "x"})
        self.assertTrue(any("行の配列でない" in x for x in ask_final.fix_beside([self.place("fix/fix/fix.diff", "")])["beside_unread"]))

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
        """L-W32: 修正前の関所で通した項目（gatemarks.pass_lines。事前審査の review の隣の gate-passes.json）と事前審査の往復
        （gate.json の converge）を最後の関所の文に並べる。案の直しの事前審査の物も足す"""
        row = {"node": gatemarks.GATE_NODE, "round": 1, "by": gatemarks.PASSED_BY, "item": "修正案 1 が狭める能力: x", "decided_by": "docs/adr.md:3"}
        self.place(f"plan-review/pass-1/{gatemarks.PASSES_FILE}", [row])
        self.place(f"plan-review/pass-1/{gatemarks.PLAN_GATE_FILE}", {"items": [], "converge": ["壁打ち: 2 往復で clean", "  - 往復 1: …"]})
        review = self.place("plan-review/pass-1/review.json", {})
        passes, rounds, unread = ask_final.review_rows((review, None))
        self.assertEqual((passes, rounds, unread), ([gatemarks.pass_lines([row])[0]], ["壁打ち: 2 往復で clean", "  - 往復 1: …"], []))
        text = ask_final.final_text(final_got(passes=passes, converge=rounds), [], RUN)
        self.assertIn(f"  - {gatemarks.named(gatemarks.GATE_NODE)}（周 1）で決め手が在るので聞かずに通した: 修正案 1 が狭める能力: x", text)
        self.assertIn("- 壁打ち: 2 往復で clean\n  - 往復 1: …", text)
        _, _, unread = ask_final.review_rows(({"type": "archon_artifact", "run_id": RUN, "path": "gone/review.json"},))
        self.assertIn("事前審査の隣の控え（通した行・往復）を読めない", unread[0])

    def test_final_gate_lists_gate_passes(self):
        """P255: 事前審査の隣の gate-passes.json に 1 行在る時、最後の関所の文にその行が在る（元 works/tests/test_plan_gate.py:397・
        :515・:575 の final_text の断言の、決め手で通した行の分）"""
        row = {"node": gatemarks.GATE_NODE, "round": 1, "by": gatemarks.PASSED_BY, "item": "決め手で通した行", "decided_by": "x.md:1"}
        self.place(f"plan-review/pass-1/{gatemarks.PASSES_FILE}", [row])
        self.place(f"plan-review/pass-1/{gatemarks.PLAN_GATE_FILE}", {"items": [], "converge": []})
        passes, _, _ = ask_final.review_rows((self.place("plan-review/pass-1/review.json", {}),))
        self.assertIn("決め手で通した行（決め手: x.md:1）", ask_final.final_text(final_got(passes=passes), [], RUN))

    def test_final_text_lists_suites_baseline_and_left_tests(self):
        """L-W28・T35: 最後のテストの返りの欄（with: の by・suites_line・log・baseline_line・tests_reason）から、一式・修正前のテスト・
        ログ・認証しなかった訳を字のまま出し、作業ツリーと並べる（証拠の文は開かない）。関門が返さなかった（飛ばされた節の null）時は
        その旨と「取れない」。返す節の中の誤り（by の空の字）は返らなかった形と分ける。手元で回さなかった試験（ci_left・final_left・
        final_far）は修正の返りに控えが無い（F013。部分 D2）"""
        with_ = line_nodes()["ask-final"]["with"]
        self.assertEqual({k: with_[k] for k in ("by", "suites_line", "log", "baseline_line", "tests_reason")},
                         {"by": "$test-gate-final.output.by", "suites_line": "$test-gate-final.output.suites_line",
                          "log": "$test-gate-final.output.log", "baseline_line": "$test-gate-final.output.baseline_line",
                          "tests_reason": "$test-gate-final.output.reason"})
        returned = {"INPUTS_BY": "role_needed", "INPUTS_SUITES_LINE": "一式 X", "INPUTS_LOG": "test-gate/final/logs/checks.log",
                    "INPUTS_BASELINE_LINE": "修正前のテスト: 緑（元の結末）", "INPUTS_TESTS_REASON": "任せ先の自己申告の緑"}
        with mock.patch.dict(os.environ, returned):
            got = ask_final.final_tests()
        text = ask_final.final_text(final_got(tests=got, tests_ok=False), [], RUN)
        for want in ("- テストの一式: role_needed・一式 X", "- 修正前のテスト: 緑（元の結末）", "- ログ: test-gate/final/logs/checks.log",
                     "- 走れなかった・認証しなかった理由: 任せ先の自己申告の緑", "- run の作業ツリー: /tmp/tree"):
            self.assertIn(want, text)
        with mock.patch.dict(os.environ, {k: "null" for k in returned}):
            got = ask_final.final_tests()
        missing = ask_final.declared_checks.GATE_MISSING
        self.assertEqual((got["suites"], got["log"], got["baseline"], got["reason"]), (missing, missing, f"修正前のテスト: {missing}", ""))
        self.assertIn(f"- {got['unread']}", ask_final.final_text(final_got(tests=got, tests_ok=False), [], RUN))
        self.assertTrue(got["unread"])
        with mock.patch.dict(os.environ, {k: "" for k in returned}):
            self.assertEqual(ask_final.final_tests()["unread"], "")

    def test_deleted_files_named(self):
        """M38: 封じた差分の中で消えるファイルを、当てる前に 1 本ずつ名指す（「取り込むと消えるファイル: <パス>」）"""
        diff = ("diff --git a/old.py b/old.py\ndeleted file mode 100644\nindex 1..0\n--- a/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n"
                "diff --git a/keep.py b/keep.py\nindex 1..2 100644\n--- a/keep.py\n+++ b/keep.py\n@@ -1 +1 @@\n-a\n+b\n")
        ptr = self.place("merge/sealed.diff", {})
        (self.artifacts / "merge/sealed.diff").write_text(diff, encoding="utf-8")
        self.assertEqual(ask_final.deleted_files(ptr), (["old.py"], ""))
        self.assertIn(f"- {seal.DELETED_HEAD}: old.py", ask_final.final_text(final_got(deleted=["old.py"]), [], RUN))
        self.assertIn("封じた差分を読めない", ask_final.deleted_files({"type": "archon_artifact", "run_id": "x", "path": "d"})[1])

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
        base = {key: None for key in plan_out.PLAN + plan_out.REVIEW + plan_out.DEPTH}
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
        self.assertEqual(set(self.got()), set(plan_out.PLAN + plan_out.REVIEW + plan_out.DEPTH) | {"nothing_owed", "done", "stop_reason"})

    def test_depth_fields_pass_through(self):
        got = self.got(depth_skip=True, depth_skipped=[plan_review_due.ROW], depth_raised=[])
        self.assertEqual((got["depth_skip"], got["depth_skipped"], got["depth_raised"]), (True, [plan_review_due.ROW], []))


class PlanReviewDueCase(unittest.TestCase):
    """往復の 1 周で事前審査の輪を飛ばすか（issue #441。中身は lib/headdepth.due）: 飛ばす時だけ表の行の id を名指す"""

    LIGHT = [{"unit_id": "u1", "depth": "軽量", "why": "配線だけ"}]

    def test_light_head_and_light_units_skip_the_review_loop(self):
        got = plan_review_due.plan_review_due("軽量", True, self.LIGHT)
        self.assertEqual((got["skip"], got["skipped"], got["raised"]), (True, ["plan-review-run__review-loop"], []))

    def test_a_standard_unit_raises_and_runs_the_loop(self):
        got = plan_review_due.plan_review_due("軽量", True, [*self.LIGHT, {"unit_id": "u2", "depth": "標準", "why": "w"}])
        self.assertEqual((got["skip"], got["skipped"]), (False, []))
        self.assertTrue(got["raised"])

    def test_standard_head_never_skips(self):
        got = plan_review_due.plan_review_due("標準", True, self.LIGHT)
        self.assertEqual((got["skip"], got["skipped"], got["raised"]), (False, [], []))

    def test_wiring(self):
        """頭の深さ・計画ができたか・単位ごとの深さを受け、事前審査の差し込みに飛ばすかと訳を渡し、往復の返しの節が報告と目に運ぶ"""
        nodes = line_nodes()
        self.assertEqual(nodes["plan-review-due"]["with"], {"head_depth": "$judge.output.depth", "ready": "$plan.output.ready",
                                                            "plan_depth": "$plan.output.depth"})
        run = nodes["plan-review-run"]
        self.assertIn("plan-review-due", run["depends_on"])
        self.assertEqual((run["with"]["depth_skip"], run["with"]["depth_why"]),
                         ("$plan-review-due.output.skip", "$plan-review-due.output.why"))
        self.assertEqual(nodes["fixed"]["with"]["review_skipped"], {"from": "$plan-rounds.output.depth_skip", "if_skipped": None})
        self.assertEqual(nodes["eyes"]["with"]["review_skipped"], "$fixed.output.review_skipped")
        self.assertEqual((nodes["judge-out"]["with"]["got_depth"], nodes["judge-out"]["with"]["got_depth_why"]),
                         ("$judge.output.depth", "$judge.output.depth_why"))


class PlanOutNothingOwedCase(Artifacts):
    def round_pointer(self, why: str) -> dict:
        rdir = self.artifacts / "plan" / "r1"
        rdir.mkdir(parents=True)
        (rdir / planfile.ROUND_FILE).write_text(json.dumps({"round": 1, "mode": "plan", "go": False, "why": why}), encoding="utf-8")
        (rdir / "plan-fields.json").write_text("{}", encoding="utf-8")
        return boundary.pointer("plan/r1/plan-fields.json")

    def test_nothing_owed_is_read_from_the_round(self):
        """#291: 直す義務 0 件の周（round.json の why が planfile.NOTHING_OWED。lib/outcome.py の plan_nothing_owed と同じ読み）だけが
        nothing_owed。ほかの訳・ほかの run の指し札・指し札の無い時は偽。計画ができた周は読みが真でも偽"""
        self.assertTrue(plan_out.round_owes_nothing(self.round_pointer(planfile.NOTHING_OWED)))
        self.assertFalse(plan_out.round_owes_nothing({**boundary.pointer("plan/r1/plan-fields.json"), "run_id": "other"}))
        self.assertFalse(plan_out.round_owes_nothing(None))
        got = {key: None for key in plan_out.PLAN + plan_out.REVIEW}
        self.assertTrue(plan_out.plan_out({**got, "ready": False}, ROUND_LIMIT, True)["nothing_owed"])
        self.assertFalse(plan_out.plan_out({**got, "ready": True, "round": 1}, ROUND_LIMIT, True)["nothing_owed"])

    def test_another_reason_is_not_nothing_owed(self):
        self.assertFalse(plan_out.round_owes_nothing(self.round_pointer("")))

    def read_from_env(self, pointer: dict) -> dict:
        env = {f"INPUTS_{key.upper()}": "null" for key in plan_out.PLAN + plan_out.REVIEW}
        env.update({"INPUTS_READY": "false", "INPUTS_PLAN": json.dumps(pointer), "INPUTS_ROUND_LIMIT": str(ROUND_LIMIT)})
        with mock.patch.dict(os.environ, env):
            return plan_out.plan_out(*plan_out.from_env())

    def test_the_node_reads_the_round_from_its_plan_input(self):
        """本番の節の口（from_env）が plan の入力の指し札から周の訳を読んで nothing_owed に渡す"""
        self.assertTrue(self.read_from_env(self.round_pointer(planfile.NOTHING_OWED))["nothing_owed"])

    def test_the_node_leaves_another_reason_false(self):
        self.assertFalse(self.read_from_env(self.round_pointer(""))["nothing_owed"])


class AfterFixAndJudgedCase(Artifacts):
    def test_after_fix_counts(self):
        self.assertEqual(after_fix.decide([]), {"replan": False, "stop_reason": ""})
        self.assertEqual(after_fix.decide(["1"]), {"replan": True, "stop_reason": ""})

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

    def rejudged(self, before, after, objection, verdicts=("一部採る",)):
        """判定のブロックの書き手（judge_accept.diff_units・rejudge_collect）が再審の置き場に書く judgment.json・rejudge-diff.json・
        rejudge-exit.json（再審の judgment の隣の約束のファイル）"""
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
        再審の judgment の隣に書く rejudge-exit.json だけが数え（元 rejudge.collect と diff_units）、judged はそれを読んで返す（数えを
        2 か所に持たない。K20）"""
        before = [{"key": "a", "label": "block", "disposition": "fix"}, {"key": "b", "label": "suggest", "disposition": "later"},
                  {"key": "c", "label": "block", "disposition": "fix"}, {"key": "d", "label": "nit", "disposition": "later"}]
        after = [{"key": "a", "label": "suggest", "disposition": "later"}, {"key": "b", "label": "suggest", "disposition": "do-now"},
                 {"key": "c", "label": "block", "disposition": "fix"}, {"key": "d", "label": "nit", "disposition": "drop"},
                 {"key": "e", "label": "block", "disposition": "fix"}]
        judge = self.returned(self.judgment("judge/judgment.json", before))
        again = self.returned(self.rejudged(before, after, "a は直さなくてよい。no 2 も"), "一部採る")
        got = judged.judged(judge, again, "a は直さなくてよい。no 2 も")
        self.assertEqual((got["judgment"], got["rejudged"], got["rejudge_verdict"]), (again["judgment"], True, "一部採る"))
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
        self.assertEqual(nodes["judged"]["with"]["rejudge_stop_reason"], {"from": "$rejudge-run.output.stop_reason", "if_skipped": None})
        # 再審は 2 度目の修正の後（L-D42）なので、judged の止めは fixed でなく試験の関門（final）の when が読む。独立の目・merge はその後ろ
        self.assertIn("$judged.output.stop_reason == ''", nodes["test-gate-final"]["when"])
        self.assertIn("$fixed.output.go == true", nodes["test-gate-final"]["when"])
        self.assertEqual(nodes["redepth"]["depends_on"], ["judged"])

    def test_unreadable_judgments_are_said(self):
        judge = self.returned({"type": "archon_artifact", "run_id": "another", "path": "judge/judgment.json"})
        got = judged.judged(judge, self.returned(judge["judgment"]), "")
        self.assertEqual((got["new_open_units"], got["lowered"], got["unnamed_changed"], got["stop_reason"]), ([], [], [], ""))
        self.assertIn("比べられない", got["unread"])
        judge = self.returned(self.judgment("judge/judgment.json", []))
        got = judged.judged(judge, self.returned(self.judgment("rejudge/judgment.json", [])), "")
        self.assertIn(f"{judge_accept.REJUDGE_EXIT} が無い", got["unread"])


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

    def test_no_fix_round_goes_on_with_the_design(self):
        """L-W07: 直す物が無い周（fix が走らず、独立設計だけを作る差し込み design-only が走った）は、fixed が直す物の無い形
        （no_fix・go・差分も申し出も無い）と独立設計の指し札を返し、最後のテスト・独立の目へ進める。普段の周は計画の往復の設計と
        修正前の問い・答えをそのまま渡す"""
        design = {"path": "plan-review/design.json"}
        plans = {"plan": None, "ripple": None, "replanned": None, "design": None, "no_fix_design": design,
                 "plan_questions": None, "answer": None}
        got = fixed.fixed({key: None for key in fixed.FIELDS}, None, replan=False, stops=("",), plans=plans)
        self.assertEqual((got["no_fix"], got["go"], got["done"], got["design"], got["diff"], got["diffs"], got["units"],
                          got["conflicts"], got["rejudge"], got["plan_questions"], got["answer"]),
                         (True, True, True, design, None, [], [], [], False, [], None))
        normal = fixed.fixed(self.fix(), None, replan=False, stops=("",),
                             plans={"design": {"path": "pr/design.json"}, "plan_questions": [{"kind": "fork", "text": "q"}],
                                    "answer": {"decision": "continue"}})
        self.assertEqual((normal["no_fix"], normal["design"], normal["plan_questions"], normal["answer"]),
                         (False, {"path": "pr/design.json"}, [{"kind": "fork", "text": "q"}], {"decision": "continue"}))

    def test_review_skipped_reaches_the_eyes_only_when_true(self):
        """issue #441: 計画の往復が事前審査を run の頭の深さで飛ばした印（plan-rounds の depth_skip）を、独立の目へ渡す"""
        self.assertIs(fixed.fixed(self.fix(), None, replan=False, stops=("",), review_skipped=True)["review_skipped"], True)
        self.assertIs(fixed.fixed(self.fix(), None, replan=False, stops=("",))["review_skipped"], False)
        with mock.patch.dict(os.environ, {"INPUTS_REVIEW_SKIPPED": "null"}):
            self.assertIs(fixed.from_env()["review_skipped"], False)

    def test_diffs_name_both_passes(self):
        """部分 D2: fixed は段ごとの diff の指し札の並び diffs（1 回目・2 度目の順。どちらの隣にも段の約束のファイル）を返し、最後の
        関所と報告が両方を読む。2 度目が走らなければ 1 回目だけ"""
        first = fixed.fixed(self.fix(), None, replan=False, stops=("", ""))
        self.assertEqual(first["diffs"], [{"path": "fix/diff"}])
        both = fixed.fixed(self.fix(), self.fix(diff={"path": "refix/diff"}), replan=True, stops=("", ""))
        self.assertEqual((both["diff"], both["diffs"]), ({"path": "refix/diff"}, [{"path": "fix/diff"}, {"path": "refix/diff"}]))

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

    def test_eyes_get_the_final_test_outcomes_and_every_fix_diff(self):
        """issue #384: R2 の比較役の実測は最後のテストの関門の比べ（base の関門の欄は常に null）と、修正の段ごとの diff"""
        self.assertEqual({k: line_nodes()["eyes"]["with"][k] for k in ("test_outcomes", "diffs")},
                         {"test_outcomes": "$test-gate-final.output.test_outcomes", "diffs": "$fixed.output.diffs"})

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
                         {"plan": {"from": "$plan-rounds.output.plan", "if_skipped": None},
                          "ripple": {"from": "$plan-rounds.output.ripple", "if_skipped": None},
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
        self.assertEqual(nodes["fixed"]["with"]["refix_x_scalars"], {"from": "$refix-run.output.x_scalars", "if_skipped": None})
        self.assertIn("x_scalars", block_doc("works-factory-fix")["nodes"][-1]["output_format"]["required"])


    def test_fields_are_every_field_fix_returns_and_fixed_takes_them_all(self):
        """fixed.FIELDS は fix の返す節の output_format の欄の組と同じで、fixed は 1 回目（fix）と 2 度目（refix-run）の欄の全部を
        fix_<欄>・refix_<欄> で受ける（片側だけ変えると欄が黙って落ちる。stop_reason は refix-run から fixed を通ってだけ報告に届く）"""
        doc = block_doc("works-factory-fix")
        returns = next(n for n in doc["nodes"] if n["id"] == doc["returns"])
        self.assertEqual(set(fixed.FIELDS), set(returns["output_format"]["properties"]))
        took = line_nodes()["fixed"]["with"]
        for prefix, node in (("fix", "fix"), ("refix", "refix-run")):
            with self.subTest(node=node):
                self.assertEqual({f: took.get(f"{prefix}_{f}") for f in fixed.FIELDS},
                                 {f: {"from": f"${node}.output.{f}", "if_skipped": None} for f in fixed.FIELDS})


class RedepthCase(Artifacts):
    LIGHT = [{"unit_id": "u1", "depth": "軽量", "why": "配線だけ"}]

    def redepth(self, *, units=(), conflicts=(), signals=(), replanned=False, rejudged=False, replanned_depth=None, counted=""):
        return redepth.redepth(self.LIGHT, replanned_depth, list(units), list(conflicts), list(signals), replanned=replanned,
                               rejudged=rejudged, counted=counted)

    def put(self, rel, doc):
        (self.artifacts / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.artifacts / rel).write_text(doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return {"type": "archon_artifact", "run_id": RUN, "path": rel}

    def test_quiet_run_stays_light_and_names_what_it_skips(self):
        got = self.redepth(units=[{"unit_id": "u1", "status": "fixed"}])
        self.assertEqual(got["depth"][0]["depth"], "軽量")
        self.assertTrue(got["skip_optional"])

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
        self.assertEqual(redepth.pending_signals(judgment, start, answer, judgment), ["答えていない問い q2"])
        held = {**answer, "text": "保留: q1", "asked": [gatemarks.ask_text(q) for q in questions[:2]]}
        self.assertEqual(redepth.pending_signals(judgment, start, held, judgment), ["答えていない問い q1"])
        self.assertEqual(redepth.pending_signals(judgment, start, None, judgment), ["答えていない問い q1", "答えていない問い q2"])
        broken = self.put("judge/broken.json", "{壊れた")
        self.assertTrue(redepth.pending_signals(broken, start, None, broken)[0].startswith("問いの台帳が読めない"))
        self.assertEqual(redepth.pending_signals(None, start, None, None), [])
        got = self.redepth(signals=redepth.pending_signals(judgment, start, answer, judgment))
        self.assertEqual(got["depth"][0]["depth"], "標準")
        self.assertIn("答えていない問い q2", got["raised"])

    def test_wide_run_raises_to_standard(self):
        """L-D10: run 全体の広さ（計画の allowed_paths と修正の実際の差分のファイルの和集合・受け入れと書き換えのテストの本数。
        depth.run_wide）が単位ごとの上限を超えれば、軽量の名指しでも全部の単位を標準へ上げ、数えた数と起点を counted に残す
        （元 depth.raise_ :302-313）"""
        plan = self.put("plan/plan-fields.json", {"fields": [{"unit_keys": ["u1"], "allowed_paths": ["a.py"], "tests": [], "rewrite_tests": []}]})
        diff = "".join(f"diff --git a/w{n}.py b/w{n}.py\n--- a/w{n}.py\n+++ b/w{n}.py\n@@ -1 +1 @@\n-x\n+y\n" for n in range(4))
        ptr = self.put("fix/diff.patch", diff)
        signals, counted = redepth.wide_signals(plan, ptr, ["u1"])
        self.assertEqual(signals, ["run 全体で触るファイル 5 個（3 個まで）"])
        self.assertEqual(counted, "触るファイル 5 個（起点: 修正の差分 fix/diff.patch）")
        got = self.redepth(signals=signals, counted=counted)
        self.assertEqual((got["depth"][0]["depth"], got["counted"]), ("標準", counted))
        signals, counted = redepth.wide_signals(plan, None, ["u1"])
        self.assertEqual(signals, [])
        self.assertTrue(counted.startswith(f"触るファイル 1 個（起点: {redepth.PLAN_ORIGIN}"), counted)

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
               "INPUTS_TIES_JUDGMENT": json.dumps(judgment), "INPUTS_REPLANNED": "false", "INPUTS_REJUDGED": "false"}
        self.assertLessEqual({k.removeprefix("INPUTS_").lower() for k in env}, set(line_nodes()["redepth"]["with"]))
        with mock.patch.dict(os.environ, env):
            got = redepth.compute()
        self.assertEqual(got["depth"][0]["depth"], "標準")
        self.assertIn("答えていない問い q1", got["raised"])
        self.assertIn("run 全体で触るファイル 5 個（3 個まで）", got["raised"])
        self.assertEqual(got["counted"], "触るファイル 5 個（起点: 修正の差分 fix/diff.patch）")

    def test_replanned_depth_merges_by_unit(self):
        """L-D15: 案の直しの後の深さは、1 回目の単位の行を残して直した案の単位の行で単位ごとに置き換える（元 depth.raise_ は全部の単位の
        控えを残して上げた）"""
        got = self.redepth(replanned_depth=[{"unit_id": "u9", "depth": "標準", "why": "直した案"}], replanned=True)
        self.assertEqual([row["unit_id"] for row in got["depth"]], ["u1", "u9"])
        got = self.redepth(replanned_depth=[{"unit_id": "u1", "depth": "標準", "why": "直した案"}])
        self.assertEqual([(row["unit_id"], row["depth"]) for row in got["depth"]], [("u1", "標準")])

    def test_line_passes_what_the_signals_read(self):
        """L-D08・L-D10: redepth は判定の問いの台帳（判定と始めの記録と修正前の関所の答えと 1 回目の判定の結び）と、修正の計画と差分を
        受ける"""
        with_ = line_nodes()["redepth"]["with"]
        self.assertEqual({k: with_[k] for k in ("judgment", "start", "answer", "ties_judgment", "plan", "diff")},
                         {"judgment": "$judged.output.judgment", "start": "$start.output.record",
                          "answer": {"from": "$answer-before-fix.output.answer", "if_skipped": None},
                          "ties_judgment": "$judge.output.judgment",
                          "plan": "$fixed.output.plan", "diff": "$fixed.output.diff"})
        self.assertIn("counted", line_nodes()["redepth"]["output_format"]["required"])


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

    def test_no_fix_design_is_the_plan_review(self):
        """L-W07: 直す物が無い周（計画の往復が飛んだ）は、report の plan-review の欄に design-only の受け皿の返りを置く"""
        only = {"pass": True, "design": {"path": "plan-review/design.json"}}
        got = collect.collect({"design_only": json.dumps({"got": only, "stop_reason": ""})}, self.line())
        self.assertEqual((got["plan"], got["plan_review"]), (None, only))
        self.assertEqual(line_nodes()["collect"]["with"]["design_only"], {"from": "$design-only-out.output", "if_skipped": None})

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

    def test_absorbed_stages_are_declared_once_in_the_line(self):
        """R82: 受け止める段（落ちても線が先へ進めてよい段。元は線の YAML の節の description の [optional]）の宣言は線の YAML の 1 か所
        （collect の with: の optional）で、report の入力 optional に届く。元の宣言は世界の解・構造の実測・レンズ・直した後の構造・独立の目
        （works/darkfactory/darkfactory.yaml 347・445・946・1124・1196 行）"""
        declared = json.loads(line_nodes()["collect"]["with"]["optional"])
        self.assertEqual(collect.collect({}, self.line(optional=json.dumps(declared)))["optional"], declared)
        for stage in ("judge__world", "plan__structure", "fix__lens", "eyes__"):
            with self.subTest(stage=stage):
                self.assertIn(stage, declared)
        self.assertEqual(line_nodes()["report"]["with"]["optional"], "$collect.output.optional")

    def test_result_carries_what_apply_reads(self):
        """線の返りの欄 apply・sealed・r2_status・final_answer（bin/apply と段 1 が読む）は collect が集めた返りから組み、飛ばされた段は
        null。result は merge・eyes・関所の返りを直に読まず collect を通す"""
        seal = {"mode": "seal", "ok": True, "hash": "h", "diff": {"path": "merge/sealed.diff"}, "protected_hits": [], "reason": ""}
        put = {**seal, "mode": "apply", "diff": {"path": "merge/apply.diff"}}
        eyes = {"ok": True, "r2": {"status": "pass", "reason": ""}}
        answer = {"decision": "stop", "text": "やめる"}
        got = result.result({"outcome": "fixed"}, {"merge_apply": put, "merge_seal": seal, "eyes": eyes, "gate_final": answer}, None)
        self.assertEqual(got["apply"], {"ok": True, "hash": "h", "diff": {"path": "merge/apply.diff"}, "reason": ""})
        self.assertEqual(got["sealed"], {"ok": True, "hash": "h", "diff": {"path": "merge/sealed.diff"}})
        self.assertEqual((got["r2_status"], got["final_answer"]), ("pass", answer))
        got = result.result({"outcome": ""}, {"merge_apply": None, "merge_seal": None, "eyes": {"ok": True, "r2": None}, "gate_final": None},
                            None)
        self.assertEqual((got["apply"], got["sealed"], got["r2_status"], got["final_answer"]), (None, None, None, None))
        with_ = line_nodes()["result"]["with"]
        for key in ("merge_apply", "merge_seal", "eyes", "gate_final"):
            with self.subTest(key=key):
                self.assertEqual(with_[key], {"from": f"$collect.output.{key}", "if_skipped": None})
        self.assertFalse([v for v in with_.values() if "$merge-" in json.dumps(v) or "$eyes" in json.dumps(v)])

    def test_result_fixed(self):
        for outcome, want in (("fixed", True), ("fixed_needs_check", True), ("no_fix_needed", False), ("", False)):
            with self.subTest(outcome=outcome):
                self.assertEqual(result.result({"outcome": outcome}, {}, None)["fixed"], want)


class SweepChildrenCase(unittest.TestCase):
    """線の後始末の節 sweep-children（issue #113）: 報告の後・線の返す節の前に在り、落ちずに {cleaned, left, error} を返し、
    result がそれを線の返りの欄 children に載せる。選びと Archon の起こし方は tests/bin/test_childsweep.py"""

    def test_runs_after_the_report_and_feeds_only_the_result(self):
        nodes = line_nodes()
        node = nodes["sweep-children"]
        self.assertEqual((node["script"], node["depends_on"], node["trigger_rule"]), ("sweep_children", ["report"], "all_done"))
        self.assertIs(node["mutates_checkout"], False)
        self.assertEqual({key for key, other in nodes.items() if "sweep-children" in other.get("depends_on", [])}, {"result"})
        self.assertIn("sweep-children", nodes["result"]["depends_on"])
        self.assertEqual(nodes["result"]["with"]["children"], {"from": "$sweep-children.output", "if_skipped": None})
        top = {node["id"]: node for node in LINE["nodes"]}
        self.assertEqual({key for key in top if not any(key in other.get("depends_on", []) for other in top.values())}, {"result"})

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
            env = {k: v for k, v in os.environ.items() if k != "WORKS_FACTORY_ARCHON_SOURCE"}
            env.update({"PATH": f"{tmp / 'bin'}{os.pathsep}{env.get('PATH', '')}", "WORKFLOW_ID": RUN, "ARTIFACTS_DIR": str(tmp),
                        "WORKS_FACTORY_ROOT": str(ROOT)})
            env.update({k: v.replace("<tmp>", str(tmp)) for k, v in extra.items()})
            done = subprocess.run([sys.executable, str(copied / "line/scripts/sweep_children.py")], cwd=tmp, env=env,
                                  capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_run_without_children_does_not_fail(self):
        self.assertEqual(self.run_node({"WORKS_FACTORY_ARCHON_SOURCE": "<tmp>/archon"}), {"cleaned": [], "left": [], "error": ""})

    def test_run_outside_the_launcher_does_not_fail(self):
        got = self.run_node({})
        self.assertEqual((got["cleaned"], got["left"]), ([], []))
        self.assertIn("WORKS_FACTORY_ARCHON_SOURCE", got["error"])


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
        for key in ("fix_done", "fix_units", "plan", "ripple", "replan", "stop_after_fix", "design", "no_fix_design",
                    "plan_questions", "answer"):
            self.assertIsInstance(nodes["fixed"]["with"][key], dict, key)
        self.assertEqual(nodes["eyes"]["with"]["design"], "$fixed.output.design")
        self.assertEqual(nodes["eyes"]["with"]["plan_questions"], "$fixed.output.plan_questions")
        self.assertEqual(nodes["eyes"]["with"]["answers"], "$fixed.output.answer")
        self.assertIn("$fixed.output.no_fix == false", nodes["merge-seal"]["when"])
        self.assertIn("$fixed.output.no_fix == false", nodes["merge-apply"]["when"])
        self.assertEqual((nodes["ask-final"]["depends_on"], nodes["ask-final"]["trigger_rule"]),
                         (["eyes", "merge-seal"], "none_failed_min_one_success"))
        for key in ("protected_hits", "sealed", "seal_reason", "hash", "sealed_diff", "plan_review", "structure", "before_fix_answer"):
            self.assertIsInstance(nodes["ask-final"]["with"][key], dict, key)
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
        PLAN・DEPTH と REVIEW）と同じ（受け皿の鍵を消すか向け違えると、その欄が黙って報告から落ちる）"""
        nodes = line_nodes()
        rounds = {"plan-rounds-out": plan_out.PLAN + plan_out.DEPTH, "plan-rounds-review-out": plan_out.REVIEW}
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
        ("fix", "prior_conflicts"): "1 回目の段は前の段の申し出が無い（refix-run だけが 1 回目の conflicts を渡す）",
        ("fix", "notes"): "機械の申し送りは案の直しの後の 2 度目の修正だけ（refix-run だけが answer-replan の fix_notes を渡す）",
        ("plan-review-run", "conflicts"): "修正の前なので申し出が無い",
        ("plan-review-run", "gate_answers"): "修正前の承認ノードより前に走る",
        ("plan-review-run", "mode"): "計画の往復の事前審査は形が空（既定）",
        ("replan-review", "round_limit"): "案の直しの事前審査は往復のループの外で、ループの上限が無い",
        ("replan-review", "mode"): "案の直しの事前審査は形が空（既定）。形 design は直す物が無い周の design-only だけ",
        ("replan-review", "depth_skip"): "run の頭の深さで飛ばすのは計画の往復の事前審査だけ（docs/design.md の深さで飛ばすノードの表）",
        ("replan-review", "depth_why"): "run の頭の深さで飛ばすのは計画の往復の事前審査だけ（docs/design.md の深さで飛ばすノードの表）",
        ("design-only", "depth_skip"): "形 design は事前審査の輪を回さない",
        ("design-only", "depth_why"): "形 design は事前審査の輪を回さない",
        ("design-only", "ruling"): "直す物が無い周は修正案を読まない形 design（裁定が無い）",
        ("design-only", "conflicts"): "直す物が無い周は修正の段が無いので申し出が無い",
        ("design-only", "gate_answers"): "直す物が無い周は修正前の承認ノードが無い",
        ("design-only", "round_limit"): "形 design は往復のループの外で、ループの上限が無い",
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
        "answer-ties.json": (("judge", "judgment"), "lib/marks.py"),
        "local-review-lenses.json": (("judge", "judgment"), "lib/diverted.py"),
        "pr-downgrades.json": (("judge", "judgment"), "lib/prcheck.py"),
        "world-state.json": (("judge", "judgment"), "lib/worldmark.py"),
        "p2.fix_plan.json": (("plan", "plan"), "lib/fixboard.py"),
        "rejects-plan.json": (("plan", "plan"), "lib/boardview.py"),
        "replan-gave-up.json": (("plan", "plan"), "lib/runreport.py"),
        "design.jsonl": (("plan", "structure"), "lib/boardview.py"),
        "gate-passes.json": (("plan-review", "review"), "lib/gatemarks.py"),
        "gate.json": (("plan-review", "review"), "lib/gatemarks.py"),
        "rejudge-exit.json": (("judge", "judgment"), "lib/report.py"),
        "rejudge-diff.json": (("judge", "judgment"), "lib/report.py"),
        "r4-gate-passes.json": (("eyes", "notes"), "lib/eyeverdict.py"),
        "premise-check.json": (("eyes", "notes"), "lib/eyeverdict.py"),
        "design-premises.json": (("plan-review", "design"), "lib/eyeverdict.py"),
        "allowed-tests.json": (("fix", "diff"), "workflows/line/scripts/ask_final.py"),
        "lenses.json": (("fix", "diff"), "lib/fixbeside.py"),
        "accept-trace.json": (("fix", "diff"), "lib/fixbeside.py"),
        "closure.json": (("fix", "diff"), "lib/fixbeside.py"),
        "delta-holes.json": (("fix", "diff"), "lib/fixbeside.py"),
        "fix-removed.json": (("fix", "diff"), "lib/leftovers.py"),
        "tdd-unit.json": (("fix", "diff"), "lib/fixbeside.py"),
    }
    # 書き手の返す節を空の置き場で走らせる時の入力（ブロックの YAML がその節に渡す with: と、Archon がブロックの入力を渡す INPUTS_*）
    RETURN_INPUTS = {
        "judge": {"INPUTS_OBJECTION": ""},
        "plan": {"INPUTS_DIR": "plan/r1", "INPUTS_START": "", "INPUTS_JUDGMENT": ""},
        "plan-review": {},
        "fix": {"INPUTS_MODE": ""},
        "eyes": {},
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
        **{(name, check): "fix の出力を組めない道では置かない（読み手 fixbeside.read が「無い」と名指し、最後の承認ノードを開ける理由にし、"
                          "閉鎖の表は残りに数える）"
           for name in ("closure.json", "delta-holes.json") for check in ("stop", "bare")},
        **{("fix-removed.json", check): "書き手は fix のノード clean で出力ノードではない（clean の前に止まった run には無く、"
                                        "leftovers.removed が「走らせていない」と読む）" for check in ("stop", "bare")},
        **{("tdd-unit.json", check): "書き手は fix のノード tdd-unit で出力ノードではない（tdd-unit の前に止まった run と組の子の run には"
                                     "無く、読み手 fixbeside.tdd が「無い」と名指す）" for check in ("stop", "bare")},
        **{(name, check): "eyes の出力ノードは目の材料を書けない道で notes を null にする（読み手 ask_final.eye_notes と報告が null を訳にする）"
           for name in ("r4-gate-passes.json", "premise-check.json") for check in ("stop", "bare")},
        **{(name, check): "再審（rejudge-run）の判定の隣にだけ在り、判定の道では書かれない（読み手 report.rejudge_exit が「無い」を訳にする）"
           for name in ("rejudge-exit.json", "rejudge-diff.json") for check in ("stop", "bare")},
        **{("rejects-plan.json", check): "拒んだ回にだけ書く（rolekit.reject）。空の置き場の返す節は書かない"
           for check in ("stop", "bare")},
        ("rejects-plan.json", "named"): "名は rolekit.rejects_path が役の名から組み（rejects-<役>.json）、字の定数が無い",
        ("rejects-plan.json", "read"): "plan-review は rolekit.reject_rows で役の名から開き、名の字を持たない",
        **{("replan-gave-up.json", check): "案の直しで役が諦めた項目が在る時だけ書く（planfile.note_gave_up）。空の置き場の返す節は書かない"
           for check in ("stop", "bare")},
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
            if ptr is None:   # 欄が null の止めの道（隣のファイルも無い。読み手が null を訳にする）
                return set()
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
        止めた Archon の packages/workflows/src/dry-run.ts 795・849-890 行）ので、2 周目の値は段 1 の本物の run で見る。ブロックの側は
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
        self.assertEqual(line_nodes()["replan-review"]["with"]["gate_answers"], "$answer-before-fix.output.answer")

    def test_plan_review_gets_conflicts_and_gate_answers(self):
        """P152・L-W45: 事前審査の差し込みのうち、修正の後に走る replan-review には申し出と関所の答えの両方が届き、修正前の関所より前に
        走る往復の中の plan-review-run には渡さない（まだ無い。UNPASSED に訳つき）"""
        nodes = line_nodes()
        self.assertLessEqual({"conflicts", "gate_answers"}, set(nodes["replan-review"]["with"]))
        self.assertFalse({"conflicts", "gate_answers"} & set(nodes["plan-review-run"]["with"]))
        self.assertEqual({name for key, name in self.UNPASSED if key == "plan-review-run"}, {"conflicts", "gate_answers", "mode"})
        self.assertEqual({name for key, name in self.UNPASSED if key == "replan-review"},
                         {"mode", "round_limit", "depth_skip", "depth_why"},
                         "申し出と関所の答えは渡す（mode は直す物が無い周の design-only だけ）")

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
         "works/blk-delta/commands/delta-review.md:8。S02）", "fix", "plan_review", "$plan-rounds.output.review"),
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

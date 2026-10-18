"""周の鎖 works-factory-chain（workflows/chain/）の script・グラフの形・筋書きの試験。

script は子のプロセスとして使い捨ての置き場（runs/<親>・runs/<子>）・run の記録・git の木で走らせる（Archon を起こさない）。
グラフの形は YAML を読んで照らす（5 組の周のノードが番号と前の決めのほかは同じ形・子へ渡す入力がメイングラフの入力と同じ）。
筋書き（workflows/chain/fixtures/）は止めた Archon の `workflow test` で合否を、`workflow run --dry-run` の trace で決めの語を照らす
（子の run と、読み書きをするノード round-k-commit・round-k-facts は stub で差し、chain-start・round-k-decide・result は本当に走る）。
"""
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests import archon
from tests.bin import hermetic
from tests.bin.gitkit import git
from tests.e2e.test_line_scenarios import bound, dry_run_traces, scenarios

ROOT = archon.ROOT
FOLDER = ROOT / "workflows" / "chain"
SCRIPTS = FOLDER / "scripts"
CHAIN = yaml.safe_load((FOLDER / "works-factory-chain.yaml").read_text(encoding="utf-8"))
LINE = yaml.safe_load((ROOT / "workflows" / "line" / "works-factory-line.yaml").read_text(encoding="utf-8"))
NAME = CHAIN["name"]
SCENARIOS = ("limit-then-fixed", "rounds-reached", "needs-human", "same-items", "interrupted", "child-failed", "refused", "deliver-pr")

if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))
import carry  # noqa: E402
import chain  # noqa: E402

NODES = {n["id"]: n for n in CHAIN["nodes"]}


def run_script(name: str, env: dict, cwd: pathlib.Path) -> dict:
    """鎖の script を Archon と同じく子のプロセスで走らせ、標準出力の JSON を返す"""
    done = subprocess.run([sys.executable, str(SCRIPTS / f"{name}.py")], cwd=cwd, env=hermetic.child_env(**{"PYTHONDONTWRITEBYTECODE": "1", **env}),
                          capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise AssertionError(f"{name} が終了の値 {done.returncode}: {done.stderr}")
    return json.loads(done.stdout)


ROUND_FILES = ("one.txt", "two.txt", "three.txt")


def three_rounds(repo: pathlib.Path, halted_last: bool = True, placed=(1, 2, 3), r2=None, spec=None) -> tuple:
    """repo の HEAD を元の基に、周ごとに 1 ファイルを足す commit を 3 つ積む。(chain-start の出力, 周 1〜3 の決めの出力)。
    3 周目の結末の種は halted_last なら halted。子が差分を置いた周の番号は placed、周ごとの R2 の状態は r2（{周: 状態}）、
    周ごとの承認し直すかの問いの数は spec（{周: 数}）"""
    origin = git(repo, "rev-parse", "HEAD")
    rows, made = [], []
    for n, name in enumerate(ROUND_FILES, 1):
        (repo / name).write_text(f"{n}\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", f"round {n}")
        kind = chain.KIND_HALTED if halted_last and n == 3 else chain.KIND_OPEN
        rows.append({"n": n, "run": f"child-{n}", "outcome": "stopped_by_human" if kind == chain.KIND_HALTED else "round_limit",
                     "kind": kind, "keys": [f"k{n}"], "held": 0, "same_tree": False, "cost": 1.0 * n, "cost_read": True,
                     "minutes": 10.0, "head": git(repo, "rev-parse", "HEAD"), "placed": n in placed, "r2_status": (r2 or {}).get(n),
                     "spec_questions": (spec or {}).get(n, 0), "request": "", "source": ""})
        act = "launch" if n < 3 else "stop"
        made.append({"act": act, "word": "" if act == "launch" else "halted", "text": "t", "request": "", "base": "", "pr": "",
                     "spec": "", "rows": [dict(r) for r in rows]})
    start = {"ok": True, "reason": "", "act": "launch", "word": "", "text": "", "rows": [], "rounds": 3, "origin": origin}
    return start, made


def run_final(repo: pathlib.Path, artifacts: pathlib.Path, run_id: str, start, *decisions) -> dict:
    env = {"INPUTS_START": json.dumps(start), "ARTIFACTS_DIR": str(artifacts), "WORKFLOW_ID": run_id}
    env.update({f"INPUTS_D{i}": json.dumps(d) for i, d in enumerate(decisions, 1)})
    return run_script("final_diff", env, repo)


def run_result(start, final, *decisions, artifacts: pathlib.Path, run_id: str = "parent") -> dict:
    env = {"INPUTS_START": json.dumps(start), "INPUTS_FINAL": json.dumps(final), "ARTIFACTS_DIR": str(artifacts),
           "WORKFLOW_ID": run_id}
    env.update({f"INPUTS_D{i}": json.dumps(d) for i, d in enumerate(decisions, 1)})
    return run_script("result", env, artifacts)


def prev_of(k: int) -> str:
    return "chain-start" if k == 1 else f"round-{k - 1}-decide"


def group(k: int) -> list:
    return [NODES[f"round-{k}"], NODES[f"round-{k}-commit"], NODES[f"round-{k}-facts"], NODES[f"round-{k}-decide"]]


def shape(k: int) -> str:
    """組 k を、番号を N に、前の決めの id を PREV に置いた YAML の字（前の決めは子の入力と when と決めの rows でだけ読む）"""
    child, commit, facts, decide = (dict(n) for n in group(k))
    prev = prev_of(k)
    child = yaml.safe_load(yaml.safe_dump(child).replace(prev, "PREV"))
    decide["with"] = {**decide["with"], "rows": decide["with"]["rows"].replace(prev, "PREV")}
    text = yaml.safe_dump([child, commit, facts, decide], allow_unicode=True, sort_keys=True)
    return re.sub(rf"round-{k}(?![0-9])", "round-N", text)


class Tree(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)


class RoundCommitCase(Tree):
    """周の結果の commit は Archon が切った run の作業ツリー（worktree）の枝にだけ積み、利用者の枝は動かさない"""

    def setUp(self):
        super().setUp()
        self.main = self.tmp / "main"
        self.main.mkdir()
        git(self.main, "init", "-q", "-b", "main")
        (self.main / "a.txt").write_text("a\n", encoding="utf-8")
        git(self.main, "add", "-A")
        git(self.main, "commit", "-q", "-m", "seed")
        self.run_tree = self.tmp / "run"
        git(self.main, "worktree", "add", "-q", "-b", "run-branch", str(self.run_tree))
        self.seed = git(self.main, "rev-parse", "HEAD")

    def commit(self, cwd: pathlib.Path) -> dict:
        return run_script("round_commit", {}, cwd)

    def test_change_is_committed_on_the_run_branch_only(self):
        (self.run_tree / "b.txt").write_text("b\n", encoding="utf-8")
        (self.run_tree / ".archon").mkdir()
        (self.run_tree / ".archon" / "copy.yaml").write_text("x\n", encoding="utf-8")
        got = self.commit(self.run_tree)
        self.assertEqual((got["ok"], got["changed"]), (True, True), got)
        self.assertEqual(got["head"], git(self.run_tree, "rev-parse", "HEAD"))
        self.assertNotEqual(got["head"], self.seed)
        self.assertEqual(git(self.main, "rev-parse", "main"), self.seed, "利用者の枝は動かない")
        self.assertEqual(git(self.run_tree, "show", "--name-only", "--format=", "HEAD").splitlines(), ["b.txt"],
                         "Archon が写した置き場は積まない")

    def test_no_change_is_not_committed(self):
        got = self.commit(self.run_tree)
        self.assertEqual((got["ok"], got["changed"], got["head"]), (True, False, self.seed), got)
        self.assertEqual(git(self.run_tree, "rev-parse", "HEAD"), self.seed)

    def test_main_tree_is_refused_without_touching_it(self):
        (self.main / "b.txt").write_text("b\n", encoding="utf-8")
        before = git(self.main, "status", "--porcelain")
        got = self.commit(self.main)
        self.assertEqual((got["ok"], got["changed"]), (False, None), got)
        self.assertIn("本体の作業ツリー", got["reason"])
        self.assertEqual((git(self.main, "status", "--porcelain"), git(self.main, "rev-parse", "HEAD")), (before, self.seed))

    def test_detached_head_is_refused(self):
        git(self.run_tree, "checkout", "-q", "--detach")
        (self.run_tree / "b.txt").write_text("b\n", encoding="utf-8")
        got = self.commit(self.run_tree)
        self.assertEqual(got["ok"], False, got)
        self.assertEqual(git(self.run_tree, "rev-parse", "HEAD"), self.seed)


FINDINGS = [{"where": "a.py:1", "text": "mean が空で落ちる"}, {"where": "b.py:2", "text": "空の列で 0 を返す"}]
MEASURED = {"text": "設定は 3 つ", "measured_how": "前の run の前提の検算（run child）", "kind": carry.MEASURED}


class RoundFactsCase(Tree):
    """子の次の依頼を兄弟の置き場から読み、運ぶ次の依頼を親の置き場に書き、周の費用を親の run の記録から読む"""

    def setUp(self):
        super().setUp()
        runs = self.tmp / "runs"
        self.parent, child = runs / "parent", runs / "child"
        (child / "report").mkdir(parents=True)
        self.parent.mkdir()
        nxt = {"findings": [*FINDINGS, carry.draft({"where": "c.py", "text": "目的の外"}, "purpose")],
               "prior_failures": [], "constraints": [MEASURED]}
        (child / "report" / carry.NEXT_REQUEST_FILE).write_text(json.dumps(nxt, ensure_ascii=False), encoding="utf-8")
        self.first = self.tmp / "request.json"
        self.first.write_text(json.dumps({"findings": [FINDINGS[0]], "answers": [{"question": "q1", "text": "a"}]}), encoding="utf-8")
        self.logs = self.tmp / "logs"
        self.logs.mkdir()
        self.pointer = {"type": "archon_artifact", "run_id": "child", "path": f"report/{carry.NEXT_REQUEST_FILE}"}

    def log(self, *rows):
        (self.logs / "parent.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def facts(self, pointer="", **env) -> dict:
        base = {"ARTIFACTS_DIR": str(self.parent), "WORKFLOW_ID": "parent", "LOG_DIR": str(self.logs),
                "INPUTS_NEXT_REQUEST": json.dumps(pointer) if pointer != "" else json.dumps(self.pointer),
                "INPUTS_CHILD": "round-1", "INPUTS_FIRST_REQUEST": str(self.first), "INPUTS_FIRST_PR": "7"}
        return run_script("round_facts", {**base, **env}, self.tmp)

    def test_next_request_is_carried_into_the_parent_run(self):
        self.log({"type": "node_complete", "step": "round-1", "cost_usd": 1.5, "execution": {"accounting": "node"}})
        got = self.facts()
        self.assertEqual(got["error"], "", got)
        self.assertEqual((len(got["keys"]), len(got["held_rows"]), got["run"]), (2, 1, "child"))
        written = pathlib.Path(got["request"])
        self.assertEqual(written, self.parent / "chain" / "round-1" / carry.NEXT_REQUEST_FILE)
        parts = carry.parts(json.loads(written.read_text(encoding="utf-8")))
        self.assertEqual((parts["findings"], parts["constraints"], parts["pr"]), (FINDINGS, [MEASURED], [7]))
        self.assertEqual(parts["answers"], [{"question": "q1", "text": "a"}])
        self.assertTrue(got["source"].endswith(f"child/report/{carry.NEXT_REQUEST_FILE}"))
        self.assertEqual((got["cost"], got["cost_read"]), (1.5, True))

    def test_minutes_are_the_child_node_rows(self):
        self.log({"type": "node_start", "step": "round-1", "ts": "2026-10-14T10:00:00Z"},
                 {"type": "node_complete", "step": "round-1", "ts": "2026-10-14T10:12:30Z", "cost_usd": 1.0,
                  "execution": {"accounting": "node"}})
        self.assertEqual(self.facts()["minutes"], 12.5)
        (self.logs / "parent.jsonl").unlink()
        self.assertIsNone(self.facts()["minutes"])

    def test_unreadable_cost_is_not_zero(self):
        self.log({"type": "node_complete", "step": "round-1", "execution": {"accounting": "node"}})
        self.assertIs(self.facts()["cost_read"], False)
        (self.logs / "parent.jsonl").unlink()
        got = self.facts()
        self.assertEqual((got["cost"], got["cost_read"]), (None, False))

    def test_null_pointer_is_no_next_request(self):
        got = self.facts(pointer=None)
        self.assertEqual((got["error"], got["request"], got["keys"]), ("", "", []), got)

    def test_pointer_out_of_the_child_run_is_an_error(self):
        got = self.facts(pointer={**self.pointer, "path": "../parent/x.json"})
        self.assertNotEqual(got["error"], "")
        self.assertEqual(got["request"], "")


class ChainStartCase(Tree):
    def start(self, **inputs) -> dict:
        env = {f"INPUTS_{k.upper()}": v for k, v in {"rounds": "", "budget_usd": "", "request": "", "base": "", "pr": "",
                                                       "spec": "", **inputs}.items()}
        git(self.tmp, "init", "-q")
        return run_script("chain_start", {**env, "ARTIFACTS_DIR": str(self.tmp), "WORKFLOW_ID": "parent"}, self.tmp)

    def test_out_of_range_is_refused_before_any_round(self):
        for rounds in ("0", "6", "x", ""):
            with self.subTest(rounds=rounds):
                got = self.start(rounds=rounds)
                self.assertEqual((got["ok"], got["act"]), (False, "refused"), got)
                self.assertIn("rounds", got["text"])
        self.assertEqual(self.start(rounds="2", budget_usd="-1")["act"], "refused")

    def test_design_only_is_refused_before_any_round(self):
        """#505: 設計だけの run は差分を作らず次の周の基が無いので、鎖は AI の前で拒む（元 works の dev/use.sh 214 行）"""
        got = self.start(rounds="2", design_only="design_only")
        self.assertEqual((got["ok"], got["act"]), (False, "refused"), got)
        self.assertIn("design_only", got["text"])

    def test_fix_fixture_is_refused_before_any_round(self):
        """#509: 固定材料は 1 つの run の修正の前の写しで、2 周目からの依頼と木はそれと違うので、鎖は AI の前で拒む（元 works の
        dev/use.sh 215 行）"""
        got = self.start(rounds="2", fix_fixture="fixture")
        self.assertEqual((got["ok"], got["act"]), (False, "refused"), got)
        self.assertIn("fix_fixture", got["text"])

    def test_user_env_dir_is_the_chain_run_place(self):
        """hand の pr-commit が印を置く置き場は、鎖の run の置き場（ARTIFACTS_DIR）。拒んだ時は空"""
        self.assertEqual(self.start(rounds="2").get("user_env_dir"), str(self.tmp))
        self.assertEqual(self.start(rounds="0").get("user_env_dir"), "")

    def test_accepted_inputs_are_the_first_round(self):
        got = self.start(rounds="3", budget_usd="2.5", request="req.json", pr="7")
        self.assertEqual((got["ok"], got["act"], got["rounds"], got["budget"], got["rows"]), (True, "launch", 3, 2.5, []))
        self.assertEqual((got["request"], got["pr"], got["first_pr"]), ("req.json", "7", 7))
        self.assertEqual(pathlib.Path(got["first_request"]).resolve(), (self.tmp / "req.json").resolve())

    def test_origin_is_the_head_when_the_chain_starts(self):
        self.assertEqual(self.start(rounds="2")["origin"], "", "commit の無い木の元の基は空")
        (self.tmp / "a.txt").write_text("a\n", encoding="utf-8")
        git(self.tmp, "add", "-A")
        git(self.tmp, "commit", "-q", "-m", "seed")
        self.assertEqual(self.start(rounds="2")["origin"], git(self.tmp, "rev-parse", "HEAD"))

    def test_deliver_word_is_checked_before_any_round(self):
        got = self.start(rounds="2", deliver="merge")
        self.assertEqual((got["ok"], got["act"]), (False, "refused"), got)
        self.assertIn("deliver", got["text"])
        self.assertEqual((self.start(rounds="2", deliver="pr")["deliver"], self.start(rounds="2")["deliver"]), ("pr", ""))

    def test_padded_pr_is_read_like_the_main_graph(self):
        """メイングラフの入口は pr の前後の空白を除いて読む。1 周目に名指した PR を後ろの周へ運ぶ鎖も同じに読む"""
        got = self.start(rounds="2", pr=" 7 ")
        self.assertEqual((got["act"], got["pr"], got["first_pr"]), ("launch", " 7 ", 7), got)


class DecideCase(Tree):
    def decide(self, **inputs) -> dict:
        base = {"rows": "[]", "outcome": "round_limit", "rounds_max": "3", "budget": "",
                "facts": json.dumps({"ok": True, "error": "", "run": "c", "keys": ["k"], "held_rows": [], "request": "/r.json",
                                     "source": "", "cost": 1.0, "cost_read": True}),
                "commit": json.dumps({"ok": True, "changed": True, "head": "h", "reason": ""}), "apply": "null",
                "r2_status": "null", "spec_questions": "0"}
        env = {f"INPUTS_{k.upper()}": v for k, v in {**base, **inputs}.items()}
        return run_script("decide", {**env, "ARTIFACTS_DIR": str(self.tmp), "WORKFLOW_ID": "parent"}, self.tmp)

    def test_open_round_launches_with_only_the_request(self):
        got = self.decide()
        self.assertEqual((got["act"], got["request"], got["base"], got["pr"], got["spec"]), ("launch", "/r.json", "", "", ""))
        self.assertEqual(len(got["rows"]), 1)
        self.assertEqual(got["rows"][0]["kind"], chain.KIND_OPEN)

    def test_row_carries_the_child_verdict_for_the_final_diff(self):
        got = self.decide(apply=json.dumps({"ok": True, "hash": "h", "diff": None, "reason": ""}), r2_status="pass")
        self.assertEqual((got["rows"][0]["placed"], got["rows"][0]["r2_status"], got["rows"][0]["head"]), (True, "pass", "h"))
        got = self.decide(apply="null", r2_status="null")
        self.assertEqual((got["rows"][0]["placed"], got["rows"][0]["r2_status"]), (False, None))
        for given, want in (("2", 2), ("null", 0), ("true", 0)):
            with self.subTest(spec_questions=given):
                self.assertEqual(self.decide(spec_questions=given)["rows"][0]["spec_questions"], want)

    def test_failed_commit_halts_with_the_reason(self):
        got = self.decide(commit=json.dumps({"ok": False, "changed": None, "head": "", "reason": "本体の作業ツリーでは commit しない"}))
        self.assertEqual((got["act"], got["word"], got["request"]), ("stop", "halted", ""), got)
        self.assertIn("本体の作業ツリー", got["text"])

    def test_unchanged_tree_is_no_change(self):
        got = self.decide(commit=json.dumps({"ok": True, "changed": False, "head": "h", "reason": ""}))
        self.assertEqual(got["word"], "no_change")

    def facts(self, cost, cost_read=True) -> str:
        return json.dumps({"ok": True, "error": "", "run": "c2", "keys": ["k2"], "held_rows": [], "request": "/r2.json", "source": "",
                           "cost": cost, "cost_read": cost_read})

    def test_budget_input_stops_before_the_round_that_can_exceed_it(self):
        prev = [{"n": 1, "outcome": "round_limit", "kind": chain.KIND_OPEN, "keys": ["k1"], "cost": 6.0, "cost_read": True}]
        self.assertEqual(self.decide(rows=json.dumps(prev), facts=self.facts(8.0))["act"], "launch", "上限が無ければ次を起こす")
        got = self.decide(rows=json.dumps(prev), facts=self.facts(8.0), budget="10")
        self.assertEqual((got["act"], got["word"], got["request"]), ("stop", "budget", ""), got)

    def test_unread_cost_under_a_budget_is_cost_unread(self):
        got = self.decide(facts=self.facts(None, cost_read=False), budget="10")
        self.assertEqual((got["act"], got["word"]), ("stop", "cost_unread"), got)


class FinalDiffCase(Tree):
    """3 周目が halted の時、最後の差分は元の基から 2 周目までで、3 周目の差分は残して chain.md に名指す"""

    def setUp(self):
        super().setUp()
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        (self.repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "seed")
        self.artifacts = self.tmp / "runs" / "parent"
        self.artifacts.mkdir(parents=True)

    def final(self, start, *made) -> dict:
        return run_final(self.repo, self.artifacts, "parent", start, *made)

    def names(self, data: bytes) -> list:
        return sorted(re.findall(r"^diff --git a/(\S+)", data.decode("utf-8"), re.M))

    def test_halted_last_round_is_not_taken_and_its_diff_is_named(self):
        start, made = three_rounds(self.repo)
        got = self.final(start, *made)
        self.assertEqual((got["ok"], got["kept"], got["skipped"], got["outcome"]), (True, 2, [3], "round_limit"), got)
        final = self.artifacts / chain.FINAL
        self.assertEqual(self.names(final.read_bytes()), ["one.txt", "two.txt"])
        self.assertEqual(got["sealed"], {"ok": True, "hash": hashlib.sha256(final.read_bytes()).hexdigest(),
                                         "diff": {"type": "archon_artifact", "run_id": "parent", "path": "chain/final.diff"}})
        self.assertEqual(got["apply"], {**got["sealed"], "reason": ""})
        self.assertIs(got["placed"], True)
        left = self.artifacts / "chain" / "round-3.diff"
        self.assertEqual(self.names(left.read_bytes()), ["three.txt"])
        report = (self.artifacts / chain.REPORT).read_text(encoding="utf-8")
        self.assertEqual(got["report"], {"type": "archon_artifact", "run_id": "parent", "path": chain.REPORT})
        self.assertIn(f"止まった周 3: 差分 {left}", report)
        self.assertIn(f"最後の差分: {final}", report)
        self.assertIn("取り込む: bin/apply parent", report)
        self.assertIn("| 3 | child-3 | stopped_by_human | 10 | 3.00 | 1 | 1 |", report)
        self.assertIn("合計: 3 周・30 分・$6.00", report)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "", "作業ツリーを変えない")

    def test_round_without_a_placed_diff_is_sealed_but_not_placed(self):
        start, made = three_rounds(self.repo, halted_last=False, placed=())
        got = self.final(start, *made)
        self.assertEqual((got["kept"], got["sealed"]["ok"], got["apply"]["ok"], got["placed"]), (3, True, False, False), got)
        self.assertIn("差分を置かなかった", got["apply"]["reason"])

    def test_earlier_round_without_a_placed_diff_is_not_placed(self):
        """最後の差分は元の基からなので、採る周が置いても、前の周の置かなかった変更が入る"""
        start, made = three_rounds(self.repo, halted_last=False, placed=(2, 3))
        got = self.final(start, *made)
        self.assertEqual((got["kept"], got["apply"]["ok"]), (3, False), got)
        self.assertIn("周 1（結末 round_limit）", got["apply"]["reason"])
        self.assertNotIn("周 3", got["apply"]["reason"])

    def test_r2_status_is_the_kept_round_unless_a_carried_round_said_redesign(self):
        for r2, want in (({2: "pass"}, "pass"), ({1: "redesign-needed", 2: "pass"}, "redesign-needed"),
                         ({3: "redesign-needed"}, None)):
            with self.subTest(r2=r2):
                tree = self.tmp / f"repo-{len(r2)}-{want}"
                git(self.tmp, "clone", "-q", str(self.repo), str(tree))
                start, made = three_rounds(tree, r2=r2)
                got = run_final(tree, self.artifacts, "parent", start, *made)
                self.assertEqual((got["kept"], got["r2_status"]), (2, want), got)

    def test_spec_questions_add_up_over_the_carried_rounds(self):
        """前の周の変更も最後の差分に入るので、その周の問いも数える。止まって採らなかった 3 周目の問いは数えない"""
        start, made = three_rounds(self.repo, spec={1: 1, 2: 2, 3: 4})
        got = self.final(start, *made)
        self.assertEqual((got["kept"], got["spec_questions"]), (2, 3), got)

    def test_round_whose_diff_cannot_be_made_names_the_round_and_child_run(self):
        """最後の差分を残りの周だけで作らない。止まりの訳（result の stop_reason）が周の番号と子の run の id を名指す"""
        start, made = three_rounds(self.repo, halted_last=False)
        self.final(start, *made)
        broken = [{**d, "rows": [{**r, "head": "0" * 40} if r["n"] == 2 else r for r in d["rows"]]} for d in made]
        got = self.final(start, *broken)
        self.assertEqual((got["ok"], got["sealed"], got["apply"]), (False, None, None), got)
        self.assertIn("周 2（d2・子の run child-2）の差分を作れない", got["reason"])
        self.assertFalse((self.artifacts / chain.FINAL).exists(), "前の最後の差分が残った")
        self.assertFalse((self.artifacts / chain.REPORT).exists(), "前の最後の差分を名指す chain.md が残った")
        self.assertEqual(run_result(start, got, *broken, artifacts=self.artifacts)["stop_reason"], got["reason"])

    def test_nothing_to_take_leaves_no_final_diff(self):
        start, made = three_rounds(self.repo)
        self.final(start, *made)
        halted = [{**d, "rows": [{**r, "kind": chain.KIND_HALTED} for r in d["rows"]]} for d in made]
        got = self.final(start, *halted)
        self.assertEqual((got["ok"], got["kept"], got["skipped"], got["sealed"], got["apply"]), (False, 0, [3, 2, 1], None, None))
        self.assertFalse((self.artifacts / chain.FINAL).exists(), "前の最後の差分が残った")
        self.assertIn("採れる周が無かった", (self.artifacts / chain.REPORT).read_text(encoding="utf-8"))

    def test_result_and_the_report_read_the_same_rounds_and_stop(self):
        """result は lib を読まないので、周の決め d<k> の読み（行・最後の決めが launch なら止めていない）を final-diff と別に持つ。
        同じ決めから、chain.md の表と result の rounds が同じ周を並べ、止めた訳の有無が result の act と合うことをここで縛る"""
        start, made = three_rounds(self.repo)
        for decisions, act in ((made, "stop"), (made[:2], "wait")):
            with self.subTest(rounds=len(decisions)):
                self.final(start, *decisions)
                report = (self.artifacts / chain.REPORT).read_text(encoding="utf-8")
                got = run_result(start, None, *decisions, artifacts=self.artifacts)
                table = [int(n) for n in re.findall(r"^\| (\d+) \|", report, re.M)]
                self.assertEqual([r["n"] for r in got["rounds"]], table)
                self.assertEqual(got["act"], act)
                self.assertEqual("止めていない" in report, act == "wait", report)

    def test_refused_start_returns_nothing_and_leaves_no_earlier_report(self):
        start, made = three_rounds(self.repo)
        self.final(start, *made)
        got = self.final({"ok": False, "reason": "rounds は 1〜5"})
        self.assertEqual((got["ok"], got["reason"], got["sealed"], got["report"]), (False, "rounds は 1〜5", None, None))
        self.assertFalse((self.artifacts / chain.FINAL).exists(), "前の最後の差分が残った")
        self.assertFalse((self.artifacts / chain.REPORT).exists(), "前の最後の差分を名指す chain.md が残った")


class ResultCase(Tree):
    def result(self, start, *decisions, final=None) -> dict:
        return run_result(start, final, *decisions, artifacts=self.tmp)

    def test_final_diff_fields_are_the_ones_bin_apply_reads(self):
        start = {"ok": True, "reason": "", "act": "launch", "word": "", "text": "", "rows": []}
        decided = {"act": "stop", "word": "closed", "text": "t", "request": "", "rows": [{"n": 1}]}
        sealed = {"ok": True, "hash": "h", "diff": {"type": "archon_artifact", "run_id": "parent", "path": "chain/final.diff"}}
        final = {"ok": True, "reason": "", "apply": {**sealed, "reason": ""}, "sealed": sealed, "report": {"path": "chain.md"},
                 "kept": 1, "skipped": [], "outcome": "fixed", "r2_status": "pass", "spec_questions": 2}
        got = self.result(start, decided, final=final)
        self.assertEqual({k: got[k] for k in ("apply", "sealed", "report", "outcome", "r2_status", "spec_questions")},
                         {"apply": final["apply"], "sealed": sealed, "report": {"path": "chain.md"}, "outcome": "fixed",
                          "r2_status": "pass", "spec_questions": 2})
        self.assertEqual(got["stop_reason"], "")
        got = self.result(start, decided)
        self.assertEqual((got["apply"], got["sealed"], got["report"], got["outcome"], got["r2_status"], got["spec_questions"]),
                         (None, None, None, "", None, 0))
        self.assertIn("final-diff の出力が無い", got["stop_reason"])

    def test_why_nothing_was_placed_is_the_stop_reason(self):
        start = {"ok": True, "reason": "", "act": "launch", "word": "", "text": "", "rows": []}
        decided = {"act": "stop", "word": "halted", "text": "t", "request": "", "rows": [{"n": 1}]}
        final = {"ok": False, "reason": "採れる周が無い", "apply": None, "sealed": None, "report": None, "kept": 0, "skipped": [1],
                 "outcome": "", "r2_status": None}
        self.assertEqual(self.result(start, decided, final=final)["stop_reason"], "採れる周が無い")
        sealed = {"ok": True, "hash": "h", "diff": None}
        final = {**final, "ok": True, "reason": "", "sealed": sealed, "apply": {**sealed, "ok": False, "reason": "周 1 が置かなかった"}}
        self.assertEqual(self.result(start, decided, final=final)["stop_reason"], "周 1 が置かなかった")

    def test_deliver_is_the_hand_return_only_for_the_word_pr(self):
        start = {"ok": True, "reason": "", "act": "launch", "word": "", "text": "", "rows": [], "deliver": ""}
        decided = {"act": "stop", "word": "closed", "text": "t", "request": "", "rows": [{"n": 1}]}
        made = {"act": "pr", "pr": {"number": 7, "url": "https://github.com/o/r/pull/7", "is_draft": True}, "reason": ""}
        self.assertIsNone(self.result(start, decided)["deliver"])
        start["deliver"] = "pr"
        env = {"INPUTS_START": json.dumps(start), "INPUTS_FINAL": "null", "INPUTS_HAND": json.dumps(made),
               "INPUTS_D1": json.dumps(decided), "ARTIFACTS_DIR": str(self.tmp), "WORKFLOW_ID": "parent"}
        self.assertEqual(run_script("result", env, self.tmp)["deliver"], made)
        unplaced = {"ok": False, "reason": "採れる周が無い", "apply": None, "sealed": None, "placed": False}
        got = self.result(start, decided, final=unplaced)["deliver"]
        self.assertEqual((got["act"], got["pr"]), ("stopped", None))
        self.assertIn("採れる周が無い", got["reason"])
        got = self.result(start, decided, final={**unplaced, "ok": True, "placed": True})["deliver"]
        self.assertEqual(got["act"], "unconfirmed", "差分を置いた後の hand の中で push や PR の作成が済んだかもしれない")
        self.assertIn("出力が無い", got["reason"])

    def test_pr_word_is_the_entry_word(self):
        """result は lib を読まないので出口の語 pr を字で持つ。lib/entry の DELIVER_PR と同じことをここで縛る"""
        spec = importlib.util.spec_from_file_location("chain_result", SCRIPTS / "result.py")
        script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(script)
        import entry
        self.assertEqual(script.PR, entry.DELIVER_PR)

    def test_launch_without_the_next_decision_is_wait(self):
        start = {"ok": True, "reason": "", "act": "launch", "word": "", "text": "", "rows": []}
        got = self.result(start, None)
        self.assertEqual((got["act"], got["closed"]), ("wait", False), got)
        self.assertIn("1 周目", got["text"])
        row = {"n": 1, "request": "/r1.json", "act": "launch"}
        got = self.result(start, {"act": "launch", "word": "", "text": "", "request": "/r1.json", "rows": [row]}, None)
        self.assertEqual((got["act"], got["request"], got["rounds"]), ("wait", "/r1.json", [row]))
        self.assertIn("2 周目", got["text"])

    def test_closed_word_is_closed(self):
        start = {"ok": True, "reason": "", "act": "launch", "word": "", "text": "", "rows": []}
        got = self.result(start, {"act": "stop", "word": "closed", "text": "t", "request": "", "rows": [{"n": 1}]})
        self.assertEqual((got["closed"], got["word"], got["act"]), (True, "closed", "stop"))

    def test_closed_is_a_stop_word_of_the_chain(self):
        """result は lib を読まないので止めの語 closed を字で持つ。lib/chain の STOPS の語と同じであることをここで縛る"""
        spec = importlib.util.spec_from_file_location("chain_result", SCRIPTS / "result.py")
        script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(script)
        self.assertIn(script.CLOSED, chain.STOPS)

    def test_decisions_are_read_in_round_order_up_to_the_last_round(self):
        start = {"ok": True, "reason": "", "act": "launch", "word": "", "text": "", "rows": []}
        made = [{"act": "launch", "word": "", "text": "", "request": f"/r{k}.json", "rows": [{"n": n} for n in range(1, k + 1)]}
                for k in range(1, chain.MAX_ROUNDS)]
        last = {"act": "stop", "word": "closed", "text": "t", "request": "", "rows": [{"n": n} for n in range(1, chain.MAX_ROUNDS + 1)]}
        got = self.result(start, *made, last)
        self.assertEqual((got["closed"], got["act"], len(got["rounds"])), (True, "stop", chain.MAX_ROUNDS), got)


class ShapeCase(unittest.TestCase):
    """グラフの形の約束（Archon を起こさない）"""

    def test_node_ids_are_the_start_the_rounds_and_the_result(self):
        want = {"chain-start", "final-diff", "hand", "result"} | {f"round-{k}{tail}" for k in range(1, chain.MAX_ROUNDS + 1)
                                                    for tail in ("", "-commit", "-facts", "-decide")}
        self.assertEqual(set(NODES), want)
        self.assertEqual(len(CHAIN["nodes"]), 4 + 4 * chain.MAX_ROUNDS)

    def test_children_never_deliver_and_the_parent_hands_once(self):
        """周の子は出口の語を空で受けて PR を作らない。出口の語 pr の時だけ、親が最後の差分を封じた後にブロック merge を 1 度 include
        して PR を 1 本作る"""
        for k in range(1, chain.MAX_ROUNDS + 1):
            with self.subTest(round=k):
                self.assertEqual(NODES[f"round-{k}"]["with"]["deliver"], "")
        hand = NODES["hand"]
        self.assertEqual((hand["include"], hand["depends_on"]), ("works-factory-merge", ["final-diff"]))
        self.assertEqual(hand["when"], "$chain-start.output.deliver == 'pr' && $final-diff.output.placed == true")
        self.assertEqual(hand["with"], {"mode": "check", "base_rev": "$chain-start.output.origin",
                                        "sealed_hash": "$final-diff.output.sealed.hash", "deliver": "$chain-start.output.deliver",
                                        "request": "$chain-start.output.first_request",
                                        "user_env_dir": "$chain-start.output.user_env_dir"})
        self.assertEqual(NODES["result"]["with"]["hand"], {"from": "$hand.output.deliver", "if_skipped": None})

    def test_round_groups_differ_only_by_number_and_previous_decision(self):
        first = shape(1)
        for k in range(2, chain.MAX_ROUNDS + 1):
            with self.subTest(round=k):
                self.assertEqual(shape(k), first)

    def test_round_bodies_are_written_once(self):
        """周の 4 つのノードの本体（子の workflow と commit・facts・decide の script）は YAML の字に 1 度だけ在り、2〜5 周目はアンカーで受ける
        （周ごとに書き写すと、1 周だけ直して形が分かれる）"""
        text = (FOLDER / "works-factory-chain.yaml").read_text(encoding="utf-8")
        for body in ("workflow: works-factory-line", "script: round_commit", "script: round_facts", "script: decide"):
            with self.subTest(body=body):
                self.assertEqual(len(re.findall(rf"^\s*{re.escape(body)}\s*$", text, re.M)), 1)

    def test_rounds_launch_the_main_graph_on_launch(self):
        for k in range(1, chain.MAX_ROUNDS + 1):
            with self.subTest(round=k):
                node = NODES[f"round-{k}"]
                self.assertEqual(node["workflow"], archon.PACK["ours"]["line"])
                self.assertEqual(node["when"], f"${prev_of(k)}.output.act == 'launch'")
                self.assertEqual(set(node["with"]), set(LINE["inputs"]))
                for name in ("request", "base", "pr", "spec"):
                    self.assertEqual(node["with"][name], f"${prev_of(k)}.output.{name}")

    def test_inputs_are_the_main_graph_inputs_and_the_chain_limits(self):
        self.assertEqual(set(CHAIN["inputs"]), set(LINE["inputs"]) | {"rounds", "budget_usd"})
        for name, spec in LINE["inputs"].items():
            self.assertEqual(CHAIN["inputs"][name].get("default"), spec.get("default"), name)

    def test_head_has_no_interactive_and_returns_closed(self):
        self.assertNotIn("interactive", CHAIN)
        self.assertEqual((CHAIN["returns"], CHAIN["outcome_field"]), ("result", "closed"))

    def test_head_pins_the_run_worktree(self):
        """周の commit は run の作業ツリーの枝に積む。--no-worktree で利用者の作業ツリーに走らせない（Archon が起動を拒む）"""
        self.assertEqual(CHAIN.get("worktree"), {"enabled": True})

    def test_decisions_read_the_limits_from_the_start(self):
        for k in range(1, chain.MAX_ROUNDS + 1):
            with self.subTest(round=k):
                bound = NODES[f"round-{k}-decide"]["with"]
                self.assertEqual((bound["rounds_max"], bound["budget"]),
                                 ("$chain-start.output.rounds", "$chain-start.output.budget"))

    def test_final_diff_and_result_read_the_start_and_every_round_decision(self):
        rounds = range(1, chain.MAX_ROUNDS + 1)
        for name, extra in (("final-diff", set()), ("result", {"final", "hand"})):
            with self.subTest(node=name):
                node = NODES[name]
                self.assertEqual(set(node["with"]), {"start"} | {f"d{k}" for k in rounds} | extra)
                for k in rounds:
                    self.assertEqual(node["with"][f"d{k}"], {"from": f"$round-{k}-decide.output", "if_skipped": None})
                self.assertEqual(set(node["depends_on"]), {"chain-start"} | {f"round-{k}-decide" for k in rounds}
                                 | ({"final-diff", "hand"} if extra else set()))
                self.assertEqual((node["trigger_rule"], node["always_run"]), ("all_done", True))
        self.assertEqual(NODES["result"]["with"]["final"], {"from": "$final-diff.output", "if_skipped": None})

    def test_decisions_read_the_child_verdict(self):
        for k in range(1, chain.MAX_ROUNDS + 1):
            with self.subTest(round=k):
                bound = NODES[f"round-{k}-decide"]["with"]
                self.assertEqual((bound["apply"], bound["r2_status"], bound["spec_questions"]),
                                 (f"$round-{k}.output.apply", f"$round-{k}.output.r2_status",
                                  f"$round-{k}.output.spec_questions"))


class ChainScenariosTest(unittest.TestCase):
    """筋書きの合否（workflow test）と、決めの語（dry-run の trace）。Archon の源か bun が無ければ見送る"""

    @classmethod
    def setUpClass(cls):
        with archon.tree(["chain", "merge"]) as tree:
            cls.results = scenarios(archon.archon(tree, "workflow", "test", NAME, "--cwd", str(tree), "--json"))
        cls.traces = dry_run_traces("chain", NAME, ["chain", "merge"], SCENARIOS)

    def out(self, scenario: str, node: str) -> dict:
        return json.loads(self.traces[scenario][node]["output"])

    def ran(self, scenario: str, node: str) -> bool:
        trace = self.traces[scenario]
        return node in trace and trace[node]["state"] in ("completed", "stubbed")

    def test_every_scenario_passes(self):
        self.assertEqual(sorted(self.results), sorted(SCENARIOS))
        for name, got in self.results.items():
            with self.subTest(scenario=name):
                self.assertTrue(got["pass"], json.dumps(got, ensure_ascii=False))

    def test_carried_request_reaches_the_next_child_and_fixed_closes(self):
        trace = self.traces["limit-then-fixed"]
        carried = self.out("limit-then-fixed", "round-1-facts")["request"]
        self.assertEqual(bound(trace, NODES["round-2"]["with"]["request"]), carried)
        for name in ("base", "pr", "spec"):
            self.assertEqual(bound(trace, NODES["round-2"]["with"][name]), "", name)
        self.assertEqual(self.out("limit-then-fixed", "round-2-decide")["word"], "closed")
        self.assertFalse(self.ran("limit-then-fixed", "round-3"))
        self.assertIs(self.out("limit-then-fixed", "result")["closed"], True)
        self.assertEqual(self.out("limit-then-fixed", "result")["sealed"], self.out("limit-then-fixed", "final-diff")["sealed"])

    def test_default_word_hands_nothing_and_the_word_pr_makes_one_pr_in_the_parent(self):
        for scenario in SCENARIOS[:-1]:
            with self.subTest(scenario=scenario):
                self.assertFalse(self.ran(scenario, "hand__pr-commit"))
                self.assertFalse(self.ran(scenario, "hand__pr-open"))
                self.assertIsNone(self.out(scenario, "result")["deliver"])
        trace = self.traces["deliver-pr"]
        self.assertEqual(bound(trace, NODES["round-1"]["with"]["deliver"]), "", "周の子は PR を作らない")
        self.assertEqual(self.out("deliver-pr", "result")["deliver"],
                         {"act": "pr", "pr": {"number": 9, "url": "https://github.com/owner/repo/pull/9", "is_draft": True}, "reason": ""})

    def test_rounds_reached_skips_the_next_round(self):
        self.assertEqual(self.out("rounds-reached", "round-2-decide")["word"], "rounds_reached")
        self.assertFalse(self.ran("rounds-reached", "round-3"))

    def test_needs_human_stops_before_the_next_round(self):
        self.assertEqual(self.out("needs-human", "round-1-decide")["word"], "human")
        self.assertFalse(self.ran("needs-human", "round-2"))

    def test_same_keys_stop_with_same_items(self):
        self.assertEqual(self.out("same-items", "round-2-decide")["word"], "same_items")
        self.assertFalse(self.ran("same-items", "round-3"))

    def test_interrupted_child_does_not_launch_the_next(self):
        self.assertEqual(self.out("interrupted", "round-1-decide")["act"], "aborted")
        self.assertFalse(self.ran("interrupted", "round-2"))

    def test_failed_child_skips_the_decision_and_the_result_says_wait(self):
        """wait の 2 つ目の形: 子が落ちると親の周のノードが落ち、決めは走らない。親の出力は落ちずに wait を返す"""
        self.assertEqual(self.traces["child-failed"]["round-1"]["state"], "failed")
        self.assertFalse(self.ran("child-failed", "round-1-decide"))
        got = self.out("child-failed", "result")
        self.assertEqual((got["act"], got["closed"]), ("wait", False), got)

    def test_out_of_range_rounds_stop_before_any_child(self):
        self.assertEqual(self.out("refused", "chain-start")["act"], "refused")
        self.assertFalse(self.ran("refused", "round-1"))
        self.assertEqual(self.out("refused", "result")["ok"], False)

    def test_result_lists_each_round_decision(self):
        for scenario, words in (("limit-then-fixed", ["", "closed"]), ("rounds-reached", ["", "rounds_reached"]),
                                ("needs-human", ["human"]), ("same-items", ["", "same_items"]), ("interrupted", [""])):
            with self.subTest(scenario=scenario):
                rounds = self.out(scenario, "result")["rounds"]
                self.assertEqual([r["word"] for r in rounds], words)
                self.assertTrue(all({"act", "word", "text"} <= set(r) for r in rounds))


if __name__ == "__main__":
    unittest.main()

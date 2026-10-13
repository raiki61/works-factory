"""周の鎖 works-factory-chain（workflows/chain/）の script・グラフの形・筋書きの試験。

script は子のプロセスとして使い捨ての置き場（runs/<親>・runs/<子>）・run の記録・git の木で走らせる（Archon を起こさない）。
グラフの形は YAML を読んで照らす（5 組の周のノードが番号と前の決めのほかは同じ形・子へ渡す入力がメイングラフの入力と同じ）。
筋書き（workflows/chain/fixtures/）は止めた Archon の `workflow test` で合否を、`workflow run --dry-run` の trace で決めの語を照らす
（子の run と、読み書きをするノード round-k-commit・round-k-facts は stub で差し、chain-start・round-k-decide・result は本当に走る）。
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests import archon
from tests.bin.gitkit import git
from tests.e2e.test_line_scenarios import bound, dry_run_traces, scenarios

ROOT = archon.ROOT
FOLDER = ROOT / "workflows" / "chain"
SCRIPTS = FOLDER / "scripts"
CHAIN = yaml.safe_load((FOLDER / "works-factory-chain.yaml").read_text(encoding="utf-8"))
LINE = yaml.safe_load((ROOT / "workflows" / "line" / "works-factory-line.yaml").read_text(encoding="utf-8"))
NAME = CHAIN["name"]
SCENARIOS = ("limit-then-fixed", "rounds-reached", "needs-human", "same-items", "interrupted", "child-failed", "refused")

if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))
import carry  # noqa: E402
import chain  # noqa: E402

NODES = {n["id"]: n for n in CHAIN["nodes"]}


def run_script(name: str, env: dict, cwd: pathlib.Path) -> dict:
    """鎖の script を Archon と同じく子のプロセスで走らせ、標準出力の JSON を返す"""
    keep = {k: v for k, v in os.environ.items() if not k.startswith("INPUTS_") and k not in ("ARTIFACTS_DIR", "WORKFLOW_ID", "LOG_DIR")}
    done = subprocess.run([sys.executable, str(SCRIPTS / f"{name}.py")], cwd=cwd, env={**keep, "PYTHONDONTWRITEBYTECODE": "1", **env},
                          capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise AssertionError(f"{name} が終了の値 {done.returncode}: {done.stderr}")
    return json.loads(done.stdout)


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

    def test_accepted_inputs_are_the_first_round(self):
        got = self.start(rounds="3", budget_usd="2.5", request="req.json", pr="7")
        self.assertEqual((got["ok"], got["act"], got["rounds"], got["budget"], got["rows"]), (True, "launch", 3, 2.5, []))
        self.assertEqual((got["request"], got["pr"], got["first_pr"]), ("req.json", "7", 7))
        self.assertEqual(pathlib.Path(got["first_request"]).resolve(), (self.tmp / "req.json").resolve())


class DecideCase(Tree):
    def decide(self, **inputs) -> dict:
        base = {"rows": "[]", "outcome": "round_limit", "rounds_max": "3", "budget": "",
                "facts": json.dumps({"ok": True, "error": "", "run": "c", "keys": ["k"], "held_rows": [], "request": "/r.json",
                                     "source": "", "cost": 1.0, "cost_read": True}),
                "commit": json.dumps({"ok": True, "changed": True, "head": "h", "reason": ""})}
        env = {f"INPUTS_{k.upper()}": v for k, v in {**base, **inputs}.items()}
        return run_script("decide", {**env, "ARTIFACTS_DIR": str(self.tmp), "WORKFLOW_ID": "parent"}, self.tmp)

    def test_open_round_launches_with_only_the_request(self):
        got = self.decide()
        self.assertEqual((got["act"], got["request"], got["base"], got["pr"], got["spec"]), ("launch", "/r.json", "", "", ""))
        self.assertEqual(len(got["rows"]), 1)
        self.assertEqual(got["rows"][0]["kind"], chain.KIND_OPEN)

    def test_failed_commit_halts_with_the_reason(self):
        got = self.decide(commit=json.dumps({"ok": False, "changed": None, "head": "", "reason": "本体の作業ツリーでは commit しない"}))
        self.assertEqual((got["act"], got["word"], got["request"]), ("stop", "halted", ""), got)
        self.assertIn("本体の作業ツリー", got["text"])

    def test_unchanged_tree_is_no_change(self):
        got = self.decide(commit=json.dumps({"ok": True, "changed": False, "head": "h", "reason": ""}))
        self.assertEqual(got["word"], "no_change")


class ResultCase(Tree):
    def result(self, start, *decisions) -> dict:
        env = {"INPUTS_START": json.dumps(start)}
        env.update({f"INPUTS_D{i}": json.dumps(d) for i, d in enumerate(decisions, 1)})
        return run_script("result", {**env, "ARTIFACTS_DIR": str(self.tmp), "WORKFLOW_ID": "parent"}, self.tmp)

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


class ShapeCase(unittest.TestCase):
    """グラフの形の約束（Archon を起こさない）"""

    def test_node_ids_are_the_start_the_rounds_and_the_result(self):
        want = {"chain-start", "result"} | {f"round-{k}{tail}" for k in range(1, chain.MAX_ROUNDS + 1)
                                            for tail in ("", "-commit", "-facts", "-decide")}
        self.assertEqual(set(NODES), want)
        self.assertEqual(len(CHAIN["nodes"]), 2 + 4 * chain.MAX_ROUNDS)

    def test_round_groups_differ_only_by_number_and_previous_decision(self):
        first = shape(1)
        for k in range(2, chain.MAX_ROUNDS + 1):
            with self.subTest(round=k):
                self.assertEqual(shape(k), first)

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


class ChainScenariosTest(unittest.TestCase):
    """筋書きの合否（workflow test）と、決めの語（dry-run の trace）。Archon の源か bun が無ければ見送る"""

    @classmethod
    def setUpClass(cls):
        with archon.tree(["chain"]) as tree:
            cls.results = scenarios(archon.archon(tree, "workflow", "test", NAME, "--cwd", str(tree), "--json"))
        cls.traces = dry_run_traces("chain", NAME, ["chain"], SCENARIOS)

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

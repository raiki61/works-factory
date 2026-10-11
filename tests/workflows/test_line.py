"""線の script（workflows/line/scripts/）の決めを、関数を直に呼んで照らす。

筋書き（tests/e2e/test_line_scenarios.py）は関所の答えを stub で差し、往復を 1 周で終えるので、関所の答えの読み・往復の抜け方・
入口の拒み・返りの合わせ方はここで照らす。種の git は gitkit の型の写し。
"""
import json
import os
import pathlib
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
ask_before_fix = load("ask_before_fix")
ask_replan = load("ask_replan")
ask_final = load("ask_final")
plan_out = load("plan_out")
after_fix = load("after_fix")
judged = load("judged")
fixed = load("fixed")
redepth = load("redepth")
planned_node = load("planned")
collect = load("collect")
result = load("result")

import answer  # noqa: E402  （線の script が lib/ を sys.path に足した後に読む）
import gatemarks  # noqa: E402
import stopby  # noqa: E402

SEED = SCRIPTS.parents[2] / "tests" / "e2e" / "target-seed"
RUN = "run-1"
LINE = yaml.safe_load((SCRIPTS.parent / "works-factory-line.yaml").read_text(encoding="utf-8"))


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
                self.assertEqual((got["ok"], got["stop_reason"], got["ask"]), (False, linekit.START_REFUSED, False), got)
                self.assertIn(words, got["reason"])
                self.assertEqual(self.record(got)["refused"], got["reason"])


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

    def test_objection_left_after_the_rejudge_is_a_reason(self):
        self.assertIn("止めずに残った異議が在る", ask_final.final_needs(self.got(objection="異議", rejudge_verdict="退ける")))
        self.assertEqual(ask_final.final_needs(self.got(objection="異議", rejudge_verdict="採る")), [])


class AskFinalReadsCase(Artifacts):
    """最後の関所が指し札の先から読む物: 判定の保留の問い（judgment.json）と直した後の実測（structure-after.json）"""

    def place(self, rel, doc):
        path = self.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return {"type": "archon_artifact", "run_id": RUN, "path": rel}

    def test_held_questions_come_from_the_judgment(self):
        fork = {"key": "q1", "kind": "fork", "status": "held", "origin": "u1", "options": ["a", "b"], "reason": "割れる"}
        ptr = self.place("judge/judgment.json", {"units": [], "questions": [
            fork, {**fork, "key": "q2", "status": "answered"}, {**fork, "key": "q3", "kind": "awaiting", "status": "escalate"}]})
        held, unread = ask_final.held_questions(ptr, answered=False)
        self.assertEqual(([q.split("（")[0] for q in held], unread), ([f"{gatemarks.ASK_HEAD} q1", f"{gatemarks.ASK_HEAD} q3"], ""))
        self.assertEqual(ask_final.held_questions(ptr, answered=True), ([], ""))
        self.assertEqual(ask_final.held_questions(None, answered=False), ([], ""))

    def test_unreadable_judgment_is_said(self):
        held, unread = ask_final.held_questions({"type": "archon_artifact", "run_id": "another", "path": "x.json"}, answered=False)
        self.assertEqual(held, [])
        self.assertIn("判定の問いの控えを読めない", unread)

    def test_fence_rows_come_from_the_structure_after(self):
        rise = {"concept": "止め", "what": "語", "path": "a.py", "before": 1, "after": 2}
        ptr = self.place("eyes/structure-after.json", {"status": "ok", "reason": "", "deviations": [],
                                                       "after": {"tables": ["t"], "fence_up": [rise]}})
        self.assertEqual([row["where"] for row in ask_final.fenced_rows(ptr)], ["a.py"])
        self.assertEqual(ask_final.fenced_rows(None), [])


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


class CollectAndResultCase(unittest.TestCase):
    def line(self, **kw):
        got = {"start": "null", "prior_failures": "null",
               "stops": ["", "", "null", "", "", "", "null", "", "", "human:gate-final", "works:needs-human"],
               "gates": {"gate_start": "null", "gate_before_fix": "null", "gate_replan": "null", "gate_final": "null"},
               "deferred_questions": "null", "widened": "null", "final_reasons": "null",
               "judged": {"rejudged": "null"}, "fixed": {"conflicts": "[]"}, "redepth": {"depth": "null"}}
        got.update(kw)
        return got

    def test_skipped_include_is_null_and_strings_stay_strings(self):
        got = collect.collect({"judge": {"ready": "null", "stop_reason": "null"}, "merge_seal": {"ok": "true", "hash": "123"}},
                              self.line())
        self.assertIsNone(got["judge"])
        self.assertEqual(got["merge_seal"], {"ok": True, "hash": "123"})
        self.assertEqual((got["judged"], got["fixed"]), (None, {"conflicts": []}))

    def test_first_stop_reason_wins(self):
        self.assertEqual(collect.collect({}, self.line())["stop_reason"], "human:gate-final")

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
    止めの理由 works:line-script を持ち、関所を通さないこと"""

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

    def __init__(self):
        super().__init__()
        self.read = set()

    def get(self, key, default=None):
        self.read.add(key)
        return default


class LineWiringCase(unittest.TestCase):
    """返しの節の with: の鍵と、その script が読む INPUTS_<名> が同じ（片方だけ欄を足すと、欄が黙って報告から落ちる）"""

    READERS = {
        "plan-out": lambda: plan_out.from_env(),
        "planned": lambda: planned_node.from_env(),
        "judged": lambda: judged.from_env(),
        "fixed": lambda: fixed.from_env(),
        "collect": lambda: (collect.blocks_of_env(), collect.line_of_env()),
    }

    def test_with_keys_are_what_the_script_reads(self):
        nodes = line_nodes()
        for key, read in self.READERS.items():
            with self.subTest(node=key):
                env = Recorded()
                with mock.patch.object(os, "environ", env):
                    read()
                self.assertEqual(env.read, {f"INPUTS_{name.upper()}" for name in nodes[key]["with"]})

    def test_round_limit_is_the_loop_limit(self):
        self.assertEqual(line_nodes()["plan-rounds"]["loop_group"]["max_iterations"], plan_out.ROUND_LIMIT)


if __name__ == "__main__":
    unittest.main()

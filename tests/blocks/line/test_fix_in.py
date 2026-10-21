"""修正の段へ運ぶ値の中継 fix-in（docs/design/line.md の 4.1・5.2。元 tests/workflows/test_line.py の FixInCase）。

運ぶ欄の全部・固定材料の run（写しの値を同じ式で運ぶ）・no_fix・excluded（判定のまとめの excluded を fix の 2 段へ。8.2・
integration.md 4.1-5 の line の側）・units_tier・skip_rerun・switches・修正前の答えの方針の写し・記録された方針の行と、前の版の返り
（要る欄の欠けた got）を空と読まずに止めること（integration.md 4.3-12）を見る。
"""
import json
import pathlib
import unittest

import yaml

from tests.blocks import kit

BLOCK = "line"
U1 = "u1"
# 仕様駆動の道の配線（docs/design/spec-driven.md の 6.2）を足す前の fix-in の返り（場面の名 → 返りの全部の欄）
BEFORE_SPEC = pathlib.Path(__file__).with_name("fix_in_before_spec.json")
# 仕様駆動の run だけが渡す入力（docs/design/spec-driven.md の 6.2 の変える node の 4。ほかの run では null）
SPEC_INPUTS = ("spec", "spec_before_fix_go", "spec_before_fix_answer", "spec_before_fix_policy", "spec_deferred", "spec_passes")


def line_node(node_id: str) -> dict:
    doc = yaml.safe_load((kit.BLOCKS / BLOCK / f"works-factory-{BLOCK}.yaml").read_text(encoding="utf-8"))
    return next(n for n in doc["nodes"] if n["id"] == node_id)


class FixInCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, BLOCK)

    def ptr(self, rel, doc=None):
        if doc is not None:
            path = self.run.artifacts / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": rel}

    def judge(self, **kw):
        names = ("judgment", "answer_ties", "out_of_purpose", "materials", "brief", "inputs", "purpose", "constraints", "world", "spec",
                 "excluded", "decisions", "tier_record", "verify")
        return {"ok": True, "stop_reason": "", "ready": True, "units": [{"id": U1, "paths": ["a.py"], "summary": "s"}],
                "purpose_text": "P", "means": ["m"], "tier": "軽量", **{n: self.ptr(f"judge/{n}.json") for n in names}, **kw}

    def rounds(self, **kw):
        plan = self.ptr("plan/plan-fields.json", {"fields": [{"unit_keys": [U1], "allowed_paths": ["a.py"], "tests": [], "rewrite_tests": []}]})
        return {"ok": True, "status": "ok", "round": 2, "record": self.ptr("plan-converge.json"), "plan": plan,
                "fix_plan": self.ptr("plan/fix-plan.json"), "reply": self.ptr("plan/reply.json"), "handoffs": [{"round": 1}],
                "ripple": self.ptr("plan/ripple.json"), "owed": [U1], "review": self.ptr("plan-review/review.json"), **kw}

    def inputs(self, **kw):
        base = {"fixture": "null", "start_go": "true",
                "ports": {"policy": "/p/frozen.md", "forced": "", "has_checks": True, "tree_named": ""},
                "test_gate_base": {"baseline": self.ptr("test-gate/baseline.json"), "suite": "/s/run.sh"},
                "judge": self.judge(), "tiers": {"tier": "軽量", "omits": True, "merge": True, "tree": "off", "adds": [], "lines": ["l"],
                                                 "stop_reason": ""},
                "structure": {"structure": self.ptr("structure/structure.json")},
                "design": {"design": self.ptr("independent-design/design.json"), "reason": "", "premises": None, "stop_reason": ""},
                "rounds": self.rounds(), "before_fix_go": True, "before_fix_answer": {"decision": "approve", "text": "", "asked": []},
                "before_fix_policy": None, "deferred": [], "passes": ["通した行"], "recorded": [{"source": "answer", "name": "q", "text": "a"}],
                **dict.fromkeys(SPEC_INPUTS, "null")}
        base.update(kw)
        return {k: v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for k, v in base.items()}

    def fix_in(self, **kw):
        return self.run.script("fix_in", **self.inputs(**kw))

    def test_every_carried_field_is_flat(self):
        got = self.fix_in()
        self.assertEqual(set(got), set(line_node("fix-in")["output_format"]["required"]))
        self.assertEqual((got["go"], got["no_fix"], got["stop_reason"]), (True, False, ""))
        self.assertEqual(got["excluded"], self.ptr("judge/excluded.json"), "外した hunk は判定のまとめの excluded（8.2）")
        self.assertEqual((got["baseline"], got["suite"]), (self.ptr("test-gate/baseline.json"), "/s/run.sh"))
        self.assertEqual((got["structure"], got["design"], got["design_reason"]),
                         (self.ptr("structure/structure.json"), self.ptr("independent-design/design.json"), ""))
        self.assertEqual((got["plan"], got["review"], got["round"], got["owed"]), (self.rounds()["plan"], self.rounds()["review"], 2, [U1]))
        self.assertEqual((got["purpose_text"], got["means"], got["units"][0]["id"]), ("P", ["m"], U1))
        self.assertEqual(got["policy"], "/p/frozen.md", "修正前の答えが固め直さなければ配る値の方針の写し")
        self.assertEqual((got["passes"], got["recorded"][0]["source"]), (["通した行"], "answer"))
        self.assertEqual(got["answer"]["decision"], "approve")

    def test_unit_tier_and_switches(self):
        got = self.fix_in()
        self.assertEqual([(r["unit_id"], r["depth"]) for r in got["units_tier"]], [(U1, "軽量")])
        self.assertEqual(got["skip_rerun"], [U1], "段が省く物を持つ時だけ軽量の単位の走らせ直しを省く")
        self.assertEqual((got["switches"]["tier"], got["switches"]["merge"], got["switches"]["tree"]), ("軽量", True, "off"))
        standard = self.fix_in(tiers={"tier": "標準", "omits": False, "merge": False, "tree": "auto", "adds": [], "lines": []})
        self.assertEqual(standard["skip_rerun"], [])
        forced = self.fix_in(ports={"policy": "", "forced": "標準", "has_checks": True, "tree_named": ""})
        self.assertEqual(forced["units_tier"][0]["depth"], "標準", "thickness の名指しで固定する")
        unchecked = self.fix_in(ports={"policy": "", "forced": "", "has_checks": False, "tree_named": ""})
        self.assertEqual(unchecked["units_tier"][0]["depth"], "標準", "機械の確かめが無ければ標準")

    def test_refrozen_policy_reaches_the_later_nodes(self):
        self.assertEqual(self.fix_in(before_fix_policy="/p/refrozen.md")["policy"], "/p/refrozen.md")

    def test_not_approved_does_not_go(self):
        got = self.fix_in(before_fix_go="null", before_fix_answer="null")
        self.assertEqual((got["go"], got["answer"]), (False, None))
        self.assertFalse((self.run.artifacts / "fixture").exists())

    def test_no_fix_marks(self):
        """直す物が無い周の印: 判定が止めずに直す単位を出さなかったか、計画の status が nothing_owed"""
        self.assertTrue(self.fix_in(judge=self.judge(ready=False), rounds="null", before_fix_go="null")["no_fix"])
        self.assertTrue(self.fix_in(rounds=self.rounds(ok=False, status="nothing_owed"))["no_fix"])
        self.assertFalse(self.fix_in(judge=self.judge(ok=False, ready=False, stop_reason="works:judge"), rounds="null")["no_fix"],
                         "判定が止めた run は直す物が無い周でない")

    def test_fixture_run_carries_the_copy(self):
        """固定材料の run: start が置いた運ぶ値を同じ式で平らにし、go は起動の承認。判定・計画・修正前の承認は飛んでいる"""
        received = {name: json.loads(self.inputs()[name]) for name in ("test_gate_base", "judge", "tiers", "structure", "design", "rounds")}
        received.update({"gate_before_fix": {"decision": "approve", "text": "", "asked": []}, "before_fix_policy": None, "deferred": [],
                         "passes": [], "recorded": []})
        carried = self.ptr("fixture-in/carried.json", received)
        skipped = {name: "null" for name in ("test_gate_base", "judge", "tiers", "structure", "design", "rounds", "before_fix_go",
                                             "before_fix_answer", "before_fix_policy", "deferred", "passes", "recorded")}
        got = self.fix_in(fixture=carried, **skipped)
        self.assertEqual((got["go"], got["no_fix"], got["excluded"], got["received"]["judge"]["tier"]),
                         (True, False, self.ptr("judge/excluded.json"), "軽量"))
        self.assertEqual(got["units_tier"][0]["depth"], "軽量")
        self.assertEqual(self.fix_in(fixture=carried, start_go="false", **skipped)["go"], False)

    def test_older_returns_are_not_read_as_empty(self):
        """要る欄の欠けた got（前の版の返りを resume で受けた）は空と読まずに止める（integration.md 4.3-12）"""
        judge = self.judge()
        del judge["excluded"]
        got = self.fix_in(judge=judge)
        self.assertEqual((got["go"], got["stop_reason"]), (False, "works:line-script"))
        rounds = self.rounds()
        del rounds["review"]
        self.assertEqual(self.fix_in(rounds=rounds)["stop_reason"], "works:line-script")

    def test_a_fall_keeps_its_reason_and_names_the_broken_start_record(self):
        """受け取りに落ちた訳は返りの reason に載る（壊れた始めの記録 start.json の名が報告まで届く）。落ちない時は空"""
        self.assertEqual(self.fix_in()["reason"], "")
        broken = self.run.artifacts / "r1" / "start.json"
        broken.parent.mkdir(parents=True, exist_ok=True)
        broken.write_text("{not json", encoding="utf-8")
        got = self.fix_in(record=self.ptr("r1/start.json"))
        self.assertEqual((got["go"], got["stop_reason"]), (False, "works:line-script"))
        self.assertIn("start.json", got["reason"])
        self.assertIn("JSON として読めない", got["reason"])

    def before_spec_cases(self) -> dict:
        return {"approved": {},
                "not_approved": {"before_fix_go": "null", "before_fix_answer": "null"},
                "no_fix_judge": {"judge": self.judge(ready=False), "rounds": "null", "before_fix_go": "null"},
                "nothing_owed": {"rounds": self.rounds(ok=False, status="nothing_owed")},
                "refrozen": {"before_fix_policy": "/p/refrozen.md"}}

    def spec_rounds(self, **judge):
        """spec-rounds の返り {judge, rounds}（判定の部は spec-driven.md の 6.8 の 1 の値）"""
        j = {"ok": True, "stop_reason": "", "ready": True, "units": [{"id": U1, "paths": ["a.py"], "summary": "s"}],
             "questions": [], "judgment": self.ptr("spec-diagnose/judgment.json"), "answer_ties": None, "out_of_purpose": None,
             "materials": None, "brief": None, "inputs": None, "purpose": self.ptr("spec-entry/purpose.json"), "purpose_text": "P",
             "means": [], "constraints": None, "world": None, "spec": None, "excluded": None, "decisions": None, "tier": "標準",
             "tier_record": None, "verify": None, **judge}
        return {"judge": j, "rounds": {**self.rounds(round=1, record=None, review=None, handoffs=[]), "done": True}}

    def test_spec_run_reads_the_spec_rounds_and_the_spec_gate(self):
        """仕様駆動の run（spec が在る）: 判定の部と往復の部は spec-rounds の返りから、修正前の承認の答えは spec- の付いた 4 つから取り、
        段の表（tiers）は無いので判定の部の tier で引き直す（段の表に在る語なので「段の語が表に無い」の行は出ない）"""
        skipped = dict.fromkeys(("judge", "tiers", "structure", "design", "rounds", "before_fix_go", "before_fix_answer",
                                 "before_fix_policy", "deferred", "passes", "recorded"), "null")
        got = self.fix_in(**skipped, spec=self.spec_rounds(), spec_before_fix_go=True,
                          spec_before_fix_answer={"decision": "approve", "text": "", "asked": []}, spec_before_fix_policy=None,
                          spec_deferred=[], spec_passes=["通した narrows"])
        self.assertEqual((got["go"], got["no_fix"], got["stop_reason"]), (True, False, ""), got)
        self.assertEqual((got["judgment"], got["purpose_text"], got["round"], got["review"]),
                         (self.ptr("spec-diagnose/judgment.json"), "P", 1, None))
        self.assertEqual((got["answer"]["decision"], got["passes"]), ("approve", ["通した narrows"]))
        self.assertEqual(got["switches"]["tier"], "標準")
        self.assertFalse(any("表に無い" in line for line in got["switches"]["lines"]), got["switches"]["lines"])
        self.assertIs(self.fix_in(**skipped, spec=self.spec_rounds(), spec_before_fix_go="null")["go"], False)

    def test_returns_are_the_same_as_before_the_spec_driven_wiring(self):
        """依頼の文の run の返りは、仕様駆動の道の配線を足す前と全部の欄で同じ（docs/design/spec-driven.md の 6.5 の 3）。足す前の返りは
        BEFORE_SPEC に控えた。配線を足す PR は、仕様駆動の道の入力（spec_ で始まる with:）を null で渡した返りを、この控えと照らす
        （控えは書き替えない。依頼の文の run の振る舞いを変える直しの時だけ、訳を commit に書いて取り直す）"""
        before = json.loads(BEFORE_SPEC.read_text(encoding="utf-8"))
        self.assertEqual(set(before), set(self.before_spec_cases()))
        for name, kw in self.before_spec_cases().items():
            with self.subTest(name):
                self.assertEqual(self.fix_in(**kw), before[name])


if __name__ == "__main__":
    unittest.main()

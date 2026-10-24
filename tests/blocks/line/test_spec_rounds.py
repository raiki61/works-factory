"""仕様駆動の道の node spec-rounds（workflows/line/scripts/spec_rounds.py。docs/design/spec-driven.md の 6.2 の足す node の 8・6.5 の 8・
6.8 の 1 と 2）。

判定の役（spec-diagnose）と計画の部品（spec-plan）の返りを、今の judge-out と plan-rounds-out の受け皿の got と同じ形に組み直す:
- 判定の部は fix-in が読む欄（fix_in.NAMES["judge"]）を全部持ち、値は今の本線でその欄を作る段が回らなかった run と同じ
- 往復の部は ask_before_fix が求める欄（ask_before_fix.ROUNDS の 21）を全部持ち、ok は真・status は計画の部品の語・review_status は
  ok・deviations は空
- 決まっていない narrows（decided_by が無い）は lib/gatemarks.narrow_asks で asks の行になる
"""
import json
import unittest

from tests.blocks import kit

BLOCK = "line"
U1 = "u1"


def script_names(name: str, attr: str) -> tuple:
    """line の script の名の表（fix_in.NAMES・ask_before_fix.ROUNDS）を、script を走らせずに字から引く"""
    import ast
    tree = ast.parse((kit.BLOCKS / BLOCK / "scripts" / f"{name}.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == attr for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name}.py に {attr} が無い")


class SpecRoundsCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, BLOCK)

    def ptr(self, rel, doc=None):
        if doc is not None:
            path = self.run.artifacts / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": rel}

    def inputs(self, narrows=(), forced=""):
        (self.run.repo / "docs").mkdir(exist_ok=True)
        (self.run.repo / "docs" / "d.md").write_text("# 設計書\n\n公開の口は増やさない\n", encoding="utf-8")
        (self.run.repo / "docs" / "t.yaml").write_text("purpose: 目的\n", encoding="utf-8")
        diagnose = {"ok": True, "status": "ok", "mode": "judge", "stop_reason": "", "reason": "", "ready": True,
                    "judgment": self.ptr("spec-diagnose/judgment.json", {"units": []}),
                    "units": [{"id": U1, "paths": ["a.py"], "summary": "s"}], "questions": [{"key": "q1"}],
                    "inputs": self.ptr("spec-diagnose/in.json", {}), "brief": None, "materials": self.ptr("spec-diagnose/m.json", {}),
                    "out_of_purpose": self.ptr("spec-diagnose/oop.json", {"rounds": {}}), "answer_ties": None, "downgrades": [],
                    "report": []}
        fix_plan = {"plan": [{"unit_keys": [U1], "narrows": list(narrows)}]}
        plan = {"ok": True, "status": "ok", "reason": "", "mode": "plan", "round": 1, "owed": [U1],
                "plan": self.ptr("spec-plan/plan-fields.json", {"round": 1, "fields": []}),
                "fix_plan": self.ptr("spec-plan/p2.fix_plan.json", fix_plan), "reply": self.ptr("spec-plan/reply.json", fix_plan),
                "handoff": None, "replan": None, "ripple": self.ptr("spec-plan/ripple.json", {"items": []}), "rejects": [],
                "gave_up": None, "report": []}
        entry = {"ok": True, "stop_reason": "", "reason": "", "request": self.ptr("spec-entry/request.json", []), "origin": "o",
                 "purpose": self.ptr("spec-entry/purpose.json", {"purpose_text": "目的の文", "source": "②計画・タスク記述", "known_weaknesses": [], "source_files": []}), "spec": self.ptr("spec-entry/spec.md", "x"),
                 "spec_files": ["docs/t.yaml", "docs/d.md"], "tdd": False, "out_of_scope": [], "mismatches": [], "report": []}
        ports = {"forced": forced, "policy": "", "unattended": False}
        return {k: json.dumps(v, ensure_ascii=False) for k, v in
                {"diagnose": diagnose, "plan": plan, "entry": entry, "ports": ports}.items()}

    def rounds(self, **kw):
        return self.run.script("spec_rounds", **self.inputs(**kw))

    def test_judge_part_has_every_field_fix_in_reads(self):
        got = self.rounds()
        self.assertEqual(got["stop_reason"], "", got)
        judge = got["judge"]
        self.assertEqual(set(script_names("fix_in", "NAMES")["judge"]) - set(judge), set())
        self.assertEqual((judge["ok"], judge["stop_reason"], judge["ready"], judge["units"][0]["id"]), (True, "", True, U1))
        self.assertEqual((judge["purpose_text"], judge["means"], judge["tier"], judge["tier_record"]), ("目的の文", [], "標準", None))
        for name in ("constraints", "world", "spec", "excluded", "decisions", "verify"):
            self.assertIsNone(judge[name], name)
        self.assertEqual(judge["questions"], [{"key": "q1"}])
        self.assertEqual(self.rounds(forced="軽量")["judge"]["tier"], "軽量", "thickness の名指しは段の語")

    def test_rounds_part_has_every_field_ask_before_fix_reads(self):
        rounds = self.rounds()["rounds"]
        self.assertEqual(set(script_names("ask_before_fix", "ROUNDS")) - set(rounds), set())
        self.assertEqual(set(script_names("fix_in", "NAMES")["rounds"]) - set(rounds), set())
        self.assertEqual((rounds["done"], rounds["ok"], rounds["status"], rounds["round"]), (True, True, "ok", 1))
        self.assertEqual((rounds["review_status"], rounds["review_reason"], rounds["stop_reason"]), ("ok", "", ""))
        self.assertEqual((rounds["stalled"], rounds["capped"], rounds["handoffs"], rounds["deviations"]), (False, False, [], []))
        for name in ("plan_prior", "record", "review", "gave_up"):
            self.assertIsNone(rounds[name], name)
        self.assertEqual(rounds["owed"], [U1])

    def test_undecided_narrows_become_asks(self):
        """decided_by の無い narrows は decided が偽の asks の行（lib/gatemarks.narrow_asks。承認ノードに出る）。設計書の行を
        決め手に持つ narrows は decided が真"""
        undecided = {"what": "空の列の mean", "why": "例外のまま"}
        decided = {"what": "公開の口", "why": "増やさない", "decided_by": "docs/d.md:3 の決め", "undecided_because": "", "fences": [],
                   "world": "公開の口を増やさないのは定石"}
        asks = self.rounds(narrows=[undecided, decided])["rounds"]["asks"]
        self.assertEqual([a["text"] for a in asks], ["修正案 1 が狭める能力: 空の列の mean——例外のまま", "修正案 1 が狭める能力: 公開の口——増やさない"])
        self.assertEqual([a["decided"] for a in asks], [False, True])
        self.assertIn("obvious", asks[0]["why"])
        self.assertEqual(asks[1]["why"], {})


if __name__ == "__main__":
    unittest.main()

"""仕様駆動の道の node spec-rounds（workflows/line/scripts/spec_rounds.py。docs/design/spec-driven.md の 6.2 の足す node の 8・6.5 の 8・
6.8 の 1 と 2）。

判定の役（spec-diagnose）と計画の部品（spec-plan）の返りを、今の judge-out と plan-rounds-out の受け皿の got と同じ形に組み直す。
ここで照らすのは、決まっていない narrows（decided_by が無い）が lib/gatemarks.narrow_asks で asks の行になり、修正前の承認ノードに
出ること（欄が揃うかの形は照らさない。読む側の script が欄の欠けで落ちる）
"""
import json
import unittest

from tests.blocks import kit

BLOCK = "line"
U1 = "u1"


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

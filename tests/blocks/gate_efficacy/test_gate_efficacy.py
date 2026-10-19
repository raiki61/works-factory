"""ゲートの検算の block を、script を子のプロセスで回して確かめる（docs/design/materials.md の 8 節・docs/design/gate-efficacy.md の 2.9）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → role_prep → 台本の返答 →
role_accept → finish と回し、material.json と出力の 5 欄を照らす。筋書きを Archon の workflow test で回すのは
tests/layers/test_block_shape.py。
"""
import json
import sys
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

sys.path.append(str(kit.ROOT / "lib"))
BLOCK = kit.BLOCKS / "gate-efficacy"
NAME = "gate-efficacy"
LOOP = f"{NAME}-loop"
ARM = {"gate": "tests/test_app.py", "arm": "the fence on a pinned value", "red_confirmed": True, "control_green": True,
       "hit_evidence": "the unique marker appeared in the test output"}
GOOD = {"material": {"status": "clean", "checked": "the arms of the gate the diff adds"}, "arms": [ARM]}
NA = {"material": {"status": "not_applicable", "reason": "the diff does not touch a gate"}, "arms": []}
MERGE_WHY = "変異の検算は合流した版でまとめて 1 回撃つ"


class FlowCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, NAME)
        (self.run.repo / "app.txt").write_text("一行目\n二行目\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")

    def intake(self, **inputs):
        ports = {"base": "", "gates": "", "entry": "", "lang": "", **inputs}
        return self.run.script("intake", "intake", **ports)

    def prep(self):
        return self.run.script("role_prep", f"{LOOP}.{NAME}-prep")["prompt"]

    def accept(self, reply):
        return self.run.script("role_accept", f"{LOOP}.{NAME}-accept", reply=json.dumps(reply, ensure_ascii=False))

    def finish(self):
        return self.run.script("finish", "finish")

    def material(self):
        return json.loads((self.run.artifacts / "material.json").read_text(encoding="utf-8"))

    def change(self, *files):
        (self.run.repo / "app.txt").write_text("一行目\n直した\n", encoding="utf-8")
        for f in files:
            (self.run.repo / f).parent.mkdir(parents=True, exist_ok=True)
            (self.run.repo / f).write_text("x\n", encoding="utf-8")

    def instruction(self):
        """役に渡る指示の全部"""
        return self.prep()

    # ---- 回さない道（写す元 DueCase.test_gates_merge_turns_gate_efficacy_off）
    def test_merge_route_does_not_run_the_role(self):
        got = self.intake(gates="merge")
        self.assertEqual(got["due"], False)
        self.assertTrue(got["reason"].startswith(MERGE_WHY), got)
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (True, "skipped"))
        doc = self.material()
        mat = doc["materials"]["gate_efficacy"]
        self.assertEqual(mat["status"], "not_applicable")
        self.assertTrue(mat["reason"].startswith(MERGE_WHY), mat)
        self.assertIsNone(doc["reply"])

    def test_entry_route_does_not_run_the_role_and_merge_wins_when_both(self):
        self.assertEqual(self.intake(entry="人の依頼（試験）")["due"], False)
        self.assertEqual(self.finish()["status"], "skipped")
        mat = self.material()["materials"]["gate_efficacy"]
        self.assertEqual(mat["status"], "not_applicable")
        self.assertIn("人の依頼（試験）", mat["reason"])
        self.assertIn("渡されていない", mat["reason"], "request を持たないので件数の句は『渡されていない』")
        self.setUp()
        self.intake(entry="人の依頼（試験）", gates="merge")
        self.finish()
        self.assertTrue(self.material()["materials"]["gate_efficacy"]["reason"].startswith(MERGE_WHY))

    def test_other_gates_words_run_the_role(self):
        for gates in ("", "other"):
            with self.subTest(gates=gates):
                self.setUp()
                self.assertTrue(self.intake(gates=gates)["due"])

    # ---- 受け付け（写す元 MaterialCase.test_accept_rules の gate-efficacy の部分）
    def test_clean_with_an_unred_arm_is_refused(self):
        self.change("tests/test_app.py")
        self.intake()
        self.prep()
        got = self.accept({**GOOD, "arms": [{**ARM, "red_confirmed": False}]})
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertIn("赤を見ていない腕", got["reason"])
        self.assertFalse((self.run.artifacts / "accepted.json").exists())

    def test_good_reply_is_taken_and_reported(self):
        self.change("tests/test_app.py")
        self.assertTrue(self.intake()["due"])
        self.prep()
        self.assertEqual(self.accept(GOOD), {"ok": True, "done": True, "reason": ""})
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["reason"]), (True, "ran", ""))
        self.assertEqual(fin["report"][0], "素材 gate_efficacy: clean（見た所: the arms of the gate the diff adds）")
        self.assertEqual(fin["report"][1], "  - 腕: the fence on a pinned value（tests/test_app.py。赤 見た・対照の緑 見た・守る行の通過 見た）")
        self.assertEqual(self.material()["materials"], {"gate_efficacy": GOOD["material"]})

    def test_three_rejections_give_up(self):
        self.change("tests/test_app.py")
        self.intake()
        dones = []
        for _ in range(3):
            self.prep()
            dones.append(self.accept({**GOOD, "arms": []})["done"])
        self.assertEqual(dones, [False, False, True])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "gave_up"))
        self.assertEqual(self.material()["materials"]["gate_efficacy"]["status"], "not_run")

    # ---- 『条件に当たらない』（写す元 test_gate_role_may_judge_a_gate_free_diff_not_applicable）
    def test_gate_free_diff_lets_the_role_judge_not_applicable(self):
        for extra, ok in ((None, True), ("test_app.txt", False)):
            with self.subTest(extra=extra):
                self.setUp()
                self.change(*([extra] if extra else []))
                self.intake()
                self.assertEqual("none of the facts the machine holds raise it" in self.instruction(), ok)
                got = self.accept(NA)
                self.assertEqual(got["ok"], ok, got)
                if not ok:
                    self.assertIn("条件が真で走ったのに not_applicable", got["reason"])

    # ---- 変異の宣言（写す元 test_gate_prep_shows_the_declared_mutation_stage。照らすのは段落の真偽と値）
    def test_declared_mutation_stage_reaches_the_instruction(self):
        self.change("tests/test_app.py")
        (self.run.repo / "arms.txt").write_text("arm-1\n", encoding="utf-8")
        decl = {"suite": [{"name": "t", "argv": ["true"]}], "mutation": {"argv": ["mutate", "--fast"], "arms": "arms.txt"}}
        undeclared = "has no mutation stage"
        cases = (
            (json.dumps(decl), ['["mutate", "--fast"]', "arms.txt"], [undeclared, "its mutation stage cannot be read"]),
            (json.dumps({"suite": decl["suite"]}), [undeclared], ["mutate", "its mutation stage cannot be read"]),
            (json.dumps({**decl, "mutation": {"argv": []}}), [undeclared, "its mutation stage cannot be read"], ["mutate"]),
            ("{", [undeclared, "its mutation stage cannot be read"], ["mutate"]),
            (json.dumps({**decl, "suite": []}), [undeclared, "its mutation stage cannot be read"], ["mutate"]),
        )
        for text, said, unsaid in cases:
            with self.subTest(text=text):
                (self.run.repo / ".review-checks.json").write_text(text, encoding="utf-8")
                git(self.run.repo, "add", "-A")
                git(self.run.repo, "commit", "-q", "-m", "decl")
                self.intake()
                got = self.instruction()
                for s in said:
                    self.assertIn(s, got)
                for s in unsaid:
                    self.assertNotIn(s, got)

    def test_unreadable_gates_input_cannot_happen_but_missing_intake_fails_prep(self):
        self.assertIn("intake.json", self.run.failing("role_prep", f"{LOOP}.{NAME}-prep"))

    def test_included_block_writes_in_its_own_place(self):
        self.run.script("intake", "judge__gate-efficacy__intake", base="", gates="", entry="", lang="")
        self.run.script("role_prep", f"judge__gate-efficacy__{LOOP}.{NAME}-prep")
        self.assertTrue((self.run.artifacts / "judge" / "gate-efficacy" / f"{NAME}-prompt-1.md").is_file())
        fin = self.run.script("finish", "judge__gate-efficacy__finish")
        self.assertEqual(fin["material"]["path"], "judge/gate-efficacy/material.json")


class ShapeCase(unittest.TestCase):
    """YAML の揃い（block の形の検査は tests/layers/test_block_shape.py）"""

    # 今の判定のゲートの検算の役の起こし方（tests/workflows/test_judge.py の ROLES["gate-efficacy"] の行と、
    # workflows/judge/works-factory-judge.yaml の錨 test_run_launch を、作り直しの時に字で写した物）
    LAUNCH = {"model": "@wf-judge-materials", "settingSources": ["user"],
              "allowed_tools": ["Read", "Grep", "Glob", "Bash", "WebSearch", "WebFetch"],
              "sandbox": {"enabled": True, "allowUnsandboxedCommands": False, "failIfUnavailable": True,
                          "enableWeakerNetworkIsolation": True,
                          "network": {"allowedDomains": ["*"], "allowLocalBinding": True},
                          "filesystem": {"allowWrite": ["/"], "denyWrite": ["~/../archon-home"]}},
              "idle_timeout": 1728000000, "retry": {"max_attempts": 2, "on_error": "all"}}

    def setUp(self):
        doc = yaml.safe_load((BLOCK / f"works-factory-{NAME}.yaml").read_text(encoding="utf-8"))
        self.nodes = {n["id"]: n for n in doc["nodes"]}
        self.body = {n["id"]: n for n in self.nodes[LOOP]["loop_group"]["nodes"]}

    def test_loop_bound_matches_the_give_up_count(self):
        import rolekit
        self.assertEqual(self.nodes[LOOP]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER)

    def test_launch_matches_the_judge_role(self):
        """起こし方は今の判定のゲートの検算の役と同じ（群の既定は sonnet・medium。役の node は mutates_checkout を持たない）"""
        import launchgroups
        role = self.body[NAME]
        self.assertEqual({k: role.get(k) for k in self.LAUNCH}, self.LAUNCH)
        self.assertEqual(launchgroups.default_of(role["model"]), ("sonnet", "medium"))
        self.assertNotIn("mutates_checkout", role)
        self.assertEqual(role["output_format"]["required"], ["material", "arms"])
        self.assertEqual(role["output_format"]["properties"]["arms"]["items"]["required"],
                         ["gate", "arm", "red_confirmed", "control_green", "hit_evidence"])


if __name__ == "__main__":
    unittest.main()

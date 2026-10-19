"""根拠の出所検査の block を、script を子のプロセスで回して確かめる（docs/design/materials.md の 8 節・docs/design/provenance.md の 2.9）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → role_prep → 台本の返答 →
role_accept → finish と回し、material.json と出力の 5 欄を照らす。拒まれる返答 3 回で gave_up になる道も回す。
筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = kit.BLOCKS / "provenance"
NAME = "provenance"
LOOP = f"{NAME}-loop"
CLAIMS = [{"claim": "正本は docs/spec.md", "exists_at_base": True, "evidence": "git log -S で根に在った"},
          {"claim": "規約は docs/rules.md（この差分が足す）", "exists_at_base": False, "evidence": "差分の + 行が docs/rules.md を足している"}]
FOUND = {"material": {"status": "found", "count": 1, "detail": "規約の出どころは差分が足した docs/rules.md（循環）"}, "claims": CLAIMS}
CLEAN = {"material": {"status": "clean", "checked": "差分の本文と docstring の主張"}, "claims": []}


class FlowCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, NAME)
        (self.run.repo / "README.md").write_text("# 対象\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")

    def intake(self, **inputs):
        return self.run.script("intake", "intake", **{"base": "", "entry": "", "lang": "", **inputs})

    def prep(self):
        return self.run.script("role_prep", f"{LOOP}.{NAME}-prep")

    def accept(self, reply):
        return self.run.script("role_accept", f"{LOOP}.{NAME}-accept", reply=json.dumps(reply, ensure_ascii=False))

    def finish(self):
        return self.run.script("finish", "finish")

    def material(self):
        return json.loads((self.run.artifacts / "material.json").read_text(encoding="utf-8"))

    def test_found_reply_is_kept_as_it_is_and_reported(self):
        """見た返答（found・count・detail・claims 2 行）は material.json の reply.claims に字のまま載り、materials が
        {"provenance": <返答の material>}。report には exists_at_base が偽の行だけが出る"""
        self.assertTrue(self.intake()["due"])
        self.prep()
        self.assertEqual(self.accept(FOUND), {"ok": True, "done": True, "reason": ""})
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["reason"]), (True, "ran", ""))
        self.assertEqual(fin["material"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "material.json"})
        self.assertEqual(fin["report"][1:], ["  - 差分の根に無い根拠: 規約は docs/rules.md（この差分が足す）"])
        self.assertTrue(fin["report"][0].startswith("素材 provenance: found"), fin["report"][0])
        doc = self.material()
        self.assertEqual((doc["role"], doc["status"]), (NAME, "ran"))
        self.assertEqual(doc["reply"]["claims"], CLAIMS)
        self.assertEqual(doc["materials"], {"provenance": FOUND["material"]})

    def test_carried_over_and_not_applicable_are_refused(self):
        """写す元 MaterialCase.test_accept_rules の provenance の行: 走った観点の carried_over と、名乗れない not_applicable は拒む"""
        self.intake()
        self.prep()
        for material, said in (({"status": "carried_over", "from_round": 1, "reason": "前の周と同じ"}, "carried_over"),
                               ({"status": "not_applicable", "reason": "主張が無い"}, "『条件に当たらない』を名乗れない")):
            with self.subTest(status=material["status"]):
                got = self.accept({"material": material, "claims": []})
                self.assertEqual((got["ok"], got["done"]), (False, False))
                self.assertIn(said, got["reason"])
        self.prep()
        self.assertTrue((self.run.artifacts / f"{NAME}-prompt-2.md").is_file())

    def test_tree_change_is_refused_without_blaming_the_role(self):
        """写す元 MaterialCase.test_material_role_changed_the_tree_rejected（provenance で回す）"""
        self.intake()
        self.prep()
        (self.run.repo / "new.txt").write_text("役が足した\n", encoding="utf-8")
        got = self.accept(CLEAN)
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertIn("new.txt", got["reason"])
        self.assertIn("変えたのがこの役とは限らない", got["reason"])

    def test_three_rejections_give_up(self):
        self.intake()
        bad = {"material": {"status": "carried_over", "from_round": 1, "reason": "前の周と同じ"}, "claims": []}
        dones = []
        for _ in range(3):
            self.prep()
            dones.append(self.accept(bad)["done"])
        self.assertEqual(dones, [False, False, True])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "gave_up"))
        self.assertIn("3 回とも受け付けで拒まれた", fin["reason"])
        self.assertEqual(self.material()["materials"]["provenance"]["status"], "not_run")

    def test_entry_run_does_not_wake_the_role(self):
        """写す元 DueCase の provenance の部分: entry が空なら回し（差分が空でも）、在れば回さずに入口の理由つきの
        not_applicable を書く"""
        self.assertTrue(self.intake()["due"])
        self.setUp()
        got = self.intake(entry="人の依頼（試験）")
        self.assertFalse(got["due"])
        self.assertEqual(got["reason"], kit.load(NAME, "viewpoint").materialkit.entry_skip("出典の確かめ").why)
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["reason"]), (True, "skipped", got["reason"]))
        mat = self.material()["materials"]["provenance"]
        self.assertEqual(mat["status"], "not_applicable")
        self.assertIn("出どころ: 人の依頼（試験）", mat["reason"])
        self.assertIn("件数は渡されていない", mat["reason"])
        self.assertIsNone(self.material()["reply"])

    def test_unreadable_base_fails_with_the_reason(self):
        got = self.intake(base="no-such-commit")
        self.assertFalse(got["due"])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertEqual(self.material()["materials"]["provenance"]["status"], "not_run")

    def test_prompt_is_built_from_the_slots(self):
        self.intake(lang="Japanese")
        got = self.prep()["prompt"]
        self.assertIn("in Japanese.", got)
        self.assertIn("- Target diff (Read it): ", got)
        self.assertIn("- Repository: " + str(self.run.repo.resolve()), got.replace(str(self.run.repo), str(self.run.repo.resolve())))
        self.assertNotIn("new conversation", got, "輪は会話を続けるので、毎回新しい会話とは言わない")
        self.assertFalse((self.run.artifacts / "material-provenance-brief.md").exists())

    def test_prep_without_intake_fails_the_node(self):
        self.assertIn("intake.json", self.run.failing("role_prep", f"{LOOP}.{NAME}-prep"))

    def test_included_block_writes_in_its_own_place(self):
        self.run.script("intake", "judge__provenance__intake", base="", entry="", lang="")
        self.run.script("role_prep", f"judge__provenance__{LOOP}.{NAME}-prep")
        self.assertTrue((self.run.artifacts / "judge" / "provenance" / f"{NAME}-prompt-1.md").is_file())
        fin = self.run.script("finish", "judge__provenance__finish")
        self.assertEqual(fin["material"]["path"], "judge/provenance/material.json")


class ShapeCase(unittest.TestCase):
    """YAML の揃い（block の形の検査は tests/layers/test_block_shape.py）"""

    def setUp(self):
        doc = yaml.safe_load((BLOCK / f"works-factory-{NAME}.yaml").read_text(encoding="utf-8"))
        self.nodes = {n["id"]: n for n in doc["nodes"]}
        self.body = {n["id"]: n for n in self.nodes[LOOP]["loop_group"]["nodes"]}

    def test_loop_bound_matches_the_give_up_count(self):
        import rolekit
        self.assertEqual(self.nodes[LOOP]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER)

    # 今の判定の provenance の役の起こし方（tests/workflows/test_judge.py の ROLES["provenance"] の行と、
    # workflows/judge/works-factory-judge.yaml の錨 test_run_launch を、作り直しの時に字で写した物）。組み込みで workflows/ が
    # 入れ替わっても、この期待は block の起こし方の正本として残る
    LAUNCH = {"model": "@wf-judge-materials", "settingSources": ["user"],
              "allowed_tools": ["Read", "Grep", "Glob", "Bash", "WebSearch", "WebFetch"],
              "sandbox": {"enabled": True, "allowUnsandboxedCommands": False, "failIfUnavailable": True,
                          "enableWeakerNetworkIsolation": True, "network": {"allowedDomains": ["*"], "allowLocalBinding": True},
                          "filesystem": {"allowWrite": ["/"], "denyWrite": ["~/../archon-home"]}},
              "idle_timeout": 1728000000, "retry": {"max_attempts": 2, "on_error": "all"}}

    def test_launch_matches_the_judge_role(self):
        """起こし方は今の判定の provenance の役と同じ（群の既定は sonnet・medium。役の node は mutates_checkout を持たない）"""
        import launchgroups
        role = self.body[NAME]
        self.assertEqual({k: role.get(k) for k in self.LAUNCH}, self.LAUNCH)
        self.assertEqual(launchgroups.default_of(role["model"]), ("sonnet", "medium"))
        self.assertNotIn("mutates_checkout", role)
        self.assertEqual(role["output_format"]["required"], ["material", "claims"])
        self.assertEqual(role["output_format"]["properties"]["claims"]["items"]["required"], ["claim", "exists_at_base", "evidence"])


if __name__ == "__main__":
    unittest.main()

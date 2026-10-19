"""先行議論の突合の block を、script を子のプロセスで回して確かめる（docs/design/materials.md の 8 節・docs/design/prior-decisions.md の 2.9）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → role_prep → 台本の返答 →
role_accept → finish と回し、material.json と出力の 5 欄を照らす。拒まれる返答 3 回で gave_up になる道も回す。
筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import sys
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = kit.BLOCKS / "prior-decisions"
NAME = "prior-decisions"
REQUEST = json.dumps([{"where": "README.md の頭", "text": "README に始め方を書きたい"}], ensure_ascii=False)
GOOD = {"material": {"status": "clean", "checked": "README.md と docs/ の決定記録"}, "checked": True,
        "searched": ["README.md", "docs/"], "settled": []}
SETTLED = [{"topic": "公開の口", "decision": "減らさない", "reason": "使い手が在る", "revisit": "使い手が消えた時",
            "where": "docs/adr/0002.md"}]
LOOP = f"{NAME}-loop"


class FlowCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, NAME)
        (self.run.repo / "README.md").write_text("# 対象\n\n始め方\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")

    def intake(self, **inputs):
        ports = {"base": "", "request": REQUEST, "entry": "人の依頼（試験）", "lang": "", **inputs}
        return self.run.script("intake", "intake", **ports)

    def prep(self):
        return self.run.script("role_prep", f"{LOOP}.{NAME}-prep")

    def accept(self, reply):
        return self.run.script("role_accept", f"{LOOP}.{NAME}-accept", reply=json.dumps(reply, ensure_ascii=False))

    def finish(self):
        return self.run.script("finish", "finish")

    def material(self):
        return json.loads((self.run.artifacts / "material.json").read_text(encoding="utf-8"))

    def test_port_values_alone_reach_the_material(self):
        """写す元 MaterialCase.test_prior_decisions_reply_is_taken_or_refused: 見た返答は素材の欄に写して受け、名乗れない
        not_applicable は拒み、settled の where は記録された方針の読み手（policy.recorded）の名指しに出る"""
        self.assertEqual(self.intake()["due"], True)
        got = self.prep()["prompt"]
        self.assertIn('"README.md の頭"', got, "判定から入る run は依頼の行の where を材料に入れる")
        self.assertIn("Files the target diff touches: []", got)
        self.assertIn("in the language of the request", got, "lang が空なら既定の言語の文")
        self.assertNotIn("Why your previous answer was rejected", got)
        refused = self.accept({**GOOD, "material": {"status": "not_applicable", "reason": "無い"}})
        self.assertEqual((refused["ok"], refused["done"]), (False, False))
        self.assertIn("『条件に当たらない』を名乗れない", refused["reason"])
        again = self.prep()["prompt"]
        self.assertTrue(again.startswith("## Why your previous answer was rejected"), again[:80])
        self.assertIn("名乗れない", again)
        self.assertTrue((self.run.artifacts / f"{NAME}-prompt-2.md").is_file())
        self.assertEqual(self.accept({**GOOD, "settled": SETTLED}), {"ok": True, "done": True, "reason": ""})
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["reason"]), (True, "ran", ""))
        self.assertEqual(fin["material"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "material.json"})
        self.assertEqual(fin["report"], ["素材 prior_decisions: clean（見た所: README.md と docs/ の決定記録）",
                                         "  - 決着済みの論点: 公開の口（docs/adr/0002.md）"])
        doc = self.material()
        self.assertEqual((doc["role"], doc["status"]), (NAME, "ran"))
        self.assertEqual(doc["materials"], {"prior_decisions": GOOD["material"]})
        sys.path.append(str(kit.ROOT / "lib"))
        import policy
        rows = policy.recorded({}, self.run.artifacts / "material.json")
        self.assertEqual([r["name"] for r in rows if r["source"] == "settled"], ["docs/adr/0002.md"])

    def test_three_rejections_give_up(self):
        self.intake()
        bad = {**GOOD, "material": {"status": "not_applicable", "reason": "無い"}}
        dones = []
        for _ in range(3):
            self.prep()
            dones.append(self.accept(bad)["done"])
        self.assertEqual(dones, [False, False, True])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "gave_up"))
        self.assertIn("3 回とも受け付けで拒まれた", fin["reason"])
        self.assertEqual(self.material()["materials"]["prior_decisions"]["status"], "not_run")

    def test_empty_diff_entry_run_still_runs(self):
        """写す元 DueCase.test_empty_diff_run_with_requests_runs_only_prior_decisions の prior-decisions の部分"""
        got = self.intake()
        self.assertTrue(got["due"])
        self.assertEqual(json.loads((self.run.artifacts / "view.json").read_text(encoding="utf-8"))["changed_files"], [])

    def test_request_wheres_follow_the_entry(self):
        """entry が空なら request_wheres は []、在れば依頼の行の where の並び（findings の欄に持つオブジェクトの形でも）"""
        self.intake(entry="")
        self.assertIn("(in a run that enters at the judgment; `[]` in a run with a diff): []", self.prep()["prompt"])
        self.setUp()
        self.intake(request=json.dumps({"findings": [{"where": "a.py:1", "text": "x"}, {"where": "b.py", "text": "y"}]}))
        self.assertIn('[\n "a.py:1",\n "b.py"\n]', self.prep()["prompt"])

    def test_unreadable_request_fails_with_the_port_name(self):
        got = self.intake(request="{not json")
        self.assertFalse(got["due"])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIn("request", fin["reason"])
        self.assertEqual(self.material()["materials"]["prior_decisions"]["status"], "not_run")

    def test_lang_reaches_the_prompt(self):
        self.intake(lang="Japanese")
        self.assertIn("row in Japanese.", self.prep()["prompt"])

    def test_prep_without_intake_fails_the_node(self):
        self.assertIn("intake.json", self.run.failing("role_prep", f"{LOOP}.{NAME}-prep"))

    def test_included_block_writes_in_its_own_place(self):
        self.run.script("intake", "judge__prior-decisions__intake", base="", request=REQUEST, entry="", lang="")
        self.run.script("role_prep", f"judge__prior-decisions__{LOOP}.{NAME}-prep")
        self.assertTrue((self.run.artifacts / "judge" / "prior-decisions" / f"{NAME}-prompt-1.md").is_file())
        fin = self.run.script("finish", "judge__prior-decisions__finish")
        self.assertEqual(fin["material"]["path"], "judge/prior-decisions/material.json")


class ShapeCase(unittest.TestCase):
    """YAML の揃い（block の形の検査は tests/layers/test_block_shape.py）"""

    def setUp(self):
        doc = yaml.safe_load((BLOCK / f"works-factory-{NAME}.yaml").read_text(encoding="utf-8"))
        self.nodes = {n["id"]: n for n in doc["nodes"]}
        self.body = {n["id"]: n for n in self.nodes[LOOP]["loop_group"]["nodes"]}

    def test_loop_bound_matches_the_give_up_count(self):
        import rolekit
        self.assertEqual(self.nodes[LOOP]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER)

    def test_launch_matches_the_judge_role(self):
        """起こし方は今の判定の prior-decisions の役と同じ（tests/workflows/test_judge.py の ROLES の行が照らす物）"""
        from tests.workflows import test_judge as tj
        import launchgroups
        model, effort, tools, sandbox, read_only, _, _, _ = tj.ROLES[NAME]
        role = self.body[NAME]
        old = tj.nodes()[NAME]
        self.assertEqual(launchgroups.default_of(role["model"]), (model, effort))
        self.assertEqual(role["allowed_tools"], tools)
        self.assertEqual(role["sandbox"], sandbox)
        self.assertEqual(role.get("mutates_checkout"), False if read_only else None)
        for key in ("model", "settingSources", "allowed_tools", "sandbox", "idle_timeout", "retry", "output_format"):
            with self.subTest(key=key):
                self.assertEqual(role[key], old[key])


if __name__ == "__main__":
    unittest.main()

"""手順トレースの block を、script を子のプロセスで回して確かめる（docs/design/materials.md の 8 節・docs/design/procedure-trace.md の 2.9）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → role_prep → 台本の返答 → role_accept →
finish と回し、material.json と出力の 5 欄を照らす。拒まれる返答 3 回で gave_up になる道も回す。
筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import sys
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = kit.BLOCKS / "procedure-trace"
NAME = "procedure-trace"
LOOP = f"{NAME}-loop"
GOOD = {"material": {"status": "clean", "checked": "run.sh を上から順に動かした"}, "findings": [], "unmeasured": []}
FOUND = {"material": {"status": "found", "count": 1, "detail": "run.sh の前提が欠ける"},
         "findings": [{"where": "run.sh:1", "text": "環境変数が前提", "mechanism": "未設定だと空で進む"}],
         "unmeasured": ["網が閉じていて取得を試せていない"]}
NA_WHY = "The condition of this viewpoint holds for this run (差分に手順書・スクリプト・CI 定義が 1 件)"


class FlowCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, NAME)
        (self.run.repo / "src.txt").write_text("x\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")

    def script_file(self, name="run.sh"):
        (self.run.repo / name).write_text("echo $HOME_DIR\n", encoding="utf-8")

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

    def test_procedure_file_runs_the_role_and_not_applicable_is_refused(self):
        """写す元 MaterialCase.test_procedure_trace_reply_is_taken_or_refused と DueCase.test_run_with_a_diff_runs_them"""
        self.script_file()
        self.assertTrue(self.intake()["due"])
        got = self.prep()["prompt"]
        self.assertIn(NA_WHY, got)
        self.assertNotIn("The condition of this viewpoint does not hold", got)
        self.assertNotIn("Why your previous answer was rejected", got)
        self.assertIn('"run.sh"', got)
        self.assertNotIn("The target's own review guide", got)
        refused = self.accept({**GOOD, "material": {"status": "not_applicable", "reason": "無い"}})
        self.assertEqual((refused["ok"], refused["done"]), (False, False))
        self.assertIn("条件が真で走ったのに not_applicable", refused["reason"])
        self.assertTrue(self.prep()["prompt"].startswith("## Why your previous answer was rejected"))
        self.assertEqual(self.accept(FOUND), {"ok": True, "done": True, "reason": ""})
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["reason"]), (True, "ran", ""))
        self.assertEqual(fin["material"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "material.json"})
        self.assertEqual(fin["report"], ["素材 procedure_trace: found（1 件）: run.sh の前提が欠ける",
                                         "  - 所見: run.sh:1: 環境変数が前提", "  - 未実測: 網が閉じていて取得を試せていない"])
        doc = self.material()
        self.assertEqual((doc["role"], doc["status"], doc["reply"]), (NAME, "ran", FOUND))
        self.assertEqual(doc["materials"], {"procedure_trace": FOUND["material"]})

    def test_no_procedure_file_does_not_start_the_role(self):
        """写す元 DueCase.test_procedure_trace_needs_procedure_files"""
        (self.run.repo / "a.txt").write_text("y\n", encoding="utf-8")
        got = self.intake()
        self.assertFalse(got["due"])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (True, "skipped"))
        want = {"status": "not_applicable", "reason": "対象差分に手順書・スクリプト・CI 定義の変更が無い（差分に手順書・スクリプト・CI 定義が無い）"}
        self.assertEqual(self.material()["materials"], {"procedure_trace": want})
        self.assertEqual(fin["reason"], got["reason"])

    def test_entry_run_with_an_empty_diff_is_skipped_with_the_out_of_condition_text(self):
        """写す元 DueCase.test_empty_diff_run_with_requests_runs_only_prior_decisions の procedure-trace の部分"""
        got = self.intake(entry="人の依頼（試験）")
        self.assertFalse(got["due"])
        self.assertIn("手順の追跡を起こさない", got["reason"])
        fin = self.finish()
        self.assertEqual(fin["status"], "skipped")
        self.assertIn("対象差分に手順書・スクリプト・CI 定義の変更が無い", self.material()["materials"]["procedure_trace"]["reason"])

    def test_entry_with_a_diff_still_runs(self):
        self.script_file()
        self.assertTrue(self.intake(entry="人の依頼（試験）")["due"])

    def test_target_review_guide_paragraph_follows_the_file(self):
        self.script_file()
        (self.run.repo / "REVIEW.md").write_text("# 観点\n", encoding="utf-8")
        git(self.run.repo, "add", "REVIEW.md")
        git(self.run.repo, "commit", "-q", "-m", "guide")
        self.intake(base="HEAD~1")
        got = self.prep()["prompt"]
        self.assertIn("The target's own review guide (Read it as well): ", got)
        self.assertIn("REVIEW.md", got.split("The target's own review guide")[1])

    def test_reply_that_changes_the_tree_is_refused(self):
        """写す元 test_test_caches_count_like_any_change: 計器が作業ツリーに控えを書いた時も拒む"""
        self.script_file()
        self.intake()
        self.prep()
        (self.run.repo / "test-cache.txt").write_text("c\n", encoding="utf-8")
        refused = self.accept(GOOD)
        self.assertFalse(refused["ok"])
        self.assertIn("作業ツリー", refused["reason"])

    def test_three_rejections_give_up(self):
        self.script_file()
        self.intake()
        bad = {**GOOD, "material": {"status": "not_applicable", "reason": "無い"}}
        dones = []
        for _ in range(3):
            self.prep()
            dones.append(self.accept(bad)["done"])
        self.assertEqual(dones, [False, False, True])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "gave_up"))
        self.assertEqual(self.material()["materials"]["procedure_trace"]["status"], "not_run")

    def test_lang_reaches_the_prompt(self):
        self.script_file()
        self.intake(lang="Japanese")
        self.assertIn("in Japanese.", self.prep()["prompt"])

    def test_prep_without_intake_fails_the_node(self):
        self.assertIn("intake.json", self.run.failing("role_prep", f"{LOOP}.{NAME}-prep"))

    def test_included_block_writes_in_its_own_place(self):
        self.script_file()
        self.run.script("intake", "judge__procedure-trace__intake", base="", entry="", lang="")
        self.run.script("role_prep", f"judge__procedure-trace__{LOOP}.{NAME}-prep")
        self.assertTrue((self.run.artifacts / "judge" / "procedure-trace" / f"{NAME}-prompt-1.md").is_file())


class ShapeCase(unittest.TestCase):
    """YAML の揃い（block の形の検査は tests/layers/test_block_shape.py）"""

    # 今の判定の procedure-trace の役の起こし方（tests/workflows/test_judge.py の表の行と、workflows/judge/works-factory-judge.yaml の
    # 錨 net_closed_launch を、作り直しの時に字で写した物）
    LAUNCH = {"model": "@wf-judge-materials", "settingSources": ["user"],
              "allowed_tools": ["Read", "Grep", "Glob", "Bash", "WebSearch", "WebFetch"],
              "sandbox": {"enabled": True, "allowUnsandboxedCommands": False, "failIfUnavailable": True,
                          "excludedCommands": ["works-gh:*"], "network": {"allowedDomains": []},
                          "filesystem": {"denyWrite": ["~/../archon-home"]}},
              "idle_timeout": 1728000000, "retry": {"max_attempts": 2, "on_error": "all"}}

    def setUp(self):
        sys.path.append(str(kit.ROOT / "lib"))
        doc = yaml.safe_load((BLOCK / f"works-factory-{NAME}.yaml").read_text(encoding="utf-8"))
        self.nodes = {n["id"]: n for n in doc["nodes"]}
        self.body = {n["id"]: n for n in self.nodes[LOOP]["loop_group"]["nodes"]}

    def test_loop_bound_matches_the_give_up_count(self):
        import rolekit
        self.assertEqual(self.nodes[LOOP]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER)

    def test_launch_matches_the_judge_role(self):
        import launchgroups
        role = self.body[NAME]
        self.assertEqual({k: role.get(k) for k in self.LAUNCH}, self.LAUNCH)
        self.assertEqual(launchgroups.default_of(role["model"]), ("sonnet", "medium"))
        self.assertNotIn("mutates_checkout", role)
        self.assertEqual(role["output_format"]["required"], ["material", "findings", "unmeasured"])

    def test_role_follows_only_its_prep_so_the_session_continues(self):
        """fresh_context: false の輪の役の直前の層は 1 node だけ（Archon は層に node が 2 つ以上在ると会話を切る）"""
        self.assertEqual(self.body[NAME]["depends_on"], [f"{NAME}-prep"])
        self.assertNotIn("depends_on", self.body[f"{NAME}-prep"])


if __name__ == "__main__":
    unittest.main()

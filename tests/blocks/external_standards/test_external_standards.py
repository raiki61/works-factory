"""外部標準照合の block を、script を子のプロセスで回して確かめる（docs/design/materials.md の 8 節・docs/design/external-standards.md の 2.9）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → role_prep → 台本の返答 →
role_accept → finish と回し、material.json と出力の 5 欄を照らす。拒まれる返答 3 回で gave_up になる道と、判定から入る run で
役を起こさない道も回す。筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import copy
import json
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = kit.BLOCKS / "external-standards"
NAME = "external-standards"
LOOP = f"{NAME}-loop"
PURPOSE = {"purpose_text": "設定ファイルの読み込みを速くする変更", "source": "①PR 説明", "known_weaknesses": [], "source_files": []}
RANK = {"problem": "設定ファイルの構文解析", "source": "言語の公式文書の「設定ファイル」の節: 標準の解析器を使え",
        "ranked": ["標準の解析器を使う", "区切りで手で切る"], "diff_at": "標準の解析器を使う"}
GOOD = {"material": {"status": "clean", "checked": "差分が import する依存と宣言済みのプラグイン"}, "findings": [],
        "seen": "触ったファイルとその依存", "unseen": "触っていない領域", "web_refetched": True, "rankings": [RANK]}
HEAD = "観点 external-standards: "


class FlowCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, NAME)
        (self.run.repo / "a.py").write_text("x = 1\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")
        (self.run.repo / "a.py").write_text("x = 2\n", encoding="utf-8")

    def intake(self, **inputs):
        ports = {"base": "", "purpose": json.dumps(PURPOSE, ensure_ascii=False), "entry": "", "lang": "", **inputs}
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
        self.assertEqual(self.intake()["due"], True)
        self.prep()
        self.assertEqual(self.accept(GOOD), {"ok": True, "done": True, "reason": ""})
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["reason"]), (True, "ran", ""))
        self.assertEqual(fin["material"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "material.json"})
        self.assertEqual(fin["report"], ["素材 external_standards: clean（見た所: 差分が import する依存と宣言済みのプラグイン）",
                                         "  - 順位: 設定ファイルの構文解析——差分は 1 位／2 位中（標準の解析器を使う）"])
        doc = self.material()
        self.assertEqual((doc["role"], doc["status"]), (NAME, "ran"))
        self.assertEqual(doc["materials"], {"external_standards": GOOD["material"]})
        self.assertEqual(doc["reply"]["rankings"], [RANK])

    def refused(self, reply, *words):
        self.assertEqual(self.intake()["due"], True)
        self.prep()
        got = self.accept(reply)
        self.assertEqual((got["ok"], got["done"]), (False, False))
        for word in words:
            self.assertIn(word, got["reason"])
        self.assertFalse((self.run.artifacts / "material.json").exists(), "拒んだ返答では material.json を書かない")
        return got

    def test_diff_at_outside_ranked_is_refused(self):
        self.refused({**GOOD, "rankings": [{**RANK, "diff_at": "フィールドごとに別 commit"}]}, "ranked に無い", HEAD)

    def test_below_the_top_needs_a_reason(self):
        low = {**RANK, "diff_at": "区切りで手で切る"}
        self.refused({**GOOD, "rankings": [low]}, "why_not_higher", HEAD)
        self.setUp()
        self.intake()
        self.prep()
        self.assertTrue(self.accept({**GOOD, "rankings": [{**low, "why_not_higher": "標準の解析器は入れ子を持てない"}]})["ok"])

    def test_empty_rankings_need_the_reason_for_none(self):
        self.refused({**GOOD, "rankings": []}, "rankings_none", HEAD)
        self.setUp()
        self.intake()
        self.prep()
        self.assertTrue(self.accept({**GOOD, "rankings": [], "rankings_none": "一般化できる問題が無い（設定の書き換えだけ）"})["ok"])

    def test_not_applicable_is_refused(self):
        self.refused({**GOOD, "material": {"status": "not_applicable", "reason": "無い"}}, "名乗れない")

    def test_a_changed_working_tree_is_refused(self):
        self.assertTrue(self.intake()["due"])
        self.prep()
        (self.run.repo / "b.py").write_text("y = 1\n", encoding="utf-8")
        got = self.accept(GOOD)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリーを変えた", got["reason"])

    def test_a_finding_outside_the_file_is_refused(self):
        row = {"where": "a.py:99", "text": "区切りで切っている"}
        self.refused({**GOOD, "findings": [row]}, "a.py:99")

    def test_three_rejections_give_up(self):
        self.intake()
        bad = {**GOOD, "rankings": [{**RANK, "diff_at": "どこにも無い"}]}
        dones = []
        for _ in range(3):
            self.prep()
            dones.append(self.accept(bad)["done"])
        self.assertEqual(dones, [False, False, True])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "gave_up"))
        self.assertIn("3 回とも受け付けで拒まれた", fin["reason"])
        self.assertEqual(self.material()["materials"]["external_standards"]["status"], "not_run")

    def test_entry_run_does_not_start_the_role(self):
        got = self.intake(entry="人の依頼（試験）")
        self.assertFalse(got["due"])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (True, "skipped"))
        mat = self.material()["materials"]["external_standards"]
        self.assertEqual(mat["status"], "not_applicable")
        self.assertIn("人の依頼（試験）", mat["reason"])
        self.assertIn("件数は渡されていない", mat["reason"])

    def test_unreadable_purpose_fails_with_the_port_name(self):
        got = self.intake(purpose='{"purpose_text": ""}')
        self.assertFalse(got["due"])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIn("purpose", fin["reason"])
        self.assertEqual(self.material()["materials"]["external_standards"]["status"], "not_run")

    def test_prompt_with_and_without_a_purpose(self):
        """写す元 test_missing_purpose_is_said_not_invented: 目的の文が無い run は目的を作らせない 1 文を入れ、目的の値を渡さない"""
        self.intake()
        got = self.prep()["prompt"]
        self.assertIn("Original purpose: " + PURPOSE["purpose_text"], got)
        self.assertIn("Weaknesses already known and accepted: []", got)
        self.assertNotIn("no purpose text is given", got)
        self.assertNotIn("Why your previous answer was rejected", got)
        self.assertIn("in the language of the request", got, "lang が空なら既定の言語の文")
        self.setUp()
        self.intake(purpose="null", lang="Japanese")
        got = self.prep()["prompt"]
        self.assertIn("Original purpose: no purpose text is given in this run.", got)
        self.assertNotIn(PURPOSE["purpose_text"], got)
        self.assertIn("in Japanese.", got)
        self.assertIn("Files the target diff touches: [\n \"a.py\"\n]", got)

    def test_repo_review_paragraph_follows_the_file(self):
        self.intake()
        self.assertNotIn("The target repository's own source of truth", self.prep()["prompt"])
        self.setUp()
        (self.run.repo / "REVIEW.md").write_text("# 対象の観点\n", encoding="utf-8")
        self.intake()
        got = self.prep()["prompt"]
        self.assertIn("The target repository's own source of truth: Read ", got)
        self.assertIn(str((self.run.repo / "REVIEW.md").resolve()), got)
        self.assertIn('Read the section "外部標準照合観点" of', got)

    def test_a_rejection_is_shown_on_the_next_round(self):
        self.intake()
        self.prep()
        self.accept({**GOOD, "rankings": [{**RANK, "diff_at": "どこにも無い"}]})
        got = self.prep()["prompt"]
        self.assertTrue(got.startswith("## Why your previous answer was rejected"), got[:80])
        self.assertIn("ranked に無い", got)
        self.assertTrue((self.run.artifacts / f"{NAME}-prompt-2.md").is_file())
        self.assertNotIn("started in a new conversation", got, "同じ会話で続ける役の指示に『新しい会話』と書かない")

    def test_prep_without_intake_fails_the_node(self):
        self.assertIn("intake.json", self.run.failing("role_prep", f"{LOOP}.{NAME}-prep"))

    def test_included_block_writes_in_its_own_place(self):
        self.run.script("intake", "judge__external-standards__intake", base="", purpose="null", entry="", lang="")
        self.assertTrue((self.run.artifacts / "judge" / "external-standards" / "intake.json").is_file())
        fin = self.run.script("finish", "judge__external-standards__finish")
        self.assertEqual(fin["material"]["path"], "judge/external-standards/material.json")


class ShapeCase(unittest.TestCase):
    """YAML の揃い（block の形の検査は tests/layers/test_block_shape.py）"""

    def setUp(self):
        kit.load(NAME, "viewpoint")   # lib/ を読めるようにする
        doc = yaml.safe_load((BLOCK / f"works-factory-{NAME}.yaml").read_text(encoding="utf-8"))
        self.nodes = {n["id"]: n for n in doc["nodes"]}
        self.body = {n["id"]: n for n in self.nodes[LOOP]["loop_group"]["nodes"]}

    def test_loop_bound_matches_the_give_up_count(self):
        import rolekit
        self.assertEqual(self.nodes[LOOP]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER)

    # 今の判定の external-standards の役の起こし方（tests/workflows/test_judge.py の ROLES["external-standards"] の行と、
    # workflows/judge/works-factory-judge.yaml の錨 net_closed_launch を、作り直しの時に字で写した物）
    LAUNCH = {"model": "@wf-judge-materials", "settingSources": ["user"],
              "allowed_tools": ["Read", "Grep", "Glob", "Bash", "WebSearch", "WebFetch"],
              "sandbox": {"enabled": True, "allowUnsandboxedCommands": False, "failIfUnavailable": True,
                          "excludedCommands": ["works-gh:*"], "network": {"allowedDomains": []},
                          "filesystem": {"denyWrite": ["~/../archon-home"]}},
              "idle_timeout": 1728000000, "retry": {"max_attempts": 2, "on_error": "all"}}

    def test_launch_matches_the_judge_role(self):
        import launchgroups
        role = self.body[NAME]
        self.assertEqual({k: role.get(k) for k in self.LAUNCH}, self.LAUNCH)
        self.assertEqual(launchgroups.default_of(role["model"]), ("sonnet", "medium"))
        self.assertNotIn("mutates_checkout", role)
        self.assertEqual(role["output_format"]["required"], ["material", "findings", "seen", "unseen", "web_refetched", "rankings"])
        self.assertEqual(role["output_format"]["properties"]["rankings"]["items"]["required"], ["problem", "source", "ranked", "diff_at"])


if __name__ == "__main__":
    unittest.main()

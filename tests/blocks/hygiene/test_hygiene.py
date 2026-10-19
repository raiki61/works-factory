"""衛生の観点の block を、script を子のプロセスで回して確かめる（docs/design/materials.md の 8 節・docs/design/hygiene.md の 2.9）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → role_prep → 台本の返答 →
role_accept → finish と回し、material.json と出力の 5 欄を照らす。拒まれる返答 3 回で gave_up になる道も回す。
筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import pathlib
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = kit.BLOCKS / "hygiene"
NAME = "hygiene"
LOOP = f"{NAME}-loop"
REVIEW = "# 観点\n\n## コード衛生観点\n\n衛生の本文\n\n### 小見出し\n\n中の字\n\n## 次\n\n別の節\n"


class FlowCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, NAME)
        (self.run.repo / "app.txt").write_text("一行目\n二行目\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")

    def change(self):
        (self.run.repo / "app.txt").write_text("一行目\n直した行\n", encoding="utf-8")

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

    def test_reply_is_taken_or_refused(self):
        """写す元 MaterialCase.test_hygiene_reply_is_taken_or_refused: seen の空の clean は拒み、行の在る返答は受けて素材に写す"""
        self.change()
        self.assertTrue(self.intake()["due"])
        self.prep()
        refused = self.accept({"findings": [], "seen": ""})
        self.assertEqual((refused["ok"], refused["done"]), (False, False))
        self.assertIn("素材 'hygiene'（clean）に 'checked' が要る", refused["reason"])
        self.prep()
        self.assertEqual(self.accept({"findings": [{"where": "app.txt:2", "text": "名が短い"}], "seen": "差分"}),
                         {"ok": True, "done": True, "reason": ""})
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["reason"]), (True, "ran", ""))
        self.assertEqual(fin["material"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "material.json"})
        doc = self.material()
        self.assertEqual((doc["role"], doc["status"]), (NAME, "ran"))
        self.assertEqual(doc["materials"], {"hygiene": {"status": "found", "checked": "差分", "count": 1,
                                                        "detail": "app.txt:2: 名が短い"}})
        self.assertEqual(doc["reply"]["findings"][0]["where"], "app.txt:2")

    def test_clean_reply_with_what_was_seen(self):
        self.change()
        self.intake()
        self.prep()
        self.assertTrue(self.accept({"findings": [], "seen": "差分の全部"})["done"])
        self.finish()
        self.assertEqual(self.material()["materials"], {"hygiene": {"status": "clean", "checked": "差分の全部"}})

    def test_location_beyond_the_file_is_refused(self):
        """写す元 test_location_beyond_the_file_is_sent_back_then_marked: ファイルの外の行は出し直させる"""
        self.change()
        self.intake()
        self.prep()
        got = self.accept({"findings": [{"where": "app.txt:99", "text": "x"}], "seen": "差分"})
        self.assertFalse(got["ok"])
        self.assertIn("app.txt", got["reason"])

    def test_changed_tree_is_refused(self):
        self.change()
        self.intake()
        self.prep()
        (self.run.repo / "ignored.txt").write_text("役が書いた\n", encoding="utf-8")
        (self.run.repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        got = self.accept({"findings": [], "seen": "差分"})
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリー", got["reason"])

    def test_three_rejections_give_up(self):
        self.change()
        self.intake()
        dones = []
        for _ in range(3):
            self.prep()
            dones.append(self.accept({"findings": [], "seen": ""})["done"])
        self.assertEqual(dones, [False, False, True])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "gave_up"))
        self.assertIn("3 回とも受け付けで拒まれた", fin["reason"])
        self.assertEqual(self.material()["materials"]["hygiene"]["status"], "not_run")

    def test_entry_run_is_skipped_with_a_reason(self):
        """写す元 DueCase.test_empty_diff_run_with_requests_runs_only_prior_decisions のこの観点の部分"""
        got = self.intake(entry="人の依頼（試験）")
        self.assertFalse(got["due"])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (True, "skipped"))
        mat = self.material()["materials"]["hygiene"]
        self.assertEqual(mat["status"], "not_applicable")
        self.assertIn("人の依頼（試験）", mat["reason"])

    def test_entry_with_a_diff_still_runs(self):
        self.change()
        self.assertTrue(self.intake(entry="人の依頼（試験）")["due"])

    def test_without_entry_runs_on_an_empty_diff(self):
        self.assertTrue(self.intake()["due"])

    def test_failed_when_the_role_never_answered(self):
        """prep が落ちた（観点の節が無い等）時、出口は落ちずに failed で返る"""
        self.change()
        self.intake()
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIn("役の返答を受けた記録が無い", fin["reason"])
        self.assertEqual(self.material()["materials"]["hygiene"]["status"], "not_run")

    def test_prep_without_intake_fails_the_node(self):
        self.assertIn("intake.json", self.run.failing("role_prep", f"{LOOP}.{NAME}-prep"))

    def test_included_block_writes_in_its_own_place(self):
        self.run.script("intake", "judge__hygiene__intake", base="", entry="", lang="")
        self.run.script("role_prep", f"judge__hygiene__{LOOP}.{NAME}-prep")
        fin = self.run.script("finish", "judge__hygiene__finish")
        self.assertEqual(fin["material"]["path"], "judge/hygiene/material.json")


class PasteCase(unittest.TestCase):
    def setUp(self):
        self.paste = kit.load("hygiene", "paste")
        self.tmp = pathlib.Path(__import__("tempfile").mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)

    def test_section_runs_to_the_next_heading_of_the_same_depth(self):
        got = self.paste.section_of(REVIEW, "コード衛生観点", "p")
        self.assertEqual(got, "## コード衛生観点\n\n衛生の本文\n\n### 小見出し\n\n中の字")
        self.assertNotIn("別の節", got)

    def test_section_at_the_end_and_partial_match(self):
        self.assertEqual(self.paste.section_of("# a\n\n## 前のコード衛生観点 ③\n本文\n", "コード衛生観点", "p"),
                         "## 前のコード衛生観点 ③\n本文")

    def test_missing_heading_is_a_key_error(self):
        with self.assertRaises(KeyError):
            self.paste.section_of("# 観点\n\n本文\n", "コード衛生観点", "p")

    def test_diff_body_replaces_bad_bytes_and_does_not_cut(self):
        path = self.tmp / "d.patch"
        path.write_bytes(b"+ok\n+bad \xff byte\n" + b"+x\n" * 50000)
        got = self.paste.diff_body(str(path))
        self.assertIn("bad � byte", got)
        self.assertEqual(got.count("+x\n"), 50000)

    def test_review_section_reads_the_file(self):
        path = self.tmp / "REVIEW.md"
        path.write_text(REVIEW, encoding="utf-8")
        self.assertTrue(self.paste.review_section(str(path)).startswith("## コード衛生観点"))

    def test_the_factory_review_md_has_the_section(self):
        vp = kit.load("hygiene", "viewpoint")
        own, _ = vp.materialkit.review_md_paths(kit.ROOT)
        self.assertIn("衛生", self.paste.review_section(own))

    def test_values_use_the_factory_review_md_only(self):
        """対象の根の REVIEW.md は使わない（観点の正本は工場の物）"""
        vp = kit.load("hygiene", "viewpoint")
        repo = self.tmp / "repo"
        repo.mkdir()
        (repo / "REVIEW.md").write_text("# 対象\n\n## コード衛生観点\n\n対象の本文\n", encoding="utf-8")
        diff = self.tmp / "d.patch"
        diff.write_text("+直した\n", encoding="utf-8")
        view = vp.materialkit.View(repo, "b", "r", str(diff), ("a",), "c", "", 0)
        got = vp.values(view, {})
        self.assertNotIn("対象の本文", got["review_section"])
        self.assertEqual(got["diff"], "+直した\n")


class ShapeCase(unittest.TestCase):
    """YAML の揃い（block の形の検査は tests/layers/test_block_shape.py）"""

    def setUp(self):
        doc = yaml.safe_load((BLOCK / f"works-factory-{NAME}.yaml").read_text(encoding="utf-8"))
        self.nodes = {n["id"]: n for n in doc["nodes"]}
        self.body = {n["id"]: n for n in self.nodes[LOOP]["loop_group"]["nodes"]}

    def test_loop_bound_matches_the_give_up_count(self):
        import rolekit
        self.assertEqual(self.nodes[LOOP]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER)

    # 今の判定の hygiene の役の起こし方（tests/workflows/test_judge.py の表の hygiene の行と workflows/judge/works-factory-judge.yaml の
    # node を、作り直しの時に字で写した物）。組み込みで workflows/ が入れ替わっても、この期待は block の起こし方の正本として残る
    LAUNCH = {"model": "@wf-judge-materials", "settingSources": ["user"], "allowed_tools": [], "mutates_checkout": False,
              "sandbox": {"enabled": True, "allowUnsandboxedCommands": False},
              "idle_timeout": 1728000000, "retry": {"max_attempts": 2, "on_error": "all"}}

    def test_launch_matches_the_judge_role(self):
        """起こし方は今の判定の hygiene の役と同じ（群の既定は sonnet・medium。道具を 1 つも持たない）"""
        import launchgroups
        role = self.body[NAME]
        self.assertEqual({k: role.get(k) for k in self.LAUNCH}, self.LAUNCH)
        self.assertEqual(launchgroups.default_of(role["model"]), ("sonnet", "medium"))
        self.assertEqual(role["output_format"]["required"], ["findings", "seen"])
        self.assertEqual(sorted(role["output_format"]["properties"]), ["findings", "seen"])

    def test_inputs_are_the_family_three(self):
        doc = yaml.safe_load((BLOCK / f"works-factory-{NAME}.yaml").read_text(encoding="utf-8"))
        self.assertEqual(sorted(doc["inputs"]), ["base", "entry", "lang"])


if __name__ == "__main__":
    unittest.main()

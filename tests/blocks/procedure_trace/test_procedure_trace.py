"""手順トレースの block を、script を子のプロセスで回して確かめる（docs/design/materials.md の 8 節・docs/design/procedure-trace.md の 2.9）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → role_prep → 台本の返答 → role_accept →
finish と回し、material.json と出力の 5 欄を照らす。拒まれる返答 3 回で gave_up になる道も回す。
筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import unittest


from tests.bin.gitkit import git
from tests.blocks import kit

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


if __name__ == "__main__":
    unittest.main()

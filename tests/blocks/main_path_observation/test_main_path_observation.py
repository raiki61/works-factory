"""主経路の実行観測の block を、script を子のプロセスで回して確かめる（docs/design/materials.md の 8 節・docs/design/main-path-observation.md の 2.9）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → role_prep → 台本の返答 →
role_accept → finish と回し、material.json と出力の 5 欄を照らす。拒まれる返答 3 回で gave_up になる道も回す。
筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import sys
import unittest


from tests.bin.gitkit import git
from tests.blocks import kit

sys.path.append(str(kit.ROOT / "lib"))
NAME = "main-path-observation"
LOOP = f"{NAME}-loop"
ROW = {"path": "変えたコマンドを 1 回動かした", "value": "使い方の文を出して終了コード 0"}
GOOD = {"material": {"status": "clean", "checked": "変えたコマンドの入口を写しで 1 回動かした"}, "observed": [ROW]}


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

    def test_observed_reply_is_taken_into_the_material(self):
        """写す元 MaterialCase.test_accept_writes_material_file: clean と観測の行 1 つの返答が通り、素材の欄に写る"""
        self.assertTrue(self.intake()["due"])
        self.prep()
        self.assertEqual(self.accept(GOOD), {"ok": True, "done": True, "reason": ""})
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["reason"]), (True, "ran", ""))
        self.assertEqual(fin["material"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "material.json"})
        doc = self.material()
        self.assertEqual((doc["role"], doc["status"]), (NAME, "ran"))
        self.assertEqual(doc["materials"], {"main_path_observation": GOOD["material"]})
        self.assertEqual(doc["reply"], GOOD)
        self.assertEqual(fin["report"], ["素材 main_path_observation: clean（見た所: 変えたコマンドの入口を写しで 1 回動かした）",
                                         "  - 観測: 変えたコマンドを 1 回動かした → 使い方の文を出して終了コード 0"])

    def test_seen_status_without_observed_rows_is_refused(self):
        """写す元 MaterialCase.test_accept_rules の main-path-observation の場合: 見たと言う状態に観測の行が無ければ拒む"""
        self.intake()
        for status, extra in (("clean", {"checked": "見た"}), ("found", {"count": 1, "detail": "x"})):
            with self.subTest(status=status):
                self.prep()
                got = self.accept({"material": {"status": status, **extra}, "observed": []})
                self.assertEqual((got["ok"], got["done"]), (False, False))
                self.assertTrue(got["reason"].startswith(f"観点 {NAME}: status={status} なのに観測した値（observed）が 1 つも無い"),
                                got["reason"])
                self.assertFalse((self.run.artifacts / "accepted.json").exists())

    def test_unobserved_statuses_pass_without_rows(self):
        self.intake()
        for material in ({"status": "awaiting_human", "reason": "実 DB が無い。人が結合テストを走らせて画面を見る"},
                         {"status": "not_run", "reason": "動かす手段が無い"}):
            with self.subTest(status=material["status"]):
                self.prep()
                self.assertTrue(self.accept({"material": material, "observed": []})["ok"])
                self.assertEqual(self.finish()["status"], "ran")
                self.assertEqual(self.material()["materials"], {"main_path_observation": material})
                (self.run.artifacts / "accepted.json").unlink()

    def test_not_applicable_is_refused(self):
        self.intake()
        self.prep()
        got = self.accept({"material": {"status": "not_applicable", "reason": "無い"}, "observed": []})
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertIn("条件が真で走ったのに not_applicable", got["reason"])
        self.assertTrue(self.prep()["prompt"].startswith("## Why your previous answer was rejected"))

    def test_three_rejections_give_up(self):
        self.intake()
        bad = {"material": {"status": "clean", "checked": "読んだだけ"}, "observed": []}
        dones = []
        for _ in range(3):
            self.prep()
            dones.append(self.accept(bad)["done"])
        self.assertEqual(dones, [False, False, True])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "gave_up"))
        self.assertIn("3 回とも受け付けで拒まれた", fin["reason"])
        self.assertEqual(self.material()["materials"]["main_path_observation"]["status"], "not_run")

    def test_changed_working_tree_is_refused(self):
        self.intake()
        self.prep()
        (self.run.repo / "README.md").write_text("役が書き換えた\n", encoding="utf-8")
        got = self.accept(GOOD)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリー", got["reason"])


if __name__ == "__main__":
    unittest.main()

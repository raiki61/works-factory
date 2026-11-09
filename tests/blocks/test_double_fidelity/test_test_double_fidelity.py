"""代役の忠実性の block を、script を子のプロセスで回して確かめる（docs/design/materials.md の 8 節・docs/design/test-double-fidelity.md の 2.9）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → role_prep → 台本の返答 →
role_accept → finish と回し、material.json と出力の 5 欄を照らす。筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import sys
import unittest


from tests.bin.gitkit import git
from tests.blocks import kit

NAME = "test-double-fidelity"
LOOP = f"{NAME}-loop"
GOOD = {"material": {"status": "clean", "checked": "client.py の代役と実物の応答 1 件の形"}, "mismatches": []}
FOUND = {"material": {"status": "found", "count": 1, "detail": "応答の形が違う"},
         "mismatches": [{"where": "app.txt:1", "text": "代役の応答に id が無い", "mechanism": "実物は id を返す"}]}


class FlowCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, NAME)
        (self.run.repo / "app.txt").write_text("1 行目\n", encoding="utf-8")
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

    def test_port_values_alone_reach_the_material(self):
        """写す元 MaterialCase.test_test_double_fidelity_reply_is_taken_or_refused: carried_over は拒み、clean は素材の欄に写して受ける"""
        self.assertEqual(self.intake()["due"], True)
        self.prep()
        refused = self.accept({**GOOD, "material": {"status": "carried_over"}})
        self.assertEqual((refused["ok"], refused["done"]), (False, False))
        self.assertIn("素材 'test_double_fidelity'（観点 test-double-fidelity）は今の周に走ったのに carried_over", refused["reason"])
        self.prep()
        self.assertEqual(self.accept(GOOD), {"ok": True, "done": True, "reason": ""})
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["reason"]), (True, "ran", ""))
        self.assertEqual(fin["material"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "material.json"})
        doc = self.material()
        self.assertEqual((doc["role"], doc["status"]), (NAME, "ran"))
        self.assertEqual(doc["materials"], {"test_double_fidelity": GOOD["material"]})

    def test_not_applicable_is_refused(self):
        self.intake()
        self.prep()
        refused = self.accept({**GOOD, "material": {"status": "not_applicable", "reason": "継ぎ目が無い"}})
        self.assertEqual((refused["ok"], refused["done"]), (False, False))
        self.assertIn("条件が真で走ったのに not_applicable", refused["reason"])

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
        self.assertEqual(self.material()["materials"]["test_double_fidelity"]["status"], "not_run")

    def test_location_beyond_the_file_is_sent_back_then_marked(self):
        """写す元 MaterialCase.test_location_beyond_the_file_is_sent_back_then_marked: 外れた where は 1・2 回目は拒み、3 回目は印を付けて受ける"""
        sys.path.append(str(kit.ROOT / "lib"))
        import materialkit
        self.intake()
        bad = {**FOUND, "mismatches": [{"where": "app.txt:1", "text": "a"}, {"where": "app.txt:99", "text": "b"}]}
        for _ in range(2):
            self.prep()
            got = self.accept(bad)
            self.assertEqual((got["ok"], got["done"]), (False, False))
            self.assertIn(materialkit.LOCATION_HEAD, got["reason"])
        self.prep()
        self.assertEqual(self.accept(bad)["ok"], True)
        self.finish()
        wheres = [r["where"] for r in self.material()["reply"]["mismatches"]]
        self.assertEqual(wheres, ["app.txt:1", "app.txt:99" + materialkit.LOCATION_MARK])


if __name__ == "__main__":
    unittest.main()

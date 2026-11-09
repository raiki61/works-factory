"""外部標準照合の block を、script を子のプロセスで回して確かめる（docs/design/materials.md の 8 節・docs/design/external-standards.md の 2.9）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → role_prep → 台本の返答 →
role_accept → finish と回し、material.json と出力の 5 欄を照らす。拒まれる返答 3 回で gave_up になる道と、判定から入る run で
役を起こさない道も回す。筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import unittest


from tests.bin.gitkit import git
from tests.blocks import kit

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

    def test_unreadable_purpose_fails_with_the_port_name(self):
        got = self.intake(purpose='{"purpose_text": ""}')
        self.assertFalse(got["due"])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIn("purpose", fin["reason"])
        self.assertEqual(self.material()["materials"]["external_standards"]["status"], "not_run")


if __name__ == "__main__":
    unittest.main()

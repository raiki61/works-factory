"""整合性と迂回の block を、script を子のプロセスで回して確かめる（docs/design/materials.md の 8 節・docs/design/consistency-bypass.md の 2.9）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → role_prep → 台本の返答 →
role_accept → finish と回し、material.json と出力の 5 欄を照らす。拒まれる返答 3 回で gave_up になる道・判定から入る run で
skipped になる道も回す。筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import unittest


from tests.bin.gitkit import git
from tests.blocks import kit

NAME = "consistency-bypass"
LOOP = f"{NAME}-loop"
GOOD = {"consistency": {"status": "found", "count": 1, "detail": "a.py:1 が b.py の宣言と食い違う"},
        "bypass": {"status": "clean", "checked": "標準の口を見た"},
        "findings": [{"where": "README.md:1", "text": "呼び手が追従していない", "measured": "未実測"}],
        "bypass_findings": [], "seen": "差分の全部", "unseen": "CI の定義"}


class FlowCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, NAME)
        (self.run.repo / "README.md").write_text("# 対象\n\n始め方\n", encoding="utf-8")
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

    def test_reply_is_taken_or_refused(self):
        """写す元 MaterialCase.test_consistency_bypass_reply_is_taken_or_refused: bypass の無い返答は拒み、2 つを書いた返答は受けて、
        material.json の materials が {consistency, bypass}"""
        got = self.intake()
        self.assertTrue(got["due"])
        self.assertIn("通常の run", got["reason"])
        self.prep()
        refused = self.accept({k: v for k, v in GOOD.items() if k != "bypass"})
        self.assertEqual((refused["ok"], refused["done"]), (False, False))
        self.assertIn("素材 'bypass' が返答に無い", refused["reason"])
        again = self.prep()["prompt"]
        self.assertIn("素材 'bypass' が返答に無い", again, "次の回の指示に拒否の文が入る")
        self.assertTrue((self.run.artifacts / f"{NAME}-prompt-2.md").is_file())
        self.assertEqual(self.accept(GOOD), {"ok": True, "done": True, "reason": ""})
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["reason"]), (True, "ran", ""))
        self.assertEqual(fin["material"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "material.json"})
        self.assertEqual(fin["report"], ["素材 consistency: found（1 件）: a.py:1 が b.py の宣言と食い違う",
                                         "素材 bypass: clean（見た所: 標準の口を見た）",
                                         "  - 見ていない範囲: CI の定義"])
        doc = self.material()
        self.assertEqual((doc["role"], doc["status"]), (NAME, "ran"))
        self.assertEqual(doc["materials"], {"consistency": GOOD["consistency"], "bypass": GOOD["bypass"]})
        self.assertEqual(doc["reply"], GOOD)

    def test_each_material_is_checked_on_its_own(self):
        self.intake()
        self.prep()
        no_count = {**GOOD, "bypass": {"status": "found", "detail": "標準の口を使っていない"}}
        refused = self.accept(no_count)
        self.assertFalse(refused["ok"])
        self.assertIn("bypass", refused["reason"])
        self.prep()
        for status in ("not_applicable", "carried_over"):
            with self.subTest(status=status):
                self.assertFalse(self.accept({**GOOD, "consistency": {"status": status, "reason": "x", "from_round": 1}})["ok"])

    def test_three_rejections_give_up(self):
        self.intake()
        bad = {**GOOD, "consistency": {"status": "not_applicable", "reason": "無い"}}
        dones = []
        for _ in range(3):
            self.prep()
            dones.append(self.accept(bad)["done"])
        self.assertEqual(dones, [False, False, True])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "gave_up"))
        self.assertIn("3 回とも受け付けで拒まれた", fin["reason"])
        mats = self.material()["materials"]
        self.assertEqual({k: v["status"] for k, v in mats.items()}, {"consistency": "not_run", "bypass": "not_run"})
        self.assertEqual(mats["consistency"], mats["bypass"])

    def test_entry_run_skips_the_role(self):
        """写す元 DueCase.test_empty_diff_run_with_requests_runs_only_prior_decisions のこの観点の部分と
        test_run_with_a_diff_runs_them: entry が在り差分が空なら due が偽、出口が skipped で 2 つの素材が not_applicable"""
        got = self.intake(entry="人の依頼（/tmp/req.json）")
        self.assertFalse(got["due"])
        self.assertIn("起こさない", got["reason"])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (True, "skipped"))
        self.assertIn("件数は渡されていない", json.dumps(self.material(), ensure_ascii=False))
        for name, mat in self.material()["materials"].items():
            with self.subTest(name=name):
                self.assertEqual(mat["status"], "not_applicable")
                self.assertIn("人の依頼（/tmp/req.json）", mat["reason"])
        self.setUp()
        (self.run.repo / "README.md").write_text("直した\n", encoding="utf-8")
        self.assertTrue(self.intake(entry="人の依頼（/tmp/req.json）")["due"], "差分が在る run は entry が在っても回す")

    def test_unreadable_base_fails_with_the_port_name(self):
        got = self.intake(base="no-such-revision")
        self.assertFalse(got["due"])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertEqual({k: v["status"] for k, v in self.material()["materials"].items()},
                         {"consistency": "not_run", "bypass": "not_run"})


class ViewpointCase(unittest.TestCase):
    def setUp(self):
        self.vp = kit.load(NAME, "viewpoint")

    def test_declaration(self):
        self.assertEqual((self.vp.MATERIALS, self.vp.GUARDED, self.vp.NA, self.vp.NA_REASON),
                         (("consistency", "bypass"), True, "never", ""))
        with self.assertRaises(NotImplementedError):
            self.vp.applies(None, {})
        self.assertFalse(self.vp.judged_na(None, {}))

    def test_materials_of_takes_only_object_materials(self):
        self.assertEqual(self.vp.materials_of({"consistency": {"status": "clean"}, "bypass": "x"}),
                         {"consistency": {"status": "clean"}})


if __name__ == "__main__":
    unittest.main()

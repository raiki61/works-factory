"""衛生の観点の block を、script を子のプロセスで回して確かめる（docs/design/materials.md の 8 節・docs/design/hygiene.md の 2.9）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → role_prep → 台本の返答 →
role_accept → finish と回し、material.json と出力の 5 欄を照らす。拒まれる返答 3 回で gave_up になる道も回す。
筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import pathlib
import unittest
from unittest import mock


from tests.bin.gitkit import git
from tests.blocks import kit

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

    def test_missing_viewpoint_section_fails_prep_and_finish_still_returns(self):
        """観点の節が見つからない時は黙って空で役を起こさず、prep の本体（prompt_inputs）が見出しの名つきの KeyError で落ちる
        （工場の不具合）。役の返答が無いまま出口を回すと、落ちずに failed で返る（docs/design/hygiene.md の 2.9）"""
        vp = kit.load("hygiene", "viewpoint")
        self.change()
        self.intake()
        own = self.run.repo / "no-section" / "REVIEW.md"
        own.parent.mkdir()
        own.write_text("# 観点\n\n本文\n", encoding="utf-8")
        with self.run.env(), mock.patch.object(vp.materialkit, "review_md_paths", return_value=(str(own), "")):
            with self.assertRaises(KeyError) as caught:
                vp.materialkit.prompt_inputs(vp, self.run.artifacts, lambda raw: raw)
        self.assertIn("見出し「コード衛生観点」が無い", str(caught.exception))
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIn("役の返答を受けた記録が無い", fin["reason"])
        self.assertEqual(self.material()["materials"]["hygiene"]["status"], "not_run")

    def test_failed_when_the_role_never_answered(self):
        """役の返答を受けた記録が無いまま出口を回すと、落ちずに failed で返る。prep を回さない道を見る
        （prep が落ちる道は上の試験）"""
        self.change()
        self.intake()
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIn("役の返答を受けた記録が無い", fin["reason"])
        self.assertEqual(self.material()["materials"]["hygiene"]["status"], "not_run")


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
        own, _ = vp.materialkit.review_md_paths(kit.ROOT, vp.REVIEW_MD)
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


if __name__ == "__main__":
    unittest.main()

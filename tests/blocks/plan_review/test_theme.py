"""事前審査の block の形 theme（設計の案の審査。docs/design/plan-review.md の 19 節）の試験。

script（intake → theme_prep → 台本の返答 → theme_accept → finish）を子のプロセスで回す。入口は入力 theme_doc が空でなければ形 theme と決め、
設計の案の md を place に写し、往復の記録 prior から往復の番号を数える。指示は prompts/review-theme.md と断片から組み、設計の案の
在りか・目的・世界の解の行・独立設計・前の往復の答えの要る穴・8 種の確かめと設計の観点（parts/theme-checks.md）を持ち、修正案の構造を
前提にする文を持たない。受け付けは形 text の照らしに、前の往復の答えの要る穴が resolved か faces のどちらかに在る照らしを項目なしで
足し、受け付けの網 rolekit.NET_AFTER 回目で諦める。拒まれた後の出し直しは同じ会話の続きの review-theme-fix で、前の答えと合わせる。
"""
import unittest

from tests.blocks import kit
from tests.blocks.plan_review import values as V

ROUNDS = kit.load("line", "rounds")   # 往復の記録の書き手（line）。plan-review の src を読む前に読む（kit.load は前の src を外す）
themeform = kit.load("plan-review", "themeform")
files = themeform.files
import converge   # noqa: E402  lib/
import rolekit    # noqa: E402  lib/

DRAFT = "# 設計の案\n\nTHEME-DRAFT-MARK-4411 入口を 1 か所に寄せる\n\n## 問い\n\n- Q1: 段をいくつにするか\n"
THEME_NODE = "p2.plan_review.theme"


def face(key, kind="contract_drift", severity="block", reach="forces_redesign", **extra) -> dict:
    """設計の案の審査の穴の行（unit_keys を持たない）"""
    return {"key": key, "kind": kind, "where": "設計の案の changes C1", "why": f"{key} の穴になる筋道を 20 字以上で書いた行",
            "severity": severity, "reach": reach, **extra}


def reply(*faces, **extra) -> dict:
    out = {"faces": list(faces), "shrink": [], "reason": V.REASON}
    if not faces:
        out["faces_none"] = V.FACES_NONE
    return {**out, **extra}


def record(run, *passes) -> str:
    """line の書き手で組んだ往復の記録（rounds.fresh に、穴の行の並び passes の往復を rounds.record_pass で足した物。項目の行 plan を
    持たない）を run の置き場に置いた pointer。手で枠を組まない"""
    doc = ROUNDS.fresh()
    for n, faces in enumerate(passes, 1):
        got = {"pass": n, "answers": [], "review": {"faces": list(faces), "shrink": [], "reason": V.REASON}, "resolved": []}
        ROUNDS.record_pass(doc, got, at_cap=False, dest=run.artifacts / "line" / "passes")
    return run.put("line/theme-converge.json", kit.shaped("shared:plan-converge.schema.json", doc))


class _Case(unittest.TestCase):
    def setUp(self):
        self.r = V.Block(self)

    def draft(self, text=DRAFT) -> str:
        return self.r.put("theme/design.md", text, raw=True)

    def intake(self, **inputs) -> dict:
        got = self.r.intake(**{"theme_doc": self.draft(), "purpose": V.PURPOSE, **inputs})
        self.assertEqual((got["due"], got["form"]), (True, "theme"), got)
        return got

    def prep(self, prev="") -> dict:
        return self.r.script("theme_prep", prev=prev)

    def prompt(self, **inputs) -> str:
        self.intake(**inputs)
        got = self.prep()
        self.assertFalse(got["resubmit"], got)
        return got["prompt"]

    def accept(self, doc=None, fix=None) -> dict:
        def raw(x):
            return "null" if x is None else x if isinstance(x, str) else V.dump(x)
        return self.r.script("theme_accept", reply=raw(doc), fix_reply=raw(fix), status_guarded="true")


class ThemeIntakeCase(_Case):
    def test_theme_doc_decides_the_form_and_copies_the_draft(self):
        """theme_doc が空でなければ形 theme。設計の案を place に写し、1 往復目は k=1"""
        got = self.intake()
        self.assertEqual(got["k"], 1)
        doc = self.r.read(files.INTAKE)
        self.assertEqual(doc["form"], "theme")
        self.assertEqual((self.r.artifacts / files.THEME_COPY).read_text(encoding="utf-8"), DRAFT)
        self.assertEqual(doc["theme_file"], str(self.r.artifacts / files.THEME_COPY))

    def test_theme_doc_wins_over_the_other_review_inputs(self):
        """theme_doc と plan・proposal を一緒に渡されても形 theme と決め、読まなかった入力を既定の訳に名指す"""
        self.intake(proposal=V.POLICY_TEXT)
        self.assertIn("入力 proposal は形 theme では読まない（theme_doc が在る）", self.r.read(files.INTAKE)["defaults"])

    def test_prior_gives_the_pass_number(self):
        self.assertEqual(self.intake(prior=record(self.r, [face("design-gap-entrance")]))["k"], 2)

    def test_empty_or_missing_draft_fails(self):
        got = self.r.intake(theme_doc=self.draft(" \n"))
        self.assertEqual((got["due"], got["form"]), (False, "theme"))
        self.assertIn("入力 theme_doc", got["reason"])
        got = self.r.intake(theme_doc=self.r.pointer("theme/nope.md"))
        self.assertFalse(got["due"])
        self.assertIn("入力 theme_doc", got["reason"])


class ThemePromptCase(_Case):
    def test_prompt_names_the_draft_and_the_design_checks(self):
        """設計の案の在りか・目的・Repository の行・8 種の確かめ・設計の観点を持つ。組んだ指示と作業ツリーの姿を place に置く"""
        prompt = self.prompt()
        for want in (str(self.r.artifacts / files.THEME_COPY), "## Purpose", V.PURPOSE,
                     f"Repository: {self.r.repo} (read version: `HEAD`) BASE: `HEAD`", "## What to look at", "8. **Precedent source**",
                     "## What to look at in a design draft", "a design draft, not a fix plan", "Do not write `unit_keys`"):
            self.assertIn(want, prompt, want)
        self.assertTrue((self.r.artifacts / "review-theme-prompt-1.md").is_file())
        self.assertTrue((self.r.artifacts / files.TREE_STATE).is_file())

    def test_prompt_skips_what_needs_a_plan_structure(self):
        prompt = self.prompt()
        for absent in ("## Material", "Units:", "Items that write design_map", "How the checks above read the plan", "`shrink_first`",
                       "Agent", "## Previous passes"):
            self.assertNotIn(absent, prompt, absent)

    def test_independent_design_and_world_rows(self):
        prompt = self.prompt(design=V.dump(V.DESIGN_OK), world_rows=self.r.world(V.WORLD_ROW))
        self.assertIn(V.DESIGN_TEXT, prompt)
        self.assertIn("## Standard practice found for the theme", prompt)
        self.assertIn("There is no independent design", self.prompt())

    def test_previous_passes_list_the_owed_holes(self):
        """2 往復目からは、前の往復の block の穴を挙げ、resolved か同じ key で faces に挙げ直せと頼む"""
        prompt = self.prompt(prior=record(self.r, [face("design-gap-entrance")]))
        self.assertIn("## Previous passes", prompt)
        self.assertIn("#### design-gap-entrance", prompt)
        self.assertIn("put the key in `resolved`", prompt)

    def test_resubmit_prompt_continues_the_conversation(self):
        """前の周の受け付けが拒み、合わせた答えの控えが在れば、出し直しの役の指示（拒否の訳と合わせた答えの在りか）を組む"""
        self.intake()
        self.prep()
        got = self.accept(reply(face("entrance-without-no-add", kind="entrance")))
        self.assertFalse(got["ok"], got)
        self.assertEqual(self.prep(prev="false"), {"prompt": "", "resubmit": True})
        out = self.r.script("theme_fix_prep")
        self.assertIn("Your previous answer was rejected by the machine's check.", out["prompt"])
        self.assertIn(str(rolekit.candidate_path(self.r.artifacts, THEME_NODE)), out["prompt"])
        self.assertIn("no_add", out["prompt"])
        self.assertTrue((self.r.artifacts / "review-theme-fix-prompt-1.md").is_file())


class ThemeAcceptCase(_Case):
    def setUp(self):
        super().setUp()
        self.intake()
        self.prep()

    def rejected(self, doc, want: str) -> dict:
        got = self.accept(doc)
        self.assertEqual((got["ok"], got["done"]), (False, False), got)
        self.assertIn(want, got["reason"])
        self.assertFalse((self.r.artifacts / files.REVIEW).exists())
        return got

    def test_pass_writes_the_review_and_finish_returns_the_round(self):
        got = self.accept(reply(face("design-gap-entrance")))
        self.assertEqual((got["ok"], got["done"], got["give_up"]), (True, True, False), got)
        out = self.r.script("finish")
        self.assertEqual((out["ok"], out["status"], out["form"], out["round"], out["blocks"], out["pass"], out["asks"]),
                         (True, "ok", "theme", 1, ["design-gap-entrance"], None, []))
        self.assertEqual(self.r.read(out["holes"]["path"])["faces"][0]["key"], "design-gap-entrance")
        self.assertEqual(out["report"][0], "事前審査（1 往復目・設計の案）: block design-gap-entrance・suggest 0 件・別案 0 件・消えた穴 0 件")

    def test_face_rows_and_whole_reply_are_checked_like_the_text_form(self):
        self.rejected(reply(face("entrance-without-no-add", kind="entrance")), "no_add")
        self.rejected(reply(face("policy-unnamed-face", kind="policy", severity="suggest")), "policy")
        self.rejected({"faces": [], "shrink": [], "reason": V.REASON, "faces_none": "無い"}, "faces_none")
        self.rejected({"faces": [], "reason": V.REASON, "faces_none": V.FACES_NONE}, "shrink")

    def test_read_only_tree_changed_rejected(self):
        (self.r.repo / "stray.txt").write_text("役が足した\n", encoding="utf-8")
        self.rejected(reply(), "読むだけの役が作業ツリーを変えた")

    def test_resubmit_is_merged_with_the_previous_answer(self):
        """出し直しの役は拒まれた欄だけを返し、受け付けが前の答えと合わせてから全体を照らす"""
        self.rejected(reply(face("entrance-without-no-add", kind="entrance")), "no_add")
        fixed = face("entrance-with-no-add", kind="entrance", no_add="柵を足さずに 2 つの入口を 1 つの口にまとめる形")
        got = self.accept(fix={"faces": [fixed]})
        self.assertTrue(got["ok"], got)
        saved = self.r.read(files.REVIEW)
        self.assertEqual(([f["key"] for f in saved["faces"]], saved["reason"]), (["entrance-with-no-add"], V.REASON))

    def test_give_up_at_the_net(self):
        """拒否の回数では諦めず、受け付けの網 rolekit.NET_AFTER 回目で done・give_up。出口は gave_up と諦めの訳"""
        bad = reply(face("entrance-without-no-add", kind="entrance"))
        for _ in range(rolekit.NET_AFTER - 1):
            self.rejected(bad, "no_add")
        got = self.accept(bad)
        self.assertEqual((got["ok"], got["done"], got["give_up"]), (False, True, True), got)
        out = self.r.script("finish")
        self.assertEqual((out["ok"], out["status"], out["form"]), (False, "gave_up", "theme"))
        self.assertTrue(out["reason"].startswith("事前審査の受け付けが諦めた: "), out["reason"])
        self.assertEqual(self.r.read(files.REVIEW)["faces"], [], "諦めた時も holes は空の返答を指す")


class ThemeRoundsCase(_Case):
    """2 往復目から: 前の往復の答えの要る穴は resolved か faces のどちらかに要る（項目なしで鍵だけで照らす）"""

    def setUp(self):
        super().setUp()
        self.intake(prior=record(self.r, [face("design-gap-entrance"), face("design-gap-copy", kind="copy")]))
        self.prep()

    def test_every_owed_hole_needs_a_destination(self):
        got = self.accept(reply(face("design-gap-copy", kind="copy")))
        self.assertFalse(got["ok"], got)
        self.assertIn("design-gap-entrance", got["reason"])
        self.assertNotIn("design-gap-copy", got["reason"].split("design-gap-entrance")[0])

    def test_resolved_and_raised_again_pass(self):
        got = self.accept(reply(face("design-gap-copy", kind="copy"), resolved=["design-gap-entrance"]))
        self.assertTrue(got["ok"], got)
        saved = self.r.read(files.REVIEW)
        self.assertEqual(saved[converge.RESOLVED], ["design-gap-entrance"])
        out = self.r.script("finish")
        self.assertEqual((out["round"], out["blocks"]), (2, ["design-gap-copy"]))
        self.assertTrue(out["report"][0].endswith("・消えた穴 1 件"), out["report"])

    def test_stray_resolved_and_both_places_rejected(self):
        got = self.accept(reply(face("design-gap-copy", kind="copy"), resolved=["design-gap-entrance", "never-raised-key"]))
        self.assertIn("never-raised-key", got["reason"])
        got = self.accept(reply(face("design-gap-copy", kind="copy"), resolved=["design-gap-entrance", "design-gap-copy"]))
        self.assertIn("resolved と block の face の両方", got["reason"])


class ThemeReadsCase(_Case):
    def test_reads_role_and_handed_draft(self):
        """形 theme の読んだ証拠は役の名 plan-review-theme で、渡したパスは設計の案の写し"""
        import json
        import pathlib
        import subprocess
        import sys

        from tests.bin import hermetic
        self.intake()
        config = self.r.artifacts.parent / "claude"
        done = subprocess.run([sys.executable, str(kit.BLOCKS / "plan-review" / "scripts" / "review_reads.py")], cwd=self.r.repo,
                              capture_output=True, text=True, encoding="utf-8",
                              env=hermetic.child_env(**self.r.environ(), CLAUDE_CONFIG_DIR=str(config)))
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(done.stdout)
        index = json.loads(pathlib.Path(got["index_file"]).read_text(encoding="utf-8"))
        self.assertEqual(list(index), ["plan-review-theme"])


if __name__ == "__main__":
    unittest.main()

"""指示の比べ（docs/design/README.md の 11.4・docs/design/gate-efficacy.md の 2.9。1 つ目の commit だけ。2 つ目の commit で消す）。

block の prep が組んだ指示が、今の判定の指示（workflows/judge/commands/material-gate-efficacy.md に prep の 3 つの値を入れた物）と
空白を除いて同じこと、block が書く材料のファイルが今の判定の material_prep の物と同じ字であることを照らす。
"""
import json
import pathlib
import sys
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

NAME = "gate-efficacy"
CURRENT = kit.ROOT / "workflows" / "judge" / "commands" / "material-gate-efficacy.md"


def squeeze(text: str) -> str:
    return "".join(text.split())


class PromptCase(unittest.TestCase):
    def setUp(self):
        sys.path.append(str(kit.ROOT / "lib"))
        import judge_accept
        import rolekit
        self.ja, self.rolekit = judge_accept, rolekit
        self.run = kit.Run(self, NAME)
        (self.run.repo / "app.txt").write_text("一行目\n二行目\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")
        (self.run.repo / "app.txt").write_text("一行目\n直した\n", encoding="utf-8")
        self.head = git(self.run.repo, "rev-parse", "HEAD").strip()

    def built(self, lang=""):
        self.run.script("intake", "intake", base="", gates="", entry="", lang=lang)
        return self.run.script("role_prep", f"{NAME}-loop.{NAME}-prep")["prompt"]

    def current_prompt(self, lang_line, reason, brief_file):
        text = CURRENT.read_text(encoding="utf-8")
        for key, value in (("lang_line", lang_line), ("reason", reason), ("brief_file", brief_file)):
            text = text.replace(f"$gate-efficacy-prep.output.{key}", value)
        return text

    def test_prompt_equals_the_current_prompt_filled_with_the_same_values(self):
        brief = str(self.run.artifacts / "material-gate-efficacy-brief.md")
        for lang in ("", "Japanese"):
            with self.subTest(lang=lang):
                self.assertEqual(squeeze(self.built(lang)),
                                 squeeze(self.current_prompt(self.rolekit.lang_line({"lang": lang}), "", brief)))

    def test_prompt_carries_the_rejection_reason_as_the_current_one_does(self):
        self.run.script("intake", "intake", base="", gates="", entry="", lang="")
        self.run.script("role_prep", f"{NAME}-loop.{NAME}-prep")
        reply = {"material": {"status": "clean", "checked": "x"}, "arms": []}
        got = self.run.script("role_accept", f"{NAME}-loop.{NAME}-accept", reply=json.dumps(reply))
        self.assertFalse(got["ok"])
        again = self.run.script("role_prep", f"{NAME}-loop.{NAME}-prep")["prompt"]
        brief = str(self.run.artifacts / "material-gate-efficacy-brief.md")
        reason = self.rolekit.rejects_text(self.rolekit.rejected(self.run.artifacts, NAME))
        self.assertIn(got["reason"], reason)
        self.assertEqual(squeeze(again), squeeze(self.current_prompt(self.rolekit.lang_line({"lang": ""}), reason, brief)))

    def test_brief_equals_the_current_material_prep(self):
        """例の run の値の形（ゲートの印の在る差分・無い差分・変異の宣言の 3 通り）で、今の material_prep の材料のファイルと同じ字"""
        ja = self.ja
        decl = {"suite": [{"name": "t", "argv": ["true"]}], "mutation": {"argv": ["mutate", "--fast"], "arms": "arms.txt"}}
        (self.run.repo / "arms.txt").write_text("arm-1\n", encoding="utf-8")
        cases = (("gate-free", {}), ("tests file", {"tests/test_a.py": "x\n"}), ("declared", {".review-checks.json": json.dumps(decl)}),
                 ("no stage", {".review-checks.json": json.dumps({"suite": decl["suite"]})}),
                 ("broken", {".review-checks.json": "{"}))
        for label, files in cases:
            with self.subTest(label):
                for name in (".review-checks.json", "tests/test_a.py"):
                    (self.run.repo / name).unlink(missing_ok=True)
                for name, body in files.items():
                    path = self.run.repo / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(body, encoding="utf-8")
                self.built()
                ours = (self.run.artifacts / "material-gate-efficacy-brief.md").read_text(encoding="utf-8")
                view = json.loads((self.run.artifacts / "view.json").read_text(encoding="utf-8"))
                jdir = self.run.artifacts / "oldjudge"
                jdir.mkdir(exist_ok=True)
                start = ja.start_view({"base_rev": self.head, "input": {"base": {"rev": self.head}, "diff": {"empty": False},
                                                                        "requests": 1}})
                ja.write_json(jdir / ja.START_FILE, start)
                ja.material_route(jdir, self.run.repo)
                old = ja.material_prep(jdir, "gate-efficacy", self.run.repo, "")["brief"]
                old_view = ja.read_json(jdir / ja.MATERIAL_VIEW_FILE)
                swap = lambda text, v, d: text.replace(v["diff_file"], d + "/diff.patch").replace(  # noqa: E731
                    v["changed_files_file"], d + "/changed-files.txt")
                self.assertEqual(swap(ours, view, "<dir>"), swap(old, old_view, "<dir>"))


if __name__ == "__main__":
    unittest.main()

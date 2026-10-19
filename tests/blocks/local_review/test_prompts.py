"""指示の比べ（docs/design/README.md の 11.4。1 つ目の commit だけ。2 つ目の commit で消す）。

prompts/local-review.md は、今の workflows/judge/commands/material-local-review.md の $local-review-prep.output.<欄> の 5 つ
（lang_line・reason・brief_file・review_md・repo_review_md）を {<欄>} に替えた日本語の字。prep が組んだ指示が、今の md に同じ 5 つの値を入れた
字と（空白を除いて）同じか、材料のファイルを組む src/oldbrief.py が今の material_prep と同じ字かを照らす。
"""
import json
import pathlib
import subprocess
import sys
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

NAME = "local-review"
OLD_MD = kit.ROOT / "workflows" / "judge" / "commands" / "material-local-review.md"


def squeeze(text: str) -> str:
    return " ".join(text.split())


def filled(**values) -> str:
    text = OLD_MD.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace(f"$local-review-prep.output.{key}", value)
    return text


class PromptCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, NAME)
        (self.run.repo / "app.txt").write_text("一行目\n", encoding="utf-8")
        (self.run.repo / "REVIEW.md").write_text("# 対象の観点\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")
        (self.run.repo / "app.txt").write_text("一行目\n直した\n", encoding="utf-8")
        self.run.script("intake", "intake", base="", entry="", lang="")
        self.mk = kit.load(NAME, "viewpoint").materialkit

    def values(self, reason):
        import rolekit
        own, theirs = self.mk.review_md_paths(self.run.repo)
        return {"lang_line": rolekit.lang_line({"lang": ""}), "reason": reason, "review_md": own, "repo_review_md": theirs,
                "brief_file": str(self.run.artifacts / "material-local-review-brief.md")}

    def test_first_round_prompt_is_the_current_prompt(self):
        got = self.run.script("role_prep", f"{NAME}-loop.{NAME}-prep")["prompt"]
        self.assertEqual(squeeze(got), squeeze(filled(**self.values(""))))

    def test_prompt_after_a_rejection_is_the_current_prompt(self):
        bad = {"material": {"status": "not_applicable", "reason": "無い"}, "simplify_carried": False, "findings": []}
        refused = self.run.script("role_accept", f"{NAME}-loop.{NAME}-accept", reply=json.dumps(bad))
        self.assertFalse(refused["ok"])
        got = self.run.script("role_prep", f"{NAME}-loop.{NAME}-prep")["prompt"]
        self.assertEqual(squeeze(got), squeeze(filled(**self.values(refused["reason"]))))

    def test_old_brief_is_the_current_brief(self):
        """src/oldbrief.py の字は、今の judge_accept.material_prep が組む材料のファイルと同じ"""
        sys.path.append(str(kit.ROOT / "lib"))
        import judge_accept as ja
        lenses = kit.load(NAME, "lenses")
        oldbrief = kit.load(NAME, "oldbrief")
        jdir = self.run.artifacts / "judge"
        jdir.mkdir()
        head = git(self.run.repo, "rev-parse", "HEAD").strip()
        ja.write_json(jdir / ja.START_FILE, {"base_rev": head, "input": {"base": {"rev": head}, "diff": {"empty": False}, "requests": 1}})
        ja.material_route(jdir, self.run.repo)
        own, theirs = self.mk.review_md_paths(self.run.repo)
        want = ja.material_prep(jdir, NAME, self.run.repo, own, theirs)["brief"]
        doc = ja.read_json(jdir / ja.MATERIAL_VIEW_FILE)
        view = self.mk.View.from_dict(self.run.repo, {"commits": 0, "stat": "", **doc})
        self.assertEqual(oldbrief.brief(view, own, theirs, lenses.skills()), want)


if __name__ == "__main__":
    unittest.main()

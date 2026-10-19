"""指示の比べ（docs/design/README.md の 11.4・docs/design/consistency-bypass.md の 2.9）。1 つ目の commit だけ。2 つ目の commit（英語）で消す。

(a) block の prep が組んだ指示は、今の指示 workflows/judge/commands/material-consistency-bypass.md に同じ値を入れた字と、空白を無視して同じ。
(b) src/oldbrief.py が組む材料のファイルは、同じリポジトリと同じ差分で今の judge_accept.material_prep が返す字と同じ。
"""
import pathlib
import re
import sys
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

sys.path.append(str(kit.ROOT / "lib"))
import judge_accept as ja  # noqa: E402
import materialkit  # noqa: E402
import rolekit  # noqa: E402

NAME = "consistency-bypass"
OLD_MD = kit.ROOT / "workflows" / "judge" / "commands" / "material-consistency-bypass.md"


def squeeze(text: str) -> str:
    return re.sub(r"\s+", "", text)


class PromptCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, NAME)
        repo = self.run.repo
        (repo / "README.md").write_text("# 対象\n\n始め方\n", encoding="utf-8")
        (repo / "app.txt").write_text("一行目\n二行目\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "seed")
        (repo / "app.txt").write_text("一行目\n直した\n", encoding="utf-8")

    def old_prompt(self, **values) -> str:
        return re.sub(r"\$consistency-bypass-prep\.output\.(\w+)", lambda m: values[m.group(1)],
                      OLD_MD.read_text(encoding="utf-8"))

    def test_prompt_equals_the_current_one_filled_with_the_same_values(self):
        for with_repo_review in (False, True):
            with self.subTest(repo_review=with_repo_review):
                self.setUp()
                if with_repo_review:
                    (self.run.repo / "REVIEW.md").write_text("# 対象の観点\n", encoding="utf-8")
                self.run.script("intake", "intake", base="", entry="", lang="Japanese")
                got = self.run.script("role_prep", f"{NAME}-loop.{NAME}-prep")["prompt"]
                own, theirs = materialkit.review_md_paths(self.run.repo)
                want = self.old_prompt(lang_line=rolekit.lang_line({"lang": "Japanese"}), reason="",
                                       brief_file=str(self.run.artifacts / "material-consistency-bypass-brief.md"),
                                       review_md=own, repo_review_md=theirs)
                self.assertEqual(squeeze(got), squeeze(want))
                self.assertEqual(bool(theirs), with_repo_review)

    def test_rejected_round_carries_the_reason_like_the_current_one(self):
        self.run.script("intake", "intake", base="", entry="", lang="")
        self.run.script("role_prep", f"{NAME}-loop.{NAME}-prep")
        refused = self.run.script("role_accept", f"{NAME}-loop.{NAME}-accept", reply="{}")
        self.assertFalse(refused["ok"])
        got = self.run.script("role_prep", f"{NAME}-loop.{NAME}-prep")["prompt"]
        own, _ = materialkit.review_md_paths(self.run.repo)
        want = self.old_prompt(lang_line=rolekit.lang_line({}), reason=refused["reason"],
                               brief_file=str(self.run.artifacts / "material-consistency-bypass-brief.md"),
                               review_md=own, repo_review_md="")
        self.assertEqual(squeeze(got), squeeze(want))

    def test_old_brief_equals_the_current_material_prep(self):
        for with_repo_review in (False, True):
            with self.subTest(repo_review=with_repo_review):
                self.setUp()
                repo, jdir = self.run.repo, self.run.artifacts / ja.JUDGE_DIR
                jdir.mkdir(parents=True, exist_ok=True)
                head = git(repo, "rev-parse", "HEAD").strip()
                ja.write_json(jdir / ja.START_FILE, ja.start_view(
                    {"base_rev": head, "input": {"base": {"rev": head}, "diff": {"empty": False}, "requests": 1}}))
                ja.material_route(jdir, repo)
                own, _ = materialkit.review_md_paths(repo)
                theirs = ""
                if with_repo_review:
                    (repo / "REVIEW.md").write_text("# 対象の観点\n", encoding="utf-8")
                    theirs = str(repo.resolve() / "REVIEW.md")
                want = ja.material_prep(jdir, NAME, repo, own, theirs)["brief"]
                doc = ja.read_json(jdir / ja.MATERIAL_VIEW_FILE)
                view = materialkit.View.from_dict(repo, {**doc, "stat": "", "commits": 0})
                oldbrief = kit.load(NAME, "oldbrief")
                self.assertEqual(oldbrief.brief(view, {}), want)


if __name__ == "__main__":
    unittest.main()

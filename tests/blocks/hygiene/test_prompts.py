"""指示の比べ（docs/design/README.md の 11.4 の 1 つ目の commit。docs/design/hygiene.md の 2.9）: 日本語の md を組んだ指示が、
今の commands/material-hygiene.md に同じ 5 つの値を入れた字と同じで（空白と改行の違いは除く）、材料の本文（src/oldbrief.py）が
今の judge_accept.material_prep が同じ値で返す字と同じ。2 つ目の commit（英語）で消す"""
import json
import sys
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

OLD_MD = kit.ROOT / "workflows" / "judge" / "commands" / "material-hygiene.md"
REVIEW = "# 観点\n\n## コード衛生観点\n\n衛生の本文\n\n### 小見出し\n\n中の字\n\n## 次\n\n別の節\n"


def squeeze(text: str) -> str:
    return " ".join(text.split())


class PromptCompareCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "hygiene")
        (self.run.repo / "app.txt").write_text("一行目\n二行目\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")
        self.head = git(self.run.repo, "rev-parse", "HEAD").strip()
        (self.run.repo / "app.txt").write_text("一行目\n直した $HOME と $x\n", encoding="utf-8")
        sys.path.append(str(kit.ROOT / "lib"))

    def test_new_prompt_and_brief_match_the_old(self):
        import judge_accept as ja
        import materialkit
        import rolekit
        self.run.script("intake", "intake", base="", entry="", lang="")
        got = self.run.script("role_prep", "hygiene-loop.hygiene-prep")["prompt"]
        own, theirs = materialkit.review_md_paths(self.run.repo)
        brief_file = self.run.artifacts / "material-hygiene-brief.md"
        brief = brief_file.read_text(encoding="utf-8")
        old = (OLD_MD.read_text(encoding="utf-8")
               .replace("$hygiene-prep.output.lang_line", rolekit.lang_line({}))
               .replace("$hygiene-prep.output.reason", "")
               .replace("$hygiene-prep.output.review_md", own)
               .replace("$hygiene-prep.output.repo_review_md", theirs)
               .replace("$hygiene-prep.output.brief", brief))
        self.assertEqual(squeeze(got), squeeze(old))
        self.assertIn("直した $HOME と $x", brief, "差分の本文を貼る")
        self.assertIn("コード衛生観点", brief)

    def test_brief_equals_the_current_material_prep(self):
        """同じ値（試験の REVIEW.md・使い捨てのリポジトリ）で今の material_prep が返す材料の字と、同じ字"""
        import judge_accept as ja
        review = self.run.artifacts.parent / "REVIEW.md"
        review.write_text(REVIEW, encoding="utf-8")
        jdir = self.run.artifacts.parent / "judge"
        jdir.mkdir()
        ja.write_json(jdir / ja.START_FILE, {"base_rev": self.head,
                                             "input": {"base": {"rev": self.head}, "diff": {"empty": False}, "requests": 1}})
        old = ja.material_prep(jdir, "hygiene", self.run.repo, str(review), "")["brief"]
        self.run.script("intake", "intake", base="", entry="", lang="")
        vp = kit.load("hygiene", "viewpoint")
        from src import oldbrief
        import materialkit
        view, values, _ = materialkit._intake_doc(self.run.artifacts)
        orig = vp.materialkit.review_md_paths
        vp.materialkit.review_md_paths = lambda repo, lib_dir=None: (str(review), "")
        try:
            new = oldbrief.brief(view, values)
        finally:
            vp.materialkit.review_md_paths = orig
        self.assertEqual(new, old)


if __name__ == "__main__":
    unittest.main()

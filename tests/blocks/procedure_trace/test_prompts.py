"""指示の比べ（docs/design/README.md の 11.4 の 1 つ目の commit。docs/design/procedure-trace.md の 2.9）: 日本語の md を組んだ指示が、
今の commands/material-procedure-trace.md に同じ 5 つの値を入れた字と同じで（空白と改行の違いは除く）、材料のファイルが今の
judge_accept.material_prep が同じ値で描く字と同じ。この観点は記録の在る run のどれでも回っていないので（設計書の頭）、本物の run の
材料のファイルは無く、今のコードで描いた字と比べる。2 つ目の commit（英語）で消す"""
import sys
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

OLD_MD = kit.ROOT / "workflows" / "judge" / "commands" / "material-procedure-trace.md"


def squeeze(text: str) -> str:
    return " ".join(text.split())


class PromptCompareCase(unittest.TestCase):
    def setUp(self):
        sys.path.append(str(kit.ROOT / "lib"))
        self.run = kit.Run(self, "procedure-trace")
        (self.run.repo / "README.md").write_text("# 対象\n\n始め方\n", encoding="utf-8")
        (self.run.repo / "app.txt").write_text("一行目\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")
        self.head = git(self.run.repo, "rev-parse", "HEAD").strip()

    def old_brief(self, review_md: str, repo_review_md: str) -> dict:
        import judge_accept as ja
        jdir = self.run.artifacts.parent / "old-judge"
        jdir.mkdir()
        ja.write_json(jdir / ja.START_FILE, ja.start_view(
            {"base_rev": self.head, "input": {"base": {"rev": self.head}, "diff": {"empty": False}, "requests": 0}}))
        return jdir, ja.material_prep(jdir, "procedure-trace", self.run.repo, review_md, repo_review_md)

    def compare(self):
        import rolekit
        self.run.script("intake", "intake", base=self.head, entry="", lang="")
        got = self.run.script("role_prep", "procedure-trace-loop.procedure-trace-prep")["prompt"]
        own = str(kit.ROOT / "lib" / "REVIEW.md")
        theirs = self.run.repo / "REVIEW.md"
        theirs = str(theirs.resolve()) if theirs.is_file() else ""
        jdir, old = self.old_brief(own, theirs)
        brief_file = self.run.artifacts / "material-procedure-trace-brief.md"
        new_brief = brief_file.read_text(encoding="utf-8")
        self.assertEqual(new_brief, old["brief"].replace(str(jdir / "diff.patch"), str(self.run.artifacts / "diff.patch")))
        text = (OLD_MD.read_text(encoding="utf-8")
                .replace("$procedure-trace-prep.output.lang_line", rolekit.lang_line({}))
                .replace("$procedure-trace-prep.output.reason", "")
                .replace("$procedure-trace-prep.output.brief_file", str(brief_file))
                .replace("$procedure-trace-prep.output.review_md", own)
                .replace("$procedure-trace-prep.output.repo_review_md", theirs))
        self.assertEqual(squeeze(got), squeeze(text))
        return new_brief

    def test_prompt_and_brief_match_the_old_when_a_procedure_file_changed(self):
        (self.run.repo / "run.sh").write_text("echo hi\n", encoding="utf-8")
        brief = self.compare()
        self.assertIn("この周に真（差分に手順書・スクリプト・CI 定義が 1 件）なので、`not_applicable` は受け付けが拒む", brief)

    def test_prompt_and_brief_match_the_old_with_the_target_review_guide(self):
        (self.run.repo / "run.sh").write_text("echo hi\n", encoding="utf-8")
        (self.run.repo / "REVIEW.md").write_text("# 観点\n", encoding="utf-8")
        self.compare()


if __name__ == "__main__":
    unittest.main()

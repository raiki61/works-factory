"""1 つ目の commit だけの試験（docs/design/external-standards.md の 2.9 の指示の比べ）: 組んだ指示が、今の指示 workflows/judge/commands/
material-external-standards.md に同じ差し込み口の値を入れた字と、空白を除いて同じ。2 つ目の commit（英語にする）でこのファイルを消す"""
import json
import re
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

OLD = kit.ROOT / "workflows" / "judge" / "commands" / "material-external-standards.md"
NAME = "external-standards"
PURPOSE = {"purpose_text": "会話スレッドにピン留めの印を付けてサイドバーの枠を分ける変更", "source": "①PR 説明",
           "known_weaknesses": [], "source_files": []}


def squeeze(text: str) -> str:
    return re.sub(r"\s+", "", text)


class SameAsTodayCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, NAME)
        (self.run.repo / "a.py").write_text("x = 1\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")
        (self.run.repo / "a.py").write_text("x = 2\n", encoding="utf-8")

    def old(self, **holes) -> str:
        text = OLD.read_text(encoding="utf-8")
        for name, value in holes.items():
            text = text.replace(f"$external-standards-prep.output.{name}", value)
        return text

    def intake(self, **inputs):
        ports = {"base": "", "purpose": json.dumps(PURPOSE, ensure_ascii=False), "entry": "", "lang": "", **inputs}
        return self.run.script("intake", "intake", **ports)

    def test_first_round_prompt_equals_the_current_prompt_filled_with_the_same_values(self):
        self.assertTrue(self.intake()["due"])
        got = self.run.script("role_prep", f"{NAME}-loop.{NAME}-prep")["prompt"]
        brief = self.run.artifacts / f"material-{NAME}-brief.md"
        own, _ = kit.load(NAME, "viewpoint").materialkit.review_md_paths(self.run.repo)
        lang_line = "人が読む文の欄（reason・how・what・why・異議・所見・申し出の文など、承認ノードと報告に載る文）は 依頼文の言語（利用者の言語） で書け。" \
                    "key・enum の値・コード識別子・パス・コマンド・エラー文はそのまま（key は周をまたいで突き合わせるので訳さない）。"
        want = self.old(lang_line=lang_line, reason="", brief_file=str(brief), review_md=own, repo_review_md="")
        self.assertEqual(squeeze(got), squeeze(want))
        text = brief.read_text(encoding="utf-8")
        self.assertIn("## 材料: loop.diff_file", text)
        self.assertIn(PURPOSE["purpose_text"], text)
        self.assertIn("a.py", text)

    def test_after_a_rejection_the_reason_is_filled_in(self):
        self.intake(purpose="null", lang="Japanese")
        self.run.script("role_prep", f"{NAME}-loop.{NAME}-prep")
        bad = {"material": {"status": "clean", "checked": "x"}, "findings": [], "seen": "s", "unseen": "u", "web_refetched": True,
               "rankings": [{"problem": "parse a file", "source": "docs", "ranked": ["a"], "diff_at": "b"}]}
        refused = self.run.script("role_accept", f"{NAME}-loop.{NAME}-accept", reply=json.dumps(bad))
        self.assertFalse(refused["ok"])
        got = self.run.script("role_prep", f"{NAME}-loop.{NAME}-prep")["prompt"]
        self.assertIn(refused["reason"], got)
        self.assertIn("Japanese", got)
        self.assertIn("目的の文はこの run に無い", (self.run.artifacts / f"material-{NAME}-brief.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

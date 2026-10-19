"""指示の比べ（docs/design/README.md の 11.4・docs/design/provenance.md の 2.9。1 つ目の commit だけ。2 つ目の commit で消す）。

日本語の md が、今の指示 workflows/judge/commands/material-provenance.md に同じ値を入れた字と、空白を除いて同じになること、
材料のファイル（今の material-provenance-brief.md）を同じ字で組めることを照らす。
"""
import json
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

NAME = "provenance"
OLD_MD = kit.ROOT / "workflows" / "judge" / "commands" / "material-provenance.md"
LANG_LINE = "人が読む文の欄は日本語で書け。"
# 例の run（53e71318）の judge/material-provenance-brief.md の字。3 つの値（差分・根・リポジトリ）だけ穴にした
BRIEF = """# 素材集めの役の材料（機械が描いた物）

素材集めの役 provenance（graphloops のノード p1.provenance）の指示書の「［材料: 〜］」は、この下の同じ名のセクションの値。パス（対象差分・変更ファイルの一覧・観点の正本など）は Read で読め（道具の無い役には本文を貼ってある）。

## 材料: loop.diff_file

{diff_file}

## 材料: record.base

{base}

## 材料: inputs.cwd

{repo}

## 『条件に当たらない』（not_applicable）を書けるか（works の受け付けより。上の指示書の読み替え）

このノードは条件（applies_cond）を持たず、graph も『条件に当たらない』を名乗れるノードと宣言していない（na_self_ok が無い）ので、`not_applicable` は受け付けが拒む——見た結果を found・clean で、確かめられなかったなら not_run（理由つき）で書け。
"""


def squeeze(text: str) -> str:
    return " ".join(text.split())


def old_prompt(lang_line: str, reason: str, brief_file: str) -> str:
    """今の md に、Archon が入れる 3 つの値（$provenance-prep.output.<欄>）を入れた字"""
    text = OLD_MD.read_text(encoding="utf-8")
    for field, value in (("lang_line", lang_line), ("reason", reason), ("brief_file", brief_file)):
        text = text.replace(f"$provenance-prep.output.{field}", value)
    return text


class PromptCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, NAME)
        (self.run.repo / "README.md").write_text("# 対象\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")
        self.run.script("intake", "intake", base="", entry="", lang="")
        self.brief_file = self.run.artifacts / "material-provenance-brief.md"

    def prep(self):
        return self.run.script("role_prep", f"{NAME}-loop.{NAME}-prep")["prompt"]

    def test_first_round_equals_the_current_prompt(self):
        kit.load(NAME, "viewpoint")
        with self.run.env():
            import prompt
            lang = prompt.lang("")
        got = self.prep()
        self.assertEqual(squeeze(got), squeeze(old_prompt(lang, "", str(self.brief_file))))

    def test_rejected_round_equals_the_current_prompt(self):
        self.prep()
        reply = {"material": {"status": "carried_over", "from_round": 1, "reason": "前の周と同じ"}, "claims": []}
        refused = self.run.script("role_accept", f"{NAME}-loop.{NAME}-accept", reply=json.dumps(reply, ensure_ascii=False))
        self.assertFalse(refused["ok"])
        got = self.prep()
        kit.load(NAME, "viewpoint")
        with self.run.env():
            import prompt
            import rolekit
            lang = prompt.lang("")
            reason = rolekit.rejects_text(rolekit.rejected(self.run.artifacts, NAME))
        self.assertIn("carried_over", reason)
        self.assertEqual(squeeze(got), squeeze(old_prompt(lang, reason, str(self.brief_file))))

    def test_brief_file_equals_the_current_brief(self):
        self.prep()
        view = json.loads((self.run.artifacts / "view.json").read_text(encoding="utf-8"))
        want = BRIEF.format(diff_file=view["diff_file"], base=view["base"], repo=view["repo"])
        self.assertEqual(self.brief_file.read_text(encoding="utf-8"), want)


if __name__ == "__main__":
    unittest.main()

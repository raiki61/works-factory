"""指示の比べ（docs/design/README.md の 11.4 の 1 つ目の commit。docs/design/main-path-observation.md の 2.9）: 日本語の md を組んだ指示が、
今の commands/material-main-path-observation.md に同じ 3 つの値を入れた字と同じで（空白と改行の違いは除く）、材料のファイルが本物の run の
judge/material-main-path-observation-brief.md と同じ字（パスは試験の物に置き換える）。2 つ目の commit（英語）で消す"""
import json
import sys
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

# 本物の run の材料のファイル。3 つのパスだけ <DIFF>・<CHANGED>・<REPO> に置き換えてある
RUN_BRIEF = ('# 素材集めの役の材料（機械が描いた物）\n\n素材集めの役 main-path-observation（graphloops のノード p1.main_path_observation）の指示書の'
             '「［材料: 〜］」は、この下の同じ名のセクションの値。パス（対象差分・変更ファイルの一覧・観点の正本など）は Read で読め（道具の無い役には本文を貼ってある）。\n\n'
             '## 材料: loop.diff_file\n\n<DIFF>\n\n## 材料: loop.changed_files_file\n\n<CHANGED>\n\n## 材料: inputs.cwd\n\n<REPO>\n\n'
             '## 『条件に当たらない』（not_applicable）を書けるか（works の受け付けより。上の指示書の読み替え）\n\n'
             'このノードの条件 `user_path_touched` はこの周に真（差分が利用者から見える経路に触れる）なので、`not_applicable` は受け付けが拒む'
             '——見た結果を found・clean で、確かめられなかったなら not_run（理由つき）で書け。\n')
OLD_MD = kit.ROOT / "workflows" / "judge" / "commands" / "material-main-path-observation.md"


def squeeze(text: str) -> str:
    return " ".join(text.split())


class PromptCompareCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "main-path-observation")
        (self.run.repo / "README.md").write_text("x\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")
        (self.run.repo / "README.md").write_text("y\n", encoding="utf-8")

    def test_new_prompt_and_brief_match_the_old(self):
        self.run.script("intake", "intake", base="", entry="", lang="")
        got = self.run.script("role_prep", "main-path-observation-loop.main-path-observation-prep")["prompt"]
        brief_file = self.run.artifacts / "material-main-path-observation-brief.md"
        sys.path.append(str(kit.ROOT / "lib"))
        import rolekit
        old = (OLD_MD.read_text(encoding="utf-8")
               .replace("$main-path-observation-prep.output.lang_line", rolekit.lang_line({}))
               .replace("$main-path-observation-prep.output.reason", "")
               .replace("$main-path-observation-prep.output.brief_file", str(brief_file)))
        self.assertEqual(squeeze(got), squeeze(old))
        view = json.loads((self.run.artifacts / "view.json").read_text(encoding="utf-8"))
        want = (RUN_BRIEF.replace("<DIFF>", view["diff_file"]).replace("<CHANGED>", view["changed_files_file"])
                .replace("<REPO>", view["repo"]))
        self.assertEqual(brief_file.read_text(encoding="utf-8"), want)


if __name__ == "__main__":
    unittest.main()

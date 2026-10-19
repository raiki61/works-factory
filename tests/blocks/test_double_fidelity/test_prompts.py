"""指示の比べ（docs/design/README.md の 11.4 の 1 つ目の commit。docs/design/test-double-fidelity.md の 2.9）: 日本語の md を例の run の値で
組んだ指示が、今の commands/material-test-double-fidelity.md に同じ 3 つの値を入れた字と同じで（空白と改行の違いは除く）、材料のファイルが
例の run の judge/material-test-double-fidelity-brief.md と同じ字（パスは試験の物に置き換える）。2 つ目の commit（英語）で消す"""
import sys
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

OLD_MD = kit.ROOT / "workflows" / "judge" / "commands" / "material-test-double-fidelity.md"
JUDGE = "<state>/workspaces/<owner>/<repo>/artifacts/runs/53e71318-ac9f-4468-ae72-5f6ed569a667/judge"
RUN_REPO = "<state>/workspaces/<owner>/<repo>/worktrees/archon/task-works-factory-line-1792307529854"
RUN_BRIEF = ('# 素材集めの役の材料（機械が描いた物）\n\n素材集めの役 test-double-fidelity（graphloops のノード p1.test_double_fidelity）の指示書の'
             '「［材料: 〜］」は、この下の同じ名のセクションの値。パス（対象差分・変更ファイルの一覧・観点の正本など）は Read で読め（道具の無い役には本文を貼ってある）。\n\n'
             f'## 材料: loop.diff_file\n\n{JUDGE}/diff.patch\n\n## 材料: loop.changed_files_file\n\n{JUDGE}/changed-files.txt\n\n'
             f'## 材料: inputs.cwd\n\n{RUN_REPO}\n\n'
             '## 『条件に当たらない』（not_applicable）を書けるか（works の受け付けより。上の指示書の読み替え）\n\n'
             'このノードの条件 `seams_touched` はこの周に真（差分が外部との継ぎ目に触れる）なので、`not_applicable` は受け付けが拒む——見た結果を found・clean で、確かめられなかったなら not_run（理由つき）で書け。\n')


def squeeze(text: str) -> str:
    return " ".join(text.split())


class PromptCompareCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "test-double-fidelity")
        (self.run.repo / "README.md").write_text("x\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")

    def test_new_prompt_and_brief_match_the_old(self):
        self.run.script("intake", "intake", base="", entry="", lang="")
        got = self.run.script("role_prep", "test-double-fidelity-loop.test-double-fidelity-prep")["prompt"]
        brief_file = self.run.artifacts / "material-test-double-fidelity-brief.md"
        sys.path.append(str(kit.ROOT / "lib"))
        import rolekit
        old = (OLD_MD.read_text(encoding="utf-8")
               .replace("$test-double-fidelity-prep.output.lang_line", rolekit.lang_line({}))
               .replace("$test-double-fidelity-prep.output.reason", "")
               .replace("$test-double-fidelity-prep.output.brief_file", str(brief_file)))
        self.assertEqual(squeeze(got), squeeze(old))
        import json
        view = json.loads((self.run.artifacts / "view.json").read_text(encoding="utf-8"))
        want = (RUN_BRIEF.replace(f"{JUDGE}/diff.patch", view["diff_file"])
                .replace(f"{JUDGE}/changed-files.txt", view["changed_files_file"]).replace(RUN_REPO, view["repo"]))
        self.assertEqual(brief_file.read_text(encoding="utf-8"), want)


if __name__ == "__main__":
    unittest.main()

"""指示の比べ（docs/design/README.md の 11.4 の 1 つ目の commit。docs/design/prior-decisions.md の 2.9）: 日本語の md を例の run
df5e111f-ea97-409b-8066-2245d32746ab の値で組んだ指示が、今の commands/material-prior-decisions.md に同じ 3 つの値を入れた字と同じで
（空白と改行の違いは除く）、材料のファイルが例の run の judge/material-prior-decisions-brief.md と同じ字（リポジトリのパスは試験の
リポジトリに置き換える）。2 つ目の commit（英語）で消す"""
import json
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

RUN_REPO = "/Users/p03623/.local/state/works-factory/targets/6c76444e/archon-home/workspaces/raiki61/works-factory/worktrees/archon/task-works-factory-line-1792348017642"
RUN_BRIEF = '# 素材集めの役の材料（機械が描いた物）\n\n素材集めの役 prior-decisions（graphloops のノード p0.prior_decisions）の指示書の「［材料: 〜］」は、この下の同じ名のセクションの値。パス（対象差分・変更ファイルの一覧・観点の正本など）は Read で読め（道具の無い役には本文を貼ってある）。\n\n## 材料: inputs.cwd\n\n/Users/p03623/.local/state/works-factory/targets/6c76444e/archon-home/workspaces/raiki61/works-factory/worktrees/archon/task-works-factory-line-1792348017642\n\n## 材料: record.base\n\n4428f368d229f2d4f4343122c620c3fdeb334184\n\n## 材料: loop.changed_files\n\n[]\n\n## 材料: loop.request_wheres\n\n[\n "workflows/merge/scripts/pr_commit.py の hook_env（73 行あたり）"\n]\n\n## 『条件に当たらない』（not_applicable）を書けるか（works の受け付けより。上の指示書の読み替え）\n\nこのノードは条件（applies_cond）を持たず、graph も『条件に当たらない』を名乗れるノードと宣言していない（na_self_ok が無い）ので、`not_applicable` は受け付けが拒む——見た結果を found・clean で、確かめられなかったなら not_run（理由つき）で書け。\n'
REQUEST = json.dumps([{"where": "workflows/merge/scripts/pr_commit.py の hook_env（73 行あたり）", "text": "直したい事"}],
                     ensure_ascii=False)
OLD_MD = kit.ROOT / "workflows" / "judge" / "commands" / "material-prior-decisions.md"
RUN_BASE = "4428f368d229f2d4f4343122c620c3fdeb334184"


def squeeze(text: str) -> str:
    return " ".join(text.split())


class PromptCompareCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "prior-decisions")
        (self.run.repo / "README.md").write_text("x\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")

    def test_new_prompt_and_brief_match_the_old(self):
        self.run.script("intake", "intake", base="", request=REQUEST, entry="人の依頼（/p/req.json）", lang="")
        got = self.run.script("role_prep", "prior-decisions-loop.prior-decisions-prep")["prompt"]
        brief_file = self.run.artifacts / "material-prior-decisions-brief.md"
        sys_path = kit.ROOT / "lib"
        import sys
        sys.path.append(str(sys_path))
        import rolekit
        old = (OLD_MD.read_text(encoding="utf-8")
               .replace("$prior-decisions-prep.output.lang_line", rolekit.lang_line({}))
               .replace("$prior-decisions-prep.output.reason", "")
               .replace("$prior-decisions-prep.output.brief_file", str(brief_file)))
        self.assertEqual(squeeze(got), squeeze(old))
        view = json.loads((self.run.artifacts / "view.json").read_text(encoding="utf-8"))
        want = RUN_BRIEF.replace(RUN_REPO, view["repo"]).replace(RUN_BASE, view["base"])
        self.assertEqual(brief_file.read_text(encoding="utf-8"), want)


if __name__ == "__main__":
    unittest.main()

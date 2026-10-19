"""1 つ目の commit だけの試験（docs/design/head-depth.md の 7.3）: depth_prep が組んだ指示が、今の指示（workflows/judge/commands/head-depth.md
と、役に Read させる材料 lib/headdepth.brief）を同じ値で並べた物と、空白と改行の違いを除いて同じ字か。2 つ目の commit で消す"""
import json
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

OLD = kit.ROOT / "workflows" / "judge" / "commands" / "head-depth.md"
LANG_SENTENCE = "- `why` と `groups` の各 `why` は the language of the request (the user's language) で書け。key・enum の値・識別子・パス・引用の写し・コマンドはそのまま。"
READ_BRIEF = "- 材料: `$head-depth-prep.output.brief_file`"


def squash(text: str) -> str:
    return "".join(text.split())


class CompareCase(unittest.TestCase):
    def test_prompt_equals_the_current_one(self):
        run = kit.Run(self, "head-depth")
        (run.repo / "stats.py").write_text("a\nb\nc\nreturn sum(xs) / 2\n", encoding="utf-8")
        git(run.repo, "add", "-A")
        git(run.repo, "commit", "-q", "-m", "seed")
        rows = [{"where": "stats.py:4", "text": "mean は 2 でなく 3 を返す。分母を len(xs) にする"}, {"where": "nowhere.py:3", "text": "もう 1 行"}]
        run.script("intake", request=json.dumps(rows, ensure_ascii=False), has_checks="true", thickness="auto", spec="false",
                   design_only="false", lang="")
        new = run.script("depth_prep")["prompt"]

        steps = kit.load("head-depth", "steps")
        with run.env():
            facts = json.loads((run.artifacts / "intake.json").read_text(encoding="utf-8"))["facts"]
        brief = steps.headdepth.brief(facts).split("\n", 1)[1].strip()
        old_lines = OLD.read_text(encoding="utf-8").split("\n")
        body = old_lines[12:]   # 1 行目（言語の 1 行）と 3〜11 行目（拒みの節と区切り）を除く
        at = next(i for i, line in enumerate(body) if line.startswith(READ_BRIEF))
        body[at] = brief
        old = "\n".join(body).rstrip("\n") + "\n" + LANG_SENTENCE
        self.assertEqual(squash(new), squash(old))


if __name__ == "__main__":
    unittest.main()

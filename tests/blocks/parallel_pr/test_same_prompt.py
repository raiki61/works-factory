"""commit 1 だけの試験（commit 2 で消す）: prep が組む指示は、今の工場の指示 workflows/judge/commands/pr-check.md を同じ値で埋めた物と、
空白を除いて同じ（docs/design/parallel-pr.md の 7 節の指示の比べ）。値は今の置き換えの 3 つ: 前の回の拒否の理由（1 回目は空）・言語の 1 行・
渡し物のパス（今は $ARTIFACTS_DIR/judge/pr-brief.json、block では place の pr-brief.json の絶対パス）。
"""
import re
import sys
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

sys.path.append(str(kit.ROOT / "lib"))
import rolekit  # noqa: E402

CURRENT = kit.ROOT / "workflows" / "judge" / "commands" / "pr-check.md"


def squeezed(text: str) -> str:
    return re.sub(r"\s+", "", text)


class SamePromptCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "parallel-pr")
        (self.run.repo / "a.py").write_text("x = 1\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")

    def current(self, *, lang_line: str, reason: str = "") -> str:
        brief = self.run.artifacts / "pr-brief.json"
        return (CURRENT.read_text(encoding="utf-8")
                .replace("$pr-check-reject.output.lang_line", lang_line)
                .replace("$pr-check-reject.output.reason", reason)
                .replace("$ARTIFACTS_DIR/judge/pr-brief.json", str(brief)))

    def test_first_round_is_the_current_prompt(self):
        self.run.script("scan", "scan", base="", request="[]", changed='["a.py"]', lang="日本語")
        got = self.run.script("prep", "pr-check-loop.pr-check-prep", lang="日本語")
        want = self.current(lang_line=rolekit.lang_line({"lang": "日本語"}))
        self.assertEqual(squeezed(got["prompt"]), squeezed(want))

    def test_default_language_is_the_current_default(self):
        self.run.script("scan", "scan", base="", request="[]", changed='["a.py"]', lang="")
        got = self.run.script("prep", "pr-check-loop.pr-check-prep")
        self.assertEqual(squeezed(got["prompt"]), squeezed(self.current(lang_line=rolekit.lang_line({}))))

"""block r1 の指示の md に貼った外の作者の本文の縛り（docs/design/r1.md の 8 節）。

r1-comments の md は pr-review-toolkit:comment-analyzer の定義の本文を字のまま運ぶ（持ち主の決め `prompts-english` の当て方が名指す、
外の作者の本文を書き換えない決め）。本文を sha256 で縛る。役の形（道具・群・返答の型）は tests/layers の全体の検査が見る。
"""
import hashlib
import unittest

from tests.blocks import kit

BLOCK = kit.BLOCKS / "r1"

# pr-review-toolkit:comment-analyzer の定義の本文（anthropics/claude-plugins-official の ce721c1f1d5da2c281588818e072ae01a05d2e73 の
# plugins/pr-review-toolkit/agents/comment-analyzer.md。Apache-2.0）の sha256
COMMENT_ANALYZER_SHA256 = "4a9c1f2eb8234a4b9231983e75739663d512e1aed242388964a165a719b84698"
COMMENT_ANALYZER_FRONT = """---
name: comment-analyzer
description: Use this agent when you need to analyze code comments for accuracy, completeness, and long-term maintainability. This includes (1) after generating large documentation comments or docstrings, (2) before finalizing a pull request that adds or modifies comments, (3) when reviewing existing comments for potential technical debt or comment rot, and (4) when you need to verify that comments accurately reflect the code they describe. See "When to invoke" in the agent body for worked scenarios.
model: inherit
color: green
---

"""
ROLE_HEAD = "## Role definition (comment analyzer)\n\n"


class TextCase(unittest.TestCase):
    def test_r1_comments_carries_the_comment_analyzer_definition_verbatim(self):
        """r1-comments の md の役の定義の節が、comment-analyzer の定義の本文と 1 字も違わない"""
        text = (BLOCK / "prompts" / "r1-comments.md").read_text(encoding="utf-8")
        body = text.partition(ROLE_HEAD)[2].partition("\n\n---\n\n")[0]
        self.assertEqual(hashlib.sha256((COMMENT_ANALYZER_FRONT + body + "\n").encode("utf-8")).hexdigest(), COMMENT_ANALYZER_SHA256)


if __name__ == "__main__":
    unittest.main()

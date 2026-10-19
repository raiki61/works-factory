"""指示の比べ（docs/design/README.md の 11.4。1 つ目の commit だけ。2 つ目の commit で消す）。

組んだ指示が、今の報告の初見の読み手の指示 workflows/report/commands/cold-check.md から、報告の頭に特有の 3 行（md:11-13）を除き、
本文を差し込んだ字と同じ（空白と改行の違いは除く）。
"""
import pathlib
import unittest

from tests.blocks import kit
from tests.blocks.cold_read import values

OLD = kit.ROOT / "workflows" / "report" / "commands" / "cold-check.md"


def flat(text: str) -> str:
    return " ".join(text.split())


class CompareCase(unittest.TestCase):
    def test_same_text_as_the_current_prompt_without_the_report_head_rules(self):
        run = kit.Run(self, "cold-read")
        (run.repo / "draft.md").write_text(values.BODY, encoding="utf-8")
        built = run.script("cold_prep", text="draft.md", lang="")["prompt"]
        lines = OLD.read_text(encoding="utf-8").split("\n")
        old = "\n".join(lines[:10] + lines[13:]).replace("$cold-prep.output.body", values.BODY)
        self.assertNotIn("機械が組んだ事実", old)
        self.assertEqual(flat(built), flat(old))


if __name__ == "__main__":
    unittest.main()

"""持ち主の決めの正本 `docs/owner-decisions.md` の `small-core` の項目が、決めの核と足しを保ち、足しが名指す機械の置き場が実在する。

- 照らすのは語とパスだけで、行の全文は写さない（文を直しても試験が赤にならず、語やパスが外れた時だけ赤にする）。
"""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "owner-decisions.md"
HEADING = "#### `small-core`"
RETURN_ADDITION = "- 足し（2026-11-08）"
KEEPS_OUT_ADDITION = "- 足し（2026-11-04）"
CORE = "R2 が作り直しと言った run は部分を取り込まない。"
RETURN_WORDS = ("`redesign-needed`", "`fix-needed`", "3 周", "「修正の段に返す道を作りたいね」", "「B」")
PLACES = ("lib/seal.py", "workflows/r2/", "workflows/line/")


def small_core(text: str) -> list:
    """`small-core` の項目の行（見出しから次の見出しの前まで）"""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(HEADING))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("#")), len(lines))
    return lines[start:end]


class SmallCoreCase(unittest.TestCase):
    def test_return_addition_names_its_places(self):
        item = small_core(DOC.read_text(encoding="utf-8"))
        added = [line for line in item if line.startswith(RETURN_ADDITION)]
        self.assertEqual(len(added), 1, "small-core に「足し（2026-11-08）」の行が 1 行ある")
        for word in RETURN_WORDS:
            self.assertIn(word, added[0])
        for place in PLACES:
            self.assertIn(f"`{place}`", added[0])
            self.assertTrue((ROOT / place).exists(), f"足しが名指す置き場 {place} が根から見て在る")
        self.assertTrue(any(line.startswith(KEEPS_OUT_ADDITION) for line in item), "2026-11-04 の足しが残る")
        self.assertTrue(any(CORE in line for line in item), "決めの行が残る")


if __name__ == "__main__":
    unittest.main()

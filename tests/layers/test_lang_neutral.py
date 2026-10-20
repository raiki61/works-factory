"""AI のノードへの指示の md（`workflows/*/prompts/`・`workflows/.shared/prompts/`）と `lib/` に、言語と実行器の名の語の表に当たる字が無い（根の `AGENTS.md` の E13 の機械の行。持ち主の決め `lang-neutral`）。

- 語の表は `tests/layers/scan.py` の `LANG_WORDS`。事実上の標準の形式（JUnit XML など）は表に入れない。
- 照らさない物: `lib/tests/`（lib 自身の試験）・`lib/AGENTS.md`・借りた superpowers の写し `lib/borrow/superpowers/`（上流の字のままの写しで、固定 `lib/borrow/borrow.json` の pin の sha256 が 1 字も変えさせない。フォルダに固定のファイルと台帳 `COPIED_FROM` のほかが無いことをここで見る）。
- 例外: 拡張子と言語の対応・テストのファイルの名の慣習の表と、それを作る標準ライブラリの import は、`lib/impact.py`・`lib/changemap.py`・`lib/libdocs.py`・`lib/libdocs_local.py` に限って書いてよい（根の `AGENTS.md` の E13 の「例外」の行）。機械はファイルごとに外すので、表の外に言語の名が無いことは人が見る。
"""
import json
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"


class LangNeutralTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E13", ROOT), [])

    def test_borrowed_copy_holds_only_pinned_files(self):
        """E13 が丸ごと外す lib/borrow/superpowers/ の下は、固定（borrow.json の pin.files）が sha256 で縛るファイルと台帳だけ"""
        borrow = ROOT / "lib" / "borrow"
        pin = json.loads((borrow / "borrow.json").read_text(encoding="utf-8"))["superpowers"]["pin"]
        want = {"COPIED_FROM", *(f"{pin['version']}/{rel}" for rel in pin["files"])}
        copy = borrow / "superpowers"
        have = {p.relative_to(copy).as_posix() for p in copy.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
        self.assertEqual(have, want)

    def test_seed_caught(self):
        got = scan.problems("E13", SEEDS / "e13")
        self.assertGreaterEqual(len(got), 1)
        self.assertTrue(any("workflows/judge/prompts/a.md" in line for line in got), got)

    def test_shared_prompts_and_parts_are_in_scope(self):
        files = {"workflows/.shared/prompts/a.md": "pytest\n", "workflows/judge/prompts/parts/b.md": "pytest\n",
                 "workflows/judge/scripts/c.py": 'CMD = "pytest"\n'}
        with tree(files) as root:
            got = scan.problems("E13", root)
        self.assertEqual(sorted(line.split(":")[0] for line in got),
                         ["workflows/.shared/prompts/a.md", "workflows/judge/prompts/parts/b.md"], got)

    def test_lib_is_in_scope(self):
        with tree({"lib/run.py": 'CMD = "pytest"\n'}) as root:
            got = scan.problems("E13", root)
        self.assertTrue(any("lib/run.py:1" in line for line in got), got)

    def test_name_with_version_is_red(self):
        with tree({"workflows/judge/prompts/a.md": "run `ruby3 check.rb`\n"}) as root:
            got = scan.problems("E13", root)
        self.assertTrue(any("a.md:1" in line and "ruby" in line for line in got), got)

    def test_lib_tests_and_lib_rules_are_allowed(self):
        files = {"lib/tests/test_x.py": 'CMD = "pytest"\n', "lib/AGENTS.md": "pytest を名指さない\n"}
        with tree(files) as root:
            self.assertEqual(scan.problems("E13", root), [])

    def test_unreadable_file_is_red(self):
        with tree({"workflows/judge/prompts/b.md": b"\xe9 pytest\n"}) as root:
            got = scan.problems("E13", root)
        self.assertTrue(any("prompts/b.md" in line for line in got), got)


if __name__ == "__main__":
    unittest.main()

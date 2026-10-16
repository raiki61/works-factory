"""`workflows/.shared/` と `bin/_lib/` のファイルが境の口・入口の部品の外し・埋めの名簿の `- 埋め:` の行の頭の欄のどれかに当たり（説明の文にだけ出る名は数えない）、名簿の `- 埋め:` の行の全部のリポジトリの中のパスが木に無い行も赤。「（予定）」の行は木に無くてよい（workflows/AGENTS.md の E2 の機械の行）。"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"


class PolyfillsListedTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E2", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E2", SEEDS / "e2")
        self.assertGreaterEqual(len(got), 1)
        self.assertTrue(any("workflows/.shared/extra.py" in line for line in got), got)

    def test_listed_but_missing_is_red(self):
        got = scan.problems("E2", SEEDS / "e2")
        self.assertTrue(any("docs/polyfills.md" in line and "gone.py" in line for line in got), got)

    def test_unlisted_bin_lib_file_is_red(self):
        got = scan.problems("E2", SEEDS / "e2")
        self.assertTrue(any("bin/_lib/extra.py" in line for line in got), got)

    def test_listed_bin_lib_missing_is_red(self):
        got = scan.problems("E2", SEEDS / "e2")
        self.assertTrue(any("docs/polyfills.md" in line and "bin/_lib/gone.py" in line for line in got), got)

    def test_listed_workflow_file_missing_is_red(self):
        """置き場の外のリポジトリの中のパス（YAML の型の埋めの script など）が木に無い行も赤"""
        registry = "- 埋め: メイングラフの受け皿のノード（script `workflows/line/scripts/returned.py`）\n"
        with tree({"docs/polyfills.md": registry}) as root:
            got = scan.problems("E2", root)
        self.assertTrue(any("docs/polyfills.md:1" in line and "returned.py" in line for line in got), got)

    def test_path_ends_at_full_width_space(self):
        """名簿の行の素のパスは全角の空白（U+3000）で切れる。続く字までパスに入れると、木に在るファイルを無いと言う"""
        registry = "- 埋め: workflows/line/scripts/returned.py\u3000の外\n"
        with tree({"docs/polyfills.md": registry, "workflows/line/scripts/returned.py": ""}) as root:
            got = scan.problems("E2", root)
        self.assertEqual(got, [])

    def test_entry_part_allowance_is_not_red(self):
        with tree({"bin/_lib/pack.py": "", "bin/_lib/borrow/x.json": ""}) as root:
            got = scan.problems("E2", root)
        self.assertEqual(got, [])

    def test_planned_row_may_be_missing(self):
        got = scan.problems("E2", SEEDS / "e2")
        self.assertFalse(any("later.py" in line for line in got), got)

    def test_planned_row_followed_by_text_may_be_missing(self):
        with tree({"docs/polyfills.md": "- 埋め: `workflows/.shared/later.py`（予定）の部品\n"}) as root:
            got = scan.problems("E2", root)
        self.assertEqual(got, [])

    def test_boundary_and_listed_are_allowed(self):
        got = scan.problems("E2", SEEDS / "e2")
        self.assertFalse(any("boundary.py" in line or "listed.py" in line for line in got), got)

    def test_required_mention_wins_over_planned(self):
        registry = "- 埋め: `workflows/.shared/later.py`（予定）\n- 埋め: `workflows/.shared/later.py`\n"
        with tree({"docs/polyfills.md": registry}) as root:
            got = scan.problems("E2", root)
        self.assertTrue(any("docs/polyfills.md:2" in line and "later.py" in line for line in got), got)

    def test_bin_lib_name_only_in_description_is_red(self):
        """頭の欄の外（説明の文）にだけ名が出る bin/_lib/ の部品は、名簿に載った埋めに数えない"""
        registry = "- 埋め: `bin/_lib/y.py`。説明の中の `bin/_lib/x.py`\n"
        with tree({"docs/polyfills.md": registry, "bin/_lib/x.py": "", "bin/_lib/y.py": ""}) as root:
            got = scan.problems("E2", root)
        self.assertEqual(got, ["bin/_lib/x.py:1: 名簿にも境の口にも当たらない"])

    def test_shared_name_only_in_description_is_red(self):
        registry = "- 埋め: `workflows/.shared/y.py`。説明の中の `workflows/.shared/x.py`\n"
        files = {"docs/polyfills.md": registry, "workflows/.shared/x.py": "", "workflows/.shared/y.py": ""}
        with tree(files) as root:
            got = scan.problems("E2", root)
        self.assertEqual(got, ["workflows/.shared/x.py:1: 名簿にも境の口にも当たらない"])

    def test_every_head_path_counts_and_description_does_not(self):
        registry = "- 埋め: `bin/_lib/a.py`、`bin/_lib/b.py`。説明の `bin/_lib/c.py`\n"
        files = {"docs/polyfills.md": registry, **{f"bin/_lib/{n}.py": "" for n in "abc"}}
        with tree(files) as root:
            got = scan.problems("E2", root)
        self.assertEqual(got, ["bin/_lib/c.py:1: 名簿にも境の口にも当たらない"])

    def test_parenthesized_description_after_head_is_not_counted(self):
        """（予定）は欄を続け、ほかの `（` は欄を閉じる"""
        registry = "- 埋め: `bin/_lib/p.py`（予定）、`bin/_lib/y.py`（中身は `bin/_lib/x.py`）。\n"
        with tree({"docs/polyfills.md": registry, "bin/_lib/x.py": "", "bin/_lib/y.py": ""}) as root:
            got = scan.problems("E2", root)
        self.assertEqual(got, ["bin/_lib/x.py:1: 名簿にも境の口にも当たらない"])


if __name__ == "__main__":
    unittest.main()

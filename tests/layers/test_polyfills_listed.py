"""`workflows/.shared/` と `bin/_lib/` のファイルが境の口・入口の部品の外し・埋めの名簿の行のどれかに当たり、名簿の `- 埋め:` の行のリポジトリの中のパスが木に無い行も赤。「（予定）」の行は木に無くてよい（workflows/AGENTS.md の E2 の機械の行）。"""
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

    def test_entry_part_allowance_is_not_red(self):
        """名簿に無い bin/_lib/ のファイルも、ALLOWED["E2"] の行に当たれば赤にしない"""
        with tree({"bin/_lib/pack.py": "", "bin/_lib/borrow/x.json": ""}) as root:
            got = scan.problems("E2", root)
        self.assertEqual(got, [])

    def test_planned_row_may_be_missing(self):
        got = scan.problems("E2", SEEDS / "e2")
        self.assertFalse(any("later.py" in line for line in got), got)

    def test_boundary_and_listed_are_allowed(self):
        got = scan.problems("E2", SEEDS / "e2")
        self.assertFalse(any("boundary.py" in line or "listed.py" in line for line in got), got)

    def test_required_mention_wins_over_planned(self):
        registry = "- 埋め: `workflows/.shared/later.py`（予定）\n- 埋め: `workflows/.shared/later.py`\n"
        with tree({"docs/polyfills.md": registry}) as root:
            got = scan.problems("E2", root)
        self.assertTrue(any("docs/polyfills.md:2" in line and "later.py" in line for line in got), got)


if __name__ == "__main__":
    unittest.main()

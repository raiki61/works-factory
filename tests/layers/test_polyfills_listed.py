"""`workflows/.shared/` と `bin/_lib/` のファイルが、pack の口・入口の部品の外し・埋めの名簿の `- 埋め:` の行の頭の欄のどれかに当たる（`workflows/AGENTS.md` の E2 の機械の行）。

- pack の口: `ports.py`・`prompt.py`・`requestrows.py`。2 つ以上の block が使う断片と形（`prompts/`・`schemas/`）と `AGENTS.md` も口の側に数える。
- 入口の部品の外し: `bin/_lib/` の埋めでない物（起動の認証と隔離を元の works から持ってきた部品）は `tests/layers/scan.py` の `ALLOWED["E2"]` に 1 行ずつ訳つきで置く。
- 名簿 `docs/polyfills.md` の `- 埋め:` の行の頭の欄（`- 埋め:` の直後の、`、` 区切りのパスの並び）が名指す物だけを数え、行の説明の文にだけ名が出る部品は数えない。
- 木に在るかの照らしは頭の欄に限らず行の全部のパスに掛かり、名簿の `- 埋め:` の行が名指す `workflows/`・`bin/`・`lib/`・`tests/` の下のパスが木に無い行も赤。置き場のパスの直後に「（予定）」と書いた行は、木に無くてよい。
"""
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
        with tree({"bin/_lib/pack.py": "", "bin/_lib/no-post-bin/x": ""}) as root:
            got = scan.problems("E2", root)
        self.assertEqual(got, [])

    def test_planned_row_may_be_missing(self):
        got = scan.problems("E2", SEEDS / "e2")
        self.assertFalse(any("later.py" in line for line in got), got)

    def test_planned_row_followed_by_text_may_be_missing(self):
        with tree({"docs/polyfills.md": "- 埋め: `workflows/.shared/later.py`（予定）の部品\n"}) as root:
            got = scan.problems("E2", root)
        self.assertEqual(got, [])

    def test_pack_ports_and_listed_are_allowed(self):
        got = scan.problems("E2", SEEDS / "e2")
        self.assertFalse(any(name in line for line in got
                             for name in ("ports.py", "listed.py", "prompts/piece.md", "schemas/shape.schema.json")), got)

    def test_every_pack_port_is_allowed(self):
        names = ("ports.py", "prompt.py", "requestrows.py", "AGENTS.md", "prompts/a.md", "schemas/b.schema.json")
        with tree({f"workflows/.shared/{n}": "" for n in names}) as root:
            got = scan.problems("E2", root)
        self.assertEqual(got, [])

    def test_retired_boundary_is_not_a_port(self):
        """入れ替えで消した境の口 boundary.py は、もう pack の口に数えない"""
        with tree({"workflows/.shared/boundary.py": "", "workflows/.shared/sub/ports.py": ""}) as root:
            got = scan.problems("E2", root)
        self.assertEqual(got, ["workflows/.shared/boundary.py:1: 名簿にも pack の口にも当たらない",
                               "workflows/.shared/sub/ports.py:1: 名簿にも pack の口にも当たらない"])

    def test_required_mention_wins_over_planned(self):
        registry = "- 埋め: `workflows/.shared/later.py`（予定）\n- 埋め: `workflows/.shared/later.py`\n"
        with tree({"docs/polyfills.md": registry}) as root:
            got = scan.problems("E2", root)
        self.assertTrue(any("docs/polyfills.md:2" in line and "later.py" in line for line in got), got)

    def test_bin_lib_name_only_in_description_is_red(self):
        registry = "- 埋め: `bin/_lib/y.py`。説明の中の `bin/_lib/x.py`\n"
        with tree({"docs/polyfills.md": registry, "bin/_lib/x.py": "", "bin/_lib/y.py": ""}) as root:
            got = scan.problems("E2", root)
        self.assertEqual(got, ["bin/_lib/x.py:1: 名簿にも pack の口にも当たらない"])

    def test_shared_name_only_in_description_is_red(self):
        registry = "- 埋め: `workflows/.shared/y.py`。説明の中の `workflows/.shared/x.py`\n"
        files = {"docs/polyfills.md": registry, "workflows/.shared/x.py": "", "workflows/.shared/y.py": ""}
        with tree(files) as root:
            got = scan.problems("E2", root)
        self.assertEqual(got, ["workflows/.shared/x.py:1: 名簿にも pack の口にも当たらない"])

    def test_every_head_path_counts_and_description_does_not(self):
        registry = "- 埋め: `bin/_lib/a.py`、`bin/_lib/b.py`。説明の `bin/_lib/c.py`\n"
        files = {"docs/polyfills.md": registry, **{f"bin/_lib/{n}.py": "" for n in "abc"}}
        with tree(files) as root:
            got = scan.problems("E2", root)
        self.assertEqual(got, ["bin/_lib/c.py:1: 名簿にも pack の口にも当たらない"])

    def test_parenthesized_description_after_head_is_not_counted(self):
        """（予定）は欄を続け、ほかの `（` は欄を閉じる"""
        registry = "- 埋め: `bin/_lib/p.py`（予定）、`bin/_lib/y.py`（中身は `bin/_lib/x.py`）。\n"
        with tree({"docs/polyfills.md": registry, "bin/_lib/x.py": "", "bin/_lib/y.py": ""}) as root:
            got = scan.problems("E2", root)
        self.assertEqual(got, ["bin/_lib/x.py:1: 名簿にも pack の口にも当たらない"])


if __name__ == "__main__":
    unittest.main()

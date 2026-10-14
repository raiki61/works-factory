"""`workflows/` の YAML の AI ノード（`prompt:`・`command:`。輪の中も）が `retry` を持つか、真上に外す理由の行を持つ（workflows/AGENTS.md の E19 の機械の行）。"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"
BLOCK = "workflows/judge/works-factory-judge.yaml"
RETRY = "retry: {max_attempts: 2, on_error: all}"


class RoleRetryTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E19", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E19", SEEDS / "e19")
        self.assertEqual(len(got), 1, got)
        self.assertIn(f"{BLOCK}:3", got[0])

    def problems(self, nodes):
        with tree({BLOCK: "name: works-factory-judge\nnodes:\n" + nodes}) as root:
            return scan.problems("E19", root)

    def test_retry_or_reason_is_clean(self):
        nodes = (
            f"  - id: ask\n    prompt: hi\n    {RETRY}\n"
            f"  # retry なし: 2 回走ると外に 2 回書く\n  - id: post\n    command: post\n"
            "  - id: run\n    script: stub\n"
            f"  - id: g\n    loop_group:\n      nodes:\n        - id: again\n          prompt: hi\n          {RETRY}\n"
        )
        self.assertEqual(self.problems(nodes), [])

    def test_removing_one_retry_from_the_real_tree_is_red(self):
        path = ROOT / BLOCK
        text = path.read_text(encoding="utf-8")
        self.assertIn(RETRY, text)
        with tree({BLOCK: text.replace(RETRY, "", 1)}) as root:
            got = scan.problems("E19", root)
        self.assertEqual(len(got), 1, got)
        self.assertIn("retry も", got[0])

    def test_role_without_retry_is_red(self):
        got = self.problems("  - id: ask\n    command: ask\n")
        self.assertEqual(got, [f"{BLOCK}:3: 役 ask に retry も、真上の「{scan.NO_RETRY} <理由>」の行も無い"])

    def test_nested_role_without_retry_is_red(self):
        got = self.problems("  - id: g\n    loop_group:\n      nodes:\n        - id: again\n          prompt: hi\n")
        self.assertEqual(len(got), 1, got)
        self.assertIn(f"{BLOCK}:6: 役 again", got[0])

    def test_reason_line_without_reason_is_red(self):
        got = self.problems(f"  {scan.NO_RETRY}\n  - id: ask\n    prompt: hi\n")
        self.assertEqual(len(got), 1, got)
        self.assertIn("retry も", got[0])

    def test_reason_line_not_directly_above_is_red(self):
        got = self.problems(f"  {scan.NO_RETRY} 外に書く\n\n  - id: ask\n    prompt: hi\n")
        self.assertEqual(len(got), 1, got)

    def test_retry_with_reason_line_is_red(self):
        got = self.problems(f"  {scan.NO_RETRY} 外に書く\n  - id: ask\n    prompt: hi\n    {RETRY}\n")
        self.assertEqual(got, [f"{BLOCK}:4: 役 ask は retry を持つのに、外す理由の行が在る"])

    def test_retry_from_merge_key_counts(self):
        nodes = f"  - id: a\n    <<: &launch\n      prompt: hi\n      {RETRY}\n  - id: b\n    <<: *launch\n"
        self.assertEqual(self.problems(nodes), [])


if __name__ == "__main__":
    unittest.main()

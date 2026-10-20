"""graph と block の YAML の AI のノード（`prompt:`・`command:`。`loop_group` の本体の中も）が `retry` を形 `scan.ROLE_RETRY`（`{max_attempts: 2, on_error: all}`）で持つか、ノードの頭の行の真上に外す理由の行 `# retry なし: <理由>` を持つ（`workflows/AGENTS.md` の E19 の機械の行）。

- 両方在るのも赤。照らしは `tests/layers/scan.py` の `_role_retry`。
- `on_error: all` を書く訳（止めた Archon の既定は `on_error: transient` で、種類が `unknown` の失敗を出し直さない）と、`loop_group` のノードそのものに書けない訳は `docs/design/archon.md` の E19 の節。
"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"
BLOCK = "workflows/judge/works-factory-judge.yaml"
RETRY = "retry: {max_attempts: 2, on_error: all}"
REAL = "workflows/diagnose/works-factory-diagnose.yaml"   # AI の node を持つ本物の block（judge の graph は include だけで AI の node を持たない）


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
        path = ROOT / REAL
        text = path.read_text(encoding="utf-8")
        self.assertIn(RETRY, text)
        with tree({REAL: text.replace(RETRY, "", 1)}) as root:
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

    def test_retry_of_another_form_is_red(self):
        for retry in ("retry: {max_attempts: 2}", "retry: {max_attempts: 1, on_error: all}",
                      "retry: {max_attempts: 2, on_error: transient}", "retry: {max_attempts: '2', on_error: all}", "retry: ~"):
            with self.subTest(retry):
                got = self.problems(f"  - id: ask\n    prompt: hi\n    {retry}\n")
                self.assertEqual(got, [f"{BLOCK}:5: 役 ask の retry が {scan.ROLE_RETRY} でない"])

    def test_retry_from_merge_key_counts(self):
        nodes = f"  - id: a\n    <<: &launch\n      prompt: hi\n      {RETRY}\n  - id: b\n    <<: *launch\n"
        self.assertEqual(self.problems(nodes), [])


if __name__ == "__main__":
    unittest.main()

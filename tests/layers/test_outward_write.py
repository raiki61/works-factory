"""外へ書く（`gh`・`git push`・`git merge` を呼ぶ）節が、ブロックごとに 1 つ以下（workflows/AGENTS.md の E6 の機械の行）。

節の字は、直に書いた `script:`・`bash:` の中身と、名前の script（ブロックの `scripts/` のファイル）の中身。
書いた後に読み戻すかは人が見る。
"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"
BLOCK = "workflows/merge/works-factory-merge.yaml"


class OutwardWriteTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E6", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E6", SEEDS / "e6")
        self.assertEqual(len(got), 1, got)
        self.assertIn(BLOCK, got[0])

    def problems(self, files):
        with tree(files) as root:
            return scan.problems("E6", root)

    def test_one_writing_node_is_clean(self):
        yaml = (
            "name: works-factory-merge\nnodes:\n  - id: apply\n    script: apply\n    runtime: uv\n    timeout: 1728000000\n"
            "  - id: read\n    bash: git log -1\n    timeout: 1728000000\n"
        )
        files = {BLOCK: yaml, "workflows/merge/scripts/apply.py": 'run(["git", "push", "origin", "HEAD"])\n'}
        self.assertEqual(self.problems(files), [])

    def test_named_scripts_are_read(self):
        yaml = (
            "name: works-factory-merge\nnodes:\n  - id: a\n    script: a\n    runtime: uv\n    timeout: 1728000000\n"
            "  - id: b\n    script: b\n    runtime: uv\n    timeout: 1728000000\n"
        )
        files = {BLOCK: yaml, "workflows/merge/scripts/a.py": 'run(["gh", "pr", "create"])\n',
                 "workflows/merge/scripts/b.py": 'run(["git", "merge", "--ff-only", "x"])\n'}
        got = self.problems(files)
        self.assertEqual(len(got), 1, got)
        self.assertIn("a・b", got[0])

    def test_lib_write_call_counts_as_a_writing_node(self):
        """lib の書く口（deliver.submit）を呼ぶ節も外へ書く節に数える。同じブロックに別の書く節が在れば 2 つで赤"""
        yaml = (
            "name: works-factory-merge\nnodes:\n  - id: merge\n    script: merge\n    runtime: uv\n    timeout: 1728000000\n"
            "  - id: other\n    script: other\n    runtime: uv\n    timeout: 1728000000\n"
        )
        files = {BLOCK: yaml, "workflows/merge/scripts/merge.py": "delivered = deliver.submit(repo, base_rev, data, run_id, scratch)\n",
                 "workflows/merge/scripts/other.py": 'run(["gh", "pr", "create"])\n'}
        got = self.problems(files)
        self.assertEqual(len(got), 1, got)
        self.assertIn("merge・other", got[0])
        files["workflows/merge/scripts/other.py"] = "print('read only')\n"
        self.assertEqual(self.problems(files), [], "書く節が 1 つなら緑")

    def test_nodes_inside_a_loop_group_count(self):
        yaml = (
            "name: works-factory-merge\nnodes:\n  - id: g\n    loop_group:\n      nodes:\n"
            "        - id: a\n          bash: gh pr merge 1\n        - id: b\n          bash: git push\n"
        )
        self.assertEqual(len(self.problems({BLOCK: yaml})), 1)

    def test_words_that_only_contain_gh_are_clean(self):
        yaml = (
            "name: works-factory-merge\nnodes:\n  - id: a\n    bash: echo high ghost gh-pages\n    timeout: 1728000000\n"
            "  - id: b\n    bash: git log --merges\n    timeout: 1728000000\n"
        )
        self.assertEqual(self.problems({BLOCK: yaml}), [])


if __name__ == "__main__":
    unittest.main()

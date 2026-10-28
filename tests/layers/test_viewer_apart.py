"""見る道具（根のフォルダ viewer/）を、見る道具とその試験（tests/viewer/）と文書（docs/・どの階層の AGENTS.md・根の md）のほかから名指さない
（viewer/AGENTS.md の E25 の 1 の機械の行。持ち主の決め viewer-in-repo）。

- 照らす字は 2 つの形だけ: フォルダのパス `viewer/`（前が語の字・`-` でない所。`../viewer/`・`./viewer/`・`{ROOT}/viewer/` も当てる。
  見る道具の試験のフォルダ `tests/viewer/` は当てない）と、行の頭の `import viewer`・`from viewer`。
  語 viewer だけでは当てない（workflows/.shared/prompt.py の値の記録の名 VIEWER_VALUES = "viewer-values" が当たるため）。
- 照らさない形（人が見る）: パスを部品で組む形（`ROOT / "viewer"`）と、名を字で渡す読み込み（`importlib.import_module("viewer...")`）。
- 照らしから外すのは tests/layers/scan.py の ALLOWED["E25"] の行（この試験の小さな木の字）だけ。
"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]


class ViewerApartTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E25", ROOT), [])

    def test_naming_from_the_factory_is_red(self):
        for rel, text in (("bin/_lib/x.py", "from viewer.src import shape\n"), ("lib/y.py", "import viewer\n"),
                          ("workflows/a/scripts/z.py", 'PAGE = ROOT / "viewer/flowview.py"\n'),
                          ("tests/bin/test_w.py", "# viewer/ の入口を起こす\n"), ("pyproject.toml", 'x = "viewer/"\n'),
                          ("workflows/a/a.yaml", "bash: python3 ../viewer/flowview.py\n"), ("bin/_lib/v.py", 'X = "./viewer/flowview.py"\n'),
                          ("lib/z.py", 'X = f"{ROOT}/viewer/flowview.py"\n')):
            with self.subTest(rel=rel), tree({rel: text}) as root:
                got = scan.problems("E25", root)
                self.assertEqual(len(got), 1, got)
                self.assertTrue(got[0].startswith(f"{rel}:1: "), got)

    def test_homes_and_documents_are_clean(self):
        files = {"viewer/flowview.py": "from viewer.src import shape\n", "tests/viewer/test_a.py": "from viewer import flowview\n",
                 "docs/design/viewer.md": "`viewer/`\n", "bin/AGENTS.md": "`viewer/` が読む口\n", "MISSION.md": "`viewer/`\n",
                 "workflows/.shared/prompt.py": 'VIEWER_VALUES = "viewer-values"\n', "workflows/a/b.py": "# <node>-viewer-values-<n>.json\n",
                 ".github/workflows/tests.yml": "run: python3 -m unittest discover -s tests/viewer/\n"}
        with tree(files) as root:
            self.assertEqual(scan.problems("E25", root), [])


if __name__ == "__main__":
    unittest.main()

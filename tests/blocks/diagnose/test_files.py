"""place のファイルの名（src/files.py）が、lib が書く名と同じこと（docs/design/diagnose.md の 9.2 の test_place_names_match_lib）。
作業ツリーの写し）で、ここは消す時のために名を写して持つ。"""
import pathlib
import unittest

from tests.blocks.diagnose import support


class PlaceNamesCase(unittest.TestCase):
    def setUp(self):
        self.files = support.modules()["files"]

    def test_place_names_match_lib(self):
        import materialkit
        import outpurpose
        import querytest
        import rolekit
        f = self.files
        self.assertEqual(f.QUERY_EXAMPLES_FILE, querytest.EXAMPLES_FILE)
        self.assertEqual(f.OUT_OF_PURPOSE_FILE, outpurpose.FILE)
        self.assertEqual((f.VIEW_FILE, f.DIFF_FILE, f.CHANGED_FILE, f.TREE_FILE),
                         (materialkit.VIEW, materialkit.DIFF, materialkit.CHANGED, materialkit.TREE))
        self.assertEqual(rolekit.rejects_path(pathlib.Path(), f.DIAGNOSE_ROLE).name, "rejects-diagnose.json")
        self.assertIn("rejects-diagnose.md", f.OWN_FILES)
        self.assertIn("rejects-rejudge.json", f.OWN_FILES)


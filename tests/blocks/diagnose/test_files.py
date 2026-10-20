"""place のファイルの名（src/files.py）が、lib が書く名と同じこと（docs/design/diagnose.md の 9.2 の test_place_names_match_lib）。
作業ツリーの写し）で、ここは消す時のために名を写して持つ。"""
import pathlib
import unittest

from tests.bin import hermetic
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

    def test_own_files_are_named_not_patterns(self):
        for name in self.files.OWN_FILES:
            self.assertNotIn("*", name)
        self.assertEqual(len(self.files.OWN_FILES), len(set(self.files.OWN_FILES)))

    def test_reply_keys_cover_the_documented_roles(self):
        roles = {role for role, _ in self.files.REPLY_KEYS.values()}
        self.assertEqual(roles, {"local-review", "consistency-bypass", "external-standards", "procedure-trace",
                                 "test-double-fidelity", "main-path-observation", "provenance", "prior-decisions", "purpose-review"})

"""place のファイルの名（src/files.py）が、lib が書く名と同じこと（docs/design/diagnose.md の 9.2 の test_place_names_match_lib）。
名の元は lib/marks.py（控えの種）・lib/rolekit.py（拒否の控え）・lib/judgebeside.py（判定の隣のファイル）・lib/materialkit.py（対象差分と
作業ツリーの写し）で、ここは消す時のために名を写して持つ。"""
import pathlib
import unittest

from tests.bin import hermetic
from tests.blocks.diagnose import support


class PlaceNamesCase(unittest.TestCase):
    def setUp(self):
        self.files = support.modules()["files"]

    def test_place_names_match_lib(self):
        import judgebeside
        import marks
        import materialkit
        import outpurpose
        import querytest
        import rolekit
        f = self.files
        self.assertEqual(f.QUERY_EXAMPLES_FILE, marks.KINDS["query"].file)
        self.assertEqual(f.QUERY_EXAMPLES_FILE, querytest.EXAMPLES_FILE)
        self.assertEqual(f.OUT_OF_PURPOSE_FILE, marks.KINDS["purpose"].file)
        self.assertEqual(f.OUT_OF_PURPOSE_FILE, outpurpose.FILE)
        self.assertEqual(f.ANSWER_TIES_FILE, marks.KINDS["answers"].file)
        self.assertEqual(f.ANSWER_TIES_FILE, judgebeside.ANSWER_TIES_FILE)
        self.assertEqual(f.REJUDGE_EXIT_FILE, judgebeside.REJUDGE_EXIT_FILE)
        self.assertEqual(f.REJUDGE_DIFF_FILE, judgebeside.REJUDGE_DIFF_FILE)
        self.assertEqual(f.MATERIALS_FILE, judgebeside.MATERIALS_FILE)
        self.assertEqual((f.VIEW_FILE, f.DIFF_FILE, f.CHANGED_FILE, f.TREE_FILE),
                         (materialkit.VIEW, materialkit.DIFF, materialkit.CHANGED, materialkit.TREE))
        self.assertEqual(rolekit.rejects_path(pathlib.Path(), f.DIAGNOSE_ROLE).name, "rejects-diagnose.json")
        self.assertIn("rejects-diagnose.md", f.OWN_FILES)
        self.assertIn("rejects-rejudge.json", f.OWN_FILES)

    def test_count_files_match_the_old_acceptance(self):
        import judge_accept
        self.assertEqual((self.files.COUNT_CACHE_FILE, self.files.COUNT_BUDGET_FILE),
                         (judge_accept.COUNT_CACHE_FILE, judge_accept.COUNT_BUDGET_FILE))
        self.assertEqual(self.files.JUDGMENT_FILE, judge_accept.JUDGMENT_FILE)
        self.assertEqual(self.files.STRUCTURE_DROPPED_FILE, judge_accept.STRUCTURE_DROPPED_FILE)
        self.assertEqual(self.files.REJUDGE_NODE, judge_accept.REJUDGE_NODE)

    def test_tables_match_the_old_acceptance(self):
        """写した表が元の表と同じ語を持つ（元を消すまでの間、突き合わせる）"""
        import judge_accept as old
        judge, rejudge = support.modules()["judge"], support.modules()["rejudge"]
        self.assertEqual(judge.LABELS, old.LABELS)
        self.assertEqual(judge.REVIEWS, old.REVIEWS)
        self.assertEqual(judge.QUESTION_FIELDS, old.QUESTION_FIELDS)
        self.assertEqual(judge.UNIT_FIELDS, old.UNIT_FIELDS)
        self.assertEqual(judge.QUESTION_STATUS, old.QUESTION_STATUS)
        self.assertEqual(judge.NO_OPEN_ORIGIN, old.NO_OPEN_ORIGIN)
        self.assertEqual(judge.EMPTY, old.EMPTY)
        self.assertEqual(judge.ASK_KEYS, old.ASK_KEYS)
        self.assertEqual(judge.COUNT_BUDGET, old.COUNT_BUDGET)
        self.assertEqual({k: (v.domain, v.fields) for k, v in judge.QUESTION_KINDS.items()},
                         {k: (v.domain, v.fields) for k, v in old.QUESTION_KINDS.items()})
        self.assertEqual((rejudge.REJUDGE_VERDICTS, rejudge.REJUDGE_SETTLED, rejudge.REJUDGE_UNIT_FIELDS),
                         (old.REJUDGE_VERDICTS, old.REJUDGE_SETTLED, old.REJUDGE_UNIT_FIELDS))

    def test_stop_words_are_declared_with_the_old_meaning(self):
        import judge_accept as old
        self.assertEqual((self.files.JUDGE_STOP, self.files.MATERIAL_STOP, self.files.REQUEST_STOP),
                         (old.JUDGE_STOP, old.MATERIAL_STOP, old.REQUEST_STOP))

    def test_the_hypothesis_word_matches_the_report(self):
        import runreport
        self.assertEqual(self.files.HYPOTHESIS, runreport.HYPOTHESIS)

    def test_own_files_are_named_not_patterns(self):
        for name in self.files.OWN_FILES:
            self.assertNotIn("*", name)
        self.assertEqual(len(self.files.OWN_FILES), len(set(self.files.OWN_FILES)))

    def test_reply_keys_cover_the_documented_roles(self):
        roles = {role for role, _ in self.files.REPLY_KEYS.values()}
        self.assertEqual(roles, {"local-review", "consistency-bypass", "external-standards", "procedure-trace",
                                 "test-double-fidelity", "main-path-observation", "provenance", "prior-decisions", "purpose-review"})

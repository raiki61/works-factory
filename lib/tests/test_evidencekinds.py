"""証拠の種類の数え（lib/evidencekinds.py）と、パスの形から変更の種類を見分ける表（lib/impact.py の kind_of）の検査。修正の block の
rules.py から出した物（書き手の slots・振り分け・TDD の輪の周が共に使う）。置き場は使い捨てのフォルダ、差分は使い捨ての git。
"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from tests.bin.gitkit import git  # noqa: E402
import evidencekinds  # noqa: E402
import impact  # noqa: E402


class KindOfTest(unittest.TestCase):
    def test_paths_map_to_one_kind_by_their_shape(self):
        for path, kind in (("README.md", "docs"), ("docs/a.rst", "docs"), ("notes.txt", "docs"),
                           ("AGENTS.md", "prompts"), ("skills/x/SKILL.md", "prompts"), ("prompts/a.md", "prompts"),
                           ("a/commands/b.md", "prompts"), ("pack.yaml", "config"), ("a/b.json", "config"), ("Makefile", "config"),
                           (".github/workflows/ci.yml", "config"), ("src/a.py", "code"), ("x/y.go", "code"), ("run.sh", "code")):
            with self.subTest(path=path):
                self.assertEqual(impact.kind_of(path), kind)

    def test_a_path_with_no_known_shape_has_no_kind(self):
        for path in ("a.bin", "LICENSE", "x/y", "pic.png"):
            self.assertIsNone(impact.kind_of(path), path)

    def test_the_path_is_normalised_first(self):
        self.assertEqual(impact.kind_of("  ./src//a.py "), "code")

    def test_kinds_are_the_four_the_writer_rules_have_a_paragraph_for(self):
        self.assertEqual(evidencekinds.KINDS, ("docs", "prompts", "config", "code"))
        self.assertEqual(set(evidencekinds.WRITER_KINDS), set(evidencekinds.KINDS))


class SelectKindsTest(unittest.TestCase):
    def test_kinds_come_with_the_sources_and_paths_that_gave_them(self):
        got = evidencekinds.select_kinds({"判定": ["a.py"], "差分": ["README.md", "b.py"]})
        self.assertEqual(list(got), ["docs", "code"])
        self.assertEqual(got["code"], "判定 a.py; 差分 b.py")

    def test_more_than_five_paths_are_cut_with_a_count(self):
        got = evidencekinds.select_kinds({"差分": [f"f{i}.py" for i in range(7)]})
        self.assertTrue(got["code"].endswith("ほか 2 本"), got["code"])

    def test_nothing_recognised_selects_every_kind(self):
        got = evidencekinds.select_kinds({"判定": ["x.bin"], "差分": []})
        self.assertEqual(list(got), list(evidencekinds.KINDS))
        self.assertIn("パス 1 本", got["code"])


class UnitPathsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="works-evk-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def judgment(self, units):
        path = self.tmp / "judgment.json"
        path.write_text(json.dumps({"units": units}), encoding="utf-8")
        return str(path)

    def test_paths_of_the_open_units_come_from_the_query_and_the_key(self):
        units = [{"key": "a.py f: 壊れ", "class_query": {"how": {"paths": ["a.py", "b.py"]}}},
                 {"key": "other.py g", "class_query": {"how": {"paths": ["z.py"]}}}]
        got, why = evidencekinds.unit_paths(self.judgment(units), json.dumps(["a.py f: 壊れ"]))
        self.assertEqual((got, why), (["a.py", "b.py"], ""))

    def test_an_unreadable_judgment_is_named_not_raised(self):
        got, why = evidencekinds.unit_paths(str(self.tmp / "none.json"), "[]")
        self.assertEqual(got, [])
        self.assertIn("読めない", why)


class DiffTest(unittest.TestCase):
    def test_changed_paths_are_the_diff_and_the_untracked_without_ignored_ones(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="works-evk-git-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        git(tmp, "init", "-q")
        (tmp / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        (tmp / "a.py").write_text("x = 1\n", encoding="utf-8")
        git(tmp, "add", "-A")
        git(tmp, "commit", "-q", "-m", "seed")
        (tmp / "a.py").write_text("x = 2\n", encoding="utf-8")
        (tmp / "new.md").write_text("n\n", encoding="utf-8")
        (tmp / "ignored.txt").write_text("i\n", encoding="utf-8")
        self.assertEqual(sorted(evidencekinds.changed_paths(tmp)), ["a.py", "new.md"])

    def test_without_git_the_diff_is_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(evidencekinds.changed_paths(pathlib.Path(td) / "nope"), [])


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="works-evk-ledger-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.ledger = self.tmp / "x.delivered.json"

    def test_a_missing_or_broken_ledger_is_empty_and_the_first_round_is_1(self):
        self.assertEqual(evidencekinds.delivered(self.ledger), {})
        self.assertEqual(evidencekinds.iteration_next(self.ledger), 1)
        self.ledger.write_text("[1]", encoding="utf-8")
        self.assertEqual(evidencekinds.delivered(self.ledger), {})

    def test_remember_accumulates_the_rounds_and_keeps_the_latest_kinds(self):
        evidencekinds.remember(self.ledger, {"code", "docs"}, 1)
        self.assertEqual(evidencekinds.delivered(self.ledger), {"kinds": ["code", "docs"], "iterations": [1]})
        evidencekinds.remember(self.ledger, ["code"], 2)
        self.assertEqual(evidencekinds.delivered(self.ledger), {"kinds": ["code"], "iterations": [1, 2]})
        self.assertEqual(evidencekinds.iteration_next(self.ledger), 3)

    def test_kinds_never_shrink_inside_a_loop_and_start_kinds_are_added(self):
        judgment = self.tmp / "judgment.json"
        judgment.write_text(json.dumps({"units": [{"key": "a.py f", "class_query": {"how": {"paths": ["a.py"]}}}]}), encoding="utf-8")
        values = {"judgment_file": str(judgment), "open_units": json.dumps(["a.py f"])}
        first = evidencekinds.kinds_for(self.ledger, values, None)
        self.assertEqual(list(first), ["code"])
        evidencekinds.remember(self.ledger, ["docs"], 1)
        again = evidencekinds.kinds_for(self.ledger, values, None, start=["config"])
        self.assertEqual(set(again), {"code", "docs", "config"})
        self.assertEqual(again["docs"], "このループで前に渡した")

    def test_unreadable_judgment_with_no_diff_selects_every_kind_with_the_reason(self):
        got = evidencekinds.kinds_now({"judgment_file": str(self.tmp / "none.json"), "open_units": "[]"}, None)
        self.assertEqual(list(got), list(evidencekinds.KINDS))
        self.assertIn("読めない", got["code"])


class KindsWhenTest(unittest.TestCase):
    def test_paragraphs_follow_the_kinds_and_the_role_names_where_the_answer_goes(self):
        got = evidencekinds.kinds_when({"code": "x", "docs": "y"}, "tdd")
        self.assertEqual((got["code"], got["docs"], got["config"], got["prompts_kind"]), (True, True, False, False))
        self.assertIs(got["evidence"], True)
        self.assertEqual((got["where_writer"], got["where_tdd"], got["where_rework"]), (False, True, False))

    def test_a_continuing_round_has_no_kinds_so_the_evidence_heading_drops(self):
        got = evidencekinds.kinds_when({}, "writer")
        self.assertIs(got["evidence"], False)
        self.assertEqual({k: got[k] for k in ("docs", "prompts_kind", "config", "code")}, dict.fromkeys(("docs", "prompts_kind", "config", "code"), False))
        self.assertIs(got["where_writer"], True)


if __name__ == "__main__":
    unittest.main()

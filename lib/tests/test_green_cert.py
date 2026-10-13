"""緑の認証の行（lib/green_cert.py）の検査。対象のリポジトリは tests/e2e/target-seed/ の写し（committed_copy）。

- 指紋: 同じ木で 2 度同じ。追跡のファイルの書き換え・未追跡のファイルの追加・HEAD の移動で変わる。.gitignore に当たる
  ファイルでは変わらない。git の木でなければ ValueError
- diff_bytes: 未追跡のファイルが入り、.gitignore に当たるファイルは入らず、本物の index を動かさない。rev の側と比べ、引けない rev は ValueError
- matches: 今の指紋と同じ時だけ真。None・形の違いは偽
- classify: 6 つの道と、その間の順
- certify: base と final の順。final は before と違う指紋（after・now のどちらでも）を認証しない
"""
import hashlib
import os
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
SEED = LIB.parent / "tests" / "e2e" / "target-seed"
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import gatemarks  # noqa: E402
import green_cert  # noqa: E402
from tests.bin.gitkit import committed_copy, git  # noqa: E402


class RepoCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name)
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, SEED)


class FingerprintCase(RepoCase):
    def test_same_tree_same_fingerprint(self):
        first = green_cert.fingerprint(self.repo)
        self.assertEqual(set(first), {"head", "diff_hash"})
        self.assertEqual(first["head"], git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(first["diff_hash"], hashlib.sha256(b"").hexdigest(), "差分が無ければ空のバイトの sha256")
        self.assertEqual(green_cert.fingerprint(self.repo), first)

    def test_tracked_edit_changes_it(self):
        before = green_cert.fingerprint(self.repo)
        (self.repo / "stats.py").write_text("x = 1\n", encoding="utf-8")
        after = green_cert.fingerprint(self.repo)
        self.assertEqual(after["head"], before["head"])
        self.assertNotEqual(after["diff_hash"], before["diff_hash"])

    def test_untracked_file_changes_it(self):
        before = green_cert.fingerprint(self.repo)
        (self.repo / "new_test.py").write_text("x = 1\n", encoding="utf-8")
        self.assertNotEqual(green_cert.fingerprint(self.repo), before)

    def test_commit_moves_head(self):
        (self.repo / "stats.py").write_text("x = 1\n", encoding="utf-8")
        before = green_cert.fingerprint(self.repo)
        git(self.repo, "commit", "-qam", "edit")
        after = green_cert.fingerprint(self.repo)
        self.assertNotEqual(after["head"], before["head"])

    def test_ignored_file_does_not_change_it(self):
        before = green_cert.fingerprint(self.repo)
        (self.repo / "__pycache__").mkdir()
        (self.repo / "__pycache__" / "stats.cpython.pyc").write_bytes(b"\0cache")
        (self.repo / "x.pyc").write_bytes(b"\0")
        self.assertEqual(green_cert.fingerprint(self.repo), before)

    def test_not_a_git_tree_is_value_error(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        with self.assertRaises(ValueError):
            green_cert.fingerprint(plain)


class DiffBytesCase(RepoCase):
    def test_untracked_in_ignored_out_index_unmoved(self):
        index = pathlib.Path(git(self.repo, "rev-parse", "--path-format=absolute", "--git-path", "index"))
        stat = (index.read_bytes(), os.stat(index).st_mtime_ns)
        (self.repo / "added.py").write_text("ADDED = 1\n", encoding="utf-8")
        (self.repo / "y.pyc").write_bytes(b"\0")
        out = green_cert.diff_bytes(self.repo, "HEAD")
        self.assertIsInstance(out, bytes)
        self.assertIn(b"added.py", out)
        self.assertIn(b"ADDED = 1", out)
        self.assertNotIn(b"y.pyc", out)
        self.assertEqual((index.read_bytes(), os.stat(index).st_mtime_ns), stat, "本物の index が動いた")
        self.assertEqual(git(self.repo, "status", "--porcelain"), "?? added.py")

    def test_rev_is_the_side_compared(self):
        base = git(self.repo, "rev-parse", "HEAD")
        (self.repo / "stats.py").write_text("COMMITTED = 1\n", encoding="utf-8")
        git(self.repo, "commit", "-qam", "edit")
        self.assertIn(b"COMMITTED = 1", green_cert.diff_bytes(self.repo, base))
        self.assertNotIn(b"COMMITTED = 1", green_cert.diff_bytes(self.repo, "HEAD"))
        with self.assertRaises(ValueError):
            green_cert.diff_bytes(self.repo, "no-such-rev")

    def test_diff_bytes_skips_given_prefixes(self):
        (self.repo / "stats.py").write_text("x = 3\n", encoding="utf-8")
        (self.repo / "run" / "deep").mkdir(parents=True)
        (self.repo / "run" / "deep" / "copy.yaml").write_text("RUNTIME = 1\n", encoding="utf-8")
        whole = green_cert.diff_bytes(self.repo, "HEAD")
        self.assertIn(b"RUNTIME = 1", whole)
        skipped = green_cert.diff_bytes(self.repo, "HEAD", skip=("run/",))
        self.assertNotIn(b"run/deep/copy.yaml", skipped)
        self.assertIn(b"x = 3", skipped)
        self.assertEqual(green_cert.diff_bytes(self.repo, "HEAD", skip=()), whole)

    def test_fingerprint_hash_is_of_diff_bytes(self):
        (self.repo / "stats.py").write_text("x = 2\n", encoding="utf-8")
        self.assertEqual(green_cert.fingerprint(self.repo)["diff_hash"],
                         hashlib.sha256(green_cert.diff_bytes(self.repo, "HEAD")).hexdigest())


class MatchesCase(RepoCase):
    def test_matches_only_the_current_fingerprint(self):
        now = green_cert.fingerprint(self.repo)
        self.assertTrue(green_cert.matches(now, self.repo))
        self.assertTrue(green_cert.matches(dict(now), self.repo))
        (self.repo / "stats.py").write_text("x = 3\n", encoding="utf-8")
        self.assertFalse(green_cert.matches(now, self.repo))

    def test_none_and_wrong_shape_are_false(self):
        now = green_cert.fingerprint(self.repo)
        for bad in (None, [], "x", {}, {"head": now["head"]}, {"diff_hash": now["diff_hash"]},
                    {"head": 1, "diff_hash": now["diff_hash"]}):
            with self.subTest(bad=bad):
                self.assertFalse(green_cert.matches(bad, self.repo))

    def test_git_error_is_false(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        self.assertFalse(green_cert.matches({"head": "h", "diff_hash": "d"}, plain))


def case(name, outcome):
    return {"classname": "test_stats.TestStats", "name": name, "outcome": outcome}


def classify(status="found", runs=(), cases=None, baseline=None, junit_steps=(), junit_unran=()):
    return green_cert.classify(material={"status": status}, runs=list(runs), cases=cases or [], baseline_cases=baseline,
                               junit_steps=list(junit_steps), junit_unran=list(junit_unran))


RED_UNIT = {"name": "unit", "exit": 1}
BROKEN = {"name": "lint", "exit": None}


class ClassifyCase(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(classify("clean", [{"name": "unit", "exit": 0}]), ("", ""))

    def test_environment_only_broken_steps(self):
        cause, summary = classify("found", [BROKEN, {"name": "unit", "exit": 0}])
        self.assertEqual(cause, "environment")
        self.assertIn("lint", summary)

    def test_environment_wins_over_not_run(self):
        self.assertEqual(classify("not_run", [BROKEN])[0], "environment")

    def test_carried_over_is_incomplete(self):
        self.assertEqual(classify("carried_over", [RED_UNIT])[0], "incomplete")

    def test_every_material_word_is_decided(self):
        """素材の語は全部、測った結果（MEASURED）か未了（NOT_DONE）のどちらかに決めて在る"""
        for word in gatemarks.MATERIAL_WORDS:
            with self.subTest(word):
                self.assertIn(word, (*green_cert.MEASURED, *green_cert.NOT_DONE))

    def test_incomplete(self):
        for status in ("not_run", "awaiting_human", "not_applicable"):
            with self.subTest(status):
                self.assertEqual(classify(status, [RED_UNIT])[0], "incomplete")
        cause, summary = classify("found", [RED_UNIT], junit_steps=["unit"], junit_unran=["unit"])
        self.assertEqual(cause, "incomplete")
        self.assertIn("unit", summary)

    def test_incomplete_comes_before_the_baseline(self):
        for status in ("found", "not_run"):
            with self.subTest(status):
                unran = ["unit"] if status == "found" else []
                self.assertEqual(classify(status, [RED_UNIT], [case("t", "failure")], [case("t", "passed")], ["unit"], unran)[0],
                                 "incomplete")

    def test_ran_red_wins_over_an_unran_step(self):
        """#404: 走った段の赤は、ほかの段が走らなかったことに隠されず本当の原因で分かれ、走らなかった段は要約に添える
        （declared_checks.checks_reply の #370 と同じ決め）"""
        e2e = {"name": "e2e", "exit": 1}
        cause, summary = classify("found", [RED_UNIT, e2e], [case("t", "failure")], [case("t", "passed")], ["unit", "e2e"], ["e2e"])
        self.assertEqual(cause, "introduced")
        self.assertIn("e2e", summary)
        cause, _ = classify("found", [RED_UNIT, e2e], [case("t", "failure")], [case("t", "failure")], ["unit", "e2e"], ["e2e"])
        self.assertEqual(cause, "", "走らなかった赤の段が在れば、受け継いだ赤とは言えない")

    def test_broken_mixed_with_red_is_not_environment(self):
        self.assertNotEqual(classify("found", [BROKEN, RED_UNIT])[0], "environment")

    def test_introduced(self):
        cause, summary = classify("found", [RED_UNIT], [case("test_mean_of_three", "failure")],
                                  [case("test_mean_of_three", "passed")], ["unit"])
        self.assertEqual(cause, "introduced")
        self.assertIn("test_stats.TestStats::test_mean_of_three", summary)

    def test_case_absent_from_baseline_is_introduced(self):
        self.assertEqual(classify("found", [RED_UNIT], [case("test_new", "error")], [], ["unit"])[0], "introduced")

    def test_inherited(self):
        cause, summary = classify("found", [RED_UNIT], [case("test_mean_of_three", "failure"), case("test_clamp_within_range", "passed")],
                                  [case("test_mean_of_three", "failure")], ["unit"])
        self.assertEqual(cause, "inherited")
        self.assertIn("test_stats.TestStats::test_mean_of_three", summary)

    def test_inherited_with_broken_step_outside_junit(self):
        self.assertEqual(classify("found", [RED_UNIT, BROKEN], [case("t", "failure")], [case("t", "failure")], ["unit"])[0],
                         "inherited")

    def test_introduced_and_inherited_mixed_is_introduced(self):
        cases = [case("old", "failure"), case("new", "failure")]
        self.assertEqual(classify("found", [RED_UNIT], cases, [case("old", "failure"), case("new", "passed")], ["unit"])[0],
                         "introduced")

    def test_no_baseline_is_causeless(self):
        cause, summary = classify("found", [RED_UNIT], [case("t", "failure")], None, ["unit"])
        self.assertEqual(cause, "")
        self.assertIn(gatemarks.BASELINE_UNVERIFIED, summary)

    def test_red_step_without_junit_is_not_inherited(self):
        cause, summary = classify("found", [RED_UNIT, {"name": "shell", "exit": 2}], [case("t", "failure")],
                                  [case("t", "failure")], ["unit"])
        self.assertEqual(cause, "")
        self.assertIn(gatemarks.BASELINE_UNVERIFIED, summary)

    def test_summary_lists_ten_keys_and_counts_the_rest(self):
        """赤の原因の要約は落ちた試験の鍵を 10 件まで並べ、超えた分は「ほか N 件」と数える"""
        failed = [case(f"t{i:02d}", "failure") for i in range(12)]
        cause, summary = classify("found", [RED_UNIT], failed, [], ["unit"])
        self.assertEqual(cause, "introduced")
        for i in range(10):
            self.assertIn(f"::t{i:02d}", summary)
        self.assertNotIn("::t10", summary)
        self.assertIn("ほか 2 件", summary)

    def test_red_without_failed_cases_is_causeless(self):
        self.assertEqual(classify("found", [RED_UNIT], [case("t", "passed")], [case("t", "passed")], ["unit"])[0], "")


FP = {"head": "h1", "diff_hash": "d1"}


class CertifyCase(unittest.TestCase):
    def final(self, **kw):
        args = {"mode": "final", "material_status": "found", "green": True, "before": FP, "after": dict(FP), "now": dict(FP)}
        return green_cert.certify(**{**args, **kw})

    def test_final_green_and_same_fingerprints(self):
        self.assertEqual(self.final(), (True, ""))

    def test_fingerprint_mismatch_comes_first(self):
        ok, reason = self.final(green=False, now={"head": "h2", "diff_hash": "d1"})
        self.assertFalse(ok)
        self.assertIn("now", reason)
        self.assertNotEqual(reason, "緑でない")
        ok, reason = self.final(before=None)
        self.assertFalse(ok)
        self.assertIn("before", reason)

    def test_after_differing_alone_is_refused(self):
        ok, reason = self.final(after={"head": "h1", "diff_hash": "d2"})
        self.assertFalse(ok)
        self.assertIn("after", reason)

    def test_final_red_is_never_certified(self):
        self.assertEqual(self.final(green=False), (False, "緑でない"), "inherited・environment の赤も認証しない")

    def test_truthy_non_bool_green_is_not_certified(self):
        """green は bool の True だけ。JSON から来た文字列 "false"・"true" や 1 は緑と読まない"""
        for green in ("false", "true", 1):
            with self.subTest(green=green):
                self.assertEqual(self.final(green=green), (False, "緑でない"))

    def test_final_self_reported_green_is_not_certified(self):
        """任せ先の役が書いた緑は認証しない（元 review-loop.py の _ci_by_engine）。base の控えは変えない"""
        self.assertEqual(self.final(self_reported=True), (False, green_cert.SELF_REPORTED))
        self.assertEqual(green_cert.certify(mode="base", material_status="clean", green=True, before=None, after=None, now=None,
                                            self_reported=True), (True, ""))

    def test_base(self):
        for status, want in (("clean", True), ("found", True), ("not_applicable", True),
                             ("not_run", False), ("awaiting_human", False), ("carried_over", False), (None, False)):
            with self.subTest(status):
                ok, reason = green_cert.certify(mode="base", material_status=status, green=False, before=None, after=None, now=None)
                self.assertEqual(ok, want)
                self.assertEqual(bool(reason), not want)


if __name__ == "__main__":
    unittest.main()

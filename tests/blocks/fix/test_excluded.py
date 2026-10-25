"""port excluded（並行 PR の確かめが外した hunk）と修正の受け付けの関門（docs/design/fix.md の 1.2・8.1。line の設計書の 8.2 の決め）:
修正の段の始めの木からの変更が外した hunk の行に触れた返答は、hunk を名指して拒む。触れなければ、この確かめでは拒まない"""
import hashlib
import json
import pathlib
import subprocess
import unittest

from tests.bin import hermetic
from tests.bin.gitkit import git
from tests.blocks import kit

RUNNER = pathlib.Path(__file__).resolve().parents[3] / "workflows" / "fix" / "fixtures" / "tdd-runner.py"

KEY = "stats.py:2 mean"
JUDGMENT = json.dumps({"units": [{"key": KEY, "label": "block", "reason": "空の並びで 0 除算する"}], "questions": []})
GROUP = json.dumps({"group_id": "g1", "unit_ids": [KEY], "items": []})
SOURCE = "def mean(xs):\n    return sum(xs) / len(xs)\n\n\ndef total(xs):\n    return sum(xs)\n"
EXCLUDED = json.dumps({"node": "pr-check", "head": "", "excluded": [
    {"pr": 7, "file": "stats.py", "start": 5, "end": 6, "why": "PR 7 が同じ total を書き換える"}]})


def anchored(rows, source=SOURCE):
    """並行 PR の確かめが付ける錨（行の中身 text と sha256）を、行 start〜end の source の中身から足す"""
    out = []
    for r in rows:
        raw = b"".join(source.encode("utf-8").splitlines(keepends=True)[r["start"] - 1:r["end"]])
        out.append({**r, "text": raw.decode("utf-8"), "sha256": hashlib.sha256(raw).hexdigest()})
    return out


def reply_for(files):
    return {"changes": [{"unit_key": KEY, "files": files, "what": "空の並びを先に返す",
                         "closure": {"mechanism": "0 除算", "fix_mechanism": "空を先に返す", "verified_how": "走らせた",
                                     "sites": [{"site": "mean", "red_seen": True, "path": "stats.py"}]},
                         "root_or_symptom": {"kind": "root", "why": "根を塞いだ"}, "bypass_tried": "空の並びを渡した",
                         "breaks": {"how": "grep mean", "result": "呼び元は動く"},
                         "precedent": {"verdict": "does_not_apply", "reason": "当たらない", "problem": "0 除算の守り",
                                       "source": "Python の文書"}}],
            "not_done": [], "fix_closure": {"status": "clean", "checked": "赤を見た"}, "mechanism_changed": False,
            "premise_drift": False, "gates_changed": False, "seams_changed": False, "security_surface_changed": False,
            "path_changed": False, "interactions": [], "wrote_refs": [], "plan_faces": []}


class ExcludedCase(unittest.TestCase):
    def started(self, excluded=EXCLUDED, source=SOURCE) -> kit.Run:
        run = kit.Run(self, "fix")
        (run.repo / "stats.py").write_text(source, encoding="utf-8")
        git(run.repo, "add", ".")
        git(run.repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "seed")
        self.assertTrue(run.script("intake", mode="group", group=GROUP, judgment=JUDGMENT, excluded=excluded, tdd_suite=str(RUNNER))["ok"])
        run.script("group_start")
        self.assertTrue(run.script("fix_prep")["go"])
        return run

    def edit(self, run, old, new):
        path = run.repo / "stats.py"
        path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

    def test_port_lands_in_values(self):
        run = self.started()
        doc = json.loads((run.artifacts / "values.json").read_text(encoding="utf-8"))
        self.assertEqual([(r["pr"], r["file"], r["start"], r["end"]) for r in doc["excluded"]], [(7, "stats.py", 5, 6)])

    def test_touching_an_excluded_hunk_is_rejected_naming_it(self):
        run = self.started()
        self.edit(run, "    return sum(xs)\n", "    return sum(xs) + 0\n")
        out = run.script("fix_accept", reply_variant=json.dumps(reply_for(["stats.py"])), consulted="false")
        self.assertFalse(out["ok"], out)
        self.assertIn("並行 PR #7 に回した hunk stats.py:5-6（PR 7 が同じ total を書き換える）を変えた", out["reason"])

    def test_change_outside_the_hunk_passes_this_check(self):
        run = self.started()
        self.edit(run, "    return sum(xs) / len(xs)\n", "    return sum(xs) / len(xs) if xs else 0\n")
        out = run.script("fix_accept", reply_variant=json.dumps(reply_for(["stats.py"])), consulted="false")
        self.assertNotIn("並行 PR", out["reason"], out)

    def test_a_later_stage_finds_the_hunk_by_its_anchor_not_by_the_recorded_lines(self):
        """2 回目の修正の段は、1 回目の段が上を直した後の木から始まるので、記録した行はずれている。錨で引き直し、ずれた先の hunk を
        変えれば拒み、記録した行に今在る別の所を変えても拒まない"""
        shifted = "import math\n\n" + SOURCE
        row = anchored([json.loads(EXCLUDED)["excluded"][0]])
        later = json.dumps({"node": "pr-check", "head": "", "excluded": row})
        run = self.started(later, shifted)
        self.edit(run, "    return sum(xs)\n", "    return sum(xs) + 0\n")
        out = run.script("fix_accept", reply_variant=json.dumps(reply_for(["stats.py"])), consulted="false")
        self.assertFalse(out["ok"], out)
        self.assertIn("並行 PR #7 に回した hunk stats.py:5-6", out["reason"])
        self.assertIn("変えた行 8-8", out["reason"])
        other = self.started(later, shifted)
        self.edit(other, "import math\n\n", "import math\nimport os\n\n")
        out = other.script("fix_accept", reply_variant=json.dumps(reply_for(["stats.py"])), consulted="false")
        self.assertNotIn("並行 PR", out["reason"], out)

    def test_ruled_accept_checks_the_hunk_too(self):
        """裁定の後の修正の受け付け（fix_ruled_accept）も同じ関門を通る"""
        import conflict
        run = self.started()
        conflict.park(run.artifacts, [{"unit_key": KEY, "between": ["stats.py:5", "stats.py:2"],
                                       "why_both_cannot_hold": "どちらも成り立たない", "which_is_right": "request",
                                       "kind": "unnamed_test_broke"}],
                      source=conflict.FIX_SOURCE, ruling={"decision": "fix_code_as", "text": "total も直せ", "limits": []})
        self.assertTrue(run.script("fix_ruled_prep")["go"])
        self.edit(run, "    return sum(xs)\n", "    return sum(xs) + 0\n")
        out = run.script("fix_ruled_accept", reply_variant=json.dumps(reply_for(["stats.py"])), consulted="false", iteration="1")
        self.assertFalse(out["ok"], out)
        self.assertIn("並行 PR #7 に回した hunk stats.py:5-6", out["reason"])

    def test_bare_rows_and_null_are_read(self):
        intake = kit.load("fix", "intake")
        rows = [{"pr": 1, "file": "a.py", "start": 1, "end": 2, "why": "w"}]
        self.assertEqual(intake.excluded_rows(rows), rows)
        self.assertEqual(intake.excluded_rows({"excluded": rows}), rows)
        self.assertEqual(intake.excluded_rows(None), [])

    def test_a_broken_row_is_refused_not_dropped(self):
        """形の崩れた行・start が end より大きい行は、黙って捨てずに入口で拒む"""
        for bad in ('[{"pr": 1, "file": "a.py", "start": 1}]', '[{"pr": 1, "file": "a.py", "start": "1", "end": 2}]',
                    '[{"pr": 1, "file": "a.py", "start": 4, "end": 2}]', '[{"pr": 1, "start": 1, "end": 2}]'):
            with self.subTest(bad=bad):
                run = kit.Run(self, "fix")
                out = run.script("intake", mode="group", group=GROUP, judgment=JUDGMENT, excluded=bad)
                self.assertFalse(out["ok"], out)
                self.assertIn("excluded", out["reason"])


HUNK = {"pr": 7, "file": "stats.py", "start": 5, "end": 6, "why": "PR 7 が同じ total を書き換える"}


class CheckExcludedCase(unittest.TestCase):
    """関門の本体 board.check_excluded を、一時のリポジトリの始めの木から今の作業ツリーへの変更で照らす（受け付けを通さない）"""

    def setUp(self):
        self.board = kit.load("fix", "board")
        self.runvals = kit.load("fix", "runvals")
        self.tmp = hermetic.tmpdir(self, prefix="works-fix-excl-")
        self.repo, self.place = self.tmp / "repo", self.tmp / "place"
        self.repo.mkdir()
        self.place.mkdir()
        git(self.repo, "init", "-q")
        self.put(SOURCE)
        git(self.repo, "add", ".")
        git(self.repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "seed")
        self.tree = git(self.repo, "rev-parse", "HEAD^{tree}").strip()

    def put(self, text, name="stats.py"):
        (self.repo / name).write_text(text, encoding="utf-8")

    def check(self, rows):
        self.runvals.write(self.place, {"excluded": rows})
        return self.board.check_excluded(self.place, self.repo, self.tree)

    def touched(self, rows):
        return [line for line in self.check(rows) if "を変えた" in line]

    def test_pure_insertion_next_to_the_hunk_counts_but_one_further_away_does_not(self):
        """足しただけの所は足した位置の前後の行に数える: hunk の直前（4 行目の後）と直後（6 行目の後）は触れた、離れた所は触れない"""
        lines = SOURCE.splitlines(keepends=True)
        for after, hit in ((4, True), (6, True), (2, False), (3, False)):
            with self.subTest(after=after):
                self.put("".join(lines[:after]) + "# 足した行\n" + "".join(lines[after:]))
                self.assertEqual(bool(self.touched([HUNK])), hit)

    def test_deleting_the_lines_or_the_file_or_renaming_it_counts(self):
        self.put(SOURCE.replace("    return sum(xs)\n", ""))
        self.assertEqual(len(self.touched([HUNK])), 1)
        self.put(SOURCE)
        (self.repo / "stats.py").unlink()
        self.assertEqual(len(self.touched([HUNK])), 1)
        self.put(SOURCE, "renamed.py")
        self.assertEqual(len(self.touched([HUNK])), 1)

    def test_only_the_touched_hunk_of_several_is_named(self):
        other = {"pr": 9, "file": "stats.py", "start": 1, "end": 2, "why": "別の PR"}
        self.put(SOURCE.replace("    return sum(xs)\n", "    return sum(xs) + 0\n"))
        got = self.touched([other, HUNK])
        self.assertEqual(len(got), 1, got)
        self.assertIn("#7", got[0])
        self.assertNotIn("#9", got[0])

    def test_message_without_a_pr_or_a_reason_has_no_empty_marks(self):
        self.put(SOURCE.replace("    return sum(xs)\n", "    return sum(xs) + 0\n"))
        (line,) = self.touched([{"file": "stats.py", "start": 5, "end": 6}])
        self.assertNotIn("None", line)
        self.assertNotIn("（）", line)

    def test_a_file_name_is_read_literally(self):
        """パス指定は文字どおりに読む（glob の * を含む名でも、ほかのファイルへ広がらない）"""
        self.put("a\nb\n", "w*.py")
        self.put("c\n", "wide.py")
        git(self.repo, "add", ".")
        git(self.repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "two")
        self.tree = git(self.repo, "rev-parse", "HEAD^{tree}").strip()
        self.put("c\nd\n", "wide.py")
        self.assertEqual(self.touched([{"pr": 1, "file": "w*.py", "start": 1, "end": 2, "why": "x"}]), [])

    def test_a_check_that_cannot_run_says_so_instead_of_passing(self):
        """始めの木が無い・木にファイルが無い・git が読めない時は、通さずに照らせない訳を 1 行で返す"""
        self.runvals.write(self.place, {"excluded": [HUNK]})
        self.assertIn("始めの木が無い", self.board.check_excluded(self.place, self.repo, "")[0])
        got = self.check([{**HUNK, "file": "missing.py"}])
        self.assertEqual(len(got), 1, got)
        self.assertIn("照らせない", got[0])
        self.assertIn("missing.py", got[0])

    def test_rows_are_found_by_their_anchor_after_the_lines_moved(self):
        """前の段の修正で行がずれた始めの木でも、錨（text・sha256）で引き直す。ずれた先の hunk を変えれば触れた、記録した行に今在る
        別の所を変えても触れていない"""
        shifted = "import math\n\n" + SOURCE   # total は 5-6 行目から 7-8 行目に移った
        self.put(shifted)
        git(self.repo, "add", ".")
        git(self.repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "stage 1")
        self.tree = git(self.repo, "rev-parse", "HEAD^{tree}").strip()
        row = anchored([HUNK])[0]
        self.put(shifted.replace("    return sum(xs)\n", "    return sum(xs) + 0\n"))
        self.assertEqual(len(self.touched([row])), 1)
        self.put(shifted.replace("import math\n\n", "import math\n# 足した\n\n", 1).replace("def mean", "def mean2", 1))
        self.assertEqual(self.touched([row]), [])
        # 錨が無い行は記録した行のまま（ずれたあとでは別の所を指す）
        self.put(shifted.replace("    return sum(xs)\n", "    return sum(xs) + 0\n"))
        self.assertEqual(self.touched([HUNK]), [])

    def test_the_nearest_copy_wins_when_the_anchor_text_appears_twice(self):
        twice = SOURCE + "\n\n" + SOURCE.split("\n\n\n", 1)[1]   # total の定義が 2 つ（5-6 行目と 11-12 行目）
        self.put(twice)
        git(self.repo, "add", ".")
        git(self.repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "dup")
        self.tree = git(self.repo, "rev-parse", "HEAD^{tree}").strip()
        row = anchored([HUNK])[0]
        lines = twice.splitlines(keepends=True)
        self.put("".join(lines[:10]) + "    return sum(xs) + 0\n" + "".join(lines[11:]))
        self.assertEqual(self.touched([row]), [], "遠い方の写しを変えても、記録した行に近い方は触れていない")


if __name__ == "__main__":
    unittest.main()

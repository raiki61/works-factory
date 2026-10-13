"""組の合わせの直し（lib/clash.py）と、その申し出・裁定の語（conflict.JOIN_SOURCE・conflict.REJUDGE。持ち主の決め clash-goes-to-ruling）。

- 合わせの申し出は組の単位ごとに 1 件で、kind・which_is_right は機械が埋める決まった値。控えの差分を置いた行の直しの在りかは控え
- 裁定 rejudge は直す裁定でない（単位を直す義務から外す）が人には回さず、裁定の文は修正の出力の異議になる。裁定役の返答の照らしは
  rejudge を合わせの申し出だけに許し、範囲を持たせず、同じ組の行の裁定を揃えさせる
- 申し出の名指しは差分のファイルごとの最初の塊の新しい側の行。当て直しが当たらない組は作業ツリーを変えない
筋書き（join から裁定の後の合わせのループまで script を順に起こす）は tests/workflows/test_fix.py の ClashScenarioCase。
"""
import pathlib
import shutil
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import clash  # noqa: E402
import conflict  # noqa: E402
import fixboard  # noqa: E402
import ruling  # noqa: E402
import tddloop  # noqa: E402

WHY = "組 g2 の直しを親の作業ツリーで前の組と合わせると試験が赤"


class Place(unittest.TestCase):
    def setUp(self):
        self.place = pathlib.Path(tempfile.mkdtemp(prefix="works-clash-"))
        self.addCleanup(shutil.rmtree, self.place, True)

    def parked(self, units=("B", "C")) -> list:
        return conflict.park(self.place, conflict.clash_claims(list(units), ["e.py:1"], WHY), source=conflict.JOIN_SOURCE)


class ClashClaimsCase(Place):
    def test_one_claim_per_unit_with_machine_values(self):
        rows = conflict.clash_claims(["B", "C"], ["e.py:1", "b.py:4"], WHY)
        self.assertEqual([r["unit_key"] for r in rows], ["B", "C"])
        self.assertEqual({(r[conflict.KIND_FIELD], r[conflict.WHICH_FIELD]) for r in rows}, {(conflict.NEEDS_CONTEXT, conflict.UNKNOWN)})

    def test_patch_marks_the_fix_as_kept_in_the_patch(self):
        ids = self.parked()
        conflict.mark_clash_patch(self.place, ids, "/p/join/g2.diff")
        conflict.apply_rulings(self.place, {i: {"decision": conflict.ASK, "text": "人が決める", "limits": []} for i in ids}, by="t")
        rows = conflict.asked(self.place)
        self.assertEqual(conflict.place_words(rows), conflict.FIX_REVERTED.format(patch="/p/join/g2.diff"))

    def test_rulings_file_tells_the_ruled_fixer_not_to_fix_clash_units(self):
        [rid] = self.parked(["B"])
        conflict.apply_rulings(self.place, {rid: {"decision": "fix_code_as", "text": "b.py をこう直す", "limits": []}}, by="t")
        self.assertIn(conflict.CLASH_PROMISE, (self.place / conflict.RULINGS_FILE).read_text(encoding="utf-8"))


class RejudgeCase(Place):
    def test_rejudge_holds_the_unit_without_asking_a_human(self):
        [rid] = self.parked(["B"])
        conflict.apply_rulings(self.place, {rid: {"decision": conflict.REJUDGE, "text": "B と A は 1 つの問題", "limits": []}}, by="t")
        self.assertIn("B", conflict.held_by_rulings(self.place))
        self.assertEqual(conflict.asked(self.place), [])
        self.assertEqual(conflict.human_lines(self.place), [])
        self.assertEqual(conflict.rejudge_texts(conflict.items(self.place)), ["B と A は 1 つの問題"])
        self.assertEqual(conflict.counts(self.place)[conflict.REJUDGE], 1)

    def test_counts_omit_rejudge_when_none_was_ruled(self):
        self.assertNotIn(conflict.REJUDGE, conflict.counts_of([]))


class RulingProblemsCase(unittest.TestCase):
    TODO = {"c1-1": {"id": "c1-1", "unit_key": "B", "source": conflict.JOIN_SOURCE, conflict.WHY_FIELD: WHY},
            "c1-2": {"id": "c1-2", "unit_key": "C", "source": conflict.JOIN_SOURCE, conflict.WHY_FIELD: WHY},
            "c1-3": {"id": "c1-3", "unit_key": "D", "source": conflict.FIX_SOURCE, conflict.WHY_FIELD: "別の申し出の理由"}}

    def problems(self, *rows):
        todo = {r["id"]: self.TODO[r["id"]] for r in rows}
        return ruling.problems({"rulings": list(rows)}, todo, "/nonexistent")

    def ruled(self, rid, decision, limits=()):
        return {"id": rid, "decision": decision, "text": "裁きの理由の文", "limits": list(limits)}

    def test_rejudge_only_for_clash_claims(self):
        self.assertEqual(self.problems(self.ruled("c1-1", conflict.REJUDGE), self.ruled("c1-2", conflict.REJUDGE)), [])
        got = self.problems(self.ruled("c1-3", conflict.REJUDGE))
        self.assertTrue(any(conflict.JOIN_SOURCE in e for e in got), got)

    def test_rejudge_has_no_limits(self):
        got = self.problems(self.ruled("c1-1", conflict.REJUDGE, ["b.py"]), self.ruled("c1-2", conflict.REJUDGE))
        self.assertTrue(any("範囲を持たない" in e for e in got), got)

    def test_rows_of_one_group_share_one_ruling(self):
        got = self.problems(self.ruled("c1-1", conflict.REJUDGE), self.ruled("c1-2", conflict.ASK))
        self.assertTrue(any("同じ組の合わせの申し出" in e for e in got), got)


class CitesCase(unittest.TestCase):
    def test_first_hunk_new_side_line_per_file(self):
        patch = ("diff --git a/e.py b/e.py\n--- a/e.py\n+++ b/e.py\n@@ -11,1 +12,1 @@\n-E8 = 8\n+E8 = 80\n@@ -20 +30 @@\n"
                 "diff --git a/n.py b/n.py\nnew file mode 100644\n--- /dev/null\n+++ b/n.py\n@@ -0,0 +1 @@\n+N = 1\n")
        self.assertEqual(clash.cites(patch, ["e.py", "n.py", "x.py"]), ["e.py:12", "n.py:1", "x.py:1"])


class StageCase(Place):
    def test_patch_that_does_not_apply_leaves_the_tree_alone(self):
        from tests.bin.gitkit import committed_copy
        repo = self.place / "repo"
        committed_copy(repo, LIB.parent / "tests" / "e2e" / "target-seed")
        tree = tddloop.snapshot(repo)
        patch = self.place / "join" / "g2.diff"
        patch.parent.mkdir()
        patch.write_text("diff --git a/stats.py b/stats.py\n--- a/stats.py\n+++ b/stats.py\n@@ -1,1 +1,1 @@\n-nothing like this\n+X\n",
                         encoding="utf-8")
        out_dir = self.place / "groups"
        fixboard.write_json(self.place / fixboard.GROUPS_FILE, {"groups": [], "out_dir": str(out_dir)})
        fixboard.write_json(out_dir / "g2" / fixboard.RESULT_FILE, {"end_tree": tree, "verified": []})
        clash.record(self.place, [{"group_id": "g2", "unit_ids": ["B"], "patch": str(patch), "names": ["stats.py"], "shared": [],
                                   "why": WHY}])
        ok, why = clash.stage(self.place, repo, "g2", clash.FIRST)
        self.assertFalse(ok)
        self.assertIn("当たらない", why)
        self.assertEqual(tddloop.snapshot(repo), tree)
        self.assertEqual(clash.todo(self.place, clash.FIRST), ["g2"], "当たらなかった組はまだ直し待ち（呼び手が申し出へ回す）")


if __name__ == "__main__":
    unittest.main()

"""fix の部品の継ぎ目の直し（盤面の物を置き場のパスと引数に替えた所）と lib/groups.py の試験。盤面は使わず、
tests/bin/gitkit.py と tests/e2e/target-seed/ の写しで小さなリポジトリを作る。

縛る事:
- groups.adopt_tree・end_tree・diff_since: 同じ clone の 2 つの worktree の間で親の姿の木を子に写し、子の変更の差分を取り、
  unittrees.apply で 2 つの組の差分を順に当てる。2 つ目が当たらない時に 1 つ目が残り、2 つ目は当たらないと返る
- leftovers.record_ignored・remove_new_ignored: 控えに無かった無視されるファイルだけを消し、前から在った無視されるフォルダの
  中は残し、除くパスの頭の下は消さない。既定の () では除かない。控えは置き場のフォルダに置く
- writes の除き（check・unrecorded の skip）も同じ。writes.base_test_texts は版を引数で受け、読み損ねを置き場の trace.jsonl に残す
  （元 tests/test_plan_fields.py の TestBaseTestTexts の場合を写した）。fixboard.base_rev は元の writes.base_rev と同じ順で版を選ぶ
- lens の控えは置き場の lens.json。summary は差分の審査の出力をファイルのパスで受ける
"""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from tests.bin.gitkit import committed_copy, git  # noqa: E402
import fixboard  # noqa: E402
import groups  # noqa: E402
import leftovers  # noqa: E402
import lens  # noqa: E402
import unittrees  # noqa: E402
import writes  # noqa: E402

SEED = LIB.parent / "tests" / "e2e" / "target-seed"
SKIP = ("vendored/",)
WHY = "整形の道具で 40 ファイルを一度に書き換えた"


def _traced(place) -> list:
    p = pathlib.Path(place) / "trace.jsonl"
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []


class TempCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="works-fix-seams-")
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        self.rev = committed_copy(self.repo, SEED)
        self.place = self.tmp / "place"
        self.place.mkdir()


class TestGroups(TempCase):
    """親の作業ツリー（未 commit の直しを持つ）の姿を木で子の worktree に写し、子の差分を親へ順に当てる"""

    def child(self, name: str) -> pathlib.Path:
        path = self.tmp / name
        git(self.repo, "worktree", "add", "--detach", "--quiet", str(path), "HEAD")
        return path

    def test_adopt_copies_parent_shape_and_diffs_apply_in_order(self):
        stats = (self.repo / "stats.py").read_text(encoding="utf-8")
        (self.repo / "stats.py").write_text(stats + "\n# 親の直し\n", encoding="utf-8")
        (self.repo / "NOTES.md").write_text("親の新しいファイル\n", encoding="utf-8")
        tree = groups.end_tree(self.repo)
        self.assertEqual(tree, leftovers.snapshot(self.repo))

        c1, c2 = self.child("c1"), self.child("c2")
        (c1 / "NOTES.md").write_text("子に前から在った追跡外のファイル\n", encoding="utf-8")   # 木にも在る名
        for c in (c1, c2):
            groups.adopt_tree(c, tree)
            self.assertEqual((c / "stats.py").read_text(encoding="utf-8"), stats + "\n# 親の直し\n", "親の未 commit の直しが見える")
            self.assertEqual((c / "NOTES.md").read_text(encoding="utf-8"), "親の新しいファイル\n", "木の姿に替わる")
            self.assertEqual(groups.end_tree(c), tree, "写した後の子の姿は親の木と同じ")
            self.assertEqual(groups.diff_since(c, tree, groups.end_tree(c)), "", "変えていなければ差分は空")

        (c1 / "NOTES.md").write_text("組 1 の直し\n", encoding="utf-8")
        (c1 / "ONE.md").write_text("組 1 の新しいファイル\n", encoding="utf-8")
        (c2 / "NOTES.md").write_text("組 2 の直し\n", encoding="utf-8")   # 組 1 と同じ行
        d1 = groups.diff_since(c1, tree, groups.end_tree(c1))
        d2 = groups.diff_since(c2, tree, groups.end_tree(c2))
        self.assertIn("diff --git a/NOTES.md b/NOTES.md", d1)
        self.assertIn("diff --git a/ONE.md b/ONE.md", d1)

        self.assertEqual(unittrees.apply(self.repo, d1), (True, ""))
        ok, why = unittrees.apply(self.repo, d2)
        self.assertFalse(ok)
        self.assertTrue(why)
        self.assertEqual((self.repo / "NOTES.md").read_text(encoding="utf-8"), "組 1 の直し\n", "1 つ目が残る")
        self.assertEqual((self.repo / "ONE.md").read_text(encoding="utf-8"), "組 1 の新しいファイル\n")
        self.assertEqual((self.repo / "stats.py").read_text(encoding="utf-8"), stats + "\n# 親の直し\n")


class TestLeftovers(TempCase):
    """控えは置き場のフォルダに置く。消すのは控えに無かった無視されるファイルだけ"""

    def setUp(self):
        super().setUp()
        (self.repo / ".gitignore").write_text("*.log\n.venv/\nvendored/\n", encoding="utf-8")
        git(self.repo, "add", ".gitignore")
        git(self.repo, "commit", "-q", "-m", "ignore")
        (self.repo / ".venv").mkdir()
        (self.repo / ".venv" / "old.txt").write_text("前から\n", encoding="utf-8")
        (self.repo / "old.log").write_text("前から\n", encoding="utf-8")

    def make_new(self):
        (self.repo / "new.log").write_text("修正役が残した\n", encoding="utf-8")
        (self.repo / ".venv" / "new.txt").write_text("前から在ったフォルダの中\n", encoding="utf-8")
        (self.repo / "vendored").mkdir(exist_ok=True)
        (self.repo / "vendored" / "copy.log").write_text("除く頭の下\n", encoding="utf-8")

    def test_record_writes_before_into_the_place(self):
        got = leftovers.record_ignored(self.place, self.repo)
        self.assertEqual(got["file"], str(self.place / leftovers.IGNORED_BEFORE_FILE))
        before = json.loads((self.place / leftovers.IGNORED_BEFORE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(set(before), {"ignored", "ignored_dirs", "dirs", "head_tree"})
        self.assertEqual(before["ignored_dirs"], [".venv/"])
        self.assertIn("old.log", before["ignored"])
        self.assertEqual(leftovers.head_tree(self.place), leftovers.snapshot(self.repo))

    def test_removes_only_new_ignored_and_keeps_skip_prefix(self):
        leftovers.record_ignored(self.place, self.repo)
        self.make_new()
        got = leftovers.remove_new_ignored(self.place, self.repo, skip=SKIP)
        self.assertEqual(got["count"], 1)
        self.assertEqual(json.loads((self.place / leftovers.REMOVED_FILE).read_text(encoding="utf-8")), {"removed": ["new.log"]})
        self.assertFalse((self.repo / "new.log").exists())
        self.assertTrue((self.repo / "old.log").is_file(), "前から在った無視されるファイルは残す")
        self.assertTrue((self.repo / ".venv" / "new.txt").is_file(), "前から在った無視されるフォルダの中は残す")
        self.assertTrue((self.repo / "vendored" / "copy.log").is_file(), "除くパスの頭の下は消さない")

    def test_default_skips_nothing(self):
        leftovers.record_ignored(self.place, self.repo)
        self.make_new()
        got = leftovers.remove_new_ignored(self.place, self.repo)
        self.assertEqual(got["count"], 2)
        self.assertFalse((self.repo / "vendored").exists(), "既定の () では除かない（空になった親も消す）")
        self.assertTrue((self.repo / ".venv" / "new.txt").is_file())

    def test_no_before_is_unreadable(self):
        with self.assertRaises(leftovers.Unreadable):
            leftovers.remove_new_ignored(self.place, self.repo, skip=SKIP)


class TestWritesSeams(TempCase):
    def setUp(self):
        super().setUp()
        self.log = self.tmp / "writes.jsonl"
        self.log.write_text("", encoding="utf-8")
        d = self.repo / "vendored" / "workflows"
        d.mkdir(parents=True)
        (d / "copy.yaml").write_text("x: 1\n", encoding="utf-8")

    def test_skip_prefix_is_not_counted(self):
        paths = writes.changed(self.repo, self.rev)
        self.assertEqual(paths, ["vendored/workflows/copy.yaml"])
        self.assertEqual(writes.check({}, self.repo, paths, self.log, skip=SKIP)["problems"], [])
        self.assertEqual(writes.unrecorded(self.repo, paths, self.log, skip=SKIP), [])

    def test_default_counts_everything(self):
        paths = writes.changed(self.repo, self.rev)
        got = writes.check({}, self.repo, paths, self.log)
        self.assertEqual(got["left"], ["vendored/workflows/copy.yaml"])
        self.assertIn("vendored/workflows/copy.yaml", got["problems"][0])

    def test_trace_rows_go_to_the_place(self):
        writes.trace(self.place, "fix", {"note": writes.NO_RECORD, "left": ["a.py"]})
        writes.trace(self.place, "refix", {"note": "", "left": []})
        self.assertEqual(_traced(self.place), [{"op": writes.NO_RECORD_OP, "node": "fix", "note": writes.NO_RECORD},
                                               {"op": writes.LEFT_OP, "node": "fix", "paths": ["a.py"]}])


class TestBaseTestTexts(TempCase):
    """writes.base_test_texts: 修正前の版のテストを読み損ねたら、黙って空にせず置き場の trace.jsonl に残す
    （元 tests/test_plan_fields.py の TestBaseTestTexts の場合を、版を引数で受ける形に写した）"""

    def test_readable_base_leaves_no_trace_row(self):
        self.assertEqual(sorted(writes.base_test_texts(self.place, self.repo, self.rev)), ["test_stats.py"])
        self.assertEqual(_traced(self.place), [])

    def test_unreadable_rev_is_traced(self):
        self.assertEqual(writes.base_test_texts(self.place, self.repo, "0" * 40), {})
        self.assertEqual(_traced(self.place), [{"op": writes.BASE_TESTS_UNREAD_OP, "rev": "0" * 40, "unread": ["<版>"]}])

    def test_unreadable_file_is_traced_with_its_path(self):
        real = writes.git

        def flaky(repo, *args, **kw):
            if args[0] == "show":
                raise leftovers.Unreadable("読めない")
            return real(repo, *args, **kw)

        with mock.patch.object(writes, "git", flaky):
            self.assertEqual(writes.base_test_texts(self.place, self.repo, self.rev), {})
        self.assertEqual(_traced(self.place), [{"op": writes.BASE_TESTS_UNREAD_OP, "rev": self.rev, "unread": ["test_stats.py"]}])

    def test_base_rev_order(self):
        self.assertEqual(fixboard.base_rev({"inputs": {"review_rev": "abc"}}, "def"), "abc")
        self.assertEqual(fixboard.base_rev({"inputs": {}}, "def"), "def")
        self.assertEqual(fixboard.base_rev(None), "HEAD")


class TestLensPlace(unittest.TestCase):
    """lens の控え lens.json は置き場のフォルダに置き、summary は差分の審査の出力のファイルを受ける"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.place = pathlib.Path(tmp.name)

    def test_routes_collect_and_summary(self):
        self.assertIsNone(lens.read(self.place))
        lens.write_routes(self.place, [{"lens": "a", "agent": "x", "go": True}, {"lens": "b", "agent": "y", "go": False}])
        self.assertTrue((self.place / lens.LENS_FILE).is_file())
        lens.collect(self.place, {"a": {"findings": [{"where": "w", "cite": "c", "why": "y"}, {"where": ""}]}})
        rows = lens.read(self.place)
        self.assertEqual([(r["lens"], r["state"]) for r in rows], [("a", "ran"), ("b", "not_routed")])
        self.assertEqual(lens.summary(self.place)["adopted"], None, "審査の出力を渡さなければ調べていない")
        review = self.place / "review.json"
        review.write_text(json.dumps({"faces": [{"key": "k", "lens": "a"}, {"key": "j", "lens": "zz"}]}), encoding="utf-8")
        s = lens.summary(self.place, review)
        self.assertEqual((s["adopted"], s["not_adopted"], s["dropped"], s["unmatched"]), (1, 0, 1, 1))
        self.assertIn("採った 1 件", lens.report_lines(self.place, review)[-1])
        broken = lens.summary(self.place, self.place / "none.json")
        self.assertFalse(broken["readable"])



KEY_A = "stats.py clamp: 上限を超えた値に lo を返す"
KEY_B = "stats.py mean: 分母が len - 1"
CLAIM = {"unit_key": KEY_A, "between": ["stats.py:3", "test_stats.py:2"],
         "why_both_cannot_hold": "テストは上限 hi を期待し、今のコードは lo を返す——両方は成り立たない",
         "which_is_right": "request", "kind": "brief_vs_judgment"}


def _trace_rows(place: pathlib.Path) -> list:
    p = place / "trace.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []


class ConflictSeamCase(unittest.TestCase):
    """conflict の継ぎ目: 申し出の控えは置き場（pathlib.Path(b)）の conflicts.json {"items": [...]}、trace は置き場の
    trace.jsonl（fixboard.trace）、周は引数 round_（既定 1）、壊れた控えは ValueError"""

    def setUp(self):
        import conflict
        import fixboard
        self.conflict, self.fixboard = conflict, fixboard
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.place = pathlib.Path(tmp.name)

    def test_park_writes_and_reads_the_places_json(self):
        c = self.conflict
        ids = c.park(self.place, [CLAIM], source=c.FIX_SOURCE)
        self.assertEqual(ids, ["c1-1"])
        doc = json.loads((self.place / "conflicts.json").read_text(encoding="utf-8"))
        self.assertEqual(list(doc), ["items"])
        self.assertEqual([r["unit_key"] for r in doc["items"]], [KEY_A])
        self.assertEqual(c.items(str(self.place))[0]["kind"], "brief_vs_judgment")   # 文字列のパスでも同じ置き場
        self.assertEqual([r["id"] for r in c.unruled(self.place)], ["c1-1"])
        self.assertEqual(c.park(self.place, [CLAIM], source=c.FIX_SOURCE), ["c1-1"], "同じ申し出は積み増さない")
        self.assertEqual([r["op"] for r in _trace_rows(self.place)], [c.PARK_OP])
        self.assertEqual(c.park(self.place, [{**CLAIM, "unit_key": KEY_B}], source=c.TDD_SOURCE, round_=2), ["c2-2"])

    def test_ruling_leaves_duty_and_fix_plan_item_gets_replan(self):
        c = self.conflict
        c.park(self.place, [CLAIM, {**CLAIM, "unit_key": KEY_B}], source=c.FIX_SOURCE)
        self.assertEqual(self.fixboard.fix_duty(self.place, {KEY_A, KEY_B}), ({KEY_A, KEY_B}, {}))
        path = c.apply_rulings(self.place, {"c1-1": {"decision": c.REPLAN, "text": "案の項目 1 の受け入れのテストが誤り",
                                                     "limits": [], "plan_items": [1], "plan_units": [KEY_A]},
                                            "c1-2": {"decision": "fix_code_as", "text": "コードを hi を返す形に直せ",
                                                     "limits": ["stats.py"]}}, by="t")
        self.assertEqual(path, self.place / c.RULINGS_FILE)
        self.assertTrue(path.is_file())
        rows = {r["id"]: r for r in c.items(self.place)}
        self.assertEqual(rows["c1-1"][c.REPLAN_STATE], c.WAITING)
        self.assertEqual(rows["c1-1"]["ruling"]["decision"], c.REPLAN)
        self.assertNotIn(c.REPLAN_STATE, rows["c1-2"])
        self.assertEqual([r["id"] for r in c.waiting(self.place)], ["c1-1"])
        self.assertEqual([r["id"] for r in c.ruled_fix(self.place)], ["c1-2"])
        self.assertEqual(c.asked(self.place), [])
        owed, excused = self.fixboard.fix_duty(self.place, {KEY_A, KEY_B})
        self.assertEqual(owed, {KEY_B})
        self.assertIn("fix_plan_item の裁定 c1-1", excused[KEY_A])
        self.assertEqual(self.fixboard.nothing_owed_but_excused(self.place, {KEY_A}), {KEY_A: excused[KEY_A]})
        self.assertEqual(self.fixboard.nothing_owed_but_excused(self.place, {KEY_A, KEY_B}), {})
        self.assertEqual([r["op"] for r in _trace_rows(self.place)], [c.PARK_OP, c.PARK_OP, c.RULE_OP, c.RULE_OP])

    def test_ask_human_is_asked_and_amended_returns_to_duty(self):
        c = self.conflict
        c.park(self.place, [CLAIM, {**CLAIM, "unit_key": KEY_B}], source=c.FIX_SOURCE)
        c.apply_rulings(self.place, {"c1-1": {"decision": c.ASK, "text": "方針の変更で人が決める", "limits": []},
                                     "c1-2": {"decision": c.REPLAN, "text": "案の項目 2 の範囲が誤り", "limits": []}},
                        by="t")
        self.assertEqual([r["id"] for r in c.asked(self.place)], ["c1-1"])
        c.set_replan(self.place, ["c1-2"], c.AMENDED)
        self.assertEqual(c.amended_keys(self.place), {KEY_B})
        self.assertEqual(self.fixboard.fix_duty(self.place, {KEY_A, KEY_B})[0], {KEY_B})
        self.assertEqual(_trace_rows(self.place)[-1], {"op": c.REPLAN_OP, "id": "c1-2", "unit_key": KEY_B,
                                                       "state": c.AMENDED, "why": ""})
        with self.assertRaises(ValueError):
            c.set_replan(self.place, ["c1-1"], c.AMENDED)

    def test_withheld_and_returned_are_arguments(self):
        owed, excused = self.fixboard.fix_duty(self.place, {KEY_A, KEY_B},
                                               withheld_by={KEY_B: {"key": "q1", "kind": "fork", "status": "held"}})
        self.assertEqual(owed, {KEY_A})
        self.assertIn("答え待ちの問い q1", excused[KEY_B])
        owed, _ = self.fixboard.fix_duty(self.place, {KEY_A}, withheld_by={}, returned={KEY_B})
        self.assertEqual(owed, {KEY_A, KEY_B})

    def test_broken_store_is_value_error(self):
        c = self.conflict
        for text in ("{", "[]", '{"items": {}}'):
            with self.subTest(text=text):
                (self.place / "conflicts.json").write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    c.items(self.place)
        with self.assertRaises(ValueError):
            c.park(self.place, [CLAIM], source="other")

    def test_plan_asks_read_the_places_trace(self):
        c = self.conflict
        self.fixboard.trace(self.place, c.ASKED_OP, id="a1", item=1, status="answered", decision="allow",
                            granted_paths=["docs/x.md"])
        self.fixboard.trace(self.place, c.ASKED_OP, id="a2", item=1, status="answered", decision="deny")
        self.assertEqual([r["id"] for r in c.plan_asks(self.place)], ["a1", "a2"])
        self.assertEqual([r["id"] for r in c.agreed(self.place)], ["a1"])

    def test_permits_read_the_frozen_fields_in_the_place(self):
        import planmarks
        c = self.conflict
        fields = [{"unit_keys": [KEY_A], "rewrite_tests": [{"id": "test_stats.py::test_clamp", "new": "hi を期待する",
                                                            "limit": "test_stats.py:1"}]}]
        planmarks.save(self.place, 1, fields)
        got = c.test_permits(self.place)
        self.assertEqual([(p["id"], p["limit"]) for p in got], [(f"{c.PLAN_TEST_ID}-1", "test_stats.py:1")])
        self.assertEqual(c.test_permits(self.place, round_=2), [], "周の違う控えは読まない")
        self.assertEqual(c.frozen_fields(self.place), fields)
        (self.place / planmarks.FIELDS_FILE).write_text("{}", encoding="utf-8")   # 受け付けの後に書き換えた
        stopped = []
        with self.assertRaises(ValueError) as cm:
            c.test_permits(self.place)
        self.assertIn(c.FIELDS_TAMPERED, str(cm.exception))
        err = c.fields_broken(self.place, planmarks.FieldsBroken("x"), stop=lambda why, by: stopped.append(by))
        self.assertIsInstance(err, ValueError)
        self.assertEqual(stopped, [c.stopby.FIX])


class PlanrangeSeamCase(unittest.TestCase):
    """planrange の継ぎ目: 承認済みの修正案の項目は値 items で受け、合意と裁定は置き場（conflict と同じ置き場）から読む"""

    ITEMS = [{"item": 1, "unit_keys": [KEY_A], "allowed_paths": ["stats.py"], "tests": [], "rewrite_tests": [],
              "out_of_scope": [{"glob": "vendored/**", "why": "外の写し"}]}]

    def setUp(self):
        import conflict
        import planrange
        self.conflict, self.planrange = conflict, planrange
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.place = pathlib.Path(tmp.name)

    def test_outside_the_items_range_is_rejected_inside_passes(self):
        pr = self.planrange
        lines, rec = pr.check_paths(self.place, ["stats.py"], items=self.ITEMS)
        self.assertEqual((lines, rec), ([], {"checked": True, "items": [1]}))
        lines, rec = pr.check_paths(self.place, ["stats.py", "other.py", "vendored/x.py"], items=self.ITEMS)
        self.assertTrue(rec["checked"])
        self.assertEqual(len(lines), 2, lines)
        self.assertTrue(any("other.py" in x and "allowed_paths" in x for x in lines), lines)
        self.assertTrue(any("vendored/x.py" in x and "out_of_scope" in x for x in lines), lines)

    def test_unchecked_without_a_scoped_plan(self):
        pr = self.planrange
        self.assertEqual(pr.check_paths(self.place, ["x.py"], items=None), ([], {"checked": False, "why": pr.NO_PLAN}))
        self.assertEqual(pr.check_paths(self.place, ["x.py"], items=[{"item": 1}]),
                         ([], {"checked": False, "why": pr.NO_SCOPE}))
        self.assertEqual(pr.approved(self.ITEMS), (self.ITEMS, ""))

    def test_agreed_and_ruled_paths_widen_from_the_place(self):
        c, pr = self.conflict, self.planrange
        import fixboard
        fixboard.trace(self.place, c.ASKED_OP, id="a1", item=1, status="answered", decision="allow",
                       granted_paths=["docs/x.md"])
        c.park(self.place, [CLAIM], source=c.FIX_SOURCE)
        c.apply_rulings(self.place, {"c1-1": {"decision": "fix_code_as", "text": "設定のファイルも直してよい",
                                              "limits": ["conf.ini"]}}, by="t")
        self.assertEqual(pr.check_paths(self.place, ["docs/x.md", "conf.ini"], items=self.ITEMS)[0], [])
        lines, _ = pr.check_paths(self.place, ["conf.ini"], items=self.ITEMS, ruled=False)
        self.assertTrue(any("conf.ini" in x for x in lines), lines)
        self.assertEqual(pr.permit_paths(self.place, ruled=True), ["conf.ini"])


if __name__ == "__main__":
    unittest.main()

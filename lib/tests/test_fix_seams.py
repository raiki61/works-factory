"""fix の部品の継ぎ目の直し（盤面の物を置き場のパスと引数に替えた所）と lib/groups.py の試験。盤面は使わず、
tests/bin/gitkit.py と tests/e2e/target-seed/ の写しで小さなリポジトリを作る。

縛る事:
- groups.adopt_tree・end_tree・diff_since: 同じ clone の 2 つの worktree の間で親の姿の木を子に写し、子の変更の差分を取り、
  unittrees.apply で 2 つの組の差分を順に当てる。2 つ目が当たらない時に 1 つ目が残り、2 つ目は当たらないと返る
- leftovers.record_ignored・remove_new_ignored: 控えに無かった無視されるファイルだけを消し、前から在った無視されるフォルダの
  中は残し、除くパスの頭の下は消さない。既定の () では除かない。控えは置き場のフォルダに置く
- writes の除き（check・unrecorded の skip）も同じ。fixboard.base_rev は元の writes.base_rev と同じ順で版を選ぶ
- lens の控えは置き場の lens.json。summary は差分の審査の出力をファイルのパスで受ける
- refix・lenses・rulebook: refix.cut・accept_review・accept_fix は置き場のファイルと引数の値で回り、範囲の外の手直しを
  planrange.check_paths の行で拒む。lenses.render は役の定義の本文から、rulebook.render は rolekit.compose で指示書を組む
- ruling.prep・accept_rule: 置き場のファイルで回り、作業ツリーの控えは fixboard.snapshot、拒否の理由のファイル・言語の行・輪の回は
  引数、配線の誤りは ValueError
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

from tests.bin.gitkit import committed_copy, git  # noqa: E402
import fixboard  # noqa: E402
import groups  # noqa: E402
import leftovers  # noqa: E402
import lens  # noqa: E402
import rolekit  # noqa: E402
import unittrees  # noqa: E402
import writes  # noqa: E402
from tests.bin import hermetic  # noqa: E402

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

    def test_keeps_files_inside_old_ignored_dirs_and_empty_dirs(self):
        """F418: 前から在った無視されるフォルダ（svc/.venv）に足したファイルは 1 本も消さず、新しく出来た無視されるフォルダは丸ごと
        消す。前から在った空のフォルダ（build/empty・追跡するフォルダの下の src/cache）に置かれた無視されるファイルは消すがフォルダは
        残し、後から出来たフォルダは消す。フォルダの控えの無い古い形の控えは拒んで何も消さない（元 works/tests/test_blk_fix.py:1641
        test_keeps_new_files_inside_ignored_dir_that_was_there_before・:1661 test_keeps_empty_dir_that_was_there_before・:1682
        test_refuses_old_record_without_dirs の写し）"""
        (self.repo / ".gitignore").write_text("*.log\n.venv/\nvendored/\n__pycache__/\n*.pyc\n**/.venv\n", encoding="utf-8")
        (self.repo / "src").mkdir()
        (self.repo / "src" / "keep.txt").write_text("k\n", encoding="utf-8")
        git(self.repo, "add", ".gitignore", "src/keep.txt")
        git(self.repo, "commit", "-q", "-m", "ignore")
        venv = self.repo / "svc" / ".venv"
        (venv / "lib").mkdir(parents=True)
        (venv / "lib" / "old.py").write_text("o\n", encoding="utf-8")
        (self.repo / "build" / "empty").mkdir(parents=True)
        (self.repo / "src" / "cache").mkdir()
        leftovers.record_ignored(self.place, self.repo)
        added = [venv / "lib" / "pkg" / f"m{i}.py" for i in range(5)]
        added[0].parent.mkdir()
        for p in added:
            p.write_text("m\n", encoding="utf-8")
        (self.repo / "svc2" / ".venv" / "lib").mkdir(parents=True)
        (self.repo / "svc2" / ".venv" / "lib" / "n.py").write_text("n\n", encoding="utf-8")
        (self.repo / "build" / "empty" / "x.pyc").write_bytes(b"x")
        (self.repo / "src" / "cache" / "y.pyc").write_bytes(b"y")
        (self.repo / "src" / "new" / "__pycache__").mkdir(parents=True)
        (self.repo / "src" / "new" / "__pycache__" / "z.pyc").write_bytes(b"z")
        got = leftovers.remove_new_ignored(self.place, self.repo, skip=SKIP)
        removed = json.loads((self.place / leftovers.REMOVED_FILE).read_text(encoding="utf-8"))["removed"]
        self.assertEqual(got["count"], len(removed))
        self.assertEqual([p for p in added if not p.exists()], [], "前から在った .venv に足したファイルは残す")
        self.assertTrue((venv / "lib" / "old.py").exists())
        self.assertFalse((self.repo / "svc2").exists(), "修正役の後に出来た無視のフォルダは消す")
        self.assertTrue((self.repo / "build" / "empty").is_dir(), "前から在った空のフォルダは残す")
        self.assertFalse((self.repo / "build" / "empty" / "x.pyc").exists())
        self.assertTrue((self.repo / "src" / "cache").is_dir(), "前から在った空のフォルダは残す")
        self.assertFalse((self.repo / "src" / "cache" / "y.pyc").exists())
        self.assertFalse((self.repo / "src" / "new").exists(), "修正役の後に出来たフォルダは消す")
        self.assertTrue((self.repo / "src" / "keep.txt").exists())
        with self.subTest("フォルダの控えの無い古い形の控え"):
            (self.place / leftovers.IGNORED_BEFORE_FILE).write_text(json.dumps({"ignored": []}), encoding="utf-8")
            (self.repo / "__pycache__").mkdir()
            (self.repo / "__pycache__" / "x.pyc").write_bytes(b"x")
            with self.assertRaisesRegex(leftovers.Unreadable, "dirs"):
                leftovers.remove_new_ignored(self.place, self.repo, skip=SKIP)
            self.assertTrue((self.repo / "__pycache__" / "x.pyc").exists())


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
    """fixboard.base_rev は元の writes.base_rev と同じ順で修正前の版を選ぶ"""

    def test_base_rev_order(self):
        self.assertEqual(fixboard.base_rev({"inputs": {"review_rev": "abc"}}, "def"), "abc")
        self.assertEqual(fixboard.base_rev({"inputs": {}}, "def"), "def")
        self.assertEqual(fixboard.base_rev(None), "HEAD")


class TestLensPlace(unittest.TestCase):
    """lens の控え lens.json は置き場のフォルダに置く"""

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

    def test_replan_readers_take_the_items_from_the_stored_ruling(self):
        """apply_rulings が積んだ fix_plan_item の行から、fixboard.replan_items と conflict.replan_rows が同じ案の項目を読む
        （項目の番号は裁定の欄の中。組の項目に落ちない）"""
        c = self.conflict
        c.park(self.place, [CLAIM], source=c.FIX_SOURCE)
        c.apply_rulings(self.place, {"c1-1": {"decision": c.REPLAN, "text": "案の項目 1 の受け入れのテストが誤り",
                                              "limits": [], "plan_items": [1], "plan_units": [KEY_A, KEY_B]}}, by="t")
        rows = c.items(self.place)
        self.assertEqual(self.fixboard.replan_items(rows, [{"unit_ids": [KEY_A, KEY_B], "items": [1, 2]}]), ["1"])
        self.assertEqual(self.fixboard.replan_items(rows), ["1"])
        self.assertEqual([r["id"] for r in c.replan_rows(rows, 1, [])], ["c1-1"])
        self.assertEqual(c.replan_rows(rows, 2, [KEY_B]), [])

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

    def test_trailing_slash_scope_globs_cover_paths_underneath(self):
        """末尾 / の allowed_paths・out_of_scope の glob は、その下の全部に効く（前は何にも当たらず、範囲が空・柵が空だった）"""
        items = [{"item": 1, "unit_keys": [KEY_A], "allowed_paths": ["lib/"], "tests": [], "rewrite_tests": [],
                  "out_of_scope": [{"glob": "lib/vendored/", "why": "外の写し"}]}]
        lines, rec = self.planrange.check_paths(self.place, ["lib/x.py", "docs/x.md", "lib/vendored/y.py"], items=items)
        self.assertTrue(rec["checked"])
        self.assertEqual(len(lines), 2, lines)
        self.assertFalse(any("lib/x.py" in x for x in lines), lines)
        self.assertTrue(any("docs/x.md" in x and "allowed_paths" in x for x in lines), lines)
        self.assertTrue(any("lib/vendored/y.py" in x and "out_of_scope" in x for x in lines), lines)

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


R_MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
R_CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
# 判定の units（元 works/tests/replies/judge_ok.json の class_query）
R_JUDGED = [{"key": R_MEAN, "class_query": {"how": {"patterns": ["(len(xs) - 1)"], "fixed": True, "paths": ["stats.py"],
                                                     "count": "lines"}, "counts": "defects", "total": 1}},
            {"key": R_CLAMP, "class_query": {"how": {"patterns": ["return lo"], "fixed": True, "paths": ["stats.py"],
                                                      "count": "lines"}, "counts": "population", "total": 2}}]
R_FIXED = {"sum(xs) / (len(xs) - 1)": "sum(xs) / len(xs)", "    if x > hi:\n        return lo": "    if x > hi:\n        return hi"}
R_RESIDUE = {"sum(xs) / (len(xs) - 1)": "sum(xs) / len(xs)  # 前は sum(xs) / (len(xs) - 1)",
             "    if x > hi:\n        return lo": "    if x > hi:\n        return hi"}


# 修正役の返答の changes の行の自己申告の欄（recount._reply_shape_problems が照らす。数え直しの試験の外の欄）
SELF_REPORT = {"bypass_tried": "修正を残したまま空の並びを渡して破りに行き、例外で止まるのを見た",
                "breaks": {"how": "git grep -n mean", "result": "呼び手は 1 か所で、戻り値の型は変わらない"},
                "precedent": {"problem": "平均の分母の誤り", "verdict": "adopt", "reason": "標準の定義に合わせる",
                              "source": "https://docs.python.org/3/library/statistics.html"},
                "root_or_symptom": {"kind": "root", "why": "分母の式そのものを直した"}}


def _fix_row(key, sites, **cov):
    return {"unit_key": key, "what": "直した", "files": ["stats.py"], "coverage": cov, **SELF_REPORT,
            "closure": {"sites": [{"site": f"s{i}", "red_seen": True} for i in range(sites)]}}


def _fix_ok() -> dict:
    """元 works/tests/replies/fix2_ok.json の数え直しに効く欄（mean の site 1・clamp の site 2）"""
    return {"changes": [_fix_row(R_MEAN, 1), _fix_row(R_CLAMP, 2)], "not_done": [],
            "interactions": [{"surface": "stats.py", "checked": "mean と clamp は別の関数で、順序を入れ替えても結果が同じ"}]}


class RecountSeamCase(TempCase):
    """recount.accept_fix: 受け付けの時に数え直しの欄を照らす（元 works/tests/test_blk_fix.py の TestRecount・
    test_fix_accept_all.py の DryTakeCase の場合を写した。盤面の代わりに判定の units・直す義務・修正前の版を引数で渡す）。
    fixboard.fix_reply は置き場のファイルで読む"""

    def setUp(self):
        super().setUp()
        import recount
        self.recount = recount

    def edit_tree(self, subs):
        path = self.repo / "stats.py"
        text = path.read_text(encoding="utf-8")
        for old, new in subs.items():
            self.assertIn(old, text)
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")

    def accept(self, reply, **kw):
        kw.setdefault("judged", R_JUDGED)
        kw.setdefault("owed", {R_MEAN, R_CLAMP})
        return self.recount.accept_fix(reply, self.place, self.rev, self.repo, **kw)

    def test_rejects_self_reports_the_machine_can_check(self):
        """元の写しの fix_covers_open_units の照らし: 黙って通る閉鎖の状態・赤を見ない clean・同じファイルの interactions・
        bypass_tried・breaks.result・判定者の行の無い from_judge_row・理由の短い symptom。1 誤り 1 行で全部並べる"""
        self.edit_tree(R_FIXED)
        bad = _fix_ok()
        bad["fix_closure"] = {"status": "not_applicable"}
        bad["interactions"] = []
        bad["changes"][0].update({"bypass_tried": "なし", "breaks": {"how": "x", "result": ""},
                                  "precedent": {"from_judge_row": True, "verdict": "adopt", "reason": "判定者の行"}})
        bad["changes"][1]["root_or_symptom"] = {"kind": "symptom", "why": "後で"}
        got = self.accept(bad)
        self.assertFalse(got["ok"], got)
        for word in ("fix_closure が not_applicable", "interactions に無い", "bypass_tried が空同然", "breaks.result が空同然",
                     "from_judge_row", "症状を塞ぐ"):
            self.assertIn(word, got["reason"])
        self.assertTrue(self.accept(bad, precedents=[{"key": R_MEAN}])["problems"])
        self.assertFalse(any("from_judge_row" in e for e in self.accept(bad, precedents=[{"key": R_MEAN}])["problems"]))
        clean = _fix_ok()
        clean["fix_closure"] = {"status": "clean"}
        for c in clean["changes"]:
            for site in c["closure"]["sites"]:
                site["red_seen"] = False
        self.assertIn("赤を一度も見ていない", self.accept(clean)["reason"])

    def test_rejects_wrote_refs_and_added_links_that_do_not_resolve(self):
        """修正が書いた指し（wrote_refs）は指し先の中で数え直し、差分が足した Markdown のリンクは申告に依らず指し先を引く"""
        self.edit_tree(R_FIXED)
        (self.repo / "NOTES.md").write_text("# 覚え\n\n[式](stats.py) と [無い](gone.md) と [節](NOTES.md#無い見出し)\n",
                                            encoding="utf-8")
        reply = {**_fix_ok(), "wrote_refs": [{"kind": "text", "cite": "def median", "target": "stats.py", "where": "NOTES.md"}]}
        got = self.accept(reply)
        self.assertFalse(got["ok"], got)
        self.assertIn("'def median' は指し先 'stats.py' の中に無い", got["reason"])
        self.assertIn("gone.md", got["reason"])
        self.assertIn("#無い見出し", got["reason"])
        self.assertNotIn("(stats.py)", got["reason"])
        (self.repo / "NOTES.md").write_text("# 覚え\n\n[式](stats.py)\n", encoding="utf-8")
        reply["wrote_refs"] = [{"kind": "text", "cite": "def mean", "target": "stats.py", "where": "NOTES.md"}]
        self.assertTrue(self.accept(reply)["ok"])

    def calls(self) -> int:
        p = self.place / self.recount.COUNT_BUDGET_FILE
        return json.loads(p.read_text(encoding="utf-8"))["calls"] if p.is_file() else 0

    def assert_rejected(self, reply, *words, **kw):
        calls = self.calls()
        got = self.accept(reply, **kw)
        self.assertFalse(got["ok"], got)
        self.assertEqual(got["changes"], [], "拒んだときの changes は空（1 本目と同じ）")
        if "直していない" not in got["reason"]:
            self.assertGreater(self.calls(), calls, "数えた量は拒否でも刻む")
        for w in words:
            self.assertIn(w, got["reason"])
        self.assertFalse((self.place / self.recount.COVERAGE_FILE).exists(), "拒んだ受け付けは件数を書かない")
        return got

    def test_accepts_real_fix_and_keeps_counts(self):
        self.edit_tree(R_FIXED)
        reply = _fix_ok()
        got = self.accept(reply)
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["changes"], [{"unit_key": k, "files": ["stats.py"], "what": "直した"} for k in (R_MEAN, R_CLAMP)])
        cov = json.loads((self.place / self.recount.COVERAGE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(cov["round"], 1)
        self.assertEqual({i["unit_key"]: (i["total"], i["after"]) for i in cov["items"]}, {R_MEAN: (1, 0), R_CLAMP: (2, 1)})
        self.assertEqual(reply["changes"][0]["coverage"]["how"], R_JUDGED[0]["class_query"]["how"], "判定者の how を書き戻す")
        cov = json.loads((self.place / self.recount.COVERAGE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(cov["round"], 1)
        self.assertEqual({i["unit_key"]: (i["total"], i["after"]) for i in cov["items"]}, {R_MEAN: (1, 0), R_CLAMP: (2, 1)})

    def test_rejects_count_not_dropped(self):
        self.assert_rejected(_fix_ok(), R_MEAN, "母数 1", "修正の後も 1 件")
        self.edit_tree(R_RESIDUE)
        self.assert_rejected(_fix_ok(), R_MEAN, "母数 1", "修正の後も 1 件")

    def test_rejects_sites_mismatch_unless_remaining_is_written(self):
        self.edit_tree(R_FIXED)
        short = _fix_ok()
        short["changes"][1]["closure"]["sites"] = short["changes"][1]["closure"]["sites"][:1]
        self.assert_rejected(short, R_CLAMP, "母数 2", "1 件", "remaining")
        over = _fix_ok()
        over["changes"][0]["closure"]["sites"] *= 3
        self.assert_rejected(over, R_MEAN, "3 件", "母数は 1")
        short["changes"][1]["coverage"] = {"remaining": "x < lo の枝は正しく lo を返すので、この周では直さない"}
        self.assertTrue(self.accept(short)["ok"], "残した理由を書けば通す（黙って残すのだけを拒む）")

    def test_rejects_uncovered_owed_unit(self):
        self.edit_tree(R_FIXED)
        reply = _fix_ok()
        del reply["changes"][1]
        self.assert_rejected(reply, "直していない", R_CLAMP)
        self.assertTrue(self.accept(reply, owed={R_MEAN})["ok"], "直す義務に無い単位は求めない")

    def test_rejects_narrowed_query_and_unknown_direction(self):
        self.edit_tree(R_FIXED)
        narrow = _fix_ok()
        narrow["changes"][1]["coverage"] = {"how": {"patterns": ["return lo"], "fixed": True, "paths": ["stats.py"],
                                                    "count": "files"}}
        narrow["changes"][1]["closure"]["sites"] = narrow["changes"][1]["closure"]["sites"][:1]
        self.assert_rejected(narrow, R_CLAMP, "判定者が数えた母数は 2", "狭めている")
        bare = _fix_ok()
        got = self.accept(bare, judged=[])
        self.assertFalse(got["ok"])
        self.assertIn("coverage.how", got["reason"], "判定者の class_query も役の how も無い単位は拒む")
        bare["changes"][0]["coverage"] = {"how": R_JUDGED[0]["class_query"]["how"]}
        got = self.accept(bare, judged=[])
        self.assertIn("数えるものの向きが決まらない", got["reason"])

    def test_dry_take_lists_problems_and_writes_nothing(self):
        # 元 test_fix_accept_all.DryTakeCase: 乾いた照らしは誤りを problems に並べ、件数を書かない。通る返答は後で commit しても通る
        bad = _fix_ok()
        bad["changes"][1]["closure"]["sites"] *= 2
        got = self.accept(bad, commit=False)
        self.assertEqual((got["ok"], got["dry"], got["changes"]), (False, True, []), got)
        self.assertEqual(len(got["problems"]), 2, got)
        self.assertFalse((self.place / self.recount.COVERAGE_FILE).exists())
        self.edit_tree(R_FIXED)
        got = self.accept(_fix_ok(), commit=False)
        self.assertEqual((got["ok"], got["dry"]), (True, True), got)
        self.assertFalse((self.place / self.recount.COVERAGE_FILE).exists())
        self.assertIs(self.accept(_fix_ok())["ok"], True)
        self.assertTrue((self.place / self.recount.COVERAGE_FILE).is_file())

    def test_fixed_rev_counts_are_cached_in_the_place(self):
        self.edit_tree(R_FIXED)
        self.accept(_fix_ok(), commit=False)
        first = self.calls()
        self.accept(_fix_ok(), commit=False)
        self.assertEqual(self.calls() - first, 2, "修正前の版の 2 つは取り置きから読み、修正後の 2 つだけ数える")

    def test_budget_exhausted_is_a_reject_line(self):
        """1 周に数える問いを走らせる量の上限（COUNT_BUDGET）に達したら、問いを走らせずに『上限に達した』の行で拒む
        （元 works/.shared/core/graphloops/rules/review-loop.py:3304 COUNT_BUDGET・:3307 _run_query）"""
        self.edit_tree(R_FIXED)
        spent = {"round": 1, "calls": self.recount.COUNT_BUDGET["calls"], "seconds": 0.0}
        (self.place / self.recount.COUNT_BUDGET_FILE).write_text(json.dumps(spent), encoding="utf-8")
        got = self.accept(_fix_ok())
        self.assertFalse(got["ok"], got)
        self.assertIn(f"上限（{self.recount.COUNT_BUDGET['calls']} 回か {self.recount.COUNT_BUDGET['seconds']} 秒）に達した",
                      got["reason"])
        self.assertEqual(self.calls(), spent["calls"], "上限の後は走らせない")
        self.assertTrue(self.accept(_fix_ok(), round_=2)["ok"], "周が替われば数え直す")

    def test_zero_unit_is_not_rejected_as_narrowed(self):
        """判定の時に engine が 0 件と数えた単位（zero_keys）は、判定者の母数より修正前の数が少なくても『問いを狭めている』で
        拒まない（元 review-loop.py:2638・:2776-2777 の盤面の engine_zero）"""
        judged = [{"key": R_MEAN, "class_query": {"how": {"patterns": ["zzz-none"], "fixed": True, "paths": ["stats.py"],
                                                           "count": "lines"}, "counts": "population", "total": 2}}]
        reply = {"changes": [{**_fix_row(R_MEAN, 0)}], "not_done": []}
        got = self.accept(reply, judged=judged, owed={R_MEAN})
        self.assertFalse(got["ok"], got)
        self.assertIn("判定者が数えた母数は 2", got["reason"])
        self.assertIn("狭めている", got["reason"])
        got = self.accept(reply, judged=judged, owed={R_MEAN}, zero_keys={R_MEAN})
        self.assertTrue(got["ok"], got)

    def test_rejects_blank_interaction_check(self):
        """2 つの修正が同じファイルを触った時、interactions のそのファイルの checked が空同然なら拒む（元 review-loop.py:2690-2709）"""
        self.edit_tree(R_FIXED)
        reply = _fix_ok()
        reply["interactions"] = [{"surface": "stats.py", "checked": "済み"}]
        got = self.accept(reply)
        self.assertFalse(got["ok"], got)
        self.assertIn("interactions[stats.py] の checked が空同然", got["reason"])
        self.assertTrue(self.accept(_fix_ok())["ok"], "突き合わせた結果を書けば通す")

    def test_rejects_precedent_without_problem_or_source(self):
        """precedent は from_judge_row でなければ problem と source（verdict が not_found なら searched）を求める
        （元 review-loop.py:2725-2732）"""
        self.edit_tree(R_FIXED)
        bare = _fix_ok()
        bare["changes"][0]["precedent"] = {"verdict": "adopt", "reason": "標準の定義に合わせる"}
        self.assertIn(f"{R_MEAN[:60]}: precedent に problem と source", self.accept(bare)["reason"])
        unsourced = _fix_ok()
        unsourced["changes"][0]["precedent"] = {"problem": "平均の分母の誤り", "verdict": "adopt", "reason": "標準の定義に合わせる"}
        self.assertIn("precedent に problem と source", self.accept(unsourced)["reason"])
        unsearched = _fix_ok()
        unsearched["changes"][0]["precedent"] = {"problem": "平均の分母の誤り", "verdict": "not_found", "reason": "見つからない"}
        self.assertIn("precedent に problem と source", self.accept(unsearched)["reason"])
        unsearched["changes"][0]["precedent"]["searched"] = "標準ライブラリの文書と課題の一覧を引いた"
        self.assertTrue(self.accept(unsearched)["ok"], "not_found は searched が在れば通す")

    def test_fix_reply_reads_the_reply_file(self):
        import fixboard
        f = self.place / "fix-reply.json"
        f.write_text(json.dumps(_fix_ok(), ensure_ascii=False), encoding="utf-8")
        got, path = fixboard.fix_reply(f)
        self.assertEqual((len(got["changes"]), path), (2, f.resolve()))
        with self.assertRaises(self.recount.Unreadable):
            fixboard.fix_reply(None)


class RulebookSeamCase(unittest.TestCase):
    def test_render_heads_rejects_and_lang(self):
        """rulebook.render: 1 行目に載せた節と理由と決まりの sha、続けて拒否の理由のファイルの 1 行（rolekit.compose）、
        before・決まり・after・言語の 1 行の順。同じ入力からは同じバイト"""
        import rulebook
        parts = [("a", "- 決まり A", "いつも"), ("b", "- 決まり B", "いつも")]
        got = rulebook.render("refix", 1, parts, before=("頭",), after=("尻",), reject_file="/home/x/r.md", lang="言語")
        lines = got["text"].split("\n")
        head = json.loads(lines[0][len("<!-- works-prompt "):-len(" -->")])
        self.assertEqual(head, got["head"])
        self.assertEqual((head["role"], head["iteration"], [s["id"] for s in head["sections"]]), ("refix", 1, ["a", "b"]))
        self.assertEqual(head["rules_sha"], rulebook.sha("- 決まり A\n- 決まり B"))
        self.assertEqual(got["text"].split("\n", 1)[1],
                         rolekit.REJECT_LINE.format(path="/home/x/r.md") + "\n\n頭\n\n- 決まり A\n- 決まり B\n\n尻\n\n言語\n")
        self.assertEqual(rulebook.render("refix", 1, parts), rulebook.render("refix", 1, parts))
        self.assertNotIn("拒まれた", rulebook.render("refix", 1, parts)["text"])


if __name__ == "__main__":
    unittest.main()

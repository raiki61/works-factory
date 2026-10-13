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
  planrange.check_paths の行で拒む。lenses.render は役の定義の本文から、rulebook.render は fixboard.compose で指示書を組む
- ruling.prep・accept_rule: 置き場のファイルで回り、作業ツリーの控えは fixboard.snapshot、拒否の理由のファイル・言語の行・輪の回は
  引数、配線の誤りは ValueError
"""
import json
import pathlib
import subprocess
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
import gatemarks  # noqa: E402
import groups  # noqa: E402
import jsonfile  # noqa: E402
import leftovers  # noqa: E402
import lens  # noqa: E402
import unittrees  # noqa: E402
import writelog  # noqa: E402
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


class GateAsksCase(TempCase):
    """P241: 修正の置き場の判定の写しと関所の答え（answers.json の {decision, text, asked}）から引く、答えで戻る単位と外れる単位"""

    FORK = {"key": "q1", "kind": "fork", "status": "held", "origin": "u1", "options": ["a", "b"], "reason": "割れる"}

    def put(self, answers):
        (self.place / fixboard.JUDGMENT_FILE).write_text(json.dumps({"units": [{"key": "u1", "label": "block"}], "questions": [self.FORK]}),
                                                         encoding="utf-8")
        (self.place / fixboard.ANSWERS_FILE).write_text(json.dumps(answers, ensure_ascii=False), encoding="utf-8")

    def test_continue_returns_the_fork_origin(self):
        self.put({"decision": "approve", "text": "", "asked": [gatemarks.ask_text(self.FORK)]})
        self.assertEqual(fixboard.gate_asks(self.place), ({}, {"u1"}))
        self.assertEqual(fixboard.group_owed(self.place), ["u1"])
        self.put({"decision": "approve", "text": "", "asked": []})
        withheld, back = fixboard.gate_asks(self.place)
        self.assertEqual((set(withheld), back, fixboard.group_owed(self.place)), ({"u1"}, set(), []))


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


class RefixSeamCase(TempCase):
    """refix の継ぎ目: 差分の審査の材料と受け付けは置き場のファイルと引数の値で回る（盤面を開かない）。範囲の照らしは
    planrange.check_paths に承認済みの修正案の項目を値で渡す"""

    KEY_MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
    ITEMS = [{"item": 1, "unit_keys": [KEY_MEAN], "allowed_paths": ["stats.py"], "tests": [], "rewrite_tests": [],
              "out_of_scope": [{"glob": "vendored/**", "why": "外の写し"}]}]
    REVIEW = {"faces": [{"key": "stats.py mean: docstring が無い", "kind": "contract_drift", "where": "stats.py",
                         "cite": "return sum(xs)", "why": "分母を直したが docstring が平均の定義を書かず、読む側が古い式を想定する"}],
              "checks": [],
              "compliance": {"verdict": "pass", "items": [], "read": "修正案の項目 1 と差分の stats.py を読み、項目と差分を照らした"},
              "quality": {"verdict": "fail", "why": "faces に挙げた穴は修正案の項目への準拠の外の品質の穴で、準拠の行には結ばない"}}
    HANDLED = {"handled": [{"key": "stats.py mean: docstring が無い", "handled": "fixed", "how": "mean に docstring を足した",
                            "files": ["stats.py"]}]}

    def setUp(self):
        super().setUp()
        import refix
        self.refix = refix
        p = self.repo / "stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")

    def _cut_and_review(self):
        rf = self.refix
        got = rf.cut(self.place, 1, self.repo, self.rev, items=self.ITEMS, fix_reply={"changes": [], "not_done": []})
        self.assertTrue(got["ok"], got)
        out = rf.accept_review(self.REVIEW, self.place, self.rev, self.repo, n=1, items=self.ITEMS)
        self.assertTrue(out["ok"], out)
        p = self.repo / "stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("def mean(xs):\n", 'def mean(xs):\n    """算術平均"""\n'),
                     encoding="utf-8")

    def test_accept_fix_rejects_change_outside_the_items_range(self):
        """承認済みの修正案の項目の範囲の外を変えた手直しを拒み（planrange.check_paths と同じ行）、範囲の中なら通す"""
        import planrange
        import stopby
        rf = self.refix
        self._cut_and_review()
        (self.repo / "other.py").write_text("X = 1\n", encoding="utf-8")
        lines, rec = planrange.check_paths(self.place, ["other.py"], items=self.ITEMS, by=stopby.REFIX)
        self.assertTrue(rec["checked"])
        got = rf.accept_fix(self.HANDLED, self.place, self.rev, self.repo, n=1, items=self.ITEMS)
        self.assertFalse(got["ok"], got)
        self.assertEqual(got["reason"], rf.SCOPE_REJECT + "\n" + "\n".join(f"  - {x}" for x in lines))
        self.assertIsNone(fixboard.output(self.place, "p3.delta_fix"))
        (self.repo / "other.py").unlink()
        got = rf.accept_fix(self.HANDLED, self.place, self.rev, self.repo, n=1, items=self.ITEMS)
        self.assertTrue(got["ok"], got)
        self.assertEqual(fixboard.output(self.place, "p3.delta_fix"), self.HANDLED)

    def test_cut_and_accept_review_use_the_place(self):
        """cut は置き場に差分・状態・材料（brief）・作業ツリーの写しを書き、accept_review は 2 判定の欄を外した返答と控えを
        置き場に置く。欄が欠ければ拒み、何も置かない"""
        import deltamarks
        rf = self.refix
        got = rf.cut(self.place, 1, self.repo, self.rev, items=self.ITEMS, plan_review={"faces": []})
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["files"], ["stats.py"])
        self.assertEqual(rf.fix_delta(self.place)["file"], got["diff_file"])
        brief = json.loads(pathlib.Path(got["brief_file"]).read_text(encoding="utf-8"))
        self.assertEqual(pathlib.Path(got["brief_file"]).parent, self.place)
        self.assertEqual((brief["reads"]["out.p2.plan_review"], [it["item"] for it in brief["plan_items"]]), ({"faces": []}, [1]))
        self.assertTrue((self.place / rf.snapshot_name(1)).is_file())
        lacking = {k: v for k, v in self.REVIEW.items() if k != "quality"}
        bad = rf.accept_review(lacking, self.place, self.rev, self.repo, n=1, items=self.ITEMS)
        self.assertFalse(bad["ok"])
        self.assertTrue(bad["reason"].startswith(deltamarks.REJECT), bad["reason"])
        self.assertIn("quality", bad["reason"])
        self.assertEqual((fixboard.output(self.place, "p3.delta_review"), deltamarks.read(self.place)), (None, None))
        ok = rf.accept_review(self.REVIEW, self.place, self.rev, self.repo, n=1, items=self.ITEMS)
        self.assertEqual((ok["ok"], ok["owed"]), (True, 1))
        self.assertNotIn("quality", fixboard.output(self.place, "p3.delta_review"))
        self.assertEqual(deltamarks.read(self.place)["quality"]["verdict"], "fail")
        self.assertIn({"op": deltamarks.SAVED_OP, "compliance": "pass", "quality": "fail"}, _traced(self.place))


class LensesSeamCase(unittest.TestCase):
    """lenses.render: 役の定義の本文（engine.validator.agent_def が利用者の入れた plugin の agents/<役>.md から引いた body）から、
    レンズの節の指示書を組む。見出しは fixboard.ROLE_DEF_HEAD（元 rolekit の写し）"""

    def test_render_builds_prompt_from_the_role_definition(self):
        import os
        import lenses
        from engine.validator import agent_def
        row = lenses.LENSES[0]
        plugin, _, role = row["agent"].rpartition(":")
        with tempfile.TemporaryDirectory() as td:
            agents = pathlib.Path(td) / "agents"
            agents.mkdir()
            (agents / f"{role}.md").write_text("---\nname: x\nmodel: inherit\n---\n黙って失敗する所を探す役。\n",
                                               encoding="utf-8")
            with mock.patch.dict(os.environ, {plugin.upper().replace("-", "_") + "_ROOT": td}):
                got = agent_def(row["agent"])
        self.assertEqual(got["body"], "黙って失敗する所を探す役。")
        text = lenses.render(row, got["body"], "/home/x/fix-delta.patch", ["stats.py"], "LANG の 1 行")
        self.assertTrue(text.startswith(fixboard.ROLE_DEF_HEAD.format(agent=row["agent"]) + "\n\n黙って失敗する所を探す役。\n"))
        for w in (lenses.TASK_HEAD, lenses.REPLY_HEAD, "/home/x/fix-delta.patch", '["stats.py"]', row["lens"]):
            self.assertIn(w, text)
        self.assertNotIn("model: inherit", text)
        self.assertTrue(text.endswith("LANG の 1 行\n"))


class RulebookSeamCase(unittest.TestCase):
    def test_render_heads_rejects_and_lang(self):
        """rulebook.render: 1 行目に載せた節と理由と決まりの sha、続けて拒否の理由のファイルの 1 行（fixboard.compose）、
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
                         fixboard.REJECT_LINE.format(path="/home/x/r.md") + "\n\n頭\n\n- 決まり A\n- 決まり B\n\n尻\n\n言語\n")
        self.assertEqual(rulebook.render("refix", 1, parts), rulebook.render("refix", 1, parts))
        self.assertNotIn("拒まれた", rulebook.render("refix", 1, parts)["text"])


class LanekitSeamCase(TempCase):
    """lanekit.groups: 項目を共にする単位は同じ組（推移的）・組の順と組の中の順は入力の順。待ちの列と固定の枝の数は持たない
    （持ち主の決め no-queue）"""

    def test_groups_units_sharing_items_transitively_in_input_order(self):
        import lanekit
        rows = [("u3", ["i1"]), ("u1", ["i2"]), ("u2", ["i1", "i3"]), ("u5", []), ("u4", ["i3"]), ("u6", ["i2"])]
        self.assertEqual(lanekit.groups(rows), [["u3", "u2", "u4"], ["u1", "u6"], ["u5"]])

    def test_no_queue_and_no_fixed_lane_count(self):
        import lanekit
        for name in ("MAX_LANES", "queue_put", "take"):
            self.assertFalse(hasattr(lanekit, name), name)


class RulingSeamCase(TempCase):
    """ruling の継ぎ目: prep・accept_rule は置き場（pathlib.Path(board)）の conflicts.json・rule-tree.json・rejects-rule.json・
    prompt-rule.md で回る。作業ツリーの控えは fixboard.snapshot、前の拒否の理由のファイルと言語の行と輪の回は引数、
    配線の誤りは ValueError"""

    def setUp(self):
        super().setUp()
        import conflict
        import fixrules
        import rulebook
        import ruling
        self.conflict, self.ruling = conflict, ruling
        fr = LIB.parent / "workflows" / "fix" / "commands" / "fix-rules"
        for obj, name, value in ((rulebook, "CANON", fr / "common.md"), (fixrules, "SHARED", fr / "common.md"),
                                 (fixrules, "RULES_DIR", fr)):
            p = mock.patch.object(obj, name, value)
            p.start()
            self.addCleanup(p.stop)
        conflict.park(self.place, [CLAIM], source=conflict.FIX_SOURCE)

    VALUES = {"judgment_file": "/home/x/j.json", "policy_path": ""}

    def reply(self, **extra):
        return {"rulings": [{"id": "c1-1", "decision": "ask_human", "text": "方針の変更で人が決める", "limits": [], **extra}]}

    def test_prep_writes_prompt_and_tree_in_the_place(self):
        r = self.ruling
        got = r.prep(self.place, self.repo, self.VALUES, lang="日本語で書け")
        self.assertEqual(got, {"prompt_file": str(self.place / r.PROMPT), "iteration": 1})
        text = (self.place / r.PROMPT).read_text(encoding="utf-8")
        for w in ("`c1-1`", f"`{self.place / self.conflict.FILE}`", "日本語で書け"):
            self.assertIn(w, text)
        self.assertFalse(text.split("\n")[1].startswith(fixboard.REJECT_LINE[:10]), "1 回目は拒否の理由を名指さない")
        self.assertTrue((self.place / r.TREE).is_file(), "作業ツリーの姿の控えは置き場")
        bad = {"rulings": [{"id": "c9-9", "decision": "ask_human", "text": "方針の変更で人が決める", "limits": []}]}
        self.assertFalse(r.accept_rule(bad, self.place, self.rev, self.repo)["ok"])   # 回の数えは拒否の控え（rolekit）
        again = r.prep(self.place, self.repo, self.VALUES, reject_file="/home/x/reject.md")
        self.assertEqual(again["iteration"], 2)
        self.assertEqual((self.place / r.PROMPT).read_text(encoding="utf-8").split("\n")[1],
                         fixboard.REJECT_LINE.format(path="/home/x/reject.md"), "2 回目は 1 行目の後に拒否の理由のファイルを名指す")

    def test_accept_rule_applies_rulings_to_the_place(self):
        r = self.ruling
        r.prep(self.place, self.repo, self.VALUES)
        got = r.accept_rule(self.reply(), self.place, self.rev, self.repo)
        self.assertEqual((got["ok"], got["done"], got["reason"]), (True, True, ""), got)
        self.assertEqual(got["rulings_file"], str(self.place / self.conflict.RULINGS_FILE))
        self.assertEqual(self.conflict.unruled(self.place), [])
        row, = self.conflict.items(self.place)
        self.assertEqual(row["ruling"]["decision"], self.conflict.ASK)
        self.assertIn(self.conflict.RULE_OP, [x["op"] for x in _traced(self.place)])

    def test_accept_rule_rejects_then_gives_up_to_the_human(self):
        r = self.ruling
        r.prep(self.place, self.repo, self.VALUES)
        bad = {"rulings": [{"id": "c9-9", "decision": "ask_human", "text": "方針の変更で人が決める", "limits": []}]}
        for _ in range(r.GIVE_UP_AFTER - 1):
            got = r.accept_rule(bad, self.place, self.rev, self.repo)
            self.assertEqual((got["ok"], got["done"]), (False, False))
            self.assertIn("c9-9", got["reason"])
        self.assertEqual(len(self.conflict.unruled(self.place)), 1, "拒んだ回は積まない")
        (self.repo / "stats.py").write_text("# 変えた\n", encoding="utf-8")
        got = r.accept_rule(self.reply(), self.place, self.rev, self.repo)
        self.assertTrue(got["reason"].startswith(r.READONLY), got)
        self.assertEqual((got["ok"], got["done"]), (False, True))
        row, = self.conflict.items(self.place)
        self.assertEqual((row["ruling"]["decision"], row["ruling"]["text"]), (self.conflict.ASK, r.GIVE_UP_TEXT))

    def test_wiring_errors_are_value_errors(self):
        r = self.ruling
        with self.assertRaises(ValueError):
            r.accept_rule(self.reply(), self.place, self.rev, self.repo)   # rule-prep が走っていない
        self.conflict.apply_rulings(self.place, {"c1-1": {"decision": "ask_human", "text": "方針の変更で人が決める",
                                                          "limits": []}}, by="t")
        with self.assertRaises(ValueError):
            r.prep(self.place, self.repo, self.VALUES)   # 裁く申し出が無い

    def _rule_errs(self, row, item, briefs=None):
        """裁定 1 行 row を、申し出 item（id c1-1）への返答として ruling.problems に当てた文（grounds は置き場の中も名指せる。
        accept_rule と同じ roots）"""
        return self.ruling.problems({"rulings": [{"id": "c1-1", **row}]}, {"c1-1": {"id": "c1-1", **item}}, self.repo, "",
                                    (str(self.place),), briefs=briefs)

    def test_replace_query_is_tried_on_hits_misses_and_correct_lines(self):
        """F212: 裁定 replace_query の新しい問いは、hits に全部当たり、misses にも申し出の correct_lines にも当たらない時だけ通る
        （Semgrep の規則の試験の形）。which_is_right が query でない申し出には裁けない（元 works/tests/test_fix_rules.py:727
        test_replace_query_ruling_is_tried_on_examples の写し）"""
        item = {**CLAIM, "which_is_right": "query", "kind": "query_hits_fixed", "correct_lines": ["        return lo"]}

        def row(patterns, hits, misses):
            how = {"patterns": patterns, "fixed": True, "paths": ["stats.py"], "count": "lines"}
            return {"decision": "replace_query", "limits": [], "text": "上限の枝だけに当たる問いに置き換える",
                    "query": {"how": how, "counts": "defects", "hits": hits, "misses": misses}}
        good = row(["return lo  # hi"], ["        return lo  # hi"], ["        return hi"])
        self.assertEqual(self._rule_errs(good, item), [], "全部を満たす問いは通す")
        cases = ((row(["return lo  # hi"], ["        return hi"], []), "hits に当たらない"),
                 (row(["return lo  # hi"], ["        return lo  # hi"], ["        return lo  # hi"]), "misses に当たる"),
                 (row(["return lo"], ["        return lo  # hi"], ["        return hi"]), "correct_lines"))
        for bad, word in cases:
            with self.subTest(word=word):
                errs = self._rule_errs(bad, item)
                self.assertTrue(any(word in e for e in errs), errs)
        errs = self._rule_errs(good, {**CLAIM, "which_is_right": "request"})
        self.assertTrue(any("which_is_right が query の申し出だけ" in e for e in errs), errs)

    def test_fix_plan_item_needs_brief_grounds_and_no_limits(self):
        """F213: 裁定 fix_plan_item は範囲 limits を持たず、grounds にその単位の brief の行を名指す時だけ通り、受けた裁定には機械が
        plan_items（brief の項目の番号）と plan_units（その項目に載る単位の全部）を足す。機械が諦めた単位の申し出
        （source tdd-gave-up）への fix_code_as は grounds を要る（元 works/tests/test_conflict_kinds.py:270・277
        FixPlanItemRulingCase・:309 GaveUpRulingCase の写し）"""
        c = self.conflict
        brief = self.place / "brief-1.md"
        brief.write_text("# brief 1\n受け入れのテストは assertion で赤\n", encoding="utf-8")
        briefs = {KEY_A: [{"item": 1, "file": str(brief)}], KEY_B: [{"item": 1, "file": str(brief)}]}
        row = {"decision": c.REPLAN, "text": "受け入れのテストの赤の種類を exception に直す", "limits": [],
               "grounds": [f"{brief}:2"]}
        self.assertEqual(self._rule_errs(row, CLAIM, briefs), [])
        self.assertTrue(any("brief が無い" in e for e in self._rule_errs(row, CLAIM, {})))
        self.assertTrue(any("範囲を持たない" in e for e in self._rule_errs({**row, "limits": ["test_stats.py:2"]}, CLAIM, briefs)))
        for grounds in ([], ["stats.py:3"]):
            errs = self._rule_errs({**row, "grounds": grounds}, CLAIM, briefs)
            self.assertTrue(any(c.REPLAN in e and "grounds" in e and str(brief) in e for e in errs), (grounds, errs))
        code_as = {"decision": "fix_code_as", "text": "コードの返り値を hi に直せ", "limits": []}
        gave_up = {**CLAIM, "source": c.GAVE_UP_SOURCE, "which_is_right": "unknown", "kind": "needs_context"}
        self.assertTrue(any("grounds" in e and "fix_code_as" in e for e in self._rule_errs(code_as, gave_up)))
        self.assertEqual(self._rule_errs({**code_as, "grounds": ["stats.py:3", "test_stats.py:2"]}, gave_up), [])
        self.assertEqual(self._rule_errs(code_as, {**gave_up, "source": c.TDD_SOURCE}), [], "役の申し出は grounds なしで通る")
        self.ruling.prep(self.place, self.repo, self.VALUES)
        with mock.patch.object(self.ruling.planbrief, "by_unit_at", return_value=briefs):
            got = self.ruling.accept_rule({"rulings": [{"id": "c1-1", **row}]}, self.place, self.rev, self.repo)
        self.assertTrue(got["ok"], got)
        stored, = c.items(self.place)
        self.assertEqual((stored["ruling"][c.PLAN_ITEMS], stored["ruling"][c.PLAN_UNITS]), ([1], [KEY_A, KEY_B]))
        self.assertEqual(set(c.held_by_rulings(self.place)), {KEY_A, KEY_B}, "項目の単位の全部を直す義務から外す")


class FactchecksSeamCase(TempCase):
    """factchecks の継ぎ目: 事前の確かめと受け付けの事実の確かめは、置き場（board）のファイルと引数の値で回り、置き場を書かない
    （元 works/tests/test_fix_precheck.py の PrecheckCase の場合を写した。盤面の代わりに承認済みの修正案の項目 items を値で渡し、
    合意は置き場の trace.jsonl に置く）。直す義務は fixboard.fix_duty、書き込みの記録は引数 log、除くパスの頭は skip"""

    ITEM = {"item": 1, "unit_keys": [R_MEAN], "adds": [], "removes": [], "route": "direct", "tests": [], "rewrite_tests": [],
            "allowed_paths": ["docs/**"], "out_of_scope": []}

    def setUp(self):
        super().setUp()
        import factchecks
        self.fc = factchecks
        path = self.repo / "stats.py"
        text = path.read_text(encoding="utf-8")
        for old, new in R_FIXED.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
        self.reply = {"changes": [{"unit_key": R_MEAN, "files": ["stats.py"]}]}
        self.cfg = {"board": str(self.place), "repo": str(self.repo), "base_rev": self.rev, "tdd_state": "", "pass": "first"}

    def shas(self) -> dict:
        import hashlib
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(self.place.rglob("*")) if p.is_file()}

    def agree(self, paths):
        """確かめの節が書く合意の行（allow）を置き場の trace に直に置く"""
        import conflict
        fixboard.trace(self.place, conflict.ASKED_OP, id=1, item="1", status="answered", decision="allow",
                       granted_paths=paths, granted_tests=[], reason="直しに伴うので足してよい")

    def test_scope_reject_listed_and_place_untouched(self):
        import planscope
        before = self.shas()
        got = self.fc.precheck(self.cfg, self.reply, items=[self.ITEM])
        self.assertFalse(got["ok"])
        scope = [r["text"] for r in got["rejects"] if r["check"] == "scope"]
        self.assertTrue(any("stats.py" in t for t in scope), got)
        self.assertTrue(scope[0].startswith(planscope.REJECT_ASK), "事前の確かめは相談の節の道具なので、拒否の頭は相談を先の道に言う")
        self.assertEqual(self.shas(), before, "置き場を書かない")

    def test_place_agreement_counts(self):
        self.agree(["stats.py"])
        self.assertEqual(self.fc.precheck(self.cfg, self.reply, items=[self.ITEM]), {"ok": True, "rejects": []})

    def test_other_place_rows_do_not_count(self):
        """置き場の trace の allow の行だけが合意（前の形の記録 exchanges.jsonl を偽っても範囲は広がらない）"""
        (self.place / "exchanges.jsonl").write_text(json.dumps(
            {"id": 1, "item": "1", "status": "answered", "decision": "allow", "granted_paths": ["stats.py"],
             "granted_tests": [], "reason": "偽の合意の行"}) + "\n", encoding="utf-8")
        self.assertFalse(self.fc.precheck(self.cfg, self.reply, items=[self.ITEM])["ok"])

    def test_no_plan_items_is_not_scoped(self):
        self.assertEqual(self.fc.precheck(self.cfg, self.reply)["rejects"], [])
        self.assertTrue(self.fc.precheck(self.cfg, self.reply, items=[{**self.ITEM, "allowed_paths": ["stats.py"]}])["ok"])

    def test_scope_head_follows_the_consult_place(self):
        import consult
        import planscope
        args = (self.reply, [R_MEAN], self.place, self.rev, self.repo, "", "first")
        lines, _ = self.fc.check_plan_scope(*args, items=[self.ITEM])
        self.assertTrue(lines[0].startswith(planscope.REJECT), "相談の控えが無ければ申し出の道")
        consult.write_config(self.place, {"board": str(self.place), "repo": str(self.repo), "pass": "first",
                                          "items": {"1": {"unit_keys": [R_MEAN]}}})
        lines, _ = self.fc.check_plan_scope(*args, items=[self.ITEM], consult_place=self.place)
        self.assertTrue(lines[0].startswith(planscope.REJECT_ASK), lines)

    def test_writes_use_the_log_and_skip(self):
        log = self.place / writelog.LOG
        log.write_text("", encoding="utf-8")   # 記録の在る run（Edit・Write の行は無い）
        (self.repo / "vendored").mkdir()
        (self.repo / "vendored" / "x.py").write_text("x = 1\n", encoding="utf-8")
        got = self.fc.check_writes(self.reply, self.place, self.rev, self.repo, "")
        self.assertTrue(any("stats.py" in p for p in got["problems"]), got)
        self.assertTrue(any("vendored/x.py" in p for p in got["problems"]), got)
        got = self.fc.check_writes(self.reply, self.place, self.rev, self.repo, "", skip=SKIP)
        self.assertFalse(any("vendored/x.py" in p for p in got["problems"]), got)
        declared = {**self.reply, writes.FIELD: [{"path": "stats.py", "why": WHY}]}
        got = self.fc.check_writes(declared, self.place, self.rev, self.repo, "", log=log, skip=SKIP)
        self.assertEqual(got["problems"], [], got)
        self.assertNotIn(writes.FIELD, got["reply"])

    def test_fix_unit_keys_and_duty(self):
        got = self.fc.fix_unit_keys(self.reply, self.place, {R_MEAN, R_CLAMP})
        self.assertEqual(got, ([R_MEAN], {R_MEAN, R_CLAMP}, {}))
        self.assertIsNone(self.fc.fix_unit_keys({"changes": "x"}, self.place, set()))
        self.assertIsNone(self.fc.fix_unit_keys({"changes": [{"unit_key": 1}]}, self.place, set()))

    def test_no_loop_has_no_frozen_rejects(self):
        self.assertEqual(self.fc.check_frozen(self.place, "", self.repo, "first", base_rev=self.rev), [])

    def test_declared_files(self):
        rows = [{"files": [str(self.repo / "a" / ".." / "stats.py"), " docs/x.md ", "", 3]}]
        self.assertEqual(self.fc.declared_files(rows, self.repo), {"stats.py", "docs/x.md"})

    def run_main(self, allowed):
        """置き場に修正案の控え（planmarks.save の欄・p2.fix_plan.json・judgment.json）と相談の控えを置き、下書きの返答で main を
        子のプロセスで回す（修正役の指示書に書くコマンド `<python> factchecks.py <相談の控え> --reply <下書き>` の形）"""
        import subprocess
        import consult
        import planmarks
        planmarks.save(self.place, 1, [{"route": "direct", "tests": [], "rewrite_tests": [], "allowed_paths": allowed,
                                         "out_of_scope": []}])
        (self.place / f"{planmarks.NODE}.json").write_text(json.dumps(
            {"plan": [{"unit_keys": [R_MEAN], "approach": "分母を直す", "adds": [], "removes": []}]}, ensure_ascii=False),
            encoding="utf-8")
        (self.place / "judgment.json").write_text(json.dumps({"units": R_JUDGED}, ensure_ascii=False), encoding="utf-8")
        cfg = consult.write_config(self.place, {**self.cfg, "items": {"1": {"unit_keys": [R_MEAN]}}})
        draft = self.tmp / "draft.json"
        draft.write_text(json.dumps(self.reply, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, str(LIB / "factchecks.py"), str(cfg), "--reply", str(draft)], cwd=str(self.repo),
                           capture_output=True, text=True, encoding="utf-8")
        return r.returncode, r.stdout, r.stderr

    def test_main_reads_the_plan_in_the_place(self):
        import planscope
        code, out, err = self.run_main(["docs/**"])
        self.assertEqual(code, 1, out + err)
        got = json.loads(out)
        self.assertTrue(any(r["check"] == "scope" and "stats.py" in r["text"] and r["text"].startswith(planscope.REJECT_ASK)
                            for r in got["rejects"]), got)

    def test_main_passes_inside_the_plan(self):
        code, out, err = self.run_main(["stats.py"])
        self.assertEqual((code, json.loads(out)), (0, {"ok": True, "rejects": []}), out + err)

    def test_main_wiring_error_is_two(self):
        import subprocess
        r = subprocess.run([sys.executable, str(LIB / "factchecks.py"), str(self.place / "none.json")],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)



class FixgatesSeamCase(TempCase):
    """fixgates の継ぎ目: 盤面の b.work・b.dir/r<周> を置き場のパスに、writes.base_rev を fixboard.base_rev に、
    conflict.owed_units_but_asked を fixboard.owed_units_but_asked（値で受ける）に、entry.open_board を置き場のパスに替えた所"""

    MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
    ID = "test_stats.py::TestStats::test_mean_of_three"   # 種で赤（len-1 で割る）の既存のテスト
    FIELDS = [{"unit_keys": [MEAN], "route": "tdd", "route_why": "", "rewrite_tests": [], "refactor": {"declared": False, "why": ""},
               "tests": [{"id": ID, "behavior": "3 つの平均", "path": "p", "red_kind": "assertion", "red_why": "len-1"}]}]

    def setUp(self):
        super().setUp()
        import planmarks
        from lib.tests.test_blk_fix_tdd import PYTEST_LIKE
        planmarks.save(self.place, 1, self.FIELDS)
        self.suite = self.tmp / "suite.py"
        self.suite.write_text(PYTEST_LIKE, encoding="utf-8")
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")

    def test_ledger_cache_and_logs_live_in_the_place(self):
        """帳面・base の木の控え・一式のログは置き場の中だけに書き、skipped・guards・unchecked は置き場の帳面を読む"""
        import fixgates
        self.assertEqual(fixgates.problems(self.place, self.repo, self.rev, str(self.suite), 1), [])
        self.assertTrue((self.place / fixgates.BASE_CACHE).is_file())
        self.assertTrue((self.place / f"{fixgates.RUN}-first-1").is_dir())
        self.assertFalse((self.place / "r1").exists(), "盤面の周のフォルダは作らない")
        self.assertEqual(fixgates.problems(self.place, self.repo, self.rev, "", 2), [])
        self.assertEqual(json.loads((self.place / fixgates.LEDGER).read_text(encoding="utf-8"))["skipped"],
                         [{"pass": "first", "attempt": 2, "why": fixgates.NO_SUITE}])
        self.assertEqual(fixgates.skipped(self.place, pass_="first", attempt=2), [fixgates.NO_SUITE])
        self.assertEqual(fixgates.unchecked(self.place, pass_="first", attempt=2), [fixgates.NO_SUITE])
        self.assertEqual(git(self.repo, "status", "--porcelain"), "M stats.py", "作業ツリーに走らせた跡を残さない")

    def test_base_rev_and_duty_come_from_arguments(self):
        """修正前の版は fixboard.base_rev(state, base_rev) の順、直す義務は owed・withheld・returned の値で受ける"""
        import fixgates
        with mock.patch.object(fixgates.fixboard, "base_rev", wraps=fixboard.base_rev) as rev, \
                mock.patch.object(fixgates.fixboard, "owed_units_but_asked", wraps=fixboard.owed_units_but_asked) as duty:
            fixgates.problems(self.place, self.repo, "HEAD", "", 1, state={"inputs": {"review_rev": self.rev}},
                              owed=[self.MEAN], withheld=[self.MEAN], returned=())
        rev.assert_called_once_with({"inputs": {"review_rev": self.rev}}, "HEAD")
        duty.assert_called_once_with(self.place, [self.MEAN], withheld=[self.MEAN], returned=())
        why = fixgates.skipped(self.place, pass_="first", attempt=1)
        self.assertTrue(why and why[0].startswith(fixgates.OUT_OF_DUTY), why)

    def test_broken_fields_are_a_value_error(self):
        """凍結の印と食い違う欄の控えは、盤面を止める BoardGap でなく ValueError（止めるのは呼び手）"""
        import fixgates
        import marks
        marks.path_of("plan", self.place).write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            fixgates.problems(self.place, self.repo, self.rev, "", 1)
        self.assertFalse((self.place / fixgates.LEDGER).exists())


class LaneChecksSeamCase(TempCase):
    """元 tddlanes.py・fixlanes.py の枝の中の確かめのうち、ほかの lib/tests に同じ場合が無い物を、残る lib の関数で縛る
    （tddlanes・fixlanes は枝の輪・待ちの列・盤面の口だけになり lib/ に置かない。組ごとの子の run の 1 本の輪がこの口を読む）。
    - tddloop.step の log: 作業ツリーと書き込みの記録を別に受け、記録も申告も無い変更は段を拒み、記録が在れば通す
      （元 works/tests/test_tdd_lanes.py の TestLaneCommand.test_unrecorded_write_in_lane_is_rejected を写した）
    - factchecks.check_plan_scope・check_writes の since: 見る変更は since の木からの物だけで、その前の変更を範囲と出どころで
      照らさない。since の後に自分の out_of_scope を触れば今どおり拒む（元 works/tests/test_fix_lanes.py の TestItemStartPoint の
      test_second_item_is_checked_from_its_own_start・test_second_item_touching_its_own_out_of_scope_is_still_rejected を写した）"""

    def record(self, log, path):
        import os
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"tool_name": "Write", "path": os.path.realpath(path),
                                "file_sha": writes._sha(os.path.realpath(path))}) + "\n")

    def test_tdd_step_matches_writes_with_the_given_log(self):
        import tddloop
        from lib.tests.test_blk_fix_tdd import CLAMP, MEAN, NEW_TEST, OPEN, SUITE
        suite = self.tmp / "suite.py"
        suite.write_text(SUITE, encoding="utf-8")
        start = tddloop.start(self.place, self.repo, str(suite), OPEN)
        self.assertTrue(start["go"], start)
        state = start["state_file"]
        log = self.tmp / "run-writes.jsonl"   # 置き場の外の記録（既定の置き場の記録は使わない）
        log.write_text("", encoding="utf-8")
        got = tddloop.step(state, {"phase": "route", "units": [
            {"unit_key": MEAN, "route": "tdd"},
            {"unit_key": CLAMP, "route": "direct", "why": "文書の直しと同じで、先にテストを書けない単位"}]}, self.repo, log=log)
        self.assertTrue(got["ok"], got)
        tests = self.repo / "test_stats.py"
        tests.write_text(tests.read_text(encoding="utf-8").replace("\n\nif __name__", NEW_TEST + "\n\nif __name__"),
                         encoding="utf-8")
        reply = {"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                 "tests": ["test_stats.py::TestStats::test_mean_of_two"]}
        got = tddloop.step(state, dict(reply), self.repo, log=log)
        self.assertEqual((got["ok"], got["phase"]), (False, "test"), got)
        self.assertIn(writes.REJECT, got["reason"])
        self.assertIn("test_stats.py", got["reason"])
        self.record(log, tests)
        got = tddloop.step(state, dict(reply), self.repo, log=log)
        self.assertEqual((got["ok"], got["phase"]), (True, "fix"), got)

    def since_case(self):
        """1 つ目の項目の直し（test_stats.py に行を足し、新しい NOTES.md を作る。記録は無い）の後の木を since に取り、
        2 つ目の項目の直し（stats.py）を足す。2 つ目の項目は NOTES.md と test_stats.py を out_of_scope に持つ"""
        import factchecks
        tests = self.repo / "test_stats.py"
        tests.write_text(tests.read_text(encoding="utf-8") + "# 項目 1 の注記\n", encoding="utf-8")
        (self.repo / "NOTES.md").write_text("項目 1 の記録\n", encoding="utf-8")
        since = leftovers.snapshot(self.repo)
        stats = self.repo / "stats.py"
        text = stats.read_text(encoding="utf-8")
        for old, new in R_FIXED.items():
            text = text.replace(old, new)
        stats.write_text(text, encoding="utf-8")
        item = {"item": 2, "unit_keys": [R_MEAN], "adds": [], "removes": [], "route": "direct", "tests": [],
                "rewrite_tests": [], "allowed_paths": ["stats.py"],
                "out_of_scope": [{"glob": "NOTES.md", "why": "記録は項目 2 では触らない"},
                                 {"glob": "test_stats.py", "why": "試験は項目 2 では触らない"}]}
        reply = {"changes": [{"unit_key": R_MEAN, "files": ["stats.py"]}]}
        return factchecks, since, item, reply

    def test_plan_scope_looks_only_after_since(self):
        fc, since, item, reply = self.since_case()
        args = (reply, [R_MEAN], self.place, self.rev, self.repo, "", "first")
        lines, _ = fc.check_plan_scope(*args, items=[item])
        self.assertTrue(any("NOTES.md" in t for t in lines), "since が無ければ版からの変更を全部照らす")
        lines, _ = fc.check_plan_scope(*args, since=since, items=[item])
        self.assertEqual(lines, [], "since の前の変更は照らさない")
        (self.repo / "NOTES.md").write_text("項目 2 が書き足した\n", encoding="utf-8")
        lines, _ = fc.check_plan_scope(*args, since=since, items=[item])
        self.assertTrue(any("NOTES.md" in t for t in lines), lines)
        self.assertFalse(any("test_stats.py" in t for t in lines), "since の前に変えたファイルは照らさない")

    def test_plan_scope_counts_what_the_loop_fixed_before_since(self):
        """TDD の輪が直し終えた単位（stats.py の直しと adds・tests の test_mean_of_two）の後の木を since（段の頭）に取り、修正役が
        何も変えずにその単位の行だけを返せば、欠けにしない（修正役の指示書は輪の単位を直し直させない。較正 clamp-above）"""
        import factchecks
        from lib.tests.test_blk_fix_tdd import NEW_TEST
        tests = self.repo / "test_stats.py"
        tests.write_text(tests.read_text(encoding="utf-8").replace("\n\nif __name__", NEW_TEST + "\n\nif __name__"),
                         encoding="utf-8")
        stats = self.repo / "stats.py"
        text = stats.read_text(encoding="utf-8")
        for old, new in R_FIXED.items():
            text = text.replace(old, new)
        stats.write_text(text, encoding="utf-8")
        since = leftovers.snapshot(self.repo)
        tid = "test_stats.py::TestStats::test_mean_of_two"
        item = {"item": 1, "unit_keys": [R_MEAN], "removes": [], "route": "tdd", "tests": [{"id": tid}], "rewrite_tests": [],
                "adds": [{"kind": "test", "name": tid, "canonical": "test_stats.py に新設"}],
                "allowed_paths": ["stats.py", "test_stats.py"], "out_of_scope": []}
        reply = {"changes": [{"unit_key": R_MEAN, "files": ["stats.py", "test_stats.py"]}]}
        args = (reply, [R_MEAN], self.place, self.rev, self.repo, "", "first")
        lines, _ = factchecks.check_plan_scope(*args, since=since, items=[item])
        self.assertEqual(lines, [])

    def test_writes_look_only_after_since(self):
        fc, since, _, reply = self.since_case()
        log = self.place / writelog.LOG
        log.write_text("", encoding="utf-8")
        got = fc.check_writes(reply, self.place, self.rev, self.repo, "")
        self.assertTrue(any("NOTES.md" in p for p in got["problems"]), got)
        got = fc.check_writes(reply, self.place, self.rev, self.repo, "", since=since)
        self.assertTrue(any("stats.py" in p for p in got["problems"]), got)
        self.assertFalse(any("NOTES.md" in p or "test_stats.py" in p for p in got["problems"]), got)
        self.record(log, self.repo / "stats.py")
        self.assertEqual(fc.check_writes(reply, self.place, self.rev, self.repo, "", since=since)["problems"], [])


class DeltaSeamCase(TempCase):
    """差分の審査・レンズ・手直しの scripts が呼ぶ fixboard の口: 深さの控えから審査を省く理由、受け付けの返りと 3 回目の諦め、
    手直しと審査の返答の照らし（元 review-loop.py の delta_fix_output・delta_review_output）、組ごとの修正役の返答のまとめ、
    手直しの指示書の組み立て、始めの木の選び"""

    KEY = "stats.py mean: 分母が len(xs) - 1 になっている"
    FACE = "stats.py mean: docstring が無い"

    def test_redepth_reads_the_rows_of_the_place(self):
        import depth
        self.assertEqual(fixboard.redepth(self.place, self.repo), "")
        fixboard.write_json(self.place / fixboard.DEPTH_FILE, [{"unit_id": "a", "depth": depth.LIGHT, "why": "x"}])
        self.assertTrue(fixboard.redepth(self.place, self.repo).startswith("軽量で省いた"))
        raised = fixboard.read_json(self.place / fixboard.DEPTH_RAISED_FILE)
        self.assertEqual(raised["units"]["a"]["depth"], depth.LIGHT)
        self.assertIn("触るファイル", raised["counted"])
        fixboard.write_json(self.place / fixboard.DEPTH_FILE, [{"unit_id": "a", "depth": depth.LIGHT, "why": "x"},
                                                               {"unit_id": "b", "depth": depth.STANDARD, "why": "y"}])
        self.assertEqual(fixboard.redepth(self.place, self.repo), "")
        fixboard.write_json(self.place / fixboard.DEPTH_FILE, [])
        self.assertEqual(fixboard.redepth(self.place, self.repo), "")
        fixboard.write_json(self.place / fixboard.DEPTH_FILE, [{"unit_id": "a", "depth": "中くらい"}])
        with self.assertRaises(ValueError):
            fixboard.redepth(self.place, self.repo)

    def test_redepth_raises_on_the_signals_after_the_fix(self):
        """修正の後の信号（申し出の在る単位・2 回目の修正・修正役の異議・広い実際の差分）で軽量の単位を標準へ上げ、審査を省かない
        （元 depth.raise_）"""
        import conflict
        import depth
        light = [{"unit_id": "a", "depth": depth.LIGHT, "why": "x"}]
        fixboard.write_json(self.place / fixboard.GROUPS_FILE, {"groups": [], "out_dir": str(self.place / "groups"),
                                                                "start_tree": leftovers.snapshot(self.repo)})

        def raised(why_part):
            fixboard.write_json(self.place / fixboard.DEPTH_FILE, light)
            self.assertEqual(fixboard.redepth(self.place, self.repo), "")
            doc = fixboard.read_json(self.place / fixboard.DEPTH_RAISED_FILE)
            self.assertEqual(doc["units"]["a"]["depth"], depth.STANDARD)
            self.assertTrue(any(why_part in w for w in doc["units"]["a"]["why"]), doc)
        fixboard.write_json(self.place / fixboard.ONLY_ITEMS_FILE, ["1"])
        raised("案の直し")
        fixboard.write_json(self.place / fixboard.ONLY_ITEMS_FILE, [])
        fixboard.write_json(self.place / fixboard.RULED_REPLY_FILE, {"rejudge_requested": "単位の見立てが違う"})
        raised("異議")
        (self.place / fixboard.RULED_REPLY_FILE).unlink()
        for n in range(depth.MAX_PATHS + 1):
            (self.repo / f"wide{n}.py").write_text("X = 1\n", encoding="utf-8")
        raised("触るファイル")
        for n in range(depth.MAX_PATHS + 1):
            (self.repo / f"wide{n}.py").unlink()
        conflict.park(self.place, [{"unit_key": "a", "between": ["stats.py:9", "test_stats.py:8"],
                                    "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
                                    "which_is_right": "request", "kind": "unnamed_test_broke"}], source=conflict.FIX_SOURCE)
        raised("食い違い")

    def test_accept_out_writes_reasons_and_gives_up_on_the_third(self):
        self.assertEqual(fixboard.accept_out(self.place, "x-accept", {"ok": True}),
                         {"ok": True, "done": True, "reason": "", "reason_file": ""})
        self.assertEqual(fixboard.last_reject_file(self.place, "x-accept"), "")
        for k in (1, 2, 3):
            out = fixboard.accept_out(self.place, "x-accept", {"ok": False, "reason": f"理由 {k}"})
            self.assertEqual((out["ok"], out["done"]), (False, k == 3))
            self.assertEqual(pathlib.Path(out["reason_file"]).read_text(encoding="utf-8"), f"理由 {k}\n")
            self.assertEqual(fixboard.last_reject_file(self.place, "x-accept"), out["reason_file"])

    def _reviewed(self):
        fixboard.write_json(fixboard.out_file(self.place, "p3.delta_review"), {"faces": [
            {"key": self.FACE, "kind": "contract_drift", "where": "stats.py", "cite": "return sum(xs)", "why": "w" * 20}],
            "checks": [{"key": "plan-face-1", "closed": False, "why": "w" * 20}]})

    def test_delta_fix_problems_answer_every_owed_key_once(self):
        self._reviewed()
        ok = {"handled": [{"key": self.FACE, "handled": "fixed", "how": "h", "files": ["stats.py"]},
                          {"key": "plan-face-1", "handled": "declared", "how": "h"}]}
        self.assertEqual(fixboard.delta_fix_problems(self.place, 1, ok), [])
        bad = {"handled": [{"key": self.FACE, "handled": "fixed", "how": "h", "files": []},
                           {"key": "知らない穴の key", "handled": "declared", "how": "h"}]}
        got = fixboard.delta_fix_problems(self.place, 1, bad)
        self.assertEqual(len(got), 3, got)
        self.assertTrue(any("plan-face-1" in x and "応答が無い" in x for x in got), got)
        self.assertTrue(any("files が空" in x for x in got), got)

    def test_delta_review_problems_check_where_cite_and_checks(self):
        fixboard.write_json(fixboard.loop_file(self.place, "fix_delta"), {"file": "", "files": ["stats.py"]})
        face = {"key": self.FACE, "kind": "contract_drift", "where": "stats.py", "cite": "def mean(xs):", "why": "w" * 20}
        fix_reply = {"plan_faces": [{"key": "pf-1", "handled": "absorbed"}, {"key": "pf-2", "handled": "declared"}]}
        ok = {"faces": [face], "checks": [{"key": "pf-1", "closed": True, "why": "w" * 20}]}
        self.assertEqual(fixboard.delta_review_problems(self.place, 1, ok, self.repo, fix_reply=fix_reply), [])
        bad = {"faces": [{**face, "where": "other.py"}, {**face, "key": "k2-------", "cite": "無い字列の引用"},
                         {**face, "key": "k3-------", "kind": "policy"}], "checks": []}
        got = fixboard.delta_review_problems(self.place, 1, bad, self.repo, fix_reply=fix_reply)
        self.assertEqual(len(got), 4, got)
        self.assertTrue(any("pf-1" in x and "検算が無い" in x for x in got), got)
        self.assertIn("faces_none", fixboard.delta_review_problems(self.place, 1, {"faces": [], "checks": []}, self.repo)[0])

    def test_group_fix_reply_merges_the_groups_in_order(self):
        out_dir = self.place / "groups"
        for gid, key in (("g1", "a"), ("g2", "b")):
            reply = fixboard.write_json(self.tmp / f"{gid}-reply.json", {"changes": [{"unit_key": key}], "not_done": [],
                                                                      "plan_faces": [{"key": f"pf-{key}"}]})
            fixboard.write_json(out_dir / gid / fixboard.RESULT_FILE, {"group_id": gid, "reply_file": str(reply)})
        fixboard.write_json(self.place / fixboard.GROUPS_FILE, {"groups": [{"group_id": "g1"}, {"group_id": "g3"},
                                                                          {"group_id": "g2"}], "out_dir": str(out_dir)})
        got = json.loads(fixboard.group_fix_reply(self.place).read_text(encoding="utf-8"))
        self.assertEqual(([c["unit_key"] for c in got["changes"]], [f["key"] for f in got["plan_faces"]]),
                         (["a", "b"], ["pf-a", "pf-b"]))
        fixboard.write_json(self.place / fixboard.GROUPS_FILE, {"groups": [{"group_id": "g3"}], "out_dir": str(out_dir)})
        self.assertIsNone(fixboard.group_fix_reply(self.place))

    def test_refix_prompt_fills_the_head_and_names_the_reject_file(self):
        import refixrules
        import rulebook
        rules, canon = self.tmp / "refix.md", self.tmp / "common.md"
        rules.write_text("".join(f"<!-- セクション {s} -->\n{s} の本文 <<brief_file>>\n" if s.startswith("refix-head") else
                                 f"<!-- セクション {s} -->\n{s} の本文\n"
                                 for s in ("refix-head-1", "refix-head-2", "refix-remap", "refix-keep", "refix-reply",
                                           "refix-tail-1", "refix-tail-2")), encoding="utf-8")
        canon.write_text("<!-- セクション core-fix -->\n直し方\n<!-- セクション core-conflict -->\n申し出\n", encoding="utf-8")
        with mock.patch.object(refixrules, "RULES", rules), mock.patch.object(rulebook, "CANON", canon):
            text = fixboard.refix_prompt(2, {"brief_file": "/b.json", "diff_file": "/d.patch", "policy_path": "",
                                             "request_file": "/req.md"},
                                         reject_file="/r.md", iteration=2, lang="言語の 1 行")
        self.assertIn(fixboard.REJECT_LINE.format(path="/r.md"), text)
        import fixrules
        for line in fixrules.start_lines({"policy_path": "", "request_file": "/req.md"}):
            self.assertLess(text.index(line), text.index("refix-head-2 の本文"), "始めの記録の 2 行は役の頭の前（修正役と同じ）")
        for w in ("refix-head-2 の本文 `/b.json`", "直し方", "refix-tail-2 の本文", "言語の 1 行"):
            self.assertIn(w, text)
        self.assertNotIn("core-conflict", text)
        self.assertNotIn("\n申し出\n", text)
        self.assertNotIn("refix-tail-1", text)
        self.assertLess(text.index("refix-keep の本文"), text.index("`receiving-code-review`"), "座は手直しだけの決まりの後")
        self.assertLess(text.index("`receiving-code-review`"), text.index("refix-reply の本文"))

    def test_start_tree_prefers_groups_then_the_ignored_record(self):
        self.assertEqual(fixboard.start_tree(self.place), "")
        leftovers.record_ignored(self.place, self.repo)
        self.assertEqual(fixboard.start_tree(self.place), leftovers.head_tree(self.place))
        fixboard.write_json(self.place / fixboard.GROUPS_FILE, {"groups": [], "start_tree": "abc"})
        self.assertEqual(fixboard.start_tree(self.place), "abc")
        import rolekit
        self.assertIn("日本語", rolekit.lang_line({"lang": "日本語"}))
        self.assertIn(rolekit.LANG_DEFAULT, rolekit.lang_line({}))

    def test_delta_review_rejects_every_plan_only_kind(self):
        """差分の審査の穴の kind が事前審査だけの語なら 1 行で拒む: regression・policy は後の段が人に聞く、precedent は判定者の
        先行例が渡っていない（元 review-loop.py:3152-3160 の HUMAN_FACE_KINDS・PLAN_ONLY_FACE_KINDS。元の試験
        works/tests/test_blk_tests_delta.py:683 test_review_policy_kind_rejected）"""
        fixboard.write_json(fixboard.loop_file(self.place, "fix_delta"), {"file": "", "files": ["stats.py"]})
        face = {"key": self.FACE, "kind": "contract_drift", "where": "stats.py", "cite": "def mean(xs):", "why": "w" * 20}
        self.assertEqual(fixboard.delta_review_problems(self.place, 1, {"faces": [face], "checks": []}, self.repo), [])
        for kind, why in (("regression", "後の段が人に聞く"), ("policy", "後の段が人に聞く"), ("precedent", "先行例")):
            with self.subTest(kind):
                got = fixboard.delta_review_problems(self.place, 1, {"faces": [{**face, "kind": kind}], "checks": []},
                                                     self.repo)
                self.assertEqual(len(got), 1, got)
                self.assertIn(f"'{kind}' は事前審査だけの語", got[0])
                self.assertIn(why, got[0])

    def test_redepth_raises_on_parked_given_up_unanswered_and_broken_store(self):
        """修正の後の信号のうち、受け付けが最後の回に止めた単位（trace の conflict.ACCEPT_PARKED_OP）・組の結末 given_up（join.json）・
        答えていない修正前の関所の問い（gatemarks.pending）・読めない食い違いの控えで、軽量の単位を標準へ上げて審査を省かない
        （元 works/darkfactory/lib/depth.py:268 の signals。元の試験 works/tests/test_depth.py の BoardReadCase の
        test_signals_conflicts_and_parked・test_signals_broken_conflicts_raise_all・test_signals_unanswered_questions_raise_all）"""
        import conflict
        import depth
        light = [{"unit_id": "a", "depth": depth.LIGHT, "why": "x"}, {"unit_id": "b", "depth": depth.LIGHT, "why": "y"}]
        fixboard.write_json(self.place / fixboard.GROUPS_FILE, {"groups": [], "out_dir": str(self.place / "groups"),
                                                                "start_tree": leftovers.snapshot(self.repo)})

        def raised(why_part, units=("a", "b")):
            fixboard.write_json(self.place / fixboard.DEPTH_FILE, light)
            self.assertEqual(fixboard.redepth(self.place, self.repo), "")
            doc = fixboard.read_json(self.place / fixboard.DEPTH_RAISED_FILE)
            for k in ("a", "b"):
                want = depth.STANDARD if k in units else depth.LIGHT
                self.assertEqual(doc["units"][k]["depth"], want, (why_part, k, doc))
            for k in units:
                self.assertTrue(any(why_part in w for w in doc["units"][k]["why"]), doc)

        fixboard.write_json(self.place / fixboard.DEPTH_FILE, light)
        self.assertTrue(fixboard.redepth(self.place, self.repo).startswith("軽量で省いた"), "信号が無ければ省く")
        fixboard.trace(self.place, conflict.ACCEPT_PARKED_OP, unit_keys=["a"])
        raised("最後の回に止めた", units=("a",))
        (self.place / "trace.jsonl").unlink()
        fixboard.write_json(self.place / fixboard.JOIN_FILE, {"groups": [], "units": [
            {"unit_id": "b", "group_id": "g1", "status": "given_up", "reason": "3 回目の拒否で諦めた"}]})
        raised("最後の回に止めた", units=("b",))
        (self.place / fixboard.JOIN_FILE).unlink()
        fixboard.write_json(self.place / fixboard.JUDGMENT_FILE, {"units": [], "questions": [
            {"key": "q1", "kind": "fork", "status": "held", "origin": "zz", "reason": "決まらない"}]})
        raised("答えていない問い q1")
        (self.place / fixboard.JUDGMENT_FILE).unlink()
        (self.place / conflict.FILE).write_text("{壊れた", encoding="utf-8")
        raised("食い違いの控えが読めない")

    def test_refix_prompt_names_the_policy_and_ends_with_the_language_line(self):
        """手直しの役の指示書の並び: 1 行目の機械の頭 → 前の回の拒否の 1 行 → 始めの記録の 2 行 → 役の頭（人の方針の文書の置き場を
        名指す）→ 書く役の決まりの正本（申し出の決まりは載せない）→ 読み替え → 手直しだけの決まり → receiving-code-review の座 →
        返す形 → 返答の後に当たる物 → 末尾に言語の 1 行。1 回目の役の頭だけが plan_items・compliance・ruled_paths を読ませる
        （元 works/blk-refix/lib/refixrules.py:36 の parts と、元の試験 works/tests/test_blk_refix.py:613
        test_refix_head_names_plan_items_and_compliance）"""
        import fixrules
        import refixrules
        import rulebook
        real = rulebook.sections(LIB.parent / "workflows" / "fix" / "commands" / "fix-rules" / "refix.md")
        for w in ("`plan_items`", "`compliance`", "`ruled_paths`"):
            self.assertIn(w, real["refix-head-1"])
            self.assertNotIn(w, real["refix-head-2"])
        rules, canon = self.tmp / "refix.md", self.tmp / "common.md"
        rules.write_text("".join(f"<!-- セクション {s} -->\n{s} の本文 方針 <<policy_path>>\n" if s.startswith("refix-head") else
                                 f"<!-- セクション {s} -->\n{s} の本文\n"
                                 for s in ("refix-head-1", "refix-head-2", "refix-remap", "refix-keep", "refix-reply",
                                           "refix-tail-1", "refix-tail-2")), encoding="utf-8")
        canon.write_text("<!-- セクション core-fix -->\n直し方\n<!-- セクション core-conflict -->\n申し出\n", encoding="utf-8")
        values = {"brief_file": "/b.json", "diff_file": "/d.patch", "policy_path": "/frozen/policy.md",
                  "request_file": "/req.md"}
        with mock.patch.object(refixrules, "RULES", rules), mock.patch.object(rulebook, "CANON", canon):
            text = fixboard.refix_prompt(1, values, reject_file="/r.md", iteration=2, lang="言語の 1 行")
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith(rulebook.HEADER.split("{")[0]), lines[0])
        self.assertEqual(lines[1], fixboard.REJECT_LINE.format(path="/r.md"), "前の回の拒否は頭の次の 1 行目で名指す")
        self.assertEqual(lines[-1], "言語の 1 行", "指示書の末尾は言語の 1 行")
        self.assertIn("refix-head-1 の本文 方針 `/frozen/policy.md`", text)
        marks = [*fixrules.start_lines(values), "refix-head-1 の本文", "直し方", "refix-remap の本文", "refix-keep の本文",
                 "`receiving-code-review`", "refix-reply の本文", "refix-tail-1 の本文", "言語の 1 行"]
        at = [text.index(m) for m in marks]
        self.assertEqual(at, sorted(at), list(zip(marks, at)))
        self.assertNotIn("\n申し出\n", text)




class GroupScriptsSeamCase(TempCase):
    """fixboard の組の分けと戻し・返す節の欄（fix の prep・join・tdd-unit・conflict-check・assert-changed・collect が呼ぶ口）"""

    def test_owed_keys_are_open_units_without_forks(self):
        judgment = {"units": [{"key": "A", "label": "block"}, {"key": "B", "label": "suggest", "disposition": "do-now"},
                              {"key": "C", "label": "suggest"}, {"key": "D", "label": "block"}, {"key": "E", "label": "block"}],
                    "questions": [{"kind": "fork", "status": "held", "origin": "D", "depends": ["E"]},
                                  {"kind": "fork", "status": "decided", "origin": "A"}]}
        self.assertEqual(fixboard.owed_keys(judgment), ["A", "B"])
        self.assertEqual(fixboard.owed_keys(None), [])

    def test_child_allowed_rows_share_the_row_check_with_collect(self):
        """#304: 組の子の結果の許しの訳は join の和と collect（allowed_test_rows）が同じ口で読む。path・permit の無い行と
        ALLOWED_SOURCES に無い source の行はどちらにも入らない"""
        good = {"path": "tests/t.py", "permit": "plan-1", "source": "plan"}
        result = {"allowed_tests": [good, {"permit": "plan-2", "source": "plan"}, {"path": "tests/u.py", "source": "plan"},
                                    {"path": "tests/v.py", "permit": "x-1", "source": "guess"}, {"path": "", "permit": "p", "source": "plan"},
                                    {"path": 7, "permit": "p", "source": "plan"}, {"path": "tests/w.py", "permit": 3, "source": "plan"},
                                    "壊れた行", good]}
        self.assertEqual(fixboard.child_allowed_rows(result), [good, good])
        self.assertEqual(fixboard.allowed_test_rows(self.place, [result]), [good])
        self.assertEqual((fixboard.child_allowed_rows(None), fixboard.child_allowed_rows({"allowed_tests": None})), ([], []))

    def test_fix_groups_join_units_through_items(self):
        items = [{"item": 1, "unit_keys": ["A", "C"]}, {"item": 2, "unit_keys": ["C", "D"]}, {"item": 3, "unit_keys": ["B"]}]
        got = fixboard.fix_groups(["A", "B", "C", "D", "E"], items)
        self.assertEqual([(g["group_id"], g["unit_ids"], g["items"]) for g in got],
                         [("g1", ["A", "C", "D"], [1, 2]), ("g2", ["B"], [3]), ("g3", ["E"], [])])
        self.assertEqual([g["unit_ids"] for g in fixboard.fix_groups(["A", "B", "C"], items, ["3"])], [["B"]])
        self.assertEqual([g["unit_ids"] for g in fixboard.fix_groups(["A", "B"], None)], [["A"], ["B"]])

    def test_parallel_needs_two_groups_no_lane_switch_and_a_remote(self):
        two = [{"group_id": "g1"}, {"group_id": "g2"}]
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            self.assertFalse(fixboard.parallel(two, [], repo))
            subprocess.run(["git", "remote", "add", "origin", str(repo / "origin.git")], cwd=repo, check=True)
            self.assertTrue(fixboard.parallel(two, [], repo))
            self.assertFalse(fixboard.parallel(two, ["tdd_lanes"], repo))
            self.assertFalse(fixboard.parallel(two[:1], None, repo))

    def test_join_rows_keep_child_status_only_for_returned_groups(self):
        gs = [{"group_id": "g1", "unit_ids": ["A", "B"]}, {"group_id": "g2", "unit_ids": ["C"]}]
        result = {"units": [{"unit_id": "A", "status": "given_up", "reason": "3 回拒まれた"}]}
        rows, units = fixboard.join_rows(gs, {"g1": (result, True, ""), "g2": (result, False, "当たらない")})
        self.assertEqual([r["returned"] for r in rows], [True, False])
        self.assertEqual([(u["unit_id"], u["status"]) for u in units], [("A", "given_up"), ("B", "not_done"), ("C", "not_done")])
        self.assertEqual(units[2]["reason"], "当たらない")
        rows, _ = fixboard.join_rows(gs[:1], {})
        self.assertEqual(rows[0]["reason"], fixboard.NO_RESULT)

    def test_tdd_units_fill_groups_without_a_loop(self):
        row = {"unit_key": "A"}
        got = fixboard.tdd_units([{"group_id": "g1"}, {"group_id": "g2"}],
                                 {"g1": {"tdd": {"ran": True, "reason": "", "suite": "s", "units": [row]}}, "g2": None})
        self.assertEqual(got[0], {"group_id": "g1", "ran": True, "reason": "", "suite": "s", "reused": {}, "units": [row]})
        self.assertEqual((got[1]["ran"], got[1]["units"], got[1]["reason"]), (False, [], fixboard.NO_RESULT))

    def test_cited_rows_drop_claims_whose_lines_are_gone(self):
        row = {"unit_key": "A", "between": ["stats.py:9", "test_stats.py:1"], "why_both_cannot_hold": "x" * 12,
               "which_is_right": "code"}
        gone = {**row, "between": ["stats.py:900", "test_stats.py:1"]}
        ok, dropped = fixboard.cited_rows([row, gone, {"unit_key": "B"}], self.repo)
        self.assertEqual(ok, [row])
        self.assertEqual(len(dropped), 2)

    def test_changed_problem_and_declared_files(self):
        self.assertEqual(fixboard.declared_files([{"changes": [{"files": ["./a.py", "b/c.py"]}]}, {"changes": []}]),
                         ["a.py", "b/c.py"])
        with self.assertRaises(ValueError):
            fixboard.declared_files([{"changes": [{"files": [""]}]}])
        self.assertEqual(fixboard.changed_problem(["a.py"], ["a.py", "b.py"]), (True, ""))
        ok, why = fixboard.changed_problem(["a.py", "c.py"], ["a.py"])
        self.assertFalse(ok)
        self.assertIn("c.py", why)
        self.assertEqual(fixboard.changed_problem([], ["a.py"]), (False, fixboard.NOT_DECLARED))
        ok, why = fixboard.changed_problem([], [], {"A": "人の答え待ち"})
        self.assertTrue(ok)
        self.assertIn("A（人の答え待ち）", why)

    def test_touched_since_and_run_diff_skip_the_given_head(self):
        start = leftovers.snapshot(self.repo)
        (self.repo / "stats.py").write_text("X = 1\n", encoding="utf-8")
        (self.repo / "vendored").mkdir()
        (self.repo / "vendored" / "w.txt").write_text("w\n", encoding="utf-8")
        self.assertEqual(fixboard.touched_since(self.repo, start, SKIP), ["stats.py"])
        self.assertEqual(fixboard.touched_since(self.repo, start), ["stats.py", "vendored/w.txt"])
        diff = fixboard.run_diff(self.repo, "HEAD", SKIP)
        self.assertIn("b/stats.py", diff)
        self.assertNotIn("vendored", diff)
        self.assertIn("vendored/w.txt", fixboard.run_diff(self.repo))

    def test_diff_file_points_at_the_reason_when_empty_or_unreadable(self):
        place = self.repo.parent / "place"
        path, text, why = fixboard.diff_file(self.repo, lambda: "HEAD", place, "x.diff", "x-none.txt")
        self.assertEqual((path.name, text, why), ("x-none.txt", "", ""))
        self.assertEqual(path.read_text(encoding="utf-8"), fixboard.DIFF_EMPTY.format(base="HEAD") + "\n")

        def no_base():
            raise ValueError("起点が無い")
        path, text, why = fixboard.diff_file(self.repo, no_base, place, "x.diff", "x-none.txt")
        self.assertEqual(text, "")
        self.assertIn("ValueError: 起点が無い", why)
        self.assertEqual(path.read_text(encoding="utf-8"), why + "\n")
        (self.repo / "stats.py").write_text("X = 1\n", encoding="utf-8")
        path, text, why = fixboard.diff_file(self.repo, lambda: "HEAD", place, "x.diff", "x-none.txt")
        self.assertEqual((path.name, why), ("x.diff", ""))
        self.assertEqual(path.read_text(encoding="utf-8"), text)
        self.assertIn("b/stats.py", text)

    def test_collect_fields(self):
        rows = [{"unit_key": "A", "ruling": {"decision": "fix_plan_item", "plan_items": [2]}},
                {"unit_key": "B", "ruling": {"decision": "fix_plan_item"}},
                {"unit_key": "C", "ruling": {"decision": "ask_human"}}]
        self.assertEqual(fixboard.replan_items(rows, [{"unit_ids": ["B"], "items": [3]}]), ["2", "3"])
        marks = fixboard.changed_marks([{"changed": {"gates_changed": True, fixboard.DRIFT_NOTE: "測り直した"}}, None,
                                        {"changed": {fixboard.DRIFT_NOTE: "測り直した"}}])
        self.assertEqual(set(marks), {*fixboard.CHANGED_MARKS, fixboard.DRIFT_NOTE})
        self.assertEqual([k for k, v in marks.items() if v is True], ["gates_changed"])
        self.assertEqual(marks[fixboard.DRIFT_NOTE], "測り直した", "同じ文は 1 度")
        self.assertEqual(fixboard.x_scalars([{"x_scalars": {"x_a": 1, "x_b": "多い"}}, {"x_scalars": {"x_a": 2.5, "x_b": 3}},
                                             {"x_scalars": "壊れた"}, None]), {"x_a": 3.5, "x_b": "多い"})
        self.assertEqual(fixboard.objection([{"objection": "前提が違う"}, {"rejudge_requested": "前提が違う"}, {}]), "前提が違う")
        self.assertEqual(fixboard.allowed_tests(self.place, [{"allowed_tests": [{"path": "t/a.py", "permit": "plan-1",
                                                                                   "source": "plan"}]}]), ["t/a.py"])

    def test_changed_marks_or_over_groups_and_ruled(self):
        """F138: 修正役の 6 つの印は、戻せた組の子の結果（group_result の changed）と裁定の後の返答（reply_marks の changed）の
        論理和。組 1 が真・組 2 が偽なら真、全部偽なら偽"""
        off = {k: False for k in fixboard.CHANGED_MARKS}
        g1 = fixboard.group_result({"group_id": "g1", "unit_ids": []}, start_tree="", end_tree="", tdd=None,
                                   reply={**off, "mechanism_changed": True})
        off = {**off, fixboard.DRIFT_NOTE: ""}   # 前提のずれの申告の文（無ければ空）も同じ欄に載る
        g2 = fixboard.group_result({"group_id": "g2", "unit_ids": []}, start_tree="", end_tree="", tdd=None, reply=dict(off))
        ruled = fixboard.reply_marks({"seams_changed": True})
        got = fixboard.changed_marks([g1, g2, ruled])
        self.assertEqual(got, {**off, "mechanism_changed": True, "seams_changed": True})
        self.assertEqual(fixboard.changed_marks([g2, fixboard.reply_marks({})]), off)
        self.assertEqual(fixboard.changed_marks([g2, g1]), {**off, "mechanism_changed": True}, "後の組が偽でも前の組の真は残る")

    def test_delta_review_counts_rounds(self):
        d = self.place / fixboard.DELTA_DIR
        self.assertEqual(fixboard.delta_review(self.place), ({"rounds": 0, "pass": False}, False))
        d.mkdir()
        (d / "review-1.json").write_text('{"pass": false}', encoding="utf-8")
        self.assertEqual(fixboard.delta_review(self.place), ({"rounds": 1, "pass": False}, False))
        (d / "review-2.json").write_text('{"pass": true}', encoding="utf-8")
        self.assertEqual(fixboard.delta_review(self.place), ({"rounds": 2, "pass": True}, False))
        (d / "skipped.json").write_text('{"reason": "軽量"}', encoding="utf-8")
        self.assertEqual(fixboard.delta_review(self.place), ({"rounds": 0, "pass": True}, True))

    def test_join_group_applies_and_check_reverts(self):
        start = leftovers.snapshot(self.repo)
        (self.repo / "extra.py").write_text("X = 1\n", encoding="utf-8")
        end = leftovers.snapshot(self.repo)
        git(self.repo, "clean", "-qfd")
        got = fixboard.join_group(self.repo, start, end, self.place / "g1.diff")
        self.assertEqual((got.why, got.names), ("", ["extra.py"]))
        self.assertTrue((self.repo / "extra.py").is_file())
        git(self.repo, "clean", "-qfd")
        got = fixboard.join_group(self.repo, start, end, self.place / "g1.diff", check=lambda names: "確かめ直しが赤")
        self.assertEqual(got.why, "確かめ直しが赤")
        self.assertFalse((self.repo / "extra.py").exists())
        self.assertIn("extra.py", (self.place / "g1.diff").read_text(encoding="utf-8"))

    def test_tests_moved_names_named_tests_that_differ_from_the_child(self):
        src = (self.repo / "test_stats.py").read_text(encoding="utf-8")
        end = leftovers.snapshot(self.repo)
        unit = {"tests": ["test_stats.py::TestStats::test_mean_of_three"], "test_files": ["test_stats.py"]}
        self.assertEqual(fixboard.tests_moved(self.repo, end, [unit], {"test_stats.py"}), "")
        (self.repo / "test_stats.py").write_text(src.replace("mean([1, 2, 3]), 2", "mean([2, 4]), 3"), encoding="utf-8")
        self.assertIn("test_mean_of_three", fixboard.tests_moved(self.repo, end, [unit], {"test_stats.py"}))
        self.assertEqual(fixboard.tests_moved(self.repo, end, [unit], set()), "")

    def test_join_group_reverts_when_the_check_raises(self):
        start = leftovers.snapshot(self.repo)
        (self.repo / "extra.py").write_text("X = 1\n", encoding="utf-8")
        end = leftovers.snapshot(self.repo)
        git(self.repo, "clean", "-qfd")

        def broken(names):
            raise RuntimeError("地図が引けない")
        with self.assertRaises(RuntimeError):
            fixboard.join_group(self.repo, start, end, self.place / "g1.diff", check=broken)
        self.assertFalse((self.repo / "extra.py").exists())

    def test_rerun_problem_is_empty_without_suite_or_names(self):
        self.assertEqual(fixboard.rerun_problem(self.place, self.repo, "", [], ["t.py::x"]), "")
        self.assertEqual(fixboard.rerun_problem(self.place, self.repo, "run.sh", [], []), "")

    def test_rerun_problem_names_red_unrunnable_and_unreported_tests(self):
        from lib.tests.test_blk_fix_tdd import SUITE
        suite = self.tmp / "suite.py"
        suite.write_text(SUITE, encoding="utf-8")
        named = ["test_stats.py::TestStats::test_mean_of_three"]
        self.assertIn("test_mean_of_three", fixboard.rerun_problem(self.place, self.repo, str(suite), [], named))
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        self.assertEqual(fixboard.rerun_problem(self.place, self.repo, str(suite), [], named), "")
        self.assertIn("走らせられない", fixboard.rerun_problem(self.place, self.repo, str(self.tmp / "no-such.py"), [], named))
        empty = self.tmp / "empty.py"
        empty.write_text("import sys\nopen(sys.argv[1], 'w').write('<testsuite/>')\n", encoding="utf-8")
        self.assertIn("test_mean_of_three", fixboard.rerun_problem(self.place, self.repo, str(empty), [], named),
                      "0 件の結末は通ったと数えない")
        import baseline_red
        cases, _, why = baseline_red.run_suite(str(suite), self.repo, self.tmp, "base")
        self.assertIsNotNone(cases, why)
        src = stats.read_text(encoding="utf-8")
        with self.subTest("名指しの無い組も、変えたファイルに当たる試験を走らせ直す（F411 の 1）"):
            stats.write_text(src.replace("    return x\n", "    return lo\n"), encoding="utf-8")
            got = fixboard.rerun_problem(self.place, self.repo, str(suite), cases, [], name="fixer-only")
            stats.write_text(src, encoding="utf-8")
            self.assertIn("test_clamp_within_range", got)
            self.assertEqual(fixboard.rerun_problem(self.place, self.repo, str(suite), cases, [], name="fixer-only-green"), "")
        with self.subTest("前の組と重なったファイルから地図が届く試験を足す（F411 の 2）"):
            self.assertEqual(fixboard.rerun_problem(self.place, self.repo, str(suite), cases, named, name="wide",
                                                    shared=["stats.py"]), "")
            st = json.loads((self.place / "wide" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(st["units"]["wide"]["test_files"], ["test_stats.py"])
        with self.subTest("重なりの在る組の赤は意味の食い違いと名指す"):
            stats.write_text(src.replace("    return x\n", "    return lo\n"), encoding="utf-8")
            got = fixboard.rerun_problem(self.place, self.repo, str(suite), cases, named, name="clash", shared=["stats.py"])
            stats.write_text(src, encoding="utf-8")
            self.assertTrue(got.startswith(fixboard.SEMANTIC_CLASH.split("{")[0]), got)
            self.assertIn("stats.py", got)
            self.assertIn("test_clamp_within_range", got)
        with self.subTest("test_cmd を渡すのは子の関門が on で軽量でない単位が在る組だけ（rerun_cmd）"):
            on = {"unit_ids": ["A", "B"], "tdd": {"test_cmd": {"gate": "on"}}}
            self.assertEqual(fixboard.rerun_cmd(self.place, on, " make test "), "make test")
            self.assertEqual(fixboard.rerun_cmd(self.place, {**on, "tdd": {"test_cmd": {"gate": "same_as_suite"}}}, "make test"), "")
            self.assertEqual(fixboard.rerun_cmd(self.place, {**on, "tdd": {"ran": False}}, "make test"), "")
            fixboard.write_json(self.place / fixboard.DEPTH_FILE, [{"unit_id": "A", "depth": "軽量", "why": "x"},
                                                                   {"unit_id": "B", "depth": "軽量", "why": "x"}])
            self.assertEqual(fixboard.rerun_cmd(self.place, on, "make test"), "", "全部の単位が軽量")
            (self.place / fixboard.DEPTH_FILE).unlink()
        with self.subTest("test_cmd が渡れば緑の後に 1 回走らせ、赤なら戻す理由（F411 の 2）"):
            red = f"{sys.executable} -c \"import sys; sys.exit(3)\""
            got = fixboard.rerun_problem(self.place, self.repo, str(suite), cases, named, name="cmd-red", test_cmd=red)
            self.assertIn("test_cmd", got)
            self.assertTrue((self.place / "cmd-red" / "test-cmd.log").is_file())
            green = f"{sys.executable} -c \"import sys; sys.exit(0)\""
            self.assertEqual(fixboard.rerun_problem(self.place, self.repo, str(suite), cases, named, name="cmd-green",
                                                    test_cmd=green), "")


class SmallGapsSeamCase(unittest.TestCase):
    """小さな抜け 3 つ: tddloop の申し出の頼みの文が種類を全部言う（元 tests/test_conflict_kinds.py の
    KindCase.test_return_conflict_lists_every_kind）、tddloop の実行器と failure の文の読みが baseline_red の物で諦めが 3 回目、
    parking の除くパスの頭（引数 skip。既定 () では除かない）"""

    def test_return_conflict_lists_every_kind(self):
        import conflict
        import tddloop
        for k in conflict.DIV_KINDS:
            self.assertIn(k, tddloop.RETURN_CONFLICT)

    def test_tdd_loop_takes_the_runner_from_baseline_red_and_gives_up_on_the_third(self):
        import baseline_red
        import tddloop
        self.assertIs(tddloop.run_suite, baseline_red.run_suite)
        self.assertIs(tddloop._failure_attrs, baseline_red._failure_attrs)
        self.assertEqual(tddloop.retry_max(), 3)

    def test_parking_ours_skips_only_the_given_heads(self):
        import parking
        self.assertTrue(parking._ours("vendored/x.py"), "既定の () では除かない")
        self.assertFalse(parking._ours("vendored/x.py", SKIP))
        self.assertFalse(parking._ours("vendored", SKIP), "頭のフォルダそのものも除く")
        self.assertTrue(parking._ours("vendoredx/x.py", SKIP), "頭の字で始まるだけの別のフォルダは除かない")
        self.assertTrue(parking._ours("stats.py", SKIP))

    def test_parking_footprint_and_settle_pass_the_skip(self):
        import parking
        rows = [{"unit_key": "a", "files": ["stats.py", "vendored/copy.py"]}]
        self.assertEqual(parking.footprint(rows, [], "/home/x/repo"), {"a": {"stats.py", "vendored/copy.py"}})
        feet = parking.footprint(rows, [], "/home/x/repo", SKIP)
        self.assertEqual(feet, {"a": {"stats.py"}})
        both = {"a": {"stats.py", "vendored/copy.py"}}
        args = dict(keys={"a"}, feet=both, reached={}, owed={"a"}, out_of_duty=set(), changed=set())
        self.assertEqual(parking.settle(["a: 落ちた"], **args).files, {"stats.py", "vendored/copy.py"})
        got = parking.settle(["a: 落ちた"], **args, skip=SKIP)
        self.assertEqual((set(got.park), got.files), ({"a"}, {"stats.py"}))
        owed = parking.park_owed(["写しの行"], feet=both, owed={"a"}, out_of_duty=set(), skip=SKIP)
        self.assertEqual((set(owed.park), owed.files), ({"a"}, {"stats.py"}))


class GroupChildSeamCase(TempCase):
    """形 group の子の run の口: fixboard.adopt_inputs（親の置き場の写しと凍結の印の置き直し）・unit_depths・verified_tests・
    group_result（組の結果の形と単位の結末の選び）"""

    def test_adopt_inputs_copies_the_parent_and_refreezes_the_fields(self):
        import conflict
        import planmarks
        parent = self.tmp / "parent"
        (parent / "r1").mkdir(parents=True)
        (parent / "r1" / "start.json").write_text('{"tdd_suite": ""}\n', encoding="utf-8")
        (parent / "judgment.json").write_text('{"units": []}\n', encoding="utf-8")
        fields = [{"route": "direct", "tests": [], "rewrite_tests": [], "refactor": "", "allowed_paths": ["stats.py"],
                   "out_of_scope": []}]
        planmarks.save(parent, 1, fields)
        got = fixboard.adopt_inputs(parent, self.place)
        self.assertEqual(got, ["r1/start.json", "judgment.json", "plan-fields.json"])
        self.assertEqual((self.place / "judgment.json").read_text(encoding="utf-8"), '{"units": []}\n')
        self.assertEqual(conflict.frozen_fields(self.place, 1), fields, "子の trace に凍結の印が在る")
        bare = self.tmp / "bare"
        bare.mkdir()
        self.assertEqual(fixboard.adopt_inputs(bare, self.tmp / "child2"), [], "欄の控えの無い親は何も置かない")
        with self.assertRaises(ValueError):
            fixboard.adopt_inputs(self.tmp / "no-such", self.place)

    def test_unit_depths_and_verified_tests(self):
        self.assertEqual(fixboard.unit_depths(self.place), "")
        (self.place / "depth.json").write_text(json.dumps([{"unit_id": "a", "depth": "軽量", "why": "1 個"}]),
                                               encoding="utf-8")
        self.assertEqual(json.loads(fixboard.unit_depths(self.place)), {"a": "軽量"})
        tdd = {"ran": True, "units": [{"unit_key": "a", "route": "tdd", "green": "ok", "tests": ["t.py::x", "t.py::y"]},
                                      {"unit_key": "b", "route": "tdd", "green": "", "tests": ["t.py::z"]},
                                      {"unit_key": "c", "route": "direct", "green": "", "tests": []}]}
        self.assertEqual(fixboard.verified_tests(tdd), ["t.py::x", "t.py::y"])

    def test_group_result_shape(self):
        tdd = {"ran": True, "suite": "s", "reason": "", "units": [
            {"unit_key": "b", "route": "parked", "gave_up": "red", "why": "赤が 3 回とも通らなかった", "tests": []}]}
        reply = {"mechanism_changed": True, "rejudge_requested": "判定の単位 a は誤り"}
        got = fixboard.group_result({"group_id": "g1", "unit_ids": ["a", "b", "c"], "items": [1]}, start_tree="t0",
                                    end_tree="t1", tdd=tdd, fix_units={"a": {"status": "fixed", "reason": ""}},
                                    reply=reply, reply_file="/r.json", conflicts=[{"id": 1}],
                                    allowed_rows=[{"path": "t.py", "permit": "p1", "source": "plan"},
                                                  {"path": "t.py", "permit": "p2", "source": "plan"}])
        self.assertEqual(set(got), {"group_id", "unit_ids", "end_tree", "start_tree", "units", "tdd", "conflicts",
                                    "objection", "changed", "x_scalars", "allowed_tests", "verified",
                                    "reply_file", "tdd_state", "worktree", "handoffs", "mismatched", "accept_trace", "closure",
                                    "claimed", "place"})
        self.assertEqual((got["worktree"], got["place"]), ("", ""), "渡さなければ空")
        self.assertEqual((got["handoffs"], got["claimed"], got["closure"], got["accept_trace"]), ([], [], [], []))
        self.assertEqual([(u["unit_id"], u["status"]) for u in got["units"]],
                         [("a", "fixed"), ("b", "given_up"), ("c", "not_done")])
        self.assertEqual(got["units"][2]["reason"], fixboard.NO_UNIT_RESULT)
        self.assertEqual(got["objection"], "判定の単位 a は誤り")
        self.assertEqual(got["changed"], {**{k: k == "mechanism_changed" for k in fixboard.CHANGED_MARKS}, fixboard.DRIFT_NOTE: ""})
        self.assertEqual([r["permit"] for r in got["allowed_tests"]], ["p1", "p2"])
        row = {"path": "t.py", "permit": "plan-rewrite-1", "source": "plan"}
        unreplied = fixboard.group_result({"group_id": "g1", "unit_ids": []}, start_tree="", end_tree="", tdd=None,
                                          allowed_rows=[row, "壊れた行"])
        self.assertEqual(unreplied["allowed_tests"], [],
                         "返答を受け付けていない組は許しの訳を載せない（join と親の collect が同じ欄から読む）")
        final = fixboard.group_result({"group_id": "g1", "unit_ids": []}, start_tree="", end_tree="", tdd=None,
                                      reply={"changes": [{"unit_key": "a", "breaks": {"accepted": "x"}}]}, mismatched=["m"],
                                      accept_trace=[{"op": "fix_tests_selected", "note": "0 件"}, "壊れた行"])
        self.assertEqual((final["handoffs"], final["mismatched"]), (["a: 壊すと分かって通した——x"], ["m"]))
        self.assertEqual(final["accept_trace"], [{"op": "fix_tests_selected", "note": "0 件", "group_id": "g1"}])
        empty = fixboard.group_result({"group_id": "g2", "unit_ids": []}, start_tree="", end_tree="", tdd=None)
        self.assertEqual((empty["tdd"]["ran"], empty["objection"], empty["reply_file"]), (False, "", ""))
        self.assertFalse(any(empty["changed"].values()))


class FixAcceptSeamCase(TempCase):
    """修正役の受け付けと範囲の相談の部品（fixboard の check_*_units・fix_reject_text・undeclared_writes・reply_marks・unit_outcomes・
    allowed_tests・ruled_owed・ruled_reply_line・consult_ask・accept_reply）。元 works/blk-fix/scripts/accept.py の単位の行の照らしと
    元 works/blk-fix/lib/consult.py:522 の頼みの節を、置き場と値で回す"""

    def test_unit_row_checks(self):
        """同じ unit_key の 2 行・義務にも外れにも無い key・外れた単位の行（元 accept.py:258・268・297）"""
        keys = ["a", "b", "a", "x", "c", "x"]
        self.assertEqual(fixboard.check_unique_units(keys), ["a", "x"])
        self.assertEqual(fixboard.check_opened_units(keys, {"a", "b", "c"}), ["x"])
        self.assertEqual(fixboard.check_excused_units(keys, {"a", "b"}, {"c": "人が決める"}), {"c": "人が決める"})

    def test_closure_reply_takes_the_replaced_query_and_the_zero_units(self):
        """閉鎖の数え直しは、裁定 replace_query を受けた単位を置き換えた問いで数え（conflict.replaced_queries）、判定者の問いが
        修正前の版で 0 件なのに total が 0 でない単位を 0 件の単位にする（元 unitrows.take の engine_zero）"""
        import conflict
        how = {"patterns": ["return lo"], "fixed": True, "paths": ["stats.py"], "count": "lines"}
        judged = [*R_JUDGED, {"key": "zero-unit", "class_query": {
            "how": {"patterns": ["zzz-none"], "fixed": True, "paths": ["stats.py"], "count": "lines"},
            "counts": "defects", "total": 3}}]
        conflict.park(self.place, [{"unit_key": R_MEAN, "between": ["stats.py:9", "stats.py:9"],
                                    "why_both_cannot_hold": "判定者の問いが直した後の正しい形にも当たる",
                                    "which_is_right": "query", "kind": "query_hits_fixed"}], source=conflict.FIX_SOURCE,
                      ruling={"decision": "replace_query", "text": "問いを置き換える", "limits": [],
                              "query": {"how": how, "counts": "population", "hits": ["return lo"], "misses": []}})
        shaped, rows, zero = fixboard.closure_reply({"changes": [_fix_row(R_MEAN, 1)]}, self.place, self.repo, self.rev, judged)
        self.assertEqual(zero, {"zero-unit"})
        self.assertTrue(rows[0]["how_from"].startswith("裁定"), rows)
        self.assertNotIn("path", shaped["changes"][0]["closure"]["sites"][0])

    def test_reject_text_follows_the_check_order(self):
        found = [("copy", "数えが合わない"), ("writes", "記録が無い"), ("writes", "記録が無い"), ("duplicate", "a")]
        text = fixboard.fix_reject_text(found)
        self.assertTrue(text.startswith(fixboard.FIX_REJECT_HEAD))
        self.assertLess(text.index("確かめ writes・1 件"), text.index("確かめ duplicate"))
        self.assertLess(text.index("確かめ duplicate"), text.index("確かめ copy"))
        self.assertEqual(fixboard.fix_reject_rows(found), [("writes", "記録が無い"), ("duplicate", "a"), ("copy", "数えが合わない")])

    def test_undeclared_writes_bind_to_changes_and_bash_writes(self):
        tree = leftovers.snapshot(self.repo)
        (self.repo / "stats.py").write_text("x = 1\n", encoding="utf-8")
        (self.repo / "gen.txt").write_text("生成\n", encoding="utf-8")
        (self.repo / "vendored").mkdir()
        (self.repo / "vendored" / "w.txt").write_text("工程の写し\n", encoding="utf-8")
        reply = {"changes": [{"unit_key": "a", "files": ["stats.py"]}]}
        got = fixboard.undeclared_writes(reply, self.repo, tree, skip=SKIP)
        self.assertEqual(got, [fixboard.UNDECLARED + "gen.txt"])
        self.assertEqual(fixboard.undeclared_writes(reply, self.repo, tree, made={"gen.txt"}, skip=SKIP), [])
        told = {**reply, "bash_writes": [{"path": "gen.txt", "why": WHY}]}
        self.assertEqual(fixboard.undeclared_writes(told, self.repo, tree, skip=SKIP), [])
        self.assertEqual(len(fixboard.undeclared_writes(reply, self.repo, tree)), 1, "既定の () では除かない")
        self.assertIn("vendored/w.txt", fixboard.undeclared_writes(reply, self.repo, tree)[0])

    def test_reply_marks_or_over_the_previous(self):
        before = fixboard.reply_marks({"gates_changed": True, "rejudge_requested": "前の異議", "premise_drift_note": "前の申告"})
        got = fixboard.reply_marks({"changes": [], "path_changed": True, "rejudge_requested": "今の異議",
                                    "premise_drift_note": "今の申告"}, before)
        self.assertEqual(got["changed"], {**{k: k in ("gates_changed", "path_changed") for k in fixboard.CHANGED_MARKS},
                                          fixboard.DRIFT_NOTE: "前の申告\n今の申告"})
        self.assertEqual(got["rejudge_requested"], "前の異議\n今の異議")
        self.assertTrue(got["gates_changed"])

    def test_unit_outcomes(self):
        reply = {"changes": [{"unit_key": "a"}], "not_done": [{"unit_key": "b", "why": "答え待ち"}]}
        got = fixboard.unit_outcomes(["a", "b", "c"], reply, excused={"d": "人が決める"}, parked={"c": "諦めた"})
        self.assertEqual(got, {"a": {"status": "fixed", "reason": ""}, "b": {"status": "not_done", "reason": "答え待ち"},
                               "c": {"status": "given_up", "reason": "諦めた"},
                               "d": {"status": "not_done", "reason": "人が決める"}})
        got = fixboard.unit_outcomes(["a"], {}, conflicted=["a"])
        self.assertEqual(got["a"], {"status": "not_done", "reason": fixboard.PARKED_FOR_RULING})

    def test_allowed_tests_take_rulings_and_agreements(self):
        import conflict
        conflict.park(self.place, [{"unit_key": "a", "between": ["stats.py:9", "test_stats.py:8"],
                                    "why_both_cannot_hold": "テストの期待が誤っている", "which_is_right": "request",
                                    "kind": "unnamed_test_broke"}], source=conflict.FIX_SOURCE,
                      ruling={"decision": "fix_test_scope", "text": "直してよい", "limits": ["test_stats.py:8"]})
        fixboard.trace(self.place, conflict.ASKED_OP, id=1, item="1", status="answered", decision="allow", granted_paths=[],
                       granted_tests=["tests/test_b.py:3"], granted_new_tests=[{"id": "tests/test_c.py::T::t", "red_kind": "red"}],
                       reason="足してよい")
        self.assertEqual(fixboard.allowed_tests(self.place), ["test_stats.py", "tests/test_b.py", "tests/test_c.py"])
        import planmarks
        planmarks.save(self.place, 1, [{"unit_keys": ["a"], "rewrite_tests": [
            {"id": "tests/test_d.py::test_d", "new": "hi を期待する", "limit": "tests/test_d.py:1"}]}])
        self.assertEqual(fixboard.allowed_test_rows(self.place), [
            {"path": "test_stats.py", "permit": f"{conflict.RULED_TEST_ID}-c1-1", "source": "ruling"},
            {"path": "tests/test_b.py", "permit": f"{conflict.AGREED_TEST_ID}-1", "source": "consult"},
            {"path": "tests/test_c.py", "permit": f"{conflict.AGREED_TEST_ID}-1", "source": "consult"},
            {"path": "tests/test_d.py", "permit": f"{conflict.PLAN_TEST_ID}-1", "source": "plan"}],
            "許しの出どころは許しの行が持つ（id の頭から引き直さない）")

    def test_ruled_owed_reads_the_join(self):
        (self.place / "judgment.json").write_text(json.dumps({"units": [{"key": k, "label": "block"} for k in "abc"]}),
                                                  encoding="utf-8")
        self.assertEqual(fixboard.ruled_owed(self.place), ["a", "b", "c"])
        (self.place / "join.json").write_text(json.dumps({
            "groups": [{"group_id": "g1", "returned": True}, {"group_id": "g2", "returned": False}],
            "units": [{"unit_id": "a", "group_id": "g1", "status": "fixed"}, {"unit_id": "b", "group_id": "g1", "status": "not_done"},
                      {"unit_id": "c", "group_id": "g2", "status": "not_done"}]}), encoding="utf-8")
        self.assertEqual(fixboard.ruled_owed(self.place), ["b"])
        self.assertEqual(fixboard.group_owed(self.place, ["c", "z"]), ["c"])

    def test_ruled_reply_line_once_after_the_title(self):
        p = self.place / "prompt.md"
        p.write_text("# 題\n本文\n", encoding="utf-8")
        fixboard.ruled_reply_line(p, "/x/fix-reply.json")
        fixboard.ruled_reply_line(p, "/x/fix-reply.json")
        lines = p.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "# 題")
        self.assertEqual(sum("/x/fix-reply.json" in ln for ln in lines), 1)
        self.assertIn("/x/fix-reply.json", lines[2])

    def test_consult_ask_screens_and_writes_the_question(self):
        import consult
        items = [{"item": 1, "unit_keys": ["a"], "allowed_paths": ["stats.py"], "out_of_scope": [], "tests": []}]
        reply = {consult.conflict.CONSULT_FIELD: [
            {"item": 1, "paths": ["docs/n.md"], "tests": [], "why": "直しに伴う記録を残す要が在る（範囲の外）"},
            {"item": 9, "paths": ["x.py"], "tests": [], "why": "知らない項目への頼みの理由の文"}]}
        got = fixboard.consult_ask(self.place, reply, "first", items, node="consult-answer", plan_file="/p/plan.json")
        self.assertEqual((got["consulted"], got["go"], got["turn"]), (True, True, 1))
        text = pathlib.Path(got["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn("/p/plan.json", text)
        self.assertNotIn("x.py", text, "断った頼みは聞かない")
        st = consult.state(self.place, "first")
        self.assertEqual([r["status"] for r in st["rows"]], [consult.ASKED, consult.REFUSED])
        self.assertEqual(fixboard.consult_ask(self.place, {"changes": []}, "first", items, node="x")["consulted"], False)
        jsonfile.write(consult.state_path(self.place, "first"), {"turns": consult.BUDGET})
        self.assertTrue(fixboard.consult_ask(self.place, reply, "first", items, node="x")["spent"])

    def test_accept_reply_parks_the_bound_unit_on_the_last_turn(self):
        """3 回目の拒否は名指しの単位だけを段の頭の木に戻して諦め、残りを受ける（元 accept.py の last_settle・park_units）"""
        import conflict
        (self.place / "judgment.json").write_text(json.dumps({"units": [{"key": "alpha-unit", "label": "block"},
                                                                        {"key": "beta-unit", "label": "block"}]}), encoding="utf-8")
        head = leftovers.snapshot(self.repo)
        (self.repo / "a.txt").write_text("a\n", encoding="utf-8")
        (self.repo / "b.txt").write_text("b\n", encoding="utf-8")
        how = {"patterns": ["zzz-none"], "fixed": True, "paths": ["stats.py"], "count": "lines"}
        reply = {"changes": [{"unit_key": "alpha-unit", "what": "足した", "files": ["a.txt"], "coverage": {"how": how, "counts": "population"},
                              "closure": {"sites": []}, **SELF_REPORT},
                             {"unit_key": "beta-unit", "what": "足した", "files": ["b.txt"], **SELF_REPORT}]}
        kw = dict(pass_="first", owed=["alpha-unit", "beta-unit"], judged=[], head=head, skip=SKIP)
        got = fixboard.accept_reply(reply, self.place, self.repo, iteration=2, **kw)
        self.assertFalse(got["ok"])
        self.assertTrue(any(r["check"] == "copy" and r["text"].startswith("beta-unit:") for r in got["rejects"]), got["rejects"])
        self.assertTrue((self.repo / "b.txt").exists(), "最後の回でなければ戻さない")
        got = fixboard.accept_reply(reply, self.place, self.repo, iteration=3, **kw)
        self.assertTrue(got["ok"], got["reason"])
        self.assertEqual({k: v["status"] for k, v in got["units"].items()}, {"alpha-unit": "fixed", "beta-unit": "given_up"}, got["units"])
        self.assertFalse((self.repo / "b.txt").exists())
        self.assertTrue((self.repo / "a.txt").exists())
        self.assertEqual([r["unit_key"] for r in conflict.items(self.place)], ["beta-unit"])
        self.assertEqual([r["op"] for r in _traced(self.place) if r["op"] == conflict.ACCEPT_PARKED_OP], [conflict.ACCEPT_PARKED_OP])


    def _accept_fixed(self, reply, precedents=()):
        """判定の写し（R_JUDGED と precedents）を置き、R_FIXED で直した木で 1 回目の受け付けを回す"""
        (self.place / "judgment.json").write_text(json.dumps({"units": R_JUDGED, "precedents": list(precedents)},
                                                             ensure_ascii=False), encoding="utf-8")
        head = leftovers.snapshot(self.repo)
        path = self.repo / "stats.py"
        text = path.read_text(encoding="utf-8")
        for old, new in R_FIXED.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
        return fixboard.accept_reply(reply, self.place, self.repo, pass_="first", iteration=1, owed=[R_MEAN, R_CLAMP],
                                     judged=R_JUDGED, head=head, base_rev=self.rev, skip=SKIP)

    def test_accept_reply_saves_the_closure_table_it_recounted(self):
        """受けた返答は閉鎖の数え直し（closure_reply）を通り、単位ごとの表を置き場に置く（querytest.save_closure）"""
        import querytest
        got = self._accept_fixed(_fix_ok())
        self.assertTrue(got["ok"], got["reason"])
        rows = json.loads((self.place / querytest.CLOSURE_FILE).read_text(encoding="utf-8"))["rows"]
        self.assertEqual({r["unit_key"]: r["how_from"] for r in rows}, {R_MEAN: "判定者", R_CLAMP: "判定者"})

    def test_accept_reply_passes_the_judged_precedents_to_the_recount(self):
        """判定の写しの precedents に在る単位の from_judge_row は通る（判定の写しを数え直しに渡す。元 review-loop.py の
        precedent.from_judge_row の照らし）"""
        reply = _fix_ok()
        reply["changes"][0]["precedent"] = {"from_judge_row": True, "verdict": "adopt", "reason": "判定者の行"}
        got = self._accept_fixed(reply, precedents=[{"key": R_MEAN}])
        self.assertTrue(got["ok"], got["reason"])

    # ---- 食い違いの申し出の道（take_conflicts）を accept_reply から通す（元 works/tests/test_blk_fix_conflict.py の写し）
    def _claim(self, *cites, **over):
        return {"unit_key": R_MEAN, "between": list(cites or ("stats.py:9", "test_stats.py:9")),
                "why_both_cannot_hold": "テストは分母 len(xs) - 1 の値を期待しているが、依頼は算術平均を求めている",
                "which_is_right": "request", "kind": "unnamed_test_broke", **over}

    def _accept_claims(self, conflicts, *, pass_="first", iteration=1, judgment=True, changes=()):
        """判定の写し（R_JUDGED。judgment が偽なら置かない）の置き場で、申し出 conflicts を持つ返答を受け付けに通す"""
        if judgment:
            (self.place / "judgment.json").write_text(json.dumps({"units": R_JUDGED}, ensure_ascii=False), encoding="utf-8")
        head = leftovers.snapshot(self.repo)
        return fixboard.accept_reply({"changes": list(changes), "conflicts": conflicts}, self.place, self.repo, pass_=pass_,
                                     iteration=iteration, owed=[R_MEAN, R_CLAMP], judged=R_JUDGED, head=head,
                                     base_rev=self.rev, skip=SKIP)

    def _conflict_rejects(self, got) -> list:
        return [r["text"] for r in got["rejects"] if r["check"] == "conflict"]

    def test_fake_citation_is_a_normal_reject(self):
        """F202: 名指しの行がファイルに無い・無いファイルの申し出は普通の拒否（check conflict。3 回の枠に数える）で、置き場の
        conflicts.json に積まない。依頼の行（run の依頼のファイルの絶対パス:行）は名指せ、行が無ければ拒む（元
        test_blk_fix_conflict.py:141 test_fake_citation_is_a_normal_reject・:162 test_request_line_citation_resolves）"""
        import conflict
        got = self._accept_claims([self._claim("stats.py:900", "no_such_test.py:1")])
        self.assertEqual((got["ok"], got["conflicted"]), (False, False), got)
        bad = " ".join(self._conflict_rejects(got))
        for w in ("stats.py:900", "行がファイルに無い", "no_such_test.py:1", "ファイルが無い"):
            self.assertIn(w, bad)
        self.assertEqual(conflict.items(self.place), [], "拒んだ申し出は積まない")
        req = self.tmp / "request.json"
        req.write_text('{"request": "平均を直す"}\n', encoding="utf-8")
        (self.place / "r1").mkdir()
        (self.place / "r1" / "start.json").write_text(json.dumps({"request_file": str(req)}), encoding="utf-8")
        got = self._accept_claims([self._claim(f"{req}:999", "test_stats.py:9")], iteration=2)
        self.assertFalse(got["ok"], got)
        self.assertIn("行がファイルに無い", " ".join(self._conflict_rejects(got)))
        got = self._accept_claims([self._claim(f"{req}:1", "test_stats.py:9")], iteration=3)
        self.assertEqual((got["ok"], got["conflicted"]), (True, True), got)
        self.assertEqual([r["unit_key"] for r in conflict.unruled(self.place)], [R_MEAN])

    def test_fixer_query_claim_tries_the_judge_query(self):
        """F205: 修正役の which_is_right: query の申し出も、置き場の判定の写し judgment.json の単位の class_query を correct_lines に
        当てて試す。当たらなければ拒み、当たれば積む。判定の写しが読めなければ「読めない」と名指して拒む（黙って試さずに通さない）
        （元 works/blk-fix/scripts/accept.py:325-326 の try_query。元 test_blk_fix_conflict.py:470 の修正役の版）"""
        import conflict
        query = dict(which_is_right="query", kind="query_hits_fixed")
        got = self._accept_claims([self._claim(**query, correct_lines=["    return sum(xs) / len(xs)"])])
        self.assertEqual((got["ok"], got["conflicted"]), (False, False), got)
        self.assertIn("どの行にも当たらない", " ".join(self._conflict_rejects(got)))
        self.assertEqual(conflict.items(self.place), [])
        (self.place / "judgment.json").unlink()
        got = self._accept_claims([self._claim(**query, correct_lines=["    return sum(xs) / (len(xs) - 1)"])],
                                  iteration=2, judgment=False)
        self.assertFalse(got["ok"], got)
        self.assertIn("judgment.json が読めない", " ".join(self._conflict_rejects(got)))
        got = self._accept_claims([self._claim(**query, correct_lines=["    return sum(xs) / (len(xs) - 1)"])], iteration=2)
        self.assertEqual((got["ok"], got["conflicted"]), (True, True), got)
        self.assertEqual([r["which_is_right"] for r in conflict.unruled(self.place)], ["query"])

    def test_resent_claim_on_a_ruled_unit_is_dropped(self):
        """F206: 裁定がもう外した単位（conflict.held_by_rulings）の申し出は、出し直されても知っている申し出として確かめずに外し、
        積み増さない（名指しが現物に無くても拒否の行にしない）（元 test_blk_fix_conflict.py:339
        test_resent_conflict_on_parked_unit_does_not_halt_last_round）"""
        import conflict
        conflict.park(self.place, [self._claim()], source=conflict.FIX_SOURCE,
                      ruling={"decision": conflict.ASK, "text": fixboard.SECOND_CONFLICT, "limits": [],
                              "by": fixboard.FIX_ACCEPT_BY})
        self.assertIn(R_MEAN, conflict.held_by_rulings(self.place))
        again = self._claim("stats.py:900", "test_stats.py:9", why_both_cannot_hold="裁定の後にもう一度、同じ単位を申し出た")
        got = self._accept_claims([again], pass_="ruled", iteration=2)
        self.assertEqual(self._conflict_rejects(got), [], got["rejects"])
        self.assertFalse(got["conflicted"])
        self.assertEqual([(r["unit_key"], r["ruling"]["decision"]) for r in conflict.items(self.place)], [(R_MEAN, conflict.ASK)],
                         "積み増さない")

    def test_consult_after_budget_is_rejected_and_dropped(self):
        """範囲の相談の周でない回に来た consult は枠を使い切った後の物: 確かめ consult の行で拒み、欄を外した返答を後の確かめに
        当てる（元 works/blk-fix/scripts/accept.py:629-631。元の試験 works/tests/test_fix_precheck.py:145・test_fix_lanes.py:223）"""
        import conflict
        import consult
        ask = [{"item": 1, "paths": ["docs/n.md"], "tests": [], "why": "直しに伴う記録を残す要が在る（範囲の外）"}]
        got = self._accept_fixed({**_fix_ok(), conflict.CONSULT_FIELD: ask})
        self.assertFalse(got["ok"], got)
        self.assertEqual(got["rejects"], [{"check": "consult", "text": fixboard.CONSULT_SPENT.format(n=consult.BUDGET)}])
        self.assertNotIn(conflict.CONSULT_FIELD, got["reply"])
        self.assertEqual(len(got["reply"]["changes"]), 2, "欄を外した返答を後の確かめに当てた")

    def _hold_clamp(self) -> str:
        """R_CLAMP を ask_human の裁定で直す義務から外し（conflict.held_by_rulings）、外れた理由を返す"""
        import conflict
        conflict.park(self.place, [{"unit_key": R_CLAMP, "between": [], "why_both_cannot_hold": "上限を超えた値の扱いを人が決める",
                                    "which_is_right": conflict.UNKNOWN, "kind": conflict.NEEDS_CONTEXT}],
                      source=conflict.FIX_SOURCE, ruling={"decision": conflict.ASK, "text": "人が決める", "limits": [], "by": "t"})
        conflict.write_rulings(self.place)
        return fixboard.fix_duty(self.place, [R_MEAN, R_CLAMP])[1][R_CLAMP]

    def _held_turns(self, held_files: dict):
        """判定の写しを置き、段の頭の木を控えてから MEAN を直し、外れた単位 CLAMP の直し held_files {パス: 中身} を書く。返りは
        受け付けを回す口 accept(返答, iteration)"""
        (self.place / "judgment.json").write_text(json.dumps({"units": R_JUDGED}, ensure_ascii=False), encoding="utf-8")
        head = leftovers.snapshot(self.repo)
        path = self.repo / "stats.py"
        path.write_text(path.read_text(encoding="utf-8").replace("sum(xs) / (len(xs) - 1)", "sum(xs) / len(xs)"),
                        encoding="utf-8")
        for rel, text in held_files.items():
            (self.repo / rel).write_text(text, encoding="utf-8")

        def accept(reply, iteration):
            return fixboard.accept_reply(reply, self.place, self.repo, pass_="first", iteration=iteration,
                                         owed=[R_MEAN, R_CLAMP], judged=R_JUDGED, head=head, base_rev=self.rev, skip=SKIP)
        return accept

    def _held_row(self, files):
        return {"unit_key": R_CLAMP, "what": "上限の枝を直した", "files": files, **SELF_REPORT}

    def test_accept_reply_rejects_duplicate_unknown_and_excused_rows(self):
        """受け付けは単位の行を照らす: 同じ unit_key の 2 行・義務にも外れにも無い key・外れた単位の行（外れた理由を名指す）。
        元 works/blk-fix/scripts/accept.py:664-672（元の試験 works/tests/test_fix_duty.py:148・:193）"""
        why = self._hold_clamp()
        accept = self._held_turns({"held.txt": "上限の枝\n", "made-up.txt": "x\n"})
        reply = {"changes": [_fix_row(R_MEAN, 1), _fix_row(R_MEAN, 1), {**_fix_row("作り話の単位", 0), "files": ["made-up.txt"]},
                             self._held_row(["held.txt"])], "not_done": []}
        got = accept(reply, 1)
        self.assertFalse(got["ok"], got)
        rows = [(r["check"], r["text"]) for r in got["rejects"] if r["check"] in ("duplicate", "not_opened", "excused")]
        self.assertEqual(rows, [("duplicate", fixboard.DUPLICATE + R_MEAN), ("not_opened", fixboard.NOT_OPENED + "作り話の単位"),
                                ("excused", f"{fixboard.EXCUSED}{R_CLAMP}（{why}）")])
        self.assertNotIn(fixboard.NOT_OPENED + R_CLAMP, got["reason"], "外れた単位は作り話の key と分けて名指す")

    def test_last_turn_drops_only_the_excused_row(self):
        """最後の回: 外れた単位にだけ結んだ拒否の行は数えず、その単位の行を changes から外して残りで受ける。外れた単位の直しは
        作業ツリーに残し、ほかの単位を止めない（trace に ABSORBED_OP）。元 works/blk-fix/scripts/accept.py:636-645・:725-726
        （元の試験 works/tests/test_fix_duty.py:157 test_last_round_drops_only_the_excused_unit・:167 の bash_writes の申告）"""
        import conflict
        why = self._hold_clamp()
        accept = self._held_turns({"held.txt": "上限の枝\n", "held-gen.txt": "生成\n"})
        reply = {"changes": [_fix_row(R_MEAN, 1), self._held_row(["held.txt"])], "not_done": [],
                 "bash_writes": [{"path": "held-gen.txt", "why": WHY}]}
        excused = f"{fixboard.EXCUSED}{R_CLAMP}（{why}）"
        got = accept(reply, 1)
        self.assertEqual((got["ok"], got["rejects"]), (False, [{"check": "excused", "text": excused}]), got)
        got = accept(reply, 3)
        self.assertTrue(got["ok"], got["reason"])
        self.assertEqual([c["unit_key"] for c in got["reply"]["changes"]], [R_MEAN])
        self.assertEqual(got["parked"], {})
        self.assertEqual(got["units"], {R_MEAN: {"status": "fixed", "reason": ""}, R_CLAMP: {"status": "not_done", "reason": why}})
        self.assertIn("sum(xs) / len(xs)", (self.repo / "stats.py").read_text(encoding="utf-8"), "残りの単位の直しを戻さない")
        self.assertEqual((self.repo / "held.txt").read_text(encoding="utf-8"), "上限の枝\n", "外れた単位の直しは作業ツリーに残す")
        self.assertEqual([r["unit_key"] for r in conflict.items(self.place)], [R_CLAMP], "新しく止めた単位は無い")
        rows = [r for r in _traced(self.place) if r["op"] in (fixboard.ABSORBED_OP, conflict.ACCEPT_PARKED_OP)]
        self.assertEqual([(r["op"], r["dropped"], r["absorbed"]) for r in rows], [(fixboard.ABSORBED_OP, [R_CLAMP], [excused])])

    def test_last_turn_parks_the_duplicate_and_absorbs_the_excused_row(self):
        """最後の回: 重なりの行は MEAN に結んで止め（stats.py を戻す）、外れた単位の行は数えずに行だけを外す（held.txt は戻さない）。
        元の試験 works/tests/test_fix_duty.py:181 test_last_round_duplicate_parks_and_excused_row_is_absorbed"""
        import conflict
        self._hold_clamp()
        accept = self._held_turns({"held.txt": "上限の枝\n"})
        reply = {"changes": [_fix_row(R_MEAN, 1), self._held_row(["held.txt"]), _fix_row(R_MEAN, 1)], "not_done": []}
        got = accept(reply, 3)
        self.assertTrue(got["ok"], got["reason"])
        self.assertEqual((got["reply"]["changes"], list(got["parked"])), ([], [R_MEAN]))
        self.assertIn("(len(xs) - 1)", (self.repo / "stats.py").read_text(encoding="utf-8"), "止めた単位の直しは戻した")
        self.assertTrue((self.repo / "held.txt").is_file(), "外れた単位の直しは戻さない")
        self.assertEqual([r["unit_key"] for r in conflict.items(self.place)], [R_CLAMP, R_MEAN])
        self.assertEqual([r["dropped"] for r in _traced(self.place) if r["op"] == fixboard.ABSORBED_OP], [[R_CLAMP]])

    def test_last_turn_without_bound_unit_parks_the_rest_or_gives_up(self):
        """最後の回に止める単位が残らないのに写しの拒否が残れば（外れた単位の足跡の Markdown のリンクが届かない）、義務の残りを
        全部止めて通し直し（parking.park_owed）、それでも残れば受けずに諦める（NOT_SETTLED）。元 works/blk-fix/scripts/accept.py:738-740
        （止めた後に残れば元は機械の空の返答 hand_empty を渡した。今は受けずに諦める）"""
        import conflict
        import parking
        self._hold_clamp()
        accept = self._held_turns({"held.md": "# 覚え\n\n[無い](gone.md)\n"})
        reply = {"changes": [_fix_row(R_MEAN, 1), self._held_row(["held.md"])], "not_done": []}
        got = accept(reply, 3)
        self.assertFalse(got["ok"], got)
        self.assertTrue(got["reason"].startswith(fixboard.NOT_SETTLED), got["reason"])
        self.assertIn("gone.md", got["reason"])
        self.assertEqual(list(got["parked"]), [R_MEAN], "義務の残りを全部止めた")
        self.assertEqual(got["units"][R_MEAN]["status"], "given_up")
        self.assertIn(parking.OUT_ONLY, got["parked"][R_MEAN])
        self.assertIn("(len(xs) - 1)", (self.repo / "stats.py").read_text(encoding="utf-8"), "止めた単位の直しは戻した")
        self.assertTrue((self.repo / "held.md").is_file(), "外れた単位の直しは戻さない")
        self.assertEqual([r["unit_key"] for r in conflict.items(self.place)], [R_CLAMP, R_MEAN])

    def test_pack_copy_change_is_rejected(self):
        """除くパスの頭（script が渡す実行基盤の工程の写しの置き場。ここでは SKIP）の下を changes[].files に申告した・修正の段の
        頭の控え（record_skipped）から中身を変えた・足した・消した返答を拒む。触れなければ通る。元 works/blk-fix/scripts/accept.py:234
        check_pack_copy・:663（元の試験 works/tests/test_blk_fix.py:1154-1175）"""
        copy = self.repo / "vendored" / "workflows" / "x.yaml"
        copy.parent.mkdir(parents=True)
        copy.write_text("a: 1\n", encoding="utf-8")
        fixboard.record_skipped(self.place, self.repo, SKIP)
        (self.place / "judgment.json").write_text(json.dumps({"units": R_JUDGED}, ensure_ascii=False), encoding="utf-8")
        head = leftovers.snapshot(self.repo)
        path = self.repo / "stats.py"
        text = path.read_text(encoding="utf-8")
        for old, new in R_FIXED.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")

        def accept(reply):
            return fixboard.accept_reply(reply, self.place, self.repo, pass_="first", iteration=1, owed=[R_MEAN, R_CLAMP],
                                         judged=R_JUDGED, head=head, base_rev=self.rev, skip=SKIP)
        declared = _fix_ok()
        declared["changes"][0]["files"].append("vendored/workflows/x.yaml")
        got = accept(declared)
        self.assertFalse(got["ok"], got)
        packs = [r["text"] for r in got["rejects"] if r["check"] == "pack"]
        self.assertEqual(len(packs), 1, got["rejects"])
        self.assertIn("vendored/workflows/x.yaml", packs[0])
        self.assertIn("vendored/", packs[0])
        copy.write_text("a: 2\n", encoding="utf-8")
        (copy.parent / "added.txt").write_text("x\n", encoding="utf-8")
        got = accept(_fix_ok())
        packs = [r["text"] for r in got["rejects"] if r["check"] == "pack"]
        self.assertEqual(len(packs), 1, got["rejects"])
        for word in ("vendored/workflows/x.yaml", "vendored/workflows/added.txt", "戻"):
            self.assertIn(word, packs[0])
        copy.unlink()
        (copy.parent / "added.txt").unlink()
        packs = [r["text"] for r in accept(_fix_ok())["rejects"] if r["check"] == "pack"]
        self.assertEqual(len(packs), 1, "消した写しも拒む")
        self.assertIn("vendored/workflows/x.yaml", packs[0])
        copy.write_text("a: 1\n", encoding="utf-8")
        self.assertTrue(accept(_fix_ok())["ok"], "前から在る写しに触れない修正は通る")


class OverflowTraceSeamCase(TempCase):
    """受けた回の impact.ACCEPT_OVERFLOW_OP の行（fixboard.overflow_trace。元 works/blk-fix/scripts/accept.py:715）が、守りのテストと
    関所の条件の相談で認めた新しいテストを元と同じ字で名指す"""

    GATE_ID = "test_stats.py::TestStats::test_mean_of_three"   # 種の今の木に在る
    GONE_ID = "test_stats.py::TestStats::test_not_written"

    def overflow_rows(self, attempt=1):
        import impact
        fixboard.overflow_trace(self.place, {"reverted": []}, self.repo, pass_="first", attempt=attempt)
        return [r for r in _traced(self.place) if r["op"] == impact.ACCEPT_OVERFLOW_OP]

    def test_nothing_to_name_writes_no_row(self):
        self.assertEqual(self.overflow_rows(), [])

    def test_accepted_guard_test_is_named_in_the_overflow_trace(self):
        import fixgates
        import impact
        (self.place / fixgates.LEDGER).write_text(json.dumps({"rows": [], "skipped": [], "guards": [
            {"pass": "first", "attempt": 1, "id": self.GATE_ID, "base": "passed"},
            {"pass": "first", "attempt": 2, "id": self.GONE_ID, "base": "passed"}]}), encoding="utf-8")
        (row,) = self.overflow_rows()
        self.assertEqual(row["guards"], [f"{self.GATE_ID}: 守りのテスト（base で passed）"])
        self.assertEqual((row["agreed"], row["reverted"], row["gate_tests"]), ([], [], []))
        self.assertEqual(set(row) - {"op", "node"}, set(impact.ACCEPT_OVERFLOW_KEYS), "行の鍵は impact の定数が持つ")

    def asked(self, *grants):
        import conflict
        for i, (origin, tid) in enumerate(grants, 1):
            fixboard.trace(self.place, conflict.ASKED_OP, id=i, item="1", status="answered", decision="allow", origin=origin,
                           granted_paths=[], granted_tests=[], granted_new_tests=[{"id": tid, "red_kind": "assertion"}],
                           reason="足してよい")

    def test_gate_agreed_new_test_is_named_in_the_overflow_trace(self):
        import consult
        self.asked((consult.ORIGIN_GATE, self.GATE_ID), (consult.ORIGIN_GATE, self.GONE_ID))
        (row,) = self.overflow_rows()
        self.assertEqual(row["gate_tests"], [f"{self.GATE_ID}（assertion）"], "今の木に無いテストは名指さない")
        self.assertEqual((row["agreed"], row["reverted"], row["guards"]), ([], [], []))

    def test_accept_agreed_test_is_not_a_gate_test(self):
        import consult
        self.asked((consult.ORIGIN_ACCEPT, self.GATE_ID))
        (row,) = self.overflow_rows()
        self.assertEqual((row["agreed"], row["gate_tests"]), ([1], []))


class GateItemsSeamCase(unittest.TestCase):
    """直す前の人の関所の答え {decision, text} が、範囲の相談の人の条件（consult.gate_notes）に届く"""

    def test_pass_word_with_text_becomes_a_note(self):
        import consult
        import fixboard
        for word in ("approve", "continue"):
            rows = fixboard.gate_items({"decision": word, "text": "テストの名は変えないこと"})
            self.assertEqual(consult.gate_notes("unused", rows), "テストの名は変えないこと")

    def test_no_note_without_text_or_on_stop(self):
        import consult
        import fixboard
        for answers in (None, "", {"decision": "stop", "text": "止める"}):
            self.assertEqual(fixboard.gate_items(answers), [])
        for answers in ({"decision": "approve", "text": ""}, {"decision": "approve"}):
            self.assertEqual(consult.gate_notes("unused", fixboard.gate_items(answers)), "")


class SettleOverflowSeamCase(TempCase):
    """はみ出しの行だけの回の道筋（fixboard.settle_overflow。元 works/blk-fix/scripts/accept.py:549）: 承認済みの項目の範囲の外に
    触れた返答は、まだ聞いていなければ拒まずに範囲の相談に積み（次の consult_ask が頼みにする）、聞いて deny された同じはみ出しは
    機械が段の頭の木に戻して受け付ける"""

    DENY = {"answers": [{"ask": 1, "decision": "deny", "reason": "見本の入力は直しに要らないので範囲に足さない"}]}

    def setUp(self):
        super().setUp()
        import planmarks
        planmarks.save(self.place, 1, [{"route": "direct", "tests": [], "rewrite_tests": [], "allowed_paths": ["stats.py"],
                                         "out_of_scope": []}])
        (self.place / f"{planmarks.NODE}.json").write_text(json.dumps(
            {"plan": [{"unit_keys": [R_MEAN], "approach": "分母を直す", "adds": [], "removes": []}]}, ensure_ascii=False),
            encoding="utf-8")
        (self.place / "judgment.json").write_text(json.dumps({"units": [R_JUDGED[0]]}, ensure_ascii=False), encoding="utf-8")
        self.head = leftovers.snapshot(self.repo)
        self.extra = self.repo / "request_ok.json"
        self.before = self.extra.read_bytes()
        path = self.repo / "stats.py"
        path.write_text(path.read_text(encoding="utf-8").replace("sum(xs) / (len(xs) - 1)", "sum(xs) / len(xs)"),
                        encoding="utf-8")
        self.extra.write_bytes(self.before + b"\n")
        self.reply = {"changes": [{**_fix_row(R_MEAN, 1), "files": ["stats.py", "request_ok.json"]}], "not_done": []}
        self.kw = dict(pass_="first", owed=[R_MEAN], judged=[R_JUDGED[0]], head=self.head, skip=SKIP, base_rev=self.rev)

    def items(self):
        import factchecks
        return factchecks.place_items(self.place)()

    def test_unasked_overflow_is_queued_not_rejected(self):
        import consult
        got = fixboard.accept_reply(self.reply, self.place, self.repo, iteration=1, **self.kw)
        self.assertFalse(got["ok"], got)
        self.assertTrue(got.get("queued"), got["reason"])
        self.assertTrue(got["reason"].startswith(fixboard.QUEUED), got["reason"])
        self.assertEqual(self.extra.read_bytes(), self.before + b"\n", "積んだ回は作業ツリーを変えない")
        rows = consult.queued(self.place, "first")
        self.assertEqual([(r["paths"], r["origin"]) for r in rows], [(["request_ok.json"], consult.ORIGIN_ACCEPT)])
        ask = fixboard.consult_ask(self.place, self.reply, "first", self.items(), node="consult-answer")
        self.assertEqual((ask["consulted"], ask["go"]), (True, True), ask)
        self.assertIn("request_ok.json", pathlib.Path(ask["prompt_file"]).read_text(encoding="utf-8"))
        self.assertEqual(consult.queued(self.place, "first"), [], "頼みにした後は積んだ物を空にする")

    def test_denied_overflow_is_reverted_and_accepted(self):
        import consult
        import impact
        self.assertTrue(fixboard.accept_reply(self.reply, self.place, self.repo, iteration=1, **self.kw).get("queued"))
        fixboard.consult_ask(self.place, self.reply, "first", self.items(), node="consult-answer")
        consult.settle(self.place, self.DENY, "first", "consult-answer")
        got = fixboard.accept_reply(self.reply, self.place, self.repo, iteration=2, **self.kw)
        self.assertTrue(got["ok"], got["reason"])
        self.assertEqual(self.extra.read_bytes(), self.before, "deny されたはみ出しは段の頭の姿に戻す")
        self.assertIn("sum(xs) / len(xs)", (self.repo / "stats.py").read_text(encoding="utf-8"))
        self.assertEqual([c["files"] for c in got["reply"]["changes"]], [["stats.py"]])
        rows = [r for r in _traced(self.place) if r["op"] == impact.ACCEPT_OVERFLOW_OP]
        self.assertEqual([r["reverted"][0]["paths"] for r in rows], [["request_ok.json"]], rows)
        self.assertTrue(pathlib.Path(rows[0]["reverted"][0]["patch"]).is_file())

    def test_copy_reject_turns_overflow_into_a_reject(self):
        """はみ出しだけに見える回でも、写しの照らし（数え直し）を乾いた形で先に当て、写しの拒否が在れば相談に積まずに拒む
        （後で見つかる写しの拒否で相談の周を無駄にしない。元 works/blk-fix/scripts/accept.py:675-681）"""
        import consult
        import recount
        reply = {"changes": [{**_fix_row(R_MEAN, 1), "bypass_tried": "なし", "files": ["stats.py", "request_ok.json"]}],
                 "not_done": []}
        got = fixboard.accept_reply(reply, self.place, self.repo, iteration=1, **self.kw)
        self.assertFalse(got["ok"], got)
        self.assertFalse(got.get("queued"), got["reason"])
        self.assertTrue(any(r["check"] == "copy" and "bypass_tried が空同然" in r["text"] for r in got["rejects"]), got["rejects"])
        self.assertTrue(any(r["check"] == "scope" and "request_ok.json" in r["text"] for r in got["rejects"]), got["rejects"])
        self.assertEqual(consult.queued(self.place, "first"), [], "相談に積まない")
        self.assertEqual(self.extra.read_bytes(), self.before + b"\n", "拒んだ回は作業ツリーを変えない")
        self.assertFalse((self.place / recount.COVERAGE_FILE).exists(), "写しの照らしは乾いた形（件数を書かない）")


if __name__ == "__main__":
    unittest.main()

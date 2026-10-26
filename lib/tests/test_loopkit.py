"""輪と修正の block が共に使う部品（lib/loopkit.py）の検査。修正の block の common.py から出した物の振る舞いのうち、輪の状態の骨・記録の写し・
組の出口の行・申し出の確かめ（置き場を引数で受ける形）・test_files の要素の決まり・状態の読み書きと流しを見る。
置き場は使い捨てのフォルダ。
"""
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import loopkit  # noqa: E402
import rolekit  # noqa: E402

BASE = {f: ({} if f in ("reused", "related") else "" if f in ("exe", "suite", "test_cmd", "test_cmd_note") else [])
        for f in loopkit.BASE_FIELDS}
BASE.update(exe="/bin/runner", suite="suite.py", test_cmd_gate=loopkit.GATE_OFF, baseline={}, baseline_exit=0)
A, B = "a.py f: 壊れている", "b.py g: 壊れている"


def skeleton(**kw):
    args = dict(base=BASE, work="/p/tdd-1", base_file="/p/base.json", keys=[A, B], excused={}, contract={}, handoff="tree0", light=())
    args.update(kw)
    return loopkit.skeleton(**args)


class SkeletonTest(unittest.TestCase):
    def test_keys_are_the_base_fields_then_the_loop_fields_in_one_fixed_order(self):
        st = skeleton()
        self.assertEqual(list(st)[:len(loopkit.BASE_FIELDS)], list(loopkit.BASE_FIELDS))
        self.assertEqual(list(st)[len(loopkit.BASE_FIELDS):],
                         ["work", "base_file", "open_units", "excused", "handoff", "phase", "tries", "reason", "iterations", "runs",
                          "order", "units", "queue", "cur", "unit_head", "green_tree", "done", "note", "frozen", "parked",
                          "parked_why", "contract", "light", "calls", "kinds"])

    def test_starts_at_the_route_phase_with_nothing_done(self):
        st = skeleton(excused={A: "外れた"}, contract={A: {"route": "tdd"}}, handoff="tree9")
        self.assertEqual((st["phase"], st["done"], st["iterations"], st["runs"], st["cur"]), ("route", False, 0, 1, 0))
        self.assertEqual((st["work"], st["base_file"], st["handoff"], st["excused"], st["contract"]),
                         ("/p/tdd-1", "/p/base.json", "tree9", {A: "外れた"}, {A: {"route": "tdd"}}))
        self.assertEqual((st["order"], st["units"], st["queue"], st["calls"], st["kinds"]), ([], {}, [], [], []))

    def test_light_keeps_only_the_units_in_open_units_sorted(self):
        self.assertEqual(skeleton(light=[B, "ghost", A])["light"], [A, B])
        self.assertEqual(skeleton(keys=[A], light=[B, A])["light"], [A])

    def test_base_fields_are_copied_by_name_and_a_missing_field_is_refused(self):
        self.assertEqual(skeleton()["exe"], "/bin/runner")
        broken = {k: v for k, v in BASE.items() if k != "baseline"}
        with self.assertRaises(KeyError):
            skeleton(base=broken)

    def test_the_skeleton_does_not_touch_the_files(self):
        with tempfile.TemporaryDirectory() as td:
            skeleton(work=pathlib.Path(td) / "tdd-1")
            self.assertEqual(list(pathlib.Path(td).iterdir()), [])


def done_state(**over):
    st = skeleton()
    st.update(order=[A, B], done=True, note="済んだ", suite="suite.py", queue=[A], frozen_tree="tree1",
              units={A: {**loopkit._unit(A, "tdd"), "green": "ok", "tests": ["t.py::T::t"], "test_files": ["t.py"], "files": ["a.py"],
                         "red_tree": "t1", "test_hashes": {"t.py": "h"}, "extra": "x"},
                     B: {**loopkit._unit(B, "direct", "直に直す"), "gave_up": ""}},
              parked=["c"], parked_why={"c": "ぶつかる"}, calls=[{"n": 1, "phase": "route", "unit_key": "", "ok": True}])
    st.update(over)
    return st


class RecordTest(unittest.TestCase):
    def test_record_carries_the_summary_path_it_is_given(self):
        rec = loopkit.record(done_state(), "/p/tdd-1/summary.md")
        self.assertEqual(rec["summary"], "/p/tdd-1/summary.md")
        self.assertIs(rec["done"], True)

    def test_unit_rows_hold_only_the_record_fields_and_fill_the_missing_ones(self):
        units = loopkit.record(done_state(), "s")["units"]
        self.assertEqual(list(units), [A, B])
        self.assertEqual(set(units[A]), set(loopkit.RECORD_UNIT))
        self.assertEqual((units[A]["green"], units[A]["test_hashes"], units[A]["tests"]), ("ok", {"t.py": "h"}, ["t.py::T::t"]))
        self.assertEqual((units[B]["route"], units[B]["test_hashes"], units[B]["red_tree"], units[B]["why"]), ("direct", {}, "", "直に直す"))

    def test_the_record_does_not_share_lists_with_the_state(self):
        st = done_state()
        rec = loopkit.record(st, "s")
        rec["units"][A]["tests"].append("x")
        rec["parked"].append("y")
        self.assertEqual(st["units"][A]["tests"], ["t.py::T::t"])
        self.assertEqual(st["parked"], ["c"])

    def test_no_suite_is_true_only_when_the_state_says_so(self):
        self.assertIs(loopkit.record(done_state(), "s")["no_suite"], False)
        self.assertIs(loopkit.record(done_state(no_suite=True), "s")["no_suite"], True)

    def test_gate_and_note_default_when_the_state_lacks_them(self):
        st = done_state()
        del st["test_cmd_gate"]
        rec = loopkit.record(st, "s")
        self.assertEqual((rec["test_cmd_gate"], rec["test_cmd_note"]), (loopkit.GATE_OFF, ""))


class ExitRowsTest(unittest.TestCase):
    def test_rows_follow_the_order_then_the_parked_units_outside_it(self):
        out = loopkit.exit_rows(done_state())
        self.assertEqual([r["unit_key"] for r in out["units"]], [A, B, "c"])
        self.assertEqual(out["units"][2]["route"], "parked")
        self.assertEqual(out["units"][2]["why"], "ぶつかる")
        for row in out["units"]:
            self.assertEqual(set(row), set(loopkit.FIELDS))

    def test_head_fields_come_from_the_state(self):
        out = loopkit.exit_rows(done_state(test_cmd_gate=loopkit.GATE_ON, test_cmd_note="n"))
        self.assertEqual((out["ran"], out["suite"], out["reason"]), (True, "suite.py", "済んだ"))
        self.assertEqual(out["test_cmd"], {"gate": loopkit.GATE_ON, "note": "n"})
        self.assertEqual(out["calls"], [{"n": 1, "phase": "route", "unit_key": "", "ok": True}])

    def test_reused_related_and_no_suite_are_added_only_when_present(self):
        plain = loopkit.exit_rows(done_state())
        self.assertEqual({"reused", "related", "no_suite"} & set(plain), set())
        out = loopkit.exit_rows(done_state(reused={"suite": "k"}, related={"applied": True, "x": 1}, no_suite=True))
        self.assertEqual((out["reused"], out["related"], out["no_suite"]), ({"suite": "k"}, {"applied": True, "x": 1}, True))
        self.assertEqual(out["reason"], "済んだ")
        self.assertNotIn("related", loopkit.exit_rows(done_state(related={"applied": False})))


class TestFilesTest(unittest.TestCase):
    def test_test_file_normalises_a_nonblank_string_and_refuses_the_rest(self):
        self.assertEqual(loopkit.test_file(" ./a//t.py "), "a/t.py")
        for bad in ("", "  ", None, 3, ["t.py"]):
            self.assertIsNone(loopkit.test_file(bad))

    def test_unit_test_files_drops_bad_elements_and_a_non_list(self):
        self.assertEqual(loopkit.unit_test_files({"test_files": ["./t.py", "", 1, "b/../u.py"]}), ["t.py", "u.py"])
        self.assertEqual(loopkit.unit_test_files({"test_files": "t.py"}), [])
        self.assertEqual(loopkit.unit_test_files(None), [])


class ConflictItemTest(unittest.TestCase):
    """置き場は状態から引かず、呼び手が値で渡す（request_file・cite_root・briefs_by_unit）"""

    def item(self, **over):
        return {"unit_key": A, "why_both_cannot_hold": "両方は同時に成り立たない理由を書いた", "between": [], "which_is_right": "unclear",
                **over}

    def call(self, reply, owed=(A,)):
        with tempfile.TemporaryDirectory() as td:
            return loopkit.conflict_item({"work": str(pathlib.Path(td) / "tdd-1")}, reply, td, set(owed),
                                         request_file="", cite_root=td, briefs_by_unit={})

    def test_extra_reply_fields_are_refused_before_anything_is_read(self):
        probs, item = self.call({"phase": "conflict", "bogus": 1, **self.item()})
        self.assertIsNone(item)
        self.assertIn("bogus", probs[0])

    def test_a_unit_outside_the_owed_set_is_refused(self):
        probs, item = self.call({"phase": "conflict", **self.item()}, owed=(B,))
        self.assertIsNone(item)
        self.assertTrue(any("直す義務の単位に無い" in p for p in probs), probs)

    def test_the_state_work_is_never_read_for_the_place(self):
        state = {"work": "/nonexistent/place/tdd-1"}
        with tempfile.TemporaryDirectory() as td:
            probs, item = loopkit.conflict_item(state, {"phase": "conflict", **self.item()}, td, {B}, request_file="", cite_root=td,
                                                briefs_by_unit={})
        self.assertIsNone(item)
        self.assertTrue(probs)

    def test_the_keyword_arguments_are_required(self):
        with self.assertRaises(TypeError):
            loopkit.conflict_item({"work": "/p"}, {"phase": "conflict"}, "/r", {A})


class StateFilesTest(unittest.TestCase):
    def test_save_then_load_round_trips_and_leaves_no_tmp_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "state.json"
            loopkit._save(path, {"a": 1, "日本語": [1]})
            self.assertEqual(loopkit._load(path), {"a": 1, "日本語": [1]})
            self.assertEqual(sorted(p.name for p in pathlib.Path(td).iterdir()), ["state.json"])

    def test_an_unreadable_state_raises_broken_naming_the_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "state.json"
            with self.assertRaises(loopkit.Broken) as cm:
                loopkit._load(path)
            self.assertIn(str(path), str(cm.exception))
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(loopkit.Broken):
                loopkit._load(path)

    def test_flush_unsent_hands_the_claims_to_park_and_empties_the_field(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "state.json"
            loopkit._save(path, {loopkit.UNSENT: [{"source": "x", "item": 1}]})
            seen = []
            loopkit.flush_unsent(path, seen.append)
            self.assertEqual(seen, [[{"source": "x", "item": 1}]])
            self.assertEqual(loopkit._load(path)[loopkit.UNSENT], [])
            loopkit.flush_unsent(path, seen.append)
            self.assertEqual(len(seen), 1, "空の並びは渡さない")

    def test_flush_keeps_the_claims_when_there_is_no_park(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "state.json"
            loopkit._save(path, {loopkit.UNSENT: [1]})
            loopkit.flush_unsent(path, None)
            self.assertEqual(loopkit._load(path)[loopkit.UNSENT], [1])


class SmallPartsTest(unittest.TestCase):
    def test_owed_drops_excused_and_parked_units_in_open_units_order(self):
        st = {"open_units": ["a", "b", "c", "d"], "excused": {"b": "w"}, "parked": ["d"]}
        self.assertEqual(loopkit._owed(st), ["a", "c"])

    def test_unit_row_has_every_exit_field(self):
        self.assertTrue(set(loopkit.FIELDS) <= set(loopkit._unit("k", "tdd")))
        self.assertEqual(loopkit._unit("k", "direct", "w")["why"], "w")

    def test_ids_are_normalised_and_the_parametrize_tail_is_dropped(self):
        self.assertEqual(loopkit._norm_id(" ./a/t.py::T::t "), "a/t.py::T::t")
        self.assertEqual(loopkit._id_base("./t.py::test_x[1]"), "t.py::test_x")
        self.assertEqual(loopkit.id_path("./a//t.py::T::t"), "a/t.py")

    def test_plan_tdd_refuses_moving_a_planned_tdd_unit_but_not_others(self):
        st = {"contract": {"k": {"route": "tdd", "tests": ["x", "y"]}, "d": {"route": "direct"}}}
        self.assertIn("受け入れのテスト 2 本", loopkit._plan_tdd(st, "k"))
        self.assertEqual((loopkit._plan_tdd(st, "d"), loopkit._plan_tdd(st, "none")), ("", ""))

    def test_verified_collects_the_tests_of_green_tdd_units_only(self):
        st = {"units": {"a": {"route": "tdd", "green": "ok", "tests": ["./t.py::T::a"]},
                        "b": {"route": "tdd", "green": "", "tests": ["t.py::T::b"]},
                        "c": {"route": "direct", "green": "ok", "tests": ["t.py::T::c"]}}}
        self.assertEqual(loopkit._verified(st), {"t.py::T::a"})

    def test_retry_max_is_the_give_up_count_of_rolekit(self):
        self.assertEqual(loopkit.retry_max(), rolekit.GIVE_UP_AFTER)

    def test_blank_reasons_are_the_ones_shorter_than_min_why(self):
        self.assertTrue(loopkit._blank("   short"))
        self.assertTrue(loopkit._blank(None))
        self.assertFalse(loopkit._blank("x" * loopkit.MIN_WHY))

    def test_abs_ids_make_the_path_part_absolute_and_keep_the_rest(self):
        got = loopkit._abs_ids("/repo", ["t.py::T::t", "u.py"])
        self.assertEqual(got, ["/repo/t.py::T::t", "/repo/u.py"])


if __name__ == "__main__":
    unittest.main()

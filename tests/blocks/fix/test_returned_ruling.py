"""返した段（独立の目から修正の段へ戻した周）で、前の段の人に回した裁定（ask_human）が止めるのは、裁定が名指した受け入れの
試験の赤の義務だけであること（docs/design/fix.md の 22.1 の「返した段の裁定の止め」。案 docs/plans の 2026-11-16-eyes-back-sort の
4 節の 2）。

- 裁定が掛かった単位でも、その試験に触れない返した項目（trim の行と、その試験を名指さない項目の unfinished の行）が在れば、
  直す義務に戻る（board.owed_units_but_asked・board.fix_duty）
- 戻した単位の計画の語は、その試験を名指す項目の unfinished の行を数えずに引き直す（route.plan_words）
- 名指した試験は、TDD の輪の約束（tdd.plan_contract）と事後の関門の受け入れのテスト（gates._accept_tests）から外れる
- 最初の段・今の段の裁定・ほかの裁定（fix_plan_item）・試験に触れる返した項目しか無い単位は、今どおり単位ごと止める
- 戻すのは試験の赤から出た申し出（機械が赤の段で諦めた物・not_red・red_at_base）の裁定だけで、直しの向きや範囲を人に聞いた裁定と、
  機械が緑の段で諦めた物（直しを 3 回とも緑にできず、人に聞くのは直しの向き）の裁定は単位ごと止める（案の 5 節の代案 C を採らない）。
  機械の諦めの段は、前の段の輪の記録（印 prior_pass）の単位の gave_up で見分け、理由の文では見分けない
- 返した段の控えが読めなければ、どの単位も戻さない（board.returned_units）
- 戻した単位の項目は、差分の審査に渡す範囲の欄（finish._scope → fixboard.scope_brief）で外れた印を持たない
- 戻した単位に返した段で立った新しい申し出は、受け付け（board.take_conflicts）が先に外さず確かめる
"""
from unittest import mock
import json
import pathlib
import tempfile
import unittest

from tests.blocks import kit

U1, U2 = "U1", "U2"
T_A = "tests/test_select.py::test_opaque_menu"      # 項目 1 の受け入れのテスト（裁定が名指す）
T_B = "tests/test_select.py::test_keeps_focus"      # 項目 2 の受け入れのテスト（裁定が名指さない）


def _row(rid, key, decision, why, *, prior=True, text="人に聞く: 名の展開の形をどちらで合わせるか", extra=None):
    out = {"id": rid, "round": 1, "source": "tdd-gave-up", "unit_key": key, "between": ["a.py:1", "b.py:1"],
           "why_both_cannot_hold": why, "which_is_right": "unknown", "kind": "needs_context", "status": "ruled",
           "ruling": {"decision": decision, "text": text, "limits": [], "by": "t", **(extra or {})}}
    if prior:
        out["prior_pass"] = True
    return out


class ReturnedRulingCase(unittest.TestCase):
    def place(self, kinds, rows, gave_up="red"):
        """2 つの tdd の項目（1: U1・T_A、2: U1 と U2・T_B）を凍らせ、裁定の行 rows と返した項目の種 kinds と、U1 を段 gave_up で
        諦めた前の段の輪の記録（印 prior_pass。gave_up が空なら記録を置かない）を置いた置き場"""
        runvals = kit.load("fix", "runvals")   # lib/ を sys.path に足す
        import planmarks
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        place = pathlib.Path(tmp.name)
        base = {"rewrite_tests": [], "refactor": {"declared": False, "why": ""}, "allowed_paths": [], "out_of_scope": [],
                "route": "tdd"}
        planmarks.save(place, 1, [{**base, "unit_keys": [U1], "tests": [{"id": T_A, "red_kind": "assertion"}]},
                                  {**base, "unit_keys": [U1, U2], "tests": [{"id": T_B, "red_kind": "assertion"}]}])
        runvals.write(place, {"item_kinds": kinds})
        (place / "conflicts.json").write_text(json.dumps({"items": rows}, ensure_ascii=False), encoding="utf-8")
        if gave_up:
            (place / "tdd-1").mkdir()
            (place / "tdd-1" / "record.json").write_text(json.dumps(
                {"prior_pass": True, "order": [U1], "units": {U1: {"route": "parked", "gave_up": gave_up}}}), encoding="utf-8")
        return place

    def named(self, prior=True):
        return [_row("c1-1", U1, "ask_human", f"TDD の赤の確認が 3 回とも通らなかった: 名指しの {T_A} が結果に居ない", prior=prior)]

    def owed(self, place):
        board = kit.load("fix", "board")
        return board.owed_units_but_asked(place, {U1, U2}), board.fix_duty(place, {U1, U2})[1]

    def test_unit_returns_to_duty_for_items_that_leave_the_named_test(self):
        place = self.place([{"item": 1, "kind": "unfinished"}, {"item": 2, "kind": "unfinished"}], self.named())
        owed, excused = self.owed(place)
        self.assertEqual(owed, {U1, U2}, "名指した試験に触れない項目 2 の作り残しが在るので、裁定の単位も直す義務に戻る")
        self.assertNotIn(U1, excused)
        route = kit.load("fix", "route")
        self.assertEqual(route.plan_words(place, [U1, U2])[U1], "tdd")
        tdd = kit.load("fix", "tdd")
        got = tdd.plan_contract(place, [U1, U2])
        self.assertEqual([t["id"] for t in got[U1]["tests"]], [T_B], "名指した試験の赤の義務は止めたまま")
        self.assertEqual([t["id"] for t in got[U2]["tests"]], [T_B])

    def test_trim_rows_return_the_unit_and_ask_no_red(self):
        place = self.place([{"item": 1, "kind": "trim"}, {"item": 1, "kind": "unfinished"}], self.named())
        owed, _ = self.owed(place)
        self.assertIn(U1, owed, "trim の行は赤の義務に触れないので直させる")
        route = kit.load("fix", "route")
        self.assertEqual(route.plan_words(place, [U1])[U1], "tidy",
                         "名指した試験の項目の作り残しは数えず、trim の行だけで語を引き直す（赤を求めない）")

    def test_only_rows_on_the_named_test_keep_the_unit_held(self):
        place = self.place([{"item": 1, "kind": "unfinished"}], self.named())
        owed, excused = self.owed(place)
        self.assertNotIn(U1, owed)
        self.assertIn("ask_human の裁定 c1-1", excused[U1])

    def test_first_pass_and_this_pass_rulings_hold_the_whole_unit(self):
        kinds = [{"item": 1, "kind": "trim"}, {"item": 2, "kind": "unfinished"}]
        for name, place in (("最初の段", self.place([], self.named())),
                            ("今の段の裁定", self.place(kinds, self.named(prior=False)))):
            with self.subTest(name):
                owed, _ = self.owed(place)
                self.assertNotIn(U1, owed)
                tdd = kit.load("fix", "tdd")
                self.assertEqual([t["id"] for t in tdd.plan_contract(place, [U1])[U1]["tests"]], [T_A, T_B])

    def test_plan_item_rulings_still_hold(self):
        row = _row("c1-1", U1, "fix_plan_item", f"{T_A} の前提が誤り", extra={"plan_items": [1], "plan_units": [U1]})
        row["replan"] = "waiting"
        place = self.place([{"item": 1, "kind": "trim"}, {"item": 2, "kind": "trim"}], [row])
        owed, _ = self.owed(place)
        self.assertNotIn(U1, owed)

    def test_a_ruling_naming_no_test_stops_every_test_of_the_unit(self):
        rows = [_row("c1-1", U1, "ask_human", "TDD の赤の確認が 3 回とも通らなかった")]
        place = self.place([{"item": 2, "kind": "unfinished"}], rows)
        owed, _ = self.owed(place)
        self.assertNotIn(U1, owed, "名指しが読めなければ単位の受け入れの試験の全部を名指したと読む（赤の義務を黙って外さない）")
        place = self.place([{"item": 2, "kind": "trim"}], rows)
        owed, _ = self.owed(place)
        self.assertIn(U1, owed)
        tdd = kit.load("fix", "tdd")
        self.assertEqual([t["id"] for t in tdd.plan_contract(place, [U1]).get(U1, {}).get("tests", [])], [])

    def test_the_after_gate_leaves_the_named_test(self):
        place = self.place([{"item": 2, "kind": "unfinished"}, {"item": 1, "kind": "trim"}], self.named())
        gates = kit.load("fix", "gates")
        import conflict
        rows, why = gates._accept_tests(place, conflict.frozen_fields(place, 1), owed={U1, U2})
        self.assertEqual([r["id"] for r in rows], [T_B])
        self.assertTrue(any(T_A in w for w in why), why)

    def test_a_ruling_asking_the_direction_holds_the_whole_unit(self):
        """試験の赤から出ていない申し出（直しの向きを人に聞いた物）の裁定は、返した段でも単位ごと止める"""
        ask = {"ask_why": {"changes": "direction", "line": "名の展開の形をどちらへ寄せるかは人の答えで変わる"}}
        row = _row("c1-1", U1, "ask_human", f"{T_A} の期待と brief の向きが食い違う", extra=ask)
        row.update(source="fix", kind="brief_vs_judgment")
        place = self.place([{"item": 1, "kind": "trim"}, {"item": 2, "kind": "unfinished"}], [row])
        owed, excused = self.owed(place)
        self.assertNotIn(U1, owed, "人が向きを決めると言った単位を機械が直さない")
        self.assertIn("ask_human の裁定 c1-1", excused[U1])
        tdd = kit.load("fix", "tdd")
        self.assertEqual([t["id"] for t in tdd.plan_contract(place, [U1])[U1]["tests"]], [T_A, T_B])

    def test_red_kinds_from_the_fix_role_also_return(self):
        for kind in ("not_red", "red_at_base"):
            with self.subTest(kind):
                row = self.named()[0]
                row.update(source="fix", kind=kind)
                place = self.place([{"item": 2, "kind": "unfinished"}], [row])
                owed, _ = self.owed(place)
                self.assertIn(U1, owed)

    def test_a_file_and_line_naming_names_the_tests_of_that_file(self):
        """between がファイルと行だけで試験を名指し、理由の文が別の試験の名を書いても、そのファイルの試験を名指したと読む"""
        row = _row("c1-1", U1, "ask_human", "TDD の赤の確認が 3 回とも通らなかった: test_keeps_focus は関わらない")
        row["between"] = ["tests/test_select.py:40", "src/select.py:12"]
        board = kit.load("fix", "board")
        place = self.place([{"item": 1, "kind": "trim"}], [row])
        self.assertEqual(board.ruled_stops(place)[U1]["tests"], sorted([T_A, T_B]))

    def test_a_machine_give_up_at_green_holds_the_whole_unit(self):
        """機械が緑の段で諦めた単位（人に聞くのは直しの向き）は、理由の文が赤の確認の形でも、返した段で単位ごと止める"""
        place = self.place([{"item": 1, "kind": "trim"}, {"item": 2, "kind": "unfinished"}], self.named(), gave_up="green")
        owed, excused = self.owed(place)
        self.assertNotIn(U1, owed, "緑で諦めた単位を機械が直しへ戻さない")
        self.assertIn("ask_human の裁定 c1-1", excused[U1])
        tdd = kit.load("fix", "tdd")
        self.assertEqual([t["id"] for t in tdd.plan_contract(place, [U1])[U1]["tests"]], [T_A, T_B])

    def test_a_machine_give_up_without_a_prior_record_holds_the_whole_unit(self):
        """前の段の輪の記録が無く、諦めた段が分からない機械の諦めは、止める側に倒す"""
        place = self.place([{"item": 1, "kind": "trim"}, {"item": 2, "kind": "unfinished"}], self.named(), gave_up="")
        owed, _ = self.owed(place)
        self.assertNotIn(U1, owed)

    def records(self, place, *docs):
        """輪の記録 tdd-<k>/record.json を docs の順に置き直す（place が置いた前の段の記録も上書きする）"""
        for k, doc in enumerate(docs, 1):
            (place / f"tdd-{k}").mkdir(exist_ok=True)
            (place / f"tdd-{k}" / "record.json").write_text(json.dumps(doc), encoding="utf-8")

    def test_a_give_up_at_both_red_and_green_holds_the_whole_unit(self):
        """前の段で赤の段と緑の段の両方で諦めた単位（諦めた段の集まりが {red, green}）は、赤だけの諦めでないので単位ごと止める"""
        place = self.place([{"item": 1, "kind": "trim"}, {"item": 2, "kind": "unfinished"}], self.named(), gave_up="")
        self.records(place, {"prior_pass": True, "order": [U1], "units": {U1: {"route": "parked", "gave_up": "red"}}},
                     {"prior_pass": True, "order": [U1], "units": {U1: {"route": "parked", "gave_up": "green"}}})
        owed, excused = self.owed(place)
        self.assertNotIn(U1, owed, "緑の段でも諦めた単位を機械が直しへ戻さない")
        self.assertIn("ask_human の裁定 c1-1", excused[U1])

    def test_only_records_marked_prior_tell_the_give_up_stage(self):
        """諦めた段は前の段の輪の記録（印 prior_pass）だけから読む。今の段の輪の記録が赤で諦めたと書いても、前の段の記録が無ければ
        単位ごと止める"""
        place = self.place([{"item": 1, "kind": "trim"}, {"item": 2, "kind": "unfinished"}], self.named(), gave_up="")
        self.records(place, {"order": [U1], "units": {U1: {"route": "parked", "gave_up": "red"}}})
        owed, _ = self.owed(place)
        self.assertNotIn(U1, owed, "今の段の記録の諦めで、前の段の裁定の単位を直しへ戻さない")
        self.records(place, {"prior_pass": True, "order": [U1], "units": {U1: {"route": "parked", "gave_up": "red"}}})
        owed, _ = self.owed(place)
        self.assertIn(U1, owed, "同じ記録に印 prior_pass が在れば赤の段の諦めとして戻す")

    def test_an_unreadable_return_holds_every_unit(self):
        """返した段の控えが読めなければ、どの単位も戻さない（ValueError を素通りさせると、義務を減らさない側の読みが単位を戻す）"""
        place = self.place([{"item": 1, "kind": "trim"}, {"item": 2, "kind": "unfinished"}], self.named())
        board = kit.load("fix", "board")
        with mock.patch.object(board, "ruled_stops", side_effect=ValueError("控えが読めない")):
            self.assertEqual(board.returned_units(place), {})
            self.assertNotIn(U1, board.owed_units_but_asked(place, {U1, U2}))

    def test_the_delta_review_scope_does_not_mark_a_returned_unit_held(self):
        place = self.place([{"item": 1, "kind": "trim"}, {"item": 2, "kind": "unfinished"}], self.named())
        files = kit.load("fix", "files")
        finish = kit.load("fix", "finish")
        from src import board   # finish が読む board（kit.load は読むたびに src を読み直す）
        (place / files.PLAN_REPLY_FILE).write_text("{}", encoding="utf-8")
        with mock.patch.object(board, "scope_brief", return_value={}) as brief:
            finish._scope(place)
        self.assertEqual(brief.call_args.kwargs["held"], {}, "直しへ戻した単位 U1 を外れた単位として渡さない")
        import fixboard
        items = [{"unit_keys": [U1], "allowed_paths": [], "tests": []}]
        with mock.patch("planrange.scope", return_value=({"items": items, "agreed": []}, None)):
            got = fixboard.scope_brief(place, items, held={})
            held = fixboard.scope_brief(place, items)
        self.assertNotIn("held", got["plan_items"][0])
        self.assertIn("held", held["plan_items"][0], "held を渡さなければ今どおり裁定の単位を外れた印にする")

    def test_take_conflicts_checks_a_new_entry_on_a_returned_unit(self):
        place = self.place([{"item": 1, "kind": "trim"}], self.named())
        board = kit.load("fix", "board")
        entry = {"unit_key": U1, "between": ["x"], "why_both_cannot_hold": "短い", "which_is_right": "unknown",
                 "kind": "needs_context"}
        with mock.patch("conflict.problems_by_entry", return_value=[(0, U1, ["形が外れた"])]) as checked:
            _, got = board.take_conflicts({"conflicts": [entry], "changes": []}, place, place, "ruled", {U1})
        self.assertTrue(checked.called, "戻した単位の申し出を、裁定が外した単位の物として先に外さない")
        self.assertFalse(got["ok"])


if __name__ == "__main__":
    unittest.main()

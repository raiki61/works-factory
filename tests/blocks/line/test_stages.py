"""2 つの修正の段の合わせ（workflows/line/src/stages.py の fixed。docs/design/line.md の 4.3）と、修正の段の控えの読み口（read・late_records）と、
script fixed の欄の読み。元は test_line.py の FixedCase（docs/design/README.md の 9.5）。

守る keep-essence: 6（受け付けが回さなかった試験の行 tests_left_lines）・11（単位ごとの閉鎖の表の行 closure_lines）
"""
import json
import unittest

from tests.blocks import kit

BLOCK = "line"


def fix(**kw) -> dict:
    """fix の受け皿の got（docs/design/fix.md の 1.2 の欄）"""
    got = {"ok": True, "reason": "", "units": [{"unit_id": "u1", "status": "given_up"}], "groups": [{"group_id": "g1"}],
           "conflicts": {"path": "fix/conflicts.json"}, "carry": None, "replan_items": ["1"], "objection": "", "diff": {"path": "fix/diff"},
           "start_tree": "t1", "reply": None, "ruled_reply": None, "scope": None, "checked": {"ok": True, "reason": ""},
           "allowed_test_changes": ["tests/a.py"], "changed": {"path_changed": False}, "x_scalars": {}, "handoffs": [], "handoff_titles": {}, "mismatched": [],
           "plan_declared": [], "stop_reason": "", "allowed_tests": {"path": "fix/allowed.json"}, "accept_trace": {"path": "fix/trace.json"},
           "closure": {"path": "fix/closure.json"}, "tdd_unit": {"path": "fix/tdd.json"}, "tdd": [{"units": []}], "frozen": None,
           "removed": [], "tdd_refused": {"refused": [], "unread": []}, "item_claims": None, "freeze_off": [], "removed_tests": [], "untested": [], "report": ["- 修正"]}
    got.update(kw)
    return got


def lens(**kw) -> dict:
    return {"ok": True, "status": "ok", "reason": "", "rows": None, "ran": 1, "failed": 0, "not_routed": 0,
            "carry": [{"where": "レンズ x", "text": "再実行の要あり"}], "report": [], **kw}


def delta(**kw) -> dict:
    return {"ok": True, "status": "ok", "reason": "", "rounds": 1, "pass": True, "holes": None, "diff": {"path": "delta/diff"},
            "carry": [], "report": [], **kw}


def values(**kw) -> dict:
    base = {"fix_in": {"go": True, "no_fix": False, "plan": {"path": "p.json"}, "ripple": {"path": "r.json"}},
            "fix": fix(), "after_fix": {"replan": False, "prior": None, "stop_reason": ""},
            "raise": {"units": [], "checks": True, "skip_why": "", "eyes_due": True, "raised": [], "counted": "", "lines": [], "stop_reason": ""},
            "lens": lens(), "delta": delta(), "replan": None, "refix": None, "lens_2": None, "delta_2": None}
    base.update(kw)
    return base


class FixedCase(unittest.TestCase):
    def setUp(self):
        self.s = kit.load(BLOCK, "stages")

    def test_first_fix_alone(self):
        got = self.s.fixed(values())
        self.assertEqual((got["conflicts"], got["refixed"], got["held"]), ([{"path": "fix/conflicts.json"}], False, False))
        self.assertEqual((got["go"], got["done"], got["diffed"], got["checks"], got["eyes_due"]), (True, True, True, True, True))
        self.assertEqual(got["diff"], {"path": "delta/diff"}, "最後の段の delta-review が回れば手直しの後の姿")
        self.assertEqual(self.s.fixed(values(delta=None, lens=None))["diff"], {"path": "fix/diff"}, "回らなければ最後の段の fix の diff")

    def test_no_fix_round(self):
        """L-W07: 直す物が無い周（fix-in の no_fix）は、直す物の無い形で最後のテストと独立の目へ進める（目は回す）"""
        got = self.s.fixed(values(fix_in={"go": True, "no_fix": True, "plan": None, "ripple": None}, fix=None, **{"raise": None}))
        self.assertEqual((got["no_fix"], got["go"], got["done"], got["diffed"], got["checks"], got["eyes_due"], got["units"], got["rejudge"]),
                         (True, True, True, False, False, True, [], False))

    def test_fix_not_run_without_no_fix_is_not_go(self):
        """承認ノードで止めた・計画ができなかった周は go: false の形（held ではない）"""
        got = self.s.fixed(values(fix_in={"go": False, "no_fix": False, "plan": None, "ripple": None}, fix=None))
        self.assertEqual((got["go"], got["held"], got["no_fix"]), (False, False, False))

    def test_fix_that_did_not_return_is_held(self):
        got = self.s.fixed(values(fix=None))
        self.assertEqual((got["go"], got["held"]), (False, True))
        self.assertEqual(self.s.held_of(values(fix=None)), (True, self.s.HELD_UNRETURNED))

    def test_replan_without_the_second_fix_is_held(self):
        got = self.s.fixed(values(after_fix={"replan": True, "prior": None, "stop_reason": ""}))
        self.assertEqual((got["held"], got["go"], got["done"]), (True, False, False))

    def test_a_line_script_stop_holds(self):
        for key in ("after_fix", "raise"):
            with self.subTest(stop=key):
                v = values()
                v[key] = {**v[key], "stop_reason": "works:line-script"}
                self.assertEqual(self.s.fixed(v)["held"], True)

    def test_a_fix_stop_holds_and_is_returned(self):
        """#403: fix か 2 度目の修正が止めの語（works:unrestored）を返したら held にして、その語を stop_reason で報告へ届ける"""
        for first, second in ((fix(stop_reason="works:unrestored"), None), (fix(), fix(stop_reason="works:unrestored"))):
            with self.subTest(refix=second is not None):
                got = self.s.fixed(values(fix=first, refix=second, after_fix={"replan": second is not None, "prior": None, "stop_reason": ""}))
                self.assertEqual((got["done"], got["go"], got["rejudge"], got["stop_reason"]), (False, False, False, "works:unrestored"))

    def test_broken_review_stops_but_failed_review_goes_on(self):
        """lens・delta-review の ok が偽（段が壊れた）なら止め、審査が通らなかった・諦めたは止めずに残りに数える（delta-review の 1.6）"""
        for broken in ({"lens": lens(ok=False)}, {"delta": delta(ok=False)}):
            with self.subTest(broken=sorted(broken)):
                self.assertFalse(self.s.fixed(values(**broken))["go"])
        failed = self.s.fixed(values(delta={**delta(status="gave_up"), "pass": False}))
        self.assertEqual((failed["go"], failed["done"]), (True, False))
        self.assertEqual(failed["left"][0]["where"], "差分の審査")

    def test_returned_stages_follow_the_second(self):
        """values の more に独立の目から返した段の fix の got を渡すと、stages が 3 段目以降を持ち、units・item_claims・objection・tdd は
        more まで合わせ、go と done は more の最後の段で決まり（返した段は lens・delta を回さない）、出力の more に並びが残る"""
        refix = fix(units=[{"unit_id": "u1", "status": "fixed"}], replan_items=[], tdd=[{"units": [1]}], diff={"path": "refix/diff"})
        back = fix(units=[{"unit_id": "u1", "status": "fixed"}, {"unit_id": "u3", "status": "fixed"}], groups=[{"group_id": "g3"}], tdd=[{"units": [3]}],
                   diff={"path": "back/diff"}, objection="返しの段の異議", changed={"path_changed": True}, handoffs=["h1"],
                   item_claims={"items": None, "claims": []}, conflicts={"path": "back/conflicts.json"})
        got = self.s.fixed(values(refix=refix, replan={"plan": {"path": "replan/p.json"}, "ripple": {"path": "replan/r.json"}},
                                  after_fix={"replan": True, "prior": None, "stop_reason": ""}, lens_2=None, delta_2=None, more=[back]))
        self.assertEqual([s["stage"] for s in got["stages"]], [1, 2, 3])
        self.assertEqual((got["stages"][2]["fix"], got["stages"][2]["lens"], got["stages"][2]["delta"]), (back, None, None))
        self.assertEqual(got["more"], [back])
        self.assertEqual([u["unit_id"] for u in got["units"]], ["u1", "u3"])
        self.assertEqual([g["group_id"] for g in got["groups"]], ["g1", "g3"])
        self.assertEqual(got["tdd"], [[{"units": []}], [{"units": [1]}], [{"units": [3]}]])
        self.assertEqual((got["objection"], got["changed"], got["handoffs"], got["diff"]), ("返しの段の異議", {"path_changed": True}, ["h1"], {"path": "back/diff"}))
        self.assertEqual(got["conflicts"], [{"path": "back/conflicts.json"}])
        self.assertEqual((got["go"], got["done"], got["held"]), (True, True, False), "返した段は lens・delta を回さないが、それまでの段の審査は数える")
        self.assertEqual(self.s.fixed(values())["more"], [], "返した段が無ければ空")
        stopped = self.s.fixed(values(more=[fix(stop_reason="works:unrestored")]))
        self.assertEqual((stopped["held"], stopped["go"], stopped["stop_reason"]), (True, False, "works:unrestored"))
        fell = self.s.fixed(values(more=[None]))
        self.assertEqual((fell["held"], fell["go"]), (True, False), "返した段の修正が返らなければ held")
        unchecked = self.s.fixed(values(more=[fix(checked={"ok": False, "reason": "変えていない"})]))
        self.assertEqual((unchecked["go"], unchecked["done"]), (True, False))

    def test_returned_stage_without_refix_is_named_by_kind(self):
        """案の直しが走らない run で 1 回返した段は、並びの 2 番目でも「独立の目から返した修正の段（1 回目）」と呼ぶ（段の名は stages の行の
        種類 kind で引く）。差分の審査の行は「回していない」の訳、TDD の記録は種類の席（first・refix・returned）に並び、R2 へ渡る名も同じ"""
        report = __import__("report")
        back = fix(tdd=[{"group_id": "g3", "units": [3]}])
        got = self.s.fixed(values(more=[back]))
        self.assertEqual([s.get("kind") for s in got["stages"]], ["first", "returned"])
        final = kit.load(BLOCK, "final")
        returned = report.stage_name("returned", 1)
        self.assertEqual(returned, "独立の目から返した修正の段（1 回目）")
        self.assertIn(f"差分の審査（{returned}）: {final.RETURNED_NOT_RUN}", final.stage_delta_lines(got["stages"], ""))
        self.assertEqual(got["tdd"], [[{"units": []}], [], [{"group_id": "g3", "units": [3]}]], "refix が走らなければ refix の席は空")
        self.assertEqual([name for name, _ in report.tdd_stage_groups(2, got["tdd"][2])], [f"{returned}（組 g3）"])
        old = [{"stage": 1, "fix": fix()}, {"stage": 3, "fix": back}]   # kind を持つ前の記録（続きの run）は番号から種類を引く
        self.assertEqual(self.s.names(old), [report.TDD_STAGES[0], returned])
        self.assertEqual(report.stage_name("other"), f"{report.UNKNOWN_STAGE}（'other'）", "知らない種類でも落ちない")

    def test_unchecked_change_is_not_done(self):
        got = self.s.fixed(values(fix=fix(checked={"ok": False, "reason": "変えていない"}), lens=None, delta=None))
        self.assertEqual((got["go"], got["done"]), (True, False))

    def test_refix_is_merged_without_losing_the_first(self):
        refix = fix(units=[{"unit_id": "u1", "status": "fixed"}, {"unit_id": "u2", "status": "fixed"}], groups=[{"group_id": "g2"}],
                    conflicts=None, replan_items=[], diff={"path": "refix/diff"}, allowed_test_changes=["tests/b.py"], tdd=[{"units": [1]}])
        replanned = {"plan": {"path": "replan/p.json"}, "ripple": {"path": "replan/r.json"}}
        got = self.s.fixed(values(refix=refix, replan=replanned, after_fix={"replan": True, "prior": None, "stop_reason": ""},
                                  lens_2=lens(carry=[]), delta_2=delta(diff={"path": "delta-2/diff"})))
        self.assertTrue(got["done"])
        self.assertEqual(got["units"], [{"unit_id": "u1", "status": "fixed"}, {"unit_id": "u2", "status": "fixed"}])
        self.assertEqual(got["groups"], [{"group_id": "g1"}, {"group_id": "g2"}])
        self.assertEqual(got["conflicts"], [{"path": "fix/conflicts.json"}])
        self.assertEqual(got["allowed_test_changes"], ["tests/a.py", "tests/b.py"])
        self.assertEqual((got["diff"], got["replan_items"], got["refixed"]), ({"path": "delta-2/diff"}, ["1"], True))
        self.assertEqual((got["plan"], got["ripple"]), (replanned["plan"], replanned["ripple"]), "案の直しが走れば直した案")
        self.assertEqual([s["stage"] for s in got["stages"]], [1, 2])
        self.assertEqual(got["tdd"], [[{"units": []}], [{"units": [1]}]], "段ごとの fix の tdd を段の順に")
        self.assertEqual(got["carry"], [{"where": "レンズ x", "text": "再実行の要あり"}])

    def test_objection_and_rejudge(self):
        got = self.s.fixed(values(fix=fix(objection="判定が違う")))
        self.assertEqual((got["objection"], got["rejudge"]), ("判定が違う", True))
        held = self.s.fixed(values(fix=fix(objection="判定が違う", stop_reason="works:unrestored")))
        self.assertFalse(held["rejudge"], "held の時は再審しない")

    def test_spec_run_stops_on_an_objection(self):
        """仕様駆動の run（from_spec）: 修正の段の異議（判定への異議か、案の直しが要る項目）は、案の直しと再審へ進まず止めて人に返す
        （docs/design/spec-driven.md の 6.2 の変える node の 6）。異議の無い run は今どおり"""
        for kw in ({"objection": "判定が違う"}, {"replan_items": ["1"]}):
            with self.subTest(kw):
                got = self.s.fixed(values(fix=fix(**kw), from_spec=True))
                self.assertEqual((got["held"], got["go"], got["rejudge"], got["stop_reason"]), (True, False, False, self.s.SPEC_OBJECTION))
        got = self.s.fixed(values(fix=fix(replan_items=[]), from_spec=True))
        self.assertEqual((got["held"], got["go"], got["stop_reason"]), (False, True, ""))
        self.assertTrue(self.s.fixed(values(fix=fix(objection="判定が違う"), from_spec=False))["rejudge"])

    def test_item_claims_take_the_later_items_and_all_claims(self):
        def claims(approach, unit, files):
            return {"items": [{"item": 1, "unit_keys": ["u1"], "approach": approach, "after": []}],
                    "claims": [{"unit_key": unit, "files": files}], "unread": []}
        both = self.s.fixed(values(fix=fix(item_claims=claims("前の案", "u1", ["a.py"])),
                                   refix=fix(item_claims=claims("直した案", "u1", ["b.py"])),
                                   after_fix={"replan": True, "prior": None, "stop_reason": ""}))
        self.assertEqual(both["item_claims"]["items"][0]["approach"], "直した案")
        self.assertEqual(both["item_claims"]["claims"], [{"unit_key": "u1", "files": ["a.py"]}, {"unit_key": "u1", "files": ["b.py"]}])

    def test_every_field_of_the_yaml(self):
        """返りの欄が YAML の output_format の required と同じ（fallback も）"""
        import yaml
        doc = yaml.safe_load((kit.BLOCKS / BLOCK / "works-factory-line.yaml").read_text(encoding="utf-8"))
        node = next(n for n in doc["nodes"] if n["id"] == "fixed")
        self.assertEqual(set(self.s.fixed(values())), set(node["output_format"]["required"]))
        self.assertEqual(set(self.s.empty()), set(node["output_format"]["required"]))


class ReadCase(unittest.TestCase):
    """修正の段の控えの読み口（元 fixbeside.read・late_records）"""

    def setUp(self):
        self.s = kit.load(BLOCK, "stages")

    def test_read_merges_the_closure_and_names_the_unread(self):
        run = kit.Run(self, BLOCK)
        (run.artifacts / "fix").mkdir()
        (run.artifacts / "fix" / "closure.json").write_text(json.dumps({"rows": [{"unit_key": "u1", "closed": False}], "claimed": ["u1"]}))
        (run.artifacts / "fix" / "diff").write_text("")
        (run.artifacts / "fix" / "trace.json").write_text(json.dumps([{"op": "fix_tests_selected", "ci_left": ["t1"], "attempt": 1}]))
        stage = self.s.stage({**fix(), **{k: {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": f"fix/{n}"}
                                         for k, n in (("diff", "diff"), ("closure", "closure.json"), ("accept_trace", "trace.json"),
                                                      ("allowed_tests", "allowed.json"), ("tdd_unit", "tdd.json"))}}, "修正の段")
        with run.env():
            got = self.s.read([stage], self.s.resolve)
        self.assertEqual(self.s.not_closed(got), ["u1"])
        self.assertIn("修正の受け付けが手元で回さなかった試験（1 件", self.s.tests_left_lines(got)[0])
        self.assertTrue(any("allowed_tests" in x for x in got["unread"]), got["unread"])
        self.assertEqual(self.s.closure_lines(got), self.s.closure_lines(got))   # querytest の行の形は lib の試験が見る
        self.assertIn(self.s.ANOMALY_LINE, self.s.always_rows(got))

    def test_read_carries_removed_tests_and_untested_with_the_stage_name(self):
        """下書き 4.1 の 7: 段ごとの欄 removed_tests・untested は段の名を付けて段の順に並び、行の並びでない欄は読めなかった訳になる
        （黙って空にしない）"""
        report = __import__("report")
        gone = {"group_id": "g1", "weapon": "remove", "units": ["u1"], "tests": ["t.py::a"], "only_removed": ["t.py"]}
        plain = {"group_id": "g2", "weapon": "static", "units": ["u2"], "why": "文書だけ", "files": [{"path": "README.md", "kind": "docs"}]}
        first = {**self.s.stage(fix(), report.stage_name(report.FIRST)), "removed_tests": [gone], "untested": []}
        second = {**self.s.stage(fix(), report.stage_name(report.REFIX)), "removed_tests": [], "untested": [plain]}
        got = self.s.read([first, second], self.s.resolve)
        self.assertEqual(got["removed_tests"], [{**gone, "stage": report.TDD_STAGES[0]}])
        self.assertEqual(got["untested"], [{**plain, "stage": report.TDD_STAGES[1]}])
        bad = self.s.read([{**first, "removed_tests": None}], self.s.resolve)
        self.assertEqual(bad["removed_tests"], [])
        self.assertTrue(any("removed_tests" in x for x in bad["unread"]), bad["unread"])

    def test_late_records_name_missing_trace(self):
        got = self.s.late_records({"tdd_refused": {"refused": ["u1"], "unread": []}, "accept_trace": None}, self.s.resolve)
        self.assertEqual((got["refused"], got["missing"], got["trace"]), (["u1"], ["accept_trace"], None))
        self.assertIn("tdd_refused の形が違う", self.s.late_records({"tdd_refused": None, "accept_trace": None}, self.s.resolve)["unread"][0])

    def test_next_items_carry_once(self):
        rows = [{"where": "a", "text": "b"}, {"where": "a", "text": "b"}]
        self.assertEqual(self.s.next_items({"closure_unread": ["x"]}, rows),
                         [{"where": "a", "text": "b"}, {"where": "修正", "text": "x（確かめ直しの要あり）"}])


class FixedScriptCase(unittest.TestCase):
    """script fixed: 受け皿の got の欄を全部名指して読み、前の版の返り（欄の欠け）は止める（integration.md 4.3-12）"""

    def test_script_and_prior_version(self):
        run = kit.Run(self, BLOCK)
        v = values()
        args = {k: json.dumps(x) for k, x in v.items() if k != "raise"}
        got = run.script("fixed", **args, **{"raise": json.dumps(v["raise"])})
        self.assertEqual((got["go"], got["stop_reason"]), (True, ""))
        old = {k: x for k, x in fix().items() if k != "checked"}
        stopped = run.script("fixed", **{**args, "fix": json.dumps(old)}, **{"raise": json.dumps(v["raise"])})
        self.assertEqual((stopped["go"], stopped["held"], stopped["stop_reason"]), (False, True, "works:line-script"))

    def test_handoff_titles_of_both_fix_stages_reach_the_merged_fix(self):
        """修正役が添えた題（行 → 題）は、1 度目と 2 度目の修正の分をつなぐ。同じ行は先の修正の題"""
        run = kit.Run(self, BLOCK)
        v = values()
        first = fix(handoffs=["A"], handoff_titles={"A": "題 A", "B": "先の題 B"})
        again = fix(handoffs=["B", "C"], handoff_titles={"B": "後の題 B", "C": "題 C"})
        args = {k: json.dumps(x) for k, x in v.items() if k not in ("raise", "fix", "refix")}
        got = run.script("fixed", **args, fix=json.dumps(first), refix=json.dumps(again), **{"raise": json.dumps(v["raise"])})
        self.assertEqual(got["handoff_titles"], {"A": "題 A", "B": "先の題 B", "C": "題 C"})


if __name__ == "__main__":
    unittest.main()

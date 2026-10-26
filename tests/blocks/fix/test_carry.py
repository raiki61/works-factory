"""修正の段の申し送り carry.json と port prior の試験（docs/design/fix.md の 1.4・7 節の prep.py・12.3・14.2 の test_carry.py）。

1 回目の修正の段（全体の形）の finish が place の申し出と裁定・TDD の輪の状態を carry.json に束ねて出力 carry で指し、2 回目の段の
prep が port prior でその束を受けて place の prior/ に置き直し、今の adopt_prior_pass と同じ写しをする（今は前の段の place の
フォルダを入力 prior_conflicts で名指して開いていた）。今の tests/workflows/test_fix.py の RefixCase・BlockScriptsCase の
test_refix_place_reads_the_first_pass_rulings・GroupChildScriptsCase の test_refix_child_sees_the_first_pass_and_returns_only_its_rows と、
lib/tests/test_blk_fix_tdd.py の test_second_place_sees_the_first_place_loops（adopt_prior_pass）を、フォルダの代わりに束で写した。
2 つの段は 1 つの run の 2 つの include（line__fix・line__refix-run）の place で回す（線の出力 carry の pointer がそのまま届く）。
写さない物: lib/tests/test_fix_seams.py の RefixSeamCase（差分の審査の手直し refix の継ぎ目。delta-review の block へ移った）
"""
import json
import pathlib
import shutil
import unittest

from tests.bin.gitkit import committed_copy
from tests.blocks import kit
from tests.blocks.fix import steps, support
from tests.blocks.fix import test_tdd as tddcase



def write_rulings(place):
    kit.load("fix", "rulings").write(place)


SEED = kit.ROOT / "tests" / "e2e" / "target-seed"
FIRST, SECOND = "line__fix", "line__refix-run"
JUDGMENT = {"units": [{"key": "A", "label": "block"}, {"key": "B", "label": "block"},
                      {"key": "C", "label": "suggest", "disposition": "do-now"}, {"key": "D", "label": "suggest"}],
            "questions": []}
PLAN = {"round": 1, "fields": [{"allowed_paths": ["**"], "out_of_scope": []}, {"allowed_paths": ["**"], "out_of_scope": []}]}
FIX_PLAN = {"plan": [{"unit_keys": ["A", "B"]}, {"unit_keys": ["C"]}]}
# 今の FixLoopPlace の判定と申し出の行（tests/workflows/test_fix.py の _FX_*）
MEAN, BOUND = "u-mean", "u-bound"
FX_JUDGMENT = {"units": [
    {"key": MEAN, "label": "block", "class_query": {
        "how": {"patterns": ["(len(xs) - 1)"], "fixed": True, "paths": ["stats.py"], "count": "lines"},
        "counts": "defects", "total": 1}},
    {"key": BOUND, "label": "block"}], "questions": []}
FX_BODY = {"between": ["stats.py:9", "test_stats.py:8"], "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
           "which_is_right": "request", "kind": "unnamed_test_broke", "round": 1, "source": "fix", "status": "ruled"}
FX_SCOPE = {**FX_BODY, "id": "c1-1", "unit_key": MEAN,
            "ruling": {"decision": "fix_test_scope", "text": "テストの期待を直してよい", "limits": ["test_stats.py"], "by": "ruler"}}
FX_REPLAN = {**FX_BODY, "id": "c1-2", "unit_key": BOUND, "replan": "waiting", "kind": "brief_vs_judgment",
             "ruling": {"decision": "fix_plan_item", "text": "項目 1 が誤り", "limits": [], "by": "ruler", "plan_items": [1],
                        "plan_units": [BOUND]}}


def _j(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _write(path, doc) -> pathlib.Path:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_j(doc), encoding="utf-8")
    return path


def _change(unit, files):
    """修正役の返答の changes の 1 行（自己申告の欄は tests/blocks/fix/support.py の SELF_REPORT）"""
    from tests.blocks.fix.support import SELF_REPORT
    return {"unit_key": unit, "files": files, "what": "直した", **SELF_REPORT,
            "closure": {"mechanism": "分母", "fix_mechanism": "len(xs)", "verified_how": "読んだ",
                        "sites": [{"site": f"{files[0]}:9", "red_seen": True}]}}


class StagesCase(unittest.TestCase):
    """1 つの run の 2 つの修正の段（include の道で place が分かれる）と、組の子の run（別の run directory）"""

    def setUp(self):
        self.carry = kit.load("fix", "carry")
        self.run = kit.Run(self, "fix")
        shutil.rmtree(self.run.repo)
        committed_copy(self.run.repo, SEED)
        self.repo, self.art = self.run.repo, self.run.artifacts
        self.first, self.second = self.art / "line" / "fix", self.art / "line" / "refix-run"

    def script(self, stage, node, **inputs):
        return self.run.script(node, include=f"{stage}__{node.replace('_', '-')}", **inputs)

    def intake(self, stage, **inputs):
        out = self.script(stage, "intake", **inputs)
        self.assertTrue(out["ok"], out)
        return out

    def first_stage(self, rows, *, judgment=JUDGMENT, plan=True) -> dict:
        """1 回目の段: intake → prep → 申し出と裁定の行を置き → join・assert-changed の控え → finish。finish の出力を返す"""
        more = {"plan": _j(PLAN), "fix_plan": _j(FIX_PLAN)} if plan else {}
        self.intake(FIRST, mode="whole", judgment=_j(judgment), **more)
        out = self.script(FIRST, "prep")
        if rows is not None:
            _write(self.first / "conflicts.json", {"items": list(rows)})
        self.joined(self.first, out["groups"])
        got = self.script(FIRST, "finish")
        self.assertTrue(got["ok"], got)
        return got

    def second_stage(self, prior, *, only='["1"]', judgment=JUDGMENT, plan=True) -> dict:
        more = {"plan": _j(PLAN), "fix_plan": _j(FIX_PLAN)} if plan else {}
        self.intake(SECOND, mode="whole", judgment=_j(judgment), only_items=only, prior=prior, **more)
        return self.script(SECOND, "prep")

    @staticmethod
    def joined(place, groups):
        _write(place / "join.json", {"par": False, "groups": [
            {"group_id": g["group_id"], "unit_ids": g["unit_ids"], "returned": True, "reason": ""} for g in groups],
            "units": [{"unit_id": k, "group_id": g["group_id"], "status": "fixed", "reason": ""} for g in groups
                      for k in g["unit_ids"]]})
        _write(place / "assert-changed.json", {"ok": True, "reason": ""})


class CarryCase(StagesCase):
    """carry.write・place_prior と出力 carry"""

    def test_nothing_to_carry_is_null(self):
        """申し出の控えも輪も無い段は carry.json を書かず、出力 carry は null。控えが在れば行が空でも束ねる"""
        got = self.first_stage(None)
        self.assertIsNone(got["carry"])
        self.assertFalse((self.first / "carry.json").exists())
        got = self.first_stage([])
        doc = json.loads((self.art / got["carry"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(doc, {"conflicts": {"items": []}, "loops": [], "accept": None, "bases": [], "returns": []})

    def test_finish_points_at_the_bundle(self):
        got = self.first_stage([FX_SCOPE])
        self.assertEqual(got["carry"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "line/fix/carry.json"})
        doc = json.loads((self.art / got["carry"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(doc, {"conflicts": {"items": [FX_SCOPE]}, "loops": [], "accept": None, "bases": [], "returns": []})

    def test_a_return_with_a_gone_frozen_file_is_carried(self):
        """tdd の返しの控えの frozen は、凍らせたファイルが無くなった時に null を持つ（common.hashes）。申し送りの形はそれを通し、
        finish は修正の段の出力を組める（輪の状態の frozen.json と同じ形）"""
        self.intake(FIRST, mode="whole", judgment=_j(JUDGMENT), plan=_j(PLAN), fix_plan=_j(FIX_PLAN))
        out = self.script(FIRST, "prep")
        _write(self.first / "returns" / "1.json",
               {"stage": 1, "weapon": "tdd", "group": "g1", "tree": "t", "units": [{"key": "A", "named": []}],
                "frozen": {"test_stats.py": "h1", "test_gone.py": None}, "frozen_tree": "t", "suite_made": [], "added": [],
                "rewritten": [], "removed": [], "files": [], "why_untested": ""})
        self.joined(self.first, out["groups"])
        got = self.script(FIRST, "finish")
        self.assertTrue(got["ok"], got)
        doc = json.loads((self.art / got["carry"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["returns"][0]["frozen"], {"test_stats.py": "h1", "test_gone.py": None})

    def test_group_form_carries_nothing(self):
        """組の形の finish は申し送りを返さない（2 回目の段に渡すのは全体の形の出力）"""
        self.intake(FIRST, mode="group", group=_j({"group_id": "g1", "unit_ids": ["A"], "items": []}), judgment=_j(JUDGMENT))
        _write(self.first / "conflicts.json", {"items": [FX_SCOPE]})
        self.assertIsNone(self.script(FIRST, "finish")["carry"])

    def test_write_and_place_prior_round_trip(self):
        """束は conflicts.json の中身と輪ごとの record.json の中身・summary.md の字を持ち（輪の状態は束に入れない）、place_prior が同じファイルに置き直す"""
        place, again = self.art / "one", self.art / "two"
        _write(place / "conflicts.json", {"items": [FX_SCOPE]})
        _write(place / "tdd-1" / "record.json", {"frozen": {"test_stats.py": "h1"}, "suite": "s", "done": True})
        _write(place / "tdd-1" / "state.json", {"frozen": {"test_stats.py": "h1"}, "contract": {}})   # 束には載らない
        (place / "tdd-1" / "summary.md").write_text("輪 1 の要約\n", encoding="utf-8")
        _write(place / "tdd-2" / "record.json", {"frozen": {}})
        _write(place / "accept.json", {"suite_made": ["a"]})
        _write(place / "bases" / "1" / "base.json", {"suite_made": ["b"]})
        _write(place / "bases" / "1" / "accept.json", {"adopted_from": "x"})
        _write(place / "returns" / "1.json", {"stage": 1, "weapon": "tdd"})
        path = self.carry.write(place)
        self.assertEqual(path, place / "carry.json")
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(doc, {"conflicts": {"items": [FX_SCOPE]},
                               "loops": [{"record": {"frozen": {"test_stats.py": "h1"}, "suite": "s", "done": True},
                                          "summary": "輪 1 の要約\n"},
                                         {"record": {"frozen": {}}, "summary": ""}],
                               "accept": {"suite_made": ["a"]},
                               "bases": [{"base": {"suite_made": ["b"]}, "accept": {"adopted_from": "x"}}],
                               "returns": [{"stage": 1, "weapon": "tdd"}]})
        root = self.carry.place_prior(again, doc)
        self.assertEqual(root, again / "prior")
        for rel in ("conflicts.json", "tdd-1/record.json", "tdd-1/summary.md", "tdd-2/record.json", "accept.json",
                    "bases/1/base.json", "bases/1/accept.json", "returns/1.json"):
            self.assertEqual(json.loads((root / rel).read_text(encoding="utf-8")) if rel.endswith(".json")
                             else (root / rel).read_text(encoding="utf-8"),
                             json.loads((place / rel).read_text(encoding="utf-8")) if rel.endswith(".json")
                             else (place / rel).read_text(encoding="utf-8"), rel)
        self.assertFalse((root / "tdd-2" / "summary.md").exists(), "空の要約は書かない")
        self.assertFalse((root / "tdd-1" / "state.json").exists(), "束は輪の状態を運ばない")

    def test_write_without_anything_is_none(self):
        place = self.art / "empty"
        place.mkdir()
        self.assertIsNone(self.carry.write(place))
        self.assertFalse((place / "carry.json").exists())

    def test_bad_shapes(self):
        with self.assertRaisesRegex(ValueError, "入力 prior が object でない"):
            self.carry.adopt(self.art / "x", ["not", "a", "bundle"], [], self.repo)
        with self.assertRaisesRegex(ValueError, r"入力 prior の loops\[0\] に record が無い"):
            self.carry.place_prior(self.art / "x", {"conflicts": None, "loops": [{"summary": "要約だけ"}]})
        with self.subTest("intake が形に合わない束を ok: false で返す"):
            out = self.script(SECOND, "intake", mode="whole", judgment=_j(JUDGMENT), prior=_j([1]))
            self.assertFalse(out["ok"])
            self.assertTrue(out["reason"].startswith("入力 prior: "), out)
            out = self.script(SECOND, "intake", mode="whole", judgment=_j(JUDGMENT), prior=_j({"loops": {}}))
            self.assertTrue(out["reason"].startswith("入力 prior: "), out)
        with self.subTest("record の無い輪の束は prep が落ちる"):
            self.intake(SECOND, mode="whole", judgment=_j(JUDGMENT), prior=_j({"conflicts": None, "loops": [{"summary": "x"}]}))
            err = self.run.failing("prep", include=f"{SECOND}__prep")
            self.assertIn("loops[0]", err)

    def test_null_prior_is_the_first_stage(self):
        """prior が null の段は prior/ を作らず、申し出の写しも無い"""
        self.intake(SECOND, mode="whole", judgment=_j(JUDGMENT), prior="null")
        self.script(SECOND, "prep")
        self.assertFalse((self.second / "prior").exists())
        self.assertFalse((self.second / "conflicts.json").exists())


class SecondStageCase(StagesCase):
    """2 回目の段が 1 回目の段の申し出と裁定を束で受ける（今の test_refix_place_reads_the_first_pass_rulings）"""

    def test_second_stage_reads_the_first_pass_rulings(self):
        """F216・L-W18・L-W48: 2 回目の修正の段の prep は port prior の束の申し出と裁定を写し、直す項目の待つ行を案を直した行にする
        （conflict.second_pass が真。裁定 fix_test_scope の範囲と直した項目の単位の許しが立つ）。この段で新しく fix_plan_item と裁いた
        行には「最後の人の関所で決める」の約束が出て、段を抜ける finish が諦めた行にする（CLOSE_WHY）。replan_items はこの段の項目
        だけ。1 回目の段の place は書き換えない"""
        import conflict
        import replan
        body = {"between": ["stats.py:9", "test_stats.py:8"], "why_both_cannot_hold": "テストと依頼が食い違う",
                "which_is_right": "request", "kind": "unnamed_test_broke", "round": 1, "source": "fix", "status": "ruled"}
        scope = {**body, "id": "c1-1", "unit_key": "A",
                 "ruling": {"decision": "fix_test_scope", "text": "テストを直してよい", "limits": ["test_stats.py"], "by": "ruler"}}
        waiting = {**body, "id": "c1-2", "unit_key": "B", "replan": "waiting",
                   "ruling": {"decision": "fix_plan_item", "text": "項目 1 が誤り", "limits": [], "by": "ruler",
                              "plan_items": [1], "plan_units": ["A", "B"]}}
        first = self.first_stage([scope, waiting])
        out = self.second_stage(_j(first["carry"]))
        rows = conflict.items(self.second)
        self.assertEqual([(r["id"], r.get(conflict.PRIOR)) for r in rows], [("c1-1", True), ("c1-2", True)])
        self.assertEqual(conflict.replan_state(rows[1]), conflict.AMENDED)
        self.assertTrue(conflict.second_pass(self.second))
        self.assertFalse(conflict.second_pass(self.first), "1 回目の段の place は書き換えない")
        self.assertTrue((self.second / "prior" / "conflicts.json").is_file(), "束は place の prior/ に置き直す")
        permits = {p["id"] for p in conflict.test_permits(self.second)}
        self.assertLessEqual({f"{conflict.RULED_TEST_ID}-c1-1", f"{conflict.AMENDED_TEST_ID}-c1-2"}, permits)
        new = conflict.park(self.second, [{"unit_key": "C", "between": ["stats.py:9", "test_stats.py:8"],
                                           "why_both_cannot_hold": "直した案の項目 2 も判定と食い違う", "which_is_right": "request",
                                           "kind": "brief_vs_judgment"}], source=conflict.FIX_SOURCE)
        conflict.apply_rulings(self.second, {new[0]: {"decision": "fix_plan_item", "text": "項目 2 も誤り", "limits": [],
                                                      "plan_items": [2], "plan_units": ["C"]}}, by="ruler")
        write_rulings(self.second)
        self.assertIn("this run's plan fix is already done", (self.second / conflict.RULINGS_FILE).read_text(encoding="utf-8"))
        self.joined(self.second, out["groups"])
        got = self.script(SECOND, "finish")
        self.assertEqual((got["replan_items"], got["conflicts"]["path"]), (["2"], "line/refix-run/conflicts.json"))
        last = conflict.items(self.second)[-1]
        self.assertEqual((conflict.replan_state(last), last[conflict.REPLAN_WHY]), (conflict.GAVE_UP, replan.CLOSE_WHY))
        self.assertEqual([r["id"] for r in conflict.asked(self.second)], [last["id"]])

    def test_items_outside_only_items_stay_waiting(self):
        """直す項目（only_items）に載らない待つ行は AMENDED へ移らない（今の conflict.adopt_prior）"""
        import conflict
        waiting = {**FX_REPLAN, "unit_key": "B", "ruling": {**FX_REPLAN["ruling"], "plan_items": [2], "plan_units": ["B"]}}
        first = self.first_stage([waiting])
        self.second_stage(_j(first["carry"]), only='["1"]')
        rows = conflict.items(self.second)
        self.assertEqual([r.get(conflict.PRIOR) for r in rows], [True])
        self.assertEqual(conflict.replan_state(rows[0]), conflict.WAITING)
        self.assertFalse(conflict.second_pass(self.second))

    def test_prep_resume_does_not_copy_twice(self):
        """prep を回し直しても、写した行を 2 度積まない"""
        import conflict
        first = self.first_stage([FX_SCOPE, FX_REPLAN], judgment=FX_JUDGMENT, plan=False)
        self.second_stage(_j(first["carry"]), judgment=FX_JUDGMENT, plan=False)
        self.script(SECOND, "prep")
        self.assertEqual([r["id"] for r in conflict.items(self.second)], ["c1-1", "c1-2"])


class RefixCase(StagesCase):
    """2 回目の段の受け付け（今の RefixCase）: 束で写した 1 回目の段の行を、組の子の受け付けと裁定の後の修正の輪が見る"""

    def prior(self, *rows) -> str:
        return _j({"conflicts": {"items": list(rows)}, "loops": []})

    def child(self, units) -> kit.Run:
        """2 回目の段の組の子の run（別の run directory・同じ作業ツリー。親の place の groups/ に書く）を group-start まで回す"""
        twin = self.run.other("fix")
        twin.artifacts = self.art.parent / "child-art"
        twin.artifacts.mkdir()
        out = twin.script("intake", mode="group", group=_j({"group_id": "g1", "unit_ids": units, "items": []}),
                          out_dir=str(self.second / "groups"))
        self.assertTrue(out["ok"], out)
        twin.script("group_start")
        return twin

    def test_refix_sees_first_pass_rulings(self):
        """L-W18・F044: 1 回目の段の裁定 fix_test_scope の範囲のテストの変更を、2 回目の段の組の子の受け付け（first）の事後の関門が
        許す（束 → 親の prep → 子の group-start が写す）"""
        import conflict
        self.second_stage(self.prior(FX_SCOPE, FX_REPLAN), judgment=FX_JUDGMENT, plan=False)
        twin = self.child([MEAN])
        self.assertTrue(conflict.second_pass(twin.artifacts))
        path = self.repo / "stats.py"
        path.write_text(path.read_text(encoding="utf-8").replace("sum(xs) / (len(xs) - 1)", "sum(xs) / len(xs)"), encoding="utf-8")
        path = self.repo / "test_stats.py"
        path.write_text(path.read_text(encoding="utf-8").replace("mean([1, 2, 3]), 2", "mean([2, 4]), 3"), encoding="utf-8")
        reply = {"changes": [_change(MEAN, ["stats.py", "test_stats.py"])]}
        out = twin.script("fix_accept", reply_variant=support.reply_json(reply), consulted="false")
        self.assertEqual((out["ok"], out["done"]), (True, True), out)

    def test_first_pass_rulings_are_not_fixed_again(self):
        """写した 1 回目の段の直す裁定（fix_test_scope）は 1 回目の段が直したので、2 回目の段の裁定の後の修正の輪を起こさない"""
        self.second_stage(self.prior(FX_SCOPE), judgment=FX_JUDGMENT, plan=False)
        out = self.script(SECOND, "fix_ruled_prep")
        self.assertFalse(out["go"], out)

    def test_second_give_up_after_replan_is_asked_to_human(self):
        """F023: 案を直して直す義務に戻った単位が、また TDD の確認の上限まで落ちたら、裁定に回さず ask_human（by tdd-repeat）で積む"""
        import conflict
        import stopby
        self.second_stage(self.prior(FX_REPLAN), judgment=FX_JUDGMENT, plan=False)
        item = {"unit_key": BOUND, "between": ["bounds.py:1", "test_stats.py:8"],
                "why_both_cannot_hold": "直した案でも上限の確認が 3 回落ちた", "which_is_right": "unknown", "kind": "needs_context"}
        ids = conflict.park_claims(self.second, [{"source": conflict.GAVE_UP_SOURCE, "item": item}])
        row = next(r for r in conflict.items(self.second) if r["id"] == ids[0])
        self.assertEqual((row["ruling"]["decision"], row["ruling"]["by"]), (conflict.ASK, stopby.TDD_REPEAT))
        self.assertEqual([r["id"] for r in conflict.this_pass(self.second)], ids)

    def test_refix_child_sees_the_first_pass_and_returns_only_its_rows(self):
        """L-W18・F023: 2 回目の段の組の子は、親の place が束から写した 1 回目の段の申し出と裁定を写して読み（conflict.second_pass
        が真）、結果の conflicts にはこの段の行だけを載せる（親の conflict-check が 1 回目の行を積み直さない）"""
        import conflict
        row = {**FX_REPLAN, "unit_key": MEAN, "ruling": {**FX_REPLAN["ruling"], "plan_units": [MEAN]}}
        self.second_stage(self.prior(row), judgment=FX_JUDGMENT, plan=False)
        twin = self.child([MEAN])
        self.assertTrue(conflict.second_pass(twin.artifacts))
        new = conflict.park(twin.artifacts, [{"unit_key": MEAN, "between": ["stats.py:9", "test_stats.py:8"],
                                              "why_both_cannot_hold": "直した後も分母が空の列で割れる", "which_is_right": "unknown",
                                              "kind": "needs_context"}], source=conflict.FIX_SOURCE)
        out = twin.script("group_end")
        result = json.loads(pathlib.Path(out["result_file"]).read_text(encoding="utf-8"))
        self.assertEqual([r["id"] for r in result["conflicts"]], new)


class PriorLoopsCase(tddcase.LoopCase):
    """F018: 1 回目の段の輪（tdd-1）が凍らせたテストは、2 回目の段の受け付けでも変えられない。束の loops が 2 回目の段の place と
    組の子の place に輪の状態を写す（今の test_second_place_sees_the_first_place_loops を、フォルダの代わりに束で）。写した輪は今の
    段の輪に数えない（board.ruled_states）"""

    def first_loop(self):
        """tdd-1: MEAN を tdd で緑にして test_stats.py を凍らせる"""
        self.route()
        self.red()
        self.assertTrue(self.fix_mean()["done"])
        self.assertEqual(list(self.st()["frozen"]), ["test_stats.py"])

    def test_second_place_sees_the_first_place_loops_through_the_bundle(self):
        from src import board, carry, facts, common, tdd
        self.first_loop()
        bundle = json.loads(carry.write(self.board).read_text(encoding="utf-8"))
        self.assertEqual([loop["record"]["frozen"] for loop in bundle["loops"]], [self.st()["frozen"]])
        second, child = self.board.parent / "refix-run", self.board.parent / "child"
        second.mkdir()
        child.mkdir()
        got = carry.adopt(second, bundle, ["1"], self.repo)
        self.assertEqual(got["loops"], [str(second / "tdd-1" / "record.json")])
        self.assertTrue(json.loads((second / "tdd-1" / "record.json").read_text(encoding="utf-8"))[board.PRIOR_LOOP])
        board.adopt_inputs(second, child, self.repo)
        for place in (second, child):
            with self.subTest(place=place.name):
                got = tdd.start(place, self.repo, str(self.suite), json.dumps([tddcase.CLAMP]))
                self.assertTrue(got["go"], got)
                rows = [{"unit_key": tddcase.CLAMP, "route": "direct", "why": "2 回目の段で先にテストを書かない単位"}]
                self.assertTrue(steps.loop_step(got["state_file"], {"phase": "route", "units": rows}, self.repo)["ok"])
                loop = steps.resolve(got["state_file"])
                record = tddcase.record_of(loop)
                self.assertEqual(len(common.records(place)), 2)
                self.assertEqual(board.ruled_states(place), (record, record))
                self.assertEqual(facts.check_frozen(place, record, self.repo, "first"), [])
                self.edit("test_stats.py", "mean([2, 4]), 3", "mean([2, 4]), 3.0")   # 2 回目の修正役が tdd-1 の凍ったテストを変えた
                problems = facts.check_frozen(place, record, self.repo, "first")
                self.assertTrue(problems and "test_stats.py" in problems[0], problems)
                self.edit("test_stats.py", "mean([2, 4]), 3.0", "mean([2, 4]), 3")


class BasesCarryCase(unittest.TestCase):
    """下書き docs/plans/2026-10-24-fix-weapons.md の 4.4 の 3 の縛る試験 (i)〜(iv): 元の結末 base.json と受け付けの書き戻し accept.json と
    返しの控え returns/ が、組を合わせる時に親へ（board.adopt_returned）、束 carry.json で 2 回目の修正の段の置き場へ（carry.adopt）、
    その組の子へ（board.adopt_inputs）写る。どの試験も対象の試験を走らせない（持ち主の決め base-runs-nothing）"""

    def setUp(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        kit.load("fix", "board")
        from src import basecase, board, carry, files
        self.basecase, self.board, self.carry, self.files = basecase, board, carry, files

    def child(self, name, *, accept=None, ret=None):
        """元の結末を取った組の子の置き場（base.json と、accept が在れば accept.json、ret が在れば returns/1.json）と、その組の結果"""
        place = self.root / name
        _write(place / self.files.BASE_FILE, {"work": str(place), "baseline_cases": [], "suite_made": [f"{name}.base"]})
        if accept is not None:
            _write(place / self.files.ACCEPT_FILE, accept)
        if ret is not None:
            _write(place / self.files.RETURNS_DIR / "1.json", ret)
        return {"group_id": name, "base": str(place / self.files.BASE_FILE), "place": str(place), "tdd_record": ""}

    def read(self, path):
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))

    def joined(self):
        """1 回目の段の親: 組 g1（accept.json と返しの控えあり）と g2（accept.json なし）を合わせ、親の裁定の後の受け付けが accept.json を書いた"""
        parent = self.root / "first"
        parent.mkdir()
        results = [self.child("g1", accept={"final_left": [], "suite_made": ["g1.accept"]},
                              ret={"stage": 1, "weapon": "tdd", "suite_made": ["g1.ret"], "added": [], "rewritten": []}),
                   self.child("g2")]
        self.board.adopt_returned(parent, self.repo, results)
        _write(parent / self.files.ACCEPT_FILE, {"final_left": [], "suite_made": ["first.accept"]})
        return parent, results

    def test_i_join_marks_accept_and_never_copies_twice(self):
        """(i) 親の bases/<k>/accept.json が ADOPTED_FROM を持つ。子に accept.json が無い組でも印だけの物が出来る。base.json は字のまま
        写り印を持たない。2 度合わせても写し直さない（返しの控えも同じ）"""
        parent, results = self.joined()
        b1, b2 = (parent / self.files.BASES_DIR / k for k in ("1", "2"))
        self.assertEqual(self.read(b1 / self.files.ACCEPT_FILE),
                         {"final_left": [], "suite_made": ["g1.accept"], self.board.ADOPTED_FROM: results[0]["base"]})
        self.assertEqual(self.read(b2 / self.files.ACCEPT_FILE), {self.board.ADOPTED_FROM: results[1]["base"]})
        for b, r in ((b1, results[0]), (b2, results[1])):
            self.assertEqual((b / self.files.BASE_FILE).read_text(encoding="utf-8"),
                             pathlib.Path(r["base"]).read_text(encoding="utf-8"))
        self.assertEqual(self.read(parent / self.files.RETURNS_DIR / "1.json")[self.board.ADOPTED_FROM],
                         str(self.root / "g1" / self.files.RETURNS_DIR / "1.json"))
        self.board.adopt_returned(parent, self.repo, results)
        self.assertEqual(sorted(p.name for p in (parent / self.files.BASES_DIR).iterdir()), ["1", "2"])
        self.assertEqual(sorted(p.name for p in (parent / self.files.RETURNS_DIR).iterdir()), ["1.json"])

    def second(self):
        parent, _ = self.joined()
        bundle = self.read(self.carry.write(parent))
        second = self.root / "refix-run"
        second.mkdir()
        got = self.carry.adopt(second, bundle, ["1"], self.repo)
        return second, got

    def test_ii_first_parent_accept_becomes_an_accept_only_prior_base(self):
        """(ii) 1 回目の段の親の accept.json が、2 回目の段の置き場で accept.json だけの bases/<k>/ になり PRIOR_LOOP を持つ。親の bases/ と
        returns/ も PRIOR_LOOP つきで写る"""
        second, got = self.second()
        dirs = self.board.base_dirs(second)
        self.assertEqual([str(d) for d in dirs], got["bases"])
        accs = [self.read(d / self.files.ACCEPT_FILE) for d in dirs]
        self.assertTrue(all(a.get(self.board.PRIOR_LOOP) for a in accs), accs)
        only = [d for d in dirs if not (d / self.files.BASE_FILE).is_file()]
        self.assertEqual([self.read(d / self.files.ACCEPT_FILE)["suite_made"] for d in only], [["first.accept"]])
        self.assertEqual(len(dirs), 3)
        self.assertTrue(self.read(got["returns"][0])[self.board.PRIOR_LOOP])

    def test_iii_prior_bases_reach_the_child_and_its_suite_made_all(self):
        """(iii) その bases/<k>/ が 2 回目の段の組の子へ写り、子の basecase.suite_made_all にその suite_made が入る"""
        second, _ = self.second()
        child = self.root / "child"
        child.mkdir()
        self.board.adopt_inputs(second, child, self.repo)
        self.assertEqual(len(self.board.base_dirs(child)), 3)
        self.assertTrue({"first.accept", "g1.accept", "g1.base", "g2.base", "g1.ret"} <= self.basecase.suite_made_all(child),
                        self.basecase.suite_made_all(child))
        self.board.adopt_inputs(second, child, self.repo)
        self.assertEqual(len(self.board.base_dirs(child)), 3)

    def test_iv_parent_base_choice_skips_prior_bases(self):
        """(iv) 親の受け付けが読む元の結末の選び（board.ruled_base）が PRIOR_LOOP の物を外す: 写しが 1 回目の段の物だけなら無し、
        この段の組を合わせれば最後の組の物"""
        second, _ = self.second()
        self.assertEqual(self.board.ruled_base(second), "")
        self.board.adopt_returned(second, self.repo, [self.child("h1"), self.child("h2")])
        self.assertEqual(self.read(pathlib.Path(self.board.ruled_base(second)) / self.files.ACCEPT_FILE)[self.board.ADOPTED_FROM],
                         str(self.root / "h2" / self.files.BASE_FILE))


if __name__ == "__main__":
    unittest.main()

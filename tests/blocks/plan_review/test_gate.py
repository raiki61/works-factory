"""人に回しうる行と外れの事実（docs/design/plan-review.md の 10 節。src/gate.py）。

行の照らし（asks の行・4 つの軸ごとの揃わない訳 why・世界の解の外れ・独立設計の外れ・案の直しの事実）は、この過程で src/gate の関数を
直に呼ぶ（place のファイルは試験が書き、intake.json の中身は試験が組む。git も子のプロセスも無し）。port を通す場面（依頼の解き方と
依頼のファイルを出どころにした外れ・出口の返りの asks）だけ test_take.py の Flow で script を回す。

写した元は lib/tests/test_gate_axes.py の SplitCase・RunRootCase と、tests/workflows/test_plan_review.py の FourAxesCase・WorldGateCase・
WorldGateRunCase・GateFromPlanCase・ReplanCase の行の事実の半分（試験ごとの docstring に元の名を書く）。元の「聞かずに通る」は行の
decided が真で why が空、「聞く」は decided が偽か why が在る、に読み替えた。承認ノードを開くか・聞き直さないか・無人の推し・
4 つの軸のまとめは line の試験に残す。
"""
import json
import os
import pathlib
import tempfile
import unittest

from tests.blocks import kit
from tests.blocks.plan_review.test_take import (UNIT_CLAMP, UNIT_MEAN, Flow, dump, face, fields, item, review)

BLOCK = "plan-review"
# 元 lib/tests/test_plan_gate.py の値
NARROW = {"what": "空の列の mean", "why": "空の列の平均は 0 割りの例外のまま"}
URL = "https://docs.python.org/3/library/statistics.html#statistics.mean"
DECIDED = {"decided_by": f"{URL} の定義（空の列は StatisticsError）", "undecided_because": "", "fences": [],
           "world": "Python 公式の statistics.mean は空の列で例外を投げる"}
FACE = {"key": "clamp の上限の意味が変わる", "unit_keys": ["u"], "kind": "regression", "where": "stats.py clamp",
        "why": "上限を超えた値に lo を返す今の振る舞いに頼る呼び手が在れば結果が変わる", "severity": "block"}
ROUTE_UP = {"unit_id": "u", "verdict": "汚れる", "faces": [2], "evidence": ["/units/0/measure"], "reason": "責務が割れる",
            "chosen": "判定の式を report に 1 つ置く", "chosen_reason": "読み手が 1 つになる",
            "rejected": [{"option": "境の節に写す", "cost": "知る場所が 2 つになる"}],
            "route": "人に上げる", "route_reason": "人の前の決定が 2 つの置き場を別々に推している",
            "undecided_because": "人の前の決定が 2 つの置き場を別々に推している"}
WORLD_ROW = {"finding": 1, "where": "stats.py", "class_id": "w-mean", "problem": "空の数の並びの平均をどう扱うか",
             "activity": "統計の関数の直し", "practice": "空の並びの平均は定義されないので例外にする（見本の印 WG-4410）",
             "sources": [{"id": "x1", "url": "https://example.org/stats/mean", "excerpt": "The mean of an empty sequence is undefined."}],
             "applies": "空の並びの平均の扱い", "not_applies": "",
             "versus": {"proposed": "空の並びは 0 を返す", "verdict": "differs",
                        "challenge": "依頼は 0 を返す、定石は例外にする。呼び手が 0 を要る訳が無い限り定石を選ぶ"},
             "basis": "web", "cached": False}
REQUEST_LINE = "空の列の mean は 0 を返してほしい"
SEED_DOCSTRING = "tests/calibration/seed/test_stats.py:1"


class GateBase(unittest.TestCase):
    """place と作業ツリーを同じ一時のフォルダにして、intake.json の中身を組んで src/gate を直に呼ぶ（元 GateBase・AxesBase の見え方）"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(os.path.realpath(self._tmp.name))
        self.place = self.tmp
        self.cwd = self.tmp
        self.gate = kit.load(BLOCK, "gate")
        self.lib = self.gate   # lib のモジュールは gate の名で引く（gate.structmark など）
        self.request_text, self.request_file = "", ""

    def intake(self, narrows=(), plan_marks=None, recorded=(), **extra) -> dict:
        return {"plan": {"plan": [{"unit_keys": ["u"], "narrows": list(narrows)}]}, "plan_marks": plan_marks or [[]],
                "cwd": str(self.cwd), "request": self.request_text, "request_file": self.request_file,
                "recorded_policy": list(recorded), "units": [], "names": [], **extra}

    def asks(self, narrows=(), faces=(), *, marks=None, plan_marks=None, recorded=()) -> list:
        if marks is not None:
            (self.place / self.gate.FACE_MARKS).write_text(dump(marks), encoding="utf-8")
        return self.gate.asks(self.place, self.intake(narrows, plan_marks, recorded), {"faces": list(faces)})

    def row(self, mark, units=("u",)) -> dict:
        """決め手の欄 mark を持つ 1 行（units を名指す事前審査の regression の穴。units が案の単位なら narrows の行と同じ照らし）"""
        if list(units) == ["u"]:
            [got] = self.asks(narrows=[{**NARROW, **mark}])
        else:
            [got] = self.asks(faces=[{**FACE, **mark, "unit_keys": list(units)}])
        self.assertEqual(set(got["why"]) - set(self.gate.AXES), set())
        self.assertTrue(all(got["why"].values()), got["why"])   # 揃う軸は載らない
        return got

    def bad(self, got) -> list:
        return sorted(got["why"])

    def note(self, got, axis) -> str:
        return " / ".join(got["why"].get(axis) or [])

    def deviations(self, review_doc=None) -> list:
        return self.gate.deviations(self.place, self.intake(), review_doc or {"faces": []})

    def put_rows(self, *rows):
        """構造の目の行（元 FourAxesCase.put_rows）"""
        design = self.tmp / "design.jsonl"
        design.write_text("".join(dump(r) + "\n" for r in rows), encoding="utf-8")
        self.lib.structmark.write(self.place / self.lib.structmark.COPY_FILE, status="ok", reason="", design_file=str(design))

    def put_world(self, *rows):
        wf = self.tmp / "world-out" / self.lib.worldmark.WORLD_FILE
        wf.parent.mkdir(parents=True, exist_ok=True)
        wf.write_text("".join(dump(r) + "\n" for r in rows), encoding="utf-8")
        self.lib.worldmark.write(self.place, status="ok", reason="", world_file=str(wf), classes=len(rows), dropped=0,
                                 name=self.lib.worldmark.COPY_STATE)

    def put_answers(self, *answers):
        self.lib.planmarks.save(self.place, 1, [{"structure": list(answers)}])

    def put_request(self, doc=None):
        req = self.tmp / "request.json"
        req.write_text(dump(doc if doc is not None else {"findings": [{"where": "stats.py", "text": REQUEST_LINE}]}),
                       encoding="utf-8")
        self.request_file, self.request_text = str(req), req.read_text(encoding="utf-8")
        return req

    def world_why(self) -> list:
        [got] = [d for d in self.deviations() if d["source"] == "world"]
        return got


# ---------------------------------------------------------------- 行
class RowsCase(GateBase):
    def test_narrows_and_human_faces_are_rows_with_the_gate_heads(self):
        """行は修正案の narrows の行と、人に回す種類（regression・policy）の穴だけ。字の頭は line の照らし gatemarks.NARROW_HEAD・
        FACE_HEAD の形（元 gatemarks._gate_rows）"""
        got = self.asks(narrows=[{**NARROW, **DECIDED}],
                        faces=[{**FACE, **DECIDED}, face("drift-only-row", "u", kind="contract_drift"), face("copy-only-row", "u", kind="copy")])
        self.assertEqual([(r["kind"], r["node"]) for r in got], [("regression", "p2.fix_plan"), ("regression", "p2.plan_review")])
        self.assertRegex(got[0]["text"], self.gate.gatemarks.NARROW_HEAD)
        self.assertTrue(self.gate.gatemarks.NARROW_HEAD.match(got[0]["text"]))
        self.assertTrue(self.gate.gatemarks.FACE_HEAD.match(got[1]["text"]))
        self.assertEqual(got[0]["text"], f"修正案 1 が狭める能力: {NARROW['what']}——{NARROW['why']}")
        self.assertEqual(got[1]["text"], f"事前審査の穴 [regression] {FACE['key']}: {FACE['why']}")
        self.assertEqual([r["units"] for r in got], [["u"], ["u"]])
        self.assertEqual([(r["decided"], r["why"]) for r in got], [(True, {}), (True, {})])

    def test_non_human_face_kinds_are_not_asked(self):
        """元 GateFromPlanCase.test_non_human_face_kinds_are_not_asked の行の事実の半分: contract_drift の block の穴だけの返答は行を持たない"""
        self.assertEqual(self.asks(faces=[face("mean-contract-drift", "u", kind="contract_drift")]), [])

    def test_target_text_as_contract_drift_is_not_asked(self):
        """元 GateFromPlanCase.test_target_text_as_contract_drift_is_not_asked の行の事実の半分（#427）: 対象の文（テストの docstring）を
        contract_drift で挙げた穴は行にならない"""
        self.assertEqual(self.asks(faces=[face("seed-docstring-stale", "u", severity="suggest", where=SEED_DOCSTRING)]), [])

    def test_policy_face_without_a_recorded_row_is_not_a_row(self):
        """記録された方針を名指さない kind policy の穴は行にしない（policy.unrecorded）。一覧の行を名指す穴は行になる"""
        note = face("policy-note-mean", "u", kind="policy", severity="suggest", decided_by="q-mean-empty")
        self.assertEqual(self.asks(faces=[note]), [])
        rows = [{"source": "answer", "name": "q-mean-empty", "text": "空の列の平均は例外にする"}]
        got = self.asks(faces=[note], recorded=rows)
        self.assertEqual([(r["kind"], r["node"]) for r in got], [("policy", "p2.plan_review")])
        self.assertIn("[policy] policy-note-mean:", got[0]["text"])

    def test_held_face_added_by_the_machine_is_not_a_row(self):
        """機械が足した保留の block（converge.HELD_MARK）は行にしない（元 gatemarks._gate_rows）"""
        held = {**FACE, **DECIDED, self.gate.converge.HELD_MARK: True}
        self.assertEqual(self.asks(faces=[held]), [])

    def test_separated_marks_are_read_back_onto_the_rows(self):
        """決め手の欄は、narrows の分は intake の plan_marks（入口が外した物）、穴の分は受け付けが外した review-marks.json から行に
        重ねて読む（14 節の 10。欄の無い行は決め手が無い）"""
        got = self.asks(narrows=[dict(NARROW)], faces=[dict(FACE)])
        self.assertEqual([r["decided"] for r in got], [False, False])
        self.assertIn(self.gate.gatemarks.NOT_DECIDED, self.note(got[0], "obvious"))
        got = self.asks(narrows=[dict(NARROW)], faces=[dict(FACE)], plan_marks=[[DECIDED]], marks=[DECIDED])
        self.assertEqual([(r["decided"], r["why"], r["mark"]) for r in got], [(True, {}, DECIDED), (True, {}, DECIDED)])


# ---------------------------------------------------------------- 4 つの軸（元 lib/tests/test_gate_axes.py の SplitCase）
class SplitCase(GateBase):
    def test_decided_url_is_all_ok(self):
        """元 SplitCase.test_decided_url_is_all_ok（元 FourAxesCase.test_decided_by_url_passes）"""
        got = self.row(DECIDED)
        self.assertEqual((got["decided"], got["why"]), (True, {}))

    def test_no_decided_by_is_not_obvious(self):
        """元 SplitCase.test_no_decided_by_is_not_obvious"""
        got = self.row({**DECIDED, "decided_by": ""})
        self.assertEqual(self.bad(got), ["obvious"])
        self.assertFalse(got["decided"])
        self.assertIn(self.gate.gatemarks.NOT_DECIDED, self.note(got, "obvious"))

    def test_undecided_because_is_not_obvious(self):
        """元 SplitCase.test_undecided_because_is_not_obvious"""
        got = self.row({**DECIDED, "undecided_because": "世界の解が 2 つに割れる"})
        self.assertEqual(self.bad(got), ["obvious"])
        self.assertFalse(got["decided"])

    def test_decided_by_must_exist(self):
        """元 SplitCase.test_decided_by_must_exist: 現物に無い出どころは自明でない"""
        got = self.row({**DECIDED, "decided_by": "docs/adr/0099-nope.md:3 の決め"})
        self.assertIn("obvious", self.bad(got))
        self.assertIn("決め手の出どころが現物に無い", self.note(got, "obvious"))

    def test_decided_by_file_line_passes(self):
        """元 SplitCase.test_decided_by_file_line_passes"""
        (self.tmp / "docs").mkdir()
        (self.tmp / "docs" / "0002-keep.md").write_text("# 決め\n\n空の列は例外のまま\n", encoding="utf-8")
        self.assertEqual(self.row({**DECIDED, "decided_by": "docs/0002-keep.md:3（人の前の決定）"})["why"], {})

    def test_request_quote_must_be_in_request(self):
        """元 SplitCase.test_request_quote_must_be_in_request: 依頼の引用「…」は port request の本文に字のまま在る時だけ出どころ"""
        self.put_request({"findings": [{"where": "stats.py", "text": "空の列の mean は今までどおり例外でよい"}]})
        self.assertEqual(self.row({**DECIDED, "decided_by": "依頼の本文「空の列の mean は今までどおり例外でよい」"})["why"], {})
        got = self.row({**DECIDED, "decided_by": "依頼の本文「空の列は 0 を返す」"})
        self.assertEqual(self.bad(got), ["obvious"])
        self.assertIn("依頼の文に無い", self.note(got, "obvious"))

    def test_no_world_is_not_world(self):
        """元 SplitCase.test_no_world_is_not_world（元 FourAxesCase.test_no_world_asks）"""
        (self.tmp / "keep.md").write_text("空の列は例外のまま\n", encoding="utf-8")
        got = self.row({**DECIDED, "decided_by": "keep.md:1", "world": ""})
        self.assertEqual(self.bad(got), ["world"])
        self.assertEqual(got["why"]["world"], [self.gate.gatemarks.NO_WORLD])

    def test_world_rows_take_the_axis_off_the_row(self):
        """元 SplitCase.test_world_rows_take_the_axis_off_the_row: 世界の解の段の行の在る run は、行の world が空でもこの軸で見ない"""
        self.put_world(WORLD_ROW)
        (self.tmp / "keep.md").write_text("空の列は例外のまま\n", encoding="utf-8")
        self.assertEqual(self.row({**DECIDED, "decided_by": "keep.md:1", "world": ""})["why"], {})

    def test_route_up_unit_is_not_clean(self):
        """元 SplitCase.test_route_up_unit_is_not_clean"""
        self.put_rows(ROUTE_UP)
        got = self.row(DECIDED)
        self.assertEqual(self.bad(got), ["clean"])
        self.assertIn("構造の目が人に上げた単位（u）", self.note(got, "clean"))

    def test_clean_route_rows_do_not_block(self):
        """元 SplitCase.test_clean_route_rows_do_not_block"""
        self.put_rows({**ROUTE_UP, "route": "自分で決める", "route_reason": "決め手で決まる", "undecided_because": ""})
        self.assertEqual(self.row(DECIDED)["why"], {})

    def test_dirty_unit_without_answer_is_not_clean(self):
        """元 SplitCase.test_dirty_unit_without_answer_is_not_clean"""
        self.put_rows({**ROUTE_UP, "route": "自分で決める", "route_reason": "決め手で決まる", "undecided_because": ""})
        self.lib.planmarks.save(self.place, 1, [{"structure": []}])
        got = self.row(DECIDED)
        self.assertEqual(self.bad(got), ["clean"])
        self.assertIn("修正案の答えが無い", self.note(got, "clean"))
        self.lib.planmarks.save(self.place, 1, [{"structure": [{"row": "u", "follows": True}]}])
        self.assertEqual(self.row(DECIDED)["why"], {})

    def test_structure_rows_not_ok_or_unreadable_are_none(self):
        """足す: 構造の目の控えが ok でない周と、行のファイルが読めない周は、構造の目の行が無いと読む（人に上げた単位に当たらない）"""
        self.put_rows(ROUTE_UP)
        copy = self.place / self.lib.structmark.COPY_FILE
        self.lib.structmark.write(copy, status="failed", reason="落ちた", design_file=str(self.tmp / "design.jsonl"))
        self.assertEqual(self.row(DECIDED)["why"], {})
        (self.tmp / "broken.jsonl").write_text("{\n", encoding="utf-8")
        self.lib.structmark.write(copy, status="ok", reason="", design_file=str(self.tmp / "broken.jsonl"))
        self.assertEqual(self.row(DECIDED)["why"], {})

    def test_dirty_unit_without_fields_record_is_not_checked(self):
        """足す: 欄の控えが無い周は、汚れる単位の答えの欠けを照らさない（欠けは受け付けが拒む）"""
        self.put_rows({**ROUTE_UP, "route": "自分で決める", "route_reason": "決め手で決まる", "undecided_because": ""})
        self.assertEqual(self.row(DECIDED)["why"], {})

    def test_fences_are_overkill(self):
        """元 SplitCase.test_fences_are_overkill: 柵の印が在る行は決め手が在っても揃わない"""
        got = self.row({**DECIDED, "fences": ["external_write"]})
        self.assertEqual(self.bad(got), ["not_overkill"])
        self.assertFalse(got["decided"])
        self.assertIn("external_write", self.note(got, "not_overkill"))

    def test_face_outside_plan_units_is_overkill(self):
        """元 SplitCase.test_face_outside_plan_units_is_overkill（元 FourAxesCase.test_face_outside_plan_units_asks）"""
        got = self.row(DECIDED, units=("別の単位",))
        self.assertEqual(self.bad(got), ["not_overkill"])
        self.assertIn("修正案の単位の外を名指す（別の単位）", self.note(got, "not_overkill"))


# ---------------------------------------------------------------- 元 tests/workflows/test_plan_review.py の FourAxesCase
class FourAxesCase(GateBase):
    """承認ノードに載せずに通してよいかは、自明・世界の解・汚くない・やりすぎでないの 4 つが全部揃う時だけ（持ち主 2026-10-09 の決め 1）。
    この block は行ごとの揃わない訳を返し、聞くかは line が決める"""

    def test_decided_by_must_exist(self):
        """元 FourAxesCase.test_decided_by_must_exist: 決め手の出どころが現物に無ければ揃わない"""
        [got] = self.asks(narrows=[{**NARROW, **DECIDED, "decided_by": "docs/adr/0099-nope.md:3 の決め"}])
        self.assertIn("決め手の出どころが現物に無い", self.note(got, "obvious"))

    def test_decided_by_url_passes(self):
        """元 FourAxesCase.test_decided_by_url_passes"""
        [got] = self.asks(narrows=[{**NARROW, **DECIDED}])
        self.assertEqual((got["decided"], got["why"]), (True, {}))

    def test_decided_by_file_line_passes(self):
        """元 FourAxesCase.test_decided_by_file_line_passes"""
        (self.tmp / "docs").mkdir()
        (self.tmp / "docs" / "0002-keep.md").write_text("# 決め\n\n空の列は例外のまま\n", encoding="utf-8")
        [got] = self.asks(narrows=[{**NARROW, **DECIDED, "decided_by": "docs/0002-keep.md:3（人の前の決定）"}])
        self.assertEqual(got["why"], {})

    def test_no_world_asks(self):
        """元 FourAxesCase.test_no_world_asks"""
        (self.tmp / "keep.md").write_text("空の列は例外のまま\n", encoding="utf-8")
        [got] = self.asks(narrows=[{**NARROW, **DECIDED, "decided_by": "keep.md:1", "world": ""}])
        self.assertIn("世界の解", self.note(got, "world"))

    def test_face_outside_plan_units_asks(self):
        """元 FourAxesCase.test_face_outside_plan_units_asks"""
        [got] = self.asks(faces=[{**FACE, **DECIDED, "unit_keys": ["別の単位"]}])
        self.assertIn("修正案の単位の外", self.note(got, "not_overkill"))

    def test_eye_route_up_becomes_gate_item(self):
        """元 FourAxesCase.test_eye_route_up_becomes_gate_item の行の事実の半分: 構造の目が人に上げた単位の決め手の行は、汚くないの軸が
        揃わない（構造の目の行そのものを承認ノードの項目にするのは line）"""
        self.put_rows(ROUTE_UP)
        [got] = self.asks(narrows=[{**NARROW, **DECIDED}])
        self.assertEqual(sorted(got["why"]), ["clean"])
        self.assertTrue(got["decided"])
        self.assertIn("構造の目", self.note(got, "clean"))

    def test_request_quote_must_be_in_request(self):
        """元 FourAxesCase.test_request_quote_must_be_in_request"""
        self.put_request({"findings": [{"where": "stats.py", "text": "空の列の mean は今までどおり例外でよい"}]})
        [ok] = self.asks(narrows=[{**NARROW, **DECIDED, "decided_by": "依頼の本文「空の列の mean は今までどおり例外でよい」"}])
        self.assertEqual(ok["why"], {})
        [bad] = self.asks(narrows=[{**NARROW, **DECIDED, "decided_by": "依頼の本文「空の列は 0 を返す」"}])
        self.assertIn("依頼の文に無い", self.note(bad, "obvious"))

    def test_sources_ignore_times_and_dirs_and_take_absolute_request_cites(self):
        """元 FourAxesCase.test_sources_ignore_times_and_dirs_and_take_absolute_request_cites: 出どころの照らしは時刻と出典の引用を
        数えず、フォルダだけを出どころにせず、依頼の絶対パスの引用を受ける"""
        cite = self.gate.cite
        (self.tmp / "docs").mkdir()
        (self.tmp / "docs" / "x.md").write_text("一\n二\n三\n", encoding="utf-8")
        req = self.tmp / "req.json"
        req.write_text("[]\n[]\n", encoding="utf-8")
        self.assertEqual(cite.sources_problem("12:30 に決めた docs/x.md:3 の「三」の行", self.tmp), "")
        self.assertEqual(cite.sources_problem(f"{req}:2", self.tmp / "docs", [str(self.tmp)]), "")
        self.assertEqual(cite.sources_problem("docs/ の慣習", self.tmp), cite.NO_SOURCE)
        self.assertIn("依頼の文に無い", cite.sources_problem("依頼の本文「無い字の並び」", self.tmp, quoted="ある字"))

    def test_clean_route_rows_do_not_block(self):
        """元 FourAxesCase.test_clean_route_rows_do_not_block"""
        self.put_rows({**ROUTE_UP, "route": "自分で決める", "route_reason": "決め手で決まる", "undecided_because": ""})
        [got] = self.asks(narrows=[{**NARROW, **DECIDED}])
        self.assertEqual(got["why"], {})


# ---------------------------------------------------------------- 決め手の出どころに引いてよい根（元 lib/tests/test_gate_axes.py の RunRootCase）
class RunRootCase(GateBase):
    """決め手の出どころに引いてよい作業ツリーの外の根は、依頼のファイル（port request）と place の親。場面は run f3a32503: 計画の役が
    定石から外れる訳に、run の置き場の plan/r1/brief-2.md:62（判定の処方の行）を挙げた"""

    def setUp(self):
        super().setUp()
        self.run_dir = self.tmp / "run"
        self.place = self.run_dir / "plan-review"
        self.place.mkdir(parents=True)
        self.cwd = self.tmp / "repo"
        self.cwd.mkdir()
        self.brief = self.run_dir / "plan" / "r1" / "brief-2.md"
        self.brief.parent.mkdir(parents=True)
        self.brief.write_text("前置き\n" * 61 + "判定の処方: 空の列は 0 を返す\n", encoding="utf-8")
        self.judgment = self.run_dir / "judge" / "judgment.json"
        self.judgment.parent.mkdir(parents=True)
        self.judgment.write_text("{\n \"units\": []\n}\n", encoding="utf-8")

    def deviate(self, deviation: str) -> list:
        """世界の解の外れ 1 行の揃わない訳（揃えば []）"""
        self.put_world(WORLD_ROW)
        self.put_answers({"world": "w-mean", "deviation": deviation})
        return self.world_why()["why"]

    def test_absolute_run_file_is_a_source(self):
        """元 RunRootCase.test_absolute_run_file_is_a_source"""
        self.assertEqual(self.deviate(f"判定の処方 {self.brief}:62 が 0 を返すと決めている"), [])
        self.assertEqual(self.row({**DECIDED, "decided_by": f"判定の処方 {self.judgment}:2 の単位の並び"})["why"], {})

    def test_bare_name_is_still_asked(self):
        """元 RunRootCase.test_bare_name_is_still_asked: 相対の素の名は作業ツリーの根から引く（run の置き場で探し直さない）"""
        why = self.deviate("brief-2.md:62 の処方が 0 を返すと決めている")
        self.assertEqual(len(why), 1)
        self.assertIn("ファイルが無い", why[0])

    def test_outside_the_run_is_still_asked(self):
        """元 RunRootCase.test_outside_the_run_is_still_asked"""
        other = self.tmp / "other.md"
        other.write_text("判定の処方\n", encoding="utf-8")
        got = self.row({**DECIDED, "decided_by": f"{other}:1 の処方"})
        self.assertEqual(self.bad(got), ["obvious"])
        self.assertIn("の外", self.note(got, "obvious"))

    def test_request_file_is_a_source_but_not_its_folder(self):
        """元 RunRootCase.test_request_file_is_a_source_but_not_its_folder（依頼のファイルは始めの記録でなく port request から）"""
        req = self.tmp / "request.json"
        req.write_text("[{\"where\": \"stats.py\", \"text\": \"空の列\"}]\n", encoding="utf-8")
        self.request_file, self.request_text = str(req), req.read_text(encoding="utf-8")
        self.assertEqual(self.row({**DECIDED, "decided_by": f"{req}:1 の依頼の行"})["why"], {})
        (self.tmp / "other.md").write_text("依頼の横の文書\n", encoding="utf-8")
        got = self.row({**DECIDED, "decided_by": f"{self.tmp / 'other.md'}:1 の処方"})
        self.assertEqual(self.bad(got), ["obvious"])


# ---------------------------------------------------------------- 世界の解の外れ（元 WorldGateCase）
class WorldGateCase(GateBase):
    """世界の解の軸は、役が書く world の文でなく、世界の解の行への修正案の答えで機械が決める（worldmark.world_ok）。外れの行は
    deviations の source world に、揃わない訳を why に持って返る（keep-essence の 12。人に回すのは line）"""

    def test_following_world_row_passes_without_asking(self):
        """元 WorldGateCase.test_following_world_row_passes_without_asking: 世界の解の行に従う案の行は、役が world の文を書かず URL の
        決め手も無くても、世界の解の軸が揃う。従う答えは外れの行にならない"""
        (self.tmp / "keep.md").write_text("空の列は例外のまま\n", encoding="utf-8")
        mark = {**DECIDED, "decided_by": "keep.md:1", "world": ""}
        [got] = self.asks(narrows=[{**NARROW, **mark}])
        self.assertIn("world", got["why"], "世界の解の行が無い run は今どおり world か URL が要る")
        self.put_world(WORLD_ROW)
        self.put_answers({"world": "w-mean", "follows": True})
        [got] = self.asks(narrows=[{**NARROW, **mark}])
        self.assertEqual((got["decided"], got["why"]), (True, {}))
        self.assertEqual(self.deviations(), [])

    def test_world_deviation_becomes_gate_item(self):
        """元 WorldGateCase.test_world_deviation_becomes_gate_item: 出どころの無い外れは why を持つ外れの行になり、行の定石と依頼の
        解き方との比べが文に載る"""
        self.put_world(WORLD_ROW)
        deviation = "呼び手の都合で 0 を返す形に寄せたい、と考えた"
        self.put_answers({"world": "w-mean", "deviation": deviation})
        got = self.world_why()
        self.assertEqual(got["item"], 1)
        self.assertTrue(got["text"].startswith("修正案 1 の"), got["text"])
        for want in ("w-mean", "WG-4410", deviation):
            self.assertIn(want, got["text"])
        self.assertEqual(got["mark"]["decided_by"], deviation)
        self.assertIn("w-mean", got["mark"]["world"])
        self.assertEqual(len(got["why"]), 1)

    def test_world_deviation_is_asked_once(self):
        """元 WorldGateCase.test_world_deviation_is_asked_once の行の事実の半分: 外れの行は 1 つで、同じ項目の決め手の揃った narrows の
        行は世界の解の軸で止めない（why が空）"""
        self.put_world(WORLD_ROW)
        self.put_answers({"world": "w-mean", "deviation": "呼び手の都合で 0 を返す形に寄せたい、と考えた"})
        self.assertEqual(len([d for d in self.deviations() if d["source"] == "world"]), 1)
        [got] = self.asks(narrows=[{**NARROW, **DECIDED}])
        self.assertEqual(got["why"], {})

    def test_deviation_cited_to_request_goes_to_human(self):
        """元 WorldGateCase.test_deviation_cited_to_request_goes_to_human: 依頼を出どころにした外れは、引用が依頼に在っても why を持つ。
        依頼の外の出どころ（現物に在るパス:行）で訳の立つ外れは why が空"""
        self.put_request()
        self.put_world(WORLD_ROW)
        self.put_answers({"world": "w-mean", "deviation": f"依頼の本文「{REQUEST_LINE}」に従い、定石から外れる"})
        got = self.world_why()
        self.assertEqual(len(got["why"]), 1)
        self.assertIn("依頼", got["why"][0])
        [narrow] = self.asks(narrows=[{**NARROW, **DECIDED}])
        self.assertEqual(narrow["why"], {})
        (self.tmp / "docs").mkdir()
        (self.tmp / "docs" / "0007-zero.md").write_text("# 決め\n\n空の列は 0 を返す\n", encoding="utf-8")
        self.put_answers({"world": "w-mean", "deviation": "人の前の決定 docs/0007-zero.md:3 が 0 を返すと決めた"})
        self.assertEqual(self.world_why()["why"], [])

    def test_code_lines_in_purpose_sources_pass_without_asking(self):
        """run 6444e6d7 の形（元 WorldGateCase.test_code_lines_in_purpose_sources_pass_without_asking）: 外れの訳が直す対象のコードの行を
        挙げただけなら、依頼を出どころにした外れでなく why が空"""
        self.put_request()
        self.put_world(WORLD_ROW)
        (self.tmp / "stats.py").write_text("".join(f"x{i} = {i}\n" for i in range(1, 40)), encoding="utf-8")
        (self.tmp / "test_stats.py").write_text("".join(f"y{i} = {i}\n" for i in range(1, 40)), encoding="utf-8")
        self.put_answers({"world": "w-mean", "deviation": "今の形 stats.py:29 を試験 test_stats.py:28 が縛るので、定石から外れる"})
        self.assertEqual(self.world_why()["why"], [])

    def test_request_quote_on_none_verdict_row_passes_without_asking(self):
        """元 WorldGateCase.test_request_quote_on_none_verdict_row_passes_without_asking: 依頼が解き方を示していない行（verdict none）の
        外れは、依頼の引用を挙げても依頼を出どころにした外れにならない"""
        self.put_request()
        self.put_world({**WORLD_ROW, "versus": {"proposed": "", "verdict": "none", "challenge": ""}})
        self.put_answers({"world": "w-mean", "deviation": f"依頼の本文「{REQUEST_LINE}」に従い、定石から外れる"})
        self.assertEqual(self.world_why()["why"], [])

    def test_knowledge_row_named_in_gate_item(self):
        """元 WorldGateCase.test_knowledge_row_named_in_gate_item: web で確かめていない（knowledge）行からの外れは、依頼の外の出どころが
        在っても why を持ち、そう名指す"""
        (self.tmp / "docs").mkdir()
        (self.tmp / "docs" / "0007-zero.md").write_text("# 決め\n\n空の列は 0 を返す\n", encoding="utf-8")
        self.put_world({**WORLD_ROW, "basis": "knowledge", "sources": []})
        self.put_answers({"world": "w-mean", "deviation": "人の前の決定 docs/0007-zero.md:3 が 0 を返すと決めた"})
        got = self.world_why()
        self.assertEqual(len(got["why"]), 1)
        self.assertIn(self.lib.worldmark.NOT_WEB, got["why"][0])

    def test_no_world_rows_no_world_deviations(self):
        """世界の解の段の控えの無い run は、欄 structure に外れの答えが在っても外れの行を返さない（今どおりの軸）"""
        self.put_answers({"world": "w-mean", "deviation": "呼び手の都合で 0 を返す形に寄せたい、と考えた"})
        self.assertEqual(self.deviations(), [])


class DesignDeviationCase(GateBase):
    def test_design_heads_are_design_deviations(self):
        """独立設計との構造の食い違い・対の無い仕組みの穴（why の頭が design.DRIFT_HEAD・UNPAIRED_HEAD）は source design の行になる。
        ほかの穴は行にならない"""
        design = self.gate.design
        drift = face("item1-design-drift", "u", why=design.DRIFT_HEAD + "設計の「上限は入口 1 箇所」に対し案は各所で掛ける")
        unpaired = face("item1-design-unpaired", "u", why=design.UNPAIRED_HEAD + "案の「助け手」に設計の対が無い")
        other = face("item1-other-drift", "u")
        got = self.deviations({"faces": [drift, unpaired, other]})
        self.assertEqual(got, [{"source": "design", "key": f["key"], "kind": "contract_drift", "why": f["why"]} for f in (drift, unpaired)])


# ---------------------------------------------------------------- 案の直しの事実（元 ReplanCase の事実の半分）
class ReplanCase(GateBase):
    OLD = {**item(UNIT_CLAMP, 2), **fields(UNIT_CLAMP)}

    def rows(self, new=None, faces=()) -> list:
        new = dict(self.OLD) if new is None else new
        doc = self.intake(replan_items=[{"item": 2, "units": [UNIT_CLAMP], "rows": [], "old": dict(self.OLD), "new": new}])
        return self.gate.replan(self.place, doc, {"faces": list(faces)})

    def test_contract_change_or_human_face_asks(self):
        """元 ReplanCase.test_contract_change_or_human_face_asks の事実の半分: 約束の欄（allowed_paths）を変えた直しは contract_changed
        に欄の名、人に回す種類の穴（regression）は human に載る。同じ行を replan.json にも書く"""
        widened = {**self.OLD, "allowed_paths": ["stats.py", "test_stats.py"]}
        got = self.rows(widened)
        self.assertEqual([(r["item"], r["units"], r["contract_changed"], r["human"]) for r in got],
                         [(2, [UNIT_CLAMP], ["allowed_paths"], [])])
        self.assertEqual(json.loads((self.place / "replan.json").read_text(encoding="utf-8")), got)
        hole = face("clamp-regression", UNIT_CLAMP, kind="regression", severity="suggest")
        got = self.rows(faces=[hole, face("clamp-drift-only", UNIT_CLAMP)])
        self.assertEqual(got[0]["contract_changed"], [])
        self.assertEqual(got[0]["human"], [{"key": "clamp-regression", "kind": "regression", "why": hole["why"]}])
        self.assertIsNone(got[0]["widened"])

    def test_unattended_widen_only_is_not_asked(self):
        """元 ReplanCase.test_unattended_widen_only_is_not_asked の事実の半分: 範囲を広げただけ（allowed_paths に足しただけ）の直しは
        widened に足した glob が載る（無人の run で聞かないかは line が決める）。人に回す穴の在る直しは widened を計算しない"""
        widened = {**self.OLD, "allowed_paths": ["stats.py", "test_stats.py"]}
        [got] = self.rows(widened)
        self.assertEqual(got["widened"], {"allowed_paths": ["test_stats.py"], "out_of_scope": []})
        [got] = self.rows(widened, faces=[face("clamp-regression", UNIT_CLAMP, kind="regression", severity="suggest")])
        self.assertIsNone(got["widened"])
        changed = {**widened, "approach": "上限の枝を hi に直す別の直し方に変えた"}
        self.assertIsNone(self.rows(changed)[0]["widened"])

    def test_faces_of_other_items_are_not_this_items(self):
        """穴のうち直した項目の分は、unit_keys が項目の単位と重なる行と、どの直した項目とも重ならない行（元 boardview._faces_of）"""
        mine = face("clamp-regression", UNIT_CLAMP, kind="regression", severity="suggest")
        other = face("mean-regression", UNIT_MEAN, kind="regression", severity="suggest")
        doc = self.intake(replan_items=[
            {"item": 2, "units": [UNIT_CLAMP], "rows": [], "old": dict(self.OLD), "new": dict(self.OLD)},
            {"item": 3, "units": ["stats.py other: 別の単位"], "rows": [], "old": dict(self.OLD), "new": dict(self.OLD)}])
        got = self.gate.replan(self.place, doc, {"faces": [mine, other]})
        self.assertEqual([[h["key"] for h in r["human"]] for r in got],
                         [["clamp-regression", "mean-regression"], ["mean-regression"]])


# ---------------------------------------------------------------- port を通す場面
class WorldGateRunCase(unittest.TestCase):
    """元 WorldGateRunCase: 入口を通った place で、世界の解の軸が依頼の出どころ（port means の依頼の解き方・port request の依頼の
    ファイル）を照らす"""

    def setUp(self):
        self.flow = Flow(self)
        self.gate = kit.load(BLOCK, "gate")

    def deviate(self, why) -> list:
        f = self.flow
        f.world(WORLD_ROW)
        f.plan([item(UNIT_MEAN, 1)], field_rows=[fields(structure=[{"world": "w-mean", "deviation": why}])])
        f.intake()
        return [d for d in self.gate.deviations(f.place, f.intake_doc(), {"faces": []}) if d["source"] == "world"]

    def test_deviation_cited_to_means_goes_to_human(self):
        """元 WorldGateRunCase.test_deviation_cited_to_means_goes_to_human"""
        means = "空の並びは 0 を返す形に寄せる"
        why = f"{means}、と stats.py:1 の呼び手が決める"
        [got] = self.deviate(why)
        self.assertEqual(got["why"], [], "means が渡っていなければ依頼の外の出どころで通る")
        self.flow.inputs["means"] = dump([means])
        [got] = self.deviate(why)
        self.assertEqual(len(got["why"]), 1, got)
        self.assertIn("依頼", got["why"][0])

    def test_deviation_cited_to_request_file_goes_to_human(self):
        """元 WorldGateRunCase.test_deviation_cited_to_request_file_goes_to_human（依頼のファイルは port request）"""
        req = pathlib.Path(self.flow.request({"findings": []}))
        for cited in (str(req), f"{req.parent}/./request.json", f"{req.parent}/../{req.parent.name}/request.json"):
            with self.subTest(cited=cited):
                [got] = self.deviate(f"{cited}:1 が 0 を返せと言う")
                self.assertEqual(len(got["why"]), 1, got)
                self.assertIn("依頼", got["why"][0])


class FinishCase(unittest.TestCase):
    def test_asks_reach_the_finish_output(self):
        """出口の返りの asks（10.1）: 修正案の役の返答の narrows の行は入口が決め手の欄を外し（plan_marks）、出口がそれを行に重ねて返す。
        決め手の揃わない行は decided が偽で why に軸ごとの訳。揃う行は decided が真で why が空（元 GateFromPlanCase.
        test_decided_narrow_passes_and_undecided_asks の行の事実の半分）"""
        f = Flow(self)
        decided = {**NARROW, **DECIDED, "no_narrow": "空の列で例外を投げる今の動きを残すと直したい呼び手が成り立たない"}
        f.plan([item(UNIT_MEAN, 1, narrows=[decided]), item(UNIT_CLAMP, 2)])
        got = f.pass_(review())
        self.assertEqual(got["status"], "ok", got)
        [row] = got["asks"]
        self.assertEqual((row["kind"], row["node"], row["units"], row["decided"], row["why"]),
                         ("regression", "p2.fix_plan", [UNIT_MEAN], True, {}))
        self.assertEqual(row["mark"]["decided_by"], DECIDED["decided_by"])
        self.assertNotIn("decided_by", json.dumps(f.intake_doc()["plan"], ensure_ascii=False))
        f.plan([item(UNIT_MEAN, 1, narrows=[{**decided, "undecided_because": "世界の解が 2 つに割れる"}]), item(UNIT_CLAMP, 2)])
        got = f.pass_(review())
        [row] = got["asks"]
        self.assertFalse(row["decided"])
        self.assertIn("obvious", row["why"])
        self.assertIn(NARROW["what"], row["text"])


if __name__ == "__main__":
    unittest.main()

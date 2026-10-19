"""構造の目の受け付けと出口の決定的な試験（src/eye.py・src/survey.py・src/state.py。元 lib/tests/test_structure_eye.py・test_structfile.py）。
script を回す通しの試験は test_structure.py"""
import json
import pathlib
import re
import unittest

from tests.bin import trimmed
from tests.blocks import kit

SHOWN_UNIT = {"id": "u-1", "summary": "直す所", "measure": {"churn": 3}}
SHOWN = {"units": [SHOWN_UNIT], "timing": {"wall_s": 0.5}}
CLEAN = {"unit_id": "u-1", "verdict": "汚れない", "faces": [], "evidence": ["/units/0/measure/churn"], "reason": "形が増えない"}
DIRTY = {"unit_id": "u-1", "verdict": "汚れる", "faces": [2], "evidence": ["/units/0/measure"], "reason": "責務を割る",
         "chosen": "1 か所に固める", "chosen_reason": "読み直しを割らない"}
UP = {**DIRTY, "route": "人に上げる", "rejected": [{"option": "2 か所に置く", "cost": "読み直しが割れる"}],
      "undecided_because": "人の前の決定が 2 つの置き場を別々に推していて、どちらにも決まらない"}


class _Case(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "structure")
        self.eye = kit.load("structure", "eye")
        self.files = kit.load("structure", "files")
        self.out = self.run.artifacts


class ProblemsCase(_Case):
    def test_good_rows_pass(self):
        self.assertEqual(self.eye.problems(SHOWN, {"rows": [CLEAN]}), [])
        self.assertEqual(self.eye.problems(SHOWN, {"rows": [DIRTY]}), [])

    def test_bad_rows_are_named(self):
        """行の意味の外れ（行の形の外れ——知らない行き先・形の外の欄・形の番号の型——は目の node の output_format が拒む）"""
        for name, rows in (("汚れるで避け方が無い", [{**DIRTY, "chosen": ""}]),
                           ("汚れるで形が無い", [{**DIRTY, "faces": []}]),
                           ("測れなかった単位", [CLEAN, {**CLEAN, "unit_id": "u-2"}]),
                           ("同じ単位の 2 行", [CLEAN, CLEAN]),
                           ("行が無い", []),
                           ("ポインタでない根拠", [{**CLEAN, "evidence": ["units/0/measure"]}]),
                           ("前に 0 を付けた添字", [{**CLEAN, "evidence": ["/units/00/measure"]}]),
                           ("無い欄", [{**CLEAN, "evidence": ["/units/1/measure"]}]),
                           ("根拠が空の配列", [{**CLEAN, "evidence": []}]),
                           ("汚れるで chosen_reason が無い", [{**DIRTY, "chosen_reason": ""}]),
                           ("汚れるで chosen_reason の欄が無い", [{k: v for k, v in DIRTY.items() if k != "chosen_reason"}])):
            with self.subTest(name):
                self.assertTrue(self.eye.problems(SHOWN, {"rows": rows}))
        self.assertTrue(self.eye.problems(SHOWN, None))

    def test_null_field_is_not_evidence(self):
        shown = {"units": [{**SHOWN_UNIT, "measure": None}], "timing": None}
        self.assertTrue(self.eye.problems(shown, {"rows": [{**CLEAN, "evidence": ["/units/0/measure"]}]}))

    def test_route_up_needs_reason(self):
        """人に上げる行は、決まらない訳（undecided_because）と、捨てた案と代償（rejected）が要る。汚れない行は上げない"""
        self.assertEqual(self.eye.problems(SHOWN, {"rows": [UP]}), [])
        for name, bad in (("訳が無い", {"undecided_because": ""}), ("捨てた案が無い", {"rejected": []}),
                          ("汚れないのに上げる", {"verdict": "汚れない", "faces": []})):
            with self.subTest(name):
                self.assertTrue(self.eye.problems(SHOWN, {"rows": [{**UP, **bad}]}), name)
        self.assertTrue(any("undecided_because" in g for g in self.eye.problems(SHOWN, {"rows": [{**UP, "undecided_because": ""}]})))

    def test_own_decision_row_must_not_carry_undecided(self):
        got = self.eye.problems(SHOWN, {"rows": [{**DIRTY, "undecided_because": "人の前の決定が 2 つの置き場を別々に推している"}]})
        self.assertEqual(got, ["行 0（u-1）: undecided_because は 人に上げる行だけに書く"])


class AcceptCase(_Case):
    def setUp(self):
        super().setUp()
        (self.out / self.files.VIEW_FILE).write_text(json.dumps(SHOWN, ensure_ascii=False), encoding="utf-8")
        (self.out / self.files.DESIGN_FILE).write_bytes(b"")

    def accept(self, reply):
        with self.run.env():
            return self.eye.accept(self.out, reply)

    def test_unusable_ledger_is_a_done_reject(self):
        """拒否の控え rejects-structure-eye.json が読めない時、accept は例外を上げず、done 真・give_up 真の拒否を返し、理由に
        『拒否の控えが扱えない』と名指す"""
        (self.out / "rejects-structure-eye.json").mkdir()
        for reply in ({"rows": []}, {"rows": [DIRTY]}):
            got = self.accept(reply)
            self.assertEqual((got["ok"], got["done"], got["give_up"]), (False, True, True))
            self.assertIn("拒否の控えが扱えない", got["reason"])
        self.assertEqual(self.eye.state(self.out)["status"], "gave_up")

    def test_route_up_row_written(self):
        """受け付けた人に上げる行は、行き先とその訳（route_reason＝決まらない訳）を design.jsonl に残す"""
        self.assertTrue(self.accept({"rows": [UP]})["ok"])
        row = json.loads((self.out / self.files.DESIGN_FILE).read_text(encoding="utf-8"))
        self.assertEqual((row["route"], row["route_reason"], row["undecided_because"]),
                         ("人に上げる", UP["undecided_because"], UP["undecided_because"]))

    def test_third_rejection_gives_up_and_leaves_no_rows(self):
        got = [self.accept({"rows": []}) for _ in range(self.eye.rolekit.GIVE_UP_AFTER)]
        self.assertEqual([(g["ok"], g["done"], g["give_up"]) for g in got], [(False, False, False)] * 2 + [(False, True, True)])
        self.assertEqual((self.out / self.files.DESIGN_FILE).stat().st_size, 0)


class UnreadableRowsCase(_Case):
    def test_rows_that_cannot_be_read_back_fail_the_state(self):
        """受け付けが書いた設計の行を書いた直後に読み直し、読めなければ ok にしない"""
        (self.out / self.files.VIEW_FILE).write_text(json.dumps(SHOWN, ensure_ascii=False), encoding="utf-8")
        (self.out / self.files.DESIGN_FILE).write_bytes(b"")
        (self.out / self.files.STRUCTURE_FILE).write_text(json.dumps(StateCase.MEASURED, ensure_ascii=False), encoding="utf-8")
        state = kit.load("structure", "state")
        original = self.eye.structmark.rows

        def broken(path):
            raise ValueError("設計の行 1 が JSON でない")
        self.eye.structmark.rows = broken
        try:
            with self.run.env():
                got = self.eye.accept(self.out, {"rows": [CLEAN]})
                self.assertEqual((got["ok"], got["done"], got["give_up"]), (False, True, False))
                self.assertIn("設計の行が読めない", got["reason"])
                self.eye.structmark.rows = original
                doc = json.loads(state.write_state(self.out).read_text(encoding="utf-8"))
        finally:
            self.eye.structmark.rows = original
        self.assertEqual((doc["status"], doc["reason"]), ("failed", "設計の行が読めない: 設計の行 1 が JSON でない"))


class NamesCase(_Case):
    def test_after_file_name_is_the_one_the_readers_know(self):
        self.assertEqual(self.files.AFTER_FILE, self.eye.structmark.AFTER_FILE)


class VocabularyCase(unittest.TestCase):
    """受け付けと指示が使う語と形の数は、目の node の output_format の enum と faces の範囲と同じ"""

    @classmethod
    def setUpClass(cls):
        import yaml
        doc = yaml.safe_load((kit.BLOCKS / "structure" / "works-factory-structure.yaml").read_text(encoding="utf-8"))
        loop = next(n for n in doc["nodes"] if n["id"] == "structure-eye-loop")["loop_group"]["nodes"]
        cls.fmt = next(n for n in loop if n["id"] == "structure-eye")["output_format"]
        cls.eye = kit.load("structure", "eye")

    def test_vocabulary_matches_output_format(self):
        row = self.fmt["properties"]["rows"]["items"]["properties"]
        self.assertEqual(row["verdict"]["enum"], list(self.eye.VERDICTS))
        self.assertEqual(row["route"]["enum"], list(self.eye.ROUTES))
        self.assertEqual((row["faces"]["items"]["minimum"], row["faces"]["items"]["maximum"]), (1, 6))

    def test_trimmed_min_length_kept_by_pattern(self):
        self.assertEqual(trimmed.missing_patterns(self.fmt), [])

    def test_rows_outside_the_type_are_rejected(self):
        from engine.schema import validate_schema
        self.assertEqual(validate_schema({"rows": [CLEAN]}, self.fmt), [])
        for name, row in (("知らない行き先", {**CLEAN, "route": "後で"}), ("形の外の欄", {**CLEAN, "note": "x"}),
                          ("真偽を形の番号に", {**CLEAN, "faces": [True]}), ("形の番号の外", {**CLEAN, "faces": [7]})):
            with self.subTest(name):
                self.assertTrue(validate_schema({"rows": [row]}, self.fmt))

    def test_numbered_forms_in_the_md_match_the_count(self):
        md = (kit.BLOCKS / "structure" / "prompts" / "structure-eye.md").read_text(encoding="utf-8")
        numbers = [int(n) for n in re.findall(r"^(\d)\. ", md, re.M)]
        self.assertEqual(numbers, list(range(1, self.eye.FORM_COUNT + 1)))


class ViewCase(_Case):
    def test_only_measured_units_are_shown_and_indexed_from_zero(self):
        survey = kit.load("structure", "survey")
        doc = {"status": "ok", "units": [{"id": "u-2", "status": "failed", "measure": None},
                                         {"id": "u-1", "summary": "直す所", "status": "measured", "measure": {"churn": 3}}],
               "timing": {"wall_s": 0.5}}
        self.assertEqual([u["id"] for u in survey.view(doc)["units"]], ["u-1"])
        self.assertTrue(survey.due(doc))
        self.assertFalse(survey.due({**doc, "status": "failed"}))
        self.assertFalse(survey.due({**doc, "units": doc["units"][:1]}))

    def test_long_duplicates_are_cut_with_the_total(self):
        survey = kit.load("structure", "survey")
        shown = survey.listcut.SHOWN
        dups = [{"line": i, "other_line": i, "path": "x.yaml"} for i in range(shown * 40)]
        doc = {"units": [{"id": "u-1", "status": "measured", "measure": {"paths": [{"path": "a.txt", "duplicates": dups}]}}]}
        got = survey.view(doc)["units"][0]["measure"]["paths"][0]
        self.assertEqual(len(got["duplicates"]), shown)
        self.assertEqual(got["duplicates_total"], len(dups))


class StateCase(_Case):
    """構造の目の控え structure-state.json（元 lib/tests/test_structfile.py の StateCase）"""

    MEASURED = {"status": "ok", "reason": "", "units": [{"id": "u-1", "status": "measured", "measure": {"churn": 3}}],
                "timing": {"wall_s": 0.5}}

    def state(self, structure, kept=None, rejects=()):
        state = kit.load("structure", "state")
        out = self.out / f"s{len(list(self.out.iterdir()))}"
        out.mkdir()
        (out / self.files.STRUCTURE_FILE).write_text(json.dumps(structure, ensure_ascii=False), encoding="utf-8")
        if kept is not None:
            (out / self.files.EYE_FILE).write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")
        for why in rejects:
            self.eye.rolekit.with_done(out, self.files.NAME, {"ok": False, "reason": why})
        return json.loads(state.write_state(out).read_text(encoding="utf-8"))

    def test_each_failure_names_the_reason(self):
        cases = {
            "目が通った": (self.MEASURED, {"status": "ok"}, (), "ok", ""),
            "目を起こさない run": ({**self.MEASURED, "units": []}, None, (), "ok", ""),
            "会話が落ちた": (self.MEASURED, None, (), "failed", "構造の目の会話が落ちたか走らなかった（目の受け付けの控えが無いか途中のまま）"),
            "3 回拒まれた": (self.MEASURED, {"status": "gave_up"}, ("欠け", "型", "行が無い"), "failed",
                         "構造の目の返答が 3 回とも受け付けで拒まれた: 行が無い"),
            "実測が落ちた": ({**self.MEASURED, "status": "failed", "reason": "git が無い"}, None, (), "failed", "実測が落ちた: git が無い"),
        }
        with self.run.env():
            for name, (structure, kept, rejects, status, reason) in cases.items():
                with self.subTest(name):
                    got = self.state(structure, kept, rejects)
                    self.assertEqual((got["status"], got["reason"]), (status, reason))

    def test_wall_adds_the_eye_time(self):
        with self.run.env():
            self.assertEqual(self.state(self.MEASURED, {"status": "ok", "wall_s": 2.25})["wall_s"], 2.75)

    def test_unmeasured_run_is_failed_with_an_existing_design_file(self):
        state = kit.load("structure", "state")
        out = self.out / "x"
        out.mkdir()
        with self.run.env():
            got = json.loads(state.write_state(out).read_text(encoding="utf-8"))
        self.assertEqual((got["status"], got["reason"]), ("failed", f"段 A の {self.files.STRUCTURE_FILE} が読めない"))
        self.assertEqual(pathlib.Path(got["design_file"]).stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()

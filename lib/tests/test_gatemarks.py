"""関所の問いの台帳の値の見え方（gatemarks.ledger）と、直す義務の数えの 1 つの口（gatemarks.duty）。

plan（1 回目の周の必ず入れる単位・行き止まり）と fix（直す義務）が同じ口を呼ぶ。義務の集合が食い違うと fix の受け付け
check_opened_units が NOT_OPENED で拒むので、両方を同じ入力（判定・始めの記録の依頼の answers・判定の隣の結びと素材の状態）で照らす。
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

import fixboard  # noqa: E402
import gatemarks  # noqa: E402
import planfile  # noqa: E402
import startrec  # noqa: E402

FORK = {"key": "q-a", "kind": "fork", "status": "held", "origin": "A", "depends": ["B"], "options": ["x", "y"], "reason": "割れる"}
ESC = {"key": "q-c", "kind": "awaiting", "status": "escalate", "origin": "C", "reason": "人でないと決められない"}
ANSWERED = {"key": "q-d", "kind": "fork", "status": "held", "origin": "D", "options": ["x", "y"], "reason": "割れる"}
TIED = {"key": "q-e", "kind": "fork", "status": "held", "origin": "E", "options": ["x", "y"], "reason": "割れる"}
FIELD = {"key": "parallel_pr: 重なりを確かめる", "kind": "field", "status": "escalate", "origin": "", "depends": ["F"],
         "reason": "測れていない"}
JUDGMENT = {"units": [{"key": k, "label": "block"} for k in "ABCEFG"] + [{"key": "D", "label": "suggest", "disposition": "defer"}],
            "questions": [FORK, ESC, ANSWERED, TIED, FIELD]}
ANSWERS = [{"question": "q-d", "text": "x を選ぶ"}, {"question": "どちらでもよい", "text": "y"},
           {"question": "parallel_pr", "text": "重ならない", "command": "gh pr list", "output": "[]"}]
TIES = {"rounds": {"1": [{"answer": "どちらでもよい", "to": "q-e"}]}}
MATERIALS = {"parallel_pr": {"status": "not_run", "reason": "網に出られない"}}


class DutyCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.jdir = self.tmp / "judge"
        self.jdir.mkdir()
        for name, doc in (("judgment.json", JUDGMENT), (gatemarks.BESIDE[0], TIES), (gatemarks.MATERIALS_FILE, MATERIALS)):
            (self.jdir / name).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        self.start = {"run_id": "run-1", "answers": ANSWERS}

    def plan_duty(self) -> set:
        """plan の口: 線の指し札の先を read_judgment で読み、planfile.plan_slots の必ず入れる単位"""
        raw = json.dumps({"path": str(self.jdir / "judgment.json")})
        judgment, why = planfile.read_judgment(raw, self.start, lambda text: pathlib.Path(json.loads(text)["path"]))
        self.assertEqual(why, "")
        return planfile.plan_slots(judgment)[0]

    def fix_duty(self, answers=None) -> set:
        """fix の口: prep が置き場に写す物（判定・始めの記録・判定の隣の結びと素材の状態・関所の答え）から group_owed と fix_duty"""
        place = self.tmp / "fix"
        place.mkdir(exist_ok=True)
        startrec.write(place, self.start)
        for name in ("judgment.json", *gatemarks.BESIDE):
            (place / name).write_bytes((self.jdir / name).read_bytes())
        if answers is not None:
            (place / fixboard.ANSWERS_FILE).write_text(json.dumps(answers, ensure_ascii=False), encoding="utf-8")
        owed = set(fixboard.group_owed(place))
        self.assertEqual(fixboard.fix_duty(place, owed)[0], owed)
        return owed

    def test_plan_and_fix_get_the_same_duty(self):
        """開いた単位 − 答えの無い問い（fork・escalate）の出どころ・depends ＋ 依頼の answers が答えた問いの出どころ・depends
        （字の一致・判定の結び・測れていない素材の名のどれで当たっても。開いていない単位も戻る）"""
        want = {"D", "E", "F", "G"}
        self.assertEqual(self.plan_duty(), want)
        self.assertEqual(self.fix_duty(), want)

    def test_gate_continue_returns_what_it_was_asked(self):
        """P241: 関所の continue は asked に載った問いだけに答え、その出どころ・depends を直す義務に戻す（fix だけに届く）"""
        gate = {"decision": "approve", "text": "", "asked": [gatemarks.ask_text(FORK)]}
        self.assertEqual(self.fix_duty(gate), {"A", "B", "D", "E", "F", "G"})
        self.assertEqual(self.fix_duty({**gate, "asked": []}), {"D", "E", "F", "G"})
        held = gatemarks.ledger(JUDGMENT, gate={**gate, "text": "保留: q-a"})
        self.assertEqual(gatemarks.duty(held), {"G"}, "「保留: <key>」で名指した問いは答えに数えない")

    def test_binds_is_the_one_formula(self):
        """K20: 依頼の答えの当ては gatemarks.binds の 1 つの式（判定の受け付け・報告の読み・最後の関所が呼ぶ）。結びの宛て先が無い時は
        字の一致に落とし、落としたことを 1 行で名指す"""
        b = gatemarks.ledger_beside(self.jdir, JUDGMENT, answers=ANSWERS)
        self.assertEqual([q["key"] for q in gatemarks.binds(ANSWERS[1], JUDGMENT["questions"], ties=b.ties)], ["q-e"])
        self.assertEqual([q["key"] for q in gatemarks.binds(ANSWERS[2], JUDGMENT["questions"], missing=gatemarks.unmeasured_of(MATERIALS))],
                         [FIELD["key"]])
        self.assertEqual(gatemarks.binds(ANSWERS[1], [FORK], ties=b.ties), [])
        self.assertEqual(gatemarks.lost_ties(b.ties, [FORK], ["A"]),
                         ["判定の結びの宛て先 q-e が今の問いにも単位にも無い（字の一致で当てた）: 依頼の答え どちらでもよい"])


class PushRecCase(unittest.TestCase):
    """#552: 関所の項目の推しの尾（_push の形）を読み戻し、無人の run が推しで通る答えを組む"""
    REC = {"answer": "continue", "note": "空の列は 0 を返す／形で通す", "why": "呼び手が 0 を前提に書かれている"}
    BODY = "修正案 1 が狭める能力: 空の列で例外を投げる——0 を返す形に変える（人に聞く訳: 決め手の欄が揃わない）"

    def row(self, **rec):
        return gatemarks._item(self.BODY, {gatemarks.RECOMMEND: {**self.REC, **rec}})

    def test_round_trip_of_the_push_tail(self):
        got = gatemarks.push_rec(self.row())
        self.assertEqual(got, {"item": self.BODY, "answer": "continue", "note": "空の列は 0 を返す・形で通す",
                               "why": "呼び手が 0 を前提に書かれている"})
        self.assertEqual(gatemarks.push_rec(self.row(answer="stop"))["answer"], "stop")

    def test_rows_without_an_answer_word_are_not_pushes(self):
        for text in (self.BODY, f"{gatemarks.DESIGN_HEAD}x／推し: 案 A", f"x／推し: {gatemarks.NO_PUSH}",
                     "x／推し: 止める（continue）——a（理由: b）"):
            with self.subTest(text=text):
                self.assertIsNone(gatemarks.push_rec(text))

    def test_pushed_answer_only_when_every_row_pushes_continue(self):
        rows = [self.row(), self.row(), gatemarks._item("修正案 2 が狭める能力: y", {gatemarks.RECOMMEND: {**self.REC, "note": "y で通す"}})]
        got = gatemarks.pushed_answer(rows)
        self.assertEqual((got["decision"], got["text"]), ("continue", "空の列は 0 を返す・形で通す；y で通す"))
        self.assertEqual(got[gatemarks.answer.PUSHED], [gatemarks.push_rec(r) for r in rows])
        for rows in ([], [self.row(), self.BODY], [self.row(), self.row(answer="stop")]):
            with self.subTest(rows=rows):
                self.assertIsNone(gatemarks.pushed_answer(rows))

    def test_scenario_rows_are_read(self):
        """筋書き unattended-push・unattended-push-stop の項目の字は push_rec で読める（字の形のずれを赤にする）"""
        fixtures = pathlib.Path(__file__).resolve().parents[2] / "workflows" / "line" / "fixtures"
        for name, word in (("unattended-push", "continue"), ("unattended-push-stop", "stop")):
            with self.subTest(name=name):
                text = (fixtures / f"{name}.stubs.yaml").read_text(encoding="utf-8")
                row = next(line.split('"text": "', 1)[1].split('"', 1)[0] for line in text.splitlines() if "／推し: " in line)
                self.assertEqual(gatemarks.push_rec(row)["answer"], word)

    def test_pass_line_tells_a_push_from_a_human(self):
        row = {"node": gatemarks.R4_GATE_NODE, "round": 1, "item": "x", "passed_at": {"node": gatemarks.GATE_NODE, "round": 1}}
        pushed, human = gatemarks.pass_lines([{**row, "by": gatemarks.PASSED_BY_PUSH}, {**row, "by": gatemarks.PASSED_BY_HUMAN}])
        self.assertIn("無人の run で推しを採って通した", pushed)
        self.assertNotIn("人が通した", pushed)
        self.assertIn("人が通した", human)



if __name__ == "__main__":
    unittest.main()

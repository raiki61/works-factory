"""関所の問いの台帳の値の見え方（gatemarks.ledger）と、直す義務の数えの 1 つの口（gatemarks.duty）。

plan（1 回目の周の必ず入れる単位・行き止まり）と fix（直す義務）が同じ口を呼ぶ。義務の集合が食い違うと fix の受け付け
check_opened_units が NOT_OPENED で拒むので、両方を同じ入力（判定・始めの記録の依頼の answers・判定の隣の結びと素材の状態）で照らす。
"""
import ast
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import answer  # noqa: E402
import fixboard  # noqa: E402
import gatemarks  # noqa: E402
import planfile  # noqa: E402
import seal  # noqa: E402
import startrec  # noqa: E402

FORK = {"key": "q-a", "kind": "fork", "status": "held", "origin": "A", "depends": ["B"], "options": ["x", "y"], "reason": "割れる"}
PUSHED_FORK = {**FORK, "reason": "割れる。推し: x——呼び手が既に x を前提にしている"}
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

    def judge(self, *questions) -> None:
        doc = {**JUDGMENT, "questions": [*questions, ANSWERED, TIED, FIELD]}
        (self.jdir / "judgment.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def test_unattended_run_takes_the_held_fork_push(self):
        """#593: 無人の run は判定が保留にした fork・held の理由の推しを答えに採り、出どころ・depends を直す義務に戻す（計画と修正が
        同じ口で数える）。人のいる run・推しの無い問い・escalate は今どおり外す"""
        want = {"D", "E", "F", "G"}
        escalated = {**FORK, "key": "q-x", "status": "escalate", "origin": "C", "depends": [], "reason": "人でないと決められない。推し: x"}
        self.judge(PUSHED_FORK, escalated, {**ESC, "reason": "人でないと決められない。推し: z"})
        self.assertEqual((self.plan_duty(), self.fix_duty()), (want, want), "人のいる run は推しを採らない")
        self.start = {**self.start, "unattended": "true"}
        self.assertEqual((self.plan_duty(), self.fix_duty()), (want | {"A", "B"}, want | {"A", "B"}), "fork・escalate の推しは採らない")
        self.assertEqual([q["key"] for q, _, _ in gatemarks.taken_pushes(fixboard.gate_view(self.tmp / "fix"))], ["q-a"])
        line = next(x for x in gatemarks.returned_lines(fixboard.gate_view(self.tmp / "fix")) if "q-a" in x)
        self.assertTrue(line.startswith(f"{answer.PUSHED_NOTE}\n無人の run が採った推しで答えた{gatemarks.ASK_HEAD} q-a"), line)
        self.assertIn("——推し: x——呼び手が既に x を前提にしている。", line)
        self.assertEqual(line.count(answer.PUSHED_NOTE), 1)
        self.judge(FORK, ESC)
        self.assertEqual((self.plan_duty(), self.fix_duty()), (want, want), "推しの無い問いは止まる")

    def test_unattended_run_takes_only_a_push_that_names_an_option_of_open_units(self):
        """#593: 推しの最後の「推し:」の頭が選択肢のどれかを名指し、出どころ・depends が開いた単位の時だけ採る。ほかは保留のまま
        （推しの無い問いと同じく止め、報告の冒頭で名指す）"""
        def take(reason, origin="A", options=("x", "y")):
            q = {**FORK, "reason": reason, "origin": origin, "depends": [], "options": list(options)}
            b = gatemarks.ledger({"units": [{"key": "A", "label": "block"}, {"key": "C", "label": "suggest", "disposition": "defer"}],
                                  "questions": [q]}, takes_push=True)
            return gatemarks.run_push(b, q), gatemarks.duty(b), [x for x in gatemarks.held_lines(b) if "q-a" in x]
        push, duty, held = take("割れる。推し: x——理由")
        self.assertEqual((push, duty, held), ("x——理由", {"A"}, []))
        self.assertEqual(take("前の周の推し: y は捨てた。推し: x——理由")[0], "x——理由")
        long_option = ("例外を投げる。帰結: 呼び手が捕まえる", "0 を返す")
        self.assertEqual(take("割れる。推し: 例外を投げる——理由", options=long_option)[0], "例外を投げる——理由")
        self.assertEqual(take("割れる。推し: x。呼び手が x を前提にする")[0], "x。呼び手が x を前提にする")
        for reason, origin, options in (("割れる。推し: なし——人が決める", "A", ("x", "y")),
                                        ("割れる。推し: x——理由", "C", ("x", "y")),
                                        ("割れる。推し: x——理由", "gone", ("x", "y")),
                                        ("割れる。推し: xyz を足す——理由", "A", ("x", "y")),
                                        ("割れる。推し: 例外——理由", "A", long_option)):
            with self.subTest(reason=reason, origin=origin):
                push, duty, held = take(reason, origin, options)
                self.assertEqual((push, duty), ("", {"A"} - {origin}))
                self.assertTrue(held, "採らない問いは保留のまま名指す")

    def test_request_answer_comes_before_the_push(self):
        """#593: 依頼の answers が答えた問いは推しで上書きしない。推しだけで答えた問いは PUSH_TAKEN の印で答えた行に並ぶ"""
        judgment = {**JUDGMENT, "questions": [PUSHED_FORK, ESC]}
        b = gatemarks.ledger(judgment, answers=[{"question": "q-a", "text": "y を選ぶ"}], takes_push=True)
        self.assertNotIn(gatemarks.PUSH_TAKEN, gatemarks.answered_ledger_lines(b)[0])
        self.assertEqual(gatemarks.taken_pushes(b), [])
        b = gatemarks.ledger(judgment, takes_push=True)
        self.assertIn(gatemarks.PUSH_TAKEN, gatemarks.answered_ledger_lines(b)[0])
        self.assertNotIn("q-a", "".join(gatemarks.held_lines(b)))
        self.assertEqual(gatemarks.taken_pushes(b), [(PUSHED_FORK, "x——呼び手が既に x を前提にしている", ["A", "B"])])
        self.assertEqual(gatemarks.taken_pushes(gatemarks.ledger(judgment)), [])


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

    def test_gate_items_keep_the_push_origin(self):
        """推しで通した答えを human_items の行にしても欄 answer.PUSHED を落とさない（人の答えの行は持たない）"""
        pushed = gatemarks.pushed_answer([self.row()])
        self.assertEqual(gatemarks.gate_items(pushed)[0][gatemarks.answer.PUSHED], pushed[gatemarks.answer.PUSHED])
        self.assertNotIn(gatemarks.answer.PUSHED, gatemarks.gate_items({"decision": "continue", "text": "人"})[0])

    def test_pass_line_tells_a_push_from_a_human(self):
        row = {"node": gatemarks.R4_GATE_NODE, "round": 1, "item": "x", "passed_at": {"node": gatemarks.GATE_NODE, "round": 1}}
        pushed, human = gatemarks.pass_lines([{**row, "by": gatemarks.PASSED_BY_PUSH}, {**row, "by": gatemarks.PASSED_BY_HUMAN}])
        self.assertIn("無人の run で推しを採って通した", pushed)
        self.assertNotIn("人が通した", pushed)
        self.assertIn("人が通した", human)



class EyeWordsCase(unittest.TestCase):
    def test_eye_words_come_from_seal(self):
        got = gatemarks.eye_named("R1", "fix-needed")
        self.assertIn("直しが要る（fix-needed）", got)
        self.assertNotIn("作り直し", got)
        for word in seal.STATUSES:
            with self.subTest(word):
                self.assertEqual(gatemarks.REVIEW_WORDS[word], seal.STATUS_WORDS[word])


class SpecWordsCase(unittest.TestCase):
    """承認し直すかの問いを「変わった」か「照らせなかった」かで言う選びは spec_words の 1 か所だけ（#564）"""
    CHOOSERS = (LIB.parent / "workflows" / "line" / "scripts" / "ask_final.py", LIB / "runreport.py")
    WORDS = ("SPEC_UNCHECKED", "SPEC_UNCHECKED_HEAD", "SPEC_UNCHECKED_NOTE", "SPEC_CHANGED_HEAD", "SPEC_CHANGED_LABEL",
             "SPEC_CHANGED_KIND", "SPEC_CHANGED_NOTE")

    def test_words_follow_whether_the_tests_could_be_checked(self):
        self.assertEqual(gatemarks.spec_words(False), (gatemarks.KIND_WORDS[gatemarks.SPEC_CHANGED_KIND],
                                                       gatemarks.SPEC_CHANGED_LABEL, gatemarks.SPEC_CHANGED_HEAD,
                                                       gatemarks.SPEC_CHANGED_NOTE))
        self.assertEqual(gatemarks.spec_words(True), (gatemarks.SPEC_UNCHECKED, gatemarks.SPEC_UNCHECKED,
                                                      gatemarks.SPEC_UNCHECKED_HEAD, gatemarks.SPEC_UNCHECKED_NOTE))

    def test_callers_choose_only_through_spec_words(self):
        for path in self.CHOOSERS:
            with self.subTest(path.name):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                attrs = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                         and n.value.id == "gatemarks"]
                self.assertEqual([n.attr for n in attrs if n.attr in self.WORDS], [])
                self.assertEqual(sum(n.attr == "spec_words" for n in attrs), 2)



if __name__ == "__main__":
    unittest.main()

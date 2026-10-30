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
import gatemarks  # noqa: E402
import seal  # noqa: E402
from tests.blocks.kit import BLOCKS as WORKFLOWS  # noqa: E402  （pack のフォルダ。入れ替えの前も後も同じ口）

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
        for name, doc in (("judgment.json", JUDGMENT), ("answer-ties.json", TIES), ("materials.json", MATERIALS)):
            (self.jdir / name).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        self.start = {"run_id": "run-1", "answers": ANSWERS}

    def ledger(self, gate=None, takes_push=False):
        """値の見え方: 判定・結び・素材の状態のファイルと依頼の answers・関所の答え・無人の run か（始めの記録は読まない。呼び手が値で渡す）"""
        judgment = json.loads((self.jdir / "judgment.json").read_text(encoding="utf-8"))
        return gatemarks.ledger_files(judgment, ties_file=self.jdir / "answer-ties.json", materials_file=self.jdir / "materials.json",
                                      answers=self.start["answers"], gate=gate, takes_push=takes_push)

    def owed(self, gate=None, takes_push=False) -> set:
        return gatemarks.duty(self.ledger(gate, takes_push))

    def test_duty_of_the_ledger(self):
        """開いた単位 − 答えの無い問い（fork・escalate）の出どころ・depends ＋ 依頼の answers が答えた問いの出どころ・depends
        （字の一致・判定の結び・測れていない素材の名のどれで当たっても。開いていない単位も戻る）。plan と fix は同じこの口を呼ぶ"""
        self.assertEqual(self.owed(), {"D", "E", "F", "G"})

    def test_gate_continue_returns_what_it_was_asked(self):
        """P241: 関所の continue は asked に載った問いだけに答え、その出どころ・depends を直す義務に戻す（fix だけに届く）"""
        gate = {"decision": "approve", "text": "", "asked": [gatemarks.ask_text(FORK)]}
        self.assertEqual(self.owed(gate), {"A", "B", "D", "E", "F", "G"})
        self.assertEqual(self.owed({**gate, "asked": []}), {"D", "E", "F", "G"})
        held = gatemarks.ledger(JUDGMENT, gate={**gate, "text": "保留: q-a"})
        self.assertEqual(gatemarks.duty(held), {"G"}, "「保留: <key>」で名指した問いは答えに数えない")

    def test_binds_is_the_one_formula(self):
        """K20: 依頼の答えの当ては gatemarks.binds の 1 つの式（判定の受け付け・報告の読み・最後の関所が呼ぶ）。結びの宛て先が無い時は
        字の一致に落とし、落としたことを 1 行で名指す"""
        b = gatemarks.ledger_files(JUDGMENT, ties_file=self.jdir / "answer-ties.json", materials_file=self.jdir / "materials.json",
                                   answers=ANSWERS)
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
        self.assertEqual(self.owed(), want, "人のいる run は推しを採らない")
        self.assertEqual(self.owed(takes_push=True), want | {"A", "B"}, "fork・escalate の推しは採らない")
        self.assertEqual([q["key"] for q, _, _ in gatemarks.taken_pushes(self.ledger(takes_push=True))], ["q-a"])
        line = next(x for x in gatemarks.returned_lines(self.ledger(takes_push=True)) if "q-a" in x)
        self.assertTrue(line.startswith(f"{answer.PUSHED_NOTE}\n無人の run が採った推しで答えた{gatemarks.ASK_HEAD} q-a"), line)
        self.assertIn("——推し: x——呼び手が既に x を前提にしている。", line)
        self.assertEqual(line.count(answer.PUSHED_NOTE), 1)
        self.judge(FORK, ESC)
        self.assertEqual(self.owed(takes_push=True), want, "推しの無い問いは止まる")

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

    def test_the_go_push_word_is_the_go_answer_word(self):
        """#733: 通す推しの字と、推しで進んだ時に答えに書く字（answer.VERBS の頭）は同じ"""
        self.assertEqual(gatemarks.RECOMMEND_ANSWERS[0], answer.VERBS[0])

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

    def test_pass_line_tells_no_standard_from_a_source(self):
        """定石が見つからず推しで進めた行は、決め手で通した行と分けて、探した所を 1 行に残す"""
        row = {"node": gatemarks.GATE_NODE, "round": 1, "item": "x", "by": gatemarks.PASSED_BY}
        found, none = gatemarks.pass_lines([{**row, "decided_by": "https://semver.org/"},
                                            {**row, "decided_by": f"{gatemarks.NO_STANDARD} 公式の文書を探した"}])
        self.assertIn("決め手が在るので聞かずに通した", found)
        self.assertIn("定石が見つからず", none)
        self.assertIn("探した所: 公式の文書を探した", none)
        self.assertNotIn(gatemarks.NO_STANDARD, none)



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
    # 最後の承認ノードの文（元 ask_final.py）と報告の事実（元 runreport.py）は、組み込みで line の src/final.py・facts.py へ移った
    CHOOSERS = (WORKFLOWS / "line" / "src" / "final.py", WORKFLOWS / "line" / "src" / "facts.py")
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

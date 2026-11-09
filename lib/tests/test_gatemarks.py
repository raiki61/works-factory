"""関所の問いの台帳の値の見え方（gatemarks.ledger）と、直す義務の数えの 1 つの口（gatemarks.duty）。

plan（1 回目の周の必ず入れる単位・行き止まり）と fix（直す義務）が同じ口を呼ぶ。義務の集合が食い違うと fix の受け付け
check_opened_units が NOT_OPENED で拒むので、両方を同じ入力（判定・始めの記録の依頼の answers・判定の隣の結びと素材の状態）で照らす。
"""
import ast
import inspect
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
import plainask  # noqa: E402
import seal  # noqa: E402
from tests.blocks.kit import BLOCKS as WORKFLOWS  # noqa: E402  （pack のフォルダ。入れ替えの前も後も同じ口）
from tests.blocks.kit import load as kit_load  # noqa: E402

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
    """#552: 関所の項目の推しは行の欄 recommend が運び、下書きは同じ欄を同じ recommend_of で読む。項目の文の末尾の字は推しと読まない"""
    REC = {"answer": "continue", "note": "空の列は 0 を返す／形で通す", "why": "呼び手が 0 を前提に書かれている"}
    BODY = "修正案 1 が狭める能力: 空の列で例外を投げる——0 を返す形に変える（人に聞く訳: 決め手の欄が揃わない）"

    def tail(self, **rec):
        """審査役が文の末尾に書いた推しの形の字（欄 recommend ではない）"""
        return gatemarks._push({gatemarks.RECOMMEND: {**self.REC, **rec}})

    def test_item_draft_answers_from_the_recommend_field(self):
        """欄 recommend が在る項目は推しが下書きの答えになり（question は文のまま）、欄が無い・崩れた項目は text が空。文の末尾が推しの形でも答えにしない"""
        self.assertIn("recommend", inspect.signature(gatemarks.item_draft).parameters, "呼び手が行の欄を渡す口")
        self.assertNotIn("read_tail", inspect.signature(gatemarks.item_draft).parameters)
        got = gatemarks.item_draft(self.BODY, gatemarks.GATE_NODE, recommend=self.REC)
        self.assertEqual(got["question"], self.BODY)
        self.assertEqual(got["text"], "continue: 空の列は 0 を返す／形で通す（推す理由: 呼び手が 0 を前提に書かれている）")
        self.assertIn(gatemarks.RECOMMEND, got["source"])
        self.assertTrue(gatemarks.item_draft(self.BODY, gatemarks.GATE_NODE, recommend={**self.REC, "answer": "stop"})["text"].startswith("stop: "))
        bare = gatemarks.item_draft(self.BODY, gatemarks.GATE_NODE, recommend=None)
        self.assertEqual((bare["question"], bare["text"]), (self.BODY, ""))
        self.assertIn("推しの欄が無い", bare["source"])
        self.assertNotIn("役が書いていない", bare["note"])
        tailed = gatemarks.item_draft(self.BODY + self.tail(), gatemarks.GATE_NODE, recommend=None)
        self.assertEqual(tailed["text"], "", "文の末尾の字は推しの欄ではない")
        self.assertEqual(tailed["question"], self.BODY + self.tail(), "question は文の全体のまま")
        self.assertNotIn("文に書かれた推し", tailed["note"], "note は文から推しを拾わない")
        short = gatemarks.item_draft(self.BODY, gatemarks.GATE_NODE, recommend={**self.REC, "note": "短"})
        self.assertEqual(short["text"], "")
        self.assertIn("推しの欄が無い", short["source"])

    def test_item_draft_notes_world_and_no_narrow_tails(self):
        """推しの欄の無い文は、_world・_no_narrow が付けた尾の値を note が名指す。欄の無い行の置き字は値として置かない。
        recommend を渡せば、同じ文でも答えが推しになる"""
        mark = {"decided_by": "x", "world": "W（括弧つき）", gatemarks.NO_NARROW: "N"}
        why = "（人に聞く訳: 2 つの形が割れる）"
        text = self.BODY + gatemarks._world(mark) + gatemarks._no_narrow(mark) + why
        got = gatemarks.item_draft(text, gatemarks.GATE_NODE, recommend=None)
        self.assertEqual((got["question"], got["text"]), (text, ""))
        self.assertIn("世界の解: W（括弧つき）", got["note"])
        self.assertIn("狭めない案: N", got["note"])
        self.assertNotIn("人に聞く訳", got["note"])
        unsaid = gatemarks.item_draft(self.BODY + gatemarks._world({"decided_by": "x"}) + why, gatemarks.GATE_NODE, recommend=None)
        self.assertNotIn("世界の解:", unsaid["note"], "欄の無い行の置き字は値として写さない")
        self.assertNotIn("役が書いていない", unsaid["note"])
        pushed = gatemarks.item_draft(text, gatemarks.GATE_NODE, recommend=self.REC)
        self.assertTrue(pushed["text"].startswith("continue: "))

    def test_item_draft_without_a_field_does_not_answer_from_a_tail_shaped_text(self):
        """gatemarks._push で組んだ尾を末尾に持つ文でも、欄 recommend が無ければ text は空で、question は文の全体のまま、note は文の推しを名指さない
        （尾を読むかを言う口 read_tail は無い）。同じ文に欄を渡せばその推しが答え"""
        self.assertNotIn("read_tail", inspect.signature(gatemarks.item_draft).parameters)
        text = self.BODY + self.tail()
        got = gatemarks.item_draft(text, gatemarks.GATE_NODE, recommend=None)
        self.assertEqual((got["question"], got["text"]), (text, ""))
        self.assertNotIn("文に書かれた推し", got["note"])
        self.assertNotIn("空の列は 0 を返す", got["note"])
        self.assertTrue(gatemarks.item_draft(text, gatemarks.GATE_NODE, recommend=self.REC)["text"].startswith("continue: "))

    def test_scenario_rows_are_read(self):
        """筋書き unattended-push・unattended-push-stop の事前審査の行は、推しを mark の欄 recommend に持ち（recommend_of が読める）、
        文に「／推し:」を書かない"""
        fixtures = pathlib.Path(__file__).resolve().parents[2] / "workflows" / "line" / "fixtures"
        for name, word in (("unattended-push", "continue"), ("unattended-push-stop", "stop")):
            with self.subTest(name=name):
                text = (fixtures / f"{name}.stubs.yaml").read_text(encoding="utf-8")
                line = next(line for line in text.splitlines() if line.startswith("plan-out:"))
                ask = json.loads(line.split(":", 1)[1])["asks"][0]
                self.assertEqual(gatemarks.recommend_of(ask["mark"])["answer"], word)
                self.assertNotIn("／推し:", ask["text"])

    def test_the_go_push_word_is_the_go_answer_word(self):
        """#733: 通す推しの字と、推しで進んだ時に答えに書く字（answer.VERBS の頭）は同じ"""
        self.assertEqual(gatemarks.RECOMMEND_ANSWERS[0], answer.VERBS[0])

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


class GateTextCase(unittest.TestCase):
    """答えを受ける関所の文（gate_text）の答え方。通す行の約束は、向きを照らす関所（修正前の承認ノード）と、照らさない関所（仕様の承認ノード）で違う"""
    ASKING = {"node": "", "kinds": ["plan_review"], "question": "通す範囲と条件を一言に", "items": ["修正案 1 が狭める能力: 空の列の mean"]}
    CHECKED = "次の依頼の下書きに回る"

    def pass_line(self, node: str, record_name: str) -> str:
        text = gatemarks.gate_text(self.ASKING, run_id="run-1", node=node, record_name=record_name)
        [line] = [x for x in text.splitlines() if x.startswith("- 通す:")]
        return line

    def test_the_pass_line_says_a_redirecting_note_stops(self):
        """修正前の承認ノードの通す行は、仕様駆動の run と写しの run では計画と違う向きの一言（向きが読めない一言・判定が落ちた時も）が修正へ進まずに止まり
        次の依頼の下書きに回ること、それ以外の一言は修正役に届くことを言う。仕様の承認ノードは向きを照らさないので、今の文のまま"""
        spec_approve = kit_load("spec", "files").APPROVE
        before_fix = self.pass_line(gatemarks.GATE_NODE, "run の置き場の gates/gate-before-fix.json")
        self.assertIn(self.CHECKED, before_fix)
        self.assertIn("仕様駆動の run と写しの run", before_fix)
        self.assertIn("向きが読めない", before_fix)
        self.assertIn("修正へ進まず", before_fix)
        self.assertIn("判定が落ちた", before_fix)
        self.assertIn("それ以外の一言は修正役に届く", before_fix)
        self.assertIn("gates/gate-before-fix.json", before_fix)
        spec = self.pass_line(spec_approve, "process.spec.approval")
        self.assertNotIn(self.CHECKED, spec)
        self.assertIn("修正役に届く", spec)
        self.assertIn("process.spec.approval", spec)

    REC = {"answer": "continue", "note": "このまま通す", "why": "呼び手が前提にしている"}

    def text_of(self, *items) -> str:
        return gatemarks.gate_text({**self.ASKING, "items": list(items)}, run_id="run-1", node=gatemarks.GATE_NODE, record_name="r")

    def test_gate_text_shows_each_rows_recommend_field(self):
        """承認ノードの文は、欄 recommend の推しを、その項目の下の子の行「機械が検めた推し: …」と冒頭 3 行の推しの行にだけ出す。末尾が推しの尾の形でも
        欄の無い行・字の要素は、本文の字のまま並び、子の行も冒頭の推しも持たない"""
        tail = gatemarks._push({gatemarks.RECOMMEND: self.REC})
        pushed = plainask.item_row("欄に推しを持つ行", None, self.REC)
        tailed = plainask.item_row("尾だけ在る行" + tail)
        lines = self.text_of(pushed, tailed, "字の要素" + tail).splitlines()
        i = lines.index("- 欄に推しを持つ行")
        self.assertEqual(lines[i + 1], gatemarks.MACHINE_PUSH + "通す（continue）——このまま通す（理由: 呼び手が前提にしている）")
        self.assertEqual(lines[i + 2], "- 尾だけ在る行" + tail, "欄の無い行は本文のまま、子の行を持たない")
        self.assertEqual(lines[i + 3], "- 字の要素" + tail)
        self.assertEqual(sum(x.startswith(gatemarks.MACHINE_PUSH) for x in lines), 1)
        head = [x for x in lines if x.startswith(gatemarks.PUSH)]
        self.assertEqual(head, [gatemarks.PUSH + "通す（continue）——このまま通す（理由: 呼び手が前提にしている）（ほかの項目の推しは判定の役が書いていない）"])
        self.assertNotIn("dict", "".join(lines), "行の要素を dict の字のまま並べない")

    def test_head_push_line_is_built_only_from_row_fields(self):
        """冒頭の推しの行は行の欄（recommend・reason_push）からだけ組む。文の途中に「推し: …」が在っても、欄が無い行はその切れ端を出さない"""
        middle = "割れる。推し: 案A——訳（これは審査役の字の途中）。ほかに案B が在る"
        lines = self.text_of(plainask.item_row(middle), middle).splitlines()
        self.assertEqual([x for x in lines if x.startswith(gatemarks.PUSH)], [gatemarks.PUSH + gatemarks.NO_PUSH])
        self.assertNotIn(gatemarks.MACHINE_PUSH, "".join(lines))
        shown = self.text_of(plainask.item_row(middle, None, None, "案B——訳"), plainask.item_row("欄の推し", None, self.REC)).splitlines()
        [head] = [x for x in shown if x.startswith(gatemarks.PUSH)]
        self.assertEqual(head, gatemarks.PUSH + "案B——訳；通す（continue）——このまま通す（理由: 呼び手が前提にしている）")
        self.assertEqual(sum(x.startswith(gatemarks.MACHINE_PUSH) for x in shown), 1, "表示だけの欄 reason_push は機械が検めた推しの子の行にしない")


class MeansRowsCase(unittest.TestCase):
    """頼みの解き方の外れの行（計画 means-answers の 3.2 の 8・3.3 の 2）: 文の頭・推しの尾・鍵の読み戻し。推しは渡した行の物だけ"""
    SAID = {"M1": "分母を len(xs) にする"}
    REC = {"answer": "continue", "note": "計画のまま進める", "why": "リポジトリの決まりに合う"}
    FIELDS = [{"structure": [{"means": "M1", "follows": True}]},
              {"structure": [{"means": "M1", "deviation": "リポジトリの決まりが別の層に置くと決めている"}]}]

    def test_plan_row_carries_the_departs_recommend(self):
        rows = gatemarks.means_rows(self.FIELDS, self.SAID, [{"item": 2, "means": "M1", "why": "決まりに合う", "recommend": self.REC}])
        self.assertEqual(len(rows), 1, rows)
        r = rows[0]
        self.assertEqual((r["source"], r["item"]), (gatemarks.MEANS_KIND, 2))
        self.assertTrue(r["text"].startswith("修正案 2 は頼みの解き方 M1「分母を len(xs) にする」に従わない——"), r["text"])
        self.assertEqual(r["mark"]["recommend"], self.REC)
        self.assertEqual(r["why"], [gatemarks.MEANS_WHY])
        text = gatemarks.depart_item(r)
        self.assertNotIn("世界の解:", text)
        self.assertEqual(gatemarks.recommend_of(r["mark"])["answer"], "continue", "推しは行の mark の欄 recommend が運ぶ")
        self.assertNotIn(gatemarks.PUSH, text, "文には推しの尾を書かない")
        self.assertEqual(gatemarks.means_key(text), (2, "M1", "departs"))

    def test_plan_row_without_departs_has_no_push(self):
        r = gatemarks.means_rows(self.FIELDS, self.SAID)[0]
        self.assertNotIn("recommend", r["mark"])
        self.assertIsNone(gatemarks.recommend_of(r["mark"]))
        self.assertNotIn(gatemarks.PUSH, gatemarks.depart_item(r))

    def test_drift_row(self):
        r = gatemarks.means_drift_rows([{"item": 1, "means": "M1", "design_quote": "設計の字", "plan_quote": "案の字",
                                         "why": "独立設計は別の層に置く", "recommend": self.REC}], self.SAID)[0]
        self.assertTrue(r["text"].startswith("修正案 1 は頼みの解き方 M1「分母を len(xs) にする」に従うが、独立設計と食い違う——"))
        self.assertEqual(gatemarks.means_key(r["text"]), (1, "M1", "drifts"))
        self.assertIsNone(gatemarks.means_key("修正案 1 の世界の解の行"))
        self.assertEqual(gatemarks.means_key(gatemarks.means_depart_text(1, "M1", {}, "別の層")), (1, "M1", "departs"))


class PrescriptionRowsCase(unittest.TestCase):
    RX = {"U": ["分母を len(xs) にする", "上限の枝を hi にする"]}
    REC = {"answer": "continue", "note": "計画のまま進める", "why": "リポジトリの決まりに合う"}
    FIELDS = [{"structure": [{"prescription": "U", "follows": True}]},
              {"structure": [{"prescription": "U", "deviation": "リポジトリの決まりが別の層に置くと決めている"},
                             {"means": "M1", "deviation": "頼みの解き方の外れはこの行に入らない"}]}]

    def test_plan_row_carries_the_departs_recommend(self):
        rows = gatemarks.prescription_depart_rows(
            self.FIELDS, self.RX, [{"item": 2, "prescription": "U", "why": "決まりに合う", "recommend": self.REC}])
        self.assertEqual(len(rows), 1, rows)
        r = rows[0]
        self.assertEqual((r["source"], r["item"]), (gatemarks.PRESCRIPTION_KIND, 2))
        self.assertTrue(r["text"].startswith("修正案 2 は単位 U の判定の処方「"), r["text"])
        self.assertIn("1. 分母を len(xs) にする", r["text"])
        self.assertIn("2. 上限の枝を hi にする", r["text"])
        self.assertIn("に従わない——リポジトリの決まりが別の層に置くと決めている", r["text"])
        self.assertNotIn(gatemarks.PRESCRIPTION_UNREAD, r["text"])
        self.assertEqual(r["mark"]["recommend"], self.REC)
        self.assertEqual(r["mark"]["decided_by"], "リポジトリの決まりが別の層に置くと決めている")
        self.assertEqual(r["why"], [gatemarks.PRESCRIPTION_WHY])
        self.assertTrue(gatemarks.PRESCRIPTION_WHY.startswith(gatemarks.ASK_CASES[0]), gatemarks.PRESCRIPTION_WHY)
        text = gatemarks.depart_item(r)
        self.assertNotIn("世界の解:", text)
        self.assertEqual(gatemarks.recommend_of(r["mark"])["answer"], "continue")
        self.assertNotIn(gatemarks.PUSH, text, "文には推しの尾を書かない")
        bare = gatemarks.prescription_depart_rows(self.FIELDS, self.RX)[0]
        self.assertNotIn("recommend", bare["mark"])
        self.assertIsNone(gatemarks.recommend_of(bare["mark"]), "推しの行を渡さなければ推しの欄は無い")
        self.assertNotIn(gatemarks.PUSH, gatemarks.depart_item(bare))
        unread = gatemarks.prescription_depart_rows(self.FIELDS, {})[0]
        self.assertIn(gatemarks.PRESCRIPTION_UNREAD, unread["text"])


if __name__ == "__main__":
    unittest.main()

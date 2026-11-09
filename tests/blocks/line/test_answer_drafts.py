"""人の判断を待つ項目への答えの下書き（workflows/line/src/facts.py の answer_drafts。報告が次の run の依頼の下書きの answers に置く）。

元は test_runreport.py の DraftsCase（元 runreport.answer_drafts。その前は lib/tests/test_gate_drafts.py の DraftsCase。
docs/design/README.md の 9.5）。新しい形では下書きの材料を、承認し直すかの問い（spec_check の questions）・独立の目 R4 の問い・
無人の run で修正前の承認ノードが通さなかった時の載せなかった台帳の問い（ask_before_fix の deferred）・保留の台帳の問い・問いの
立っていない測れていない素材の 5 つから組む。承認ノードの項目は、行の欄 recommend だけを gatemarks.item_draft(…, recommend=…) で
答えにする（test_gate_item_push_tail_becomes_the_draft_answer。抜け方 gates.passage が同じ欄を同じ recommend_of で読む）。欄の無い項目は
text が空で、文の世界の解・狭めない案の尾（gates が付けた物を item_draft が読み戻す）を note に置き、人が答えを書く
（test_gate_item_without_push_tail_keeps_what_its_text_says。元 test_no_narrow_and_face_rows_give_their_marks の働き）。
文の末尾の字は推しと読まない。R4 の問いの行は欄を持たないので、末尾が推しの形でも答えにしない
（test_r4_question_push_tail_is_not_the_draft_answer）。
推しで抜けるかは test_gate_drafts.py。
"""
import json
import unittest

from tests.blocks import kit

BLOCK = "line"
FORK_UNIT = "stats.py mean: 空の列の扱いが決まらない"
FORK = {"key": "q-empty-mean", "kind": "fork", "status": "held", "origin": FORK_UNIT, "options": ["例外", "0 を返す"],
        "reason": "空の列の意味が 2 つに割れる。推し: 例外——呼び手が既に例外を捕まえている"}
BARE_FORK = {**FORK, "key": "q-bare", "reason": "空の列の意味が 2 つに割れる"}


def ptr(path: str) -> dict:
    return {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": path}


class AnswerDraftsCase(unittest.TestCase):
    def setUp(self):
        self.f = kit.load(BLOCK, "facts")
        self.gm = __import__("gatemarks")
        self.run = kit.Run(self, BLOCK)

    def put(self, rel: str, doc) -> dict:
        p = self.run.artifacts / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return ptr(rel)

    def judged(self, questions=(), units=(), materials=None) -> dict:
        """判定の返り（judgment と materials のポインタ）を持つ returns"""
        judge = {"judgment": self.put("judge/judgment.json", {"units": list(units), "questions": list(questions)})}
        if materials is not None:
            judge["materials"] = self.put("judge/materials.json", materials)
        return {"judge": judge}

    def drafts(self, returns=None, *, values=None, gates=None, unattended=False) -> list:
        with self.run.env():
            return self.f.answer_drafts(values or {}, returns or {}, gates or {}, unattended)

    def test_final_gate_r4_questions_are_drafted_even_when_passed(self):
        """元 test_final_gate_r4_questions_are_drafted_even_when_passed: 独立の目 R4 の問いごとに下書き。関所の continue は問いに
        答えないので、人の居る run でも関所が通した run でも作る（#505）"""
        returns = {"eyes": {"questions": ["守りを触ってよいか", ""]}}
        drafts = self.drafts(returns, unattended=True)
        self.assertEqual([(d["question"], d["text"]) for d in drafts], [("守りを触ってよいか", "")])
        for unattended in (True, False):
            with self.subTest(unattended=unattended):
                self.assertEqual(self.drafts(returns, gates={"gate-final": {"decision": "continue", "text": ""}}, unattended=unattended),
                                 drafts)

    def test_means_questions_are_drafted_only_while_unanswered(self):
        """計画 means-answers の 6.3 の 3 の 4: R2 の頼みどおりの違いの問いは、最後の承認ノードの continue / stop がそのまま答えなので
        下書きにしない。答えの無い run と、R2 が redesign-needed の run（continue を答えに数えない）だけ下書きにする"""
        q = "R2: 差分は頼みの解き方 M1「x」どおりだが、独立設計と食い違う——y"
        returns = {"eyes": {"questions": [], "means_questions": [q]}}
        self.assertEqual([d["question"] for d in self.drafts(returns, unattended=True)], [q])
        for decision in ("continue", "stop"):
            with self.subTest(decision=decision):
                self.assertEqual(self.drafts(returns, gates={"gate-final": {"decision": decision, "text": ""}}), [])
        red = {"eyes": {**returns["eyes"], "r2": {"status": "redesign-needed", "reason": "別"}}}
        self.assertEqual([d["question"] for d in self.drafts(red, gates={"gate-final": {"decision": "continue", "text": ""}})], [q])

    def test_each_item_of_a_stopped_unattended_gate_gets_a_draft(self):
        """元 test_each_stopped_item_gets_a_marked_draft: 無人の run で修正前の承認ノードが開かずに止まった時、止めた項目（事前審査が
        人に回した行）ごとに印つきの下書き。gates.before_fix が組んだ出力を ask_before_fix の値としてそのまま渡す"""
        gates = kit.load(BLOCK, "gates")
        rounds = {"ok": True, "status": "ok", "round": 1, "deviations": [],
                  "asks": [{"kind": "regression", "text": "狭めるか", "decided": False},
                           {"kind": "world", "text": "どの定石に寄せるか", "decided": False}]}
        got = gates.before_fix(rounds, unattended_run=True, design=False)
        self.assertEqual((got["open"], got["go"]), (False, False), got)
        items = [row["text"] for _, row in got["items"]]
        self.assertEqual(len(items), 2, got)
        drafts = self.drafts(values={"ask_before_fix": {k: got[k] for k in ("deferred", "asked")}},
                             gates={"gate-before-fix": None}, unattended=True)
        self.assertEqual([d["question"] for d in drafts], items, drafts)
        self.assertTrue(all(d["draft"] is True and d["source"] for d in drafts), drafts)

    SHOWN = ["修正案 1 が狭める能力: 空の列の mean——0 を返していた呼び手が例外を受ける", "修正案 2 が狭める能力: 呼び手の docs"]
    NOTE = "計画と違い、空の列は例外を投げる形にして"
    REASON = "判定: redirected（計画は 0 を返すが一言は例外を選んでいる）。一言: " + NOTE

    def redirected(self, **over) -> dict:
        return {"answer_before_fix": {"go": False, "stop_reason": "works:answer-redirected", "reason": self.REASON, "policy": "",
                                      "answer": {"decision": "continue", "text": self.NOTE, "asked": self.SHOWN}, **over}}

    def test_redirected_note_is_drafted_for_each_shown_item(self):
        """修正前の答えが works:answer-redirected で止めた run は、承認ノードで見せた項目ごとに、下書きの印つきの答えの行を出す（question は項目の
        文の全文、text は空、note に返りの reason。reason が含む人の一言は重ねない）。止めていない run・人が止めた run・項目の無い答えは出さない"""
        got = self.drafts(values=self.redirected())
        self.assertEqual([(d["question"], d["text"]) for d in got], [(q, "") for q in self.SHOWN])
        for draft in got:
            self.assertTrue(draft["draft"] is True and draft["source"] == self.f.REDIRECT_SOURCE, draft)
            self.assertEqual(draft["note"].count(self.NOTE), 1, draft["note"])
            self.assertIn(self.REASON, draft["note"])
            self.assertIn(self.f.REDIRECT_NOTE.split("{")[0], draft["note"])
        for name, values in (("passed", self.redirected(go=True, stop_reason="")),
                             ("human stop", self.redirected(stop_reason="human:gate-before-fix")),
                             ("no items", self.redirected(answer={"decision": "continue", "text": self.NOTE, "asked": []})),
                             ("no answer", self.redirected(answer=None)), ("no gate", {})):
            with self.subTest(name):
                self.assertEqual(self.drafts(values=values), [])
        # 同じ項目の文が無人の run の載せなかった項目の下書きにも在れば、答えの下書きは 1 行にまとめる（先に置く一言つきの行が残る）
        values = {**self.redirected(), "ask_before_fix": {"deferred": [self.SHOWN[0]], "asked": []}}
        got = [d for d in self.drafts(values=values, gates={"gate-before-fix": None}, unattended=True) if d["question"] == self.SHOWN[0]]
        self.assertEqual(len(got), 1, got)
        self.assertEqual(got[0]["source"], self.f.REDIRECT_SOURCE)

    def stopped_gate(self, rounds, **kw) -> dict:
        """無人の run で止まった修正前の承認ノードの出力のうち、下書きの材料（ask_before_fix の値）"""
        gates = kit.load(BLOCK, "gates")
        got = gates.before_fix(rounds, unattended_run=True, design=False, **kw)
        self.assertEqual((got["open"], got["go"]), (False, False), got)
        return {k: got[k] for k in ("deferred", "asked")}

    def test_gate_item_push_tail_becomes_the_draft_answer(self):
        """推しの欄 recommend を持つ項目（頼みの解き方の行）の下書きは、欄の推しが答え。欄の無い穴の行は text が空。欄の在る項目は
        承認ノードの抜け方が読む答え（gates.passage の pushed）と下書きの頭の答えが一致し、question は推しの尾の無い本文"""
        gates = kit.load(BLOCK, "gates")
        rec = {"answer": "continue", "note": "空の列は 0 を返す形で通す", "why": "呼び手が 0 を前提に書かれている"}
        means = {"source": self.gm.MEANS_KIND, "item": 1, "why": [self.gm.MEANS_WHY],
                 "mark": {"decided_by": "リポジトリの決まりが別の層に置く", "recommend": rec},
                 "text": "修正案 1 は頼みの解き方 M1「分母を直す」に従うが、独立設計と食い違う——別の層に置く"}
        rounds = {"ok": True, "status": "ok", "round": 1, "deviations": [means],
                  "asks": [{"kind": "regression", "text": "狭めるか", "decided": False}]}
        ask_before_fix = self.stopped_gate(rounds)
        drafts = self.drafts(values={"ask_before_fix": ask_before_fix}, gates={"gate-before-fix": None}, unattended=True)
        by_question = {d["question"]: d for d in drafts}
        pushed_row = next(r for r in ask_before_fix["deferred"] if r.get("recommend"))
        self.assertNotIn(self.gm.PUSH, pushed_row["text"], "question は推しの尾の無い本文")
        pushed = by_question[pushed_row["text"]]
        self.assertEqual(pushed["text"], "continue: 空の列は 0 を返す形で通す（推す理由: 呼び手が 0 を前提に書かれている）")
        decided = gates.passage([pushed_row]).pushed[self.gm.answer.PUSHED][0]
        self.assertTrue(pushed["text"].startswith(decided["answer"]))
        self.assertIn(decided["note"], pushed["text"])
        self.assertIn("recommend", pushed["source"])
        bare = by_question["狭めるか"]
        self.assertEqual(bare["text"], "")

    def test_deferred_and_means_rows_recommend_field_is_the_draft_answer(self):
        """載せなかった修正前の項目の行と R2 の問いの行が欄 recommend を持てば、推しの尾の無い文でも下書きの text がその欄の推しの答えになり、
        question は尾の無い本文。欄を持たない行は、末尾が推しの形でも text が空"""
        rec = {"answer": "continue", "note": "空の列は 0 を返す形で通す", "why": "呼び手が 0 を前提に書かれている"}
        tail = self.gm._push({self.gm.RECOMMEND: rec})
        values = {"ask_before_fix": {"deferred": [{"text": "載せなかった行", "recommend": rec}, {"text": "欄の無い行" + tail}], "asked": []}}
        returns = {"eyes": {"questions": [], "means_questions": [{"text": "R2 の問い", "recommend": {**rec, "answer": "stop"}},
                                         {"text": "R2 の欄の無い問い" + tail}]}}
        by_question = {d["question"]: d for d in self.drafts(returns, values=values, gates={"gate-before-fix": None}, unattended=True)}
        self.assertEqual(by_question["載せなかった行"]["text"], "continue: 空の列は 0 を返す形で通す（推す理由: 呼び手が 0 を前提に書かれている）")
        self.assertEqual(by_question["R2 の問い"]["text"], "stop: 空の列は 0 を返す形で通す（推す理由: 呼び手が 0 を前提に書かれている）")
        for question in ("欄の無い行" + tail, "R2 の欄の無い問い" + tail):
            with self.subTest(question=question):
                self.assertEqual(by_question[question]["text"], "")
                self.assertNotIn("文に書かれた推し", by_question[question]["note"])

    def test_r4_question_push_tail_is_not_the_draft_answer(self):
        """R4 の問いの行は役が書いた文なので、末尾が推しの尾（_push の形）でも答えにしない（text は空で、question は尾を含む文の全体）。
        同じ run の、載せなかった修正前の項目の欄 recommend の推しは今どおり答えになる"""
        rec = {"answer": "continue", "note": "空の列は 0 を返す形で通す", "why": "呼び手が 0 を前提に書かれている"}
        means = {"source": self.gm.MEANS_KIND, "item": 1, "why": [self.gm.MEANS_WHY],
                 "mark": {"decided_by": "リポジトリの決まりが別の層に置く", "recommend": rec},
                 "text": "修正案 1 は頼みの解き方 M1「分母を直す」に従うが、独立設計と食い違う——別の層に置く"}
        rounds = {"ok": True, "status": "ok", "round": 1, "deviations": [means],
                  "asks": [{"kind": "regression", "text": "狭めるか", "decided": False}]}
        r4_row = "守りを触ってよいか" + self.gm._push({self.gm.RECOMMEND: rec})
        drafts = self.drafts({"eyes": {"questions": [r4_row]}}, values={"ask_before_fix": self.stopped_gate(rounds)},
                             gates={"gate-before-fix": None}, unattended=True)
        by_question = {d["question"]: d for d in drafts}
        self.assertIn(r4_row, by_question, "R4 の行は尾を含む文の全体を question にする")
        self.assertEqual(by_question[r4_row]["text"], "")
        pushed = [d["text"] for q, d in by_question.items() if q not in (r4_row, "狭めるか")]
        self.assertEqual(pushed, ["continue: 空の列は 0 を返す形で通す（推す理由: 呼び手が 0 を前提に書かれている）"])

    def test_gate_item_without_push_tail_keeps_what_its_text_says(self):
        """推しの欄 recommend を持たない項目は text が空で、機械は推しを作らない。構造の目の設計の行の採った案（chosen）は question の本文の
        「構造の目が採った案」の句に在り、note は文から推しを拾わない。世界の解・狭めない案の尾つきの穴の行も「推しも狭めない案も世界の解も
        役が書いていない」とは言わない"""
        gates = kit.load(BLOCK, "gates")
        rounds = {"ok": True, "status": "ok", "round": 1, "deviations": [],
                  "asks": [{"kind": "regression", "text": "狭めるか", "decided": False,
                            "mark": {"decided_by": "x", "world": "W", "no_narrow": "N"}}]}
        design = [{"route": gates.structmark.ROUTE_UP, "unit_id": "u1", "undecided_because": "2 つの形が割れる", "chosen": "案Zを採る"},
                  {"route": gates.structmark.ROUTE_UP, "unit_id": "u2", "undecided_because": "採る案を書いていない"}]
        ask_before_fix = self.stopped_gate(rounds, design_rows_=design)
        drafts = self.drafts(values={"ask_before_fix": ask_before_fix}, gates={"gate-before-fix": None}, unattended=True)
        self.assertEqual(len(drafts), 3, drafts)
        for d in drafts:
            with self.subTest(question=d["question"]):
                self.assertEqual(d["text"], "")
                self.assertNotIn("役が書いていない", d["note"])
        design_draft = next(d for d in drafts if d["question"].startswith(self.gm.DESIGN_HEAD))
        self.assertIn(self.gm.CHOSEN_HEAD + "案Zを採る", design_draft["question"])
        self.assertNotIn("文に書かれた推し:", design_draft["note"])
        hole = next(d for d in drafts if "狭めるか" in d["question"])
        self.assertIn("世界の解: W", hole["note"])
        self.assertIn("狭めない案: N", hole["note"])
        no_chosen = next(d for d in drafts if "u2" in d["question"])
        self.assertNotIn("文に書かれた推し:", no_chosen["note"])

    def test_attended_or_passed_gate_gets_no_gate_item_drafts(self):
        """元 test_attended_run_gets_no_gate_item_drafts: 人の居る run と、修正前の承認ノードを通した（approve・continue）無人の run は、
        承認ノードの項目の下書きを作らない"""
        values = {"ask_before_fix": {"deferred": ["載せなかった問い", {"text": "行の形の問い"}]}}
        for gates, unattended in (({}, False), ({"gate-before-fix": {"decision": "approve", "text": ""}}, True),
                                  ({"gate-before-fix": {"decision": "continue", "text": ""}}, True)):
            with self.subTest(gates=gates, unattended=unattended):
                self.assertEqual(self.drafts(values=values, gates=gates, unattended=unattended), [])

    def test_held_ledger_question_is_drafted_in_attended_run_too(self):
        """元 test_held_ledger_question_is_drafted_in_attended_run_too: 保留のままの台帳の問いは、人の居る run でも key を question に
        した推しの下書きになる。決着した問いと関所で通した問いは下書きにしない。「保留: key」で保留を続けた問いは下書きにする"""
        returns = self.judged([FORK, {**FORK, "key": "q-done", "status": "resolved"}])
        drafts = self.drafts(returns)
        self.assertEqual([(d["question"], d["text"]) for d in drafts], [(FORK["key"], "例外——呼び手が既に例外を捕まえている")])
        passed = {"gate-before-fix": {"decision": "continue", "text": ""}}
        self.assertEqual(len(self.drafts(returns, gates=passed)), 1, "関所が聞いていない問いは答えていない")
        passed = {"gate-before-fix": {"decision": "continue", "text": "", "asked": [self.gm.ask_text(FORK)]}}
        self.assertEqual(self.drafts(returns, gates=passed), [])
        held = {"gate-before-fix": {"decision": "continue", "text": f"保留: {FORK['key']}", "asked": [self.gm.ask_text(FORK)]}}
        self.assertEqual(len(self.drafts(returns, gates=held)), 1)

    def test_unattended_run_takes_the_held_fork_push(self):
        """元 test_unattended_run_takes_the_held_fork_push_in_the_head の下書きの分: 無人の run が推しを答えに採った台帳の問いは下書きに
        しない（推しの無い問いは下書きにする）"""
        returns = self.judged([FORK, BARE_FORK], units=[{"key": FORK_UNIT, "label": "block"}])
        self.assertEqual([d["question"] for d in self.drafts(returns, unattended=True)], [BARE_FORK["key"]])
        self.assertEqual([d["question"] for d in self.drafts(returns)], [FORK["key"], BARE_FORK["key"]])

    def test_unmeasured_material_draft_carries_its_reason(self):
        """元 test_unmeasured_material_draft_carries_its_reason: 問いの立っていない測れていない素材は素材の名を question にした下書きで、
        測れなかった訳を note に置く。依頼の答えが当たった素材は下書きにしない（命令と出力が無くても）"""
        returns = self.judged(materials={"parallel_pr": {"status": "not_run", "reason": "forge が無い"}})
        drafts = self.drafts(returns)
        self.assertEqual([(d["question"], d["text"]) for d in drafts], [("parallel_pr", "")])
        self.assertIn("forge が無い", drafts[0]["note"])
        answered = {"request_answers": [{"question": "parallel_pr", "text": "無い", "command": "gh pr list", "output": "[]"}]}
        self.assertEqual(self.drafts({**returns, "request_in": answered}), [])
        unmeasured = {"request_answers": [{"question": "parallel_pr", "text": "無いはず"}]}
        self.assertEqual(self.drafts({**returns, "request_in": unmeasured}), [])


if __name__ == "__main__":
    unittest.main()

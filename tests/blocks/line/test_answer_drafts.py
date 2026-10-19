"""人の判断を待つ項目への答えの下書き（workflows/line/src/facts.py の answer_drafts。報告が次の run の依頼の下書きの answers に置く）。

元は今の lib/tests/test_runreport.py の DraftsCase（元 runreport.answer_drafts。その前は lib/tests/test_gate_drafts.py の DraftsCase。
docs/design/README.md の 9.5）。新しい形では下書きの材料を、承認し直すかの問い（spec_check の questions）・独立の目 R4 の問い・
無人の run で修正前の承認ノードが通さなかった時の載せなかった台帳の問い（ask_before_fix の deferred）・保留の台帳の問い・問いの
立っていない測れていない素材の 5 つから組む。修正案の狭める行と事前審査の穴の推しを読む元の下書き（元 test_recommend_of_the_narrow_
becomes_the_answer・test_no_narrow_and_face_rows_give_their_marks・test_world_deviation_drafted_once）は、承認ノードの項目を line の
gates.before_fix が組むようになって下書きの材料から外れたので写さない（推しで抜けるかは test_gate_drafts.py）。
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

    def drafts(self, returns=None, *, values=None, gates=None, record=None, unattended=False) -> list:
        with self.run.env():
            return self.f.answer_drafts(values or {}, returns or {}, gates or {}, record or {}, unattended)

    def test_every_draft_is_marked(self):
        """下書きは全部 draft: true と出どころ source を持つ（依頼の入口 carry.parts が拒む印）"""
        got = self.drafts({**self.judged([FORK]), "eyes": {"questions": ["守りを触ってよいか"]}},
                          values={"spec_check": {"questions": ["受け入れ条件のテストが変わった"]}})
        self.assertEqual(len(got), 3, got)
        self.assertTrue(all(d["draft"] is True and d["source"] for d in got), got)

    def test_spec_question_is_drafted_with_its_words(self):
        """承認し直すかの問いは text が空の下書き。照らせなかった（unchecked が false でない）時は「照らせなかった」の語で名乗る"""
        for unchecked in (False, True):
            with self.subTest(unchecked=unchecked):
                got = self.drafts(values={"spec_check": {"questions": ["受け入れ条件のテストが変わった", " "], "unchecked": unchecked}})
                words = self.gm.spec_words(unchecked)
                self.assertEqual([(d["question"], d["text"], d["source"]) for d in got],
                                 [("受け入れ条件のテストが変わった", "", words.source)])

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

    def test_each_item_of_a_stopped_unattended_gate_gets_a_draft(self):
        """元 test_each_stopped_item_gets_a_marked_draft: 無人の run で修正前の承認ノードが開かずに止まった時、止めた項目（事前審査が
        人に回した行）ごとに印つきの下書き。gates.before_fix が組んだ出力を ask_before_fix の値としてそのまま渡す"""
        gates = kit.load(BLOCK, "gates")
        rounds = {"ok": True, "status": "ok", "round": 1, "deviations": [],
                  "asks": [{"kind": "regression", "text": "狭めるか", "decided": False},
                           {"kind": "world", "text": "どの定石に寄せるか", "decided": False}]}
        got = gates.before_fix(rounds, unattended_run=True, design=False)
        self.assertEqual((got["open"], got["go"]), (False, False), got)
        items = [text for _, text in got["items"]]
        self.assertEqual(len(items), 2, got)
        drafts = self.drafts(values={"ask_before_fix": {k: got[k] for k in ("deferred", "asked")}},
                             gates={"gate-before-fix": None}, unattended=True)
        self.assertEqual([d["question"] for d in drafts], items, drafts)
        self.assertTrue(all(d["draft"] is True and d["source"] for d in drafts), drafts)

    def test_attended_or_passed_gate_gets_no_gate_item_drafts(self):
        """元 test_attended_run_gets_no_gate_item_drafts: 人の居る run と、修正前の承認ノードを通した（approve・continue）無人の run は、
        承認ノードの項目の下書きを作らない"""
        values = {"ask_before_fix": {"deferred": ["載せなかった問い", {"text": "行の形の問い"}]}}
        for gates, unattended in (({}, False), ({"gate-before-fix": {"decision": "approve", "text": ""}}, True),
                                  ({"gate-before-fix": {"decision": "continue", "text": ""}}, True)):
            with self.subTest(gates=gates, unattended=unattended):
                self.assertEqual(self.drafts(values=values, gates=gates, unattended=unattended), [])

    def test_deferred_ledger_question_is_drafted_once(self):
        """元 runreport.answer_drafts の ②（保留のままの台帳の問いごとに 1 行）と「同じ問いは 1 度だけ」: 無人の run が承認ノードに
        載せなかった台帳の問い（deferred は gates.before_fix が gatemarks.ask_text で組む）は、保留の台帳の問いとして key で 1 行だけ
        下書きにする。承認ノードの項目の文の行を重ねて作らない"""
        returns = self.judged([BARE_FORK])
        values = {"ask_before_fix": {"deferred": [self.gm.ask_text(BARE_FORK)]}}
        got = self.drafts(returns, values=values, unattended=True)
        self.assertEqual([d["question"] for d in got], [BARE_FORK["key"]], got)

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

    def test_held_question_without_push_names_its_options(self):
        """元 test_row_with_nothing_still_gets_a_draft_saying_so の台帳の問いの分: 推しの無い保留の問いは text が空で、選択肢を note に置く"""
        drafts = self.drafts(self.judged([BARE_FORK]))
        self.assertEqual([(d["question"], d["text"]) for d in drafts], [(BARE_FORK["key"], "")])
        self.assertIn("推しを判定の役が書いていない", drafts[0]["note"])
        self.assertIn("例外・0 を返す", drafts[0]["note"])

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
        answered = {"answers": [{"question": "parallel_pr", "text": "無い", "command": "gh pr list", "output": "[]"}]}
        self.assertEqual(self.drafts(returns, record=answered), [])
        unmeasured = {"answers": [{"question": "parallel_pr", "text": "無いはず"}]}
        self.assertEqual(self.drafts(returns, record=unmeasured), [])

    def test_material_with_its_question_is_drafted_once(self):
        """素材から立てた問いが台帳に在れば、素材の行は足さず問いの下書きだけ（出どころ origin が素材の名）"""
        q = {"key": "parallel_pr: 重なりを確かめる", "kind": "field", "status": "escalate", "origin": "", "reason": "測れていない"}
        returns = self.judged([q], materials={"parallel_pr": {"status": "not_run", "reason": "forge が無い"}})
        self.assertEqual([d["question"] for d in self.drafts(returns)], ["parallel_pr"], "素材の名だけに当たる問いは素材の名で答える")

    def test_same_question_is_drafted_once(self):
        """同じ question の下書きは 1 つだけ（先に組んだ物を残す）"""
        got = self.drafts({"eyes": {"questions": ["同じ問い", "同じ問い"]}}, values={"spec_check": {"questions": ["同じ問い"], "unchecked": False}})
        self.assertEqual(len(got), 1, got)
        self.assertEqual(got[0]["source"], self.gm.spec_words(False).source)


if __name__ == "__main__":
    unittest.main()

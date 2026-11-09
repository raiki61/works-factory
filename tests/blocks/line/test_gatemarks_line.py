"""問いの台帳の承認ノードの決めの部分（元 lib/tests/test_gatemarks.py の PushRecCase のうち、line の src/gates.py へ移った
passage・design_talk・request_answers の部分。integration.md の 4.5-4 (a)(b)）。推しの欄の検め（recommend_of）と表示の句（_push）と問いの行の形は
KEEP の lib/gatemarks.py に残り、その試験は lib/tests/test_gatemarks.py が持つ。"""
import unittest

from tests.blocks import kit

gates = kit.load("line", "gates")
import answer  # noqa: E402
import gatemarks  # noqa: E402
import plainask  # noqa: E402


class PushRecCase(unittest.TestCase):
    """#552: 承認ノードの項目の行の欄 recommend を検め直し、無人の run が推しで通る答えを組む"""
    REC = {"answer": "continue", "note": "空の列は 0 を返す／形で通す", "why": "呼び手が 0 を前提に書かれている"}
    BODY = "修正案 1 が狭める能力: 空の列で例外を投げる——0 を返す形に変える（人に聞く訳: 決め手の欄が揃わない）"

    def row(self, **rec):
        """事前審査の行（gates._gate_row が組む。文に推しの尾は書かず、推しは欄 recommend が運ぶ）"""
        return gates._gate_row("regression", self.BODY, {**self.REC, **rec})[1]

    def test_passage_reads_the_recommend_field_and_stops_on_a_tail_shaped_text(self):
        """#653: 無人の方針の口 gates.passage は行の欄 recommend を読む。通すかは欄の answer、note は 1 行に畳んだ字（「／」は「・」）で、
        答えに残す行は {item, answer, note, why}。末尾を推しの尾の形にした欄の無い行や、止める推しの行が混じれば止まる"""
        rows = [self.row(), self.row(), gates._gate_row("regression", "修正案 2 が狭める能力: y", {**self.REC, "note": "y で通す"})[1]]
        got = gates.passage(rows).pushed
        self.assertEqual((got["decision"], got["text"]), ("continue", "空の列は 0 を返す・形で通す；y で通す"))
        self.assertEqual(got[answer.PUSHED], [{"item": r["text"], "answer": "continue", "note": n, "why": "呼び手が 0 を前提に書かれている"}
                                              for r, n in zip(rows, ("空の列は 0 を返す・形で通す", "空の列は 0 を返す・形で通す", "y で通す"))])
        self.assertNotIn(gatemarks.PUSH, self.row()["text"], "推しは文に書かない")
        tailed = plainask.item_row(self.BODY + gatemarks._push({gatemarks.RECOMMEND: self.REC}))
        for rows in ([], [self.row(), self.BODY], [self.row(), self.row(answer="stop")], [tailed], [self.row(), tailed]):
            with self.subTest(rows=rows):
                self.assertIsNone(gates.passage(rows).pushed)

    def test_the_go_push_word_is_the_go_answer_word(self):
        """#733: passage が欄の answer と比べる通す推しの字（RECOMMEND_ANSWERS[0]）と、推しで進んだ時に口が答えに書く字（passage の decision）は同じ"""
        self.assertEqual(gatemarks.RECOMMEND_ANSWERS[0], answer.VERBS[0])

    def test_gate_items_keep_the_push_origin(self):
        """推しで通した答えを human_items の行にしても欄 answer.PUSHED を落とさない（人の答えの行は持たない）"""
        pushed = gates.passage([self.row()]).pushed
        self.assertEqual(gatemarks.gate_items(pushed)[0][answer.PUSHED], pushed[answer.PUSHED])
        self.assertNotIn(answer.PUSHED, gatemarks.gate_items({"decision": "continue", "text": "人"})[0])


class RecordReadsCase(unittest.TestCase):
    """4.5-4 (b): 設計だけの run かは始めの記録の dict の値で、依頼の答えは配る値（src.descend.dealt の写し）の値で読む（KEEP の lib に記録を
    読ませない）"""

    def test_design_only_and_request_answers(self):
        self.assertTrue(gates.design_talk({"design_talk": gatemarks.DESIGN_ONLY}))
        self.assertFalse(gates.design_talk({}))
        self.assertFalse(gates.design_talk(None))
        self.assertEqual(gates.request_answers({"request_answers": [{"question": "q", "text": "a"}, "x"]}), [{"question": "q", "text": "a"}])
        self.assertEqual(gates.request_answers({"request_answers": "x"}), [])


if __name__ == "__main__":
    unittest.main()

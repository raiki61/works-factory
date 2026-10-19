"""問いの台帳の承認ノードの決めの部分（元 lib/tests/test_gatemarks.py の PushRecCase のうち、line の src/gates.py へ移った row_push・
passage・design_only・request_answers の部分。integration.md の 4.5-4 (a)(b)）。推しの尾の字の形（push_rec・_push）と問いの行の形は
KEEP の lib/gatemarks.py に残り、その試験は lib/tests/test_gatemarks.py が持つ。"""
import unittest

from tests.blocks import kit

gates = kit.load("line", "gates")
import answer  # noqa: E402
import gatemarks  # noqa: E402


class PushRecCase(unittest.TestCase):
    """#552: 承認ノードの項目の推しの尾を読み戻し、無人の run が推しで通る答えを組む"""
    REC = {"answer": "continue", "note": "空の列は 0 を返す／形で通す", "why": "呼び手が 0 を前提に書かれている"}
    BODY = "修正案 1 が狭める能力: 空の列で例外を投げる——0 を返す形に変える（人に聞く訳: 決め手の欄が揃わない）"

    def row(self, **rec):
        return gates._item(self.BODY, {gatemarks.RECOMMEND: {**self.REC, **rec}})

    def test_row_push_is_the_policy_reading_of_the_tail(self):
        """#653: 推しの尾の読みを無人の方針の口（gates.passage）に渡す形にする。通すかと note は尾の字のまま、答えに残す読みは push_rec"""
        rows = [self.row(), self.row(), gates._item("修正案 2 が狭める能力: y", {gatemarks.RECOMMEND: {**self.REC, "note": "y で通す"}})]
        got = gates.passage(rows, gates.row_push).pushed
        self.assertEqual((got["decision"], got["text"]), ("continue", "空の列は 0 を返す・形で通す；y で通す"))
        self.assertEqual(got[answer.PUSHED], [gatemarks.push_rec(r) for r in rows])
        self.assertEqual(gates.row_push(self.row(answer="stop")).go, False)
        self.assertIsNone(gates.row_push(self.BODY))
        for rows in ([], [self.row(), self.BODY], [self.row(), self.row(answer="stop")]):
            with self.subTest(rows=rows):
                self.assertIsNone(gates.passage(rows, gates.row_push).pushed)

    def test_the_go_push_word_is_the_go_answer_word(self):
        """#733: 通す推しの字（row_push の go）と、推しで進んだ時に口が答えに書く字（passage の decision）は同じ"""
        self.assertEqual(gatemarks.RECOMMEND_ANSWERS[0], answer.VERBS[0])

    def test_gate_items_keep_the_push_origin(self):
        """推しで通した答えを human_items の行にしても欄 answer.PUSHED を落とさない（人の答えの行は持たない）"""
        pushed = gates.passage([self.row()], gates.row_push).pushed
        self.assertEqual(gatemarks.gate_items(pushed)[0][answer.PUSHED], pushed[answer.PUSHED])
        self.assertNotIn(answer.PUSHED, gatemarks.gate_items({"decision": "continue", "text": "人"})[0])


class RecordReadsCase(unittest.TestCase):
    """4.5-4 (b): 設計だけの run か・依頼が先に持っていた答えは、始めの記録の dict の値で読む（KEEP の lib に記録を読ませない）"""

    def test_design_only_and_request_answers(self):
        self.assertTrue(gates.design_only({"design_only": gatemarks.DESIGN_ONLY}))
        self.assertFalse(gates.design_only({}))
        self.assertFalse(gates.design_only(None))
        self.assertEqual(gates.request_answers({"answers": [{"question": "q", "text": "a"}, "x"]}), [{"question": "q", "text": "a"}])
        self.assertEqual(gates.request_answers({"answers": "x"}), [])


if __name__ == "__main__":
    unittest.main()

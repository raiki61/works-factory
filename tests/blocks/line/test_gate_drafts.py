"""承認ノードの項目の推しと無人の run（元 lib/tests/test_gate_drafts.py の line の部分）。

元のファイルの SchemaCase・GapsCase（推しの欄の形と照らし。KEEP の lib/gatemarks.py）・IntakeCase（下書きの答えを依頼の入口が拒む。
KEEP の lib/carry.py）は lib/tests に残り、planblk.RECOMMEND_REJECT の照らしは plan の block の試験へ移る。line に移るのは、役が
書いた推しの尾で無人の run が修正前の承認ノードを抜けるか止まるかの決め（src/gates.py。機械は推しを作らない）。
"""
import unittest

from tests.blocks import kit

gates = kit.load("line", "gates")
import gatemarks  # noqa: E402
import stopby  # noqa: E402

REC = {"answer": "continue", "note": "daemon だけを Recreate にする範囲で通す", "why": "Dagster 公式の chart が同じ分け方"}
NARROW = "修正案 1 が狭める能力: webserver を RollingUpdate から外す——daemon と同じ Deployment に置く"


def rounds_with(marks):
    rows = [{"kind": "regression", "node": "p2.fix_plan", "text": NARROW, "units": ["u1"], "mark": m, "decided": False,
             "why": {"obvious": ["決め手の欄が揃わない"]}} for m in marks]
    return {"ok": True, "status": "ok", "round": 1, "stalled": False, "asks": rows, "deviations": []}


class UnattendedDraftsCase(unittest.TestCase):
    def ask(self, marks):
        return gates.before_fix(rounds_with(marks), unattended_run=True, design=False)

    def test_recommend_tail_reaches_the_gate_row(self):
        """役が人に回す行に書いた推し recommend は、項目の文の末尾の尾になり、無人の run の答えに読み戻せる"""
        out = self.ask([{gatemarks.RECOMMEND: REC}])
        self.assertTrue(out["asked"][0].startswith(NARROW))
        self.assertEqual(gatemarks.push_rec(out["asked"][0])["note"], REC["note"])
        self.assertEqual((out["go"], out["pushed"]["text"]), (True, REC["note"]))

    def test_no_recommend_stops_without_making_a_push(self):
        """推しの無い行が 1 つでも在れば止まる（実の利用者の run ac9e02ab。機械は推しを作らず、答えの下書きは報告が組む）"""
        for marks in ([{}], [{gatemarks.RECOMMEND: REC}, {}], [{gatemarks.RECOMMEND: {**REC, "answer": "stop"}}]):
            with self.subTest(marks=marks):
                out = self.ask(marks)
                self.assertEqual((out["go"], out["stop_reason"], out["pushed"]), (False, stopby.NEEDS_HUMAN, None))


if __name__ == "__main__":
    unittest.main()

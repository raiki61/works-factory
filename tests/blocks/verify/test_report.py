"""判定の裏取りの報告の行（src/report.py。docs/design/verify.md の 5 節）。今の lib/tests/test_runreport.py の裏取りの部分から写した。"""
import unittest

from tests.blocks import kit

HEAD = "判定の単位の裏取り（{n} 単位。単位は消していない。減らすなら承認ノードか再審で）:"


def checked(key, **over):
    return {"key": key, "state": "checked", "verdict": "root", "evidence_found": True, "evidence": "e", "location_ok": True,
            "location": "l", "why": "w", **over}


GOOD_SYNERGY = {"state": "checked", "why": "w", "duplicates": [], "relations": [], "order": []}


class ReportCase(unittest.TestCase):
    def setUp(self):
        self.lines = kit.load("verify", "report").lines

    def doc(self, units, synergy=GOOD_SYNERGY):
        return {"units": units, "synergy": synergy}

    def test_all_good_is_one_line(self):
        self.assertEqual(self.lines(self.doc([checked("u1"), checked("u2")]), True),
                         ["判定の単位の裏取り: 2 単位とも根本・証拠・場所が合った（重複・順番の名指しなし）"])

    def test_each_finding_has_its_line(self):
        units = [checked("u1", verdict="not_root", real_root="b.py。呼び手の側", why="呼び手が根"),
                 checked("u2", verdict="unsure", why="決められない"), checked("u3", evidence_found=False, evidence="無かった"),
                 checked("u4", location_ok=False, location="c.py:3"),
                 {"key": "u5", "state": "unverified", "errors": ["答えのファイルが無い（x）", "二つ目"]}]
        got = self.lines(self.doc(units), True)
        self.assertEqual(got[0], HEAD.format(n=5))
        self.assertEqual(got[1:], ["  - 根本でない: u1（本当の根: b.py。呼び手の側。呼び手が根）",
                                   "  - 根本か決められない: u2（決められない）", "  - 証拠が無い: u3（無かった）",
                                   "  - 場所が違う: u4（正しい場所: c.py:3）",
                                   "  - 確かめられなかった: u5（答えのファイルが無い（x）・二つ目）"])

    def test_synergy_lines(self):
        syn = {**GOOD_SYNERGY, "duplicates": [{"units": ["u1", "u2"], "why": "同じ根"}],
               "relations": [{"units": ["u1", "u2"], "why": "触る", "place": "same"}],
               "order": [{"first": "u1", "then": "u2", "why": "先に直す"}]}
        got = self.lines(self.doc([checked("u1"), checked("u2")], syn), True)
        self.assertEqual(got, [HEAD.format(n=2), "  - 重複: u1・u2（同じ根）", "  - 順番: u1 → u2（先に直す）"])

    def test_unverified_synergy(self):
        got = self.lines(self.doc([checked("u1")], {"state": "unverified", "errors": ["x"]}), True)
        self.assertEqual(got, [HEAD.format(n=1), "  - 単位どうしの相乗りは確かめられなかった"])

    def test_not_run_line_carries_the_reason(self):
        doc = {"units": [], "synergy": {"state": "unverified", "errors": ["開いた単位が 1 つ", "二つ目"]}}
        self.assertEqual(self.lines(doc, False), ["判定の単位の裏取り: 回さなかった（開いた単位が 1 つ・二つ目）"])


if __name__ == "__main__":
    unittest.main()

"""機械の報告（.shared/core/report.py・darkfactory/scripts/report.py・dev/report.sh）の検査（P1 計画 Task 27・〔線A計〕T15）。

盤面は線 A の試験と同じ組み方（linekit の種で start → 見本の返答を entry.take で進める。役の返答の前に起こした印）で、道ごとに作る。
全部の道（修正 → 差分の審査 → 手直し → 2 回目の審査 → 最後のテスト → 周の締め）は test_blk_refix の DeltaBoardCase の
手順を続け、p4.ci は宣言（.review-checks.json）を engine が走らせる（entry.run_ci）。
最後の関所の答え・止めた口（P1 Task 26 の境の節が書く）は、その Task の名前（final-gate-answer.json・human:final-gate）で
盤面に置いて見る。版の一覧の行（Task 18・19）はこの枝に無いので試験も無い。
"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import report  # noqa: E402


TDD_RAN = {"ran": True, "suite": "tests/run.sh", "reason": "", "test_cmd": {"gate": "off", "note": ""}, "calls": [],
           "units": [{"unit_key": "u-green", "route": "tdd", "why": "", "tests": ["t.py::test_a"], "red": "ok", "green": "ok",
                      "refactor": "none", "gave_up": ""},
                     {"unit_key": "u-gave", "route": "direct", "why": "赤が error で落ちた", "tests": [], "red": "", "green": "",
                      "refactor": "", "gave_up": "test"},
                     {"unit_key": "u-direct", "route": "direct", "why": "文書だけの直し", "tests": [], "red": "", "green": "",
                      "refactor": "", "gave_up": ""},
                     {"unit_key": "u-parked", "route": "parked", "why": "依頼とテストが食い違う", "tests": [], "red": "",
                      "green": "", "refactor": "", "gave_up": ""}]}
TDD_OFF = {"ran": False, "suite": "", "reason": "テストの実行器（入力 tdd_suite）が無い", "units": []}


class TddLinesCase(unittest.TestCase):
    """keep-essence の 11: TDD の輪の単位ごとの結末を報告の行にする（report.tdd_lines）"""

    def test_each_unit_gets_its_outcome(self):
        rows = report.tdd_lines([(report.TDD_STAGES[0], TDD_RAN)])
        self.assertIn("4 単位", rows[0])
        self.assertTrue(rows[0].startswith(report.TDD_STAGES[0]))
        body = "\n".join(rows[1:])
        for key in ("u-green", "u-gave", "u-direct", "u-parked"):
            self.assertEqual(sum(key in r for r in rows[1:]), 1, key)
        self.assertIn("t.py::test_a", body)
        self.assertIn("赤が error で落ちた", body)
        self.assertIn("依頼とテストが食い違う", body)
        self.assertTrue(all(r.startswith("  - ") for r in rows[1:]))

    def test_stage_line_names_reused_source(self):
        """出口 tdd に reused（元の結末と test_cmd の句）が在れば、段の行に『控えから使った結果』とその句が出る。無ければ出ない"""
        suite = "run run-a・2026-10-10T09:00:00+09:00・鍵 0123456789ab"
        test_cmd = "run run-a・2026-10-10T09:05:00+09:00・鍵 ba9876543210"
        rows = report.tdd_lines([(report.TDD_STAGES[0], {**TDD_RAN, "reused": {"suite": suite, "test_cmd": test_cmd}})])
        self.assertIn("控えから使った結果", rows[0])
        self.assertIn(suite, rows[0])
        self.assertIn(test_cmd, rows[0])
        self.assertNotIn("控えから使った結果", report.tdd_lines([(report.TDD_STAGES[0], TDD_RAN)])[0])

    def test_tdd_unit_shows_red_quotes_stub_files_and_unchecked(self):
        """人が報告で赤の理由の正しさを見るため、単位の行に名指しごとの引用と理由・仮の実装のファイル・引用を照らせなかった
        名指しが載る（1 単位 1 行のまま）"""
        unit = {"unit_key": "u-green", "route": "tdd", "why": "", "tests": ["t.py::test_a", "t.py::test_b"], "red": "ok", "green": "ok",
                "refactor": "none", "gave_up": "",
                "red_quotes": {"t.py::test_a": {"quote": "AssertionError: 6.0 != 3", "why": "分母を 1 つ少なく割るので期待どおりに落ちる"}},
                "stub_files": ["stats.py"], "quote_unchecked": ["t.py::test_b"]}
        rows = report.tdd_lines([(report.TDD_STAGES[0], {**TDD_RAN, "units": [unit]})])
        self.assertEqual(len(rows), 2, rows)
        for w in ("t.py::test_a", "AssertionError: 6.0 != 3", "分母を 1 つ少なく割るので期待どおりに落ちる", "stats.py", "t.py::test_b"):
            self.assertIn(w, rows[1])
        plain = report.tdd_lines([(report.TDD_STAGES[0], {**TDD_RAN, "units": [TDD_RAN["units"][0]]})])
        self.assertNotIn("赤の引用", plain[1], "引用の無い単位の行は今どおり")

    def test_stage_without_loop_says_why(self):
        rows = report.tdd_lines([(report.TDD_STAGES[0], TDD_OFF)])
        self.assertEqual(len(rows), 1)
        self.assertIn("回していない", rows[0])
        self.assertIn(TDD_OFF["reason"], rows[0])

    def test_head_names_stages_without_freeze(self):
        """keep-essence の 3: TDD の輪を回していない修正の段は、テストの凍結が効いていないと冒頭 2 の行で理由つきで言う（黙らない）"""
        rows = report.freeze_lines([(report.TDD_STAGES[0], TDD_OFF), (report.TDD_STAGES[1], None)])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].startswith(report.FREEZE_OFF_HEAD), rows)
        self.assertIn(report.TDD_STAGES[0], rows[0])
        self.assertIn(TDD_OFF["reason"], rows[0])
        self.assertEqual(report.freeze_lines([(report.TDD_STAGES[0], TDD_RAN), (report.TDD_STAGES[1], None)]), [])
        self.assertEqual(report.freeze_lines([]), [])

    def test_stages_that_did_not_run_are_left_out(self):
        self.assertEqual(report.tdd_lines([(report.TDD_STAGES[0], None), (report.TDD_STAGES[1], None)]), [])
        self.assertEqual(len(report.tdd_lines([(report.TDD_STAGES[0], None), (report.TDD_STAGES[1], TDD_OFF)])), 1)


if __name__ == "__main__":
    unittest.main()

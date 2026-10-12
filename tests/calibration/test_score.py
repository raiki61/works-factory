"""score（後の走り手が 1 行の run の結果を数える口）の試験。合成の observed だけで回す。"""
import unittest

from tests.calibration.corpus import score

DEFECT = {"id": "load-tested-only-with-stand-in", "kind": "stand-in-diverges", "catcher": "p1.test_double_fidelity",
          "also": ["p1.gate_efficacy"], "outcome": "fixed"}
CONTROL = {"id": "control-clearer-names", "kind": "none", "catcher": None, "outcome": "no_fix_needed"}
UNREACHED = ("record_invalid", "interrupted", "stopped_by_request", "stopped_by_human", "stopped_by_line")


def observed(row, outcome, flagged, **over):
    return {"id": row["id"], "factory": "works-factory", "run_id": "run-1", "outcome": outcome, "flagged": flagged,
            **over}


class TestScore(unittest.TestCase):
    def test_score_caught_by_aim(self):
        got = score(DEFECT, observed(DEFECT, "fixed", ["p1.test_double_fidelity", "p1.hygiene"]))
        self.assertEqual(got["id"], DEFECT["id"])
        self.assertEqual(got["verdict"], "CAUGHT")
        self.assertTrue(got["aimed_hit"])
        self.assertEqual(got["caught_by"], ["p1.test_double_fidelity"])
        self.assertEqual(got["missed_by"], ["p1.gate_efficacy"])
        self.assertTrue(got["outcome_as_expected"])

    def test_score_caught_by_also_marks_aim_missed(self):
        got = score(DEFECT, observed(DEFECT, "fixed", ["p1.gate_efficacy"]))
        self.assertEqual(got["verdict"], "CAUGHT")
        self.assertFalse(got["aimed_hit"])
        self.assertEqual(got["caught_by"], ["p1.gate_efficacy"])
        self.assertEqual(got["missed_by"], ["p1.test_double_fidelity"])

    def test_score_escaped(self):
        got = score(DEFECT, observed(DEFECT, "no_fix_needed", ["p1.hygiene"]))
        self.assertEqual(got["verdict"], "ESCAPED")
        self.assertFalse(got["aimed_hit"])
        self.assertEqual(got["caught_by"], [])
        self.assertEqual(got["missed_by"], ["p1.test_double_fidelity", "p1.gate_efficacy"])
        self.assertFalse(got["outcome_as_expected"])

    def test_score_inconclusive_on_unreached_outcomes(self):
        for outcome in UNREACHED:
            with self.subTest(outcome=outcome):
                got = score(DEFECT, observed(DEFECT, outcome, ["p1.test_double_fidelity"]))
                self.assertEqual(got["verdict"], "INCONCLUSIVE")
                self.assertEqual(got["missed_by"], [])
                self.assertIn(outcome, got["detail"])
                control = score(CONTROL, observed(CONTROL, outcome, []))
                self.assertEqual(control["verdict"], "INCONCLUSIVE")
        unknown = score(DEFECT, observed(DEFECT, "done", ["p1.test_double_fidelity"]))
        self.assertEqual(unknown["verdict"], "INCONCLUSIVE")
        self.assertEqual(unknown["missed_by"], [])
        self.assertIn("done", unknown["detail"])

    def test_score_control_clean(self):
        got = score(CONTROL, observed(CONTROL, "no_fix_needed", []))
        self.assertEqual(got["verdict"], "CLEAN")
        self.assertTrue(got["outcome_as_expected"])
        self.assertEqual(got["caught_by"], [])
        self.assertEqual(got["missed_by"], [])

    def test_score_control_false_alarm(self):
        got = score(CONTROL, observed(CONTROL, "fixed", ["r1.minimality"]))
        self.assertEqual(got["verdict"], "FALSE_ALARM")
        self.assertFalse(got["outcome_as_expected"])
        self.assertIn("r1.minimality", got["detail"])
        quiet = score(CONTROL, observed(CONTROL, "fixed", []))
        self.assertEqual(quiet["verdict"], "FALSE_ALARM")
        self.assertFalse(quiet["outcome_as_expected"])

    def test_score_reports_outcome_mismatch_separately(self):
        got = score(DEFECT, observed(DEFECT, "needs_human", ["p1.test_double_fidelity"]))
        self.assertEqual(got["verdict"], "CAUGHT")
        self.assertFalse(got["outcome_as_expected"])

    def test_score_malformed_observed_is_inconclusive(self):
        cases = {
            "欄の欠け": {k: v for k, v in observed(DEFECT, "fixed", []).items() if k != "flagged"},
            "id の違い": observed(DEFECT, "fixed", ["p1.test_double_fidelity"], id="other-row"),
            "flagged が並びでない": observed(DEFECT, "fixed", "p1.test_double_fidelity"),
            "factory が知らない語": observed(DEFECT, "fixed", ["p1.test_double_fidelity"], factory="elsewhere"),
            "dict でない": ["fixed"],
        }
        for name, obs in cases.items():
            with self.subTest(case=name):
                got = score(DEFECT, obs)
                self.assertEqual(got["verdict"], "INCONCLUSIVE")
                self.assertFalse(got["aimed_hit"])
                self.assertEqual(got["caught_by"], [])
                self.assertEqual(got["missed_by"], [])
                self.assertFalse(got["outcome_as_expected"])
                self.assertTrue(got["detail"])


if __name__ == "__main__":
    unittest.main()

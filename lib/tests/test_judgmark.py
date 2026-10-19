"""判定の出力の行の形（lib/judgmark.py）。開いた単位の選びだけを見る。"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import judgmark  # noqa: E402


def unit(key, label="block", disposition=None):
    return {"key": key, "label": label, **({"disposition": disposition} if disposition else {})}


class IsOpenCase(unittest.TestCase):
    def test_block_and_do_now_suggest_are_open(self):
        self.assertTrue(judgmark.is_open({"label": "block"}))
        self.assertTrue(judgmark.is_open({"label": "suggest", "disposition": "do-now"}))

    def test_deferred_suggest_and_other_labels_are_closed(self):
        self.assertFalse(judgmark.is_open({"label": "suggest", "disposition": "defer"}))
        self.assertFalse(judgmark.is_open({"label": "suggest"}))
        for label in ("nit", "question", "info"):
            self.assertFalse(judgmark.is_open({"label": label, "disposition": "do-now"}))

    def test_unit_without_label_or_not_a_dict_is_closed(self):
        self.assertFalse(judgmark.is_open({"key": "k"}))
        self.assertFalse(judgmark.is_open("block"))
        self.assertFalse(judgmark.is_open(None))


class OpenUnitsCase(unittest.TestCase):
    def test_keeps_judgment_order_and_skips_rows_without_a_string_key(self):
        doc = {"units": [{"key": "a", "label": "block"}, {"key": "b", "label": "nit"}, {"label": "block"},
                         {"key": 3, "label": "block"}, "x", {"key": "c", "label": "suggest", "disposition": "do-now"}]}
        self.assertEqual([u["key"] for u in judgmark.open_units(doc)], ["a", "c"])

    def test_missing_or_malformed_units_give_nothing(self):
        for doc in (None, [], {}, {"units": None}, {"units": "x"}):
            self.assertEqual(judgmark.open_units(doc), [])


class OwedCase(unittest.TestCase):
    """直す義務と計画の周が役を起こすかの決め（plan の周を開く口と line の node owed が共に引く 1 か所）"""

    def test_slots_and_plan_slots_follow_the_judgment_order(self):
        doc = {"units": [unit("a"), unit("n", "nit"), unit("b", "suggest", "do-now"), unit("d", "suggest", "defer")], "questions": []}
        self.assertEqual(judgmark.slots(doc), ["a", "b"])
        owed, opened, units = judgmark.plan_slots(doc)
        self.assertEqual((owed, opened, list(units)), ({"a", "b"}, {"a", "b"}, ["a", "n", "b", "d"]))

    def test_nothing_owed_and_unreadable_hold_the_round(self):
        self.assertEqual(judgmark.held_why(None), "判定が読めない")
        self.assertEqual(judgmark.held_why({"units": [unit("n", "nit")], "questions": []}), judgmark.NOTHING_OWED)

    def test_owed_and_open_units_hold_nothing(self):
        self.assertEqual(judgmark.held_why({"units": [unit("a")], "questions": []}), "")

    def test_owed_unit_that_is_not_open_is_a_dead_end_naming_no_and_key(self):
        doc = {"units": [unit("a"), unit("d", "suggest", "defer")], "questions": []}
        orig = judgmark.owed_units
        judgmark.owed_units = lambda judgment: {"a", "d", "ghost"}
        try:
            why = judgmark.plan_stuck_reason(doc)
            self.assertEqual(judgmark.held_why(doc), why)
        finally:
            judgmark.owed_units = orig
        self.assertTrue(why.startswith(judgmark.PLAN_STUCK), why)
        self.assertIn("no の一覧に無い単位（d）", why)
        self.assertIn("no の一覧に無い単位（ghost）", why)
        self.assertTrue(why.endswith(judgmark.STUCK_WHY), why)

    def test_with_ledger_adds_the_ledger_view_without_changing_the_judgment(self):
        import gatemarks
        doc = {"units": [unit("a")], "questions": []}
        got = judgmark.with_ledger(doc, answers=[{"question": "q", "text": "t"}, "x"], takes_push=True)
        self.assertNotIn(judgmark.LEDGER, doc)
        self.assertIsInstance(got[judgmark.LEDGER], gatemarks.Ledger)
        self.assertEqual(judgmark.owed_units(got), {"a"})
        self.assertIsNone(judgmark.with_ledger(None))


if __name__ == "__main__":
    unittest.main()

"""共通の形 judgment.schema.json（受け付けた判定）と prior-failures.schema.json の試験。判定を読む block（plan・verify・fix ほか）が
同じ形で受ける。verify が持っていた block ごとの形（下の VERIFY_SCHEMA）が通す判定は、共通の形も全部通す。"""
import json
import unittest

from tests.blocks.diagnose import support
from tests.blocks.diagnose.support import judge_ok

VERIFY_SCHEMA = {"type": "object", "required": ["units"],
                 "properties": {"framing": {"type": "string"}, "one_shot": {"type": "string"},
                                "units": {"type": "array", "items": {"type": "object", "required": ["key", "label"],
                                                                     "properties": {"key": {"type": "string", "minLength": 1},
                                                                                    "label": {"type": "string"},
                                                                                    "disposition": {"type": "string"}}}}}}


class _Base(unittest.TestCase):
    def setUp(self):
        support.modules()
        import ports
        from engine.schema import validate_schema
        self.ports, self.validate = ports, validate_schema

    def shared_accepts(self, value, name="judgment.schema.json"):
        try:
            self.ports.json(json.dumps(value), f"shared:{name}")
            return True
        except ValueError:
            return False

    def verify_accepts(self, value):
        return not self.validate(value, VERIFY_SCHEMA)


class JudgmentSchemaCase(_Base):
    GOOD = [
        {"units": []},
        {"units": [], "questions": [], "framing": "", "one_shot": "", "materials_missing": [], "carried_r1": [], "one_shot_closes": [],
         "precedents": []},
        {"framing": "根は 1 つ", "one_shot": "直す", "units": [
            {"key": "k", "label": "block", "disposition": "do-now", "reason": "r", "origin_analysis": "①ロジック",
             "why_chain": ["a", "b"], "prescriptions": ["零処方: x"], "class_query": {"how": {}}}]},
        {"units": [{"key": "k", "label": "weird-new-label"}], "extra": {"anything": 1}},
        {"units": [{"key": "k", "label": "info"}], "questions": [{"key": "q", "kind": "field", "status": "held", "reason": "r"}]},
    ]
    BAD = [
        {},
        {"units": [{"label": "block"}]},
        {"units": [{"key": "", "label": "block"}]},
        {"units": "x"},
        {"units": [], "questions": ["q"]},
        {"units": [{"key": "k", "label": "block", "prescriptions": "x"}]},
    ]
    # verify の block ごとの形は通すが、plan の置いた共通の形は通さない判定（型の崩れ・label 無し）。diagnose が書く判定には無い
    VERIFY_ONLY = [
        {"units": [{"key": "k", "label": "block", "prescriptions": "x"}]},
        {"units": [], "questions": ["q"]},
    ]

    def test_good_judgments_pass(self):
        for value in self.GOOD:
            with self.subTest(value):
                self.assertTrue(self.shared_accepts(value))

    def test_bad_judgments_fail(self):
        for value in self.BAD:
            with self.subTest(value):
                self.assertFalse(self.shared_accepts(value))

    def test_verify_accepted_judgments_the_block_can_write_pass(self):
        """verify の block ごとの形が通す判定のうち、diagnose が書ける物（型が保たれた物）は共通の形も通す。通らない差は VERIFY_ONLY"""
        for value in [*self.GOOD, *self.BAD]:
            with self.subTest(value):
                if self.verify_accepts(value) and value not in self.VERIFY_ONLY:
                    self.assertTrue(self.shared_accepts(value))

    def test_the_known_difference_with_verify(self):
        for value in self.VERIFY_ONLY:
            self.assertTrue(self.verify_accepts(value))
            self.assertFalse(self.shared_accepts(value))
        self.assertTrue(self.shared_accepts({"units": [{"key": "k"}]}), "共通の形は label を要らない（verify の is_open は label を直に引く）")

    def test_what_the_block_writes_passes(self):
        mod = support.modules()
        self.assertTrue(self.shared_accepts(mod["exit"].EMPTY_JUDGMENT))
        self.assertTrue(self.shared_accepts(judge_ok()))


class PriorFailuresSchemaCase(_Base):
    def test_rows(self):
        name = "prior-failures.schema.json"
        self.assertTrue(self.shared_accepts([], name))
        self.assertTrue(self.shared_accepts([{"where": "受け付け", "text": "t", "extra": 1}], name))
        for bad in ({}, [{"where": "w"}], [{"where": 1, "text": "t"}], ["x"]):
            with self.subTest(bad):
                self.assertFalse(self.shared_accepts(bad, name))

"""engine の型検査（lib/graphloops/engine/schema.py）の allOf・if・then・not（JSON Schema 2020-12 の意味。else は使い手が無いので持たない）と、
知る語の集合 KNOWN_KEYWORDS に入っていること。使い手は書き手の返答の形 writer-reply.schema.json の precedent の 3 つの条件"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
for p in (LIB, LIB / "graphloops"):
    if str(p) not in sys.path:
        sys.path.append(str(p))
from engine import schema  # noqa: E402

NEEDS_A = {"required": ["a"], "properties": {"a": {"type": "string", "minLength": 2}}}


class CombinatorCase(unittest.TestCase):
    def test_the_four_words_are_known(self):
        self.assertLessEqual({"allOf", "if", "then", "not"}, schema.KNOWN_KEYWORDS)
        self.assertNotIn("else", schema.KNOWN_KEYWORDS)

    def test_all_of_is_the_union_of_the_errors_of_every_part(self):
        shape = {"type": "object", "allOf": [{"required": ["a"]}, {"required": ["b"]}]}
        self.assertEqual(schema.validate_schema({"a": 1, "b": 2}, shape), [])
        self.assertEqual(len(schema.validate_schema({}, shape)), 2)
        self.assertEqual(len(schema.validate_schema({"a": 1}, shape)), 1)

    def test_then_applies_only_when_if_passes(self):
        shape = {"type": "object", "if": {"required": ["kind"], "properties": {"kind": {"const": "x"}}}, "then": NEEDS_A}
        self.assertEqual(schema.validate_schema({"kind": "x", "a": "ab"}, shape), [])
        self.assertTrue(schema.validate_schema({"kind": "x"}, shape))
        self.assertTrue(schema.validate_schema({"kind": "x", "a": "b"}, shape))
        self.assertEqual(schema.validate_schema({"kind": "y"}, shape), [], "if が通らなければ then を当てない")
        self.assertEqual(schema.validate_schema({}, shape), [])

    def test_an_if_without_then_does_nothing(self):
        shape = {"type": "object", "if": {"required": ["a"]}}
        self.assertEqual(schema.validate_schema({"a": 1}, shape), [])
        self.assertEqual(schema.validate_schema({}, shape), [])

    def test_not_is_one_error_when_the_part_passes(self):
        shape = {"type": "object", "not": {"required": ["a"], "properties": {"a": {"const": True}}}}
        self.assertEqual(len(schema.validate_schema({"a": True}, shape)), 1)
        self.assertEqual(schema.validate_schema({"a": False}, shape), [])
        self.assertEqual(schema.validate_schema({}, shape), [])

    def test_the_parts_nest_under_properties_with_the_path(self):
        shape = {"type": "object", "properties": {"p": {"type": "object", "allOf": [{"required": ["a"]}]}}}
        self.assertIn("$.p", schema.validate_schema({"p": {}}, shape)[0])

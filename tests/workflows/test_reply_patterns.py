"""役の返答の字の欄の、前後の空白を除いた長さの下限を持つ pattern（tests/bin/trimmed.py）が、Ajv と同じ当て方（RegExp の test。
ここでは re.search）で空白だけ・空白で水増しした字を外し、普通の字を通す事を見る（FAST。YAML・プロセスなし）"""
import unittest

from tests.bin import trimmed


class TrimmedPatternCase(unittest.TestCase):
    def test_min_length_one_needs_a_visible_character(self):
        p = trimmed.trimmed_pattern(1)
        for bad in ("", " ", "\t\n", "　"):
            with self.subTest(bad=bad):
                self.assertFalse(trimmed.matches(p, bad))
        for good in ("a", "  a  ", "改行の\n後"):
            with self.subTest(good=good):
                self.assertTrue(trimmed.matches(p, good))

    def test_min_length_n_counts_without_the_outer_spaces(self):
        for n in (2, 4, 8, 20):
            p = trimmed.trimmed_pattern(n)
            with self.subTest(n=n):
                self.assertTrue(trimmed.matches(p, "x" * n))
                self.assertTrue(trimmed.matches(p, "x" + " " * (n - 2) + "x"), "内側の空白は数える")
                self.assertFalse(trimmed.matches(p, "x" * (n - 1)))
                self.assertFalse(trimmed.matches(p, "  " + "x" * (n - 1) + "  "), "前後の空白で水増しした字")
                self.assertFalse(trimmed.matches(p, " " * (n + 4)))

    def test_one_line_field_needs_a_visible_character_and_no_line_break(self):
        for bad in ("", "  ", "a\nb", "a\rb", "a\x00", " \t "):
            with self.subTest(bad=bad):
                self.assertFalse(trimmed.matches(trimmed.LINE, bad))
        for good in ("a", " def foo", "x = 1  "):
            with self.subTest(good=good):
                self.assertTrue(trimmed.matches(trimmed.LINE, good))

    def test_missing_patterns_names_the_bare_min_length(self):
        schema = {"type": "object", "properties": {
            "a": {"type": "string", "minLength": 4, "pattern": trimmed.trimmed_pattern(4)},
            "b": {"type": "string", "minLength": 4},
            "c": {"type": "array", "items": {"type": ["integer", "string"], "minLength": 1}},
            "d": {"type": "string", "minLength": 1, "pattern": trimmed.LINE}}}
        self.assertEqual(trimmed.missing_patterns(schema), [("/properties/b", None), ("/properties/c/items", None)])
        self.assertEqual(trimmed.without_trimmed(schema)["properties"]["a"], {"type": "string", "minLength": 4})


if __name__ == "__main__":
    unittest.main()

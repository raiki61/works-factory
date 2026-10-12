"""人が関所に答える行（answer.head・answer.line）の検査。env を直に渡す純な関数だけ。"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import answer  # noqa: E402


class HeadCase(unittest.TestCase):
    def test_without_env_is_the_hole(self):
        self.assertEqual(answer.head(env={}), answer.HOLE)

    def test_env_head_is_stripped(self):
        self.assertEqual(answer.head(env={answer.ENV: "  sh x  "}), "sh x")


class LineCase(unittest.TestCase):
    def test_line(self):
        self.assertEqual(answer.line("r", "continue", "n", env={answer.ENV: "H"}), 'H r continue "n"')

    def test_who_is_appended(self):
        got = answer.line("r", "stop", "n", env={answer.ENV: "H", answer.WHO_ENV: "w"})
        self.assertEqual(got, 'H r stop "n" "w"')

    def test_blank_who_adds_nothing(self):
        self.assertEqual(answer.line("r", "continue", "n", env={answer.ENV: "H", answer.WHO_ENV: "  "}),
                         'H r continue "n"')

    def test_unknown_verb_raises(self):
        with self.assertRaises(ValueError):
            answer.line("r", "maybe", "n", env={answer.ENV: "H"})


if __name__ == "__main__":
    unittest.main()

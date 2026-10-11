"""関所の答えの行（lib/answer.py）。起動の殻が置く頭で打てる行になる事と、殻の外の穴の字（FAST）"""
import pathlib
import shlex
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import answer  # noqa: E402

SHELL = "/opt/works factory/bin/works-factory"
TARGET = "/home/me/my repo"


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

    def test_shell_head_makes_a_typeable_respond(self):
        env = {answer.ENV: shlex.join([SHELL, "workflow", "respond", "--cwd", TARGET])}
        self.assertEqual(shlex.split(answer.line("run-1", "continue", "x", env=env)),
                         [SHELL, "workflow", "respond", "--cwd", TARGET, "run-1", "continue", "x"])

    def test_outside_the_shell_the_head_is_the_hole(self):
        self.assertEqual(answer.head(env={}), answer.HOLE)
        self.assertTrue(answer.line("run-1", "stop", "x", env={}).startswith(answer.HOLE + " "))
        self.assertIn("bin/works-factory workflow respond --cwd", answer.HOLE)
        self.assertNotIn("use.sh", answer.HOLE)


if __name__ == "__main__":
    unittest.main()

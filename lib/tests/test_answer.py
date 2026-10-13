"""関所の答えの行（lib/answer.py）。起動の殻が置く頭で打てる行になる事と、殻の外の穴の字（FAST）"""
import pathlib
import re
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

    def test_nothing_follows_the_note(self):
        """実行基盤の respond は一言の後ろを一言に繋ぐので、答えた者などを末尾に足さない（利用者の env に昔の名が在っても）"""
        self.assertEqual(answer.line("r", "stop", "n", env={answer.ENV: "H", "WORKS_ANSWER_WHO": "w"}), 'H r stop "n"')

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


class GoWordsOwner(unittest.TestCase):
    """関所を通す語の並びを宣言するのは answer.GO_WORDS の 1 か所（#392。ほかは引く。写すと語を足した時に片方だけ変わる）"""
    TUPLE = re.compile(r"""\(\s*["'](approve|continue)["']\s*,\s*(["'](approve|continue)["']|(answer\.)?VERBS\[0\])\s*\)""")

    def test_declared_once_in_lib(self):
        found = sorted(str(f.relative_to(LIB)) for f in LIB.rglob("*.py")
                       if "tests" not in f.relative_to(LIB).parts and self.TUPLE.search(f.read_text(encoding="utf-8")))
        self.assertEqual(found, ["answer.py"])

    def test_pattern_sees_a_second_copy(self):
        for copy in ('PASS = ("continue", "approve")', "GATE_GO = ('approve', VERBS[0])"):
            with self.subTest(copy=copy):
                self.assertTrue(self.TUPLE.search(copy))


class StopWordsOwner(unittest.TestCase):
    """関所を止める語の並びを宣言するのは answer.STOP_WORDS の 1 か所（通す語の GoWordsOwner と同じ訳）"""
    WORD = r"""(["'](stop|reject)["']|(answer\.)?VERBS\[1\]|(answer\.)?REJECT)"""
    TUPLE = re.compile(rf"""\(\s*{WORD}\s*,\s*{WORD}\s*\)""")

    def test_declared_once_in_lib(self):
        found = sorted(str(f.relative_to(LIB)) for f in LIB.rglob("*.py")
                       if "tests" not in f.relative_to(LIB).parts and self.TUPLE.search(f.read_text(encoding="utf-8")))
        self.assertEqual(found, ["answer.py"])

    def test_pattern_sees_a_second_copy(self):
        for copy in ('STOPS = (VERBS[1], "reject")', "GATE_STOP = ('stop', 'reject')", "STOPS = (VERBS[1], REJECT)",
                     'STOPS = ("reject", "stop")', "STOPS = (answer.VERBS[1], answer.REJECT)"):
            with self.subTest(copy=copy):
                self.assertTrue(self.TUPLE.search(copy))


if __name__ == "__main__":
    unittest.main()

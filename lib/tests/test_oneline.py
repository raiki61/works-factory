"""1 行に畳む口（lib/oneline）の畳み方"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import oneline  # noqa: E402

class OneLineCase(unittest.TestCase):
    def test_folds_every_run_of_whitespace_into_one_space(self):
        self.assertEqual(oneline.one_line("a\n b\t\tc  "), "a b c")
        self.assertEqual(oneline.one_line(ValueError("x\ny")), "x y")

if __name__ == "__main__":
    unittest.main()

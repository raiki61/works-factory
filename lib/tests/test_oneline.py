"""1 行に畳む口（lib/oneline）。畳み方と、lib に同じ中身の写しが育ち直さないこと（FAST。lib の字を読むだけ）"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import oneline  # noqa: E402

# 振る舞いの違う畳みを持ち主に残すモジュール: 色の制御文字を除く・NFKC に揃える cite と、lib を読まない単独の script の measure、
# 殻も読むので標準ライブラリだけで書く spseam
OWN_FOLDS = {"oneline.py", "cite.py", "measure.py", "spseam.py"}


class OneLineCase(unittest.TestCase):
    def test_folds_every_run_of_whitespace_into_one_space(self):
        self.assertEqual(oneline.one_line("a\n b\t\tc  "), "a b c")
        self.assertEqual(oneline.one_line(ValueError("x\ny")), "x y")

    def test_lib_has_no_copy_of_the_fold(self):
        copies = [f"{p.name}:{n}" for p in sorted(LIB.glob("*.py")) if p.name not in OWN_FOLDS
                  for n, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
                  if ('" ".join(' in ln or "' '.join(" in ln) and ".split())" in ln]
        self.assertEqual(copies, [], "1 行に畳む写しは oneline.one_line を引く")


if __name__ == "__main__":
    unittest.main()

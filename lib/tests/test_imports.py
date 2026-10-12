"""lib の各モジュールを、新しい interpreter で最初に読んでも落ちない（落とし穴 K8 の循環 import の半分）。

読み込みの時に相手の名を引く 2 つのモジュールが互いを import すると、先に読んだ方によって AttributeError か ImportError で落ちる
（PR #76: judgeverify を先に読むと judge_accept が落ちた）。lib/*.py を 1 本ずつ、lib だけを sys.path に足した新しい子のプロセスで
最初に import し、終了の値が 0 であることを見る。どの順で読まれても落ちない。
"""
import pathlib
import subprocess
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]


def first_import_failures(lib: pathlib.Path) -> dict[str, str]:
    """lib の .py ごとに、新しい interpreter で最初に import して落ちたモジュールの名 -> 標準エラーの最後の行"""
    failures = {}
    with tempfile.TemporaryDirectory() as cwd:
        for path in sorted(lib.glob("*.py")):
            if path.stem == "__init__":
                continue
            code = f"import sys; sys.dont_write_bytecode = True; sys.path.append({str(lib)!r}); import {path.stem}"
            done = subprocess.run([sys.executable, "-B", "-c", code], cwd=cwd, stdin=subprocess.DEVNULL,
                                  capture_output=True, text=True, encoding="utf-8")
            if done.returncode != 0:
                failures[path.stem] = (done.stderr.strip().splitlines() or [f"終了の値 {done.returncode}"])[-1]
    return failures


class LibImportCase(unittest.TestCase):
    def test_every_module_imports_first_in_a_fresh_interpreter(self):
        self.assertTrue(list(LIB.glob("*.py")), "lib/*.py が 1 本も無い")
        self.assertEqual(first_import_failures(LIB), {})

    def test_answer_imports_as_a_member_of_lib(self):
        """起動の殻（bin/_lib/launcher.py）は lib を sys.path に足さず from lib import answer で読む"""
        done = subprocess.run([sys.executable, "-I", "-B", "-c", "import sys; sys.path.insert(0, '.'); from lib import answer"],
                              cwd=LIB.parent, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_cycle_that_fails_by_order_is_named(self):
        """読み込みの時に相手の名を引く循環は、先に読んだ方の名で落ちる。循環の無い方は落ちない。"""
        with tempfile.TemporaryDirectory() as tmp:
            lib = pathlib.Path(tmp)
            (lib / "first.py").write_text("import second\nNAME = 'first.json'\nPAIR = second.NAME\n", encoding="utf-8")
            (lib / "second.py").write_text("import first\nNAME = 'second.json'\nPAIR = first.NAME\n", encoding="utf-8")
            (lib / "alone.py").write_text("NAME = 'alone.json'\n", encoding="utf-8")
            failures = first_import_failures(lib)
        self.assertEqual(sorted(failures), ["first", "second"])
        self.assertIn("AttributeError", failures["first"])


if __name__ == "__main__":
    unittest.main()

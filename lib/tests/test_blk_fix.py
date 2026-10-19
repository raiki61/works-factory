"""修正のブロック（blk-fix）の検査のうち、lib/ に残るモジュールを直に呼ぶ物（指示の組み立ての検査は fix の block の試験へ移った）。

- 後始末のモジュール leftovers は標準ライブラリだけを読む
"""
import ast
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


class TestLeftoversModule(unittest.TestCase):
    def test_leftovers_is_stdlib_only(self):
        """標準ライブラリと、何も import しない修正の名の住処 fixnames だけ（lib のほかのモジュールは読まない）"""
        def imported(module):
            tree = ast.parse((LIB / f"{module}.py").read_text(encoding="utf-8"))
            self.assertFalse(any(isinstance(n, ast.ImportFrom) and n.level for n in ast.walk(tree)))
            names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            return names | {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level == 0}
        names = imported("leftovers")
        self.assertTrue(names)
        self.assertEqual(sorted(names - set(sys.stdlib_module_names)), ["fixnames"])
        self.assertEqual(imported("fixnames"), set())


if __name__ == "__main__":
    unittest.main()

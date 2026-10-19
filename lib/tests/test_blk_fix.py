"""修正のブロック（blk-fix）の検査のうち、lib/ に残るモジュールを直に呼ぶ物（指示の組み立ての検査は fix の block の試験へ移った）。

- 後始末のモジュール leftovers は標準ライブラリだけを読む
"""
import ast
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


if __name__ == "__main__":
    unittest.main()

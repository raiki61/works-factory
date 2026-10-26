"""書き手の型の block tidy（workflows/weapon-tidy/）の試験。照らす事は tests/blocks/kit.py の WriterBlockCase に 1 か所（block の名を渡して継ぐだけ）"""
import unittest

from tests.blocks import kit


class TidyCase(kit.WriterBlockCase):
    block = "weapon-tidy"


if __name__ == "__main__":
    unittest.main()

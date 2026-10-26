"""書き手の型の block tdd-close（workflows/weapon-tdd-close/）の試験。照らす事は tests/blocks/kit.py の WriterBlockCase に 1 か所（block の名を渡して継ぐだけ）"""
import unittest

from tests.blocks import kit


class TddCloseCase(kit.WriterBlockCase):
    block = "weapon-tdd-close"


if __name__ == "__main__":
    unittest.main()

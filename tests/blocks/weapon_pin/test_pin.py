"""書き手の型の block pin（workflows/weapon-pin/）の試験。照らす事は tests/blocks/kit.py の WriterBlockCase に 1 か所（block の名を渡して継ぐだけ）"""
import unittest

from tests.blocks import kit


class PinCase(kit.WriterBlockCase):
    block = "weapon-pin"


if __name__ == "__main__":
    unittest.main()

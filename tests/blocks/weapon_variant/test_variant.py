"""書き手の型の block variant（workflows/weapon-variant/）の試験。照らす事は tests/blocks/kit.py の WriterBlockCase に 1 か所（block の名を渡して継ぐだけ）"""
import unittest

from tests.blocks import kit


class VariantCase(kit.WriterBlockCase):
    block = "weapon-variant"


if __name__ == "__main__":
    unittest.main()

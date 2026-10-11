"""lib/changemap.py と bin/_lib/changemap.py は同じ元（今の works の .shared/core/changemap.py）の写しで、同じバイトのまま持つ。

lib/ は bin/ を import できない（E3）ので、2 つのファイルをバイトで読み比べる。
"""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class SameBytesCase(unittest.TestCase):
    def test_lib_and_bin_copies_are_the_same_bytes(self):
        self.assertEqual((ROOT / "lib" / "changemap.py").read_bytes(), (ROOT / "bin" / "_lib" / "changemap.py").read_bytes())


if __name__ == "__main__":
    unittest.main()

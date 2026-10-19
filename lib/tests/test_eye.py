"""ブロックの時間の欄（lib/eye.py。integration.md 4.3-8・4.4-J）の試験。"""
import pathlib
import sys
import time
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import eye  # noqa: E402


class TimeFieldCase(unittest.TestCase):
    def test_stamp_then_wall(self):
        doc = {}
        eye.stamp(doc, time.monotonic() - 2, units=3)
        self.assertEqual(set(doc["timing"]), {"units", eye.WALL})
        self.assertGreaterEqual(eye.wall(doc), 2)
        self.assertEqual(eye.wall({eye.WALL: 1.5}), 1.5, "timing の無い控えはそのものを読む")
        self.assertEqual((eye.wall(None), eye.wall({}), eye.wall({"timing": {}})), (0, 0, 0))

    def test_only_the_time_field_is_left(self):
        self.assertEqual({n for n in vars(eye) if not n.startswith("_")} - {"time"}, {"WALL", "stamp", "wall"})

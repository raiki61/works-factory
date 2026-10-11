"""lib/seat.py（修正の役の座）が、起動の bin/_lib/spseam.py と同じ借りた物の置き場を読み、部品の型を同じ文に埋めることの試験。

lib/ は bin/ を import しない（lib/AGENTS.md の E3）ので、seat は置き場の読み口と型の埋め方を spseam と別に持つ。
"""
import pathlib
import sys
import unittest

from bin._lib import spseam

LIB = pathlib.Path(__file__).resolve().parents[2] / "lib"
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import seat  # noqa: E402
from lib.tests.test_seat import IMPL, REVIEW  # noqa: E402


class SeatBorrowCase(unittest.TestCase):
    def test_same_borrow_place_as_the_launcher(self):
        self.assertEqual(seat.BORROW_DIR, spseam.BORROW_DIR)
        self.assertEqual((seat.SEAMS_FILE, seat.OVERLAY_FILE, seat.BRACKETED.pattern),
                         (spseam.SEAMS_FILE, spseam.OVERLAY_FILE, spseam.BRACKETED.pattern))

    def test_fill_matches_the_launchers_fill(self):
        item, src = seat.pinned()
        for sid, values in (("implementer", IMPL), ("task-review", REVIEW)):
            self.assertEqual(seat.fill(sid, values), spseam.fill(sid, values, src, item), sid)


if __name__ == "__main__":
    unittest.main()

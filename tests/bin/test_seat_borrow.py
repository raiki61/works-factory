"""lib/seat.py（修正の役の座）が、起動の bin/_lib/spseam.py と同じ借りた物の置き場を読み、写しを同じ行で固定と照らし、部品の型を
同じ文に埋めることの試験。

lib/ は bin/ を import しない（lib/AGENTS.md の E3）ので、seat は置き場の読み口・固定との照らし・型の埋め方を spseam と別に持つ。
"""
import json
import pathlib
import shutil
import sys
import tempfile
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


    def test_pin_problems_match_the_launchers(self):
        """写しが固定と同じ時も、ファイルを足した・変えた・消した・固定から外した時も、spseam.pin_problems と同じ行を返す"""
        item, src = seat.pinned()
        self.assertEqual(seat.pin_problems(src, item), [])
        with tempfile.TemporaryDirectory() as tmp:
            copy = pathlib.Path(tmp) / "v"
            shutil.copytree(src, copy)
            listed = sorted(item["pin"]["files"])
            (copy / listed[0]).write_text("変えた\n", encoding="utf-8")
            (copy / listed[1]).unlink()
            (copy / f"skills/{item['skills'][0]}/extra.md").write_text("足した\n", encoding="utf-8")
            loose = json.loads(json.dumps(item))
            loose["pin"]["files"].pop(f"skills/{item['skills'][0]}/SKILL.md")
            for it in (item, loose):
                got = seat.pin_problems(copy, it)
                self.assertGreaterEqual(len(got), 3)
                self.assertEqual(got, spseam.pin_problems(copy, it))
            self.assertEqual(seat.pin_problems(copy, {**item, "pin": None}), spseam.pin_problems(copy, {**item, "pin": None}))


if __name__ == "__main__":
    unittest.main()

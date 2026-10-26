"""書き手の型の block static（workflows/weapon-static/）の試験。照らす事は tests/blocks/kit.py の WriterBlockCase に 1 か所（block の名を渡して継ぐだけ）。
筋書きの返答は static の義務（kinds_rows）が読む evidence.kinds の行を書く。"""
import unittest

from tests.blocks import kit


class StaticCase(kit.WriterBlockCase):
    block = "weapon-static"

    def test_the_scenario_reply_carries_kinds_rows_and_fits_the_shape(self):
        """F1（docs/plans/2026-10-24-fix-weapons.md の 11.6 の F1 の縛る試験の 4）: 筋書きの返答は、受け付けの義務が読む欄を書き、
        書き手の返答の形（shared:writer-reply.schema.json）に合う"""
        reply = kit.shaped("shared:writer-reply.schema.json", self.reply())
        self.assertTrue(reply["evidence"]["kinds"] and all(r["kind"] and r["did"] for r in reply["evidence"]["kinds"]))

if __name__ == "__main__":
    unittest.main()

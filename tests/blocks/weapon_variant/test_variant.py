"""書き手の型の block variant（workflows/weapon-variant/）の試験。照らす事は tests/blocks/kit.py の WriterBlockCase に 1 か所（block の名を渡して継ぐだけ）。
筋書きの返答は variant の義務（sites_shape・unit_red）が読む sites の行 at・fixed_by・red_seen を書く。"""
import unittest

from tests.blocks import kit


class VariantCase(kit.WriterBlockCase):
    block = "weapon-variant"

    def test_the_scenario_reply_carries_sites_at_fixed_by_and_fits_the_shape(self):
        """F1（docs/plans/2026-10-24-fix-weapons.md の 11.6 の F1 の縛る試験の 4）: 筋書きの返答は、受け付けの義務が読む欄を書き、
        書き手の返答の形（shared:writer-reply.schema.json）に合う"""
        reply = kit.shaped("shared:writer-reply.schema.json", self.reply())
        [site] = reply["changes"][0]["closure"]["sites"]
        self.assertTrue(site["red_seen"] and site["at"] and site["fixed_by"], site)
        self.assertNotIn("test", site)

if __name__ == "__main__":
    unittest.main()

"""事前審査の block の、筋書き（fixtures/）で届かない AI の node の指示を、その prep を回して md から組み、決まった文が入ることを見る。

表 RENDERED は、筋書きで届かない node（形 theme の出し直しの役 review-theme-fix。輪の 2 周目だけに回り、出し直しの指示は 1 回目の役と
同じ prep の theme-prep が組むので、prep を差し替える筋書きでは本物の指示を照らせない）の md の決まった文。
tests/layers/test_block_shape.py の 7.1 の 3 の照らしは、この表の在りと字だけを見る。表の行は下の試験が本当に組んだ指示の中に在ることを
照らす。
"""
import unittest

from tests.blocks import kit
from tests.blocks.plan_review import values as V

RENDERED = {
    "review-theme-fix": "Your previous answer was rejected by the machine's check.",
}


class RenderedCase(unittest.TestCase):
    def test_review_theme_fix(self):
        """形 theme の 1 回目の答えが拒まれた後の周は、theme-prep が出し直しの役の指示を md から組む"""
        r = V.Block(self)
        draft = r.put("theme/design.md", "# 設計の案\n", raw=True)
        self.assertEqual(r.intake(theme_doc=draft)["form"], "theme")
        r.script("theme_prep", prev="")
        bad = {"faces": [{"key": "entrance-without-no-add", "kind": "entrance", "where": "設計の案", "why": "w" * 20,
                          "severity": "block", "reach": "forces_redesign"}], "shrink": [], "reason": V.REASON}
        self.assertFalse(r.script("theme_accept", reply=V.dump(bad), fix_reply="null", status_guarded="true")["ok"])
        got = r.script("theme_prep", prev="false")
        self.assertTrue(got["resubmit"], got)
        self.assertIn(RENDERED["review-theme-fix"], got["prompt"])
        self.assertTrue((r.artifacts / "review-theme-fix-prompt-1.md").is_file())


if __name__ == "__main__":
    unittest.main()

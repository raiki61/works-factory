"""人の方針を役に届ける形（policy）。盤面の写しから組む brief と、盤面の無いブロックが貼る節 section が同じ上限で本文を切ること
（元 works/.shared/core/gl-prompts/prompts/policy-paste.md・policy.md）"""
import pathlib
import sys
import tempfile
import types
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import policy  # noqa: E402
from engine.render import MATERIAL_NOTE  # noqa: E402


class SectionCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pol = pathlib.Path(tmp.name) / "policy.md"

    def test_section_carries_preface_material_and_rule_only_when_present(self):
        self.pol.write_text("- 公開の口を減らさない\n", encoding="utf-8")
        got = policy.section(self.pol)
        self.assertTrue(got.startswith(f"{policy.HEAD}\n\n{policy.PREFACE}{MATERIAL_NOTE}\n"), got)
        self.assertIn("- 公開の口を減らさない", got)
        self.assertTrue(got.endswith(policy.RULE))
        self.assertIn("自分の判断で通すな", policy.RULE)
        self.assertEqual(policy.section(""), "")
        self.assertEqual(policy.section(self.pol.parent / "無い.md"), "")

    def test_section_cuts_the_body_at_the_paste_cap_and_names_the_rest(self):
        """上限を越えた方針は先頭だけを貼り、続きの置き場を書く（貼った本文は上限の内。brief と同じ切り方）"""
        self.pol.write_bytes(("- 決まり\n" * 6000).encode("utf-8") + "TAIL-MARK".encode("utf-8"))
        got = policy.section(self.pol)
        body = got.split(f"{MATERIAL_NOTE}\n", 1)[1].rsplit(f"\n{MATERIAL_NOTE}", 1)[0]
        self.assertLessEqual(len(body.encode("utf-8")), policy.PASTE_CAP)
        self.assertNotIn("TAIL-MARK", got)
        self.assertIn(f"{policy.PASTE_CAP} バイトまでを貼った。続きは {self.pol}", body)
        self.assertEqual(body, policy.brief(types.SimpleNamespace(
            record={"process": {"policy": {"copy": str(self.pol)}}}))["paste"])
        self.assertTrue(got.endswith(policy.RULE))


if __name__ == "__main__":
    unittest.main()

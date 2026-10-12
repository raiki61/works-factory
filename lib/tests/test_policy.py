"""人の方針を役に届ける形（policy）。盤面の写しから組む brief と、盤面の無いブロックが貼る節 section が同じ上限で本文を切ること
（元 works/.shared/core/gl-prompts/prompts/policy-paste.md・policy.md）"""
import hashlib
import pathlib
import subprocess
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


class FreezeCase(unittest.TestCase):
    """run の始めに 1 度だけ固める版 {named, path, sha256, copy}（元 graphloops/rules/policy_input.py の locate・snapshot）と、
    ブロックが読む写し frozen_copy"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo, self.run = self.tmp / "repo", self.tmp / "run"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

    def assert_copied(self, got, named, path, body: bytes):
        sha = hashlib.sha256(body).hexdigest()
        self.assertEqual((got["named"], got["path"], got["sha256"]), (named, path, sha))
        self.assertEqual(pathlib.Path(got["copy"]), self.run / policy.DIR / f"{sha}.md")
        self.assertEqual(pathlib.Path(got["copy"]).read_bytes(), body)

    def test_freeze_named_default_and_absent(self):
        self.assertEqual(policy.freeze(self.run, self.repo, ""), {"named": "", "path": "", "sha256": None, "copy": None})
        default = self.repo / ".git" / "graphloops" / "policy.md"
        default.parent.mkdir(parents=True)
        default.write_bytes("- 既定の置き場の方針\n".encode("utf-8"))
        self.assert_copied(policy.freeze(self.run, self.repo, ""), "", str(default.resolve()), default.read_bytes())
        named = self.tmp / "named.md"
        named.write_bytes("- 名指した方針\n".encode("utf-8"))
        self.assert_copied(policy.freeze(self.run, self.repo, str(named)), str(named), str(named), named.read_bytes())

    def test_frozen_copy_reads_the_version_and_falls_back_to_policy_md(self):
        """欄 policy の在る記録は写し copy（文書が無い版は空）、欄の無い・壊れた記録は今どおり policy_md"""
        frozen = {"named": "/p.md", "path": "/p.md", "sha256": "a" * 64, "copy": "/run/policy/a.md"}
        self.assertEqual(policy.frozen_copy({"policy_md": "/p.md", "policy": frozen}), "/run/policy/a.md")
        self.assertEqual(policy.frozen_copy({"policy_md": "/p.md", "policy": {**frozen, "sha256": None, "copy": None}}), "")
        for start in ({"policy_md": "/p.md"}, {"policy_md": "/p.md", "policy": "壊れた"},
                      {"policy_md": "/p.md", "policy": {"copy": 3}}):
            with self.subTest(start=start):
                self.assertEqual(policy.frozen_copy(start), "/p.md")
        self.assertEqual(policy.frozen_copy(None), "")


if __name__ == "__main__":
    unittest.main()

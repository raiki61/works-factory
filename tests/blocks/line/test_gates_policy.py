"""方針の文書の変化（workflows/line/src/gates.py の policy_change・change_row・DIFF_MISSING）。

元は今の lib/tests/test_boardview.py の、方針の文書の版と変化を見る 4 本（test_policy_version_comes_from_start・
test_record_without_a_version_freezes_on_first_open・test_document_placed_later_at_the_default_is_a_change・
test_lost_frozen_copy_is_named_not_diffed。docs/design/README.md の 9.5）。元は事前審査の置き場（boardview の folder）に固めた版を
置いて policy_change(folder, cwd) を呼んだ。line の policy_change は始めの記録の欄 policy（run の始めに固めた版）を直に受けるので、
固めた版は policy.freeze で作って記録の dict に入れる。
"""
import pathlib
import subprocess
import tempfile
import unittest

from tests.blocks import kit
from tests.bin import hermetic

gates = kit.load("line", "gates")
import policy  # noqa: E402


class PolicyChangeCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name).resolve()
        self.run = self.tmp / "run"         # 始めに固めた版の写しの置き場
        self.folder = self.tmp / "folder"   # 今の版の写しと差分の置き場

    def frozen(self, named: str) -> dict:
        return {"run_id": "r", "policy_md": named, "policy": policy.freeze(self.run, self.tmp, named)}

    def change(self, record: dict):
        return gates.policy_change(record, self.tmp, self.folder)

    def test_changed_document_is_named_with_its_diff(self):
        """元 test_policy_version_comes_from_start の変化の部分: 始めに固めた版から変わった文書は、固めた版と今の版の写しと差分で
        名指す。関所の行は置き場だけを持ち、本文を載せない。変わっていなければ None"""
        pol = self.tmp / "policy.md"
        pol.write_text("# 方針\n- 公開の口を減らさない\n", encoding="utf-8")
        record = self.frozen(str(pol))
        self.assertIsNone(self.change(record))
        pol.write_text("# 方針\n- 公開の口を減らさない\n- 足した\n", encoding="utf-8")
        ch = self.change(record)
        self.assertEqual((ch["from"], ch["from_copy"], ch["path"]), (record["policy"]["sha256"], record["policy"]["copy"], str(pol)))
        self.assertIn("足した", pathlib.Path(ch["diff_file"]).read_text(encoding="utf-8"))
        self.assertIn("足した", pathlib.Path(ch["to_copy"]).read_text(encoding="utf-8"))
        self.assertNotIn("diff_missing", ch)
        row = gates.change_row(ch)
        self.assertIn(str(pol), row)
        self.assertIn(f"差分 {ch['diff_file']}", row)
        self.assertIn(f"{ch['from'][:12]} → {ch['to'][:12]}", row)
        self.assertNotIn("足した", row, "関所の行は置き場だけで本文を載せない")

    def test_record_without_a_version_is_not_a_change(self):
        """元 test_record_without_a_version_freezes_on_first_open の変化の部分: 欄 policy の無い・形の違う始めの記録（線の外から
        差し込んだ run）は、文書が在っても変化に数えない"""
        pol = self.tmp / "policy.md"
        pol.write_text("- 前\n", encoding="utf-8")
        for record in ({"run_id": "r", "policy_md": str(pol)}, {"run_id": "r", "policy": {"sha256": "x"}}, {}):
            with self.subTest(record=record):
                self.assertIsNone(self.change(record))

    def test_document_placed_later_at_the_default_is_a_change(self):
        """元 test_document_placed_later_at_the_default_is_a_change: 固めた時に文書が無くても、後で既定の置き場に置いた文書は変化に
        数える（置き場を引き直す。元 policy_input.change が locate を引き直す）"""
        subprocess.run(["git", "init", "-q", str(self.tmp)], check=True, env=hermetic.child_env())
        record = self.frozen("")
        self.assertEqual((record["policy"]["path"], record["policy"]["sha256"]), ("", None))
        self.assertIsNone(self.change(record))
        doc = self.tmp / ".git" / "graphloops" / "policy.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("- 後で置いた\n", encoding="utf-8")
        ch = self.change(record)
        self.assertEqual((ch["from"], pathlib.Path(ch["path"])), (None, doc.resolve()))
        self.assertIn("後で置いた", pathlib.Path(ch["diff_file"]).read_text(encoding="utf-8"))
        self.assertIn("前の版の写し （無い）", gates.change_row(ch))

    def test_lost_frozen_copy_is_named_not_diffed(self):
        """元 test_lost_frozen_copy_is_named_not_diffed: 固めた版の写しが消えていれば、空の文と比べた差分を作らず diff_missing を
        関所の行に名指す"""
        pol = self.tmp / "policy.md"
        pol.write_text("- 前\n", encoding="utf-8")
        record = self.frozen(str(pol))
        pathlib.Path(record["policy"]["copy"]).unlink()
        pol.write_text("- 後\n", encoding="utf-8")
        ch = self.change(record)
        self.assertEqual((ch["diff_missing"], ch["diff_file"]), (gates.DIFF_MISSING, None))
        self.assertIn(gates.DIFF_MISSING, gates.change_row(ch))
        self.assertEqual(list((self.folder / policy.DIR).glob("*.diff")), [], "差分のファイルを置かない")

    def test_removed_document_is_named_gone(self):
        """元 change_row の「消えた」: 固めた後に文書が消えた run は、今の版を消えたと言い、今の版の写しは無い"""
        pol = self.tmp / "policy.md"
        pol.write_text("- 前\n", encoding="utf-8")
        record = self.frozen(str(pol))
        pol.unlink()
        ch = self.change(record)
        self.assertEqual((ch["to"], ch["to_copy"]), (None, None))
        row = gates.change_row(ch)
        self.assertIn("→ 消えた", row)
        self.assertIn("今の版の写し （無い）", row)


if __name__ == "__main__":
    unittest.main()

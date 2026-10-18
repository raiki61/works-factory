"""修正のブロック（blk-fix）の検査のうち、lib/ の部品を直に呼ぶ物。

- 役の指示書（fixrules.render が fix_parts の修正の決まりの正本と run の値から組む）が値と決まり（commit しない・テスト）を持ち、
  修正案・人の答え・方針の文書・TDD の輪の結果を run の値のパスから読ませ、前の回の拒否の理由をファイルのパスで頭に置く
- 後始末のモジュール leftovers は標準ライブラリだけを読む
盤面・git・子のプロセスは使わない（関数を直に呼ぶ）。
"""
import ast
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import fixboard  # noqa: E402
import fixrules  # noqa: E402
import policy  # noqa: E402
import rulebook  # noqa: E402
from lib.tests.test_fix_rules import fix_prompt  # noqa: E402

# 決まりの文の本体の置き場（scripts が import の後にする置き替えと同じ。lib/ の字にパスを書かない）
FR = LIB.parent / "workflows" / "fix" / "commands" / "fix-rules"
rulebook.CANON = FR / "common.md"
fixrules.SHARED = rulebook.CANON
fixrules.RULES_DIR = FR


class TestFixPrompt(unittest.TestCase):
    def fix_prompt(self):
        return fix_prompt({k: f"/b/{k}" for k in fixrules.FIX_VALUES})

    def test_fix_prompt(self):
        """組んだ指示書: run の値は全部パスで埋まり（実行基盤の $ の置き換えに通さない）、決まり（commit しない・テスト）と欄を持つ"""
        body = self.fix_prompt()
        for k in fixrules.FIX_VALUES:
            self.assertIn(f"`/b/{k}`", body)
        for s in ("git commit", "テスト", "unit_key"):
            self.assertIn(s, body)
        for gone in ("$INPUTS", "$LOOP_PREV", "{{", "<<"):
            self.assertNotIn(gone, body)

    def test_fix_prompt_reads_inputs(self):
        """0.21.0 の p3.fix.md から書き直した指示書: 修正案・承認ノードの答え（人の答えか推し）・方針の文書・TDD の輪の結果を run の値のパスから読む。
        前の回の拒否の理由は reason_file（パス）で指示書の頭に（裁定 R44）。返答の欄を名指し、判定の prescriptions（零処方）を先に採らせる"""
        body = self.fix_prompt()
        for s in ("修正案", "承認ノードで答えたことを書いたファイル", "無人の run が採った推し", "人の方針の文書", "TDD のループの結果"):
            self.assertIn(s, body)
        for field in ("closure", "coverage", "precedent", "root_or_symptom", "bypass_tried", "breaks"):
            self.assertIn(f"`{field}`", body, field)
        self.assertIn("`prescriptions`", body)
        self.assertIn("零処方", body)
        # 盤面の無い物を読ませない: engine の穴（{{…}}）・前の周の R1/R4・並行の線の合流は無い
        for gone in ("{{", "prev.r1", "prev.r4", "lane_merge"):
            self.assertNotIn(gone, body)
        again = fix_prompt({k: f"/b/{k}" for k in fixrules.FIX_VALUES}, reject_file="/b/reject-accept_fix-1.txt")
        self.assertIn("/b/reject-accept_fix-1.txt", again.split("\n")[1])


class TestPolicyBrief(unittest.TestCase):
    def test_policy_brief_reads_frozen_copy(self):
        """修正の役に貼る方針と渡すパスは始めの記録の固めた版の写し（始めの後に policy_md の文書を書き換えても固めた版）"""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        pmd = root / "policy.md"
        pmd.write_text("方針の印: 固めた版\n", encoding="utf-8")
        frozen = policy.freeze(root / "run", root, str(pmd))
        start = {"policy_md": str(pmd), "policy": frozen}
        pmd.write_text("方針の印: 書き換えた版\n", encoding="utf-8")
        self.assertEqual(fixboard.policy_brief(start), {"paste": "方針の印: 固めた版\n", "path": frozen["copy"]})
        self.assertEqual(fixboard.fix_values(root, [], start=start)["policy_path"], frozen["copy"])
        self.assertEqual(fixboard.policy_brief({}), {"paste": "", "path": ""})


class TestLeftoversModule(unittest.TestCase):
    def test_leftovers_is_stdlib_only(self):
        """標準ライブラリと、何も import しない修正の名の住処 fixnames だけ（lib のほかのモジュールは読まない）"""
        def imported(module):
            tree = ast.parse((LIB / f"{module}.py").read_text(encoding="utf-8"))
            self.assertFalse(any(isinstance(n, ast.ImportFrom) and n.level for n in ast.walk(tree)))
            names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            return names | {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level == 0}
        names = imported("leftovers")
        self.assertTrue(names)
        self.assertEqual(sorted(names - set(sys.stdlib_module_names)), ["fixnames"])
        self.assertEqual(imported("fixnames"), set())


if __name__ == "__main__":
    unittest.main()

"""判定のブロックの受け付けと支度の芯（lib/judge_accept）の試験。

今の works の試験（test_blk_judge・test_blk_premises・test_blk_purpose・test_blk_material・test_blk_spec・test_rejudge・
test_judge_verify・test_structure_units・test_accept の TestJudge・TestIntake）が盤面の上で確かめていた場面を、値を渡す形に写した。
各試験の docstring に元の試験の名を書く。
"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import judge_accept as ja  # noqa: E402


class TablesCase(unittest.TestCase):
    def test_is_open_follows_label_and_disposition(self):
        """元 test_judge_verify の開いた単位の数え（検証器の is_open）"""
        self.assertTrue(ja.is_open({"label": "block"}))
        self.assertTrue(ja.is_open({"label": "suggest", "disposition": "do-now"}))
        self.assertFalse(ja.is_open({"label": "suggest", "disposition": "defer"}))
        self.assertFalse(ja.is_open({"label": "nit"}))


# ================================================================ 依頼と判定（A）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
# ================================================================ 依頼と判定（A）の終わり


# ================================================================ 材料・前提・目的・素材（B）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
# ================================================================ 材料・前提・目的・素材（B）の終わり


# ================================================================ 再審と仕様（C）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
# ================================================================ 再審と仕様（C）の終わり


# ================================================================ 並行 PR と世界の解（W）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
# ================================================================ 並行 PR と世界の解（W）の終わり


# ================================================================ 入口と返り（F）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
# ================================================================ 入口と返り（F）の終わり


if __name__ == "__main__":
    unittest.main()

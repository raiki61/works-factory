"""手直しの役（refix・refix2）の指示書の組み立て。AI を通さず、機械が書く役の決まりの正本（rulebook.CANON）のうちこの役に
当たる節（NOT_HERE の外）を字のまま載せ、手直しの決まり（rules/refix.md）と run の値を繋ぐ。同じ入力からはバイト単位で同じ。

並び: 役の頭（refix-head-<n>）→ 正本の節（NOT_HERE を除いた全部。ファイルの順）→ 読み替え（refix-remap。正本より勝つ）→ 手直しだけの決まり
（refix-keep）→ 借りたスキルの座（seat。receiving-code-review。fixboard.refix_prompt が seat.section で組む）→ 返答（refix-reply。どの回も同じ）→ 返答の後に当たる物（refix-tail-<n>）。支度は周ごとに組み、この輪の拒否の理由の全部のファイルは
指示書の 1 行目で名指す（fixboard.refix_prompt の reject_file）。並べて組むのは呼び手の script の節（fixrules と同じ形。
rulebook.sections・fill・pick・render を呼ぶ）で、ここは決まりのファイルの置き場と節の表だけを持つ。
"""
import pathlib
import sys

sys.dont_write_bytecode = True

import refix  # noqa: E402  （差分の往復の役の名 FIX_ROLE・REVIEW_ROLE）
import rulebook  # noqa: E402

RULES = pathlib.Path(__file__).resolve().parents[1] / "rules" / "refix.md"
VALUES = ("brief_file", "diff_file", "policy_path")
ROLES = {1: "refix", 2: "refix2"}
ALWAYS = "いつも"
# 正本のうち載せない節: 食い違いの申し出（conflicts）の出口はこの役に無い。曲げない決まりと、申し出の代わりの declared は読み替え
# （refix-remap）が言う
NOT_HERE = ("core-conflict",)

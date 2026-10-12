"""役に写させない——engine が一覧に振った番号で役に指させる（graph の節の `pointers`）。元の engine の pointers.py のうち、
Renderer が貼る一覧の各行へ番号の欄 NO を足す number だけを持つ（番号を名前に戻すのは呼び手。修正案は planfile.named）。

役に長い文字列（判定の単位の key・事前審査の穴の key）を一字一句写させ、1 字違えば受け付けで拒んで返させ直していた
（実測: run 20260924-081523 の 5 周目に 3 回の差し戻し）。Anthropic の Citations が文書の添字で指させ、本文を API の側で
引くのと同じ形にする。
"""
NO = "no"   # 貼る一覧の各行に足す番号の欄


def number(rows, offset):
    """貼る一覧の各行の先頭に no を足した写し（ctx の値は書き換えない——record と loop_state に no を残さない）。
    行が元から no の欄を持っていても engine の番号で上書きする（役が指すのは engine の番号だけ）"""
    return [{NO: offset + i + 1, **{k: v for k, v in x.items() if k != NO}} if isinstance(x, dict) else {NO: offset + i + 1, "value": x}
            for i, x in enumerate(rows)]


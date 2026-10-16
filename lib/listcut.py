"""件数の決まらない一覧を、先頭 SHOWN 件と『ほか K 件（全件: 置き場）』の行に切る口。対象の木で役が作ったファイルの数のように、
件数が run の決定でなく外の事実で決まる一覧を行に組むと、承認ノードの文と報告が件数に比例して膨らむ。clean が消したファイル
（fixbeside）・取り込むと消えるファイル（seal）・新しい名と知る場所の増え（structmark）の一覧はこの口で切る。

- SHOWN: 先頭に残す件数（lib/eye.py の DUP_SHOWN と同じ考えの値）
- REST: 残りの行の字（`{n}` に残りの件数）
- lines(items, *, where='', shown=SHOWN, prefix='  - '): items が shown 件以下なら全件を prefix つきで返す。超える時は先頭
  shown 件と、残りの 1 行（where が在れば『（全件: where）』を添える）だけを返す。行の数は件数に依らない

標準ライブラリだけ（lib のほかの物を import しない）。
"""

SHOWN = 5
REST = "ほか {n} 件"


def lines(items, *, where: str = "", shown: int = SHOWN, prefix: str = "  - ") -> list:
    items = list(items)
    out = [f"{prefix}{x}" for x in items[:shown]]
    if len(items) > shown:
        out.append(f"{prefix}{REST.format(n=len(items) - shown)}" + (f"（全件: {where}）" if where else ""))
    return out

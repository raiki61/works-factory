"""件数の決まらない一覧を、先頭 SHOWN 件と『ほか K 件（全件: 置き場）』の行に切る口。対象の木で役が作ったファイルの数のように、
件数が run の決定でなく外の事実で決まる一覧を行に組むと、承認ノードの文と報告が件数に比例して膨らむ。clean が消したファイル
（fixbeside）・取り込むと消えるファイル（seal）・新しい名と知る場所の増え（structmark）・守りのファイルに当たった物（protect）の
一覧はこの口で切る。

- SHOWN: 先頭に残す件数
- REST: 残りの行の字（`{n}` に残りの件数）
- lines(items, *, name='', where='', shown=SHOWN, prefix='  - '): items が shown 件以下なら全件を prefix つきで返す。超える時は先頭
  shown 件と、残りの 1 行だけを返す。残りの行は、name（一覧の名と、全件を持つ JSON の欄の名）が在れば頭に『<name>の』を付け、
  where が在れば『（全件: where）』を添える。1 つの節に一覧が 2 本並ぶ時も、どちらの残りかが読める。行の数は件数に依らない

標準ライブラリだけ（lib のほかの物を import しない）。
"""

SHOWN = 5
REST = "ほか {n} 件"


def lines(items, *, name: str = "", where: str = "", shown: int = SHOWN, prefix: str = "  - ") -> list:
    items = list(items)
    out = [f"{prefix}{x}" for x in items[:shown]]
    if len(items) > shown:
        out.append(f"{prefix}{name + 'の' if name else ''}{REST.format(n=len(items) - shown)}" + (f"（全件: {where}）" if where else ""))
    return out

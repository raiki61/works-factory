"""依頼の行を port から読む共通の口（2 つ以上の block が使う。docs/design/README.md の 13 章）。

依頼は、行の配列か、それを findings の欄に持つ工場の依頼のファイルの形（`.shared/schemas/request.schema.json`）。形を照らした後、
lib/carry.py の parts で容器を読む: 知らない最上位の鍵・前の run の報告が運んだ所見の下書き（draft・source の欄の行）・pr と issue の
番号の形・answers・prior_failures・constraints の形を、名指して拒む（今の worldblk._findings が carry.parts で拒んでいた物）。
下書きの行は、行の配列の形でも拒む（carry.parts は配列の形では見ない）。

- parts(raw) -> dict: carry.parts の返り（findings・pr・issue・answers・prior_failures・constraints）。読めなければ ValueError
- findings(raw) -> list: parts(raw) の findings。空の配列 `[]`（と findings が空の容器）は拒まずに `[]` を返す。空の依頼の扱いは block が
  決める（`.shared/AGENTS.md`）ので、block の空の依頼の不具合でここを直さない

作り直しの間は lib/ を触らないので、ここに置く。組み込みで lib/ の carry の隣へ移すかは、その時に使い手の数で決める。
"""
import ports

import carry  # lib/。依頼の容器の形の住処

SCHEMA = "shared:request.schema.json"


def parts(raw) -> dict:
    value = ports.json(raw, SCHEMA)
    # 行の配列も容器に包んでから読む（carry.parts は配列の形では下書きの行を見ないので、2 つの形で拒む物を揃える）
    return carry.parts({carry.FINDINGS: value} if isinstance(value, list) else value)


def findings(raw) -> list:
    return parts(raw)[carry.FINDINGS]

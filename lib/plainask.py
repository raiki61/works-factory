"""人に聞く文の照らし（共通の断片 workflows/.shared/prompts/plain-ask.md の機械で縛れる部分）。

役が書く人に聞く文（承認ノードの項目と報告の「人が決めること」に載る欄）は、初見の読み手（run も工場の内部の語も知らない持ち主）が
その文だけで判断できる形で書く。そのうち yes/no で照らせるのは「run の中を指す参照を書かない」だけで、ここはそれを拒む文を返す。
詳しさ・項目の形（題／今／工場の案／代償／推し）・同じ論点を 1 項目にまとめることは人が見る（憲法の 6。数の上限で縛らない）。

- refs(text) -> list[str]: 文の中の、run の中を指す参照（重ねずに出た順）。2 つの形だけを数える:
  `<パス>:<行>`（`a/b.py:12`・`x.md:3-5`。拡張子の在る名に `:` と数が続く物）と `<名>[<番号>]`（`plan[0]`・`faces[2]` のような返答の
  JSON の中の位置）。正当な文を差し戻さないよう、次は数えない: URL の中（世界の解の出典の URL は引いてよい）・バッククォートの中の
  <名>[<番号>]（対象のコードの添え字の字のままの引用。<パス>:<行> は囲んでも数える）・拡張子の表（KNOWN_EXT。lib/changemap.py の表から
  組む）に無い拡張子の <パス>:<行>（番地とポート・製品の名と版）・大文字の混じる名の <名>[<番号>]（脚注。返答の JSON の欄の名は小文字）。
  数えなかった物は人が見る
- gaps(where, text) -> list[str]: 参照を 1 つでも持てば、受け付けが役に返す 1 行（where は欄の名指し）。無ければ []
- 記録のファイルの名・単位の key・行や答えの id は、対象のリポジトリのファイルの名や役の文と字で見分けられないので照らさない（人が見る）
"""
from __future__ import annotations

import re

import changemap   # 拡張子の表（写しは直さないので、ここで組む。lib/COPIED_FROM.changemap）

# changemap の表のどれかに在る拡張子（<パス>:<行> の形の数え方を、番地とポート・製品の名と版から分ける）
KNOWN_EXT = frozenset(set(changemap.OUTLINE_PATTERNS) | changemap.PROSE_EXT
                      | {e for exts in changemap.COMMENT_BY_EXT.values() for e in exts}
                      | {e for exts in changemap.FENCE_BY_EXT.values() for e in exts})
URL = re.compile(r"https?://\S+")
CODE = re.compile(r"`[^`\n]*`")
LINE_REF = re.compile(r"(?<![A-Za-z0-9_./-])[A-Za-z0-9_./-]*[A-Za-z0-9_-]\.([A-Za-z][A-Za-z0-9]*):\d+(?:-\d+)?")
INDEX_REF = re.compile(r"(?<![A-Za-z0-9_])[a-z_][a-z0-9_]*\[\d+\]")
WHY = ("初見の読み手が解けない run の中を指す参照（{refs}）が在る——人に聞く文には <パス>:<行> も <欄>[<番号>] も書かず、"
       "指す物が何かを平易な言葉で書け（出どころの名指しは決め手・根拠の欄に）")


def _blank(m) -> str:
    """消した所を同じ長さの空白にする（2 つの形の見つけた位置を同じ物差しで並べる）"""
    return " " * len(m.group(0))


def refs(text) -> list[str]:
    """text の中の run の中を指す参照（重ねずに出た順。文字列でなければ []）"""
    if not isinstance(text, str):
        return []
    plain = URL.sub(_blank, text)
    found = sorted([(m.start(), m.group(0)) for m in LINE_REF.finditer(plain) if m.group(1).lower() in KNOWN_EXT]
                   + [(m.start(), m.group(0)) for m in INDEX_REF.finditer(CODE.sub(_blank, plain))])
    return list(dict.fromkeys(ref for _, ref in found))


def gaps(where: str, text) -> list[str]:
    """参照を持つ文の拒否の 1 行（無ければ []）"""
    found = refs(text)
    return [f"{where}: {WHY.format(refs='・'.join(found))}"] if found else []

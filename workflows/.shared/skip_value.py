"""埋め P2（docs/polyfills.md）: include の with: に `{from, if_skipped}` を書けない穴を、線の返しの節で受ける部品。

返しの節は線の script の節で、with: に `{from: "$<節>.output.<欄>", if_skipped: null}` を欄ごとに書き、明示の値で返し直す。
止めた Archon は束ねた値を環境変数 INPUTS_<名> に、字の値はそのまま、ほかの値（数・真偽・配列・object・null）は JSON の字で渡す
（packages/workflows/src/output-ref.ts の canonicalValueText）。ここはその字を値に戻すだけ。

- value(raw): JSON の値に戻す（JSON でなければ字のまま）。飛ばされた節の null と無い入力は None
- text(raw): 字の欄の値（JSON に戻さない）。null と無い入力は None
"""
import json

SKIPPED = "null"


def value(raw):
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def text(raw):
    return None if raw is None or raw == SKIPPED else raw

"""埋め P2（docs/polyfills.md）: include の with: に `{from, if_skipped}` を書けない穴を、線の返しの節で受ける部品。

返しの節は線の script の節で、with: に `{from: "$<節>.output.<欄>", if_skipped: null}` を欄ごとに書き、明示の値で返し直す。
止めた Archon は束ねた値を環境変数 INPUTS_<名> に、字の値はそのまま、ほかの値（数・真偽・配列・object・null）は JSON の字で渡す
（packages/workflows/src/output-ref.ts の canonicalValueText）。ただし output_format で宣言した欄の null と無い欄は空の字で渡す
（output-ref.ts の resolveNodeOutputField が empty に解き、dag-executor.ts の substituteNodeOutputRefs が '' にする。
tests/shared/test_archon_contract.py が照らす）。ここはその字を値に戻すだけ。

- parsed(raw): JSON の値に戻す。飛ばされた節の null・宣言した null の欄の空の字・無い入力は None。JSON でなければ ValueError
- value(raw): parsed と同じで、JSON でなければ字のまま
"""
import json


def parsed(raw):
    return None if raw is None or not raw.strip() else json.loads(raw)


def value(raw):
    try:
        return parsed(raw)
    except ValueError:
        return raw

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返し（埋め P2。docs/design/line.md の 1.5 の relay）: 飛ばされうる値を明示の値で返し直す node（structure-in・design-in・lens-in・
lens-2-in。今の structure_in.py の形を 1 本にした物）。include の with: は `{from, if_skipped}` の束ねを読まないため、後ろの include は
ここの欄を読む。

入力（with:）: got（作り手の出力まるごとか受け皿の got。`{from, if_skipped: null}` で受ける。飛ばされたら null）と field（運ぶ欄の名を
空白で区切った字）。出力は field の欄と stop_reason。got が null なら各欄 null（読み手の block は値の無い run として進む）。
got が field の欄を持たなければ（前の版の返り）、例外の時と同じく各欄 null と止めの語 works:line-script を返し、後ろへ進めない
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

FIELDS = ports.text(os.environ.get("INPUTS_FIELD")).split()
GOT = os.environ.get("INPUTS_GOT")


def relayed() -> dict:
    if not FIELDS:
        raise ValueError("運ぶ欄の名（field）が無い。with: の鍵の結びを確かめる")
    got = ports.picked(GOT, FIELDS)
    return {**{name: None if got is None else got[name] for name in FIELDS}, "stop_reason": ""}


def fallback(reason: str) -> dict:
    from src import guard

    return {**dict.fromkeys(FIELDS), "stop_reason": guard.LINE_SCRIPT}


ports.run(relayed, fallback)

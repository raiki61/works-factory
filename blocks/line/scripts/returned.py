# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""受け皿 <include の id>-out: include した block の出力を受け直す（埋め P8。docs/design/line.md の頭の語・13 節。今の returned.py）。

all_done で集める node（collect・ask-final・fix-in・fixed・judged）は受け皿だけを読む（Archon は落ちた node への with: を誤りにする
ので、block の返す node が落ちても受け皿が飛ぶだけにする）。受け皿は既定の trigger_rule（all_success）で受ける node の後ろに置く。

入力（with:）: got（受ける include の出力まるごと）と names（運ぶ欄の名を空白で区切った字。optional はいつも無くてよい欄）。
宣言した欄が無ければ got: null と訳 why を返す（落ちない。欄の欠けた前の版の返りを空と読まない。integration.md の 4.3-12）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    raw_names, raw_got = os.environ.get("INPUTS_NAMES"), os.environ.get("INPUTS_GOT")
    names = ports.text(raw_names).split()
    if not names:
        raise ValueError("運ぶ欄の名（names）が無い。with: の鍵の結びを確かめる")
    got = ports.picked(raw_got, names, optional=("optional",))
    if got is None:
        raise ValueError("受ける出力（got）が読めない。with: の鍵の結びを確かめる")
    return {"got": dict(got), "why": ""}


ports.run(compute, lambda why: {"got": None, "why": why})

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""埋め P8（docs/polyfills.md）。ブロックの返りを受け直す受け皿の節（<include の id>-out）。collect は返りをここから読む。
計画の往復の受け皿 2 本（plan-rounds-out・plan-rounds-review-out）は欄ごとに受ける別の script returned_fields。

ブロックの返す節が落ちると、その出力は `{from, if_skipped}` でも読めない（止めた Archon の dag-executor.ts の
resolveBindingDirective は落ちた節を if_skipped に落とさない）ので、collect が返りを直に読むと collect も落ち、報告が出ない。
受け皿は既定の trigger_rule（all_success）で受ける節の後ろに置くので、受ける節が落ちても飛ばされても飛ばされ、飛ばされた受け皿は
collect の if_skipped: null に落ちる。走った時は受けた返りの宣言した欄を got にして返す。

入力（with:）: got（受ける節の返りまるごと `$<受ける節>.output`。型を保った object で届く）と names（運ぶ欄の名を空白で区切った字）。
口 boundary.picked に names を渡すので、got は宣言した欄だけを持ち、宣言の外の欄は運ばない（workflows/AGENTS.md の E5 が、names が
受ける節の output_format に在ることと、output_format の欄のどれかが宣言されていることを照らす）。
どちらの入力も読めない時（with: の鍵の結び違い）は、空の got を成功で返さず fallback（stop_reason が works:line-script）に落とす
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402


def returned() -> dict:
    whole = boundary.picked(os.environ.get("INPUTS_GOT"), boundary.text(os.environ.get("INPUTS_NAMES")).split())
    if whole is None:
        raise ValueError("受ける出力（got）が読めない。with: の鍵の結びを確かめる")
    if not whole:
        raise ValueError("運ぶ欄の名（names）が無い。with: の鍵の結びを確かめる")
    return {"got": whole, "stop_reason": ""}


def fallback(reason: str) -> dict:
    return {"got": None, "stop_reason": boundary.LINE_SCRIPT}


if __name__ == "__main__":
    boundary.run(returned, fallback)

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""埋め P8（docs/polyfills.md）。ブロックと計画の往復の返りを受け直す受け皿の節（<include の id>-out と plan-rounds-out・
plan-rounds-review-out）。collect は返りをここから読む。

ブロックの返す節（や往復の中の節）が落ちると、その出力は `{from, if_skipped}` でも読めない（止めた Archon の dag-executor.ts の
resolveBindingDirective は落ちた節を if_skipped に落とさない）ので、collect が返りを直に読むと collect も落ち、報告が出ない。
受け皿は既定の trigger_rule（all_success）で受ける節の後ろに置くので、受ける節が落ちても飛ばされても飛ばされ、飛ばされた受け皿は
collect の if_skipped: null に落ちる。走った時は受けた返りを got にして返す。

入力（with:）: got（受ける節の返りまるごと `$<受ける節>.output`。型を保った object で届くので、書き写さずそのまま got にする。
素通しの宣言は PASSES）。計画の往復の 2 本（plan-rounds-out・plan-rounds-review-out）だけは、plan-out の 1 つの返りを PLAN と REVIEW の
2 つの got に分けて受けるので、got_<欄>（`$plan-rounds.output.<欄>`）を欄ごとに受け、欄の名は with: の鍵の got_ の後ろで、一覧を
持たない（Archon は線の inputs: も INPUTS_<名> で渡すので、頭 got_ の付いた物だけを読む。欄は boundary.value で JSON の値として読む）。
どちらの入力も読めない時（with: の鍵の結び違い）は、空の got を成功で返さず fallback（stop_reason が works:line-script）に落とす
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

PASSES = ("got",)
HEAD = "INPUTS_GOT_"


def returned(env) -> dict:
    whole = boundary.value(env.get("INPUTS_GOT"))
    if whole is not None:
        if not isinstance(whole, dict):
            raise ValueError(f"受ける返りが object でない（{type(whole).__name__}）")
        return {"got": whole, "stop_reason": ""}
    got = {key.removeprefix(HEAD).lower(): raw for key, raw in env.items() if key.startswith(HEAD)}
    if not got:
        raise ValueError("受ける返り（got か got_<欄>）が読めない。with: の鍵の結びを確かめる")
    return {"got": {key: boundary.value(raw) for key, raw in got.items()}, "stop_reason": ""}


def fallback(reason: str) -> dict:
    return {"got": None, "stop_reason": boundary.LINE_SCRIPT}


if __name__ == "__main__":
    boundary.run(lambda: returned(os.environ), fallback)

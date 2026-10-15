# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""埋め P8（docs/polyfills.md）。ブロックと計画の往復の返りを受け直す受け皿の節（<include の id>-out と plan-rounds-out・
plan-rounds-review-out）。collect は返りをここから読む。

ブロックの返す節（や往復の中の節）が落ちると、その出力は `{from, if_skipped}` でも読めない（止めた Archon の dag-executor.ts の
resolveBindingDirective は落ちた節を if_skipped に落とさない）ので、collect が返りを直に読むと collect も落ち、報告が出ない。
受け皿は既定の trigger_rule（all_success）で受ける節の後ろに置くので、受ける節が落ちても飛ばされても飛ばされ、飛ばされた受け皿は
collect の if_skipped: null に落ちる。走った時は受けた欄を got に組んで返す（字の欄は字のまま。boundary.field）。

入力（with:）: got_<欄>（受ける節の返りの欄 `$<受ける節>.output.<欄>`）。欄の名は with: の鍵の got_ の後ろで、一覧を持たない
（Archon は線の inputs: も INPUTS_<名> で渡すので、頭 got_ の付いた物だけを読む）
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

HEAD = "INPUTS_GOT_"


def returned(env) -> dict:
    got = {key.removeprefix(HEAD).lower(): raw for key, raw in env.items() if key.startswith(HEAD)}
    return {"got": {key: boundary.field(key, raw) for key, raw in got.items()}, "stop_reason": ""}


def fallback(reason: str) -> dict:
    return {"got": None, "stop_reason": boundary.LINE_SCRIPT}


if __name__ == "__main__":
    boundary.run(lambda: returned(os.environ), fallback)

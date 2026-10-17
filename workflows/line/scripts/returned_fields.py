# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""埋め P8（docs/polyfills.md）。計画の往復の返りを受け直す受け皿の節（plan-rounds-out・plan-rounds-review-out）。受け直す訳と
落ちた時の形はブロックの受け皿 returned と同じ。

plan-out の 1 つの返りを plan_out.PLAN と REVIEW の 2 つの got に分けて受けるので、まるごとでなく got_<欄>
（`$plan-rounds.output.<欄>`）を欄ごとに受ける。欄の名は with: の鍵の got_ の後ろで、一覧を持たない（Archon は線の inputs: も
INPUTS_<名> で渡すので、頭 got_ の付いた物だけを読む。欄は boundary.value で JSON の値として読む）。
got_<欄> の入力が 1 つも無い時（with: の鍵の結び違い）は、空の got を成功で返さず fallback（stop_reason が works:line-script）に落とす
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

HEAD = "INPUTS_GOT_"


def returned_fields(env) -> dict:
    got = {key.removeprefix(HEAD).lower(): raw for key, raw in env.items() if key.startswith(HEAD)}
    if not got:
        raise ValueError("受ける出力（got_<欄>）が読めない。with: の鍵の結びを確かめる")
    return {"got": {key: boundary.value(raw) for key, raw in got.items()}, "stop_reason": ""}


def fallback(reason: str) -> dict:
    return {"got": None, "stop_reason": boundary.LINE_SCRIPT}


if __name__ == "__main__":
    boundary.run(lambda: returned_fields(os.environ), fallback)

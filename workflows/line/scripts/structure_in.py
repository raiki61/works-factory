# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""構造の目の控えのポインタを計画の往復へ渡す返しのノード structure-in（埋め P2）。

構造のサブグラフは直す義務が在り行き止まりの無い run でだけ走る（ノード owed）ので、飛ばされうる。その出力の欄 structure を
`{from, if_skipped: null}` で受け、飛ばされたら null を返す（計画と事前審査は控えの無い run として構造の目の行なしで進む）。
出力 {structure, stop_reason}。例外の時は止めの理由 works:line-script を返し、計画の往復へ進めない。

入力（with:）: structure（構造の目の控えのポインタか null）
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402


def relayed(raw) -> dict:
    return {"structure": boundary.value(raw), "stop_reason": ""}


def fallback(reason: str) -> dict:
    return {"structure": None, "stop_reason": boundary.LINE_SCRIPT}


if __name__ == "__main__":
    boundary.run(lambda: relayed(os.environ.get("INPUTS_STRUCTURE")), fallback)

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正の後に、案の直しを差し込むかを決めるノード after-fix（docs/design.md の「メイングラフ」の「順と承認ノード」の 7）。

when: は配列が空かを比べられないので、ここで数える。fix の返りの replan_items（裁定が誤りとした計画の項目）が空でなければ案の直し。
線に差し込みが 1 つしか無いので、1 run に 1 度。再審を差し込むかは、2 度目の修正の後の節 fixed が両方の修正役の異議で決める
（元 works/darkfactory/darkfactory.yaml:827。再審は案の直しと 2 度目の修正の後）。
例外で決められなかった時は止めの理由 works:line-script を返し、fixed がそれを読んで後ろ（試験の関門から先）へ進めない。

入力（with:）: replan_items（fix の返り）
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402


def decide(replan_items: list) -> dict:
    return {"replan": bool(replan_items), "stop_reason": ""}


def fallback(reason: str) -> dict:
    return {"replan": False, "stop_reason": boundary.LINE_SCRIPT}


if __name__ == "__main__":
    boundary.run(lambda: decide(boundary.items(os.environ.get("INPUTS_REPLAN_ITEMS"))), fallback)

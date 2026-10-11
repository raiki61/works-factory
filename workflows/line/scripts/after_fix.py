"""修正の後に、案の直しと再審を差し込むかを決める節 after-fix（docs/design.md の「線」の「順と関所」の 7）。

when: は配列が空かを比べられないので、ここで数える。fix の返りの replan_items（裁定が誤りとした計画の項目）が空でなければ案の直し、
objection（修正役の異議）が空でなければ再審。どちらも線に差し込みが 1 つずつしか無いので、1 run に 1 度。
例外で決められなかった時は止めの理由 works:line-script を返し、fixed がそれを読んで後ろ（試験の関門から先）へ進めない。

入力（with:）: replan_items・objection（fix の返り）
"""
import os

import linekit


def decide(replan_items: list, objection: str) -> dict:
    return {"replan": bool(replan_items), "rejudge": bool(objection.strip()), "stop_reason": ""}


def fallback(reason: str) -> dict:
    return {"replan": False, "rejudge": False, "stop_reason": linekit.LINE_SCRIPT}


if __name__ == "__main__":
    linekit.run(lambda: decide(linekit.items(os.environ.get("INPUTS_REPLAN_ITEMS")), linekit.text(os.environ.get("INPUTS_OBJECTION"))),
                fallback)

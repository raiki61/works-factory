"""計画の往復の返りを往復の外で返し直す節 planned（埋め P2）。collect は計画の往復の返りをここから読む。

往復の中の節が落ちると plan-rounds も落ち、落ちた節の出力は `{from, if_skipped}` でも読めない（止めた Archon の dag-executor.ts の
resolveBindingDirective）ので、collect が $plan-rounds.output を直に読むと collect も落ち、報告が出ない。plan-rounds の後ろの
この節は、plan-rounds が落ちても飛ばされても飛ばされ、飛ばされた節は if_skipped に落ちる。

入力（with:）: plan-rounds の返り（plan-out の欄。plan の 6 つ・plan-review の 7 つ・stop_reason）
"""
import os

import linekit
import plan_out

FIELDS = (*plan_out.PLAN, *plan_out.REVIEW, "stop_reason")


def from_env() -> dict:
    return {key: linekit.field(key, os.environ.get(f"INPUTS_{key.upper()}")) for key in FIELDS}


def fallback(reason: str) -> dict:
    return {**{key: None for key in FIELDS}, "stop_reason": linekit.LINE_SCRIPT}


if __name__ == "__main__":
    linekit.run(from_env, fallback)

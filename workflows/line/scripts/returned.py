# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""ブロックと計画の往復の返りを受け直す受け皿の節（<include の id>-out と plan-rounds-out）。collect は返りをここから読む。

ブロックの返す節（や往復の中の節）が落ちると、その出力は `{from, if_skipped}` でも読めない（止めた Archon の dag-executor.ts の
resolveBindingDirective は落ちた節を if_skipped に落とさない）ので、collect が返りを直に読むと collect も落ち、報告が出ない。
受け皿は既定の trigger_rule（all_success）で受ける節の後ろに置くので、受ける節が落ちても飛ばされても飛ばされ、飛ばされた受け皿は
collect の if_skipped: null に落ちる。走った時は受けた欄を got に組んで返す（字の欄は字のまま。linekit.field）。

入力（with:）: block（下の SHAPES の名）と、その返りの欄（`$<受ける節>.output.<欄>`）
"""
import os

import fixed
import linekit
import plan_out

SHAPES = {
    "test_gate": ("mode", "ok", "green", "red_cause", "baseline", "fingerprint", "evidence"),
    "judge": ("ready", "stop_reason", "units", "judgment", "purpose", "world", "spec", "out_of_purpose", "rejudge_verdict"),
    "plan": plan_out.PLAN,
    "plan_review": plan_out.REVIEW,
    "plan_rounds": (*plan_out.PLAN, *plan_out.REVIEW, "stop_reason"),
    "fix": fixed.FIELDS,
    "eyes": ("ok", "r1", "r2", "r3", "r4", "questions", "premise_check", "structure_after", "protected_hits"),
    "merge": ("mode", "ok", "hash", "diff", "protected_hits", "reason"),
}


def returned(block: str, read) -> dict:
    return {"got": {key: linekit.field(key, read(key)) for key in SHAPES[block]}, "stop_reason": ""}


def from_env() -> dict:
    return returned(os.environ.get("INPUTS_BLOCK"), lambda key: os.environ.get(f"INPUTS_{key.upper()}"))


def fallback(reason: str) -> dict:
    return {"got": None, "stop_reason": linekit.LINE_SCRIPT}


if __name__ == "__main__":
    linekit.run(from_env, fallback)

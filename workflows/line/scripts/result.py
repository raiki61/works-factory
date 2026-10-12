# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""線の返す節 result（線の returns: result・outcome_field: fixed）。

report の返りを受けて返し、結末の語が fixed・fixed_needs_check の時に fixed を真にする。report が届かなければ（report の中の節が
落ちた）結末の語は空で、fixed は偽。
差分を当てる殻 bin/apply と通しの試験が読む欄を、collect が集めた返りから足す（merge の返りを直に読むと、merge の返す節が落ちた時に
線の返りまで落ちる）: apply（merge-apply の {ok, hash, diff, reason}。飛ばされたら null）・sealed（merge-seal の {ok, hash, diff}。
飛ばされたら null）・r2_status（独立の目の R2 の status。省いた・飛ばされたら null）・final_answer（最後の関所の答え {decision, text}。
関所が開かなかったら null）。

入力（with:）: report の返りの欄と、collect の merge_apply・merge_seal・eyes・gate_final（どれも `{from, if_skipped: null}`）
"""
import os

import linekit

FIXED = ("fixed", "fixed_needs_check")
APPLY = ("ok", "hash", "diff", "reason")
SEALED = ("ok", "hash", "diff")


def pick(got, keys) -> dict | None:
    return {key: got.get(key) for key in keys} if isinstance(got, dict) else None


def result(got: dict, line: dict | None = None) -> dict:
    line = line or {}
    r2 = (line.get("eyes") or {}).get("r2") if isinstance(line.get("eyes"), dict) else None
    answer = line.get("gate_final")
    return {**got, "fixed": got["outcome"] in FIXED, "apply": pick(line.get("merge_apply"), APPLY),
            "sealed": pick(line.get("merge_seal"), SEALED), "r2_status": r2.get("status") if isinstance(r2, dict) else None,
            "final_answer": answer if isinstance(answer, dict) else None}


def from_env() -> dict:
    return {
        "ok": linekit.value(os.environ.get("INPUTS_OK")),
        "outcome": linekit.text(os.environ.get("INPUTS_OUTCOME")),
        "stop_reason": linekit.text(os.environ.get("INPUTS_STOP_REASON")),
        "report": linekit.value(os.environ.get("INPUTS_REPORT")),
        "report_ai": linekit.value(os.environ.get("INPUTS_REPORT_AI")),
        "next_request": linekit.value(os.environ.get("INPUTS_NEXT_REQUEST")),
        "prior_failures": linekit.value(os.environ.get("INPUTS_PRIOR_FAILURES")),
    }


def line_of_env() -> dict:
    return {key: linekit.value(os.environ.get(f"INPUTS_{key.upper()}")) for key in ("merge_apply", "merge_seal", "eyes", "gate_final")}


def fallback(reason: str) -> dict:
    return {"fixed": False, "ok": False, "outcome": "", "stop_reason": linekit.LINE_SCRIPT, "report": None, "report_ai": None,
            "next_request": None, "prior_failures": None, "apply": None, "sealed": None, "r2_status": None, "final_answer": None}


if __name__ == "__main__":
    linekit.run(lambda: result(from_env(), line_of_env()), fallback)

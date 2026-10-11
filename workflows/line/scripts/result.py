# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""線の返す節 result（線の returns: result・outcome_field: fixed）。

report の返りを受けて返し、結末の語が fixed・fixed_needs_check の時に fixed を真にする。report が届かなければ（report の中の節が
落ちた）結末の語は空で、fixed は偽。

入力（with:）: report の返りの欄（`{from, if_skipped: null}`）
"""
import os

import linekit

FIXED = ("fixed", "fixed_needs_check")


def result(got: dict) -> dict:
    return {**got, "fixed": got["outcome"] in FIXED}


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


def fallback(reason: str) -> dict:
    return {"fixed": False, "ok": False, "outcome": "", "stop_reason": linekit.LINE_SCRIPT, "report": None, "report_ai": None,
            "next_request": None, "prior_failures": None}


if __name__ == "__main__":
    linekit.run(lambda: result(from_env()), fallback)

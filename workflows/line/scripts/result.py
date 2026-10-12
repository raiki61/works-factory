# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""線の返す節 result（線の returns: result・outcome_field: fixed）。

report の返りを受けて返し、結末の語が fixed・fixed_needs_check の時に fixed を真にする。report が届かなければ（report の中の節が
落ちた）結末の語は空で、fixed は偽。
返す節は落ちない: 境の口を読めない時も、標準ライブラリだけで fallback の返りを書く（止めの理由は LINE_SCRIPT。境の口の
LINE_SCRIPT の写しで、lib/tests/test_stopby.py が突き合わせる）。

入力（with:）: report の返りの欄（`{from, if_skipped: null}`）
"""
import json
import os
import sys
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    unread = None
except Exception as error:   # 返す節は落ちない（上の docstring）
    boundary, unread = None, error

FIXED = ("fixed", "fixed_needs_check")
LINE_SCRIPT = "works:line-script"


def result(got: dict) -> dict:
    return {**got, "fixed": got["outcome"] in FIXED}


def from_env() -> dict:
    return {
        "ok": boundary.value(os.environ.get("INPUTS_OK")),
        "outcome": boundary.text(os.environ.get("INPUTS_OUTCOME")),
        "stop_reason": boundary.text(os.environ.get("INPUTS_STOP_REASON")),
        "report": boundary.value(os.environ.get("INPUTS_REPORT")),
        "report_ai": boundary.value(os.environ.get("INPUTS_REPORT_AI")),
        "next_request": boundary.value(os.environ.get("INPUTS_NEXT_REQUEST")),
        "prior_failures": boundary.value(os.environ.get("INPUTS_PRIOR_FAILURES")),
    }


def fallback(reason: str) -> dict:
    return {"fixed": False, "ok": False, "outcome": "", "stop_reason": LINE_SCRIPT, "report": None, "report_ai": None,
            "next_request": None, "prior_failures": None}


def main() -> None:
    if boundary is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(fallback(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        boundary.run(lambda: result(from_env()), fallback)


if __name__ == "__main__":
    main()

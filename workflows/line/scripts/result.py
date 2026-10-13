# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""メイングラフの出力ノード result（メイングラフの returns: result・outcome_field: fixed）。

report の返りを受けて返し、結末の語が fixed・fixed_needs_check の時に fixed を真にする。report が届かなければ（report の中の節が
落ちた）結末の語は空で、fixed は偽。
差分を当てる殻 bin/apply と通しの試験が読む欄を、collect が集めた返りから足す（merge の返りを直に読むと、merge の返す節が落ちた時に
メイングラフの返りまで落ちる）: apply（merge-apply の {ok, hash, diff, reason}。飛ばされたら null）・sealed（merge-seal の
{ok, hash, diff}。飛ばされたら null）・r2_status（独立の目の R2 の status。省いた・飛ばされたら null）・final_answer（最後の関所の
答え {decision, text, asked}。関所が開かなかったら null）。
後始末の節 sweep-children の返り {cleaned, left, error} を欄 children に載せる（節が飛ばされたら null）。
返す節は落ちない: 境の口を読めない時も、標準ライブラリだけで fallback の返りを書く（止めの理由は LINE_SCRIPT。境の口の
LINE_SCRIPT の写しで、lib/tests/test_stopby.py が突き合わせる）。

入力（with:）: report の返りの欄と、collect の merge_apply・merge_seal・eyes・gate_final と、sweep-children の返り children
（どれも `{from, if_skipped: null}`）
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
APPLY = ("ok", "hash", "diff", "reason")
SEALED = ("ok", "hash", "diff")
COLLECTED = ("merge_apply", "merge_seal", "eyes", "gate_final")


def pick(got, keys) -> dict | None:
    return {key: got.get(key) for key in keys} if isinstance(got, dict) else None


def result(got: dict, line: dict, children) -> dict:
    r2 = (line.get("eyes") or {}).get("r2") if isinstance(line.get("eyes"), dict) else None
    answer = line.get("gate_final")
    return {**got, "fixed": got["outcome"] in FIXED, "apply": pick(line.get("merge_apply"), APPLY),
            "sealed": pick(line.get("merge_seal"), SEALED), "r2_status": r2.get("status") if isinstance(r2, dict) else None,
            "final_answer": answer if isinstance(answer, dict) else None,
            "children": children if isinstance(children, dict) else None}


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


def line_of_env() -> dict:
    return {key: boundary.value(os.environ.get(f"INPUTS_{key.upper()}")) for key in COLLECTED}


def fallback(reason: str) -> dict:
    return {"fixed": False, "ok": False, "outcome": "", "stop_reason": LINE_SCRIPT, "report": None, "report_ai": None,
            "next_request": None, "prior_failures": None, "apply": None, "sealed": None, "r2_status": None, "final_answer": None,
            "children": None}


def main() -> None:
    if boundary is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(fallback(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        boundary.run(lambda: result(from_env(), line_of_env(), boundary.value(os.environ.get("INPUTS_CHILDREN"))), fallback)


if __name__ == "__main__":
    main()

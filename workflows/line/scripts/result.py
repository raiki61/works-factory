# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""line の返す node result（returns: result・outcome_field: fixed。docs/design/line.md の 1.2 の出力。欄の名は今のまま）。

report の返りを受けて返し、結末の語が fixed・fixed_needs_check の時に fixed を真にする。report の返りの machine・human を今の名
report・report_ai で写す（report の設計書の 1.6）。report の返りの detail（詳しい報告 report-detail.md の pointer）と report（報告の行の配列）は、人がどこを開けばよいかと
報告の要点を line の返りで見られるように report_detail・report_lines で写す（line の返りを読むのは人と起動の殻）。
report が届かなければ（report の中の node が落ちた）結末の語は空で、fixed は偽。
差分を当てる殻 bin/apply・chain・通しの試験が読む欄を、受け皿の got から足す（merge の返りを直に読むと、merge の返す node が落ちた時に
line の返りまで落ちる）: apply（merge-apply の {ok, hash, diff, reason}。飛ばされたら null）・sealed（merge-seal の {ok, hash, diff}）・
r2_status（独立の目の R2 の status。省いた・飛ばされたら null）・final_answer（最後の承認ノードの答え {decision, text, asked}。開かなかったら
null）・spec_questions（仕様の照らしが残した承認し直すかの問いの数。照らせなかった時の問いも数える。bin/apply は止めの語でなくこの数を読む）・
children（後始末の node sweep-children の返り {cleaned, left, error}。飛ばされたら null）。
返す node は落ちない: 共通の口を読めない時も、標準ライブラリだけで fallback の返りを書く（止めの語は works:line-script。
src/guard.py の LINE_SCRIPT と同じ字で、tests/blocks/line/test_scripts_misc.py が突き合わせる）。

入力（with:）: report（report の返りまるごと）・merge_apply・merge_seal・eyes・spec_check（受け皿の got）・answer_final（最後の承認ノードの
答え）・children（sweep-children の返り）。どれも `{from, if_skipped: null}`
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
try:
    sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
    import ports
    unread = None
except Exception as error:   # 返す node は落ちない（上の docstring）
    ports, unread = None, error

FIXED = ("fixed", "fixed_needs_check")
LINE_SCRIPT = "works:line-script"
APPLY = ("ok", "hash", "diff", "reason")
SEALED = ("ok", "hash", "diff")
REPORT = ("ok", "outcome", "stop_reason", "machine", "human", "detail", "next_request", "prior_failures", "report")


def pick(got, keys) -> dict | None:
    return {key: got.get(key) for key in keys} if isinstance(got, dict) else None


def result(report, *, merge_apply, merge_seal, eyes, spec_check, answer_final, children) -> dict:
    got = report if isinstance(report, dict) else {}
    outcome = got.get("outcome") if isinstance(got.get("outcome"), str) else ""
    r2 = eyes.get("r2") if isinstance(eyes, dict) else None
    questions = spec_check.get("questions") if isinstance(spec_check, dict) else None
    lines = got.get("report")
    return {"fixed": outcome in FIXED, "ok": got.get("ok") is True, "outcome": outcome,
            "stop_reason": got.get("stop_reason") if isinstance(got.get("stop_reason"), str) else "",
            "report": got.get("machine"), "report_ai": got.get("human"), "report_detail": got.get("detail"),
            "report_lines": lines if isinstance(lines, list) else [], "next_request": got.get("next_request"),
            "prior_failures": got.get("prior_failures"), "apply": pick(merge_apply, APPLY), "sealed": pick(merge_seal, SEALED),
            "r2_status": r2.get("status") if isinstance(r2, dict) else None,
            "final_answer": answer_final if isinstance(answer_final, dict) else None,
            "spec_questions": len(questions) if isinstance(questions, list) else 0,
            "children": children if isinstance(children, dict) else None}


def compute() -> dict:
    report = ports.picked(os.environ.get("INPUTS_REPORT"), REPORT)
    raw = {"merge_apply": os.environ.get("INPUTS_MERGE_APPLY"),
           "merge_seal": os.environ.get("INPUTS_MERGE_SEAL"), "eyes": os.environ.get("INPUTS_EYES"),
           "spec_check": os.environ.get("INPUTS_SPEC_CHECK"), "answer_final": os.environ.get("INPUTS_ANSWER_FINAL"),
           "children": os.environ.get("INPUTS_CHILDREN")}
    value = ports.polyfill("skip_value").value
    return result(None if report is None else dict(report), **{name: value(got) for name, got in raw.items()})


def fallback(reason: str) -> dict:
    return {"fixed": False, "ok": False, "outcome": "", "stop_reason": LINE_SCRIPT, "report": None, "report_ai": None,
            "report_detail": None, "report_lines": [], "next_request": None, "prior_failures": None, "apply": None, "sealed": None, "r2_status": None, "final_answer": None,
            "spec_questions": 0, "children": None}



def main() -> None:
    if ports is None:
        print(f"{type(unread).__name__}: {unread}", file=sys.stderr)
        print(json.dumps(fallback(""), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        ports.run(compute, fallback)


if __name__ == "__main__":   # 試験は名で読んで main を直に呼ぶ
    main()

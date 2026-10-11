"""全部のブロックと関所と返しの節の返りを報告へ渡す形に集める返しの節 collect（埋め P2。trigger_rule: all_done）。

ブロックの返りは欄ごとに `{from: "$<include の id>.output.<欄>", if_skipped: null}` で受け、include の id ごとの object に
組み直す。飛ばされた include（欄が全部 null）は null。受ける欄の名は下の SHAPES が持ち、with: の鍵と同じなのは
tests/workflows/test_line.py の LineWiringCase が照らす（読み手の無い欄の試験 tests/layers/test_block_returns.py は with: だけを見る）。
計画の往復の plan と plan-review は planned から読む（$plan-rounds.output は往復の中の節が落ちると読めない。planned の docstring）。
止めの理由は、始めの節・関所の答えの返しの節（関所の前の止め needs-human も運ぶ）・線の script の節（例外の works:line-script）の、
線の順で最初の空でない物。
report の with: は $collect.output.<欄> だけを読む。

入力（with:）: <include の id>_<欄>・start_<欄>・gate_<関所>・stop_<所>・線の節の欄（下の SHAPES・line_of_env）
"""
import os

import fixed
import linekit
import plan_out


def group(raw: dict):
    got = {key: linekit.field(key, value) for key, value in raw.items()}
    return None if all(value is None for value in got.values()) else got


def collect(blocks: dict, line: dict) -> dict:
    out = {name: group(raw) for name, raw in blocks.items()}
    stops = [linekit.text(raw) for raw in line["stops"]]
    out.update({
        "start": linekit.value(line["start"]),
        "prior_failures": linekit.value(line["prior_failures"]),
        **{name: linekit.value(raw) for name, raw in line["gates"].items()},
        "stop_reason": next((s for s in stops if s), ""),
        "deferred_questions": linekit.items(line["deferred_questions"]),
        "widened": linekit.items(line["widened"]),
        "final_reasons": linekit.items(line["final_reasons"]),
        "judged": group(line["judged"]),
        "fixed": group(line["fixed"]),
        "redepth": group(line["redepth"]),
    })
    return out


TEST_GATE = ("mode", "ok", "green", "red_cause", "baseline", "fingerprint", "evidence")
JUDGE = ("ready", "stop_reason", "units", "judgment", "purpose", "world", "spec", "out_of_purpose", "rejudge_verdict")
EYES = ("ok", "r1", "r2", "r3", "r4", "questions", "premise_check", "structure_after", "protected_hits")
MERGE = ("mode", "ok", "hash", "diff", "protected_hits", "reason")
SHAPES = {
    "test_gate_base": TEST_GATE,
    "judge": JUDGE,
    "plan": plan_out.PLAN,
    "plan_review": plan_out.REVIEW,
    "fix": fixed.FIELDS,
    "rejudge": JUDGE,
    "replan": plan_out.PLAN,
    "replan_review": plan_out.REVIEW,
    "refix": fixed.FIELDS,
    "test_gate_final": TEST_GATE,
    "eyes": EYES,
    "merge_seal": MERGE,
    "merge_apply": MERGE,
}
STOPS = ("start", "answer_start", "plan", "before_fix", "after_fix", "judged", "replan", "fixed", "redepth", "final")


def blocks_of_env() -> dict:
    return {name: {key: os.environ.get(f"INPUTS_{name}_{key}".upper()) for key in keys} for name, keys in SHAPES.items()}


def line_of_env() -> dict:
    return {
        "start": os.environ.get("INPUTS_START_RECORD"),
        "prior_failures": os.environ.get("INPUTS_START_PRIOR_FAILURES"),
        "stops": [os.environ.get(f"INPUTS_STOP_{place.upper()}") for place in STOPS],
        "gates": {
            "gate_start": os.environ.get("INPUTS_GATE_START"),
            "gate_before_fix": os.environ.get("INPUTS_GATE_BEFORE_FIX"),
            "gate_replan": os.environ.get("INPUTS_GATE_REPLAN"),
            "gate_final": os.environ.get("INPUTS_GATE_FINAL"),
        },
        "deferred_questions": os.environ.get("INPUTS_DEFERRED_QUESTIONS"),
        "widened": os.environ.get("INPUTS_WIDENED"),
        "final_reasons": os.environ.get("INPUTS_FINAL_REASONS"),
        "judged": {
            "rejudged": os.environ.get("INPUTS_JUDGED_REJUDGED"),
            "new_open_units": os.environ.get("INPUTS_JUDGED_NEW_OPEN_UNITS"),
            "lowered": os.environ.get("INPUTS_JUDGED_LOWERED"),
        },
        "fixed": {
            "conflicts": os.environ.get("INPUTS_FIXED_CONFLICTS"),
            "refixed": os.environ.get("INPUTS_FIXED_REFIXED"),
        },
        "redepth": {
            "depth": os.environ.get("INPUTS_REDEPTH_DEPTH"),
            "skip_optional": os.environ.get("INPUTS_REDEPTH_SKIP_OPTIONAL"),
            "raised": os.environ.get("INPUTS_REDEPTH_RAISED"),
        },
    }


def fallback(reason: str) -> dict:
    return {**{name: None for name in SHAPES}, "start": None, "prior_failures": None, "gate_start": None, "gate_before_fix": None,
            "gate_replan": None, "gate_final": None, "stop_reason": linekit.LINE_SCRIPT, "deferred_questions": [], "widened": [],
            "final_reasons": [reason], "judged": None, "fixed": None, "redepth": None}


if __name__ == "__main__":
    linekit.run(lambda: collect(blocks_of_env(), line_of_env()), fallback)

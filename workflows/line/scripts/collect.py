"""全部のブロックと関所と返しの節の返りを報告へ渡す形に集める返しの節 collect（埋め P2。trigger_rule: all_done）。

ブロックの返りは欄ごとに `{from: "$<include の id>.output.<欄>", if_skipped: null}` で受け（欄ごとに受けるので、読み手の無い欄の
試験 tests/layers/test_block_returns.py が働く）、include の id ごとの object に組み直す。飛ばされた include（欄が全部 null）は null。
計画の往復の plan と plan-review は $plan-rounds.output から読む（loop_group の中の節は外から見えない）。
止めの理由は、始めの節と関所の答えの返しの節（関所の前の止め needs-human も運ぶ）の最初の空でない物。
report の with: は $collect.output.<欄> だけを読む。

入力（with:）: <include の id>_<欄>・start_<欄>・gate_<関所>・stop_<所>・線の節の欄（下の from_env）
"""
import os

import linekit

STRINGS = ("mode", "red_cause", "stop_reason", "objection", "rejudge_verdict", "hash", "reason")


def group(raw: dict):
    got = {key: linekit.skip_value.text(value) if key in STRINGS else linekit.value(value) for key, value in raw.items()}
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


BLOCKS = {
    "test_gate_base": {
        "mode": os.environ.get("INPUTS_TEST_GATE_BASE_MODE"),
        "ok": os.environ.get("INPUTS_TEST_GATE_BASE_OK"),
        "green": os.environ.get("INPUTS_TEST_GATE_BASE_GREEN"),
        "red_cause": os.environ.get("INPUTS_TEST_GATE_BASE_RED_CAUSE"),
        "baseline": os.environ.get("INPUTS_TEST_GATE_BASE_BASELINE"),
        "fingerprint": os.environ.get("INPUTS_TEST_GATE_BASE_FINGERPRINT"),
        "evidence": os.environ.get("INPUTS_TEST_GATE_BASE_EVIDENCE"),
    },
    "judge": {
        "ready": os.environ.get("INPUTS_JUDGE_READY"),
        "stop_reason": os.environ.get("INPUTS_JUDGE_STOP_REASON"),
        "units": os.environ.get("INPUTS_JUDGE_UNITS"),
        "judgment": os.environ.get("INPUTS_JUDGE_JUDGMENT"),
        "purpose": os.environ.get("INPUTS_JUDGE_PURPOSE"),
        "world": os.environ.get("INPUTS_JUDGE_WORLD"),
        "spec": os.environ.get("INPUTS_JUDGE_SPEC"),
        "out_of_purpose": os.environ.get("INPUTS_JUDGE_OUT_OF_PURPOSE"),
        "rejudge_verdict": os.environ.get("INPUTS_JUDGE_REJUDGE_VERDICT"),
    },
    "plan": {
        "ready": os.environ.get("INPUTS_PLAN_READY"),
        "plan": os.environ.get("INPUTS_PLAN_PLAN"),
        "structure": os.environ.get("INPUTS_PLAN_STRUCTURE"),
        "ripple": os.environ.get("INPUTS_PLAN_RIPPLE"),
        "depth": os.environ.get("INPUTS_PLAN_DEPTH"),
        "round": os.environ.get("INPUTS_PLAN_ROUND"),
    },
    "plan_review": {
        "pass": os.environ.get("INPUTS_PLAN_REVIEW_PASS"),
        "stalled": os.environ.get("INPUTS_PLAN_REVIEW_STALLED"),
        "review": os.environ.get("INPUTS_PLAN_REVIEW_REVIEW"),
        "design": os.environ.get("INPUTS_PLAN_REVIEW_DESIGN"),
        "gate_axes": os.environ.get("INPUTS_PLAN_REVIEW_GATE_AXES"),
        "ask_human": os.environ.get("INPUTS_PLAN_REVIEW_ASK_HUMAN"),
        "questions": os.environ.get("INPUTS_PLAN_REVIEW_QUESTIONS"),
    },
    "fix": {
        "done": os.environ.get("INPUTS_FIX_DONE"),
        "units": os.environ.get("INPUTS_FIX_UNITS"),
        "groups": os.environ.get("INPUTS_FIX_GROUPS"),
        "conflicts": os.environ.get("INPUTS_FIX_CONFLICTS"),
        "replan_items": os.environ.get("INPUTS_FIX_REPLAN_ITEMS"),
        "objection": os.environ.get("INPUTS_FIX_OBJECTION"),
        "diff": os.environ.get("INPUTS_FIX_DIFF"),
        "allowed_test_changes": os.environ.get("INPUTS_FIX_ALLOWED_TEST_CHANGES"),
        "changed": os.environ.get("INPUTS_FIX_CHANGED"),
        "delta_review": os.environ.get("INPUTS_FIX_DELTA_REVIEW"),
    },
    "rejudge": {
        "ready": os.environ.get("INPUTS_REJUDGE_READY"),
        "stop_reason": os.environ.get("INPUTS_REJUDGE_STOP_REASON"),
        "units": os.environ.get("INPUTS_REJUDGE_UNITS"),
        "judgment": os.environ.get("INPUTS_REJUDGE_JUDGMENT"),
        "purpose": os.environ.get("INPUTS_REJUDGE_PURPOSE"),
        "world": os.environ.get("INPUTS_REJUDGE_WORLD"),
        "spec": os.environ.get("INPUTS_REJUDGE_SPEC"),
        "out_of_purpose": os.environ.get("INPUTS_REJUDGE_OUT_OF_PURPOSE"),
        "rejudge_verdict": os.environ.get("INPUTS_REJUDGE_REJUDGE_VERDICT"),
    },
    "replan": {
        "ready": os.environ.get("INPUTS_REPLAN_READY"),
        "plan": os.environ.get("INPUTS_REPLAN_PLAN"),
        "structure": os.environ.get("INPUTS_REPLAN_STRUCTURE"),
        "ripple": os.environ.get("INPUTS_REPLAN_RIPPLE"),
        "depth": os.environ.get("INPUTS_REPLAN_DEPTH"),
        "round": os.environ.get("INPUTS_REPLAN_ROUND"),
    },
    "replan_review": {
        "pass": os.environ.get("INPUTS_REPLAN_REVIEW_PASS"),
        "stalled": os.environ.get("INPUTS_REPLAN_REVIEW_STALLED"),
        "review": os.environ.get("INPUTS_REPLAN_REVIEW_REVIEW"),
        "design": os.environ.get("INPUTS_REPLAN_REVIEW_DESIGN"),
        "gate_axes": os.environ.get("INPUTS_REPLAN_REVIEW_GATE_AXES"),
        "ask_human": os.environ.get("INPUTS_REPLAN_REVIEW_ASK_HUMAN"),
        "questions": os.environ.get("INPUTS_REPLAN_REVIEW_QUESTIONS"),
    },
    "refix": {
        "done": os.environ.get("INPUTS_REFIX_DONE"),
        "units": os.environ.get("INPUTS_REFIX_UNITS"),
        "groups": os.environ.get("INPUTS_REFIX_GROUPS"),
        "conflicts": os.environ.get("INPUTS_REFIX_CONFLICTS"),
        "replan_items": os.environ.get("INPUTS_REFIX_REPLAN_ITEMS"),
        "objection": os.environ.get("INPUTS_REFIX_OBJECTION"),
        "diff": os.environ.get("INPUTS_REFIX_DIFF"),
        "allowed_test_changes": os.environ.get("INPUTS_REFIX_ALLOWED_TEST_CHANGES"),
        "changed": os.environ.get("INPUTS_REFIX_CHANGED"),
        "delta_review": os.environ.get("INPUTS_REFIX_DELTA_REVIEW"),
    },
    "test_gate_final": {
        "mode": os.environ.get("INPUTS_TEST_GATE_FINAL_MODE"),
        "ok": os.environ.get("INPUTS_TEST_GATE_FINAL_OK"),
        "green": os.environ.get("INPUTS_TEST_GATE_FINAL_GREEN"),
        "red_cause": os.environ.get("INPUTS_TEST_GATE_FINAL_RED_CAUSE"),
        "baseline": os.environ.get("INPUTS_TEST_GATE_FINAL_BASELINE"),
        "fingerprint": os.environ.get("INPUTS_TEST_GATE_FINAL_FINGERPRINT"),
        "evidence": os.environ.get("INPUTS_TEST_GATE_FINAL_EVIDENCE"),
    },
    "eyes": {
        "ok": os.environ.get("INPUTS_EYES_OK"),
        "r1": os.environ.get("INPUTS_EYES_R1"),
        "r2": os.environ.get("INPUTS_EYES_R2"),
        "r3": os.environ.get("INPUTS_EYES_R3"),
        "r4": os.environ.get("INPUTS_EYES_R4"),
        "questions": os.environ.get("INPUTS_EYES_QUESTIONS"),
        "premise_check": os.environ.get("INPUTS_EYES_PREMISE_CHECK"),
        "structure_after": os.environ.get("INPUTS_EYES_STRUCTURE_AFTER"),
        "protected_hits": os.environ.get("INPUTS_EYES_PROTECTED_HITS"),
    },
    "merge_seal": {
        "mode": os.environ.get("INPUTS_MERGE_SEAL_MODE"),
        "ok": os.environ.get("INPUTS_MERGE_SEAL_OK"),
        "hash": os.environ.get("INPUTS_MERGE_SEAL_HASH"),
        "diff": os.environ.get("INPUTS_MERGE_SEAL_DIFF"),
        "protected_hits": os.environ.get("INPUTS_MERGE_SEAL_PROTECTED_HITS"),
        "reason": os.environ.get("INPUTS_MERGE_SEAL_REASON"),
    },
    "merge_apply": {
        "mode": os.environ.get("INPUTS_MERGE_APPLY_MODE"),
        "ok": os.environ.get("INPUTS_MERGE_APPLY_OK"),
        "hash": os.environ.get("INPUTS_MERGE_APPLY_HASH"),
        "diff": os.environ.get("INPUTS_MERGE_APPLY_DIFF"),
        "protected_hits": os.environ.get("INPUTS_MERGE_APPLY_PROTECTED_HITS"),
        "reason": os.environ.get("INPUTS_MERGE_APPLY_REASON"),
    },
}


def line_of_env() -> dict:
    return {
        "start": os.environ.get("INPUTS_START_RECORD"),
        "prior_failures": os.environ.get("INPUTS_START_PRIOR_FAILURES"),
        "stops": [os.environ.get("INPUTS_STOP_START"), os.environ.get("INPUTS_STOP_ANSWER_START"),
                  os.environ.get("INPUTS_STOP_BEFORE_FIX"), os.environ.get("INPUTS_STOP_REPLAN"),
                  os.environ.get("INPUTS_STOP_FINAL")],
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
    return {**{name: None for name in BLOCKS}, "start": None, "prior_failures": None, "gate_start": None, "gate_before_fix": None,
            "gate_replan": None, "gate_final": None, "stop_reason": linekit.LINE_SCRIPT, "deferred_questions": [], "widened": [],
            "final_reasons": [reason], "judged": None, "fixed": None, "redepth": None}


if __name__ == "__main__":
    linekit.run(lambda: collect(BLOCKS, line_of_env()), fallback)

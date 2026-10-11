"""全部のブロックと関所と返しの節の返りを報告へ渡す形に集める返しの節 collect（埋め P2。trigger_rule: all_done）。

ブロックと計画の往復の返りは受け皿の節（returned.py。<include の id>-out・plan-rounds-out）の出力を
`{from: "$<受け皿>.output", if_skipped: null}` で受ける。受けた物の got が、include の id ごとの返りの欄の object になる。
飛ばされた（受ける節が落ちたか飛ばされた）受け皿は null。計画の往復の返りは plan と plan-review の欄に分け、欄が全部 null の方は null。
止めの理由は、始めの節・関所の答えの返しの節（関所の前の止め needs-human も運ぶ）・計画の往復・線の script の節（例外の
works:line-script）の、線の順で最初の空でない物。受け皿の例外の止めはその後ろ。
report の with: は $collect.output.<欄> だけを読む。

入力（with:）: <include の id>（受け皿の出力）・plan_rounds・start_<欄>・gate_<関所>・stop_<所>・線の節の欄（line_of_env）
"""
import os

import linekit
import plan_out

RECEIVED = ("test_gate_base", "judge", "rejudge", "replan", "replan_review", "fix", "refix", "test_gate_final", "eyes",
            "merge_seal", "merge_apply")
STOPS = ("start", "answer_start", "plan", "before_fix", "after_fix", "judged", "replan", "fixed", "redepth", "final")


def group(got: dict | None, keys) -> dict | None:
    part = {key: (got or {}).get(key) for key in keys}
    return None if all(value is None for value in part.values()) else part


def collect(received: dict, line: dict) -> dict:
    taken = {name: linekit.value(raw) for name, raw in received.items()}
    got = {name: (doc or {}).get("got") for name, doc in taken.items()}
    rounds = got.pop("plan_rounds", None)
    stopped = {**{place: linekit.text(raw) for place, raw in line["stops"].items()}, "plan": (rounds or {}).get("stop_reason") or ""}
    stops = [stopped[place] for place in STOPS] + [doc.get("stop_reason") or "" for doc in taken.values() if isinstance(doc, dict)]
    return {
        **got,
        "plan": group(rounds, plan_out.PLAN),
        "plan_review": group(rounds, plan_out.REVIEW),
        "start": linekit.value(line["start"]),
        "prior_failures": linekit.value(line["prior_failures"]),
        **{name: linekit.value(raw) for name, raw in line["gates"].items()},
        "stop_reason": next((s for s in stops if s), ""),
        "deferred_questions": linekit.items(line["deferred_questions"]),
        "widened": linekit.items(line["widened"]),
        "final_reasons": linekit.items(line["final_reasons"]),
        **{name: group({key: linekit.field(key, raw) for key, raw in fields.items()}, fields)
           for name, fields in line["nodes"].items()},
    }


def received_of_env() -> dict:
    return {name: os.environ.get(f"INPUTS_{name.upper()}") for name in (*RECEIVED, "plan_rounds")}


def line_of_env() -> dict:
    return {
        "start": os.environ.get("INPUTS_START_RECORD"),
        "prior_failures": os.environ.get("INPUTS_START_PRIOR_FAILURES"),
        "stops": {place: os.environ.get(f"INPUTS_STOP_{place.upper()}") for place in STOPS if place != "plan"},
        "gates": {
            "gate_start": os.environ.get("INPUTS_GATE_START"),
            "gate_before_fix": os.environ.get("INPUTS_GATE_BEFORE_FIX"),
            "gate_replan": os.environ.get("INPUTS_GATE_REPLAN"),
            "gate_final": os.environ.get("INPUTS_GATE_FINAL"),
        },
        "deferred_questions": os.environ.get("INPUTS_DEFERRED_QUESTIONS"),
        "widened": os.environ.get("INPUTS_WIDENED"),
        "final_reasons": os.environ.get("INPUTS_FINAL_REASONS"),
        "nodes": {
            "judged": {key: os.environ.get(f"INPUTS_JUDGED_{key.upper()}")
                       for key in ("rejudged", "new_open_units", "lowered", "unnamed_changed", "unread")},
            "fixed": {key: os.environ.get(f"INPUTS_FIXED_{key.upper()}") for key in ("conflicts", "refixed")},
            "redepth": {key: os.environ.get(f"INPUTS_REDEPTH_{key.upper()}") for key in ("depth", "skip_optional", "raised")},
        },
    }


def fallback(reason: str) -> dict:
    return {**{name: None for name in RECEIVED}, "plan": None, "plan_review": None, "start": None, "prior_failures": None,
            "gate_start": None, "gate_before_fix": None, "gate_replan": None, "gate_final": None, "stop_reason": linekit.LINE_SCRIPT,
            "deferred_questions": [], "widened": [], "final_reasons": [reason], "judged": None, "fixed": None, "redepth": None}


if __name__ == "__main__":
    linekit.run(lambda: collect(received_of_env(), line_of_env()), fallback)
